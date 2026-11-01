#!/usr/bin/env python3
"""check.py — 프로젝트의 완료 조건(기계 칸)을 차례로 돌린다. 하나라도 실패하면 종료 코드 1.

언제: 세션을 닫기 전(wrap), commit 전, 세션 시작에 "지난번 상태가 아직 맞나" 볼 때.
      글로 적은 규칙은 잊히지만 검사는 잊히지 않는다. 지켜야 할 것을 검사 한 줄로 바꿔 여기에 둔다.
kind: gate
status: active

사용:
  python check.py [CONFIG] [--only NAME] [--timeout S] [--quiet]
  python check.py [CONFIG] --selftest     실행기 자체 시험(심은 실패를 여전히 잡나) + 설정의 selftests
CONFIG를 주지 않으면 지금 폴더에서 checks.yaml · checks.json · 00_META/checks.yaml · 00_META/checks.json 순으로 찾는다.
명령은 CONFIG가 있는 폴더(또는 설정의 root)에서 돈다.

설정 형식(YAML 또는 JSON). PyYAML이 없어도 아래 모양은 읽힌다:
  root: ..                     # 선택. CONFIG 폴더 기준 상대 경로
  checks:
    - python tools/validate.py           # 문자열 = 명령 하나(이름 = 명령)
    - name: smoke                        # 또는 이름 · 명령 · 폴더 · 시간 제한
      run: node tools/smoke.mjs
      cwd: app
      timeout: 120
  selftests:                   # 이 프로젝트가 만든 검사 도구가 "심은 결함을 여전히 잡나" (선택, 형식은 checks와 같다)
    - python tools/validate.py --selftest

종료 코드: 0 = 모두 통과(또는 checks 없음), 1 = 실패 있음, 2 = 설정 파일 없음 · 읽기 오류.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

CANDIDATES = ['checks.yaml', 'checks.yml', 'checks.json', os.path.join('00_META', 'checks.yaml'), os.path.join('00_META', 'checks.json')]


def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in '\'"':
        return v[1:-1]
    if re.fullmatch(r'-?\d+', v):
        return int(v)
    return v


def mini_yaml(text):
    """top-level `key: value`와 `key:` 아래 `- 문자열` / `- k: v` 묶음만 읽는다."""
    out, key, item = {}, None, None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        line = raw.rstrip()
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if indent == 0:
            m = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', s)
            if not m:
                raise ValueError('읽을 수 없는 줄: %s' % s)
            key, item = m.group(1), None
            val = m.group(2).split(' #', 1)[0].strip()
            out[key] = _scalar(val) if val else []
            continue
        if key is None:
            raise ValueError('키 밖의 줄: %s' % s)
        if s.startswith('- '):
            body = s[2:].strip()
            m = re.match(r'^([A-Za-z_][\w-]*):\s+(.*)$', body)
            if m and not body.startswith(('python ', 'node ', 'bash ', 'pwsh ', 'powershell ')):
                item = {m.group(1): _scalar(m.group(2))}
                out[key].append(item)
            else:
                item = None
                out[key].append(_scalar(body))
            continue
        m = re.match(r'^([A-Za-z_][\w-]*):\s+(.*)$', s)
        if m and isinstance(item, dict):
            item[m.group(1)] = _scalar(m.group(2))
            continue
        raise ValueError('읽을 수 없는 줄: %s' % s)
    return out


def load(path):
    text = io.open(path, encoding='utf-8').read()
    if path.lower().endswith('.json'):
        return json.loads(text)
    try:
        import yaml  # noqa: F401
        return yaml.safe_load(text) or {}
    except ImportError:
        return mini_yaml(text)


def norm(entries):
    out = []
    for e in entries or []:
        if isinstance(e, str):
            out.append({'name': e, 'run': e})
        elif isinstance(e, dict) and e.get('run'):
            out.append({'name': e.get('name') or e['run'], 'run': e['run'], 'cwd': e.get('cwd'), 'timeout': e.get('timeout')})
        else:
            raise ValueError('check 항목에 run이 없다: %r' % (e,))
    return out


def _text(b):
    for enc in ('utf-8', 'cp949'):  # Windows 한국어 명령의 오류 메시지는 cp949로 나온다
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode('utf-8', errors='replace')


def run(checks, root, timeout, label='', quiet=False):
    bad = 0
    for c in checks:
        cwd = os.path.join(root, c['cwd']) if c.get('cwd') else root
        try:
            r = subprocess.run(c['run'], shell=True, cwd=cwd, capture_output=True, timeout=c.get('timeout') or timeout)
            ok, tail = r.returncode == 0, (_text(r.stdout) + _text(r.stderr)).strip().splitlines()[-3:]
        except subprocess.TimeoutExpired:
            ok, tail = False, ['timeout %ss' % (c.get('timeout') or timeout)]
        bad += 0 if ok else 1
        if not (quiet and ok):
            print('%s%s  %s%s' % (label, 'PASS' if ok else 'FAIL', c['name'], ('\n      ' + '\n      '.join(tail)) if (tail and not ok) else ''))
    return bad


def selftest(cfg, root, timeout):
    fails = []
    py = '"%s"' % sys.executable
    if run([{'name': 'planted failure', 'run': py + ' -c "import sys; sys.exit(3)"'}], root, timeout, '[심은 실패] ') != 1:
        fails.append('심은 실패를 잡지 못함')
    if run([{'name': 'passing', 'run': py + ' -c "pass"'}], root, timeout, '[정상] ') != 0:
        fails.append('통과해야 할 check를 실패로 셈')
    if run([{'name': 'planted hang', 'run': py + ' -c "import time; time.sleep(30)"', 'timeout': 2}], root, timeout, '[심은 멈춤] ') != 1:
        fails.append('시간 초과를 잡지 못함')
    try:
        parsed = mini_yaml('checks:\n  - python a.py\n  - name: b\n    run: node b.mjs\n    timeout: 5\n')
        if norm(parsed['checks']) != [{'name': 'python a.py', 'run': 'python a.py'},
                                       {'name': 'b', 'run': 'node b.mjs', 'cwd': None, 'timeout': 5}]:
            fails.append('설정 읽기가 틀림')
    except Exception as e:
        fails.append('설정 읽기 오류: %s' % e)
    own = norm((cfg or {}).get('selftests'))
    if own and run(own, root, timeout, '[project selftest] '):
        fails.append('프로젝트 검사 도구의 selftest 실패')
    print('selftest: %s' % ('PASS' if not fails else 'FAIL — ' + ' / '.join(fails)))
    return 1 if fails else 0


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='완료 조건(기계 칸) 실행기')
    ap.add_argument('config', nargs='?')
    ap.add_argument('--only', action='append', default=[])
    ap.add_argument('--timeout', type=int, default=600)
    ap.add_argument('--quiet', action='store_true', help='통과한 줄은 찍지 않는다')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    path = a.config or next((c for c in CANDIDATES if os.path.isfile(c)), None)
    if not path or not os.path.isfile(path):
        if a.selftest:
            return selftest({}, os.getcwd(), a.timeout)
        print('check: 설정 파일이 없다 (%s)' % (a.config or ' · '.join(CANDIDATES)))
        return 2
    try:
        cfg = load(path)
        checks = norm(cfg.get('checks'))
    except Exception as e:
        print('check: 설정을 읽지 못했다: %s' % e)
        return 2
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), cfg.get('root') or '.'))
    if a.selftest:
        return selftest(cfg, root, a.timeout)
    if a.only:
        checks = [c for c in checks if c['name'] in a.only]
    if not checks:
        print('checks 없음 (%s) — 통과' % path)
        return 0
    bad = run(checks, root, a.timeout, quiet=a.quiet)
    print('checks: PASS %d / FAIL %d' % (len(checks) - bad, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
