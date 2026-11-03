/**
 * Property tests of the last-mile kit over SEEDED SYNTHETIC cases (lastmile.generator.ts, mulberry32,
 * no new dependency): inputs the six booth caches do not contain — any date and hour, other horizons
 * and departure steps, gaps, late first checks, window-closed tails, missing / Hangul-only / long
 * names, far entry points, live results, MOCK and test-data flags, explanation entries of every
 * reason code, consistent or not. For every case and every output, in Korean and English: no rule
 * violation (the module's own checks), and independently of the module: the message kind follows
 * the planner's verdict, a leave-by time is the contiguous basis with every earlier requested time
 * checked, no departure instruction or clock time without a checked departure window, no forbidden
 * word, no Hangul read in English, never a green status without a checked route, the arrival clock and
 * minutes from one rounding, the MOCK / test markers, an origin without a result never called
 * computed, the reason the explanation entry calls for, and every length limit (Korean bytes counted
 * again with Python's `euc_kr` codec).
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { enDateSpoken, hm, koDateSpoken } from '../../planner/src/features/lastmile/compose';
import { maskData } from '../../planner/src/features/lastmile/checks';
import { BROADCAST_MAX_S, LMS_MAX_BYTES, SMS_EN_MAX_GSM7, SMS_KO_MAX_BYTES, spokenSeconds } from '../../planner/src/features/lastmile/encoding';
import { allTexts, buildFieldMessages, type FieldMessages } from '../../planner/src/features/lastmile/messages';
import { OFFICIAL_FIRST } from '../../planner/src/features/lastmile/strings';
import { generateCases, type GenCase } from './lastmile.generator';
import { DEPART, expectedReasonKind, GSM7, HANGUL, leaveByOutputFacts, NEVER, pythonEucKr } from './lastmile.oracle';

/** Fixed seed (the date of this test); the cases are the same on every run. */
const SEED = 20261103;
const COUNT = 600;

let cases: (GenCase & { fm: FieldMessages })[] = [];

beforeAll(() => {
  cases = generateCases(SEED, COUNT).map((c) => ({ ...c, fm: buildFieldMessages(c.input, c.file) }));
}, 120_000);

const where = (c: GenCase) => `case ${c.n} [${c.tags.join(' ')}] ${c.input.scenario.inputTimeIso}`;

/** Independent of the module: every generated check has a job id, so an origin has a result iff its sweep holds a check. */
const hasResult = (c: GenCase) => (c.input.plan?.sweep ?? []).some((x) => x.attempts.length > 0);

describe(`seeded synthetic cases (mulberry32, seed ${SEED}, ${COUNT} cases)`, () => {
  it('the generator is deterministic and covers every message kind, reason kind and flag', () => {
    const again = generateCases(SEED, 25).map((c) => buildFieldMessages(c.input, c.file));
    expect(again.map((fm) => allTexts(fm, 'ko').lms)).toEqual(cases.slice(0, 25).map((c) => allTexts(c.fm, 'ko').lms));
    const seen = new Set<string>();
    for (const c of cases) {
      seen.add(`kind:${c.fm.kind}`);
      seen.add(`reason:${c.fm.reason?.kind ?? 'none'}`);
      if (c.fm.kind === 'leave_by') seen.add(`after:${c.fm.plan.after}`);
      if (c.input.mock) seen.add('mock');
      if (c.input.testData) seen.add(`test:${c.input.provenance.source}`);
      if (!hasResult(c)) seen.add(`no_result:${c.input.provenance.source}`);
      if (c.fm.plan.destinationVaries) seen.add('destination_varies');
    }
    for (const k of [
      'kind:leave_by',
      'kind:partial',
      'kind:no_route',
      'kind:unresolved',
      'after:horizon',
      'after:none_checked',
      'after:gap',
      'reason:none',
      'reason:flame_on_route',
      'reason:dwell_at_destination',
      'reason:time_window',
      'reason:no_flame_avoiding_route',
      'reason:all_exits_blocked',
      'reason:entry_in_flame',
      'reason:no_route_flames',
      'reason:no_route_time_window',
      'mock',
      'test:cache',
      'test:live',
      'no_result:cache',
      'no_result:live',
      'destination_varies',
    ]) {
      expect(seen.has(k), k).toBe(true);
    }
  });

  it('every output of every case passes the module rule checks', () => {
    const bad = cases.filter((c) => c.fm.violations.length).map((c) => `${where(c)}: ${c.fm.violations.join(' | ')}`);
    expect(bad).toEqual([]);
  });

  it('the message follows the planner: leave_by only with a contiguous checked run up to T; never green otherwise', () => {
    for (const c of cases) {
      const plan = c.input.plan;
      const v = plan?.bestVerdict ?? 'unresolved';
      const fm = c.fm;
      if (fm.kind === 'leave_by' || fm.kind === 'partial') expect(v, where(c)).toBe('checked_route');
      if (fm.kind === 'no_route') expect(v, where(c)).toBe('model_no_route');
      if (fm.kind === 'unresolved') expect(v, where(c)).toBe('unresolved');
      expect(fm.text.ko.card.statusIcon, where(c)).toBe(fm.kind === 'leave_by' ? 'checked_route' : fm.kind === 'no_route' ? 'model_no_route' : 'unresolved');
      if (fm.kind === 'leave_by') {
        const T = fm.leaveByS!;
        expect(T, where(c)).toBe(plan!.contiguousSafeDepartureS);
        const upTo = plan!.sweep.filter((x) => x.verdict !== 'window_closed' && x.offsetS <= T);
        expect(upTo.length).toBeGreaterThan(0);
        expect(upTo.every((x) => x.verdict === 'checked_route'), where(c)).toBe(true);
        // the destination named is checked at T
        const d = fm.plan.destination;
        if (d) expect(upTo[upTo.length - 1]!.attempts.some((a) => a.destinationId === d.id && a.verdict === 'checked_route'), where(c)).toBe(true);
      }
    }
  });

  it('no departure instruction and no clock time but the data time without a checked departure window; leave_by names its time', () => {
    for (const c of cases) {
      const iso = c.input.scenario.inputTimeIso;
      const texts = [...Object.values(allTexts(c.fm, 'ko')), ...Object.values(allTexts(c.fm, 'en'))].map((t) => maskData(t, c.fm.inserted));
      if (c.fm.kind === 'leave_by') {
        expect(c.fm.text.ko.sms, where(c)).toContain(`${hm(iso, c.fm.leaveByS!)}까지 차로 출발`);
        continue;
      }
      // the spoken data time ("July 9, 2025, 10:30 p.m.", "2025년 7월 9일 밤 10시 30분") is the data time itself
      const spokenData = [koDateSpoken(iso), enDateSpoken(iso)];
      for (const t0 of texts) {
        const t = spokenData.reduce((acc, d) => acc.split(d).join(' '), t0);
        expect(t, where(c)).not.toMatch(DEPART);
        // HH:MM other than the data time, after removing date-time stamps; no spoken clock time at all
        const stripped = t.replace(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}|\d{2}\.\d{1,2}\.\d{1,2} \d{2}:\d{2}|\d{4}년 \d{1,2}월 \d{1,2}일 \d{2}:\d{2}/g, '');
        for (const m of stripped.matchAll(/(?<![\w:.])(\d{2}):(\d{2})(?![\d:])/g)) expect(`${m[1]}:${m[2]}`, where(c)).toBe(hm(iso));
        expect(stripped, where(c)).not.toMatch(/(새벽|오전|낮|오후|밤) \d{1,2}시|\d{1,2}(:\d{2})? [ap]\.m\./);
      }
    }
  });

  it('no forbidden word; no Hangul read in English; the data time and "official orders come first" in every output', () => {
    for (const c of cases) {
      const iso = c.input.scenario.inputTimeIso;
      for (const lang of ['ko', 'en'] as const) {
        const t = allTexts(c.fm, lang);
        for (const x of Object.values(t)) expect(maskData(x, c.fm.inserted), where(c)).not.toMatch(NEVER);
        for (const k of ['sms', 'lms', 'card'] as const) expect(t[k], where(c)).toContain(hm(iso));
        for (const k of ['lms', 'broadcast', 'call', 'card'] as const) expect(t[k], where(c)).toContain(OFFICIAL_FIRST[lang]);
      }
      for (const t of [c.fm.text.en.broadcast, c.fm.text.en.call]) expect(t, where(c)).not.toMatch(HANGUL);
    }
  });

  it('MOCK and test data are marked in every output (the SMS and the long text on their first line)', () => {
    for (const c of cases) {
      const first = (t: string) => t.split('\n')[0]!;
      if (c.input.mock) {
        for (const l of ['ko', 'en'] as const) for (const t of [first(c.fm.text[l].sms), first(c.fm.text[l].lms), c.fm.text[l].card.badges.join(' ')]) expect(t, where(c)).toContain('MOCK');
        expect(c.fm.text.ko.broadcast + c.fm.text.ko.call, where(c)).toContain('모의 서버');
      }
      if (c.input.testData) {
        expect(first(c.fm.text.ko.sms), where(c)).toContain('시험');
        expect(first(c.fm.text.en.sms), where(c)).toContain('TEST');
        expect(c.fm.text.ko.card.badges, where(c)).toContain('시험 데이터 · 평가 호스트 아님');
        expect(c.fm.text.ko.broadcast, where(c)).toContain('시험용');
      }
      // a live result never carries the precomputed cache's stamp
      if (c.input.provenance.source === 'live') for (const l of ['ko', 'en'] as const) for (const t of Object.values(allTexts(c.fm, l))) expect(t, where(c)).not.toMatch(/사전 계산|Precomputed/);
    }
  });

  it('an origin without a result is never called computed (data line, card staff line); a live one is never test data', () => {
    for (const c of cases) {
      const has = hasResult(c);
      expect(c.input.provenance.computed, where(c)).toBe(has);
      const line = (l: 'ko' | 'en') => c.fm.text[l].lms.split('\n')[2]!;
      if (has) {
        expect(line('ko'), where(c)).not.toContain('결과 없음');
        if (c.input.provenance.source === 'live') expect(line('ko'), where(c)).toContain(' · API 점검 결과 · 계산 호스트 ');
        continue;
      }
      expect(line('ko').endsWith(' · 이 출발지 결과 없음'), where(c)).toBe(true);
      expect(line('en').endsWith(' · no result for this origin'), where(c)).toBe(true);
      for (const l of ['ko', 'en'] as const) expect(c.fm.text[l].card.meta.endsWith(l === 'ko' ? ' · 이 출발지 결과 없음' : ' · no result for this origin'), where(c)).toBe(true);
      for (const l of ['ko', 'en'] as const) for (const t of Object.values(allTexts(c.fm, l))) expect(t, where(c)).not.toMatch(/API 점검 결과|API results|계산 호스트|host unknown|사전 계산 2|Precomputed 2/);
      if (c.input.provenance.source === 'live') expect(c.input.testData, where(c)).toBe(false);
    }
  });

  it('a reason only where the explanation entry establishes it (oracle from the entry\'s own fields), never for unresolved', () => {
    for (const c of cases) {
      const entry = c.file ? (c.file.origins as Record<string, unknown>)[c.input.origin.id] : undefined;
      expect(c.fm.reason?.kind ?? null, where(c)).toBe(c.file ? expectedReasonKind(entry, c.fm) : null);
      if (c.fm.kind === 'unresolved' || c.fm.kind === 'partial') expect(c.fm.reason, where(c)).toBeNull();
    }
  });

  it('what each output of a leave-by message gives (LASTMILE.md §2), every leave-by case: varying destinations, gaps, markers', () => {
    const seen = new Set<string>();
    const bad: string[] = [];
    for (const c of cases) {
      if (c.fm.kind !== 'leave_by') continue;
      const f = leaveByOutputFacts(c.fm);
      bad.push(...f.violations.map((v) => `${where(c)}: ${v}`));
      if (c.fm.plan.destinationVaries) seen.add('varies');
      if (f.noLatinName) seen.add('no_latin_name');
      if (c.input.mock || c.input.testData) seen.add('marker');
      for (const l of ['ko', 'en'] as const) seen.add(`${l}.broadcast_reason:${f.broadcastReason[l]}`);
      if (c.fm.plan.after) seen.add(`after:${c.fm.plan.after}`);
    }
    expect(bad).toEqual([]);
    // the cases reach the branches the booth caches do not (a destination that varies, gaps, markers)
    for (const k of ['varies', 'no_latin_name', 'marker', 'ko.broadcast_reason:true', 'ko.broadcast_reason:false', 'en.broadcast_reason:true', 'after:gap', 'after:horizon', 'after:none_checked']) expect(seen.has(k), k).toBe(true);
  });

  it('the arrival clock and the travel minutes agree (one rounding)', () => {
    let n = 0;
    for (const c of cases) {
      const m = c.fm.text.ko.lms.match(/(\d{2}):(\d{2})에 출발하면 (\d{2}):(\d{2})쯤 도착합니다\(차로 약 (\d+)분/);
      if (!m) continue;
      n += 1;
      const dep = Number(m[1]) * 60 + Number(m[2]);
      const arr = Number(m[3]) * 60 + Number(m[4]);
      expect((arr - dep + 1440) % 1440, where(c)).toBe(Number(m[5]));
      // never earlier than the model's arrival
      const a = c.fm.plan.destination!.arrivalS!;
      expect(Math.ceil(a / 60) * 60, where(c)).toBeLessThanOrEqual(c.fm.leaveByS! + 60 * Number(m[5]) + 60);
    }
    expect(n).toBeGreaterThan(50);
  });

  it('every length limit holds (Korean bytes recounted with Python euc_kr, GSM-7 class, spoken seconds)', () => {
    for (const c of cases) {
      expect(GSM7.test(c.fm.text.en.sms), where(c)).toBe(true);
      expect(c.fm.text.en.sms.length, where(c)).toBeLessThanOrEqual(SMS_EN_MAX_GSM7);
      expect(spokenSeconds(c.fm.text.ko.broadcast, 'ko'), where(c)).toBeLessThanOrEqual(BROADCAST_MAX_S);
      expect(spokenSeconds(c.fm.text.en.broadcast, 'en'), where(c)).toBeLessThanOrEqual(BROADCAST_MAX_S);
    }
    const sms = cases.map((c) => c.fm.text.ko.sms);
    const lms = cases.flatMap((c) => [c.fm.text.ko.lms, c.fm.text.en.lms]);
    const py = pythonEucKr([...sms, ...lms]);
    if (!py) {
      console.warn('python3 not found: independent EUC-KR recount skipped (module counts still enforced)');
      return;
    }
    py.slice(0, sms.length).forEach((b, i) => expect(b, where(cases[i]!)).toBeLessThanOrEqual(SMS_KO_MAX_BYTES));
    py.slice(sms.length).forEach((b, i) => {
      expect(typeof b, lms[i]).toBe('number');
      expect(b as number).toBeLessThanOrEqual(LMS_MAX_BYTES);
    });
  }, 60_000);
});
