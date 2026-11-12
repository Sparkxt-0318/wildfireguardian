/**
 * Loads the committed replay caches the way the planner does (src/api/cache.ts, src/data/staticData.ts) and turns one
 * scenario into last-mile inputs. Only the page's own static files are read (the same-origin fetch guard is installed
 * by the entry point). Every scenario origin without a cached result gets an unresolved plan (never safe).
 */
import { loadCacheFile, loadCacheIndex } from '../../api/cache';
import { loadPlaces, loadRegionIndex, scenarioOrigins } from '../../data/staticData';
import { unresolvedPlan } from '../../domain/plan';
import type { CacheEntry, OriginPlan, Place } from '../../domain/types';
import { buildLastMileInputs } from '../lastmile/input';
import type { LastMileInput } from '../lastmile/types';

export interface ReplayScenario {
  entry: CacheEntry;
  inputs: LastMileInput[];
  places: Place[];
}

export async function loadEntries(signal?: AbortSignal): Promise<CacheEntry[]> {
  return loadCacheIndex(signal);
}

export async function loadScenario(entry: CacheEntry, signal?: AbortSignal): Promise<ReplayScenario> {
  const [regions, places, model] = await Promise.all([loadRegionIndex(signal), loadPlaces(entry.regionId, signal), loadCacheFile(entry, signal)]);
  const region = regions.find((r) => r.id === entry.regionId);
  if (!region) throw new Error(`unknown region ${entry.regionId}`);
  const plans: Record<string, OriginPlan> = { ...model.plans };
  for (const o of scenarioOrigins(places, entry.scenarioSetId)) {
    if (!plans[o.id]) plans[o.id] = unresolvedPlan(o.id, model.offsetsS, o.checkable ? 'not_computed' : 'not_checkable', 'cache', model.meta.mock);
  }
  const inputs = buildLastMileInputs({
    region: { id: region.id, nameKo: region.nameKo, nameEn: region.nameEn, fireYear: region.fireYear },
    scenario: { scenarioSetId: entry.scenarioSetId, inputTimeIso: entry.inputTime, horizonS: model.horizonS ?? 3600 },
    places,
    plans,
    mock: model.meta.mock,
    cache: { path: entry.path, createdAtIso: model.meta.createdAt || null, testData: model.meta.testData },
    liveHosts: {},
    source: 'cache',
    generatedAtIso: new Date().toISOString(),
  });
  return { entry, inputs, places };
}

/** Destination coordinates by place id (for the hand-off). */
export function coordsOf(places: Place[]): (id: string) => { lat: number; lon: number } | null {
  const by = new Map(places.map((p) => [p.id, p]));
  return (id) => {
    const p = by.get(id);
    return p ? { lat: p.lat, lon: p.lon } : null;
  };
}

/** Saved places (origin ids) live only in this browser; every access is guarded and the page works without it. */
const KEY = 'wfg.publicview.saved.v1';
export function readSaved(): string[] {
  try {
    const raw = globalThis.localStorage?.getItem(KEY);
    const v = raw ? JSON.parse(raw) : [];
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}
export function writeSaved(ids: string[]): void {
  try {
    globalThis.localStorage?.setItem(KEY, JSON.stringify([...new Set(ids)]));
  } catch {
    /* storage unavailable: the list lasts for this visit only */
  }
}
