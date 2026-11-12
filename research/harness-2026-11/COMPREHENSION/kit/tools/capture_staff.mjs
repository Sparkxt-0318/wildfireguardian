#!/usr/bin/env node
/**
 * Captures the two STAFF surfaces of each found case from the real planner static build, in headless Chromium:
 *   - the staff headline: the right panel's [data-testid="headline"] of the selected origin (text + element PNG);
 *   - the A4 plan sheet: the plan-sheet dialog's page of that origin (text + one-page A4 PDF, as
 *     planner/scripts/export_plan_pdfs.mjs prints it; the other origins' pages are hidden so only this one prints).
 * Nothing is recomputed or reworded: the app shows what it loads from planner/cache.
 *
 * Usage (from the repository root, after `cd planner && npm run build:static`):
 *   node planner/scripts/serve_static.mjs --dir dist --base / --port 4180 &   (run from planner/)
 *   node research/harness-2026-11/COMPREHENSION/kit/tools/capture_staff.mjs [--url http://127.0.0.1:4180/] [--check]
 *
 * The page clock is fixed at CASES.json now_iso (the A4 sheet prints its own "작성 시각"), so the text captures are
 * reproducible. --check writes nothing: it captures again and fails on any byte difference in headline.ko.txt and
 * a4.ko.txt (PNG and PDF bytes carry renderer metadata and are not compared; they are pictures of the same page).
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const KIT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CHECK = process.argv.includes('--check');
const argUrl = process.argv.indexOf('--url');
const BASE = argUrl > 0 ? process.argv[argUrl + 1] : 'http://127.0.0.1:4180/';
const req = createRequire(join(process.cwd(), 'planner', 'package.json'));
let chromium;
try {
  chromium = req('playwright').chromium;
} catch {
  chromium = createRequire(import.meta.url)('playwright').chromium;
}

const CASES = JSON.parse(readFileSync(join(KIT, 'CASES.json'), 'utf8'));
const cases = CASES.cases.filter((c) => c.found);
const compact = (iso) => iso.replace(/[-:]/g, '').replace(/\.\d+/, '').replace(/Z$/, 'Z');
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2, locale: 'ko-KR', timezoneId: 'Asia/Seoul' });
const page = await ctx.newPage();
await page.clock.setFixedTime(new Date(CASES.now_iso));
const diffs = [];
function put(path, body) {
  if (!CHECK) return writeFileSync(path, body);
  let old = null;
  try {
    old = readFileSync(path, 'utf8');
  } catch {}
  if (old !== body) diffs.push(path);
}
const fail = [];
page.on('pageerror', (e) => fail.push(String(e)));

async function ready() {
  await page.waitForFunction(() => document.documentElement.dataset.wfgDataReady === 'true', null, { timeout: 120000 });
  await page.waitForTimeout(1000);
}

for (const c of cases) {
  const out = join(KIT, 'items', c.case);
  mkdirSync(out, { recursive: true });
  const q = new URLSearchParams({ region: c.region, scenario: compact(c.input_time), origin: c.origin_id, lang: 'ko' });
  // 1. staff headline
  await page.goto(`${BASE}?${q}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await ready();
  const h = page.locator('[data-testid="headline"]').first();
  await h.waitFor({ state: 'visible', timeout: 30000 });
  const title = (await page.locator('[data-testid="rp-title"]').first().innerText()).trim();
  put(join(out, 'headline.ko.txt'), (await h.innerText()).replace(/\r\n/g, '\n').trim() + '\n');
  if (!CHECK) await h.screenshot({ path: join(out, 'headline.ko.png') });
  // 2. A4 plan sheet (print-all mode renders every page; only this origin's page is printed)
  q.delete('origin');
  await page.goto(`${BASE}?print=all&${q}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await ready();
  await page.waitForSelector('.wfgf-plansheet-root[data-wfg-sheets-ready="true"]', { timeout: 600000 });
  await page.waitForTimeout(1500);
  const sheet = page.locator(`.wfgf-sheet[data-sheet-origin="${c.origin_id}"]`);
  put(join(out, 'a4.ko.txt'), (await sheet.innerText()).replace(/\r\n/g, '\n').trim() + '\n');
  await page.addStyleTag({ content: `.wfgf-sheet:not([data-sheet-origin="${c.origin_id}"]){display:none!important}` });
  if (!CHECK) await page.pdf({ path: join(out, 'a4.ko.pdf'), format: 'A4', printBackground: true, preferCSSPageSize: true, margin: { top: '0', right: '0', bottom: '0', left: '0' } });
  console.log(`${c.case} ${c.origin_id} panel title "${title}" ok`);
}
await browser.close();
if (diffs.length) {
  console.error('differs from the committed capture:\n' + diffs.join('\n'));
  process.exit(1);
}
if (CHECK) console.log('check: every headline.ko.txt and a4.ko.txt is byte-identical to a fresh capture');
if (fail.length) {
  console.error('page errors:\n' + fail.join('\n'));
  process.exit(1);
}
