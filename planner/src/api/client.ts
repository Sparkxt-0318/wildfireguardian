/**
 * HTTP client for the Route-Check API (same-origin /api/v1/*, proxied by Vite dev and preview to
 * the configured target). Timeouts, polling and abort; every failure becomes an ApiError that
 * carries the API's error.code and error.message (unknown codes are kept verbatim).
 */
import type {
  WireDispatchPlanJob,
  WireDispatchPlanRequest,
  WireError,
  WireForecastCollection,
  WireHealth,
  WireJobAccepted,
  WireRegionList,
  WireRouteCheckJob,
  WireRouteCheckRequest,
} from './wire';

export const API_BASE = '/api/v1';

export class ApiError extends Error {
  /** HTTP status (0 = network failure or client timeout) */
  readonly status: number;
  /** API error code (e.g. SNAP_TOO_FAR, BUSY) or a client code: NETWORK, CLIENT_TIMEOUT, ABORTED, BAD_RESPONSE */
  readonly code: string;
  readonly details: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isAbort(e: unknown): boolean {
  return e instanceof ApiError ? e.code === 'ABORTED' : e instanceof DOMException && e.name === 'AbortError';
}

interface RequestOpts {
  signal?: AbortSignal;
  timeoutMs?: number;
}

function linkSignals(outer: AbortSignal | undefined, timeoutMs: number): { signal: AbortSignal; cleanup: () => void; timedOut: () => boolean } {
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, timeoutMs);
  const onAbort = () => ctrl.abort();
  if (outer) {
    if (outer.aborted) ctrl.abort();
    else outer.addEventListener('abort', onAbort, { once: true });
  }
  return {
    signal: ctrl.signal,
    cleanup: () => {
      clearTimeout(timer);
      outer?.removeEventListener('abort', onAbort);
    },
    timedOut: () => timedOut,
  };
}

async function request<T>(method: 'GET' | 'POST', path: string, body: unknown, opts: RequestOpts = {}): Promise<T> {
  const { signal, cleanup, timedOut } = linkSignals(opts.signal, opts.timeoutMs ?? 20000);
  let r: Response;
  try {
    r = await fetch(API_BASE + path, {
      method,
      signal,
      headers: body === undefined ? { Accept: 'application/json' } : { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    cleanup();
    if (timedOut()) throw new ApiError(0, 'CLIENT_TIMEOUT', `${method} ${path}: no response within ${opts.timeoutMs ?? 20000} ms`);
    if (opts.signal?.aborted) throw new ApiError(0, 'ABORTED', 'aborted');
    throw new ApiError(0, 'NETWORK', e instanceof Error ? e.message : String(e));
  }
  let text = '';
  try {
    text = await r.text();
  } catch (e) {
    cleanup();
    if (opts.signal?.aborted) throw new ApiError(0, 'ABORTED', 'aborted');
    throw new ApiError(r.status, 'NETWORK', e instanceof Error ? e.message : String(e));
  }
  cleanup();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }
  if (!r.ok) {
    const err = (json as WireError | null)?.error;
    if (err && typeof err.code === 'string') throw new ApiError(r.status, err.code, String(err.message ?? ''), err.details);
    // Vite's proxy answers 500/502/504 with a non-JSON body when the target is down.
    const code = r.status >= 500 ? 'NETWORK' : `HTTP_${r.status}`;
    throw new ApiError(r.status, code, text.slice(0, 300) || r.statusText);
  }
  if (json === null || typeof json !== 'object') throw new ApiError(r.status, 'BAD_RESPONSE', `${method} ${path}: response is not JSON`);
  return json as T;
}

export const api = {
  health: (opts?: RequestOpts) => request<WireHealth>('GET', '/health', undefined, { timeoutMs: 5000, ...opts }),
  regions: (opts?: RequestOpts) => request<WireRegionList>('GET', '/regions', undefined, opts),
  forecast: (region: string, inputTime: string, onlyNonzero = true, opts?: RequestOpts) =>
    request<WireForecastCollection>(
      'GET',
      `/regions/${encodeURIComponent(region)}/forecast?input_time=${encodeURIComponent(inputTime)}&only_nonzero=${onlyNonzero}`,
      undefined,
      { timeoutMs: 30000, ...opts },
    ),
  submitRouteCheck: (body: WireRouteCheckRequest, opts?: RequestOpts) => request<WireJobAccepted>('POST', '/route-checks', body, opts),
  routeCheck: (jobId: string, opts?: RequestOpts) => request<WireRouteCheckJob>('GET', `/route-checks/${encodeURIComponent(jobId)}`, undefined, opts),
  submitDispatch: (body: WireDispatchPlanRequest, opts?: RequestOpts) => request<WireJobAccepted>('POST', '/dispatch-plans', body, opts),
  dispatch: (jobId: string, opts?: RequestOpts) => request<WireDispatchPlanJob>('GET', `/dispatch-plans/${encodeURIComponent(jobId)}`, undefined, opts),
};

export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new ApiError(0, 'ABORTED', 'aborted'));
    const t = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(new ApiError(0, 'ABORTED', 'aborted'));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

interface PollOpts {
  signal?: AbortSignal;
  /** first poll delay; later polls back off to maxIntervalMs */
  intervalMs?: number;
  maxIntervalMs?: number;
  /** overall wait limit (the API itself enforces the 30 s compute budget per check) */
  timeoutMs?: number;
  /**
   * how often (ms) a job that is still queued/running is checked against GET /health: after an API
   * restart, jobs that were queued or running at shutdown are served from job.json frozen at that
   * status and never finish. When /health reports no queued or running work twice in a row while
   * the job still is not finished, the wait ends with JOB_FROZEN (shown as unresolved, never safe).
   */
  frozenCheckMs?: number;
}

/** API error code (client side) of a job frozen by an API restart. */
export const JOB_FROZEN = 'JOB_FROZEN';

/** True when GET /health says the API process holds queued or running work (unknown → true). */
export async function apiHasLiveWork(opts: RequestOpts = {}): Promise<boolean> {
  let h: WireHealth;
  try {
    h = await api.health(opts);
  } catch (e) {
    if (isAbort(e)) throw e;
    return true; // cannot tell: keep waiting
  }
  const rec = h as unknown as Record<string, unknown>;
  const jobs = rec.jobs && typeof rec.jobs === 'object' ? (rec.jobs as Record<string, unknown>) : {};
  // only job counts by state (real API: jobs.queued / jobs.running) can say "no live work"; the
  // MOCK counts jobs by kind, and a health without state counts cannot tell
  if (!('queued' in jobs) && !('running' in jobs)) return true;
  return Boolean(rec.queued_tasks) || Boolean(jobs.queued) || Boolean(jobs.running);
}

async function poll<T extends { status: string }>(get: (o: RequestOpts) => Promise<T>, onUpdate: ((job: T) => void) | undefined, opts: PollOpts): Promise<T> {
  const start = Date.now();
  let interval = opts.intervalMs ?? 400;
  const maxInterval = opts.maxIntervalMs ?? 3000;
  const limit = opts.timeoutMs ?? 6 * 3600 * 1000;
  let transientFailures = 0;
  const frozenEvery = opts.frozenCheckMs ?? 30000;
  let lastFrozenCheck = start;
  let idleHealth = 0;
  for (;;) {
    let job: T;
    try {
      job = await get({ signal: opts.signal, timeoutMs: 15000 });
      transientFailures = 0;
    } catch (e) {
      // a busy API may drop a poll; retry a few times before giving up
      if (e instanceof ApiError && (e.code === 'NETWORK' || e.code === 'CLIENT_TIMEOUT' || e.status >= 500) && transientFailures < 5) {
        transientFailures += 1;
        await sleep(Math.min(maxInterval * 2, 1000 * 2 ** transientFailures), opts.signal);
        continue;
      }
      throw e;
    }
    onUpdate?.(job);
    if (job.status === 'done' || job.status === 'failed') return job;
    if (Date.now() - start > limit) throw new ApiError(0, 'CLIENT_TIMEOUT', `job not finished after ${Math.round(limit / 1000)} s`);
    if (frozenEvery > 0 && Date.now() - lastFrozenCheck >= frozenEvery) {
      lastFrozenCheck = Date.now();
      // the job could finish between its poll and /health: the next poll re-reads it first
      if (await apiHasLiveWork({ signal: opts.signal })) idleHealth = 0;
      else idleHealth += 1;
      if (idleHealth >= 2) {
        const again = await get({ signal: opts.signal, timeoutMs: 15000 });
        onUpdate?.(again);
        if (again.status === 'done' || again.status === 'failed') return again;
        throw new ApiError(410, JOB_FROZEN, `job still '${again.status}' while the API reports no queued or running work (API restarted?)`);
      }
    }
    await sleep(interval, opts.signal);
    interval = Math.min(maxInterval, Math.round(interval * 1.5));
  }
}

export function waitRouteCheck(jobId: string, onUpdate?: (job: WireRouteCheckJob) => void, opts: PollOpts = {}): Promise<WireRouteCheckJob> {
  return poll((o) => api.routeCheck(jobId, o), onUpdate, opts);
}

export function waitDispatch(jobId: string, onUpdate?: (job: WireDispatchPlanJob) => void, opts: PollOpts = {}): Promise<WireDispatchPlanJob> {
  return poll((o) => api.dispatch(jobId, o), onUpdate, { maxIntervalMs: 4000, ...opts });
}

/** Runs async tasks with a fixed concurrency (in the given order). */
export async function runPool<T>(items: T[], concurrency: number, worker: (item: T, index: number) => Promise<void>, signal?: AbortSignal): Promise<void> {
  let next = 0;
  const lanes = Array.from({ length: Math.max(1, Math.min(concurrency, items.length)) }, async () => {
    while (next < items.length) {
      if (signal?.aborted) return;
      const i = next++;
      await worker(items[i]!, i);
    }
  });
  await Promise.all(lanes);
}
