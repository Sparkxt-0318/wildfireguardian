/**
 * wfg.explanation/1 — deadline explanations written by tools/explain_deadlines (see its README.md).
 * One file per recorded scenario set: public/data/explanations/<region_id>__<inputYYYYMMDDTHHMMSSZ>.json.
 * All times are seconds after `input_time`. Only the fields the UI reads are typed strictly.
 */
import type { Verdict } from '../../domain/types';

export const EXPLANATION_SCHEMA = 'wfg.explanation/1';

export type ExplStatus = 'explained' | 'explained_partial' | 'not_explainable';
export type ExplReason =
  | 'flame_on_route'
  | 'no_flame_avoiding_route'
  | 'all_exits_blocked'
  | 'dwell_at_destination'
  | 'unresolved_next'
  | 'window'
  | 'no_later_offset'
  | 'other';
export type ExplLabelSource = 'osm_name' | 'osm_ref' | 'nearest_place' | 'unnamed';

export interface ExplItem {
  edge_id: string | null;
  osm_way_id?: number | null;
  label_ko: string | null;
  label_en: string | null;
  label_source: ExplLabelSource;
  place_osm_id?: string | null;
  /** OSM place=* value of the named place (village, hamlet, town, ...) */
  place_kind?: string | null;
  /** straight-line distance (m, EPSG:5179) from the road point to the named place */
  place_distance_m?: number | null;
  /** the named place is the origin itself */
  place_is_origin?: boolean;
  near_node_id?: string | null;
  point?: [number, number] | null;
  /** predicted flame start in the cell (0 = burning at the input time) */
  flame_time_s: number;
  /** when the journey meets the flame (binding: leaving at the next offset; exits: reaching the road as early as possible) */
  contact_time_s?: number | null;
  /** scenario member suffixes (0-3) with contact */
  members: number[];
  members_total: number;
  /** binding only: when the vehicle leaving at the deadline leaves that 375 m cell */
  pass_time_at_deadline_s: number | null;
  /** binding only: flame_time_s - pass_time_at_deadline_s */
  slack_s: number | null;
  segment?: 'edge' | 'issue' | 'wait' | 'dwell';
  /** binding only: router-grid cells of the earliest contact at N and of the smallest margin (pass/flame/slack) */
  contact_cell?: number | null;
  slack_cell?: number | null;
  reached_at_s?: number | null;
  destination_ids?: string[];
}

export interface ExplWindow {
  close_s: number;
  open_s?: number;
  dwell_s?: number;
  fire_free: boolean | null;
  fastest_end_s: number | null;
  flame_avoiding_arrival_s: number | null;
  limit?: 'scenario_window' | 'arrival_window';
  horizon_s?: number;
}

/** One shelter considered at the next departure time (checked at the deadline or tried at the next time). */
export interface ExplShelter {
  destination_id: string;
  checked_at_deadline: boolean;
  tried_next: boolean;
  class: string;
  proven: boolean;
  close_s: number | null;
  dwell_s: number | null;
  /** a fire-free road would finish the stay by close_s */
  fire_free_fits: boolean | null;
  fire_free_end_s: number | null;
  flame_avoiding_arrival_s: number | null;
}

export interface ExplOrigin {
  status: ExplStatus;
  verdict_summary: Verdict;
  deadline_offset_s: number | null;
  next_offset_s: number | null;
  next_verdict: 'model_no_route' | 'unresolved' | 'window' | null;
  reason_code: ExplReason;
  binding: ExplItem[];
  exits: ExplItem[];
  notes: string[];
  detail_code?: string | null;
  window?: ExplWindow | null;
  deadline_route?: { route_check_job_id: string | null; destination_id: string | null; arrival_s?: number | null; dwell_s?: number | null } | null;
  /** class per shelter checked at the deadline (window_fire_free, window_fire_detour, flame_on_route, ...) */
  destination_classes?: Record<string, string>;
  /** what keeps a later departure from working: the time window alone, or the flames (null: not established) */
  deadline_cause?: 'time_window' | 'flames' | null;
  shelters_next?: ExplShelter[];
  checked_at_deadline?: number;
  proven_unreachable_next?: number;
  /** model_no_route origins: the first checked departure offset */
  first_offset_s?: number | null;
  checks?: Record<string, boolean>;
}

/** Where tools/explain_deadlines computed the file (Python's platform.platform/system/machine and library versions). */
export interface ExplComputedOn {
  platform?: string;
  system?: string;
  machine?: string;
  python?: string;
  numpy?: string;
  pyproj?: string;
}

export interface ExplFile {
  schema: string;
  region_id: string;
  input_time: string;
  scenario_set_id: string;
  provenance: {
    cache_sha256?: string;
    packet_hashes?: Record<string, string>;
    graph_sha256?: string;
    code_commit?: string | null;
    generated_at?: string;
    horizon_s?: number;
    /** scenario ids of the set (4 members) */
    members?: string[];
    computed_on?: ExplComputedOn | null;
    /** true only for a run on the evaluated host (generate --evaluated-host, native macOS arm64); else not an evaluated-host computation */
    evaluated_host?: boolean;
  };
  summary: { origins: number; explained: number; explained_partial: number; not_explainable: number; by_reason: Record<string, number> };
  origins: Record<string, ExplOrigin>;
}

/** What the planner currently shows for the origin (to refuse an explanation that belongs to other results). */
export interface ShownPlan {
  bestVerdict: Verdict;
  deadlineS: number | null;
  /** destination of the route shown for the deadline (best attempt), when known */
  bestDestinationId?: string | null;
  /** route-check job of that attempt, when known */
  bestJobId?: string | null;
}
