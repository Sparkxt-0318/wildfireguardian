/**
 * Derived data (pure functions of the state) and memoised hooks for components.
 */
import { useMemo } from 'react';
import { CONFIG } from '../config/env';
import { mockActive } from '../domain/labels';
import { RECORDED_HORIZON_S } from '../domain/plan';
import type { FireInput, OriginPlan, Place, RegionIndexEntry, RouteDetail, ScenarioSet } from '../domain/types';
import {
  fingerprint,
  hasAnyZone,
  issuedAtFor,
  rsgTags,
  validateZones,
  zonesFeatureCollection,
  type BBox,
  type RsgTag,
  type ZoneIssue,
} from '../domain/zones';
import { scenarioDestinations, scenarioOrigins, scenarioSetsFromPlaces } from '../data/staticData';
import { DRAWN_SCENARIO, useStore, type PlannerState } from './store';

export function regionEntry(s: Pick<PlannerState, 'regionIndex' | 'regionId'>): RegionIndexEntry | null {
  return s.regionIndex.find((r) => r.id === s.regionId) ?? null;
}

/** Recorded scenario sets of the region: API ∪ cache ∪ research places (API data wins). */
export function scenarioSetsOf(s: Pick<PlannerState, 'apiRegions' | 'cacheIndex' | 'places' | 'regionId'>): ScenarioSet[] {
  if (!s.regionId) return [];
  const out = new Map<string, ScenarioSet>();
  for (const set of s.apiRegions[s.regionId]?.scenarioSets ?? []) out.set(set.id, set);
  for (const e of s.cacheIndex) {
    if (e.regionId !== s.regionId || out.has(e.scenarioSetId)) continue;
    out.set(e.scenarioSetId, { id: e.scenarioSetId, inputTime: e.inputTime, scenarioIds: [], horizonS: null, hazardSha256: null, source: 'cache' });
  }
  for (const set of scenarioSetsFromPlaces(s.places)) if (!out.has(set.id)) out.set(set.id, set);
  return [...out.values()].sort((a, b) => a.inputTime.localeCompare(b.inputTime));
}

export function currentScenarioSet(s: PlannerState): ScenarioSet | null {
  if (!s.scenarioId || s.scenarioId === DRAWN_SCENARIO) return null;
  return scenarioSetsOf(s).find((x) => x.id === s.scenarioId) ?? null;
}

/** Scenario horizon: API → cache → recorded research mission → the fixed recorded window (3600 s). */
export function horizonOf(s: PlannerState): number {
  if (s.scenarioId === DRAWN_SCENARIO) return drawnHorizonS(s);
  const set = currentScenarioSet(s);
  if (set?.horizonS) return set.horizonS;
  if (s.cache?.horizonS) return s.cache.horizonS;
  const research = s.places.find((p) => p.role === 'research_origin' && p.scenarioSetId === s.scenarioId && p.recorded?.horizonS);
  return research?.recorded?.horizonS ?? RECORDED_HORIZON_S;
}

export function fireInputOf(s: PlannerState): FireInput | { type: 'spread_zones' } | null {
  if (s.scenarioId === DRAWN_SCENARIO) return drawnFireInput(s) ?? { type: 'spread_zones' };
  const set = currentScenarioSet(s);
  return set ? { type: 'recorded', scenarioSetId: set.id, inputTime: set.inputTime } : null;
}

export function isMockActive(s: PlannerState): boolean {
  const resultsMock =
    Boolean(s.cache?.meta.mock) ||
    Object.values(s.plans).some((p) => p.mock) ||
    Object.values(s.routes).some((r) => r.mock) ||
    Boolean(s.forecast.data?.mock);
  return mockActive({ envMode: CONFIG.apiMode, healthMock: Boolean(s.health?.mock), resultsMock });
}

export function routeById(s: Pick<PlannerState, 'routes' | 'cache'>, jobId: string | null | undefined): RouteDetail | null {
  if (!jobId) return null;
  return s.routes[jobId] ?? s.cache?.route(jobId) ?? null;
}

/**
 * The travel-time-only comparison of an origin, only while it belongs to the origin's current
 * best checked attempt (a late response of another scenario, fire input or recompute never shows).
 */
export function travelOnlyDetail(
  s: Pick<PlannerState, 'travelOnly' | 'plans'>,
  originId: string | null | undefined,
): RouteDetail | null {
  if (!originId) return null;
  const st = s.travelOnly[originId];
  if (!st || st.state !== 'ready' || !st.detail) return null;
  return st.forJobId !== null && st.forJobId === (s.plans[originId]?.best?.jobId ?? null) ? st.detail : null;
}

// ---------------------------------------------------------------- drawn spread zones

export function isDrawnMode(s: Pick<PlannerState, 'scenarioId'>): boolean {
  return s.scenarioId === DRAWN_SCENARIO;
}

/** The region's RECORDED input times (contract: spread_zones input_time must be one of them). */
export function recordedInputTimes(s: Pick<PlannerState, 'apiRegions' | 'cacheIndex' | 'places' | 'regionId'>): string[] {
  const out = new Set<string>(s.regionId ? s.apiRegions[s.regionId]?.inputTimes ?? [] : []);
  for (const set of scenarioSetsOf(s)) out.add(set.inputTime);
  return [...out].sort();
}

/** Recorded scenario set at the drawn base input time (burning_scenario_set_id consistency check). */
export function drawnBaseSet(s: Pick<PlannerState, 'apiRegions' | 'cacheIndex' | 'places' | 'regionId' | 'drawn'>): ScenarioSet | null {
  const it = s.drawn.settings.inputTime;
  return it ? scenarioSetsOf(s).find((x) => x.inputTime === it) ?? null : null;
}

/** Hazard horizon of spread zones = the recorded window of the base input (contract v1.1: 1 h). */
export function drawnHorizonS(s: Pick<PlannerState, 'apiRegions' | 'cacheIndex' | 'places' | 'regionId' | 'drawn'>): number {
  return drawnBaseSet(s)?.horizonS ?? RECORDED_HORIZON_S;
}

/** Region bbox for zone validation: API region bbox, else the static index bbox. */
export function regionBBox(s: Pick<PlannerState, 'apiRegions' | 'regionIndex' | 'regionId'>): BBox | null {
  if (!s.regionId) return null;
  const api = s.apiRegions[s.regionId]?.bbox;
  if (api && api.length === 4) return [api[0], api[1], api[2], api[3]];
  return regionEntry(s)?.bbox ?? null;
}

export function zoneIssues(s: Pick<PlannerState, 'apiRegions' | 'regionIndex' | 'regionId' | 'drawn'>): ZoneIssue[] {
  return validateZones(s.drawn.zones, regionBBox(s));
}

export function drawnIssuedAt(s: Pick<PlannerState, 'drawn'>): string | null {
  const it = s.drawn.settings.inputTime;
  return it ? issuedAtFor(it, s.drawn.settings.issueOffsetH) : null;
}

/**
 * The spread_zones fire input of the zones on screen (null when there is no base input time or no
 * zone). Validity is checked separately (drawnReadiness) so an invalid zone is never sent.
 */
export function drawnFireInput(s: Pick<PlannerState, 'apiRegions' | 'cacheIndex' | 'places' | 'regionId' | 'drawn'>): Extract<FireInput, { type: 'spread_zones' }> | null {
  const d = s.drawn;
  const inputTime = d.settings.inputTime;
  if (!inputTime || !hasAnyZone(d.zones)) return null;
  return {
    type: 'spread_zones',
    issuedAt: issuedAtFor(inputTime, d.settings.issueOffsetH),
    inputTime,
    zones: zonesFeatureCollection(d.zones),
    marginMin: d.settings.marginMin,
    burningScenarioSetId: drawnBaseSet(s)?.id ?? null,
  };
}

/** Fingerprint of region + fire input; drawn results are shown only while it matches. */
export function drawnFireKey(s: Pick<PlannerState, 'apiRegions' | 'cacheIndex' | 'places' | 'regionId' | 'drawn'>): string | null {
  const fi = drawnFireInput(s);
  return fi ? fingerprint({ region: s.regionId, ...fi }) : null;
}

export type DrawnProblem = 'no_input_time' | 'no_zone' | 'invalid_zone' | 'outside_region' | 'api_offline';

/** Whether the zones can be sent (never send an invalid zone; the API would answer 422 INVALID_ZONES). */
export function drawnReadiness(s: PlannerState): { ok: boolean; problems: DrawnProblem[] } {
  const problems: DrawnProblem[] = [];
  if (!s.drawn.settings.inputTime) problems.push('no_input_time');
  if (!hasAnyZone(s.drawn.zones)) problems.push('no_zone');
  const issues = zoneIssues(s).filter((i) => i.severity === 'error');
  if (issues.some((i) => i.code === 'outside_region')) problems.push('outside_region');
  if (issues.some((i) => i.code !== 'outside_region')) problems.push('invalid_zone');
  if (s.apiStatus !== 'online') problems.push('api_offline');
  return { ok: problems.length === 0, problems };
}

// ---------------------------------------------------------------- hooks

export function useRegionEntry(): RegionIndexEntry | null {
  const regionIndex = useStore((s) => s.regionIndex);
  const regionId = useStore((s) => s.regionId);
  return useMemo(() => regionEntry({ regionIndex, regionId }), [regionIndex, regionId]);
}

export function useScenarioSets(): ScenarioSet[] {
  const apiRegions = useStore((s) => s.apiRegions);
  const cacheIndex = useStore((s) => s.cacheIndex);
  const places = useStore((s) => s.places);
  const regionId = useStore((s) => s.regionId);
  return useMemo(() => scenarioSetsOf({ apiRegions, cacheIndex, places, regionId }), [apiRegions, cacheIndex, places, regionId]);
}

export function useCurrentScenarioSet(): ScenarioSet | null {
  const sets = useScenarioSets();
  const scenarioId = useStore((s) => s.scenarioId);
  return useMemo(() => sets.find((x) => x.id === scenarioId) ?? null, [sets, scenarioId]);
}

export function useHorizon(): number {
  const set = useCurrentScenarioSet();
  const cacheHorizon = useStore((s) => s.cache?.horizonS ?? null);
  const places = useStore((s) => s.places);
  const scenarioId = useStore((s) => s.scenarioId);
  const drawnBase = useDrawnBaseSet();
  return useMemo(() => {
    if (scenarioId === DRAWN_SCENARIO) return drawnBase?.horizonS ?? RECORDED_HORIZON_S;
    if (set?.horizonS) return set.horizonS;
    if (cacheHorizon) return cacheHorizon;
    const research = places.find((p) => p.role === 'research_origin' && p.scenarioSetId === scenarioId && p.recorded?.horizonS);
    return research?.recorded?.horizonS ?? RECORDED_HORIZON_S;
  }, [set, cacheHorizon, places, scenarioId, drawnBase]);
}

export function useIsDrawn(): boolean {
  return useStore((s) => s.scenarioId === DRAWN_SCENARIO);
}

export function useRecordedInputTimes(): string[] {
  const apiRegions = useStore((s) => s.apiRegions);
  const cacheIndex = useStore((s) => s.cacheIndex);
  const places = useStore((s) => s.places);
  const regionId = useStore((s) => s.regionId);
  return useMemo(() => recordedInputTimes({ apiRegions, cacheIndex, places, regionId }), [apiRegions, cacheIndex, places, regionId]);
}

export function useDrawnBaseSet(): ScenarioSet | null {
  const sets = useScenarioSets();
  const it = useStore((s) => s.drawn.settings.inputTime);
  return useMemo(() => (it ? sets.find((x) => x.inputTime === it) ?? null : null), [sets, it]);
}

/**
 * Clock of the shown results: wall time = input time + offset (the API's journey clock). In drawn
 * mode `issuedAt` is also set, for the relative "T+h:mm" after the zone forecast's issue time.
 */
export function useClockBase(): { inputTime: string | null; issuedAt: string | null } {
  const set = useCurrentScenarioSet();
  const drawn = useIsDrawn();
  const it = useStore((s) => s.drawn.settings.inputTime);
  const off = useStore((s) => s.drawn.settings.issueOffsetH);
  return useMemo(() => {
    if (drawn) return { inputTime: it, issuedAt: it ? issuedAtFor(it, off) : null };
    return { inputTime: set?.inputTime ?? null, issuedAt: null };
  }, [drawn, it, off, set]);
}

export function useZoneIssues(): ZoneIssue[] {
  const zones = useStore((s) => s.drawn.zones);
  const apiRegions = useStore((s) => s.apiRegions);
  const regionIndex = useStore((s) => s.regionIndex);
  const regionId = useStore((s) => s.regionId);
  return useMemo(() => validateZones(zones, regionBBox({ apiRegions, regionIndex, regionId })), [zones, apiRegions, regionIndex, regionId]);
}

/** Ready-Set-Go tags of the drawn-mode origins (planner-side point-in-polygon only). */
export function useRsgTags(): Map<string, RsgTag> {
  const drawn = useIsDrawn();
  const zones = useStore((s) => s.drawn.zones);
  const { origins } = useScenarioPlaces();
  return useMemo(() => (drawn ? rsgTags(origins, zones) : new Map<string, RsgTag>()), [drawn, zones, origins]);
}

export function useDrawnFireKey(): string | null {
  const zones = useStore((s) => s.drawn.zones);
  const settings = useStore((s) => s.drawn.settings);
  const apiRegions = useStore((s) => s.apiRegions);
  const cacheIndex = useStore((s) => s.cacheIndex);
  const places = useStore((s) => s.places);
  const regionId = useStore((s) => s.regionId);
  return useMemo(
    () => drawnFireKey({ apiRegions, cacheIndex, places, regionId, drawn: { zones, settings } as PlannerState['drawn'] }),
    [zones, settings, apiRegions, cacheIndex, places, regionId],
  );
}

export function useScenarioPlaces(): { origins: Place[]; destinations: Place[]; byId: Map<string, Place> } {
  const places = useStore((s) => s.places);
  const scenarioId = useStore((s) => s.scenarioId);
  return useMemo(() => {
    const setId = scenarioId === DRAWN_SCENARIO ? null : scenarioId;
    const origins = scenarioOrigins(places, setId);
    const destinations = scenarioDestinations(places, setId);
    const byId = new Map<string, Place>();
    for (const p of places) byId.set(p.id, p);
    return { origins, destinations, byId };
  }, [places, scenarioId]);
}

export function useMockActive(): boolean {
  const cacheMock = useStore((s) => Boolean(s.cache?.meta.mock));
  const plans = useStore((s) => s.plans);
  const routes = useStore((s) => s.routes);
  const healthMock = useStore((s) => Boolean(s.health?.mock));
  const forecastMock = useStore((s) => Boolean(s.forecast.data?.mock));
  return useMemo(() => {
    const resultsMock = cacheMock || forecastMock || Object.values(plans).some((p) => p.mock) || Object.values(routes).some((r) => r.mock);
    return mockActive({ envMode: CONFIG.apiMode, healthMock, resultsMock });
  }, [cacheMock, plans, routes, healthMock, forecastMock]);
}

export function useSelectedPlace(): Place | null {
  const id = useStore((s) => s.selectedOriginId);
  const places = useStore((s) => s.places);
  return useMemo(() => places.find((p) => p.id === id) ?? null, [places, id]);
}

export function useSelectedPlan(): OriginPlan | null {
  const id = useStore((s) => s.selectedOriginId);
  return useStore((s) => (id ? s.plans[id] ?? null : null));
}

export function useRoute(jobId: string | null | undefined): RouteDetail | null {
  const live = useStore((s) => (jobId ? s.routes[jobId] ?? null : null));
  const cache = useStore((s) => s.cache);
  return useMemo(() => live ?? (jobId && cache ? cache.route(jobId) : null), [live, cache, jobId]);
}

/** The route shown for the selected origin: best checked attempt of the selected departure cell. */
export function useShownAttempt() {
  const plan = useSelectedPlan();
  const offset = useStore((s) => s.selectedOffsetS);
  return useMemo(() => {
    if (!plan) return { cell: null, attempt: null };
    const cell = plan.sweep.find((c) => c.offsetS === offset) ?? null;
    const attempt = cell?.best ?? (offset === null ? plan.best ?? null : null);
    return { cell, attempt };
  }, [plan, offset]);
}
