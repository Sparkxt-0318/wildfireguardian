#!/usr/bin/env node
/**
 * Writes ONE PDF with every plan sheet (기관용 사전 대피계획서, one A4 page per origin) of a region
 * and scenario, by opening the running planner app in headless Chromium and printing the plan-sheet
 * dialog with page.pdf({ format: 'A4' }). Nothing is recomputed: the sheets show what the app has
 * loaded (precomputed cache or API results), with the fire-input label, MOCK badge and provenance.
 *
 * Usage (app running, e.g. `npm run dev` on :5173):
 *   PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \
 *   node planner/scripts/export_plan_pdfs.mjs [--url http://127.0.0.1:5173] [--out planner/exports]
 *        [--region uiseong_andong_2025[,yeongdeok_2025]] [--scenario 20250324T090000Z|<scenario_set_id>]
 *        [--lang ko|en] [--timeout-s 900]
 *
 * How the app is driven:
 *   1. open  <url>/?print=all&region=<id>[&scenario=<input_compact|scenario_set_id|zones>]&lang=<ko|en>
 *      - region / scenario / lang are the app's deep-link query (the app resolves an input time such as
 *        20250324T090000Z to its recorded scenario set; "zones" = drawn spread zones);
 *      - `?print=all` makes PlanSheetDialog render every static map up front, and the app opens the
 *        plan-sheet dialog by itself once its data is ready;
 *   2. wait for the app's data: html[data-wfg-data-ready="true"] (else network idle);
 *   3. open the plan-sheet dialog (button "계획서" / "Plan sheet") unless the app already opened it;
 *   4. wait for [data-wfg-sheets-ready="true"] (all maps final, fonts loaded), check it stays stable;
 *   5. page.pdf (print CSS prints only the sheets, one per page) → <out>/wfg_plan_sheets_<region>_<input>_<lang>[_MOCK].pdf
 *
 * Exit code 0 when every requested PDF was written, 1 otherwise.
 */
import { existsSync, mkdirSync, statSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const PLANNER = resolve(fileURLToPath(new URL('..', import.meta.url)));
const DEFAULT_CHROMIUM = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

function pick(mod) {
  return mod?.chromium ?? mod?.default?.chromium ?? null;
}

async function loadChromium() {
  const tried = [];
  const env = process.env.PLAYWRIGHT_MODULE;
  if (env) {
    const abs = resolve(env);
    const req = createRequire(join(PLANNER, 'package.json'));
    const candidates = [abs];
    if (existsSync(abs) && statSync(abs).isDirectory()) candidates.push(join(abs, 'node_modules', 'playwright'), join(abs, 'node_modules', 'playwright-core'));
    for (const c of candidates) {
      try {
        const chromium = pick(req(c));
        if (chromium) return chromium;
      } catch (e) {
        tried.push(`${c}: ${e.message.split('\n')[0]}`);
      }
    }
  }
  const req = createRequire(join(PLANNER, 'package.json'));
  for (const name of ['playwright', 'playwright-core', '@playwright/test']) {
    try {
      const chromium = pick(req(name));
      if (chromium) return chromium;
    } catch (e) {
      tried.push(`${name}: ${e.message.split('\n')[0]}`);
    }
  }
  throw new Error(
    'Playwright not found. Install it outside the project (e.g. `npm i playwright@1.56.1` in a scratch dir) and set ' +
      'PLAYWRIGHT_MODULE=/path/to/node_modules/playwright. Tried:\n  ' +
      tried.join('\n  '),
  );
}

async function launchBrowser() {
  const chromium = await loadChromium();
  const executablePath =
    process.env.CHROMIUM_PATH || process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (existsSync(DEFAULT_CHROMIUM) ? DEFAULT_CHROMIUM : undefined);
  return chromium.launch({
    executablePath,
    // software WebGL so MapLibre renders in headless mode
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--font-render-hinting=none'],
  });
}

/** --key value / --key=value / --flag parsing. */
function parseArgs(argv, defaults) {
  const out = { ...defaults };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const eq = a.indexOf('=');
    const key = (eq > 0 ? a.slice(2, eq) : a.slice(2)).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    let val = eq > 0 ? a.slice(eq + 1) : argv[i + 1];
    if (eq < 0) {
      if (val === undefined || val.startsWith('--')) val = 'true';
      else i += 1;
    }
    out[key] = val;
  }
  return out;
}

function log(...xs) {
  console.error('[planner]', ...xs);
}

/** "20250324T090000Z" or ISO → "2025-03-24T09:00:00Z"; anything else → null. */
function toIso(s) {
  if (!s) return null;
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(s);
  if (m) return `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`;
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(s)) return s.replace(/\.\d+Z$/, 'Z');
  return null;
}

/** ISO → "20250324T090000Z" */
function toCompact(iso) {
  return iso ? iso.replace(/\.\d+Z$/, 'Z').replace(/[-:]/g, '') : 'scenario';
}

/** Resolve a scenario argument (input_compact, ISO, scenario set id or "drawn") through GET /api/v1/regions. */
async function resolveScenario(baseUrl, regionId, scenario) {
  if (!scenario) return { setId: null, iso: null };
  if (scenario === 'drawn') return { setId: 'drawn', iso: null };
  const iso = toIso(scenario);
  try {
    const r = await fetch(new URL('/api/v1/regions', baseUrl), { signal: AbortSignal.timeout(15000) });
    if (r.ok) {
      const body = await r.json();
      const region = (body.regions || []).find((x) => x.id === regionId);
      const set = (region?.scenario_sets || []).find((x) => x.scenario_set_id === scenario || (iso && toIso(x.input_time) === iso));
      if (set) return { setId: set.scenario_set_id, iso: toIso(set.input_time) };
    }
  } catch {
    /* API offline: fall back to clicking the scenario button by its input time */
  }
  return { setId: iso ? null : scenario, iso };
}

/** Waits until the core reports its data as loaded (html[data-wfg-data-ready]) or the network is idle. */
async function waitForAppData(page, timeoutMs) {
  const t0 = Date.now();
  await page.waitForLoadState('domcontentloaded');
  try {
    await page.waitForFunction(() => document.documentElement.dataset.wfgDataReady === 'true', null, { timeout: Math.min(30000, timeoutMs) });
    return 'data-ready';
  } catch {
    /* the core may not expose the flag: fall back to network idle */
  }
  try {
    await page.waitForLoadState('networkidle', { timeout: Math.max(5000, timeoutMs - (Date.now() - t0)) });
  } catch {
    /* keep going */
  }
  await page.waitForTimeout(1500);
  return 'networkidle';
}

/** Clicks the first visible button whose accessible name matches. Returns false when none. */
async function clickButton(page, re, timeoutMs = 4000) {
  const b = page.getByRole('button', { name: re }).first();
  try {
    await b.waitFor({ state: 'visible', timeout: timeoutMs });
    await b.click();
    return true;
  } catch {
    return false;
  }
}

async function exportRegion(browser, opts, regionId) {
  const base = opts.url.replace(/\/+$/, '') + '/';
  const scen = await resolveScenario(base, regionId, opts.scenario);
  const query = new URLSearchParams({ print: 'all', region: regionId, lang: opts.lang });
  if (opts.scenario) query.set('scenario', opts.scenario === 'drawn' ? 'zones' : opts.scenario);
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, locale: opts.lang === 'en' ? 'en-US' : 'ko-KR' });
  // the app remembers the UI language in localStorage
  await context.addInitScript((lang) => {
    try {
      localStorage.setItem('wfg.planner.lang', lang);
    } catch {
      /* ignore */
    }
  }, opts.lang);
  const page = await context.newPage();
  page.on('pageerror', (e) => log('page error:', e.message));
  const timeoutMs = Number(opts.timeoutS) * 1000;
  try {
    await page.goto(`${base}?${query.toString()}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await waitForAppData(page, 60000);
    if (!(await page.locator('.wfgf-plansheet-root').count())) {
      if (!(await clickButton(page, /^\s*(계획서|Plan sheet)\s*$/i, 15000))) throw new Error('plan-sheet button not found (is the app running at ' + base + '?)');
    }
    await page.waitForSelector('.wfgf-plansheet-root', { timeout: 30000 });
    const count0 = Number(await page.getAttribute('.wfgf-plansheet-root', 'data-wfg-sheet-count'));
    if (!count0) throw new Error('the plan-sheet dialog has no sheets (no origins loaded for this scenario?)');
    log(`${regionId}: ${count0} sheets, rendering maps…`);
    let stable = false;
    const t0 = Date.now();
    while (!stable && Date.now() - t0 < timeoutMs) {
      await page.waitForSelector('.wfgf-plansheet-root[data-wfg-sheets-ready="true"]', { timeout: timeoutMs });
      await page.waitForTimeout(1500);
      const again = await page.getAttribute('.wfgf-plansheet-root', 'data-wfg-sheets-ready');
      const count = Number(await page.getAttribute('.wfgf-plansheet-root', 'data-wfg-sheet-count'));
      stable = again === 'true' && count === Number(await page.locator('.wfgf-sheet').count());
    }
    if (!stable) throw new Error('sheets did not become ready in time');
    const meta = await page.$eval('.wfgf-sheet', (el) => ({ input: el.getAttribute('data-input-time'), mock: el.getAttribute('data-mock') === 'true' }));
    if (scen.iso && meta.input && toIso(meta.input) !== scen.iso) log(`scenario ${opts.scenario} not found for ${regionId}; the sheets show ${meta.input}`);
    const count = await page.locator('.wfgf-sheet').count();
    await page.emulateMedia({ media: 'print' });
    mkdirSync(opts.out, { recursive: true });
    const file = join(opts.out, `wfg_plan_sheets_${regionId}_${toCompact(meta.input)}_${opts.lang}${meta.mock ? '_MOCK' : ''}.pdf`);
    await page.pdf({ path: file, format: 'A4', printBackground: true, preferCSSPageSize: true, margin: { top: '0', right: '0', bottom: '0', left: '0' } });
    const bytes = statSync(file).size;
    log(`wrote ${file} (${count} pages, ${(bytes / 1e6).toFixed(2)} MB)${meta.mock ? ' — MOCK data' : ''}`);
    if (bytes > 25e6) log('warning: the PDF is larger than 25 MB; do not commit it');
    return { region: regionId, file, pages: count, bytes, mock: meta.mock };
  } finally {
    await context.close();
  }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2), {
    url: 'http://127.0.0.1:5173',
    out: join(PLANNER, 'exports'),
    region: 'uiseong_andong_2025',
    scenario: '',
    lang: 'ko',
    timeoutS: '900',
  });
  opts.out = resolve(opts.out);
  opts.lang = opts.lang === 'en' ? 'en' : 'ko';
  const browser = await launchBrowser();
  const results = [];
  let failed = 0;
  try {
    for (const regionId of String(opts.region).split(',').map((s) => s.trim()).filter(Boolean)) {
      try {
        results.push(await exportRegion(browser, opts, regionId));
      } catch (e) {
        failed += 1;
        log(`${regionId}: FAILED — ${e.message}`);
      }
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ written: results, failed }, null, 1));
  process.exit(failed ? 1 : 0);
}

main().catch((e) => {
  log(e.stack || e.message);
  process.exit(1);
});
