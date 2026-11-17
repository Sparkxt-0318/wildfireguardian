// Smoke test, honesty checks and load-time measurement for the KCF 3D scene (planner/public/kcf-scene).
//
//   node research/kcf-replay/scene/tests/smoke.mjs [--out DIR] [--throttle 4] [--quick]
//
// 1. Serves planner/public under /wildfireguardian/ (like GitHub Pages) and opens /wildfireguardian/kcf-scene/.
// 2. Opens the same folder with file:// (the offline case).
// 3. In each view (region, place for all six bookmarks, check it, one minute later, drive) checks that the two labels
//    are visible, that every number in the panels sits in an element with data-src, and that there are no page errors.
// 4. Re-walks every witness road in the scene data with the page's own code and compares with the committed arrival.
// 5. Measures load time (scripts parsed, map load, first idle, ready) cold, with and without CPU/network throttling.
// Uses the Playwright that ships with this machine (require('playwright')); headless Chromium renders WebGL in software
// (SwiftShader), so its frame times are an upper bound for any laptop with a GPU.
import { createServer } from 'node:http';
import { readFileSync, existsSync, mkdirSync, writeFileSync, statSync } from 'node:fs';
import { join, resolve, extname, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../../..');
const pub = join(root, 'planner/public');
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const OUT = resolve(opt('--out', join(here, 'out')));
const THROTTLE = Number(opt('--throttle', '4'));
const QUICK = args.includes('--quick');
mkdirSync(OUT, { recursive: true });

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.pbf': 'application/x-protobuf', '.txt': 'text/plain', '.md': 'text/plain; charset=utf-8' };
function serve() {
  return new Promise((res) => {
    const srv = createServer((req, rsp) => {
      let u = decodeURIComponent(new URL(req.url, 'http://x').pathname);
      if (!u.startsWith('/wildfireguardian/')) { rsp.writeHead(404); return rsp.end(); }
      let p = join(pub, u.slice('/wildfireguardian/'.length));
      if (existsSync(p) && statSync(p).isDirectory()) p = join(p, 'index.html');
      if (!p.startsWith(pub) || !existsSync(p)) { rsp.writeHead(404); return rsp.end(); }
      rsp.writeHead(200, { 'content-type': TYPES[extname(p)] || 'application/octet-stream' });
      rsp.end(readFileSync(p));
    });
    srv.listen(0, '127.0.0.1', () => res(srv));
  });
}

const report = { started_utc: new Date().toISOString(), runs: [], checks: {}, errors: [] };
const IGNORE = /GL Driver Message|GPU stall|WebGL-|Automatic fallback to software WebGL|swiftshader/i;

async function open(browser, url, { throttle = 0, network = null, label }) {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message));
  page.on('console', (m) => { if ((m.type() === 'error' || m.type() === 'warning') && !IGNORE.test(m.text())) errs.push(m.type() + ': ' + m.text()); });
  page.on('request', (r) => { const u = r.url(); if (/^https?:/.test(u) && !u.startsWith('http://127.0.0.1')) errs.push('external request: ' + u); });
  const cdp = await ctx.newCDPSession(page);
  if (throttle) await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle });
  if (network) { await cdp.send('Network.enable'); await cdp.send('Network.emulateNetworkConditions', network); }
  const t0 = Date.now();
  await page.goto(url, { waitUntil: 'load', timeout: 300000 });
  const timings = await page.evaluate(() => window.KCF_APP.ready);
  const wall = Date.now() - t0;
  report.runs.push({ label, url: url.replace(root, '<repo>'), throttle, network, wall_ms: wall, timings });
  console.log(label, 'wall', wall, 'ms', JSON.stringify(timings));
  return { ctx, page, errs, cdp };
}

// every digit-bearing text in the info panels must sit in (or under) an element with data-src, or be UI chrome
async function provenance(page, view) {
  return page.evaluate((view) => {
    const roots = ['#summary', '#panel', '#hud'].map((s) => document.querySelector(s)).filter((e) => e && e.offsetParent);
    const bad = [];
    const CHROME = /^(\s*(edge \d+ of \d+|\d+ edges|key \d|[1-6]|of \d+ places|×|S|\?)\s*)$/;
    for (const r of roots) {
      const w = document.createTreeWalker(r, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = w.nextNode())) {
        const t = n.textContent.trim();
        if (!/\d/.test(t)) continue;
        const el = n.parentElement;
        if (el.closest('[data-src]')) continue;
        if (el.closest('kbd, .strip.head, .note, .meta, .muted, th, .sub, .rk')) continue; // labels, ids, help text
        if (el.closest('tr[data-k] td:first-child')) continue; // issue-hour labels (the 13 issue times, HOTSPOT_RULE.md)
        bad.push({ view, text: t.slice(0, 120), where: el.className || el.tagName });
      }
    }
    return bad;
  }, view);
}
async function labelsVisible(page) {
  return page.evaluate(() => {
    const vis = (sel) => { const e = document.querySelector(sel); if (!e) return false; const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && r.top >= 0 && r.bottom <= innerHeight; };
    return { test: vis('.badge.test') && /시험 데이터/.test(document.querySelector('.badge.test').textContent), recon: vis('.badge.recon') && /reconstruction from the 2025 record/.test(document.querySelector('.badge.recon').textContent), standin: vis('#standinBtn') };
  });
}

const browser = await chromium.launch({ args: ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] });
const srv = await serve();
const base = `http://127.0.0.1:${srv.address().port}/wildfireguardian/kcf-scene/`;
const fileUrl = pathToFileURL(join(pub, 'kcf-scene/index.html')).href;

try {
  // ---- full walk-through over http (the published-site case)
  const { ctx, page, errs } = await open(browser, base, { label: 'http cold' });
  const views = [];
  const shot = async (name) => { await page.evaluate(() => window.KCF_APP.idle()); await page.screenshot({ path: join(OUT, name + '.png') }); };
  const record = async (name) => {
    const lv = await labelsVisible(page);
    const prov = await provenance(page, name);
    views.push({ view: name, labels: lv, unsourced: prov });
  };
  await record('region-12:00'); await shot('1-region-1200');
  await page.evaluate(() => window.KCF_APP.setIssue(6));
  await record('region-18:00'); await shot('1-region-1800');
  const named = await page.evaluate(() => window.KCF.scene.named.map((n) => n.id));
  const checks = [];
  for (const [i, id] of named.entries()) {
    for (const k of (QUICK ? [6] : [4, 6, 8])) {
      await page.evaluate(([id, k]) => { window.KCF_APP.setIssue(k); window.KCF_APP.selectPlace(id); }, [id, k]);
      await record(`place-${i + 1}-k${k}`);
      const r = await page.evaluate(() => {
        const st = window.KCF_APP.state, k = Math.floor(st.s / 3600), rt = window.KCF.scene.routes[st.standin][st.place.id][k];
        if (!rt) return { none: true };
        const a = window.KCF_APP.check(0); const v1 = document.querySelector('#verdict').textContent;
        const b = window.KCF_APP.check(60); const v2 = document.querySelector('#verdict').textContent;
        return { ok0: a.ok, arr0: a.arrival, committed: rt.arr, ok60: b.ok, v1: v1.slice(0, 160), v2: v2.slice(0, 160) };
      });
      checks.push({ id, k, ...r });
      if (k === 6) { await page.evaluate(() => window.KCF_APP.check(0)); await record(`check-${i + 1}`); if (i === 2) await shot('2-place-check'); }
    }
  }
  // drive (level 3) at 18:00 for bookmark 3
  await page.evaluate((id) => { window.KCF_APP.setIssue(6); window.KCF_APP.selectPlace(id); }, named[2]);
  await page.evaluate(() => window.KCF_APP.drive({ manual: true }));
  for (const f of [0, 0.5, 1]) { await page.evaluate((f) => window.KCF_APP.driveSeek(f), f); await record(`drive-${f}`); await shot(`3-drive-${f}`); }
  await page.evaluate(() => window.KCF_APP.stopDrive());
  // horizon-capped rows (ORDINARY, NOT_CUT_WITHIN_H): one minute later, drive HUD
  await page.evaluate(() => { window.KCF_APP.setStandin('ORDINARY'); window.KCF_APP.setIssue(0); window.KCF_APP.selectPlace(window.KCF.scene.named[0].id); });
  report.checks.not_cut = await page.evaluate(() => {
    const st = window.KCF_APP.state, h = window.KCF.scene.hourly.ORDINARY[st.place.id][0];
    const a = window.KCF_APP.check(60); const v = document.querySelector('#verdict').textContent;
    return { state: h.state, ok60: a.ok, overH: !!a.overH, verdict: v.slice(0, 300), nan: /NaN|undefined/.test(v) };
  });
  await record('notcut-check60');
  await page.evaluate(() => window.KCF_APP.drive({ manual: true }));
  await page.evaluate(() => window.KCF_APP.driveSeek(0.5));
  report.checks.not_cut.hud = await page.evaluate(() => document.querySelector('#hud').textContent.slice(0, 400));
  await record('notcut-drive');
  await page.evaluate(() => { window.KCF_APP.stopDrive(); window.KCF_APP.setStandin('RUNNING'); });
  // every path the sources panel names must be a committed file in this repository
  const paths = new Set();
  for (const id of named.slice(0, 2)) {
    await page.evaluate((id) => { window.KCF_APP.setIssue(4); window.KCF_APP.selectPlace(id); window.KCF_APP.check(0); }, id);
    (await page.evaluate(() => window.KCF_APP.sources())).forEach((p) => paths.add(p));
  }
  report.checks.source_paths = [...paths].map((p) => ({ path: p, exists: existsSync(join(root, p)) }));
  report.checks.views = views;
  report.checks.named_checks = checks;
  report.checks.http_errors = errs.slice(0, 50);

  // ---- every witness road, re-walked by the page's own code
  report.checks.rewalk_all = await page.evaluate(() => {
    const S = window.KCF.scene, out = {};
    for (const sd of Object.keys(S.routes)) {
      const o = { routes: 0, pass: 0, same_arrival: 0, later_fail: 0, later_pass: 0, mismatches: [] };
      for (const pid of Object.keys(S.routes[sd])) S.routes[sd][pid].forEach((rt, k) => {
        if (!rt) return;
        o.routes++;
        const r = window.KCF_APP.rewalk(pid, k, rt.ld, sd);
        if (r.ok) o.pass++;
        if (r.ok && r.arrival === rt.arr) o.same_arrival++; else if (o.mismatches.length < 10) o.mismatches.push({ pid, k, ok: r.ok, arrival: r.arrival, arr: rt.arr });
        const l = window.KCF_APP.rewalk(pid, k, rt.ld + 60, sd); if (l.ok) o.later_pass++; else o.later_fail++;
      });
      out[sd] = o;
    }
    return out;
  });
  console.log('rewalk', JSON.stringify(report.checks.rewalk_all));
  await ctx.close();

  // ---- offline: file://
  {
    const { ctx, page, errs } = await open(browser, fileUrl, { label: 'file:// cold' });
    await page.evaluate((id) => { window.KCF_APP.setIssue(6); window.KCF_APP.selectPlace(id); }, named[2]);
    const r = await page.evaluate(() => { const a = window.KCF_APP.check(0); return { ok: a.ok, arrival: a.arrival }; });
    report.checks.file_url = { check: r, labels: await labelsVisible(page), errors: errs.slice(0, 30) };
    await page.screenshot({ path: join(OUT, 'file-url-place.png') });
    await ctx.close();
  }

  // ---- load time with throttling (a slow 2020 laptop on venue Wi-Fi)
  if (!QUICK) {
    const net = { offline: false, latency: 40, downloadThroughput: (20 * 1e6) / 8, uploadThroughput: (5 * 1e6) / 8 };
    for (const [label, o] of [
      ['file:// cold, full quality (?full), no throttling', { file: true, q: '?full' }],
      ['http cold, CPU x' + THROTTLE + ', 20 Mbit/s', { throttle: THROTTLE, network: net }],
      ['file:// cold, CPU x' + THROTTLE, { throttle: THROTTLE, file: true }]]) {
      const { ctx, page } = await open(browser, (o.file ? fileUrl : base) + (o.q || ''), { ...o, label });
      // interaction latency under throttling: issue-hour step and place selection
      const lat = await page.evaluate(async () => {
        const t = performance.now(); window.KCF_APP.setIssue(7); await window.KCF_APP.idle(); const a = performance.now() - t;
        const t2 = performance.now(); window.KCF_APP.selectPlace(window.KCF.scene.named[3].id); const b = performance.now() - t2;
        return { issue_step_to_idle_ms: Math.round(a), select_place_sync_ms: Math.round(b) };
      });
      report.runs[report.runs.length - 1].interaction = lat;
      console.log(label, JSON.stringify(lat));
      await ctx.close();
    }
  }
} catch (e) {
  report.errors.push(String(e && e.stack || e));
  console.error(e);
} finally {
  srv.close();
  await browser.close();
  report.finished_utc = new Date().toISOString();
  writeFileSync(join(OUT, 'results.json'), JSON.stringify(report, null, 1));
  const unsourced = (report.checks.views || []).flatMap((v) => v.unsourced);
  const labelFail = (report.checks.views || []).filter((v) => !(v.labels.test && v.labels.recon));
  console.log('views', (report.checks.views || []).length, 'unsourced numbers', unsourced.length, 'views missing a label', labelFail.length, 'errors', report.errors.length);
  if (unsourced.length) console.log(JSON.stringify(unsourced.slice(0, 20), null, 1));
}
