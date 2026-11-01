r"""redact_check — 공개 전 gate. 금지어와 로컬 경로가 섞였는지 본다.

언제: 무엇이든 공개 repo · GitHub Pages · 공유 artifact로 내보내기 직전에 한 번.
      pages-deploy/deploy.py가 첫 단계에서 이것을 부른다.
kind: gate
status: active

사용:
  python redact_check.py PATH [PATH ...]      파일 · 폴더 검사(폴더는 텍스트 파일만 재귀)
  python redact_check.py --sources            어떤 원천을 읽었는지만(파일 이름 · 낱말 수)
  python redact_check.py --selftest           일부러 금지어를 심은 임시 파일로 gate가 여전히 막는지 본다
  옵션: --terms-dir DIR    금지어 폴더(기본: 환경변수 REDACT_DIR, 없으면 ~/.claude/private/redact)
        --sections 1,2,3   redact_keywords.txt에서 쓸 절(기본 전부)
        --no-paths         로컬 경로 패턴 검사를 끈다

종료 코드: 0 = 위반 없음, 1 = 위반 있음, 2 = 금지어 원천이 없음(gate를 돌릴 수 없음 — 통과로 치지 않는다).

금지어 원천(어느 repo에도 속하지 않는 비공개 자리 한 곳에서 읽는다. 복사해 들고 다니지 않는다):
  <terms-dir>/redact_keywords.txt   "## [n] 제목" 절로 나뉜 목록
  <terms-dir>/*.txt (그 밖)          한 줄에 한 낱말. 라벨은 파일 이름
  '#'로 시작하는 줄과 빈 줄은 건너뛴다.
판정 규칙:
  word   대소문자 무시. 영문이 든 낱말은 앞뒤가 영문자가 아닐 때만 맞는다("Tomato" ≠ "Tom")
  =word  대소문자 구분, 경계 규칙은 같다
  한글만  부분 문자열
출력에는 낱말 자체를 찍지 않는다(로그 · 보고로 새지 않게). 라벨 · 첫 글자 · 길이만.

다른 도구에서: import 뒤 load_terms() · scan_text() · scan_paths() · mask_text()를 쓴다.
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

DEFAULT_DIR = os.path.join(os.path.expanduser('~'), '.claude', 'private', 'redact')
SECTIONED = 'redact_keywords.txt'
TEXT_EXT = ('.md', '.txt', '.html', '.htm', '.js', '.mjs', '.cjs', '.ts', '.json', '.jsonl', '.yaml', '.yml',
            '.css', '.csv', '.tsv', '.py', '.sh', '.ps1', '.xml', '.svg', '.webmanifest', '.vtt', '.srt')
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.local', '.venv'}
# 이 PC의 로컬 경로: 드라이브 문자 + 알려진 뿌리 폴더, 또는 Git Bash 형식
PATH_RE = re.compile(
    r'(?i)\b[a-z]:[\\/]+(users|idea|c[0-3]_[a-z_]+)[\\/]'
    r'|/c/(users|idea|c[0-3]_[a-z_]+)/')


def terms_dir(override=None):
    return override or os.environ.get('REDACT_DIR') or DEFAULT_DIR


def _read(path):
    with io.open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def source_files(tdir=None):
    d = terms_dir(tdir)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, n) for n in os.listdir(d) if n.lower().endswith('.txt'))


def load_terms(tdir=None, sections=None):
    """[(label, raw)]. label = '[n]'(절) 또는 파일 이름. sections=None이면 모든 절."""
    terms = []
    for path in source_files(tdir):
        name = os.path.basename(path)
        if name == SECTIONED:
            cur = None
            for ln in _read(path).splitlines():
                m = re.match(r'^## \[(\d+)\]', ln)
                if m:
                    cur = m.group(1)
                    continue
                if ln.startswith('## '):
                    cur = None
                    continue
                t = ln.strip()
                if cur and (sections is None or cur in sections) and t and not t.startswith('#'):
                    terms.append(('[%s]' % cur, t))
        else:
            label = os.path.splitext(name)[0]
            for ln in _read(path).splitlines():
                t = ln.strip()
                if t and not t.startswith('#'):
                    terms.append((label, t))
    return terms


def _compile(raw):
    case = raw.startswith('=')
    word = raw[1:] if case else raw
    if re.search(r'[A-Za-z]', word):
        pat = r'(?<![A-Za-z])' + re.escape(word) + r'(?![A-Za-z])'
    else:
        pat = re.escape(word)
    return re.compile(pat, 0 if case else re.IGNORECASE)


def compile_terms(terms):
    return [(label, raw, _compile(raw)) for label, raw in terms]


def _masked(raw):
    w = raw.lstrip('=')
    return '%s…(%d자)' % (w[:1], len(w))


def scan_text(text, terms, paths=True):
    """[(line_no, label, masked)] — masked는 낱말을 드러내지 않는 표시."""
    comp = terms if (terms and len(terms[0]) == 3) else compile_terms(terms)
    hits = []
    for i, ln in enumerate(text.splitlines(), 1):
        for label, raw, rx in comp:
            if rx.search(ln):
                hits.append((i, label, _masked(raw)))
        if paths and PATH_RE.search(ln):
            hits.append((i, 'path', '로컬 경로'))
    return hits


def mask_text(text, terms, token='[가림]'):
    """금지어를 token으로 바꾼 문자열(지도 같은 생성물에 쓴다)."""
    comp = terms if (terms and len(terms[0]) == 3) else compile_terms(terms)
    for _label, _raw, rx in comp:
        text = rx.sub(token, text)
    return text


def iter_files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for dp, dns, fns in os.walk(p):
                dns[:] = [d for d in dns if d not in SKIP_DIRS]
                for fn in fns:
                    if fn.lower().endswith(TEXT_EXT):
                        yield os.path.join(dp, fn)


def scan_paths(paths, terms, check_paths=True):
    """[(file, line, label, masked)]"""
    comp = compile_terms(terms)
    out = []
    for f in iter_files(paths):
        for line, label, masked in scan_text(_read(f), comp, check_paths):
            out.append((f, line, label, masked))
    return out


def selftest(tdir):
    """심은 금지어 → 1, 깨끗한 파일 → 0, 원천 없음 → 2 를 실제 명령줄로 확인한다. 낱말은 출력하지 않는다."""
    terms = load_terms(tdir)
    if not terms:
        print('selftest: 금지어 원천이 없어 시험할 수 없다 (%s)' % terms_dir(tdir))
        return 2
    planted = terms[0][1].lstrip('=')
    tmp = tempfile.mkdtemp(prefix='redact-selftest-')
    fails = []
    try:
        bad = os.path.join(tmp, 'planted.md')
        good = os.path.join(tmp, 'clean.md')
        empty_dir = os.path.join(tmp, 'no-terms')
        os.makedirs(empty_dir)
        with io.open(bad, 'w', encoding='utf-8') as f:
            f.write('공개 문서 한 줄\nxx %s yy\n' % planted)
        with io.open(good, 'w', encoding='utf-8') as f:
            f.write('아무 문제 없는 공개 문서\nplain text only\n')
        base = [sys.executable, os.path.abspath(__file__), '--terms-dir', terms_dir(tdir)]
        quiet = dict(capture_output=True, text=True, encoding='utf-8', errors='replace')
        r1 = subprocess.run(base + [bad], **quiet)
        r0 = subprocess.run(base + [good], **quiet)
        r2 = subprocess.run([sys.executable, os.path.abspath(__file__), '--terms-dir', empty_dir, good], **quiet)
        if r1.returncode != 1:
            fails.append('심은 금지어를 잡지 못함(code %s)' % r1.returncode)
        if planted in (r1.stdout + r1.stderr):
            fails.append('출력에 낱말이 그대로 찍힘')
        if r0.returncode != 0:
            fails.append('깨끗한 파일을 위반으로 셈(code %s)' % r0.returncode)
        if r2.returncode != 2:
            fails.append('원천이 없는데 2가 아님(code %s)' % r2.returncode)
        print('selftest: planted=%s clean=%s no-source=%s' % (r1.returncode, r0.returncode, r2.returncode))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('selftest: %s' % ('PASS' if not fails else 'FAIL — ' + ' / '.join(fails)))
    print('temp removed: %s' % (not os.path.exists(tmp)))
    return 1 if fails else 0


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='공개 전 gate (금지어 · 로컬 경로)')
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--terms-dir')
    ap.add_argument('--sections', help='redact_keywords.txt에서 쓸 절, 예: 1,2')
    ap.add_argument('--no-paths', action='store_true')
    ap.add_argument('--sources', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    secs = tuple(s.strip() for s in a.sections.split(',') if s.strip()) if a.sections else None
    if a.selftest:
        return selftest(a.terms_dir)
    terms = load_terms(a.terms_dir, secs)
    if a.sources:
        files = source_files(a.terms_dir)
        print('terms-dir: %s' % terms_dir(a.terms_dir))
        for f in files:
            print('  %s' % os.path.basename(f))
        print('terms: %d' % len(terms))
        return 0 if terms else 2
    if not terms:
        print('redact_check: 금지어 원천이 없다 (%s) — gate를 돌릴 수 없다' % terms_dir(a.terms_dir))
        return 2
    if not a.paths:
        ap.error('검사할 PATH가 없다')
    hits = scan_paths(a.paths, terms, not a.no_paths)
    for f, line, label, masked in hits:
        print('%s:%d: %s %s' % (f, line, label, masked))
    print('redact_check: %d hit(s)' % len(hits))
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
