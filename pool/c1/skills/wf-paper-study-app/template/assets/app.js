/* ===========================================================
   학습 앱 템플릿 — 로직 (도메인 무관, 수정 불필요)
   콘텐츠는 assets/content.js 에서만 정의합니다.
   필요한 전역: APP_ID, SUBJECT, SOURCES, CHAPTERS, QUIZ, THINK, RELATED, GUIDE
   =========================================================== */
const LS = "studyapp_" + (typeof APP_ID !== "undefined" ? APP_ID : "default");
const state = load();
function load(){ try{return JSON.parse(localStorage.getItem(LS))||{}}catch(e){return {}} }
function save(){ localStorage.setItem(LS, JSON.stringify(state)); }
state.read = state.read || {};
state.quiz = state.quiz || {};
let curChapter = 0, quizTab = "basic";

const SECTIONS = [
  ["home","🏠","개요"],
  ["sources","📄","자료 원문"],
  ["chapters","📚","챕터 학습"],
  ["quiz","✏️","이해도 퀴즈"],
  ["think","💭","생각해볼 주제"],
  ["related","🔗","연관 주제 탐색"],
  ["guide","📝","산출물 가이드"]
];

function buildNav(){
  const ul = document.getElementById("nav");
  ul.innerHTML = SECTIONS.map(([id,ic,label])=>`
    <li><button data-sec="${id}"><span>${ic}</span><span>${label}</span><span class="done" id="navdone-${id}"></span></button></li>`).join("");
  ul.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{ go(b.dataset.sec); ul.classList.remove("open"); }));
}
function go(sec){
  document.querySelectorAll(".section").forEach(s=>s.classList.toggle("active", s.id==="sec-"+sec));
  document.querySelectorAll("#nav button").forEach(b=>b.classList.toggle("active", b.dataset.sec===sec));
  window.scrollTo(0,0);
  if(sec==="quiz") renderQuiz();
}
function updateProgress(){
  const total = CHAPTERS.length;
  const done = CHAPTERS.filter(c=>state.read[c.id]).length;
  document.getElementById("prog-text").textContent = `챕터 ${done}/${total} 읽음`;
  document.getElementById("prog-bar").style.width = (total? done/total*100:0)+"%";
  document.getElementById("navdone-chapters").textContent = done? `${done}/${total}`:"";
  document.getElementById("navdone-quiz").textContent = (state.quiz.basic!=null||state.quiz.inter!=null)? "✓":"";
}

/* ---------- 홈 ---------- */
function sourceCard(s){
  return `<div class="card">
    <span class="tag">${s.kind||"자료"}</span>
    <h3 style="margin-top:10px">${s.title}</h3>
    ${s.sub?`<p style="color:var(--muted);font-style:italic">${s.sub}</p>`:""}
    ${(s.meta||[]).map(([k,v])=>`<p class="kv"><b>${k}</b> ${v}</p>`).join("")}
    ${s.url?`<a class="btn ghost sm" href="${s.url}" target="_blank" rel="noopener" style="margin-top:8px">${s.urlLabel||"원문 보기"} →</a>`:""}
    ${s.note?`<p class="src">${s.note}</p>`:""}
  </div>`;
}
function renderHome(){
  const cards = SOURCES.slice(0,2).map(sourceCard).join("");
  document.getElementById("sec-home").innerHTML = `
    <h1 class="page">${SUBJECT.title}</h1>
    <p class="lead">${SUBJECT.subtitle||""}</p>
    <div class="pair">${cards}</div>
    ${SUBJECT.story?`<div class="card" style="background:var(--soft)"><h3>한눈에 보는 스토리</h3><p>${SUBJECT.story}</p>
      <button class="btn" onclick="go('chapters')">📚 챕터 학습 시작하기 →</button></div>`:""}
    <h2>이렇게 학습하세요</h2>
    <div class="card"><p>① <b>자료 원문</b> 훑기 → ② <b>챕터</b>를 해설과 함께 읽고 ‘읽음’ 체크 →
      ③ <b>퀴즈 초급·중급</b>으로 점검 → ④ <b>생각해볼 주제·연관 주제</b>로 넓히기 →
      ⑤ <b>산출물 가이드</b>로 마무리. <br>진행 상황은 이 브라우저에 자동 저장됩니다.</p></div>`;
}

/* ---------- 자료 원문 ---------- */
function renderSources(){
  document.getElementById("sec-sources").innerHTML = `
    <h1 class="page">📄 자료 원문 보기</h1>
    <p class="lead">아래 버튼으로 공식 출처(원문)를 새 탭에서 볼 수 있습니다.</p>
    ${SOURCES.map(sourceCard).join("")}
    <div class="card" style="background:var(--soft)">
      💡 원문이 어렵게 느껴지면, 먼저 <a href="#" onclick="go('chapters');return false">📚 챕터 학습</a>의 해설을 읽은 뒤 원문을 보면 훨씬 잘 읽힙니다.
    </div>`;
}

/* ---------- 챕터 ---------- */
function renderChapters(){
  if(!CHAPTERS.length){ document.getElementById("sec-chapters").innerHTML="<h1 class='page'>📚 챕터 학습</h1><p class='lead'>아직 챕터가 없습니다.</p>"; return; }
  const chips = CHAPTERS.map((c,i)=>{
    const cls = (state.read[c.id]?"read ":"") + (i===curChapter?"cur":"");
    return `<button class="${cls}" onclick="openChapter(${i})">${i+1}${state.read[c.id]?" ✓":""}</button>`;
  }).join("");
  const c = CHAPTERS[curChapter];
  document.getElementById("sec-chapters").innerHTML = `
    <h1 class="page">📚 챕터 학습</h1>
    <p class="lead">${CHAPTERS.length}개 챕터를 차례로 읽고 ‘읽음’을 체크하세요. 다 읽으면 퀴즈가 열립니다.</p>
    <div class="chip-row">${chips}</div>
    <div class="card">
      <span class="tag">CHAPTER ${curChapter+1} / ${CHAPTERS.length}</span>
      <h3 style="margin-top:10px;font-size:1.25rem">${c.title}</h3>
      ${c.tldr?`<div class="tldr">📌 ${c.tldr}</div>`:""}
      <div class="body">${c.body.map(p=>`<p>${p}</p>`).join("")}</div>
      ${(c.terms&&c.terms.length)?`<div class="terms"><h4>🔑 핵심 용어</h4>${c.terms.map(t=>`<div><b>${t.t}</b> — ${t.d}</div>`).join("")}</div>`:""}
      ${c.src?`<p class="src">📖 원문 근거: ${c.src}</p>`:""}
      <div class="chap-nav">
        <button class="btn ghost" onclick="prevChapter()" ${curChapter===0?"disabled":""}>◀ 이전</button>
        <button class="btn" onclick="toggleRead('${c.id}')">${state.read[c.id]?"✓ 읽음 (취소)":"읽음 표시하기"}</button>
        <button class="btn ghost" onclick="nextChapter()" ${curChapter===CHAPTERS.length-1?"disabled":""}>다음 ▶</button>
      </div>
    </div>`;
}
function openChapter(i){ curChapter=i; renderChapters(); window.scrollTo(0,0); }
function prevChapter(){ if(curChapter>0){curChapter--;renderChapters();window.scrollTo(0,0);} }
function nextChapter(){ if(curChapter<CHAPTERS.length-1){curChapter++;renderChapters();window.scrollTo(0,0);} }
function toggleRead(id){
  state.read[id] = !state.read[id]; save(); updateProgress();
  const allRead = CHAPTERS.every(c=>state.read[c.id]);
  if(state.read[id] && curChapter<CHAPTERS.length-1){ nextChapter(); } else { renderChapters(); }
  if(allRead) setTimeout(()=>{ if(confirm("모든 챕터를 읽었습니다! 이해도 퀴즈를 풀어볼까요?")) go("quiz"); },200);
}

/* ---------- 퀴즈 ---------- */
let qIdx=0, qScore=0, qAnswered=false;
function tabsHtml(){ return `<div class="tabs">
    <button class="${quizTab==='basic'?'active':''}" onclick="setTab('basic')">초급 (${(QUIZ.basic||[]).length})</button>
    <button class="${quizTab==='inter'?'active':''}" onclick="setTab('inter')">중급 (${(QUIZ.inter||[]).length})</button></div>`; }
function renderQuiz(){
  const allRead = CHAPTERS.length>0 && CHAPTERS.every(c=>state.read[c.id]);
  const sec = document.getElementById("sec-quiz");
  const head = `<h1 class="page">✏️ 이해도 퀴즈</h1><p class="lead">초급(사실 확인) → 중급(적용·분석) 순서로 풀어보세요.</p>${tabsHtml()}`;
  if(!allRead){
    sec.innerHTML = head + `<div class="card lock"><div class="big">🔒</div>
      <p>먼저 <b>모든 챕터를 읽어</b> 주세요. (${CHAPTERS.filter(c=>state.read[c.id]).length}/${CHAPTERS.length} 읽음)</p>
      <button class="btn" onclick="go('chapters')">📚 챕터 학습으로</button>
      <p style="margin-top:14px"><button class="btn ghost sm" onclick="forceQuiz()">그래도 지금 풀기</button></p></div>`;
    return;
  }
  startQuiz(head);
}
function forceQuiz(){ startQuiz(`<h1 class="page">✏️ 이해도 퀴즈</h1>${tabsHtml()}`); }
function setTab(t){ quizTab=t; renderQuiz(); }
function startQuiz(head){ qIdx=0; qScore=0; qAnswered=false; document.getElementById("sec-quiz").innerHTML = head + `<div id="qbox"></div>`; renderQ(); }
function curList(){ return QUIZ[quizTab]||[]; }
function correctIndex(item){ return item.type==='ox' ? (item.answer?0:1) : item.answer; }
function renderQ(){
  const list=curList(); if(!list.length){ document.getElementById("qbox").innerHTML="<div class='card'>문항이 없습니다.</div>"; return; }
  const item=list[qIdx]; qAnswered=false;
  const choices = item.type==='ox' ? ['⭕ 맞다 (O)','❌ 아니다 (X)'] : item.choices;
  document.getElementById("qbox").innerHTML = `
    <div class="card">
      <div class="qmeta">문제 ${qIdx+1} / ${list.length} · ${quizTab==='basic'?'초급':'중급'}</div>
      <div class="q">${item.q}</div>
      <div class="choices">${choices.map((c,i)=>`<button class="choice" data-i="${i}">${c}</button>`).join("")}</div>
      <div class="why" id="why"></div>
      <div class="chap-nav" style="justify-content:flex-end"><button class="btn" id="qnext" disabled>다음 ▶</button></div>
    </div>`;
  document.querySelectorAll(".choice").forEach(b=>b.addEventListener("click",pickQ));
  document.getElementById("qnext").addEventListener("click",nextQ);
}
function pickQ(e){
  if(qAnswered) return; qAnswered=true;
  const item=curList()[qIdx]; const chosen=+e.target.dataset.i; const correct=correctIndex(item);
  document.querySelectorAll(".choice").forEach((b,i)=>{ b.disabled=true;
    if(i===correct)b.classList.add("correct"); if(i===chosen&&chosen!==correct)b.classList.add("wrong"); });
  if(chosen===correct)qScore++;
  const why=document.getElementById("why"); why.innerHTML=(chosen===correct?"✅ 정답! ":"❌ 오답. ")+(item.why||""); why.classList.add("show");
  document.getElementById("qnext").disabled=false;
}
function nextQ(){ qIdx++; if(qIdx<curList().length)renderQ(); else finishQuiz(); }
function finishQuiz(){
  const list=curList(); const pct=Math.round(qScore/list.length*100);
  state.quiz[quizTab]=qScore; save(); updateProgress();
  let msg = pct>=80?"훌륭해요! 잘 이해했어요 👍":pct>=50?"좋아요. 틀린 부분은 챕터로 복습!":"챕터를 한 번 더 읽어볼까요?";
  const nextBtn = quizTab==='basic' ? `<button class="btn" onclick="setTab('inter')">중급 도전 →</button>` : `<button class="btn" onclick="go('think')">💭 생각해볼 주제로 →</button>`;
  document.getElementById("qbox").innerHTML = `<div class="card score">
      <div class="big">${qScore} / ${list.length}</div>
      <p style="font-size:1.1rem;font-weight:700">${pct}점 · ${msg}</p>
      <div class="chap-nav" style="justify-content:center;gap:10px">
        <button class="btn ghost" onclick="setTab('${quizTab}')">다시 풀기</button>${nextBtn}</div></div>`;
}

/* ---------- 생각해볼 주제 ---------- */
function renderThink(){
  document.getElementById("sec-think").innerHTML = `
    <h1 class="page">💭 생각해볼 주제</h1>
    <p class="lead">정답이 없는 질문들입니다. 산출물에 깊이를 더하거나 토론거리로 좋아요.</p>
    ${THINK.map((t,i)=>`<div class="think">
        <div class="qq">${i+1}. ${t.q}</div>
        ${t.hint?`<details><summary>생각 도우미 보기</summary><div class="hint">💡 ${t.hint}</div></details>`:""}
      </div>`).join("")}`;
}

/* ---------- 연관 주제 탐색 ---------- */
function renderRelated(){
  document.getElementById("sec-related").innerHTML = `
    <h1 class="page">🔗 연관 주제 탐색 도우미</h1>
    <p class="lead">더 알아보고 싶은 주제를 바로 검색해 보세요. (새 탭으로 열립니다)</p>
    ${RELATED.map(r=>{
      const g="https://scholar.google.com/scholar?q="+encodeURIComponent(r.kw);
      const w="https://www.google.com/search?q="+encodeURIComponent(r.kw);
      return `<div class="related">
        <div class="txt"><b>${r.t}</b><span>${r.d}</span></div>
        <div class="search-actions">
          <a class="btn sm" href="${g}" target="_blank" rel="noopener">Scholar</a>
          <a class="btn ghost sm" href="${w}" target="_blank" rel="noopener">Web</a>
        </div></div>`;
    }).join("")}`;
}

/* ---------- 산출물 가이드 ---------- */
function renderGuide(){
  const g=GUIDE||{};
  document.getElementById("sec-guide").innerHTML = `
    <h1 class="page">📝 ${g.title||"산출물 가이드"}</h1>
    <p class="lead">${g.intro||"아래 구조·규칙을 지켜 산출물을 완성하세요."}</p>
    ${(g.structure&&g.structure.length)?`<div class="card"><h3>구조</h3>
      <table class="guide-table">${g.structure.map(([a,b])=>`<tr><td>${a}</td><td>${b}</td></tr>`).join("")}</table></div>`:""}
    ${(g.rules&&g.rules.length)?`<div class="card"><h3>⚖️ 규칙</h3><ul class="rules">${g.rules.map(r=>`<li>${r}</li>`).join("")}</ul></div>`:""}
    ${(g.checklist&&g.checklist.length)?`<div class="card"><h3>✅ 제출 전 체크리스트</h3><ul class="check">${g.checklist.map(c=>`<li><label><input type="checkbox"> ${c}</label></li>`).join("")}</ul></div>`:""}
    ${g.current?`<h2>📄 현재 산출물</h2><div class="report-md">${mdToHtml(g.current)}</div>`:""}`;
}

/* 작은 마크다운 → HTML (제목/굵게/이탤릭/문단) */
function mdToHtml(md){
  return md.split("\n").map(line=>{
    line=line.replace(/\*\*(.+?)\*\*/g,"<b>$1</b>").replace(/\*(.+?)\*/g,"<em>$1</em>");
    if(line.startsWith("## ")) return "<h2>"+line.slice(3)+"</h2>";
    if(line.startsWith("# ")) return "<h1>"+line.slice(2)+"</h1>";
    if(line.trim()==="") return "";
    return "<p>"+line+"</p>";
  }).join("");
}

function init(){
  buildNav();
  renderHome(); renderSources(); renderChapters(); renderThink(); renderRelated(); renderGuide();
  updateProgress();
  document.getElementById("menu-btn").addEventListener("click",()=>document.getElementById("nav").classList.toggle("open"));
  go("home");
}
init();
