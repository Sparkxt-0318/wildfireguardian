#!/usr/bin/env node
// Build the standalone offline viewer and the saved static examples.
// Usage: node tools/build.js
'use strict';
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const K = require(path.join(ROOT, 'src/brief_core.js'));

const CASES = [
  { key: 'delayed_vehicle', label: '사례 1 · 2호차 지연 (KCF-EX-DELAY-01)' },
  { key: 'unknown_input', label: '사례 2 · 화재 입력 결측 (KCF-EX-UNKNOWN-02)' },
  { key: 'destination_pending', label: '사례 3 · 목적지 수용 확인 대기 (KCF-EX-DEST-03)' }
];

const rd = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');
const safeScript = (s) => s.replace(/<\/script/gi, '<\\/script').replace(/<!--/g, '<\\!--');

function fixtureFile(caseKey, f) {
  const rel = `fixtures/${caseKey}/${f}`;
  return { name: rel, text: rd(rel) };
}

// Copy the @media print rules under a `.pm` scope so the viewer can lay a sheet out off-screen
// exactly as it will print and measure it against the A4 page height.
function printMeasureCss(css) {
  const m = /@media print \{([\s\S]*?)\n\}/.exec(css);
  if (!m) throw new Error('no @media print block');
  const rules = m[1].split('\n').map((l) => l.trim()).filter(Boolean).map((line) => {
    const i = line.indexOf('{');
    const sels = line.slice(0, i).split(',').map((x) => x.trim()).map((x) => (
      /^body/.test(x) ? x.replace(/^body/, '.pm') : /^#out/.test(x) ? x.replace(/^#out/, '.pm') : '.pm ' + x));
    return sels.join(', ') + ' ' + line.slice(i);
  });
  return '\n/* generated: print rules scoped to .pm for off-screen measurement */\n' + rules.join('\n') + '\n';
}

function buildViewer() {
  const fixtures = {};
  for (const c of CASES) {
    fixtures[c.key] = {
      label: c.label,
      baseline: fixtureFile(c.key, 'baseline.json'),
      revised: fixtureFile(c.key, 'revised.json'),
      meta: fixtureFile(c.key, 'briefing_meta.json')
    };
  }
  let html = rd('src/viewer_shell.html');
  html = html.replace('/*__CSS__*/', () => css('inline') + printMeasureCss(rd('src/brief.css')));
  html = html.replace('/*__CORE__*/', () => safeScript(rd('src/brief_core.js')));
  html = html.replace('/*__FIXTURES__*/', () => safeScript(JSON.stringify(fixtures)));
  fs.writeFileSync(path.join(ROOT, 'viewer.html'), html);
  return html;
}

// @font-face for the bundled Noto Sans KR subset: data URIs (viewer) or relative file URLs (static pages).
const FONT_FILES = { 400: 'assets/fonts/NotoSansKR-subset-400.woff2', 700: 'assets/fonts/NotoSansKR-subset-700.woff2' };
function fontFace(mode, pageDir) {
  return Object.entries(FONT_FILES).map(([w, rel]) => {
    const abs = path.join(ROOT, rel);
    const src = mode === 'inline'
      ? 'data:font/woff2;base64,' + fs.readFileSync(abs).toString('base64')
      : path.relative(pageDir, abs).split(path.sep).join('/');
    return `@font-face { font-family: "KCF Noto Sans KR Subset"; font-style: normal; font-weight: ${w}; font-display: block; src: url("${src}") format("woff2"); }`;
  }).join('\n');
}
function css(mode, pageDir) { return rd('src/brief.css').replace('/*__FONT_FACE__*/', () => fontFace(mode, pageDir)); }

function staticPage(title, sheetHtml, pageDir) {
  return `<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; font-src file: data:;">
<title>${K.esc(title)}</title><style>${css('link', pageDir)}</style></head>
<body class="static"><main id="out">${sheetHtml}</main></body></html>
`;
}

function buildExamples() {
  const summary = {};
  for (const c of CASES) {
    const dir = path.join(ROOT, 'examples', c.key);
    fs.mkdirSync(dir, { recursive: true });
    const b = fixtureFile(c.key, 'baseline.json'), r = fixtureFile(c.key, 'revised.json'), m = fixtureFile(c.key, 'briefing_meta.json');
    const before = K.brief({ baseline_text: b.text, baseline_name: b.name, meta_text: m.text, meta_name: m.name });
    const after = K.brief({ baseline_text: b.text, baseline_name: b.name, revised_text: r.text, revised_name: r.name, meta_text: m.text, meta_name: m.name });
    if (!before.ok || !after.ok) throw new Error(c.key + ': ' + JSON.stringify((before.errors || []).concat(after.errors || [])));
    fs.writeFileSync(path.join(dir, 'county_before.html'), staticPage('변경 전 · 시군 담당자용 (훈련)', before.county, dir));
    fs.writeFileSync(path.join(dir, 'county_after.html'), staticPage('변경 후 · 시군 담당자용 (훈련)', after.county, dir));
    fs.writeFileSync(path.join(dir, 'facility_after.html'), staticPage('변경 후 · 시설 담당자용 (훈련)', after.facility, dir));
    const ho = (x) => `${x.text}\n\n[측정] 음절 단위 ${x.units} / 상한 ${x.budget} · 약 ${x.est_seconds}초 (초당 5.5음절 가정)\n`;
    fs.writeFileSync(path.join(dir, 'handoff_30s_before.txt'), ho(before.handoff));
    fs.writeFileSync(path.join(dir, 'handoff_30s_after.txt'), ho(after.handoff));
    const pick = (mm) => ({
      as_of_s: mm.curAt, status: mm.cur.status, people_total: mm.cur.people_total, checked: mm.cur.checked,
      unconfirmed: mm.cur.unconfirmed, final_unload_s: mm.cur.final_unload_s,
      final_unload_display: K.fmtT(mm.meta, mm.cur.final_unload_s), changes: mm.changes.map((x) => x.text),
      requests: mm.requests.map((x) => ({ text: x.text, people: x.people, who: x.who })),
      handoff_units: mm.handoff.units
    });
    summary[c.key] = {
      label: c.label,
      inputs: { baseline: b.name, revised: r.name, meta: m.name, sha256: { baseline: K.sha256(b.text), revised: K.sha256(r.text), meta: K.sha256(m.text) } },
      before: pick(before.model), after: pick(after.model), warnings: after.warnings
    };
  }
  fs.writeFileSync(path.join(ROOT, 'examples', 'SUMMARY.json'), JSON.stringify({ core_version: K.CORE_VERSION, cases: summary }, null, 2) + '\n');
  return summary;
}

if (require.main === module) {
  buildViewer();
  const s = buildExamples();
  console.log('viewer.html written; examples:', Object.keys(s).join(', '));
}
module.exports = { buildViewer, buildExamples, staticPage, CASES };
