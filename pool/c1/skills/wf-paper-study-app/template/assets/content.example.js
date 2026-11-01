/* ===========================================================
   콘텐츠 스키마 예시 (assets/content.js 로 복사해 내용만 교체)
   ── 이 파일 하나만 채우면 앱이 완성됩니다. 도메인 무관. ──
   아래는 HW/NPU 예시. 점검: node <skill 폴더>/tools/check_content.mjs assets/content.js
   =========================================================== */

const APP_ID = "npu_dataflow_v1";          // localStorage 네임스페이스(프로젝트마다 고유)
const FOOTER = "출처: <논문/표준 서지> · 학습용";

const SUBJECT = {
  brand: "🧮 NPU Dataflow 스터디",        // 사이드바 제목(짧게)
  brandSub: "가속기 데이터플로우 한 편",    // 사이드바 보조설명
  title: "NPU 데이터플로우 이해 — Weight/Output Stationary",
  subtitle: "논문 1편으로 배우는 가속기 데이터 재사용 전략",
  story: "딥러닝 가속기의 핵심은 <b>데이터 이동 최소화</b>다. 같은 연산이라도 어떤 데이터를 PE에 머무르게 하느냐(stationary)에 따라 에너지가 크게 달라진다. 이 앱은 대표 논문을 챕터로 쪼개 해설한다."
};

/* 자료(논문/특허/표준/문서) — 개수 자유. 저작권: PDF 재배포 대신 공식 링크로. */
const SOURCES = [
  { kind:"📄 논문", title:"Eyeriss: An Energy-Efficient Reconfigurable Accelerator …",
    sub:"Chen, Emer, Sze (2016)", meta:[["출처","ISSCC / JSSC 2017"],["주제","Row-Stationary dataflow"]],
    url:"https://doi.org/10.1109/JSSC.2016.2616357", urlLabel:"DOI로 원문 보기",
    note:"기관 접근 또는 공식 오픈액세스 출처로 연결" }
];

/* 챕터: TL;DR → 본문(여러 문단) → 핵심 용어 → 원문 근거. 충실하게! */
const CHAPTERS = [
  { id:"c1", title:"왜 데이터 이동이 문제인가",
    tldr:"연산보다 메모리 접근이 훨씬 비싸다 — 에너지의 대부분이 데이터 이동.",
    body:[
      "딥러닝 추론에서 곱셈-누산(MAC) 자체는 싸지만, 그 데이터를 DRAM에서 가져오는 비용은 수백 배 비싸다.",
      "따라서 가속기 설계의 목표는 ‘연산을 빠르게’보다 ‘데이터를 덜 옮기게’가 된다."
    ],
    terms:[{t:"MAC", d:"Multiply-Accumulate, 가속기의 기본 연산"},{t:"data reuse", d:"한 번 가져온 데이터를 여러 연산에 재사용"}],
    src:"서론" },
  { id:"c2", title:"Stationary 전략 비교",
    tldr:"무엇을 PE에 머무르게 하나 — Weight / Output / Row Stationary.",
    body:["가중치를 고정하면(WS) 가중치 재사용이 극대화되고, 출력을 고정하면(OS) 부분합 이동이 준다.",
      "Eyeriss는 행 단위 재사용을 노린 Row-Stationary로 종합적 에너지를 최적화했다."],
    terms:[{t:"PE", d:"Processing Element, MAC 한 단위"},{t:"Row-Stationary", d:"행 단위 재사용으로 전체 데이터 이동 최소화"}],
    src:"본문 — dataflow taxonomy" }
];

const QUIZ = {
  basic:[
    { type:"mc", q:"가속기에서 가장 비싼 비용은?", choices:["MAC 연산","DRAM 데이터 접근","클럭 분배","리셋"], answer:1,
      why:"메모리 접근 에너지가 연산보다 수백 배 큽니다." },
    { type:"ox", q:"Weight Stationary는 가중치 재사용을 극대화한다.", answer:true, why:"가중치를 PE에 고정해 재사용합니다." }
  ],
  inter:[
    { type:"mc", q:"Row-Stationary가 노리는 핵심 이점은?", choices:["클럭↑","행 단위 종합 재사용으로 총 이동량↓","면적↓만","정확도↑"], answer:1,
      why:"특정 데이터 하나가 아닌 전체 이동량을 줄이도록 설계됐습니다." }
  ]
};

const THINK = [
  { q:"배치 크기가 커지면 어떤 stationary 전략이 유리해질까?", hint:"재사용되는 데이터의 종류(가중치 vs 입력)와 배치의 관계를 생각." },
  { q:"학습(training)에도 같은 dataflow가 최적일까?", hint:"역전파의 데이터 의존성과 메모리 패턴은 추론과 다르다." }
];

const RELATED = [
  { t:"Sparsity 가속", d:"0을 건너뛰어 연산·이동을 줄이는 기법.", kw:"sparse neural network accelerator dataflow" },
  { t:"Roofline 모델", d:"연산강도 대비 성능 한계를 보는 분석틀.", kw:"roofline model accelerator arithmetic intensity" }
];

const GUIDE = {
  title: "정리 노트 가이드",
  intro: "배운 내용을 한 장으로 정리할 때 이 틀을 따르세요.",
  structure: [
    ["① 한 줄 정의", "이 논문이 푸는 문제를 한 문장으로."],
    ["② 핵심 아이디어", "제안 기법과 ‘왜 통하는지’."],
    ["③ 핵심 수치", "에너지/성능 개선 등 숫자 1개."],
    ["④ 한계·내 생각", "적용 범위와 비판적 관점."],
    ["⑤ 출처", "정식 서지."]
  ],
  rules: ["본문 복사 금지, 자기 말로 요약.", "직접 인용은 짧게+출처.", "확실치 않은 수치는 빼기."],
  checklist: ["핵심 수치가 있는가?", "출처가 적혔는가?", "내 관점이 한 줄 있는가?"],
  current: ""   // 현재 산출물(마크다운). 없으면 빈 문자열.
};
