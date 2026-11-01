#!/usr/bin/env node
// check.mjs — open pages in headless Chrome and report only what is wrong.
// 언제: 앱 · 페이지를 고친 뒤 실제로 열어 눌러 봐도 오류가 없나 볼 때, 공개 배포 직전, 폰 폭 · PDF가 필요할 때
// kind: check
// status: active
//
//   node check.mjs <url> [options]
//   node check.mjs --dir <site folder> [--path index.html --path other.html ...] [options]
//
// Options
//   --dir DIR        serve DIR on 127.0.0.1 (free port) for the run and stop it afterwards
//   --path P         page under --dir to check (repeatable; default index.html)
//   --phone          390x844 mobile layout (device emulation, touch) + horizontal-overflow check
//   --size WxH       viewport (default 1280x900); --mobile to emulate a mobile device at that size
//   --wait JS        condition to wait for (default: document.readyState === "complete")
//   --timeout S      wait timeout in seconds (default 60)
//   --eval JS        expression to evaluate and print (repeatable; may return a promise)
//   --click X,Y      real click at viewport coordinates before the evals (repeatable)
//   --smoke          press every visible button --rounds times (default 3) with real clicks; fail on any error
//   --overflow       check horizontal overflow at any size (on by default with --phone; --no-overflow turns it off)
//   --shot FILE      screenshot (PNG) after the checks; --full for the whole page. With several pages: FILE-<n>.png
//   --pdf FILE       print the page to PDF (Page.printToPDF). With several pages: FILE-<n>.pdf
//   --ignore-net     do not fail on failed requests / HTTP >= 400 (still reported)
//
// Prints one JSON report. Exit 0 = nothing wrong, 1 = a check failed (console error, page exception, failed
// request, overflow, smoke error, wait timeout, eval threw), 2 = usage error or no Chrome.
import { launch, serveStatic, smokeButtons, CHROME } from './cdp.mjs';
import { existsSync } from 'node:fs';

const args = process.argv.slice(2);
const FLAGS = new Set(['--phone', '--mobile', '--smoke', '--overflow', '--no-overflow', '--full', '--ignore-net']);
const all = (name) => args.flatMap((a, i) => (a === name ? [args[i + 1]] : []));
const one = (name, d) => { const v = all(name); return v.length ? v[v.length - 1] : d; };
const has = (name) => args.includes(name);
const positional = args.filter((a, i) => !a.startsWith('--') && (i === 0 || !args[i - 1].startsWith('--') || FLAGS.has(args[i - 1])));

function usage(msg) {
  if (msg) console.error('check: ' + msg);
  console.error('usage: node check.mjs <url> | --dir DIR [--path P]... [--phone|--size WxH] [--smoke] [--wait JS] [--eval JS]... [--shot F] [--pdf F]');
  process.exit(2);
}

const dir = one('--dir', null);
const url = positional[0];
if (!dir && !url) usage('give a url or --dir');
if (dir && !existsSync(dir)) usage('no such folder: ' + dir);
if (!CHROME) { console.error('check: Chrome/Edge not found (set CHROME_PATH)'); process.exit(2); }

const phone = has('--phone');
const size = phone ? '390x844' : one('--size', '1280x900');
const mobile = phone || has('--mobile');
const checkOverflow = (phone || has('--overflow')) && !has('--no-overflow');
const paths = all('--path').length ? all('--path') : ['index.html'];
const numbered = (file, i, n) => (n === 1 ? file : file.replace(/(\.[a-z0-9]+)?$/i, (ext) => `-${i + 1}${ext || ''}`));

let srv = null, browser = null, code = 0;
const report = { size, mobile, pages: [] };
try {
  if (dir) { srv = await serveStatic(dir); report.served = dir; }
  const targets = srv ? paths.map((p) => srv.url + p.replace(/^\/+/, '')) : [url];
  browser = await launch();
  for (const [i, target] of targets.entries()) {
    const r = { url: target, problems: [] };
    const page = await browser.newPage({ size, mobile, dpr: mobile ? 2 : 1 });
    try {
      await page.navigate(target);
      r.wait = await page.waitFor(one('--wait', 'document.readyState === "complete"'), +one('--timeout', '60'));
      for (const c of all('--click')) { const [x, y] = c.split(',').map(Number); await page.click(x, y); }
      r.evals = [];
      for (const e of all('--eval')) {
        try { r.evals.push(await page.eval(e)); } catch (err) { r.evals.push(null); r.problems.push('eval threw: ' + err.message); }
      }
      if (has('--smoke')) {
        r.smoke = await smokeButtons(page, { rounds: +one('--rounds', '3') });
        if (r.smoke.errors.length) r.problems.push(`smoke: ${r.smoke.errors.length} error(s) after ${r.smoke.clicks} clicks`);
      }
      if (checkOverflow) {
        r.overflow = await page.overflow();
        if (r.overflow.offenders.length) r.problems.push(`horizontal overflow: page ${r.overflow.scrollW}px > viewport ${r.overflow.clientW}px`);
      }
      if (one('--shot', null)) r.shot = await page.screenshot(numbered(one('--shot'), i, targets.length), { fullPage: has('--full') });
      if (one('--pdf', null)) r.pdf = await page.pdf(numbered(one('--pdf'), i, targets.length));
    } catch (err) {
      r.problems.push(err.message);
    }
    r.console_errors = page.consoleErrors();
    r.net_failures = page.netFailures();
    if (r.console_errors.length) r.problems.push(`${r.console_errors.length} console error(s)`);
    if (r.net_failures.length && !has('--ignore-net')) r.problems.push(`${r.net_failures.length} failed request(s)`);
    await page.close();
    if (r.problems.length) code = 1;
    report.pages.push(r);
  }
} catch (err) {
  report.error = err.message;
  code = 1;
} finally {
  if (browser) await browser.close();
  if (srv) await srv.close();
}
report.ok = code === 0;
console.log(JSON.stringify(report, null, 1));
process.exit(code);
