// check_content.mjs — paper-study-app의 assets/content.js를 기계로 점검한다.
// 사용: node check_content.mjs <content.js> [--blind <out.md>]
//   --blind: 정답 · 해설을 뺀 문항 사본을 써서, 만든 세션이 아닌 쪽이 독립으로 다시 풀게 한다.
// 종료 코드: error가 하나라도 있으면 1.
import fs from "node:fs";
import vm from "node:vm";

const args = process.argv.slice(2);
const file = args[0];
if (!file) { console.error("usage: node check_content.mjs <content.js> [--blind <out.md>]"); process.exit(2); }
const blindIdx = args.indexOf("--blind");
const blindOut = blindIdx >= 0 ? args[blindIdx + 1] : null;

const NAMES = ["APP_ID", "FOOTER", "SUBJECT", "SOURCES", "CHAPTERS", "QUIZ", "THINK", "RELATED", "GUIDE"];
const code = fs.readFileSync(file, "utf8");
const probe = NAMES.map(n => `${n}: typeof ${n} === "undefined" ? undefined : ${n}`).join(", ");
let C;
try { C = vm.runInNewContext(`${code}\n;({${probe}})`, {}, { filename: file }); }
catch (e) { console.error("ERROR content.js가 실행되지 않음:", e.message); process.exit(1); }

const errors = [], warns = [];
const err = m => errors.push(m), warn = m => warns.push(m);
const nonEmpty = s => typeof s === "string" && s.trim().length > 0;

NAMES.filter(n => n !== "FOOTER").forEach(n => { if (C[n] === undefined) err(`전역 ${n} 없음`); });

// 자료
(C.SOURCES || []).forEach((s, i) => {
  if (!nonEmpty(s.title)) err(`SOURCES[${i}] title 없음`);
  if (s.url && !/^https:\/\//.test(s.url)) warn(`SOURCES[${i}] url이 https가 아님: ${s.url}`);
  if (s.url && /\.pdf($|\?)/i.test(s.url) && !/doi\.org|arxiv\.org/i.test(s.url)) warn(`SOURCES[${i}] PDF 직접 링크 — 공식 랜딩 페이지가 있으면 그쪽으로`);
});

// 챕터
const ids = new Set();
(C.CHAPTERS || []).forEach((c, i) => {
  if (!nonEmpty(c.id)) err(`CHAPTERS[${i}] id 없음`);
  else if (ids.has(c.id)) err(`CHAPTERS id 중복: ${c.id}`); else ids.add(c.id);
  if (!nonEmpty(c.title)) err(`CHAPTERS[${i}] title 없음`);
  if (!Array.isArray(c.body) || c.body.length === 0) err(`CHAPTERS[${i}] body 비었음`);
  if (!nonEmpty(c.src)) err(`CHAPTERS[${i}] src(원문 근거) 없음`);
  if (!nonEmpty(c.tldr)) warn(`CHAPTERS[${i}] tldr 없음`);
});

// 퀴즈
const seenQ = new Set();
const answerPos = {};
for (const level of ["basic", "inter"]) {
  const list = (C.QUIZ || {})[level];
  if (!Array.isArray(list)) { err(`QUIZ.${level} 배열 없음`); continue; }
  if (list.length < 5) warn(`QUIZ.${level} ${list.length}문항 — 5문항 이상 권장`);
  let ox = 0;
  list.forEach((q, i) => {
    const at = `QUIZ.${level}[${i}]`;
    if (!nonEmpty(q.q)) err(`${at} q 없음`);
    else if (seenQ.has(q.q.trim())) err(`${at} 같은 문항이 이미 있음`); else seenQ.add(q.q.trim());
    if (!nonEmpty(q.why)) err(`${at} why(해설) 없음`);
    if (q.type === "mc") {
      if (!Array.isArray(q.choices) || q.choices.length < 2) err(`${at} choices 부족`);
      else if (!Number.isInteger(q.answer) || q.answer < 0 || q.answer >= q.choices.length) err(`${at} answer가 choices 범위 밖: ${q.answer}`);
      else { answerPos[q.answer] = (answerPos[q.answer] || 0) + 1; }
      if (Array.isArray(q.choices) && new Set(q.choices).size !== q.choices.length) err(`${at} 같은 보기가 둘`);
    } else if (q.type === "ox") {
      ox++;
      if (typeof q.answer !== "boolean") err(`${at} ox의 answer는 true/false`);
    } else err(`${at} type은 mc|ox: ${q.type}`);
  });
  if (list.length && ox / list.length > 0.4) warn(`QUIZ.${level} OX가 ${ox}/${list.length} — 찍어서 맞히기 쉬움`);
}
const mcTotal = Object.values(answerPos).reduce((a, b) => a + b, 0);
Object.entries(answerPos).forEach(([pos, n]) => {
  if (mcTotal >= 6 && n / mcTotal > 0.5) warn(`정답 위치가 ${Number(pos) + 1}번에 ${n}/${mcTotal} 몰림 — 보기 순서를 섞기`);
});

(C.THINK || []).forEach((t, i) => { if (!nonEmpty(t.q)) err(`THINK[${i}] q 없음`); });
(C.RELATED || []).forEach((r, i) => { if (!nonEmpty(r.kw)) err(`RELATED[${i}] kw(검색어) 없음`); });

if (blindOut) {
  const lines = ["# 독립 재풀이용 문항 (정답 · 해설 없음)", "", "각 문항의 정답 번호(OX는 O/X)와 근거 한 줄을 적는다. content.js를 열지 않는다.", ""];
  for (const level of ["basic", "inter"]) {
    ((C.QUIZ || {})[level] || []).forEach((q, i) => {
      lines.push(`## ${level}-${i + 1}`, q.q || "");
      if (q.type === "mc") (q.choices || []).forEach((c, j) => lines.push(`${j + 1}. ${c}`));
      else lines.push("O / X");
      lines.push("");
    });
  }
  fs.writeFileSync(blindOut, lines.join("\n"), "utf8");
  console.log(`blind 사본: ${blindOut}`);
}

warns.forEach(w => console.log("WARN ", w));
errors.forEach(e => console.log("ERROR", e));
const nq = ["basic", "inter"].map(l => ((C.QUIZ || {})[l] || []).length);
console.log(`챕터 ${(C.CHAPTERS || []).length} · 퀴즈 초급 ${nq[0]} / 중급 ${nq[1]} · error ${errors.length} · warn ${warns.length}`);
process.exit(errors.length ? 1 : 0);
