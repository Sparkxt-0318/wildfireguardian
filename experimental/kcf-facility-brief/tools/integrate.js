#!/usr/bin/env node
// One-command integration check for a real planner output.
//
//   node tools/integrate.js --baseline <file|git:TAG:path> --revised <file|git:TAG:path> \
//        [--meta <file|git:TAG:path>] [--out <dir>] [--no-pdf]
//
// `git:TAG:path` reads a file from a tagged commit with `git show` (read-only; no checkout,
// no worktree change). Writes county/facility HTML, A4 PDFs, the 30 s handoff and
// integration_report.json to --out (default: qa/integration-<case_id>). Exit 0 = accepted,
// 1 = rejected by validation, 2 = usage / read error.
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const K = require(path.join(ROOT, 'src/brief_core.js'));
const { staticPage } = require('./build.js');

function args() {
  const a = process.argv.slice(2), o = { pdf: true };
  for (let i = 0; i < a.length; i++) {
    if (a[i] === '--no-pdf') o.pdf = false;
    else if (a[i].startsWith('--')) o[a[i].slice(2)] = a[++i];
  }
  return o;
}
function readSrc(spec) {
  if (!spec) return null;
  const m = /^git:([^:]+):(.+)$/.exec(spec);
  if (m) {
    const text = execFileSync('git', ['-C', ROOT, 'show', `${m[1]}:${m[2]}`], { encoding: 'utf8' });
    const commit = execFileSync('git', ['-C', ROOT, 'rev-list', '-n', '1', m[1]], { encoding: 'utf8' }).trim();
    return { name: `${m[1]}:${m[2]}`, text, origin: { kind: 'git-tag', tag: m[1], commit, path: m[2] } };
  }
  return { name: path.basename(spec), text: fs.readFileSync(spec, 'utf8'), origin: { kind: 'file', path: path.resolve(spec) } };
}

(async () => {
  const o = args();
  if (!o.baseline) { console.error('usage: node tools/integrate.js --baseline B --revised R [--meta M] [--out DIR] [--no-pdf]'); process.exit(2); }
  let b, r, m;
  try { b = readSrc(o.baseline); r = readSrc(o.revised); m = readSrc(o.meta); }
  catch (e) { console.error('read error: ' + e.message); process.exit(2); }
  const res = K.brief({
    baseline_text: b.text, baseline_name: b.name, revised_text: r && r.text, revised_name: r && r.name,
    meta_text: m && m.text, meta_name: m && m.name
  });
  const report = {
    tool: 'kcf-facility-brief/tools/integrate.js', core_version: K.CORE_VERSION,
    inputs: {
      baseline: b && { ...b.origin, sha256: K.sha256(b.text) },
      revised: r && { ...r.origin, sha256: K.sha256(r.text) },
      meta: m ? { ...m.origin, sha256: K.sha256(m.text) } : null
    },
    accepted: res.ok, errors: res.errors || [], warnings: res.warnings || []
  };
  let caseId = 'unknown';
  try { caseId = JSON.parse(b.text).case_id || caseId; } catch (e) { /* reported by validation */ }
  const out = path.resolve(o.out || path.join(ROOT, 'qa', 'integration-' + String(caseId).replace(/[^A-Za-z0-9_.-]/g, '_')));
  fs.mkdirSync(out, { recursive: true });
  if (res.ok) {
    const mm = res.model;
    report.summary = {
      case_id: mm.meta.case_id, status: mm.cur.status, people_total: mm.cur.people_total, checked: mm.cur.checked,
      unconfirmed: mm.cur.unconfirmed, final_unload: K.fmtT(mm.meta, mm.cur.final_unload_s),
      changes: mm.changes.map((x) => x.text), requests: mm.requests.map((x) => `${x.text} (${x.people == null ? '모름' : x.people + '명'}) → ${x.who}`),
      handoff: mm.handoff
    };
    fs.writeFileSync(path.join(out, 'county.html'), staticPage('시군 담당자용 (훈련)', res.county, out));
    fs.writeFileSync(path.join(out, 'facility.html'), staticPage('시설 담당자용 (훈련)', res.facility, out));
    fs.writeFileSync(path.join(out, 'handoff_30s.txt'), mm.handoff.text + '\n');
    if (o.pdf) {
      try {
        const { chromium } = require('playwright');
        const browser = await chromium.launch();
        report.pdf = {};
        const { fitPrint } = require('./fit_print.js');
        for (const v of ['county', 'facility']) {
          const html = path.join(out, v + '.html'), pdf = path.join(out, v + '.a4.pdf');
          const fit = await fitPrint(browser, html, pdf);
          const page = await browser.newPage({ viewport: { width: 900, height: 1300 } });
          await page.route('**/*', (rt) => (rt.request().url().startsWith('file:') ? rt.continue() : rt.abort()));
          await page.goto('file://' + html);
          await page.locator('.sheet').first().screenshot({ path: path.join(out, v + '.png') });
          await page.close();
          report.pdf[v] = { file: path.basename(pdf), png: v + '.png', pages: fit.pages, one_page: fit.pages === 1, density_start: fit.density_start, density_used: fit.density_used };
        }
        await browser.close();
      } catch (e) { report.pdf = { skipped: 'playwright unavailable: ' + e.message }; }
    }
  }
  fs.writeFileSync(path.join(out, 'integration_report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(`${res.ok ? 'ACCEPTED' : 'REJECTED'}  case=${caseId}  out=${path.relative(process.cwd(), out) || '.'}`);
  for (const e of report.errors) console.log('  오류: ' + e);
  for (const w of report.warnings) console.log('  주의: ' + w);
  if (res.ok) {
    const s = report.summary;
    console.log(`  상태 ${s.status} · 전체 ${s.people_total}명 · 배정 확인 ${s.checked}명 · 미확정 ${s.unconfirmed}명 · 전원 하차 ${s.final_unload}`);
    if (report.pdf && report.pdf.county) console.log(`  A4: county ${report.pdf.county.pages}쪽, facility ${report.pdf.facility.pages}쪽`);
  }
  process.exit(res.ok ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(2); });
