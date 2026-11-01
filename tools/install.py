r"""install.py — WF core 정본을 ~/.claude\ 로 설치한다. 세션이 읽는 것은 설치본뿐이다.

언제: core(뼈대 · 카테고리 문서 · 전역 skill · agent · 공용 도구)를 고친 뒤. wrap이 --check로 설치할 차이를 알린다.
kind: tool
status: active

사용:
  python install.py              dry-run: 무엇이 어디로 복사 · 갱신 · 제거되는지
  python install.py --apply      설치(+ INSTALLED.json, 지도 다시 굽기)
  python install.py --check      정본과 설치본이 다른 것만(다르면 종료 코드 1)

설치 대상(정본 → 설치본):
  skeleton\skeleton.md          → ~\.claude\workflow\skeleton.md
  categories\c?.md               → ~\.claude\workflow\categories\c?.md
  shared-tools\*                 → ~\.claude\workflow\tools\
  global\skills\wf-*\            → ~\.claude\skills\wf-*\            (/wf-... 로 불림)
  global\agents\wf-*.md          → ~\.claude\agents\wf-*.md
설치본에서만 있는 wf-* skill · agent(정본에서 지운 것)는 제거한다. wf-로 시작하지 않는 것은 건드리지 않는다.
전역 CLAUDE.md · 카테고리 폴더 CLAUDE.md · settings.json은 이 script가 고치지 않는다(경로는 한 번 바꾸면 그대로다).
"""
import argparse
import datetime
import filecmp
import json
import os
import pathlib
import shutil
import subprocess
import sys

CORE = pathlib.Path(__file__).resolve().parent.parent
HOME = pathlib.Path(os.path.expanduser("~")) / ".claude"
WF = HOME / "workflow"


def pairs():
    """(정본 파일, 설치 파일) 목록."""
    out = [(CORE / "skeleton" / "skeleton.md", WF / "skeleton.md")]
    for p in sorted((CORE / "categories").glob("c*.md")):
        out.append((p, WF / "categories" / p.name))
    for p in sorted((CORE / "shared-tools").glob("*")):
        if p.is_file() and p.suffix in {".py", ".md", ".js", ".mjs"}:
            out.append((p, WF / "tools" / p.name))
    for d in sorted((CORE / "global" / "skills").glob("wf-*")):
        for p in sorted(d.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                out.append((p, HOME / "skills" / d.name / p.relative_to(d)))
    for p in sorted((CORE / "global" / "agents").glob("wf-*.md")):
        out.append((p, HOME / "agents" / p.name))
    return out


def stale():
    """설치본에만 있는 wf-* (정본에서 지운 것)."""
    want_sk = {d.name for d in (CORE / "global" / "skills").glob("wf-*")}
    want_ag = {p.name for p in (CORE / "global" / "agents").glob("wf-*.md")}
    out = []
    if (HOME / "skills").is_dir():
        out += [d for d in (HOME / "skills").glob("wf-*") if d.is_dir() and d.name not in want_sk]
    if (HOME / "agents").is_dir():
        out += [p for p in (HOME / "agents").glob("wf-*.md") if p.name not in want_ag]
    return out


def head():
    r = subprocess.run(["git", "-C", str(CORE), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    d = subprocess.run(["git", "-C", str(CORE), "status", "--porcelain"], capture_output=True, text=True)
    return (r.stdout.strip() or "?") + ("+dirty" if d.stdout.strip() else "")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    todo = []
    for src, dst in pairs():
        if not dst.exists():
            todo.append(("새로", src, dst))
        elif not filecmp.cmp(src, dst, shallow=False):
            todo.append(("갱신", src, dst))
    gone = stale()

    if a.check:
        for kind, src, dst in todo:
            print("%s  %s" % (kind, dst))
        for p in gone:
            print("제거  %s" % p)
        print("설치할 차이: %d" % (len(todo) + len(gone)))
        return 1 if (todo or gone) else 0

    for kind, src, dst in todo:
        print("%s  %s  ←  %s" % (kind, dst, src.relative_to(CORE)))
    for p in gone:
        print("제거  %s" % p)
    print("합계: 새로 %d · 갱신 %d · 제거 %d" % (sum(k == "새로" for k, _, _ in todo), sum(k == "갱신" for k, _, _ in todo), len(gone)))
    if not a.apply:
        print("(dry-run — --apply로 설치)")
        return 0

    for kind, src, dst in todo:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for p in gone:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    WF.mkdir(parents=True, exist_ok=True)
    info = {"core": str(CORE), "commit": head(), "installed_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "files": len(pairs())}
    (WF / "INSTALLED.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print("설치함: %s (core %s)" % (WF / "INSTALLED.json", info["commit"]))
    left = [d for s, d in pairs() if not d.exists() or not filecmp.cmp(s, d, shallow=False)]
    print("확인: 설치 뒤 남은 차이 %d" % len(left))
    mp = CORE / "tools" / "map.py"
    if mp.exists():
        r = subprocess.run([sys.executable, str(mp), "--build", "--quiet"], capture_output=True, text=True, encoding="utf-8")
        print("지도: %s" % ((r.stdout.strip().splitlines() or ["?"])[-1] if r.returncode == 0 else "실패 " + r.stderr.strip()[-200:]))
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
