#!/usr/bin/env python3
"""scan_sessions — 어느 폴더에서 어떤 Claude 세션이 무엇을 하다 멈췄나(PC 전체).

언제: PC가 꺼지거나 업데이트로 Claude 창들이 닫힌 뒤 "어느 세션을 resume하나", 오랜만에 돌아와 "최근에 무엇을 했나".
kind: recover
status: active

사용:
  python scan_sessions.py [--days 7] [--root C:\\C1_Career ...] [--full] [--git] [--out FILE]
    --days N    최근 N일 안의 활동만 (기본 7)
    --root DIR  이 뿌리 아래 폴더의 세션만 (여러 번 가능). 기본은 전부
    --full      사용자 요청을 자르지 않고 모두
    --git       활동한 폴더마다 같은 기간의 git log · 안 올린 commit · 바뀐 파일 수를 붙인다
    --out FILE  화면 대신 파일로

읽는 곳: ~/.claude/projects/<인코딩된 폴더>/<세션 id>.jsonl
중요: 활동은 **로그 안의 시각**으로 판정한다. 파일 수정 시각은 resume · 요약만으로도 바뀐다(실측).
폴더마다 뿌리(카테고리) 이름을 붙인다. 뿌리 목록은 아래 ROOTS 한 곳에서 정한다.
비공개 폴더(PRIVATE)의 세션 로그는 열지도 않는다.
"""
import argparse
import collections
import datetime
import json
import os
import subprocess
import sys

PROJECTS = os.path.join(os.path.expanduser('~'), '.claude', 'projects')
# 뿌리(카테고리) — 앞에 있을수록 먼저 맞춘다. E4 이동 뒤에는 카테고리 폴더 셋이 대부분을 덮는다.
ROOTS = [
    ('C1', r'C:\C1_Career'), ('C2', r'C:\C2_Learn'), ('C3', r'C:\C3_Life'),
    ('old', r'C:\Old'),   # 카테고리 이전의 옛 뿌리 폴더(예시)
]
# 이 폴더의 세션은 그 폴더에서 연 세션만 다룬다. 다른 세션은 읽지 않는다.
PRIVATE = ['private-folder']   # 그 폴더에서 연 세션만 다루는 폴더 이름(예시)


def is_private(s):
    low = (s or '').lower()
    return any(p in low for p in PRIVATE)


assert is_private(r'C:\private-folder') and is_private('C--private-folder')


def root_of(cwd):
    low = (cwd or '').lower().rstrip('\\/')
    for label, r in ROOTS:
        rl = r.lower()
        if low == rl or low.startswith(rl + '\\') or low.startswith(rl + '/'):
            return label
    return '-'


def block_text(msg):
    c = msg.get('content')
    if isinstance(c, str):
        return c
    out = []
    if isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get('type') == 'text':
                out.append(b.get('text', ''))
    return '\n'.join(out)


def scan_file(path, since):
    st = {'cwd': '', 'first': '', 'last': '', 'win_first': '', 'win_last': '', 'days': collections.Counter(),
          'users': [], 'files': collections.Counter(), 'commits': 0, 'tail': '', 'lines': 0}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            st['lines'] += 1
            st['cwd'] = r.get('cwd') or st['cwd']
            t = r.get('timestamp') or ''
            rtype = r.get('type')
            if t:
                st['first'] = st['first'] or t
                st['last'] = t
            if rtype in ('user', 'assistant'):
                st['tail'] = rtype
            if not t or t[:10] < since:
                continue
            st['win_first'] = st['win_first'] or t
            st['win_last'] = t
            st['days'][t[:10]] += 1
            if r.get('isSidechain'):
                continue
            if rtype == 'user' and not r.get('isMeta'):
                s = block_text(r.get('message', {})).strip()
                if (s and not s.startswith('<') and 'tool_result' not in s[:40]
                        and not s.startswith('This session is being continued') and not s.startswith('Caveat:')):
                    st['users'].append((t, s.replace('\n', ' ')))
            elif rtype == 'assistant':
                for b in r.get('message', {}).get('content', []) or []:
                    if not isinstance(b, dict) or b.get('type') != 'tool_use':
                        continue
                    inp = b.get('input', {}) or {}
                    if b.get('name') in ('Write', 'Edit', 'NotebookEdit') and inp.get('file_path'):
                        st['files'][inp['file_path']] += 1
                    elif b.get('name') in ('Bash', 'PowerShell') and 'git commit' in str(inp.get('command', '')):
                        st['commits'] += 1
    return st


def fmt_ts(t):
    return t[:16].replace('T', ' ') if t else '?'


def rel(path, cwd):
    if cwd and path.lower().startswith(cwd.lower()):
        return path[len(cwd):].lstrip('\\/')
    return path


def git_summary(cwd, since):
    def g(*a):
        r = subprocess.run(['git', '-C', cwd] + list(a), capture_output=True, text=True, encoding='utf-8', errors='replace')
        return r.stdout.strip() if r.returncode == 0 else None
    if g('rev-parse', '--is-inside-work-tree') != 'true':
        return ['    git       : (git repo 아님)']
    out = []
    log = g('log', '--since=%s' % since, '--pretty=%ad %s', '--date=short') or ''
    lines = log.splitlines()
    out.append('    git log   : %d commit(s) since %s' % (len(lines), since))
    out += ['      %s' % ln[:150] for ln in lines[:8]]
    ahead = g('rev-list', '--count', '@{u}..HEAD')
    out.append('    unpushed  : %s' % (ahead if ahead is not None else '(upstream 없음)'))
    status = g('status', '--short') or ''
    out.append('    changed   : %d file(s) not committed' % len([x for x in status.splitlines() if x.strip()]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--root', action='append', default=[])
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--git', action='store_true')
    ap.add_argument('--out', default='')
    a = ap.parse_args()

    now = datetime.datetime.now()
    since = (now - datetime.timedelta(days=a.days)).strftime('%Y-%m-%d')
    stale_cut = now - datetime.timedelta(days=a.days + 30)
    want = [r.lower().rstrip('\\/') for r in a.root]

    def wanted(cwd):
        low = (cwd or '').lower()
        return not want or any(low == w or low.startswith(w + '\\') or low.startswith(w + '/') for w in want)

    if not os.path.isdir(PROJECTS):
        print('no projects dir: ' + PROJECTS)
        return 1
    active, idle = {}, []
    skipped_private = 0
    for d in sorted(os.listdir(PROJECTS)):
        dp = os.path.join(PROJECTS, d)
        if not os.path.isdir(dp):
            continue
        if is_private(d):
            skipped_private += 1
            continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith('.jsonl'):
                continue
            fp = os.path.join(dp, fn)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fp))
            if mtime < stale_cut:
                continue
            st = scan_file(fp, since)
            cwd = st['cwd'] or ('?' + d)
            if is_private(cwd):
                skipped_private += 1
                continue
            if not wanted(cwd):
                continue
            if st['days']:
                active.setdefault(cwd, []).append((fn[:-6], st))
            elif mtime >= now - datetime.timedelta(days=a.days):
                idle.append((cwd, fn[:-6], st, mtime))

    lines = []
    w = lines.append
    w('== CLAUDE SESSION SCAN ==')
    w('window   : last %d days (since %s)  |  now %s' % (a.days, since, now.strftime('%Y-%m-%d %H:%M')))
    w('basis    : timestamps INSIDE each log (mtime is unreliable)')
    w('dirs     : %d active%s' % (len(active), ('  |  roots: ' + ', '.join(a.root)) if a.root else ''))
    by_root = collections.Counter(root_of(c) for c in active)
    w('by root  : ' + (', '.join('%s %d' % kv for kv in sorted(by_root.items())) or '-'))
    w('private  : %d project folder(s) not read' % skipped_private)
    w('')
    order = sorted(active.items(), key=lambda kv: max(s['win_last'] for _, s in kv[1]), reverse=True)
    for cwd, sessions in order:
        w('=' * 78)
        w('DIR  [%s] %s' % (root_of(cwd), cwd))
        for sid, st in sorted(sessions, key=lambda x: x[1]['win_last'], reverse=True):
            days = ' '.join('%s(%d)' % (k[5:], v) for k, v in sorted(st['days'].items()))
            w('  session %s   [%d lines]' % (sid, st['lines']))
            w('    in-window : %s -> %s' % (fmt_ts(st['win_first']), fmt_ts(st['win_last'])))
            w('    started   : %s' % fmt_ts(st['first']))
            w('    days      : %s' % days)
            flag = ''
            if st['tail'] == 'assistant':
                try:
                    last = datetime.datetime.strptime(st['last'][:19], '%Y-%m-%dT%H:%M:%S')
                    utcnow = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                    fresh = (utcnow - last).total_seconds() < 3 * 3600
                except Exception:
                    fresh = False
                flag = '  <-- still open right now?' if fresh else '  <-- ended on assistant turn (forced-close candidate)'
            w('    tail      : %s%s' % (st['tail'], flag))
            w('    resume    : cd "%s"; claude --resume %s' % (cwd, sid))
            w('    asks (%d):' % len(st['users']))
            for t, s in st['users']:
                w('      [%s] %s' % (fmt_ts(t)[5:], s if a.full else s[:170]))
            w('    edits (%d files, %d writes), git-commit cmds: %d' % (len(st['files']), sum(st['files'].values()), st['commits']))
            for k, v in st['files'].most_common(12):
                w('      %2dx %s' % (v, rel(k, cwd)))
        if a.git and os.path.isdir(cwd):
            for ln in git_summary(cwd, since):
                w(ln)
        w('')
    if idle:
        w('=' * 78)
        w('TOUCHED BUT IDLE  (file mtime is recent, but NO activity in window --')
        w('                   resumed/summarized only; do NOT report as worked on)')
        for cwd, sid, st, mtime in sorted(idle, key=lambda x: x[3], reverse=True):
            w('  [%s] %s' % (root_of(cwd), cwd))
            w('    session %s  last real activity %s   (mtime %s)' % (sid, fmt_ts(st['last']), mtime.strftime('%Y-%m-%d %H:%M')))
            w('    resume  : cd "%s"; claude --resume %s' % (cwd, sid))
        w('')
    if not a.git:
        w('=' * 78)
        w('NEXT: --git 으로 다시 돌리면 폴더마다 git log · unpushed · 안 commit한 파일 수가 붙는다')

    text = '\n'.join(lines)
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
        print('written: %s  (%d lines)' % (a.out, len(lines)))
    else:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
