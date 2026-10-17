/**
 * Precompute cache (planner/cache/**, written by planner/scripts/precompute.py, served at /cache/**).
 * Loads INDEX.json and one cache file into the internal model:
 * - dispatch plans' attempts → per-origin sweeps;
 * - research_checks → sweeps built from the route_checks results; offsets skipped as
 *   WINDOW_UNSATISFIABLE become distinct "시간창 밖" cells (no check, grey, never safe);
 * - travel_only comparison checks;
 * - provenance: api.mode, created_at, generator.client_host and each result's provenance.host.
 */
import type { WireCacheFile, WireCacheIndexEntry, WireDispatchPlanRequest, WireRouteCheckJob } from './wire';
import type { CacheData, CacheEntry, CacheMeta, HostInfo, OriginPlan, RouteDetail, SkipReason, Attempt } from '../domain/types';
import { adaptDispatchJob, adaptHealth, adaptHost, adaptRouteJob, attemptFromRoute, isMockHealth } from './adapter';
import { planFromAttempts, unresolvedPlan } from '../domain/plan';

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
  for (const job of doc.plans ?? []) {
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
  const jobs: Record<string, WireRouteCheckJob> = doc.route_checks ?? {};
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
  for (const job of doc.plans ?? []) {
    const a = adaptDispatchJob(job, 'cache');
    if (a.mock) anyMock = true;
    for (const p of a.plans) plans[p.originId] = p;
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
  const byOrigin = new Map<string, { attempts: Attempt[]; offsets: number[]; skipped: Record<number, SkipReason>; snap: RouteDetail['snap'] }>();
  for (const rc of doc.research_checks ?? []) {
    const slot = byOrigin.get(rc.origin_id) ?? { attempts: [], offsets: [], skipped: {}, snap: null };
    byOrigin.set(rc.origin_id, slot);
    const off = Number(rc.depart_offset_s);
    slot.offsets.push(off);
    const job = rc.job_id ? jobs[rc.job_id] : undefined;
    if (job) {
      const d = adaptRouteJob(job);
      if (d.mock) anyMock = true;
      slot.attempts.push(attemptFromRoute(d, rc.destination_id, off));
      if (!slot.snap && d.snap) slot.snap = d.snap;
    } else if (rc.skipped) {
      slot.skipped[off] = rc.skipped === 'WINDOW_UNSATISFIABLE' ? 'window_unsatisfiable' : rc.skipped;
    } else {
      // listed but no result stored: unknown, shown as unresolved (never safe)
      slot.attempts.push({ offsetS: off, destinationId: rc.destination_id, verdict: 'unresolved', arrivalS: null, computeS: null, jobId: null, reasonCode: null });
    }
  }
  for (const [originId, slot] of byOrigin) {
    const plan = planFromAttempts({ originId, offsetsS: slot.offsets, attempts: slot.attempts, source: 'cache', mock: anyMock, skipped: slot.skipped });
    if (slot.snap) plan.apiSnap = slot.snap.start;
    if (slot.attempts.length === 0 && Object.keys(slot.skipped).length > 0) {
      const codes = Object.values(slot.skipped).filter((c) => c !== 'window_unsatisfiable');
      if (codes.length) {
        plan.note = 'rejected';
        plan.rejectReason = { code: String(codes[0]), message: '' };
      }
    }
    plans[originId] = plan;
  }

  const travelOnly: Record<string, RouteDetail> = {};
  for (const [originId, job] of Object.entries(doc.travel_only ?? {})) travelOnly[originId] = adaptRouteJob(job);

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

  const meta: CacheMeta = {
    entry,
    createdAt: str(doc.created_at) ?? entry.createdAt,
    apiBase: str(doc.api?.base),
    apiMode: str(doc.api?.mode) ?? entry.apiMode,
    plannerCommit: str(doc.planner_commit),
    health,
    clientHost: str(generator.client_host),
    computeHost: firstHost(doc),
    stepMin: num(generator.step_min),
    sheltersPerOrigin: num(generator.shelters_per_origin),
    wallS: num(generator.wall_s) ?? num(generator.wall_s_this_invocation),
    rejectedRequests: (doc.rejected_requests ?? []).length,
    mock: anyMock || entry.apiMode === 'mock',
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
