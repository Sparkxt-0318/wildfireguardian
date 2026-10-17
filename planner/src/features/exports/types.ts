/**
 * Input of the client-side exports (GeoJSON / KML of a selected route, CSV dispatch list).
 * Used for cache/offline data; when the API is live the core may prefer the API's own
 * `/route-checks/{id}/export` endpoint for single routes.
 *
 * All times are seconds after `scenario.inputTimeIso` (UTC). Every export carries the fire-input
 * label, the MOCK flag and provenance.
 */
import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson';
import type { Policy, Verdict } from '../../domain/types';

export interface ExportPlace {
  id: string;
  name: string | null;
  nameEn?: string | null;
  /** localised category, e.g. "마을", "학교" */
  categoryLabel: string;
  /** exact source tag, e.g. "place=village" or "request <case> origin node osm:…" */
  sourceTag: string;
  lon: number;
  lat: number;
}

export interface ExportOriginPlan {
  bestVerdict: Verdict;
  latestSafeDepartureS: number | null;
  /** contract v1.4 latest_contiguous_checked_depart_offset_s */
  contiguousSafeDepartureS: number | null;
  sweep?: { offsetS: number; verdict: Verdict | 'window_closed' }[];
  /** best attempt at the latest checked offset (checked origins only) */
  best: { shelter: ExportPlace; departureS: number; arrivalS: number | null } | null;
  /** unresolved reason code (contract ReasonCode) when known */
  reasonCode?: string | null;
  /** planner-side note when the API was never asked */
  note?: 'not_checkable' | 'rejected' | 'not_computed' | null;
}

export interface ExportOrigin extends ExportPlace {
  vulnerable: boolean;
  /** drawn zones: Ready-Set-Go tag text (planner-side point-in-polygon), e.g. "실행(Go) — 전원 대피" */
  rsgLabel?: string | null;
  /** 1-based urgency rank from the API / core; when absent the export sorts by the planner rule */
  urgencyRank?: number | null;
  /** null = no result at all (shown as unresolved, never safe) */
  plan: ExportOriginPlan | null;
}

export interface ExportProvenance {
  checkpoint: string;
  packageName?: string;
  packageVersion: string;
  kit: string;
  apiMode: 'mock' | 'live' | 'cache';
  /** for apiMode 'cache': the mode of the API that produced the cache */
  cacheApiMode?: 'mock' | 'live' | null;
  apiVersion: string | null;
  gitCommit: string | null;
  cacheCreatedAtIso: string | null;
  scenarioSetId: string | null;
  scenarioIds?: string[];
  inputHashes?: Record<string, string>;
  graphId?: string | null;
  hostLabel?: string | null;
  evaluatedConfiguration?: boolean | null;
  recordedMissionMatch?: string | null;
  approximation?: string | null;
}

export type RouteRole = 'evacuation_route' | 'travel_only_comparison';

export interface ExportRoute {
  /** evacuation_route = checked full-policy route; travel_only_comparison = dashed comparison only */
  role: RouteRole;
  origin: ExportPlace;
  shelter: ExportPlace;
  /** verdict of this check under its own policy */
  verdict: Verdict;
  policy: Policy;
  /** travel_only: recorded/offline full-hazard grade (false = would fail the full check) */
  fullPolicyPass?: boolean | null;
  fullPolicyFailures?: string[] | null;
  departureS: number | null;
  arrivalS: number | null;
  dwellEndS?: number | null;
  /** WGS84 vertices [lon, lat] */
  coordinates: [number, number][];
  /** one time per vertex (s after input time) */
  timesS: number[];
  lengthM?: number | null;
  exposure?: { scenarioId: string; peakKwM2: number | null; doseKjM2: number | null; contact: boolean | null }[];
  computeS?: number | null;
  jobId?: string | null;
  /** provenance of this check (falls back to the input's provenance) */
  provenance?: ExportProvenance | null;
}

export interface ExportInput {
  region: { id: string; nameKo: string; nameEn: string; fireYear: number | null };
  /** banner text, e.g. "2025년 실제 산불 기록 기반 시나리오 재현" */
  fireInputLabel: string;
  fireInputType?: 'recorded' | 'spread_zones';
  mock: boolean;
  scenario: {
    scenarioSetId: string | null;
    inputTimeIso: string;
    /** drawn zones: issued time (wall clock = issued + offset) */
    issuedAtIso?: string | null;
  };
  /**
   * drawn zones: the user-drawn spread zones (assumption) as an extra GeoJSON layer — one feature per
   * zone with properties.arrival_h_max (plus label, vertex count, area)
   */
  zones?: FeatureCollection<Polygon | MultiPolygon> | null;
  /** every origin of the dispatch list */
  origins: ExportOrigin[];
  /** route of the selected origin, if any (must be checked_route to be exported) */
  selectedRoute: ExportRoute | null;
  /** optional travel-time-only comparison of the selected origin */
  comparisonRoute?: ExportRoute | null;
  provenance: ExportProvenance;
  generatedAtIso: string;
}
