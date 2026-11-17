/**
 * Replay packs: planner caches (schema wfg.planner.cache/1) written OUTSIDE the Route-Check API by a
 * research replay, shown as their own scenario next to the recorded booth results.
 *
 * vite.config.ts copies every `available` pack from `source` (relative to planner/) to
 * `<base>cache/packs/<id>/` (dev and preview serve it from there too), and
 * scripts/check_static_dist.mjs checks every shipped file's bytes and SHA-256 against the pack's
 * own INDEX.json. A `pending` pack is listed in the app as "not yet computed", has no data and is
 * never shipped.
 *
 * Plain data on purpose: vite.config.ts imports this file at build time.
 *
 * HOOK for the MEASURED arms (research/kcf-margin R(h) put through research/kcf-replay/replay.py):
 * when their planner cache lands (research/kcf-replay/make_planner_cache.py --standin <LABEL>),
 *   1. set `source` to that folder, `scenarioPrefix` to its scenario_set_id prefix and
 *      `status` to 'available';
 *   2. write its six-place file: node scripts/build_replay_named_places.mjs --standin <LABEL> --horizon 8h;
 *   3. set `namedPlaces` to that file.
 * Nothing else in the app changes: the pack is picked up by the scenario selector, the hour
 * slider and the six-place panel.
 */
export type ReplayPackStatus = 'available' | 'pending';

export interface ReplayPack {
  id: string;
  status: ReplayPackStatus;
  /** pack folder relative to planner/ (null while pending) */
  source: string | null;
  /** every scenario_set_id of the pack starts with this */
  scenarioPrefix: string;
  /** R(h) label used by the replay (HOTSPOT_RULE.md / kcf-margin) */
  standin: string;
  horizon: '5h' | '8h';
  /** R(h) as shown to the reader; null while pending */
  rate: string | null;
  /** six-place timeline under the app base (null while pending) */
  namedPlaces: string | null;
  /** where the numbers are explained (repository path) */
  results: string;
}

export const REPLAY_PACKS: readonly ReplayPack[] = [
  {
    id: 'kcf-replay-RUNNING_8h',
    status: 'available',
    source: '../research/kcf-replay/planner_cache/RUNNING_8h',
    scenarioPrefix: 'kcf-replay:RUNNING:8h:',
    standin: 'RUNNING',
    horizon: '8h',
    rate: '8.2 km/h',
    namedPlaces: 'data/replay/kcf-replay-RUNNING_8h.named_places.json',
    results: 'research/kcf-replay/RESULTS.md',
  },
  {
    // research/kcf-margin (MEASURED R(h)) has landed; the replay re-run with it has not:
    // no planner cache for a MEASURED arm exists in research/kcf-replay/planner_cache.
    id: 'kcf-replay-MEASURED',
    status: 'pending',
    source: null,
    scenarioPrefix: 'kcf-replay:MEASURED',
    standin: 'MEASURED',
    horizon: '8h',
    rate: null,
    namedPlaces: null,
    results: 'research/kcf-margin/RESULTS.md',
  },
];

/** Folder of a pack under the cache base ("packs/<id>"). */
export function packCacheDir(id: string): string {
  return `packs/${id}`;
}

export function availablePacks(packs: readonly ReplayPack[] = REPLAY_PACKS): ReplayPack[] {
  return packs.filter((p) => p.status === 'available' && p.source);
}

/** The pack a scenario set id belongs to (by prefix), or null for recorded booth results. */
export function packOfScenario(scenarioSetId: string | null | undefined, packs: readonly ReplayPack[] = REPLAY_PACKS): ReplayPack | null {
  if (!scenarioSetId) return null;
  return packs.find((p) => scenarioSetId.startsWith(p.scenarioPrefix)) ?? null;
}
