/**
 * Loads the six booth caches (planner/cache/<region>/<input>.json, schema wfg.planner.cache/1) the
 * way the app does — src/api/cache.ts cacheToModel, the places file through src/data/staticData.ts,
 * every origin of the scenario completed with an unresolved plan when it has no result (as the
 * controller's completePlans does) — and turns them into last-mile inputs. One file at a time,
 * so only one parsed cache document is alive at once.
 */
import { readFileSync } from 'node:fs';
import { cacheToModel, parseCacheIndex } from '../../planner/src/api/cache';
import { parsePlaces, parseRegionIndex, scenarioOrigins } from '../../planner/src/data/staticData';
import { unresolvedPlan } from '../../planner/src/domain/plan';
import type { CacheEntry, OriginPlan } from '../../planner/src/domain/types';
import { buildLastMileInputs } from '../../planner/src/features/lastmile/input';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import type { ExplanationFile, LastMileInput } from '../../planner/src/features/lastmile/types';

const PLANNER = new URL('../../planner/', import.meta.url);

export const FIXED_GENERATED_AT = '2026-11-02T05:00:00Z';

export interface BoothCache {
  entry: CacheEntry;
  inputs: LastMileInput[];
  /** origins with a result in the cache file itself */
  cachedOrigins: number;
}

export function loadBoothCaches(): BoothCache[] {
  const index = parseCacheIndex(JSON.parse(readFileSync(new URL('cache/INDEX.json', PLANNER), 'utf8')));
  const regions = parseRegionIndex(JSON.parse(readFileSync(new URL('public/data/regions/index.json', PLANNER), 'utf8')));
  const out: BoothCache[] = [];
  for (const entry of index) {
    const region = regions.find((r) => r.id === entry.regionId);
    if (!region) throw new Error(`region ${entry.regionId} missing from public/data/regions/index.json`);
    let doc: unknown = JSON.parse(readFileSync(new URL(`cache/${entry.path}`, PLANNER), 'utf8'));
    const model = cacheToModel(doc as Parameters<typeof cacheToModel>[0], entry);
    doc = null;
    const places = parsePlaces(JSON.parse(readFileSync(new URL(`public/data/regions/${entry.regionId}/places.geojson`, PLANNER), 'utf8')));
    const plans: Record<string, OriginPlan> = { ...model.plans };
    const cachedOrigins = Object.keys(model.plans).length;
    for (const o of scenarioOrigins(places, entry.scenarioSetId)) {
      if (!plans[o.id]) plans[o.id] = unresolvedPlan(o.id, model.offsetsS, o.checkable ? 'not_computed' : 'not_checkable', 'cache', model.meta.mock);
    }
    const inputs = buildLastMileInputs({
      region: { id: region.id, nameKo: region.nameKo, nameEn: region.nameEn, fireYear: region.fireYear },
      scenario: { scenarioSetId: entry.scenarioSetId, inputTimeIso: entry.inputTime, horizonS: model.horizonS ?? 3600 },
      places,
      plans,
      mock: model.meta.mock,
      testData: model.meta.testData,
      source: 'cache',
      cacheCreatedAtIso: model.meta.createdAt,
      generatedAtIso: FIXED_GENERATED_AT,
    });
    out.push({ entry, inputs, cachedOrigins });
  }
  return out;
}

/** A made-up road name exactly as long as the reader accepts (MAX_LABEL_CHARS = 40) in both languages. Tests only. */
export const SYNTHETIC_ROAD = { ko: '합성 시험용 아주 긴 이름의 지방도로 구간 (최대 마흔 글자 길이 시험)', en: 'Synthetic test road with a 40-char label' };

/**
 * A SYNTHETIC `wfg.explanation/1` file for one booth cache, shaped by the contract and built from
 * the planner's own deadlines: every leave-by origin whose next departure is a recorded "no route"
 * gets a flame-on-route reason on SYNTHETIC_ROAD, every model_no_route origin four blocked exits,
 * the rest `not_explainable`. Made-up flame times — for testing the reader and the length budgets
 * only; it never leaves the tests. `shift` moves every deadline (a file that disagrees).
 */
export function syntheticExplanationFor(cache: BoothCache, shift = 0): ExplanationFile {
  const origins: Record<string, unknown> = {};
  for (const input of cache.inputs) {
    const p = messagePlan(input, null);
    const item = (flame: number, pass: number | null) => ({
      edge_id: 'synthetic:edge',
      label_ko: SYNTHETIC_ROAD.ko,
      label_en: SYNTHETIC_ROAD.en,
      label_source: 'osm_name',
      flame_time_s: flame,
      members: [0, 1, 2],
      members_total: 4,
      pass_time_at_deadline_s: pass,
      slack_s: pass === null ? null : flame - pass,
    });
    if (p.kind === 'leave_by' && p.nextVerdict === 'model_no_route' && p.leaveByS !== null && p.nextOffsetS !== null) {
      origins[input.origin.id] = {
        status: 'explained',
        verdict_summary: 'checked_route',
        deadline_offset_s: p.leaveByS + shift,
        next_offset_s: p.nextOffsetS,
        next_verdict: 'model_no_route',
        reason_code: 'flame_on_route',
        binding: [item(p.nextOffsetS + 300, p.leaveByS + 300)],
        exits: [],
        notes: [],
      };
    } else if (p.kind === 'no_route') {
      origins[input.origin.id] = {
        status: 'explained',
        verdict_summary: 'model_no_route',
        deadline_offset_s: null,
        next_offset_s: null,
        next_verdict: null,
        reason_code: 'all_exits_blocked',
        binding: [],
        exits: [1, 2, 3, 4].map((i) => ({ ...item(600 * i, null), edge_id: `synthetic:exit:${i}` })),
        notes: [],
      };
    } else {
      origins[input.origin.id] = {
        status: 'not_explainable',
        verdict_summary: input.plan?.bestVerdict ?? 'unresolved',
        deadline_offset_s: null,
        next_offset_s: null,
        next_verdict: null,
        reason_code: 'other',
        binding: [],
        exits: [],
        notes: [],
      };
    }
  }
  return {
    schema: 'wfg.explanation/1',
    region_id: cache.entry.regionId,
    input_time: cache.entry.inputTime,
    scenario_set_id: cache.entry.scenarioSetId,
    provenance: { synthetic: true },
    summary: {},
    origins: origins as ExplanationFile['origins'],
  };
}
