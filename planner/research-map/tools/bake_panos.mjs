#!/usr/bin/env node
// Bakes the Kakao road view photo IDs along each region's 길 안내 routes, so the page never looks them up while it is used.
//
//   node tools/bake_panos.mjs [region ...]      (default: every region in site/regions/index.js)
//
// Needs the site served at http://127.0.0.1:8840 (any static server on site/) and a Kakao JavaScript key registered for
// that address in site/kakao-keys.js. Opens each region with #bakepano=1 (the page then looks every 30 m stop up afresh),
// waits until all are answered and writes site/regions/<id>.pano.js: the nearest photo ID per stop, null where there is
// none within 50 m. Only IDs are kept, no photos.
// Playwright: PLAYWRIGHT_MODULE=/path/to/node_modules/playwright, else the planner's node_modules; CHROMIUM_PATH optional;
// HTTPS_PROXY is passed to Chromium when set.
import { createRequire } from 'module';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SITE = join(ROOT, 'site');
const PLANNER = resolve(ROOT, '..');
const BASE = process.env.BAKE_BASE || 'http://127.0.0.1:8840';

function loadChromium() {
  const req = createRequire(join(PLANNER, 'package.json'));
  const names = [process.env.PLAYWRIGHT_MODULE && resolve(process.env.PLAYWRIGHT_MODULE), 'playwright', 'playwright-core'].filter(Boolean);
  for (const n of names) { try { const m = req(n); const c = m.chromium || (m.default && m.default.chromium); if (c) return c; } catch (e) { } }
  throw new Error('Playwright not found: npm i playwright in a scratch dir and set PLAYWRIGHT_MODULE=/path/to/node_modules/playwright');
}

const index = readFileSync(join(SITE, 'regions/index.js'), 'utf8');
const all = JSON.parse(index.slice(index.indexOf('=') + 1).trim().replace(/;$/, '')).map(r => r.id);
const regions = process.argv.slice(2).length ? process.argv.slice(2) : all;
const exe = process.env.CHROMIUM_PATH || (existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined);
const args = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'];
if (process.env.HTTPS_PROXY) args.push('--proxy-server=' + process.env.HTTPS_PROXY);
const browser = await loadChromium().launch({ executablePath: exe, args });

for (const id of regions) {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage();
  // Kakao's script asks for its next files with the page's own scheme; over plain http on 127.0.0.1 ask https instead
  await page.route(/^http:\/\/(?!127\.0\.0\.1|localhost)/, async r => { try { await r.fulfill({ response: await r.fetch({ url: r.request().url().replace(/^http:/, 'https:') }) }); } catch { await r.abort(); } });
  await page.goto(`${BASE}/#region=${id}&bakepano=1`);
  await page.waitForSelector('#loading', { state: 'detached', timeout: 120000 });
  if (await page.evaluate(() => window.__wfg && window.__wfg.RID) !== id) throw new Error(`${id}: the page opened another region`);
  let st = null;
  for (let i = 0; i < 600; i++) {
    await page.waitForTimeout(2000);
    st = await page.evaluate(() => window.__navPano && window.__navPano());
    if (!st || !st.case) break;
    const done = st.pols.length && st.pols.every(p => Array.isArray(st.ids[p]) && st.ids[p].every(v => v !== undefined));
    if (done && st.left === 0) break;
  }
  if (!st || !st.case) { console.log(`${id}: no navigation case`); await page.context().close(); continue; }
  const out = { case: st.case };
  for (const p of st.pols) out[p] = st.ids[p].map(v => v === undefined ? null : v);
  writeFileSync(join(SITE, 'regions', `${id}.pano.js`), `(window.WFG_PANO=window.WFG_PANO||{})[${JSON.stringify(id)}]=${JSON.stringify(out)};\n`);
  console.log(`${id}: ${st.pols.map(p => `${p} ${out[p].filter(v => v != null).length}/${out[p].length} stops with a photo`).join(', ')}`);
  await page.context().close();
}
await browser.close();
