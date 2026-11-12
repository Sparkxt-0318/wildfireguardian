/**
 * W-KIT channel outputs (planner/src/features/lastmile/channels/build.ts), checked over EVERY origin of the six booth
 * caches and the kit's 600 generated synthetic cases, plus unit tests of each rule. The module's own checks
 * (checkChannels) are re-tested with independent oracles: Python's strict euc_kr codec for byte counts, the kit's
 * NEVER / DEPART patterns (lastmile.oracle.ts) and a separate clock-time regex.
 */
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { hm } from '../../planner/src/features/lastmile/compose';
import { OFFICIAL_FIRST, OFFICIAL_FIRST_SMS } from '../../planner/src/features/lastmile/strings';
import { smsSegments } from '../../planner/src/features/lastmile/encoding';
import { AGENCY_REGISTRY, type RegistryEntry } from '../../planner/src/features/lastmile/channels/agencyRegistry';

// TEST-ONLY registry substitution through a module mock: production code has no override at all (Mira note N2).
const regState = vi.hoisted(() => ({ current: null as null | readonly { ko: string; en: string | null; source: string }[] }));
vi.mock('../../planner/src/features/lastmile/channels/agencyRegistry', async (orig) => {
  const m = await orig<typeof import('../../planner/src/features/lastmile/channels/agencyRegistry')>();
  return { ...m, activeRegistry: () => regState.current ?? m.AGENCY_REGISTRY };
});
function withTestRegistryOnly<T>(entries: readonly RegistryEntry[], fn: () => T): T {
  if (entries.some((e) => !e.source.trim())) throw new Error('registry entries need a source');
  const prev = regState.current;
  regState.current = entries;
  try {
    return fn();
  } finally {
    regState.current = prev;
  }
}
import { buildFieldMessages } from '../../planner/src/features/lastmile/messages';
import { messagePlan, type MessagePlan } from '../../planner/src/features/lastmile/plan';
import { parseSigungu } from '../../planner/src/data/staticData';
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
  phoneShaped,
  agencyLike,
  checkIssuer,
  englishCallDropped,
  NO_EN_CALL_REPORT,
  staffSummary,
  namedDestination,
  type ChannelSet,
  type Reply,
} from '../../planner/src/features/lastmile/channels/build';
import { loadBoothCaches } from './lastmile.cachedata';
import { generateCases } from './lastmile.generator';
import { DEPART, NEVER, pythonEucKr } from './lastmile.oracle';
import { synInput, cells } from './lastmile.fixture';

const NOW = '2026-11-12T10:00:00Z';
/** SYNTHETIC registry for the W6 tests (the committed AGENCY_REGISTRY holds only sourced real bodies) */
const TEST_REG: RegistryEntry[] = [
  { ko: '합성군 재난안전과', en: 'Synthetic County Disaster Safety Division', source: 'synthetic test entry' },
  { ko: '합성 119구조대', en: 'Synthetic Rescue Unit', source: 'synthetic test entry' },
  { ko: '재난안전과', en: 'Safety Division', source: 'synthetic test entry' },
  { ko: '합성군', en: 'Hapseong County', source: 'synthetic test entry' },
  { ko: `${'가'.repeat(19)}과`, en: null, source: 'synthetic test entry (long name)' },
];
/**
 * TEST-ONLY place label for the W6 contact-line MECHANICS tests (budgets, SMS fit, decree report, replay mark, English
 * names): the place is labelled as established in the supplied issuer's own 시·군, so the jurisdiction rule (fail closed,
 * JURISDICTION/DESIGN.md) admits it and these tests keep testing what they tested. The jurisdiction rule itself is
 * tested on the real labels in "jurisdiction (pre-registered pass rule)" below.
 */
function inIssuerCounty(p: MessagePlan, issuer: unknown): MessagePlan {
  const ko = (issuer as { agency?: { ko?: unknown } } | null)?.agency?.ko;
  if (typeof ko !== 'string') return p;
  const sigungu = { ko: ko.normalize('NFC').trim(), status: 'established' as const, reason: null, source: 'TEST: labelled in the issuer\'s own 시·군' };
  return { ...p, input: { ...p.input, origin: { ...p.input.origin, sigungu } } };
}
const B = (p: MessagePlan, o: Parameters<typeof buildChannels>[1]) => withTestRegistryOnly(TEST_REG, () => buildChannels(inIssuerCounty(p, o.issuer), o));
const R = <T,>(fn: () => T): T => withTestRegistryOnly(TEST_REG, fn);
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
    return [t.head.script, t.voice, t.familyText, t.familyScript.join('\n')].filter((x): x is string => x !== null);
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
    // buildFieldMessages echoes its input, which now carries the place's 시·군 label (jurisdiction cut): the snapshot is
    // taken over the inputs without that one field, and the label is shown to change nothing else in the messages
    const strip = (i: (typeof realInputs)[number]) => ({ ...i, origin: (({ sigungu: _s, ...o }) => o)(i.origin) });
    expect(realInputs.every((i) => i.origin.sigungu?.status === 'established')).toBe(true);
    for (const i of realInputs) {
      const a = buildFieldMessages(strip(i) as never, null), b = buildFieldMessages(i, null);
      expect(JSON.stringify([b.text, b.metrics, b.inserted, b.violations, b.kind, b.leaveByS])).toBe(JSON.stringify([a.text, a.metrics, a.inserted, a.violations, a.kind, a.leaveByS]));
    }
    const h = createHash('sha256').update(JSON.stringify(realInputs.map((i) => buildFieldMessages(strip(i) as never, null)))).digest('hex');
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
      const b = B(p, { nowIso: NOW, issuer: ISS }).violations;
      expect(b, p.input.origin.id).toEqual(a);
    }
    // a rescue-unit name (구조) is data too
    const p = real.find((x) => x.kind === 'leave_by')!;
    expect(B(p, { nowIso: NOW, issuer: { agency: { ko: '합성 119구조대', en: 'Synthetic Rescue Unit' }, contact: '000-000-0000', forDrillOrReplay: true } }).violations).toEqual([]);
  });

  it('the scan still catches the same word in generated text, even when the agency name is exactly that word', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    for (const iss of [ISS, { agency: { ko: '재난안전과', en: 'Safety Division' }, contact: '000-0000-0000', forDrillOrReplay: true }]) {
      expect(R(() => validIssuer(iss))).not.toBeNull();
      const set = B(p, { nowIso: NOW, issuer: iss });
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
      expect(R(() => validIssuer(iss as never))).toBeNull();
      const s = B(p, { nowIso: NOW, issuer: iss as never, draftDecreeCheck: true });
      expect(residentTexts(s).join('\n')).not.toMatch(/문의|Contact/);
      for (const l of ['ko', 'en'] as const) for (const o of RESIDENT_OUTPUTS) expect(s.decree![l][o].produced === false ? ['no_output'] : ['not_supplied', 'not_in_registry']).toContain(s.decree![l][o].contact);
    }
  });

  it('English outputs never carry Hangul: no English name => the English field is withheld, not filled; a Hangul "English" name is refused', () => {
    expect(R(() => validIssuer({ agency: { ko: '합성군', en: '합성군' }, contact: '000-0000-0000' }))!.agency.en).toBeNull();
    expect(R(() => validIssuer({ agency: { ko: '합성군', en: 'Hapseong County' }, contact: '000-0000-0000' }))!.agency.en).toBe('Hapseong County');
    expect(R(() => validIssuer({ agency: { ko: '합성군', en: 'Hapseong-gun Café' }, contact: '000-0000-0000' }))!.agency.en).toBeNull(); // é: not GSM-7 basic
    for (const p of real) {
      const s = B(p, { nowIso: NOW, issuer: { agency: { ko: ISS.agency.ko }, contact: ISS.contact, forDrillOrReplay: true }, draftDecreeCheck: true });
      const en = s.text.en;
      for (const t of [en.head.script, en.voice, en.familyText, en.familyScript.join('\n')]) if (t !== null) expect(t).not.toContain(ISS.agency.ko);
      for (const o of RESIDENT_OUTPUTS) expect(s.decree!.en[o].contact).toBe(s.decree!.en[o].produced === false ? 'no_output' : 'no_english_name');
      expect(s.violations.filter((v) => v.startsWith('en.familyText'))).toEqual([]); // GSM-7 check kept, and passes
    }
  });

  it('the contact line has its own head budget; over it, the head leaves the FIELD out and the message stays usable', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    const long = { agency: { ko: `${'가'.repeat(19)}과`, en: 'X' }, contact: '000-0000-0000', forDrillOrReplay: true };
    const iss = R(() => validIssuer(long))!;
    expect(contactSeconds(contactLine(iss, 'ko')!, iss, 'ko')).toBeGreaterThan(HEAD_CONTACT_MAX_S);
    const s = B(p, { nowIso: NOW, issuer: long, draftDecreeCheck: true });
    expect(s.text.ko.head.script).not.toContain('문의');
    expect(s.decree!.ko.head.contact).toBe('over_length');
    expect(outputWithheld(s, 'ko', 'head')).toBe(false);
    expect(s.text.ko.voice).toContain(contactLine(iss, 'ko')!);
    expect(s.text.ko.familyScript[2]).toContain(contactLine(iss, 'ko')!);
    expect(s.text.ko.familyScript.length).toBe(3);
    // within budget: the line is in the head, after the closer, and the 35 s opener+core+closer budget is unchanged
    const ok = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
    expect(ok.text.ko.head.script.endsWith(contactLine(R(() => validIssuer(ISS))!, 'ko')!)).toBe(true);
    expect(ok.text.ko.head.fullS).toBe(buildChannels(p, { nowIso: NOW }).text.ko.head.fullS);
    expect(ok.text.ko.head.contactS!).toBeLessThanOrEqual(HEAD_CONTACT_MAX_S);
  });

  it('the family text carries the contact only if it still fits its byte / GSM-7 limit (measured: never in Korean at 90 bytes; English 509 of 531)', () => {
    let koIn = 0, enIn = 0;
    const koTexts: string[] = [];
    for (const p of real) {
      const s = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
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
      const notProduced: Record<string, number> = {};
      for (const l of ['ko', 'en'] as const) for (const o of RESIDENT_OUTPUTS) out[`${l}.${o}`] = { all: 0, allN: 0, app: 0, appN: 0 };
      for (const p of real) {
        const s = B(p, { nowIso: NOW, issuer: iss, draftDecreeCheck: true });
        const applicable = p.kind === 'leave_by';
        for (const l of ['ko', 'en'] as const) for (const o of RESIDENT_OUTPUTS) {
          const r = s.decree![l][o];
          // an output that is not produced at all (the English call, owner decision) is counted apart, not as a pass
          if (r.produced === false) { notProduced[`${l}.${o}`] = (notProduced[`${l}.${o}`] ?? 0) + 1; continue; }
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
          const txt = (o === 'head' ? s.text[l].head.script : o === 'familyScript' ? s.text[l].familyScript.join('\n') : s.text[l][o])!;
          const name = iss ? (l === 'ko' ? iss.agency.ko : iss.agency.en) : null;
          expect(r.present.includes('agency_contact')).toBe(!!name && txt.includes(name) && txt.includes(iss!.contact));
        }
      }
      const fmt = Object.fromEntries(Object.entries(out).map(([k, v]) => [k, `${v.all}/${v.allN} · ${v.app}/${v.appN}`]));
      return { fmt, reasons, withheld, notProduced };
    };
    const none = run(null);
    const withIss = run(ISS);
    console.log('[W6] no issuer', JSON.stringify(none));
    console.log('[W6] issuer', JSON.stringify(withIss));
    expect(none.withheld).toBe(0);
    expect(Object.entries(none.fmt).every(([k, v]) => v === (k === 'en.voice' ? '0/158 · 0/128' : '0/531 · 0/501'))).toBe(true);
    // owner decision: no English automated call at the 373 places whose shelter has no English name
    expect(none.notProduced).toEqual({ 'en.voice': 373 });
    expect(withIss.notProduced).toEqual({ 'en.voice': 373 });
    expect(withIss.withheld).toBe(0);
    expect(withIss.fmt).toEqual({
      'ko.head': '299/531 · 299/501', 'ko.voice': '299/531 · 299/501', 'ko.familyText': '0/531 · 0/501', 'ko.familyScript': '440/531 · 440/501',
      // owner decision (Korean shelter name in English when there is no English name): en head and family script
      // 64 -> 431. Owner decision: no English automated call where the shelter has no English name (373 places), so
      // the English call is counted over the 158 places where it is produced (128 leave-by)
      'en.head': '431/531 · 431/501', 'en.voice': '64/158 · 64/128', 'en.familyText': '0/531 · 0/501', 'en.familyScript': '431/531 · 431/501',
    });
    expect(DECREE_FIELDS.length).toBe(4);
  });

  it('replay, mock and test data: the contact line is rendered only for an issuer explicitly marked for drill or replay use; live data needs no mark', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    expect(p.input.replay).toBe(true);
    const unmarked = { ...ISS, forDrillOrReplay: undefined };
    const s = B(p, { nowIso: NOW, issuer: unmarked, draftDecreeCheck: true });
    expect(residentTexts(s).join('\n')).not.toContain(ISS.contact);
    for (const l of ['ko', 'en'] as const) for (const o of RESIDENT_OUTPUTS) {
      if (s.decree![l][o].produced === false) { expect(s.decree![l][o].contact).toBe('no_output'); continue; }
      expect(s.decree![l][o].contact).toBe('replay_not_marked');
      expect(s.decree![l][o].reasons.agency_contact).toBe('not_supplied');
    }
    const live = messagePlan(synInput({ replay: false, mock: false, testData: false }), null);
    const sl = B(live, { nowIso: NOW, issuer: unmarked, draftDecreeCheck: true });
    expect(sl.decree!.ko.voice.contact).toBe('included');
    for (const flag of [{ mock: true }, { testData: true }]) {
      const q = messagePlan(synInput({ replay: false, mock: false, testData: false, ...flag }), null);
      expect(B(q, { nowIso: NOW, issuer: unmarked, draftDecreeCheck: true }).decree!.ko.voice.contact).toBe('replay_not_marked');
    }
  });

  it('committed fixtures use only undiallable placeholder numbers (all zeros) or numbers the validator refuses', () => {
    const src = readFileSync(new URL(import.meta.url), 'utf8');
    const nums = [...src.matchAll(/contact: '([^']*)'/g)].map((m) => m[1]!);
    expect(nums.length).toBeGreaterThan(5);
    for (const n of nums) {
      const zeros = /^[0-]+$/.test(n) && /0/.test(n);
      expect(zeros || R(() => validIssuer({ agency: { ko: '합성군' }, contact: n })) === null, n).toBe(true);
    }
  });

  it('the contact line never displaces "official orders first": opener, core and closer stay together and in order, the line comes after them, and every output keeps the official-first text', () => {
    for (const p of all()) {
      const s = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      for (const l of ['ko', 'en'] as const) {
        const t = s.text[l];
        const frame = [t.head.opener, t.head.core, t.head.closer].join('\n');
        expect(t.head.script.startsWith(frame)).toBe(true);
        expect(t.head.closer).toContain(OFFICIAL_FIRST[l]);
        const line = contactLine(R(() => validIssuer(ISS))!, l)!;
        for (const [txt, first] of ([[t.head.script, OFFICIAL_FIRST[l]], [t.voice, OFFICIAL_FIRST[l]], [t.familyScript.join('\n'), OFFICIAL_FIRST[l]]] as const).filter((x): x is readonly [string, string] => x[0] !== null)) {
          expect(txt).toContain(first);
          if (txt.includes(line)) expect(txt.indexOf(line)).toBeGreaterThan(txt.indexOf(first));
        }
        expect(t.familyText.includes(OFFICIAL_FIRST_SMS[l]) || t.familyText.includes(OFFICIAL_FIRST[l])).toBe(true);
      }
    }
  });

  it('staff outputs always show the report (Korean and English), name it a draft requirement, leave the send decision to officials, and pass the kit scans', () => {
    for (const p of real.slice(0, 200)) {
      const s = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      expect(s.text.ko.staff.decree).toMatch(/입법예고안\(2026-11-04 공고\)/);
      expect(s.text.ko.staff.decree).toMatch(/초안 기준/);
      expect(s.text.ko.staff.decree).toMatch(/담당 기관이 정합니다/);
      expect(s.text.en.staff.decree).toMatch(/draft requirement as of that date/);
      expect(s.text.en.staff.decree).toMatch(/for officials to decide/);
      expect(s.text.ko.staff.decree!.split('\n').length).toBeGreaterThanOrEqual(6); // header, 4 outputs, head length (+ voice gap)
      expect(s.text.ko.staff.decree).toMatch(/이장 방송 길이: 기본 [\d.]+초\(한도 35초\) \+ 문의 [\d.]+초\(한도 10초\) = [\d.]+초/);
      expect(s.text.en.staff.decree).not.toMatch(HANGUL);
      expect(s.violations.filter((v) => v.includes('staff.decree'))).toEqual([]);
    }
  });

  it('a report only: with or without the check, the same outputs and the same violations', () => {
    for (const p of real.slice(0, 120)) {
      const a = B(p, { nowIso: NOW, issuer: ISS });
      const b = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
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
      // form lint only (secondary); the registry decides what renders
      expect(agencyLike(bad, 'ko'), bad).toBe(bad === '합성군');
    }
    for (const bad of ['Leave now 18:30 you are safe', 'Safe Haven Office.', 'Hapseong County, depart by 6', 'We will send a bus Office']) {
      expect(agencyLike(bad, 'en'), bad).toBe(false);
    }
    for (const ok of ['합성군 재난안전과', '합성군 산림과', '합성군 119구조대', '합성읍 행정복지센터', '합성군청', '합성시 안전총괄과']) {
      expect(agencyLike(ok, 'ko'), ok).toBe(true);
    }
    for (const ok of ['Synthetic County Disaster Safety Division', 'Hapseong County Office', 'Synthetic Rescue Unit']) {
      expect(agencyLike(ok, 'en'), ok).toBe(true);
    }
  });

  it('English outputs carry Hangul only as the plan\'s own shelter name (head and family script), never in the voice call or family text; nothing withheld', () => {
    let koNameShown = 0;
    for (const p of real) {
      const s = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      expect(s.violations).toEqual([]);
      const en = s.text.en;
      const ko = s.destinationName?.ko;
      for (const t of [en.head.script, en.familyScript.join('\n')]) {
        const left = ko ? t.split(ko).join('') : t;
        expect(left).not.toMatch(HANGUL);
      }
      if (en.voice !== null) expect(en.voice).not.toMatch(HANGUL);
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
      const s = B(p, { nowIso: NOW, issuer: ISS });
      const m = smsSegments(s.text.en.familyText);
      seg[`${m.encoding}:${m.segments}`] = (seg[`${m.encoding}:${m.segments}`] ?? 0) + 1;
    }
    expect(seg).toEqual({ 'gsm7:1': 531 });
  });
});

describe('W6 confirmed answers (Iris / orchestrator): contact line last, voice interim, issuer form guard, whole-guidance recount', () => {
  const ISS = { agency: { ko: '합성군 재난안전과', en: 'Synthetic County Disaster Safety Division' }, contact: '000-0000-0000', forDrillOrReplay: true };

  it('the contact line is the last thing in the head, after the closer; the core stays within 20 s; per-message totals are reported (35 s + own 10 s)', () => {
    let max = 0, withLine = 0;
    for (const p of [...real, ...syn]) {
      const s = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      for (const l of ['ko', 'en'] as const) {
        const h = s.text[l].head;
        expect(h.coreS).toBeLessThanOrEqual(HEAD_CORE_MAX_S + 1e-9);
        if (h.contact) {
          withLine += 1;
          expect(h.script).toBe([h.opener, h.core, h.closer, h.contact].join('\n'));
          expect(h.contactS!).toBeLessThanOrEqual(HEAD_CONTACT_MAX_S);
          if (l === 'ko' && real.includes(p)) max = Math.max(max, h.fullS + h.contactS!);
        }
      }
    }
    expect(withLine).toBeGreaterThan(0);
    expect(max).toBeLessThanOrEqual(HEAD_FULL_MAX_S + HEAD_CONTACT_MAX_S);
    console.log('[W6] max ko head total over 531 real (opener+core+closer + contact):', max.toFixed(1), 's');
  });

  it('owner decision: no English automated call at a place whose shelter has no English name (373 of 531 real); every English call that exists names its destination in English; the human-read head keeps the Korean name with a reader note', () => {
    let dropped = 0, readerNotes = 0;
    const HANGUL = /[ᄀ-ᇿ㄰-㆏가-힣]/;
    const check = (p: MessagePlan, counted: boolean) => {
      const s = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      const d = namedDestination(p);
      const koOnly = !!d && !d.en;
      expect(englishCallDropped(p)).toBe(koOnly);
      // no English call output at all for those places: no text, a "not produced" report, no violation for it
      expect(s.text.en.voice === null).toBe(koOnly);
      expect(s.text.ko.voice).not.toBeNull();
      if (koOnly) {
        if (counted) dropped += 1;
        expect(s.decree!.en.voice.produced).toBe(false);
        expect(s.decree!.en.voice.contact).toBe('no_output');
        expect(s.violations.some((v) => v.startsWith('en.voice'))).toBe(false);
        expect(s.text.en.staff.decree).toContain(NO_EN_CALL_REPORT.en);
        expect(s.text.ko.staff.decree).toContain(NO_EN_CALL_REPORT.ko);
        // what the staff line says is true (Iris): the Korean call is unchanged, and in English the shelter is named
        // only in the village-head script and the family call script, in Korean script
        expect(s.text.en.head.script).toContain(d!.ko);
        expect(s.text.en.familyScript.join('\n')).toContain(d!.ko);
        expect(s.text.en.familyText).not.toContain(d!.ko);
      } else {
        // no partial call: an English call that exists for a place with a named destination names it in English and
        // never carries Hangul, and no call ever points to "the Korean message"
        const v = s.text.en.voice!;
        if (d) expect(v).toContain(d.en);
        expect(v).not.toMatch(HANGUL);
        expect(v).not.toMatch(/Korean message|no English name/i);
        expect(s.decree!.en.voice.produced).not.toBe(false);
      }
      const inHead = !!d && s.text.en.head.script.includes(d.ko) && !d.en;
      expect(!!s.text.en.staff.readerNote).toBe(inHead);
      if (inHead && counted) { readerNotes += 1; expect(s.text.en.staff.readerNote).toBe(`Reader: say the shelter name in Korean: ${d!.ko}`); }
    };
    for (const p of real) check(p, true);
    for (const p of syn) check(p, false);
    // Mira N1: the Korean automated call is unchanged by the drop — produced at every place, and identical to the call
    // built for the same place with an English shelter name added (so the English call is produced)
    let koSame = 0;
    for (const p of [...real, ...syn]) {
      if (!englishCallDropped(p)) continue;
      const withEn = { ...p, destination: { ...p.destination!, name: { ...p.destination!.name!, en: 'Synthetic Shelter Hall' } } } as MessagePlan;
      expect(englishCallDropped(withEn)).toBe(false);
      const a = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      const b = B(withEn, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      expect(a.text.ko.voice).not.toBeNull();
      expect(a.text.ko.voice).toBe(b.text.ko.voice);
      expect(b.text.en.voice).toContain('Synthetic Shelter Hall');
      koSame += 1;
    }
    expect(koSame).toBe(373 + 91);
    // the Korean staff line has one label separator (Mira N3)
    for (const p of real.filter(englishCallDropped).slice(0, 5)) expect(B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true }).text.ko.staff.decree).toContain(`영어 자동 음성전화: ${NO_EN_CALL_REPORT.ko}`);
    // the removed interim sentence reaches no output anywhere
    for (const p of [...real, ...syn]) expect(residentTexts(B(p, { nowIso: NOW, issuer: ISS })).join('\n')).not.toMatch(/named in the Korean message|no English name/);
    // the kit summary shows the size of the gap (Iris)
    expect(staffSummary(real, 'en')).toBe('[Staff] Places with no English automated call: 373 of 531 (the shelter has no English name; a design decision of this tool). The Korean automated call is unchanged at every place.');
    expect(staffSummary(real, 'ko')).toBe('[직원용] 영어 자동 음성전화를 만들지 않은 장소: 531곳 중 373곳 (대피장소에 영어 이름이 없음, 개발 측 결정). 한국어 자동 음성전화는 모든 장소에서 그대로 만듭니다.');
    // staff wording never uses "owner decision" / 소유자 / 운영책임자 (Iris, Sofia)
    for (const l of ['ko', 'en'] as const) for (const t of [NO_EN_CALL_REPORT[l], staffSummary(real, l)]) expect(t).not.toMatch(/owner|소유자|운영책임자|callers/i);
    console.log('[W6] English automated calls not produced (shelter without an English name, 531 real):', dropped, '; reader notes on English heads:', readerNotes);
    expect(dropped).toBe(373);
  });

  it('issuer form guard (Iris): agency names of the 2025 messages and standard agencies pass; adversarial names fail, including instructions ending in a valid suffix; form only', () => {
    // sender tags of the real 2025 evacuation texts (Sofia) and standard public agencies — public names, no resident data
    const realIssuers = ['의성군', '청송군', '안동시', '영양군', '산림청', '행정안전부', '경상북도', '소방청', '의성군청', '안동시청', '의성군 안전재난과', '안동시 재난안전과', '의성소방서', '단촌면 행정복지센터', '119안전센터', '경상북도 재난안전실', '남부지방산림청'];
    const failed = realIssuers.filter((n) => !agencyLike(n, 'ko'));
    console.log('[W6] real issuer strings passing the form guard:', realIssuers.length - failed.length, 'of', realIssuers.length, failed.length ? `failing: ${failed.join(', ')}` : '');
    expect(failed).toEqual([]);
    const adversarial = [
      '지금 출발하십시오 18:30 안전합니다',
      '지금 바로 출발하십시오 동',
      '18:30까지 대피 동',
      '18시까지 대피 센터',
      '안전합니다 센터',
      '대피하시기 바랍니다 군',
      '즉시 대피하라 면',
      '안심하세요 과',
      '구출합니다 대',
      '차량을 보내드립니다 센터',
      '합성군. 지금 대피 동',
      '가'.repeat(26) + '과',
      '합 성 군 재 난 안 전 과 팀',
    ];
    // Mira's FAIL set at 344657e: instruction-, transport-, status- and time-shaped names that end in a valid suffix
    adversarial.push(
      '구조대 도착 예정 본부', '119구조 출동 중 센터', '버스 배차 완료 상황실', '셔틀 운행 센터', '대피 불필요 상황실', '오늘 밤 대피 불필요 군',
      '대피 안 해도 됨 군', '대피명령 해제 상황실', '지금 바로 대피 동', '즉시 대피 대피소', '여섯시 출발 상황실', '30분 내 대피 본부',
      '반시간 후 출발 본부', '산불 진화 완료 본부', '셔틀운행센터', '대피불필요본부', '구조대도착예정본부', '버스배차상황실',
    );
    for (const a of adversarial) expect(agencyLike(a, 'ko'), a).toBe(false);
    for (const a of ['Rescue is coming Unit', 'Help is on the way Team', 'Transport provided Agency', 'No need to evacuate Office', 'Evacuate at six Office', 'Go now Unit', 'All clear Division', 'Evacuation cancelled Office', 'Bus at the hall Station', 'No Need To Evacuate Office', 'All Clear Division', 'Transport Provided Agency', 'Go Now Unit', 'Rescue Coming Unit', 'Shuttle Service']) expect(agencyLike(a, 'en'), a).toBe(false);
    for (const a of ['Leave now 18:30 you are safe', 'Leave by 6 p.m. Office', 'You are safe. Division', 'We will send a bus Office', 'Stay inside County']) expect(agencyLike(a, 'en'), a).toBe(false);
  });

  it('guidance as a whole (Sofia: the duty attaches to the guidance, not to each channel): places whose four Korean outputs together carry all four items', () => {
    let whole = 0, leaveBy = 0;
    const firstMissingDest: Record<string, number> = {};
    for (const p of real) {
      const s = B(p, { nowIso: NOW, issuer: ISS, draftDecreeCheck: true });
      const union = new Set(RESIDENT_OUTPUTS.flatMap((o) => s.decree!.ko[o].present));
      if (p.kind === 'leave_by') leaveBy += 1;
      if (DECREE_FIELDS.every((f) => union.has(f))) whole += 1;
      // first-message property (Iris, from Sofia's Andong case), measured: a timed output without the named shelter
      if (p.kind === 'leave_by' && namedDestination(p)) for (const o of RESIDENT_OUTPUTS) if (!s.decree!.ko[o].present.includes('shelter')) firstMissingDest[o] = (firstMissingDest[o] ?? 0) + 1;
    }
    console.log('[W6] places whose Korean guidance as a whole carries all four items:', whole, 'of 531 (leave-by', leaveBy, '); timed Korean outputs without the nameable shelter, by output:', JSON.stringify(firstMissingDest));
    expect(whole).toBeGreaterThan(0);
  });
});

describe('W6 issuer guard after Mira FAIL @ 344657e: registry first, structure second; staff told when a name is refused; packed SMS segments', () => {
  it('ALLOWLIST: only an exact registry name renders a contact line; the English name only when it is the entry\'s own; the committed registry has a source per entry and no numbers', () => {
    const reg: RegistryEntry[] = [{ ko: '합성군 재난안전과', en: 'Synthetic County Disaster Safety Division', source: 'test' }];
    expect(withTestRegistryOnly(reg, () => validIssuer({ agency: { ko: '합성군 재난안전과', en: 'Synthetic County Disaster Safety Division' }, contact: '000-0000-0000' }))!.agency.en).toBe('Synthetic County Disaster Safety Division');
    expect(withTestRegistryOnly(reg, () => validIssuer({ agency: { ko: '합성군 산림과' }, contact: '000-0000-0000' }))).toBeNull();
    expect(withTestRegistryOnly(reg, () => validIssuer({ agency: { ko: '합성군 재난안전과 ' }, contact: '000-0000-0000' }))).not.toBeNull(); // trimmed
    expect(withTestRegistryOnly(reg, () => validIssuer({ agency: { ko: '합성군재난안전과' }, contact: '000-0000-0000' }))).toBeNull(); // exact only
    expect(withTestRegistryOnly(reg, () => validIssuer({ agency: { ko: '합성군 재난안전과', en: 'Synthetic County Office' }, contact: '000-0000-0000' }))!.agency.en).toBeNull();
    expect(withTestRegistryOnly(reg, () => checkIssuer({ agency: { ko: '합성군 산림과' }, contact: '000-0000-0000' })).status).toBe('not_in_registry');
    // the committed registry: sourced, lint-clean, no digits that could be a number, no synthetic names
    expect(AGENCY_REGISTRY.length).toBeGreaterThan(0);
    for (const e of AGENCY_REGISTRY) {
      expect(e.source.length, e.ko).toBeGreaterThan(5);
      expect(agencyLike(e.ko, 'ko'), e.ko).toBe(true);
      expect(e.ko).not.toMatch(/합성|\d/);
      if (e.en) expect(agencyLike(e.en, 'en'), e.en).toBe(true);
    }
    // default registry in use when none is passed: a real body renders, a synthetic one does not
    const p = real.find((x) => x.kind === 'leave_by')!;
    const yes = buildChannels(p, { nowIso: NOW, issuer: { agency: { ko: '의성군' }, contact: '000-0000-0000', forDrillOrReplay: true }, draftDecreeCheck: true });
    expect(yes.text.ko.voice).toContain('문의: 의성군 000-0000-0000');
    const no = buildChannels(p, { nowIso: NOW, issuer: { agency: { ko: '합성군 재난안전과' }, contact: '000-0000-0000', forDrillOrReplay: true }, draftDecreeCheck: true });
    expect(residentTexts(no).join('\n')).not.toContain('000-0000-0000');
    expect(no.decree!.ko.voice.contact).toBe('not_in_registry');
    expect(no.decree!.ko.voice.reasons.agency_contact).toBe('not_supplied');
  });

  it('property: no free-text issuer string reaches any output — Mira\'s 36 names, the adversarial lists and 2,000 fuzzed strings, with the default registry', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    const q = real.find((x) => x.kind !== 'leave_by')!;
    const mira = ['구조대 도착 예정 본부', '119구조 출동 중 센터', '버스 배차 완료 상황실', '셔틀 운행 센터', '대피 불필요 상황실', '오늘 밤 대피 불필요 군', '대피 안 해도 됨 군', '대피명령 해제 상황실', '지금 바로 대피 동', '즉시 대피 대피소', '여섯시 출발 상황실', '30분 내 대피 본부', '반시간 후 출발 본부', '산불 진화 완료 본부', '지금 출발하십시오 18:30 안전합니다', '합성군 재난안전과', '의성군 ', ' 안동시청'];
    let seed = 20261112;
    const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    const parts = ['의성군', '안동시', '대피', '본부', '지금', ' ', '과', '센터', '안전', '18:30', '군', 'Office', 'safe', '출발', '산림청', '행정안전부', '청', '·'];
    const fuzz = Array.from({ length: 2000 }, () => Array.from({ length: 1 + Math.floor(rnd() * 4) }, () => parts[Math.floor(rnd() * parts.length)]).join(''));
    const reg = new Set(AGENCY_REGISTRY.map((e) => e.ko));
    let tried = 0;
    for (const name of [...mira, ...fuzz]) {
      if (reg.has(name.trim())) continue; // an exact registry name is allowed by design
      tried += 1;
      for (const pl of [p, q]) {
        const s = buildChannels(pl, { nowIso: NOW, issuer: { agency: { ko: name, en: 'Synthetic Office' }, contact: '000-0000-0000', forDrillOrReplay: true }, draftDecreeCheck: true });
        const texts = residentTexts(s).join('\n');
        expect(texts.includes('000-0000-0000'), name).toBe(false);
        expect(/문의:|Contact:/.test(texts), name).toBe(false);
      }
    }
    expect(tried).toBeGreaterThan(1500);
  });

  it('an issuer not in the registry adds no contact line, and both staff reports say why', () => {
    const p = real.find((x) => x.kind === 'leave_by')!;
    const s = B(p, { nowIso: NOW, issuer: { agency: { ko: '구조대 도착 예정 본부', en: 'Rescue is coming Unit' }, contact: '000-0000-0000', forDrillOrReplay: true }, draftDecreeCheck: true });
    expect(residentTexts(s).join('\n')).not.toMatch(/문의|Contact|도착 예정|coming/);
    expect(s.text.ko.staff.decree).toMatch(/문의처 없음 — 고칠 항목: 기관명\. 입력한 기관명이 등록된 공식 발령 기관\(시·군\) 목록에 없습니다/);
    expect(s.text.en.staff.decree).toMatch(/No contact line — field to fix: issuer name\. It is not in the registry of official issuing bodies/);
    const ok = B(p, { nowIso: NOW, issuer: { agency: { ko: '합성군 재난안전과' }, contact: '000-0000-0000', forDrillOrReplay: true }, draftDecreeCheck: true });
    expect(ok.text.ko.staff.decree).not.toMatch(/문의처 없음/);
  });

  it('SMS segments are packed: an escape pair or a surrogate pair never straddles a segment boundary (Mira note)', () => {
    expect(smsSegments(`${'a'.repeat(152)}{${'a'.repeat(152)}`).segments).toBe(3); // 306 septets, naive ceil = 2
    expect(smsSegments(`${'a'.repeat(153)}${'a'.repeat(153)}`).segments).toBe(2);
    expect(smsSegments(`${'가'.repeat(66)}😀${'가'.repeat(66)}`).segments).toBe(3); // 134 units, naive ceil = 2
    expect(smsSegments('가'.repeat(134)).segments).toBe(2);
  });
});

describe('W6 delta after Mira PASS WITH NOTES @ 9695e26: 시·군 registry, phone-shaped numbers, no registry override in app code, exact-match normalisation', () => {
  const p = () => real.find((x) => x.kind === 'leave_by')!;
  const q = () => real.find((x) => x.kind !== 'leave_by')!;
  const outs = (s: ChannelSet) => residentTexts(s).join('\n');

  it('the committed registry holds issuing 시·군 only, each sourced and lint-clean (build-time self-test)', () => {
    // 영덕군 added by owner decision (2026-11-12) from a secondary source, flagged in its entry
    expect(AGENCY_REGISTRY.map((e) => e.ko)).toEqual(['의성군', '청송군', '안동시', '영양군', '영덕군']);
    for (const e of AGENCY_REGISTRY) {
      expect(e.ko).toMatch(/(시|군)$/);
      expect(e.source.trim().length).toBeGreaterThan(10);
      expect(agencyLike(e.ko, 'ko'), e.ko).toBe(true);
      if (e.en) expect(agencyLike(e.en, 'en'), e.en).toBe(true);
    }
    expect(validIssuer({ agency: { ko: '안동시', en: 'Andong City' }, contact: '000-000-0000' })!.agency.en).toBe('Andong City');
    expect(validIssuer({ agency: { ko: '안동시', en: 'Andong-si' }, contact: '000-000-0000' })!.agency.en).toBeNull();
  });

  it('exact match after NFC + trim only: extra text, look-alikes, zero-width and inner whitespace all fail', () => {
    const c = '000-000-0000';
    expect(validIssuer({ agency: { ko: ' 의성군\t' }, contact: c })).not.toBeNull();
    expect(validIssuer({ agency: { ko: '의성군'.normalize('NFD') }, contact: c })!.agency.ko).toBe('의성군');
    for (const bad of ['의성군 지금 대피', '지금 대피 의성군', '의성군(버스 배차 완료)', '의성 군', '​의성군', '의성군​', '의‍성군', '의성郡', '경북 의성군', '의성군청', '안동시 안전재난과', '영덕군청', '경북 영덕군', '경상북도', '산림청']) {
      expect(validIssuer({ agency: { ko: bad }, contact: c }), bad).toBeNull();
      expect(outs(buildChannels(p(), { nowIso: NOW, issuer: { agency: { ko: bad }, contact: c, forDrillOrReplay: true } }))).not.toContain(c);
    }
  });

  it('the contact number must have a Korean phone shape; times, dates, bare digits and emergency numbers are refused, and staff are told which field to fix', () => {
    for (const ok of ['000-000-0000', '000-0000-0000', '02-2000-0000', '054-200-0000', '031-2000-0000', '064-700-0000', '1588-0000', '1600-0000', '1800-0000']) expect(phoneShaped(ok), ok).toBe(true);
    // tidy-up: personal safe numbers (050), VoIP (070), unassigned prefixes and non-representative 1XXX are refused too
    for (const bad of ['050-0000-0000', '0505-000-0000', '070-0000-0000', '012-000-0000', '013-000-0000', '1000-0000', '1119-0000', '1004-0000', '054-000-0000', '054-123-0000', '02-0123-0000', '039-200-0000', '065-200-0000', '080-200-0000', '010-112-0000']) expect(phoneShaped(bad), bad).toBe(false);
    // mobile numbers are personal data, never an agency contact line (Mira note N1)
    for (const mob of ['010-0000-0000', '011-000-0000', '016-0000-0000', '017-000-0000', '018-0000-0000', '019-000-0000']) expect(phoneShaped(mob), mob).toBe(false);
    for (const bad of ['18-30', '1830', '2025-03-25', '112-0', '01-12', '112', '119', '1-1-2', '0000', '18:30', '000-0000-0000-0000', '000 000 0000', '1-000-0000', '+82-00-000-0000']) expect(phoneShaped(bad), bad).toBe(false);
    const s = buildChannels(p(), { nowIso: NOW, issuer: { agency: { ko: '의성군' }, contact: '18-30', forDrillOrReplay: true }, draftDecreeCheck: true });
    expect(outs(s)).not.toMatch(/문의|18-30/);
    expect(s.text.ko.staff.decree).toMatch(/고칠 항목: 연락처/);
    expect(s.text.en.staff.decree).toMatch(/field to fix: contact number/);
    const ok = buildChannels(p(), { nowIso: NOW, issuer: { agency: { ko: '의성군' }, contact: '000-000-0000', forDrillOrReplay: true }, draftDecreeCheck: true });
    expect(ok.text.ko.voice).toContain('문의: 의성군 000-000-0000');
    expect(ok.text.ko.staff.decree).toMatch(/입력값이며 확인되지 않았습니다/);
  });

  it('property: free text in ANY field of the contact line (name or number) never reaches an output — 3,000 fuzzed pairs, default registry', () => {
    let seed = 912;
    const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
    const nameParts = ['의성군', '안동시', ' ', '지금', '대피', '​', '군', '시', 'Office', '청', '(', ')', '영덕군', '안전'];
    const numParts = ['000', '-', '18', ':', '30', '0000', '2025', '119', '1', ' ', 'a', '+82'];
    const reg = new Set(AGENCY_REGISTRY.map((e) => e.ko));
    let refused = 0;
    for (let n = 0; n < 3000; n++) {
      const name = Array.from({ length: 1 + Math.floor(rnd() * 3) }, () => nameParts[Math.floor(rnd() * nameParts.length)]).join('');
      const num = Array.from({ length: 1 + Math.floor(rnd() * 5) }, () => numParts[Math.floor(rnd() * numParts.length)]).join('');
      const nameOk = reg.has(name.normalize('NFC').trim());
      const numOk = phoneShaped(num.trim());
      const s = buildChannels(n % 2 ? p() : q(), { nowIso: NOW, issuer: { agency: { ko: name, en: 'Synthetic Office' }, contact: num, forDrillOrReplay: true } });
      const o = outs(s);
      if (!(nameOk && numOk)) {
        refused += 1;
        expect(/문의:|Contact:/.test(o), `${name} | ${num}`).toBe(false);
      }
      expect(o.includes('Synthetic Office')).toBe(false);
    }
    expect(refused).toBeGreaterThan(2500);
  });

  it('owner decision: 영덕군 is registered from a SECONDARY source (the 경상북도 contact table) and says so; with an issuer record supplied, the 영덕 place-scenarios IN 영덕군 gain a contact line (246 of 273; the 27 in 청송군/영양군 are withheld by the jurisdiction rule)', () => {
    const e = AGENCY_REGISTRY.find((x) => x.ko === '영덕군')!;
    expect(e).toBeDefined();
    expect(e.secondary).toBe(true);
    expect(e.en).toBeNull();
    expect(e.source).toMatch(/^SECONDARY SOURCE/);
    expect(e.source).toContain('gb.go.kr/gbsafe/page/2406/5015.tc');
    // every other entry is a primary source
    for (const x of AGENCY_REGISTRY) if (x.ko !== '영덕군') expect(x.secondary).toBeUndefined();
    const before = AGENCY_REGISTRY.filter((x) => x.ko !== '영덕군');
    const iss = { agency: { ko: '영덕군' }, contact: '000-000-0000', forDrillOrReplay: true };
    let n = 0, gained = 0, others = 0, withheld = 0;
    for (const pl of real) {
      if (!pl.input.region.id.startsWith('yeongdeok')) continue;
      n += 1;
      const now = buildChannels(pl, { nowIso: NOW, issuer: iss, draftDecreeCheck: true });
      const old = withTestRegistryOnly(before, () => buildChannels(pl, { nowIso: NOW, issuer: iss, draftDecreeCheck: true }));
      expect(old.decree!.ko.familyScript.contact).toBe('not_in_registry');
      expect(residentTexts(old).join('\n')).not.toContain('문의: 영덕군');
      if (pl.input.origin.sigungu?.ko !== '영덕군') {
        withheld += 1;
        expect(now.decree!.ko.familyScript.contact).toBe('jurisdiction_mismatch');
        expect(residentTexts(now).join('\n')).not.toContain('000-000-0000');
        continue;
      }
      if (now.decree!.ko.familyScript.contact === 'included') gained += 1;
      expect(now.text.ko.familyScript.join('\n')).toContain('문의: 영덕군 000-000-0000');
      // no English name: no English contact line (the field is reported, not filled)
      expect(residentTexts(now).filter((t) => /^[\x00-\x7F\n]*$/.test(t)).join('\n')).not.toContain('000-000-0000');
      expect(now.violations).toEqual(old.violations);
    }
    for (const pl of real) if (!pl.input.region.id.startsWith('yeongdeok')) others += 1;
    console.log('[W6] 영덕 place-scenarios gaining a contact line with an issuer record (531 real):', gained, 'of', n, '; other regions:', others);
    expect(n).toBe(273);
    expect(gained).toBe(246);
    expect(withheld).toBe(27);
  });

  it('no registry override is reachable from app code: no ChannelOptions field, and nothing under planner/src calls the test-only hook', () => {
    const { execFileSync } = require('node:child_process') as typeof import('node:child_process');
    let hits: string[] = [];
    try {
      hits = execFileSync('grep', ['-rlnE', 'withTestRegistryOnly|override|agencyRegistry[?]?:', new URL('../../planner/src/features/lastmile/', import.meta.url).pathname], { encoding: 'utf8' }).trim().split('\n').filter(Boolean);
    } catch {
      hits = []; // grep exits 1 when nothing matches
    }
    // production code has no registry override at all; the substitution lives only in this test file's module mock
    expect(hits).toEqual([]);
    expect(() => withTestRegistryOnly([{ ko: 'x군', en: null, source: '' }], () => 0)).toThrow();
  });
});

// ------------------------------------------------------------------------------------------------ jurisdiction

describe('jurisdiction (pre-registered pass rule, research/harness-2026-11/W-KIT/JURISDICTION/DESIGN.md)', () => {
  const drill = (ko: string) => ({ agency: { ko }, contact: '000-000-0000', forDrillOrReplay: true });
  const withLabel = (p: MessagePlan, sigungu: unknown): MessagePlan => ({ ...p, input: { ...p.input, origin: { ...p.input.origin, sigungu: sigungu as never } } });
  const resident = (s: ChannelSet) => residentTexts(s).join('\n');
  const staffBoth = (s: ChannelSet) => [s.text.ko.staff.jurisdiction ?? '', s.text.en.staff.jurisdiction ?? ''];

  it('item 5: every real origin carries exactly one label with a source; counts by region and county', () => {
    const counts: Record<string, Record<string, number>> = {};
    const seen = new Set<string>();
    for (const i of realInputs) {
      const g = i.origin.sigungu;
      expect(g, i.origin.id).toBeTruthy();
      expect(g!.source).toMatch(/^행정구역: BND_SIGUNGU_PG \(BASE_DATE 2025-06-30\)/);
      expect(g!.status === 'established' ? g!.reason === null && !!g!.ko : g!.ko === null && !!g!.reason).toBe(true);
      if (seen.has(`${i.region.id}/${i.origin.id}`)) continue;
      seen.add(`${i.region.id}/${i.origin.id}`);
      const k = g!.status === 'established' ? g!.ko! : g!.reason!;
      (counts[i.region.id] ??= {})[k] = (counts[i.region.id]![k] ?? 0) + 1;
    }
    console.log('[JUR] origins by region and 시·군 (50 m):', JSON.stringify(counts));
    expect(counts).toEqual({ uiseong_andong_2025: { 의성군: 48, 안동시: 38 }, yeongdeok_2025: { 영덕군: 82, 청송군: 4, 영양군: 5 } });
  });

  it('items 1-3 (531 real): no registered issuer renders a line outside its own established 시·군; every withheld line has a staff warning in both languages; correct-county coverage reported', () => {
    const cross: string[] = [];
    const report: Record<string, { correct: number; included: number; withheld: number }> = {};
    for (const e of AGENCY_REGISTRY) {
      const r = (report[e.ko] = { correct: 0, included: 0, withheld: 0 });
      for (const pl of real) {
        const s = buildChannels(pl, { nowIso: NOW, issuer: drill(e.ko), draftDecreeCheck: true });
        const has = resident(s).includes('000-000-0000');
        const g = pl.input.origin.sigungu;
        const own = g?.status === 'established' && g.ko === e.ko;
        if (own) r.correct += 1;
        if (has) {
          r.included += 1;
          if (!own) cross.push(`${e.ko} @ ${pl.input.region.id}/${pl.input.origin.id} (${g?.ko ?? g?.reason})`);
        } else if (!own) {
          r.withheld += 1;
          const [ko, en] = staffBoth(s);
          expect(ko).toContain(`입력한 기관(${e.ko})이 이 장소가 속한 시·군(${g!.ko})과 다릅니다`);
          expect(en).toContain(`The issuer (${e.ko}) is not this place's 시·군 (${g!.ko})`);
          expect(s.text.ko.staff.decree).toContain(ko);
          expect(s.text.en.staff.decree).toContain(en);
          expect(s.decree!.ko.familyScript.contact).toBe('jurisdiction_mismatch');
        }
      }
      // coverage: every place-scenario of the issuer's own county keeps its line (head may be over budget, family text may not fit, so count the family script)
      expect(r.included).toBe(r.correct);
    }
    console.log('[JUR] per registered issuer over 531 real place-scenarios {correct-county, line rendered, withheld}:', JSON.stringify(report));
    expect(cross).toEqual([]);
    expect(report['영덕군']).toEqual({ correct: 246, included: 246, withheld: 285 });
    expect(report['의성군']!.included).toBe(144);
    // the two cross-county cases named in the design: 영덕군 on 의성–안동 and 의성군 on 영덕 are now 0 (from 258 and 273)
    expect(real.filter((pl) => pl.input.region.id.startsWith('uiseong') && resident(buildChannels(pl, { nowIso: NOW, issuer: drill('영덕군') })).includes('000-000-0000')).length).toBe(0);
    expect(real.filter((pl) => pl.input.region.id.startsWith('yeongdeok') && resident(buildChannels(pl, { nowIso: NOW, issuer: drill('의성군') })).includes('000-000-0000')).length).toBe(0);
  });

  it('item 2: no line where the label is not established, absent or malformed — each reason in plain words, both languages', () => {
    const pl = real.find((x) => x.input.origin.sigungu?.ko === '의성군')!;
    const cases: [unknown, RegExp, RegExp][] = [
      [{ ko: null, status: 'not_established', reason: 'near_boundary', source: 's' }, /경계에서 50 m 안/, /within 50 m of a 시·군 boundary/],
      [{ ko: null, status: 'not_established', reason: 'outside_all', source: 's' }, /어느 시·군 경계 안에도/, /inside no 시·군 boundary/],
      [{ ko: null, status: 'not_established', reason: 'multiple', source: 's' }, /두 시·군 경계/, /more than one 시·군 boundary/],
      [{ ko: null, status: 'not_established', reason: 'entry_differs', source: 's' }, /도로 진입 지점이 다른 시·군/, /road entry point lies in another 시·군/],
      [null, /행정구역 자료 없음/, /no boundary label/],
      [undefined, /행정구역 자료 없음/, /no boundary label/],
    ];
    for (const [label, ko, en] of cases) {
      const s = buildChannels(withLabel(pl, label), { nowIso: NOW, issuer: drill('의성군'), draftDecreeCheck: true });
      expect(resident(s)).not.toContain('000-000-0000');
      expect(s.decree!.ko.familyScript.contact).toBe('jurisdiction_not_established');
      expect(s.text.ko.staff.jurisdiction).toMatch(ko);
      expect(s.text.en.staff.jurisdiction).toMatch(en);
    }
    // the parser never reads a malformed label as established
    for (const bad of [{ ko: '의성군', status: 'established', reason: null }, { ko: '의성군 ', status: 'established', reason: null, source: 's' }, { ko: '의성군', status: 'established', reason: 'near_boundary', source: 's' }, { ko: '의성군', status: 'not_established', reason: 'near_boundary', source: 's' }, { ko: null, status: 'not_established', reason: 'other', source: 's' }, 'established'])
      expect(parseSigungu(bad)).toBeNull();
    expect(parseSigungu({ ko: '의성군', status: 'established', reason: null, source: 's' })).toEqual({ ko: '의성군', status: 'established', reason: null, source: 's' });
  });

  it('item 4: nothing else changes — no issuer: the label changes no output; matched: Main\'s output; withheld: exactly the no-issuer resident output and violations (531 real + 600 synthetic)', () => {
    let matched = 0, withheld = 0;
    for (const pl of [...real, ...syn]) {
      const unlabelled = withLabel(pl, null);
      const a = buildChannels(pl, { nowIso: NOW, draftDecreeCheck: true });
      const b = buildChannels(unlabelled, { nowIso: NOW, draftDecreeCheck: true });
      expect(JSON.stringify(a.text)).toBe(JSON.stringify(b.text));
      expect(a.violations).toEqual(b.violations);
      for (const ko of ['의성군', '영덕군']) {
        const s = buildChannels(pl, { nowIso: NOW, issuer: drill(ko), draftDecreeCheck: true });
        const g = pl.input.origin.sigungu;
        if (g?.status === 'established' && g.ko === ko) {
          matched += 1;
          continue;
        }
        withheld += 1;
        expect(residentTexts(s)).toEqual(residentTexts(a));
        expect(s.violations).toEqual(a.violations);
      }
    }
    console.log('[JUR] item 4: matched', matched, 'withheld', withheld);
    expect(matched).toBe(144 + 246);
    expect(withheld).toBe(2 * (531 + 600) - matched);
  });

  it('item 4 (matched = Main): with the label matching, the output equals the pre-jurisdiction kit (rule bypassed by labelling every place in the issuer\'s county)', () => {
    for (const pl of real.filter((x) => x.input.origin.sigungu?.ko === '의성군').slice(0, 60)) {
      const s = buildChannels(pl, { nowIso: NOW, issuer: drill('의성군'), draftDecreeCheck: true });
      const t = buildChannels(withLabel(pl, { ko: '의성군', status: 'established', reason: null, source: 'other' }), { nowIso: NOW, issuer: drill('의성군'), draftDecreeCheck: true });
      expect(JSON.stringify(s.text)).toBe(JSON.stringify(t.text));
      expect(s.text.ko.staff.jurisdiction ?? null).toBeNull();
      expect(resident(s)).toContain('문의: 의성군 000-000-0000');
    }
  });
});
