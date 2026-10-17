/**
 * Data flow (I/O). On region + scenario selection:
 *   1. the precompute cache when INDEX.json lists the scenario set (instant, offline);
 *   2. else, when the API is reachable: dispatch plans for OSM origins (grouped by their K nearest
 *      shelters) + individual route checks for research origins, with progress. The mock answers
 *      instantly, so the batch starts by itself; against the real API the batch (hundreds of
 *      ~10 s checks) starts only after the user confirms;
 *   3. else the honest empty state.
 * Live recompute of ONE origin: one route check per offset per candidate shelter, concurrency 2,
 * coarse-to-fine order.
 *
 * The API has no cancel endpoint: "중지" only stops this browser. Submitted batch jobs are
 * remembered in memory (per API identity and request body) so "다시 시도" or coming back to the
 * scenario re-attaches to them instead of submitting the same work again. After a fatal
 * LAUNCHES_PAUSED, checks still in flight are waited for at most TAIL_AFTER_PAUSE_MS and then shown
 * as unresolved with that code (queued work never starts while launches are paused).
 *
 * Drawn spread zones (사용자 입력 확산 구역, 가정): no cache exists, nothing starts by itself.
 *   - "선택한 출발지 계산": the live recompute machinery with fire_input {type: "spread_zones"};
 *   - "구역 안·주변 마을 계산": origins inside a zone or within 2 km, grouped into dispatch plans,
 *     started only after a confirm card (count of checks + honest time bound).
 * Drawn results live in `plans` while drawn mode is shown and are tagged with the fire-input
 * fingerprint; editing the zones or settings drops them. Recorded results are stashed when the user
 * switches to drawn mode and come back when they switch back (and vice versa).
 */
import { api, ApiError, isAbort, runPool, waitDispatch, waitRouteCheck } from '../api/client';
import {
  adaptDispatchJob,
  adaptForecast,
  adaptHealth,
  adaptRegionList,
  adaptRouteJob,
  attemptFromRoute,
  toWireDispatch,
  toWireRouteCheck,
  travelOnlySpec,
  type RecordedContext,
} from '../api/adapter';
import { findCacheEntry, loadCacheFile, loadCacheIndex } from '../api/cache';
import { CONFIG } from '../config/env';
import { parseUtc } from '../domain/clock';
import {
  coarseToFine,
  countAttempts,
  gridOffsets,
  groupDispatch,
  kNearestDestinations,
  originOffsets,
  osmCheckSpecs,
  planFromAttempts,
  researchCheckSpecs,
  unresolvedPlan,
} from '../domain/plan';
import type { ApiRegion, Attempt, CacheData, CheckSpec, DispatchGroup, OriginPlan, Place, RouteDetail, SkipReason } from '../domain/types';
import { defaultPresetTimes, originsNearZones, ZONE_KEYS, zoneSummary } from '../domain/zones';
import { loadFootprints, loadPlaces, loadRegionIndex, scenarioDestinations, scenarioOrigins, type Footprint } from '../data/staticData';
import { useLangStore } from '../i18n';
import {
  currentScenarioSet,
  drawnFireInput,
  drawnFireKey,
  drawnHorizonS,
  drawnReadiness,
  horizonOf,
  recordedInputTimes,
  routeById,
  scenarioSetsOf,
} from './selectors';
import {
  DRAWN_SCENARIO,
  IDLE_BATCH,
  getState,
  setState,
  type ApiErrorInfo,
  type BatchState,
  type CellProgress,
  type DrawnDispatchInfo,
  type PlannerState,
  type SubmittedZones,
  type TravelOnlyState,
} from './store';
import { applyPreset, ensureInputTime, loadZonesForRegion, notice, onFireInputChange, setFootprints, setRightTab } from './zoneActions';

const HEALTH_POLL_MS = 15000;
/** after a fatal LAUNCHES_PAUSED: how long checks already in flight are still waited for */
export const TAIL_AFTER_PAUSE_MS = 120000;

let scenarioCtrl: AbortController | null = null;
let recomputeCtrl: AbortController | null = null;
let healthTimer: ReturnType<typeof setInterval> | null = null;
/** in-flight travel-time-only comparisons by origin (aborted on scenario / fire-input change) */
const travelCtrls = new Map<string, AbortController>();

// ---------------------------------------------------------------- submitted batch jobs (re-attach)

/** job ids of batch submissions by (API identity, kind, request body hash); in memory only */
const submittedJobs = new Map<string, string>();
let submittedApi: string | null = null;

function apiIdentity(): string {
  const h = getState().health;
  return h ? `${h.apiVersion}|${h.gitCommit}|${h.checkpoint}|${h.mock ? 'mock' : 'real'}` : 'none';
}

/** 53-bit string hash (cyrb53) — keys stay small for large request bodies. */
function hash53(str: string): string {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
}

function submissionKey(kind: 'dispatch' | 'route_check', body: unknown): string {
  return `${apiIdentity()}|${kind}|${hash53(JSON.stringify(body))}`;
}

/** Forget remembered submissions when the API identity changes (another API or a new build). */
function syncSubmittedApi(): void {
  const id = apiIdentity();
  if (submittedApi !== null && submittedApi !== id) submittedJobs.clear();
  submittedApi = id;
}

/** Test hook: forget every remembered submission. */
export function forgetSubmittedJobs(): void {
  submittedJobs.clear();
}

/**
 * Submit `body` once per API identity: a remembered job id is re-attached (polled) instead of
 * submitting the same work again; a job the API no longer knows (404) is submitted again.
 * A job that ended `failed` is forgotten, so a retry submits it again.
 */
async function submitOnceAndWait<J extends { status: string }>(
  kind: 'dispatch' | 'route_check',
  body: unknown,
  submit: () => Promise<string>,
  wait: (id: string) => Promise<J>,
  onId?: (id: string) => void,
): Promise<J> {
  const key = submissionKey(kind, body);
  let id = submittedJobs.get(key);
  if (!id) {
    id = await submit();
    submittedJobs.set(key, id);
  }
  onId?.(id);
  let job: J;
  try {
    job = await wait(id);
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 404)) throw e;
    submittedJobs.delete(key);
    id = await submit();
    submittedJobs.set(key, id);
    onId?.(id);
    job = await wait(id);
  }
  if (job.status === 'failed') submittedJobs.delete(key);
  return job;
}

// ---------------------------------------------------------------- run guard (fatal + bounded tail)

/** An AbortSignal that aborts when either input aborts. */
function linkedSignal(a: AbortSignal, b: AbortSignal): AbortSignal {
  const c = new AbortController();
  const stop = () => c.abort();
  if (a.aborted || b.aborted) c.abort();
  else {
    a.addEventListener('abort', stop, { once: true });
    b.addEventListener('abort', stop, { once: true });
  }
  return c.signal;
}

/**
 * Fatal error of a run (5xx at submission: BUSY, LAUNCHES_PAUSED, DATA_UNAVAILABLE) reported at
 * once, plus a bounded tail: after LAUNCHES_PAUSED nothing queued will start, so the checks still
 * in flight are given TAIL_AFTER_PAUSE_MS and then become unresolved with that code.
 */
class RunGuard {
  fatal: ApiErrorInfo | null = null;
  private readonly tail = new AbortController();
  private timer: ReturnType<typeof setTimeout> | null = null;
  readonly signal: AbortSignal;
  constructor(
    private readonly outer: AbortSignal,
    private readonly onFatal: (e: ApiErrorInfo) => void = () => {},
  ) {
    this.signal = linkedSignal(outer, this.tail.signal);
  }
  setFatal(e: ApiErrorInfo): void {
    if (this.fatal) return;
    this.fatal = e;
    this.onFatal(e);
    if (e.code === 'LAUNCHES_PAUSED') this.timer = setTimeout(() => this.tail.abort(), TAIL_AFTER_PAUSE_MS);
  }
  /** the tail ran out (not a user stop or a scenario change) */
  tailExpired(): boolean {
    return this.tail.signal.aborted && !this.outer.aborted;
  }
  /** unresolved code of checks cut off by the tail */
  tailCode(): ApiErrorInfo {
    return this.fatal ?? { code: 'LAUNCHES_PAUSED', message: '' };
  }
  dispose(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }
}

function errInfo(e: unknown): ApiErrorInfo {
  if (e instanceof ApiError) return { code: e.code, message: e.message, status: e.status };
  return { code: 'CLIENT_ERROR', message: e instanceof Error ? e.message : String(e) };
}

function scenarioKey(): string {
  const s = getState();
  return `${s.regionId}|${s.scenarioId}`;
}

// ---------------------------------------------------------------- URL deep links

export interface DeepLink {
  region?: string;
  scenario?: string;
  origin?: string;
  lang?: 'ko' | 'en';
  /** drawn mode: base recorded input time (input_compact or ISO) */
  input?: string;
  /** drawn mode: "footprints" applies the default recorded-footprint preset */
  preset?: string;
}

const QUERY_KEYS = ['region', 'scenario', 'origin', 'lang', 'input', 'preset'] as const;

/** Hash deep link: #region=<id>&scenario=<scenario_set_id|drawn>&origin=<place id>. */
export function readHash(): { region?: string; scenario?: string; origin?: string } {
  if (typeof window === 'undefined') return {};
  const p = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const out: { region?: string; scenario?: string; origin?: string } = {};
  const region = p.get('region');
  const scenario = p.get('scenario');
  const origin = p.get('origin');
  if (region) out.region = region;
  if (scenario) out.scenario = scenario;
  if (origin) out.origin = origin;
  return out;
}

/**
 * Query deep link (screenshot and PDF scripts): ?region=<id>&scenario=<input_compact|zones>
 * &origin=<id>&lang=ko|en (+ drawn mode: &input=<input_compact>&preset=footprints). The query wins
 * over the hash.
 */
export function readQuery(search: string = typeof window === 'undefined' ? '' : window.location.search): DeepLink {
  const p = new URLSearchParams(search);
  const out: DeepLink = {};
  for (const k of QUERY_KEYS) {
    const v = p.get(k);
    if (!v) continue;
    if (k === 'lang') {
      if (v === 'ko' || v === 'en') out.lang = v;
    } else out[k] = v;
  }
  return out;
}

/** "20250324T090000Z" / ISO → epoch ms; NaN otherwise. */
function timeParam(v: string): number {
  return /^\d{8}T\d{6}Z$/.test(v) || /^\d{4}-\d{2}-\d{2}T/.test(v) ? parseUtc(v) : Number.NaN;
}

/** scenario param → scenario set id or DRAWN_SCENARIO ("zones" / "drawn"), else null. */
export function resolveScenarioParam(param: string | null | undefined, sets: { id: string; inputTime: string }[]): string | null {
  if (!param) return null;
  if (param === DRAWN_SCENARIO || param === 'zones') return DRAWN_SCENARIO;
  if (sets.some((x) => x.id === param)) return param;
  const t = timeParam(param);
  if (Number.isFinite(t)) return sets.find((x) => parseUtc(x.inputTime) === t)?.id ?? null;
  return null;
}

/** Removes the deep-link keys from the query (keeps ?print=all etc.) so a reload follows the hash. */
function stripDeepLinkQuery(): void {
  if (typeof window === 'undefined') return;
  const url = new URL(window.location.href);
  let changed = false;
  for (const k of QUERY_KEYS) {
    if (url.searchParams.has(k)) {
      url.searchParams.delete(k);
      changed = true;
    }
  }
  if (changed) window.history.replaceState(null, '', `${url.pathname}${url.search}${window.location.hash}`);
}

function writeHash(): void {
  if (typeof window === 'undefined') return;
  const s = getState();
  const p = new URLSearchParams();
  if (s.regionId) p.set('region', s.regionId);
  if (s.scenarioId) p.set('scenario', s.scenarioId);
  if (s.selectedOriginId) p.set('origin', s.selectedOriginId);
  const next = '#' + p.toString();
  if (window.location.hash !== next) window.history.replaceState(null, '', next);
}

// ---------------------------------------------------------------- API status

export async function refreshApi(): Promise<void> {
  const before = getState().apiStatus;
  try {
    const health = adaptHealth(await api.health());
    const needRegions = Object.keys(getState().apiRegions).length === 0;
    let apiRegions = getState().apiRegions;
    if (needRegions) {
      const list = adaptRegionList(await api.regions({ timeoutMs: 15000 }));
      apiRegions = Object.fromEntries(list.map((r: ApiRegion) => [r.id, r]));
    }
    setState({ apiStatus: 'online', health, apiError: null, apiRegions });
    syncSubmittedApi();
    if (before !== 'online') onApiCameOnline();
  } catch (e) {
    setState({ apiStatus: 'offline', apiError: errInfo(e) });
  }
}

/** When the API becomes reachable after start-up, fill what was missing. */
function onApiCameOnline(): void {
  const s = getState();
  if (!s.regionId || !s.scenarioId) return;
  if (s.scenarioId === DRAWN_SCENARIO) {
    const times = recordedInputTimes(s);
    ensureInputTime(times, times[0] ?? null);
    return;
  }
  loadForecast();
  if (s.dataSource === 'none' && !s.dataLoading && s.batch.state === 'idle') prepareBatch();
}

let initStarted = false;

export async function initApp(): Promise<void> {
  if (initStarted) return; // React StrictMode runs effects twice in development
  initStarted = true;
  const hash = readHash();
  const query = readQuery();
  if (query.lang) useLangStore.getState().setLang(query.lang);
  stripDeepLinkQuery();
  const link = {
    region: query.region ?? hash.region,
    scenario: query.scenario ?? hash.scenario,
    origin: query.origin ?? hash.origin,
  };
  const [index] = await Promise.all([
    loadRegionIndex().catch((e) => {
      setState({ regionIndexError: e instanceof Error ? e.message : String(e) });
      return [];
    }),
    refreshApi(),
    loadCacheIndex().then((cacheIndex) => setState({ cacheIndex })),
  ]);
  setState({ regionIndex: index });
  if (healthTimer === null) healthTimer = setInterval(() => void refreshApi(), HEALTH_POLL_MS);
  const region = index.find((r) => r.id === link.region) ?? index.find((r) => r.demo) ?? index[0];
  if (region) {
    await selectRegion(region.id, {
      scenarioId: link.scenario,
      originId: link.origin,
      inputTime: query.input,
      preset: query.preset === 'footprints',
    });
  }
}

// ---------------------------------------------------------------- stashes (recorded ⇄ drawn)

interface RecordedStash {
  regionId: string;
  scenarioId: string;
  plans: Record<string, OriginPlan>;
  cache: CacheData | null;
  dataSource: PlannerState['dataSource'];
  batch: BatchState;
  travelOnly: Record<string, TravelOnlyState>;
}

interface DrawnStash {
  regionId: string;
  key: string;
  plans: Record<string, OriginPlan>;
  submitted: SubmittedZones | null;
  dispatch: DrawnDispatchInfo[];
  batch: BatchState;
  travelOnly: Record<string, TravelOnlyState>;
}

let recordedStash: RecordedStash | null = null;
let drawnStash: DrawnStash | null = null;

/** The recorded results kept while drawn mode is shown (plan sheet comparison row). */
export function recordedComparison(): RecordedStash | null {
  const s = getState();
  return recordedStash && recordedStash.regionId === s.regionId ? recordedStash : null;
}

function stashCurrent(next: string): void {
  const s = getState();
  if (!s.regionId || !s.scenarioId) return;
  if (s.scenarioId === DRAWN_SCENARIO && next !== DRAWN_SCENARIO) {
    drawnStash = s.drawn.resultsKey
      ? { regionId: s.regionId, key: s.drawn.resultsKey, plans: s.plans, submitted: s.drawn.submitted, dispatch: s.drawn.dispatch, batch: s.batch.state === 'running' ? { ...s.batch, state: 'cancelled' } : s.batch, travelOnly: s.travelOnly }
      : null;
  } else if (s.scenarioId !== DRAWN_SCENARIO && next === DRAWN_SCENARIO) {
    recordedStash =
      s.dataSource !== 'none' || s.cache
        ? { regionId: s.regionId, scenarioId: s.scenarioId, plans: s.plans, cache: s.cache, dataSource: s.dataSource, batch: s.batch, travelOnly: s.travelOnly }
        : null;
  }
}

// ---------------------------------------------------------------- region / scenario

export async function selectRegion(
  regionId: string,
  opts: { scenarioId?: string | undefined; originId?: string | undefined; inputTime?: string | undefined; preset?: boolean } = {},
): Promise<void> {
  abortScenarioWork();
  recordedStash = null;
  drawnStash = null;
  setState({
    regionId,
    scenarioId: null,
    places: [],
    placesState: 'loading',
    plans: {},
    cache: null,
    dataSource: 'none',
    dataError: null,
    selectedOriginId: null,
    selectedOffsetS: null,
    batch: IDLE_BATCH,
    recompute: null,
    travelOnly: {},
    forecast: { state: 'idle', key: null, data: null, error: null },
  });
  try {
    const places = await loadPlaces(regionId);
    if (getState().regionId !== regionId) return;
    setState({ places, placesState: 'ready' });
  } catch (e) {
    if (getState().regionId !== regionId) return;
    setState({ placesState: 'error', dataError: e instanceof Error ? e.message : String(e) });
  }
  const s = getState();
  const sets = scenarioSetsOf(s);
  const wanted = resolveScenarioParam(opts.scenarioId, sets);
  const cached = sets.find((x) => findCacheEntry(s.cacheIndex, regionId, x.id));
  const scenarioId = wanted ?? cached?.id ?? sets[0]?.id ?? null;
  const so: { originId?: string; inputTime?: string; preset?: boolean } = {};
  if (opts.originId) so.originId = opts.originId;
  if (opts.inputTime) so.inputTime = opts.inputTime;
  if (opts.preset) so.preset = true;
  if (scenarioId) await selectScenario(scenarioId, so);
  else writeHash();
}

function abortScenarioWork(): void {
  scenarioCtrl?.abort();
  scenarioCtrl = null;
  recomputeCtrl?.abort();
  recomputeCtrl = null;
  // a comparison started for the old scenario / fire input must never land in the new state
  for (const c of travelCtrls.values()) c.abort();
  travelCtrls.clear();
}

/** Stashed comparisons still marked "loading" were cut off by the switch: drop them. */
function settledTravelOnly(t: Record<string, TravelOnlyState>): Record<string, TravelOnlyState> {
  const out: Record<string, TravelOnlyState> = {};
  for (const [k, v] of Object.entries(t)) if (v.state !== 'loading') out[k] = v;
  return out;
}

/** Plans for every origin of the scenario; origins without a result are unresolved (never safe). */
function completePlans(plans: Record<string, OriginPlan>, origins: Place[], offsetsFor: (p: Place) => number[], source: 'cache' | 'live', mock: boolean): Record<string, OriginPlan> {
  const out = { ...plans };
  for (const o of origins) {
    if (out[o.id]) continue;
    out[o.id] = unresolvedPlan(o.id, offsetsFor(o), o.checkable ? 'not_computed' : 'not_checkable', source, mock);
  }
  return out;
}

/** Drawn mode: every OSM origin starts "not computed" (unresolved, never safe). */
function drawnBasePlans(s: PlannerState = getState()): Record<string, OriginPlan> {
  const offsets = gridOffsets(drawnHorizonS(s), CONFIG.stepMin);
  return completePlans({}, scenarioOrigins(s.places, null), () => offsets, 'live', false);
}

export async function selectScenario(scenarioId: string, opts: { originId?: string; inputTime?: string; preset?: boolean } = {}): Promise<void> {
  const prev = getState();
  const prevSet = currentScenarioSet(prev);
  stashCurrent(scenarioId);
  abortScenarioWork();
  const ctrl = new AbortController();
  scenarioCtrl = ctrl;
  // keep the selected village across the recorded ⇄ drawn switch (OSM origins exist in both)
  const keep = opts.originId ?? (prev.selectedOriginId && prev.places.find((p) => p.id === prev.selectedOriginId)?.role === 'origin' ? prev.selectedOriginId : null);
  setState({
    scenarioId,
    plans: {},
    cache: null,
    dataSource: 'none',
    dataError: null,
    dataLoading: false,
    batch: IDLE_BATCH,
    recompute: null,
    travelOnly: {},
    selectedOffsetS: null,
    selectedOriginId: keep,
    playing: false,
    clockS: 0,
  });
  writeHash();
  if (scenarioId === DRAWN_SCENARIO) {
    enterDrawn(prevSet?.inputTime ?? null, opts);
    if (keep) selectOrigin(keep);
    return;
  }
  const s = getState();
  // recorded results that were stashed when the user switched to drawn mode
  const st = recordedStash;
  if (st && st.regionId === s.regionId && st.scenarioId === scenarioId && st.batch.state !== 'running') {
    recordedStash = null;
    setState({ plans: st.plans, cache: st.cache, dataSource: st.dataSource, batch: st.batch, travelOnly: settledTravelOnly(st.travelOnly) });
    loadForecast();
    if (keep) selectOrigin(keep);
    return;
  }
  loadForecast();
  const entry = s.regionId ? findCacheEntry(s.cacheIndex, s.regionId, scenarioId) : null;
  const origins = scenarioOrigins(s.places, scenarioId);
  const horizon = horizonOf(s);
  if (entry) {
    setState({ dataLoading: true });
    try {
      const cache = await loadCacheFile(entry, ctrl.signal);
      if (ctrl.signal.aborted) return;
      const step = cache.meta.stepMin ?? CONFIG.stepMin;
      const plans = completePlans(
        cache.plans,
        origins,
        (p) => (p.role === 'research_origin' ? originOffsets(p, horizon, step) : cache.offsetsS.length ? cache.offsetsS : gridOffsets(horizon, step)),
        'cache',
        cache.meta.mock,
      );
      setState({ cache, plans, dataSource: 'cache', dataLoading: false });
      if (keep) selectOrigin(keep);
      return;
    } catch (e) {
      if (ctrl.signal.aborted) return;
      setState({ dataLoading: false, dataError: e instanceof Error ? e.message : String(e) });
    }
  }
  setState({ plans: completePlans({}, origins, (p) => originOffsets(p, horizon, CONFIG.stepMin), 'live', false) });
  if (keep) selectOrigin(keep);
  if (getState().apiStatus === 'online') prepareBatch();
}

/** Enter drawn mode: zones + settings of the region, footprints for presets, drawn plans. */
function enterDrawn(prevInputTime: string | null, opts: { inputTime?: string; preset?: boolean }): void {
  const s = getState();
  const regionId = s.regionId;
  if (!regionId) return;
  const times = recordedInputTimes(s);
  const wantT = opts.inputTime ? timeParam(opts.inputTime) : Number.NaN;
  const fromLink = Number.isFinite(wantT) ? times.find((t) => parseUtc(t) === wantT) ?? null : null;
  const fallback = fromLink ?? (prevInputTime && times.includes(prevInputTime) ? prevInputTime : times[0] ?? null);
  loadZonesForRegion(regionId, times, fallback);
  if (fromLink && getState().drawn.settings.inputTime !== fromLink) {
    setState((st) => ({ drawn: { ...st.drawn, settings: { ...st.drawn.settings, inputTime: fromLink } } }));
  }
  setState((st) => ({ forecast: { state: 'idle', key: null, data: null, error: null }, drawn: { ...st.drawn, rightTab: st.selectedOriginId ? 'origin' : 'zones' } }));
  const key = drawnFireKey(getState());
  const ds = drawnStash;
  if (ds && key && ds.regionId === regionId && ds.key === key) {
    drawnStash = null;
    setState((st) => ({
      plans: { ...drawnBasePlans(st), ...ds.plans },
      batch: ds.batch,
      travelOnly: settledTravelOnly(ds.travelOnly),
      dataSource: 'live',
      drawn: { ...st.drawn, resultsKey: ds.key, submitted: ds.submitted, dispatch: ds.dispatch },
    }));
  } else {
    setState((st) => ({ plans: drawnBasePlans(st), drawn: { ...st.drawn, resultsKey: null, submitted: null, dispatch: [] } }));
  }
  void ensureFootprints(regionId, Boolean(opts.preset));
}

async function ensureFootprints(regionId: string, applyDefault: boolean): Promise<void> {
  const fp = getState().drawn.footprints;
  if (fp.regionId === regionId && fp.state === 'ready') {
    if (applyDefault) applyDefaultPreset(fp.items);
    return;
  }
  if (fp.regionId === regionId && fp.state === 'loading') return;
  setFootprints({ regionId, state: 'loading', items: [], error: null });
  try {
    const items = await loadFootprints(regionId);
    if (getState().regionId !== regionId) return;
    if (applyDefault) applyDefaultPreset(items);
    setFootprints({ regionId, state: 'ready', items, error: null });
  } catch (e) {
    if (getState().regionId !== regionId) return;
    setFootprints({ regionId, state: 'error', items: [], error: e instanceof Error ? e.message : String(e) });
  }
}

/** 5 h ← footprint at the base input time, 8 h ← the next later recorded footprint (when one exists). */
export function applyDefaultPreset(items: Footprint[] = getState().drawn.footprints.items): void {
  const d = getState().drawn;
  const times = defaultPresetTimes(
    items.map((f) => f.inputTime),
    d.settings.inputTime,
  );
  const h5 = items.find((f) => f.inputTime === times.h5) ?? null;
  const h8 = items.find((f) => f.inputTime === times.h8) ?? null;
  if (h5 || h8) applyPreset({ h5, h8 });
}

export async function loadForecast(): Promise<void> {
  const s = getState();
  const set = currentScenarioSet(s);
  if (!s.regionId || !set) return;
  const key = `${s.regionId}|${set.inputTime}`;
  if (s.forecast.key === key && (s.forecast.state === 'ready' || s.forecast.state === 'loading')) return;
  if (s.apiStatus !== 'online') {
    setState({ forecast: { state: 'unavailable', key, data: null, error: null } });
    return;
  }
  setState({ forecast: { state: 'loading', key, data: null, error: null } });
  try {
    const fc = await api.forecast(s.regionId, set.inputTime, true);
    if (getState().forecast.key !== key) return;
    setState({ forecast: { state: 'ready', key, data: adaptForecast(fc, s.regionId, set.inputTime), error: null } });
  } catch (e) {
    if (getState().forecast.key !== key) return;
    setState({ forecast: { state: 'error', key, data: null, error: errInfo(e) } });
  }
}

// ---------------------------------------------------------------- dispatch plans (shared by recorded and drawn batches)

interface DispatchRunHooks {
  /** plans adapted from finished jobs (and unresolved plans of rejected groups) */
  onPlans: (plans: OriginPlan[]) => void;
  /** checks of a job the API processed (finished, any verdict) */
  onProgress: (id: string, done: number) => void;
  /** checks the API refused (422 at submission, rejected origins) or that failed without a result */
  onRejected: (id: string, n: number, info: ApiErrorInfo) => void;
  onResult?: (info: DrawnDispatchInfo) => void;
}

/**
 * Submits every group as POST /dispatch-plans (re-attaching to a job submitted earlier for the
 * same body) and waits for all of them. A 5xx at submission (BUSY, LAUNCHES_PAUSED,
 * DATA_UNAVAILABLE) stops the run with `guard.fatal`; a 422 leaves the group's origins unresolved
 * with the API's code and counts its checks as rejected, never as done.
 */
async function runDispatchGroups(
  groups: DispatchGroup[],
  placesById: Map<string, Place>,
  ctx: RecordedContext & { horizonS: number },
  alive: () => boolean,
  guard: RunGuard,
  hooks: DispatchRunHooks,
): Promise<void> {
  const size = (g: DispatchGroup) => g.originIds.length * g.destinationIds.length * g.offsetsS.length;
  const unresolved = (group: DispatchGroup, ids: string[], info: { code: string; message: string }, mock: boolean) =>
    ids.map((id) => {
      const p = unresolvedPlan(id, group.offsetsS, 'rejected', 'live', mock);
      p.rejectReason = { code: info.code, message: info.message };
      return p;
    });
  const runs: Promise<void>[] = [];
  for (const group of groups) {
    if (!alive() || guard.fatal) break;
    const body = toWireDispatch(group, placesById, ctx, `planner-ui:${ctx.region}`);
    const key = `group:${group.originIds[0]}:${group.offsetsS[0]}`;
    let resolveSubmitted: () => void = () => {};
    const submitted = new Promise<void>((r) => (resolveSubmitted = r));
    let submitError: unknown = null;
    let currentId: string | null = null;
    const onId = (id: string) => {
      // a job the API forgot was submitted again: its old progress no longer counts
      if (currentId && currentId !== id) hooks.onProgress(currentId, 0);
      currentId = id;
      resolveSubmitted();
    };
    const run = (async () => {
      try {
        const job = await submitOnceAndWait(
          'dispatch',
          body,
          async () => (await api.submitDispatch(body, { signal: guard.signal })).job_id,
          (id) => waitDispatch(id, (j) => hooks.onProgress(id, Math.min(j.progress?.done ?? 0, size(group))), { signal: guard.signal }),
          onId,
        );
        if (!alive()) return;
        const a = adaptDispatchJob(job, 'live');
        const rejected = a.rejected.map((r) => {
          const p = unresolvedPlan(r.originId, group.offsetsS, 'rejected', 'live', a.mock);
          p.rejectReason = { code: r.code, message: r.message };
          return p;
        });
        const missing = group.originIds.filter((oid) => !a.plans.some((p) => p.originId === oid) && !a.rejected.some((r) => r.originId === oid));
        const failed = job.status === 'failed' ? unresolved(group, missing, a.error ?? { code: 'JOB_FAILED', message: '' }, a.mock) : [];
        hooks.onPlans([...a.plans, ...rejected, ...failed]);
        hooks.onResult?.({ jobId: a.jobId, assumptions: a.assumptions, provenance: a.provenance, mock: a.mock, origins: group.originIds.length });
        const perOrigin = group.destinationIds.length * group.offsetsS.length;
        const notRun = (rejected.length + failed.length) * perOrigin;
        hooks.onProgress(a.jobId, Math.max(0, size(group) - notRun));
        if (notRun > 0) hooks.onRejected(`${a.jobId}:rejected`, notRun, a.rejected[0] ? { code: a.rejected[0].code, message: a.rejected[0].message } : a.error ?? { code: 'JOB_FAILED', message: '' });
      } catch (e) {
        resolveSubmitted();
        if (isAbort(e)) {
          // the bounded tail after LAUNCHES_PAUSED ran out: these checks never started
          if (guard.tailExpired() && alive()) {
            const info = guard.tailCode();
            hooks.onPlans(unresolved(group, group.originIds, info, false));
            hooks.onRejected(key, size(group), info);
          }
          return;
        }
        submitError = e;
        const info = errInfo(e);
        if (!info.status || info.status >= 500) {
          // BUSY / LAUNCHES_PAUSED / DATA_UNAVAILABLE / API gone: stop and say why
          guard.setFatal(info);
          return;
        }
        if (!alive()) return;
        // 422 (e.g. TOO_MANY_ATTEMPTS, SNAP_TOO_FAR, INVALID_ZONES) or a poll failure: these
        // origins stay unresolved with the code, and their checks count as rejected/failed
        hooks.onPlans(unresolved(group, group.originIds, info, false));
        hooks.onRejected(key, size(group), info);
      }
    })();
    runs.push(run);
    // submit one group at a time (keeps a 5xx from flooding the API); polls then run in parallel
    await submitted;
    if (submitError && guard.fatal) break;
  }
  await Promise.all(runs);
}

// ---------------------------------------------------------------- live batch (recorded)

interface BatchPlanInput {
  ctx: RecordedContext & { horizonS: number };
  osmOrigins: Place[];
  shelters: Place[];
  groups: ReturnType<typeof groupDispatch>;
  research: { place: Place; specs: CheckSpec[]; skipped: Record<number, SkipReason>; offsets: number[] }[];
  gridOffsetsS: number[];
}

function batchInput(): BatchPlanInput | null {
  const s = getState();
  const set = currentScenarioSet(s);
  if (!s.regionId || !set) return null;
  const horizon = horizonOf(s);
  const grid = gridOffsets(horizon, CONFIG.stepMin);
  const origins = scenarioOrigins(s.places, set.id);
  const dests = scenarioDestinations(s.places, set.id);
  const osmOrigins = origins.filter((p) => p.role === 'origin');
  const shelters = dests.filter((p) => p.role === 'destination');
  const groups = groupDispatch(osmOrigins, shelters, CONFIG.sheltersPerOrigin, grid);
  const research = origins
    .filter((p) => p.role === 'research_origin' && p.checkable)
    .map((place) => {
      const offsets = originOffsets(place, horizon, CONFIG.stepMin);
      return { place, offsets, ...researchCheckSpecs(place, offsets, horizon) };
    });
  return { ctx: { region: s.regionId, inputTime: set.inputTime, scenarioSetId: set.id, horizonS: horizon }, osmOrigins, shelters, groups, research, gridOffsetsS: grid };
}

/**
 * Counts the batch and either starts it (mock) or asks for confirmation (real API). With
 * VITE_WFG_ALLOW_BATCH=0 a real API never offers it (state 'disabled').
 */
export function prepareBatch(): void {
  if (getState().scenarioId === DRAWN_SCENARIO) {
    prepareDrawnBatch();
    return;
  }
  const input = batchInput();
  if (!input) return;
  const researchChecks = input.research.reduce((n, r) => n + r.specs.length, 0);
  const total = countAttempts(input.groups) + researchChecks;
  const mock = getState().health?.mock === true;
  setState({
    batch: {
      ...IDLE_BATCH,
      state: !CONFIG.allowBatch && !mock ? 'disabled' : 'confirm',
      key: scenarioKey(),
      total,
      dispatchPlans: input.groups.length,
      researchChecks,
      origins: input.groups.reduce((n, g) => n + g.originIds.length, 0) + input.research.length,
    },
  });
  if (mock) void startBatch();
}

/** Stops waiting in this browser; submitted checks keep running on the API (no cancel endpoint). */
export function cancelBatch(): void {
  scenarioCtrl?.abort();
  const s = getState();
  if (s.batch.state === 'running') setState({ batch: { ...s.batch, state: 'cancelled', finishedAt: Date.now() } });
  else if (s.batch.state === 'confirm' && s.scenarioId === DRAWN_SCENARIO) setState({ batch: IDLE_BATCH });
}

/** Final batch state: error when fatal or when the API refused everything; never a plain "done" with refusals hidden. */
function finalBatch(b: BatchState, guard: RunGuard, firstReject: ApiErrorInfo | null): Partial<BatchState> {
  if (guard.fatal) return { state: 'error', error: guard.fatal, finishedAt: Date.now() };
  if (b.done === 0 && b.rejected > 0) return { state: 'error', error: firstReject, finishedAt: Date.now() };
  return { state: 'done', error: b.rejected > 0 ? firstReject : null, finishedAt: Date.now() };
}

export async function startBatch(): Promise<void> {
  if (getState().scenarioId === DRAWN_SCENARIO) return startDrawnBatch();
  if (getState().batch.state === 'disabled') return;
  const input = batchInput();
  if (!input) return;
  scenarioCtrl?.abort();
  const ctrl = new AbortController();
  scenarioCtrl = ctrl;
  const key = scenarioKey();
  const { ctx } = input;
  const placesById = new Map(getState().places.map((p) => [p.id, p]));
  const researchTotal = input.research.reduce((n, r) => n + r.specs.length, 0);
  const total = countAttempts(input.groups) + researchTotal;
  const planProgress = new Map<string, number>();
  const planRejected = new Map<string, number>();
  let researchDone = 0;
  let researchFailed = 0;
  let firstReject: ApiErrorInfo | null = null;
  setState((s) => ({
    dataSource: 'live',
    batch: { ...s.batch, state: 'running', key, total, done: 0, rejected: 0, error: null, startedAt: Date.now(), finishedAt: null },
  }));
  const alive = () => !ctrl.signal.aborted && scenarioKey() === key;
  const bump = () => {
    if (!alive()) return;
    let done = researchDone;
    for (const v of planProgress.values()) done += v;
    let rejected = researchFailed;
    for (const v of planRejected.values()) rejected += v;
    done = Math.min(done, total);
    setState((s) => ({ batch: { ...s.batch, done, rejected: Math.min(rejected, total - done) } }));
  };
  const reject = (id: string, n: number, info: ApiErrorInfo) => {
    firstReject = firstReject ?? info;
    planRejected.set(id, n);
    bump();
  };
  const mergePlans = (plans: OriginPlan[]) => {
    if (!alive() || plans.length === 0) return;
    setState((s) => {
      const next = { ...s.plans };
      for (const p of plans) next[p.originId] = p;
      return { plans: next };
    });
  };
  // a fatal error shows at once (in-flight checks keep arriving until the bounded tail ends)
  const guard = new RunGuard(ctrl.signal, (e) => {
    if (alive()) setState((s) => ({ batch: { ...s.batch, state: 'error', error: e } }));
  });

  // Research skipped cells are known before any request.
  mergePlans(
    input.research.map(({ place, offsets, skipped }) => {
      const p = planFromAttempts({ originId: place.id, offsetsS: offsets, attempts: [], source: 'live', mock: false, skipped });
      p.note = 'not_computed';
      return p;
    }),
  );

  const dispatchRun = runDispatchGroups(input.groups, placesById, ctx, alive, guard, {
    onPlans: mergePlans,
    onProgress: (id, done) => {
      planProgress.set(id, done);
      bump();
    },
    onRejected: reject,
  });

  const researchRun = (async () => {
    for (const r of input.research) {
      if (!alive() || guard.fatal) return;
      const attempts: Attempt[] = [];
      let snap: RouteDetail['snap'] = null;
      const update = () => {
        const p = planFromAttempts({ originId: r.place.id, offsetsS: r.offsets, attempts: [...attempts], source: 'live', mock: attempts.length > 0 && getState().health?.mock === true, skipped: r.skipped });
        if (snap) p.apiSnap = snap.start;
        if (attempts.length < r.specs.length) p.note = 'not_computed';
        mergePlans([p]);
      };
      await runPool(
        r.specs,
        2,
        async (spec) => {
          if (!alive() || guard.fatal) return;
          try {
            const d = await runOneCheck(spec, ctx, guard.signal, undefined, true);
            if (d.snap && !snap) snap = d.snap;
            attempts.push(attemptFromRoute(d, spec.destinationId, spec.offsetS));
            researchDone += 1;
          } catch (e) {
            if (isAbort(e) && !guard.tailExpired()) return;
            const info = isAbort(e) ? guard.tailCode() : errInfo(e);
            if (!isAbort(e) && (!info.status || info.status >= 500)) guard.setFatal(info);
            // refused or failed without a result: unresolved with the code, never counted as done
            attempts.push({ offsetS: spec.offsetS, destinationId: spec.destinationId, verdict: 'unresolved', arrivalS: null, computeS: null, jobId: null, reasonCode: info.code, rawStatus: info.message });
            researchFailed += 1;
            firstReject = firstReject ?? info;
          }
          update();
          bump();
        },
        guard.signal,
      );
    }
  })();

  await Promise.all([dispatchRun, researchRun]);
  guard.dispose();
  if (!alive()) return;
  setState((s) => ({ batch: { ...s.batch, ...finalBatch(s.batch, guard, firstReject) } }));
  const sel = getState().selectedOriginId;
  if (sel) selectOrigin(sel);
}

/**
 * Submits one route check, waits for it and stores the detail. `reuse` (batches only): re-attach
 * to a job submitted earlier for the same request instead of submitting it again.
 */
async function runOneCheck(
  spec: Omit<CheckSpec, 'originId' | 'destinationId'> & { originId?: string },
  ctx: RecordedContext,
  signal: AbortSignal,
  onStatus?: (status: string) => void,
  reuse = false,
): Promise<RouteDetail> {
  const body = toWireRouteCheck(spec, ctx, spec.originId ? `planner-ui:${spec.originId}` : 'planner-ui');
  const submit = async () => {
    const acc = await api.submitRouteCheck(body, { signal });
    onStatus?.(acc.status);
    return acc.job_id;
  };
  const wait = (id: string) => waitRouteCheck(id, (j) => onStatus?.(j.status), { signal });
  const job = reuse ? await submitOnceAndWait('route_check', body, submit, wait) : await wait(await submit());
  const d = adaptRouteJob(job);
  setState((s) => ({ routes: { ...s.routes, [d.jobId]: d } }));
  return d;
}

// ---------------------------------------------------------------- drawn spread zones: context, invalidation, batch

/** Context of the checks for the scenario on screen (recorded set, or the drawn fire input). */
function fireContext(s: PlannerState): RecordedContext | null {
  if (!s.regionId) return null;
  if (s.scenarioId === DRAWN_SCENARIO) {
    const fi = drawnFireInput(s);
    if (!fi) return null;
    return { region: s.regionId, inputTime: fi.inputTime, scenarioSetId: fi.burningScenarioSetId ?? '', fireInput: fi };
  }
  const set = currentScenarioSet(s);
  return set ? { region: s.regionId, inputTime: set.inputTime, scenarioSetId: set.id } : null;
}

function submittedSummary(s: PlannerState, key: string): SubmittedZones | null {
  const fi = drawnFireInput(s);
  if (!fi) return null;
  return {
    key,
    inputTime: fi.inputTime,
    issuedAt: fi.issuedAt,
    marginMin: fi.marginMin,
    burningScenarioSetId: fi.burningScenarioSetId,
    zones: ZONE_KEYS.filter((k) => s.drawn.zones[k].polygons.length > 0).map((k) => {
      const z = s.drawn.zones[k];
      const sum = zoneSummary(z);
      return { key: k, arrivalHMax: sum.arrivalHMax, polygons: sum.polygons, vertices: sum.vertices, areaKm2: sum.areaKm2, presetTime: z.preset?.inputTime ?? null, edited: z.edited };
    }),
    submittedAt: new Date().toISOString(),
  };
}

/** Marks the drawn results as belonging to `key` (dropping results of an older fire input). */
function claimDrawnResults(key: string): void {
  const s = getState();
  if (s.drawn.resultsKey === key && s.drawn.submitted) return;
  const fresh = s.drawn.resultsKey !== key;
  setState((st) => ({
    plans: fresh ? drawnBasePlans(st) : st.plans,
    travelOnly: fresh ? {} : st.travelOnly,
    drawn: { ...st.drawn, resultsKey: key, submitted: submittedSummary(st, key), dispatch: fresh ? [] : st.drawn.dispatch },
  }));
}

// Editing the zones or settings drops drawn results that no longer match the zones on screen.
onFireInputChange(() => {
  const s = getState();
  if (s.scenarioId !== DRAWN_SCENARIO) return;
  const key = drawnFireKey(s);
  const running = s.recompute?.state === 'running' || s.batch.state === 'running';
  if (key !== null && key === s.drawn.resultsKey) return;
  if (s.drawn.resultsKey === null && !running && s.batch.state === 'idle') return;
  const had = s.drawn.resultsKey !== null;
  abortScenarioWork();
  setState((st) => ({
    plans: drawnBasePlans(st),
    recompute: null,
    batch: IDLE_BATCH,
    travelOnly: {},
    drawn: { ...st.drawn, resultsKey: null, submitted: null, dispatch: [] },
  }));
  if (had || running) notice('zones.notice.resultsCleared');
});

interface DrawnBatchInput {
  ctx: RecordedContext & { horizonS: number };
  key: string;
  groups: DispatchGroup[];
  inside: Place[];
  near: Place[];
}

function drawnBatchInput(): DrawnBatchInput | null {
  const s = getState();
  if (!drawnReadiness(s).ok) return null;
  const ctx = fireContext(s);
  const key = drawnFireKey(s);
  if (!ctx || !key) return null;
  const horizon = drawnHorizonS(s);
  const offsets = gridOffsets(horizon, CONFIG.stepMin);
  const origins = scenarioOrigins(s.places, null).filter((p) => p.role === 'origin' && p.checkable);
  const { inside, near } = originsNearZones(origins, s.drawn.zones);
  const shelters = scenarioDestinations(s.places, null).filter((d) => d.role === 'destination');
  const groups = groupDispatch([...inside, ...near], shelters, CONFIG.sheltersPerOrigin, offsets);
  return { ctx: { ...ctx, horizonS: horizon }, key, groups, inside, near };
}

/** Counts of "구역 안·주변 마을 계산" for the confirm card (no request is sent). */
export function drawnBatchPreview(): { inside: number; near: number; plans: number; checks: number } | null {
  const input = drawnBatchInput();
  if (!input) return null;
  return { inside: input.inside.length, near: input.near.length, plans: input.groups.length, checks: countAttempts(input.groups) };
}

/** Shows the confirm card; drawn batches never start by themselves (mock or real API). */
export function prepareDrawnBatch(): void {
  const input = drawnBatchInput();
  if (!input) return;
  setState({
    batch: {
      ...IDLE_BATCH,
      state: 'confirm',
      key: scenarioKey(),
      total: countAttempts(input.groups),
      dispatchPlans: input.groups.length,
      researchChecks: 0,
      origins: input.groups.reduce((n, g) => n + g.originIds.length, 0),
    },
  });
}

export async function startDrawnBatch(): Promise<void> {
  const input = drawnBatchInput();
  if (!input || input.groups.length === 0) return;
  scenarioCtrl?.abort();
  const ctrl = new AbortController();
  scenarioCtrl = ctrl;
  const key = scenarioKey();
  const fireKey = input.key;
  claimDrawnResults(fireKey);
  const placesById = new Map(getState().places.map((p) => [p.id, p]));
  const total = countAttempts(input.groups);
  const progress = new Map<string, number>();
  const rejectedBy = new Map<string, number>();
  let firstReject: ApiErrorInfo | null = null;
  setState((s) => ({
    dataSource: 'live',
    batch: { ...s.batch, state: 'running', key, total, done: 0, rejected: 0, error: null, startedAt: Date.now(), finishedAt: null, dispatchPlans: input.groups.length, origins: input.inside.length + input.near.length },
  }));
  const alive = () => !ctrl.signal.aborted && scenarioKey() === key && getState().drawn.resultsKey === fireKey;
  const bump = () => {
    if (!alive()) return;
    let n = 0;
    for (const v of progress.values()) n += v;
    let r = 0;
    for (const v of rejectedBy.values()) r += v;
    const done = Math.min(n, total);
    setState((s) => ({ batch: { ...s.batch, done, rejected: Math.min(r, total - done) } }));
  };
  const guard = new RunGuard(ctrl.signal, (e) => {
    if (alive()) setState((s) => ({ batch: { ...s.batch, state: 'error', error: e } }));
  });
  await runDispatchGroups(input.groups, placesById, input.ctx, alive, guard, {
    onPlans: (plans) => {
      if (!alive() || !plans.length) return;
      setState((s) => {
        const next = { ...s.plans };
        for (const p of plans) next[p.originId] = p;
        return { plans: next };
      });
    },
    onProgress: (id, done) => {
      progress.set(id, done);
      bump();
    },
    onRejected: (id, n, info) => {
      firstReject = firstReject ?? info;
      rejectedBy.set(id, n);
      bump();
    },
    onResult: (info) => {
      if (!alive()) return;
      setState((s) => ({ drawn: { ...s.drawn, dispatch: [...s.drawn.dispatch, info] } }));
    },
  });
  guard.dispose();
  if (!alive()) return;
  setState((s) => ({ batch: { ...s.batch, ...finalBatch(s.batch, guard, firstReject) } }));
  const sel = getState().selectedOriginId;
  if (sel) selectOrigin(sel);
}

// ---------------------------------------------------------------- selection

export function selectOrigin(originId: string | null): void {
  const s = getState();
  if (originId === null) {
    setState((st) => ({ selectedOriginId: null, selectedOffsetS: null, playing: false, drawn: { ...st.drawn, rightTab: 'zones' } }));
    writeHash();
    return;
  }
  const plan = s.plans[originId];
  const offset = plan?.latestSafeDepartureS ?? null;
  setState({ selectedOriginId: originId, selectedOffsetS: offset, playing: false, clockS: offset ?? s.clockS });
  if (s.scenarioId === DRAWN_SCENARIO) setRightTab('origin');
  writeHash();
  if (plan?.best?.jobId) void ensureRoute(plan.best.jobId);
  void ensureTravelOnly(originId, false);
}

export function selectOffset(offsetS: number): void {
  const s = getState();
  setState({ selectedOffsetS: offsetS, clockS: offsetS, playing: false });
  const plan = s.selectedOriginId ? s.plans[s.selectedOriginId] : null;
  const cell = plan?.sweep.find((c) => c.offsetS === offsetS);
  if (cell?.best?.jobId) void ensureRoute(cell.best.jobId);
}

export async function ensureRoute(jobId: string): Promise<RouteDetail | null> {
  const s = getState();
  const known = routeById(s, jobId);
  if (known) return known;
  if (s.apiStatus !== 'online') return null;
  try {
    const job = await api.routeCheck(jobId);
    const d = adaptRouteJob(job);
    setState((st) => ({ routes: { ...st.routes, [jobId]: d } }));
    return d;
  } catch (e) {
    setState((st) => ({ routeErrors: { ...st.routeErrors, [jobId]: errInfo(e) } }));
    return null;
  }
}

/**
 * Travel-time-only comparison for the origin's best checked attempt: from the cache when present,
 * otherwise one route check with policy travel_only (automatic against the mock, on request
 * against the real API so a shared API is not loaded by browsing). In drawn mode it uses the same
 * spread_zones fire input as the checked route.
 */
export async function ensureTravelOnly(originId: string, userRequested: boolean): Promise<void> {
  const s = getState();
  const plan = s.plans[originId];
  // the cached comparison belongs to the cached best attempt; after a live recompute it no longer applies
  const cached = plan?.source === 'cache' ? s.cache?.travelOnly[originId] : undefined;
  if (cached) {
    setState((st) => ({ travelOnly: { ...st.travelOnly, [originId]: { state: 'ready', forJobId: plan?.best?.jobId ?? null, detail: cached, error: null, source: 'cache' } } }));
    return;
  }
  const bestJob = plan?.best?.jobId;
  const existing = s.travelOnly[originId];
  if (!bestJob || (existing && existing.forJobId === bestJob && existing.state !== 'error')) return;
  if (s.apiStatus !== 'online') return;
  if (!userRequested && !s.health?.mock) return;
  const ctx = fireContext(s);
  if (!ctx) return;
  const drawnKey = s.scenarioId === DRAWN_SCENARIO ? s.drawn.resultsKey : null;
  if (s.scenarioId === DRAWN_SCENARIO && (!drawnKey || drawnKey !== drawnFireKey(s))) return;
  // one comparison per origin at a time; aborted by a scenario / fire-input switch
  travelCtrls.get(originId)?.abort();
  const ctrl = new AbortController();
  travelCtrls.set(originId, ctrl);
  const key = scenarioKey();
  const alive = () =>
    !ctrl.signal.aborted &&
    scenarioKey() === key &&
    getState().plans[originId]?.best?.jobId === bestJob &&
    (!drawnKey || getState().drawn.resultsKey === drawnKey);
  setState((st) => ({ travelOnly: { ...st.travelOnly, [originId]: { state: 'loading', forJobId: bestJob, detail: null, error: null, source: 'live' } } }));
  try {
    const full = await ensureRoute(bestJob);
    if (!alive()) return;
    const spec = full ? travelOnlySpec(full) : null;
    if (!spec) throw new ApiError(0, 'NO_REQUEST', 'the checked route has no request to compare');
    const d = await runOneCheck({ ...spec, originId }, ctx, ctrl.signal);
    if (!alive()) return;
    setState((st) => ({ travelOnly: { ...st.travelOnly, [originId]: { state: 'ready', forJobId: bestJob, detail: d, error: null, source: 'live' } } }));
  } catch (e) {
    // an aborted or outdated request never writes an entry (also not an error)
    if (isAbort(e) || !alive()) return;
    setState((st) => ({ travelOnly: { ...st.travelOnly, [originId]: { state: 'error', forJobId: bestJob, detail: null, error: errInfo(e), source: 'live' } } }));
  } finally {
    if (travelCtrls.get(originId) === ctrl) travelCtrls.delete(originId);
  }
}

// ---------------------------------------------------------------- live recompute of one origin

export function cancelRecompute(): void {
  recomputeCtrl?.abort();
  const r = getState().recompute;
  if (r && r.state === 'running') setState({ recompute: { ...r, state: 'cancelled', finishedAt: Date.now() } });
}

/** Specs of one origin's recompute: (offsets, specs, skipped) for the scenario on screen. */
function originSpecs(s: PlannerState, place: Place): { offsets: number[]; specs: CheckSpec[]; skipped: Record<number, SkipReason> } {
  const horizon = horizonOf(s);
  if (s.scenarioId === DRAWN_SCENARIO) {
    // drawn zones: OSM origins only, K nearest shelters, offsets over the 1 h hazard horizon
    const offsets = gridOffsets(horizon, CONFIG.stepMin);
    const shelters = kNearestDestinations(place, scenarioDestinations(s.places, null).filter((d) => d.role === 'destination'), CONFIG.sheltersPerOrigin);
    return { offsets, specs: osmCheckSpecs(place, shelters, offsets, horizon), skipped: {} };
  }
  const set = currentScenarioSet(s)!;
  const offsets = originOffsets(place, horizon, CONFIG.stepMin);
  if (place.role === 'research_origin') {
    const r = researchCheckSpecs(place, offsets, horizon);
    return { offsets, specs: r.specs, skipped: r.skipped };
  }
  const shelters = kNearestDestinations(place, scenarioDestinations(s.places, set.id).filter((d) => d.role === 'destination'), CONFIG.sheltersPerOrigin);
  return { offsets, specs: osmCheckSpecs(place, shelters, offsets, horizon), skipped: {} };
}

/** Number of single checks "이 출발지 다시 계산" / "선택한 출발지 계산" would send. */
export function originCheckCount(originId: string): number {
  const s = getState();
  const place = s.places.find((p) => p.id === originId);
  if (!place || !place.checkable) return 0;
  if (s.scenarioId !== DRAWN_SCENARIO && !currentScenarioSet(s)) return 0;
  return originSpecs(s, place).specs.length;
}

/**
 * Recompute ONE origin: one POST /route-checks per departure offset per candidate shelter (entry
 * nodes as {node_id}), concurrency 2, coarse-to-fine order, per-cell progress and the real
 * compute_s of every check. In drawn mode the fire input is the zones on screen ("선택한 출발지 계산").
 */
export async function recomputeOrigin(originId: string): Promise<void> {
  const s = getState();
  const place = s.places.find((p) => p.id === originId);
  const drawn = s.scenarioId === DRAWN_SCENARIO;
  if (!place || !s.regionId || s.apiStatus !== 'online' || !place.checkable) return;
  if (drawn && !drawnReadiness(s).ok) return;
  const ctx = fireContext(s);
  if (!ctx) return;
  const fireKey = drawn ? drawnFireKey(s) : null;
  if (drawn && !fireKey) return;
  recomputeCtrl?.abort();
  const ctrl = new AbortController();
  recomputeCtrl = ctrl;
  if (drawn) claimDrawnResults(fireKey!);
  const planned = originSpecs(getState(), place);
  const { offsets, skipped } = planned;
  let specs = planned.specs;
  const order = coarseToFine(specs.map((x) => x.offsetS));
  const rank = new Map(order.map((o, i) => [o, i]));
  specs = [...specs].sort((a, b) => (rank.get(a.offsetS)! - rank.get(b.offsetS)!) || a.destinationId.localeCompare(b.destinationId));
  const perOffset = new Map<number, number>();
  for (const sp of specs) perOffset.set(sp.offsetS, (perOffset.get(sp.offsetS) ?? 0) + 1);
  const cells: Record<number, CellProgress> = {};
  for (const o of perOffset.keys()) cells[o] = 'pending';
  setState({ recompute: { originId, state: 'running', total: specs.length, done: 0, cells, error: null, startedAt: Date.now(), finishedAt: null } });
  if (drawn) setState({ dataSource: 'live' });

  const attempts: Attempt[] = [];
  const finished = new Map<number, number>();
  let snap: RouteDetail['snap'] = null;
  const key = scenarioKey();
  const alive = () => !ctrl.signal.aborted && scenarioKey() === key && (!drawn || getState().drawn.resultsKey === fireKey);
  const publish = () => {
    if (!alive()) return;
    const mock = attempts.some((a) => a.jobId && getState().routes[a.jobId]?.mock);
    const plan = planFromAttempts({ originId, offsetsS: offsets, attempts: [...attempts], source: 'live', mock, skipped });
    if (snap) plan.apiSnap = snap.start;
    setState((st) => ({ plans: { ...st.plans, [originId]: plan } }));
  };
  publish();
  // a fatal error shows at once; checks in flight keep arriving until the bounded tail ends
  const handled = new Set<(typeof specs)[number]>();
  const guard = new RunGuard(ctrl.signal, (e) => {
    if (alive()) setState((st) => (st.recompute && st.recompute.originId === originId ? { recompute: { ...st.recompute, state: 'error', error: e } } : {}));
  });
  await runPool(
    specs,
    2,
    async (spec) => {
      if (!alive() || guard.fatal) return;
      handled.add(spec);
      setState((st) => (st.recompute && st.recompute.originId === originId ? { recompute: { ...st.recompute, cells: { ...st.recompute.cells, [spec.offsetS]: 'running' } } } : {}));
      try {
        const d = await runOneCheck(spec, ctx, guard.signal);
        if (d.snap && !snap) snap = d.snap;
        attempts.push(attemptFromRoute(d, spec.destinationId, spec.offsetS));
      } catch (e) {
        if (isAbort(e) && !guard.tailExpired()) return;
        const info = isAbort(e) ? guard.tailCode() : errInfo(e);
        if (!isAbort(e) && (!info.status || info.status >= 500)) guard.setFatal(info);
        attempts.push({ offsetS: spec.offsetS, destinationId: spec.destinationId, verdict: 'unresolved', arrivalS: null, computeS: null, jobId: null, reasonCode: info.code, rawStatus: info.message });
      }
      const n = (finished.get(spec.offsetS) ?? 0) + 1;
      finished.set(spec.offsetS, n);
      publish();
      setState((st) =>
        st.recompute && st.recompute.originId === originId
          ? {
              recompute: {
                ...st.recompute,
                done: st.recompute.done + 1,
                cells: { ...st.recompute.cells, [spec.offsetS]: n >= (perOffset.get(spec.offsetS) ?? 1) ? 'done' : 'running' },
              },
            }
          : {},
      );
    },
    guard.signal,
  );
  guard.dispose();
  if (!alive()) return;
  const fatal = guard.fatal;
  // checks never started because of a fatal error or the expired tail: unresolved with that code
  // (never left out of the sweep), as the dispatch path marks the whole group
  if (fatal || guard.tailExpired()) {
    const info = guard.tailCode();
    const skippedSpecs = specs.filter((sp) => !handled.has(sp));
    for (const sp of skippedSpecs) {
      attempts.push({ offsetS: sp.offsetS, destinationId: sp.destinationId, verdict: 'unresolved', arrivalS: null, computeS: null, jobId: null, reasonCode: info.code, rawStatus: info.message });
    }
    if (skippedSpecs.length) publish();
  }
  setState((st) => (st.recompute && st.recompute.originId === originId ? { recompute: { ...st.recompute, state: fatal ? 'error' : 'done', error: fatal, finishedAt: Date.now() } } : {}));
  // refresh the shown route + comparison for the new result
  const plan = getState().plans[originId];
  if (getState().selectedOriginId === originId) {
    // show the deadline's route; without a checked route, the first departure's evidence (reason, compute time)
    setState({ selectedOffsetS: plan?.latestSafeDepartureS ?? getState().selectedOffsetS ?? plan?.sweep.find((c) => c.attempts.length)?.offsetS ?? null });
    setState((st) => {
      const t = { ...st.travelOnly };
      if (t[originId] && t[originId]!.forJobId !== (plan?.best?.jobId ?? null)) delete t[originId];
      return { travelOnly: t };
    });
    if (plan?.best?.jobId) void ensureTravelOnly(originId, false);
  }
}

// ---------------------------------------------------------------- UI helpers

export function setClock(t: number): void {
  setState({ clockS: t });
}

export function setPlaying(playing: boolean): void {
  setState({ playing });
}

export function openDialog(name: 'about' | 'planSheet' | 'export'): void {
  setState((s) => ({ dialogs: { ...s.dialogs, [name]: true } }));
}

export function closeDialog(name: 'about' | 'planSheet' | 'export'): void {
  setState((s) => ({ dialogs: { ...s.dialogs, [name]: false } }));
}
