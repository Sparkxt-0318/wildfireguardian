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
  /** data from the MOCK server */
  mock: boolean;
  /** computed on a host other than the evaluated booth host */
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
  provenance: {
    cacheCreatedAtIso: string | null;
    source: 'cache' | 'live';
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
  /** first predicted flame contact on this edge (s after input_time) */
  flame_time_s: number;
  /** scenario members with flame contact there */
  members: number[];
  members_total: number;
  /** when the vehicle departing at the deadline passes this edge (s after input_time) */
  pass_time_at_deadline_s: number | null;
  /** flame arrival minus passing time at the deadline (s) */
  slack_s: number | null;
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
