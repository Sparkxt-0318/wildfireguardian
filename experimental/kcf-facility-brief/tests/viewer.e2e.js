#!/usr/bin/env node
// Offline browser check of viewer.html: network blocked, view switching, stale-value
// clearing, rejection display, view agreement, one-page A4 print of each view.
// Usage: node tests/viewer.e2e.js     (requires a prior `node tools/build.js`)
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');
const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(ROOT, 'qa');
fs.mkdirSync(OUT, { recursive: true });

const results = [];
function check(name, cond, detail) { results.push({ name, pass: !!cond, detail: detail === undefined ? null : detail }); }

async function activeVals(page) {
  return page.evaluate(() => {
    const o = {};
    document.querySelectorAll('.sheet.active [data-k]').forEach((e) => { o[e.getAttribute('data-k')] = e.textContent; });
    return o;
  });
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 1400 }, deviceScaleFactor: 1 });
  const external = [];
  await ctx.route('**/*', (route) => {
    const u = route.request().url();
    if (u.startsWith('file:') || u.startsWith('data:') || u.startsWith('blob:')) return route.continue();
    external.push(u); return route.abort();
  });
  const page = await ctx.newPage();
  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  const url = 'file://' + path.join(ROOT, 'viewer.html');
  await page.goto(url);

  check('launches offline and renders', (await page.getAttribute('body', 'data-rendered')) === 'ok');
  let v = await activeVals(page);
  check('default: delayed case, county view, final unload unknown', v.final_unload === '모름' && v.case_id === 'KCF-EX-DELAY-01', v.final_unload);
  const fontState = await page.evaluate(async () => {
    await document.fonts.ready;
    return ['400', '700'].map((w) => document.fonts.check(`${w} 16px "KCF Noto Sans KR Subset"`, '훈련'))
      .concat([Array.from(document.fonts).filter((f) => f.family.includes('KCF Noto Sans KR Subset') && f.status === 'loaded').length]);
  });
  check('bundled Korean font (regular + bold) loads offline from data URI', fontState[0] && fontState[1] && fontState[2] === 2, fontState);
  check('exercise label visible on screen', await page.locator('.sheet.active .band').isVisible());
  await page.screenshot({ path: path.join(OUT, 'viewer_county_delayed.png') });

  // before → after → before: the displayed time must follow the loaded data every time
  await page.check('#beforeOnly');
  v = await activeVals(page);
  check('before-only shows baseline number', v.final_unload === 'T0+34분 (14:34)' && v.unconfirmed === '0', v.final_unload);
  await page.uncheck('#beforeOnly');
  v = await activeVals(page);
  check('after re-toggle the old number is gone from current fields', v.final_unload === '모름' && v.unconfirmed === '4' && v['prev:final_unload'] === 'T0+34분 (14:34)', v);

  // facility view
  await page.click('[data-view-btn="facility"]');
  check('facility view active', (await page.getAttribute('.sheet.active', 'data-view')) === 'facility');
  await page.screenshot({ path: path.join(OUT, 'viewer_facility_delayed.png') });

  // two views agree on all shared fields (for each case)
  for (const c of ['delayed_vehicle', 'unknown_input', 'destination_pending']) {
    await page.selectOption('#caseSel', c);
    const mismatch = await page.evaluate(() => {
      const get = (sel) => { const o = {}; document.querySelectorAll(sel + ' [data-k]').forEach((e) => { o[e.getAttribute('data-k')] = e.textContent; }); return o; };
      const f = get('.sheet[data-view=facility]'), k = get('.sheet[data-view=county]');
      const shared = Object.keys(f).filter((x) => x in k);
      return { n: shared.length, bad: shared.filter((x) => f[x] !== k[x]) };
    });
    check(`views agree (${c})`, mismatch.n >= 10 && mismatch.bad.length === 0, mismatch);
  }

  // updated time case
  await page.selectOption('#caseSel', 'destination_pending');
  await page.click('[data-view-btn="county"]');
  v = await activeVals(page);
  check('updated time shown; previous only as prev', v.final_unload === 'T0+44분 (16:44)' && v['prev:final_unload'] === 'T0+35분 (16:35)', v.final_unload);

  // load a different-case revised file through the real file input → rejection, nothing stale left
  await page.setInputFiles('#fRevised', path.join(ROOT, 'fixtures/delayed_vehicle/revised.json'));
  await page.waitForFunction(() => document.body.getAttribute('data-rendered') === 'error');
  const errText = await page.locator('#out').innerText();
  check('different-case revised rejected with message', /다른 사례끼리 비교 불가/.test(errText));
  check('no brief numbers left after rejection', !/T0\+44분|T0\+35분/.test(errText) && (await page.locator('.sheet[data-view=county]').count()) === 0);

  // stale final unload file rejected
  await page.selectOption('#caseSel', 'delayed_vehicle');
  await page.setInputFiles('#fRevised', path.join(ROOT, 'fixtures/invalid/stale_final_unload.revised.json'));
  await page.waitForFunction(() => document.body.getAttribute('data-rendered') === 'error');
  check('stale final_unload file rejected', /final_unload_s 가 숫자임/.test(await page.locator('#out').innerText()));
  await page.setInputFiles('#fRevised', path.join(ROOT, 'fixtures/invalid/unload_before_depart.revised.json'));
  await page.waitForFunction(() => /출발 시각/.test(document.getElementById('out').innerText));
  check('impossible timestamp file rejected', (await page.getAttribute('body', 'data-rendered')) === 'error');
  await page.setInputFiles('#fMeta', path.join(ROOT, 'fixtures/invalid/reversed_update_times.meta.json'));
  await page.setInputFiles('#fRevised', path.join(ROOT, 'fixtures/delayed_vehicle/revised.json'));
  await page.waitForFunction(() => /갱신 시각 순서 오류/.test(document.getElementById('out').innerText));
  check('reversed update times rejected', true);
  // recover with valid files
  await page.setInputFiles('#fMeta', path.join(ROOT, 'fixtures/delayed_vehicle/briefing_meta.json'));
  await page.waitForFunction(() => document.body.getAttribute('data-rendered') === 'ok');
  v = await activeVals(page);
  check('valid files load again after errors', v.final_unload === '모름' && v.unconfirmed === '4');

  // print each view from the viewer itself
  for (const view of ['county', 'facility']) {
    await page.click(`[data-view-btn="${view}"]`);
    const pdf = path.join(OUT, `viewer_print_${view}.pdf`);
    await page.pdf({ path: pdf, format: 'A4', printBackground: true, preferCSSPageSize: true });
    const pages = Number(/Pages:\s+(\d+)/.exec(execFileSync('pdfinfo', [pdf]).toString())[1]);
    const txt = execFileSync('pdftotext', ['-layout', pdf, '-']).toString('utf8');
    check(`print ${view}: one A4 page`, pages === 1, pages);
    check(`print ${view}: PDF embeds bundled font`, /KCFNotoSansKRSubset-Regular/.test(execFileSync('pdffonts', [pdf]).toString()));
    check(`print ${view}: toolbar hidden, Korean + exercise label kept`, !/예시 사례/.test(txt) && /훈련 · 가상 상황/.test(txt) && (view === 'county' ? /시군 재난안전 담당자용/ : /시설 담당자용/).test(txt));
    check(`print ${view}: only the selected view printed`, !(view === 'county' ? /시설 담당자용 · 이송 준비 현황/ : /시군 재난안전 담당자용 · 시설/).test(txt));
  }

  // real planner output (kcf-facility-planner @ 4169ccc) loaded through the file inputs, then printed
  {
    const PQ = path.join(ROOT, 'qa/planner-4169ccc/inputs');
    await page.selectOption('#caseSel', 'delayed_vehicle');
    await page.setInputFiles('#fMeta', path.join(PQ, 'demo_briefing_meta.json'));
    await page.setInputFiles('#fBaseline', path.join(PQ, 'demo_two_vehicle.result.json'));
    await page.setInputFiles('#fRevised', path.join(PQ, 'demo_two_vehicle_v2plus600.result.json'));
    await page.waitForFunction(() => document.body.getAttribute('data-rendered') === 'ok' && /kcf-demo-two-vehicle-v1/.test(document.getElementById('out').innerText));
    for (const view of ['county', 'facility']) {
      await page.click(`[data-view-btn="${view}"]`);
      v = await activeVals(page);
      const pdf = path.join(OUT, `viewer_print_planner4169ccc_${view}.pdf`);
      await page.pdf({ path: pdf, format: 'A4', printBackground: true, preferCSSPageSize: true });
      const pages = Number(/Pages:\s+(\d+)/.exec(execFileSync('pdfinfo', [pdf]).toString())[1]);
      check(`planner 4169ccc via file inputs, ${view}: final T0+57분, one A4 page`, v.final_unload === 'T0+57분 (10:57)' && pages === 1, { final: v.final_unload, pages });
    }
  }

  // phone width: no horizontal page scroll
  await page.setViewportSize({ width: 390, height: 900 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check('phone width (390px): no horizontal page scroll', overflow <= 1, overflow);

  check('no network requests attempted', external.length === 0, external);
  check('no script errors', consoleErrors.length === 0, consoleErrors);
  await browser.close();

  const failed = results.filter((r) => !r.pass);
  fs.writeFileSync(path.join(OUT, 'viewer_e2e_result.json'), JSON.stringify({ passed: results.length - failed.length, failed: failed.length, results }, null, 2) + '\n');
  for (const r of results) console.log(`${r.pass ? 'PASS' : 'FAIL'}  ${r.name}${r.pass ? '' : '  ' + JSON.stringify(r.detail)}`);
  console.log(`${results.length - failed.length}/${results.length} passed`);
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
