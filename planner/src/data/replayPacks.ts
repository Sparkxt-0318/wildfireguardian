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
 * To add another arm (a new R(h) put through research/kcf-replay/replay.py):
 *   1. write its planner cache: make_planner_cache.py out/runs planner_cache/<LABEL>_8h --standin <LABEL> --horizon 8h;
 *   2. write its six-place file: node scripts/build_replay_named_places.mjs --standin <LABEL> --horizon 8h;
 *   3. add an entry here (status 'available', its `source`, exact `scenarioPrefix` and `namedPlaces`) and the
 *      button label `replay.pack.<id>` in features/replay/strings.ts.
 * Nothing else in the app changes: the pack is picked up by the scenario selector, the hour
 * slider and the six-place panel. A `pending` entry is listed disabled with a note.
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
  /** shown as PROVISIONAL wherever the pack is named (MEASURED+GUST: ERA5 gusts only) */
  provisional?: boolean;
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
    // research/kcf-replay MEASURED arm (MEASURED_RULE.md): kcf-margin R(h) by the prior-3 h spread class, one class per
    // issue hour; planner cache from replay.py --standins MEASURED + make_planner_cache.py --standin MEASURED --horizon 8h
    id: 'kcf-replay-MEASURED_8h',
    status: 'available',
    source: '../research/kcf-replay/planner_cache/MEASURED_8h',
    scenarioPrefix: 'kcf-replay:MEASURED:8h:',
    standin: 'MEASURED',
    horizon: '8h',
    rate: 'R(8 h) quiet 3.5 / slow 6.4 / running 10.0 km',
    namedPlaces: 'data/replay/kcf-replay-MEASURED_8h.named_places.json',
    results: 'research/kcf-replay/RESULTS.md §2b',
  },
  {
    // MEASURED+GUST arm: R(h) by the max ERA5 gust over (T, T+H]; PROVISIONAL (ERA5 only, >= 20 m/s class rests on 9 fires)
    id: 'kcf-replay-MEASURED_GUST_8h',
    status: 'available',
    source: '../research/kcf-replay/planner_cache/MEASURED_GUST_8h',
    scenarioPrefix: 'kcf-replay:MEASURED_GUST:8h:',
    standin: 'MEASURED_GUST',
    horizon: '8h',
    rate: 'R(8 h) gust <10 m/s 3.0 / 10–20 m/s 5.9 / ≥20 m/s 12.0 km',
    namedPlaces: 'data/replay/kcf-replay-MEASURED_GUST_8h.named_places.json',
    results: 'research/kcf-replay/RESULTS.md §2b',
    provisional: true,
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
