/**
 * Precompute cache loading (planner/src/api/cache.ts) from an inline SYNTHETIC cache document
 * shaped like planner/scripts/precompute.py output (schema wfg.planner.cache/1).
 */
import { describe, expect, it } from 'vitest';
import { cacheToModel, findCacheEntry, parseCacheIndex } from '../../planner/src/api/cache';
import type { WireCacheFile, WireDispatchPlanJob, WireProvenance, WireRouteCheckJob } from '../../planner/src/api/wire';

const SET = 'ffb1:20990101T000000Z:synthetic';
const PROV = (mock: boolean, host: Record<string, unknown> | null): WireProvenance => ({
  api_version: '1.5.0',
  package: 'wfg_latest',
  package_version: '1.0.0',
  kit: 'v3',
  checkpoint: 'c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843',
  git_commit: 'synthetic',
  input_hashes: {},
  scenario_ids: [],
  scenario_set_id: SET,
  host,
  ...(mock ? { mock: true } : {}),
});
const HOST = { platform: 'Linux-6.0-x86_64', machine: 'x86_64', cpu_count: 4 };

function rc(id: string, verdict: 'checked_route' | 'model_no_route' | 'unresolved', off: number, arrival: number | null, policy = 'full', mock = false): WireRouteCheckJob {
  return {
    job_id: id,
    kind: 'route_check',
    status: 'done',
    created_at: '2099-01-01T00:00:00Z',
    request: { start: { node_id: 'osm:10' }, destination: { node_id: 'osm:20' }, depart_offset_s: off, dwell_s: 120, destination_window: [0, 2619], policy: policy as 'full' },
    snap: {
      start: { node_id: 'osm:10', distance_m: 0, lon: 1, lat: 1, input: 'node_id' },
      destination: { node_id: 'osm:20', distance_m: 0, lon: 2, lat: 2, input: 'node_id' },
    },
    result: {
      verdict,
      reason_code: verdict === 'unresolved' ? 'TIMEOUT' : null,
      arrival_s: arrival,
      lower_bound_L_s: null,
      dwell_end_s: arrival === null ? null : arrival + 120,
      route: verdict === 'checked_route' ? { type: 'Feature', geometry: { type: 'LineString', coordinates: [[1, 1], [2, 2]] }, properties: { times_s: [off, arrival ?? off], node_ids: ['osm:10', 'osm:20'], segment_count: 1 } } : null,
      exposure: [],
      compute_s: 5,
      within_budget: true,
      policy: policy as 'full',
      provenance: PROV(mock, HOST),
    },
    error: null,
    ...(mock ? { mock: true } : {}),
  };
}

const plan: WireDispatchPlanJob = {
  job_id: 'dp_1',
  kind: 'dispatch_plan',
  status: 'done',
  created_at: '2099-01-01T00:00:00Z',
  request: { depart_offsets_s: [0, 600], origins: [{ id: 'osm:node/1', location: { node_id: 'osm:1' } }] },
  progress: { done: 2, total: 2 },
  result: {
    plans: [
      {
        origin_id: 'osm:node/1',
        urgency_rank: 1,
        best_verdict: 'checked_route',
        latest_checked_depart_offset_s: 600,
        latest_contiguous_checked_depart_offset_s: 600,
        best: { destination_id: 'osm:node/9', depart_offset_s: 600, verdict: 'checked_route', reason_code: null, arrival_s: 1800, compute_s: 6, route_check_job_id: 'rc_osm_600' },
        attempts: [
          { destination_id: 'osm:node/9', depart_offset_s: 0, verdict: 'checked_route', reason_code: null, arrival_s: 1200, compute_s: 6, route_check_job_id: 'rc_osm_0' },
          { destination_id: 'osm:node/9', depart_offset_s: 600, verdict: 'checked_route', reason_code: null, arrival_s: 1800, compute_s: 6, route_check_job_id: 'rc_osm_600' },
        ],
      },
    ],
    summary: { origins: 1, attempts: 2, checked_route: 1, model_no_route: 0, unresolved: 0 },
    rejected_origins: [{ origin_id: 'osm:node/2', error: { code: 'NODE_NOT_ALLOWED', message: 'synthetic' } }],
    provenance: PROV(false, HOST),
  },
  error: null,
};

const RID = 'research:synthetic:20990101T000000Z_FD1:origin';
const DOC: WireCacheFile = {
  schema: 'wfg.planner.cache/1',
  region_id: 'synthetic_region',
  scenario_set_id: SET,
  input_time: '2099-01-01T00:00:00Z',
  fire_input: { type: 'recorded', scenario_set_id: SET },
  created_at: '2099-01-01T09:30:00+00:00',
  api: { base: 'http://127.0.0.1:8765/v1', mode: 'live', health: null, host: HOST },
  planner_commit: 'synthetic',
  generator: { client_host: 'Darwin arm64', step_min: 10, shelters_per_origin: 3 },
  requests: [
    {
      region: 'synthetic_region',
      input_time: '2099-01-01T00:00:00Z',
      fire_input: { type: 'recorded', scenario_set_id: SET },
      origins: [{ id: 'osm:node/1', location: { node_id: 'osm:1' } }],
      destinations: [{ id: 'osm:node/9', location: { node_id: 'osm:9' }, dwell_s: 120, window: [0, 3600] }],
      depart_offsets_s: [0, 600],
    },
  ],
  plans: [plan],
  research_checks: [
    { origin_id: RID, destination_id: 'rd', depart_offset_s: 0, job_id: 'rc_r0' },
    { origin_id: RID, destination_id: 'rd', depart_offset_s: 600, job_id: 'rc_r600' },
    { origin_id: RID, destination_id: 'rd', depart_offset_s: 3000, job_id: null, skipped: 'WINDOW_UNSATISFIABLE' },
  ],
  rejected_requests: [
    { kind: 'dispatch_plan', request: { origins: [{ id: 'osm:node/3' }], depart_offsets_s: [0, 600] }, status: 422, code: 'TOO_MANY_ATTEMPTS', error: { error: { code: 'TOO_MANY_ATTEMPTS', message: 'synthetic' } } },
  ],
  route_checks: {
    rc_osm_0: rc('rc_osm_0', 'checked_route', 0, 1200),
    rc_osm_600: rc('rc_osm_600', 'checked_route', 600, 1800),
    rc_r0: rc('rc_r0', 'unresolved', 0, null),
    rc_r600: rc('rc_r600', 'checked_route', 600, 2000),
  },
  travel_only: { [RID]: rc('rc_to', 'checked_route', 600, 1500, 'travel_only') },
};

const ENTRY = parseCacheIndex([
  { region_id: 'synthetic_region', scenario_set_id: SET, input_time: '2099-01-01T00:00:00Z', path: 'synthetic_region/20990101T000000Z.json', api_mode: 'live', created_at: '2099-01-01T09:30:00+00:00', origins: 2, bytes: 1, sha256: 'x' },
  { region_id: 'bad' },
])[0]!;

describe('cache index', () => {
  it('parses INDEX.json entries and finds a scenario set', () => {
    expect(ENTRY).toMatchObject({ regionId: 'synthetic_region', scenarioSetId: SET, apiMode: 'live' });
    expect(findCacheEntry([ENTRY], 'synthetic_region', SET)).toBe(ENTRY);
    expect(findCacheEntry([ENTRY], 'synthetic_region', 'other')).toBeNull();
    expect(parseCacheIndex(null)).toEqual([]);
  });
});

describe('cache file → internal model', () => {
  const data = cacheToModel(DOC, ENTRY);
  it('turns dispatch attempts into per-origin sweeps', () => {
    const p = data.plans['osm:node/1']!;
    expect(p.source).toBe('cache');
    expect(p.sweep.map((c) => c.verdict)).toEqual(['checked_route', 'checked_route']);
    expect(p.latestSafeDepartureS).toBe(600);
    expect(p.contiguousSafeDepartureS).toBe(600);
    expect(data.offsetsS).toEqual([0, 600]);
    expect(data.horizonS).toBe(3600);
  });
  it('turns research_checks into sweeps from route_checks, with a distinct "시간창 밖" cell', () => {
    const p = data.plans[RID]!;
    expect(p.sweep.map((c) => [c.offsetS, c.verdict, c.skipped ?? null])).toEqual([
      [0, 'unresolved', null],
      [600, 'checked_route', null],
      [3000, 'unresolved', 'window_unsatisfiable'],
    ]);
    expect(p.latestSafeDepartureS).toBe(600);
    expect(p.contiguousSafeDepartureS).toBeNull();
    expect(p.bestVerdict).toBe('checked_route');
    expect(p.apiSnap?.nodeId).toBe('osm:10');
  });
  it('keeps rejected origins as unresolved with their code (never safe)', () => {
    expect(data.plans['osm:node/2']).toMatchObject({ bestVerdict: 'unresolved', note: 'rejected', rejectReason: { code: 'NODE_NOT_ALLOWED' } });
    expect(data.plans['osm:node/3']).toMatchObject({ bestVerdict: 'unresolved', note: 'rejected', rejectReason: { code: 'TOO_MANY_ATTEMPTS' } });
    expect(data.plans['osm:node/3']!.latestSafeDepartureS).toBeNull();
  });
  it('exposes route details by job id and travel-only checks by origin', () => {
    expect(data.route('rc_osm_600')?.arrivalS).toBe(1800);
    expect(data.route('missing')).toBeNull();
    expect(data.travelOnly[RID]?.policy).toBe('travel_only');
  });
  it('carries provenance: api mode, created_at, client host and compute host', () => {
    expect(data.meta).toMatchObject({ apiMode: 'live', createdAt: '2099-01-01T09:30:00+00:00', clientHost: 'Darwin arm64', stepMin: 10, mock: false, rejectedRequests: 1 });
    expect(data.meta.computeHost).toMatchObject({ machine: 'x86_64', cpuCount: 4, recorded: false });
  });
  it('a cache made from the mock is MOCK', () => {
    const m = cacheToModel({ ...DOC, api: { ...DOC.api, mode: 'mock' } }, { ...ENTRY, apiMode: 'mock' });
    expect(m.meta.mock).toBe(true);
    expect(Object.values(m.plans).every((p) => p.mock)).toBe(true);
    const viaJobs = cacheToModel({ ...DOC, route_checks: { ...DOC.route_checks, rc_r0: rc('rc_r0', 'unresolved', 0, null, 'full', true) } }, ENTRY);
    expect(viaJobs.meta.mock).toBe(true);
  });
});
