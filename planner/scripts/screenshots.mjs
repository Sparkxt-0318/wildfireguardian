#!/usr/bin/env node
/**
 * Captures every planner screen at 1440×900 and 1920×1080 into planner/docs/screenshots/ by driving
 * the running app in headless Chromium. Robust to missing states: a state that cannot be reached
 * is logged and skipped, the others are still captured. Writes manifest.json next to the images.
 *
 * Usage (app running, e.g. `npm run dev` on :5173):
 *   PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \
 *   node planner/scripts/screenshots.mjs [--url http://127.0.0.1:5173] [--out planner/docs/screenshots]
 *        [--sizes 1440x900,1920x1080] [--only main-uiseong,about] [--origin <place id>]
 *
 * States (file <nn>-<state>-<w>x<h>.png):
 *   01 main-uiseong      main screen, recorded 의성·안동 scenario (2025년 실제 산불 기록 기반 시나리오 재현)
 *   02 main-yeongdeok    main screen, recorded 영덕 scenario
 *   03 origin-route      의성·안동, an origin selected with its checked route (default: the first origin
 *                        whose list item shows a checked route, else --origin, else the recorded FL2 mission)
 *   04 english           the main screen in English
 *   05 about             About panel (이 도구에 대하여)
 *   06 plan-sheet        plan-sheet preview (기관용 사전 대피계획서) of the selected origin
 *   07 export            export dialog (GeoJSON / KML / CSV)
 *   08 drawn-zones       drawn-zones mode (사용자 입력 확산 구역 (가정)) with the recorded-footprint preset
 *                        (?scenario=zones&input=20250324T090000Z&preset=footprints); nothing is computed
 *   09 live-recompute    live recompute in progress — ONLY when /api/v1/health reports the MOCK; never
 *                        triggers computation on a real API
 *
 * Deep links use the app's query: ?region=<id>&scenario=<input_compact|zones>&origin=<place id>&lang=ko|en
 * (drawn zones also take &input=<input_compact>&preset=footprints). The app waits with
 * html[data-wfg-data-ready="true"] until the scenario's results (or drawn-zone state) are loaded.
 */
import { existsSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
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

const DEFAULT_RESEARCH_ORIGIN = 'research:uiseong_andong_2025:20250324T090000Z_FL2:origin';

async function apiIsMock(base) {
  try {
    const r = await fetch(new URL('/api/v1/health', base), { signal: AbortSignal.timeout(8000) });
    if (!r.ok) return false;
    const h = await r.json();
    return h.mode === 'mock' || h.mock === true;
  } catch {
    return false;
  }
}

let navSeq = 0;

async function gotoState(page, base, link) {
  // a fresh query string forces a full load; the app reads the deep link from the query
  navSeq += 1;
  const q = new URLSearchParams({ shot: String(navSeq), ...link });
  await page.goto(`${base}?${q.toString()}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await waitForAppData(page, 45000);
}

async function mapSettle(page) {
  // let MapLibre finish drawing (tiles, fit-bounds animation)
  await page.waitForTimeout(1200);
}

async function selectRouteOrigin(page, base, opts) {
  const hash = { region: 'uiseong_andong_2025', scenario: '20250324T090000Z' };
  if (opts.origin) hash.origin = opts.origin;
  await gotoState(page, base, hash);
  if (opts.origin) return opts.origin;
  // first origin in the list whose status reads "확인된 경로" (status = icon + text); results may still be arriving
  const item = page.locator('[data-testid^="origin-"]').filter({ hasText: /확인된 경로|Checked route/ }).first();
  const t0 = Date.now();
  while (!(await item.count()) && Date.now() - t0 < 30000) await page.waitForTimeout(1000);
  if (await item.count()) {
    await item.scrollIntoViewIfNeeded().catch(() => {});
    await item.click();
    await waitForAppData(page, 20000);
    return (await item.getAttribute('data-testid'))?.replace(/^origin-/, '') ?? 'first checked';
  }
  await gotoState(page, base, { ...hash, origin: DEFAULT_RESEARCH_ORIGIN });
  return DEFAULT_RESEARCH_ORIGIN;
}

const STATES = [
  {
    id: 'main-uiseong',
    title: '메인 — 의성·안동 (기록 시나리오)',
    run: async (page, base) => {
      await gotoState(page, base, { region: 'uiseong_andong_2025' });
      await mapSettle(page);
    },
  },
  {
    id: 'main-yeongdeok',
    title: '메인 — 영덕 (기록 시나리오)',
    run: async (page, base) => {
      await gotoState(page, base, { region: 'yeongdeok_2025' });
      await mapSettle(page);
    },
  },
  {
    id: 'origin-route',
    title: '출발지 선택 + 확인된 경로',
    run: async (page, base, opts) => {
      await selectRouteOrigin(page, base, opts);
      await mapSettle(page);
    },
  },
  {
    id: 'english',
    title: 'English UI',
    run: async (page, base) => {
      await gotoState(page, base, { region: 'uiseong_andong_2025', lang: 'en' });
      if ((await page.getAttribute('html', 'lang')) !== 'en' && !(await clickButton(page, /^English$/))) throw new Error('language toggle "English" not found');
      await mapSettle(page);
    },
  },
  {
    id: 'about',
    title: '소개 (About)',
    run: async (page, base) => {
      await gotoState(page, base, { region: 'uiseong_andong_2025' });
      if (!(await clickButton(page, /^\s*(소개|About)\s*$/))) throw new Error('About button not found');
      await page.waitForSelector('[data-testid="about-panel"]', { timeout: 10000 });
      await page.waitForTimeout(400);
    },
  },
  {
    id: 'plan-sheet',
    title: '사전 대피계획서 미리보기',
    run: async (page, base, opts) => {
      await selectRouteOrigin(page, base, opts);
      if (!(await clickButton(page, /^\s*(계획서|Plan sheet)\s*$/))) throw new Error('plan-sheet button not found');
      await page.waitForSelector('.wfgf-plansheet-root[data-wfg-current-ready="true"]', { timeout: 90000 });
      await page.waitForTimeout(600);
    },
  },
  {
    id: 'export',
    title: '내보내기',
    run: async (page, base, opts) => {
      await selectRouteOrigin(page, base, opts);
      if (!(await clickButton(page, /^\s*(내보내기|Export)\s*$/))) throw new Error('export button not found');
      await page.waitForSelector('[data-testid="export-dialog"], [role="dialog"]', { timeout: 10000 });
      await page.waitForTimeout(400);
    },
  },
  {
    id: 'drawn-zones',
    title: '사용자 입력 확산 구역 (가정)',
    run: async (page, base) => {
      await gotoState(page, base, { region: 'uiseong_andong_2025', scenario: 'zones', input: '20250324T090000Z', preset: 'footprints' });
      const btn = page.locator('[data-testid="scenario-drawn"]');
      if ((await btn.count()) && (await btn.first().getAttribute('aria-pressed')) !== 'true') await btn.first().click();
      if (!(await btn.count())) throw new Error('drawn-zones scenario button not found');
      await mapSettle(page);
    },
  },
  {
    id: 'live-recompute',
    title: '실시간 재계산 진행 중 (MOCK API)',
    run: async (page, base, opts) => {
      if (!(await apiIsMock(base))) throw new Error('skipped: the API is not the MOCK — screenshots never trigger computation on a real API');
      await selectRouteOrigin(page, base, opts);
      const btn = page.locator('[data-testid="recompute"]');
      if (!(await btn.count())) throw new Error('recompute button [data-testid="recompute"] not found');
      await btn.first().click();
      await page.waitForTimeout(350); // the mock moves queued → running → done over ≈ 0.6 s
    },
  },
];

async function main() {
  const opts = parseArgs(process.argv.slice(2), {
    url: 'http://127.0.0.1:5173',
    out: join(PLANNER, 'docs', 'screenshots'),
    sizes: '1440x900,1920x1080',
    only: '',
    origin: '',
  });
  const base = opts.url.replace(/\/+$/, '') + '/';
  const out = resolve(opts.out);
  mkdirSync(out, { recursive: true });
  const only = new Set(String(opts.only).split(',').map((s) => s.trim()).filter(Boolean));
  const sizes = String(opts.sizes)
    .split(',')
    .map((s) => s.trim().split('x').map(Number))
    .filter(([w, h]) => w > 0 && h > 0);
  const browser = await launchBrowser();
  const manifest = { generated_at: new Date().toISOString(), url: base, states: [] };
  try {
    for (const [w, h] of sizes) {
      for (const [i, st] of STATES.entries()) {
        if (only.size && !only.has(st.id)) continue;
        const file = `${String(i + 1).padStart(2, '0')}-${st.id}-${w}x${h}.png`;
        const context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'ko-KR' });
        await context.addInitScript(() => {
          try {
            localStorage.setItem('wfg.planner.lang', 'ko');
          } catch {
            /* ignore */
          }
        });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', (e) => errors.push(e.message));
        try {
          await st.run(page, base, opts);
          await page.screenshot({ path: join(out, file) });
          log(`ok   ${file}`);
          manifest.states.push({ state: st.id, title: st.title, size: `${w}x${h}`, file, ok: true, page_errors: errors });
        } catch (e) {
          log(`skip ${file}: ${e.message.split('\n')[0]}`);
          manifest.states.push({ state: st.id, title: st.title, size: `${w}x${h}`, file: null, ok: false, reason: e.message.split('\n')[0], page_errors: errors });
        } finally {
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
  writeFileSync(join(out, 'manifest.json'), JSON.stringify(manifest, null, 1) + '\n');
  const ok = manifest.states.filter((s) => s.ok).length;
  log(`${ok}/${manifest.states.length} screenshots written to ${out}`);
}

main().catch((e) => {
  log(e.stack || e.message);
  process.exit(1);
});
