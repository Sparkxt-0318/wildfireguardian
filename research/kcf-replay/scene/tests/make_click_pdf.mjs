// Renders research/kcf-replay/scene/CLICK_SCRIPT.md to a one-page A4 landscape PDF (CLICK_SCRIPT.pdf) with Playwright
// (the body size steps down from 10.4 pt to fit one page; it fails below 8.6 pt).
// The markdown is small and regular (headings, one table, bold, code), so a tiny converter is enough.
//   node research/kcf-replay/scene/tests/make_click_pdf.mjs
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const here = dirname(fileURLToPath(import.meta.url));
const dir = resolve(here, '..');
const md = readFileSync(join(dir, 'CLICK_SCRIPT.md'), 'utf8');

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const inline = (s) => esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
let html = '', inTable = false, para = [];
const flush = () => { if (para.length) { html += '<p>' + inline(para.join(' ')) + '</p>'; para = []; } };
for (const line of md.split('\n')) {
  if (/^# /.test(line)) { flush(); html += '<h1>' + inline(line.slice(2)) + '</h1>'; continue; }
  if (/^\|/.test(line)) {
    flush();
    const cells = line.split('|').slice(1, -1).map((c) => c.trim());
    if (cells.every((c) => /^-+$/.test(c))) continue;
    if (!inTable) { html += '<table><tr>' + cells.map((c) => '<th>' + inline(c) + '</th>').join('') + '</tr>'; inTable = true; continue; }
    html += '<tr>' + cells.map((c) => '<td>' + inline(c) + '</td>').join('') + '</tr>';
    continue;
  }
  if (inTable) { html += '</table>'; inTable = false; }
  if (!line.trim()) { flush(); continue; }
  para.push(line.trim());
}
flush(); if (inTable) html += '</table>';

const page = `<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: A4 landscape; margin: 9mm 10mm; }
body { font-family: 'Noto Sans CJK KR', 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; font-size: 10.4pt; line-height: 1.32; color: #111; }
h1 { font-size: 15pt; margin: 0 0 4px; }
p { margin: 3px 0; }
table { border-collapse: collapse; width: 100%; margin: 5px 0; }
th, td { border: 1px solid #999; padding: 2px 4px; vertical-align: top; text-align: left; }
th { background: #eee; }
td:first-child { width: 14px; text-align: center; font-weight: 700; }
td:nth-child(2) { width: 17%; } td:nth-child(3) { width: 38%; }
code { font-family: Menlo, Consolas, monospace; font-size: 9.4pt; background: #f1f1f1; padding: 0 2px; }
</style></head><body>${html}</body></html>`;
mkdirSync(join(dir, 'tests', 'out'), { recursive: true });
writeFileSync(join(dir, 'tests', 'out', 'click_script.html'), page);
const browser = await chromium.launch();
const p = await browser.newPage();
await p.setContent(page, { waitUntil: 'load' });
// Korean glyphs: use the scene's own UI font subset if the system has no Korean font
const fonts = readFileSync(resolve(dir, '../../../planner/public/kcf-scene/data/fonts.js'), 'utf8');
const m = /"src":"(data:font\/woff2;base64,[^"]+)"/.exec(fonts);
if (m) await p.addStyleTag({ content: `@font-face { font-family: 'KCF UI Sans'; src: url(${m[1]}); font-weight: 45 930; } body { font-family: 'KCF UI Sans', 'Noto Sans CJK KR', sans-serif; }` });
await p.evaluate(() => document.fonts.ready);
// one page: step the body size down from 10.4 pt until the PDF has a single page (floor 8.6 pt, still readable)
const pages = (buf) => (buf.toString('latin1').match(/\/Type\s*\/Page[^s]/g) || []).length;
let size = 10.4, buf;
for (;;) {
  await p.evaluate((pt) => { document.body.style.fontSize = pt + 'pt'; document.querySelectorAll('code').forEach((c) => { c.style.fontSize = (pt - 1) + 'pt'; }); }, size);
  buf = await p.pdf({ format: 'A4', landscape: true, printBackground: true });
  if (pages(buf) <= 1 || size <= 8.6) break;
  size = Math.round((size - 0.2) * 10) / 10;
}
writeFileSync(join(dir, 'CLICK_SCRIPT.pdf'), buf);
await browser.close();
console.log('wrote CLICK_SCRIPT.pdf:', pages(buf), 'page(s) at', size, 'pt');
if (pages(buf) > 1) { console.error('CLICK_SCRIPT.md does not fit one page at 8.6 pt: shorten it'); process.exit(1); }
