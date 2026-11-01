#!/usr/bin/env python3
r"""map.py — WF 지도 넷(자산 · 지식 · 프로젝트 · WF 사용법)을 원천에서 기계로 만든다. 손으로 고치는 지도는 없다.

언제: init 끝 · wrap · install · 폴더 이동 뒤, 하루 넘게 낡았으면 세션 시작 hook이 background로 다시 굽는다. Init · 착수 때는 몇 줄만 조회한다.
kind: map
status: active

출력: ~\.claude\workflow\maps\ (환경 변수 WF_MAPS로 바꿀 수 있음) — assets.md · assets.tsv · knowledge.md · projects.md · wf.md. git 밖 파생물.
사용:
  python tools/map.py --build             다시 굽는다(--quiet: 한 줄만)
  python tools/map.py --check             다시 굽고 경고 수만 보인다(경고가 있으면 종료 코드 1)
  python tools/map.py --kind gate         그 kind의 자산 몇 줄 (assets.tsv를 읽기만 한다 — 지도가 없으면 굽지 않고 멈춘다)
  python tools/map.py --when "배포 검사"   when · 설명 · 이름에 낱말이 하나라도 든 자산, 맞은 낱말 수 순
  python tools/map.py --workspaces "이력서" 선례 워크스페이스(낱말 OR)
  인자 없이 돌리면 도움말만 보인다.
    조회 옵션: --category C1 · --type skill · --limit 12 · --all(script · 미기재 포함 모두)

자산(skill · agent · command · hook · MCP · plugin · script)의 칸:
  name · type · scope · category · when · kind · status · origin · fork · location · desc
  when · kind · status · origin · fork 는 원천의 앞머리(skill · agent의 `metadata:`, script 머리의 `언제:/when:` `kind:` `status:` 줄)에서만
  읽는다. 없으면 "미기재"로 두고 추측하지 않는다.
  category = 경로로 판정: 카테고리 폴더(C1 · C2 · C3) → pool 폴더 → S7 이동 목록의 카테고리 열(지금 경로를 앞부분으로 맞춤) → 그 밖.
  계정 동기화 skill은 category "바깥".
지식(knowledge.md): 워크스페이스마다 재진입 · 결정 · 기록 · 함정 · 방식 · 도메인 · 이해 · 나 자리의 경로와 한 줄 제목만. 내용은 복사하지 않는다.
비공개: 금지어(redact-check 원천)에 걸리는 낱말은 출력에서 [가림]으로 바꾼다. 금지어 원천이 없으면 지도를 쓰지 않는다.
"""
import argparse
import collections
import csv
import datetime
import io
import json
import os
import re
import subprocess
import sys

# ============================================================== 훑는 범위 (한 곳)
HOME = os.path.expanduser('~')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # WF core 정본 repo
MAPS = os.environ.get('WF_MAPS') or os.path.join(HOME, '.claude', 'workflow', 'maps')   # 파생물: git 밖(설계 12 §8.3)
GLOBAL_CLAUDE = os.path.join(HOME, '.claude')
CLAUDE_JSON = os.path.join(HOME, '.claude.json')
CATEGORY_ROOTS = [('C0', r'C:\C0_Workflow_Core'), ('C1', r'C:\C1_Career'), ('C2', r'C:\C2_Learn'), ('C3', r'C:\C3_Life')]
OTHER_PERSON = [r'<other-person-folder>']                     # 다른 사람의 작업 폴더: 이름과 표시만
FROZEN_SEEDS = [r'<old-workspace>', r'<old-workspace>', r'<old-workspace>']   # 얼린 seed(설계 §6.5)
WORK_ROOTS = [r for _, r in CATEGORY_ROOTS] + [r'<old-workspace>', r'<old-workspace>', r'<old-workspace>', r'<other-person-folder>', r'<idea-inbox>']
MOVE_LIST = r'<design-notes>\research\s7\I_move_list.tsv'
NEVER = [r'<private-folder>']               # 읽지 않는다(그 폴더에서 연 세션만 다룬다)
SKIP_DIRS = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'worktrees', 'site-packages', '.next', 'dist-electron'}
CLAUDE_DIR_DEPTH = 5                             # 뿌리 아래 .claude를 찾는 깊이
WORKSPACE_DEPTH = 4                              # 뿌리 아래 워크스페이스(CLAUDE.md · .git)를 찾는 깊이
INSIDE_DEPTH = 3                                 # 워크스페이스 안을 보는 깊이(script · 지식)
TOOLDIRS = {'tools', '70_tools', 'scripts', '30_pipeline', '80_publish', 'bin', '_tools', '90_tools', '60_tools', '50_tools'}
SCRIPT_EXT = ('.py', '.sh', '.ps1', '.mjs', '.js', '.cmd', '.bat')
SCRIPT_JS_ONLY_IN_TOOLDIR = True                 # .js는 도구 폴더 바로 아래 것만(앱 소스 .js를 script로 세지 않게)
SCRIPT_SKIP_DIRS = {'90_archive', '99_archive', '90_frozen', '90_work'}   # 보관 · 일회성 작업 폴더의 script는 세지 않는다
SCRIPT_SKIP_SUFFIX = ('_clone',)                 # 남의 repo를 받아 둔 폴더
MISSING = '미기재'
TERMS_TOOL = os.path.join(os.path.expanduser('~'), '.claude', 'workflow', 'tools')   # 설치본(redact_check.py)
if not os.path.exists(os.path.join(TERMS_TOOL, 'redact_check.py')):
    TERMS_TOOL = os.path.join(REPO, 'shared-tools')                                # 설치 전에는 정본
# 지도에서 가리는 금지어: 회사 절([1])과 따로 둔 개인 낱말 파일(아이 이름 등). [2] 작성자 · [3] 작업 공간 참조는
# 공개 앱용 규칙이라 비공개 지도에서는 가리지 않는다(가리면 경로가 쓸모없어진다).
MASK_SECTIONS = ('1',)

for _n in NEVER:
    assert 'private-folder' in _n.lower(), 'NEVER 목록에서 private-folder을 빼지 않는다'

sys.path.insert(0, TERMS_TOOL)
try:
    import redact_check  # noqa: E402
except ImportError:      # pool이 아직 없을 때
    redact_check = None

# ============================================================== 공통
WARN, NOTE = [], []


def low(p):
    return os.path.normcase(os.path.abspath(p)).rstrip('\\/')


def under(path, root):
    p, r = low(path), low(root)
    return p == r or p.startswith(r + os.sep)


def never(path):
    return any(under(path, n) for n in NEVER)


def read_head(path, n=6000):
    try:
        with io.open(path, encoding='utf-8', errors='replace') as f:
            return f.read(n)
    except OSError as e:
        WARN.append('읽기 실패: %s (%s)' % (path, e.__class__.__name__))
        return ''


def depth(path, root):
    return low(path).count(os.sep) - low(root).count(os.sep)


# ============================================================== 앞머리
META_KEYS = ('when', 'kind', 'status', 'origin', 'base', 'fork', 'called_by')


def frontmatter(path):
    """skill · agent · command의 YAML 앞머리에서 name · description · metadata.* (또는 맨 위 when 등)."""
    t = read_head(path)
    out = {}
    if not t.startswith('---'):
        m = re.search(r'^#\s+(.*)$', t, re.M)
        if m:
            out['title'] = m.group(1).strip()
        return out
    end = t.find('\n---', 3)
    if end < 0:
        WARN.append('앞머리가 닫히지 않음: %s' % path)
        return out
    lines = t[3:end].strip('\n').splitlines()
    i, in_meta = 0, False
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'^(\s*)([A-Za-z_][\w-]*):\s*(.*)$', ln)
        if not m:
            i += 1
            continue
        ind, key, val = len(m.group(1)), m.group(2), m.group(3).strip()
        if ind == 0:
            in_meta = key == 'metadata'
        if val in ('>', '|', '>-', '|-', '>+', '|+'):
            buf = []
            j = i + 1
            while j < len(lines) and (lines[j].startswith(' ' * (ind + 1)) or not lines[j].strip()):
                buf.append(lines[j].strip())
                j += 1
            val, i = ' '.join(x for x in buf if x), j
        else:
            i += 1
        val = val.strip().strip('"\'')
        if ind == 0 and key in ('name', 'description'):
            out[key] = val
        elif key in META_KEYS and (ind == 0 or in_meta) and val:
            out.setdefault(key, val)
    return out


SCRIPT_META = re.compile(r'^\s*(?:#|//|\*|rem\s|::|r?""")?\s*(when|언제|kind|status|origin|base|fork)\s*:\s*(.+?)\s*$', re.I)


def script_head(path):
    """script 머리 40줄에서 meta 줄과 첫 설명 줄."""
    t = read_head(path, 4000)
    meta, desc = {}, ''
    for ln in t.splitlines()[:40]:
        m = SCRIPT_META.match(ln)
        if m:
            k = m.group(1).lower()
            meta.setdefault('when' if k == '언제' else k, m.group(2).strip('"\' '))
            continue
        s = ln.strip()
        if not desc and s and not s.startswith(('#!', '# -*-', 'import ', 'from ', 'param(', 'use strict', "'use strict'", '@echo')):
            s = re.sub(r'^(#+|//+|/\*+|\*+|r?"""|\'\'\'|rem\s|::)\s*', '', s, flags=re.I).strip()
            s = s.rstrip('"').strip()
            if len(s) > 3 and not s.startswith(('-*-', '=')):
                desc = s
    return meta, desc


# ============================================================== 카테고리
def load_move_list():
    rows = []
    if not os.path.isfile(MOVE_LIST):
        NOTE.append('S7 이동 목록이 없다: %s (경로로만 카테고리 판정)' % MOVE_LIST)
        return rows
    with io.open(MOVE_LIST, encoding='utf-8') as f:
        rd = csv.reader(f, delimiter='\t')
        next(rd, None)
        for r in rd:
            if len(r) >= 3 and r[0].strip():
                rows.append((r[0].strip(), r[2].strip()))
    rows.sort(key=lambda x: -len(x[0]))
    return rows


MOVES = []


def category(path, scope=''):
    if scope == '바깥':
        return '바깥'
    pool = os.path.join(REPO, 'pool')            # core 정본이 C0 폴더 안에 있으므로 pool · core 판정을 카테고리보다 먼저
    if under(path, pool):
        sub = low(path)[len(low(pool)) + 1:].split(os.sep)[0]
        return {'c0': 'C0', 'c1': 'C1', 'c2': 'C2', 'c3': 'C3', 'common': '공통', '_retired': '은퇴'}.get(sub, '공통')
    if under(path, REPO):
        return '뼈대'
    for label, r in CATEGORY_ROOTS:
        if under(path, r):
            return label
    if under(path, GLOBAL_CLAUDE) or scope in ('전역', '플러그인'):
        return '전역'
    for cur, cat in MOVES:
        if under(path, cur):
            return cat
    return '미분류'


# ============================================================== 자산
ROWS = []
COLS = ['name', 'type', 'scope', 'category', 'when', 'kind', 'status', 'origin', 'fork', 'location', 'desc']


def add(name, typ, scope, location, meta=None, desc='', cat=None):
    meta = meta or {}
    ROWS.append({
        'name': name, 'type': typ, 'scope': scope, 'category': cat or category(location, scope),
        'when': meta.get('when') or MISSING, 'kind': meta.get('kind') or MISSING, 'status': meta.get('status') or MISSING,
        'origin': meta.get('origin') or ('(원본)' if scope in ('pool', 'core') else MISSING),
        'fork': meta.get('fork') or ('-' if scope in ('pool', 'core') else MISSING),
        'location': location, 'desc': (desc or '')[:400 if scope == 'core' else 140],
    })


def scan_claude_dir(cd, scope, ws=None):
    """skills · commands · agents · settings*.json(hooks · plugins · mcp)."""
    ws = ws or os.path.dirname(cd)
    sk = os.path.join(cd, 'skills')
    if os.path.isdir(sk):
        for dp, dns, fns in os.walk(sk):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            if 'SKILL.md' in fns:
                p = os.path.join(dp, 'SKILL.md')
                fm = frontmatter(p)
                if not fm.get('description'):
                    NOTE.append('description 없는 skill: %s' % p)
                add(fm.get('name') or os.path.basename(dp), 'skill', scope, p, fm, fm.get('description') or fm.get('title', ''))
                dns[:] = []
    cm = os.path.join(cd, 'commands')
    if os.path.isdir(cm):
        for dp, dns, fns in os.walk(cm):
            for fn in sorted(fns):
                if fn.endswith('.md'):
                    p = os.path.join(dp, fn)
                    fm = frontmatter(p)
                    add(os.path.splitext(fn)[0], 'command', scope, p, fm, fm.get('description') or fm.get('title', ''))
    ag = os.path.join(cd, 'agents')
    if os.path.isdir(ag):
        for fn in sorted(os.listdir(ag)):
            if fn.endswith('.md'):
                p = os.path.join(ag, fn)
                fm = frontmatter(p)
                add(fm.get('name') or os.path.splitext(fn)[0], 'agent', scope, p, fm, fm.get('description') or fm.get('title', ''))
    for sname in ('settings.json', 'settings.local.json'):
        sp = os.path.join(cd, sname)
        if os.path.isfile(sp):
            scan_settings(sp, scope)
    mj = os.path.join(ws, '.mcp.json')
    if os.path.isfile(mj):
        try:
            d = json.load(io.open(mj, encoding='utf-8'))
            for k in (d.get('mcpServers') or {}):
                add(k, 'mcp', scope, mj, desc='.mcp.json 서버')
        except Exception as e:
            WARN.append('.mcp.json을 읽지 못함: %s (%s)' % (mj, e.__class__.__name__))


def scan_settings(sp, scope):
    try:
        d = json.load(io.open(sp, encoding='utf-8'))
    except Exception as e:
        WARN.append('settings를 읽지 못함: %s (%s)' % (sp, e.__class__.__name__))
        return
    hooks = d.get('hooks') or {}
    by_cmd = collections.defaultdict(list)
    for ev, lst in hooks.items():
        for g in lst or []:
            for h in g.get('hooks', []):
                by_cmd[h.get('command', '')].append(ev)
    for cmd, evs in by_cmd.items():
        add('hook:' + ','.join(sorted(set(evs)))[:60], 'hook', scope, sp, desc=cmd[:140])
    if d.get('statusLine'):
        add('statusLine', 'statusline', scope, sp, desc=str(d['statusLine'].get('command', ''))[:140])
    for k, v in (d.get('enabledPlugins') or {}).items():
        add(k, 'plugin-flag', scope, sp, desc='켜짐' if v else '꺼짐')
    for k in (d.get('mcpServers') or {}):
        add(k, 'mcp', scope, sp, desc='settings mcpServers')
    if d.get('enabledMcpjsonServers'):
        add(','.join(d['enabledMcpjsonServers']), 'mcp-enabled', scope, sp, desc='.mcp.json 서버 사용 허가')


def scan_plugins():
    ip = os.path.join(GLOBAL_CLAUDE, 'plugins', 'installed_plugins.json')
    if not os.path.isfile(ip):
        return
    enabled = {}
    try:
        enabled = json.load(io.open(os.path.join(GLOBAL_CLAUDE, 'settings.json'), encoding='utf-8')).get('enabledPlugins') or {}
    except Exception:
        pass
    d = json.load(io.open(ip, encoding='utf-8'))
    for pid, installs in (d.get('plugins') or {}).items():
        for inst in installs:
            path = inst.get('installPath', '')
            on = enabled.get(pid)
            state = '켜짐' if on else '꺼짐'
            if pid.startswith('nk@'):
                NOTE.append('nk 플러그인(%s)은 repo `nk\\`를 직접 훑는다. 설치 기록 경로: %s' % (state, path))
                continue
            if not os.path.isdir(path):
                (WARN if on else NOTE).append('플러그인 %s(%s)의 설치 경로가 없다: %s' % (pid, state, path))
                continue
            add(pid, 'plugin', '플러그인', path, desc='%s · v%s' % (state, inst.get('version', '?')))
            n0 = len(ROWS)
            scan_plugin_dir(path, '플러그인')
            for r in ROWS[n0:]:
                r['name'] = '%s:%s' % (pid.split('@')[0], r['name'])


def scan_plugin_dir(root, scope):
    """플러그인 구조(skills · agents · commands · hooks/hooks.json · .mcp.json)를 .claude 폴더처럼 훑는다."""
    scan_claude_dir(root, scope, ws=root)
    hj = os.path.join(root, 'hooks', 'hooks.json')
    if os.path.isfile(hj):
        scan_settings(hj, scope)


def scan_global():
    sk = os.path.join(GLOBAL_CLAUDE, 'skills')
    if os.path.isdir(sk):
        for dp, dns, fns in os.walk(sk):
            if 'SKILL.md' in fns:
                p = os.path.join(dp, 'SKILL.md')
                synced = 'synced' in low(p).split(os.sep)
                if not synced and os.path.basename(dp).startswith('wf-'):
                    dns[:] = []
                    continue          # WF 설치본: 정본(core global)을 이미 훑었다
                fm = frontmatter(p)
                add(fm.get('name') or os.path.basename(dp), 'skill', '바깥' if synced else '전역', p, fm,
                    ('계정 동기화 · ' if synced else '') + (fm.get('description') or ''))
                dns[:] = []
    for sub, typ in (('agents', 'agent'), ('commands', 'command')):
        d = os.path.join(GLOBAL_CLAUDE, sub)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.endswith('.md') and not fn.startswith('wf-'):   # wf-*는 WF 설치본(정본을 훑음)
                    p = os.path.join(d, fn)
                    fm = frontmatter(p)
                    add(fm.get('name') or os.path.splitext(fn)[0], typ, '전역', p, fm, fm.get('description', ''))
    sp = os.path.join(GLOBAL_CLAUDE, 'settings.json')
    if os.path.isfile(sp):
        scan_settings(sp, '전역')
    if os.path.isfile(CLAUDE_JSON):
        try:
            d = json.load(io.open(CLAUDE_JSON, encoding='utf-8'))
            for k in (d.get('mcpServers') or {}):
                add(k, 'mcp', '전역', CLAUDE_JSON, desc='사용자 범위 MCP')
            for proj, v in (d.get('projects') or {}).items():
                if never(proj) or 'appdata/local/temp' in proj.replace('\\', '/').lower():
                    continue
                for k in ((v or {}).get('mcpServers') or {}):
                    add(k, 'mcp', '워크스페이스', proj, desc='~/.claude.json 프로젝트 범위 MCP')
        except Exception as e:
            WARN.append('~/.claude.json을 읽지 못함 (%s)' % e.__class__.__name__)


def scan_pool_repo():
    gl = os.path.join(REPO, 'global')               # 전역 설치되는 core skill · agent(정본)
    if os.path.isdir(gl):
        scan_claude_dir(gl, 'core', ws=gl)
    st = os.path.join(REPO, 'shared-tools')
    if os.path.isdir(st):
        for fn in sorted(os.listdir(st)):
            if fn.endswith(SCRIPT_EXT):
                add_script(os.path.join(st, fn), 'core')
    pool = os.path.join(REPO, 'pool')
    if os.path.isdir(pool):
        for cat in sorted(os.listdir(pool)):
            cdir = os.path.join(pool, cat)
            if not os.path.isdir(cdir):
                continue
            scan_claude_dir(cdir, 'pool', ws=cdir)
            tools = os.path.join(cdir, 'tools')
            if os.path.isdir(tools):
                for dp, dns, fns in os.walk(tools):
                    dns[:] = [d for d in dns if d not in SKIP_DIRS]
                    for fn in sorted(fns):
                        if fn.endswith(SCRIPT_EXT):
                            add_script(os.path.join(dp, fn), 'pool')
    for dname in ('tools',):
        d = os.path.join(REPO, dname)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.endswith(SCRIPT_EXT):
                    add_script(os.path.join(d, fn), 'core')


def add_script(p, scope):
    meta, desc = script_head(p)
    add(os.path.basename(p), 'script', scope, p, meta, desc)


# ============================================================== 워크스페이스 훑기
def walk_roots():
    """(.claude 폴더 목록, 워크스페이스 목록). private-folder과 pool repo는 들어가지 않는다."""
    claude_dirs, workspaces = [], set()
    seen = set()
    for r in WORK_ROOTS:
        if not os.path.isdir(r):
            continue
        for dp, dns, fns in os.walk(r):
            key = low(dp)
            if key in seen or never(dp) or under(dp, REPO):
                dns[:] = []
                continue
            seen.add(key)
            dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and not d.lower().endswith(SCRIPT_SKIP_SUFFIX))
            dep = depth(dp, r)
            if os.path.basename(dp) == '.claude':
                claude_dirs.append(dp)
                dns[:] = []
                continue
            if dep >= 1 and 'CLAUDE.md' in fns and dep <= WORKSPACE_DEPTH:
                workspaces.add(dp)
            if '.claude' in dns and dep >= 1:
                workspaces.add(dp)
            if dep >= CLAUDE_DIR_DEPTH:
                dns[:] = [d for d in dns if d == '.claude']
    for _, r in CATEGORY_ROOTS:          # 카테고리 폴더 자체(카테고리 지시 CLAUDE.md)
        if os.path.isdir(r):
            workspaces.add(r)
    return claude_dirs, sorted(workspaces, key=low)


def owner(path, workspaces_sorted):
    best = None
    for w in workspaces_sorted:
        if under(path, w) and (best is None or len(w) > len(best)):
            best = w
    return best


def scan_scripts(workspaces):
    found = set()
    for ws in workspaces:
        if any(low(ws) == low(r) for r in WORK_ROOTS):
            continue
        for dp, dns, fns in os.walk(ws):
            if never(dp):
                dns[:] = []
                continue
            dns[:] = [d for d in dns if d not in SKIP_DIRS and d != '.claude' and d.lower() not in SCRIPT_SKIP_DIRS
                      and not d.lower().endswith(SCRIPT_SKIP_SUFFIX)]
            if depth(dp, ws) > INSIDE_DEPTH:
                dns[:] = []
                continue
            parts = [x.lower() for x in os.path.relpath(dp, ws).split(os.sep) if x and x != '.']
            if not set(parts) & TOOLDIRS:
                continue
            in_tooldir = parts and parts[-1] in TOOLDIRS
            for fn in fns:
                if not fn.endswith(SCRIPT_EXT):
                    continue
                if fn.endswith('.js') and SCRIPT_JS_ONLY_IN_TOOLDIR and not in_tooldir:
                    continue
                found.add(os.path.join(dp, fn))
    for p in sorted(found, key=low):
        add_script(p, '워크스페이스')


# ============================================================== 지식
KNOW_ORDER = ['재진입(지식 아님)', '결정', '기록', '함정 · 노하우', '방식', '도메인 지식', '이해 기록', '나']
FILE_RULES = [
    ('재진입(지식 아님)', re.compile(r'^(reentry|handoff|master_plan|status)\.md$', re.I)),
    ('결정', re.compile(r'^decisions?(_log)?\.md$', re.I)),
    ('기록', re.compile(r'^(worklog|session_log|conversation_log)\.md$', re.I)),
    ('함정 · 노하우', re.compile(r'^(insights|gotchas?|lessons?|pitfalls?|patches)\.md$', re.I)),
    ('방식', re.compile(r'^(claude\.md|app_principles\.md|content_model\.md|working-rules\.md)$', re.I)),
    ('도메인 지식', re.compile(r'^(glossary|curriculum)\.md$', re.I)),
    ('이해 기록', re.compile(r'^(understanding|misconceptions?|my_understanding|weakness(_db)?|confusions?)[\w-]*\.md$|^이해', re.I)),
]
DIR_RULES = [
    ('결정', re.compile(r'^decisions$', re.I)),
    ('기록', re.compile(r'^(sessions|session_logs?|rounds|chatlog|conversation_log)$', re.I)),
    ('도메인 지식', re.compile(r'^(notes|\d\d_notes|refs|references?|research|knowledge|\d\d_domains|domains|kb|specs?)$', re.I)),
    ('이해 기록', re.compile(r'^(understanding|misconceptions|weakness(_db)?|오답\w*)$', re.I)),
]
ME_DIRS = re.compile(r'^(my_career|_resume|10_master)$', re.I)
KNOW = []


def title_of(path):
    t = read_head(path, 3000)
    m = re.search(r'^#\s+(.+)$', t, re.M)
    return m.group(1).strip()[:90] if m else ''


def md_count(d):
    n = 0
    for dp, dns, fns in os.walk(d):
        dns[:] = [x for x in dns if x not in SKIP_DIRS]
        n += sum(1 for f in fns if f.lower().endswith('.md'))
    return n


def add_know(ws, kind, path, title):
    KNOW.append({'ws': ws, 'kind': kind, 'path': path, 'title': title, 'category': category(path)})


def scan_knowledge(workspaces):
    wl = [low(w) for w in workspaces]
    for ws in workspaces:
        for dp, dns, fns in os.walk(ws):
            if never(dp):
                dns[:] = []
                continue
            if dp != ws and low(dp) in wl:          # 안쪽 워크스페이스는 그쪽에서
                dns[:] = []
                continue
            dns[:] = sorted(d for d in dns if d not in SKIP_DIRS and d != '.claude' and d.lower() not in SCRIPT_SKIP_DIRS
                            and not d.lower().endswith(SCRIPT_SKIP_SUFFIX))
            if depth(dp, ws) > INSIDE_DEPTH:
                dns[:] = []
                continue
            # .claude\skills 폴더는 자산 지도에 있으므로 지식 지도에 넣지 않는다(잡음, R14 K6)
            for fn in sorted(fns):
                for kind, rx in FILE_RULES:
                    if rx.search(fn):
                        if kind == '방식' and fn.lower() == 'claude.md' and dp != ws:
                            break
                        add_know(ws, kind, os.path.join(dp, fn), title_of(os.path.join(dp, fn)))
                        break
            keep = []
            for d in dns:
                full = os.path.join(dp, d)
                hit = None
                if ME_DIRS.match(d) and '50_career' in low(full):
                    hit = '나'
                else:
                    for kind, rx in DIR_RULES:
                        if rx.match(d):
                            hit = kind
                            break
                if hit:
                    add_know(ws, hit, full, '(폴더 · md %d개)' % md_count(full))
                else:
                    keep.append(d)
            dns[:] = keep
    # 프로젝트 메모리(~/.claude/projects/<인코딩된 경로>/memory)
    proj = os.path.join(GLOBAL_CLAUDE, 'projects')
    enc = {re.sub(r'[^A-Za-z0-9]', '-', w): w for w in workspaces}
    if os.path.isdir(proj):
        for d in sorted(os.listdir(proj)):
            mem = os.path.join(proj, d, 'memory')
            if 'private-folder' in d.lower() or 'appdata-local-temp' in d.lower() or not os.path.isdir(mem):
                continue  # 비공개 폴더 · 임시(scratchpad) 세션 키는 지도에 넣지 않는다
            n = sum(1 for f in os.listdir(mem) if f.endswith('.md'))
            ws = enc.get(d)
            if ws:
                add_know(ws, '함정 · 노하우', mem, '(프로젝트 메모리 · md %d개)' % n)
            else:
                add_know('(워크스페이스 밖)', '함정 · 노하우', mem, '(프로젝트 메모리 · md %d개 · 키 %s)' % (n, d))
    # 뼈대 · 카테고리 공통 문서(pool repo)
    for rel, kind in (('skeleton', '방식'), ('categories', '방식')):
        d = os.path.join(REPO, rel)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.endswith('.md'):
                    add_know(REPO, kind, os.path.join(d, fn), title_of(os.path.join(d, fn)))
    mem = os.path.join(GLOBAL_CLAUDE, 'MEMORY.md')
    if os.path.isfile(mem):
        add_know(GLOBAL_CLAUDE, '나', mem, '전역 MEMORY.md (사람 · PC 사실)')


# ============================================================== 프로젝트 · 사용 횟수 (설계 12 §8.3 · §8.6)
PROJECTS = []
USAGE = {}                                       # wf-이름 → (과정 기록 "쓴 것"에 나온 횟수, 마지막 날짜)
USE_RX = re.compile(r'\bwf-[a-z][a-z0-9-]*')
DATE_RX = re.compile(r'(20\d\d-\d\d-\d\d)')


def line_after(lines, key):
    """key가 든 줄의 뒷부분, 없으면 다음 몇 줄 중 첫 내용 줄."""
    for i, ln in enumerate(lines):
        if key in ln:
            rest = ln.split(key, 1)[1].strip(' :*#—-|')
            if len(rest) > 3:
                return rest[:140]
            for nx in lines[i + 1:i + 6]:
                s = nx.strip().lstrip('-*> ').strip()
                if s and not s.startswith('#'):
                    return s[:140]
    return ''


def intro_of(ws):
    for fn in ('CLAUDE.md', 'README.md'):
        p = os.path.join(ws, fn)
        if os.path.isfile(p):
            m = re.search(r'^#\s+(.+)$', read_head(p, 4000), re.M)
            if m:
                return m.group(1).strip()[:120]
    return ''


def last_activity(ws):
    if os.path.isdir(os.path.join(ws, '.git')):
        try:
            r = subprocess.run(['git', '-C', ws, 'log', '-1', '--format=%cs'], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    newest = 0
    for d in (ws, os.path.join(ws, '00_META')):
        try:
            for x in os.scandir(d):
                if x.is_file():
                    newest = max(newest, x.stat().st_mtime)
        except OSError:
            pass
    return datetime.date.fromtimestamp(newest).isoformat() if newest else ''


def scan_usage(ws):
    meta = os.path.join(ws, '00_META')
    files = [os.path.join(meta, 'process_log.md')]
    rd = os.path.join(meta, 'rounds')
    if os.path.isdir(rd):
        files += [os.path.join(rd, f) for f in os.listdir(rd) if f.endswith('.md')]
    for p in files:
        if not os.path.isfile(p):
            continue
        date = ''
        for ln in io.open(p, encoding='utf-8', errors='replace').read().splitlines():
            if ln.startswith('## 과정 기록'):
                m = DATE_RX.search(ln)
                date = m.group(1) if m else date
            elif ln.lstrip('- ').startswith('쓴 것'):
                for name in set(USE_RX.findall(ln)):
                    n, last = USAGE.get(name, (0, ''))
                    USAGE[name] = (n + 1, max(last, date))


def scan_projects(workspaces):
    roots = {low(r) for _, r in CATEGORY_ROOTS}
    for ws in workspaces:
        if low(ws) in roots or under(ws, REPO) or never(ws):
            continue
        other = any(under(ws, o) for o in OTHER_PERSON)
        meta = os.path.join(ws, '00_META')
        re_path = os.path.join(meta, 'REENTRY.md')
        lines = read_head(re_path, 6000).splitlines() if os.path.isfile(re_path) else []
        wf = os.path.isdir(meta) and any(f.startswith('INIT_') for f in os.listdir(meta))
        frozen = any(under(ws, f) for f in FROZEN_SEEDS)
        PROJECTS.append({
            'name': os.path.basename(ws), 'path': ws, 'category': category(ws),
            'intro': '다른 사람의 작업 폴더' if other else (line_after(lines, '목적') or intro_of(ws)),
            'wf': '얼림(읽기 전용 seed)' if frozen else ('WF' if wf else '옛 방식'),
            'last': last_activity(ws),
            'next': '' if other else line_after(lines, '다음 첫 행동'),
        })
        if not other:
            scan_usage(ws)


def usage_of(name):
    n, last = USAGE.get(name, (0, ''))
    return '%d회%s' % (n, (' · ' + last) if last else '')


def write_projects(mask, now):
    for p in PROJECTS:
        for f in ('name', 'path', 'intro', 'next'):
            p[f] = mask(p[f])
    order = ['C0', 'C1', 'C2', 'C3']
    L = ['# 프로젝트 지도', '',
         '> 기계가 만든 파일이다. 손으로 고치지 않는다. 다시 굽기: `python <core>/tools/map.py --build` (생성 %s)' % now,
         '> 소개 = 재진입 카드의 "목적" 줄 → CLAUDE.md · README 첫 제목. 방식 = WF(`00_META\\INIT_*.md` 있음) · 옛 방식(다음에 열 때 `/wf-project-init` 업그레이드). '
         '마지막 활동 = git 마지막 commit 날짜(없으면 파일 시각). 카테고리 = 지금 위치(옛 위치면 이동 목록의 카테고리).', '',
         '| 카테고리 | 프로젝트 | WF | 옛 방식 |', '|---|---|---|---|']
    cats = order + sorted({p['category'] for p in PROJECTS} - set(order))
    for c in cats:
        ps = [p for p in PROJECTS if p['category'] == c]
        if ps:
            L.append('| %s | %d | %d | %d |' % (c, len(ps), sum(p['wf'] == 'WF' for p in ps), sum(p['wf'] != 'WF' for p in ps)))
    L.append('')
    for c in cats:
        ps = sorted([p for p in PROJECTS if p['category'] == c], key=lambda p: p['last'], reverse=True)
        if not ps:
            continue
        L += ['## %s' % c, '', '| 프로젝트 | 소개 | 방식 | 마지막 활동 | 다음 첫 행동 | 경로 |', '|---|---|---|---|---|---|']
        for p in ps:
            L.append('| %s | %s | %s | %s | %s | `%s` |' % (cell(p['name']), cell(p['intro']), p['wf'], p['last'], cell(p['next']), cell(p['path'])))
        L.append('')
    L += ['## 지도에 넣지 않는 곳', '', '- `<private-folder>` — 그 폴더에서 연 세션만 다룬다. 내용은 지도에 없다.', '']
    with io.open(os.path.join(MAPS, 'projects.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')


def write_wf(mask, now):
    L = ['# WF 사용법', '',
         '> 기계가 만든 파일이다(뼈대 · core 정본의 앞머리에서). `/wf-help`가 이 파일로 답한다. 생성 %s' % now,
         '> 이름 규칙: `wf-*` = WF가 관리(전역 또는 pool에서 복사), 주제 prefix(`vca-` 등) = 그 주제 것, prefix 없음 = Claude Code 기본.', '']
    sk = os.path.join(REPO, 'skeleton', 'skeleton.md')
    text = io.open(sk, encoding='utf-8').read() if os.path.isfile(sk) else ''
    m = re.search(r'^## 세션의 순간\n(.*?)(?=^## )', text, re.S | re.M)
    L += ['## 세션의 순간 — 무엇이 끼어드나', '', (m.group(1).strip() if m else '(뼈대에서 찾지 못함)'), '']
    for typ, title in (('skill', '전역 skill — 어디서나. `/이름`으로 부르거나, 설명에 든 말로 부르면 된다'),
                       ('agent', '전역 agent — skill의 고정 단계가 부른다. 사용자가 직접 부를 일은 없다')):
        rows = sorted([r for r in ROWS if r['scope'] == 'core' and r['type'] == typ], key=lambda r: r['name'])
        L += ['## ' + title, '', '| 이름 | 언제 | 누가 · 언제 부르나 | 설명(부르는 말) | 쓰인 횟수 |', '|---|---|---|---|---|']
        for r in rows:
            by = frontmatter(r['location']).get('called_by') or ('사용자(`/%s` 또는 설명의 말)' % r['name'] if typ == 'skill' else MISSING)
            L.append('| `%s` | %s | %s | %s | %s |' % (r['name'], cell(r['when']), cell(by), cell(mask(r['desc'])), usage_of(r['name'])))
        L.append('')
    tools = sorted([r for r in ROWS if r['scope'] == 'core' and r['type'] == 'script'], key=lambda r: r['location'])
    L += ['## 도구', '', '| 이름 | 언제 | 위치 |', '|---|---|---|']
    for r in tools:
        L.append('| `%s` | %s | `%s` |' % (r['name'], cell(r['when'] if r['when'] != MISSING else r['desc'][:80]), cell(mask(r['location']))))
    L.append('')
    pool = sorted([r for r in ROWS if r['scope'] == 'pool' and r['type'] in ('skill', 'agent')], key=lambda r: (r['category'], r['name']))
    L += ['## pool — 주제가 `/wf-project-init` 때 골라 복사해 간다', '', '| 이름 | 카테고리 | 종류 | 언제 | 상태 | 쓰인 횟수 |', '|---|---|---|---|---|---|']
    for r in pool:
        L.append('| `%s` | %s | %s | %s | %s | %s |' % (r['name'], r['category'], r['type'], cell(r['when']), r['status'], usage_of(r['name'])))
    L += ['', '쓰인 횟수 = 주제들의 과정 기록 "쓴 것" 줄에 그 이름이 나온 수. 90일 넘게 0회면 wrap이 retired 후보로 올린다.', '']
    with io.open(os.path.join(MAPS, 'wf.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')


# ============================================================== 출력
def masker():
    if redact_check is None:
        return None
    terms = redact_check.load_terms(sections=MASK_SECTIONS)
    if not terms:
        return None
    comp = redact_check.compile_terms(terms)
    return lambda s: redact_check.mask_text(s, comp) if s else s


def cell(s):
    return str(s).replace('|', '\\|').replace('\n', ' ')


def write_maps(mask):
    os.makedirs(MAPS, exist_ok=True)
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for r in ROWS:
        for k in COLS:
            r[k] = mask(r[k])
    for k in KNOW:
        for f in ('ws', 'path', 'title'):
            k[f] = mask(k[f])
    with io.open(os.path.join(MAPS, 'assets.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(COLS) + '\n')
        for r in ROWS:
            f.write('\t'.join(str(r[c]).replace('\t', ' ').replace('\n', ' ') for c in COLS) + '\n')

    cats = ['C1', 'C2', 'C3', '공통', '뼈대', '전역', '바깥']
    cats += sorted({r['category'] for r in ROWS} - set(cats), key=lambda c: (c == '미분류', c))
    types = ['skill', 'agent', 'command', 'hook', 'mcp', 'plugin', 'script']
    L = []
    w = L.append
    w('# 자산 지도')
    w('')
    w('> 기계가 만든 파일이다. 손으로 고치지 않는다. 다시 굽기: `python <core>/tools/map.py --build` (생성 %s)' % now)
    w('> 조회: `python <core>/tools/map.py --kind <kind>` · `--when "<낱말 낱말>"` · `--workspaces "<낱말>"`. 칸이 "%s"이면 원천 앞머리에 그 칸이 없다는 뜻이다(추측하지 않음).' % MISSING)
    w('> 경고 %d · 참고 %d — 맨 아래.' % (len(WARN), len(NOTE)))
    w('')
    w('## 카테고리 × 종류')
    w('')
    cnt = collections.Counter((r['category'], r['type'] if r['type'] in types else '기타') for r in ROWS)
    w('| 카테고리 | ' + ' | '.join(types) + ' | 기타 | 합 |')
    w('|---|' + '---|' * (len(types) + 2))
    for c in cats:
        vals = [cnt[(c, t)] for t in types + ['기타']]
        if sum(vals):
            w('| %s | %s | %d |' % (c, ' | '.join(str(v) for v in vals), sum(vals)))
    w('')
    filled = sum(1 for r in ROWS if r['type'] in ('skill', 'agent', 'command') and r['when'] != MISSING)
    total = sum(1 for r in ROWS if r['type'] in ('skill', 'agent', 'command'))
    w('skill · agent · command %d개 중 `when`이 적힌 것 %d개.' % (total, filled))
    w('')
    for c in cats:
        rows = [r for r in ROWS if r['category'] == c]
        if not rows:
            continue
        w('## %s' % c)
        w('')
        main = [r for r in rows if r['type'] != 'script']
        if main:
            w('| 이름 | 종류 | when | kind | status | 위치 |')
            w('|---|---|---|---|---|---|')
            for r in sorted(main, key=lambda r: (r['scope'] != 'pool', r['type'], r['name'].lower())):
                when = r['when'] if r['when'] != MISSING else (MISSING + (' · ' + r['desc'][:70] if r['desc'] else ''))
                w('| %s | %s | %s | %s | %s | `%s` |' % (cell(r['name']), r['type'], cell(when), r['kind'], r['status'], cell(r['location'])))
            w('')
        scripts = [r for r in rows if r['type'] == 'script']
        if scripts:
            groups = collections.defaultdict(list)
            for r in scripts:
                d = os.path.dirname(r['location'])
                groups[d].append(r)
            w('script %d개 (폴더별):' % len(scripts))
            w('')
            for d in sorted(groups, key=str.lower):
                g = groups[d]
                tagged = [x for x in g if x['when'] != MISSING]
                names = ', '.join(x['name'] for x in g[:15]) + (' 외 %d' % (len(g) - 15) if len(g) > 15 else '')
                w('- `%s` (%d): %s%s' % (d, len(g), names, (' — when 있음 %d' % len(tagged)) if tagged else ''))
            w('')
    dup = collections.defaultdict(list)
    for r in ROWS:
        if r['type'] in ('skill', 'agent', 'command') and r['scope'] != '바깥':
            dup[(r['type'], r['name'].split(':')[-1].lower())].append(r['location'])
    dups = {k: v for k, v in dup.items() if len(v) > 1}
    w('## 같은 이름이 여러 곳에 있는 것 (%d)' % len(dups))
    w('')
    for (t, n), locs in sorted(dups.items()):
        w('- %s `%s`: %d곳' % (t, n, len(locs)))
    w('')
    w('## 경고 (%d)' % len(WARN))
    w('')
    for x in WARN:
        w('- ' + mask(x))
    w('')
    w('## 참고 (%d)' % len(NOTE))
    w('')
    for x in NOTE[:80]:
        w('- ' + mask(x))
    if len(NOTE) > 80:
        w('- … 외 %d' % (len(NOTE) - 80))
    with io.open(os.path.join(MAPS, 'assets.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')

    K = []
    k = K.append
    k('# 지식 지도')
    k('')
    k('> 기계가 만든 파일이다. 손으로 고치지 않는다. 다시 굽기: `python <core>/tools/map.py --build` (생성 %s)' % now)
    k('> 종류는 결과물 문서 §3.1(기록 · 결정 · 함정 · 노하우 · 방식 · 도메인 지식 · 이해 기록 · 나)과 "재진입(지식 아님)". 파일 · 폴더 이름 규칙으로만 가른다. 내용은 복사하지 않고 경로와 첫 제목만.')
    k('')
    kc = collections.Counter(x['kind'] for x in KNOW)
    k('| 종류 | 수 |')
    k('|---|---|')
    for kind in KNOW_ORDER:
        k('| %s | %d |' % (kind, kc[kind]))
    k('')
    by_ws = collections.defaultdict(list)
    for x in KNOW:
        by_ws[x['ws']].append(x)
    by_cat = collections.defaultdict(list)
    for ws in by_ws:
        by_cat[by_ws[ws][0]['category'] if ws != '(워크스페이스 밖)' else '워크스페이스 밖'].append(ws)
    for c in sorted(by_cat, key=lambda c: (c not in ('C1', 'C2', 'C3'), c)):
        k('## %s' % c)
        k('')
        for ws in sorted(by_cat[c], key=str.lower):
            k('### `%s`' % ws)
            k('')
            for x in sorted(by_ws[ws], key=lambda x: (KNOW_ORDER.index(x['kind']), x['path'].lower())):
                rel = x['path'][len(ws):].lstrip('\\/') if x['path'].lower().startswith(ws.lower()) else x['path']
                k('- %s · `%s`%s' % (x['kind'], rel or x['path'], (' — ' + cell(x['title'])) if x['title'] else ''))
            k('')
    with io.open(os.path.join(MAPS, 'knowledge.md'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(K) + '\n')
    write_projects(mask, now)
    write_wf(mask, now)


def build():
    global MOVES
    MOVES = load_move_list()
    scan_global()
    scan_plugins()
    scan_pool_repo()
    claude_dirs, workspaces = walk_roots()
    for cd in claude_dirs:
        scan_claude_dir(cd, '워크스페이스')
    scan_scripts(workspaces)
    scan_knowledge(workspaces)
    scan_projects(workspaces)
    for r in ROWS:
        assert not never(r['location']), r['location']
    for x in KNOW:
        assert not never(x['path']), x['path']
    return claude_dirs, workspaces


# ============================================================== 조회
def query(a):
    tsv = os.path.join(MAPS, 'assets.tsv')
    if not os.path.isfile(tsv):
        print('지도가 없다. 조회는 지도를 굽지 않는다: python <core>/tools/map.py --build')
        return 2
    rows = list(csv.DictReader(io.open(tsv, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE))
    out = []
    words = [x.lower() for x in (a.when or '').replace(',', ' ').split() if len(x) > 1]
    score = {}
    for r in rows:
        if a.kind and r['kind'].lower() != a.kind.lower():
            continue
        if words:
            hay = ' '.join((r['when'], r['desc'], r['name'], r['kind'], r['location'])).lower()
            s = sum(1 for wd in words if wd in hay)
            if s == 0:
                continue
            score[id(r)] = s
        if a.category and r['category'].lower() != a.category.lower():
            continue
        if a.type and r['type'] != a.type:
            continue
        if not a.all and (r['type'] not in ('skill', 'agent', 'command', 'script') or r['scope'] == '바깥'):
            continue
        if not a.all and r['type'] == 'script' and r['when'] == MISSING:
            continue
        out.append(r)
    rank = {'pool': 0, 'core': 1, '워크스페이스': 2, '플러그인': 3, '전역': 4}
    out.sort(key=lambda r: (-score.get(id(r), 0), rank.get(r['scope'], 9), r['status'] != 'active', r['when'] == MISSING, r['type'], r['name']))
    print('자산 %d개 중 %d개 (상위 %d):' % (len(rows), len(out), min(a.limit, len(out))))
    for r in out[:a.limit]:
        when = r['when'] if r['when'] != MISSING else r['desc'][:60]
        print('- %s [%s · %s · %s] %s — %s' % (r['name'], r['type'], r['category'], r['kind'], when, r['location']))
    return 0


def query_workspaces(a):
    """선례 찾기: 지식 지도의 워크스페이스 절 가운데 낱말이 하나라도 맞는 것을 맞은 수 순으로."""
    km = os.path.join(MAPS, 'knowledge.md')
    if not os.path.isfile(km):
        print('지식 지도가 없다: python <core>/tools/map.py --build')
        return 2
    words = [x.lower() for x in (a.workspaces or '').replace(',', ' ').split() if len(x) > 1]
    secs, cur = [], None
    for line in io.open(km, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.startswith('### '):
            cur = [line[4:].strip('` '), []]
            secs.append(cur)
        elif cur is not None and line.startswith('- '):
            cur[1].append(line[2:])
    hits = []
    for name, lines in secs:
        hay = (name + ' ' + ' '.join(lines)).lower()
        s = sum(1 for wd in words if wd in hay)
        if s:
            hits.append((s, name, lines))
    hits.sort(key=lambda h: (-h[0], h[1]))
    print('워크스페이스 %d곳 중 %d곳 (상위 %d):' % (len(secs), len(hits), min(a.limit, len(hits))))
    for s, name, lines in hits[:a.limit]:
        print('- %s (맞은 낱말 %d)' % (name, s))
        for l in [l for l in lines if any(wd in l.lower() for wd in words)][:3] or lines[:2]:
            print('    · ' + l)
    return 0


def main_build(quiet=False):
    mask = masker()
    if mask is None:
        print('map: 금지어 원천을 읽지 못해 지도를 쓰지 않는다 (pool redact-check · ~/.claude/private/redact)')
        return 2
    claude_dirs, workspaces = build()
    write_maps(mask)
    if not quiet:
        c = collections.Counter(r['type'] for r in ROWS)
        print('map: 자산 %d (%s) · .claude %d곳 · 워크스페이스 %d · 지식 %d · 경고 %d · 참고 %d' % (
            len(ROWS), ', '.join('%s %d' % kv for kv in c.most_common()), len(claude_dirs), len(workspaces),
            len(KNOW), len(WARN), len(NOTE)))
        print('  → %s' % MAPS)
    return 0


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='자산 · 지식 지도 생성기 + 조회')
    ap.add_argument('--kind')
    ap.add_argument('--when')
    ap.add_argument('--category')
    ap.add_argument('--type')
    ap.add_argument('--limit', type=int, default=12)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--workspaces', help='선례 워크스페이스 찾기(낱말 OR)')
    ap.add_argument('--build', action='store_true', help='지도를 다시 굽는다(조회 인자와 같이 쓰지 않음)')
    ap.add_argument('--quiet', action='store_true', help='굽기 결과 한 줄만(hook · install이 부를 때)')
    a = ap.parse_args()
    if a.workspaces:
        return query_workspaces(a)
    if a.kind or a.when or a.category or a.type:
        return query(a)
    if not (a.build or a.check):
        ap.print_help()
        print('\n조회: --when "낱말 낱말" · --kind · --category · --type · --workspaces "낱말". 다시 굽기: --build')
        return 0
    rc = main_build(quiet=a.quiet)
    if a.quiet and not rc:
        print('map: 프로젝트 %d · 자산 %d · 지식 %d → %s' % (len(PROJECTS), len(ROWS), len(KNOW), MAPS))
    if rc:
        return rc
    if a.check:
        for x in WARN:
            print('  경고: ' + x)
        return 1 if WARN else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
