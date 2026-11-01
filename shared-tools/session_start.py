r"""session_start.py — WF SessionStart hook. 세션이 열릴 때 몇 줄만 보인다(stdout이 세션 맥락에 들어간다).

언제: settings.json의 SessionStart hook이 모든 세션 시작 · resume · compact 뒤에 부른다. 5초 안에 끝나고, 무엇이 실패해도 세션은 연다.
kind: hook
status: active

보이는 것(해당할 때만):
  1. 재진입 카드 머리: cwd\00_META\REENTRY.md의 앞부분(목적 · 지금 · 사용자 차례 · 다음 첫 행동)
  2. wrap 빠짐: 재진입 카드보다 새 commit이 있거나 commit 안 된 변경이 남아 있으면 한 줄
  3. core 설치 차이: 정본 HEAD가 INSTALLED.json의 commit과 다르면 한 줄
  4. 지도: 24시간보다 오래됐으면 background로 다시 굽는다(기다리지 않음, 보이는 것 없음)
"""
import json
import os
import pathlib
import subprocess
import sys
import time

HOME = pathlib.Path(os.path.expanduser("~")) / ".claude" / "workflow"
MAPS = HOME / "maps"
CARD_LINES = 28


def git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8", timeout=2)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def card(cwd, out):
    p = cwd / "00_META" / "REENTRY.md"
    if not p.is_file():
        return None
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    out.append("[WF] 재진입 카드 %s (앞 %d줄):" % (p, min(CARD_LINES, len(lines))))
    out.extend(lines[:CARD_LINES])
    if len(lines) > CARD_LINES:
        out.append("… (나머지는 파일에서)")
    return p.stat().st_mtime


def wrap_missing(cwd, card_mtime, out):
    if card_mtime is None or git(cwd, "rev-parse", "--is-inside-work-tree") != "true":
        return
    if not list((cwd / "00_META").glob("INIT_*.md")):
        out.append("[WF] 이 폴더는 아직 WF 방식이 아니다(INIT 기록 없음). 이 프로젝트로 일을 이어 가면 먼저 /wf-project-init 업그레이드를 권한다(옛 위치면 카테고리 폴더에서 열어 옮기며).")
        return
    last = git(cwd, "log", "-1", "--format=%ct")
    dirty = git(cwd, "status", "--porcelain")
    newer = last and int(last) > card_mtime + 120
    if newer or dirty:
        why = []
        if newer:
            why.append("재진입 카드보다 새 commit")
        if dirty:
            why.append("commit 안 된 변경 %d개" % len(dirty.splitlines()))
        out.append("[WF] 지난 세션은 wrap 없이 끝난 것으로 보임(%s). 사용자가 다른 일을 청하지 않았으면 먼저 /wf-project-wrap을 권한다." % ", ".join(why))


def install_drift(out):
    try:
        info = json.loads((HOME / "INSTALLED.json").read_text(encoding="utf-8"))
    except Exception:
        return
    core = info.get("core")
    head = git(core, "rev-parse", "--short", "HEAD") if core else None
    if head and not str(info.get("commit", "")).startswith(head):
        try:   # commit만 다르고 설치 대상 파일은 같으면(core 도구만 바뀜) 알리지 않는다
            r = subprocess.run([sys.executable, str(pathlib.Path(core) / "tools" / "install.py"), "--check"],
                               capture_output=True, text=True, encoding="utf-8", timeout=3)
            if r.returncode == 0:
                return
        except Exception:
            pass
        out.append("[WF] core 정본(%s)이 설치본(%s)보다 새것이다. core를 고친 세션이면: python %s/tools/install.py --check"
                   % (head, info.get("commit"), core.replace("\\", "/")))


def refresh_maps():
    try:
        info = json.loads((HOME / "INSTALLED.json").read_text(encoding="utf-8"))
        mp = pathlib.Path(info["core"]) / "tools" / "map.py"
        stamp = MAPS / "assets.md"
        if stamp.exists() and time.time() - stamp.stat().st_mtime < 24 * 3600:
            return
        if not mp.exists():
            return
        flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([sys.executable, str(mp), "--build", "--quiet"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    except Exception:
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    cwd = None
    try:
        data = json.loads(sys.stdin.read() or "{}")
        cwd = data.get("cwd")
    except Exception:
        pass
    cwd = pathlib.Path(cwd or os.getcwd())
    out = []
    try:
        m = card(cwd, out)
        wrap_missing(cwd, m, out)
    except Exception:
        pass
    try:
        install_drift(out)
    except Exception:
        pass
    refresh_maps()
    if out:
        print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
