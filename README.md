# WF · Workflow Core

The source files of WF, a working setup for [Claude Code](https://claude.com/claude-code): the frame every session loads, the skills and agents that step in at fixed moments of work, the tools behind them, and a pool of reusable pieces that topic workspaces copy in.

An explainer of the idea (article, slides, an explorable 3D model and narrated videos) is at **https://nick-public.github.io/wf/**. This repository is the thing itself. The workspace that made the explainer is published as [nick-public/publish-studio](https://github.com/nick-public/publish-studio).

## What it is, and what it is not

- It is a snapshot of one person's real setup on one Windows PC, published so the structure can be read and borrowed.
- It is not a product or a plugin. Nothing here installs itself into your machine, and there is no support.
- The documents are written in Korean, because they are instructions that Claude reads in every session of a Korean-speaking user. Technical terms stay in English. The tools, this README and the code comments in English are the easiest entry points.
- Personal details were generalized for publication: the owner is "사용자" (the user), and folders are placeholders (see below).

## The idea in four lines

1. Rules kept only as documents are absent when work happens. So the workflow is **installed into the moments of work**: session start, starting a topic, asking the user for a decision, splitting work across agents, wrapping up.
2. Every session loads the same **five-piece core**: the frame document, global skills, global agents, enforcement (permissions and hooks) and shared tools.
3. Each topic gets its own workspace on top of the core, and picks reusable pieces from the **pool**.
4. When a task ends, its lessons go back to the **narrowest layer where they actually repeated**: the topic, the pool, or (only with the user's approval) the core.

## What is inside

| Path | What | Where it goes when installed |
|---|---|---|
| `skeleton/skeleton.md` | The frame: the moments of a session and what steps in at each, how to talk to the user, autonomy and approval, records, splitting work, traps of this PC | `~/.claude/workflow/skeleton.md`, loaded by the global `CLAUDE.md` with `@` |
| `categories/c0.md` – `c3.md` | Instructions per category of topics (workflow itself, career, learning, life) | `~/.claude/workflow/categories/`, loaded by each category folder's `CLAUDE.md` |
| `global/skills/wf-*` | Seven global skills: `wf-project-init`, `wf-project-wrap`, `wf-review-page`, `wf-help`, `wf-idea`, `wf-ask`, `wf-recover` | `~/.claude/skills/` (called as `/wf-…`) |
| `global/agents/wf-*.md` | Four global agents: `wf-project-scout`, `wf-wrap-refiner`, `wf-second-look`, `wf-researcher` | `~/.claude/agents/` |
| `shared-tools/` | Scripts the skills call: `check`, `redact_check` (private-term gate), `review_page` (decision pages), `scan_sessions`, `session_start` (hook) | `~/.claude/workflow/tools/` |
| `pool/common`, `pool/c1`, `pool/c2` | Skills, agents and tools that a topic copies in when it needs them (not installed globally) | copied by `tools/pool_sync.py` |
| `tools/` | Tools that work on this repository: `install.py` (install and diff), `map.py` (machine-built maps of assets, knowledge and projects), `pool_sync.py` (pool ↔ topic copies) | run from here |
| `README.ko.md` | The original Korean README of the repository | — |

## Placeholders

| In the files | Meaning |
|---|---|
| `~/.claude` | The Claude Code user folder (`C:\Users\<you>\.claude` on Windows) |
| `<core>` | This repository's local clone |
| `C:\C0_Workflow_Core` … `C:\C3_Life` | The four category roots of the original PC. Topic folders under them appear as `<topic>` |
| `<old-workspace>` | Folders from before the category layout; their names were removed |
| `<private-folder>` | A folder that only sessions opened inside it may read. Every other session and tool skips it |
| `<other-person-folder>` | Another person's work folder on the same PC: shown by name only |
| `<design-notes>`, `<idea-inbox>` | The owner's design notes and idea inbox (not published) |
| `<work-account>`, `<user>.github.io` | The owner's private GitHub account and its Pages site |

## Trying it yourself

The setup assumes Windows, Git Bash and Windows PowerShell 5.1, Python 3 and Node 22+.

1. Clone this repository anywhere. Read `tools/install.py` first: it copies files into `~/.claude/` and removes installed `wf-*` skills and agents that no longer exist here.
2. Run `python tools/install.py` (dry run), then `python tools/install.py --apply`.
3. Add `@~/.claude/workflow/skeleton.md` to your global `~/.claude/CLAUDE.md`, and point the category folders' `CLAUDE.md` at their category document.
4. `shared-tools/redact_check.py` reads a private list of words that must never be published from `~/.claude/private/redact/`. Create your own list there; without it the gate refuses to pass.
5. `tools/map.py` has the original PC's folder roots at the top (`CATEGORY_ROOTS`, `WORK_ROOTS`). Change them to yours.

Two tools that some documents mention are not published: `tools/move_one.py` and `tools/move_engine.py` moved the original PC's old folders into the category layout once, and only make sense on that PC.

Expect to edit the frame and the category documents: they record what actually repeated for one person, which is the point of the design.

## License

MIT, see `LICENSE`. Third-party pieces keep their own notices where they appear.
