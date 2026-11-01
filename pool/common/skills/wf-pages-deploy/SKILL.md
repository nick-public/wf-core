---
name: wf-pages-deploy
description: 앱 하나를 <user>.github.io의 하위 폴더로 올리고 포털 카드를 갱신한 뒤 라이브를 확인한다. "배포해", "github.io에 올려", "라이브 갱신" 같은 요청이나 공개 앱의 내용을 바꾼 뒤에 쓴다.
metadata:
  when: 공개 앱 하나를 github.io 공유 배포 repo에 올리고 라이브까지 확인
  kind: procedure
  status: active
---

# wf-pages-deploy

배포 repo의 기본은 사용자의 `<user>.github.io` repo(여러 앱 · 여러 세션이 함께 쓴다)다. 다른 Pages repo(예: 새 공개 계정의 허브)로 올릴 때는 주제 설정의 `pages_repo` 칸(또는 `--pages`)으로 대상을 바꾼다 — script를 복제하지 않는다. **새 공개 계정 repo에 처음 올릴 때는 `--push` 없이 `--commit`까지만 돌리고, push는 사용자가 공개본을 본 뒤 `git push public <branch>`로 한다**(script 안의 push는 확인 창에 걸리지 않는다). 조립 · 복사 · 카드 · stage · 라이브 대기는 script `<core>\pool\common\tools\pages-deploy\`가 한다(사용법은 그 폴더 README). script는 기본이 dry-run이다: 먼저 dry-run 출력으로 바뀔 경로와 stage 목록을 보고, 맞으면 실제로 돌린다.

## 멈추고 묻는 곳
- **처음 올리는 앱(새 하위 폴더)은 공개 확대다.** 주제의 경계 표가 허락하지 않았으면 사용자에게 묻는다. 이미 공개된 앱의 갱신은 묻지 않는다.

## 순서와 판정
1. **공개 gate:** 올릴 폴더에 redact-check(`~/.claude\workflow\tools\redact_check.py`, deploy.py가 첫 단계에서 부른다)를 돌린다. 걸리면 원본을 고친다. 샘플 · demo는 합성만, 아이 이름 · 학교 · 성적, 회사 정보는 넣지 않는다.
2. **배포 repo 상태:** `git status --short`가 비어 있고 `git fetch` 뒤 뒤처지지 않았는지 본다. 다른 세션의 변경이 있으면 건드리지 않고, 그 경로는 stage하지 않는다.
3. **조립 전 검사(데이터 · 링크를 바꿨을 때):** 외부 링크는 실제 200을 받은 것만, 이미지는 내려받아 실물 형식 확인, 앱 script를 바꿨으면 `node --check`.
4. **로컬 확인:** 조립된 사이트를 정적 서버로 띄워 데스크톱 · 모바일 캡처를 보고, 바뀐 파일에 `.html` · `.js` · `.css`가 있으면 `wf-ui-qa`로 실제 입력 시험(판단하지 않고 파일 종류로 정한다).
5. **배포:** 그 앱의 하위 폴더와 루트 `index.html`(카드)만 파일 경로로 add · commit · push. `-A` · 디렉토리 전체 add 금지. commit 메시지 끝에 attribution trailer.
6. **라이브 확인:** Pages 빌드가 늦으므로 script가 캐시 버스트(`?cb=`)를 붙여 기다린다. 판정 = 페이지와 데이터 · 이미지 자산 200, 새로 넣은 문자열 하나가 라이브에 보임, 라이브 캡처가 로컬 캡처와 같음, 포털에 카드가 보임. 사용자에게 라이브 URL을 준다.

## 함정
- GitHub Pages는 파일을 약 10분 캐시한다. JS · CSS가 여러 파일이면 배포마다 `?v=<hash>`를 모든 상대 import에 붙인다. 하나라도 빠지면 옛 모듈과 새 모듈이 섞여 돈다.
- 미리보기 서버가 조립 폴더를 cwd로 잡고 있으면 폴더째 지우기가 실패한다 → 폴더는 두고 내용만 비운다.
- 루트 카드는 `EXTRA_APPS` 목록에 URL을 열쇠로 멱등 삽입 · 갱신한다(같은 앱 카드가 둘 생기지 않게).
- 대기 반복문 · `rm -rf` · `cp -r`를 shell에 쓰지 않는다. 모두 script 안에서 한다.
