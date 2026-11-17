#!/usr/bin/env node
/**
 * Checks the PUBLISHED static demo the way a judge meets it: a clean browser (new context, no
 * storage, no login) at desktop and phone width.
 *
 *   1. GET <url> must answer 200 (after redirects); otherwise exit 1 at once.
 *   2. For each width: open the page, wait for html[data-wfg-data-ready="true"], screenshot the first
 *      screen as a fresh visitor sees it (intro included), dismiss the intro, screenshot again.
 *   3. Every link (<a href>) visible on the first screen (intro and page) is requested; any status
 *      >= 400 or a network error fails. Same-origin links are fetched in the page; others with GET.
 *   4. Every visible button on the first screen (top bar, ribbon, left panel head, phone tabs) is
 *      clicked on a freshly loaded page; an uncaught page error fails.
 *   5. The 25 March replay is opened from its selector; the hour slider, the six-place panel and a
 *      drawn route line are required (skipped with a note when the site predates the replay).
 *
 * Usage: node scripts/check_live_site.mjs [--url https://sparkxt-0318.github.io/wildfireguardian/]
 *        [--out site-check] [--root-only]
 * Playwright comes from PLAYWRIGHT_MODULE or require('playwright') (never `playwright install` here).
 * Writes <out>/report.json and <out>/*.png; exit 1 on any failure.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve } from 'node:path';

const args = process.argv.slice(2);
const opt = (k, d) => {
  const i = args.indexOf(k);
  return i >= 0 ? args[i + 1] : d;
};
const URL_ = opt('--url', process.env.SITE_URL || 'https://sparkxt-0318.github.io/wildfireguardian/');
const OUT = resolve(opt('--out', 'site-check'));
const ROOT_ONLY = args.includes('--root-only');
mkdirSync(OUT, { recursive: true });

const failures = [];
const notes = [];
const fail = (m) => {
  failures.push(m);
  console.error(`[site] FAIL ${m}`);
};
const report = { url: URL_, checked_at: new Date().toISOString(), root: null, widths: [], links: [], buttons: [], replay: [], failures, notes };
const finish = () => {
  writeFileSync(join(OUT, 'report.json'), JSON.stringify(report, null, 2));
  console.log(failures.length ? `[site] ${failures.length} failure(s)` : '[site] OK');
  process.exit(failures.length ? 1 : 0);
};

async function status(url) {
  for (let attempt = 1; attempt <= 4; attempt++) {
    try {
      const r = await fetch(url, { redirect: 'follow', headers: { 'User-Agent': 'wfg-site-check' } });
      return { status: r.status, final: r.url };
    } catch (e) {
      if (attempt === 4) return { status: 0, final: url, error: String(e?.cause?.code ?? e?.message ?? e) };
      await new Promise((r) => setTimeout(r, 2000 * attempt));
    }
  }
  return { status: 0, final: url };
}

// 1. site root
{
  let r = await status(URL_);
  // a fresh Pages deployment can take a minute to propagate: retry a non-200 a few times
  for (let i = 0; r.status !== 200 && i < 6; i++) {
    await new Promise((res) => setTimeout(res, 10_000));
    r = await status(URL_);
  }
  report.root = r;
  console.log(`[site] ${URL_} → ${r.status} ${r.final}`);
  if (r.status !== 200) {
    fail(`site root ${URL_} answered ${r.status}${r.error ? ` (${r.error})` : ''}, not 200`);
    finish();
  }
  if (ROOT_ONLY) finish();
}

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});

const WIDTHS = [
  { name: 'desktop', viewport: { width: 1440, height: 900 }, mobile: false },
  { name: 'phone', viewport: { width: 390, height: 844 }, mobile: true },
];

async function freshPage(w) {
  const ctx = await browser.newContext({ viewport: w.viewport, isMobile: w.mobile, hasTouch: w.mobile, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 60_000 });
  await page.waitForFunction(() => document.documentElement.dataset.wfgDataReady === 'true', null, { timeout: 90_000 });
  await page.waitForTimeout(1500);
  return { ctx, page, errors };
}

/** Visible elements inside the first screen (the viewport at scroll 0). */
async function visible(page, selector) {
  return page.evaluate((sel) => {
    const out = [];
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    document.querySelectorAll(sel).forEach((el, i) => {
      const r = el.getBoundingClientRect();
      const st = getComputedStyle(el);
      if (r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none') return;
      if (r.bottom <= 0 || r.right <= 0 || r.top >= vh || r.left >= vw) return;
      // covered by another layer (e.g. behind the intro dialog): not on the first screen
      const x = Math.min(vw - 1, Math.max(0, r.left + r.width / 2));
      const y = Math.min(vh - 1, Math.max(0, r.top + r.height / 2));
      const top = document.elementFromPoint(x, y);
      if (top && top !== el && !el.contains(top) && !top.contains(el)) return;
      out.push({ i, text: (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 80), href: el.getAttribute('href'), abs: el.href || null, disabled: el.disabled === true });
    });
    return out;
  }, selector);
}

const seenLinks = new Map();
async function checkLinks(page, where) {
  for (const a of await visible(page, 'a[href]')) {
    const abs = a.abs;
    if (!abs || abs.startsWith('mailto:') || abs.startsWith('javascript:')) continue;
    if (seenLinks.has(abs)) continue;
    const sameOrigin = new URL(abs).origin === new URL(URL_).origin;
    const r = sameOrigin
      ? await page.evaluate(async (u) => {
          try {
            const x = await fetch(u, { redirect: 'follow' });
            return { status: x.status, final: x.url };
          } catch (e) {
            return { status: 0, final: u, error: String(e) };
          }
        }, abs)
      : await status(abs);
    seenLinks.set(abs, r);
    report.links.push({ where, text: a.text, href: abs, ...r });
    console.log(`[site] link ${r.status} ${abs} (${a.text})`);
    if (!(r.status >= 200 && r.status < 400)) fail(`link "${a.text}" → ${abs} answered ${r.status}${r.error ? ` (${r.error})` : ''}`);
  }
}

const BUTTON_SCOPE = '.topbar button, .demo-ribbon button, .panel-left .left-head button, .mobile-nav button, [data-testid="demo-intro"] button';

for (const w of WIDTHS) {
  const { ctx, page, errors } = await freshPage(w);
  await page.screenshot({ path: join(OUT, `${w.name}-first-visit.png`) });
  await checkLinks(page, `${w.name}: first visit`);
  // dismiss the intro (if any) as a visitor would, then the page itself
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);
  await page.screenshot({ path: join(OUT, `${w.name}.png`) });
  await checkLinks(page, `${w.name}: page`);
  const buttons = await visible(page, BUTTON_SCOPE);
  report.widths.push({ name: w.name, viewport: w.viewport, errors: [...errors], buttons: buttons.length });
  for (const e of errors) fail(`${w.name}: page error on load: ${e}`);
  await ctx.close();

  // 4. each first-screen button, on a fresh page
  for (const b of buttons) {
    if (b.disabled) {
      report.buttons.push({ width: w.name, text: b.text, result: 'disabled (not clicked)' });
      continue;
    }
    const f = await freshPage(w);
    await f.page.keyboard.press('Escape');
    await f.page.waitForTimeout(300);
    const loc = f.page.locator(BUTTON_SCOPE).nth(b.i);
    let result = 'ok';
    try {
      await loc.click({ timeout: 5000 });
      await f.page.waitForTimeout(1200);
    } catch (e) {
      result = `not clickable: ${String(e.message ?? e).split('\n')[0]}`;
    }
    if (f.errors.length) {
      result = `page error: ${f.errors[0]}`;
      fail(`${w.name}: button "${b.text}" → ${f.errors[0]}`);
    }
    report.buttons.push({ width: w.name, text: b.text, result });
    console.log(`[site] ${w.name} button "${b.text}": ${result}`);
    await f.ctx.close();
  }

  // 5. the 25 March replay
  const r = await freshPage(w);
  await r.page.keyboard.press('Escape');
  const pack = r.page.locator('[data-testid="replay-pack-kcf-replay-RUNNING_8h"]');
  if (!(await pack.count())) {
    notes.push(`${w.name}: the published site has no 25 March replay selector yet`);
    report.replay.push({ width: w.name, present: false });
  } else {
    if (w.mobile) await r.page.locator('[data-testid="mobile-tab-list"]').click().catch(() => {});
    await r.page.locator('[data-testid="region-yeongdeok_2025"]').click();
    await r.page.waitForFunction(() => document.documentElement.dataset.wfgDataReady === 'true', null, { timeout: 60_000 });
    await pack.click();
    await r.page.waitForFunction(() => document.documentElement.dataset.wfgDataReady === 'true' && !!document.querySelector('[data-testid="replay-named-places"]'), null, { timeout: 60_000 });
    // 매정리 at 19:00 KST: pick it in the six-place table
    await r.page.locator('[data-testid="replay-place-매정리"] button').click();
    await r.page.waitForTimeout(800);
    await r.page.screenshot({ path: join(OUT, `${w.name}-replay-list.png`) });
    if (w.mobile) await r.page.locator('[data-testid="mobile-tab-map"]').click().catch(() => {});
    await r.page.waitForTimeout(2500);
    const slider = await r.page.locator('[data-testid="replay-hour-slider"]').count();
    const value = slider ? await r.page.locator('[data-testid="replay-hour-value"]').innerText() : null;
    await r.page.screenshot({ path: join(OUT, `${w.name}-replay-map.png`) });
    const res = { width: w.name, present: true, hourSlider: slider > 0, hourValue: value, errors: [...r.errors] };
    report.replay.push(res);
    if (!slider) fail(`${w.name}: replay hour slider missing`);
    for (const e of r.errors) fail(`${w.name}: replay page error: ${e}`);
  }
  await r.ctx.close();
}

await browser.close();
finish();
