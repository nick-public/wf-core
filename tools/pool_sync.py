"""pool <-> project copy tracking (the user's Workflow 2026 §5.5).

  python pool_sync.py copy <pool item> <topic dir>      copy a pool item into the topic, record origin/base
  python pool_sync.py status <topic dir>                compare each copy with pool (base and HEAD)
  python pool_sync.py upstream <topic dir> <dest>       push a local improvement back to pool (commit + CHANGELOG)
  python pool_sync.py fork <topic dir> <dest> "<why>"   mark a copy as an intentional topic-only fork
  python pool_sync.py sync <topic dir> [--apply]        update untouched copies to pool HEAD
  python pool_sync.py archive <topic dir> <path>        move a file/folder under .claude to 90_Archive/claude/ (git mv if tracked)

<pool item> is relative to the pool repo, e.g. pool/c1/skills/wf-study-session or pool/common/agents/wf-ui-qa.md.
<dest> is the path inside the topic, e.g. .claude/skills/ask.
Tracking lives in <topic>/.claude/pool.json. origin/base are also written into the copy's front matter.
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

POOL = pathlib.Path(__file__).resolve().parent.parent
FORBIDDEN = pathlib.Path(r"<private-folder>")
INJECTED = re.compile(r"^\s*(origin|base|fork):.*$")


def guard(p):
    p = pathlib.Path(p).resolve()
    assert not str(p).lower().startswith(str(FORBIDDEN).lower()), "refused: private folder"
    return p


def git(*args):
    r = subprocess.run(["git", "-C", str(POOL), *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def head():
    return git("rev-parse", "--short", "HEAD").strip()


def manifest_path(topic):
    return topic / ".claude" / "pool.json"


def load(topic):
    mp = manifest_path(topic)
    return json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}


def save(topic, m):
    mp = manifest_path(topic)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dest_for(item):
    item = item.replace("\\", "/").strip("/")
    name = item.split("/")[-1]
    kind = "agents" if "/agents/" in item else "skills"
    return f".claude/{kind}/{name}"


def files_of(root):
    root = pathlib.Path(root)
    if root.is_file():
        return {"": root}
    return {str(p.relative_to(root)).replace("\\", "/"): p for p in sorted(root.rglob("*")) if p.is_file()}


def clean(text):
    return "\n".join(l for l in text.replace("\r\n", "\n").split("\n") if not INJECTED.match(l)).strip()


def pool_text(rev, item, rel):
    path = item if not rel else f"{item}/{rel}"
    r = subprocess.run(["git", "-C", str(POOL), "show", f"{rev}:{path}"], capture_output=True, text=True, encoding="utf-8")
    return None if r.returncode != 0 else r.stdout


def main_file(dest_path):
    if dest_path.is_file():
        return dest_path
    s = dest_path / "SKILL.md"
    return s if s.exists() else None


def inject(md, origin, base, fork=None):
    if md is None:
        return
    t = md.read_text(encoding="utf-8")
    lines = [l for l in t.replace("\r\n", "\n").split("\n") if not INJECTED.match(l)]
    if not lines or lines[0].strip() != "---":
        return
    end = lines.index("---", 1)
    add = [f"origin: {origin}", f"base: {base}"] + ([f"fork: {fork}"] if fork else [])
    if any(l.strip() == "metadata:" for l in lines[1:end]):
        i = next(i for i in range(1, end) if lines[i].strip() == "metadata:")
        lines[i + 1:i + 1] = ["  " + a for a in add]
    else:
        lines[end:end] = add
    md.write_text("\n".join(lines), encoding="utf-8")


def state(topic, dest, e):
    local = files_of(topic / dest)
    base_changed = head_changed = False
    for rel, p in local.items():
        lt = clean(p.read_text(encoding="utf-8", errors="replace"))
        bt = pool_text(e["base"], e["origin"], rel)
        ht = pool_text("HEAD", e["origin"], rel)
        if bt is None or clean(bt) != lt:
            base_changed = True
        if ht is None or clean(ht or "") != clean(bt or ""):
            head_changed = True
    if e.get("fork"):
        return "fork"
    if not base_changed:
        return "pool-newer" if head_changed else "same"
    return "both-changed" if head_changed else "local-changed"


def cmd_copy(item, topic):
    topic = guard(topic)
    src = guard(POOL / item)
    if not src.exists():
        raise SystemExit(f"no such pool item: {item}")
    dest = dest_for(item)
    dp = topic / dest
    if dp.exists():
        raise SystemExit(f"already exists: {dp}")
    dp.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dp)
    else:
        shutil.copy2(src, dp.with_suffix(src.suffix) if dp.suffix == "" else dp)
    b = head()
    inject(main_file(dp), item, b)
    m = load(topic)
    m[dest] = {"origin": item.replace("\\", "/"), "base": b}
    save(topic, m)
    print(f"copied {item} -> {dp} (base {b})")


def cmd_status(topic):
    topic = guard(topic)
    m = load(topic)
    if not m:
        print("no pool copies")
        return
    for dest, e in m.items():
        print(f"{state(topic, dest, e):14} {dest}  <- {e['origin']}@{e['base']}" + (f"  fork: {e['fork']}" if e.get("fork") else ""))


def cmd_upstream(topic, dest):
    topic = guard(topic)
    m = load(topic)
    e = m[dest]
    src = topic / dest
    target = POOL / e["origin"]
    for rel, p in files_of(src).items():
        out = target if not rel else target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".md":
            out.write_text(clean(p.read_text(encoding="utf-8")) + "\n", encoding="utf-8")
        else:
            shutil.copy2(p, out)
    log = POOL / "CHANGELOG.md"
    with log.open("a", encoding="utf-8") as f:
        f.write(f"- {e['origin']}: improvement from {topic.name}\n")
    git("add", "--", e["origin"], "CHANGELOG.md")
    git("commit", "-m", f"pool: {e['origin']} improved in {topic.name}")
    e["base"] = head()
    inject(main_file(src), e["origin"], e["base"])
    save(topic, m)
    print(f"upstreamed {dest} -> {e['origin']} (now {e['base']})")


def cmd_fork(topic, dest, why):
    topic = guard(topic)
    m = load(topic)
    m[dest]["fork"] = why
    inject(main_file(topic / dest), m[dest]["origin"], m[dest]["base"], why)
    save(topic, m)
    print(f"fork recorded: {dest}")


def cmd_sync(topic, apply):
    topic = guard(topic)
    m = load(topic)
    h = head()
    for dest, e in m.items():
        st = state(topic, dest, e)
        if st != "pool-newer":
            continue
        print(f"{'update' if apply else 'would update'} {dest} {e['base']} -> {h}")
        if apply:
            dp = topic / dest
            src = POOL / e["origin"]
            if src.is_dir():
                shutil.rmtree(dp)
                shutil.copytree(src, dp)
            else:
                shutil.copy2(src, dp)
            e["base"] = h
            inject(main_file(dp), e["origin"], h)
    if apply:
        save(topic, m)


def cmd_archive(topic, rel):
    topic = guard(topic)
    rel = rel.replace("\\", "/").strip("/")
    assert rel.startswith(".claude/"), "archive only moves things under .claude/"
    src = topic / rel
    if not src.exists():
        raise SystemExit(f"no such path: {src}")
    dst = topic / "90_Archive" / "claude" / rel[len(".claude/"):]
    if dst.exists():
        raise SystemExit(f"already archived: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tracked = subprocess.run(["git", "-C", str(topic), "ls-files", "--error-unmatch", rel],
                             capture_output=True, text=True).returncode == 0
    if tracked:
        r = subprocess.run(["git", "-C", str(topic), "mv", rel, str(dst.relative_to(topic)).replace("\\", "/")],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise SystemExit(f"git mv failed: {r.stderr.strip()}")
    else:
        shutil.move(str(src), str(dst))
    m = load(topic)
    if rel in m:
        m.pop(rel)
        save(topic, m)
    print(f"archived {rel} -> {dst.relative_to(topic)}" + (" (git mv)" if tracked else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "copy":
        cmd_copy(a[1], a[2])
    elif a[0] == "status":
        cmd_status(a[1])
    elif a[0] == "upstream":
        cmd_upstream(a[1], a[2])
    elif a[0] == "fork":
        cmd_fork(a[1], a[2], a[3])
    elif a[0] == "sync":
        cmd_sync(a[1], "--apply" in a)
    elif a[0] == "archive":
        cmd_archive(a[1], a[2])
    else:
        print(__doc__)
