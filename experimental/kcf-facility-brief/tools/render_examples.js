#!/usr/bin/env node
// Render saved examples to A4 PDF + PNG with network blocked, and check one-page fit.
// Usage: node tools/render_examples.js
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const { CASES } = require('./build.js');
const { fitPrint } = require('./fit_print.js');

const PAGES = ['county_before', 'county_after', 'facility_after'];

function pdfPages(file) {
  try { return Number(/Pages:\s+(\d+)/.exec(execFileSync('pdfinfo', [file]).toString())[1]); }
  catch (e) { const s = fs.readFileSync(file, 'latin1'); return (s.match(/\/Type\s*\/Page[^s]/g) || []).length; }
}
function pdfFonts(file) {
  try { return execFileSync('pdffonts', [file]).toString(); } catch (e) { return null; }
}
function pdfText(file) {
  try { return execFileSync('pdftotext', ['-layout', file, '-']).toString('utf8'); } catch (e) { return null; }
}

(async () => {
  const browser = await chromium.launch();
  const report = { rendered_at_note: 'local render, network blocked', pages: [] };
  for (const c of CASES) {
    for (const p of PAGES) {
      const html = path.join(ROOT, 'examples', c.key, p + '.html');
      const external = [];
      const pdf = path.join(ROOT, 'examples', c.key, p + '.a4.pdf');
      const fit = await fitPrint(browser, html, pdf, external);
      const ctx = await browser.newContext({ viewport: { width: 900, height: 1300 }, deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      await page.route('**/*', (route) => {
        const u = route.request().url();
        if (u.startsWith('file:') || u.startsWith('data:')) return route.continue();
        external.push(u); return route.abort();
      });
      await page.goto('file://' + html);
      await page.emulateMedia({ media: 'print' });
      const overflowX = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
      await page.emulateMedia({ media: 'screen' });
      const png = path.join(ROOT, 'examples', c.key, p + '.png');
      await page.locator('.sheet').first().screenshot({ path: png });
      const n = fit.pages;
      const txt = pdfText(pdf);
      const hangul = txt ? (txt.match(/[\uac00-\ud7a3]/g) || []).length : null;
      report.pages.push({
        case: c.key, page: p, density_start: fit.density_start, density_used: fit.density_used, pdf: path.relative(ROOT, pdf), png: path.relative(ROOT, png), pdf_pages: n,
        one_page: n === 1, horizontal_overflow: overflowX, external_requests: external,
        pdf_hangul_chars: hangul, pdf_has_exercise_label: txt ? /훈련/.test(txt) : null,
        pdf_uses_bundled_font: (() => { const f = pdfFonts(pdf); return f == null ? null : /KCFNotoSansKRSubset-Regular/.test(f) && /KCFNotoSansKRSubset-Bold/.test(f); })()
      });
      await ctx.close();
    }
  }
  await browser.close();
  report.all_one_page = report.pages.every((x) => x.one_page);
  report.no_external_requests = report.pages.every((x) => x.external_requests.length === 0);
  report.korean_text_in_pdf = report.pages.every((x) => x.pdf_hangul_chars > 200 && x.pdf_has_exercise_label);
  report.bundled_font_in_pdf = report.pages.every((x) => x.pdf_uses_bundled_font !== false);
  fs.writeFileSync(path.join(ROOT, 'examples', 'RENDER_REPORT.json'), JSON.stringify(report, null, 2) + '\n');
  for (const x of report.pages) console.log(`${x.case}/${x.page}: pages=${x.pdf_pages} overflowX=${x.horizontal_overflow} hangul=${x.pdf_hangul_chars} ext=${x.external_requests.length}`);
  console.log('all_one_page=%s no_external_requests=%s korean_text_in_pdf=%s', report.all_one_page, report.no_external_requests, report.korean_text_in_pdf);
  console.log('bundled_font_in_pdf=%s', report.bundled_font_in_pdf);
  process.exit(report.all_one_page && report.no_external_requests && report.korean_text_in_pdf && report.bundled_font_in_pdf ? 0 : 1);
})();
