// Print a static brief page to A4 PDF; if it spills past one page, step the density class up
// (density-0 … density-3), rewrite the HTML with the fitted class and print again.
'use strict';
const fs = require('fs');
const { execFileSync } = require('child_process');

function pdfPages(file) {
  try { return Number(/Pages:\s+(\d+)/.exec(execFileSync('pdfinfo', [file]).toString())[1]); }
  catch (e) { return (fs.readFileSync(file, 'latin1').match(/\/Type\s*\/Page[^s]/g) || []).length; }
}

async function fitPrint(browser, htmlPath, pdfPath, external) {
  const original = fs.readFileSync(htmlPath, 'utf8');
  const m = /class="sheet ([a-z-]+) density-(\d)"/.exec(original);
  let level = m ? Number(m[2]) : 0;
  const start = level;
  let pages = null;
  for (;;) {
    const page = await browser.newPage();
    await page.route('**/*', (rt) => {
      const u = rt.request().url();
      if (u.startsWith('file:') || u.startsWith('data:')) return rt.continue();
      if (external) external.push(u);
      return rt.abort();
    });
    await page.goto('file://' + htmlPath);
    await page.pdf({ path: pdfPath, format: 'A4', printBackground: true, preferCSSPageSize: true });
    await page.close();
    pages = pdfPages(pdfPath);
    if (pages <= 1 || level >= 3 || !m) break;
    level += 1;
    fs.writeFileSync(htmlPath, original.replace(/(class="sheet [a-z-]+ )density-\d/, '$1density-' + level));
  }
  return { pages, density_start: start, density_used: level };
}
module.exports = { fitPrint, pdfPages };
