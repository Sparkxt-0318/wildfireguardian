// node --test tests/
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const K = require('../src/brief_core.js');
const ROOT = path.resolve(__dirname, '..');
const CASES = ['delayed_vehicle', 'unknown_input', 'destination_pending'];

const rd = (c, f) => fs.readFileSync(path.join(ROOT, 'fixtures', c, f), 'utf8');
const J = (c, f) => JSON.parse(rd(c, f));
const clone = (x) => JSON.parse(JSON.stringify(x));
function run(b, r, m) {
  return K.brief({ baseline_text: JSON.stringify(b), revised_text: r == null ? null : JSON.stringify(r), meta_text: m == null ? null : JSON.stringify(m) });
}
function rejects(b, r, m, re) {
  const out = run(b, r, m);
  assert.equal(out.ok, false, 'expected rejection matching ' + re);
  assert.ok(out.errors.some((e) => re.test(e)), 'errors: ' + JSON.stringify(out.errors));
}
// Extract data-k values from rendered HTML (no DOM needed: values are escaped plain text).
function kvals(html) {
  const out = {};
  const re = /<span data-k="([^"]+)"[^>]*>([^<]*)<\/span>/g;
  let m;
  while ((m = re.exec(html))) out[m[1]] = m[2];
  return out;
}

test('all three fixture pairs validate, before and after', () => {
  for (const c of CASES) {
    const after = run(J(c, 'baseline.json'), J(c, 'revised.json'), J(c, 'briefing_meta.json'));
    assert.ok(after.ok, c + ' ' + JSON.stringify(after.errors));
    const before = run(J(c, 'baseline.json'), null, J(c, 'briefing_meta.json'));
    assert.ok(before.ok, c + ' before ' + JSON.stringify(before.errors));
  }
});

test('sha256 matches node crypto, including Korean text', () => {
  for (const s of ['', 'abc', '훈련 · 가상 상황', rd('delayed_vehicle', 'briefing_meta.json')]) {
    assert.equal(K.sha256(s), crypto.createHash('sha256').update(s, 'utf8').digest('hex'));
  }
});

test('facility and county views agree on every shared people/time field', () => {
  for (const c of CASES) {
    for (const withRev of [true, false]) {
      const out = run(J(c, 'baseline.json'), withRev ? J(c, 'revised.json') : null, J(c, 'briefing_meta.json'));
      const f = kvals(out.facility), k = kvals(out.county);
      const shared = Object.keys(f).filter((x) => x in k);
      for (const must of ['people_total', 'checked', 'unconfirmed', 'final_unload', 'as_of', 'case_id']) assert.ok(shared.includes(must), c + ' missing shared ' + must);
      assert.ok(shared.filter((x) => /^trip:.*:(depart|unload|people)$/.test(x)).length >= 4, c + ' trip fields shared');
      for (const x of shared) assert.equal(f[x], k[x], `${c} ${withRev ? 'after' : 'before'}: ${x} facility="${f[x]}" county="${k[x]}"`);
      // Group sums in facility view equal the headline numbers.
      const g = out.model.cur.groups;
      assert.equal(g.reduce((s, x) => s + x.group.people, 0), out.model.cur.people_total);
      assert.equal(g.reduce((s, x) => s + x.unconfirmed, 0), out.model.cur.unconfirmed);
    }
  }
});

test('unavailable time: revised null replaces the old number everywhere current values are shown', () => {
  const out = run(J('delayed_vehicle', 'baseline.json'), J('delayed_vehicle', 'revised.json'), J('delayed_vehicle', 'briefing_meta.json'));
  for (const html of [out.facility, out.county]) {
    const v = kvals(html);
    assert.equal(v.final_unload, '모름');
    assert.equal(v['trip:T2:depart'], '모름');
    assert.equal(v['trip:T2:unload'], '모름');
    // The old value may appear only as an explicitly marked previous value.
    assert.equal(v['prev:final_unload'], 'T0+34분 (14:34)');
    for (const [k, val] of Object.entries(v)) if (!k.startsWith('prev:')) assert.ok(!/T0\+34분/.test(val) || k === 'trip:T3:unload', 'stale 34min in ' + k);
  }
  assert.match(out.handoff.text, /하차 예상 시각은 지금 모릅니다/);
  assert.doesNotMatch(out.handoff.text, /14시 34분/);
});

test('updated time: destination change shows the new unload time, never the old one as current', () => {
  const out = run(J('destination_pending', 'baseline.json'), J('destination_pending', 'revised.json'), J('destination_pending', 'briefing_meta.json'));
  for (const html of [out.facility, out.county]) {
    const v = kvals(html);
    assert.equal(v.final_unload, 'T0+44분 (16:44)');
    assert.equal(v['trip:T3:unload'], 'T0+44분 (16:44)');
    assert.equal(v['trip:T3:dstatus'], '수용 확인 대기');
    for (const [k, val] of Object.entries(v)) if (!k.startsWith('prev:')) assert.doesNotMatch(val, /T0\+35분/, 'stale 35min in ' + k);
  }
  assert.match(out.handoff.text, /16시 44분/);
  assert.match(out.handoff.text, /수용 확인 전/);
});

test('unknown-input case keeps 12 unresolved people visible and says missing ≠ safe', () => {
  const out = run(J('unknown_input', 'baseline.json'), J('unknown_input', 'revised.json'), J('unknown_input', 'briefing_meta.json'));
  const v = kvals(out.county);
  assert.equal(v.unconfirmed, '12');
  assert.equal(v.checked, '0');
  assert.equal(v.final_unload, '모름');
  assert.match(out.county, /안전하다는 뜻 아님/);
  assert.match(out.handoff.text, /안전하다는 뜻은 아닙니다/);
});

test('checked assignment is never presented as boarding or arrival', () => {
  for (const c of CASES) {
    const out = run(J(c, 'baseline.json'), J(c, 'revised.json'), J(c, 'briefing_meta.json'));
    assert.match(out.county, /탑승·도착 확인 아님/);
    assert.ok(out.model.confirmations.some((x) => x.k === 'boarding'));
    assert.doesNotMatch(out.county + out.facility, /탑승 완료|도착 완료|하차 완료/);
  }
});

test('information sources stay separate: model restriction, fictional field report, road status', () => {
  const out = run(J('delayed_vehicle', 'baseline.json'), J('delayed_vehicle', 'revised.json'), J('delayed_vehicle', 'briefing_meta.json'));
  const m = /<div class="src src-model">([\s\S]*?)<\/div><div class="src src-field">([\s\S]*?)<\/div><div class="src src-road">([\s\S]*?)<\/div>/.exec(out.county);
  assert.ok(m, 'three source columns present');
  assert.match(m[1], /실제 통제 아님/);
  assert.doesNotMatch(m[1], /운전원|통제 여부 모름/);
  assert.match(m[2], /리프트 고장/);
  assert.doesNotMatch(m[2], /모델/);
  assert.match(m[3], /통제 여부 모름/);
});

test('30-second handoff stays within the spoken budget and is labelled as an exercise', () => {
  for (const c of CASES) for (const withRev of [true, false]) {
    const out = run(J(c, 'baseline.json'), withRev ? J(c, 'revised.json') : null, J(c, 'briefing_meta.json'));
    assert.equal(out.handoff.over_budget, false, c + ' ' + out.handoff.units);
    assert.ok(out.handoff.units >= 80, c + ' handoff too thin');
    assert.match(out.handoff.text, /^훈련 상황입니다\./);
    assert.match(out.handoff.text, /이상입니다\.$/);
    assert.doesNotMatch(out.handoff.text, /\(으\)|undefined|null|NaN/);
  }
});

test('exercise label, time origin and provenance are visible in both views', () => {
  const out = run(J('delayed_vehicle', 'baseline.json'), J('delayed_vehicle', 'revised.json'), J('delayed_vehicle', 'briefing_meta.json'));
  for (const html of [out.facility, out.county]) {
    assert.match(html, /<div class="band">훈련 · 가상 상황 · 실제 상황 아님<\/div>/);
    assert.match(html, /T0 = 시설 대피 결정 시각/);
    assert.match(html, /이번 갱신/);
    assert.match(html, /이전 보고 <span data-k="prev_as_of">T0\+5분 \(14:05\)<\/span>/);
    assert.match(html, /sha256 [0-9a-f]{12}/);
  }
});

// ---------- rejections ----------
const A = () => ({ b: J('delayed_vehicle', 'baseline.json'), r: J('delayed_vehicle', 'revised.json'), m: J('delayed_vehicle', 'briefing_meta.json') });

test('rejects inconsistent totals', () => {
  let x = A(); x.r.people_with_checked_transport = 16; rejects(x.b, x.r, x.m, /배정 확인 운행 인원 합/);
  x = A(); x.r.people_with_checked_transport = 19; rejects(x.b, x.r, x.m, /전체 인원.*보다 많음/);
  x = A(); x.r.trips[0].people = 13; x.r.people_with_checked_transport = 15; rejects(x.b, x.r, x.m, /메타 그룹|그룹 G3 운행 인원|운행별 인원 합/);
  x = A(); x.r.people_total = 19; rejects(x.b, x.r, x.m, /메타 그룹 인원 합/);
  x = A(); x.r.groups_total = 2; rejects(x.b, x.r, x.m, /groups_total/);
  x = A(); x.r.people_total = 17.5; rejects(x.b, x.r, x.m, /정수/);
});

test('rejects a final unload number left behind while people are unconfirmed (stale number)', () => {
  const x = A(); x.r.final_unload_s = 2040; rejects(x.b, x.r, x.m, /final_unload_s 가 숫자임/);
  const y = A(); y.b.final_unload_s = 2100; rejects(y.b, y.r, y.m, /최댓값/);
  const z = A(); z.b.status = 'UNRESOLVED'; rejects(z.b, z.r, z.m, /status UNRESOLVED 인데/);
});

test('rejects impossible timestamps', () => {
  let x = A(); x.r.trips[0].unload_s = 500; rejects(x.b, x.r, x.m, /하차 시각.*출발 시각.*보다 빠름/);
  x = A(); x.r.trips[0].depart_s = -5; rejects(x.b, x.r, x.m, /depart_s/);
  x = A(); x.m.updates.revised.at_s = 200; rejects(x.b, x.r, x.m, /갱신 시각 순서 오류/);
  x = A(); x.m.updates.revised.at_s = 300; rejects(x.b, x.r, x.m, /갱신 시각 순서 오류/);
  x = A(); x.m.field_reports[0].at_s = 1600; rejects(x.b, x.r, x.m, /최신 갱신.*보다 늦음/);
  x = A(); x.r.trips[1].depart_s = 900; x.r.trips[1].unload_s = null; rejects(x.b, x.r, x.m, /보고 시각.*이전에 출발했다는데/);
  x = A(); x.m.time_origin.clock = '25:00'; rejects(x.b, x.r, x.m, /HH:MM/);
  x = A(); x.r.final_unload_s = 'soon'; rejects(x.b, x.r, x.m, /final_unload_s/);
});

test('rejects comparison between different cases', () => {
  const x = A();
  rejects(x.b, J('destination_pending', 'revised.json'), x.m, /다른 사례끼리 비교 불가/);
  rejects(x.b, x.r, J('unknown_input', 'briefing_meta.json'), /메타 case_id/);
});

test('rejects unknown status, missing fields and personal data', () => {
  let x = A(); x.r.status = 'SAFE'; rejects(x.b, x.r, x.m, /알 수 없는 status/);
  x = A(); delete x.r.assumptions; rejects(x.b, x.r, x.m, /필수 필드 없음 — assumptions/);
  x = A(); x.r.trips[0].resident_name = '홍길동'; rejects(x.b, x.r, x.m, /개인정보로 보이는 필드/);
  x = A(); x.m.field_reports[0].text = '보호자 010-1234-5678'; rejects(x.b, x.r, x.m, /휴대전화/);
  x = A(); x.m.groups[0]['성명'] = 'x'; rejects(x.b, x.r, x.m, /개인정보로 보이는 필드/);
  x = A(); x.m.exercise_label = '상황 보고'; rejects(x.b, x.r, x.m, /훈련/);
  x = A(); x.r.trips[0].vehicle_status = 'UNAVAILABLE'; rejects(x.b, x.r, x.m, /사용 불가 차량/);
});

test('MODEL_SCOPED_NO_ROUTE is shown as model-scoped, with unknown times', () => {
  const x = A();
  x.r.status = 'MODEL_SCOPED_NO_ROUTE';
  const out = run(x.b, x.r, x.m);
  assert.ok(out.ok, JSON.stringify(out.errors));
  assert.match(out.county, /모델 범위 안에서 경로 없음/);
  assert.match(out.handoff.text, /모델 범위 안에서는 경로가 안 나왔습니다/);
});

test('adapter: planner output without metadata or per-trip flags still renders, with explicit gaps', () => {
  const r = J('delayed_vehicle', 'revised.json');
  const b = J('delayed_vehicle', 'baseline.json');
  for (const t of r.trips.concat(b.trips)) { t.vehicle = t.vehicle_id; delete t.vehicle_id; delete t.assignment_checked; delete t.destination_status; }
  const out = run(b, r, null);
  assert.ok(out.ok, JSON.stringify(out.errors));
  assert.ok(out.warnings.some((w) => /메타데이터 미제공/.test(w)));
  assert.ok(out.warnings.some((w) => /별칭 vehicle → vehicle_id/.test(w)));
  assert.ok(out.warnings.some((w) => /대조 못 함/.test(w)));
  const v = kvals(out.county);
  assert.equal(v.unconfirmed, '4');
  assert.equal(v.final_unload, '모름');
  assert.match(out.county, /T0 = 메타데이터 미제공/);
  assert.match(out.county, /그룹별 대조 불가/);
});

test('rendered HTML escapes planner text', () => {
  const x = A(); x.r.reason = '<img src=x onerror=alert(1)>';
  const out = run(x.b, x.r, x.m);
  assert.ok(out.ok);
  assert.doesNotMatch(out.county, /<img/);
  assert.match(out.county, /&lt;img/);
});

// ---------- real planner output: kcf-facility-planner @ 4169ccc (copies in qa/planner-4169ccc/inputs) ----------
const PI = (f) => JSON.parse(fs.readFileSync(path.join(ROOT, 'qa/planner-4169ccc/inputs', f), 'utf8'));

test('planner 4169ccc demo pair: accepted, delay shown, both views agree, handoff names the later departure', () => {
  const out = run(PI('demo_two_vehicle.result.json'), PI('demo_two_vehicle_v2plus600.result.json'), PI('demo_briefing_meta.json'));
  assert.ok(out.ok, JSON.stringify(out.errors));
  const f = kvals(out.facility), k = kvals(out.county);
  for (const x of Object.keys(f).filter((x) => x in k)) assert.equal(f[x], k[x], x);
  assert.equal(k.final_unload, 'T0+57분 (10:57)');
  assert.equal(k['prev:final_unload'], 'T0+35분 (10:35)');
  assert.equal(k['trip:T2:depart'], 'T0+30분 (10:30)');
  assert.equal(k.checked, '12');
  assert.match(out.handoff.text, /2호차 출발이 10시 20분에서 10시 30분으로 늦어졌습니다/);
  assert.equal(out.handoff.over_budget, false);
  assert.match(out.county, /어댑터 해석/);
});

test('planner 4169ccc: integer schema_version accepted; INVALID_INPUT and structured missing info handled', () => {
  const sh = run(PI('sample_result_shuttle.json'), null, null);
  assert.ok(sh.ok, JSON.stringify(sh.errors));
  assert.match(sh.facility, /빈 차 복귀/);
  const mi = run(PI('sample_result_missing_input.json'), null, null);
  assert.ok(mi.ok, JSON.stringify(mi.errors));
  assert.equal(kvals(mi.county).unconfirmed, '6');
  assert.equal(kvals(mi.county).final_unload, '모름');
  assert.match(mi.county, /도로 구간 e1 의 T0\+0초~40초 상태 모름/);
  assert.ok(mi.warnings.some((w) => /conditional_trips 1건/.test(w)));
  const bad = PI('sample_result_shuttle.json'); bad.status = 'INVALID_INPUT';
  rejects(bad, null, null, /INVALID_INPUT/);
  const stale = PI('demo_two_vehicle_v2plus600.result.json'); stale.final_unload_s = 2100;
  rejects(PI('demo_two_vehicle.result.json'), stale, PI('demo_briefing_meta.json'), /최댓값/);
});

test('planner 4169ccc contract pair has different case_ids and is rejected as a cross-case comparison', () => {
  rejects(PI('contract_normal.result.json'), PI('sample_result_parallel_delayed.json'), null, /다른 사례끼리 비교 불가/);
});
