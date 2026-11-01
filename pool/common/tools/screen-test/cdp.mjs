// cdp.mjs — headless Chrome driver over the DevTools Protocol. No packages (Node 22+: built-in WebSocket, fetch).
// 언제: 앱마다의 화면 시험 script가 import해 실제 입력 · 캡처 · PDF · 콘솔 오류 수집을 할 때 (명령줄은 check.mjs)
// kind: library
// status: active
//
//   import { launch, serveStatic } from './cdp.mjs';
//   const srv = await serveStatic('path/to/site');            // optional: local static server, port picked by the OS
//   const browser = await launch();
//   const page = await browser.newPage({ size: '390x844', mobile: true });   // phone layout, isolated context
//   await page.navigate(srv.url + 'index.html');
//   await page.waitFor('document.readyState === "complete"');
//   await page.click(100, 200);  await page.key('Enter');      // real input events
//   await page.screenshot('shot.png');  await page.pdf('out.pdf');
//   console.log(page.consoleErrors(), page.netFailures());
//   await browser.close();  await srv.close();
//
// Rules learned the hard way (kept from an earlier project):
// - Use real time. `chrome --screenshot --virtual-time-budget` also freezes performance.now().
// - Chrome's --window-size cannot go below ~500 px on Windows; a "390 px" window is laid out at 500 and cropped,
//   which looks like a horizontal-overflow bug but is not one. Device-metrics emulation (newPage) is the only
//   way to get a genuine phone-width layout viewport.
// - Every launch gets its own temporary profile, removed on close. Every newPage gets its own browser context.
// - Page actions are real input events (Input.dispatchMouseEvent / KeyEvent / insertText, DOM.setFileInputFiles).
//   eval() is for reading state.
// - alert / confirm / prompt dialogs are accepted automatically; otherwise the page would hang.
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtempSync, rmSync, existsSync, writeFileSync, statSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, extname, sep } from 'node:path';

const LOCAL = process.env.LOCALAPPDATA || '';
export const CHROME = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  LOCAL && join(LOCAL, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
].find((p) => p && existsSync(p));

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- static server
const MIME = {
  '.html': 'text/html; charset=utf-8', '.htm': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp',
  '.ico': 'image/x-icon', '.mp3': 'audio/mpeg', '.mp4': 'video/mp4', '.webm': 'video/webm', '.wav': 'audio/wav',
  '.woff2': 'font/woff2', '.woff': 'font/woff', '.pdf': 'application/pdf', '.wasm': 'application/wasm',
  '.webmanifest': 'application/manifest+json', '.vtt': 'text/vtt; charset=utf-8',
};

// Serves `dir` on 127.0.0.1. port 0 = any free port. Returns { url, port, close() }. No caching, no listing.
export async function serveStatic(dir, { port = 0 } = {}) {
  const root = resolve(dir);
  const srv = createServer(async (req, res) => {
    let rel;
    try { rel = decodeURIComponent(req.url.split('?')[0].split('#')[0]); } catch { res.writeHead(400).end(); return; }
    let file = resolve(join(root, rel));
    if (file !== root && !file.startsWith(root + sep)) { res.writeHead(403).end(); return; }
    try {
      if (statSync(file).isDirectory()) file = join(file, 'index.html');
      const body = await readFile(file);
      res.writeHead(200, { 'Content-Type': MIME[extname(file).toLowerCase()] || 'application/octet-stream', 'Cache-Control': 'no-store' });
      res.end(body);
    } catch { res.writeHead(404, { 'Content-Type': 'text/plain' }).end('not found'); }
  });
  await new Promise((r) => srv.listen(port, '127.0.0.1', r));
  const p = srv.address().port;
  return { url: `http://127.0.0.1:${p}/`, port: p, close: () => new Promise((r) => srv.close(() => r())) };
}

// ---------------------------------------------------------------- protocol
function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const waiting = new Map();
  const events = [];
  const handlers = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && waiting.has(msg.id)) { waiting.get(msg.id)(msg); waiting.delete(msg.id); } else if (msg.method) {
      events.push(msg);
      for (const fn of handlers.get(msg.method) || []) fn(msg.params);
    }
  };
  const ready = new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  const send = (method, params = {}) => new Promise((res) => {
    if (ws.readyState !== 1) { res({ error: { message: 'connection closed' } }); return; }
    const i = ++id; waiting.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
  });
  const on = (method, fn) => { if (!handlers.has(method)) handlers.set(method, []); handlers.get(method).push(fn); };
  return { ready, send, on, events, close: () => ws.close() };
}

const SPECIAL_KEYS = {
  Enter: ['Enter', 13, '\r'], Escape: ['Escape', 27], Tab: ['Tab', 9], Backspace: ['Backspace', 8], Delete: ['Delete', 46],
  ArrowLeft: ['ArrowLeft', 37], ArrowUp: ['ArrowUp', 38], ArrowRight: ['ArrowRight', 39], ArrowDown: ['ArrowDown', 40],
  Home: ['Home', 36], End: ['End', 35], PageUp: ['PageUp', 33], PageDown: ['PageDown', 34],
};
const PUNCT = {
  ' ': ['Space', 32, false], ',': ['Comma', 188, false], '.': ['Period', 190, false], '-': ['Minus', 189, false],
  '_': ['Minus', 189, true], '=': ['Equal', 187, false], '+': ['Equal', 187, true], '/': ['Slash', 191, false],
  '?': ['Slash', 191, true], ';': ['Semicolon', 186, false], ':': ['Semicolon', 186, true],
};
const MODIFIERS = { alt: 1, ctrl: 2, meta: 4, shift: 8 };

function keyInfo(key) {
  if (SPECIAL_KEYS[key]) { const [code, vk, text] = SPECIAL_KEYS[key]; return { key, code, vk, text, shift: false }; }
  if (key.length !== 1) throw new Error(`cdp: unknown key ${JSON.stringify(key)}`);
  if (/[a-z]/.test(key)) return { key, code: 'Key' + key.toUpperCase(), vk: key.toUpperCase().charCodeAt(0), text: key, shift: false };
  if (/[A-Z]/.test(key)) return { key, code: 'Key' + key, vk: key.charCodeAt(0), text: key, shift: true };
  if (/[0-9]/.test(key)) return { key, code: 'Digit' + key, vk: key.charCodeAt(0), text: key, shift: false };
  if (PUNCT[key]) { const [code, vk, shift] = PUNCT[key]; return { key, code, vk, text: key, shift }; }
  return { key, code: '', vk: 0, text: key, shift: false };
}

// ---------------------------------------------------------------- page
function makePage(c, extra = {}) {
  let mark = 0;
  let mouse = { x: 0, y: 0 };
  const mods = (o) => Object.entries(MODIFIERS).reduce((m, [k, v]) => m | ((o && o[k]) ? v : 0), 0);
  const page = {
    async eval(expression) {
      const r = await c.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
      if (r.result && r.result.exceptionDetails) {
        const d = r.result.exceptionDetails;
        throw new Error('page exception: ' + ((d.exception && d.exception.description) || d.text));
      }
      return r.result && r.result.result ? r.result.result.value : undefined;
    },
    async waitFor(expression, seconds = 60) {
      const t0 = Date.now();
      while (Date.now() - t0 < seconds * 1000) {
        let v;
        try { v = await page.eval(expression); } catch { v = undefined; }
        if (v) return v;
        await sleep(200);
      }
      let info = '';
      try { info = await page.eval('JSON.stringify({url: location.href, title: document.title})'); } catch { /* page gone */ }
      throw new Error(`timed out waiting for ${expression}; page: ${info}`);
    },
    async click(x, y, opts = {}) {
      const clickCount = opts.clickCount || 1;
      for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased'])
        await c.send('Input.dispatchMouseEvent', { type, x, y, button: type === 'mouseMoved' ? 'none' : 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount, modifiers: mods(opts) });
      mouse = { x, y };
    },
    // click the centre of the first element matching `selector` (scrolled into view first)
    async clickSelector(selector) {
      const r = await page.eval(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null;
        e.scrollIntoView({block: 'center', inline: 'center'}); const b = e.getBoundingClientRect();
        return {x: b.left + b.width / 2, y: b.top + b.height / 2}; })()`);
      if (!r) throw new Error(`cdp: no element ${selector}`);
      await page.click(r.x, r.y);
    },
    async mouseMove(x, y, opts = {}) {
      const steps = Math.max(1, opts.steps || 1), held = !!opts.held;
      const x0 = mouse.x, y0 = mouse.y;
      for (let i = 1; i <= steps; i++) {
        const px = x0 + (x - x0) * i / steps, py = y0 + (y - y0) * i / steps;
        await c.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: px, y: py, button: held ? 'left' : 'none', buttons: held ? 1 : 0 });
      }
      mouse = { x, y };
    },
    async drag(x0, y0, x1, y1, steps = 8) {
      await page.mouseMove(x0, y0);
      await c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: x0, y: y0, button: 'left', buttons: 1, clickCount: 1 });
      await page.mouseMove(x1, y1, { steps, held: true });
      await c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: x1, y: y1, button: 'left', buttons: 0, clickCount: 1 });
    },
    async wheel(x, y, deltaY, deltaX = 0) {
      await page.mouseMove(x, y);
      await c.send('Input.dispatchMouseEvent', { type: 'mouseWheel', x, y, deltaX, deltaY, button: 'none', buttons: 0 });
    },
    async key(name, opts = {}) {
      const k = keyInfo(name);
      const modifiers = mods({ ...opts, shift: opts.shift || k.shift });
      const base = { key: k.key, code: k.code, windowsVirtualKeyCode: k.vk, nativeVirtualKeyCode: k.vk, modifiers };
      const printable = k.text !== undefined && !(modifiers & (MODIFIERS.ctrl | MODIFIERS.alt | MODIFIERS.meta));
      await c.send('Input.dispatchKeyEvent', printable ? { type: 'keyDown', ...base, text: k.text, unmodifiedText: k.text } : { type: 'rawKeyDown', ...base });
      await c.send('Input.dispatchKeyEvent', { type: 'keyUp', ...base });
    },
    async type(text) { for (const ch of text) await page.key(ch); },
    async insertText(text) { await c.send('Input.insertText', { text }); },
    async setFiles(selector, files) {
      const doc = await c.send('DOM.getDocument', { depth: 0 });
      const q = await c.send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector });
      if (!q.result || !q.result.nodeId) throw new Error(`cdp: no element ${selector}`);
      const r = await c.send('DOM.setFileInputFiles', { nodeId: q.result.nodeId, files });
      if (r.error) throw new Error(`DOM.setFileInputFiles: ${r.error.message}`);
    },
    async navigate(url) { mouse = { x: 0, y: 0 }; const r = await c.send('Page.navigate', { url }); if (r.error) throw new Error(r.error.message); },
    async reload() { await c.send('Page.reload', { ignoreCache: false }); },
    async screenshot(path, { fullPage = false } = {}) {
      const params = { format: 'png' };
      if (fullPage) {
        const m = await c.send('Page.getLayoutMetrics');
        const s = m.result.cssContentSize || m.result.contentSize;
        params.captureBeyondViewport = true;
        params.clip = { x: 0, y: 0, width: Math.ceil(s.width), height: Math.ceil(s.height), scale: 1 };
      }
      const r = await c.send('Page.captureScreenshot', params);
      writeFileSync(path, Buffer.from(r.result.data, 'base64'));
      return path;
    },
    // PDF of the current page (headless only). Defaults: backgrounds printed, CSS @page size honoured, no header/footer.
    async pdf(path, opts = {}) {
      const r = await c.send('Page.printToPDF', { printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false, ...opts });
      if (r.error) throw new Error('Page.printToPDF: ' + r.error.message);
      writeFileSync(path, Buffer.from(r.result.data, 'base64'));
      return path;
    },
    consoleErrors() {
      return c.events.slice(mark).filter((e) => e.method === 'Runtime.exceptionThrown'
        || (e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error'))
        .map((e) => e.method === 'Runtime.exceptionThrown'
          ? (e.params.exceptionDetails.exception || {}).description || e.params.exceptionDetails.text
          : e.params.args.map((a) => a.value ?? a.description).join(' '));
    },
    clearConsole() { mark = c.events.length; },
    // requests that failed or answered with status >= 400 (favicon.ico is ignored)
    netFailures() {
      const url = new Map();
      const out = [];
      for (const e of c.events) {
        if (e.method === 'Network.requestWillBeSent') url.set(e.params.requestId, e.params.request.url);
        else if (e.method === 'Network.loadingFailed' && !e.params.canceled) out.push(`failed ${url.get(e.params.requestId) || '?'} ${e.params.errorText}`);
        else if (e.method === 'Network.responseReceived' && e.params.response.status >= 400 && !/\/favicon\.ico$/.test(e.params.response.url))
          out.push(`status ${e.params.response.status} ${e.params.response.url}`);
      }
      return out;
    },
    // elements that make the PAGE scroll sideways (things inside their own scroll box are by design)
    async overflow() {
      return page.eval(`(() => {
        const de = document.documentElement, lim = de.clientWidth + 1, over = [];
        if (de.scrollWidth > de.clientWidth) {
          document.querySelectorAll('body *').forEach((el) => {
            const r = el.getBoundingClientRect();
            if (r.right <= lim || r.width === 0 || r.height === 0) return;
            for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
              const ov = getComputedStyle(a).overflowX;
              if (ov === 'auto' || ov === 'scroll' || ov === 'hidden') return;
            }
            over.push(Math.round(r.right) + 'px ' + el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
              (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : ''));
          });
        }
        return { clientW: de.clientWidth, scrollW: de.scrollWidth, offenders: over.slice(0, 15) };
      })()`);
    },
    send(method, params = {}) { return c.send(method, params); },
    ...extra,
  };
  return page;
}

// ---------------------------------------------------------------- browser
// One headless Chrome, many isolated pages. Each newPage() has its own browser context and a fixed
// viewport by device-metrics emulation. opts: { flags: [], port }.
export async function launch(opts = {}) {
  if (!CHROME) throw new Error('Chrome/Edge not found (set CHROME_PATH)');
  const port = opts.port || (9300 + Math.floor(Math.random() * 600));
  const prof = mkdtempSync(join(tmpdir(), 'screen-test-'));
  const chrome = spawn(CHROME, ['--headless=new', ...(process.env.CDP_GPU === '1' ? [] : ['--disable-gpu']), '--hide-scrollbars', `--remote-debugging-port=${port}`,
    `--user-data-dir=${prof}`, '--window-size=1500,950', '--no-first-run', '--no-default-browser-check',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
    '--disable-extensions', '--disable-sync', '--disable-component-update', '--force-color-profile=srgb', '--font-render-hinting=none',
    '--run-all-compositor-stages-before-draw', '--num-raster-threads=1', '--disable-partial-raster',
    ...(opts.flags || []), 'about:blank'], { stdio: 'ignore' });
  let browserWs = null;
  for (let i = 0; i < 150 && !browserWs; i++) {
    try { browserWs = (await (await fetch(`http://127.0.0.1:${port}/json/version`)).json()).webSocketDebuggerUrl; } catch { await sleep(100); }
  }
  if (!browserWs) { chrome.kill(); try { rmSync(prof, { recursive: true, force: true }); } catch { /* locked */ } throw new Error('Chrome DevTools endpoint did not come up'); }
  const b = connect(browserWs);
  await b.ready;
  const open = new Set();
  return {
    port,
    // o: { size: 'WxH', mobile: bool, dpr: number, reducedMotion: bool (default true) }
    async newPage(o = {}) {
      const [w, h] = (o.size || '1500x950').split('x').map(Number);
      const ctxId = (await b.send('Target.createBrowserContext', {})).result.browserContextId;
      const targetId = (await b.send('Target.createTarget', { url: 'about:blank', browserContextId: ctxId, width: w, height: h })).result.targetId;
      const c = connect(`ws://127.0.0.1:${port}/devtools/page/${targetId}`);
      await c.ready;
      await c.send('Page.enable');
      await c.send('Runtime.enable');
      await c.send('DOM.enable');
      await c.send('Network.enable', { maxTotalBufferSize: 0, maxResourceBufferSize: 0 });
      await c.send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: o.dpr || 1, mobile: !!o.mobile });
      if (o.mobile) await c.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
      if (o.reducedMotion !== false) await c.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
      c.on('Page.javascriptDialogOpening', () => { c.send('Page.handleJavaScriptDialog', { accept: true }); });
      await c.send('Page.bringToFront');
      let closed = false;
      const page = makePage(c, {
        size: { w, h },
        async close() {
          if (closed) return;
          closed = true; open.delete(page);
          c.close();
          await b.send('Target.closeTarget', { targetId });
          await b.send('Target.disposeBrowserContext', { browserContextId: ctxId });
        },
      });
      open.add(page);
      return page;
    },
    async close() {
      for (const p of [...open]) { try { await p.close(); } catch { /* already gone */ } }
      await Promise.race([b.send('Browser.close'), sleep(1500)]);
      b.close();
      await sleep(300);
      chrome.kill();
      await sleep(200);
      try { rmSync(prof, { recursive: true, force: true }); } catch { /* profile still locked */ }
    },
  };
}

// Convenience: one page, closed afterwards. opts = newPage options.
export async function withPage(url, opts, fn) {
  const browser = await launch();
  try {
    const page = await browser.newPage(opts || {});
    await page.navigate(url);
    return await fn(page);
  } finally {
    await browser.close();
  }
}

// ---------------------------------------------------------------- generic smoke
// Press every visible, enabled button (and [role=button]) `rounds` times with real clicks and report only errors.
// Several rounds because many apps lock after one answer and take a different branch after "next".
// Empty text/number inputs get "1" first so that "check" buttons do not just return early; range sliders are
// pushed to min and max. A click that navigates away is undone (navigate back) and counted.
export async function smokeButtons(page, { rounds = 3, settleMs = 60, selector = 'button, [role="button"], input[type="button"], input[type="submit"]' } = {}) {
  const start = await page.eval('location.href.split("#")[0]');
  const before = page.consoleErrors().length;
  const n = await page.eval(`(() => {
    document.querySelectorAll('input:not([type]), input[type="text"], input[type="number"], input[inputmode]').forEach((i) => {
      if (!i.value && !i.disabled && !i.readOnly) { i.value = '1'; i.dispatchEvent(new Event('input', {bubbles: true})); }
    });
    document.querySelectorAll('input[type="range"]').forEach((r) => {
      for (const v of [r.min || 0, r.max || 100]) { r.value = v; r.dispatchEvent(new Event('input', {bubbles: true})); }
    });
    document.querySelectorAll('form').forEach((f) => f.addEventListener('submit', (e) => e.preventDefault()));
    let k = 0;
    document.querySelectorAll(${JSON.stringify(selector)}).forEach((b) => { b.setAttribute('data-smoke-id', String(k++)); });
    return k;
  })()`);
  let clicks = 0, navigations = 0, skipped = 0;
  for (let round = 0; round < rounds; round++) {
    for (let i = 0; i < n; i++) {
      const pt = await page.eval(`(() => { const e = document.querySelector('[data-smoke-id="${i}"]');
        if (!e || e.disabled || e.closest('[hidden], [inert]')) return null;
        const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none' || cs.pointerEvents === 'none') return null;
        e.scrollIntoView({block: 'center', inline: 'center'}); const b = e.getBoundingClientRect();
        if (b.width === 0 || b.height === 0) return null;
        const x = b.left + b.width / 2, y = b.top + b.height / 2, top = document.elementFromPoint(x, y);
        if (!top || !(top === e || e.contains(top) || top.contains(e))) return null;
        return {x, y}; })()`).catch(() => null);
      if (!pt) { skipped++; continue; }
      await page.click(pt.x, pt.y);
      clicks++;
      await sleep(settleMs);
      const now = await page.eval('location.href.split("#")[0]').catch(() => '');
      if (now !== start) {
        navigations++;
        await page.navigate(start);
        await page.waitFor('document.readyState === "complete"', 30).catch(() => {});
        await page.eval(`document.querySelectorAll(${JSON.stringify(selector)}).forEach((b, k) => b.setAttribute('data-smoke-id', String(k)))`).catch(() => {});
      }
    }
  }
  return { buttons: n, rounds, clicks, skipped, navigations, errors: page.consoleErrors().slice(before) };
}
