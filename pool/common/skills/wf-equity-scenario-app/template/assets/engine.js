/* equity-scenario-app 엔진 v3 — 회사 무관.
   데이터는 window.COMPANY / window.SOURCES / window.__PX 에서만 읽는다. 차트는 의존성 없는 인라인 SVG.
   필수 키: meta · market · financials{FY_prev, Q_latest} · engineDefaults · presets · narrative.
   선택 키(없으면 그 절을 숨긴다): estimate · regionMix · suppliers/customers/historyTimeline ·
   scenarios + dividendPolicies + priceBand · cashflow + balanceStress · trackIndicators · events · priceMarks · eventColors.
   v2에서 바꾼 점: 회사 이름 · 연도 · 금액 · 출처 id 하드코딩 제거, 선택 절 숨김, 월봉/일봉 모두 받음. */
(function () {
  "use strict";
  const C = window.COMPANY, S = window.SOURCES;
  // 가격 배열: [YYYYMMDD|YYYYMM, close]. 월봉(6자리)은 1일로 맞춘다.
  const PX = (window.__PX || []).map(([d, c]) => { const s = String(d); return [s.length === 6 ? s + "01" : s, c]; });
  const SRC_ORDER = Object.keys(S);
  const fnNum = (id) => SRC_ORDER.indexOf(id) + 1;
  const PAL = ["#4da3ff", "#35c46b", "#f0a13a", "#b07cff", "#ff6b9d", "#5fd0d0"];
  const has = (v) => v != null && (!Array.isArray(v) || v.length > 0);

  // ---------- format ----------
  const won = (n) => Math.round(n).toLocaleString("ko-KR") + "원";
  const wonK = (n) => Math.round(n).toLocaleString("ko-KR");
  const eok = (n) => Math.round(n).toLocaleString("ko-KR") + "억";
  const jo  = (n) => (n / 10000).toFixed(2) + "조";
  const pct = (n) => n.toFixed(1) + "%";
  const perShareWon = (amtEok, shares) => shares ? (amtEok * 1e8) / shares : 0;
  const el = (id) => document.getElementById(id);
  const hide = (id) => { const e = el(id); if (e) e.style.display = "none"; };
  const setText = (id, html) => { const e = el(id); if (e && html) e.innerHTML = html; };
  function srcSup(id) {
    const s = S[id]; if (!s) return "";
    return `<sup class="fn ${id === "assumption" ? "assref" : ""}" title="${s.title}">[${fnNum(id)}]</sup>`;
  }

  // 이벤트 회사 색: data의 eventColors가 우선, 없으면 등장 순서대로 팔레트.
  const EVENT_COLOR = Object.assign({}, C.eventColors || {});
  (C.events || []).forEach(e => { if (!EVENT_COLOR[e.company]) EVENT_COLOR[e.company] = PAL[Object.keys(EVENT_COLOR).length % PAL.length]; });
  const evColor = (name) => EVENT_COLOR[name] || "#8b93a7";

  // ---------- SVG charts ----------
  function svgLineArea(series, opt) {
    opt = opt || {}; const W = 1000, H = opt.h || 300, pad = 42, padB = 28;
    const ys = series.map(d => d[1]); const minY = Math.min(...ys), maxY = Math.max(...ys);
    const x = i => pad + (W - pad - 12) * (i / Math.max(1, series.length - 1));
    const y = v => (H - padB) - (H - padB - 14) * ((v - minY) / (maxY - minY || 1));
    const line = series.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(d[1]).toFixed(1)}`).join(" ");
    const area = `${line} L${x(series.length - 1).toFixed(1)} ${H - padB} L${x(0).toFixed(1)} ${H - padB} Z`;
    let grid = ""; const ny = 4;
    for (let g = 0; g <= ny; g++) { const v = minY + (maxY - minY) * g / ny, yy = y(v);
      grid += `<line x1="${pad}" y1="${yy}" x2="${W - 12}" y2="${yy}" class="grid"/><text x="${pad - 6}" y="${yy + 4}" class="yl" text-anchor="end">${wonK(v)}</text>`; }
    let xlab = ""; const step = Math.max(1, Math.floor(series.length / 7));
    for (let i = 0; i < series.length; i += step) xlab += `<text x="${x(i)}" y="${H - 8}" class="xl" text-anchor="middle">${series[i][0]}</text>`;
    let mk = ""; (opt.marks || []).forEach(m => { const i = m.i < 0 ? series.length + m.i : m.i;
      mk += `<circle cx="${x(i)}" cy="${y(series[i][1])}" r="4.5" fill="${m.color || "#ff6b4a"}"/>` +
            `<text x="${x(i)}" y="${y(series[i][1]) - 12}" class="mklab" text-anchor="middle" fill="${m.color || "#ff6b4a"}">${m.label}</text>`; });
    return `<svg viewBox="0 0 ${W} ${H}" class="chart">
      <defs><linearGradient id="ga" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#4da3ff" stop-opacity=".35"/><stop offset="1" stop-color="#4da3ff" stop-opacity="0"/></linearGradient></defs>
      ${grid}<path d="${area}" fill="url(#ga)"/><path d="${line}" fill="none" stroke="#4da3ff" stroke-width="2.4"/>${mk}${xlab}</svg>`;
  }

  function svgBars(series, opt) {
    opt = opt || {}; const W = 1000, H = opt.h || 260, pad = 46, padB = 30;
    if (!series.length) return "<p class='sub'>데이터 없음</p>";
    const maxV = Math.max(...series.map(d => Math.max(d.value, d.hi || 0)), 1);
    const n = series.length, bw = (W - pad - 12) / n * 0.62, gap = (W - pad - 12) / n;
    const y = v => (H - padB) - (H - padB - 16) * (v / maxV);
    let grid = ""; for (let g = 0; g <= 3; g++) { const v = maxV * g / 3, yy = y(v);
      grid += `<line x1="${pad}" y1="${yy}" x2="${W - 12}" y2="${yy}" class="grid"/><text x="${pad - 6}" y="${yy + 4}" class="yl" text-anchor="end">${opt.fmt ? opt.fmt(v) : wonK(v)}</text>`; }
    let bars = ""; series.forEach((d, i) => { const bx = pad + gap * i + (gap - bw) / 2, by = y(d.value), bh = (H - padB) - by, cxp = bx + bw / 2;
      const col = d.hot ? "#ff6b4a" : (d.est ? "#f0a13a" : (opt.color || "#4da3ff"));
      const rectAttr = d.est ? `fill="${col}" fill-opacity="0.28" stroke="${col}" stroke-width="1.5" stroke-dasharray="4 3"` : `fill="${col}"`;
      bars += `<rect x="${bx}" y="${by}" width="${bw}" height="${bh}" rx="3" ${rectAttr}/>`;
      if (d.lo != null && d.hi != null) { const yh = y(d.hi), yl = y(d.lo);
        bars += `<line x1="${cxp}" y1="${yh}" x2="${cxp}" y2="${yl}" class="wk"/><line x1="${cxp - 6}" y1="${yh}" x2="${cxp + 6}" y2="${yh}" class="wk"/><line x1="${cxp - 6}" y1="${yl}" x2="${cxp + 6}" y2="${yl}" class="wk"/>`; }
      const labY = (d.est && d.hi != null) ? y(d.hi) - 7 : by - 6;
      bars += `<text x="${cxp}" y="${labY}" class="bl" text-anchor="middle" fill="${col}">${opt.lab ? opt.lab(d.value) : wonK(d.value)}</text>` +
              `<text x="${cxp}" y="${H - 8}" class="xl" text-anchor="middle">${d.label}</text>`; });
    return `<svg viewBox="0 0 ${W} ${H}" class="chart">${grid}${bars}</svg>`;
  }

  function svgDonut(parts) {
    const R = 80, r = 48, cx = 110, cy = 110; const tot = parts.reduce((a, p) => a + p.value, 0) || 1;
    let ang = -Math.PI / 2, segs = "";
    parts.forEach((p, i) => { const a2 = ang + (p.value / tot) * Math.PI * 2;
      const x1 = cx + R * Math.cos(ang), y1 = cy + R * Math.sin(ang), x2 = cx + R * Math.cos(a2), y2 = cy + R * Math.sin(a2);
      const xi2 = cx + r * Math.cos(a2), yi2 = cy + r * Math.sin(a2), xi1 = cx + r * Math.cos(ang), yi1 = cy + r * Math.sin(ang);
      const large = (a2 - ang) > Math.PI ? 1 : 0; const col = PAL[i % PAL.length];
      segs += `<path d="M${x1} ${y1} A${R} ${R} 0 ${large} 1 ${x2} ${y2} L${xi2} ${yi2} A${r} ${r} 0 ${large} 0 ${xi1} ${yi1} Z" fill="${col}"/>`;
      ang = a2; });
    const legend = parts.map((p, i) => `<div class="lg"><span class="sw" style="background:${PAL[i % PAL.length]}"></span>${p.name} <b>${p.pct}%</b> <span class="sub">${eok(p.value)}</span></div>`).join("");
    return `<div class="donutwrap"><svg viewBox="0 0 220 220" class="donut"><g>${segs}</g></svg><div class="legend">${legend}</div></div>`;
  }

  // ---------- compute (고급 수동 슬라이더) ----------
  const D = C.engineDefaults, state = {};
  Object.keys(D).forEach(k => state[k] = D[k].value);
  function compute(st) {
    const shares = C.market.sharesTotal.value, eligible = C.market.sharesEligible.value || shares;
    const q = C.financials.Q_latest, fy = C.financials.FY_prev || {}, price = C.market.price.value;
    const fyRev = q.revenue * st.annualizeFactor, fyOp = fyRev * (st.sustainedOpMargin / 100), fyNet = fyOp * st.netToOpRatio;
    const eps = perShareWon(fyNet, shares), divTotal = fyNet * (st.payout / 100), dps = perShareWon(divTotal, eligible);
    const divYield = price ? (dps / price) * 100 : 0;
    const projEquity = (fy.equity || 0) + fyNet * (1 - st.payout / 100), bps = perShareWon(projEquity, shares);
    const ebitda = fyOp + st.depreciation;
    const targets = [
      { key: "PER", assume: `EPS ${won(eps)} × ${st.per}배`, price: eps * st.per, src: D.per.src },
      { key: "배당수익률", assume: `DPS ${won(dps)} ÷ ${st.targetYield}%`, price: dps / (st.targetYield / 100), src: D.targetYield.src },
      { key: "PBR", assume: `BPS ${won(bps)} × ${st.pbr}배`, price: bps * st.pbr, src: D.pbr.src },
      { key: "EV/EBITDA", assume: `EBITDA ${eok(ebitda)} × ${st.evEbitdaMult}배 − 순차입금 ${eok(st.netDebt)}`, price: perShareWon(ebitda * st.evEbitdaMult - st.netDebt, shares), src: D.evEbitdaMult.src }
    ].map(t => ({ ...t, upside: price ? ((t.price - price) / price) * 100 : 0 }));
    return { shares, eligible, price, fyRev, fyOp, fyNet, eps, divTotal, dps, divYield, projEquity, bps, ebitda, targets };
  }

  // ---------- date helpers (YYYYMMDD) ----------
  const pad2 = n => String(n).padStart(2, "0");
  const parseD = s => new Date(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8));
  const fmtD = d => `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}`;
  const dot = s => `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}`;
  const iso = s => `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;

  // ---------- hero ----------
  let pxLive = null, pxRefreshed = false;
  function renderHero() {
    const m = C.market;
    el("hero").innerHTML = `
      <div class="price"><b id="heroPrice">${wonK(m.price.value)}</b><span class="unit">원</span>
        ${pxRefreshed ? `<span class="chg up">↻ 갱신됨</span>` : ""}</div>
      <div class="herostats">
        <span>시총 <b>${jo(m.marketCap.value)}</b></span>
        <span>52주 <b>${wonK(m.week52.low)}~${wonK(m.week52.high)}</b></span>
        <span>발행 <b>${(m.sharesTotal.value / 1e6).toFixed(1)}M주</b></span>
        <span>최대주주 <b>${m.majorShareholder.name} ${m.majorShareholder.stake}%</b></span>
      </div>
      <div class="herostamp sub">${C.meta.market} · ${C.meta.ticker} · 종가기준일 ${m.price.date}${srcSup(m.price.src)}</div>`;
  }

  // ---------- price chart (기간 선택 + 갱신) ----------
  const pxState = { period: "3Y", from: null, to: null };
  const PERIOD_M = { "6M": 6, "1Y": 12, "3Y": 36, "10Y": 120, "ALL": 600 };

  function pxSeriesArray() {
    const arr = PX.slice();
    if (pxLive) { const last = arr[arr.length - 1];
      if (pxLive.date > last[0]) arr.push([pxLive.date, pxLive.close]);
      else if (pxLive.date === last[0]) arr[arr.length - 1] = [pxLive.date, pxLive.close]; }
    return arr;
  }

  function renderPriceChart() {
    if (!PX.length) { el("priceChart").innerHTML = "<p class='sub'>주가 데이터 없음</p>"; return; }
    const arr = pxSeriesArray();
    const ref = arr[arr.length - 1][0];
    let lo, hi;
    if (pxState.from && pxState.to) { lo = pxState.from; hi = pxState.to; }
    else { const d = parseD(ref); d.setMonth(d.getMonth() - (PERIOD_M[pxState.period] || 36)); lo = fmtD(d); hi = "99999999"; }
    let f = arr.filter(p => p[0] >= lo && p[0] <= hi);
    if (f.length < 2) f = arr.slice(-2);
    const MAX = 450, step = Math.ceil(f.length / MAX);
    const ds = step > 1 ? f.filter((_, i) => i % step === 0) : f.slice();
    if (ds[ds.length - 1][0] !== f[f.length - 1][0]) ds.push(f[f.length - 1]);
    const spanDays = (parseD(f[f.length - 1][0]) - parseD(f[0][0])) / 864e5;
    const fmtLab = spanDays <= 200 ? (s => s.slice(4, 6) + "/" + s.slice(6, 8)) : (s => s.slice(2, 4) + "/" + s.slice(4, 6));
    const series = ds.map(p => [fmtLab(p[0]), p[1]]);
    let peakI = 0; ds.forEach((p, i) => { if (p[1] > ds[peakI][1]) peakI = i; });
    const marks = [{ i: peakI, label: "최고 " + wonK(ds[peakI][1]), color: "#ff6b4a" }];
    (C.priceMarks || []).forEach(m => { const i = ds.findIndex(p => p[0] >= m.date);
      if (i >= 0 && i !== peakI) marks.unshift({ i, label: m.label, color: m.color || "#8b93a7" }); });
    el("priceChart").innerHTML = series.length > 1 ? svgLineArea(series, { h: 300, marks }) : "<p class='sub'>기간 안 데이터 부족</p>";
    const fi = f[0], la = f[f.length - 1], chg = (la[1] - fi[1]) / fi[1] * 100;
    const hp = Math.max(...f.map(p => p[1])), lp = Math.min(...f.map(p => p[1]));
    el("priceStats").innerHTML =
      `<span>${dot(fi[0])} → ${dot(la[0])}</span><span>고 <b>${wonK(hp)}</b> · 저 <b>${wonK(lp)}</b></span>` +
      `<span class="${chg >= 0 ? "up" : "down"}">기간수익률 <b>${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%</b></span>`;
  }

  function initPxControls() {
    if (!PX.length) { hide("pxCtl"); return; }
    document.querySelectorAll(".pxbtns button").forEach(b => b.addEventListener("click", () => {
      pxState.period = b.dataset.p; pxState.from = pxState.to = null;
      el("pxFrom").value = ""; el("pxTo").value = "";
      document.querySelectorAll(".pxbtns button").forEach(x => x.classList.toggle("on", x === b));
      renderPriceChart();
    }));
    const fI = el("pxFrom"), tI = el("pxTo");
    fI.min = tI.min = iso(PX[0][0]); fI.max = tI.max = iso(PX[PX.length - 1][0]);
    el("pxApply").addEventListener("click", () => {
      if (fI.value && tI.value) { pxState.from = fI.value.replace(/-/g, ""); pxState.to = tI.value.replace(/-/g, "");
        document.querySelectorAll(".pxbtns button").forEach(x => x.classList.remove("on")); renderPriceChart(); }
    });
    if (C.meta.liveRefresh === false) hide("pxRefresh");
    else el("pxRefresh").addEventListener("click", refreshPrice);
  }

  // 국내 종목 최근 종가 갱신(공개 CORS 프록시 경유 — 막히면 정적 값 유지).
  async function refreshPrice() {
    const st = el("pxStatus"); st.textContent = "갱신 중…"; st.className = "sub";
    const now = new Date(), s = new Date(now); s.setDate(s.getDate() - 16);
    const url = `https://api.finance.naver.com/siseJson.naver?symbol=${C.meta.ticker}&requestType=1&startTime=${fmtD(s)}&endTime=${fmtD(now)}&timeframe=day`;
    const proxies = [u => `https://corsproxy.io/?url=${encodeURIComponent(u)}`, u => `https://api.allorigins.win/raw?url=${encodeURIComponent(u)}`];
    for (const p of proxies) {
      try {
        const r = await fetch(p(url)); if (!r.ok) continue;
        const t = await r.text();
        const m = [...t.matchAll(/\["(\d{8})",\s*\d+,\s*\d+,\s*\d+,\s*(\d+)/g)];
        if (!m.length) continue;
        const last = m[m.length - 1], date = last[1], close = +last[2];
        pxLive = { date, close }; pxRefreshed = true;
        C.market.price = { value: close, date: iso(date), src: C.market.price.src };
        renderHero(); renderPriceChart();
        st.textContent = `✓ 갱신됨: ${dot(date)} ${wonK(close)}`; st.className = "sub up";
        refresh();
        return;
      } catch (e) { /* 다음 프록시 */ }
    }
    st.textContent = `갱신 실패 — 프록시 차단. 정적 종가(${C.market.price.date}) 유지`; st.className = "sub down";
  }

  // ---------- history charts ----------
  function renderHistory() {
    const e = C.estimate, eLab = (e && e.label) || "E";
    setText("estCap", e && e.caption);
    if (!e) hide("estCap");
    const joLab = v => (v / 10000).toFixed(1) + "조";
    const rev = (C.annualHistory || []).map(a => ({ label: a.year, value: a.rev }));
    if (e && e.revenue) rev.push({ label: eLab, value: e.revenue.mid, lo: e.revenue.lo, hi: e.revenue.hi, est: true });
    el("revChart").innerHTML = svgBars(rev, { h: 240, color: "#4da3ff", lab: joLab });
    const q = (C.quarterlyHistory || []).map(x => ({ label: x.q, value: x.rev, hot: x.hot }));
    if (e && e.quarter) (e.quarterLabels || []).forEach(lab => q.push({ label: lab, value: e.quarter.mid, lo: e.quarter.lo, hi: e.quarter.hi, est: true }));
    el("qChart").innerHTML = svgBars(q, { h: 220, lab: v => (v / 10000).toFixed(2) + "조" });
    const dps = (C.dpsHistory || []).map(d => ({ label: d.year, value: d.dps }));
    if (e && e.dps) dps.push({ label: eLab, value: e.dps.mid, lo: e.dps.lo, hi: e.dps.hi, est: true });
    el("dpsChart").innerHTML = svgBars(dps, { h: 200, color: "#35c46b", lab: v => wonK(v) });
    const op = (C.annualHistory || []).filter(a => a.rev).map(a => ({ label: a.year, value: +(a.op / a.rev * 100).toFixed(1) }));
    if (e && e.opMargin) op.push({ label: eLab, value: e.opMargin.mid, lo: e.opMargin.lo, hi: e.opMargin.hi, est: true });
    el("opChart").innerHTML = svgBars(op, { h: 200, color: "#f0a13a", lab: v => v.toFixed(1) + "%", fmt: v => v.toFixed(0) + "%" });
    if (C.regionMix && has(C.regionMix.parts)) {
      setText("regionTitle", C.regionMix.title);
      el("regionChart").innerHTML = svgDonut(C.regionMix.parts);
    } else hide("regionBox");
  }

  // ---------- company profile ----------
  function renderProfile() {
    const sup = C.suppliers || {}, cus = C.customers || {}, tl = C.historyTimeline || [];
    if (!has(sup.items) && !has(cus.items) && !tl.length) { hide("sec-profile"); return; }
    const li = (arr) => (arr || []).map(x => `<span class="chip">${x}</span>`).join("");
    el("profile").innerHTML = `
      <div class="pcard"><h3>공급사 (매입)${srcSup(sup.src)}</h3><div class="chips">${li(sup.items)}</div></div>
      <div class="pcard"><h3>주요 고객 (납품)${srcSup(cus.src)}</h3><div class="chips">${li(cus.items)}</div></div>`;
    el("timeline").innerHTML = tl.map(h =>
      `<div class="tl"><div class="tly">${h.y}</div><div class="tlt">${h.t}${srcSup(h.src)}</div></div>`).join("");
  }

  // ---------- sliders / presets ----------
  function renderSliders() {
    const groups = [
      { title: "① 실적 가정", keys: ["annualizeFactor", "sustainedOpMargin", "netToOpRatio"] },
      { title: "② 배당 가정", keys: ["payout"] },
      { title: "③ 주가 모델", keys: ["per", "targetYield", "pbr", "evEbitdaMult", "depreciation", "netDebt"] }
    ];
    el("sliders").innerHTML = groups.map(g => `<div class="sgroup"><h4>${g.title}</h4>${g.keys.map(k => {
      const d = D[k];
      const marks = d.marks ? `<div class="marks">${Object.entries(d.marks).map(([lab, val]) =>
        `<button class="mark" data-key="${k}" data-val="${val}">${lab}</button>`).join("")}</div>` : "";
      return `<div class="srow"><label>${d.label}${srcSup(d.src)}</label>
        <div class="sctl"><input type="range" id="sl_${k}" min="${d.min}" max="${d.max}" step="${d.step}" value="${state[k]}"><output id="ov_${k}">${state[k]}</output></div>${marks}</div>`;
    }).join("")}</div>`).join("");
    Object.keys(D).forEach(k => { const inp = el("sl_" + k);
      inp.addEventListener("input", () => { state[k] = parseFloat(inp.value); el("ov_" + k).textContent = state[k]; refresh(); }); });
    document.querySelectorAll(".mark").forEach(b => b.addEventListener("click", () => {
      const k = b.dataset.key, v = parseFloat(b.dataset.val); state[k] = v; el("sl_" + k).value = v; el("ov_" + k).textContent = v; refresh(); }));
  }
  function renderPresets() {
    el("presets").innerHTML = Object.keys(C.presets || {}).map(n => `<button class="preset" data-name="${n}">${n}</button>`).join("");
    document.querySelectorAll(".preset").forEach(b => b.addEventListener("click", () => {
      const p = C.presets[b.dataset.name];
      Object.entries(p).forEach(([k, v]) => { state[k] = v; el("sl_" + k).value = v; el("ov_" + k).textContent = v; });
      document.querySelectorAll(".preset").forEach(x => x.classList.remove("active")); b.classList.add("active"); refresh(); }));
  }

  // ---------- results ----------
  function renderResults(r) {
    el("pnl").innerHTML = `
      <div class="card-row"><span>연간 매출 (최근 분기×${state.annualizeFactor})</span><b>${jo(r.fyRev)}</b></div>
      <div class="card-row"><span>연간 영업이익 (${pct(state.sustainedOpMargin)})</span><b>${eok(r.fyOp)}</b></div>
      <div class="card-row"><span>연간 순이익</span><b>${eok(r.fyNet)}</b></div>
      <div class="card-row"><span>EPS</span><b>${won(r.eps)}</b></div>`;
    el("divbox").innerHTML = `
      <div class="big"><span>배당금 총액</span><b>${eok(r.divTotal)}</b></div>
      <div class="big hot"><span>1주당 배당액 (DPS)</span><b>${won(r.dps)}</b></div>
      <div class="big"><span>시가배당률</span><b>${pct(r.divYield)}</b></div>
      <div class="hint">배당성향 ${pct(state.payout)} · 배당가능 ${wonK(r.eligible)}주</div>`;
    const maxP = Math.max(r.price, ...r.targets.map(t => t.price), 1);
    el("targets").innerHTML = `<table><thead><tr><th>모델</th><th>가정</th><th class="num">내재주가</th><th class="num">상승여력</th><th class="bar"></th></tr></thead><tbody>
      ${r.targets.map(t => `<tr><td><b>${t.key}</b>${srcSup(t.src)}</td><td class="assume">${t.assume}</td>
        <td class="num"><b>${won(t.price)}</b></td><td class="num ${t.upside >= 0 ? "up" : "down"}">${t.upside >= 0 ? "+" : ""}${t.upside.toFixed(0)}%</td>
        <td class="bar"><span class="b" style="width:${(t.price / maxP) * 100}%"></span></td></tr>`).join("")}
      <tr class="cur"><td colspan="2">현재가 (기준선)</td><td class="num"><b>${won(r.price)}</b></td><td class="num">—</td><td class="bar"><span class="b cur" style="width:${(r.price / maxP) * 100}%"></span></td></tr>
      </tbody></table>`;
  }

  // ---------- signed bar chart (현금흐름: 음수 허용) ----------
  function svgSignedBars(series, opt) {
    opt = opt || {}; const W = 1000, H = opt.h || 220, pad = 60, padB = 24;
    const vals = series.map(d => d.value), maxV = Math.max(...vals, 0), minV = Math.min(...vals, 0), range = (maxV - minV) || 1;
    const y = v => (H - padB) - (H - padB - 18) * ((v - minV) / range), zeroY = y(0);
    const n = series.length, bw = (W - pad - 12) / n * 0.5, gap = (W - pad - 12) / n;
    let grid = ""; [maxV, minV].forEach(v => { const yy = y(v);
      grid += `<line x1="${pad}" y1="${yy}" x2="${W - 12}" y2="${yy}" class="grid"/><text x="${pad - 6}" y="${yy + 4}" class="yl" text-anchor="end">${wonK(v)}</text>`; });
    grid += `<line x1="${pad}" y1="${zeroY}" x2="${W - 12}" y2="${zeroY}" class="zero"/>`;
    let bars = ""; series.forEach((d, i) => { const bx = pad + gap * i + (gap - bw) / 2, vy = y(d.value), top = Math.min(vy, zeroY), h = Math.abs(vy - zeroY), col = d.value >= 0 ? "#35c46b" : "#ff5d6c";
      bars += `<rect x="${bx}" y="${top}" width="${bw}" height="${h}" rx="3" fill="${col}"/>` +
        `<text x="${bx + bw / 2}" y="${d.value >= 0 ? top - 6 : top + h + 15}" class="bl" text-anchor="middle" fill="${col}">${opt.lab ? opt.lab(d.value) : wonK(d.value)}</text>` +
        `<text x="${bx + bw / 2}" y="${H - 6}" class="xl" text-anchor="middle">${d.label}</text>`; });
    return `<svg viewBox="0 0 ${W} ${H}" class="chart">${grid}${bars}</svg>`;
  }

  // ---------- 시나리오 / 배당 정책 → 배당 · 주가 밴드 ----------
  function renderScenarioSection() {
    const SC = C.scenarios, DP = C.dividendPolicies, PB = C.priceBand;
    if (!SC || !has(SC.items) || !DP || !has(DP.items) || !PB || !has(PB.perSet)) {
      // 시나리오 데이터가 없으면 슬라이더(고급 수동)만 펼쳐 보인다.
      ["scnDriver", "scnH", "scnTabs", "scnDetail", "polH", "polTabs", "polDetail", "combo", "scnTriggers", "bandH", "priceBandTbl"].forEach(hide);
      const adv = el("adv"); if (adv) adv.open = true;
      return;
    }
    const EL = SC.eligibleShares || C.market.sharesEligible.value, price = C.market.price.value;
    const state2 = { scn: SC.defaultKey || SC.items[0].key, pol: DP.defaultKey || DP.items[0].key };
    setText("scnSub", SC.subtitle); setText("scnNote", SC.note); setText("scnH", SC.title); setText("polH", DP.title);
    el("scnDriver").innerHTML = SC.driver ? `<b>실적 동인.</b> ${SC.driver}${srcSup(SC.src)}` : "";
    el("scnTabs").innerHTML = SC.items.map(s => `<button class="segbtn" data-scn="${s.key}">${s.key}<span class="seglab">순익 ${eok(s.ni)}</span></button>`).join("");
    el("polTabs").innerHTML = DP.items.map(p => `<button class="segbtn" data-pol="${p.key}">${p.label} <span class="stars">${"★".repeat(p.stars || 0)}</span></button>`).join("");
    el("scnTriggers").innerHTML =
      (has(DP.upTriggers) ? `<div class="trig up"><b>상방 트리거</b> · ${DP.upTriggers.join(" · ")}</div>` : "") +
      (has(DP.downTriggers) ? `<div class="trig down"><b>하방 트리거</b> · ${DP.downTriggers.join(" · ")}</div>` : "");
    const pMin = PB.perSet[0], pMax = PB.perSet[PB.perSet.length - 1];

    const paint = () => {
      const s = SC.items.find(x => x.key === state2.scn), p = DP.items.find(x => x.key === state2.pol);
      document.querySelectorAll("[data-scn]").forEach(b => b.classList.toggle("on", b.dataset.scn === state2.scn));
      document.querySelectorAll("[data-pol]").forEach(b => b.classList.toggle("on", b.dataset.pol === state2.pol));
      el("scnDetail").innerHTML =
        `<div class="sdtop">순이익 <b>${eok(s.ni)}</b> · EPS <b>${won(s.eps)}</b></div>` +
        (s.h2 ? `<div class="sdh2"><span class="lbl">남은 기간 가정</span> ${s.h2}</div>` : "") + (s.why ? `<p class="why">${s.why}</p>` : "");
      let dpsLow, dpsHigh, polExtra = "";
      if (p.scaled) { dpsLow = perShareWon(s.ni * p.payoutLow, EL); dpsHigh = perShareWon(s.ni * p.payoutHigh, EL);
        polExtra = ` <span class="sub">(성향 ${(p.payoutLow * 100)}~${(p.payoutHigh * 100)}% × ${s.key} 순익)</span>`; }
      else { dpsLow = p.dpsLow; dpsHigh = p.dpsHigh; }
      const yL = price ? dpsLow / price * 100 : 0, yH = price ? dpsHigh / price * 100 : 0;
      const pbL = s.eps * pMin, pbH = s.eps * pMax;
      el("polDetail").innerHTML = p.why ? `<p class="why">${p.why}</p>` : "";
      const cen = DP.central;
      const cenBox = cen ? `<div class="cobox cen"><div class="colab">${cen.label || "중심 추정"}</div><div class="coval">${won(cen.low)} ~ ${won(cen.high)}</div>` +
        (cen.baseDps ? `<div class="cosub">${cen.baseLabel || "직전"} ${won(cen.baseDps)} 대비 ${((cen.low / cen.baseDps - 1) * 100).toFixed(0)}~${((cen.high / cen.baseDps - 1) * 100).toFixed(0)}%</div>` : "") + `</div>` : "";
      el("combo").innerHTML =
        `<div class="cobox hot"><div class="colab">${DP.label || "예상 주당배당"} · 정책 ${p.key}${polExtra}</div><div class="coval">${won(dpsLow)} ~ ${won(dpsHigh)}</div><div class="cosub">시가배당률 ${yL.toFixed(1)}~${yH.toFixed(1)}% · 총액 ${eok(dpsLow * EL / 1e8)}~${eok(dpsHigh * EL / 1e8)}</div></div>` +
        `<div class="cobox"><div class="colab">예상 주가밴드 · ${s.key} EPS × PER ${pMin}~${pMax}배</div><div class="coval">${wonK(pbL)} ~ ${wonK(pbH)}원</div><div class="cosub">현재가 대비 ${price ? ((pbL - price) / price * 100).toFixed(0) : "—"}% ~ ${price ? ((pbH - price) / price * 100).toFixed(0) : "—"}%</div></div>` + cenBox;
      el("priceBandTbl").innerHTML =
        `<table class="pbtbl"><thead><tr><th>시나리오</th><th class="num">EPS</th>${PB.perSet.map(x => `<th class="num">PER ${x}배</th>`).join("")}</tr></thead><tbody>` +
        SC.items.map(x => `<tr class="${x.key === state2.scn ? "act" : ""}"><td><b>${x.key}</b></td><td class="num">${wonK(x.eps)}</td>${PB.perSet.map(m => `<td class="num">${wonK(x.eps * m)}</td>`).join("")}</tr>`).join("") +
        `</tbody></table><p class="sub">${PB.note || ""}${srcSup(PB.src)}</p>`;
    };
    document.querySelectorAll("[data-scn]").forEach(b => b.addEventListener("click", () => { state2.scn = b.dataset.scn; paint(); }));
    document.querySelectorAll("[data-pol]").forEach(b => b.addEventListener("click", () => { state2.pol = b.dataset.pol; paint(); }));
    paint();
  }

  // ---------- 현금흐름 함정 (선택) ----------
  function renderCashflow() {
    const cf = C.cashflow, bs = C.balanceStress;
    if (!cf || !has(cf.years)) { hide("sec-cashflow"); return; }
    el("cfNote").innerHTML = `<b>⚠️ 이익 ≠ 배당.</b> ${cf.note || ""}${srcSup(cf.src)}`;
    el("cfChart").innerHTML = svgSignedBars(cf.years.map((y, i) => ({ label: y, value: cf.ocf[i] })), { h: 220, lab: v => wonK(v) });
    el("balStress").innerHTML = bs && has(bs.rows) ?
      `<table class="bstbl"><thead><tr><th>지표</th>${bs.cols.map(c => `<th class="num">${c}</th>`).join("")}<th>비고</th></tr></thead><tbody>` +
      bs.rows.map(r => `<tr><td>${r.k}</td>${r.v.map(x => `<td class="num">${x}</td>`).join("")}<td class="sub">${r.note || ""}</td></tr>`).join("") +
      `</tbody></table><p class="sub">${bs.footnote || ""}${srcSup(bs.src)}</p>` : "<p class='sub'>재무 스트레스 데이터 없음</p>";
  }

  // ---------- 추적 대시보드 (선택) ----------
  function renderTracking() {
    const t = C.trackIndicators;
    if (!t || !has(t.items)) { hide("sec-track"); return; }
    el("trackGrid").innerHTML = t.items.map((x, i) =>
      `<div class="tcard"><div class="tkn">${i + 1}. ${x.k}</div><div class="tnow">현재 <b>${x.now}</b></div><div class="twatch">관찰: ${x.watch}</div><div class="trole sub">${x.role || ""}</div></div>`).join("");
    const nx = t.next || (C.scenarios && C.scenarios.next);
    el("nextCat").innerHTML = nx ? `🎯 <b>다음 검증 시점</b> · ${nx.event} <span class="sub">(${nx.date})</span> — ${nx.watch}${srcSup(t.src)}` : "";
  }

  // ---------- calendar (월별 미니 달력, 선택) ----------
  const WD = ["일", "월", "화", "수", "목", "금", "토"];
  function renderCalendar() {
    const evs = C.events || [];
    if (!evs.length) { hide("sec-calendar"); return; }
    const byMonth = {};
    evs.forEach(e => { const k = e.date.slice(0, 7); (byMonth[k] = byMonth[k] || []).push(e); });
    const months = Object.keys(byMonth).sort();
    setText("calRange", `(${months[0].replace("-", ".")} ~ ${months[months.length - 1].replace("-", ".")})`);
    setText("calNote", C.eventsNote);
    el("calLegend").innerHTML = Object.entries(EVENT_COLOR).map(([n, c]) =>
      `<span class="lg"><span class="sw" style="background:${c}"></span>${n}</span>`).join("") + `<span class="lg"><span class="sw star">★</span>분기점</span>`;
    el("calendar").innerHTML = months.map(mk => {
      const [Y, M] = mk.split("-").map(Number);
      const first = new Date(Y, M - 1, 1).getDay(), dim = new Date(Y, M, 0).getDate();
      const evDays = {}; byMonth[mk].forEach(e => { const d = +e.date.slice(8, 10); (evDays[d] = evDays[d] || []).push(e); });
      let cells = "";
      for (let i = 0; i < first; i++) cells += `<div class="cell empty"></div>`;
      for (let d = 1; d <= dim; d++) {
        const list = evDays[d];
        if (list) { const e = list[0];
          cells += `<div class="cell ev ${e.star ? "star" : ""}" style="--ec:${evColor(e.company)}" title="${list.map(x => x.company + ": " + x.title).join(" / ")}">${d}<span class="dot"></span></div>`;
        } else cells += `<div class="cell">${d}</div>`;
      }
      const items = byMonth[mk].map(e => `<div class="elist"><span class="d" style="background:${evColor(e.company)}">${+e.date.slice(8, 10)}</span>
        <div><span class="tag">${e.company}</span> <b>${e.title}</b>${e.star ? " <span class='st'>★</span>" : ""}${srcSup(e.src)}<div class="evr">${e.relevance || ""}</div></div></div>`).join("");
      return `<div class="month"><h4>${Y}.${String(M).padStart(2, "0")}</h4>
        <div class="cal"><div class="wd">${WD.map(w => `<span>${w}</span>`).join("")}</div><div class="grid">${cells}</div></div>
        <div class="elists">${items}</div></div>`;
    }).join("");
  }

  // ---------- narrative / sources ----------
  function renderNarrative() {
    const n = C.narrative;
    el("narrative").innerHTML = `<p><b>논지.</b> ${n.thesis}</p>
      <p class="warn"><b>⚠️ 핵심 경계.</b> ${n.keyCaveat}</p>
      <p><b>관전 포인트.</b></p><ul>${(n.watchpoints || []).map(w => `<li>${w}</li>`).join("")}</ul>`;
  }
  function renderSources() {
    el("sources").innerHTML = SRC_ORDER.map(id => { const s = S[id];
      const link = s.url ? `<a href="${s.url}" target="_blank" rel="noopener">${s.url}</a>` : "<i>가정값 — 외부 출처 아님</i>";
      return `<li><b>[${fnNum(id)}]</b> ${s.title} <span class="sub">${s.date || ""}</span><br>${link}</li>`; }).join("");
    setText("srcNote", C.sourcesNote);
  }

  function refresh() { renderResults(compute(state)); }

  // ---------- theme (light/dark) ----------
  function initTheme() {
    let saved; try { saved = localStorage.getItem("eq-theme"); } catch (e) { /* 저장소 없음 */ }
    if (saved === "light") document.documentElement.classList.add("light");
    const btn = el("themeBtn");
    const sync = () => { btn.textContent = document.documentElement.classList.contains("light") ? "🌙 다크" : "☀ 라이트"; };
    sync();
    btn.addEventListener("click", () => {
      document.documentElement.classList.toggle("light");
      try { localStorage.setItem("eq-theme", document.documentElement.classList.contains("light") ? "light" : "dark"); } catch (e) { /* 저장소 없음 */ }
      sync();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    document.title = `${C.meta.name} (${C.meta.ticker}) 시나리오 분석`;
    el("title").textContent = `${C.meta.name} (${C.meta.ticker})`;
    el("subtitle").innerHTML = `${C.meta.sector} · <span class="sub">${C.meta.origin}</span>`;
    el("genstamp").textContent = "생성 " + C.meta.asOf;
    renderHero(); renderPriceChart(); initPxControls(); renderHistory(); renderProfile();
    renderScenarioSection(); renderCashflow(); renderTracking();
    renderSliders(); renderPresets(); renderCalendar(); renderNarrative(); renderSources();
    refresh();
    el("printBtn").addEventListener("click", () => window.print());
  });
})();
