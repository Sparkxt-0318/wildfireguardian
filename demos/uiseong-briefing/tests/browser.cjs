// Run with Playwright and an installed Chromium. Opens the checked-in HTML via file://.
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

const entry = pathToFileURL(path.resolve(__dirname, '../index.html')).href;
const utcContext = { timezoneId: 'UTC', locale: 'en-US' }; // the interface's clock is Korean time
const stretchesMarch24 = [
  Array.from({ length: 6 }, (_, i) => 'w30043764:s' + (5 + i)),
  Array.from({ length: 11 }, (_, i) => 'w30043764:s' + (15 + i)),
];

async function run(browser) {
  const errors = [];
  const remote = [];
  const context = await browser.newContext({
    ...utcContext,
    viewport: { width: 1280, height: 800 },
    offline: true,
  });
  context.on('request', (request) => {
    if (/^https?:/.test(request.url())) remote.push(request.url());
  });
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  page.on('pageerror', (error) => errors.push(String(error)));
  const click = (id) => page.locator(id).click();
  const text = (id) => page.locator(id).innerText();
  const value = (id) => page.locator(id).inputValue();
  async function integer(id, expected) {
    assert.equal((await text(id)).trim(), String(expected), id);
  }
  async function selectedIds() {
    return page
      .locator('#layer-selection [data-selected-id]')
      .evaluateAll((nodes) => nodes.map((node) => node.dataset.selectedId).sort());
  }
  async function reviewAt(kst) {
    if (!(await page.locator('#review-at').isVisible()))
      await page.locator('details.custom-time > summary').click();
    await page.locator('#review-at').fill('2025-03-24T' + kst);
    await click('#apply-time');
  }
  try {
    await page.goto(entry);
    await click('#start-example');
    assert.match(await value('#review-at'), /2025-03-24T12:44/);
    await integer('#watch-count', 0);
    await click('#mark-reviewed');
    await click('#next');
    assert.match(await value('#review-at'), /2025-03-24T13:07/);
    assert.match(await text('#reviewed-label'), /12:44/);
    await integer('#new-count', 187);
    await integer('#watch-count', 17);
    assert.equal(await page.locator('#layer-hotspots [data-detection]').count(), 41);
    const choices = page.locator('#stretch-list button');
    assert.equal(await choices.count(), 2);
    for (const label of await choices.allTextContents()) assert.match(label, /신감옥산로/);

    // These two separated portions of one named road must stay distinct.
    const actual = [];
    for (let i = 0; i < 2; ++i) {
      await choices.nth(i).click();
      actual.push((await selectedIds()).join(','));
      const markers = await page
        .locator('#layer-selection g[data-marker]')
        .evaluateAll((nodes) =>
          nodes.map((node) => [node.dataset.marker, node.getAttribute('transform')]),
        );
      assert.deepEqual(markers.map(([name]) => name).sort(), ['A', 'B']);
      assert.notEqual(markers[0][1], markers[1][1]);
    }
    assert.deepEqual(actual.sort(), stretchesMarch24.map((ids) => [...ids].sort().join(',')).sort());

    await click('#age-15');
    assert.match(await value('#review-at'), /2025-03-24T13:22/);
    assert.match(await text('#age'), /15\s*분/);
    await integer('#watch-count', 17);
    assert.equal(await page.locator('#layer-forecast rect[data-category]').count(), 0);
    assert.match(await text('#forecast-status'), /없|미제공|미수록/);
    // Select the stretch to brief, edit the local note, and locate its exact map geometry.
    await choices.first().click();
    const intended = await selectedIds();
    assert.match(await value('#radio-text'), /신감옥산로/);
    const edited = (await value('#radio-text')) + ' 훈련용 확인 문구.';
    await page.locator('#radio-text').fill(edited);
    await choices.nth(1).click();
    assert.notDeepEqual(await selectedIds(), intended);
    assert.notEqual(await value('#radio-text'), edited, 'draft leaked to a different stretch');
    await choices.first().click();
    await click('#radio-locate');
    assert.deepEqual(await selectedIds(), intended);
    assert.equal(await value('#radio-text'), edited);

    // Exercise the actual print button without opening an OS print dialog; then run
    // Chromium's PDF compositor and ensure it produces one nonempty printable page.
    await page.evaluate(() => {
      window.__printCalls = 0;
      window.print = () => {
        window.__printCalls++;
      };
    });
    await click('#print');
    assert.equal(await page.evaluate(() => window.__printCalls), 1);
    await page.emulateMedia({ media: 'print' });
    assert.ok(await page.locator('#map').isVisible());
    assert.ok((await text('#paper')).includes('훈련용 확인 문구.'), 'print omits edited draft');
    const print = await page.pdf({ printBackground: true, preferCSSPageSize: true });
    assert.equal(print.subarray(0, 5).toString(), '%PDF-');
    assert.equal((print.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length, 1);
    await page.emulateMedia({ media: 'screen' });
    assert.equal(await value('#radio-text'), edited);

    // Comparing 14:25 to 12:44 yields 97 new segments. Comparing 14:25
    // to the immediately preceding 13:07 observation instead yields 53.
    await click('#next');
    assert.match(await value('#review-at'), /2025-03-24T14:25/);
    assert.match(await text('#reviewed-label'), /12:44/);
    assert.doesNotMatch(await value('#radio-text'), /훈련용 확인 문구/);
    await integer('#new-count', 97);
    await click('#reset-baseline');
    await integer('#new-count', 53);

    // One of the three hourly forecasts starts and expires between satellite passes.
    // Its presence cannot be determined just by comparing to the acquisition time.
    await reviewAt('17:59');
    assert.equal(await page.locator('#layer-forecast rect[data-category]').count(), 0);
    await reviewAt('18:00');
    assert.equal(await page.locator('#layer-forecast rect[data-category]').count(), 702);
    await reviewAt('18:59');
    assert.equal(await page.locator('#layer-forecast rect[data-category]').count(), 702);
    await reviewAt('19:00');
    assert.equal(await page.locator('#layer-forecast rect[data-category]').count(), 0);

    await page.setViewportSize({ width: 390, height: 844 });
    await click('#start-example');
    await click('#mark-reviewed');
    await click('#next');
    await choices.first().click();
    await click('#radio-locate');
    await integer('#watch-count', 17);
    assert.ok(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
      'mobile layout overflows horizontally',
    );
    await click('#age-15');
    await click('#mark-reviewed'); // review happened at 13:22, after acquisition
    assert.match(await text('#review-log'), /13:22/);
    await reviewAt('13:07');
    assert.match(await text('#reviewed-label'), /직전 관측/);
    await integer('#new-count', 187);
    assert.deepEqual(errors, []);
    assert.deepEqual(remote, []);
    console.log(
      'PASS · March 24 briefing, reviewed baseline, both exact stretches, forecast validity, radio, one-page print, offline and mobile.',
    );
  } finally {
    await context.close();
  }
}

(async () => {
  const opts = { headless: true };
  if (process.env.WFG_CHROME_CHANNEL) opts.channel = process.env.WFG_CHROME_CHANNEL;
  if (process.env.WFG_CHROMIUM) opts.executablePath = process.env.WFG_CHROMIUM;
  const browser = await chromium.launch(opts);
  try {
    await run(browser);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
