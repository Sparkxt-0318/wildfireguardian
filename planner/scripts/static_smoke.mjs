#!/usr/bin/env node
/**
 * Smoke test of the public static demo in headless Chromium. By default it serves planner/dist
 * itself, the way GitHub Pages does (scripts/serve_static.mjs: dist/ only under the base path,
 * 404 without a single-page-app fallback, HTTP Range for the PMTiles basemaps) — so what is tested
 * is exactly the folder that gets published.
 *
 *   VITE_BASE_PATH=/wildfireguardian/ npm run build:static     # once
 *   npm run smoke:static                                        # dist-only server (default)
 *   node scripts/static_smoke.mjs --server vite                 # `vite preview --mode static` instead
 *   node scripts/static_smoke.mjs --url http://127.0.0.1:4173/wildfireguardian/   # an already running server
 *     [--base /wildfireguardian/] [--port 4179] [--out docs/screenshots/solve-demo] [--no-screenshots]
 *
 * Desktop 1440×900 and phone 375×812, Korean and English: load → judge intro (keyboard: focus
 * trap, Escape, focus back to the opener) → 3-step tour (step 2 picks the first origin with a
 * checked route) → its 출발 마감 / leave-by time, evidence and the recorded forecast cells →
 * A4 plan sheet with its DEMO marker → English. Every request is recorded and must stay on the
 * page's origin under the base path (no 127.0.0.1:8765, no localhost API, no internet); the page's
 * Content-Security-Policy must refuse a deliberate cross-origin probe; the honesty texts
 * (fire-input banner, planning-aid footer, three verdicts as colour + icon + text) must be visible.
 * Screenshots go to docs/screenshots/solve-demo/.
 *
 * Playwright: the `playwright` package reachable by require() (e.g. a global install on NODE_PATH)
 * or PLAYWRIGHT_MODULE=/path/to/node_modules/playwright. This script never installs browsers.
 * Exit code 1 on any failed check.
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { startStaticServer } from './serve_static.mjs';

const PLANNER = resolve(fileURLToPath(new URL('..', import.meta.url)));

function parseArgs(argv) {
  const out = { base: process.env.VITE_BASE_PATH || '/wildfireguardian/', out: join(PLANNER, 'docs', 'screenshots', 'solve-demo'), port: '4179', screenshots: true, url: '', server: 'dist' };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--no-screenshots') out.screenshots = false;
    else if (a.startsWith('--')) {
      out[a.slice(2)] = argv[i + 1];
      i += 1;
    }
  }
  out.base = `/${String(out.base).replace(/^\/+|\/+$/g, '')}/`.replace('//', '/');
  return out;
}
const opts = parseArgs(process.argv.slice(2));

function loadChromium() {
  const tried = [];
  const req = createRequire(join(PLANNER, 'package.json'));
  const candidates = [process.env.PLAYWRIGHT_MODULE, 'playwright', 'playwright-core'].filter(Boolean);
  for (const c of candidates) {
    try {
      const mod = req(c);
      const chromium = mod?.chromium ?? mod?.default?.chromium;
      if (chromium) return chromium;
    } catch (e) {
      tried.push(`${c}: ${String(e.message).split('\n')[0]}`);
    }
  }
  throw new Error(`Playwright not found (set PLAYWRIGHT_MODULE). Tried:\n  ${tried.join('\n  ')}`);
}

const failures = [];
const notes = [];
function check(ok, message) {
  if (ok) notes.push(`ok   ${message}`);
  else failures.push(message);
  console.log(`${ok ? '[ok]  ' : '[FAIL]'} ${message}`);
}

async function waitForServer(url, ms = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (r.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

let stopServer = async () => {};
let appUrl = opts.url;
let serverKind = opts.url ? `external ${opts.url}` : opts.server;
if (!appUrl) {
  const dist = join(PLANNER, 'dist');
  if (!existsSync(join(dist, 'index.html'))) {
    console.error('[smoke] planner/dist missing — run: VITE_BASE_PATH=/wildfireguardian/ npm run build:static');
    process.exit(1);
  }
  if (opts.server === 'vite') {
    appUrl = `http://127.0.0.1:${opts.port}${opts.base}`;
    const child = spawn(join(PLANNER, 'node_modules', '.bin', 'vite'), ['preview', '--mode', 'static', '--port', opts.port, '--strictPort'], {
      cwd: PLANNER,
      env: { ...process.env, VITE_BASE_PATH: opts.base },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    child.stdout.on('data', () => {});
    child.stderr.on('data', (d) => process.stderr.write(d));
    stopServer = async () => child.kill('SIGTERM');
    if (!(await waitForServer(appUrl))) {
      console.error(`[smoke] vite preview did not answer at ${appUrl}`);
      await stopServer();
      process.exit(1);
    }
    serverKind = 'vite preview --mode static (dist only)';
  } else {
    const srv = await startStaticServer({ dir: dist, base: opts.base, port: Number(opts.port) });
    appUrl = srv.url;
    stopServer = srv.close;
    serverKind = 'dist only, like GitHub Pages (scripts/serve_static.mjs)';
  }
}
const ORIGIN = new URL(appUrl).origin;
const APP_PREFIX = `${ORIGIN}${new URL(appUrl).pathname}`;
console.log(`[smoke] ${appUrl} — ${serverKind}`);

if (opts.screenshots) mkdirSync(opts.out, { recursive: true });
const shots = [];
async function shot(page, name) {
  if (!opts.screenshots) return;
  const file = join(opts.out, `${name}.png`);
  await page.screenshot({ path: file });
  shots.push({ file: `docs/screenshots/solve-demo/${name}.png`, bytes: statSync(file).size });
}

const requests = [];
const failedRequests = [];
const badResponses = [];
const consoleErrors = [];
const pageErrors = [];
/** The one deliberate cross-origin probe (an <img>) that the page's CSP must refuse. */
const CSP_PROBE = 'http://127.0.0.1:8765/v1/probe.png';
const OPTIONAL_404 = /\/temporary_housing\.geojson$/;

function watch(page, label) {
  page.on('request', (r) => requests.push({ label, url: r.url(), method: r.method() }));
  page.on('requestfailed', (r) => failedRequests.push({ label, url: r.url(), error: r.failure()?.errorText ?? '' }));
  page.on('response', (r) => {
    const s = r.status();
    if (s >= 400 && !OPTIONAL_404.test(r.url())) badResponses.push(`${label} ${s} ${r.url()}`);
  });
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push({ label, text: m.text(), url: m.location()?.url ?? '' });
  });
  page.on('pageerror', (e) => pageErrors.push(`${label} ${e.message}`));
}

/** Collects Content-Security-Policy violations in the page (deliberate probes are filtered later). */
const CSP_HOOK = `window.__cspViolations = []; document.addEventListener('securitypolicyviolation', (e) => window.__cspViolations.push({ uri: e.blockedURI, directive: e.violatedDirective }));`;

async function ready(page) {
  await page.waitForSelector('html[data-wfg-data-ready="true"]', { timeout: 60000 });
}

async function text(page, sel) {
  return (await page.locator(sel).first().innerText({ timeout: 15000 })).replace(/\s+/g, ' ').trim();
}

/** data-testid of the focused element and whether it is inside `within` (a selector). */
async function focusInfo(page, within) {
  return page.evaluate((sel) => {
    const a = document.activeElement;
    const box = sel ? document.querySelector(sel) : null;
    return { id: a?.getAttribute('data-testid') ?? a?.tagName ?? null, inside: Boolean(box && a && box.contains(a)) };
  }, within ?? null);
}

async function noHorizontalScroll(page, label) {
  const w = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, vw: window.innerWidth }));
  check(w.doc <= w.vw + 1, `${label}: no horizontal page scroll (scrollWidth ${w.doc} ≤ ${w.vw})`);
}

async function honesty(page, label, lang) {
  const banner = await text(page, '[data-testid="fire-banner"]');
  check(banner.includes(lang === 'ko' ? '2025년 실제 산불 기록 기반 시나리오 재현' : 'Recorded 2025 wildfire · scenario replay'), `${label}: fire-input banner "${banner}"`);
  const footer = await text(page, 'footer.footer');
  check(footer.includes(lang === 'ko' ? '사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.' : 'Planning aid only — not for live evacuation operations.'), `${label}: planning-aid footer`);
  const footerBox = await page.locator('footer.footer .rule').boundingBox();
  const vw = page.viewportSize().width;
  check(Boolean(footerBox) && footerBox.x >= 0 && footerBox.x + footerBox.width <= vw + 1, `${label}: footer rule fully inside the viewport`);
  const chip = await text(page, '[data-testid="demo-chip"]');
  const phone = vw <= 480;
  const wantChip = lang === 'ko' ? (phone ? '2025년 3월 기록 · 연구 프로토타입' : '2025년 3월 기록 시나리오 · 연구 프로토타입') : phone ? 'Mar 2025 replay · research prototype' : 'recorded March 2025 scenarios · research prototype';
  check(chip.includes('DEMO') && chip.includes(wantChip), `${label}: DEMO chip "${chip}"`);
  check((await page.locator('[data-testid="mock-badge"]').count()) === 0, `${label}: no MOCK badge (cache from the real API)`);
  check((await page.locator('[data-testid="test-badge"], [data-testid="test-data"]').count()) === 0, `${label}: no "not the evaluation host" marking (cache computed on the evaluated host)`);
  // three verdicts, each colour + icon + text
  const verdicts = await page.evaluate(() =>
    [...document.querySelectorAll('[data-testid="summary"] .summary-cell .l')].slice(0, 3).map((el) => ({ text: el.textContent?.trim() ?? '', icon: Boolean(el.querySelector('svg')) })),
  );
  const want = lang === 'ko' ? ['확인된 경로', '모델상 경로 없음', '미확인'] : ['Checked route', 'No route in model', 'Unresolved'];
  check(
    verdicts.length === 3 && verdicts.every((v, i) => v.icon && v.text.startsWith(want[i])),
    `${label}: three verdicts with icon + text ${JSON.stringify(verdicts.map((v) => v.text))}`,
  );
  const colours = await page.evaluate(() => {
    const c = (sel) => {
      const el = document.querySelector(sel);
      return el ? getComputedStyle(el).backgroundColor : null;
    };
    return { checked: c('.status.checked_route'), noRoute: c('.status.model_no_route'), unresolvedImg: (() => { const el = document.querySelector('.status.unresolved'); return el ? getComputedStyle(el).backgroundImage.slice(0, 30) : null; })() };
  });
  check(colours.checked === 'rgb(232, 246, 238)', `${label}: checked route chip is green-tinted (${colours.checked})`);
  if (colours.noRoute) check(colours.noRoute === 'rgb(11, 11, 12)', `${label}: no-route chip is ink (${colours.noRoute})`);
  if (colours.unresolvedImg) check(colours.unresolvedImg.startsWith('url('), `${label}: unresolved chip is grey hatch, never green`);
}

/** The selected origin is the first village or care facility (OSM) of the urgency list with a checked route. */
async function selectedIsFirstChecked(page) {
  return page.evaluate(() => {
    const rows = [...document.querySelectorAll('.origin-list .origin-row')];
    const first = rows.find((r) => r.getAttribute('data-testid')?.startsWith('origin-osm:') && r.querySelector('.status.checked_route'));
    const sel = rows.find((r) => r.getAttribute('aria-selected') === 'true');
    return { ok: Boolean(first && sel && first === sel), first: first?.getAttribute('data-testid') ?? null, selected: sel?.getAttribute('data-testid') ?? null, topVerdict: rows[0]?.querySelector('.status')?.className ?? null };
  });
}

/** Forecast layer of the static demo: on, with its legend, no "unavailable" notice. */
async function forecastLayer(page, label, lang) {
  await page.waitForFunction(() => {
    const b = document.querySelector('.map-tools .btn');
    return b && !b.disabled;
  }, null, { timeout: 30000 });
  const toggle = page.locator('.map-tools .btn').first();
  check(!(await toggle.isDisabled()) && (await toggle.getAttribute('aria-pressed')) === 'true', `${label}: forecast-cell layer is enabled and on`);
  const legend = page.locator('[data-testid="map-legend"]');
  if ((await legend.getAttribute('class'))?.includes('collapsed')) await legend.locator('.lg-toggle').click();
  const legendText = await text(page, '[data-testid="map-legend"]');
  check(legendText.includes(lang === 'ko' ? '다음 1시간 신규 연소 확률 (예측 c651)' : 'Next-hour new-burn probability (c651)') && legendText.includes(lang === 'ko' ? '입력 시각 연소 중' : 'Burning at input time'), `${label}: forecast legend keeps its labels`);
  const notice = (await page.locator('.map-notice').count()) ? await text(page, '.map-notice') : '';
  check(!/예측 격자|forecast/i.test(notice), `${label}: no forecast notice ("${notice}")`);
}

/** First OSM village or care facility in the urgency list with a checked route (a leave-by time). */
async function pickCheckedOrigin(page, { tap = false } = {}) {
  const row = page.locator('.origin-list .origin-row[data-testid^="origin-osm:"]:has(.status.checked_route)').first();
  const name = (await row.locator('.name').innerText()).trim();
  if (tap) await row.tap();
  else await row.click();
  return { name, row };
}

async function heights(page) {
  return page.evaluate(() => {
    const h = (sel) => Math.round(document.querySelector(sel)?.getBoundingClientRect().height ?? -1);
    const chip = document.querySelector('[data-testid="demo-chip"]');
    return { topbar: h('.topbar'), ribbon: h('.demo-ribbon'), chip: h('[data-testid="demo-chip"]'), chipOneLine: chip ? chip.getBoundingClientRect().height <= 24 : false };
  });
}

const chromium = loadChromium();
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
let exitCode = 0;
const measured = {};
try {
  // ------------------------------------------------------------------ desktop, Korean
  {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'ko-KR' });
    await ctx.addInitScript(CSP_HOOK);
    const page = await ctx.newPage();
    watch(page, 'desktop');
    await page.goto(appUrl);
    await ready(page);
    await page.waitForSelector('[data-testid="demo-intro"]');
    const intro = await text(page, '[data-testid="demo-intro-body"]');
    check(intro.includes('2025년 3월') && intro.includes('의성·안동') && intro.includes('영덕'), `desktop: intro names the recorded period and regions`);
    // keyboard: the modal introduction keeps the focus inside
    check((await focusInfo(page, '[data-testid="demo-intro"]')).id === 'demo-tour-start', 'desktop: the introduction opens with the focus on "3단계 둘러보기"');
    for (let i = 0; i < 9; i += 1) await page.keyboard.press('Tab');
    const afterTab = await focusInfo(page, '[data-testid="demo-intro"]');
    for (let i = 0; i < 4; i += 1) await page.keyboard.press('Shift+Tab');
    const afterShiftTab = await focusInfo(page, '[data-testid="demo-intro"]');
    check(afterTab.inside && afterShiftTab.inside, `desktop: Tab and Shift+Tab stay inside the introduction (${afterTab.id}, ${afterShiftTab.id})`);
    await page.waitForTimeout(1500);
    await shot(page, 'desktop-ko-01-intro');
    await page.click('[data-testid="demo-tour-start"]');
    await page.waitForSelector('[data-testid="tour-card"][data-step="1"]');
    check((await page.locator('.origin-list.tour-target').count()) === 1, 'desktop: tour step 1 highlights the urgency list');
    check((await focusInfo(page)).id === 'tour-card', 'desktop: tour step 1 takes the focus');
    await page.keyboard.press('Tab');
    check((await focusInfo(page, '[data-testid="tour-card"]')).inside, 'desktop: the next Tab stop is a button of the tour card');
    await shot(page, 'desktop-ko-02-tour-list');
    // step 2 without picking: the tour picks the first origin with a checked route
    await page.click('[data-testid="tour-next"]');
    await page.waitForSelector('[data-testid="tour-card"][data-step="2"]');
    check((await focusInfo(page)).id === 'tour-card', 'desktop: tour step 2 takes the focus');
    await page.waitForSelector('[data-testid="headline"]');
    const picked = await selectedIsFirstChecked(page);
    check(picked.ok, `desktop: step 2 selected the first village or facility with a checked route (${picked.selected}; the list starts with ${picked.topVerdict})`);
    const headline = await text(page, '[data-testid="headline"]');
    check(/출발 마감 \d{2}:\d{2}/.test(headline), `desktop: step 2 shows a leave-by time "${headline.slice(0, 40)}"`);
    const tour2 = await text(page, '[data-testid="tour-card"]');
    check(!tour2.includes('그 이유가 표시됩니다'), 'desktop: tour step 2 text is neutral');
    for (const id of ['shelter-card', 'exposure', 'provenance', 'travel-only']) check((await page.locator(`[data-testid="${id}"]`).count()) > 0, `desktop: evidence block ${id} shown`);
    check(await page.locator('[data-testid="recompute"]').isDisabled(), 'desktop: "이 출발지 다시 계산" is disabled in the static demo');
    check((await page.locator('.panel-right [data-testid="static-note"] a').count()) === 1, 'desktop: static note links the local Route-Check API instructions');
    const apiStatus = await text(page, '[data-testid="api-status"]');
    check(apiStatus.includes('정적 데모'), `desktop: API status "${apiStatus}" (never "connected")`);
    await honesty(page, 'desktop ko', 'ko');
    await forecastLayer(page, 'desktop ko', 'ko');
    await page.waitForTimeout(2500); // route + basemap tiles
    await shot(page, 'desktop-ko-03-leave-by');
    await page.click('[data-testid="tour-next"]');
    await page.waitForSelector('[data-testid="tour-card"][data-step="3"]');
    check((await focusInfo(page)).id === 'tour-card', 'desktop: tour step 3 takes the focus');
    await page.click('[data-testid="tour-open-plansheet"]');
    await page.waitForSelector('[data-testid="plan-sheet-dialog"]');
    await page.waitForSelector('.wfgf-plansheet-root[data-wfg-current-ready="true"]', { timeout: 60000 });
    const sheet = await text(page, '.wfgf-sheet[data-current="true"]');
    const name = picked.selected ? (await text(page, `[data-testid="${picked.selected}"] .name`)) : '';
    check(sheet.includes(name.split(' ')[0]) && sheet.includes('2025년 실제 산불 기록 기반 시나리오 재현'), 'desktop: A4 plan sheet of the selected origin with its fire-input label');
    check(sheet.includes('사전 계획 보조 도구입니다') || (await text(page, '.wfgf-plansheet__foot')).includes('사전 계획 보조 도구입니다'), 'desktop: plan sheet carries the planning-aid footer');
    const marker = await text(page, '.wfgf-sheet[data-current="true"] [data-demo-label]');
    check(marker === 'DEMO · 2025년 3월 기록 시나리오 재생 · 연구 프로토타입', `desktop: plan sheet DEMO marker "${marker}"`);
    const place = await page.evaluate(() => {
      const s = document.querySelector('.wfgf-sheet[data-current="true"]');
      const m = s?.querySelector('[data-demo-label]')?.getBoundingClientRect();
      const h = s?.querySelector('.wfgf-sheet__head')?.getBoundingClientRect();
      const b = s?.getBoundingClientRect();
      return m && h && b ? { inMargin: m.bottom <= h.top + 0.5 && m.top >= b.top, inside: m.right <= b.right } : null;
    });
    check(Boolean(place?.inMargin && place?.inside), `desktop: the DEMO marker sits in the A4 top margin, above the sheet header (${JSON.stringify(place)})`);
    const sheetCount = await page.locator('.wfgf-sheet').count();
    const markers = await page.locator('.wfgf-sheet [data-demo-label]').count();
    check(sheetCount > 0 && markers === sheetCount, `desktop: every plan sheet carries the marker (${markers}/${sheetCount})`);
    await shot(page, 'desktop-ko-04-plan-sheet');
    await page.keyboard.press('Escape');
    await page.waitForSelector('[data-testid="plan-sheet-dialog"]', { state: 'detached' });
    // the ribbon's Tour button reopens the introduction; Escape closes it wherever the focus is
    await page.click('[data-testid="demo-tour-open"]');
    await page.waitForSelector('[data-testid="demo-intro"]');
    await page.click('[data-testid="demo-intro-body"]'); // a click on text: the focus leaves the buttons
    await page.keyboard.press('Escape');
    await page.waitForSelector('[data-testid="demo-intro"]', { state: 'detached' });
    check((await focusInfo(page)).id === 'demo-tour-open', 'desktop: Escape closes the introduction and the focus returns to the Tour button');
    await page.keyboard.press('Enter');
    await page.waitForSelector('[data-testid="demo-intro"]');
    await page.keyboard.press('Enter'); // "3단계 둘러보기" has the focus
    await page.waitForSelector('[data-testid="tour-card"][data-step="1"]');
    await page.keyboard.press('Escape');
    await page.waitForSelector('[data-testid="tour-card"]', { state: 'detached' });
    check((await focusInfo(page)).id === 'demo-tour-open', 'desktop: Escape ends the tour and the focus returns to the Tour button');
    // English
    await page.locator('.topbar-right .seg button[lang="en"]').click();
    const headlineEn = await text(page, '[data-testid="headline"]');
    check(/Leave by \d{2}:\d{2}/.test(headlineEn), `desktop: English leave-by headline "${headlineEn.slice(0, 30)}"`);
    await honesty(page, 'desktop en', 'en');
    await forecastLayer(page, 'desktop en', 'en');
    await shot(page, 'desktop-en-05-leave-by');
    // a root-absolute public/data path works under the base (the generic loader for generated files)
    const probe = await page.evaluate(async (probeUrl) => {
      const ok = await fetch('/data/regions/uiseong_andong_2025/places_report.json').then((r) => r.status, (e) => `error ${e.message}`);
      const api = await fetch('http://127.0.0.1:8765/v1/health').then((r) => `answered ${r.status}`, (e) => `refused: ${e.message}`);
      const local = await fetch('/api/v1/health').then((r) => `answered ${r.status}`, (e) => `refused: ${e.message}`);
      // the browser itself (CSP) refuses a cross-origin image, independent of the fetch guard
      const img = await new Promise((res) => {
        const el = new Image();
        el.onload = () => res('loaded');
        el.onerror = () => res('blocked');
        el.src = probeUrl;
      });
      return { ok, api, local, img, csp: window.__cspViolations };
    }, CSP_PROBE);
    check(probe.ok === 200, `desktop: fetch("/data/…") is served under the base path (${probe.ok})`);
    check(String(probe.api).startsWith('refused'), `desktop: a request to http://127.0.0.1:8765 is refused before sending (${probe.api})`);
    check(String(probe.local).startsWith('refused'), `desktop: a same-origin /api/ request is refused (${probe.local})`);
    check(probe.img === 'blocked' && probe.csp.some((v) => v.uri === CSP_PROBE && v.directive === 'img-src'), `desktop: the CSP blocks a cross-origin image (${JSON.stringify(probe.csp)})`);
    const unexpectedCsp = probe.csp.filter((v) => v.uri !== CSP_PROBE);
    check(unexpectedCsp.length === 0, `desktop: no other CSP violation ${JSON.stringify(unexpectedCsp)}`);
    // drawn spread zones: an assumption, editable, never computed here
    await page.locator('.topbar-right .seg button[lang="ko"]').click();
    await page.click('[data-testid="scenario-drawn"]');
    await ready(page);
    const bannerDrawn = await text(page, '[data-testid="fire-banner"]');
    check(bannerDrawn.includes('사용자 입력 확산 구역 (가정)'), `desktop: drawn zones are labelled as an assumption (${bannerDrawn})`);
    const drawnHead = (await page.locator('[data-testid="headline"]').count()) ? await text(page, '[data-testid="headline"]') : '';
    check(!drawnHead || (/미확인/.test(drawnHead) && !drawnHead.includes('API에 점검을 요청')), `desktop: under drawn zones the selected origin is 미확인 with the static-demo wording ("${drawnHead.slice(0, 80)}")`);
    await page.click('[data-testid="tab-zones"]');
    await page.waitForSelector('[data-testid="drawn-batch"]');
    check((await page.locator('[data-testid="drawn-batch"] [data-testid="static-note"]').count()) === 1, 'desktop: drawn-zone checks show the static-demo note');
    check(await page.locator('[data-testid="drawn-batch-prepare"]').isDisabled(), 'desktop: "구역 안·주변 마을 계산" is disabled');
    await shot(page, 'desktop-ko-06-drawn-zones');
    // deep link straight into English, another region and input time
    await page.goto(`${appUrl}?region=yeongdeok_2025&scenario=20250325T230000Z&lang=en`);
    await ready(page);
    const bannerDeep = await text(page, '[data-testid="fire-banner"]');
    check(bannerDeep.includes('2025-03-26 08:00 KST'), `desktop: deep link opens Yeongdeok 2025-03-26 08:00 KST (${bannerDeep})`);
    await forecastLayer(page, 'desktop deep link', 'en');
    await ctx.close();
  }

  // ------------------------------------------------------------------ first visit from an English browser
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'en-US' });
    const page = await ctx.newPage();
    watch(page, 'english-browser');
    await page.goto(appUrl);
    await ready(page);
    check((await page.getAttribute('html', 'lang')) === 'en', 'first visit from an English browser opens in English');
    check((await text(page, '[data-testid="demo-intro-body"]')).includes('March 2025 Uiseong–Andong and Yeongdeok wildfires'), 'English intro names the recorded period and regions');
    await page.click('[data-testid="demo-intro-close"]');
    check((await focusInfo(page)).id === 'demo-tour-open', 'closing the first-visit introduction puts the focus on the Tour button');
    await page.reload();
    await ready(page);
    check((await page.locator('[data-testid="demo-intro"]').count()) === 0, 'a dismissed introduction stays closed after a reload (localStorage)');
    await ctx.close();
  }

  // ------------------------------------------------------------------ phone 375 px, Korean then English
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true, locale: 'ko-KR' });
    await ctx.addInitScript(CSP_HOOK);
    const page = await ctx.newPage();
    watch(page, 'phone');
    await page.goto(appUrl);
    await ready(page);
    await page.waitForSelector('[data-testid="demo-intro"]');
    await noHorizontalScroll(page, 'phone intro');
    await shot(page, 'phone-375-ko-01-intro');
    await page.tap('[data-testid="demo-intro-close"]');
    check((await page.locator('[data-testid="mobile-nav"]').isVisible()) && (await page.getAttribute('.app', 'data-mobile-pane')) === 'list', 'phone: list pane with the tab bar');
    await noHorizontalScroll(page, 'phone list');
    await honesty(page, 'phone ko', 'ko');
    measured.ko = await heights(page);
    check(measured.ko.chipOneLine && measured.ko.ribbon <= 38, `phone ko: the DEMO ribbon is one line (${measured.ko.ribbon} px)`);
    check(measured.ko.topbar <= 96, `phone ko: top bar is one row of controls above the banner (${measured.ko.topbar} px)`);
    await shot(page, 'phone-375-ko-02-list');
    // the tour on a phone: step 2 opens the details of the first origin with a checked route
    await page.tap('[data-testid="demo-tour-open"]');
    await page.tap('[data-testid="demo-tour-start"]');
    await page.waitForSelector('[data-testid="tour-card"][data-step="1"]');
    await page.tap('[data-testid="tour-next"]');
    await page.waitForSelector('[data-testid="tour-card"][data-step="2"]');
    await page.waitForFunction(() => document.querySelector('.app')?.getAttribute('data-mobile-pane') === 'detail');
    const tourPick = await selectedIsFirstChecked(page);
    check(tourPick.ok && /출발 마감 \d{2}:\d{2}/.test(await text(page, '[data-testid="headline"]')), `phone: tour step 2 shows the details of the first village or facility with a checked route (${tourPick.selected})`);
    await page.tap('[data-testid="tour-skip"]');
    await page.tap('[data-testid="mobile-tab-list"]');
    const { name } = await pickCheckedOrigin(page, { tap: true });
    await page.waitForFunction(() => document.querySelector('.app')?.getAttribute('data-mobile-pane') === 'detail');
    const headline = await text(page, '[data-testid="headline"]');
    check(/출발 마감 \d{2}:\d{2}/.test(headline), `phone: ${name} → details with its leave-by time "${headline.slice(0, 30)}"`);
    // the already selected village: a tap on its row opens the details again
    await page.tap('[data-testid="mobile-tab-list"]');
    await page.locator('.origin-list .origin-row[aria-selected="true"]').tap();
    await page.waitForTimeout(200);
    check((await page.getAttribute('.app', 'data-mobile-pane')) === 'detail', 'phone: tapping the already selected row opens its details again');
    await noHorizontalScroll(page, 'phone details');
    const rp = await page.locator('.panel-right').boundingBox();
    check(Boolean(rp) && rp.width <= 375 && rp.x >= 0, `phone: details pane fits the screen (${rp && Math.round(rp.width)} px)`);
    await shot(page, 'phone-375-ko-03-leave-by');
    await page.tap('[data-testid="mobile-tab-map"]');
    await forecastLayer(page, 'phone ko', 'ko');
    await page.locator('[data-testid="map-legend"] .lg-toggle').tap(); // close the legend again: the map is small
    await page.waitForTimeout(2500);
    await shot(page, 'phone-375-ko-04-map');
    await page.tap('[data-testid="open-plansheet"]');
    await page.waitForSelector('.wfgf-plansheet-root[data-wfg-current-ready="true"]', { timeout: 60000 });
    const sheetBox = await page.locator('.wfgf-sheet[data-current="true"]').boundingBox();
    check(Boolean(sheetBox) && sheetBox.width <= 375, `phone: plan sheet reflows to the screen (${sheetBox && Math.round(sheetBox.width)} px wide)`);
    const sheetText = await text(page, '.wfgf-sheet[data-current="true"]');
    check(sheetText.includes('2025년 실제 산불 기록 기반 시나리오 재현'), 'phone: plan sheet keeps its fire-input label');
    check(sheetText.includes('DEMO · 2025년 3월 기록 시나리오 재생 · 연구 프로토타입'), 'phone: plan sheet carries the DEMO marker');
    await noHorizontalScroll(page, 'phone plan sheet');
    await shot(page, 'phone-375-ko-05-plan-sheet');
    await page.tap('.wfgf-plansheet__actions .wfgf-iconbtn');
    await page.waitForSelector('[data-testid="plan-sheet-dialog"]', { state: 'detached' });
    await page.tap('[data-testid="mobile-tab-detail"]');
    await page.locator('.topbar-right .seg button[lang="en"]').tap();
    const headlineEn = await text(page, '[data-testid="headline"]');
    check(/Leave by \d{2}:\d{2}/.test(headlineEn), `phone: English leave-by headline "${headlineEn.slice(0, 30)}"`);
    await honesty(page, 'phone en', 'en');
    measured.en = await heights(page);
    check(measured.en.chipOneLine && measured.en.ribbon <= 38, `phone en: the DEMO ribbon is one line (${measured.en.ribbon} px)`);
    check(measured.en.topbar <= 96, `phone en: top bar is one row of controls above the banner (${measured.en.topbar} px)`);
    await noHorizontalScroll(page, 'phone details en');
    await shot(page, 'phone-375-en-06-leave-by');
    const csp = await page.evaluate(() => window.__cspViolations);
    check(csp.length === 0, `phone: no CSP violation ${JSON.stringify(csp)}`);
    await ctx.close();
  }

  // ------------------------------------------------------------------ request audit
  // the deliberate CSP probe is refused by the browser itself (never sent, no response)
  const probeEvents = requests.filter((r) => r.url === CSP_PROBE);
  const probeFailures = failedRequests.filter((r) => r.url === CSP_PROBE);
  check(probeEvents.length <= 1 && probeFailures.length === probeEvents.length && probeFailures.every((r) => /BLOCKED_BY_CSP|csp/i.test(r.error)), `the CSP probe never left the browser (${JSON.stringify(probeFailures)})`);
  const audited = requests.filter((r) => r.url !== CSP_PROBE);
  const offOrigin = audited.filter((r) => !/^(data|blob):/.test(r.url) && !r.url.startsWith(APP_PREFIX));
  check(audited.length > 0 && offOrigin.length === 0, `all ${audited.length} requests stay under ${APP_PREFIX} (off-origin or outside the base: ${offOrigin.length}${offOrigin.length ? ` e.g. ${offOrigin[0].url}` : ''})`);
  const apiLike = audited.filter((r) => /127\.0\.0\.1:8765|localhost|\/api\//.test(r.url));
  check(apiLike.length === 0, `no request to the Route-Check API, 127.0.0.1:8765 or localhost (${apiLike.length})`);
  const forecastFiles = new Set(audited.filter((r) => r.url.includes('/data/forecast/')).map((r) => r.url.split('/').pop()));
  check(forecastFiles.size >= 2, `the forecast cells come from data/forecast/ (${[...forecastFiles].join(', ')})`);
  // the optional temporary_housing.geojson answers 404; the app reads the status and drops the body (ERR_ABORTED)
  const otherFailed = failedRequests.filter((r) => r.url !== CSP_PROBE && !OPTIONAL_404.test(r.url));
  check(otherFailed.length === 0, `no failed request ${JSON.stringify(otherFailed.slice(0, 3))}`);
  check(badResponses.length === 0, `no error response except the optional temporary_housing.geojson (${badResponses.slice(0, 3).join(' | ')})`);
  const deliberate = (c) =>
    /\[static demo\] blocked: (cross-origin request http:\/\/127\.0\.0\.1:8765 |Route-Check API request \/api\/v1\/health )/.test(c.text) ||
    c.text.includes(CSP_PROBE) ||
    (/Failed to load resource/.test(c.text) && OPTIONAL_404.test(c.url));
  const otherErrors = consoleErrors.filter((c) => !deliberate(c));
  check(otherErrors.length === 0, `no unexpected console error ${JSON.stringify(otherErrors.slice(0, 3))}`);
  check(pageErrors.length === 0, `no page error ${JSON.stringify(pageErrors.slice(0, 3))}`);
  const byKind = {};
  for (const r of audited) {
    const path = r.url.startsWith(APP_PREFIX) ? r.url.slice(APP_PREFIX.length).split('?')[0] : r.url.slice(0, 40);
    const kind = /^(data|blob):/.test(r.url) ? r.url.slice(0, 4) : path.split('/')[0] || 'index.html';
    byKind[kind] = (byKind[kind] ?? 0) + 1;
  }
  console.log(`[smoke] requests by folder: ${JSON.stringify(byKind)}`);
  console.log(`[smoke] phone heights (px): ${JSON.stringify(measured)}`);
  if (opts.screenshots) {
    const report = {
      url: appUrl,
      base: opts.base,
      server: serverKind,
      requests: audited.length,
      requests_by_folder: byKind,
      off_origin: offOrigin.length,
      csp_probe_refused: probeFailures.map((r) => r.error),
      phone_heights_px: measured,
      checks_passed: notes.length,
      failures,
      screenshots: shots.map((s) => s.file),
    };
    writeFileSync(join(opts.out, 'smoke-report.json'), `${JSON.stringify(report, null, 2)}\n`);
    console.log(`[smoke] screenshots: ${shots.map((s) => `${s.file} (${Math.round(s.bytes / 1024)} KB)`).join(', ')}`);
  }
} catch (e) {
  failures.push(`exception: ${e.stack ?? e}`);
  console.error(e);
} finally {
  await browser.close();
  await stopServer();
}
if (failures.length) {
  console.error(`[smoke] ${failures.length} failed:\n  ${failures.join('\n  ')}`);
  exitCode = 1;
} else console.log(`[smoke] all ${notes.length} checks passed`);
process.exit(exitCode);
