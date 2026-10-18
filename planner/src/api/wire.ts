/**
 * Wire types of the official Route-Check API contract
 * (planner/contract/wfg_api_v1.yaml, OpenAPI 3.1, contract version 1.5.0; changes v1.1–v1.5 in
 * planner/contract/CHANGELOG.md).
 *
 * These mirror `components.schemas` one to one (same names, same field names, same nullability).
 * Only `src/api/adapter.ts` reads them; the UI works with the internal model in
 * `src/domain/types.ts`. Fields marked "extension" are additive properties the contract allows
 * (no `additionalProperties: false` on responses) and that the mock server or the real API add;
 * they are always optional here. Fields added by a contract minor version are marked "vX.Y".
 * Enumerations that the contract may extend (reason codes, error codes) also accept any string,
 * so an unknown code is shown with its message instead of breaking the client.
 */

export type WireVerdict = 'checked_route' | 'model_no_route' | 'unresolved';

/** Known reason codes (unresolved only; null otherwise). */
export type WireKnownReasonCode =
  | 'TIMEOUT'
  | 'STATE_CAP'
  | 'MEMORY_CAP'
  | 'CHECK_NOT_FINISHED'
  | 'CHECK_FAILED'
  | 'WORKER_ERROR'
  | 'CLEANUP_UNCONFIRMED'
  | 'INTERNAL_ERROR'
  | 'OTHER'
  // v1.1
  | 'INPUT_REJECTED'
  | 'AT_ISSUE_FAILURE'
  | 'DISCONNECTED';

export const WIRE_REASON_CODES: readonly WireKnownReasonCode[] = [
  'TIMEOUT',
  'STATE_CAP',
  'MEMORY_CAP',
  'CHECK_NOT_FINISHED',
  'CHECK_FAILED',
  'WORKER_ERROR',
  'CLEANUP_UNCONFIRMED',
  'INTERNAL_ERROR',
  'OTHER',
  'INPUT_REJECTED',
  'AT_ISSUE_FAILURE',
  'DISCONNECTED',
];

export type WireReasonCode = WireKnownReasonCode | (string & {}) | null;

/** Error codes documented in `Error.code` (v1.0–v1.5). Other strings may appear. */
export type WireKnownErrorCode =
  | 'UNKNOWN_REGION'
  | 'INPUT_TIME_UNAVAILABLE'
  | 'UNKNOWN_SCENARIO_SET'
  | 'SNAP_TOO_FAR'
  | 'UNKNOWN_NODE'
  | 'NODE_NOT_ALLOWED'
  | 'ZONES_OUTSIDE_REGION'
  | 'INVALID_ZONES'
  | 'VALIDATION_ERROR'
  | 'JOB_NOT_FOUND'
  | 'JOB_NOT_DONE'
  | 'NO_CHECKED_ROUTE'
  | 'DATA_UNAVAILABLE'
  | 'TOO_MANY_ORIGINS'
  // v1.1
  | 'INVALID_INPUT_TIME'
  | 'SCENARIO_SET_TIME_MISMATCH'
  | 'FORECAST_UNAVAILABLE'
  | 'NOT_ON_TIME_LATTICE'
  | 'DEPARTURE_OUTSIDE_HORIZON'
  | 'INVALID_WINDOW'
  | 'WINDOW_UNSATISFIABLE'
  | 'START_EQUALS_DESTINATION'
  | 'INVALID_LIMITS'
  | 'DUPLICATE_ID'
  | 'INPUT_CHANGED'
  // v1.3
  | 'GRID_MISMATCH'
  | 'CHECKPOINT_MISMATCH'
  | 'ZONE_PACKET_BUILD_FAILED'
  // v1.4
  | 'POLICY_NOT_ALLOWED'
  | 'DUPLICATE_OFFSET'
  | 'TOO_MANY_ATTEMPTS'
  // v1.5 (503)
  | 'BUSY'
  | 'LAUNCHES_PAUSED';

export type WirePolicy = 'full' | 'travel_only' | 'flame_only' | 'flame_peak' | 'flame_dose';

export type WireJobStatus = 'queued' | 'running' | 'done' | 'failed';

/** [min_lon, min_lat, max_lon, max_lat] (WGS84) */
export type WireBBox = [number, number, number, number];

/** [lon, lat] or [lon, lat, z] */
export type WirePosition = number[];

export interface WireError {
  error: { code: WireKnownErrorCode | (string & {}); message: string; details?: unknown };
  /** v1.3 (null before start-up completes) */
  provenance?: WireProvenance | null;
}

export interface WireJobError {
  code: string;
  message: string;
}

export interface WireHealth {
  status: 'ok' | 'degraded';
  api_version: string;
  package: 'wfg_latest';
  package_version: string;
  kit: string;
  checkpoint: string;
  git_commit: string;
  regions: string[];
  workers: number;
  data_root?: string | null;
  issues?: string[];
  /** v1.3 */
  provenance?: WireProvenance;
  /** extension (real API): job counts by state */
  jobs?: Record<string, number>;
  /** extension (real API) */
  queued_tasks?: number;
  /** extension (both) */
  budget_s?: number;
  /** extension (mock only): "mock" */
  mode?: string;
  /** extension (mock only) */
  mock?: boolean;
}

export interface WireGrid {
  x0: number;
  y0: number;
  resolution_m: number;
  width: number;
  height: number;
}

export interface WireScenarioSet {
  scenario_set_id: string;
  input_time: string;
  scenario_ids: string[];
  horizon_s: number;
  hazard_sha256?: string;
}

export interface WireRegion {
  id: string;
  name_ko: string;
  name_en: string;
  event_id?: string;
  bbox: WireBBox;
  graph_id: string;
  graph_sha256?: string;
  node_count: number;
  edge_count: number;
  allowed_node_count?: number;
  crs: 'EPSG:5179';
  grid: WireGrid;
  input_times: string[];
  scenario_sets: WireScenarioSet[];
  /** extension allowed by ARCHITECTURE.md §4.1 */
  fire_year?: number;
}

export interface WireProvenance {
  api_version: string;
  package: 'wfg_latest';
  package_version: string;
  kit: string;
  checkpoint: string;
  git_commit: string;
  git_dirty?: boolean | null;
  region?: string | null;
  input_time?: string | null;
  graph_id?: string | null;
  input_hashes: Record<string, string>;
  scenario_set_id?: string | null;
  scenario_ids: string[];
  fire_input_type?: 'recorded' | 'spread_zones' | null;
  policy?: string | null;
  evaluated_configuration?: boolean | null;
  approximation?: string | null;
  clock?: string | null;
  host?: Record<string, unknown> | null;
  generated_at?: string;
  /** v1.1: recorded final-panel mission whose request is identical */
  recorded_mission_match?: string | null;
  /** extension (real API) */
  kit_candidate_id?: string;
  /** extension (mock only) */
  mock?: boolean;
  [k: string]: unknown;
}

export interface WireRegionList {
  regions: WireRegion[];
  provenance: WireProvenance;
}

export interface WireGeoPolygon {
  type: 'Polygon';
  coordinates: WirePosition[][];
}

export interface WireForecastCell {
  type: 'Feature';
  id?: string;
  geometry: WireGeoPolygon;
  properties: {
    row: number;
    col: number;
    p_new_burn_1h: number | null;
    valid: boolean;
    burning_now: boolean;
    /** extension (ARCHITECTURE.md §4.1) */
    cell?: number;
    /** extension (ARCHITECTURE.md §4.1) */
    known_burned?: boolean;
  };
}

export interface WireForecastCollection {
  type: 'FeatureCollection';
  region?: string;
  input_time?: string;
  bbox?: WireBBox;
  features: WireForecastCell[];
  provenance: WireProvenance;
}

export interface WireLonLat {
  lon: number;
  lat: number;
}

export interface WireNodeRef {
  node_id: string;
}

export type WireLocation = WireLonLat | WireNodeRef;

export interface WireLimits {
  peak_kw_m2?: number;
  dose_kj_m2?: number;
}

export interface WireRecordedFireInput {
  type: 'recorded';
  scenario_set_id: string;
}

export interface WireZoneFeature {
  type: 'Feature';
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: unknown[] };
  properties: { arrival_h_max: number; [k: string]: unknown };
}

export interface WireZoneCollection {
  type: 'FeatureCollection';
  features: WireZoneFeature[];
}

export interface WireSpreadZonesFireInput {
  type: 'spread_zones';
  zones: WireZoneCollection;
  issued_at: string;
  margin_min?: number;
  burning_scenario_set_id?: string | null;
}

export type WireFireInput = WireRecordedFireInput | WireSpreadZonesFireInput;

export interface WireRouteCheckRequest {
  region: string;
  input_time: string;
  start: WireLocation;
  destination: WireLocation;
  depart_offset_s?: number;
  dwell_s?: number;
  destination_window?: [number, number];
  policy?: WirePolicy;
  limits?: WireLimits;
  incurred_dose_kj_m2?: number;
  fire_input: WireFireInput;
  run_independent_check?: boolean;
  client_ref?: string | null;
}

export interface WireSnapInfo {
  node_id: string;
  distance_m: number;
  lon: number;
  lat: number;
  input: 'lonlat' | 'node_id';
}

export interface WireSnapPair {
  start: WireSnapInfo;
  destination: WireSnapInfo;
}

export interface WireJobAccepted {
  job_id: string;
  status: WireJobStatus;
  kind: 'route_check' | 'dispatch_plan';
  snap?: WireSnapPair;
  links?: Record<string, string>;
  /** v1.4 */
  provenance?: WireProvenance;
}

export interface WireScenarioExposure {
  scenario_id: string;
  peak_kw_m2: number;
  dose_kj_m2: number;
  /** v1.1: under travel_only assessed against the full hazard and may be true */
  contact: boolean;
  /** v1.1 */
  basis?: 'centre_model' | 'full_model_centre_check' | (string & {});
  /** v1.1 (full policy only) */
  peak_upper_kw_m2?: number | null;
  /** v1.1 (full policy only) */
  dose_upper_kj_m2?: number | null;
}

export interface WireRouteFeature {
  type: 'Feature';
  geometry: { type: 'LineString'; coordinates: WirePosition[] };
  properties: {
    times_s: number[];
    node_ids: string[];
    segment_count: number;
    edge_ids?: string[];
    waits?: { node_id: string; from_s: number; to_s: number }[];
    /** extension (ARCHITECTURE.md §4.1) */
    length_m?: number;
    [k: string]: unknown;
  };
}

/**
 * v1.1 `full_policy_assessment` (type [object, null], free-form): offline assessment of a
 * reduced-policy route against the unchanged full hazard. Field names below are those the mock
 * and the real API use; all optional.
 */
export interface WireFullPolicyAssessment {
  pass?: boolean | null;
  failure_components?: string[] | null;
  source?: string;
  [k: string]: unknown;
}

/** v1.1 */
export interface WireLowerBound {
  kind?: string | null;
  arrival_s?: number | null;
  [k: string]: unknown;
}

export interface WireRouteCheckResult {
  verdict: WireVerdict;
  reason_code: WireReasonCode;
  raw_status?: string | null;
  raw_reason?: string | null;
  departure_s?: number | null;
  arrival_s: number | null;
  lower_bound_L_s: number | null;
  /** v1.1 */
  lower_bounds?: WireLowerBound[];
  dwell_end_s: number | null;
  route: WireRouteFeature | null;
  exposure: WireScenarioExposure[];
  compute_s: number | null;
  within_budget: boolean;
  policy?: WirePolicy;
  limits?: { peak_kw_m2: number; dose_kj_m2: number; incurred_dose_kj_m2?: number };
  independent_check?: {
    status?: string | null;
    classification?: string | null;
    verdict?: string | null;
    contradictions?: unknown;
  } | null;
  assumptions?: Record<string, unknown> | null;
  notes?: string[];
  provenance: WireProvenance;
  /** v1.1 */
  full_policy_assessment?: WireFullPolicyAssessment | null;
}

export interface WireRouteCheckJob {
  job_id: string;
  kind: 'route_check';
  status: WireJobStatus;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  request: Partial<WireRouteCheckRequest> & Record<string, unknown>;
  snap: WireSnapPair;
  result: WireRouteCheckResult | null;
  error: WireJobError | null;
  /** v1.4: provenance at acceptance */
  provenance?: WireProvenance;
  /** extension (mock only) */
  mock?: boolean;
  /** cache files only (precompute --recheck-timeouts): job id of the check this one re-ran */
  recheck_of?: string;
}

export interface WireDispatchDestination {
  id: string;
  location: WireLocation;
  dwell_s?: number;
  window?: [number, number];
}

export interface WireDispatchOrigin {
  id: string;
  location: WireLocation;
}

export interface WireDispatchPlanRequest {
  region: string;
  input_time: string;
  fire_input: WireFireInput;
  origins: WireDispatchOrigin[];
  destinations: WireDispatchDestination[];
  depart_offsets_s: number[];
  dwell_s?: number;
  policy?: WirePolicy;
  limits?: WireLimits;
  client_ref?: string | null;
}

export interface WireDispatchAttempt {
  destination_id: string;
  depart_offset_s: number;
  verdict: WireVerdict;
  reason_code: WireReasonCode;
  arrival_s: number | null;
  lower_bound_L_s?: number | null;
  compute_s: number | null;
  route_check_job_id?: string | null;
  /** extension (mock) */
  raw_status?: string | null;
  /** extension (mock) */
  case_id?: string | null;
}

export interface WireDispatchOriginPlan {
  origin_id: string;
  urgency_rank: number;
  snap?: WireSnapInfo;
  best_verdict: WireVerdict;
  latest_checked_depart_offset_s: number | null;
  /** v1.4: last offset such that every requested offset from the earliest up to it is checked */
  latest_contiguous_checked_depart_offset_s?: number | null;
  best: WireDispatchAttempt | null;
  attempts: WireDispatchAttempt[];
}

export interface WireDispatchPlanResult {
  plans: WireDispatchOriginPlan[];
  summary: {
    origins: number;
    attempts: number;
    checked_route: number;
    model_no_route: number;
    unresolved: number;
    median_compute_s?: number | null;
    wall_s?: number | null;
    /** extension (both) */
    attempt_verdicts?: Record<string, number>;
    [k: string]: unknown;
  };
  rejected_origins?: { origin_id: string; error: WireJobError }[];
  assumptions?: Record<string, unknown> | null;
  provenance: WireProvenance;
  /** extension (mock) */
  notes?: string[];
}

export interface WireDispatchPlanJob {
  job_id: string;
  kind: 'dispatch_plan';
  status: WireJobStatus;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  request: Partial<WireDispatchPlanRequest> & Record<string, unknown>;
  progress: { done: number; total: number };
  result: WireDispatchPlanResult | null;
  error: WireJobError | null;
  /** v1.4: provenance at acceptance */
  provenance?: WireProvenance;
  /** extension (mock only) */
  mock?: boolean;
}

/** planner/cache/INDEX.json entry (written by planner/scripts/precompute.py) */
export interface WireCacheIndexEntry {
  region_id: string;
  scenario_set_id: string;
  input_time: string;
  path: string;
  api_mode: string;
  created_at: string;
  origins: number;
  bytes: number;
  sha256: string;
  /** newer files */
  api_version?: string;
  host?: Record<string, unknown> | null;
  checks?: number;
  verdicts?: Record<string, number>;
}

/** planner/cache/<region_id>/<input_compact>.json (schema "wfg.planner.cache/1") */
export interface WireCacheFile {
  schema: string;
  region_id: string;
  scenario_set_id: string;
  input_time: string;
  fire_input: WireFireInput;
  created_at: string;
  api: { base: string; mode: string; health: WireHealth | null; host?: Record<string, unknown> | null };
  planner_commit: string | null;
  generator?: Record<string, unknown>;
  requests: WireDispatchPlanRequest[];
  /** one job per planned request; null when the API refused the request (see rejected_requests) */
  plans: (WireDispatchPlanJob | null)[];
  route_checks: Record<string, WireRouteCheckJob>;
  travel_only: Record<string, WireRouteCheckJob>;
  /**
   * Research route-check bookkeeping. `job_id` is null when the check was not sent: `skipped` is
   * then 'WINDOW_UNSATISFIABLE' (the recorded destination window cannot be met from that offset)
   * or the API's error code for a rejected request.
   */
  research_checks?: WireCacheResearchCheck[];
  rejected_requests?: WireCacheRejected[];
}

export interface WireCacheResearchCheck {
  origin_id: string;
  destination_id: string;
  depart_offset_s: number;
  job_id?: string | null;
  skipped?: string;
}

export interface WireCacheRejected {
  kind: 'dispatch_plan' | 'route_check' | 'travel_only' | (string & {});
  /** the refused request body (newer files) */
  request?: Record<string, unknown>;
  /** API error code (newer files) */
  code?: string;
  origins?: string[];
  origin_id?: string;
  depart_offset_s?: number;
  status?: number;
  error?: WireError | string | Record<string, unknown>;
}
