/**
 * Last-mile kit (현장 전달 문구) — input model and the explanation contract it reads.
 *
 * The input is built from the planner's internal model (src/domain/types.ts) by ./input.ts; the
 * templates never see wire formats. All times are seconds after the scenario's input time (UTC);
 * the wall clock shown is KST (UTC+9).
 */
import type { Verdict } from '../../domain/types';

/** Languages the templates are written in. Korean is the source text; see ./strings.ts LANGUAGES. */
export type LmLang = 'ko' | 'en';

export type LmText = Record<LmLang, string>;

export type LmCellVerdict = Verdict | 'window_closed';

export interface LmAttempt {
  destinationId: string;
  verdict: Verdict;
  /** arrival at the destination, s after the input time (checked attempts only) */
  arrivalS: number | null;
}

export interface LmCell {
  offsetS: number;
  /** best verdict over destinations at this offset; window_closed = not requested (arrival window) */
  verdict: LmCellVerdict;
  attempts: LmAttempt[];
}

export interface LmDestination {
  id: string;
  /** the OSM name (null when OSM has none) */
  name: LmText | null;
  /** what the planner calls the place (name or descriptor) — never invented */
  display: LmText;
  category: LmText;
}

export type LmOriginKind = 'village' | 'facility' | 'research';

export interface LastMileInput {
  region: { id: string; name: LmText; fireYear: number | null };
  /** fire-input banner text, e.g. "2025년 실제 산불 기록 기반 시나리오 재현" */
  fireInputLabel: LmText;
  /** recorded scenario replay (only recorded fire inputs are supported) */
  replay: boolean;
  /** data from the MOCK server (the planner's session-wide MOCK rule, state/selectors.ts isMockActive) */
  mock: boolean;
  /**
   * THIS origin's result is not established as output of the evaluated host (native macOS arm64): a
   * precomputed cache made on another host, or a result of this session's API checks whose compute
   * host is another or unknown one (src/api/cache.ts isTestDataHost). Marked in every output ("시험
   * 데이터 · 평가 호스트 아님"). Never set for a live origin without any API result (nothing computed).
   */
  testData: boolean;
  scenario: {
    scenarioSetId: string;
    /** recorded input time (UTC ISO) — the data time of every message */
    inputTimeIso: string;
    /** recorded scenario window (s), 3600 for the recorded sets */
    horizonS: number;
  };
  origin: {
    id: string;
    /** the OSM name (null when OSM has none) */
    name: LmText | null;
    /** what the planner calls the place (name or descriptor such as "이름 없는 마을 · node 1") */
    display: LmText;
    category: LmText;
    kind: LmOriginKind;
    vulnerable: boolean;
    /** distance from the OSM point to its 진입 지점 (road entry node), m */
    entryDistanceM: number | null;
    sourceTag: string;
  };
  /** null: no result at all (shown as unresolved, never safe) */
  plan: {
    bestVerdict: Verdict;
    latestSafeDepartureS: number | null;
    contiguousSafeDepartureS: number | null;
    sweep: LmCell[];
    note: 'not_checkable' | 'rejected' | 'not_computed' | null;
  } | null;
  destinations: Record<string, LmDestination>;
  /** 1-based position in the planner's urgency order */
  urgencyRank: number;
  /** where THIS origin's result comes from — its own plan's source, never the session's */
  provenance: {
    /** 'cache': the precomputed cache on screen; 'live': checks run through the API in this session */
    source: 'cache' | 'live';
    /**
     * the source holds a result for THIS origin: at least one route check with a job id. false —
     * nothing was computed for it (not computed yet, not checkable, or refused): no output calls it
     * computed (the result source says "… · 이 출발지 결과 없음 / … · no result for this origin").
     */
    computed: boolean;
    /** cache results: the cache file under planner/cache/ and its created_at */
    cachePath: string | null;
    cacheCreatedAtIso: string | null;
    /** live results: the compute host(s) their route provenance reports, as the planner labels them; null when unknown */
    host: LmText | null;
    /**
     * live results: those of the reported hosts that are NOT the evaluated host (the test-data note
     * names only these); null when none of them has a label. Absent: the same as `host`.
     */
    testHost?: LmText | null;
  };
  /** when the messages were assembled (ISO) */
  generatedAtIso: string;
}

// ---------------------------------------------------------------- explanation file (P2)

/**
 * `planner/public/data/explanations/<region_id>__<inputYYYYMMDDTHHMMSSZ>.json`, schema
 * `wfg.explanation/1`, written by tools/explain_deadlines. Times are seconds after `input_time`.
 */
export const EXPLANATION_SCHEMA = 'wfg.explanation/1';

export type ExplanationStatus = 'explained' | 'explained_partial' | 'not_explainable';
export type ExplanationVerdict = 'checked_route' | 'model_no_route' | 'unresolved';
export type ExplanationNextVerdict = 'model_no_route' | 'unresolved' | 'window' | null;
export type ExplanationReasonCode =
  | 'flame_on_route'
  | 'no_flame_avoiding_route'
  | 'all_exits_blocked'
  | 'dwell_at_destination'
  | 'unresolved_next'
  | 'window'
  | 'no_later_offset'
  | 'other';
export type ExplanationLabelSource = 'osm_name' | 'osm_ref' | 'nearest_place' | 'unnamed';

export interface ExplanationItem {
  edge_id: string;
  label_ko: string | null;
  label_en: string | null;
  label_source: ExplanationLabelSource;
  /** flame start in the grid cell the route crosses there, in the fire scenarios (s after input_time) */
  flame_time_s: number;
  /** scenario members (suffixes 0 … members_total − 1) with flame contact there */
  members: number[];
  members_total: number;
  /** when the vehicle departing at the deadline leaves that cell (s after input_time) */
  pass_time_at_deadline_s: number | null;
  /** flame start minus passing time at the deadline (s) */
  slack_s: number | null;
  /** when the vehicle leaving at the next departure time meets the flame (s after input_time) */
  contact_time_s?: number | null;
  /** binding items: the destinations whose routes share this item (the shown route's item comes first) */
  destination_ids?: string[];
  /** nearest_place labels: straight-line distance (m) from the road point the item is about to the place node */
  place_distance_m?: number | null;
  /** nearest_place labels: the place node is the origin itself ("this village") */
  place_is_origin?: boolean;
  /** nearest_place labels: the place's OSM `place` value (village, hamlet, …) */
  place_kind?: string | null;
}

/** Window facts of an origin (reason `window` and the classes behind it). */
export interface ExplanationWindow {
  close_s: number;
  dwell_s?: number;
  fire_free: boolean | null;
  fastest_end_s: number | null;
  flame_avoiding_arrival_s: number | null;
  limit: string;
  horizon_s: number;
}

export interface ExplanationOrigin {
  status: ExplanationStatus;
  verdict_summary: ExplanationVerdict;
  deadline_offset_s: number | null;
  next_offset_s: number | null;
  next_verdict: ExplanationNextVerdict;
  reason_code: ExplanationReasonCode;
  binding: ExplanationItem[];
  exits: ExplanationItem[];
  notes: string[];
  /** finer machine code, e.g. window_fire_free · window_fire_detour · last_checked_offset */
  detail_code?: string;
  /** what keeps a later departure from working, over every candidate shelter: the time window, the flames, or not established */
  deadline_cause?: 'time_window' | 'flames' | null;
  /** per candidate shelter at the next checked time (class, proven, …) */
  shelters_next?: unknown[];
  window?: ExplanationWindow;
  /** class of every destination checked at the deadline (window_fire_free, flame_on_route, …) */
  destination_classes?: Record<string, string>;
  /** destinations with a checked route at the deadline / of those, proven unreachable at the next time */
  checked_at_deadline?: number;
  proven_unreachable_next?: number;
  /** the planner's shown route at the deadline */
  deadline_route?: { destination_id?: string; departure_s?: number; arrival_s?: number };
}

export interface ExplanationFile {
  schema: typeof EXPLANATION_SCHEMA;
  region_id: string;
  input_time: string;
  scenario_set_id: string;
  provenance: Record<string, unknown>;
  summary: Record<string, unknown>;
  origins: Record<string, ExplanationOrigin>;
}
