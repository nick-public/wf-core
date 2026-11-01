# wf-pages-deploy — 앱 하나를 Pages repo 하위 폴더로

언제: 정적 앱을 `<user>.github.io` 같은 공유 Pages repo의 자기 하위 폴더로 올릴 때. 절차와 판정은 pool skill `wf-pages-deploy`가, 실제 복사 · gate · commit은 이 script가 한다.

```
python deploy.py <앱의 deploy.json>            # dry-run: gate 결과, 신규 · 갱신 · 지워질 파일, stage 경로만 보인다
python deploy.py <앱의 deploy.json> --write    # 복사 + 파일 수 검증 (+ 카드, after_copy)
python deploy.py <앱의 deploy.json> --commit   # + 그 경로만 add · commit
python deploy.py <앱의 deploy.json> --push     # + push, live가 있으면 라이브 대기
python deploy.py <앱의 deploy.json> --live-only
```

설정 파일은 앱 repo에 둔다(무엇을 복사하나는 앱마다 다르다). 예:

```json
{
  "source": "20_src/voca",
  "subdir": "apps/voca",
  "pages_repo": "<old-workspace>",
  "exclude": ["*.map", "drafts/**"],
  "forbid": [{"pattern": "weakness_db|entries\\.json", "why": "비공개 기록 참조"}],
  "stamp": true,
  "card": {"name": "Voca Vault", "description": "...", "url": "https://<user>.github.io/apps/voca/", "repoUrl": ""},
  "after_copy": ["node <core>/pool/common/tools/screen-test/check.mjs --dir {dest} --phone --smoke"],
  "live": {"url": "https://<user>.github.io/apps/voca/", "expect": "이번에 넣은 문자열", "assets": ["data.js"]},
  "commit_message": "voca: deploy"
}
```

지키는 것

- **기본은 dry-run.** 쓰기는 `--write` · `--commit` · `--push`를 줄 때만.
- **gate가 첫 단계.** pool `redact-check`의 금지어 · 로컬 경로 검사와 설정의 `forbid`에 하나라도 걸리면 아무것도 복사하지 않는다. 금지어 원천을 못 읽으면 통과로 치지 않고 멈춘다(종료 코드 2). 낱말은 출력하지 않는다.
- **하위 폴더 통째 교체.** 폴더 자체는 두고 내용만 비운 뒤 복사한다(미리보기 서버가 그 폴더를 잡고 있어도 실패하지 않게). 복사 뒤 파일 수 · 크기를 원본과 맞춰 보고 다르면 commit하지 않는다.
- **그 경로만 git add.** 하위 폴더와(카드가 있으면) 루트 `index.html`만. 다른 앱 · 다른 세션의 변경은 건드리지 않는다. 내용이 그대로면 카드 날짜도 바꾸지 않고 commit하지 않는다.
- `stamp`: 복사본의 상대 `.js` · `.mjs` · `.css` 참조에 같은 `?v=<해시>`를 붙인다(Pages는 약 10분 캐시하므로 옛 · 새 모듈이 섞이지 않게). 원본은 그대로.
- commit 메시지에 trailer가 필요하면 환경변수 `DEPLOY_COMMIT_TRAILER`.

종료 코드: 0 끝남 · 1 차단 · 검증 실패 · after_copy · git · 라이브 실패 · 2 설정 오류 · 금지어 원천 없음.

출처: VC Analyzer `80_publish/publish_github_io.py`(통째 교체 · 카드 · 그 경로만 add · 단계 분리 · 버전 stamp)를 바탕으로 다시 썼고, 시험 기록 앱 `deploy.py`(기본 dry-run, 개인정보 · 로컬 경로 차단), 역사 학습 앱 `deploy.py`(복사 뒤 파일 수 검증), eng-app `deploy.sh`(복사 뒤 스모크)의 장점을 가져왔다.
