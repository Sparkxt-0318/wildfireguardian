/**
 * W-KIT channel outputs (planner/src/features/lastmile/channels/build.ts), checked over EVERY origin of the six booth
 * caches and the kit's 600 generated synthetic cases, plus unit tests of each rule. The module's own checks
 * (checkChannels) are re-tested with independent oracles: Python's strict euc_kr codec for byte counts, the kit's
 * NEVER / DEPART patterns (lastmile.oracle.ts) and a separate clock-time regex.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { createHash } from 'node:crypto';
import { hm } from '../../planner/src/features/lastmile/compose';
import { buildFieldMessages } from '../../planner/src/features/lastmile/messages';
import { messagePlan, type MessagePlan } from '../../planner/src/features/lastmile/plan';
import {
  buildChannels,
  checkChannels,
  ELEMENTS,
  HEAD_CORE_MAX_S,
  HEAD_FULL_MAX_S,
  orderNotIssued,
  transportNeedList,
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
const ISSUE = { leaveByS: 1800, issueByS: { low: 900, median: -60, high: 600 } };
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
    expect(T({ leaveByS: 1800, issueByS: { low: -600, median: 600, high: 1800 } })).toMatch(/이미 지남 .* \d\d:\d\d .* \d\d:\d\d/);
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
