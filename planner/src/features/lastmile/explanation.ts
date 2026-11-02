/**
 * Reads the deadline explanations written by tools/explain_deadlines (schema `wfg.explanation/1`,
 * `planner/public/data/explanations/<region_id>__<input_compact>.json`) and turns ONE origin's
 * entry into a reason the templates may print — or into nothing.
 *
 * Fail-closed rules (a reason is never fabricated):
 * - the file is fetched same-origin under the app's base path; 404, HTML (an SPA fallback), bad
 *   JSON, another schema, region, input time or scenario set → no file, no reason lines;
 * - an origin entry is used only when its verdict, deadline and next departure time match the
 *   planner's own result for that origin, its status is `explained` (or `explained_partial` for a
 *   flame item), and every number it carries is finite and inside the recorded scenario window;
 * - a flame reason uses only `binding[0]` (the shown route's item) and only when the message's
 *   destination is one of its `destination_ids`;
 * - `window` with `deadline_cause: time_window` is printed as a time limit — never as a fire
 *   deadline; `no_flame_avoiding_route` (cause `flames`) says only what the file proves: at the next
 *   checked time no destination can be reached in time on a road that avoids the flames;
 * - road labels follow the file's semantics: a nearby named place and the straight-line distance
 *   to it ("구암리에서 약 800 m 떨어진 도로" / "this village"), never a road name;
 * - an unknown reason or detail code gives no reason line;
 * - `unresolved` is never turned into a reason; an unresolved or out-of-window next departure gives
 *   no reason either (the planner's own "after the deadline" line is used instead).
 */
import { compactUtc, parseUtc } from '../../domain/clock';
import {
  EXPLANATION_SCHEMA,
  type ExplanationFile,
  type ExplanationItem,
  type ExplanationLabelSource,
  type ExplanationNextVerdict,
  type ExplanationOrigin,
  type LmText,
} from './types';

const STATUSES = ['explained', 'explained_partial', 'not_explainable'] as const;
const VERDICTS = ['checked_route', 'model_no_route', 'unresolved'] as const;
const NEXT_VERDICTS = ['model_no_route', 'unresolved', 'window'] as const;
const REASONS = ['flame_on_route', 'no_flame_avoiding_route', 'all_exits_blocked', 'dwell_at_destination', 'unresolved_next', 'window', 'no_later_offset', 'other'] as const;
const LABEL_SOURCES: readonly ExplanationLabelSource[] = ['osm_name', 'osm_ref', 'nearest_place', 'unnamed'];

/** Longest road label printed, as composed (longer ones make the item unusable rather than being cut). */
export const MAX_LABEL_CHARS = 40;

// ---------------------------------------------------------------- file location + loading

function defaultBase(): string {
  try {
    const b = (import.meta as unknown as { env?: { BASE_URL?: string } }).env?.BASE_URL;
    return typeof b === 'string' && b.length > 0 ? b : '/';
  } catch {
    return '/';
  }
}

/** Same-origin URL of the explanation file under the app's base path (Vite BASE_URL). */
export function explanationUrl(regionId: string, inputTimeIso: string, base: string = defaultBase()): string {
  const prefix = base.endsWith('/') ? base : `${base}/`;
  return `${prefix}data/explanations/${encodeURIComponent(regionId)}__${compactUtc(inputTimeIso)}.json`;
}

export interface ExpectedScenario {
  regionId: string;
  inputTimeIso: string;
  scenarioSetId: string;
}

export type ExplanationState =
  | { state: 'loading' }
  | { state: 'absent'; url: string }
  | { state: 'invalid'; url: string; error: string }
  | { state: 'ready'; url: string; file: ExplanationFile };

function isObj(v: unknown): v is Record<string, unknown> {
  return Boolean(v) && typeof v === 'object' && !Array.isArray(v);
}

/** Top-level check of a parsed file against the scenario on screen (origins are checked lazily). */
export function parseExplanationFile(raw: unknown, expect: ExpectedScenario): { ok: true; file: ExplanationFile } | { ok: false; error: string } {
  if (!isObj(raw)) return { ok: false, error: 'not a JSON object' };
  if (raw.schema !== EXPLANATION_SCHEMA) return { ok: false, error: `schema is ${String(raw.schema)}, expected ${EXPLANATION_SCHEMA}` };
  if (raw.region_id !== expect.regionId) return { ok: false, error: `region_id ${String(raw.region_id)} ≠ ${expect.regionId}` };
  const it = typeof raw.input_time === 'string' ? parseUtc(raw.input_time) : NaN;
  if (!Number.isFinite(it) || it !== parseUtc(expect.inputTimeIso)) return { ok: false, error: `input_time ${String(raw.input_time)} ≠ ${expect.inputTimeIso}` };
  if (raw.scenario_set_id !== expect.scenarioSetId) return { ok: false, error: `scenario_set_id ${String(raw.scenario_set_id)} ≠ ${expect.scenarioSetId}` };
  if (!isObj(raw.origins)) return { ok: false, error: 'origins missing' };
  return {
    ok: true,
    file: {
      schema: EXPLANATION_SCHEMA,
      region_id: raw.region_id as string,
      input_time: raw.input_time as string,
      scenario_set_id: raw.scenario_set_id as string,
      provenance: isObj(raw.provenance) ? raw.provenance : {},
      summary: isObj(raw.summary) ? raw.summary : {},
      origins: raw.origins as Record<string, ExplanationOrigin>,
    },
  };
}

const memo = new Map<string, Promise<ExplanationState>>();

/** Forget loaded files (tests; a new cache on screen). */
export function clearExplanationCache(): void {
  memo.clear();
}

/**
 * Loads the explanation file of a recorded scenario. Never throws: a missing or unusable file is
 * reported as `absent` / `invalid`, and the messages are then built without reason lines.
 */
export function loadExplanation(
  expect: ExpectedScenario,
  opts: { base?: string; fetchImpl?: typeof fetch; signal?: AbortSignal } = {},
): Promise<ExplanationState> {
  const url = explanationUrl(expect.regionId, expect.inputTimeIso, opts.base);
  const key = `${url}|${expect.scenarioSetId}`;
  const hit = memo.get(key);
  if (hit) return hit;
  const f = opts.fetchImpl ?? (typeof fetch === 'function' ? fetch : null);
  const p = (async (): Promise<ExplanationState> => {
    if (!f) return { state: 'absent', url };
    let r: Response;
    try {
      r = await f(url, { signal: opts.signal, headers: { Accept: 'application/json' } });
    } catch {
      return { state: 'absent', url };
    }
    if (!r.ok) return { state: 'absent', url };
    // a static host or dev server may answer an unknown path with the app's index.html
    if ((r.headers.get('content-type') ?? '').includes('text/html')) return { state: 'absent', url };
    let raw: unknown;
    try {
      raw = await r.json();
    } catch {
      return { state: 'invalid', url, error: 'not valid JSON' };
    }
    const parsed = parseExplanationFile(raw, expect);
    return parsed.ok ? { state: 'ready', url, file: parsed.file } : { state: 'invalid', url, error: parsed.error };
  })();
  memo.set(key, p);
  // an aborted request says nothing about the file: do not keep its answer
  void p.then(() => {
    if (opts.signal?.aborted) memo.delete(key);
  });
  return p;
}

// ---------------------------------------------------------------- one origin → reason

/** How a road is named in a sentence (never invented: OSM name/ref, a nearby place, or "unnamed"). */
export interface RoadLabel {
  text: LmText;
  source: ExplanationLabelSource;
  /** nearest_place labels: the place itself ("구계리" / "Gugye-ri") */
  place?: LmText;
}

export type LmReason =
  | {
      /** leave_by: the route to the message's destination, shifted to the next checked time, meets flames */
      kind: 'flame_on_route' | 'dwell_at_destination';
      road: RoadLabel;
      edgeId: string;
      /** flame start in the cell the route crosses there, in the fire scenarios (s after input time) */
      flameS: number;
      /** scenario members with contact / members in the set */
      k: number;
      n: number;
      /** margin at the deadline (s), when given and consistent */
      slackS: number | null;
    }
  | {
      /**
       * leave_by (`window`, cause `time_window`): at the next checked time no candidate destination
       * can be reached in time even without fire — a time limit, not a fire deadline
       */
      kind: 'time_window';
    }
  | {
      /**
       * leave_by (`no_flame_avoiding_route`, cause `flames`): at the next checked time no candidate
       * destination can be reached in time on a road that avoids the flames in the fire scenarios
       */
      kind: 'no_flame_avoiding_route';
    }
  | {
      /** model_no_route: every road out of the area reachable without meeting flames is blocked */
      kind: 'all_exits_blocked';
      /** distinct road labels, in file order */
      exits: RoadLabel[];
      /** number of exit roads (may exceed the distinct labels) */
      roads: number;
      /** every exit meets flames in at least kMin of n members (each road on its own) */
      kMin: number;
      n: number;
      /** every exit is already burning at the input time */
      atStart: boolean;
    }
  | {
      /** model_no_route (`all_exits_blocked` / `entry_point_in_flame`): the road entry point is in flames at departure */
      kind: 'entry_in_flame';
    }
  | {
      /** model_no_route (`no_flame_avoiding_route`): from every departure time checked, no road that avoids the flames fits the range */
      kind: 'no_route_flames';
    }
  | {
      /** model_no_route (`window`, cause `time_window`): no destination fits the range even without fire */
      kind: 'no_route_time_window';
    };

/** What the planner itself says about the origin (the explanation must agree with it). */
export interface ReasonContext {
  /** message kind built from the planner result */
  kind: 'leave_by' | 'no_route' | 'unresolved' | 'partial';
  /** planner's latest checked departure (deadline D) */
  latestS: number | null;
  /** departure time the message tells people to leave by */
  leaveByS: number | null;
  /** next requested departure after D in the planner's sweep (null: none) */
  nextOffsetS: number | null;
  nextVerdict: ExplanationNextVerdict;
  /** destination the message names (leave_by), null otherwise */
  destinationId: string | null;
  /** recorded scenario window (s) */
  horizonS: number;
}

function cleanLabel(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  const s = v.replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
  return s.length ? s : null;
}

/** "800 m" / "1.1 km": the distance rounded to 100 m (it is a straight line to a place, not along a road). */
export function approxDistance(m: number): string {
  const tenths = Math.max(1, Math.round(m / 100));
  return tenths < 10 ? `${tenths * 100} m` : `${(tenths / 10).toFixed(1)} km`;
}

/**
 * Road label in both languages, or null when the item's label is unusable. A nearest_place label
 * names a road point by a nearby place, never the road: "구암리에서 약 800 m 떨어진 도로" / "a road about
 * 800 m from Guam-ri", or "이 마을에서 … / … from this village" when the place is the origin itself.
 */
export function roadLabel(
  it: Pick<ExplanationItem, 'label_ko' | 'label_en' | 'label_source'> & Partial<Pick<ExplanationItem, 'place_distance_m' | 'place_is_origin'>>,
): RoadLabel | null {
  const src = it.label_source;
  if (!LABEL_SOURCES.includes(src)) return null;
  const ko = cleanLabel(it.label_ko);
  const en = cleanLabel(it.label_en);
  if ((ko && ko.length > MAX_LABEL_CHARS) || (en && en.length > MAX_LABEL_CHARS)) return null;
  let label: RoadLabel;
  if (src === 'unnamed' || (!ko && !en)) label = { source: 'unnamed', text: { ko: '이름 없는 도로', en: 'an unnamed road' } };
  else {
    const k = ko ?? en!;
    const e = en ?? ko!;
    if (src === 'osm_ref') label = { source: src, text: { ko: /^\d+$/.test(k) ? `${k}번 도로` : k, en: /^\d+$/.test(e) ? `Route ${e}` : e } };
    else if (src === 'nearest_place') {
      const origin = it.place_is_origin === true;
      const place = origin ? { ko: '이 마을', en: 'this village' } : { ko: k.replace(/\s*(부근|근처|인근)$/, ''), en: e.replace(/^near\s+/i, '') };
      const dm = it.place_distance_m;
      const d = typeof dm === 'number' && Number.isFinite(dm) && dm >= 0 ? approxDistance(dm) : null;
      label = {
        source: src,
        text: d ? { ko: `${place.ko}에서 약 ${d} 떨어진 도로`, en: `a road about ${d} from ${place.en}` } : { ko: `${place.ko} 부근 도로`, en: `a road near ${place.en}` },
        place,
      };
    } else label = { source: src, text: { ko: k, en: e } };
  }
  // the composed label is what a reader sees: it must stay within the tested length too
  return label.text.ko.length > MAX_LABEL_CHARS || label.text.en.length > MAX_LABEL_CHARS ? null : label;
}

function finite(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

/**
 * A binding/exit item that can be printed: finite flame time inside the recorded window, members a
 * non-empty set of distinct integers within members_total, a usable label, and — for a binding item
 * at the deadline — flame contact strictly after the vehicle passes (slack ≥ 0 when given).
 */
export function usableItem(it: unknown, horizonS: number, deadlineS: number | null): it is ExplanationItem {
  if (!isObj(it)) return false;
  if (typeof it.edge_id !== 'string' || !it.edge_id) return false;
  if (!LABEL_SOURCES.includes(it.label_source as ExplanationLabelSource)) return false;
  if (it.label_ko !== null && it.label_ko !== undefined && typeof it.label_ko !== 'string') return false;
  if (it.label_en !== null && it.label_en !== undefined && typeof it.label_en !== 'string') return false;
  if (!roadLabel(it as unknown as ExplanationItem)) return false;
  if (!finite(it.flame_time_s) || it.flame_time_s < 0 || it.flame_time_s > horizonS) return false;
  const total = it.members_total;
  if (!Number.isInteger(total) || (total as number) < 1) return false;
  const members = it.members;
  if (!Array.isArray(members) || members.length < 1 || members.length > (total as number)) return false;
  // members are scenario suffixes 0 … members_total − 1
  if (!members.every((m) => Number.isInteger(m) && m >= 0 && m < (total as number))) return false;
  if (new Set(members).size !== members.length) return false;
  if (deadlineS !== null) {
    const pass = it.pass_time_at_deadline_s;
    if (pass !== null && pass !== undefined) {
      if (!finite(pass) || pass < deadlineS || !(it.flame_time_s > pass)) return false;
    } else if (!(it.flame_time_s > deadlineS)) return false;
    const slack = it.slack_s;
    if (slack !== null && slack !== undefined && (!finite(slack) || slack < 0)) return false;
  }
  return true;
}

function originEntry(v: unknown): ExplanationOrigin | null {
  if (!isObj(v)) return null;
  if (!STATUSES.includes(v.status as (typeof STATUSES)[number])) return null;
  if (!VERDICTS.includes(v.verdict_summary as (typeof VERDICTS)[number])) return null;
  if (!REASONS.includes(v.reason_code as (typeof REASONS)[number])) return null;
  if (v.next_verdict !== null && !NEXT_VERDICTS.includes(v.next_verdict as (typeof NEXT_VERDICTS)[number])) return null;
  for (const k of ['deadline_offset_s', 'next_offset_s'] as const) {
    if (v[k] !== null && !finite(v[k])) return null;
  }
  if (!Array.isArray(v.binding) || !Array.isArray(v.exits)) return null;
  return v as unknown as ExplanationOrigin;
}

/**
 * The reason to print for one origin, or null. `entry` is `file.origins[originId]` (any shape).
 */
export function selectReason(entry: unknown, ctx: ReasonContext): LmReason | null {
  const e = originEntry(entry);
  if (!e || e.status === 'not_explainable') return null;
  if (ctx.kind === 'leave_by') {
    if (e.verdict_summary !== 'checked_route') return null;
    // the explanation is about the deadline D; a message based on an earlier time gets none
    if (ctx.latestS === null || ctx.leaveByS !== ctx.latestS) return null;
    if (e.deadline_offset_s !== ctx.latestS) return null;
    if (e.next_offset_s !== ctx.nextOffsetS || e.next_verdict !== ctx.nextVerdict) return null;
    // only a recorded "no route" at the next departure is explained; never unresolved
    if (e.next_verdict !== 'model_no_route' || ctx.nextOffsetS === null) return null;
    const dest = ctx.destinationId;
    if (!dest) return null;
    if (e.reason_code === 'flame_on_route' || e.reason_code === 'dwell_at_destination') {
      // the contract's binding item is the first one (the shown route's); it must cover our destination
      const item = e.binding[0];
      if (!usableItem(item, ctx.horizonS, ctx.latestS)) return null;
      if (!Array.isArray(item.destination_ids) || !item.destination_ids.includes(dest)) return null;
      return {
        kind: e.reason_code,
        road: roadLabel(item)!,
        edgeId: item.edge_id,
        flameS: item.flame_time_s,
        k: item.members.length,
        n: item.members_total,
        slackS: finite(item.slack_s) ? item.slack_s : null,
      };
    }
    // claims about every candidate destination need a fully proven entry and an established cause
    if (e.status !== 'explained') return null;
    if (e.reason_code === 'window' && e.deadline_cause === 'time_window') return { kind: 'time_window' };
    if (e.reason_code === 'no_flame_avoiding_route' && e.deadline_cause === 'flames') return { kind: 'no_flame_avoiding_route' };
    return null;
  }
  if (ctx.kind === 'no_route') {
    if (e.verdict_summary !== 'model_no_route' || e.status !== 'explained') return null;
    if (e.reason_code === 'window' && e.deadline_cause === 'time_window') return { kind: 'no_route_time_window' };
    if (e.reason_code === 'no_flame_avoiding_route' && e.deadline_cause === 'flames') return { kind: 'no_route_flames' };
    if (e.reason_code !== 'all_exits_blocked') return null;
    if (e.detail_code === 'entry_point_in_flame') return { kind: 'entry_in_flame' };
    // "all n roads" is printed only when every exit item is usable
    if (e.exits.length === 0 || !e.exits.every((it) => usableItem(it, ctx.horizonS, null))) return null;
    const totals = new Set(e.exits.map((it) => it.members_total));
    if (totals.size !== 1) return null;
    const labels: RoadLabel[] = [];
    for (const it of e.exits) {
      const l = roadLabel(it)!;
      if (!labels.some((x) => x.text.ko === l.text.ko && x.text.en === l.text.en)) labels.push(l);
    }
    return {
      kind: 'all_exits_blocked',
      exits: labels,
      roads: e.exits.length,
      kMin: Math.min(...e.exits.map((it) => it.members.length)),
      n: e.exits[0]!.members_total,
      atStart: e.exits.every((it) => it.flame_time_s === 0),
    };
  }
  return null;
}
