/**
 * Wire (contract v1.5) → internal model mapping (planner/src/api/adapter.ts) and request building.
 * The wire samples are SYNTHETIC: shaped like the contract, with made-up ids and numbers.
 */
import { describe, expect, it } from 'vitest';
import {
  adaptDispatchJob,
  adaptForecast,
  adaptHealth,
  adaptRegionList,
  adaptRouteJob,
  attemptFromRoute,
  isMockDispatchJob,
  isMockHealth,
  isMockRouteJob,
  toWireDispatch,
  toWireRouteCheck,
  travelOnlySpec,
} from '../../planner/src/api/adapter';
import type { WireDispatchPlanJob, WireForecastCollection, WireHealth, WireProvenance, WireRegionList, WireRouteCheckJob } from '../../planner/src/api/wire';
import type { Place } from '../../planner/src/domain/types';

const SET = 'ffb1:20990101T000000Z:synthetic';
const PROV: WireProvenance = {
  api_version: '1.5.0',
  package: 'wfg_latest',
  package_version: '1.0.0',
  kit: 'v3',
  checkpoint: 'c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843',
  git_commit: 'synthetic000',
  input_hashes: { graph: 'aaa', hazard: 'bbb' },
  scenario_set_id: SET,
  scenario_ids: [`${SET}:0`, `${SET}:1`, `${SET}:2`, `${SET}:3`],
  graph_id: 'synthetic-graph',
  policy: 'full',
  evaluated_configuration: true,
  recorded_mission_match: null,
  host: { platform: 'Linux-6.0-x86_64', machine: 'x86_64', cpu_count: 4 },
};

const SNAP = {
  start: { node_id: 'osm:1', distance_m: 0, lon: 128.1, lat: 36.1, input: 'node_id' as const },
  destination: { node_id: 'osm:2', distance_m: 0, lon: 128.2, lat: 36.2, input: 'node_id' as const },
};

function routeJob(over: Partial<WireRouteCheckJob['result']> & { verdict: 'checked_route' | 'model_no_route' | 'unresolved' }, extra: Partial<WireRouteCheckJob> = {}): WireRouteCheckJob {
  return {
    job_id: 'rc_synthetic',
    kind: 'route_check',
    status: 'done',
    created_at: '2099-01-01T00:00:00Z',
    request: {
      region: 'synthetic_region',
      input_time: '2099-01-01T00:00:00Z',
      start: { node_id: 'osm:1' },
      destination: { node_id: 'osm:2' },
      depart_offset_s: 600,
      dwell_s: 120,
      destination_window: [0, 3600],
      policy: 'full',
      limits: { peak_kw_m2: 10, dose_kj_m2: 100 },
      incurred_dose_kj_m2: 0,
      fire_input: { type: 'recorded', scenario_set_id: SET },
    },
    snap: SNAP,
    result: {
      reason_code: null,
      arrival_s: null,
      lower_bound_L_s: null,
      dwell_end_s: null,
      route: null,
      exposure: [],
      compute_s: 9.5,
      within_budget: true,
      provenance: PROV,
      ...over,
    },
    error: null,
    ...extra,
  };
}

const CHECKED = routeJob({
  verdict: 'checked_route',
  raw_status: 'CHECKED_ROUTE',
  departure_s: 600,
  arrival_s: 2000,
  lower_bound_L_s: 1990,
  lower_bounds: [{ kind: 'flame', arrival_s: 1990 }],
  dwell_end_s: 2120,
  route: {
    type: 'Feature',
    geometry: { type: 'LineString', coordinates: [[128.1, 36.1], [128.15, 36.15], [128.2, 36.2]] },
    properties: { times_s: [600, 1300, 2000], node_ids: ['osm:1', 'osm:5', 'osm:2'], segment_count: 2, length_m: 9000 },
  },
  exposure: [
    { scenario_id: `${SET}:0`, peak_kw_m2: 0.5, dose_kj_m2: 3.25, contact: false, basis: 'centre_model', peak_upper_kw_m2: 0.7, dose_upper_kj_m2: 4 },
    { scenario_id: `${SET}:1`, peak_kw_m2: 0.1, dose_kj_m2: 1, contact: false, basis: 'centre_model' },
  ],
  limits: { peak_kw_m2: 10, dose_kj_m2: 100, incurred_dose_kj_m2: 0 },
  notes: ['synthetic note'],
});

describe('RouteCheckJob → RouteDetail', () => {
  it('maps a checked route with exposure, bounds and provenance', () => {
    const d = adaptRouteJob(CHECKED);
    expect(d.verdict).toBe('checked_route');
    expect(d.arrivalS).toBe(2000);
    expect(d.dwellEndS).toBe(2120);
    expect(d.coordinates).toHaveLength(3);
    expect(d.timesS).toEqual([600, 1300, 2000]);
    expect(d.lengthM).toBe(9000);
    expect(d.exposure[0]).toMatchObject({ member: 1, peakKwM2: 0.5, doseKjM2: 3.25, contact: false, basis: 'centre_model', peakUpperKwM2: 0.7, doseUpperKjM2: 4 });
    expect(d.exposure[1]!.peakUpperKwM2).toBeNull();
    expect(d.provenance?.checkpoint).toMatch(/^c651/);
    expect(d.provenance?.host).toEqual({ recorded: false, machine: 'x86_64', os: null, platform: 'Linux-6.0-x86_64', cpuCount: 4 });
    expect(d.provenance?.evaluatedConfiguration).toBe(true);
    expect(d.spec).toMatchObject({ offsetS: 600, start: { kind: 'node', nodeId: 'osm:1' }, window: [0, 3600], limits: { peakKwM2: 10, doseKjM2: 100 } });
    expect(d.mock).toBe(false);
    const a = attemptFromRoute(d, 'dest-1', 600);
    expect(a).toMatchObject({ verdict: 'checked_route', arrivalS: 2000, computeS: 9.5, jobId: 'rc_synthetic', reasonCode: null });
  });
  it('maps model_no_route without a route', () => {
    const d = adaptRouteJob(routeJob({ verdict: 'model_no_route', raw_status: 'PROVEN_INFEASIBLE' }));
    expect(d.verdict).toBe('model_no_route');
    expect(d.coordinates).toBeNull();
    expect(d.exposure).toEqual([]);
  });
  it('maps unresolved with its (v1.1) reason code and never a route', () => {
    const d = adaptRouteJob(routeJob({ verdict: 'unresolved', reason_code: 'AT_ISSUE_FAILURE', compute_s: null }));
    expect(d.verdict).toBe('unresolved');
    expect(d.reasonCode).toBe('AT_ISSUE_FAILURE');
    expect(d.computeS).toBeNull();
    expect(attemptFromRoute(d, 'x', 0).verdict).toBe('unresolved');
  });
  it('treats unknown verdicts and failed jobs as unresolved', () => {
    expect(adaptRouteJob(routeJob({ verdict: 'maybe' as never })).verdict).toBe('unresolved');
    const failed = adaptRouteJob({ ...routeJob({ verdict: 'checked_route' }), status: 'failed', result: null, error: { code: 'WORKER_ERROR', message: 'synthetic' } });
    expect(failed.verdict).toBe('unresolved');
    expect(failed.reasonCode).toBe('WORKER_ERROR');
    expect(attemptFromRoute(failed, 'x', 0).verdict).toBe('unresolved');
  });
  it('maps a travel_only comparison with contact and full_policy_assessment', () => {
    const d = adaptRouteJob(
      routeJob({
        verdict: 'checked_route',
        policy: 'travel_only',
        arrival_s: 1500,
        route: { type: 'Feature', geometry: { type: 'LineString', coordinates: [[1, 1], [2, 2]] }, properties: { times_s: [0, 1500], node_ids: ['a', 'b'], segment_count: 1 } },
        exposure: [{ scenario_id: `${SET}:2`, peak_kw_m2: 0.7, dose_kj_m2: 17, contact: true, basis: 'full_model_centre_check' }],
        full_policy_assessment: { pass: false, failure_components: ['FLAME'], source: 'synthetic', full_whole_status: 'DEFINITE_REJECT', nested: { x: 1 } },
      }),
    );
    expect(d.policy).toBe('travel_only');
    expect(d.exposure[0]).toMatchObject({ member: 3, contact: true, basis: 'full_model_centre_check' });
    expect(d.fullPolicy).toEqual({ pass: false, components: ['FLAME'], source: 'synthetic', details: { full_whole_status: 'DEFINITE_REJECT' } });
  });
  it('reads the real API full_policy_assessment keys (passes_full_centre_and_contact, violations)', () => {
    const d = adaptRouteJob(
      routeJob({
        verdict: 'checked_route',
        policy: 'travel_only',
        arrival_s: 1500,
        route: { type: 'Feature', geometry: { type: 'LineString', coordinates: [[1, 1], [2, 2]] }, properties: { times_s: [0, 1500], node_ids: ['a', 'b'], segment_count: 1 } },
        exposure: [{ scenario_id: `${SET}:2`, peak_kw_m2: 0.7, dose_kj_m2: 17, contact: true }],
        full_policy_assessment: {
          passes_full_centre_and_contact: false,
          grammar_ok: true,
          whole_road_contact: 'CONTACT',
          violations: [
            { scenario_id: `${SET}:2`, constraint: 'FLAME_CONTACT' },
            { scenario_id: null, constraint: 'WHOLE_ROAD_CONTACT' },
            { scenario_id: `${SET}:3`, constraint: 'FLAME_CONTACT' },
          ],
          per_scenario: { [`${SET}:2`]: { peak_kw_m2: 0.7, dose_kj_m2: 17, contact: true } },
          passes_selected_policy: true,
        },
      }),
    );
    expect(d.fullPolicy?.pass).toBe(false);
    expect(d.fullPolicy?.components).toEqual(['FLAME_CONTACT', 'WHOLE_ROAD_CONTACT']);
    expect(d.fullPolicy?.details).toMatchObject({ grammar_ok: 'true', whole_road_contact: 'CONTACT', passes_selected_policy: 'true' });
  });
  it('builds the travel-only request from the checked one (same start, shelter, offset, limits)', () => {
    const spec = travelOnlySpec(adaptRouteJob(CHECKED))!;
    const body = toWireRouteCheck(spec, { region: 'synthetic_region', inputTime: '2099-01-01T00:00:00Z', scenarioSetId: SET }, 'test');
    expect(body).toEqual({
      region: 'synthetic_region',
      input_time: '2099-01-01T00:00:00Z',
      start: { node_id: 'osm:1' },
      destination: { node_id: 'osm:2' },
      depart_offset_s: 600,
      dwell_s: 120,
      destination_window: [0, 3600],
      policy: 'travel_only',
      fire_input: { type: 'recorded', scenario_set_id: SET },
      limits: { peak_kw_m2: 10, dose_kj_m2: 100 },
      incurred_dose_kj_m2: 0,
      client_ref: 'test',
    });
  });
});

describe('DispatchPlanJob → OriginPlans', () => {
  const job: WireDispatchPlanJob = {
    job_id: 'dp_synthetic',
    kind: 'dispatch_plan',
    status: 'done',
    created_at: '2099-01-01T00:00:00Z',
    request: { depart_offsets_s: [600, 0, 1200] },
    progress: { done: 9, total: 9 },
    result: {
      plans: [
        {
          origin_id: 'o1',
          urgency_rank: 1,
          snap: { node_id: 'osm:11', distance_m: 0, lon: 1, lat: 1, input: 'node_id' },
          best_verdict: 'checked_route',
          latest_checked_depart_offset_s: 1200,
          latest_contiguous_checked_depart_offset_s: 0,
          best: { destination_id: 'd1', depart_offset_s: 1200, verdict: 'checked_route', reason_code: null, arrival_s: 2500, compute_s: 8, route_check_job_id: 'rc_3' },
          attempts: [
            { destination_id: 'd1', depart_offset_s: 0, verdict: 'checked_route', reason_code: null, arrival_s: 1200, compute_s: 7, route_check_job_id: 'rc_1' },
            { destination_id: 'd1', depart_offset_s: 600, verdict: 'unresolved', reason_code: 'DISCONNECTED', arrival_s: null, compute_s: null, route_check_job_id: 'rc_2' },
            { destination_id: 'd1', depart_offset_s: 1200, verdict: 'checked_route', reason_code: null, arrival_s: 2500, compute_s: 8, route_check_job_id: 'rc_3' },
          ],
        },
        {
          origin_id: 'o2',
          urgency_rank: 2,
          best_verdict: 'model_no_route',
          latest_checked_depart_offset_s: null,
          best: null,
          attempts: [0, 600, 1200].map((t) => ({ destination_id: 'd1', depart_offset_s: t, verdict: 'model_no_route' as const, reason_code: null, arrival_s: null, compute_s: 6, route_check_job_id: `rc_n${t}` })),
        },
      ],
      summary: { origins: 2, attempts: 6, checked_route: 1, model_no_route: 1, unresolved: 0, median_compute_s: 7 },
      rejected_origins: [{ origin_id: 'o3', error: { code: 'NODE_NOT_ALLOWED', message: 'synthetic' } }],
      provenance: PROV,
    },
    error: null,
  };
  it('builds per-origin sweeps with both deadlines', () => {
    const a = adaptDispatchJob(job, 'live');
    expect(a.plans).toHaveLength(2);
    const o1 = a.plans[0]!;
    expect(o1.sweep.map((c) => [c.offsetS, c.verdict])).toEqual([
      [0, 'checked_route'],
      [600, 'unresolved'],
      [1200, 'checked_route'],
    ]);
    expect(o1.latestSafeDepartureS).toBe(1200);
    expect(o1.contiguousSafeDepartureS).toBe(0);
    expect(o1.best?.jobId).toBe('rc_3');
    expect(o1.apiSnap?.nodeId).toBe('osm:11');
    expect(o1.sweep[1]!.attempts[0]!.reasonCode).toBe('DISCONNECTED');
    expect(a.plans[1]!.bestVerdict).toBe('model_no_route');
    expect(a.rejected).toEqual([{ originId: 'o3', code: 'NODE_NOT_ALLOWED', message: 'synthetic' }]);
    expect(a.mock).toBe(false);
    expect(a.medianComputeS).toBe(7);
  });
  it('a running job has no plans yet', () => {
    const a = adaptDispatchJob({ ...job, status: 'running', progress: { done: 3, total: 9 } }, 'live');
    expect(a.plans).toEqual([]);
    expect(a.progress).toEqual({ done: 3, total: 9 });
  });
});

describe('Region list, forecast, health', () => {
  it('maps regions and scenario sets', () => {
    const list: WireRegionList = {
      regions: [
        {
          id: 'synthetic_region',
          name_ko: '합성',
          name_en: 'Synthetic',
          bbox: [128, 36, 129, 37],
          graph_id: 'g',
          node_count: 10,
          edge_count: 20,
          crs: 'EPSG:5179',
          grid: { x0: 0, y0: 0, resolution_m: 375, width: 2, height: 2 },
          input_times: ['2099-01-01T05:00:00Z', '2099-01-01T00:00:00Z'],
          scenario_sets: [
            { scenario_set_id: 'b', input_time: '2099-01-01T05:00:00Z', scenario_ids: ['b:0', 'b:1', 'b:2', 'b:3'], horizon_s: 3600 },
            { scenario_set_id: 'a', input_time: '2099-01-01T00:00:00Z', scenario_ids: ['a:0', 'a:1', 'a:2', 'a:3'], horizon_s: 3600, hazard_sha256: 'h' },
          ],
        },
      ],
      provenance: PROV,
    };
    const [r] = adaptRegionList(list);
    expect(r!.scenarioSets.map((s) => s.id)).toEqual(['a', 'b']);
    expect(r!.scenarioSets[0]).toMatchObject({ horizonS: 3600, scenarioIds: ['a:0', 'a:1', 'a:2', 'a:3'], hazardSha256: 'h', source: 'api' });
    expect(r!.fireYear).toBeNull();
  });
  it('maps forecast cells (p, burning, valid)', () => {
    const fc: WireForecastCollection = {
      type: 'FeatureCollection',
      region: 'synthetic_region',
      input_time: '2099-01-01T00:00:00Z',
      features: [
        { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }, properties: { row: 0, col: 0, p_new_burn_1h: 0.03, valid: true, burning_now: false } },
        { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }, properties: { row: 0, col: 1, p_new_burn_1h: null, valid: false, burning_now: true } },
      ],
      provenance: { ...PROV, mock: true },
    };
    const f = adaptForecast(fc, 'synthetic_region', '2099-01-01T00:00:00Z');
    expect(f.cells.features.map((x) => x.properties)).toEqual([
      { p: 0.03, burning: false, valid: true },
      { p: null, burning: true, valid: false },
    ]);
    expect(f.mock).toBe(true);
  });
  it('MOCK detection from health, jobs and provenance', () => {
    const real: WireHealth = { status: 'ok', api_version: '1.5.0', package: 'wfg_latest', package_version: '1.0.0', kit: 'v3', checkpoint: PROV.checkpoint, git_commit: 'x', regions: [], workers: 2, queued_tasks: 7, provenance: PROV };
    expect(isMockHealth(real)).toBe(false);
    expect(adaptHealth(real)).toMatchObject({ mock: false, workers: 2, queued: 7, host: { cpuCount: 4 } });
    expect(isMockHealth({ ...real, mode: 'mock' })).toBe(true);
    expect(isMockHealth({ ...real, mock: true })).toBe(true);
    expect(isMockRouteJob(CHECKED)).toBe(false);
    expect(isMockRouteJob({ ...CHECKED, mock: true })).toBe(true);
    expect(isMockRouteJob({ ...CHECKED, result: { ...CHECKED.result!, provenance: { ...PROV, mock: true } } })).toBe(true);
    expect(adaptRouteJob({ ...CHECKED, mock: true }).mock).toBe(true);
    expect(isMockDispatchJob({ job_id: 'x', kind: 'dispatch_plan', status: 'queued', created_at: '', request: {}, progress: { done: 0, total: 0 }, result: null, error: null, provenance: { ...PROV, mock: true } })).toBe(true);
  });
});

describe('dispatch request building', () => {
  const p = (id: string, role: Place['role'], node: string | null): Place => ({
    id,
    role,
    category: role === 'destination' ? 'school' : 'village',
    name: null,
    nameEn: null,
    lon: 128.1,
    lat: 36.1,
    source: 'OpenStreetMap',
    sourceTag: 'synthetic',
    osm: null,
    snapNode: node,
    snapDistanceM: 5,
    entry: node ? { node, lon: 128.1, lat: 36.1, distanceM: 5, withinApiLonlatSnap: true } : null,
    checkable: true,
    vulnerable: false,
    scenarioSetId: null,
    inputTime: null,
    caseId: null,
    recorded: null,
  });
  it('sends entry nodes, window [0, horizon], dwell 120 and policy full', () => {
    const byId = new Map([p('o1', 'origin', 'osm:1'), p('d1', 'destination', 'osm:2'), p('o2', 'origin', null)].map((x) => [x.id, x]));
    const body = toWireDispatch({ originIds: ['o1', 'o2'], destinationIds: ['d1'], offsetsS: [0, 600] }, byId, { region: 'r', inputTime: 't', scenarioSetId: SET, horizonS: 3600 });
    expect(body.origins).toEqual([
      { id: 'o1', location: { node_id: 'osm:1' } },
      { id: 'o2', location: { lon: 128.1, lat: 36.1 } },
    ]);
    expect(body.destinations).toEqual([{ id: 'd1', location: { node_id: 'osm:2' }, dwell_s: 120, window: [0, 3600] }]);
    expect(body).toMatchObject({ depart_offsets_s: [0, 600], dwell_s: 120, policy: 'full', fire_input: { type: 'recorded', scenario_set_id: SET } });
  });
});
