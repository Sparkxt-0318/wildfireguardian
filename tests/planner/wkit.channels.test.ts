/**
 * W-KIT channel outputs (planner/src/features/lastmile/channels/build.ts), checked over EVERY origin of the six booth
 * caches and the kit's 600 generated synthetic cases, plus unit tests of each rule. The module's own checks
 * (checkChannels) are re-tested with independent oracles: Python's strict euc_kr codec for byte counts, the kit's
 * NEVER / DEPART patterns (lastmile.oracle.ts) and a separate clock-time regex.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { hm } from '../../planner/src/features/lastmile/compose';
import { OFFICIAL_FIRST, OFFICIAL_FIRST_SMS } from '../../planner/src/features/lastmile/strings';
import { smsSegments } from '../../planner/src/features/lastmile/encoding';
import { buildFieldMessages } from '../../planner/src/features/lastmile/messages';
import { messagePlan, type MessagePlan } from '../../planner/src/features/lastmile/plan';
import {
  buildChannels,
  checkChannels,
  ELEMENTS,
  HEAD_CORE_MAX_S,
  HEAD_FULL_MAX_S,
  orderNotIssued,
  CBS_CHAR_LIMIT,
  cbsChars,
  cbsClassFor,
  transportNeedList,
  validIssuer,
  contactLine,
  contactSeconds,
  outputWithheld,
  DECREE_FIELDS,
  RESIDENT_OUTPUTS,
  HEAD_CONTACT_MAX_S,
  namedDestination,
  type ChannelSet,
  type Reply,
} from '../../planner/src/features/lastmile/channels/build';
import { loadBoothCaches } from './lastmile.cachedata';
import { generateCases } from './lastmile.generator';
import { DEPART, NEVER, pythonEucKr } from './lastmile.oracle';
import { synInput, cells } from './lastmile.fixture';

const NOW = '2026-11-12T10:00:00Z';
let real: MessagePlan[] = [];
let syn: MessagePlan[] = [];
const ORDER = { status: 'not_issued' as const, suppliedBy: '합성 읍사무소 담당자', suppliedAtIso: '2026-11-12T09:30:00Z', expiresAtIso: '2026-11-12T11:00:00Z' };
const ISSUE = { leaveByS: 1800, issueByS: { low: 900, median: 600, high: -60 } };
const build = (p: MessagePlan) => buildChannels(p, { nowIso: NOW, orderStatus: ORDER, issueOrderBy: ISSUE });
let realInputs: ReturnType<typeof loadBoothCaches>[number]['inputs'] = [];

beforeAll(() => {
  realInputs = loadBoothCaches().flatMap((c) => c.inputs);
  real = realInputs.map((i) => messagePlan(i, null));
  syn = generateCases(20261102, 600).map((g) => messagePlan(g.input, g.file));
}, 300_000);

function residentTexts(s: ChannelSet): string[] {
  return (['ko', 'en'] as const).flatMap((l) => {
    const t = s.text[l];
    return [t.head.script, t.voice, t.familyText, t.familyScript.join('\n')];
  });
}

function masked(p: MessagePlan, text: string): string {
  let s = text;
  const names = [p.input.origin.name, ...Object.values(p.input.destinations).map((d) => d.name)].flatMap((n) => (n ? [n.ko, n.en] : [])).filter(Boolean) as string[];
  for (const n of names.sort((a, b) => b.length - a.length)) s = s.split(n).join('#');
  return s;
}

describe('booth caches: every real origin', () => {
  it('531 origins, every output passes its own checks', () => {
    expect(real.length).toBe(531);
    const bad = real.map(build).filter((s) => s.violations.length);
    expect(bad.map((s) => `${s.originId}: ${s.violations.join('; ')}`)).toEqual([]);
  });

  it('head core ≤ 20 s with all five warning elements; full script ≤ 35 s', () => {
    for (const p of real) {
      const s = build(p);
      for (const l of ['ko', 'en'] as const) {
        expect(s.text[l].head.coreS).toBeLessThanOrEqual(HEAD_CORE_MAX_S);
        expect(s.text[l].head.fullS).toBeLessThanOrEqual(HEAD_FULL_MAX_S);
        expect(s.text[l].head.elements).toEqual([...ELEMENTS]);
      }
    }
  });

  it('independent oracles: Python euc_kr ≤ 90 bytes for the Korean family text; no NEVER word; no departure instruction or extra clock time unless leave_by', () => {
    const sets = real.map(build);
    const bytes = pythonEucKr(sets.map((s) => s.text.ko.familyText));
    expect(bytes, 'python3 with the euc_kr codec is required for this oracle').not.toBeNull();
    for (const b of bytes!) expect(typeof b === 'number' && b <= 90).toBe(true);
    sets.forEach((s, i) => {
      const p = real[i]!;
      for (const t of residentTexts(s)) {
        expect(NEVER.test(masked(p, t))).toBe(false);
        if (p.kind !== 'leave_by') {
          expect(DEPART.test(masked(p, t))).toBe(false);
          const times = [...masked(p, t).matchAll(/\b([01]\d|2[0-3]):[0-5]\d\b/g)].map((m) => m[0]);
          expect(times.filter((x) => x !== hm(p.input.scenario.inputTimeIso))).toEqual([]);
        }
      }
    });
  });

  it('deterministic: same input, byte-identical outputs', () => {
    for (const p of real.slice(0, 60)) expect(JSON.stringify(build(p))).toBe(JSON.stringify(build(p)));
  });
});

describe('600 synthetic cases (all kinds, markers, long and unnamed places)', () => {
  it('the only violations are full head scripts over 35 s, which are withheld (fail closed)', () => {
    const viol = syn.flatMap((p) => build(p).violations);
    const kinds = new Set(viol.map((v) => v.replace(/[\d.]+ s/g, 'N s')));
    expect([...kinds].sort()).toEqual(['ko.head: N s > N s']);
    expect(viol.length).toBe(19);
  });

  it('cores always ≤ 20 s with five elements; unresolved / no_route / partial never name a destination or a time', () => {
    for (const p of syn) {
      const s = build(p);
      for (const l of ['ko', 'en'] as const) {
        expect(s.text[l].head.coreS).toBeLessThanOrEqual(HEAD_CORE_MAX_S);
        expect(s.text[l].head.elements).toEqual([...ELEMENTS]);
      }
      if (p.kind !== 'leave_by') {
        expect(s.destinationName).toBeNull();
        for (const t of residentTexts(s)) expect(DEPART.test(masked(p, t))).toBe(false);
        for (const l of ['ko', 'en'] as const) expect(s.text[l].staff.issueOrderBy).toMatch(/산출되지 않음|not computed/);
      }
      for (const l of ['ko', 'en'] as const) expect(s.text[l].staff.noOrder).not.toBeNull();
    }
  });
});

describe('rules, one by one', () => {
  const leave = () => messagePlan(synInput(), null);
  const unresolved = () => messagePlan(synInput({ plan: null }), null);

  it('no-order output: staff only, only for an explicit, attributed, unexpired not_issued status', () => {
    const p = leave();
    const at = (o: Partial<typeof ORDER> | null) => buildChannels(p, { nowIso: NOW, orderStatus: o === null ? null : ({ ...ORDER, ...o } as typeof ORDER) }).text;
    expect(buildChannels(p, { nowIso: NOW }).text.ko.staff.noOrder).toBeNull();
    expect(at(null).ko.staff.noOrder).toBeNull();
    expect(at({ status: 'issued' as never }).ko.staff.noOrder).toBeNull();
    expect(at({ suppliedBy: '  ' }).ko.staff.noOrder).toBeNull();
    expect(at({ expiresAtIso: '2026-11-12T09:59:59Z' }).ko.staff.noOrder).toBeNull();
    expect(at({ suppliedAtIso: '2026-11-12T10:00:01Z' }).ko.staff.noOrder).toBeNull();
    expect(orderNotIssued({ ...ORDER, expiresAtIso: 'not a date' }, NOW)).toBe(false);
    const t = at({});
    expect(t.ko.staff.noOrder).toContain('[이장·담당자용');
    expect(t.ko.staff.noOrder).toContain('아직 공식 대피 명령은 없습니다');
    expect(t.ko.staff.noOrder).toContain('명령이 없다고 위험이 없는 것은 아닙니다');
    expect(t.ko.staff.noOrder).toContain(ORDER.suppliedBy);
    expect(t.ko.staff.noOrder).toMatch(/기록 재현 자료/);
    expect(t.en.staff.noOrder).toContain('No order yet is not an all-clear');
    // never in a resident-facing output
    for (const l of ['ko', 'en'] as const) for (const r of [t[l].head.script, t[l].voice, t[l].familyText, ...t[l].familyScript]) expect(r).not.toMatch(/공식 대피 명령은 없습니다|no official order yet/);
  });

  it('issue-order-by (F-3.1 record): times only for leave_by; negative = already past; null leave-by only with planner no-route; absent = not computed', () => {
    const p = leave();
    const t0 = p.input.scenario.inputTimeIso;
    const ko = buildChannels(p, { nowIso: NOW, issueOrderBy: ISSUE }).text.ko.staff.issueOrderBy;
    expect(ko).toContain(hm(t0, 900));
    expect(ko).toContain(hm(t0, 600));
    expect(ko).toContain('이미 지남');
    expect(buildChannels(p, { nowIso: NOW }).text.en.staff.issueOrderBy).toContain('not computed');
    expect(buildChannels(p, { nowIso: NOW, issueOrderBy: { leaveByS: null } }).text.ko.staff.issueOrderBy).toContain('불일치');
    const u = unresolved();
    expect(buildChannels(u, { nowIso: NOW, issueOrderBy: ISSUE }).text.ko.staff.issueOrderBy).toContain('산출되지 않음');
  });

  it('issue-order-by rejects out-of-range records (Mira N1): issue after leave-by, leave-by beyond the horizon, non-integers', () => {
    const p = leave();
    const T = (r: object) => buildChannels(p, { nowIso: NOW, issueOrderBy: r as never }).text.ko.staff.issueOrderBy;
    expect(T({ leaveByS: 1800, issueByS: { low: 1860, median: 600, high: 0 } })).toContain('범위 오류');
    expect(T({ leaveByS: 99999, issueByS: { low: 600, median: 600, high: 600 } })).toContain('범위 오류');
    expect(T({ leaveByS: -5, issueByS: { low: -600, median: -600, high: -600 } })).toContain('범위 오류');
    expect(T({ leaveByS: 1800, issueByS: { low: 600.5, median: 600, high: 600 } })).toContain('범위 오류');
    expect(T({ leaveByS: 1800, issueByS: { low: 1800, median: 600, high: -600 } })).toMatch(/\d\d:\d\d .* \d\d:\d\d .* 이미 지남/);
    // Mira N6: a field later than the planner's leave-by must not push issue-by past the residents' leave-by
    expect(p.leaveByS).toBe(1800);
    expect(T({ leaveByS: 3000, issueByS: { low: 3000, median: 2700, high: 2400 } })).toContain('범위 오류');
    expect(T({ leaveByS: 3000, issueByS: { low: 1800, median: 1500, high: 1200 } })).not.toMatch(/범위 오류|불일치/);
    expect(T({ leaveByS: 1200, issueByS: { low: 600, median: 300, high: 0 } })).toContain('불일치');
    // Mira N7: shorter latency → later issue-by; out-of-order settings are refused
    expect(T({ leaveByS: 1800, issueByS: { low: 900, median: 1200, high: 1500 } })).toContain('순서 오류');
  });

  it('midnight crossing names the day (Mira N2): data 23:45 KST, leave-by after midnight', () => {
    const p = messagePlan(synInput({ scenario: { ...synInput().scenario, inputTimeIso: '2025-03-24T14:45:00Z' } }), null);
    expect(p.kind).toBe('leave_by');
    const s = buildChannels(p, { nowIso: NOW, orderStatus: ORDER });
    const crosses = new Date(Date.parse('2025-03-24T14:45:00Z') + p.leaveByS! * 1000 + 9 * 3600e3).getUTCDate() !== 24;
    expect(crosses).toBe(true);
    expect(s.text.ko.head.core).toContain('다음날 ');
    expect(s.text.ko.familyText).toContain('다음날 ');
    expect(s.text.ko.staff.noOrder).toContain('다음날 ');
    expect(s.text.en.head.core).toContain('(next day)');
    expect(s.violations).toEqual([]);
  });

  it('data age: replay says so; live states minutes; a future data time is "unknown"', () => {
    const p = leave();
    expect(buildChannels(p, { nowIso: NOW }).text.ko.staff.dataAge).toMatch(/기록 재현 자료/);
    const live = messagePlan(synInput({ replay: false }), null);
    const t0 = Date.parse(live.input.scenario.inputTimeIso);
    expect(buildChannels(live, { nowIso: new Date(t0 + 35 * 60000).toISOString() }).text.ko.staff.dataAge).toMatch(/35분 전 자료/);
    expect(buildChannels(live, { nowIso: new Date(t0 - 60000).toISOString() }).text.en.staff.dataAge).toMatch(/data age unknown/);
  });

  it('voice call: key 2 is passed on, never promised transport; key 1 means "leaving" only for leave_by', () => {
    const t = buildChannels(leave(), { nowIso: NOW }).text;
    expect(t.ko.voice).toContain('2번을 누르시면 이장과 읍·면사무소에 전달됩니다');
    expect(t.ko.voice).toContain('지금 출발하시면 1번');
    expect(buildChannels(unresolved(), { nowIso: NOW }).text.ko.voice).toContain('안내를 들으셨으면 1번');
  });

  it('family script is exactly three lines', () => {
    for (const p of [leave(), unresolved()]) for (const l of ['ko', 'en'] as const) expect(buildChannels(p, { nowIso: NOW }).text[l].familyScript).toHaveLength(3);
  });

  it('the checks catch injected faults: forbidden word, destination swap, departure time on unresolved', () => {
    const p = leave();
    const s = buildChannels(p, { nowIso: NOW });
    const bad1 = structuredClone(s); bad1.text.ko.voice += ' 안심하십시오.';
    expect(checkChannels(p, bad1).some((v) => v.startsWith('ko.voice: forbidden word'))).toBe(true);
    const p2: MessagePlan = { ...p, input: { ...p.input, destinations: { ...p.input.destinations, 'syn:dest:named-other': { id: 'syn:dest:named-other', name: { ko: '합성 다른 학교', en: 'Synthetic Other School' }, display: { ko: '합성 다른 학교', en: 'Synthetic Other School' }, category: { ko: '학교', en: 'school' } } } } };
    const bad2 = structuredClone(s); bad2.text.ko.familyScript[1] += ' 합성 다른 학교 쪽입니다.';
    expect(checkChannels(p2, bad2).some((v) => v.includes('names destination "합성 다른 학교"'))).toBe(true);
    expect(checkChannels(p2, s).some((v) => v.includes('names destination'))).toBe(false);
    const u = unresolved();
    const su = buildChannels(u, { nowIso: NOW });
    const bad3 = structuredClone(su); bad3.text.ko.familyText += '\n18:40까지 차로 출발';
    expect(checkChannels(u, bad3).some((v) => /departure instruction|clock time/.test(v))).toBe(true);
  });
});

describe('head script: inseparable framing, both reading rates', () => {
  it('the exported script is opener + core + closer; the checks read only that', () => {
    for (const p of real.slice(0, 50)) {
      const h = build(p).text.ko.head;
      expect(h.script).toBe([h.opener, h.core, h.closer].join('\n'));
      expect(h.script.startsWith(h.opener) && h.script.endsWith(h.closer)).toBe(true);
    }
  });

  it('measured fit (real origins): 531/531 at 3.0 syll/s; at 2.5 syll/s 197/531 cores ≤ 20 s and 182/531 full ≤ 35 s (reported, not enforced)', () => {
    const hs = real.map((p) => build(p).text.ko.head);
    expect(hs.filter((h) => h.coreS <= 20 && h.fullS <= 35).length).toBe(531);
    expect(hs.filter((h) => h.coreSlowS <= 20).length).toBe(197);
    expect(hs.filter((h) => h.fullSlowS <= 35).length).toBe(182);
    for (const h of hs) expect(h.coreSlowS).toBeCloseTo(h.coreS * 1.2, 9);
  });
});

describe('재난문자 character limits per message class (행안부예규 361)', () => {
  it('every kit SMS and every family text fits the STRICTEST class (90 characters) and its own class; bytes stay ≤ 90', () => {
    let maxKit = 0, maxFam = 0;
    realInputs.forEach((input, i) => {
      const p = real[i]!;
      const fm = buildFieldMessages(input, null);
      for (const t of [fm.text.ko.sms, build(p).text.ko.familyText]) {
        expect(cbsChars(t)).toBeLessThanOrEqual(CBS_CHAR_LIMIT.urgent);
        expect(cbsChars(t)).toBeLessThanOrEqual(CBS_CHAR_LIMIT[cbsClassFor(p.kind)]);
      }
      maxKit = Math.max(maxKit, cbsChars(fm.text.ko.sms));
      maxFam = Math.max(maxFam, cbsChars(build(p).text.ko.familyText));
    });
    expect(maxKit).toBeLessThanOrEqual(90);
    expect(maxFam).toBeLessThanOrEqual(90);
    expect(cbsClassFor('leave_by')).toBe('safety_guidance');
    expect(cbsClassFor('no_route')).toBe('urgent');
  });
});

describe('live data age and time wording', () => {
  it('a live origin states its age in the spoken opener; the time style is selectable', () => {
    const live = messagePlan(synInput({ replay: false }), null);
    const t0 = Date.parse(live.input.scenario.inputTimeIso);
    const s = buildChannels(live, { nowIso: new Date(t0 + 12 * 60000).toISOString() });
    expect(s.text.ko.head.opener).toContain('12분 전 자료입니다');
    expect(s.text.en.head.opener).toContain('12 minutes old');
    const rel = buildChannels(live, { nowIso: new Date(t0 + 12 * 60000).toISOString(), timeStyle: 'clock_and_minutes' });
    expect(rel.text.ko.head.core).toMatch(/자료 시각부터 \d+분 뒤인/);
    expect(buildChannels(live, { nowIso: NOW }).text.ko.head.core).not.toMatch(/자료 시각부터/);
  });
});

describe('existing kit unchanged', () => {
  it('every field message of every real origin is byte-identical to the pre-W-KIT kit (sha256 snapshot)', () => {
    const h = createHash('sha256').update(JSON.stringify(realInputs.map((i) => buildFieldMessages(i, null)))).digest('hex');
    expect(h).toBe('fc426e8ca7640ce68bd03688c00284e1b263eef637fea0493c44ac12eaf5805b');
  });
});

describe('transport-need list (key 2)', () => {
  const mk = (id: string, verdicts: Parameters<typeof cells>[0] | null, rank: number) =>
    messagePlan(synInput({ originId: id, urgencyRank: rank, plan: verdicts ? { bestVerdict: verdicts.includes('checked_route') ? 'checked_route' : (verdicts[0] as never), latestSafeDepartureS: null, contiguousSafeDepartureS: null, sweep: cells(verdicts), note: null } : null }), null);

  it('top section (no-route, then unresolved incl. missing plans, by urgency rank) apart from the by-deadline section; keys 1 and 3 excluded; unknown keys kept (synthetic households only)', () => {
    const early = messagePlan(synInput({ originId: 'o:early', urgencyRank: 5 }), null);
    expect(early.kind).toBe('leave_by');
    const plans: Record<string, MessagePlan> = {
      'o:early': early,
      'o:unres': mk('o:unres', null, 9),
      'o:noroute': mk('o:noroute', ['model_no_route', 'model_no_route', 'model_no_route', 'model_no_route', 'model_no_route', 'model_no_route'], 2),
    };
    const R = (originId: string, key: string, at: string, contact = 'h1'): Reply => ({ originId, key, receivedAtIso: at, contact });
    const rows = transportNeedList(
      [R('o:early', '2', '2026-11-12T10:00:00Z'), R('o:unres', '2', '2026-11-12T10:05:00Z'), R('o:noroute', '2', '2026-11-12T10:09:00Z'),
       R('o:early', '1', '2026-11-12T10:01:00Z'), R('o:early', '3', '2026-11-12T10:02:00Z'), R('o:missing', '2', '2026-11-12T10:03:00Z'), R('o:early', '#', '2026-11-12T10:04:00Z', 'h2')],
      plans,
    );
    expect(rows.topSection.map((r) => `${r.originId}:${r.kind}`)).toEqual(['o:noroute:no_route', 'o:unres:unresolved', 'o:missing:unresolved']);
    expect(rows.byDeadline.map((r) => `${r.originId}:${r.code}`)).toEqual(['o:early:needs_help', 'o:early:unknown']);
    expect(rows.topSection.every((r) => r.leaveByS === null) && rows.byDeadline.every((r) => r.leaveByS !== null)).toBe(true);
  });
});

describe('W6: draft decree four-field report (안 제49조②, notice 2026-11-04; draft requirement, as of the notice date)', () => {
  // SYNTHETIC issuer: the Korean and English names both contain a kit-forbidden word (안전 / Safety); the number is fake
  const ISS = { agency: { ko: '합성군 재난안전과', en: 'Synthetic County Disaster Safety Division' }, contact: '000-0000-0000', forDrillOrReplay: true };
  const HANGUL = /[가-힣ㄱ-ㆎ]/;
  const all = () => [...real, ...syn];

  it('supplied proper nouns are data: an issuer adds no violation to any of the 531 real or 600 synthetic channel sets', () => {
    for (const p of all()) {
      const a = buildChannels(p, { nowIso: NOW }).violations;
      const b = buildChannels(p, { nowIso: NOW, issuer: ISS }).violations;
      expect(b, p.input.origin.id).toEqual(a);
    }
    // a rescue-unit name (구조) is data too
    const p = real.find((x) => x.kind === 'leave_by')!;
    expect(buildChannels(p, { nowIso: NOW, issuer: { agency: { ko: '합성 119구조대', en: 'Synthetic Rescue Unit' }, contact: '000-000-0000', forDrillOrReplay: true } }).violations).toEqual([]);
  });

  it('the scan still catches the same word in generated text, even when the agency name is exactly that word', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    for (const iss of [ISS, { agency: { ko: '재난안전과', en: 'Safety Division' }, contact: '000-0000-0000', forDrillOrReplay: true }]) {
      expect(validIssuer(iss)).not.toBeNull();
      const set = buildChannels(p, { nowIso: NOW, issuer: iss });
      expect(set.violations).toEqual([]);
      set.text.ko.voice = `${set.text.ko.voice}\n이제 안전합니다.`;
      set.text.en.familyScript = [set.text.en.familyScript[0], set.text.en.familyScript[1], `${set.text.en.familyScript[2]} You are safe.`];
      const v = checkChannels(p, set);
      expect(v).toContain('ko.voice: forbidden word "안전"');
      expect(v).toContain('en.familyScript: forbidden word "safe"');
    }
  });

  it('agency and contact are never invented: no line without a valid supplied issuer; blank, multi-line, emergency or non-numeric input counts as none', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    const bad = [
      null,
      { agency: { ko: '' }, contact: '000-0000-0000' },
      { agency: { ko: '  ' }, contact: '000-0000-0000' },
      { agency: { ko: '합성군' }, contact: '' },
      { agency: { ko: '합성군' }, contact: '119' },
      { agency: { ko: '합성군' }, contact: '1-1-2' },
      { agency: { ko: '합성군' }, contact: '000-CALL-NOW' },
      { agency: { ko: '합성군\n즉시 대피' }, contact: '000-0000-0000' },
      { agency: { ko: '가'.repeat(41) }, contact: '000-0000-0000' },
    ];
    for (const iss of bad) {
      expect(validIssuer(iss as never)).toBeNull();
      const s = buildChannels(p, { nowIso: NOW, issuer: iss as never, draftDecreeCheck: true });
      expect(residentTexts(s).join('\n')).not.toMatch(/문의|Contact/);
      for (const l of ['ko', 'en'] as const) for (const o of RESIDENT_OUTPUTS) expect(s.decree![l][o].contact).toBe('not_supplied');
    }
  });

  it('English outputs never carry Hangul: no English name => the English field is withheld, not filled; a Hangul "English" name is refused', () => {
    expect(validIssuer({ agency: { ko: '합성군', en: '합성군' }, contact: '000-0000-0000' })!.agency.en).toBeNull();
    expect(validIssuer({ agency: { ko: '합성군', en: 'Hapseong County' }, contact: '000-0000-0000' })!.agency.en).toBe('Hapseong County');
    expect(validIssuer({ agency: { ko: '합성군', en: 'Hapseong-gun Café' }, contact: '000-0000-0000' })!.agency.en).toBeNull(); // é: not GSM-7 basic
    for (const p of real) {
      const s = buildChannels(p, { nowIso: NOW, issuer: { agency: { ko: ISS.agency.ko }, contact: ISS.contact, forDrillOrReplay: true }, draftDecreeCheck: true });
      const en = s.text.en;
      for (const t of [en.head.script, en.voice, en.familyText, en.familyScript.join('\n')]) expect(t).not.toContain(ISS.agency.ko);
      for (const o of RESIDENT_OUTPUTS) expect(s.decree!.en[o].contact).toBe('no_english_name');
      expect(s.violations.filter((v) => v.startsWith('en.familyText'))).toEqual([]); // GSM-7 check kept, and passes
    }
  });

  it('the contact line has its own head budget; over it, the head leaves the FIELD out and the message stays usable', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    const long = { agency: { ko: `${'가'.repeat(19)}과`, en: 'X' }, contact: '000-0000-0000', forDrillOrReplay: true };
    const iss = validIssuer(long)!;
    expect(contactSeconds(contactLine(iss, 'ko')!, iss, 'ko')).toBeGreaterThan(HEAD_CONTACT_MAX_S);
    const s = buildChannels(p, { nowIso: NOW, issuer: long, draftDecreeCheck: true });
    expect(s.text.ko.head.script).not.toContain('문의');
    expect(s.decree!.ko.head.contact).toBe('over_length');
    expect(outputWithheld(s, 'ko', 'head')).toBe(false);
    expect(s.text.ko.voice).toContain(contactLine(iss, 'ko')!);
    expect(s.text.ko.familyScript[2]).toContain(contactLine(iss, 'ko')!);
    expect(s.text.ko.familyScript.length).toBe(3);
    // within budget: the line is in the head, after the closer, and the 35 s opener+core+closer budget is unchanged
    const ok = buildChannels(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
    expect(ok.text.ko.head.script.endsWith(contactLine(validIssuer(ISS)!, 'ko')!)).toBe(true);
    expect(ok.text.ko.head.fullS).toBe(buildChannels(p, { nowIso: NOW }).text.ko.head.fullS);
    expect(ok.text.ko.head.contactS!).toBeLessThanOrEqual(HEAD_CONTACT_MAX_S);
  });

  it('the family text carries the contact only if it still fits its byte / GSM-7 limit (measured: never in Korean at 90 bytes; English 509 of 531)', () => {
    let koIn = 0, enIn = 0;
    const koTexts: string[] = [];
    for (const p of real) {
      const s = buildChannels(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      koTexts.push(s.text.ko.familyText);
      koIn += +(s.decree!.ko.familyText.contact === 'included');
      enIn += +(s.decree!.en.familyText.contact === 'included');
    }
    expect([koIn, enIn]).toEqual([0, 509]);
    const bytes = pythonEucKr(koTexts);
    expect(bytes, 'python3 with the euc_kr codec is required for this oracle').not.toBeNull();
    for (const b of bytes!) expect(typeof b === 'number' && b <= 90, String(b)).toBe(true);
  });

  it('pass metrics (531 real origins): complete AND not withheld — overall, and among outputs where all four fields apply (leave-by places); every missing field carries one of three reasons', () => {
    type Row = { all: number; allN: number; app: number; appN: number };
    const run = (iss: typeof ISS | null) => {
      const out: Record<string, Row> = {};
      const reasons: Record<string, number> = { not_applicable: 0, not_supplied: 0, does_not_fit: 0 };
      let withheld = 0;
      for (const l of ['ko', 'en'] as const) for (const o of RESIDENT_OUTPUTS) out[`${l}.${o}`] = { all: 0, allN: 0, app: 0, appN: 0 };
      for (const p of real) {
        const s = buildChannels(p, { nowIso: NOW, issuer: iss, draftDecreeCheck: true });
        const applicable = p.kind === 'leave_by';
        for (const l of ['ko', 'en'] as const) for (const o of RESIDENT_OUTPUTS) {
          const r = s.decree![l][o];
          const w = outputWithheld(s, l, o);
          withheld += +w;
          const ok = !w && r.missing.length === 0;
          const row = out[`${l}.${o}`]!;
          row.allN += 1; row.all += +ok;
          if (applicable) { row.appN += 1; row.app += +ok; }
          expect(Object.keys(r.reasons).sort()).toEqual([...r.missing].sort());
          for (const f of r.missing) reasons[r.reasons[f]!]! += 1;
          // not_applicable only ever for timing at a place without a checked time
          if (r.reasons.reason_timing === 'not_applicable') expect(applicable).toBe(false);
          for (const f of ['area_people', 'shelter', 'agency_contact'] as const) expect(r.reasons[f]).not.toBe('not_applicable');
          // the report agrees with an independent reading of the text for the agency field
          const txt = o === 'head' ? s.text[l].head.script : o === 'familyScript' ? s.text[l].familyScript.join('\n') : s.text[l][o];
          const name = iss ? (l === 'ko' ? iss.agency.ko : iss.agency.en) : null;
          expect(r.present.includes('agency_contact')).toBe(!!name && txt.includes(name) && txt.includes(iss!.contact));
        }
      }
      const fmt = Object.fromEntries(Object.entries(out).map(([k, v]) => [k, `${v.all}/${v.allN} · ${v.app}/${v.appN}`]));
      return { fmt, reasons, withheld };
    };
    const none = run(null);
    const withIss = run(ISS);
    console.log('[W6] no issuer', JSON.stringify(none));
    console.log('[W6] issuer', JSON.stringify(withIss));
    expect(none.withheld).toBe(0);
    expect(Object.values(none.fmt).every((v) => v === '0/531 · 0/501')).toBe(true);
    expect(withIss.withheld).toBe(0);
    expect(withIss.fmt).toEqual({
      'ko.head': '299/531 · 299/501', 'ko.voice': '299/531 · 299/501', 'ko.familyText': '0/531 · 0/501', 'ko.familyScript': '440/531 · 440/501',
      // owner decision (Korean shelter name in English when there is no English name): en head and family script
      // 64 -> 431; the English automated voice call does not read Hangul (open with Iris) and stays at 64
      'en.head': '431/531 · 431/501', 'en.voice': '64/531 · 64/501', 'en.familyText': '0/531 · 0/501', 'en.familyScript': '431/531 · 431/501',
    });
    expect(DECREE_FIELDS.length).toBe(4);
  });

  it('replay, mock and test data: the contact line is rendered only for an issuer explicitly marked for drill or replay use; live data needs no mark', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    expect(p.input.replay).toBe(true);
    const unmarked = { ...ISS, forDrillOrReplay: undefined };
    const s = buildChannels(p, { nowIso: NOW, issuer: unmarked, draftDecreeCheck: true });
    expect(residentTexts(s).join('\n')).not.toContain(ISS.contact);
    for (const l of ['ko', 'en'] as const) for (const o of RESIDENT_OUTPUTS) {
      expect(s.decree![l][o].contact).toBe('replay_not_marked');
      expect(s.decree![l][o].reasons.agency_contact).toBe('not_supplied');
    }
    const live = messagePlan(synInput({ replay: false, mock: false, testData: false }), null);
    const sl = buildChannels(live, { nowIso: NOW, issuer: unmarked, draftDecreeCheck: true });
    expect(sl.decree!.ko.voice.contact).toBe('included');
    for (const flag of [{ mock: true }, { testData: true }]) {
      const q = messagePlan(synInput({ replay: false, mock: false, testData: false, ...flag }), null);
      expect(buildChannels(q, { nowIso: NOW, issuer: unmarked, draftDecreeCheck: true }).decree!.ko.voice.contact).toBe('replay_not_marked');
    }
  });

  it('committed fixtures use only undiallable placeholder numbers (all zeros) or numbers the validator refuses', () => {
    const src = readFileSync(new URL(import.meta.url), 'utf8');
    const nums = [...src.matchAll(/contact: '([^']*)'/g)].map((m) => m[1]!);
    expect(nums.length).toBeGreaterThan(5);
    for (const n of nums) {
      const zeros = /^[0-]+$/.test(n) && /0/.test(n);
      expect(zeros || validIssuer({ agency: { ko: '합성군' }, contact: n }) === null, n).toBe(true);
    }
  });

  it('the contact line never displaces "official orders first": opener, core and closer stay together and in order, the line comes after them, and every output keeps the official-first text', () => {
    for (const p of all()) {
      const s = buildChannels(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      for (const l of ['ko', 'en'] as const) {
        const t = s.text[l];
        const frame = [t.head.opener, t.head.core, t.head.closer].join('\n');
        expect(t.head.script.startsWith(frame)).toBe(true);
        expect(t.head.closer).toContain(OFFICIAL_FIRST[l]);
        const line = contactLine(validIssuer(ISS)!, l)!;
        for (const [txt, first] of [[t.head.script, OFFICIAL_FIRST[l]], [t.voice, OFFICIAL_FIRST[l]], [t.familyScript.join('\n'), OFFICIAL_FIRST[l]]] as const) {
          expect(txt).toContain(first);
          if (txt.includes(line)) expect(txt.indexOf(line)).toBeGreaterThan(txt.indexOf(first));
        }
        expect(t.familyText.includes(OFFICIAL_FIRST_SMS[l]) || t.familyText.includes(OFFICIAL_FIRST[l])).toBe(true);
      }
    }
  });

  it('staff outputs always show the report (Korean and English), name it a draft requirement, leave the send decision to officials, and pass the kit scans', () => {
    for (const p of real.slice(0, 200)) {
      const s = buildChannels(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      expect(s.text.ko.staff.decree).toMatch(/입법예고안\(2026-11-04 공고\)/);
      expect(s.text.ko.staff.decree).toMatch(/초안 기준/);
      expect(s.text.ko.staff.decree).toMatch(/담당 기관이 정합니다/);
      expect(s.text.en.staff.decree).toMatch(/draft requirement as of that date/);
      expect(s.text.en.staff.decree).toMatch(/for officials to decide/);
      expect(s.text.ko.staff.decree!.split('\n').length).toBe(5);
      expect(s.text.en.staff.decree).not.toMatch(HANGUL);
      expect(s.violations.filter((v) => v.includes('staff.decree'))).toEqual([]);
    }
  });

  it('a report only: with or without the check, the same outputs and the same violations', () => {
    for (const p of real.slice(0, 120)) {
      const a = buildChannels(p, { nowIso: NOW, issuer: ISS });
      const b = buildChannels(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      expect(b.violations).toEqual(a.violations);
      for (const l of ['ko', 'en'] as const) {
        const { staff: sa, ...ra } = a.text[l];
        const { staff: sb, ...rb } = b.text[l];
        expect(rb).toEqual(ra); // every resident output identical
        expect({ ...sb, decree: undefined }).toEqual({ ...sa, decree: undefined });
        expect(sa.decree ?? null).toBeNull();
        expect(sb.decree).toBeTruthy();
      }
      expect(a.decree).toBeUndefined();
    }
    expect(HANGUL.test('Contact')).toBe(false);
  });
});

describe('W6 follow-up: agency-name guard (Mira N2) and Korean shelter names in English (owner decision)', () => {
  const ISS = { agency: { ko: '합성군 재난안전과', en: 'Synthetic County Disaster Safety Division' }, contact: '000-0000-0000', forDrillOrReplay: true };
  const HANGUL = /[ᄀ-ᇿ㄰-㆏가-힣]/;

  it('an agency name must be a name: clock times, departure instructions, sentences and loose forbidden words are refused', () => {
    for (const bad of ['지금 출발하십시오 18:30 안전합니다', '합성군 18:30 재난과', '18시 합성군청', '17시까지 출발 합성군청', '안전합니다', '합성군청입니다', '합성군 안심센터', '합성군 구출과', '합성군']) {
      // '합성군' itself ends in 군 (a county) and is accepted; everything else is refused
      if (bad === '합성군') expect(validIssuer({ agency: { ko: bad }, contact: '000-0000-0000' })).not.toBeNull();
      else expect(validIssuer({ agency: { ko: bad }, contact: '000-0000-0000' }), bad).toBeNull();
    }
    for (const bad of ['Leave now 18:30 you are safe', 'Safe Haven Office.', 'Hapseong County, depart by 6', 'We will send a bus Office']) {
      expect(validIssuer({ agency: { ko: '합성군 재난안전과', en: bad }, contact: '000-0000-0000' })!.agency.en, bad).toBeNull();
    }
    for (const ok of ['합성군 재난안전과', '합성군 산림과', '합성군 119구조대', '합성읍 행정복지센터', '합성군청', '합성시 안전총괄과']) {
      expect(validIssuer({ agency: { ko: ok }, contact: '000-0000-0000' }), ok).not.toBeNull();
    }
    for (const ok of ['Synthetic County Disaster Safety Division', 'Hapseong County Office', 'Synthetic Rescue Unit']) {
      expect(validIssuer({ agency: { ko: '합성군청', en: ok }, contact: '000-0000-0000' })!.agency.en, ok).toBe(ok);
    }
  });

  it('English outputs carry Hangul only as the plan\'s own shelter name (head and family script), never in the voice call or family text; nothing withheld', () => {
    let koNameShown = 0;
    for (const p of real) {
      const s = buildChannels(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      expect(s.violations).toEqual([]);
      const en = s.text.en;
      const ko = s.destinationName?.ko;
      for (const t of [en.head.script, en.familyScript.join('\n')]) {
        const left = ko ? t.split(ko).join('') : t;
        expect(left).not.toMatch(HANGUL);
      }
      expect(en.voice).not.toMatch(HANGUL);
      expect(en.familyText).not.toMatch(HANGUL);
      if (ko && !s.destinationName!.en && en.familyScript.join('\n').includes(ko)) koNameShown += 1;
    }
    expect(koNameShown).toBeGreaterThan(0);
    console.log('[W6] English family scripts showing a Korean-only shelter name:', koNameShown);
  });

  it('a Korean name anywhere else in an English output is a violation (the guard is live)', () => {
    const p = real.find((x) => x.kind === 'leave_by' && namedDestination(x))!;
    const s = buildChannels(p, { nowIso: NOW });
    s.text.en.familyScript = [s.text.en.familyScript[0], `${s.text.en.familyScript[1]} 마을회관`, s.text.en.familyScript[2]];
    expect(checkChannels(p, s)).toContain('en.familyScript: Hangul outside the shelter name');
  });

  it('SMS segments are counted in the encoding the text needs (GSM-7 160/153, UCS-2 70/67); no family text changes segment count', () => {
    expect(smsSegments('a'.repeat(160))).toEqual({ encoding: 'gsm7', units: 160, segments: 1 });
    expect(smsSegments('a'.repeat(161))).toEqual({ encoding: 'gsm7', units: 161, segments: 2 });
    expect(smsSegments('{'.repeat(80)).units).toBe(160);
    expect(smsSegments(`${'a'.repeat(69)}가`)).toEqual({ encoding: 'ucs2', units: 70, segments: 1 });
    expect(smsSegments(`${'a'.repeat(70)}가`)).toEqual({ encoding: 'ucs2', units: 71, segments: 2 });
    expect(smsSegments('가'.repeat(135)).segments).toBe(3);
    // the family text never names a destination, so the owner decision adds no Hangul to any SMS
    const seg: Record<string, number> = {};
    for (const p of real) {
      const s = buildChannels(p, { nowIso: NOW, issuer: ISS });
      const m = smsSegments(s.text.en.familyText);
      seg[`${m.encoding}:${m.segments}`] = (seg[`${m.encoding}:${m.segments}`] ?? 0) + 1;
    }
    expect(seg).toEqual({ 'gsm7:1': 531 });
  });
});
