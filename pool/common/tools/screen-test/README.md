# screen-test — 헤드리스 Chrome으로 화면을 시험한다

언제: 앱 · 페이지를 고친 뒤 "실제로 열어 눌러 봐도 오류가 없나"를 볼 때, 공개 배포 직전, PDF가 필요할 때.
의존성: Node 22 이상과 Chrome(없으면 Edge). npm 패키지는 쓰지 않는다. Chrome 위치가 다르면 `CHROME_PATH`.

## 파일

| 파일 | 하는 일 |
|---|---|
| `check.mjs` | 명령줄. 페이지를 열고 문제만 JSON으로 보고한다. 종료 코드 0 = 문제 없음, 1 = 문제 있음, 2 = 사용법 오류 · Chrome 없음 |
| `cdp.mjs` | 라이브러리. `launch()` · `newPage()` · 실제 입력(클릭 · 키 · 파일) · `screenshot()` · `pdf()` · `consoleErrors()` · `netFailures()` · `overflow()` · `serveStatic()` · `smokeButtons()` |

## 자주 쓰는 명령

```
# 폴더를 잠깐 띄워 폰 폭으로 열고, 보이는 버튼을 모두 세 바퀴 눌러 오류만 본다 (서버는 끝나면 닫힌다)
node check.mjs --dir <배포 폴더> --phone --smoke

# 여러 페이지
node check.mjs --dir <폴더> --path index.html --path quiz.html --phone --smoke

# 이미 떠 있는 주소, 준비 조건을 기다린 뒤 값 읽기 + 스크린숏
node check.mjs http://127.0.0.1:8000/app/ --wait "window.__ready === true" --eval "document.title" --shot shot.png --full

# PDF 뽑기 (CSS @page 크기를 따르고 배경을 인쇄한다)
node check.mjs --dir <폴더> --path print.html --pdf out.pdf
```

`--phone`은 390x844, 모바일 · 터치 에뮬레이션이고 가로 넘침 검사를 켠다. 넘침이 있으면 넘친 요소를 이름으로 적는다(자기 스크롤 상자 안에서 넘치는 것은 의도된 것으로 보고 뺀다).

## 무엇을 문제로 치나

- 콘솔 `error`와 잡히지 않은 예외
- 실패한 요청과 HTTP 400 이상(`favicon.ico` 제외). 오프라인 CDN 같은 사정이면 `--ignore-net`(보고는 계속)
- `--smoke`: 버튼 · `[role=button]`을 실제 마우스 클릭으로 누른 뒤 생긴 오류. 빈 텍스트 · 숫자 입력은 먼저 `1`로 채우고, 슬라이더는 양 끝으로 민다. 여러 바퀴를 도는 이유: 한 번 답하면 잠기고 "다음"을 눌러야 다른 갈래를 타는 앱이 많고, 정답일 때만 터지는 버그는 여러 바퀴에서 걸린다. 다른 페이지로 넘어가는 버튼은 되돌아와 센다(`navigations`)
- 가로 넘침(`--phone` 또는 `--overflow`)
- `--wait` 시간 초과, `--eval`이 던진 예외

alert · confirm · prompt는 자동으로 수락한다(그대로 두면 페이지가 멈춘다).

## 앱마다의 시나리오는 그 앱에 둔다

이 도구는 "어느 앱에나 쓰는 판"만 가진다. 앱 고유의 시나리오(예: 단어 앱의 복습 순서 · 음성)는 그 앱의 시험 script가 `cdp.mjs`를 import해 쓴다.

```js
import { launch, serveStatic } from '<pool>/common/tools/screen-test/cdp.mjs';
const srv = await serveStatic('20_src/app');
const b = await launch();
const p = await b.newPage({ size: '390x844', mobile: true });
await p.navigate(srv.url);
await p.clickSelector('#start');
await p.key('Enter');
if (p.consoleErrors().length) process.exitCode = 1;
await b.close(); await srv.close();
```

## 알아 둘 함정

- `chrome --screenshot --window-size=390,...`는 Windows에서 창 최소 폭(약 500px)에 걸려 500px로 배치한 뒤 잘라 낸다. 가로 넘침 버그처럼 보이지만 아니다. 폰 폭은 `newPage({size, mobile})`의 기기 에뮬레이션으로만 정확하다.
- `--virtual-time-budget`은 `performance.now()`까지 멈춰 애니메이션 · 타이머 앱을 틀리게 보인다. 여기서는 실제 시간을 쓴다.
- 기본은 `--disable-gpu`라 WebGL(Three.js 3D) 장면이 소프트웨어로 느리게 그려지고 GTAO 같은 후처리가 달라진다. 3D 장면은 환경 변수 `CDP_GPU=1`로 띄운다.
- 실행마다 임시 Chrome 프로필을 만들고 닫을 때 지운다. 페이지마다 따로 browser context라 저장소(localStorage)가 섞이지 않는다.

출처: 이전 프로젝트 여럿의 화면 시험 script(CDP 드라이버, 안에서 띄우는 정적 서버와 종료 코드, 버튼 전부 누르기, 넘친 요소 이름, Chrome · Edge 후보)를 모아 다시 썼다.
