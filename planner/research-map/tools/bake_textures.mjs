#!/usr/bin/env node
// Pre-builds each region's static terrain textures so the page decodes images instead of drawing them on every first visit.
//
//   node tools/bake_textures.mjs [region ...]      (default: every region in site/regions/index.js)
//
// Opens site/index.html#region=<id>&bake=1 in headless Chromium, lets the page draw its textures with its own code, and
// writes site/regions/<id>.tex.js. The page uses that file only while its key matches the region data (else it draws).
// Playwright: PLAYWRIGHT_MODULE=/path/to/node_modules/playwright, else the planner's node_modules; CHROMIUM_PATH optional.
import { createRequire } from 'module';
import { existsSync, mkdirSync, readdirSync, readFileSync, unlinkSync, writeFileSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SITE = join(ROOT, 'site');
const PLANNER = resolve(ROOT, '..');

function loadChromium() {
  const req = createRequire(join(PLANNER, 'package.json'));
  const names = [process.env.PLAYWRIGHT_MODULE && resolve(process.env.PLAYWRIGHT_MODULE), 'playwright', 'playwright-core'].filter(Boolean);
  for (const n of names) { try { const m = req(n); const c = m.chromium || (m.default && m.default.chromium); if (c) return c; } catch (e) { } }
  throw new Error('Playwright not found: npm i playwright in a scratch dir and set PLAYWRIGHT_MODULE=/path/to/node_modules/playwright');
}

const index = readFileSync(join(SITE, 'regions/index.js'), 'utf8');
const all = JSON.parse(index.slice(index.indexOf('=') + 1).trim().replace(/;$/, '')).map(r => r.id);
const regions = process.argv.slice(2).length ? process.argv.slice(2) : all;
const chromium = loadChromium();
const exe = process.env.CHROMIUM_PATH || (existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined);
const browser = await chromium.launch({ executablePath: exe, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
for (const id of regions) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = []; page.on('pageerror', e => errors.push(String(e)));
  const t0 = Date.now();
  await page.goto(pathToFileURL(join(SITE, 'index.html')).href + `#region=${id}&bake=1`, { waitUntil: 'commit' });
  await page.waitForSelector('#loading', { state: 'detached', timeout: 600000 });
  if (errors.length) throw new Error(`${id}: ${errors[0]}`);
  const tex = await page.evaluate(() => window.__bakeTextures());
  // the mask carries the land-cover codes and the forest mask: it must decode to exactly what the page computed
  const same = await page.evaluate(async url => {
    const im = new Image(); im.src = url; await im.decode(); const c = document.createElement('canvas'); c.width = im.width; c.height = im.height;
    const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(im, 0, 0); const d = x.getImageData(0, 0, c.width, c.height).data;
    let s = ''; for (let i = 0; i < d.length; i += 4) s += Math.round(d[i] / 40) * 2 + (d[i + 1] > 127 ? 1 : 0); return s === window.__maskCodes();
  }, tex.mask);
  if (!same) throw new Error(`${id}: the WebP mask does not decode to the page's land-cover codes`);
  // binary image files next to a small key file: smaller than base64, cached and decoded off the main thread
  const dir = join(SITE, 'regions', id); mkdirSync(dir, { recursive: true });
  for (const f of readdirSync(dir)) unlinkSync(join(dir, f));
  const ref = { key: tex.key }; let kb = 0;
  for (const k of ['ground', 'hs', 'ctxReal', 'ctxTopo', 'mask']) {
    const [head, b64] = tex[k].split(','), ext = head.match(/image\/(\w+)/)[1].replace('jpeg', 'jpg'), buf = Buffer.from(b64, 'base64');
    writeFileSync(join(dir, `${k}.${ext}`), buf); ref[k] = `regions/${id}/${k}.${ext}`; kb += buf.length / 1024;
  }
  await page.close();
  // the opening view as a picture, taken from a normal visit with the new textures once its later layers are in
  writeFileSync(join(SITE, 'regions', `${id}.tex.js`), `(window.WFG_TEX=window.WFG_TEX||{})[${JSON.stringify(id)}]=${JSON.stringify(ref)};\n`);
  const view = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await view.goto(pathToFileURL(join(SITE, 'index.html')).href + `#region=${id}`, { waitUntil: 'commit' });
  await view.waitForSelector('#loading', { state: 'detached', timeout: 600000 }); await view.waitForTimeout(6000);
  const poster = Buffer.from((await view.evaluate(() => window.__wfgPoster())).split(',')[1], 'base64');
  await view.close();
  writeFileSync(join(dir, 'poster.webp'), poster); ref.poster = `regions/${id}/poster.webp`; kb += poster.length / 1024;
  const out = join(SITE, 'regions', `${id}.tex.js`);
  writeFileSync(out, `(window.WFG_TEX=window.WFG_TEX||{})[${JSON.stringify(id)}]=${JSON.stringify(ref)};\n`);
  kb = Math.round(kb);
  console.log(`${id}: ${kb} kB, key ${tex.key} (${((Date.now() - t0) / 1000).toFixed(1)} s)`);
}
await browser.close();
