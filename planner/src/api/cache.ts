/**
 * Precompute cache (planner/cache/**, written by planner/scripts/precompute.py, served at /cache/**).
 * Loads INDEX.json and one cache file into the internal model:
 * - dispatch plans' attempts → per-origin sweeps (null entries — dispatch plans the API refused at
 *   submission — are skipped; their origins come from `rejected_requests`);
 * - re-checks (route_checks entries with `recheck_of`, precompute --recheck-timeouts) replace the
 *   attempt they re-ran, so the cell, deadline and evidence all show the same check;
 * - research_checks → sweeps built from the route_checks results; only offsets precompute skipped
 *   locally as WINDOW_UNSATISFIABLE (never sent) become distinct "시간창 밖" cells (no check, grey,
 *   never safe); every request the API refused — WINDOW_UNSATISFIABLE included, recognised by its
 *   entry in rejected_requests — is an unresolved attempt with the API's code (it breaks the
 *   contiguous run);
 * - travel_only comparison checks;
 * - provenance: api.mode, created_at, generator.client_host and each result's provenance.host;
 *   results from a host other than the evaluated Apple-silicon macOS host are marked test data.
 */
import type { WireCacheFile, WireCacheRejected, WireCacheIndexEntry, WireDispatchPlanJob, WireDispatchPlanRequest, WireRouteCheckJob } from './wire';
import type { CacheData, CacheEntry, CacheMeta, HostInfo, OriginPlan, RouteDetail, SkipReason, Attempt } from '../domain/types';
import { adaptDispatchJob, adaptHealth, adaptHost, adaptRouteJob, attemptFromRoute, isMockHealth } from './adapter';
import { planFromAttempts, unresolvedPlan } from '../domain/plan';

/** Dispatch-plan jobs of a cache file; refused requests are stored as null and skipped here. */
function planJobs(doc: WireCacheFile): WireDispatchPlanJob[] {
  return (doc.plans ?? []).filter((j): j is WireDispatchPlanJob => !!j && typeof j === 'object');
}

/**
 * The evaluated booth host (ARCHITECTURE.md §6): native macOS on Apple silicon. The API reports
 * only platform/machine, so the chip ("M5 Pro") cannot be verified — the test is macOS + arm64.
 */
export function isEvaluationHost(h: HostInfo | null | undefined): boolean {
  if (!h || h.recorded) return false;
  const plat = `${h.platform ?? ''} ${h.os ?? ''}`;
  return (/(^|\s)macOS/.test(plat) || plat.includes('Darwin')) && h.machine === 'arm64';
}

/** Test data = a real (non-MOCK, non-recorded) result from another host, or an unknown host. */
export function isTestDataHost(h: HostInfo | null | undefined, mock: boolean): boolean {
  if (mock) return false;
  if (h?.recorded) return false;
  return !isEvaluationHost(h);
}

export const CACHE_BASE = '/cache';

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === 'string' && v.length > 0 ? v : null;
}

export function parseCacheIndex(raw: unknown): CacheEntry[] {
  const list = Array.isArray(raw) ? raw : raw && typeof raw === 'object' && Array.isArray((raw as { entries?: unknown }).entries) ? (raw as { entries: unknown[] }).entries : [];
  const out: CacheEntry[] = [];
  for (const e of list as Partial<WireCacheIndexEntry>[]) {
    if (!e || !str(e.region_id) || !str(e.scenario_set_id) || !str(e.path)) continue;
    out.push({
      regionId: String(e.region_id),
      scenarioSetId: String(e.scenario_set_id),
      inputTime: String(e.input_time ?? ''),
      path: String(e.path),
      apiMode: String(e.api_mode ?? 'unknown'),
      createdAt: String(e.created_at ?? ''),
      origins: num(e.origins) ?? 0,
      bytes: num(e.bytes) ?? 0,
      sha256: String(e.sha256 ?? ''),
    });
  }
  return out;
}

/** INDEX.json; a missing cache is normal (returns []). */
export async function loadCacheIndex(signal?: AbortSignal): Promise<CacheEntry[]> {
  try {
    const r = await fetch(`${CACHE_BASE}/INDEX.json`, { signal, cache: 'no-cache', headers: { Accept: 'application/json' } });
    if (!r.ok) return [];
    if ((r.headers.get('content-type') ?? '').includes('text/html')) return [];
    return parseCacheIndex(await r.json());
  } catch {
    return [];
  }
}

export function findCacheEntry(index: CacheEntry[], regionId: string, scenarioSetId: string): CacheEntry | null {
  return index.find((e) => e.regionId === regionId && e.scenarioSetId === scenarioSetId) ?? null;
}

function firstHost(doc: WireCacheFile): HostInfo | null {
  const top = adaptHost(doc.api?.host);
  if (top) return top;
  for (const job of Object.values(doc.route_checks ?? {})) {
    const d = adaptRouteJob(job);
    if (d.provenance?.host) return d.provenance.host;
  }
  for (const job of planJobs(doc)) {
    const h = adaptDispatchJob(job, 'cache').provenance?.host;
    if (h) return h;
  }
  const h = doc.api?.health ? adaptHealth(doc.api.health).host : null;
  return h ?? null;
}

function rejectCode(err: unknown): { code: string; message: string } {
  if (err && typeof err === 'object') {
    const e = (err as { error?: { code?: unknown; message?: unknown } }).error;
    if (e && typeof e === 'object') return { code: String(e.code ?? 'REJECTED'), message: String(e.message ?? '') };
  }
  return { code: 'REJECTED', message: typeof err === 'string' ? err : '' };
}

/** Internal model of a parsed cache document. */
export function cacheToModel(doc: WireCacheFile, entry: CacheEntry): CacheData {
  const generator = (doc.generator ?? {}) as Record<string, unknown>;
  const health = doc.api?.health ? adaptHealth(doc.api.health) : null;
  const plans: Record<string, OriginPlan> = {};
  // route checks by their OWN job id; re-checks by the id of the check they re-ran. Older files
  // stored a re-check under the original id (the original is then gone and is not served).
  const jobs: Record<string, WireRouteCheckJob> = {};
  const rechecks: Record<string, WireRouteCheckJob> = {};
  for (const [key, job] of Object.entries(doc.route_checks ?? {})) {
    if (!job || typeof job !== 'object') continue;
    const of = typeof job.recheck_of === 'string' && job.recheck_of ? job.recheck_of : null;
    if (of) {
      rechecks[of] = job;
      if (job.job_id) jobs[job.job_id] = job;
      if (key !== of && !(key in jobs)) jobs[key] = job;
    } else {
      if (!(key in jobs)) jobs[key] = job;
      if (job.job_id && !(job.job_id in jobs)) jobs[job.job_id] = job;
    }
  }
  const recheckAttempt = (a: Attempt): Attempt => {
    const rj = a.jobId ? rechecks[a.jobId] : undefined;
    if (!rj) return a;
    return { ...attemptFromRoute(adaptRouteJob(rj), a.destinationId, a.offsetS), recheckOf: a.jobId };
  };
  const withRechecks = (p: OriginPlan): OriginPlan => {
    const attempts = p.sweep.flatMap((c) => c.attempts);
    if (!attempts.some((a) => a.jobId && rechecks[a.jobId])) return p;
    const out = planFromAttempts({ originId: p.originId, offsetsS: p.sweep.map((c) => c.offsetS), attempts: attempts.map(recheckAttempt), source: p.source, mock: p.mock });
    if (p.apiSnap) out.apiSnap = p.apiSnap;
    return out;
  };
  let anyMock = doc.api?.mode === 'mock' || isMockHealth(doc.api?.health);

  // Dispatch plans (OSM origins).
  const offsets = new Set<number>();
  let horizon: number | null = null;
  for (const req of (doc.requests ?? []) as WireDispatchPlanRequest[]) {
    for (const o of req.depart_offsets_s ?? []) offsets.add(Number(o));
    for (const d of req.destinations ?? []) {
      const w = d.window;
      if (Array.isArray(w) && w.length === 2 && Number.isFinite(Number(w[1]))) horizon = Math.max(horizon ?? 0, Number(w[1]));
    }
  }
  const offsetsS = [...offsets].sort((a, b) => a - b);
  for (const job of planJobs(doc)) {
    const a = adaptDispatchJob(job, 'cache');
    if (a.mock) anyMock = true;
    for (const p of a.plans) plans[p.originId] = withRechecks(p);
    const reqOffsets = Array.isArray(job.request?.depart_offsets_s) ? (job.request.depart_offsets_s as number[]).map(Number) : offsetsS;
    for (const r of a.rejected) {
      const plan = unresolvedPlan(r.originId, reqOffsets, 'rejected', 'cache', a.mock);
      plan.rejectReason = { code: r.code, message: r.message };
      plans[r.originId] = plan;
    }
    if (job.status === 'failed') {
      const origins = Array.isArray(job.request?.origins) ? (job.request.origins as { id: string }[]) : [];
      for (const o of origins) {
        if (plans[o.id]) continue;
        const plan = unresolvedPlan(o.id, reqOffsets, 'rejected', 'cache', a.mock);
        plan.rejectReason = a.error ?? { code: 'JOB_FAILED', message: '' };
        plans[o.id] = plan;
      }
    }
  }
  // Dispatch plans the API refused at submission (whole request rejected). Older files list
  // `origins`; newer ones keep the `request` and the error `code`.
  for (const rej of doc.rejected_requests ?? []) {
    if (rej.kind !== 'dispatch_plan') continue;
    const reqOrigins = (rej.request as { origins?: { id?: unknown }[] } | undefined)?.origins;
    const ids = Array.isArray(rej.origins) ? rej.origins : Array.isArray(reqOrigins) ? reqOrigins.map((o) => String(o.id)) : [];
    const reqOffsets = (rej.request as { depart_offsets_s?: unknown } | undefined)?.depart_offsets_s;
    const offs = Array.isArray(reqOffsets) ? reqOffsets.map(Number) : offsetsS;
    const reason = rej.code ? { code: String(rej.code), message: rejectCode(rej.error).message } : rejectCode(rej.error);
    for (const id of ids) {
      if (plans[id]) continue;
      const plan = unresolvedPlan(id, offs, 'rejected', 'cache', anyMock);
      plan.rejectReason = reason;
      plans[id] = plan;
    }
  }

  // Research origins: individual route checks per offset.
  interface ResearchSlot {
    attempts: Attempt[];
    offsets: number[];
    skipped: Record<number, SkipReason>;
    snap: RouteDetail['snap'];
    /** checks that were meant to be sent (window-unsatisfiable offsets are not) */
    sent: number;
    refused: number;
    firstRefused: string | null;
  }
  const byOrigin = new Map<string, ResearchSlot>();
  const refusedResearch = refusedResearchKeys(doc.rejected_requests ?? []);
  for (const rc of doc.research_checks ?? []) {
    const slot = byOrigin.get(rc.origin_id) ?? { attempts: [], offsets: [], skipped: {}, snap: null, sent: 0, refused: 0, firstRefused: null };
    byOrigin.set(rc.origin_id, slot);
    const off = Number(rc.depart_offset_s);
    slot.offsets.push(off);
    const job = rc.job_id ? jobs[rc.job_id] ?? rechecks[rc.job_id] : undefined;
    if (job) {
      slot.sent += 1;
      const re = rc.job_id ? rechecks[rc.job_id] : undefined;
      const d = adaptRouteJob(re ?? job);
      if (d.mock) anyMock = true;
      const a = attemptFromRoute(d, rc.destination_id, off);
      slot.attempts.push(re ? { ...a, recheckOf: rc.job_id ?? null } : a);
      if (!slot.snap && d.snap) slot.snap = d.snap;
    } else if ((rc.skipped === 'WINDOW_UNSATISFIABLE' || rc.skipped === 'window_unsatisfiable') && !refusedResearch.has(researchKey(rc.origin_id, off))) {
      // a precompute-local skip (never sent). The same code also comes back as an API 422 refusal;
      // such a request is listed in rejected_requests and falls through to the refused branch.
      slot.skipped[off] = 'window_unsatisfiable';
    } else if (rc.skipped) {
      // the API refused this request (4xx code): an unresolved, unchecked offset — never "시간창 밖"
      slot.sent += 1;
      slot.refused += 1;
      slot.firstRefused = slot.firstRefused ?? rc.skipped;
      slot.attempts.push({ offsetS: off, destinationId: rc.destination_id, verdict: 'unresolved', arrivalS: null, computeS: null, jobId: null, reasonCode: rc.skipped, rawStatus: null });
    } else {
      // listed but no result stored: unknown, shown as unresolved (never safe)
      slot.sent += 1;
      slot.attempts.push({ offsetS: off, destinationId: rc.destination_id, verdict: 'unresolved', arrivalS: null, computeS: null, jobId: null, reasonCode: null });
    }
  }
  for (const [originId, slot] of byOrigin) {
    const plan = planFromAttempts({ originId, offsetsS: slot.offsets, attempts: slot.attempts, source: 'cache', mock: anyMock, skipped: slot.skipped });
    if (slot.snap) plan.apiSnap = slot.snap.start;
    // every request of this origin was refused: say so (the cells keep each code)
    if (slot.sent > 0 && slot.refused === slot.sent) {
      plan.note = 'rejected';
      plan.rejectReason = { code: String(slot.firstRefused ?? 'REJECTED'), message: '' };
    }
    plans[originId] = plan;
  }

  const travelOnly: Record<string, RouteDetail> = {};
  for (const [originId, job] of Object.entries(doc.travel_only ?? {})) {
    if (!job || typeof job !== 'object') continue;
    const d = adaptRouteJob(job);
    // a comparison belongs to the origin's best checked attempt (same departure); drop a stale one
    const best = plans[originId]?.best;
    if (best && d.departOffsetS !== null && d.departOffsetS !== best.offsetS) continue;
    travelOnly[originId] = d;
  }

  const memo = new Map<string, RouteDetail>();
  const route = (jobId: string): RouteDetail | null => {
    const hit = memo.get(jobId);
    if (hit) return hit;
    const job = jobs[jobId];
    if (!job) return null;
    const d = adaptRouteJob(job);
    memo.set(jobId, d);
    return d;
  };

  const computeHost = firstHost(doc);
  const mock = anyMock || entry.apiMode === 'mock';
  const meta: CacheMeta = {
    entry,
    createdAt: str(doc.created_at) ?? entry.createdAt,
    apiBase: str(doc.api?.base),
    apiMode: str(doc.api?.mode) ?? entry.apiMode,
    plannerCommit: str(doc.planner_commit),
    health,
    clientHost: str(generator.client_host),
    computeHost,
    stepMin: num(generator.step_min),
    sheltersPerOrigin: num(generator.shelters_per_origin),
    wallS: num(generator.wall_s) ?? num(generator.wall_s_this_invocation),
    rejectedRequests: (doc.rejected_requests ?? []).length,
    mock,
    testData: isTestDataHost(computeHost, mock) || (!mock && generator.purpose === 'test'),
  };
  for (const p of Object.values(plans)) p.mock = meta.mock;
  return { meta, plans, route, travelOnly, offsetsS, horizonS: horizon };
}

export async function loadCacheFile(entry: CacheEntry, signal?: AbortSignal): Promise<CacheData> {
  const r = await fetch(`${CACHE_BASE}/${entry.path.split('/').map(encodeURIComponent).join('/')}`, { signal, headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`cache ${entry.path}: HTTP ${r.status}`);
  const doc = (await r.json()) as WireCacheFile;
  if (!doc || typeof doc !== 'object' || doc.region_id !== entry.regionId) throw new Error(`cache ${entry.path}: unexpected content`);
  return cacheToModel(doc, entry);
}

function researchKey(originId: string, offsetS: number): string {
  return `${originId}|${Number(offsetS)}`;
}

/**
 * (origin, offset) of research route checks the API refused. precompute writes the refusal code
 * into research_checks[].skipped, so a refused WINDOW_UNSATISFIABLE looks like a local skip there;
 * rejected_requests tells them apart (request.client_ref 'planner-precompute:<origin id>').
 */
function refusedResearchKeys(rejected: WireCacheRejected[]): Set<string> {
  const out = new Set<string>();
  for (const r of rejected) {
    if (r.kind !== 'route_check') continue;
    const req = (r.request ?? {}) as { client_ref?: unknown; depart_offset_s?: unknown };
    const ref = typeof req.client_ref === 'string' && req.client_ref.startsWith('planner-precompute:') ? req.client_ref.slice('planner-precompute:'.length) : null;
    const originId = r.origin_id ?? ref;
    const off = r.depart_offset_s ?? (typeof req.depart_offset_s === 'number' ? req.depart_offset_s : null);
    if (originId && off !== null && off !== undefined) out.add(researchKey(originId, off));
  }
  return out;
}
