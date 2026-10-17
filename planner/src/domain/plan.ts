/**
 * Pure planning functions (no I/O, no wire format). Unit-tested in tests/planner/plan.test.ts.
 *
 * Honesty rules applied here (ARCHITECTURE.md §0.4, §6; contract v1.4):
 * - a departure offset is `checked_route` if ANY candidate destination is checked,
 *   `model_no_route` only if EVERY attempted destination is `model_no_route`, else `unresolved`;
 * - the departure deadline (latestSafeDepartureS) is the latest offset whose cell is
 *   `checked_route`; unresolved cells never count toward it;
 * - the contiguous deadline follows the contract's `latest_contiguous_checked_depart_offset_s`:
 *   the last offset such that every checked-for offset from the earliest up to it is checked;
 * - offsets whose recorded destination window cannot be met are skipped (no check, "시간창 밖"),
 *   never counted as safe and never counted in a verdict.
 */
import type {
  Attempt,
  CheckSpec,
  DispatchGroup,
  LocationRef,
  OriginPlan,
  Place,
  SkipReason,
  SweepCell,
  Verdict,
  VerdictWindow,
} from './types';

export { kstClock, kstDate, kstDateTime, formatElapsed, formatRelative, compactUtc, parseUtc } from './clock';

/** Official contract limits for POST /dispatch-plans (attempts: v1.4 TOO_MANY_ATTEMPTS). */
export const CONTRACT_LIMITS = { origins: 200, destinations: 20, offsets: 24, attempts: 4800 } as const;

export type DispatchLimits = { origins: number; destinations: number; offsets: number; attempts: number };

export const ALLOWED_STEPS_MIN = [5, 10, 15, 20, 30] as const;
export const DEFAULT_STEP_MIN = 10;
export const DEFAULT_SHELTERS_PER_ORIGIN = 3;
export const DEFAULT_DWELL_S = 120;
/** API lon/lat snap limit (m); OSM places are sent by entry node, so it applies only to lon/lat input. */
export const SNAP_LIMIT_M = 300;
/** No accepted road node within this distance → 점검 불가 (ARCHITECTURE.md §4.2). */
export const ENTRY_LIMIT_M = 2000;
/** Recorded scenario window (ARCHITECTURE.md §1): 0–3600 s after the input time. */
export const RECORDED_HORIZON_S = 3600;

export function normalizeStepMin(v: unknown): number {
  const n = Number(v);
  return (ALLOWED_STEPS_MIN as readonly number[]).includes(n) ? n : DEFAULT_STEP_MIN;
}

export function normalizeShelterCount(v: unknown): number {
  const n = Math.round(Number(v));
  return Number.isFinite(n) && n >= 1 && n <= 5 ? n : DEFAULT_SHELTERS_PER_ORIGIN;
}

/** Grid offsets every `stepMin` minutes over [0, horizonS). */
export function gridOffsets(horizonS: number, stepMin: number): number[] {
  const step = Math.max(1, Math.round(stepMin * 60));
  const out: number[] = [];
  for (let t = 0; t < horizonS; t += step) out.push(t);
  return out;
}

/**
 * Departure offsets: the grid over [0, horizonS) plus extra recorded offsets (e.g. the recorded
 * research departures 300 s / 600 s), de-duplicated, sorted, restricted to [0, horizonS).
 */
export function departureOffsets(horizonS: number, stepMin: number, extraS: number[] = []): number[] {
  const set = new Set<number>(gridOffsets(horizonS, stepMin));
  for (const x of extraS) {
    if (Number.isFinite(x) && x >= 0 && x < horizonS) set.add(Math.round(x));
  }
  return [...set].sort((a, b) => a - b);
}

/** Offsets of the scenario: grid plus the recorded departure of each research origin of that scenario. */
export function scenarioOffsets(horizonS: number, stepMin: number, origins: Place[], scenarioSetId: string): number[] {
  const extra = origins
    .filter((p) => p.role === 'research_origin' && p.scenarioSetId === scenarioSetId && p.recorded)
    .map((p) => p.recorded!.departOffsetS);
  return departureOffsets(horizonS, stepMin, extra);
}

/** Offsets checked for one origin: the grid, plus the recorded departure for a research origin. */
export function originOffsets(place: Place, horizonS: number, stepMin: number): number[] {
  const extra = place.role === 'research_origin' && place.recorded ? [place.recorded.departOffsetS] : [];
  return departureOffsets(horizonS, stepMin, extra);
}

/** Drawn zones sweep window: [0, max arrival_h_max × 3600). */
export function drawnHorizonS(arrivalHoursMax: number[]): number {
  const m = Math.max(0, ...arrivalHoursMax.filter((h) => Number.isFinite(h) && h > 0));
  return m * 3600;
}

/**
 * True when no arrival can satisfy the destination window from this departure offset
 * (the API's 422 WINDOW_UNSATISFIABLE rule): max(offset, open) + dwell > min(close, horizon).
 */
export function windowUnsatisfiable(offsetS: number, window: [number, number], dwellS: number, horizonS: number | null): boolean {
  const close = horizonS === null ? window[1] : Math.min(window[1], horizonS);
  return Math.max(offsetS, window[0]) + dwellS > close;
}

/** Contract best-verdict rule over a set of verdicts (one offset or all offsets). */
export function combineVerdicts(verdicts: Verdict[]): Verdict {
  if (verdicts.length === 0) return 'unresolved';
  if (verdicts.some((v) => v === 'checked_route')) return 'checked_route';
  if (verdicts.every((v) => v === 'model_no_route')) return 'model_no_route';
  return 'unresolved';
}

export function cellVerdict(attempts: Attempt[]): Verdict {
  return combineVerdicts(attempts.map((a) => a.verdict));
}

/** Earliest-arrival checked attempt (ties → destination id). */
export function bestCheckedAttempt(attempts: Attempt[]): Attempt | undefined {
  const checked = attempts.filter((a) => a.verdict === 'checked_route');
  checked.sort((a, b) => {
    const aa = a.arrivalS ?? Number.POSITIVE_INFINITY;
    const bb = b.arrivalS ?? Number.POSITIVE_INFINITY;
    return aa - bb || a.destinationId.localeCompare(b.destinationId);
  });
  return checked[0];
}

/**
 * One cell per offset (every offset listed, every offset an attempt carries, every skipped
 * offset). A skipped offset with no attempt keeps its skip reason and verdict 'unresolved'.
 */
export function buildSweep(offsetsS: number[], attempts: Attempt[], skipped: Record<number, SkipReason> = {}): SweepCell[] {
  const offsets = new Set<number>(offsetsS);
  for (const a of attempts) offsets.add(a.offsetS);
  for (const k of Object.keys(skipped)) offsets.add(Number(k));
  return [...offsets]
    .sort((a, b) => a - b)
    .map((offsetS) => {
      const here = attempts.filter((a) => a.offsetS === offsetS);
      const best = bestCheckedAttempt(here);
      const cell: SweepCell = { offsetS, verdict: cellVerdict(here), attempts: here };
      if (best) cell.best = best;
      const skip = skipped[offsetS];
      if (skip && here.length === 0) cell.skipped = skip;
      return cell;
    });
}

/** Latest offset with a checked route; unresolved and skipped cells are ignored (never safe). */
export function latestSafeDeparture(sweep: SweepCell[]): number | null {
  let latest: number | null = null;
  for (const c of sweep) {
    if (c.verdict === 'checked_route' && (latest === null || c.offsetS > latest)) latest = c.offsetS;
  }
  return latest;
}

/**
 * Contract v1.4 `latest_contiguous_checked_depart_offset_s`: walk the checked-for offsets from the
 * earliest; stop at the first one without a checked route. Skipped offsets (no request was sent)
 * are not requested offsets and are left out, as in the API. Cells with no attempts at all
 * (not computed) break the run: an unknown cell is never assumed safe.
 */
export function contiguousSafeDeparture(sweep: SweepCell[]): number | null {
  const cells = [...sweep].filter((c) => !c.skipped).sort((a, b) => a.offsetS - b.offsetS);
  let latest: number | null = null;
  for (const c of cells) {
    if (c.verdict !== 'checked_route') break;
    latest = c.offsetS;
  }
  return latest;
}

/** Merge consecutive cells with the same verdict into windows (toS = last offset of the run). */
export function verdictWindows(sweep: SweepCell[]): VerdictWindow[] {
  const sorted = [...sweep].sort((a, b) => a.offsetS - b.offsetS);
  const out: VerdictWindow[] = [];
  for (const c of sorted) {
    const last = out[out.length - 1];
    const skipped = Boolean(c.skipped);
    if (last && last.verdict === c.verdict && Boolean(last.skipped) === skipped) last.toS = c.offsetS;
    else out.push(skipped ? { verdict: c.verdict, fromS: c.offsetS, toS: c.offsetS, skipped: true } : { verdict: c.verdict, fromS: c.offsetS, toS: c.offsetS });
  }
  return out;
}

export function planFromAttempts(args: {
  originId: string;
  offsetsS: number[];
  attempts: Attempt[];
  source: 'cache' | 'live';
  mock: boolean;
  skipped?: Record<number, SkipReason>;
}): OriginPlan {
  const sweep = buildSweep(args.offsetsS, args.attempts, args.skipped ?? {});
  const latest = latestSafeDeparture(sweep);
  const bestVerdict = combineVerdicts(args.attempts.map((a) => a.verdict));
  const plan: OriginPlan = {
    originId: args.originId,
    latestSafeDepartureS: latest,
    contiguousSafeDepartureS: contiguousSafeDeparture(sweep),
    bestVerdict,
    sweep,
    windows: verdictWindows(sweep),
    source: args.source,
    mock: args.mock,
  };
  if (latest !== null) {
    const best = sweep.find((c) => c.offsetS === latest)?.best;
    if (best) plan.best = best;
  }
  return plan;
}

/** Plan of an origin the API was never asked about: every offset unresolved, never safe. */
export function unresolvedPlan(
  originId: string,
  offsetsS: number[],
  note: 'not_checkable' | 'rejected' | 'not_computed',
  source: 'cache' | 'live',
  mock: boolean,
): OriginPlan {
  const sweep: SweepCell[] = [...new Set(offsetsS)].sort((a, b) => a - b).map((offsetS) => ({ offsetS, verdict: 'unresolved', attempts: [] }));
  return {
    originId,
    latestSafeDepartureS: null,
    contiguousSafeDepartureS: null,
    bestVerdict: 'unresolved',
    sweep,
    windows: verdictWindows(sweep),
    source,
    mock,
    note,
  };
}

/**
 * Headline for the selected origin. `caveat` is set when the contiguous deadline differs from the
 * deadline or is null: earlier departures include offsets without a checked route.
 */
export interface DeadlineHeadline {
  kind: 'deadline' | 'no_route' | 'unresolved';
  deadlineS: number | null;
  caveat: { contiguousS: number | null } | null;
}

export function deadlineHeadline(plan: OriginPlan | null | undefined): DeadlineHeadline {
  if (!plan || plan.bestVerdict === 'unresolved' || plan.latestSafeDepartureS === null) {
    if (plan && plan.bestVerdict === 'model_no_route') return { kind: 'no_route', deadlineS: null, caveat: null };
    return { kind: 'unresolved', deadlineS: null, caveat: null };
  }
  if (plan.bestVerdict === 'model_no_route') return { kind: 'no_route', deadlineS: null, caveat: null };
  const contiguous = plan.contiguousSafeDepartureS;
  const caveat = contiguous === null || contiguous !== plan.latestSafeDepartureS ? { contiguousS: contiguous } : null;
  return { kind: 'deadline', deadlineS: plan.latestSafeDepartureS, caveat };
}

const VERDICT_RANK: Record<Verdict, number> = { model_no_route: 0, unresolved: 1, checked_route: 2 };

export interface UrgencyItem {
  id: string;
  name: string;
  vulnerable: boolean;
  plan?: OriginPlan | null;
}

/**
 * Urgency order: origins whose results are only model_no_route first, then origins with no
 * checked route (unresolved), then checked origins by the contiguous deadline ascending (fallback:
 * the latest safe departure when the contiguous one is null); ties put vulnerable facilities first,
 * then name, then id.
 */
export function compareUrgency(a: UrgencyItem, b: UrgencyItem): number {
  const va: Verdict = a.plan?.bestVerdict ?? 'unresolved';
  const vb: Verdict = b.plan?.bestVerdict ?? 'unresolved';
  if (VERDICT_RANK[va] !== VERDICT_RANK[vb]) return VERDICT_RANK[va] - VERDICT_RANK[vb];
  if (va === 'checked_route') {
    const la = a.plan?.contiguousSafeDepartureS ?? a.plan?.latestSafeDepartureS ?? Number.POSITIVE_INFINITY;
    const lb = b.plan?.contiguousSafeDepartureS ?? b.plan?.latestSafeDepartureS ?? Number.POSITIVE_INFINITY;
    if (la !== lb) return la - lb;
  }
  if (a.vulnerable !== b.vulnerable) return a.vulnerable ? -1 : 1;
  const n = a.name.localeCompare(b.name, 'ko');
  return n !== 0 ? n : a.id.localeCompare(b.id);
}

export function sortByUrgency<T extends UrgencyItem>(items: T[]): T[] {
  return [...items].sort(compareUrgency);
}

/** Great-circle distance in metres (WGS84 mean radius). */
export function haversineM(a: [number, number], b: [number, number]): number {
  const toRad = Math.PI / 180;
  const [lon1, lat1] = [a[0] * toRad, a[1] * toRad];
  const [lon2, lat2] = [b[0] * toRad, b[1] * toRad];
  const h = Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2;
  return 2 * 6371008.8 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Road node a place starts or ends at: its entry node (진입 지점), else its recorded/snap node. */
export function placeNode(p: Place): string | null {
  return p.entry?.node ?? p.snapNode;
}

/**
 * K nearest checkable destinations by straight-line distance between the OSM points (ties → id).
 * A destination that shares the origin's road node is never paired (START_EQUALS_DESTINATION).
 */
export function kNearestDestinations(origin: Place, destinations: Place[], k: number): Place[] {
  const o: [number, number] = [origin.lon, origin.lat];
  const node = placeNode(origin);
  return destinations
    .filter((d) => d.checkable && (node === null || placeNode(d) !== node))
    .map((d) => ({ d, dist: haversineM(o, [d.lon, d.lat]) }))
    .sort((x, y) => x.dist - y.dist || x.d.id.localeCompare(y.d.id))
    .slice(0, Math.max(0, k))
    .map((x) => x.d);
}

function chunk<T>(xs: T[], size: number): T[][] {
  const n = Math.max(1, Math.floor(size));
  const out: T[][] = [];
  for (let i = 0; i < xs.length; i += n) out.push(xs.slice(i, i + n));
  return out;
}

/**
 * Group checkable origins by their identical K-nearest destination set and split each group into
 * dispatch requests within the contract limits (≤ 200 origins, ≤ 20 destinations, ≤ 24 offsets,
 * origins × destinations × offsets ≤ 4800). Every origin × destination × offset of the group is
 * still covered exactly once. Non-checkable origins are never sent.
 */
export function groupDispatch(
  origins: Place[],
  destinations: Place[],
  k: number,
  offsetsS: number[],
  limits: DispatchLimits = CONTRACT_LIMITS,
): DispatchGroup[] {
  const groups = new Map<string, { destinationIds: string[]; originIds: string[] }>();
  for (const o of origins) {
    if (!o.checkable) continue;
    const near = kNearestDestinations(o, destinations, k).map((d) => d.id).sort();
    if (near.length === 0) continue;
    const key = near.join('\u0000');
    const g = groups.get(key);
    if (g) g.originIds.push(o.id);
    else groups.set(key, { destinationIds: near, originIds: [o.id] });
  }
  const offsets = [...new Set(offsetsS)].sort((a, b) => a - b);
  const out: DispatchGroup[] = [];
  const keys = [...groups.keys()].sort();
  for (const key of keys) {
    const g = groups.get(key)!;
    for (const ds of chunk(g.destinationIds, limits.destinations)) {
      for (const ts of chunk(offsets, limits.offsets)) {
        const perOrigin = ds.length * ts.length;
        const originCap = Math.max(1, Math.min(limits.origins, Math.floor(limits.attempts / Math.max(1, perOrigin))));
        for (const os of chunk(g.originIds, originCap)) {
          out.push({ originIds: os, destinationIds: ds, offsetsS: ts });
        }
      }
    }
  }
  return out;
}

/** Total number of single checks (attempts) a set of dispatch groups asks for. */
export function countAttempts(groups: DispatchGroup[]): number {
  return groups.reduce((n, g) => n + g.originIds.length * g.destinationIds.length * g.offsetsS.length, 0);
}

/**
 * Location sent to the API: the entry node (진입 지점) as {node_id} for OSM places, the recorded
 * node for research points; lon/lat only for data without an entry node (the API then snaps ≤ 300 m).
 */
export function placeLocation(p: Place): LocationRef {
  const node = placeNode(p);
  if (node) return { kind: 'node', nodeId: node };
  return { kind: 'lonlat', lon: p.lon, lat: p.lat };
}

/**
 * Single route checks for a recorded research origin: its recorded destination node, dwell,
 * window, incurred dose and limits, at every offset; offsets whose window cannot be met are
 * returned in `skipped` and never sent.
 */
export function researchCheckSpecs(
  place: Place,
  offsetsS: number[],
  horizonS: number,
): { specs: CheckSpec[]; skipped: Record<number, SkipReason> } {
  const rec = place.recorded;
  const specs: CheckSpec[] = [];
  const skipped: Record<number, SkipReason> = {};
  const startNode = placeNode(place);
  if (!rec || !startNode) return { specs, skipped };
  const horizon = rec.horizonS ?? horizonS;
  for (const off of [...new Set(offsetsS)].sort((a, b) => a - b)) {
    if (windowUnsatisfiable(off, rec.destinationWindow, rec.dwellS, horizon)) {
      skipped[off] = 'window_unsatisfiable';
      continue;
    }
    specs.push({
      originId: place.id,
      destinationId: rec.destinationId,
      offsetS: off,
      start: { kind: 'node', nodeId: startNode },
      destination: { kind: 'node', nodeId: rec.destinationNode },
      dwellS: rec.dwellS,
      window: [rec.destinationWindow[0], rec.destinationWindow[1]],
      policy: 'full',
      limits: rec.limits,
      incurredDoseKjM2: rec.incurredDoseKjM2,
    });
  }
  return { specs, skipped };
}

/** Single route checks for an OSM origin against its K nearest shelters (window [0, horizon], dwell 120). */
export function osmCheckSpecs(place: Place, shelters: Place[], offsetsS: number[], horizonS: number): CheckSpec[] {
  if (!place.checkable) return [];
  const specs: CheckSpec[] = [];
  for (const off of [...new Set(offsetsS)].sort((a, b) => a - b)) {
    if (windowUnsatisfiable(off, [0, horizonS], DEFAULT_DWELL_S, horizonS)) continue;
    for (const d of shelters) {
      specs.push({
        originId: place.id,
        destinationId: d.id,
        offsetS: off,
        start: placeLocation(place),
        destination: placeLocation(d),
        dwellS: DEFAULT_DWELL_S,
        window: [0, horizonS],
        policy: 'full',
        limits: null,
        incurredDoseKjM2: null,
      });
    }
  }
  return specs;
}

/**
 * Coarse-to-fine order of offsets so a progressive recompute fills the timeline evenly:
 * first, last, then repeated bisection (breadth first). Every offset appears exactly once.
 */
export function coarseToFine(offsetsS: number[]): number[] {
  const xs = [...new Set(offsetsS)].sort((a, b) => a - b);
  if (xs.length <= 2) return xs;
  const out: number[] = [xs[0]!, xs[xs.length - 1]!];
  const seen = new Set<number>([0, xs.length - 1]);
  let intervals: [number, number][] = [[0, xs.length - 1]];
  while (intervals.length) {
    const next: [number, number][] = [];
    for (const [lo, hi] of intervals) {
      if (hi - lo < 2) continue;
      const mid = Math.floor((lo + hi) / 2);
      if (!seen.has(mid)) {
        seen.add(mid);
        out.push(xs[mid]!);
      }
      next.push([lo, mid], [mid, hi]);
    }
    intervals = next;
  }
  return out;
}

/** Summary counts by best verdict (unresolved includes origins without a result). */
export function summarize(plans: (OriginPlan | undefined | null)[]): Record<Verdict, number> {
  const out: Record<Verdict, number> = { checked_route: 0, model_no_route: 0, unresolved: 0 };
  for (const p of plans) out[p?.bestVerdict ?? 'unresolved'] += 1;
  return out;
}

/** Position of a vehicle along a timed polyline at scenario time t (s after input time). */
export function positionAt(coords: [number, number][], timesS: number[], t: number): [number, number] | null {
  const n = Math.min(coords.length, timesS.length);
  if (n === 0) return null;
  if (t <= timesS[0]!) return coords[0]!;
  if (t >= timesS[n - 1]!) return coords[n - 1]!;
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (timesS[mid]! <= t) lo = mid;
    else hi = mid;
  }
  const t0 = timesS[lo]!;
  const t1 = timesS[hi]!;
  const f = t1 > t0 ? (t - t0) / (t1 - t0) : 0;
  const a = coords[lo]!;
  const b = coords[hi]!;
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
}
