/**
 * Loads the six booth caches (planner/cache/<region>/<input>.json, schema wfg.planner.cache/1) the
 * way the app does — src/api/cache.ts cacheToModel, the places file through src/data/staticData.ts,
 * every origin of the scenario completed with an unresolved plan when it has no result (as the
 * controller's completePlans does) — and turns them into last-mile inputs. One file at a time,
 * so only one parsed cache document is alive at once.
 */
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { compactUtc } from '../../planner/src/domain/clock';
import { parseExplanationFile } from '../../planner/src/features/lastmile/explanation';
import { cacheToModel, parseCacheIndex } from '../../planner/src/api/cache';
import { parsePlaces, parseRegionIndex, scenarioOrigins } from '../../planner/src/data/staticData';
import { planFromAttempts, unresolvedPlan } from '../../planner/src/domain/plan';
import type { CacheEntry, HostInfo, OriginPlan, RouteDetail } from '../../planner/src/domain/types';
import { buildLastMileInputs, isFieldOrigin, liveHostsOf, type LastMileBuildArgs } from '../../planner/src/features/lastmile/input';
import { messagePlan } from '../../planner/src/features/lastmile/plan';
import type { ExplanationFile, LastMileInput } from '../../planner/src/features/lastmile/types';

const PLANNER = new URL('../../planner/', import.meta.url);

export const FIXED_GENERATED_AT = '2026-11-02T05:00:00Z';

export interface BoothCache {
  entry: CacheEntry;
  inputs: LastMileInput[];
  /** villages and facilities with a result in the cache file itself (research origins get no field messages) */
  cachedOrigins: number;
  /** research origins of the scenario (excluded from the inputs) */
  researchOrigins: number;
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
    const byId = new Map(places.map((p) => [p.id, p]));
    const cachedOrigins = Object.keys(model.plans).filter((id) => {
      const p = byId.get(id);
      return !p || isFieldOrigin(p);
    }).length;
    const researchOrigins = scenarioOrigins(places, entry.scenarioSetId).filter((o) => !isFieldOrigin(o)).length;
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
      generatedAtIso: FIXED_GENERATED_AT,
    });
    out.push({ entry, inputs, cachedOrigins, researchOrigins });
  }
  return out;
}

/**
 * One booth cache as the app holds it in the store (CacheData, places, region entry, index entry),
 * every scenario origin completed with an unresolved plan when it has no result — for tests that
 * drive the store-aware connect.ts with a real cache.
 */
export function loadBoothCacheModel(path: string) {
  const index = parseCacheIndex(JSON.parse(readFileSync(new URL('cache/INDEX.json', PLANNER), 'utf8')));
  const entry = index.find((e) => e.path === path);
  if (!entry) throw new Error(`${path} not in planner/cache/INDEX.json`);
  const region = parseRegionIndex(JSON.parse(readFileSync(new URL('public/data/regions/index.json', PLANNER), 'utf8'))).find((r) => r.id === entry.regionId)!;
  const model = cacheToModel(JSON.parse(readFileSync(new URL(`cache/${entry.path}`, PLANNER), 'utf8')) as Parameters<typeof cacheToModel>[0], entry);
  const places = parsePlaces(JSON.parse(readFileSync(new URL(`public/data/regions/${entry.regionId}/places.geojson`, PLANNER), 'utf8')));
  const plans: Record<string, OriginPlan> = { ...model.plans };
  for (const o of scenarioOrigins(places, entry.scenarioSetId)) {
    if (!plans[o.id]) plans[o.id] = unresolvedPlan(o.id, model.offsetsS, o.checkable ? 'not_computed' : 'not_checkable', 'cache', model.meta.mock);
  }
  return { entry, region, model, places, plans };
}

export type BoothCacheModel = ReturnType<typeof loadBoothCacheModel>;

/**
 * SYNTHETIC provenance: a cached plan "recomputed" through the API — the same attempts under new job
 * ids whose routes report `host` (a function: the host of the n-th departure time; null: routes
 * without provenance). The verdicts stay the cache's; only where they come from changes.
 */
export function reliveOnHost(m: BoothCacheModel, plan: OriginPlan, host: HostInfo | null | ((cell: number) => HostInfo), tag: string): { plan: OriginPlan; routes: Record<string, RouteDetail> } {
  const routes: Record<string, RouteDetail> = {};
  const skipped = Object.fromEntries(plan.sweep.filter((c) => c.skipped).map((c) => [c.offsetS, c.skipped!]));
  const attempts = plan.sweep.flatMap((c, cell) =>
    c.attempts.map((a, k) => {
      const jobId = `${tag}:${plan.originId}:${cell}:${k}`;
      const h = typeof host === 'function' ? host(cell) : host;
      routes[jobId] = { jobId, mock: false, provenance: h ? { host: h } : null } as unknown as RouteDetail;
      return { ...a, jobId };
    }),
  );
  return { plan: planFromAttempts({ originId: plan.originId, offsetsS: m.model.offsetsS, attempts, source: 'live', mock: false, skipped }), routes };
}

/** Origins of a live session that have no API result, by how the controller stores them. */
export interface NoResultOrigins {
  /** not computed yet (completePlans before a batch result arrives) */
  notComputed?: string[];
  /** refused by the API (runDispatchGroups: a rejected origin) */
  rejected?: string[];
  /** every check failed before a job existed (recompute: attempts without a job id) */
  failed?: string[];
}

/**
 * A SYNTHETIC live-only session over a real booth cache — no precomputed cache on screen, the Docker
 * front door's case: every origin the cache computed is "recomputed" on `host` (reliveOnHost); a
 * not-checkable origin is stored as the controller completes a live session (unresolved, source
 * live); the ids in `none` get no API result in the way named there.
 */
export function liveOnlySession(m: BoothCacheModel, host: HostInfo, tag: string, none: NoResultOrigins = {}): { plans: Record<string, OriginPlan>; routes: Record<string, RouteDetail> } {
  const plans: Record<string, OriginPlan> = {};
  const routes: Record<string, RouteDetail> = {};
  for (const [id, p] of Object.entries(m.plans)) {
    if (none.notComputed?.includes(id)) plans[id] = unresolvedPlan(id, m.model.offsetsS, 'not_computed', 'live', false);
    else if (none.rejected?.includes(id)) {
      const r = unresolvedPlan(id, m.model.offsetsS, 'rejected', 'live', false);
      r.rejectReason = { code: 'SYNTHETIC_REFUSAL', message: 'SYNTHETIC: refused by the API' };
      plans[id] = r;
    } else if (none.failed?.includes(id)) {
      const attempts = p.sweep.flatMap((c) => c.attempts).map((a) => ({ ...a, verdict: 'unresolved' as const, arrivalS: null, computeS: null, jobId: null, reasonCode: 'BUSY', rawStatus: 'SYNTHETIC: the API was busy' }));
      plans[id] = planFromAttempts({ originId: id, offsetsS: m.model.offsetsS, attempts, source: 'live', mock: false });
    } else if (p.sweep.some((c) => c.attempts.length)) {
      const live = reliveOnHost(m, p, host, tag);
      plans[id] = live.plan;
      Object.assign(routes, live.routes);
    } else plans[id] = { ...p, source: 'live' };
  }
  return { plans, routes };
}

/** Build arguments of a live-only session as connect.ts makes them (no cache; hosts from the routes). */
export function liveOnlyArgs(m: BoothCacheModel, session: { plans: Record<string, OriginPlan>; routes: Record<string, RouteDetail> }, mock = false): LastMileBuildArgs {
  const liveHosts = Object.fromEntries(Object.entries(session.plans).map(([id, p]) => [id, liveHostsOf(p, (j) => session.routes[j] ?? null)]));
  return {
    region: { id: m.region.id, nameKo: m.region.nameKo, nameEn: m.region.nameEn, fireYear: m.region.fireYear },
    scenario: { scenarioSetId: m.entry.scenarioSetId, inputTimeIso: m.entry.inputTime, horizonS: m.model.horizonS ?? 3600 },
    places: m.places,
    plans: session.plans,
    mock,
    cache: null,
    liveHosts,
    source: 'live',
    generatedAtIso: FIXED_GENERATED_AT,
  };
}

/** A made-up road name exactly as long as the reader accepts (MAX_LABEL_CHARS = 40) in both languages. Tests only. */
export const SYNTHETIC_ROAD = { ko: '합성 시험용 아주 긴 이름의 지방도로 구간 (최대 마흔 글자 길이 시험)', en: 'Synthetic test road with a 40-char label' };

/**
 * A SYNTHETIC `wfg.explanation/1` file for one booth cache, shaped by the contract and built from
 * the planner's own deadlines: every leave-by origin whose next departure is a recorded "no route"
 * gets a flame-on-route reason on SYNTHETIC_ROAD (covering the message's destination), every
 * model_no_route origin four blocked exits with distinct 40-character labels,
 * the rest `not_explainable`. Made-up flame times — for testing the reader and the length budgets
 * only; it never leaves the tests. `shift` moves every deadline (a file that disagrees).
 */
export function syntheticExplanationFor(cache: BoothCache, shift = 0): ExplanationFile {
  const origins: Record<string, unknown> = {};
  for (const input of cache.inputs) {
    const p = messagePlan(input, null);
    const item = (flame: number, pass: number | null, destinationIds: string[] | null) => ({
      edge_id: 'synthetic:edge',
      label_ko: SYNTHETIC_ROAD.ko,
      label_en: SYNTHETIC_ROAD.en,
      label_source: 'osm_name',
      flame_time_s: flame,
      members: [0, 1, 2],
      members_total: 4,
      pass_time_at_deadline_s: pass,
      slack_s: pass === null ? null : flame - pass,
      ...(destinationIds ? { destination_ids: destinationIds } : {}),
    });
    if (p.kind === 'leave_by' && p.nextVerdict === 'model_no_route' && p.leaveByS !== null && p.nextOffsetS !== null) {
      origins[input.origin.id] = {
        status: 'explained',
        verdict_summary: 'checked_route',
        deadline_offset_s: p.leaveByS + shift,
        next_offset_s: p.nextOffsetS,
        next_verdict: 'model_no_route',
        reason_code: 'flame_on_route',
        detail_code: 'route_meets_flame_when_shifted',
        deadline_cause: 'flames',
        binding: [item(p.nextOffsetS + 300, p.leaveByS + 300, p.destination ? [p.destination.id] : [])],
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
        detail_code: 'flame_free_area_closed',
        deadline_cause: 'flames',
        binding: [],
        // four exits with distinct 40-character labels (the longest the reader accepts)
        exits: [1, 2, 3, 4].map((i) => ({
          ...item(600 * i, null, null),
          edge_id: `synthetic:exit:${i}`,
          label_ko: `합성 시험용 출구 도로 ${i}번 (마흔 글자를 채우는 아주 긴 시험용 이름)`,
          label_en: `Synthetic exit road ${i} with 40-char label`,
        })),
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

/**
 * Where the real deadline explanation files are looked for: $WFG_EXPLANATIONS_DIR (a local copy,
 * never committed here) or planner/public/data/explanations/ once they are merged.
 */
export function realExplanationDir(): URL {
  const env = process.env.WFG_EXPLANATIONS_DIR;
  return env ? pathToFileURL(`${resolve(env)}/`) : new URL('public/data/explanations/', PLANNER);
}

/** The real explanation file of one booth cache: the parsed file, `null` when absent, or an error. */
export function realExplanationFor(cache: BoothCache): { file: ExplanationFile | null; url: URL; error?: string } {
  const url = new URL(`${cache.entry.regionId}__${compactUtc(cache.entry.inputTime)}.json`, realExplanationDir());
  if (!existsSync(url)) return { file: null, url };
  const parsed = parseExplanationFile(JSON.parse(readFileSync(url, 'utf8')), {
    regionId: cache.entry.regionId,
    inputTimeIso: cache.entry.inputTime,
    scenarioSetId: cache.entry.scenarioSetId,
  });
  return parsed.ok ? { file: parsed.file, url } : { file: null, url, error: parsed.error };
}
