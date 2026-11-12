/**
 * W-KIT channel outputs (planner/src/features/lastmile/channels/build.ts), checked over EVERY origin of the six booth
 * caches and the kit's 600 generated synthetic cases, plus unit tests of each rule. The module's own checks
 * (checkChannels) are re-tested with independent oracles: Python's strict euc_kr codec for byte counts, the kit's
 * NEVER / DEPART patterns (lastmile.oracle.ts) and a separate clock-time regex.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { hm } from '../../planner/src/features/lastmile/compose';
import { messagePlan, type MessagePlan } from '../../planner/src/features/lastmile/plan';
import {
  buildChannels,
  checkChannels,
  ELEMENTS,
  HEAD_CORE_MAX_S,
  HEAD_FULL_MAX_S,
  STANDARD_MAX_CHARS,
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
const build = (p: MessagePlan) => buildChannels(p, { nowIso: NOW, orderStatus: 'not_issued', issueOrderBy: { offsetS: 600 } });

beforeAll(() => {
  real = loadBoothCaches().flatMap((c) => c.inputs).map((i) => messagePlan(i, null));
  syn = generateCases(20261102, 600).map((g) => messagePlan(g.input, g.file));
}, 300_000);

function residentTexts(s: ChannelSet): string[] {
  return (['ko', 'en'] as const).flatMap((l) => {
    const t = s.text[l];
    return [[t.head.opener, t.head.core, t.head.closer].join('\n'), t.voice, t.familyText, t.familyScript.join('\n'), ...(t.noOrder ? [t.noOrder] : [])];
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
    if (bytes) for (const b of bytes) expect(typeof b === 'number' && b <= 90).toBe(true);
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
    expect(viol.length).toBe(18);
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
      for (const l of ['ko', 'en'] as const) if (s.text[l].noOrder) expect([...s.text[l].noOrder!].length).toBeLessThanOrEqual(STANDARD_MAX_CHARS);
    }
  });
});

describe('rules, one by one', () => {
  const leave = () => messagePlan(synInput(), null);
  const unresolved = () => messagePlan(synInput({ plan: null }), null);

  it('no-order message only when officials supply not_issued', () => {
    const p = leave();
    expect(buildChannels(p, { nowIso: NOW }).text.ko.noOrder).toBeNull();
    expect(buildChannels(p, { nowIso: NOW, orderStatus: 'issued' }).text.ko.noOrder).toBeNull();
    const t = buildChannels(p, { nowIso: NOW, orderStatus: 'not_issued' }).text;
    expect(t.ko.noOrder).toContain('아직 공식 대피 명령은 없습니다');
    expect(t.ko.noOrder).toContain('명령이 없다고 위험이 없는 것은 아닙니다');
    expect(t.en.noOrder).toContain('No order yet is not an all-clear');
  });

  it('issue-order-by: a time only for leave_by with a computed value; never for unresolved', () => {
    const p = leave();
    expect(buildChannels(p, { nowIso: NOW, issueOrderBy: { offsetS: 600 } }).text.ko.staff.issueOrderBy).toContain(hm(p.input.scenario.inputTimeIso, 600));
    expect(buildChannels(p, { nowIso: NOW, issueOrderBy: { status: 'unresolved' } }).text.ko.staff.issueOrderBy).toContain('산출되지 않음');
    expect(buildChannels(p, { nowIso: NOW, issueOrderBy: null }).text.en.staff.issueOrderBy).toContain('not computed');
    const u = unresolved();
    expect(buildChannels(u, { nowIso: NOW, issueOrderBy: { offsetS: 600 } }).text.ko.staff.issueOrderBy).toContain('산출되지 않음');
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
    const other = Object.values(p.input.destinations).find((d) => d.name && d.name.ko !== s.destinationName?.ko);
    if (other?.name) {
      const bad2 = structuredClone(s); bad2.text.ko.familyScript[1] += ` ${other.name.ko} 쪽입니다.`;
      expect(checkChannels(p, bad2).some((v) => v.includes('names destination'))).toBe(true);
    }
    const u = unresolved();
    const su = buildChannels(u, { nowIso: NOW });
    const bad3 = structuredClone(su); bad3.text.ko.familyText += '\n18:40까지 차로 출발';
    expect(checkChannels(u, bad3).some((v) => /departure instruction|clock time/.test(v))).toBe(true);
  });
});

describe('transport-need list (key 2)', () => {
  const mk = (id: string, verdicts: Parameters<typeof cells>[0] | null, rank: number) =>
    messagePlan(synInput({ originId: id, urgencyRank: rank, plan: verdicts ? { bestVerdict: verdicts.includes('checked_route') ? 'checked_route' : (verdicts[0] as never), latestSafeDepartureS: null, contiguousSafeDepartureS: null, sweep: cells(verdicts), note: null } : null }), null);

  it('origins without a checked leave-by come first; then leave-by ascending; ties by urgency rank then reply time; key 1 and 3 excluded; unknown keys kept', () => {
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
    expect(rows.map((r) => `${r.originId}:${r.code}`)).toEqual(['o:noroute:needs_help', 'o:unres:needs_help', 'o:missing:needs_help', 'o:early:needs_help', 'o:early:unknown']);
    expect(rows.filter((r) => r.checkFirst).map((r) => r.originId)).toEqual(['o:noroute', 'o:unres', 'o:missing']);
  });
});
