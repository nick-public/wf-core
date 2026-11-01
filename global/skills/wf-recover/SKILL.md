---
name: wf-recover
description: 전원 차단 · Windows 업데이트로 Claude 창들이 강제 종료됐거나 오래 비웠다가 돌아왔을 때, 세션 로그와 git을 읽어 "어느 폴더의 어느 세션을 resume할지"와 최근 실제 활동을 정리한다. "리부팅됐는데 복구", "어느 세션 살려야 하나", "최근 1주일 뭐 했지" 같은 요청에 쓴다. 읽기 전용.
metadata:
  when: 강제 종료 · 오랜 공백 뒤 살릴 세션과 최근 활동을 복구
  kind: procedure
  status: active
---

# wf-recover

읽기 전용이다. 프로젝트 파일 수정 · commit · push · 배포를 하지 않는다. 인자: 기간(`3d` · `7d` · `2w`, 기본 7일), `full`(사용자 요청 원문 전체), 폴더 이름(그 주제만 깊게).

## 1. 세션 로그 스캔
script = `~/.claude\workflow\tools\scan_sessions.py`. 콘솔이 한글을 깨뜨리므로 파일로 쓰고 Read한다.
```
python "~/.claude\workflow\tools\scan_sessions.py" --days 7 --out "<scratchpad>\scan.txt"
```
늘 `--out`을 준다(콘솔 출력은 한글이 깨져 도구 결과에서 읽을 수 없다).

- **활동일은 로그 안의 timestamp로만 판정한다.** 세션 파일의 수정 시각은 resume · 요약만으로도 바뀐다. 출력 끝의 `TOUCHED BUT IDLE`은 작업한 세션으로 보고하지 않는다.
- `ended on assistant turn` 표시 = 강제 종료 후보. `still open right now?`는 지금 다른 창에서 열려 있을 수 있으니 resume을 권하지 않는다.
- 폴더를 옮긴 주제는 로그의 cwd가 옛 경로다. resume 줄에 옛 경로를 쓰고 지금 경로를 옆에 적는다(지도 · 이동 기록으로 짝을 찾는다).

## 2. 결과물로 확인
스캔에 나온 폴더마다(배포 repo 포함) `git log --since=<날짜> --date=short --pretty="%ad %s"`, `git status --short`, `git log --oneline "@{u}..HEAD"`를 각각 따로 돌린다. "무엇을 했나"는 대화보다 commit이 정확하다.

## 3. 다음 진입점
주제의 재진입 카드(맨 위 목적 · 다음 첫 행동)만 읽는다. 옛 워크스페이스는 `00_META\REENTRY.md` · `HANDOFF.md` · `MASTER_PLAN.md`의 최신 부분만. 문서 전체를 읽지 않는다. 주제 목록과 경로는 지도(`~/.claude\workflow\maps`)에서 본다. 전역 MEMORY.md의 현황 목록과 대조하지 않는다(그 목록은 없앴다).

## 출력
1. 한 줄 요약: 기간, 활동한 폴더 수, 활동 없던 날.
2. 복구 목록(강제 종료가 있었을 때): 창마다 `cd "<dir>"; claude --resume <id>` 그대로 복사할 수 있게.
3. 폴더별 표: 위치 · 활동일 · 한 일(commit 기준) · commit 수.
4. 끝나지 않은 신호: 커밋 안 된 변경, push 안 된 commit, 재진입 카드의 다음 첫 행동.
5. 오래 손대지 않은 주제 중 기한이 적힌 것만 경고(D-day). 마지막은 Claude의 추천 하나(어느 창부터 살릴지)로 닫는다.

추측과 사실을 나눈다. 로그에 없으면 "기록 없음". 주제 약어는 처음 쓸 때 한 줄로 푼다. `<private-folder>` 세션은 경로와 resume 줄만 내고 내용(요청 원문 · 수정 파일)은 옮기지 않는다.
