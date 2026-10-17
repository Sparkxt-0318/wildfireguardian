/**
 * Wire (contract v1.5) ⇄ internal model. This is the only module that knows the wire format;
 * if the contract changes, only src/api/* changes (ARCHITECTURE.md preamble).
 */
import type {
  WireDispatchAttempt,
  WireDispatchOriginPlan,
  WireDispatchPlanJob,
  WireDispatchPlanRequest,
  WireFireInput,
  WireForecastCollection,
  WireHealth,
  WireLocation,
  WireProvenance,
  WireRegion,
  WireRegionList,
  WireRouteCheckJob,
  WireRouteCheckRequest,
  WireSnapInfo,
  WireSpreadZonesFireInput,
} from './wire';
import type {
  ApiRegion,
  Attempt,
  CheckSpec,
  DispatchGroup,
  Exposure,
  FireInput,
  ForecastData,
  ForecastProps,
  FullPolicyAssessment,
  HealthInfo,
  HostInfo,
  LocationRef,
  OriginPlan,
  Place,
  Policy,
  ProvenanceInfo,
  RouteDetail,
  ScenarioSet,
  SnapInfo,
  Verdict,
} from '../domain/types';
import { DEFAULT_DWELL_S, planFromAttempts, placeLocation } from '../domain/plan';
import type { FeatureCollection, Polygon } from 'geojson';

const VERDICTS: readonly Verdict[] = ['checked_route', 'model_no_route', 'unresolved'];
const POLICIES: readonly Policy[] = ['full', 'travel_only', 'flame_only', 'flame_peak', 'flame_dose'];

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === 'string' && v.length > 0 ? v : null;
}

/** Unknown verdict strings are treated as unresolved (never safe). */
export function adaptVerdict(v: unknown): Verdict {
  return VERDICTS.includes(v as Verdict) ? (v as Verdict) : 'unresolved';
}

function adaptPolicy(v: unknown): Policy {
  return POLICIES.includes(v as Policy) ? (v as Policy) : 'full';
}

// ---------------------------------------------------------------- MOCK detection

/** The mock adds `mode: "mock"` / `mock: true` to /health; the real API has neither. */
export function isMockHealth(h: Partial<WireHealth> | null | undefined): boolean {
  return Boolean(h && (h.mode === 'mock' || h.mock === true));
}

export function isMockProvenance(p: Partial<WireProvenance> | null | undefined): boolean {
  return Boolean(p && p.mock === true);
}

export function isMockRouteJob(j: Partial<WireRouteCheckJob> | null | undefined): boolean {
  return Boolean(j && (j.mock === true || isMockProvenance(j.provenance) || isMockProvenance(j.result?.provenance)));
}

export function isMockDispatchJob(j: Partial<WireDispatchPlanJob> | null | undefined): boolean {
  return Boolean(j && (j.mock === true || isMockProvenance(j.provenance) || isMockProvenance(j.result?.provenance)));
}

// ---------------------------------------------------------------- health / provenance

export function adaptHost(h: unknown): HostInfo | null {
  if (!h || typeof h !== 'object') return null;
  const r = h as Record<string, unknown>;
  if (!str(r.machine) && !str(r.os) && !str(r.platform) && r.recorded !== true) return null;
  return {
    recorded: r.recorded === true,
    machine: str(r.machine),
    os: str(r.os),
    platform: str(r.platform),
    cpuCount: num(r.cpu_count),
  };
}

export function adaptProvenance(p: WireProvenance | null | undefined): ProvenanceInfo | null {
  if (!p || typeof p !== 'object') return null;
  return {
    apiVersion: str(p.api_version),
    packageName: str(p.package),
    packageVersion: str(p.package_version),
    kit: str(p.kit),
    checkpoint: str(p.checkpoint),
    gitCommit: str(p.git_commit),
    gitDirty: typeof p.git_dirty === 'boolean' ? p.git_dirty : null,
    graphId: str(p.graph_id),
    region: str(p.region),
    inputTime: str(p.input_time),
    scenarioSetId: str(p.scenario_set_id),
    scenarioIds: Array.isArray(p.scenario_ids) ? p.scenario_ids.map(String) : [],
    inputHashes: p.input_hashes && typeof p.input_hashes === 'object' ? { ...p.input_hashes } : {},
    fireInputType: str(p.fire_input_type),
    policy: str(p.policy),
    evaluatedConfiguration: typeof p.evaluated_configuration === 'boolean' ? p.evaluated_configuration : null,
    recordedMissionMatch: str(p.recorded_mission_match),
    approximation: str(p.approximation),
    clock: str(p.clock),
    host: adaptHost(p.host),
    generatedAt: str(p.generated_at),
    mock: isMockProvenance(p),
  };
}

export function adaptHealth(h: WireHealth): HealthInfo {
  const queued = num(h.queued_tasks) ?? (h.jobs && typeof h.jobs === 'object' ? num((h.jobs as Record<string, unknown>).queued) : null);
  return {
    status: h.status === 'ok' ? 'ok' : 'degraded',
    apiVersion: String(h.api_version ?? ''),
    packageVersion: String(h.package_version ?? ''),
    kit: String(h.kit ?? ''),
    checkpoint: String(h.checkpoint ?? ''),
    gitCommit: String(h.git_commit ?? ''),
    regions: Array.isArray(h.regions) ? h.regions.map(String) : [],
    workers: num(h.workers) ?? 1,
    issues: Array.isArray(h.issues) ? h.issues.map(String) : [],
    mock: isMockHealth(h),
    host: adaptHost(h.provenance?.host),
    queued,
    budgetS: num(h.budget_s),
  };
}

// ---------------------------------------------------------------- regions / forecast

export function adaptScenarioSet(s: WireRegion['scenario_sets'][number]): ScenarioSet {
  return {
    id: s.scenario_set_id,
    inputTime: s.input_time,
    scenarioIds: Array.isArray(s.scenario_ids) ? s.scenario_ids.map(String) : [],
    horizonS: num(s.horizon_s),
    hazardSha256: str(s.hazard_sha256),
    source: 'api',
  };
}

export function adaptRegion(r: WireRegion): ApiRegion {
  return {
    id: r.id,
    nameKo: r.name_ko,
    nameEn: r.name_en,
    eventId: str(r.event_id),
    bbox: r.bbox,
    graphId: r.graph_id,
    graphSha256: str(r.graph_sha256),
    nodeCount: r.node_count,
    edgeCount: r.edge_count,
    allowedNodeCount: num(r.allowed_node_count),
    inputTimes: Array.isArray(r.input_times) ? [...r.input_times] : [],
    scenarioSets: (r.scenario_sets ?? []).map(adaptScenarioSet).sort((a, b) => a.inputTime.localeCompare(b.inputTime)),
    fireYear: num(r.fire_year),
  };
}

export function adaptRegionList(list: WireRegionList): ApiRegion[] {
  return (list.regions ?? []).map(adaptRegion);
}

export function adaptForecast(fc: WireForecastCollection, regionId: string, inputTime: string): ForecastData {
  const cells: FeatureCollection<Polygon, ForecastProps> = {
    type: 'FeatureCollection',
    features: (fc.features ?? []).map((f, i) => ({
      type: 'Feature',
      id: i,
      geometry: { type: 'Polygon', coordinates: f.geometry.coordinates as number[][][] },
      properties: {
        p: num(f.properties.p_new_burn_1h),
        burning: f.properties.burning_now === true,
        valid: f.properties.valid !== false,
      },
    })),
  };
  return {
    regionId: str(fc.region) ?? regionId,
    inputTime: str(fc.input_time) ?? inputTime,
    cells,
    provenance: adaptProvenance(fc.provenance),
    mock: isMockProvenance(fc.provenance),
  };
}

// ---------------------------------------------------------------- snaps / attempts / plans

export function adaptSnap(s: WireSnapInfo | null | undefined): SnapInfo | null {
  if (!s || typeof s !== 'object' || !str(s.node_id)) return null;
  return {
    nodeId: s.node_id,
    distanceM: num(s.distance_m) ?? 0,
    lon: num(s.lon) ?? 0,
    lat: num(s.lat) ?? 0,
    input: s.input === 'node_id' ? 'node_id' : 'lonlat',
  };
}

export function adaptAttempt(a: WireDispatchAttempt): Attempt {
  const verdict = adaptVerdict(a.verdict);
  return {
    offsetS: Number(a.depart_offset_s),
    destinationId: String(a.destination_id),
    verdict,
    arrivalS: num(a.arrival_s),
    computeS: num(a.compute_s),
    jobId: str(a.route_check_job_id),
    reasonCode: verdict === 'unresolved' ? str(a.reason_code) : null,
    rawStatus: str(a.raw_status),
    lowerBoundS: num(a.lower_bound_L_s),
  };
}

export function adaptOriginPlan(p: WireDispatchOriginPlan, offsetsS: number[], source: 'cache' | 'live', mock: boolean): OriginPlan {
  const attempts = (p.attempts ?? []).map(adaptAttempt);
  const plan = planFromAttempts({ originId: p.origin_id, offsetsS, attempts, source, mock });
  plan.apiSnap = adaptSnap(p.snap);
  return plan;
}

export interface AdaptedDispatch {
  jobId: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  progress: { done: number; total: number };
  plans: OriginPlan[];
  rejected: { originId: string; code: string; message: string }[];
  error: { code: string; message: string } | null;
  mock: boolean;
  medianComputeS: number | null;
  provenance: ProvenanceInfo | null;
  /** spread_zones: DispatchPlanResult.assumptions exactly as sent (null for recorded) */
  assumptions: Record<string, unknown> | null;
}

export function adaptDispatchJob(job: WireDispatchPlanJob, source: 'cache' | 'live'): AdaptedDispatch {
  if (!job || typeof job !== 'object') {
    // tolerate a malformed entry (cache files store null for a refused request): nothing in it
    return { jobId: '', status: 'failed', progress: { done: 0, total: 0 }, plans: [], rejected: [], error: { code: 'BAD_RESPONSE', message: 'no dispatch job' }, mock: false, medianComputeS: null, provenance: null, assumptions: null };
  }
  const mock = isMockDispatchJob(job);
  const req = (job.request ?? {}) as Partial<WireDispatchPlanRequest>;
  const offsets = Array.isArray(req.depart_offsets_s) ? [...new Set(req.depart_offsets_s.map(Number))].sort((a, b) => a - b) : [];
  const result = job.status === 'done' ? job.result : null;
  return {
    jobId: job.job_id,
    status: job.status,
    progress: { done: num(job.progress?.done) ?? 0, total: num(job.progress?.total) ?? 0 },
    plans: (result?.plans ?? []).map((p) => adaptOriginPlan(p, offsets, source, mock)),
    rejected: (result?.rejected_origins ?? []).map((r) => ({
      originId: r.origin_id,
      code: String(r.error?.code ?? 'REJECTED'),
      message: String(r.error?.message ?? ''),
    })),
    error: job.error ? { code: String(job.error.code), message: String(job.error.message) } : null,
    mock,
    medianComputeS: num(result?.summary?.median_compute_s),
    provenance: adaptProvenance(result?.provenance ?? job.provenance),
    assumptions: result?.assumptions && typeof result.assumptions === 'object' ? result.assumptions : null,
  };
}

// ---------------------------------------------------------------- route checks

function adaptLocationRef(v: unknown): LocationRef | null {
  if (!v || typeof v !== 'object') return null;
  const r = v as Record<string, unknown>;
  if (str(r.node_id)) return { kind: 'node', nodeId: String(r.node_id) };
  const lon = num(r.lon);
  const lat = num(r.lat);
  return lon !== null && lat !== null ? { kind: 'lonlat', lon, lat } : null;
}

function memberOf(scenarioId: string, index: number): number {
  const m = /:(\d+)$/.exec(scenarioId);
  return m ? Number(m[1]) + 1 : index + 1;
}

/**
 * Full-policy assessment of a reduced-policy route (contract v1.1 RouteCheckResult.full_policy_assessment).
 * The real API reports passes_full_centre_and_contact + violations[{scenario_id, constraint}] (api/runner.py);
 * recorded mock results carry the ablation grade as pass + failure_components. Both are read.
 */
function adaptFullPolicy(v: unknown): FullPolicyAssessment | null {
  if (!v || typeof v !== 'object') return null;
  const r = v as Record<string, unknown>;
  const pass =
    typeof r.passes_full_centre_and_contact === 'boolean'
      ? r.passes_full_centre_and_contact
      : typeof r.pass === 'boolean'
        ? r.pass
        : null;
  let components: string[] = [];
  if (Array.isArray(r.violations)) {
    const set = new Set<string>();
    for (const x of r.violations) {
      const c = x && typeof x === 'object' ? (x as Record<string, unknown>).constraint : null;
      if (c != null) set.add(String(c));
    }
    components = [...set];
  } else if (Array.isArray(r.failure_components)) {
    components = r.failure_components.map(String);
  } else if (typeof r.failure_components === 'string' && r.failure_components) {
    components = r.failure_components.split(/[;,|]\s*/).filter(Boolean);
  }
  const skip = new Set(['pass', 'passes_full_centre_and_contact', 'failure_components', 'violations', 'per_scenario', 'source']);
  const details: Record<string, string> = {};
  for (const [k, val] of Object.entries(r)) {
    if (skip.has(k)) continue;
    if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean') details[k] = String(val);
  }
  return { pass, components, source: str(r.source), details };
}

export function adaptRouteJob(job: WireRouteCheckJob): RouteDetail {
  const res = job.status === 'done' ? job.result : null;
  const req = (job.request ?? {}) as Record<string, unknown>;
  const verdict: Verdict = res ? adaptVerdict(res.verdict) : 'unresolved';
  const route = res && verdict === 'checked_route' ? res.route : null;
  const coords = route?.geometry?.coordinates?.map((c) => [Number(c[0]), Number(c[1])] as [number, number]) ?? null;
  const times = route?.properties?.times_s?.map(Number) ?? null;
  const start = adaptLocationRef(req.start);
  const destination = adaptLocationRef(req.destination);
  const win = Array.isArray(req.destination_window) && req.destination_window.length === 2 ? (req.destination_window as [number, number]) : null;
  const reqLimits = req.limits as Record<string, unknown> | undefined;
  const reqPeak = reqLimits ? num(reqLimits.peak_kw_m2) : null;
  const reqDose = reqLimits ? num(reqLimits.dose_kj_m2) : null;
  const spec: RouteDetail['spec'] =
    start && destination
      ? {
          offsetS: num(req.depart_offset_s) ?? 0,
          start,
          destination,
          dwellS: num(req.dwell_s) ?? DEFAULT_DWELL_S,
          // an omitted window means [0, horizon] on the API side; NaN marks "omit" for toWireRouteCheck
          window: win ? [Number(win[0]), Number(win[1])] : [0, Number.NaN],
          policy: adaptPolicy(req.policy),
          limits: reqPeak !== null && reqDose !== null ? { peakKwM2: reqPeak, doseKjM2: reqDose } : null,
          incurredDoseKjM2: num(req.incurred_dose_kj_m2),
        }
      : null;
  const s = job.snap;
  const snapStart = adaptSnap(s?.start);
  const snapDest = adaptSnap(s?.destination);
  const exposure: Exposure[] = (res?.exposure ?? []).map((e, i) => ({
    scenarioId: String(e.scenario_id),
    member: memberOf(String(e.scenario_id), i),
    peakKwM2: Number(e.peak_kw_m2),
    doseKjM2: Number(e.dose_kj_m2),
    contact: e.contact === true,
    basis: str(e.basis),
    peakUpperKwM2: num(e.peak_upper_kw_m2),
    doseUpperKjM2: num(e.dose_upper_kj_m2),
  }));
  return {
    jobId: job.job_id,
    status: job.status,
    verdict,
    reasonCode: res && verdict === 'unresolved' ? str(res.reason_code) : job.status === 'failed' ? str(job.error?.code) : null,
    rawStatus: res ? str(res.raw_status) : null,
    rawReason: res ? str(res.raw_reason) : null,
    policy: adaptPolicy(res?.policy ?? req.policy),
    departureS: res ? num(res.departure_s) : null,
    arrivalS: res ? num(res.arrival_s) : null,
    lowerBoundS: res ? num(res.lower_bound_L_s) : null,
    dwellEndS: res ? num(res.dwell_end_s) : null,
    dwellS: num(req.dwell_s),
    destinationWindow: win ? [Number(win[0]), Number(win[1])] : null,
    departOffsetS: num(req.depart_offset_s),
    coordinates: coords && coords.length > 0 ? coords : null,
    timesS: times && times.length > 0 ? times : null,
    lengthM: num(route?.properties?.length_m),
    segmentCount: num(route?.properties?.segment_count),
    exposure,
    computeS: res ? num(res.compute_s) : null,
    withinBudget: res && typeof res.within_budget === 'boolean' ? res.within_budget : null,
    limits: res?.limits
      ? {
          peakKwM2: Number(res.limits.peak_kw_m2),
          doseKjM2: Number(res.limits.dose_kj_m2),
          incurredDoseKjM2: num(res.limits.incurred_dose_kj_m2),
        }
      : null,
    notes: Array.isArray(res?.notes) ? res!.notes!.map(String) : [],
    assumptions: res?.assumptions && typeof res.assumptions === 'object' ? res.assumptions : null,
    provenance: adaptProvenance(res?.provenance ?? job.provenance),
    snap: snapStart && snapDest ? { start: snapStart, destination: snapDest } : null,
    fullPolicy: adaptFullPolicy(res?.full_policy_assessment),
    spec,
    error: job.error ? { code: String(job.error.code), message: String(job.error.message) } : null,
    mock: isMockRouteJob(job),
  };
}

/** Attempt from a single route check (research origins, live recompute). */
export function attemptFromRoute(d: RouteDetail, destinationId: string, offsetS: number): Attempt {
  return {
    offsetS,
    destinationId,
    verdict: d.status === 'done' ? d.verdict : 'unresolved',
    arrivalS: d.verdict === 'checked_route' ? d.arrivalS : null,
    computeS: d.computeS,
    jobId: d.jobId,
    reasonCode: d.verdict === 'unresolved' || d.status !== 'done' ? d.reasonCode : null,
    rawStatus: d.rawStatus,
    lowerBoundS: d.lowerBoundS,
  };
}

// ---------------------------------------------------------------- internal → wire requests

export function toWireLocation(loc: LocationRef): WireLocation {
  return loc.kind === 'node' ? { node_id: loc.nodeId } : { lon: loc.lon, lat: loc.lat };
}

export interface RecordedContext {
  region: string;
  inputTime: string;
  /** recorded scenario set (fire_input recorded); for spread_zones the burning set of input_time */
  scenarioSetId: string;
  /** when given, sent instead of {type: "recorded", scenario_set_id} (drawn spread zones) */
  fireInput?: FireInput | null;
}

/**
 * Contract FireInput. Recorded → {type, scenario_set_id}. Spread zones → {type, zones, issued_at,
 * margin_min, burning_scenario_set_id?}: zones is a ZoneCollection whose features carry exactly
 * {arrival_h_max}; burning_scenario_set_id is sent only when known (optional consistency check).
 */
export function toWireFireInput(fi: FireInput): WireFireInput {
  if (fi.type === 'recorded') return { type: 'recorded', scenario_set_id: fi.scenarioSetId };
  const features = (fi.zones.features ?? [])
    .filter((f) => f.geometry && (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon'))
    .map((f) => ({
      type: 'Feature' as const,
      geometry: { type: f.geometry.type as 'Polygon' | 'MultiPolygon', coordinates: (f.geometry as { coordinates: unknown[] }).coordinates },
      properties: { arrival_h_max: Number((f.properties as Record<string, unknown> | null)?.arrival_h_max) },
    }));
  const out: WireSpreadZonesFireInput = {
    type: 'spread_zones',
    zones: { type: 'FeatureCollection', features },
    issued_at: fi.issuedAt,
    margin_min: fi.marginMin,
  };
  if (fi.burningScenarioSetId) out.burning_scenario_set_id = fi.burningScenarioSetId;
  return out;
}

function contextFireInput(ctx: RecordedContext): WireFireInput {
  return ctx.fireInput ? toWireFireInput(ctx.fireInput) : { type: 'recorded', scenario_set_id: ctx.scenarioSetId };
}

export function toWireRouteCheck(spec: Omit<CheckSpec, 'originId' | 'destinationId'>, ctx: RecordedContext, clientRef?: string): WireRouteCheckRequest {
  const body: WireRouteCheckRequest = {
    region: ctx.region,
    input_time: ctx.inputTime,
    start: toWireLocation(spec.start),
    destination: toWireLocation(spec.destination),
    depart_offset_s: spec.offsetS,
    dwell_s: spec.dwellS,
    destination_window: [spec.window[0], spec.window[1]],
    policy: spec.policy,
    fire_input: contextFireInput(ctx),
  };
  if (spec.limits) body.limits = { peak_kw_m2: spec.limits.peakKwM2, dose_kj_m2: spec.limits.doseKjM2 };
  if (spec.incurredDoseKjM2 !== null) body.incurred_dose_kj_m2 = spec.incurredDoseKjM2;
  if (clientRef) body.client_ref = clientRef.slice(0, 200);
  if (!Number.isFinite(spec.window[1])) delete body.destination_window;
  return body;
}

/** Dispatch request for one group (OSM origins/shelters as lon/lat; window [0, horizon], dwell 120, policy full). */
export function toWireDispatch(group: DispatchGroup, placesById: Map<string, Place>, ctx: RecordedContext & { horizonS: number }, clientRef?: string): WireDispatchPlanRequest {
  const loc = (id: string) => {
    const p = placesById.get(id);
    if (!p) throw new Error(`unknown place ${id}`);
    return toWireLocation(placeLocation(p));
  };
  const body: WireDispatchPlanRequest = {
    region: ctx.region,
    input_time: ctx.inputTime,
    fire_input: contextFireInput(ctx),
    origins: group.originIds.map((id) => ({ id, location: loc(id) })),
    destinations: group.destinationIds.map((id) => ({ id, location: loc(id), dwell_s: DEFAULT_DWELL_S, window: [0, ctx.horizonS] as [number, number] })),
    depart_offsets_s: [...group.offsetsS],
    dwell_s: DEFAULT_DWELL_S,
    policy: 'full',
  };
  if (clientRef) body.client_ref = clientRef.slice(0, 200);
  return body;
}

/**
 * The travel-time-only comparison of a checked route: the same start, destination, offset, dwell,
 * window, limits and incurred dose, with policy travel_only.
 */
export function travelOnlySpec(d: RouteDetail): Omit<CheckSpec, 'originId' | 'destinationId'> | null {
  if (!d.spec) return null;
  return { ...d.spec, policy: 'travel_only' };
}
