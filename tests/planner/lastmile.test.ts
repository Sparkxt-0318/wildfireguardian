/**
 * Last-mile kit (planner/src/features/lastmile): templates per verdict, length rules, the
 * deadline-explanation contract and its fail-closed fallback, the rule checks, the CSV and the
 * language registry. All data is SYNTHETIC (tests/planner/lastmile.fixture.ts); the property tests
 * over the six booth caches are in lastmile.cache.test.ts.
 */
import { beforeEach, describe, expect, it } from 'vitest';
import {
  BROADCAST_MAX_S,
  enSpokenWords,
  eucKrBytes,
  gsm7Length,
  koReadAloud,
  koSpokenSyllables,
  nativeKorean,
  sinoKorean,
  SMS_EN_MAX_GSM7,
  SMS_KO_MAX_BYTES,
  spokenSeconds,
} from '../../planner/src/features/lastmile/encoding';
import { cardText, enDateSpoken, enSpokenTime, koDateSpoken, koSmsDate, koSpokenTime } from '../../planner/src/features/lastmile/compose';
import {
  clearExplanationCache,
  explanationUrl,
  loadExplanation,
  parseExplanationFile,
  roadLabel,
  selectReason,
  usableItem,
} from '../../planner/src/features/lastmile/explanation';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import { allTexts, buildFieldMessages, enabledLangs, TEMPLATES } from '../../planner/src/features/lastmile/messages';
import { checkFieldMessages, clockTimes, maskData } from '../../planner/src/features/lastmile/checks';
import { fieldMessagesCSV, fieldMessagesFileName, LASTMILE_CSV_COLUMNS } from '../../planner/src/features/lastmile/csv';
import { FORBIDDEN, LANGUAGES, MODEL_NOT_LIVE, NOT_REAL, OFFICIAL_FIRST, RESIDENT_119_NOW, SHIPPED_LANGS } from '../../planner/src/features/lastmile/strings';
import { cells, EXIT, ITEM, SYN_IDS, SYN_INPUT_TIME, SYN_NO_ROUTE_ID, SYN_REGION, SYN_SET, synExplanation, synInput, synNoLater, synNoRoute, synUnresolved, withEntry, withId } from './lastmile.fixture';

const EXPECT = { regionId: SYN_REGION, inputTimeIso: SYN_INPUT_TIME, scenarioSetId: SYN_SET };

function texts(fm: ReturnType<typeof buildFieldMessages>): string[] {
  return SHIPPED_LANGS.flatMap((l) => Object.values(allTexts(fm, l)));
}

describe('lengths: EUC-KR bytes, GSM-7, spoken time', () => {
  it('counts strict EUC-KR (KS X 1001): ASCII 1, Hangul and · 2, flags characters outside', () => {
    expect(eucKrBytes('ab 1').bytes).toBe(4);
    expect(eucKrBytes('공식명령 우선').bytes).toBe(13);
    expect(eucKrBytes('·').bytes).toBe(2);
    const r = eucKrBytes('A—B'); // em dash is not in KS X 1001
    expect(r.verified).toBe(true);
    expect(r.unencodable).toEqual(['—']);
    expect(eucKrBytes('똠').unencodable).toEqual(['똠']); // a Hangul syllable outside the 2,350 of KS X 1001
  });

  it('counts GSM-7 septets (extension table = 2) and flags non-GSM characters', () => {
    expect(gsm7Length('Leave by 18:40 KST.').chars).toBe(19);
    expect(gsm7Length('a{b}').chars).toBe(6);
    expect(gsm7Length('a·b').nonGsm).toEqual(['·']);
    expect(gsm7Length('합성').nonGsm.length).toBe(2);
  });

  it('reads numbers aloud the Korean way (native hours and counters, Sino minutes and dates, 119 digit by digit)', () => {
    expect(sinoKorean(2025)).toBe('이천이십오');
    expect(sinoKorean(40)).toBe('사십');
    expect(nativeKorean(4)).toBe('네');
    expect(koReadAloud('오후 6시 40분')).toBe('오후 여섯시 사십분');
    expect(koReadAloud('4가지 중 2가지')).toBe('네 가지 중 두 가지');
    expect(koReadAloud('119에 연락')).toBe('일일구에 연락');
    expect(koSpokenSyllables('2025년 3월 24일')).toBe(12); // 이천이십오년 삼월 이십사일
    expect(koSpokenSyllables('새벽 2시 20분')).toBe(7); // 새벽 두시 이십분
  });

  it('counts English words pessimistically (every digit is a word; a.m./p.m. two)', () => {
    expect(enSpokenWords('Leave by 6:40 p.m.')).toBe(2 + 3 + 2);
    expect(enSpokenWords('Call 119 now.')).toBe(1 + 3 + 1);
    expect(spokenSeconds('one two three four', 'en')).toBe(2);
    expect(spokenSeconds('가나다', 'ko')).toBe(1);
  });
});

describe('time wording (KST)', () => {
  it('speaks clock times for older listeners', () => {
    expect(koSpokenTime(SYN_INPUT_TIME, 2400)).toBe('오후 6시 40분');
    expect(koSpokenTime('2025-03-25T17:00:00Z', 1200)).toBe('새벽 2시 20분');
    expect(koSpokenTime('2025-03-25T15:00:00Z', 600)).toBe('밤 12시 10분');
    expect(koSpokenTime('2025-03-23T01:00:00Z', 0)).toBe('오전 10시');
    expect(koSpokenTime('2025-03-24T03:00:00Z', 0)).toBe('낮 12시');
    expect(koSpokenTime('2025-03-24T12:30:00Z', 0)).toBe('밤 9시 30분');
    expect(enSpokenTime(SYN_INPUT_TIME, 2400)).toBe('6:40 p.m.');
    expect(enSpokenTime('2025-03-25T19:00:00Z', 0)).toBe('4 a.m.');
    expect(koSmsDate(SYN_INPUT_TIME)).toBe('25.3.24 18:00');
    expect(koDateSpoken(SYN_INPUT_TIME)).toBe('2025년 3월 24일 오후 6시');
    expect(enDateSpoken(SYN_INPUT_TIME)).toBe('March 24, 2025, 6 p.m.');
  });

  it('finds the clock times a text names (date-time stamps excluded)', () => {
    expect(clockTimes('자료 기준: 2025년 3월 24일 18:00 (한국 시각). 18:40까지')).toEqual(['18:40']);
    expect(clockTimes('2025년 3월 24일 오후 6시 기록. 오후 6시 40분까지')).toEqual(['18:40']);
    expect(clockTimes('March 24, 2025, 6 p.m. Korea time. Leave by 6:40 p.m.')).toEqual(['18:40']);
    expect(clockTimes('25.3.24 18:00 재현 · 작성 2026-11-02 14:00 KST')).toEqual([]);
    expect(clockTimes('새벽 2시 20분 · 밤 12시')).toEqual(['02:20', '00:00']);
  });
});

describe('message plan per verdict', () => {
  it('checked_route with a contiguous basis → leave_by T, the destination checked at every time up to T', () => {
    const p = messagePlan(synInput());
    expect(p.kind).toBe('leave_by');
    expect(p.leaveByS).toBe(1800);
    expect(p.destination?.id).toBe('syn:dest:a');
    expect(p.destinationVaries).toBe(false);
    expect(p.destination?.arrivalS).toBe(3300);
    expect(p.after).toBe('none_checked');
    expect(p.nextOffsetS).toBe(2400);
    expect(p.nextVerdict).toBe('model_no_route');
    expect(p.reason).toBeNull();
  });

  it('a deadline at the end of the recorded window says later times were not checked (horizon)', () => {
    const p = messagePlan(synInput({ plan: { bestVerdict: 'checked_route', latestSafeDepartureS: 3000, contiguousSafeDepartureS: 3000, sweep: cells(Array(6).fill('checked_route')), note: null } }));
    expect(p.kind).toBe('leave_by');
    expect(p.after).toBe('horizon');
    expect(p.nextOffsetS).toBeNull();
  });

  it('a gap before the deadline: the message stops at the contiguous basis (never the later headline time)', () => {
    const p = messagePlan(
      synInput({
        plan: {
          bestVerdict: 'checked_route',
          latestSafeDepartureS: 3000,
          contiguousSafeDepartureS: 1200,
          sweep: cells(['checked_route', 'checked_route', 'checked_route', 'unresolved', 'checked_route', 'checked_route']),
          note: null,
        },
      }),
    );
    expect(p.kind).toBe('leave_by');
    expect(p.leaveByS).toBe(1200);
    expect(p.after).toBe('gap');
  });

  it('no contiguous basis (the first departure time is not checked) → partial, no departure time', () => {
    const fm = buildFieldMessages(
      synInput({
        plan: {
          bestVerdict: 'checked_route',
          latestSafeDepartureS: 1800,
          contiguousSafeDepartureS: null,
          sweep: cells(['unresolved', 'unresolved', 'unresolved', 'checked_route', 'unresolved', 'unresolved']),
          note: null,
        },
      }),
    );
    expect(fm.kind).toBe('partial');
    expect(fm.leaveByS).toBeNull();
    expect(fm.violations).toEqual([]);
    for (const t of texts(fm)) expect(t).not.toMatch(/18:30|오후 6시 30분|6:30 p\.m\./);
    // generic: the fail-closed case never claims that leaving at the data time was unchecked
    expect(fm.text.ko.lms).toContain('출발 시각에 따라 모델 결과가 달라, 출발 시각을 하나로 안내하지 않습니다.');
    expect(fm.text.en.lms).toContain('Model results differ by departure time, so no single departure time is given.');
    for (const t of texts(fm)) expect(t).not.toMatch(/자료 시각\(18:00\)|leaving at the data time/);
  });

  it('an inconsistent contiguous basis (claims a time the sweep does not support) fails closed to partial', () => {
    const p = messagePlan(
      synInput({ plan: { bestVerdict: 'checked_route', latestSafeDepartureS: 1800, contiguousSafeDepartureS: 1800, sweep: cells(['checked_route', 'unresolved', 'checked_route', 'checked_route', 'model_no_route', 'model_no_route']), note: null } }),
    );
    expect(p.kind).toBe('partial');
  });

  it('no single destination checked at every time up to T → the message says the destination varies', () => {
    const a = (d: string, v: 'checked_route' | 'model_no_route', off: number) => ({ destinationId: d, verdict: v, arrivalS: v === 'checked_route' ? off + 900 : null });
    const p = messagePlan(
      synInput({
        plan: {
          bestVerdict: 'checked_route',
          latestSafeDepartureS: 600,
          contiguousSafeDepartureS: 600,
          sweep: cells([
            { v: 'checked_route', attempts: [a('syn:dest:a', 'checked_route', 0), a('syn:dest:b', 'model_no_route', 0)] },
            { v: 'checked_route', attempts: [a('syn:dest:a', 'model_no_route', 600), a('syn:dest:b', 'checked_route', 600)] },
            'model_no_route',
            'model_no_route',
            'model_no_route',
            'model_no_route',
          ]),
          note: null,
        },
      }),
    );
    expect(p.destinationVaries).toBe(true);
    const fm = buildFieldMessages(synInput({ plan: p.input.plan }));
    expect(fm.text.ko.lms).toContain('도착지는 출발 시각에 따라 다릅니다');
    expect(fm.violations).toEqual([]);
  });

  it('window-closed departure times are not requests: they never break the contiguous run', () => {
    const p = messagePlan(
      synInput({ plan: { bestVerdict: 'checked_route', latestSafeDepartureS: 1200, contiguousSafeDepartureS: 1200, sweep: cells(['checked_route', 'checked_route', 'checked_route', 'window_closed', 'window_closed', 'window_closed']), note: null } }),
    );
    expect(p.kind).toBe('leave_by');
    expect(p.nextVerdict).toBe('window');
    // nothing after T was requested: "not checked with this data", never "no checked route"
    expect(p.after).toBe('horizon');
    const fm = buildFieldMessages(p.input);
    expect(fm.text.ko.lms).toContain('모델이 점검한 마지막 출발 시각이 18:20입니다. 그보다 늦은 출발은 점검하지 않았습니다');
    expect(fm.text.en.lms).toContain('18:20 KST is the last departure time the model checked. Later departures were not checked');
    expect(fm.text.en.lms).not.toContain('have no checked route');
    // the card never calls it a fire deadline
    expect(fm.text.ko.card.big?.label).toBe('점검한 마지막 출발');
    expect(fm.text.en.card.big?.label).toBe('Checked up to');
  });

  it('model_no_route → no_route; unresolved, not computed and not checkable → unresolved', () => {
    expect(messagePlan(synNoRoute()).kind).toBe('no_route');
    expect(messagePlan(synUnresolved()).kind).toBe('unresolved');
    expect(messagePlan(synInput({ plan: null })).kind).toBe('unresolved');
    const nc = buildFieldMessages(synInput({ plan: { bestVerdict: 'unresolved', latestSafeDepartureS: null, contiguousSafeDepartureS: null, sweep: [], note: 'not_checkable' } }));
    expect(nc.kind).toBe('unresolved');
    expect(nc.text.ko.lms).toContain('2 km 안에 점검할 수 있는 도로 지점이 없어');
  });
});

describe('templates per verdict', () => {
  it('leave_by: leave-by time, destination, arrival, after-deadline fact, data time, official-first, model line', () => {
    const fm = buildFieldMessages(synInput());
    expect(fm.violations).toEqual([]);
    const ko = fm.text.ko;
    // the replay marker comes first in every SMS and long text
    expect(ko.sms.split('\n')).toEqual(['[25.3.24 18:00 기록재현]', '모델상 18:30까지 차로 출발', '공식명령 우선·실시간 아님']);
    expect(ko.lms.split('\n')[0]).toBe('[2025년 기록 재현 · 실제 상황 아님]');
    expect(ko.lms).toContain('18:30(오후 6시 30분)까지 차로 출발하십시오');
    expect(ko.lms).toContain('모델이 점검한 도착지: 합성초등학교. 18:30에 출발하면 18:55쯤 도착합니다(차로 약 25분, 교통 정체 미반영).');
    expect(ko.lms).toContain('18:30보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다.');
    expect(ko.lms).toContain(OFFICIAL_FIRST.ko);
    expect(ko.lms).toContain(MODEL_NOT_LIVE.ko);
    // a replay broadcast opens with "not a real situation"; the no-car line is never dropped
    expect(ko.broadcast.split('\n')[0]).toBe(NOT_REAL.ko);
    expect(ko.broadcast).toContain('오후 6시 30분까지 차로 출발하십시오. 합성초등학교까지 가는 길이 컴퓨터 예측 계산으로 확인되었습니다.');
    expect(ko.broadcast).toContain('차가 없는 분은 이장에게 바로 알리십시오.');
    expect(ko.card.big).toEqual({ label: '출발 마감', time: '18:30', sub: '오후 6시 30분 · 한국 시각' });
    expect(ko.card.statusIcon).toBe('checked_route');
    expect(ko.card.badges).toContain('실제 상황 아님');
    const en = fm.text.en;
    expect(en.sms.split('\n')).toEqual(['REPLAY of 2025-03-24 18:00 KST data, not live', 'Model-based plan: leave by car no later than 18:30 KST.', 'Official orders come first.']);
    expect(en.lms.split('\n')[0]).toBe('[REPLAY of recorded 2025 data - not a real emergency]');
    expect(en.lms).toContain('Destination the model checked: Hapseong Elementary School.');
    expect(en.broadcast.split('\n')[0]).toBe(NOT_REAL.en);
    expect(en.broadcast).toContain('Leave by car no later than 6:30 p.m. The computer forecast checked a route to Hapseong Elementary School');
    expect(en.broadcast).toContain('If you have no car, tell the village head now.');
    expect(en.broadcast).not.toContain('p.m..');
  });

  it('a facility or a far road entry point: the no-car line names the eup/myeon office; > 500 m the broadcast says where the times apply', () => {
    const base = synInput();
    const fac = buildFieldMessages({ ...base, origin: { ...base.origin, kind: 'facility', name: { ko: '합성요양원', en: 'Hapseong Care Home' }, display: { ko: '합성요양원', en: 'Hapseong Care Home' }, category: { ko: '요양시설', en: 'Care home' }, entryDistanceM: 1240 } });
    expect(fac.violations).toEqual([]);
    expect(fac.text.ko.broadcast).toContain('차가 부족하면 읍·면사무소에 바로 알리십시오.');
    expect(fac.text.ko.broadcast).toContain('시각은 시설에서 1.2 km 떨어진 도로 기준입니다.');
    expect(fac.text.en.broadcast).toContain('Times are for the road 1.2 km from the facility.');
    expect(fac.text.ko.call).toContain('시설에서 1.2 km 떨어진 도로에서 오후 6시 30분까지 차로 출발하면');
    // the unnamed destination: no OSM id for residents, the id only in the card's staff footer
    const unnamed = buildFieldMessages({ ...base, destinations: { ...base.destinations, 'syn:dest:a': { ...base.destinations['syn:dest:a']!, name: null, display: { ko: '이름 없는 학교 · way 77', en: 'Unnamed school · way 77' } } } });
    expect(unnamed.violations).toEqual([]);
    for (const l of ['ko', 'en'] as const) {
      expect(unnamed.text[l].sms + unnamed.text[l].lms + unnamed.text[l].broadcast + unnamed.text[l].call).not.toContain('way 77');
      expect(unnamed.text[l].card.meta).toContain('syn:dest:a');
    }
    expect(unnamed.text.ko.lms).toContain('모델이 점검한 도착지: 지도 자료에 이름이 없는 학교.');
    expect(unnamed.text.ko.broadcast).toContain('이름 없는 학교까지 가는 길이');
  });

  it('no_route: contact 119 / 읍·면사무소 now and follow official instructions — no departure time, no tactical advice', () => {
    const fm = buildFieldMessages(synNoRoute());
    expect(fm.violations).toEqual([]);
    expect(fm.text.ko.sms.split('\n')).toEqual(['[25.3.24 18:00 기록재현]', '모델상 경로 없음·실시간 아님', '공식명령 우선, 위급 시 119']);
    // staff (long text, card) contact 119 and the office now; residents and families follow official instructions
    expect(fm.text.ko.lms).toContain('이장: 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따르십시오.');
    expect(fm.text.ko.lms).toContain('주민: 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.');
    expect(fm.text.en.lms).toContain('Village head: call 119 and the eup/myeon office now and follow official instructions.');
    expect(fm.text.ko.broadcast).toContain('이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.');
    expect(fm.text.ko.call).toContain('이런 결과라면 이장은 바로 119와 읍·면사무소에 연락해 공식 지시를 따라야 합니다.');
    expect(fm.text.en.broadcast).toContain('Follow official instructions from the village head and the eup/myeon office. In an emergency, call 119.');
    for (const l of ['ko', 'en'] as const) for (const t of [fm.text[l].sms, fm.text[l].broadcast, fm.text[l].call]) expect(t).not.toMatch(RESIDENT_119_NOW[l]);
    expect(fm.text.ko.card.statusIcon).toBe('model_no_route');
    expect(fm.text.ko.card.big).toBeNull();
    for (const t of texts(fm)) {
      expect(t).not.toMatch(/까지\s*(차로\s*)?출발|출발하(십시오|세요)|leave by|depart by/i);
      expect(t).not.toMatch(/실내|머무|stay|shelter in place|shelter-in-place/i);
    }
  });

  it('unresolved: could not be checked → follow official evacuation guidance; never safe, never green', () => {
    const fm = buildFieldMessages(synUnresolved());
    expect(fm.violations).toEqual([]);
    expect(fm.text.ko.sms.split('\n')).toEqual(['[25.3.24 18:00 기록재현]', '모델 경로 미확인·실시간 아님', '공식명령 우선·공식안내 따르십시오']);
    expect(fm.text.ko.lms).toContain('미확인은 경로가 있다는 뜻도, 없다는 뜻도 아닙니다.');
    expect(fm.text.en.lms).toContain('Unresolved means neither that a route exists nor that it does not.');
    expect(fm.text.ko.card.statusIcon).toBe('unresolved');
    for (const t of texts(fm)) {
      expect(t).not.toMatch(/안전|safe/i);
      expect(clockTimes(maskData(t, fm.inserted)).every((c) => c === '18:00')).toBe(true);
    }
  });

  it('every output, every verdict: no forbidden word and no promise of pickup, vehicle or rescue', () => {
    for (const input of [synInput(), synNoRoute(), synUnresolved()]) {
      for (const expl of [null, synExplanation()]) {
        const fm = buildFieldMessages(input, expl);
        expect(fm.violations).toEqual([]);
        for (const t of texts(fm)) for (const w of [...FORBIDDEN.ko, ...FORBIDDEN.en]) expect(t.toLowerCase()).not.toContain(w.toLowerCase());
      }
    }
  });

  it('MOCK and test data are marked in every output; the Korean SMS still fits 90 bytes', () => {
    for (const flags of [{ mock: true }, { testData: true }]) {
      for (const input of [synInput(flags), { ...synNoRoute(), ...flags }, { ...synUnresolved(), ...flags }]) {
        const fm = buildFieldMessages(input);
        expect(fm.violations).toEqual([]);
        const word = 'mock' in flags ? 'MOCK' : '시험';
        expect(fm.text.ko.sms).toContain(word);
        expect(fm.text.ko.lms).toContain(word === 'MOCK' ? 'MOCK' : '시험 데이터');
        expect(fm.text.en.sms.split('\n')[0]).toContain(word === 'MOCK' ? 'MOCK REPLAY' : 'TEST REPLAY');
        expect(fm.text.ko.sms.split('\n')[0]).toContain(word);
        expect(fm.metrics.ko.smsUnits).toBeLessThanOrEqual(SMS_KO_MAX_BYTES);
        expect(fm.metrics.en.smsUnits).toBeLessThanOrEqual(SMS_EN_MAX_GSM7);
      }
    }
  });

  it('worst-case dates (two-digit month and day) and long names still fit every limit', () => {
    const long = '구 축산항초등학교 경정분교 터';
    const base = synInput({ scenario: { scenarioSetId: SYN_SET, inputTimeIso: '2025-12-24T09:00:00Z', horizonS: 3600 } });
    const inputs = [
      { ...base, origin: { ...base.origin, name: { ko: '의성장애인복지센터', en: '의성장애인복지센터' }, display: { ko: '의성장애인복지센터', en: '의성장애인복지센터' }, kind: 'facility' as const, category: { ko: '사회복지시설', en: 'Social facility' } } },
      { ...base, destinations: { ...base.destinations, 'syn:dest:a': { ...base.destinations['syn:dest:a']!, name: { ko: long, en: long }, display: { ko: long, en: long } } } },
    ];
    for (const kindInput of [...inputs, { ...synNoRoute(), scenario: base.scenario }, { ...synUnresolved(), scenario: base.scenario }]) {
      for (const flags of [{}, { mock: true }]) {
        const fm = buildFieldMessages({ ...kindInput, ...flags }, null);
        expect(fm.violations).toEqual([]);
        expect(fm.metrics.ko.broadcastS).toBeLessThanOrEqual(BROADCAST_MAX_S);
      }
    }
  });
});

describe('deadline explanation (wfg.explanation/1): loading and fallback', () => {
  beforeEach(() => clearExplanationCache());

  it('builds a same-origin URL under the app base path', () => {
    expect(explanationUrl('yeongdeok_2025', '2025-03-25T19:00:00Z', '/')).toBe('/data/explanations/yeongdeok_2025__20250325T190000Z.json');
    expect(explanationUrl('yeongdeok_2025', '2025-03-25T19:00:00Z', '/wildfireguardian/')).toBe('/wildfireguardian/data/explanations/yeongdeok_2025__20250325T190000Z.json');
    expect(explanationUrl('uiseong_andong_2025', '2025-03-24T09:00:00Z', './')).toBe('./data/explanations/uiseong_andong_2025__20250324T090000Z.json');
    expect(explanationUrl('x', '2025-03-24T09:00:00Z', '/base')).toBe('/base/data/explanations/x__20250324T090000Z.json');
  });

  const respond = (status: number, body: unknown, type = 'application/json') =>
    (async () => new Response(typeof body === 'string' ? body : JSON.stringify(body), { status, headers: { 'content-type': type } })) as unknown as typeof fetch;

  it('missing file, SPA fallback HTML, network error → absent; bad JSON or another scenario → invalid; never throws', async () => {
    expect((await loadExplanation(EXPECT, { base: '/a/', fetchImpl: respond(404, 'not found', 'text/plain') })).state).toBe('absent');
    expect((await loadExplanation(EXPECT, { base: '/b/', fetchImpl: respond(200, '<!doctype html><html></html>', 'text/html') })).state).toBe('absent');
    expect((await loadExplanation(EXPECT, { base: '/c/', fetchImpl: (async () => Promise.reject(new Error('offline'))) as unknown as typeof fetch })).state).toBe('absent');
    expect((await loadExplanation(EXPECT, { base: '/d/', fetchImpl: respond(200, '{not json') })).state).toBe('invalid');
    expect((await loadExplanation(EXPECT, { base: '/e/', fetchImpl: respond(200, { ...synExplanation(), schema: 'wfg.explanation/2' }) })).state).toBe('invalid');
    expect((await loadExplanation(EXPECT, { base: '/f/', fetchImpl: respond(200, { ...synExplanation(), scenario_set_id: 'ffb1:other' }) })).state).toBe('invalid');
    expect((await loadExplanation(EXPECT, { base: '/g/', fetchImpl: respond(200, { ...synExplanation(), input_time: '2025-03-24T10:00:00Z' }) })).state).toBe('invalid');
    const ok = await loadExplanation(EXPECT, { base: '/h/', fetchImpl: respond(200, synExplanation()) });
    expect(ok.state).toBe('ready');
    expect(parseExplanationFile({ ...synExplanation(), input_time: '2025-03-24T09:00:00+00:00' }, EXPECT).ok).toBe(true);
  });

  it('without the file the messages carry no reason line (never fabricated)', () => {
    const without = buildFieldMessages(synInput(), null);
    expect(without.reason).toBeNull();
    for (const t of texts(without)) expect(t).not.toMatch(/이유|Why:|The reason|합성로|Hapseong-ro/);
  });

  it('a consistent explanation adds the plain reason: road, time, k of n (the card in fewer words)', () => {
    const fm = buildFieldMessages(synInput(), synExplanation());
    expect(fm.violations).toEqual([]);
    expect(fm.reason).toMatchObject({ kind: 'flame_on_route', k: 2, n: 4, flameS: 2700, slackS: 600 });
    expect(fm.text.ko.lms).toContain('이유: 산불 예측 시나리오 4가지 중 2가지에서 합성로에 18:45쯤 불길이 닿습니다. 18:30보다 늦게 출발하면 그곳에서 불길과 만날 수 있습니다.');
    expect(fm.text.en.lms).toContain('Why: in 2 of 4 fire scenarios from the forecast, flames reach Hapseong-ro around 18:45 KST. If you leave after 18:30, you may meet the fire there.');
    expect(fm.text.ko.call).toContain('산불 예측 시나리오 4가지 중 2가지에서 합성로에 오후 6시 45분쯤 불길이 닿습니다.');
    expect(cardText(fm.text.ko.card)).toContain('이유: 산불 예측 시나리오 4가지 중 2가지에서 합성로에 18:45쯤 불길이 닿습니다.');
    expect(cardText(fm.text.en.card)).toContain('Why: in 2 of 4 fire scenarios from the forecast, flames reach Hapseong-ro around 18:45.');
    expect(fm.text.ko.sms).not.toContain('합성로'); // no room in 90 bytes: the SMS never carries the reason
  });

  it('model_no_route: all exits blocked → road names and k of n per road, but no clock time and no departure window', () => {
    const fm = buildFieldMessages(synNoRoute(), synExplanation());
    expect(fm.violations).toEqual([]);
    expect(fm.reason).toMatchObject({ kind: 'all_exits_blocked', roads: 3, kMin: 1, n: 4, atStart: false });
    expect(fm.text.ko.lms).toContain(
      '이유: 이 마을에서 차로 빠져나갈 수 있는 길 3곳(합성로·7번 도로·이름 없는 도로)이 모두 자료 시각부터 1시간 안에 불길에 막힙니다(길마다 산불 예측 시나리오 4가지 중 최소 1가지에서).',
    );
    expect(fm.text.en.lms).toContain(
      'Why: all 3 roads out of this village by car (Hapseong-ro, Route 7, an unnamed road) are blocked by flames within 1 hour of the data time (on each road, in at least 1 of 4 fire scenarios from the forecast).',
    );
    for (const t of texts(fm)) expect(clockTimes(maskData(t, fm.inserted)).every((c) => c === '18:00')).toBe(true);
    expect(clockTimes('ffb1:20250324T090000Z')).toEqual([]);
  });

  it('one exit, or exits with the same label: singular wording, no duplicate names, "already" at the data time', () => {
    const one = buildFieldMessages(synNoRoute(SYN_IDS.exitOne), synExplanation());
    expect(one.violations).toEqual([]);
    expect(one.reason).toMatchObject({ kind: 'all_exits_blocked', roads: 1, kMin: 4, atStart: true });
    expect(one.text.ko.lms).toContain('이유: 이 마을에서 차로 빠져나갈 수 있는 길은 1곳(합성리 부근 도로)뿐이며, 자료 시각에 이미 불길에 막혀 있습니다(산불 예측 시나리오 4가지 모두에서).');
    expect(one.text.en.lms).toContain('Why: the only road out of this village by car (the road near Hapseong-ri) is already blocked by flames at the data time (in all 4 fire scenarios from the forecast).');
    const dup = buildFieldMessages(synNoRoute(SYN_IDS.exitDup), synExplanation());
    expect(dup.violations).toEqual([]);
    expect(dup.reason).toMatchObject({ kind: 'all_exits_blocked', roads: 2, atStart: true });
    expect(dup.text.ko.lms).toContain('길 2곳(합성리 부근 도로)이 모두 자료 시각에 이미 불길에 막혀 있습니다(길마다 산불 예측 시나리오 4가지 모두에서).');
    expect(dup.text.en.lms).toContain('both roads out of this village by car (the road near Hapseong-ri) are already blocked by flames at the data time (on each road, in all 4 fire scenarios from the forecast).');
    const win = buildFieldMessages(synNoRoute(SYN_IDS.noRouteWindow), synExplanation());
    expect(win.violations).toEqual([]);
    expect(win.reason).toMatchObject({ kind: 'no_route_window', closeS: 3600 });
    expect(win.text.ko.lms).toContain('이유: 점검한 어느 출발 시각에도, 산불 예측 시나리오상 불길을 피해 가는 길로는 1시간 자료 범위 안에 도착지에 닿을 수 없습니다.');
  });

  it('deadlines set by the one-hour range or by the last departure checked are never presented as fire deadlines', () => {
    const ex = synExplanation();
    // window_fire_free for every destination checked at T
    const free = buildFieldMessages(withId(synInput(), SYN_IDS.windowFree), ex);
    expect(free.violations).toEqual([]);
    expect(free.reason).toEqual({ kind: 'window_fire_free', closeS: 3600 });
    expect(free.text.ko.lms).toContain('18:30보다 늦은 출발은 1시간 자료 범위 안에 도착할 수 없어 점검하지 못했습니다. 불길 때문이라는 뜻은 아닙니다.');
    expect(free.text.en.lms).toContain('Departures after 18:30 could not be checked within the 1-hour data range; this is not a fire prediction.');
    expect(free.text.ko.card.big?.label).toBe('점검한 마지막 출발');
    expect(free.text.en.card.big?.label).toBe('Checked up to');
    // another destination checked at T is fire-limited: no "not a fire" claim, the neutral line stays
    const mixed = buildFieldMessages(withId(synInput(), SYN_IDS.windowMixed), ex);
    expect(mixed.reason).toBeNull();
    expect(mixed.text.ko.lms).toContain('18:30보다 늦은 출발 시각에는 모델로 확인된 경로가 없습니다.');
    expect(mixed.text.ko.card.big?.label).toBe('출발 마감');
    // window_fire_detour: a fire reason for the message's destination
    const detour = buildFieldMessages(withId(synInput(), SYN_IDS.detour), ex);
    expect(detour.violations).toEqual([]);
    expect(detour.reason).toEqual({ kind: 'window_fire_detour', closeS: 3600 });
    expect(detour.text.ko.lms).toContain('이유: 18:30보다 늦게 출발하면 산불 예측 시나리오상 불길을 피해 가는 길로는 자료 범위가 끝나는 19:00까지 도착지에 닿을 수 없습니다.');
    expect(detour.text.ko.card.big?.label).toBe('출발 마감');
    // no_later_offset: T is the last departure checked (the planner's own horizon line; no file needed)
    const later = buildFieldMessages(synNoLater(SYN_IDS.noLater), ex);
    expect(later.violations).toEqual([]);
    expect(later.reason).toBeNull();
    expect(later.text.ko.lms).toContain('모델이 점검한 마지막 출발 시각이 18:50입니다. 그보다 늦은 출발은 점검하지 않았습니다(자료 범위: 자료 시각부터 1시간). 불길 때문에 정해진 시각이 아닙니다.');
    expect(later.text.ko.card.big?.label).toBe('점검한 마지막 출발');
    // unresolved_next is never turned into a reason
    expect(buildFieldMessages(withId(synInput(), SYN_IDS.unresolvedNext), ex).reason).toBeNull();
    // none of these says that flames set the time
    for (const fm of [free, later]) for (const t of texts(fm)) expect(t).not.toMatch(/이유:|Why:/);
  });

  it('an entry that disagrees with the planner, or is not fully usable, is ignored', () => {
    const id = 'syn:origin:checked';
    const ok = synExplanation().origins[id]!;
    const bad: Record<string, unknown>[] = [
      { ...ok, binding: [ITEM({ destination_ids: ['syn:dest:b'] })] }, // the item is about another destination
      { ...ok, binding: [ITEM({ destination_ids: undefined })] },
      { ...ok, binding: [ITEM({ flame_time_s: 9999 }), ITEM()] }, // only binding[0] (the shown route's item) is read
      { ...ok, binding: [ITEM({ members: [0, 4] })] }, // members are suffixes 0 … members_total − 1
      { ...ok, verdict_summary: 'model_no_route' },
      { ...ok, deadline_offset_s: 1200 },
      { ...ok, next_offset_s: 3000 },
      { ...ok, next_verdict: 'unresolved' }, // planner says model_no_route next
      { ...ok, status: 'not_explainable' },
      { ...ok, reason_code: 'unresolved_next' },
      { ...ok, status: 'explained_partial', binding: [] },
      { ...ok, binding: [ITEM({ flame_time_s: 4000 })] }, // outside the recorded window
      { ...ok, binding: [ITEM({ flame_time_s: Number.NaN })] },
      { ...ok, binding: [ITEM({ members: [] })] },
      { ...ok, binding: [ITEM({ members: [1, 1] })] },
      { ...ok, binding: [ITEM({ members: [0, 9] })] },
      { ...ok, binding: [ITEM({ pass_time_at_deadline_s: 2800 })] }, // flames before the vehicle passes
      { ...ok, binding: [ITEM({ slack_s: -5 })] },
      { ...ok, binding: [ITEM({ label_source: 'invented' })] },
      { ...ok, binding: [ITEM({ label_ko: 'x'.repeat(41), label_en: 'x' })] },
      { ...ok, binding: 'nope' },
    ];
    for (const entry of bad) {
      const fm = buildFieldMessages(synInput(), withEntry(id, entry));
      expect(fm.reason).toBeNull();
      expect(fm.violations).toEqual([]);
    }
    // explained_partial WITH a usable item is used
    expect(buildFieldMessages(synInput(), withEntry(id, { ...ok, status: 'explained_partial' })).reason).not.toBeNull();
    // the gap basis (message time ≠ deadline D) never takes D's explanation
    const gap = synInput({
      plan: { bestVerdict: 'checked_route', latestSafeDepartureS: 1800, contiguousSafeDepartureS: 600, sweep: cells(['checked_route', 'checked_route', 'unresolved', 'checked_route', 'model_no_route', 'model_no_route']), note: null },
    });
    expect(buildFieldMessages(gap, synExplanation()).reason).toBeNull();
    // unresolved origins are never explained, whatever the file says
    expect(buildFieldMessages(synUnresolved(), withEntry('syn:origin:unresolved', { ...ok, verdict_summary: 'unresolved', status: 'explained' })).reason).toBeNull();
    // no_route: one unusable exit → no "all n roads" sentence
    const nr = synExplanation().origins[SYN_NO_ROUTE_ID]!;
    expect(buildFieldMessages(synNoRoute(), withEntry(SYN_NO_ROUTE_ID, { ...nr, exits: [...nr.exits, ITEM({ flame_time_s: -1 })] })).reason).toBeNull();
  });

  it('labels roads only from the data: OSM name, ref, nearby place or "unnamed"', () => {
    expect(roadLabel({ label_ko: '7', label_en: '7', label_source: 'osm_ref' })!.text).toEqual({ ko: '7번 도로', en: 'Route 7' });
    expect(roadLabel({ label_ko: '국도7호선', label_en: null, label_source: 'osm_ref' })!.text).toEqual({ ko: '국도7호선', en: '국도7호선' });
    expect(roadLabel({ label_ko: '신석리 부근', label_en: 'near Sinseok-ri', label_source: 'nearest_place' })!.text).toEqual({ ko: '신석리 부근 도로', en: 'the road near Sinseok-ri' });
    expect(roadLabel({ label_ko: null, label_en: null, label_source: 'osm_name' })!.text).toEqual({ ko: '이름 없는 도로', en: 'an unnamed road' });
    expect(usableItem(ITEM(), 3600, 1800)).toBe(true);
    expect(selectReason(undefined, { kind: 'leave_by', latestS: 1800, leaveByS: 1800, nextOffsetS: 2400, nextVerdict: 'model_no_route', destinationId: 'syn:dest:a', horizonS: 3600 })).toBeNull();
    expect(usableItem(EXIT({ members: [0, 1, 2, 3] }), 3600, null)).toBe(true);
    expect(usableItem(EXIT({ members: [0, 1, 2, 4] }), 3600, null)).toBe(false);
  });
});

describe('rule checks (fail closed)', () => {
  it('detect a forbidden word, a missing mandatory line, an over-long SMS and a departure time in a no-route message', () => {
    const fm = buildFieldMessages(synNoRoute());
    const tamper = (f: (t: typeof fm.text.ko) => void) => {
      const copy = structuredClone(fm);
      f(copy.text.ko);
      return checkFieldMessages(copy);
    };
    expect(tamper((t) => (t.lms += '\n안전한 길입니다')).join()).toContain('forbidden word "안전"');
    expect(tamper((t) => (t.lms = t.lms.replace(OFFICIAL_FIRST.ko, '')))).toContain(`ko.lms: missing "${OFFICIAL_FIRST.ko}"`);
    expect(tamper((t) => (t.call += '\n19:10까지 출발하십시오.')).join()).toContain('departure instruction');
    expect(tamper((t) => (t.broadcast += ' 오후 7시 10분')).join()).toContain('clock time 19:10');
    expect(tamper((t) => (t.broadcast += '\n지금 바로 119에 연락하십시오.')).join()).toContain('ko.broadcast: tells residents or families to call 119 now');
    expect(tamper((t) => (t.sms = t.sms.split('\n').reverse().join('\n'))).join()).toContain('ko.sms: the first line does not say it is a replay');
    expect(tamper((t) => (t.broadcast = t.broadcast.split('\n').slice(1).join('\n'))).join()).toContain('ko.broadcast: does not open with');
    const long = structuredClone(fm);
    long.metrics.ko.smsUnits = 91;
    expect(checkFieldMessages(long).join()).toContain('91 bytes > 90');
  });

  it('a place name from the data is masked: a village called "안전마을" does not trip the word check', () => {
    const input = synInput({ origin: { ...synInput().origin, name: { ko: '안전마을', en: 'Anjeon-maeul' }, display: { ko: '안전마을', en: 'Anjeon-maeul' } } });
    expect(buildFieldMessages(input).violations).toEqual([]);
  });
});

describe('CSV of every message (per region / input time)', () => {
  it('one row per origin in urgency order, UTF-8 BOM, CRLF, multi-line cells quoted', () => {
    const items = [buildFieldMessages(synUnresolved()), buildFieldMessages(synInput()), buildFieldMessages(synNoRoute())].map((fm, i) => ({ ...fm, urgencyRank: [3, 1, 2][i]! }));
    const csv = fieldMessagesCSV(items, { lang: 'ko' });
    expect(csv.startsWith('﻿')).toBe(true);
    const header = csv.slice(1).split('\r\n')[0]!;
    expect(header.split(',')).toEqual(LASTMILE_CSV_COLUMNS.ko);
    const ids = [...csv.matchAll(/\r\n(\d+),(syn:origin:[a-z]+),/g)].map((m) => `${m[1]}:${m[2]}`);
    expect(ids).toEqual(['1:syn:origin:checked', '2:syn:origin:noroute', '3:syn:origin:unresolved']);
    expect(csv).toContain('"[25.3.24 18:00 기록재현]\n모델상 18:30까지 차로 출발\n공식명령 우선·실시간 아님"');
    expect(csv).toContain('한국어: 원어민·현장 검토 전 · English: 원어민·현장 검토 전');
    expect(csv.endsWith('\r\n')).toBe(true);
    // a text that fails a rule check is never exported
    const failing = { ...items[1]!, violations: ['ko.sms: 91 bytes > 90'] };
    const out = fieldMessagesCSV([failing], { lang: 'ko' });
    expect(out).toContain('검사 실패 — 사용 금지: ko.sms: 91 bytes > 90');
    expect(out).not.toContain('모델상 18:30까지 차로 출발');
    expect(fieldMessagesFileName(synInput({ mock: true }))).toBe('wfg_synthetic_region_20250324T090000Z_field_messages_MOCK.csv');
  });
});

describe('languages: Korean source + English; more only after native-speaker review', () => {
  it('every shipped language has a full template set and an SMS encoding', () => {
    expect([...SHIPPED_LANGS]).toEqual(['ko', 'en']);
    expect(LANGUAGES.ko.role).toBe('source');
    for (const l of SHIPPED_LANGS) {
      expect(TEMPLATES[l].lang).toBe(l);
      for (const k of ['sms', 'lms', 'broadcastBlocks', 'call', 'card'] as const) expect(typeof TEMPLATES[l][k]).toBe('function');
    }
    expect(enabledLangs()).toEqual(['ko', 'en']);
  });

  it('a registered translation that is not the brief-required English stays disabled until reviewed', () => {
    for (const [code, meta] of Object.entries(LANGUAGES)) {
      if (code === 'ko' || code === 'en') continue;
      expect(meta.enabled && meta.nativeSpeakerReview !== 'done').toBe(false);
    }
  });
});

describe('synthetic snapshots (both languages)', () => {
  it('leave_by with a consistent explanation', () => {
    const fm = buildFieldMessages(synInput(), synExplanation());
    expect({ ko: allTexts(fm, 'ko'), en: allTexts(fm, 'en') }).toMatchInlineSnapshot(`
      {
        "en": {
          "broadcast": "This is not a real emergency.
      Attention, residents of Hapseong-ri.
      This is model-based planning information from a replay of recorded wildfire data, March 24, 2025, 6 p.m. Korea time.
      Leave by car no later than 6:30 p.m. The computer forecast checked a route to Hapseong Elementary School for departures up to then.
      If you have no car, tell the village head now.
      Follow official guidance on where to go.
      In 2 of 4 fire scenarios from the forecast, flames reach Hapseong-ro around 6:45 p.m.
      Again: this is not a real emergency; it is a replay of recorded 2025 data.
      Official evacuation orders come first.",
          "call": "[Before the call] Official evacuation orders come first. What follows is model-based planning information, not live information. Fill in the [brackets] yourself.
      Hello, this is [your name and role]. I am calling the family of [resident name], who lives in Hapseong-ri, about the wildfire evacuation plan.
      This is not a real emergency: it is model-based planning information from a replay of recorded wildfire data, March 24, 2025, 6 p.m. Korea time.
      In the computer forecast (the model), leaving by car from the road near the village no later than 6:30 p.m. gives a checked route to Hapseong Elementary School.
      In 2 of 4 fire scenarios from the forecast, flames reach Hapseong-ro around 6:45 p.m.
      Official evacuation orders come first. The actual place and time of any move may change with official guidance.
      If you have questions, please call [phone number]. Thank you.",
          "card": "Evacuation plan card · Synthetic region · Recorded 2025 wildfire · scenario replay · Not a real emergency
      Hapseong-ri (Village)
      Checked vehicle route in the model
      Leave by 18:30 (6:30 p.m. KST)
      Do not wait until this time: leave by car early.
      Model-checked destination: Hapseong Elementary School; leave 18:30, arrive around 18:55 (about 25 min by car; traffic not included)
      Why: in 2 of 4 fire scenarios from the forecast, flames reach Hapseong-ro around 18:45.
      Follow official guidance on where to go. No car or need help? Tell the village head or eup/myeon office now.
      Official evacuation orders come first.
      Data time: 2025-03-24 18:00 KST · Replay of recorded 2025 wildfire scenarios
      Model-based planning information · not live
      Times at the road entry point 120 m away; boarding time not included · Vehicle travel only · traffic, road closures and smoke not in the model · not yet tested with residents
      Planning aid only — not for live evacuation operations.
      Scenario ffb1:20250324T090000Z:synthetic0000 · Prepared 2026-11-02 14:00 KST · Precomputed 2026-10-18 07:54 KST",
          "lms": "[REPLAY of recorded 2025 data - not a real emergency]
      Wildfire evacuation plan information - Hapseong-ri (Village)
      Data time: 2025-03-24 18:00 KST

      - Leave by car no later than 18:30 KST (6:30 p.m.). Do not wait until that time.
      - Destination the model checked: Hapseong Elementary School. Leaving at 18:30, arrival around 18:55 KST (about 25 min by car; traffic not included).
      - Why: in 2 of 4 fire scenarios from the forecast, flames reach Hapseong-ro around 18:45 KST. If you leave after 18:30, you may meet the fire there.
      - Follow official guidance on where to go and which roads to use.
      - If you have no car or cannot move on your own, tell the village head or the eup/myeon office now.
      - Times refer to the nearest road point (entry point), 120 m from the village. Time to get ready and board is not included.

      Official evacuation orders come first.
      Model-based planning information · not live
      Replay of recorded 2025 wildfire scenarios.
      Planning aid only - not for live evacuation operations.",
          "sms": "REPLAY of 2025-03-24 18:00 KST data, not live
      Model-based plan: leave by car no later than 18:30 KST.
      Official orders come first.",
        },
        "ko": {
          "broadcast": "이 방송은 실제 상황이 아닙니다.
      합성마을 주민 여러분께 알려 드립니다.
      2025년 3월 24일 오후 6시 기록을 재현한 모델 기반 계획 정보입니다.
      오후 6시 30분까지 차로 출발하십시오. 합성초등학교까지 가는 길이 컴퓨터 예측 계산으로 확인되었습니다.
      차가 없는 분은 이장에게 바로 알리십시오.
      대피 장소는 공식 안내를 따르십시오.
      공식 대피 명령이 우선합니다.",
          "call": "[통화 전 확인] 공식 대피 명령이 우선합니다. 아래 내용은 모델 기반 계획 정보이며, 실시간 정보가 아닙니다. [ ] 안은 직접 채워 말하십시오.
      안녕하세요. [소속·이름]입니다. 합성마을에 사시는 [어르신 성함]의 가족분께 산불 대피 계획을 알려 드리려고 전화드렸습니다.
      지금 드리는 내용은 실제 상황이 아니라, 2025년 3월 24일 오후 6시 산불 기록을 재현한 모델 기반 계획 정보입니다.
      컴퓨터 예측 계산(모델)으로는 마을 근처 도로에서 오후 6시 30분까지 차로 출발하면 합성초등학교까지 가는 경로가 확인되었습니다.
      산불 예측 시나리오 4가지 중 2가지에서 합성로에 오후 6시 45분쯤 불길이 닿습니다.
      공식 대피 명령이 우선합니다. 실제 이동 장소와 시각은 공식 안내에 따라 바뀔 수 있습니다.
      궁금하신 점은 [연락처]로 연락해 주십시오. 감사합니다.",
          "card": "산불 대피 계획 카드 · 합성 지역 · 2025년 실제 산불 기록 기반 시나리오 재현 · 실제 상황 아님
      합성마을 (마을)
      모델로 확인된 차량 경로 있음
      출발 마감 18:30 (오후 6시 30분 · 한국 시각)
      이 시각까지 기다리지 말고 미리 차로 출발하십시오.
      모델이 점검한 도착지: 합성초등학교 · 18:30 출발 시 18:55쯤 도착(차로 약 25분, 교통 정체 미반영)
      이유: 산불 예측 시나리오 4가지 중 2가지에서 합성로에 18:45쯤 불길이 닿습니다.
      실제 대피 장소와 길은 공식 안내를 따르십시오. 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
      공식 대피 명령이 우선합니다.
      자료 기준: 2025년 3월 24일 18:00 (한국 시각) · 2025년 실제 산불 기록을 재현한 시나리오
      모델 기반 계획 정보 · 실시간 아님
      시각은 마을에서 120 m 떨어진 도로 지점(진입 지점) 기준, 준비·탑승 시간 제외 · 차량 이동만 계산 · 교통 정체·도로 통제·연기 미반영 · 주민·현장 검증 전
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.
      시나리오 ffb1:20250324T090000Z:synthetic0000 · 작성 2026-11-02 14:00 KST · 사전 계산 2026-10-18 07:54 KST",
          "lms": "[2025년 기록 재현 · 실제 상황 아님]
      산불 대피 계획 정보 · 합성마을
      자료 기준: 2025년 3월 24일 18:00 (한국 시각)

      ■ 18:30(오후 6시 30분)까지 차로 출발하십시오. 이 시각까지 기다리지 마십시오.
      ■ 모델이 점검한 도착지: 합성초등학교. 18:30에 출발하면 18:55쯤 도착합니다(차로 약 25분, 교통 정체 미반영).
      ■ 이유: 산불 예측 시나리오 4가지 중 2가지에서 합성로에 18:45쯤 불길이 닿습니다. 18:30보다 늦게 출발하면 그곳에서 불길과 만날 수 있습니다.
      ■ 실제 대피 장소와 길은 공식 안내를 따르십시오.
      ■ 차가 없거나 혼자 움직이기 어려우면 이장이나 읍·면사무소에 바로 알리십시오.
      ■ 시각은 마을에서 120 m 떨어진 가장 가까운 도로 지점(진입 지점) 기준이며, 준비·탑승 시간은 포함되지 않았습니다.

      공식 대피 명령이 우선합니다.
      모델 기반 계획 정보 · 실시간 아님
      2025년 실제 산불 기록을 재현한 시나리오입니다.
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.",
          "sms": "[25.3.24 18:00 기록재현]
      모델상 18:30까지 차로 출발
      공식명령 우선·실시간 아님",
        },
      }
    `);
  });

  it('no_route with all exits blocked', () => {
    const fm = buildFieldMessages(synNoRoute(), synExplanation());
    expect({ sms_ko: fm.text.ko.sms, lms_ko: fm.text.ko.lms, broadcast_ko: fm.text.ko.broadcast, sms_en: fm.text.en.sms, broadcast_en: fm.text.en.broadcast }).toMatchInlineSnapshot(`
      {
        "broadcast_en": "This is not a real emergency.
      Attention, residents of Hapseong-ri.
      This is model-based planning information from a replay of recorded wildfire data, March 24, 2025, 6 p.m. Korea time.
      In the computer forecast, there is no checked vehicle route from here. Follow official instructions from the village head and the eup/myeon office. In an emergency, call 119.
      In the forecast, all 3 roads out of here by car are blocked by flames within 1 hour.
      Again: this is not a real emergency; it is a replay of recorded 2025 data.
      Official evacuation orders come first.",
        "broadcast_ko": "이 방송은 실제 상황이 아닙니다.
      합성마을 주민 여러분께 알려 드립니다.
      2025년 3월 24일 오후 6시 기록을 재현한 모델 기반 계획 정보입니다.
      컴퓨터 예측 계산으로는 이곳에서 차로 나가는 확인된 길이 없습니다. 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.
      산불 예측에서는 이곳에서 차로 빠져나갈 수 있는 길 3곳이 모두 1시간 안에 불길에 막힙니다.
      공식 대피 명령이 우선합니다.",
        "lms_ko": "[2025년 기록 재현 · 실제 상황 아님]
      산불 대피 계획 정보 · 합성마을
      자료 기준: 2025년 3월 24일 18:00 (한국 시각)

      ■ 모델상 확인된 차량 경로가 없습니다.
      ■ 이장: 지금 바로 119와 읍·면사무소에 연락해 공식 지시를 따르십시오.
      ■ 주민: 이장과 읍·면사무소의 공식 지시를 따르십시오. 위급하면 119에 신고하십시오.
      ■ 이유: 이 마을에서 차로 빠져나갈 수 있는 길 3곳(합성로·7번 도로·이름 없는 도로)이 모두 자료 시각부터 1시간 안에 불길에 막힙니다(길마다 산불 예측 시나리오 4가지 중 최소 1가지에서).

      공식 대피 명령이 우선합니다.
      모델 기반 계획 정보 · 실시간 아님
      2025년 실제 산불 기록을 재현한 시나리오입니다.
      사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.",
        "sms_en": "REPLAY of 2025-03-24 18:00 KST data, not live
      Model-based plan: no checked route.
      Official orders come first. In an emergency, call 119.",
        "sms_ko": "[25.3.24 18:00 기록재현]
      모델상 경로 없음·실시간 아님
      공식명령 우선, 위급 시 119",
      }
    `);
  });
});
