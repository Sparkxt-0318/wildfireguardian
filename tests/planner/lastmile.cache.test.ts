/**
 * Property tests of the last-mile kit over EVERY origin of the six booth caches
 * (2 regions × 3 recorded input times), loaded the way the app loads them
 * (tests/planner/lastmile.cachedata.ts). For every origin and every output, in Korean and English:
 * length limits, mandatory lines, data time, replay note, no forbidden word, and no departure
 * instruction or clock time unless the planner has a checked departure window.
 *
 * The limits are checked twice: by the module's own checks (checkFieldMessages) and by independent
 * oracles written here — Python's strict `euc_kr` codec for the Korean byte counts (skipped only if
 * python3 is missing), a separate GSM-7 character class, and separate word / instruction patterns.
 *
 * Real outputs are snapshotted WITHOUT a deadline explanation. The "contract-shaped explanation"
 * block builds a synthetic `wfg.explanation/1` file from the planner's own deadlines with made-up
 * 40-character road names; it exercises the reader and the length budgets and never leaves the
 * test. The last block runs every rule over the real explanation files when they are present
 * (planner/public/data/explanations/, or a directory named by WFG_EXPLANATIONS_DIR) and is
 * skipped otherwise.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { enDateSpoken, hm, koDateSpoken } from '../../planner/src/features/lastmile/compose';
import { maskData } from '../../planner/src/features/lastmile/checks';
import { BROADCAST_MAX_S, eucKrBytes, LMS_MAX_BYTES, SMS_EN_MAX_GSM7, SMS_KO_MAX_BYTES, spokenSeconds } from '../../planner/src/features/lastmile/encoding';
import { allTexts, buildFieldMessages, type FieldMessages } from '../../planner/src/features/lastmile/messages';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import { MODEL_NOT_LIVE, NOT_REAL, OFFICIAL_FIRST } from '../../planner/src/features/lastmile/strings';
import type { LastMileInput } from '../../planner/src/features/lastmile/types';
import { loadBoothCaches, realExplanationDir, realExplanationFor, syntheticExplanationFor, type BoothCache } from './lastmile.cachedata';
import { DEPART, expectedReasonKind, GSM7, HANGUL, NEVER, pythonEucKr } from './lastmile.oracle';

let caches: BoothCache[] = [];
let all: { cache: BoothCache; input: LastMileInput; fm: FieldMessages }[] = [];

beforeAll(() => {
  caches = loadBoothCaches();
  all = caches.flatMap((cache) => cache.inputs.map((input) => ({ cache, input, fm: buildFieldMessages(input, null) })));
}, 180_000);

// independent oracles (GSM7, NEVER, DEPART, HANGUL, pythonEucKr, expectedReasonKind): lastmile.oracle.ts

describe('all six booth caches, every origin', () => {
  it('loads 2 regions × 3 recorded input times and one input per origin of each scenario', () => {
    expect(caches.map((c) => c.entry.path).sort()).toEqual([
      'uiseong_andong_2025/20250323T010000Z.json',
      'uiseong_andong_2025/20250324T090000Z.json',
      'uiseong_andong_2025/20250325T170000Z.json',
      'yeongdeok_2025/20250325T190000Z.json',
      'yeongdeok_2025/20250325T230000Z.json',
      'yeongdeok_2025/20250326T080000Z.json',
    ]);
    for (const c of caches) {
      expect(c.inputs.length).toBeGreaterThanOrEqual(c.cachedOrigins);
      expect(new Set(c.inputs.map((i) => i.origin.id)).size).toBe(c.inputs.length);
      expect(c.inputs.every((i) => !i.mock && !i.testData && i.replay)).toBe(true);
      // research origins (recorded mission start points) get no resident-addressed messages
      expect(c.inputs.every((i) => i.origin.kind !== 'research' && !i.origin.id.startsWith('research:'))).toBe(true);
    }
    expect(caches.reduce((a, c) => a + c.researchOrigins, 0)).toBeGreaterThan(0);
    const kinds: Record<string, number> = {};
    for (const x of all) kinds[x.fm.kind] = (kinds[x.fm.kind] ?? 0) + 1;
    // the message kind follows the planner's verdict
    for (const x of all) {
      const v = x.input.plan?.bestVerdict ?? 'unresolved';
      if (x.fm.kind === 'leave_by' || x.fm.kind === 'partial') expect(v).toBe('checked_route');
      if (x.fm.kind === 'no_route') expect(v).toBe('model_no_route');
      if (x.fm.kind === 'unresolved') expect(v).toBe('unresolved');
    }
    expect(Object.keys(kinds).sort()).toEqual(['leave_by', 'no_route', 'unresolved']);
    expect(all.length).toBeGreaterThan(500);
  });

  it('every output passes the module rule checks (limits, mandatory lines, data time, replay note, words, instructions)', () => {
    const bad = all.filter((x) => x.fm.violations.length).map((x) => `${x.cache.entry.path} ${x.input.origin.id}: ${x.fm.violations.join(' | ')}`);
    expect(bad).toEqual([]);
  });

  it('Korean SMS ≤ 90 bytes and long texts ≤ 2,000 bytes in strict EUC-KR (independent: Python euc_kr codec)', () => {
    const sms = all.map((x) => x.fm.text.ko.sms);
    const lms = all.flatMap((x) => [x.fm.text.ko.lms, x.fm.text.en.lms]);
    for (const x of all) expect(x.fm.metrics.ko.smsUnits).toBeLessThanOrEqual(SMS_KO_MAX_BYTES);
    const py = pythonEucKr([...sms, ...lms]);
    if (!py) {
      console.warn('python3 not found: independent EUC-KR cross-check skipped (module counts still enforced)');
      return;
    }
    py.slice(0, sms.length).forEach((n, i) => {
      expect(n, sms[i]).toBe(all[i]!.fm.metrics.ko.smsUnits);
      expect(n as number).toBeLessThanOrEqual(SMS_KO_MAX_BYTES);
    });
    py.slice(sms.length).forEach((n, i) => {
      expect(typeof n, lms[i]).toBe('number');
      expect(n as number).toBeLessThanOrEqual(LMS_MAX_BYTES);
    });
  });

  it('English SMS ≤ 160 GSM-7 characters, all inside the GSM 03.38 alphabet (independent character class)', () => {
    for (const x of all) {
      const s = x.fm.text.en.sms;
      expect(GSM7.test(s), s).toBe(true);
      expect(s.length).toBeLessThanOrEqual(SMS_EN_MAX_GSM7);
      expect(x.fm.metrics.en.smsUnits).toBe(s.length);
    }
  });

  it('village broadcast scripts read in ≤ 60 s at the assumed rate, Korean and English', () => {
    for (const x of all) {
      expect(x.fm.metrics.ko.broadcastS).toBeLessThanOrEqual(BROADCAST_MAX_S);
      expect(x.fm.metrics.en.broadcastS).toBeLessThanOrEqual(BROADCAST_MAX_S);
    }
  });

  it('every output carries the data time and "official orders come first"; written ones also the model line verbatim', () => {
    for (const x of all) {
      const it0 = x.input.scenario.inputTimeIso;
      for (const lang of ['ko', 'en'] as const) {
        const t = allTexts(x.fm, lang);
        expect(t.sms).toContain(lang === 'ko' ? '공식명령 우선' : 'Official orders come first.');
        for (const k of ['lms', 'broadcast', 'call', 'card'] as const) expect(t[k]).toContain(OFFICIAL_FIRST[lang]);
        for (const k of ['lms', 'card'] as const) expect(t[k]).toContain(MODEL_NOT_LIVE[lang]);
        expect(t.sms).toContain(hm(it0));
        expect(t.lms).toContain(hm(it0));
        expect(t.card).toContain(hm(it0));
      }
    }
  });

  it('no forbidden word anywhere (independent pattern, place names masked)', () => {
    for (const x of all) for (const lang of ['ko', 'en'] as const) for (const t of Object.values(allTexts(x.fm, lang))) expect(maskData(t, x.fm.inserted)).not.toMatch(NEVER);
  });

  it('model_no_route and unresolved never yield a departure instruction or a clock time; leave_by always names its time', () => {
    for (const x of all) {
      const texts = [...Object.values(allTexts(x.fm, 'ko')), ...Object.values(allTexts(x.fm, 'en'))].map((t) => maskData(t, x.fm.inserted));
      if (x.fm.kind === 'leave_by') {
        expect(x.fm.leaveByS).not.toBeNull();
        expect(x.fm.text.ko.sms).toContain(`${hm(x.input.scenario.inputTimeIso, x.fm.leaveByS!)}까지 차로 출발`);
        // the leave-by time is a checked departure and every earlier requested time is checked too
        const cells = x.input.plan!.sweep.filter((c) => c.verdict !== 'window_closed' && c.offsetS <= x.fm.leaveByS!);
        expect(cells.length).toBeGreaterThan(0);
        expect(cells.every((c) => c.verdict === 'checked_route')).toBe(true);
      } else {
        const spokenData = [koDateSpoken(x.input.scenario.inputTimeIso), enDateSpoken(x.input.scenario.inputTimeIso)];
        for (const t0 of texts) {
          const t = spokenData.reduce((acc, d) => acc.split(d).join(' '), t0);
          expect(t).not.toMatch(DEPART);
          const data = hm(x.input.scenario.inputTimeIso);
          const times = [...t.replace(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}|\d{2}\.\d{1,2}\.\d{1,2} \d{2}:\d{2}|\d{4}년 \d{1,2}월 \d{1,2}일 \d{2}:\d{2}/g, '').matchAll(/(?<![\w:.])(\d{2}):(\d{2})(?![\d:])/g)].map((m) => `${m[1]}:${m[2]}`);
          expect(times.every((c) => c === data), t).toBe(true);
          expect(t).not.toMatch(/(새벽|오전|낮|오후|밤) \d{1,2}시 \d{1,2}분|\d{1,2}:\d{2} [ap]\.m\./);
        }
      }
    }
  });
});

describe('audiences and replays (independent checks)', () => {
  it('every SMS and long text says first that it is a replay; every broadcast opens with "not a real situation"', () => {
    for (const x of all) {
      expect(x.fm.text.ko.sms.split('\n')[0]).toMatch(/^\[\d{2}\.\d{1,2}\.\d{1,2} \d{2}:\d{2} 기록재현\]$/);
      expect(x.fm.text.en.sms.split('\n')[0]).toMatch(/^REPLAY of \d{4}-\d{2}-\d{2} \d{2}:\d{2} KST data, not live$/);
      expect(x.fm.text.ko.lms.split('\n')[0]).toBe('[2025년 기록 재현 · 실제 상황 아님]');
      expect(x.fm.text.en.lms.split('\n')[0]).toBe('[REPLAY of recorded 2025 data - not a real emergency]');
      expect(x.fm.text.ko.broadcast.split('\n')[0]).toBe(NOT_REAL.ko);
      expect(x.fm.text.en.broadcast.split('\n')[0]).toBe(NOT_REAL.en);
    }
  });

  it('residents and families are never told to call 119 now (SMS, broadcast, call script); staff texts say it', () => {
    const now = /(지금 바로|즉시)\s*119|call 119 (now|immediately)|119 or the eup\/myeon office now/i;
    for (const x of all) {
      for (const lang of ['ko', 'en'] as const) for (const t of [x.fm.text[lang].sms, x.fm.text[lang].broadcast, x.fm.text[lang].call]) expect(t).not.toMatch(now);
      if (x.fm.kind === 'no_route') {
        expect(x.fm.text.ko.lms).toMatch(/(이장|시설 담당자): 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따르십시오\./);
        // residents (broadcast) and families (call script) are told what to do themselves
        for (const t of [x.fm.text.ko.broadcast, x.fm.text.ko.call]) expect(t).toMatch(/(이장과|시설과) 읍·면사무소의 공식 지시를 따르십시오\. 위급하면 119에 신고하십시오\./);
        for (const t of [x.fm.text.en.broadcast, x.fm.text.en.call]) expect(t).toMatch(/Follow official instructions from the (village head|facility) and the eup\/myeon office\. In an emergency, call 119\./);
      }
    }
  });

  it('every leave-by broadcast (and village call script) keeps the no-car line, and names the road entry point when it is over 500 m away', () => {
    let far = 0;
    for (const x of all) {
      if (x.fm.kind !== 'leave_by') continue;
      const fac = x.input.origin.kind === 'facility';
      expect(x.fm.text.ko.broadcast).toContain(fac ? '차가 부족하면 읍·면사무소에 바로 알리십시오.' : '차가 없는 분은 이장에게 바로 알리십시오.');
      expect(x.fm.text.en.broadcast).toContain(fac ? 'If vehicles are short, tell the eup/myeon office now.' : 'If you have no car, tell the village head now.');
      if (!fac) {
        expect(x.fm.text.ko.call).toContain('어르신께서 차가 없거나 혼자 움직이기 어려우시면 이장이나 읍·면사무소에 바로 알려 주십시오.');
        expect(x.fm.text.en.call).toContain('If [resident name] has no car or cannot move alone, please tell the village head or the eup/myeon office right away.');
      }
      const d = x.input.origin.entryDistanceM;
      if (d !== null && d > 500) {
        far += 1;
        expect(x.fm.text.ko.broadcast).toMatch(/떨어진 도로 기준입니다\./);
        expect(x.fm.text.en.broadcast).toMatch(/Times are for the road .* (from the (village|facility)|away)\./);
      }
    }
    expect(far).toBeGreaterThan(0);
  });
});

describe('MOCK and test-data markers on every origin (mock-server dev setup; results not from the evaluated host)', () => {
  const variants = [
    { name: 'MOCK', flags: { mock: true, testData: false } },
    { name: 'test data', flags: { mock: false, testData: true } },
    // a non-evaluated cache viewed while the mock server is on (MOCK is session-wide)
    { name: 'MOCK and test data', flags: { mock: true, testData: true } },
  ];
  for (const v of variants) {
    it(`${v.name}: every output of every origin passes every rule, carries the marker and keeps every limit, without and with the real explanation files`, () => {
      let n = 0;
      for (const cache of caches) {
        const real = realExplanationFor(cache).file;
        for (const file of real ? [null, real] : [null]) {
          for (const input of cache.inputs) {
            const fm = buildFieldMessages({ ...input, ...v.flags }, file);
            n += 1;
            expect(fm.violations, `${cache.entry.path} ${input.origin.id}`).toEqual([]);
            // independent of checks.ts: the marker in each output (the SMS and long text on the first line)
            const first = (t: string) => t.split('\n')[0]!;
            if (v.flags.mock) {
              for (const l of ['ko', 'en'] as const) {
                expect(first(fm.text[l].sms)).toContain('MOCK');
                expect(first(fm.text[l].lms)).toContain('MOCK');
                expect(fm.text[l].card.badges).toContain('MOCK');
              }
              expect(fm.text.ko.broadcast).toContain('모의 서버');
              expect(fm.text.en.broadcast).toContain('mock server');
            }
            if (v.flags.testData) {
              expect(first(fm.text.ko.sms)).toContain('시험');
              expect(first(fm.text.en.sms)).toContain('TEST');
              expect(first(fm.text.ko.lms)).toContain('시험 데이터');
              expect(first(fm.text.en.lms)).toContain('TEST DATA');
              expect(fm.text.ko.broadcast).toContain('시험용');
              expect(fm.text.en.broadcast).toContain('test results');
              expect(fm.text.ko.card.badges).toContain('시험 데이터 · 평가 호스트 아님');
              expect(fm.text.en.card.badges).toContain('Test data · not the evaluation host');
            }
            // the limits, recounted here
            expect(spokenSeconds(fm.text.ko.broadcast, 'ko')).toBeLessThanOrEqual(BROADCAST_MAX_S);
            expect(spokenSeconds(fm.text.en.broadcast, 'en')).toBeLessThanOrEqual(BROADCAST_MAX_S);
            expect(eucKrBytes(fm.text.ko.sms).bytes).toBeLessThanOrEqual(SMS_KO_MAX_BYTES);
            expect(fm.text.en.sms.length).toBeLessThanOrEqual(SMS_EN_MAX_GSM7);
            expect(GSM7.test(fm.text.en.sms)).toBe(true);
          }
        }
      }
      expect(n).toBeGreaterThan(1000);
    });
  }
});

describe('numbers and names a reader hears or reads (independent checks over every origin)', () => {

  it('the arrival clock and the travel minutes come from one rounding: minutes = shown arrival − departure, arrival never earlier than the model', () => {
    let lines = 0;
    for (const x of all) {
      if (x.fm.kind !== 'leave_by' || !x.fm.plan.destination || x.fm.plan.destinationVaries) continue;
      const d = x.fm.plan.destination;
      if (d.arrivalS === null || d.arrivalS <= x.fm.leaveByS!) continue;
      const iso = x.input.scenario.inputTimeIso;
      // input times and departures are whole minutes in the recorded data: ceil of the travel time
      const min = Math.ceil((d.arrivalS - x.fm.leaveByS!) / 60);
      const T = hm(iso, x.fm.leaveByS!);
      const A = hm(iso, x.fm.leaveByS! + 60 * min);
      expect(A, x.input.origin.id).toBe(hm(iso, Math.ceil(d.arrivalS / 60) * 60));
      expect(x.fm.text.ko.lms).toContain(`${T}에 출발하면 ${A}쯤 도착합니다(차로 약 ${min}분,`);
      expect(x.fm.text.en.lms).toContain(`Leaving at ${T}, arrival around ${A} KST (about ${min} min by car;`);
      expect(allTexts(x.fm, 'ko').card).toContain(`${T} 출발 시 ${A}쯤 도착(차로 약 ${min}분,`);
      expect(allTexts(x.fm, 'en').card).toContain(`leave ${T}, arrive around ${A} (about ${min} min by car;`);
      lines += 1;
    }
    expect(lines).toBe(all.filter((x) => x.fm.kind === 'leave_by').length);
  });

  it('English spoken outputs (broadcast, call script) never read a Hangul name', () => {
    let hangulNames = 0;
    for (const x of all) {
      const names = [x.input.origin.name?.en, x.fm.plan.destination?.name?.en].filter((n): n is string => Boolean(n));
      if (names.some((n) => HANGUL.test(n))) hangulNames += 1;
      for (const t of [x.fm.text.en.broadcast, x.fm.text.en.call]) expect(t, x.input.origin.id).not.toMatch(HANGUL);
    }
    // the fallback is exercised: many places have no Latin-script name in OSM
    expect(hangulNames).toBeGreaterThan(100);
  });
});

/**
 * "점검한 마지막 출발 / Checked up to" only when T really is the last departure checked: no requested
 * (not window-closed) departure after T in the sweep — read here from the sweep itself, not from
 * plan.ts. Otherwise the later departures were checked, and no text may say they were not.
 */
function checkLastCheckedWording(fm: FieldMessages): 'last' | 'later_checked' | null {
  if (fm.kind !== 'leave_by' || fm.leaveByS === null) return null;
  const T = fm.leaveByS;
  const last = !fm.plan.input.plan!.sweep.some((c) => c.verdict !== 'window_closed' && c.offsetS > T);
  expect(fm.text.ko.card.big?.label, fm.originId).toBe(last ? '점검한 마지막 출발' : '출발 마감');
  expect(fm.text.en.card.big?.label, fm.originId).toBe(last ? 'Checked up to' : 'Leave by');
  if (!last) {
    for (const lang of ['ko', 'en'] as const) {
      for (const t of Object.values(allTexts(fm, lang))) expect(t, fm.originId).not.toMatch(/점검하지 (않았|못했)|점검한 마지막|not checked|checked up to|last departure time the model checked/i);
    }
  }
  return last ? 'last' : 'later_checked';
}

describe('"checked up to" only when T is the last departure checked (independent of plan.ts)', () => {
  it('without explanation files: every leave-by origin', () => {
    const n = { last: 0, later_checked: 0 };
    for (const x of all) {
      const k = checkLastCheckedWording(x.fm);
      if (k) n[k] += 1;
    }
    expect(n.last).toBeGreaterThan(0);
    expect(n.later_checked).toBeGreaterThan(0);
  });

  it('with the real explanation files: the deadlines set by the 1-hour window are leave-by times, and the line says only what the file and the sweep establish', (ctx) => {
    const found = caches.map((c) => ({ cache: c, ...realExplanationFor(c) }));
    if (found.every((f) => !f.file)) {
      ctx.skip();
      return;
    }
    let window = 0;
    for (const { cache, file } of found) {
      for (const input of cache.inputs) {
        const fm = buildFieldMessages(input, file);
        const k = checkLastCheckedWording(fm);
        if (fm.reason?.kind !== 'time_window') continue;
        window += 1;
        expect(k, input.origin.id).toBe('later_checked');
        // the next checked time is named and later departures have "no checked route", never "not checked"
        expect(fm.text.ko.lms).toContain(`다음 점검 시각인 ${hm(input.scenario.inputTimeIso, fm.plan.nextOffsetS!)}에 출발하면 불길이 없더라도 점검한 도착지 중`);
        expect(fm.text.ko.lms).toContain(`${hm(input.scenario.inputTimeIso, fm.leaveByS!)}보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다.`);
        expect(fm.text.en.lms).toContain(`departures after ${hm(input.scenario.inputTimeIso, fm.leaveByS!)} have no checked route in the model`);
      }
    }
    expect(window).toBeGreaterThan(0);
  });
});

describe('with a contract-shaped explanation file built from the planner deadlines (synthetic road name)', () => {
  const explanationFor = syntheticExplanationFor;

  it('reasons appear exactly where the entry agrees with the planner, and every limit still holds', () => {
    let used = 0;
    let eligible = 0;
    for (const cache of caches) {
      const file = explanationFor(cache);
      for (const input of cache.inputs) {
        const fm = buildFieldMessages(input, file);
        expect(fm.violations, `${cache.entry.path} ${input.origin.id}`).toEqual([]);
        const p = messagePlan(input, null);
        const want = (p.kind === 'leave_by' && p.nextVerdict === 'model_no_route') || p.kind === 'no_route';
        if (want) eligible += 1;
        if (fm.reason) used += 1;
        expect(Boolean(fm.reason), `${cache.entry.path} ${input.origin.id}`).toBe(want);
        if (fm.kind === 'unresolved') expect(fm.reason).toBeNull();
      }
    }
    expect(eligible).toBeGreaterThan(0);
    expect(used).toBe(eligible);
  });

  it('a file whose deadlines are off by one departure step gives no reason at all (fail closed)', () => {
    for (const cache of caches) {
      const file = explanationFor(cache, 600);
      for (const input of cache.inputs) {
        const fm = buildFieldMessages(input, file);
        if (fm.kind === 'leave_by') expect(fm.reason).toBeNull();
      }
    }
  });
});

describe('real outputs (booth cache, no explanation file) — snapshots in both languages', () => {
  const pick = (path: string, id: string) => {
    const x = all.find((y) => y.cache.entry.path === path && y.input.origin.id === id);
    if (!x) throw new Error(`${path} ${id} not found`);
    return x.fm;
  };
  const view = (fm: FieldMessages) => ({ kind: fm.kind, ko: allTexts(fm, 'ko'), en: allTexts(fm, 'en') });

  it('checked_route → leave_by (삼춘리, 의성·안동, 2025-03-26 02:00 KST)', () => {
    expect(view(pick('uiseong_andong_2025/20250325T170000Z.json', 'osm:node/415160437'))).toMatchInlineSnapshot(`
      {
        "en": {
          "broadcast": "This is not a real emergency.
      Attention, residents of Samchun-ri.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time.
      Leave by car no later than 2:20 a.m. The computer forecast checked a route to Uiseong Bukbu Elementary School for departures up to then.
      If you have no car, tell the village head now.
      Follow official guidance on where to go.
      Later departures have no checked route.
      Again: this is not a real emergency; it is a replay of recorded 2025 data.
      Official evacuation orders come first.",
          "call": "[Before the call] Official evacuation orders come first. What follows is model-based planning information, not live information. Fill in the [brackets] yourself.
      Hello, this is [your name and role]. I am calling the family of [resident name], who lives in Samchun-ri, about the wildfire evacuation plan.
      This is not a real emergency: it is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time.
      In the computer forecast (the model), leaving by car from the road near the village no later than 2:20 a.m. gives a checked route to Uiseong Bukbu Elementary School.
      Later departures have no checked route.
      If [resident name] has no car or cannot move alone, please tell the village head or the eup/myeon office right away.
      Official evacuation orders come first. The actual place and time of any move may change with official guidance.
      If you have questions, please call [phone number]. Thank you.",
          "card": "Evacuation plan card · Uiseong–Andong · Recorded 2025 wildfire · scenario replay · Not a real emergency
      Samchun-ri (Village)
      Checked vehicle route in the model
      Leave by 02:20 (2:20 a.m. KST)
      Do not wait until this time: leave by car early.
      Model-checked destination: Uiseong Bukbu Elementary School; leave 02:20, arrive around 02:51 (about 31 min by car; traffic not included)
      No checked route for departures after 02:20.
      Follow official guidance on where to go. No car or need help? Tell the village head or eup/myeon office now.
      Official evacuation orders come first.
      Data time: 2025-03-26 02:00 KST · replay of 2025 data
      Model-based planning information · not live
      Times at the road entry point 195 m away; boarding time not included · Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents
      Planning aid only — not for live evacuation operations.
      Scenario ffb1:20250325T170000Z:53e6da7897bf9b5b · Prepared 2026-11-02 14:00 KST · Precomputed 2026-10-18 08:10 KST",
          "lms": "[REPLAY of recorded 2025 data - not a real emergency]
      Wildfire evacuation plan information - Samchun-ri (Village)
      Data time: 2025-03-26 02:00 KST · Precomputed 2026-10-18 08:10 KST

      - Leave by car no later than 02:20 KST (2:20 a.m.). Do not wait until that time.
      - Destination the model checked: Uiseong Bukbu Elementary School. Leaving at 02:20, arrival around 02:51 KST (about 31 min by car; traffic not included).
      - Departures after 02:20 have no checked route in the model.
      - Follow official guidance on where to go and which roads to use.
      - If you have no car or cannot move on your own, tell the village head or the eup/myeon office now.
      - Times refer to the nearest road point (entry point), 195 m from the village. Time to get ready and board is not included.

      Official evacuation orders come first.
      Model-based planning information · not live
      Replay of recorded 2025 wildfire scenarios.
      Planning aid only - not for live evacuation operations.",
          "sms": "REPLAY of 2025-03-26 02:00 KST data, not live
      Model-based plan: leave by car no later than 02:20 KST.
      Official orders come first.",
        },
        "kind": "leave_by",
        "ko": {
          "broadcast": "이 방송은 실제 상황이 아닙니다.
      삼춘리 주민 여러분께 알려 드립니다.
      2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보입니다.
      새벽 2시 20분까지 차로 출발하십시오. 의성북부초등학교까지 가는 길이 컴퓨터 예측 계산으로 확인되었습니다.
      차가 없는 분은 이장에게 바로 알리십시오.
      대피 장소는 공식 안내를 따르십시오.
      그보다 늦게 출발하는 길은 확인되지 않았습니다.
      공식 대피 명령이 우선합니다.",
          "call": "[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
      안녕하세요. [소속·이름]입니다. 삼춘리에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
      지금 드리는 내용은 실제 상황이 아니라, 2025년 3월 26일 새벽 2시 산불 기록을 재현한 모델 기반 계획 정보입니다.
      컴퓨터 예측 계산(모델)으로는 마을 근처 도로에서 새벽 2시 20분까지 차로 출발하면 의성북부초등학교까지 가는 경로가 확인되었습니다.
      그보다 늦게 출발하는 길은 확인되지 않았습니다.
      어르신께서 차가 없거나 혼자 움직이기 어려우시면 이장이나 읍·면사무소에 바로 알려 주십시오.
      공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
      궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.",
          "card": "산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현 · 실제 상황 아님
      삼춘리 (마을)
      모델로 확인된 차량 경로 있음
      출발 마감 02:20 (새벽 2시 20분 · 한국 시각)
      이 시각까지 기다리지 말고 미리 차로 출발하십시오.
      모델이 점검한 도착지: 의성북부초등학교 · 02:20 출발 시 02:51쯤 도착(차로 약 31분, 교통 정체 미반영)
      02:20보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다.
      실제 대피 장소와 길은 공식 안내를 따르십시오. 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
      공식 대피 명령이 우선합니다.
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
      모델 기반 계획 정보 · 실시간 아님
      시각은 마을에서 195 m 떨어진 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외 · 차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
      시나리오 ffb1:20250325T170000Z:53e6da7897bf9b5b · 작성 2026-11-02 14:00 KST · 사전 계산 2026-10-18 08:10 KST",
          "lms": "[2025년 기록 재현 · 실제 상황 아님]
      산불 대피 계획 정보 · 삼춘리(마을)
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 사전 계산 2026-10-18 08:10 KST

      ■ 02:20(새벽 2시 20분)까지 차로 출발하십시오. 이 시각까지 기다리지 마십시오.
      ■ 모델이 점검한 도착지: 의성북부초등학교. 02:20에 출발하면 02:51쯤 도착합니다(차로 약 31분, 교통 정체 미반영).
      ■ 02:20보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다.
      ■ 실제 대피 장소와 길은 공식 안내를 따르십시오.
      ■ 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
      ■ 시각은 마을에서 195 m 떨어진 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.

      공식 대피 명령이 우선합니다.
      모델 기반 계획 정보 · 실시간 아님
      2025년 실제 산불 기록을 재현한 시나리오입니다.
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.",
          "sms": "[25.3.26 02:00 기록재현]
      모델상 02:20까지 차로 출발
      공식명령 우선·실시간 아님",
        },
      }
    `);
  });

  it('model_no_route (구계리, 의성·안동, 2025-03-26 02:00 KST)', () => {
    expect(view(pick('uiseong_andong_2025/20250325T170000Z.json', 'osm:node/415160471'))).toMatchInlineSnapshot(`
      {
        "en": {
          "broadcast": "This is not a real emergency.
      Attention, residents of Gugye-ri.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time.
      In the computer forecast, there is no checked vehicle route from here. Follow official instructions from the village head and the eup/myeon office. In an emergency, call 119.
      Again: this is not a real emergency; it is a replay of recorded 2025 data.
      Official evacuation orders come first.",
          "call": "[Before the call] Official evacuation orders come first. What follows is model-based planning information, not live information. Fill in the [brackets] yourself.
      [Before the call] Check that the village head has contacted 119 and the eup/myeon office first.
      Hello, this is [your name and role]. I am calling the family of [resident name], who lives in Gugye-ri, about the wildfire evacuation plan.
      This is not a real emergency: it is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time.
      In the computer forecast (the model), there was no checked vehicle route from the village. With a result like this, the village head must call 119 and the eup/myeon office right away and follow official instructions.
      Follow official instructions from the village head and the eup/myeon office. In an emergency, call 119.
      Official evacuation orders come first. The actual place and time of any move may change with official guidance.
      If you have questions, please call [phone number]. Thank you.",
          "card": "Evacuation plan card · Uiseong–Andong · Recorded 2025 wildfire · scenario replay · Not a real emergency
      Gugye-ri (Village)
      No checked vehicle route in the model
      Village head: call 119 and the eup/myeon office now and follow official instructions.
      Residents: follow official instructions from the village head and the eup/myeon office. In an emergency, call 119.
      "No route in the model": no checked route at any departure time or destination checked.
      Official evacuation orders come first.
      Data time: 2025-03-26 02:00 KST · replay of 2025 data
      Model-based planning information · not live
      Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents
      Planning aid only — not for live evacuation operations.
      Scenario ffb1:20250325T170000Z:53e6da7897bf9b5b · Prepared 2026-11-02 14:00 KST · Precomputed 2026-10-18 08:10 KST",
          "lms": "[REPLAY of recorded 2025 data - not a real emergency]
      Wildfire evacuation plan information - Gugye-ri (Village)
      Data time: 2025-03-26 02:00 KST · Precomputed 2026-10-18 08:10 KST

      - No checked vehicle route in the model.
      - Village head: call 119 and the eup/myeon office now and follow official instructions.
      - Residents: follow official instructions from the village head and the eup/myeon office. In an emergency, call 119.

      Official evacuation orders come first.
      Model-based planning information · not live
      Replay of recorded 2025 wildfire scenarios.
      Planning aid only - not for live evacuation operations.",
          "sms": "REPLAY of 2025-03-26 02:00 KST data, not live
      Model-based plan: no checked route.
      Official orders come first. In an emergency, call 119.",
        },
        "kind": "no_route",
        "ko": {
          "broadcast": "이 방송은 실제 상황이 아닙니다.
      구계리 주민 여러분께 알려 드립니다.
      2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보입니다.
      컴퓨터 예측 계산으로는 이곳에서 차로 나가는 확인된 길이 없습니다. 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.
      다시 알려 드립니다. 실제 상황이 아닌 2025년 기록 재현입니다.
      공식 대피 명령이 우선합니다.",
          "call": "[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
      [통화 전 확인] 이장이 119와 읍·면사무소에 먼저 연락했는지 확인하십시오.
      안녕하세요. [소속·이름]입니다. 구계리에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
      지금 드리는 내용은 실제 상황이 아니라, 2025년 3월 26일 새벽 2시 산불 기록을 재현한 모델 기반 계획 정보입니다.
      컴퓨터 예측 계산(모델)으로는 마을에서 차로 나가는 확인된 경로가 없었습니다. 이런 결과라면 이장은 바로 119와 읍·면사무소에 연락해 공식 지시를 따라야 합니다.
      이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.
      공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
      궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.",
          "card": "산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현 · 실제 상황 아님
      구계리 (마을)
      모델상 확인된 차량 경로 없음
      이장: 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따르십시오.
      주민: 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.
      모델상 경로 없음: 점검한 모든 출발 시각과 도착지에서 확인된 경로가 없었다는 뜻입니다.
      공식 대피 명령이 우선합니다.
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
      모델 기반 계획 정보 · 실시간 아님
      차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
      시나리오 ffb1:20250325T170000Z:53e6da7897bf9b5b · 작성 2026-11-02 14:00 KST · 사전 계산 2026-10-18 08:10 KST",
          "lms": "[2025년 기록 재현 · 실제 상황 아님]
      산불 대피 계획 정보 · 구계리(마을)
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 사전 계산 2026-10-18 08:10 KST

      ■ 모델상 확인된 차량 경로가 없습니다.
      ■ 이장: 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따르십시오.
      ■ 주민: 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.

      공식 대피 명령이 우선합니다.
      모델 기반 계획 정보 · 실시간 아님
      2025년 실제 산불 기록을 재현한 시나리오입니다.
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.",
          "sms": "[25.3.26 02:00 기록재현]
      모델상 경로 없음·실시간 아님
      공식명령 우선, 위급 시 119",
        },
      }
    `);
  });

  it('unresolved (광연리, 의성·안동, 2025-03-26 02:00 KST)', () => {
    expect(view(pick('uiseong_andong_2025/20250325T170000Z.json', 'osm:node/415160467'))).toMatchInlineSnapshot(`
      {
        "en": {
          "broadcast": "This is not a real emergency.
      Attention, residents of Gwang-yeon-ri.
      This is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time.
      The computer forecast could not check a vehicle route from here. This means neither that a route exists nor that it does not. Follow official evacuation guidance.
      Again: this is not a real emergency; it is a replay of recorded 2025 data.
      Official evacuation orders come first.",
          "call": "[Before the call] Official evacuation orders come first. What follows is model-based planning information, not live information. Fill in the [brackets] yourself.
      Hello, this is [your name and role]. I am calling the family of [resident name], who lives in Gwang-yeon-ri, about the wildfire evacuation plan.
      This is not a real emergency: it is model-based planning information from a replay of recorded wildfire data, March 26, 2025, 2 a.m. Korea time.
      The computer forecast (the model) could not check a vehicle route from the village (unresolved). This means neither that a route exists nor that it does not. Official evacuation guidance must be followed.
      Official evacuation orders come first. The actual place and time of any move may change with official guidance.
      If you have questions, please call [phone number]. Thank you.",
          "card": "Evacuation plan card · Uiseong–Andong · Recorded 2025 wildfire · scenario replay · Not a real emergency
      Gwang-yeon-ri (Village)
      Unresolved: the model could not check a route
      Unresolved means neither that a route exists nor that it does not.
      Follow official evacuation guidance.
      Official evacuation orders come first.
      Data time: 2025-03-26 02:00 KST · replay of 2025 data
      Model-based planning information · not live
      Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents
      Planning aid only — not for live evacuation operations.
      Scenario ffb1:20250325T170000Z:53e6da7897bf9b5b · Prepared 2026-11-02 14:00 KST · Precomputed 2026-10-18 08:10 KST",
          "lms": "[REPLAY of recorded 2025 data - not a real emergency]
      Wildfire evacuation plan information - Gwang-yeon-ri (Village)
      Data time: 2025-03-26 02:00 KST · Precomputed 2026-10-18 08:10 KST

      - The model could not check a vehicle route (unresolved).
      - Unresolved means neither that a route exists nor that it does not.
      - Follow official evacuation guidance.

      Official evacuation orders come first.
      Model-based planning information · not live
      Replay of recorded 2025 wildfire scenarios.
      Planning aid only - not for live evacuation operations.",
          "sms": "REPLAY of 2025-03-26 02:00 KST data, not live
      Model-based plan: route not checked (unresolved).
      Official orders come first. Follow official guidance.",
        },
        "kind": "unresolved",
        "ko": {
          "broadcast": "이 방송은 실제 상황이 아닙니다.
      광연리 주민 여러분께 알려 드립니다.
      2025년 3월 26일 새벽 2시 기록을 재현한 모델 기반 계획 정보입니다.
      컴퓨터 예측 계산으로는 이곳의 차량 대피 길을 확인하지 못했습니다. 길이 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따르십시오.
      다시 알려 드립니다. 실제 상황이 아닌 2025년 기록 재현입니다.
      공식 대피 명령이 우선합니다.",
          "call": "[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
      안녕하세요. [소속·이름]입니다. 광연리에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
      지금 드리는 내용은 실제 상황이 아니라, 2025년 3월 26일 새벽 2시 산불 기록을 재현한 모델 기반 계획 정보입니다.
      컴퓨터 예측 계산(모델)으로는 마을의 차량 대피 경로를 확인하지 못했습니다(미확인). 경로가 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 대피 안내를 따라야 합니다.
      공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
      궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.",
          "card": "산불 대피 계획 카드 · 의성·안동 · 2025년 실제 산불 기록 기반 시나리오 재현 · 실제 상황 아님
      광연리 (마을)
      미확인: 모델로 확인하지 못함
      미확인은 경로가 있다는 뜻도, 없다는 뜻도 아닙니다.
      공식 대피 안내를 따르십시오.
      공식 대피 명령이 우선합니다.
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
      모델 기반 계획 정보 · 실시간 아님
      차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
      시나리오 ffb1:20250325T170000Z:53e6da7897bf9b5b · 작성 2026-11-02 14:00 KST · 사전 계산 2026-10-18 08:10 KST",
          "lms": "[2025년 기록 재현 · 실제 상황 아님]
      산불 대피 계획 정보 · 광연리(마을)
      자료 기준: 2025년 3월 26일 02:00 (한국 시각) · 사전 계산 2026-10-18 08:10 KST

      ■ 모델로 차량 경로를 확인하지 못했습니다(미확인).
      ■ 미확인은 경로가 있다는 뜻도, 없다는 뜻도 아닙니다.
      ■ 공식 대피 안내를 따르십시오.

      공식 대피 명령이 우선합니다.
      모델 기반 계획 정보 · 실시간 아님
      2025년 실제 산불 기록을 재현한 시나리오입니다.
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.",
          "sms": "[25.3.26 02:00 기록재현]
      모델 경로 미확인·실시간 아님
      공식명령 우선·공식안내 따르십시오",
        },
      }
    `);
  });
});

describe('with the real deadline explanation files, when present', () => {
  it('every origin passes every rule; a reason only where the file agrees with the planner', (ctx) => {
    const found = caches.map((c) => ({ cache: c, ...realExplanationFor(c) }));
    if (found.every((f) => !f.file && !f.error)) {
      console.warn(`no deadline explanation files in ${realExplanationDir().pathname}: real-file check skipped`);
      ctx.skip();
      return;
    }
    const kinds: Record<string, number> = {};
    for (const { cache, file, url, error } of found) {
      expect(error ?? null, url.pathname).toBeNull();
      expect(file, url.pathname).not.toBeNull();
      for (const input of cache.inputs) {
        const fm = buildFieldMessages(input, file);
        const where = `${cache.entry.path} ${input.origin.id}`;
        expect(fm.violations, where).toEqual([]);
        const key = `${fm.kind}/${fm.reason?.kind ?? 'none'}`;
        kinds[key] = (kinds[key] ?? 0) + 1;
        if (fm.kind === 'unresolved') expect(fm.reason).toBeNull();
        // every entry yields the reason its own fields call for (oracle without the detail-code
        // whitelist: a new or renamed code in the files fails here instead of dropping the reason)
        const entry = (file!.origins as Record<string, unknown>)[input.origin.id] as Record<string, unknown> & { binding: Record<string, unknown>[]; exits: Record<string, unknown>[] };
        expect(fm.reason?.kind ?? null, where).toBe(expectedReasonKind(entry, fm));
        const iso = input.scenario.inputTimeIso;
        if (fm.reason?.kind === 'flame_on_route' || fm.reason?.kind === 'dwell_at_destination') {
          const it0 = entry.binding[0]! as { flame_time_s: number; members: number[]; members_total: number };
          expect([fm.reason.flameS, fm.reason.k, fm.reason.n], where).toEqual([it0.flame_time_s, it0.members.length, it0.members_total]);
          const kn = it0.members.length >= it0.members_total ? `${it0.members_total}가지 모두에서` : `${it0.members_total}가지 중 ${it0.members.length}가지에서`;
          expect(fm.text.ko.lms, where).toContain(`산불 예측 시나리오 ${kn}는`);
          expect(fm.text.ko.lms, where).toContain(`${hm(iso, it0.flame_time_s)}쯤 불길이 닿습니다`);
        }
        if (fm.reason?.kind === 'all_exits_blocked') {
          const exits = entry.exits as { flame_time_s: number; members: number[]; members_total: number }[];
          expect([fm.reason.roads, fm.reason.n, fm.reason.kMin, fm.reason.atStart], where).toEqual([
            exits.length,
            exits[0]!.members_total,
            Math.min(...exits.map((x) => x.members.length)),
            exits.every((x) => x.flame_time_s === 0),
          ]);
          expect(fm.text.ko.lms, where).toContain(exits.length === 1 ? '구역을 벗어나는 길은 1곳(' : `구역을 벗어나는 길 ${exits.length}곳(`);
        }
        if (fm.reason?.kind === 'time_window' || fm.reason?.kind === 'no_flame_avoiding_route') {
          expect(fm.text.ko.lms, where).toContain(`다음 점검 시각인 ${hm(iso, entry.next_offset_s as number)}에 출발하면`);
        }
        // reasons say no more than the file establishes: exits are the roads out of the area reachable
        // without meeting flames (not "the roads out of the village"); "no destination" claims cover the
        // destinations checked (candidate shelters) only
        for (const lang of ['ko', 'en'] as const) {
          for (const t of Object.values(allTexts(fm, lang))) expect(t, input.origin.id).not.toMatch(/차로 빠져나갈 수 있는|out of (this village|this facility|here) by car|도착지가 없습니다|no destination can be reached/);
        }
        if (fm.reason?.kind === 'all_exits_blocked') {
          expect(fm.text.ko.lms).toMatch(/이 (마을|시설)에서 불길을 만나지 않고 차로 갈 수 있는 구역을 벗어나는 길/);
          expect(fm.text.en.lms).toMatch(/leading out of the area reachable by car from this (village|facility) without meeting flames/);
        }
      }
    }
    console.info(`real explanation files: ${JSON.stringify(kinds)}`);
    // pinned: the six files shipped in planner/public/data/explanations/ (generated at code_commit
    // 6855cc61). A change in the files' classes or codes must show up here, not pass unnoticed.
    expect(kinds).toEqual({
      'leave_by/flame_on_route': 8,
      'leave_by/no_flame_avoiding_route': 7,
      'leave_by/time_window': 131,
      'leave_by/none': 355,
      'no_route/all_exits_blocked': 10,
      'no_route/no_route_flames': 1,
      'unresolved/none': 19,
    });
  });
});
