/**
 * HTTP client (planner/src/api/client.ts): error codes and messages are surfaced verbatim
 * (including codes this build does not know), polling, and the concurrency pool.
 * fetch is stubbed; no network.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, JOB_FROZEN, runPool, waitRouteCheck } from '../../planner/src/api/client';

function respond(status: number, body: unknown, contentType = 'application/json') {
  return Promise.resolve(new Response(typeof body === 'string' ? body : JSON.stringify(body), { status, headers: { 'Content-Type': contentType } }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('error mapping', () => {
  it('surfaces the API error code and message (422)', async () => {
    vi.stubGlobal('fetch', vi.fn(() => respond(422, { error: { code: 'SNAP_TOO_FAR', message: 'synthetic 412 m', details: { distance_m: 412 } } })));
    const e = await api.submitRouteCheck({} as never).catch((x) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({ status: 422, code: 'SNAP_TOO_FAR', message: 'synthetic 412 m', details: { distance_m: 412 } });
  });
  it('v1.5 503 codes and unknown codes are kept verbatim', async () => {
    vi.stubGlobal('fetch', vi.fn(() => respond(503, { error: { code: 'BUSY', message: 'too many queued' } })));
    await expect(api.submitDispatch({} as never)).rejects.toMatchObject({ status: 503, code: 'BUSY' });
    vi.stubGlobal('fetch', vi.fn(() => respond(422, { error: { code: 'SOME_FUTURE_CODE', message: 'explained here' } })));
    await expect(api.submitDispatch({} as never)).rejects.toMatchObject({ code: 'SOME_FUTURE_CODE', message: 'explained here' });
  });
  it('a proxy error page or a refused connection is NETWORK', async () => {
    vi.stubGlobal('fetch', vi.fn(() => respond(502, 'Bad Gateway', 'text/plain')));
    await expect(api.health()).rejects.toMatchObject({ code: 'NETWORK', status: 502 });
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('fetch failed'))));
    await expect(api.health()).rejects.toMatchObject({ code: 'NETWORK', status: 0 });
  });
  it('calls the same-origin /api/v1 base', async () => {
    const f = vi.fn(() => respond(200, { status: 'ok' }));
    vi.stubGlobal('fetch', f);
    await api.forecast('synthetic_region', '2099-01-01T00:00:00Z');
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe('/api/v1/regions/synthetic_region/forecast?input_time=2099-01-01T00%3A00%3A00Z&only_nonzero=true');
  });
});

describe('polling', () => {
  it('polls a route check until it is done', async () => {
    const states = ['queued', 'running', 'done'];
    let i = 0;
    vi.stubGlobal('fetch', vi.fn(() => respond(200, { job_id: 'rc', kind: 'route_check', status: states[Math.min(i++, 2)], result: null })));
    const seen: string[] = [];
    const job = await waitRouteCheck('rc', (j) => seen.push(j.status), { intervalMs: 1, maxIntervalMs: 2 });
    expect(job.status).toBe('done');
    expect(seen).toEqual(['queued', 'running', 'done']);
  });
  it('ends a job frozen by an API restart (health: no queued or running work) as JOB_FROZEN', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => (url.endsWith('/health') ? respond(200, { status: 'ok', queued_tasks: 0, jobs: { queued: 0, running: 0, done: 4 } }) : respond(200, { job_id: 'rc', status: 'running' }))));
    const e = await waitRouteCheck('rc', undefined, { intervalMs: 1, maxIntervalMs: 2, frozenCheckMs: 1 }).catch((x) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({ code: JOB_FROZEN, status: 410 });
  });
  it('keeps waiting while health reports live work, and returns a job that finished meanwhile', async () => {
    let polls = 0;
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url.endsWith('/health')) return respond(200, { status: 'ok', queued_tasks: 0, jobs: { queued: 0, running: 1 } });
      polls += 1;
      return respond(200, { job_id: 'rc', status: polls >= 9 ? 'done' : 'running', result: null });
    }));
    const job = await waitRouteCheck('rc', undefined, { intervalMs: 1, maxIntervalMs: 2, frozenCheckMs: 1 });
    expect(job.status).toBe('done');
  });
  it('a health that fails or carries no work counts never ends the wait as frozen', async () => {
    let polls = 0;
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      // no counts, MOCK-style counts by kind, or a failed health: cannot tell, keep waiting
      if (url.endsWith('/health')) return [respond(200, { status: 'ok' }), respond(200, { status: 'ok', queued_tasks: 0, jobs: { route_check: 3, dispatch_plan: 1 } }), respond(502, 'Bad Gateway', 'text/plain')][polls % 3]!;
      polls += 1;
      return respond(200, { job_id: 'rc', status: polls >= 8 ? 'done' : 'queued', result: null });
    }));
    const job = await waitRouteCheck('rc', undefined, { intervalMs: 1, maxIntervalMs: 2, frozenCheckMs: 1 });
    expect(job.status).toBe('done');
  });
  it('stops on abort', async () => {
    vi.stubGlobal('fetch', vi.fn(() => respond(200, { job_id: 'rc', status: 'running' })));
    const ctrl = new AbortController();
    const p = waitRouteCheck('rc', undefined, { intervalMs: 5, signal: ctrl.signal });
    ctrl.abort();
    await expect(p).rejects.toMatchObject({ code: 'ABORTED' });
  });
});

describe('concurrency pool', () => {
  it('never runs more than the limit at once and runs every item', async () => {
    let running = 0;
    let peak = 0;
    const done: number[] = [];
    await runPool([1, 2, 3, 4, 5], 2, async (x) => {
      running++;
      peak = Math.max(peak, running);
      await new Promise((r) => setTimeout(r, 2));
      done.push(x);
      running--;
    });
    expect(peak).toBe(2);
    expect(done.sort()).toEqual([1, 2, 3, 4, 5]);
  });
});
