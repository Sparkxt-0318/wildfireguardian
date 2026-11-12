/**
 * Iris E (approved by the orchestrator): the staff headline time is the time residents get. Over every origin of the
 * six booth caches and the 600 synthetic cases: the planner's staff headline (deadlineHeadline, used by the right panel,
 * the origin list, the timeline ticks, the default selected departure, the A4 sheet row and the CSV deadline column)
 * equals the kit's leave-by time (messagePlan) and the public card shows a time exactly when they do. A later checked
 * departure after a gap is only ever a labelled window, never the headline.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { compareUrgency, deadlineHeadline, headlineDepartureS } from '../../planner/src/domain/plan';
import type { OriginPlan, Place } from '../../planner/src/domain/types';
import { defaultOffsetS } from '../../planner/src/state/controller';
import { scenarioRow } from '../../planner/src/state/featureData';
import { deadlineCell } from '../../planner/src/features/plansheet/sheetLogic';
import { dispatchListCSV } from '../../planner/src/features/exports/exports';
import { buildChannels } from '../../planner/src/features/lastmile/channels/build';
import { hm, koSpokenTime, enSpokenTime } from '../../planner/src/features/lastmile/compose';
import { clockAt, kstDateClock } from '../../planner/src/features/shared/format';
import { translate } from '../../planner/src/i18n';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import { cardFor } from '../../planner/src/features/publicview/model';
import type { LastMileInput } from '../../planner/src/features/lastmile/types';
import { loadBoothCaches } from './lastmile.cachedata';
import { generateCases } from './lastmile.generator';

const PROV = { checkpoint: 'x', packageVersion: '1.0.0', kit: 'v3', apiMode: 'cache' as const, cacheApiMode: null, apiVersion: null, gitCommit: null, cacheCreatedAtIso: null, scenarioSetId: 's', scenarioIds: [] };

let real: LastMileInput[] = [];
let syn: LastMileInput[] = [];
type Case = { set: 'real' | 'syn'; i: LastMileInput; op: OriginPlan | undefined; place: Place; byId: Map<string, Place> };
let cases: Case[] = [];

/** a synthetic kit input's plan as the planner holds plans (window-closed cells are window skips) */
function opOf(i: LastMileInput): OriginPlan | undefined {
  const p = i.plan;
  if (!p) return undefined;
  return {
    originId: i.origin.id,
    bestVerdict: p.bestVerdict,
    latestSafeDepartureS: p.latestSafeDepartureS,
    contiguousSafeDepartureS: p.contiguousSafeDepartureS,
    sweep: p.sweep.map((c) => ({
      offsetS: c.offsetS,
      verdict: c.verdict === 'window_closed' ? 'unresolved' : c.verdict,
      ...(c.verdict === 'window_closed' ? { skipped: 'window_unsatisfiable' } : {}),
      attempts: c.attempts.map((a) => ({ ...a, offsetS: c.offsetS, jobId: null, computeS: null })),
    })),
    windows: [],
    note: p.note ?? undefined,
  } as unknown as OriginPlan;
}

beforeAll(() => {
  const booth = loadBoothCaches();
  real = booth.flatMap((c) => c.inputs);
  syn = generateCases(20261102, 600).map((g) => g.input);
  for (const b of booth) {
    const byId = new Map(b.places.map((p) => [p.id, p]));
    for (const i of b.inputs) cases.push({ set: 'real', i, op: b.plans[i.origin.id], place: byId.get(i.origin.id)!, byId });
  }
  for (const i of syn) cases.push({ set: 'syn', i, op: opOf(i), place: { id: i.origin.id, name: i.origin.name?.ko ?? null, role: 'origin', checkable: true } as unknown as Place, byId: new Map() });
}, 300_000);

const t = (k: string, v?: Record<string, string | number>) => translate('ko', k, v);

describe('staff headline == resident card time == kit time', () => {
  it('T is the same on every surface — panel headline / origin chip (one function), default timeline selection, drawn route, A4 deadline cell, CSV deadline column, resident card and kit — and the kind matches', () => {
    for (const { set, i, op, place, byId } of cases) {
      const iso = i.scenario.inputTimeIso;
      const p = messagePlan(i, null);
      const kit = p.kind === 'leave_by' ? p.leaveByS : null;
      const h = deadlineHeadline(op);
      const id = `${set}:${i.origin.id}`;
      expect(h.deadlineS, id).toBe(kit);
      // the single function returns the kind too: partial <-> partial, no time <-> no time
      if (p.kind === 'partial') expect(h.kind, id).toBe('partial');
      if (h.kind === 'partial') expect(p.kind, id).toBe('partial');
      expect(cardFor(i).kind, id).toBe(p.kind);
      // default timeline selection
      if (op?.bestVerdict === 'checked_route' && kit !== null) expect(defaultOffsetS(op), id).toBe(kit);
      // the A4 row (drawn route departure) and its deadline cell
      const row = scenarioRow({ scenarioSetId: 's', inputTimeIso: iso, issuedAtIso: null, plans: op ? { [i.origin.id]: op } : {}, route: () => null, travelOnly: () => null, hostFallback: null }, place, byId, t);
      if (op?.bestVerdict === 'checked_route') expect(row.departureS, id).toBe(kit);
      expect(deadlineCell(row, 'ko').main, id).toBe(kit === null ? '—' : clockAt({ inputTimeIso: iso, issuedAtIso: null }, kit));
      // the CSV deadline column
      const csv = dispatchListCSV({
        region: { id: 'r', nameKo: 'r', nameEn: 'r', fireYear: 2025 }, fireInputLabel: 'x', fireInputType: 'recorded', mock: false,
        scenario: { scenarioSetId: 's', inputTimeIso: iso },
        origins: [{ id: i.origin.id, name: 'x', categoryLabel: '마을', sourceTag: 'place=village', lon: 127, lat: 36, vulnerable: false, plan: op ? { bestVerdict: op.bestVerdict, latestSafeDepartureS: op.latestSafeDepartureS, contiguousSafeDepartureS: op.contiguousSafeDepartureS, sweep: i.plan!.sweep.map((c) => ({ offsetS: c.offsetS, verdict: c.verdict })), best: null } : null }],
        selectedRoute: null, provenance: PROV,
        generatedAtIso: '2026-11-12T00:00:00Z',
      } as never);
      const col = csv.split('\r\n')[1]!.split(',')[5]!;
      if (op?.bestVerdict === 'checked_route') expect(col, id).toBe(kit === null ? '없음' : kstDateClock(iso, kit));
      else expect(col, id).toBe('');
    }
  });

  it('the later checked departure (L) of a gap case appears in no resident output: not on the card, not in any kit message', () => {
    let n = 0;
    for (const i of syn) {
      const h = deadlineHeadline(i.plan);
      if (h.kind !== 'deadline' || h.laterWindowS === null) continue;
      n += 1;
      const iso = i.scenario.inputTimeIso;
      const forms = [hm(iso, h.laterWindowS), koSpokenTime(iso, h.laterWindowS), enSpokenTime(iso, h.laterWindowS)];
      const c = cardFor(i);
      const cardText = [c.words, c.time, c.oneTrip, c.guidance, c.handoff?.text].flatMap((x) => (x ? [x.ko, x.en] : [])).join('\n');
      const kit = buildChannels(messagePlan(i, null), { nowIso: '2026-11-12T10:00:00Z' });
      const kitText = (['ko', 'en'] as const).flatMap((l) => [kit.text[l].head.script, kit.text[l].voice, kit.text[l].familyText, ...kit.text[l].familyScript]).join('\n');
      for (const f of forms) {
        // T and L can share a spoken form only if they are equal, which a gap excludes
        expect(cardText.includes(f), `${i.origin.id} card ${f}`).toBe(false);
        expect(kitText.includes(f), `${i.origin.id} kit ${f}`).toBe(false);
      }
    }
    expect(n).toBe(53);
  });

  it('urgency: places without a leave-by time (partial) sort above every timed checked place, never at the bottom', () => {
    const items = cases.filter((c) => c.op?.bestVerdict === 'checked_route').map((c) => ({ id: `${c.set}:${c.i.origin.id}`, name: c.i.origin.id, vulnerable: false, plan: c.op!, kind: deadlineHeadline(c.op).kind }));
    const sorted = [...items].sort(compareUrgency);
    const lastPartial = sorted.map((x) => x.kind).lastIndexOf('partial');
    const firstTimed = sorted.map((x) => x.kind).indexOf('deadline');
    expect(lastPartial).toBeGreaterThanOrEqual(0);
    expect(lastPartial).toBeLessThan(firstTimed);
  });

  it('real set: nothing a staff member sees changes except the renamed CSV column (now empty where it repeated the deadline); explanations still match', () => {
    let checked = 0;
    for (const { set, op } of cases) {
      if (set !== 'real' || op?.bestVerdict !== 'checked_route') continue;
      checked += 1;
      const h = deadlineHeadline(op);
      expect(h).toEqual({ kind: 'deadline', deadlineS: op.latestSafeDepartureS, laterWindowS: null }); // T = L: headline, A4, CSV deadline, default selection, explanation match unchanged
      expect(op.contiguousSafeDepartureS).toBe(op.latestSafeDepartureS); // the old second CSV column repeated it
    }
    expect(checked).toBe(501);
  });

  it('in every real and synthetic case; counts of cases whose staff time changes', () => {
    const changed = { real: 0, syn: 0 };
    const changedBy = { gap: 0, partial: 0 };
    const kinds: Record<string, number> = {};
    for (const [set, xs] of [['real', real], ['syn', syn]] as const) {
      for (const i of xs) {
        const h = deadlineHeadline(i.plan);
        const p = messagePlan(i, null);
        const kit = p.kind === 'leave_by' ? p.leaveByS : null;
        const card = cardFor(i);
        kinds[`${set}:${h.kind}:${p.kind}`] = (kinds[`${set}:${h.kind}:${p.kind}`] ?? 0) + 1;
        expect(h.deadlineS, i.origin.id).toBe(kit);
        expect(card.time !== null, i.origin.id).toBe(kit !== null);
        expect(headlineDepartureS(i.plan)).toBe(kit);
        // the later window is never the headline, and only appears after the headline time (or with no headline)
        if (h.laterWindowS !== null) {
          expect(h.laterWindowS).toBe(i.plan!.latestSafeDepartureS);
          if (h.deadlineS !== null) expect(h.laterWindowS).toBeGreaterThan(h.deadlineS);
        }
        // no headline time is ever shown for a place the kit gives no time (partial, no-route, unresolved)
        if (kit === null) expect(h.deadlineS).toBeNull();
        // what the staff headline was before this change: the latest checked departure
        const before = i.plan && i.plan.bestVerdict === 'checked_route' ? i.plan.latestSafeDepartureS : null;
        if (before !== h.deadlineS) {
          changed[set] += 1;
          if (set === 'syn') changedBy[h.kind === 'partial' ? 'partial' : 'gap'] += 1;
          // every change is one of the two known causes: a later window after a gap, or no contiguous time at all
          expect(h.kind === 'partial' || (h.kind === 'deadline' && h.laterWindowS !== null), i.origin.id).toBe(true);
        }
      }
    }
    console.log('[staff headline] cases whose staff time changed (real / synthetic):', JSON.stringify(changed), JSON.stringify(kinds));
    expect(changed.real).toBe(0);
    // pinned (Owen note 1 on #137): 131 synthetic cases change = 53 gap + 78 partial; the generator is seeded
    expect(changed.syn).toBe(131);
    expect(changedBy).toEqual({ gap: 53, partial: 78 });
  });
});

describe('fail closed', () => {
  it('a contiguous time the sweep contradicts gives no headline time (partial), never the recorded number', () => {
    const plan = {
      bestVerdict: 'checked_route' as const,
      latestSafeDepartureS: 1200,
      contiguousSafeDepartureS: 600,
      sweep: [
        { offsetS: 0, verdict: 'checked_route' },
        { offsetS: 600, verdict: 'unresolved' },
        { offsetS: 1200, verdict: 'checked_route' },
      ],
    };
    expect(deadlineHeadline(plan)).toEqual({ kind: 'partial', deadlineS: null, laterWindowS: 1200 });
    expect(deadlineHeadline({ ...plan, contiguousSafeDepartureS: 0 })).toEqual({ kind: 'deadline', deadlineS: 0, laterWindowS: 1200 });
    // a window-closed cell is not a requested departure
    expect(deadlineHeadline({ ...plan, contiguousSafeDepartureS: 600, sweep: [{ offsetS: 0, verdict: 'checked_route' }, { offsetS: 600, verdict: 'checked_route' }, { offsetS: 900, verdict: 'window_closed' }, { offsetS: 1200, verdict: 'checked_route' }] })).toEqual({ kind: 'deadline', deadlineS: 600, laterWindowS: 1200 });
    expect(deadlineHeadline({ ...plan, contiguousSafeDepartureS: 1500 })).toEqual({ kind: 'partial', deadlineS: null, laterWindowS: 1200 });
  });
});
