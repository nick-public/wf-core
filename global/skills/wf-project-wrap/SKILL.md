---
name: wf-project-wrap
description: 세션 · 라운드를 마칠 때, compact 전, 일을 넘길 때 쓴다. 완료 조건을 결과물에서 확인하고, 과정 기록(쓴 것 · 막힌 곳 · 교훈 후보)을 남기고, 정제 agent가 교훈을 맞는 층과 pool · core로 보내고, 재-Init이 필요한지 판정하고, 재진입 카드와 지도를 갱신한다. "마무리", "정리하고 닫자", "wrap" 같은 요청에 쓴다.
metadata:
  when: 세션 · 라운드 끝, compact 전, 일을 넘길 때
  kind: procedure
  status: active
---

# wf-project-wrap

중앙 인박스는 없다. 모든 처리는 이 세션 안에서 끝낸다. 카테고리 문서의 "wrap에서 더할 것" 절을 먼저 읽는다.

## 1. 결과물 확인
- 기계 칸: `00_META\checks.yaml`이 있으면 `python ~/.claude/workflow/tools/check.py 00_META/checks.yaml`. 실패면 "끝남"이라고 하지 않는다.
- **화면이 있는 결과물:** 이번에 바뀐 파일에 화면(`.html` · `.js` · `.css`)이 있고 주제에 `wf-ui-qa` 사본이 있으면, "됐다"고 하기 전에 `wf-ui-qa`를 부른다(판단하지 않고 파일 종류로 정한다).
- **판단이 든 일**(설계 · 판정 · 사용자에게 올릴 결론 · 공개할 글 — 바뀐 파일에 `.md` 설계 · 결정 문서가 있으면 그렇다고 본다)을 이번에 끝냈으면 `wf-second-look`에게 결과물 경로와 그 일의 요구 원문(사용자 원문 · 완료 조건)을 주고 다시 읽힌다. 기계 칸만 있는 일에는 부르지 않는다. 지적은 고치거나, 고치지 않는 이유를 과정 기록에 적는다.

## 2. 과정 기록
이번 라운드 로그(없으면 `00_META\process_log.md`) 끝에 덧붙인다. 지어내지 않고 이 대화에서 실제로 있던 것만:
```
## 과정 기록 (YYYY-MM-DD)
- 쓴 것: skill · agent · 도구 · 지식(경로)
- 막힌 곳: 증상 → 푼 방법 (없으면 "없음")
- 교훈 후보: 0 ~ 3줄, 일반화한 문장
- core가 모자랐던 곳: wf-project-init · 이 skill · 뼈대가 이번 일에서 틀리거나 빠뜨린 것 (없으면 "없음")
```
회사 · 동료 · 고객 이름, 회사 수치 · 코드, 아이 이름, 금액은 쓰지 않는다.

## 3. 정제 — `wf-wrap-refiner`
교훈 후보와 "core가 모자랐던 곳"이 모두 "없음"이고 바뀐 pool 사본도 없으면 부르지 않고 4단계를 건너뛴다.
넘길 것: 과정 기록, 바뀐 파일 목록(`git status` · `git diff --stat`), `python <core>/tools/pool_sync.py status <주제 경로>` 결과.
refiner가 후보마다 네 질문(모델이 모르는 것인가 · 반복인가 · 범위 · 사용자 조건)을 걸어 판정표를 돌려준다.

## 4. 반영
| 판정 | 할 일 |
|---|---|
| 이 주제 | 그 자리에서 주제 `CLAUDE.md` 함정 줄 · decisions에 |
| 지식 | 그 주제의 `knowledge\` 해석 층에, 원천 인용과 함께 |
| 카테고리 · 뼈대 · 전역 skill | 고칠 줄을 `/wf-review-page`로 보이고 승인되면 `<core>\`(categories · skeleton · global)에 새로 쓴다 → `install.py --apply`. 모든 세션이 바뀌므로 묻는다 |
| pool 복사본 · 일반 개선 | `pool_sync.py upstream` → pool에 반영, `CHANGELOG.md` 한 줄, core commit. **자율**(결과 한 줄만 보고) |
| pool 복사본 · 이 주제만의 변경 | `pool_sync.py fork <주제> <항목> "<이유>"` |
| pool이 새 판 · 복사본은 그대로 | `pool_sync.py sync <주제>` |
| 오래 안 쓰인 지식 · skill | 묻지 않고 archive(지우지 않음) |
| `wf.md`(지도)에서 90일 넘게 0회인 `wf-` 항목 | retired 후보로 사용자 보고에 한 줄(지우지 않음, core면 review-page로) |
| 같은 절차가 두 번째로 되풀이됨 | 전용 skill 후보로 decisions에 한 줄(시범 한 번 뒤 뽑는다) |

## 5. 재-Init 판정 (한 줄)
"이번 세션이 이해 시트의 '왜' · 완료 조건 · 분해 중 하나를 바꿨나?" 예이면 재진입 카드의 다음 첫 행동을 `재-Init: <바뀐 것>`으로.

## 6. 공개본 맞추기
`LINKS.md`가 있으면 원본 commit과 지금을 비교해, 공개된 원본이 바뀌었으면 "공개본 갱신 후보: <항목>"을 사용자에게 한 줄로.

## 7. 재진입 카드 · 지도 · 설치
- `00_META\REENTRY.md`를 덮어쓴다: 지금 · 사용자 차례 · 다음 첫 행동.
- 지도를 다시 굽는다(항상, 묻지 않음, 약 10초): `python <core>/tools/map.py --build`. 지도는 git에 넣지 않는 설치 쪽 파일이라 commit할 것이 없다. 굽기가 실패하면 사용자 보고에 한 줄만 남긴다(다음 이벤트가 다시 굽는다).
- core를 고쳤으면 `python <core>/tools/install.py --check` — 설치하지 않은 차이가 있으면 알린다.
- 바꾼 파일만 경로를 지정해 commit(주제 repo와 core 각각). push는 그 repo의 경계 표대로.

## 8. 사용자에게
남은 일 전체를 "끝남 · 남음"으로, 사용자 차례, 승인 요청 줄(있으면 wf-review-page 링크), pool · core에 올린 것 한 줄.
