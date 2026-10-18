/**
 * Internal model of the planner (planner/docs/ARCHITECTURE.md §6). The UI only sees these types;
 * the wire format of the Route-Check API lives in src/api/wire.ts and is mapped by src/api/adapter.ts.
 */
import type { FeatureCollection, Polygon } from 'geojson';

export type Verdict = 'checked_route' | 'model_no_route' | 'unresolved';

export const VERDICTS: readonly Verdict[] = ['checked_route', 'model_no_route', 'unresolved'];

export type FireInput =
  | { type: 'recorded'; scenarioSetId: string; inputTime: string }
  | {
      type: 'spread_zones';
      issuedAt: string;
      inputTime: string;
      zones: FeatureCollection;
      marginMin: number;
      burningScenarioSetId: string | null;
    };

export interface Attempt {
  offsetS: number;
  destinationId: string;
  verdict: Verdict;
  arrivalS: number | null;
  computeS: number | null;
  jobId: string | null;
  reasonCode: string | null;
  /** original authoritative status string when the API gives one (e.g. MOCK_NO_RECORDED_RESULT) */
  rawStatus?: string | null;
  lowerBoundS?: number | null;
  /**
   * set when this attempt is the result of a re-check (precompute --recheck-timeouts) that
   * replaced the original attempt: the original route_check_job_id
   */
  recheckOf?: string | null;
}

/**
 * Why a departure offset has no check at all. `window_unsatisfiable`: the recorded destination
 * window cannot be met from this offset (max(offset, open) + dwell > min(close, horizon)), so the
 * API was not asked (it would answer 422 WINDOW_UNSATISFIABLE). Shown as "시간창 밖" — never safe.
 * Only `window_unsatisfiable` is produced by the planner (a request the API refused is an
 * unresolved attempt with the API's code, not a skip). Any other value is treated as an
 * unresolved, unchecked offset — never as "시간창 밖" and never skipped by the deadline rules.
 */
export type SkipReason = 'window_unsatisfiable' | (string & {});

export interface SweepCell {
  offsetS: number;
  /** best over destinations at this offset; 'unresolved' for skipped or unchecked cells */
  verdict: Verdict;
  attempts: Attempt[];
  best?: Attempt;
  /** set when no check exists for this offset (not counted in verdicts or deadlines) */
  skipped?: SkipReason;
}

export interface VerdictWindow {
  verdict: Verdict;
  /** first departure offset of the run (s after input time) */
  fromS: number;
  /** last departure offset of the run, inclusive */
  toS: number;
  /** run of "시간창 밖" cells (skipped as window_unsatisfiable only) */
  skipped?: boolean;
}

/** Why an origin has no API result at all (it is then shown as unresolved). */
export type PlanNote = 'not_checkable' | 'rejected' | 'not_computed';

export interface OriginPlan {
  originId: string;
  /** latest offset with a checked route (user's definition of the departure deadline) */
  latestSafeDepartureS: number | null;
  /**
   * contract rule `latest_contiguous_checked_depart_offset_s`: last offset such that every
   * (checked-for) offset from the earliest up to it has a checked route
   */
  contiguousSafeDepartureS: number | null;
  bestVerdict: Verdict;
  /** earliest-arrival checked attempt at the latest safe departure */
  best?: Attempt;
  sweep: SweepCell[];
  windows: VerdictWindow[];
  source: 'cache' | 'live';
  mock: boolean;
  /** snap reported by the API for this origin, when known */
  apiSnap?: SnapInfo | null;
  note?: PlanNote;
  rejectReason?: { code: string; message: string } | null;
}

export type PlaceRole = 'origin' | 'destination' | 'research_origin' | 'research_destination';

export type PlaceCategory =
  | 'village'
  | 'hamlet'
  | 'nursing_home'
  | 'social_facility'
  | 'shelter'
  | 'assembly_point'
  | 'school'
  | 'community_hall'
  | 'temporary_housing'
  | 'research';

export interface RecordedMission {
  destinationId: string;
  destinationNode: string;
  departOffsetS: number;
  dwellS: number;
  destinationWindow: [number, number];
  incurredDoseKjM2: number | null;
  limits: { peakKwM2: number; doseKjM2: number } | null;
  horizonS: number | null;
}

export interface Place {
  id: string;
  role: PlaceRole;
  category: PlaceCategory;
  name: string | null;
  nameEn: string | null;
  lon: number;
  lat: number;
  source: string;
  sourceTag: string;
  osm: { type: string; id: number } | null;
  snapNode: string | null;
  /** distance from the point to snapNode (m) */
  snapDistanceM: number | null;
  /**
   * 진입 지점 (entry point): nearest road node of the largest strongly connected component — the
   * node the planner sends as {node_id} (ARCHITECTURE.md §4.2). null for older data.
   */
  entry: { node: string; lon: number; lat: number; distanceM: number; withinApiLonlatSnap: boolean } | null;
  /** false only when no accepted road node lies within 2 km (점검 불가) */
  checkable: boolean;
  vulnerable: boolean;
  scenarioSetId: string | null;
  inputTime: string | null;
  caseId: string | null;
  recorded: RecordedMission | null;
}

export interface ScenarioSet {
  id: string;
  inputTime: string;
  scenarioIds: string[];
  /** null when only known from a source that does not state it */
  horizonS: number | null;
  hazardSha256: string | null;
  /** where the planner learned about this scenario set */
  source: 'api' | 'cache' | 'places';
}

/** Region as listed in /data/regions/index.json (static, always available offline). */
export interface RegionIndexEntry {
  id: string;
  nameKo: string;
  nameEn: string;
  fireYear: number | null;
  eventId: string | null;
  bbox: [number, number, number, number] | null;
  center: [number, number] | null;
  zoom: number | null;
  demo: boolean;
  counts: { origins: number; destinations: number; research: number } | null;
}

/** Region as served by GET /regions. */
export interface ApiRegion {
  id: string;
  nameKo: string;
  nameEn: string;
  eventId: string | null;
  bbox: [number, number, number, number];
  graphId: string;
  graphSha256: string | null;
  nodeCount: number;
  edgeCount: number;
  allowedNodeCount: number | null;
  inputTimes: string[];
  scenarioSets: ScenarioSet[];
  fireYear: number | null;
}

export interface SnapInfo {
  nodeId: string;
  distanceM: number;
  lon: number;
  lat: number;
  input: 'lonlat' | 'node_id';
}

export interface HostInfo {
  /** true for results replayed from the recorded campaign (mock) */
  recorded: boolean;
  machine: string | null;
  os: string | null;
  platform: string | null;
  cpuCount: number | null;
}

export interface ProvenanceInfo {
  apiVersion: string | null;
  packageName: string | null;
  packageVersion: string | null;
  kit: string | null;
  checkpoint: string | null;
  gitCommit: string | null;
  gitDirty: boolean | null;
  graphId: string | null;
  region: string | null;
  inputTime: string | null;
  scenarioSetId: string | null;
  scenarioIds: string[];
  inputHashes: Record<string, string>;
  fireInputType: string | null;
  policy: string | null;
  evaluatedConfiguration: boolean | null;
  recordedMissionMatch: string | null;
  approximation: string | null;
  clock: string | null;
  host: HostInfo | null;
  generatedAt: string | null;
  mock: boolean;
}

export interface Exposure {
  scenarioId: string;
  /** 1-based member number for display (시나리오 1–4) */
  member: number;
  peakKwM2: number;
  doseKjM2: number;
  contact: boolean;
  basis: string | null;
  peakUpperKwM2: number | null;
  doseUpperKjM2: number | null;
}

export type Policy = 'full' | 'travel_only' | 'flame_only' | 'flame_peak' | 'flame_dose';

export type LocationRef = { kind: 'node'; nodeId: string } | { kind: 'lonlat'; lon: number; lat: number };

/** One single route check to send (internal form; the adapter converts it to the wire request). */
export interface CheckSpec {
  originId: string;
  destinationId: string;
  offsetS: number;
  start: LocationRef;
  destination: LocationRef;
  dwellS: number;
  window: [number, number];
  policy: Policy;
  limits: { peakKwM2: number; doseKjM2: number } | null;
  incurredDoseKjM2: number | null;
}

export interface FullPolicyAssessment {
  pass: boolean | null;
  components: string[];
  source: string | null;
  /** other descriptive fields the API reports (shown verbatim) */
  details: Record<string, string>;
}

/** A finished (or failed) single route check, adapted from a RouteCheckJob. */
export interface RouteDetail {
  jobId: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  verdict: Verdict;
  reasonCode: string | null;
  rawStatus: string | null;
  rawReason: string | null;
  policy: Policy;
  departureS: number | null;
  arrivalS: number | null;
  lowerBoundS: number | null;
  dwellEndS: number | null;
  dwellS: number | null;
  destinationWindow: [number, number] | null;
  departOffsetS: number | null;
  /** only for checked_route */
  coordinates: [number, number][] | null;
  timesS: number[] | null;
  lengthM: number | null;
  segmentCount: number | null;
  exposure: Exposure[];
  computeS: number | null;
  withinBudget: boolean | null;
  limits: { peakKwM2: number; doseKjM2: number; incurredDoseKjM2: number | null } | null;
  notes: string[];
  assumptions: Record<string, unknown> | null;
  provenance: ProvenanceInfo | null;
  snap: { start: SnapInfo; destination: SnapInfo } | null;
  /** v1.1 full_policy_assessment of a reduced-policy route */
  fullPolicy: FullPolicyAssessment | null;
  /** the accepted request in internal form (used to derive the travel-only comparison) */
  spec: Omit<CheckSpec, 'originId' | 'destinationId'> | null;
  error: { code: string; message: string } | null;
  mock: boolean;
}

export interface HealthInfo {
  status: 'ok' | 'degraded';
  apiVersion: string;
  packageVersion: string;
  kit: string;
  checkpoint: string;
  gitCommit: string;
  regions: string[];
  workers: number;
  issues: string[];
  mock: boolean;
  host: HostInfo | null;
  queued: number | null;
  /** compute budget per check reported by /health (budget_s), when given */
  budgetS: number | null;
}

export interface ForecastProps {
  p: number | null;
  burning: boolean;
  valid: boolean;
}

export interface ForecastData {
  regionId: string;
  inputTime: string;
  cells: FeatureCollection<Polygon, ForecastProps>;
  provenance: ProvenanceInfo | null;
  mock: boolean;
}

/** One dispatch request group: origins sharing one destination set (within contract limits). */
export interface DispatchGroup {
  originIds: string[];
  destinationIds: string[];
  offsetsS: number[];
}

export interface CacheEntry {
  regionId: string;
  scenarioSetId: string;
  inputTime: string;
  path: string;
  apiMode: string;
  createdAt: string;
  origins: number;
  bytes: number;
  sha256: string;
}

export interface CacheMeta {
  entry: CacheEntry;
  createdAt: string;
  apiBase: string | null;
  apiMode: string;
  plannerCommit: string | null;
  health: HealthInfo | null;
  /** machine that ran the precompute script (generator.client_host) */
  clientHost: string | null;
  /** compute host reported in the results' provenance */
  computeHost: HostInfo | null;
  stepMin: number | null;
  sheltersPerOrigin: number | null;
  wallS: number | null;
  rejectedRequests: number;
  mock: boolean;
  /**
   * true when the results were computed on a host other than the evaluated Apple-silicon macOS
   * booth host (e.g. a Linux container) or the compute host is unknown: test data, not the booth
   * cache (ARCHITECTURE.md §6). Never set for MOCK caches (they carry the MOCK badge instead).
   */
  testData: boolean;
}

/** A loaded precompute cache file in internal form. */
export interface CacheData {
  meta: CacheMeta;
  plans: Record<string, OriginPlan>;
  /** route details by job id (adapted lazily) */
  route: (jobId: string) => RouteDetail | null;
  /** travel-time-only comparison checks by origin id */
  travelOnly: Record<string, RouteDetail>;
  /** departure offsets used by the dispatch plans */
  offsetsS: number[];
  horizonS: number | null;
}
