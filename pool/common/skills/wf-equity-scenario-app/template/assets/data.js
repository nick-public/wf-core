/* ===== 회사별로 채우는 파일 (price.js 와 함께). 엔진 · 스타일 · index.html은 고치지 않는다. =====
   단위: 금액 = 억원, 주가 · DPS = 원, 주식수 = 주.
   모든 핵심 수치에 src(= SOURCES의 id). 외부 출처가 아닌 추정치는 src:"assumption" → 앱이 주황 [n]으로 구분.
   선택 절(estimate · scenarios/dividendPolicies/priceBand · cashflow · trackIndicators · events …)은
   키를 지우면 앱에서 그 절이 숨는다. 아래 주석 예시의 숫자는 형식만 보이는 자리값이다. */

window.SOURCES = {
  // id: { title, url(없으면 null), date }
  primary:    { title: "<주 출처 제목>", url: "<url>", date: "<YYYY-MM-DD>" },
  assumption: { title: "분석 가정 (외부 출처 아님)", url: null, date: "<YYYY-MM-DD>" }
};

window.COMPANY = {
  meta: { name: "<회사명>", ticker: "<코드>", market: "KOSPI|KOSDAQ", sector: "<업종>", asOf: "<YYYY-MM-DD>", origin: "<분석 출발점>",
          liveRefresh: true },               // false면 '최근종가 갱신' 버튼을 숨긴다(국내 종목이 아닐 때)

  market: {
    price:          { value: 0, date: "<YYYY-MM-DD>", src: "primary" },
    marketCap:      { value: 0, src: "primary" },                 // 억
    sharesTotal:    { value: 0, src: "primary" },                 // 주
    sharesEligible: { value: 0, note: "배당총액 ÷ DPS로 역산(자사주 제외)", src: "primary" },
    majorShareholder:{ name: "<>", stake: 0, src: "primary" },
    week52:         { high: 0, low: 0, src: "primary" }
  },

  financials: {
    FY_prev:  { revenue: 0, opProfit: 0, netIncome: 0, equity: 0, dps: 0, payout: 0, src: "primary" },   // 직전 결산 연도
    Q_latest: { revenue: 0, opProfit: 0, netIncome: 0, opMargin: 0, note: "", src: "primary" }          // 최근 분기(연환산 기준)
  },

  annualHistory:    [ /* { year:"YYYY", rev:0, op:0, ni:0, src:"primary" } */ ],
  quarterlyHistory: [ /* { q:"YYQn", rev:0, hot:false, src:"primary" } */ ],
  dpsHistory:       [ /* { year:"YYYY", dps:0, src:"primary" } */ ],
  regionMix:        { title: "지역별 매출 비중", src: "primary", parts: [ /* { name:"국내", value:0, pct:0 } */ ] },
  suppliers:        { src: "primary", items: [] },
  customers:        { src: "primary", items: [] },
  historyTimeline:  [ /* { y:"YYYY", t:"사건", src:"primary" } */ ],

  // 선택 — 올해 추정 막대(점선 + 수염). 없으면 지운다.
  // estimate: { label:"YYYYE", caption:"<추정 근거와 범위의 뜻>", quarterLabels:["YYQ2E","YYQ3E","YYQ4E"],
  //             revenue:{lo:0,mid:0,hi:0}, quarter:{lo:0,mid:0,hi:0}, opMargin:{lo:0,mid:0,hi:0}, dps:{lo:0,mid:0,hi:0} },

  // 시나리오 슬라이더(고급 수동) — Q_latest × annualizeFactor 로 연환산 후 마진 · 배당성향 적용
  engineDefaults: {
    annualizeFactor:  { value: 4,    min: 3.5, max: 8,    step: 0.1,  label: "연환산 배수 (Q×?)", src: "assumption" },
    sustainedOpMargin:{ value: 3,    min: 1,   max: 25,   step: 0.1,  label: "연간 영업이익률 (%)", src: "assumption" },
    netToOpRatio:     { value: 0.75, min: 0.5, max: 0.95, step: 0.01, label: "순이익/영업이익 비율", src: "primary" },
    payout:           { value: 30,   min: 10,  max: 60,   step: 0.5,  label: "배당성향 (%)", src: "primary" },
    per:              { value: 8,    min: 2,   max: 30,   step: 0.5,  label: "PER 배수", src: "assumption" },
    targetYield:      { value: 4,    min: 1,   max: 9,    step: 0.25, label: "목표 배당수익률 (%)", src: "assumption" },
    pbr:              { value: 1,    min: 0.3, max: 6,    step: 0.1,  label: "PBR 배수", src: "assumption" },
    evEbitdaMult:     { value: 6,    min: 2,   max: 14,   step: 0.5,  label: "EV/EBITDA 배수", src: "assumption" },
    depreciation:     { value: 0,    min: 0,   max: 1000, step: 10,   label: "감가상각비 (억)", src: "assumption" },
    netDebt:          { value: 0,    min: -5000, max: 10000, step: 100, label: "순차입금 (억)", src: "assumption" }
  },
  presets: { "보수": { sustainedOpMargin: 3 }, "기본": {}, "낙관": {} },

  // 선택 — 시나리오 탭 · 배당 정책 · 주가 밴드. 셋 다 있어야 절이 보인다(없으면 고급 수동만 펼쳐진다).
  // scenarios: { title:"① 실적 시나리오 (FYxxxx 순이익)", subtitle:"— <기준일> 배당 / 주가 밴드", note:"<커버리지 · 밴드의 뜻>",
  //              driver:"<실적 동인>", src:"assumption", eligibleShares:0, defaultKey:"Base",
  //              items:[ { key:"Bear", ni:0, eps:0, h2:"<남은 기간 가정>", why:"<근거>" }, { key:"Base", … }, { key:"Bull", … } ] },
  // dividendPolicies: { title:"② 배당 정책 전제", label:"<기준일> 예상 주당배당", defaultKey:"A",
  //              items:[ { key:"A", label:"점진 인상", stars:3, dpsLow:0, dpsHigh:0, why:"<>" },
  //                      { key:"B", label:"성향 고정", stars:1, scaled:true, payoutLow:0.2, payoutHigh:0.3, why:"<>" } ],
  //              upTriggers:["<>"], downTriggers:["<>"], central:{ label:"중심 추정", low:0, high:0, baseLabel:"직전 결산", baseDps:0 } },
  // priceBand: { perSet:[4,6,8,10], note:"<배수 근거>", src:"assumption" },

  // 선택 — 현금흐름 함정
  // cashflow: { years:["YYYY","YYYY"], ocf:[0,0], note:"<이익과 현금의 차이>", src:"primary" },
  // balanceStress: { cols:["YYYY","YYYY"], rows:[ { k:"부채비율", v:["0%","0%"], note:"" } ], footnote:"<>", src:"primary" },

  // 선택 — 분기마다 볼 지표
  // trackIndicators: { src:"primary", items:[ { k:"<지표>", now:"<현재>", watch:"<무엇을 보나>", role:"<왜>" } ],
  //                    next:{ event:"<다음 공시>", date:"YYYY-MM-DD", watch:"<확인할 것>" } },

  events: [ /* { date:"YYYY-MM-DD", company:"<>", title:"<>", relevance:"<>", src:"primary", star:false } */ ],
  eventColors: { /* "<회사명>": "#ff6b4a" — 없으면 등장 순서대로 자동 */ },
  eventsNote: "",                        // 달력 위 한 줄(연관사 실적이 선행지표인 이유 등)
  priceMarks: [ /* { date:"YYYYMMDD", label:"<사건>" } — 주가 차트에 점 표시 */ ],
  sourcesNote: "",                       // 출처 절 끝 한 줄(다음 갱신 공시 등)

  narrative: {
    thesis: "<핵심 논지 한 단락>",
    keyCaveat: "<추정의 한계 — 산술 환산은 전망이 아님 등>",
    watchpoints: [ "<관전 포인트>" ]
  }
};
