/**
 * Data flow (planner/src/state/controller.ts) against a stubbed fetch — no network. All places, ids
 * and results are SYNTHETIC test data ("합성" names, round coordinates).
 *
 * - a travel-time-only comparison started for one scenario never lands in the next one;
 * - a batch re-attaches to the job it submitted before ("중지" → "다시 시도" posts once per group);
 * - refused / failed checks are counted as rejected, never as "점검 완료".
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { adaptRouteJob } from '../../planner/src/api/adapter';
import type { WireRouteCheckJob } from '../../planner/src/api/wire';
import { planFromAttempts } from '../../planner/src/domain/plan';
import type { ApiRegion, HealthInfo, Place } from '../../planner/src/domain/types';
import { cancelBatch, ensureTravelOnly, forgetSubmittedJobs, selectScenario, startBatch } from '../../planner/src/state/controller';
import { DRAWN_SCENARIO, getState, IDLE_BATCH, setState } from '../../planner/src/state/store';

const REGION = 'synthetic_region';
const SET_A = 'ffb1:20990101T000000Z:synthetic-a';
const SET_B = 'ffb1:20990101T010000Z:synthetic-b';

const HEALTH: HealthInfo = {
  status: 'ok',
  apiVersion: '1.5.0',
  packageVersion: '1.0.0',
  kit: 'v3',
  checkpoint: 'c651',
  gitCommit: 'synthetic',
  regions: [REGION],
  workers: 2,
  issues: [],
  mock: false, // a real-looking API: nothing starts by itself
  host: null,
  queued: 0,
  budgetS: 30,
};

const API_REGION: ApiRegion = {
  id: REGION,
  nameKo: '합성 지역',
  nameEn: 'Synthetic region',
  eventId: null,
  bbox: [126.9, 35.9, 127.2, 36.2],
  graphId: 'synthetic',
  graphSha256: null,
  nodeCount: 10,
  edgeCount: 10,
  allowedNodeCount: 10,
  inputTimes: ['2099-01-01T00:00:00Z', '2099-01-01T01:00:00Z'],
  scenarioSets: [
    { id: SET_A, inputTime: '2099-01-01T00:00:00Z', scenarioIds: [], horizonS: 3600, hazardSha256: null, source: 'api' },
    { id: SET_B, inputTime: '2099-01-01T01:00:00Z', scenarioIds: [], horizonS: 3600, hazardSha256: null, source: 'api' },
  ],
  fireYear: 2099,
};

function place(id: string, lon: number, lat: number, extra: Partial<Place> = {}): Place {
  return {
    id,
    role: 'origin',
    category: 'village',
    name: `합성 ${id}`,
    nameEn: null,
    lon,
    lat,
    source: 'OpenStreetMap',
    sourceTag: 'place=village',
    osm: null,
    snapNode: `osm:${id}`,
    snapDistanceM: 10,
    entry: { node: `osm:${id}`, lon, lat, distanceM: 10, withinApiLonlatSnap: true },
    checkable: true,
    vulnerable: false,
    scenarioSetId: null,
    inputTime: null,
    caseId: null,
    recorded: null,
    ...extra,
  };
}

const O1 = place('o1', 127.0, 36.0);
const O2 = place('o2', 127.001, 36.0);
const D1 = place('d1', 127.01, 36.0, { role: 'destination', category: 'school' });
const D2 = place('d2', 127.02, 36.0, { role: 'destination', category: 'school' });
const R1 = place('r1', 127.05, 36.05, {
  role: 'research_origin',
  category: 'research',
  name: null,
  scenarioSetId: SET_A,
  inputTime: '2099-01-01T00:00:00Z',
  caseId: '20990101T000000Z_FD1',
  recorded: { destinationId: 'rd1', destinationNode: 'osm:rd1', departOffsetS: 300, dwellS: 120, destinationWindow: [0, 3600], incurredDoseKjM2: null, limits: null, horizonS: 3600 },
});
const RD1 = place('rd1', 127.06, 36.06, { role: 'research_destination', category: 'research', name: null, scenarioSetId: SET_A });

function routeJob(jobId: string, policy: 'full' | 'travel_only'): WireRouteCheckJob {
  return {
    job_id: jobId,
    kind: 'route_check',
    status: 'done',
    created_at: '2099-01-01T00:00:00Z',
    request: { start: { node_id: 'osm:o1' }, destination: { node_id: 'osm:d1' }, depart_offset_s: 0, dwell_s: 120, destination_window: [0, 3600], policy },
    snap: { start: { node_id: 'osm:o1', distance_m: 0, lon: 127, lat: 36, input: 'node_id' }, destination: { node_id: 'osm:d1', distance_m: 0, lon: 127.01, lat: 36, input: 'node_id' } },
    result: {
      verdict: 'checked_route',
      reason_code: null,
      arrival_s: 600,
      lower_bound_L_s: null,
      dwell_end_s: 720,
      route: { type: 'Feature', geometry: { type: 'LineString', coordinates: [[127, 36], [127.01, 36]] }, properties: { times_s: [0, 600], node_ids: ['osm:o1', 'osm:d1'], segment_count: 1 } },
      exposure: [],
      compute_s: 1,
      within_budget: true,
      policy,
    },
    error: null,
  } as unknown as WireRouteCheckJob;
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

type Handler = (method: string, url: string, body: unknown, signal: AbortSignal | undefined) => Promise<Response> | Response;

/** fetch stub: a handler per request; unknown paths answer 404 (forecast, footprints …). */
function stubFetch(handler: Handler, honourAbort = true) {
  const calls: { method: string; url: string; body: unknown }[] = [];
  const f = vi.fn((input: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url: input, body });
    const signal = init?.signal ?? undefined;
    const res = Promise.resolve(handler(method, input, body, signal));
    if (!honourAbort || !signal) return res;
    return new Promise<Response>((resolve, reject) => {
      if (signal.aborted) return reject(new DOMException('aborted', 'AbortError'));
      signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true });
      res.then(resolve, reject);
    });
  });
  vi.stubGlobal('fetch', f);
  return calls;
}

async function until(cond: () => boolean, ms = 5000): Promise<void> {
  const t0 = Date.now();
  while (!cond()) {
    if (Date.now() - t0 > ms) throw new Error('timed out waiting');
    await new Promise((r) => setTimeout(r, 10));
  }
}

function baseState(places: Place[], extra: Record<string, unknown> = {}) {
  setState({
    regionId: REGION,
    scenarioId: SET_A,
    places,
    placesState: 'ready',
    apiStatus: 'online',
    health: HEALTH,
    apiRegions: { [REGION]: API_REGION },
    cacheIndex: [],
    cache: null,
    dataSource: 'live',
    plans: {},
    routes: {},
    routeErrors: {},
    travelOnly: {},
    batch: IDLE_BATCH,
    recompute: null,
    selectedOriginId: null,
    selectedOffsetS: null,
    ...extra,
  });
}

beforeEach(() => {
  forgetSubmittedJobs();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('travel-time-only comparison and scenario switches', () => {
  const bestJob = routeJob('rc_best', 'full');
  const plan = planFromAttempts({
    originId: O1.id,
    offsetsS: [0],
    attempts: [{ offsetS: 0, destinationId: D1.id, verdict: 'checked_route', arrivalS: 600, computeS: 1, jobId: 'rc_best', reasonCode: null }],
    source: 'live',
    mock: false,
  });

  for (const [label, next, honourAbort] of [
    ['recorded → recorded (request aborted)', SET_B, true],
    ['recorded → recorded (late response arrives anyway)', SET_B, false],
    ['recorded → drawn zones', DRAWN_SCENARIO, true],
  ] as const) {
    it(`never lands in the next scenario: ${label}`, async () => {
      let release: (r: Response) => void = () => {};
      const late = new Promise<Response>((r) => (release = r));
      const calls = stubFetch((method, url) => {
        if (method === 'POST' && url.endsWith('/route-checks')) return json(202, { job_id: 'rc_to', status: 'queued' });
        if (method === 'GET' && url.endsWith('/route-checks/rc_to')) return late;
        return json(404, { error: { code: 'NOT_FOUND', message: 'synthetic' } });
      }, honourAbort);
      baseState([O1, O2, D1, D2], { plans: { [O1.id]: plan }, routes: { rc_best: adaptRouteJob(bestJob) }, selectedOriginId: O1.id, selectedOffsetS: 0 });
      const p = ensureTravelOnly(O1.id, true);
      await until(() => calls.some((c) => c.method === 'GET' && c.url.endsWith('/route-checks/rc_to')));
      expect(getState().travelOnly[O1.id]?.state).toBe('loading');
      await selectScenario(next);
      release(json(200, routeJob('rc_to', 'travel_only')));
      await p;
      await new Promise((r) => setTimeout(r, 20));
      expect(getState().scenarioId).toBe(next);
      expect(getState().travelOnly[O1.id]).toBeUndefined();
    });
  }
});

describe('batch: re-attach and honest counters', () => {
  const dispatchDone = (id: string) => ({
    job_id: id,
    kind: 'dispatch_plan',
    status: 'done',
    created_at: '2099-01-01T00:00:00Z',
    request: { depart_offsets_s: [0, 600, 1200, 1800, 2400, 3000] },
    progress: { done: 24, total: 24 },
    result: { plans: [], summary: {}, rejected_origins: [] },
    error: null,
  });

  it('"중지" then "다시 시도" re-attaches to the submitted job: one POST per group', async () => {
    let posts = 0;
    let finished = false;
    stubFetch((method, url) => {
      if (method === 'POST' && url.endsWith('/dispatch-plans')) {
        posts += 1;
        return json(202, { job_id: `dp_${posts}`, status: 'queued' });
      }
      if (method === 'GET' && url.includes('/dispatch-plans/')) {
        const id = url.split('/').pop()!;
        return json(200, finished ? dispatchDone(id) : { ...dispatchDone(id), status: 'running', result: null, progress: { done: 3, total: 24 } });
      }
      return json(404, { error: { code: 'NOT_FOUND', message: 'synthetic' } });
    });
    baseState([O1, O2, D1, D2]);
    const first = startBatch();
    await until(() => posts === 1 && getState().batch.done === 3);
    cancelBatch();
    await first;
    expect(getState().batch.state).toBe('cancelled');
    finished = true;
    await startBatch();
    expect(posts).toBe(1);
    expect(getState().batch).toMatchObject({ state: 'done', done: 24, total: 24, rejected: 0 });
  });

  it('a fully refused batch is never "점검 완료": done 0, every check rejected, state error', async () => {
    stubFetch((method, url) => {
      if (method === 'POST' && url.endsWith('/dispatch-plans')) return json(422, { error: { code: 'VALIDATION_ERROR', message: 'synthetic' } });
      if (method === 'POST' && url.endsWith('/route-checks')) return json(422, { error: { code: 'NODE_NOT_ALLOWED', message: 'synthetic' } });
      return json(404, { error: { code: 'NOT_FOUND', message: 'synthetic' } });
    });
    baseState([O1, O2, D1, D2, R1, RD1]);
    await startBatch();
    const b = getState().batch;
    expect(b.total).toBe(24 + 7);
    expect(b.done).toBe(0);
    expect(b.rejected).toBe(b.total);
    expect(b.state).toBe('error');
    expect(b.error?.code).toBe('VALIDATION_ERROR');
    // the origins stay unresolved with the API's code (never safe)
    expect(getState().plans[O1.id]).toMatchObject({ bestVerdict: 'unresolved', note: 'rejected', rejectReason: { code: 'VALIDATION_ERROR' } });
  });

  it('a refused research check is not counted as done (dispatch checks are)', async () => {
    stubFetch((method, url) => {
      if (method === 'POST' && url.endsWith('/dispatch-plans')) return json(202, { job_id: 'dp_ok', status: 'queued' });
      if (method === 'GET' && url.endsWith('/dispatch-plans/dp_ok')) return json(200, dispatchDone('dp_ok'));
      if (method === 'POST' && url.endsWith('/route-checks')) return json(422, { error: { code: 'NODE_NOT_ALLOWED', message: 'synthetic' } });
      return json(404, { error: { code: 'NOT_FOUND', message: 'synthetic' } });
    });
    baseState([O1, O2, D1, D2, R1, RD1]);
    await startBatch();
    const b = getState().batch;
    expect(b.done).toBe(24);
    expect(b.rejected).toBe(7);
    expect(b.state).toBe('done');
    expect(b.error?.code).toBe('NODE_NOT_ALLOWED');
    const r = getState().plans[R1.id]!;
    expect(r.bestVerdict).toBe('unresolved');
    expect(r.sweep.flatMap((c) => c.attempts).every((a) => a.reasonCode === 'NODE_NOT_ALLOWED')).toBe(true);
  });
});
