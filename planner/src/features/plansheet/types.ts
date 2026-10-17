/**
 * Input of the plan sheet (기관용 사전 대피계획서): ONE origin (village or care facility) per sheet.
 * Self-contained so the core can build it from its store (cache or live results) without the sheet
 * knowing wire formats. All times are seconds after the scenario's input time (UTC) unless noted.
 *
 * Honesty rules the sheet applies (ARCHITECTURE.md §0):
 * - `route` must only be given for a checked_route result; the sheet ignores it otherwise.
 * - `travelOnlyRoute` is a travel-time-only comparison (policy travel_only), drawn dashed and
 *   labelled "비교용 — 대피 경로 아님"; it is never presented as an evacuation route.
 * - unresolved is never shown as safe and never counts toward a deadline.
 */
import type { Feature, LineString } from 'geojson';
import type { Verdict } from '../../domain/types';

/** A sweep cell: the verdict at one departure offset, or `window_closed` when no arrival can meet
 *  the destination's recorded arrival window (the API refuses such a request: WINDOW_UNSATISFIABLE). */
export type SweepVerdict = Verdict | 'window_closed';

export interface PlanSheetSweepCell {
  offsetS: number;
  verdict: SweepVerdict;
  /** unresolved cells: reason code / raw status of the first unresolved attempt at this offset */
  reasonCode?: string | null;
  rawStatus?: string | null;
}

export interface PlanSheetExposure {
  scenarioId: string;
  /** maximum instantaneous heat flux over the journey (kW/m²) */
  peakKwM2: number | null;
  /** cumulative dose incl. incurred (kJ/m²) */
  doseKjM2: number | null;
  contact: boolean | null;
}

export interface PlanSheetShelter {
  id: string;
  name: string | null;
  sourceTag: string;
  lon: number;
  lat: number;
  /** arrival at the shelter, s after input time (null when not checked) */
  arrivalS: number | null;
  /** optional category label, e.g. "학교" */
  categoryLabel?: string;
}

export interface PlanSheetScenario {
  scenarioSetId: string;
  /** recorded input time (UTC ISO, e.g. 2025-03-24T09:00:00Z); offsets are seconds after it */
  inputTimeIso: string;
  /** drawn zones only: issued time of the zones; the wall clock is then issued + offset with T+h:mm */
  issuedAtIso?: string | null;
  bestVerdict: Verdict;
  /** latest offset with a checked route (contract latest_checked_depart_offset_s) */
  latestSafeDepartureS: number | null;
  /** last offset such that every offset from the earliest up to it is checked (contract v1.4) */
  contiguousSafeDepartureS: number | null;
  sweep: PlanSheetSweepCell[];
  /** shelter of the shown route (best attempt at the latest checked offset), else null */
  shelter: PlanSheetShelter | null;
  /** departure offset of the shown route (defaults to latestSafeDepartureS) */
  departureS?: number | null;
  /** checked route geometry (WGS84), only for checked_route; properties.times_s optional */
  route: Feature<LineString> | null;
  /** travel-time-only comparison route (policy travel_only), optional */
  travelOnlyRoute: Feature<LineString> | null;
  /** recorded full-policy grade of the travel-only route (false = it would fail the full check) */
  travelOnlyFullPolicyPass?: boolean | null;
  /** per hazard scenario (4 members) exposure of the shown checked route */
  exposure: PlanSheetExposure[];
  /** limits used (default 10 kW/m², 100 kJ/m²) */
  limits?: { peakKwM2: number; doseKjM2: number } | null;
  /** compute time of the shown check (s), recorded or live; without a route, of the earliest attempt with one */
  computeS: number | null;
  /** departure offset of the check that `computeS` belongs to (s after input time) */
  computeOffsetS?: number | null;
  /** host label, e.g. "Apple M5 Pro · macOS (기록)" or "Linux x86_64 · 4 vCPU" */
  host: string | null;
  /** unresolved reason code of the best attempt (contract ReasonCode), else null */
  reasonCode: string | null;
  /** raw status of that attempt (e.g. MOCK_NO_RECORDED_RESULT), shown instead of OTHER */
  rawStatus?: string | null;
  /** planner-side note when the API was never asked (e.g. no entry point within 2 km) */
  note?: 'not_checkable' | 'rejected' | 'not_computed' | null;
}

export interface PlanSheetData {
  region: { id: string; nameKo: string; nameEn: string; fireYear: number | null };
  /** banner text, e.g. "2025년 실제 산불 기록 기반 시나리오 재현" or "사용자 입력 확산 구역 (가정)" */
  fireInputLabel: string;
  /** recorded (default) or drawn spread zones */
  fireInputType?: 'recorded' | 'spread_zones';
  mock: boolean;
  origin: {
    id: string;
    name: string | null;
    nameEn?: string | null;
    /** descriptor for places without an OSM name, e.g. "기록 임무 FD1 출발점" (never an invented name) */
    displayName?: string | null;
    /** e.g. "마을", "요양시설" (already localised by the core) */
    categoryLabel: string;
    sourceTag: string;
    lon: number;
    lat: number;
    /** distance from the OSM point to its 진입 지점 (m); travel over it is not modelled */
    snapDistanceM: number | null;
    /** what the entry point is called on the sheet; research origins start at their recorded node */
    entryKind?: 'village' | 'facility' | 'research' | null;
    /** the 진입 지점 road node the checks start at (sent as node_id) */
    entryNode?: string | null;
    vulnerable: boolean;
  };
  /** drawn zones: Ready-Set-Go tag of the origin (planner-side point-in-polygon), e.g. "실행(Go) — 전원 대피" */
  rsgLabel?: string | null;
  /** vulnerable facilities near the village (with source tags), nearest first */
  facilities: { id: string; name: string | null; categoryLabel: string; sourceTag: string; distanceM: number }[];
  scenarios: PlanSheetScenario[];
  /** when the sheet data was assembled (ISO) */
  generatedAtIso: string;
  provenance: {
    checkpoint: string;
    packageVersion: string;
    kit: string;
    apiMode: 'mock' | 'live' | 'cache';
    apiVersion: string | null;
    cacheCreatedAtIso: string | null;
    gitCommit: string | null;
    /** optional: mode of the API that produced the cache (cache files record it) */
    cacheApiMode?: 'mock' | 'live' | null;
    /** spread_zones: the API's provenance.approximation ("approximation, requires expert review") */
    approximation?: string | null;
    /** recorded final-panel mission whose request is identical (contract v1.1 recorded_mission_match) */
    recordedMissionMatch?: string | null;
    /** computed on a host other than the evaluated booth host: test data, not the booth cache */
    testData?: boolean | null;
    /** MOCK: true when no check of this origin matched a recorded execution (nothing replayed) */
    mockNothingReplayed?: boolean | null;
  };
}
