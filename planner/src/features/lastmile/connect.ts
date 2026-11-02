/**
 * The ONLY store-aware file of the last-mile module (the other files are pure or presentational):
 * reads the planner store and hands plain inputs to ./input.ts. Field messages are built only
 * for a recorded scenario with results; user-drawn spread zones (an assumption) are refused.
 */
import { useMemo } from 'react';
import { currentScenarioSet, horizonOf, isMockActive, regionEntry } from '../../state/selectors';
import { DRAWN_SCENARIO, getState, useStore, type PlannerState } from '../../state/store';
import { buildLastMileInputs, isFieldOrigin, type LastMileBuildArgs } from './input';
import type { LastMileInput } from './types';

export type LastMileAvailability = { ok: true; args: LastMileBuildArgs } | { ok: false; reason: 'drawn' | 'no_scenario' | 'no_data' };

export function lastMileArgs(s: PlannerState, now: Date = new Date()): LastMileAvailability {
  if (s.scenarioId === DRAWN_SCENARIO) return { ok: false, reason: 'drawn' };
  const region = regionEntry(s);
  const set = currentScenarioSet(s);
  if (!region || !set) return { ok: false, reason: 'no_scenario' };
  if (s.dataSource === 'none' || Object.keys(s.plans).length === 0) return { ok: false, reason: 'no_data' };
  return {
    ok: true,
    args: {
      region: { id: region.id, nameKo: region.nameKo, nameEn: region.nameEn, fireYear: region.fireYear },
      scenario: { scenarioSetId: set.id, inputTimeIso: set.inputTime, horizonS: horizonOf(s) },
      places: s.places,
      plans: s.plans,
      mock: isMockActive(s),
      testData: s.dataSource === 'cache' && s.cache?.meta.testData === true,
      source: s.dataSource === 'cache' ? 'cache' : 'live',
      cacheCreatedAtIso: s.dataSource === 'cache' ? (s.cache?.meta.createdAt ?? null) : null,
      generatedAtIso: now.toISOString(),
    },
  };
}

export type UnavailableReason = 'drawn' | 'no_scenario' | 'no_data';

/** Availability for the right-panel entry (cheap: no inputs are built). */
export function useLastMileAvailability(): { ok: boolean; reason: UnavailableReason | null } {
  const scenarioId = useStore((s) => s.scenarioId);
  const plans = useStore((s) => s.plans);
  const dataSource = useStore((s) => s.dataSource);
  const regionId = useStore((s) => s.regionId);
  return useMemo(() => {
    const a = lastMileArgs(getState());
    return a.ok ? { ok: true, reason: null } : { ok: false, reason: a.reason };
  }, [scenarioId, plans, dataSource, regionId]);
}

/** All inputs of the scenario on screen (built only while `active`). */
export function useLastMileInputs(active: boolean): { inputs: LastMileInput[]; args: LastMileBuildArgs | null; reason: UnavailableReason | null } {
  const scenarioId = useStore((s) => s.scenarioId);
  const plans = useStore((s) => s.plans);
  const places = useStore((s) => s.places);
  const cache = useStore((s) => s.cache);
  const dataSource = useStore((s) => s.dataSource);
  const regionId = useStore((s) => s.regionId);
  return useMemo(() => {
    if (!active) return { inputs: [], args: null, reason: null };
    const a = lastMileArgs(getState());
    if (!a.ok) return { inputs: [], args: null, reason: a.reason };
    return { inputs: buildLastMileInputs(a.args), args: a.args, reason: null };
  }, [active, scenarioId, plans, places, cache, dataSource, regionId]);
}

/** The selected origin is a research origin (no field messages are made for it). */
export function useIsResearchOrigin(originId: string): boolean {
  return useStore((s) => {
    const p = s.places.find((x) => x.id === originId);
    return p ? !isFieldOrigin(p) : false;
  });
}
