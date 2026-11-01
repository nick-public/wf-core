---
name: wf-equity-scenario-app
description: 상장 기업 하나를 자료 조사 → 재무 정리 → 인터랙티브 시나리오 앱(주가 차트 · 실적/배당 막대 · 시나리오 탭과 배당 · 주가 밴드 · 슬라이더 · 이벤트 달력 · 출처 각주) → PDF → 배포까지 만든다. 템플릿을 복사해 data.js · price.js만 채운다. "이 종목 분석 앱", "기업 시나리오 앱", "배당 / 주가 추정 앱", "반도체 기업 분석 페이지" 같은 요청에 쓴다.
metadata:
  when: 기업 하나의 숫자와 시나리오를 출처 붙은 앱으로 볼 때(투자 · 산업 분석)
  kind: template
  status: active
---

# wf-equity-scenario-app

엔진(`engine.js`) · 스타일 · `index.html`은 회사와 무관하고, 회사마다 `assets/data.js` + `assets/price.js`만 채운다. 학습판 형제는 pool `c1\skills\wf-paper-study-app`.

**옛 판에서 고친 것(다시 쓰며 확인):** 이전 판의 템플릿은 겉으로는 범용이었지만 엔진과 `index.html`에 첫 사용처의 값이 남아 있었다 — 데이터 키가 특정 분기 · 연도 이름이었고 회사 이름 · 출처 id · 금액 · 일정 문구가 코드에 박혀 있어, 템플릿의 `data.js`로는 엔진이 돌지 않았다. v3 엔진은 그것을 데이터 키(`FY_prev` · `Q_latest` · `estimate` · `scenarios` …)로 옮기고, 선택 절은 데이터가 없으면 숨긴다. **새 회사에서 코드를 고쳐야 할 것 같으면 먼저 데이터 키로 해결되는지 보고, 엔진을 고칠 때는 회사 고유값을 코드에 넣지 않는다.**

## 원칙
1. **출처 강제.** 모든 핵심 수치에 `src`(SOURCES의 id). 외부 출처가 아닌 값은 `src:"assumption"` → 앱이 주황 [n]으로 구분한다. 가정을 데이터인 척하지 않는다.
2. **추정은 가정으로.** "최근 분기 × 4" 같은 산술 환산은 전망이 아니라 시나리오다 — `narrative.keyCaveat`에 적는다. 점 예측이 아니라 밴드로 보인다.
3. **단순 payout 공식은 점진 배당 정책을 쓰는 회사에서 과대추정한다.** 그래서 배당은 정책 시나리오(점진 인상 / 성향 고정 …)로 따로 두고, 슬라이더는 '고급 수동'으로 접는다.
4. 작업 로그는 채팅과 분리해 `worklog.md`에 누적(수집 데이터 · 출처 · 판단).
5. 원본 리포트 PDF · 유료 자료는 repo에 넣지 않는다(`.gitignore`). 앱은 공개 출처 링크로.
6. 앱 푸터에 "투자 참고용, 투자 권유 아님". 개인화된 투자 조언을 하지 않는다. 사용자의 보유 · 금액은 앱 · 로그에 쓰지 않는다.

## 1. 워크스페이스
```
<repo>/<ticker>/
  sources.json   출처 레지스트리      company.json  분석 데이터 정본
  worklog.md     작업 로그(누적)      report.md     서술 보고서(선택)
  app/           template/ 복사본(index.html, assets/)
```
여러 종목 repo면 루트에 회사 카드 목록 `index.html`, 각 사는 `<ticker>/app/`.

## 2. 자료 조사
- 현재가 · 시총 · 발행 주식수 · **배당 가능 주식수**(자사주 제외 — 배당 총액 ÷ DPS로 역산해 교차 확인).
- 연간 · 분기 실적(매출 · 영업이익 · 순이익), 배당 이력(DPS · 성향), 사업 구조(공급사 · 고객), 연혁, 지역 매출, 다가올 이벤트(자사와 연관사의 실적 발표 — 연관사 실적이 선행지표인 경우가 많다).
- 주가 이력은 브라우저 CORS를 피하려고 받아서 `price.js`에 박는다. 국내 종목은 네이버 금융 비공식 API(일봉 권장, `timeframe=month`면 월봉):
  ```
  curl -s -G "https://api.finance.naver.com/siseJson.naver" --data-urlencode symbol=<CODE> --data-urlencode requestType=1 --data-urlencode startTime=<YYYYMMDD> --data-urlencode endTime=<YYYYMMDD> --data-urlencode timeframe=day -H "Referer: https://finance.naver.com/" -H "User-Agent: Mozilla/5.0"
  ```
  응답을 파싱하는 일은 script 파일로 하고 `window.__PX=[["YYYYMMDD",종가],…]`를 쓴다. 네트워크 명령은 다른 명령과 묶지 않는다. 비공식 API라 형식이 바뀔 수 있다 — 받은 행 수와 마지막 날짜를 확인한다.
- 앱의 "최근종가 갱신" 버튼은 공개 CORS 프록시를 거친다(막히면 정적 값 유지). 국내 종목이 아니면 `meta.liveRefresh:false`.

## 3. 데이터 채우기
`template/assets/data.js`의 주석이 스키마의 정본이다. 필수: `meta` · `market` · `financials{FY_prev, Q_latest}` · `engineDefaults` · `presets` · `narrative`. 선택(지우면 그 절이 숨는다): `estimate`(올해 추정 막대 · 수염) · `scenarios` + `dividendPolicies` + `priceBand`(셋이 함께) · `cashflow` + `balanceStress`(이익 ≠ 현금) · `trackIndicators` · `events` · `priceMarks` · `eventColors`.
- 슬라이더 범위는 종목 특성에 맞게(사이클 업종은 마진 상한을 크게), `marks`로 실제값 앵커를 준다.
- 공개 증권사 컨센서스가 없는 소형주면 그 사실을 `scenarios.note`에 적고 시나리오가 유일한 틀임을 밝힌다.

## 4. 확인
- `node --check app/assets/engine.js`
- `node <이 skill>\tools\stub_check.js app\assets` — 브라우저 없이 모든 렌더 함수를 돌려 빈 칸 · 숨긴 절과 화면 글의 `NaN · undefined · Infinity`를 잡는다. PASS여야 한다.
- 화면은 헤드리스 Chrome 스크린샷(데스크톱 · 폭 420)을 직접 본다. 로컬 서버가 필요하면 멀티스레드 서버(pool `common\tools\serve\serve.ps1`) — 단일 스레드 `http.server`는 keep-alive로 멈출 수 있다.
- PDF: 앱의 "PDF로 저장"(인쇄 스타일: 슬라이더 숨김 · 라이트 · 페이지 분할 보호 · 차트 색 유지).
- 배포마다 `index.html`의 `?v=` 캐시 값을 올린다.

## 5. 배포
pool `common\skills\wf-pages-deploy`(경로만 stage). 공개 전 금지어 gate. 카드는 개인 랜딩의 목록에 한 줄.

## 엔진이 계산하는 것
연환산 = 최근 분기 × 배수 → 영업이익(마진) → 순이익 → EPS · DPS · 시가배당률. 주가 4모델: PER · 배당수익률 · PBR · EV/EBITDA(− 순차입금). 시나리오 탭: 시나리오 순이익 × 정책 → 예상 DPS 범위, 시나리오 EPS × PER 묶음 → 주가 밴드 표. 차트는 의존성 없는 인라인 SVG.
