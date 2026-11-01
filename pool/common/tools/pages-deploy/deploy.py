#!/usr/bin/env python3
r"""deploy.py — 앱 하나를 GitHub Pages repo의 하위 폴더로 내보낸다(그 경로만 commit).

언제: 정적 앱(바닐라 HTML/JS 등)을 <user>.github.io 같은 Pages repo의 자기 하위 폴더로 공개 · 배포할 때.
      Pages repo 하나에 여러 앱이 같이 살므로 `git add -A`를 쓰지 않고 자기 경로만 다룬다.
kind: deploy
status: active

사용:
  python deploy.py CONFIG                 계획만 보인다(기본 = dry-run). 아무것도 바꾸지 않는다
  python deploy.py CONFIG --write         gate → 하위 폴더 통째 교체 → 파일 수 검증 → (카드) → after_copy
  python deploy.py CONFIG --commit        --write + 그 경로만 git add · commit
  python deploy.py CONFIG --push          --commit + push
  옵션: --pages DIR  설정의 pages_repo 대신(또는 환경변수 PAGES_REPO)
        --terms-dir DIR  금지어 폴더(redact_check 기본을 바꿀 때)

종료 코드: 0 = 끝남(또는 dry-run 계획), 1 = gate 차단 · 검증 실패 · after_copy 실패 · git 실패, 2 = 설정 오류 · 금지어 원천 없음.

설정 파일(JSON, 앱 repo에 둔다. 상대 경로는 설정 파일 기준):
{
  "source": "20_src/app",                 내보낼 폴더 (필수)
  "subdir": "apps/voca",                  Pages repo 안의 대상 하위 폴더 (필수, 통째 교체된다)
  "pages_repo": "<old-workspace>",   (또는 --pages / PAGES_REPO)
  "include": ["**/*"],                    source 기준 glob, 기본 전부
  "exclude": ["*.map", "drafts/**"],      빼는 glob (.git · node_modules · __pycache__ · .DS_Store는 늘 뺀다)
  "forbid": [{"pattern": "weakness_db", "why": "비공개 기록 참조"}],   앱 고유의 멈춤 정규식(선택)
  "card": {"name": "...", "description": "...", "url": "https://.../", "repoUrl": "https://..."},  루트 index.html EXTRA_APPS 카드(선택)
  "after_copy": ["node <pool>/common/tools/screen-test/check.mjs --dir {dest} --phone --smoke"],  복사 뒤 검사(선택, {dest} 치환)
  "stamp": true,                          복사본의 상대 .js · .mjs · .css 참조에 ?v=<내용 해시>를 붙인다(선택, 원본은 그대로)
  "live": {"url": "https://<user>.github.io/apps/voca/", "expect": "새로 넣은 문자열", "assets": ["data.js"], "timeout": 600},
                                          --push 뒤 라이브 대기(선택): ?cb=로 캐시를 피해 200 + expect가 보일 때까지
  "commit_message": "voca: deploy"        (선택, 날짜가 붙는다)
}
--live-only: 복사 · commit 없이 라이브 확인만.

gate(첫 단계, 복사 전에): pool `redact-check/redact_check.py`의 금지어 · 로컬 경로 검사 + 설정의 forbid.
하나라도 걸리면 아무것도 복사하지 않고 멈춘다. 금지어 원천을 못 읽으면 통과로 치지 않고 멈춘다(2).
"""
import argparse
import fnmatch
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.expanduser('~'), '.claude', 'workflow', 'tools'))   # WF 공용 도구 설치본
sys.path.insert(1, r'<core>\shared-tools')                                # 설치 전이면 정본
import redact_check  # noqa: E402

ALWAYS_SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv'}
ALWAYS_SKIP_FILES = {'.DS_Store', 'Thumbs.db', 'desktop.ini'}


def die(msg, code=2):
    print('deploy: ' + msg)
    sys.exit(code)


def load_config(path, pages_override):
    if not os.path.isfile(path):
        die('설정 파일이 없다: %s' % path)
    with io.open(path, encoding='utf-8') as f:
        cfg = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    for k in ('source', 'subdir'):
        if not cfg.get(k):
            die('설정에 %s가 없다' % k)
    cfg['source'] = os.path.normpath(os.path.join(base, cfg['source']))
    cfg['pages_repo'] = pages_override or cfg.get('pages_repo') or os.environ.get('PAGES_REPO')
    if not cfg['pages_repo']:
        die('Pages repo가 없다 (설정 pages_repo, --pages, PAGES_REPO 중 하나)')
    cfg['pages_repo'] = os.path.abspath(cfg['pages_repo'])
    sub = cfg['subdir'].replace('\\', '/').strip('/')
    parts = sub.split('/')
    if not sub or any(p in ('', '.', '..', '.git') for p in parts):
        die('subdir가 안전하지 않다: %r' % cfg['subdir'])
    cfg['subdir'] = sub
    cfg['dest'] = os.path.join(cfg['pages_repo'], *parts)
    if not os.path.isdir(cfg['source']):
        die('source 폴더가 없다: %s' % cfg['source'])
    if not os.path.isdir(os.path.join(cfg['pages_repo'], '.git')):
        die('pages_repo가 git repo가 아니다: %s' % cfg['pages_repo'])
    if os.path.commonpath([cfg['source'], cfg['dest']]) == cfg['dest']:
        die('source가 대상 폴더 안에 있다')
    return cfg


def staged_files(cfg):
    """source 기준 상대 경로(/) 목록."""
    inc = cfg.get('include') or ['**/*']
    exc = cfg.get('exclude') or []
    out = []
    for dp, dns, fns in os.walk(cfg['source']):
        dns[:] = sorted(d for d in dns if d not in ALWAYS_SKIP_DIRS)
        for fn in sorted(fns):
            if fn in ALWAYS_SKIP_FILES:
                continue
            rel = os.path.relpath(os.path.join(dp, fn), cfg['source']).replace('\\', '/')
            match = lambda pats: any(fnmatch.fnmatch(rel, p) or (p.startswith('**/') and fnmatch.fnmatch(rel, p[3:])) for p in pats)
            if match(inc) and not match(exc):
                out.append(rel)
    return out


def gate(cfg, files, terms_dir):
    terms = redact_check.load_terms(terms_dir)
    if not terms:
        print('gate: 금지어 원천이 없다 (%s) — 멈춘다' % redact_check.terms_dir(terms_dir))
        return 2
    paths = [os.path.join(cfg['source'], f) for f in files]
    hits = redact_check.scan_paths(paths, terms, True)
    forbid = [(re.compile(x['pattern']), x.get('why', 'forbid')) for x in (cfg.get('forbid') or [])]
    if forbid:
        for p in redact_check.iter_files(paths):
            text = redact_check._read(p)
            for i, ln in enumerate(text.splitlines(), 1):
                for rx, why in forbid:
                    if rx.search(ln):
                        hits.append((p, i, 'forbid', why))
    for f, line, label, masked in hits:
        print('  차단 %s:%d %s %s' % (os.path.relpath(f, cfg['source']), line, label, masked))
    print('gate: 텍스트 %d개 검사, 위반 %d' % (sum(1 for _ in redact_check.iter_files(paths)), len(hits)))
    return 1 if hits else 0


def digest(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def plan(cfg, files):
    dest = cfg['dest']
    new = upd = same = 0
    for rel in files:
        d = os.path.join(dest, rel)
        if not os.path.exists(d):
            new += 1
        elif digest(d) != digest(os.path.join(cfg['source'], rel)):
            upd += 1
        else:
            same += 1
    keep = set(files)
    removed = []
    if os.path.isdir(dest):
        for dp, dns, fns in os.walk(dest):
            for fn in fns:
                rel = os.path.relpath(os.path.join(dp, fn), dest).replace('\\', '/')
                if rel not in keep:
                    removed.append(rel)
    return new, upd, same, removed


_LOCAL_REF = r'(?!https?:|//|#|data:|mailto:|javascript:)'
_HTML_REF = re.compile(r'''((?:src|href)\s*=\s*)(["'])(%s[^"'?#]+\.(?:js|mjs|css))\2''' % _LOCAL_REF)
_JS_SPEC = re.compile(r'''(\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)(['"])(\.{1,2}/[^'"?]+\.m?js)\2''')
_CSS_IMPORT = re.compile(r'''(@import\s+(?:url\()?\s*)(["'])(%s[^"'?#]+\.css)\2''' % _LOCAL_REF)


def stamp_version(cfg, files):
    """내용 해시 하나. Pages는 파일을 약 10분 캐시하므로, 모든 상대 참조에 같은 ?v=를 붙여 옛 · 새 모듈이 섞이지 않게 한다."""
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode() + b'\0')
        with open(os.path.join(cfg['source'], rel), 'rb') as f:
            h.update(f.read() + b'\0')
    return h.hexdigest()[:10]


def stamp_text(rel, text, ver):
    add = lambda m: '%s%s%s?v=%s%s' % (m.group(1), m.group(2), m.group(3), ver, m.group(2))
    ext = os.path.splitext(rel)[1].lower()
    if ext in ('.html', '.htm'):
        return _HTML_REF.sub(add, text)
    if ext in ('.js', '.mjs'):
        return _JS_SPEC.sub(add, text)
    if ext == '.css':
        return _CSS_IMPORT.sub(add, text)
    return text


def replace_dir(cfg, files, ver=None):
    """대상 폴더를 비우고(폴더 자체는 둔다: 미리보기 서버의 cwd일 수 있다) 새로 복사한다. 바뀐(stamp된) 파일 목록을 돌려준다."""
    dest = cfg['dest']
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(dest):
        p = os.path.join(dest, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    stamped = set()
    for rel in files:
        s = os.path.join(cfg['source'], *rel.split('/'))
        d = os.path.join(dest, *rel.split('/'))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if ver and rel.lower().endswith(('.html', '.htm', '.js', '.mjs', '.css')):
            text = io.open(s, encoding='utf-8').read()
            new = stamp_text(rel, text, ver)
            if new != text:
                with io.open(d, 'w', encoding='utf-8', newline='') as f:
                    f.write(new)
                stamped.add(rel)
                continue
        shutil.copyfile(s, d)
    return stamped


def verify(cfg, files, stamped=()):
    """복사 뒤 파일 수와 크기가 같은지(셸 cp -r은 일부만 복사할 수 있다). stamp된 파일은 있는지만 본다."""
    dest = cfg['dest']
    n_dst = sum(len(fns) for _, _, fns in os.walk(dest))
    bad = [rel for rel in files if not os.path.isfile(os.path.join(dest, rel))
           or (rel not in stamped and os.path.getsize(os.path.join(dest, rel)) != os.path.getsize(os.path.join(cfg['source'], rel)))]
    ok = n_dst == len(files) and not bad
    print('verify: source %d · dest %d · 크기 다름 %d · stamp %d → %s' % (len(files), n_dst, len(bad), len(stamped), 'OK' if ok else 'MISMATCH'))
    return ok


def wait_live(live):
    """?cb=로 캐시를 피해 페이지(와 assets)가 200이고 expect 문자열이 보일 때까지 기다린다."""
    import urllib.request
    url = live['url']
    expect = live.get('expect')
    assets = [url.rstrip('/') + '/' + a.lstrip('/') for a in live.get('assets') or []]
    deadline = time.time() + int(live.get('timeout', 600))
    last = ''
    while time.time() < deadline:
        cb = '%scb=%d' % ('&' if '?' in url else '?', int(time.time()))
        try:
            with urllib.request.urlopen(url + cb, timeout=20) as r:
                body = r.read().decode('utf-8', errors='replace')
            if expect and expect not in body:
                last = 'expect 문자열이 아직 없음'
            else:
                bad = []
                for a in assets:
                    try:
                        with urllib.request.urlopen(a + ('&' if '?' in a else '?') + cb[1:], timeout=20) as r:
                            if r.status != 200:
                                bad.append('%s %s' % (r.status, a))
                    except Exception as e:
                        bad.append('%s %s' % (e, a))
                if not bad:
                    print('live: OK %s' % url)
                    return 0
                last = '; '.join(bad)
        except Exception as e:
            last = str(e)
        time.sleep(15)
    print('live: 시간 안에 확인하지 못했다 (%s)' % last)
    return 1


def upsert_card(index_path, card, updated):
    text = io.open(index_path, encoding='utf-8').read()
    url = card['url']
    entry = ('      {\n'
             '        name: %s,\n'
             '        description: %s,\n'
             "        url: '%s',\n"
             "        repoUrl: '%s',\n"
             "        updated: '%s',\n"
             '      },\n') % (json.dumps(card['name'], ensure_ascii=False), json.dumps(card['description'], ensure_ascii=False),
                               url, card.get('repoUrl', ''), updated)
    pat = re.compile(r"      \{\n        name: [^\n]*\n        description: [^\n]*\n        url: '%s',\n"
                     r"(?:        [^\n]*\n)*?      \},\n" % re.escape(url))
    if pat.search(text):
        text = pat.sub(lambda m: entry, text, count=1)
        action = 'updated'
    else:
        marker = '    const EXTRA_APPS = [\n'
        if marker not in text:
            die('index.html에 EXTRA_APPS가 없다: %s' % index_path, 1)
        text = text.replace(marker, marker + entry, 1)
        action = 'inserted'
    with io.open(index_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    return action


def git(repo, *args, check=True):
    print('  git ' + ' '.join(args))
    return subprocess.run(['git', '-C', repo] + list(args), check=check)


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='앱 하나를 Pages repo 하위 폴더로 내보낸다 (기본 dry-run)')
    ap.add_argument('config')
    ap.add_argument('--pages')
    ap.add_argument('--terms-dir')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--commit', action='store_true')
    ap.add_argument('--push', action='store_true')
    ap.add_argument('--live-only', action='store_true')
    a = ap.parse_args()
    write = a.write or a.commit or a.push
    commit = a.commit or a.push

    cfg = load_config(a.config, a.pages)
    if a.live_only:
        if not cfg.get('live'):
            die('설정에 live가 없다')
        return wait_live(cfg['live'])
    files = staged_files(cfg)
    if not files:
        die('내보낼 파일이 없다 (include/exclude 확인)')
    print('source %s → %s (%d files)' % (cfg['source'], cfg['dest'], len(files)))

    g = gate(cfg, files, a.terms_dir)
    if g:
        print('멈춤: 공개하면 안 되는 내용이 있거나 gate를 돌릴 수 없다. 아무것도 복사하지 않았다.')
        return g

    new, upd, same, removed = plan(cfg, files)
    print('plan: 신규 %d · 갱신 %d · 같음 %d · 대상에서 지워짐 %d' % (new, upd, same, len(removed)))
    for r in removed[:20]:
        print('  - %s' % r)
    stage = [cfg['subdir']] + (['index.html'] if cfg.get('card') else [])
    if cfg.get('card'):
        print('card: %s' % cfg['card'].get('url'))
    print('stage: git add -- %s' % ' '.join(stage))
    pre = subprocess.run(['git', '-C', cfg['pages_repo'], 'status', '--short', '--', *stage],
                         capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.strip()
    if pre:
        print('주의: 이 경로에 commit 안 된 변경이 이미 있다(다른 세션의 것일 수 있다):')
        for ln in pre.splitlines()[:10]:
            print('  ' + ln)
    if not write:
        print('dry-run: 바꾼 것 없음. 복사하려면 --write, commit까지 --commit, push까지 --push')
        return 0

    ver = stamp_version(cfg, files) if cfg.get('stamp') else None
    stamped = replace_dir(cfg, files, ver)
    if ver:
        print('stamp: ?v=%s (%d files)' % (ver, len(stamped)))
    if not verify(cfg, files, stamped):
        print('멈춤: 복사 결과가 원본과 다르다. commit하지 않는다.')
        return 1
    paths = [cfg['subdir']]
    changed = bool(new or upd or removed)
    if cfg.get('card') and not changed:
        print('card: 내용이 그대로라 날짜를 바꾸지 않는다')
    elif cfg.get('card'):
        idx = os.path.join(cfg['pages_repo'], 'index.html')
        print('card %s' % upsert_card(idx, cfg['card'], time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())))
        paths.append('index.html')
    for cmd in cfg.get('after_copy') or []:
        c = cmd.replace('{dest}', '"%s"' % cfg['dest'])
        print('after_copy: %s' % c)
        if subprocess.run(c, shell=True).returncode != 0:
            print('멈춤: after_copy 실패. 복사는 됐지만 commit하지 않는다.')
            return 1
    if not commit:
        print('복사 끝. commit하지 않았다(--commit).')
        return 0
    try:
        git(cfg['pages_repo'], 'add', '--', *paths)
        if subprocess.run(['git', '-C', cfg['pages_repo'], 'diff', '--cached', '--quiet', '--', *paths]).returncode == 0:
            print('바뀐 것이 없어 commit하지 않는다.')
        else:
            msg = '%s (%s)' % (cfg.get('commit_message') or '%s: deploy' % cfg['subdir'], time.strftime('%Y-%m-%d'))
            extra = os.environ.get('DEPLOY_COMMIT_TRAILER', '')
            git(cfg['pages_repo'], 'commit', '-m', msg, *(['-m', extra] if extra else []), '--', *paths)
        if a.push:
            git(cfg['pages_repo'], 'push')
    except subprocess.CalledProcessError as e:
        print('git 실패: %s' % e)
        return 1
    if a.push and cfg.get('live'):
        return wait_live(cfg['live'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
