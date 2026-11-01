// stub_check.js — 브라우저 없이 엔진의 렌더 함수를 끝까지 돌려 본다(DOM 스텁).
// 사용: node stub_check.js <app/assets 폴더> [data.js 대신 쓸 파일]
// 출력: 채워진 칸 OK / 빈 칸 EMPTY / 숨긴 절 HIDDEN, 그리고 NaN · undefined가 화면 글에 섞였는지.
// 종료 코드: 예외 또는 NaN/undefined가 있으면 1.
const path = require("path");
const dir = path.resolve(process.argv[2] || ".");
const dataFile = process.argv[3] ? path.resolve(process.argv[3]) : path.join(dir, "data.js");

const store = {};
function makeEl(id) {
  return { id, innerHTML: "", textContent: "", value: "", style: {}, open: false, dataset: {},
    addEventListener() {}, classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } } };
}
let ready = null;
global.window = { addEventListener: (e, f) => { if (e === "DOMContentLoaded") ready = f; } };
global.document = {
  title: "",
  documentElement: { classList: { add() {}, toggle() {}, contains() { return false; } } },
  getElementById: id => store[id] || (store[id] = makeEl(id)),
  querySelectorAll: () => [],
  addEventListener: (e, f) => { if (e === "DOMContentLoaded") ready = f; }
};
global.localStorage = { getItem() { return null; }, setItem() {} };

let bad = 0;
try {
  require(path.join(dir, "price.js"));
  require(dataFile);
  require(path.join(dir, "engine.js"));
  if (!ready) throw new Error("DOMContentLoaded 처리기가 등록되지 않음");
  ready();
} catch (e) {
  console.log("EXCEPTION", e.stack || e.message);
  process.exit(1);
}
Object.keys(store).sort().forEach(id => {
  const e = store[id], html = (e.innerHTML || "") + (e.textContent || "");
  const state = e.style.display === "none" ? "HIDDEN" : (html.length > 10 ? "OK    " : "EMPTY ");
  const leak = /NaN|undefined|Infinity/.test(html) ? "  <- NaN/undefined/Infinity" : "";
  if (leak) bad++;
  console.log(state, id + leak);
});
console.log(bad ? `FAIL: 화면 글에 NaN/undefined/Infinity ${bad}곳` : "PASS");
process.exit(bad ? 1 : 0);
