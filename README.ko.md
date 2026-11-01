# WF core — Workflow Core 정본

모든 Claude 세션이 갖는 일하는 방식(WF)의 정본 repo다. 세션은 이 repo를 직접 읽지 않고, `tools/install.py`가 `~/.claude\`에 설치한 사본을 읽는다.
설계 노트는 공개하지 않는다. 해설은 https://nick-public.github.io/wf/ 에 있다.

## 이름
시스템 이름은 **WF**. WF가 관리하는 skill · agent는 모두 `wf-`로 시작한다. 주제가 직접 만든 것은 그 주제의 prefix(`vca-` 등), prefix가 없는 것은 Claude Code 기본 기능이다.

## 구조
| 경로 | 무엇 | 설치 · 쓰임 |
|---|---|---|
| `skeleton\skeleton.md` | 뼈대 문서(세션의 순간 표 · 말하는 법 · 자율 · 기록 · 일 나누기 · PC 함정) | → `~\.claude\workflow\skeleton.md`, 전역 `CLAUDE.md`가 `@`로 |
| `categories\c0 ~ c3.md` | 카테고리 지시(init · wrap에서 더할 것 포함) | → `~\.claude\workflow\categories\`, `C:\C?_*\CLAUDE.md`가 `@`로 |
| `global\skills\wf-*` | 전역 skill 일곱: project-init · project-wrap · review-page · help · idea · ask · recover | → `~\.claude\skills\` (`/wf-…`) |
| `global\agents\wf-*.md` | 전역 agent 넷: project-scout · wrap-refiner · second-look · researcher | → `~\.claude\agents\` |
| `shared-tools\` | skill이 부르는 script: check · redact_check · review_page · scan_sessions · session_start(hook) | → `~\.claude\workflow\tools\` |
| `pool\common|c1|c2\`(카테고리 폴더는 항목이 생길 때 만든다) | 주제가 골라 가져가는 skill · agent · 도구 | 설치하지 않음. `/wf-project-init`이 주제로 복사 |
| `pool\_retired\` | 은퇴한 항목(지우지 않음) | — |
| `tools\` | 정본을 다루는 도구: install · map · pool_sync (이 PC 전용 이전 도구 move_one · move_engine은 공개본에서 뺐다) | 정본에서 실행 |
지도(자산 · 지식 · 프로젝트 · WF 사용법)는 `map.py`가 `~\.claude\workflow\maps\`에 굽는다. 파생물이라 git에 넣지 않는다.

## 고칠 때
1. 정본을 고친다.
2. `python tools/install.py`(dry-run)로 무엇이 바뀌는지 보고 `--apply`. 설치하지 않으면 어느 세션에도 반영되지 않는다.
3. 뼈대 · 카테고리 · 전역 skill · agent를 바꾸는 일은 모든 세션을 바꾸므로 `/wf-review-page`로 보이고 승인받는다. pool 항목의 개선은 자율.
4. 새 전역 skill · agent는 `claude -p`로 새 세션을 한 번에 하나 띄워 실제로 읽고 행동이 바뀌는지 다른 agent가 판정한 뒤 끝난 것으로 본다.

## pool 규칙
1. pool이 정본이다. 주제는 `pool_sync.py copy`로 복사해 가고, 복사본 앞머리와 `<주제>\.claude\pool.json`에 `origin` · `base`가 남는다.
2. 주제에서는 복사본을 바로 고친다. wrap의 `wf-wrap-refiner`가 가른다: 다른 주제에도 좋은 변경은 `pool_sync.py upstream`(자율, commit + `CHANGELOG.md` 한 줄), 그 주제만의 변경은 `fork`.
3. pool이 새 판이 되면 손대지 않은 복사본은 다음에 열 때 `sync`, fork는 차이만 보인다.
4. 앞머리(`metadata:`): `when` · `kind` · `status` · `sources`, agent는 `called_by`도.
5. 넣는 조건은 반복이다: 두 주제 이상에서 실제로 쓰인 것만. 주제와 상관없이 어느 순간에나 쓰이거나 core skill이 부르는 것은 pool이 아니라 core(`global\`)다.
6. 지도가 과정 기록의 "쓴 것"에서 쓰인 횟수를 센다. 90일 넘게 0회면 wrap이 retired 후보로 올린다.
7. 이 repo에 회사 · 동료 · 고객 이름, 아이 이름, 금액, 금지어 원문을 넣지 않는다. 금지어 원천은 `~/.claude\private\redact\`(어느 repo에도 속하지 않음).

## 지도
```
python tools/map.py --build                  # 다시 굽기(init · wrap · install · 이동 · 하루 넘게 낡으면 세션 시작 hook이 부른다)
python tools/map.py --when "배포 검사"       # 자산 몇 줄(낱말 OR)
python tools/map.py --workspaces "이력서"    # 선례 워크스페이스
```
