/**
 * Iris E (approved by the orchestrator): the staff headline time is the time residents get. Over every origin of the
 * six booth caches and the 600 synthetic cases: the planner's staff headline (deadlineHeadline, used by the right panel,
 * the origin list, the timeline ticks, the default selected departure, the A4 sheet row and the CSV deadline column)
 * equals the kit's leave-by time (messagePlan) and the public card shows a time exactly when they do. A later checked
 * departure after a gap is only ever a labelled window, never the headline.
 */
import { beforeAll, describe, expect, it } from 'vitest';
import { deadlineHeadline, headlineDepartureS } from '../../planner/src/domain/plan';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import { cardFor } from '../../planner/src/features/publicview/model';
import type { LastMileInput } from '../../planner/src/features/lastmile/types';
import { loadBoothCaches } from './lastmile.cachedata';
import { generateCases } from './lastmile.generator';

let real: LastMileInput[] = [];
let syn: LastMileInput[] = [];
beforeAll(() => {
  real = loadBoothCaches().flatMap((c) => c.inputs);
  syn = generateCases(20261102, 600).map((g) => g.input);
}, 300_000);

describe('staff headline == resident card time == kit time', () => {
  it('in every real and synthetic case; counts of cases whose staff time changes', () => {
    const changed = { real: 0, syn: 0 };
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
        if (before !== h.deadlineS) changed[set] += 1;
      }
    }
    console.log('[staff headline] cases whose staff time changed (real / synthetic):', JSON.stringify(changed), JSON.stringify(kinds));
    expect(changed.real).toBe(0);
    expect(changed.syn).toBeGreaterThan(0);
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
