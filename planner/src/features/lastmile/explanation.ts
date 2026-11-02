/**
 * Reads the deadline explanations written by tools/explain_deadlines (schema `wfg.explanation/1`,
 * `planner/public/data/explanations/<region_id>__<input_compact>.json`) and turns ONE origin's
 * entry into a reason the templates may print — or into nothing.
 *
 * Fail-closed rules (a reason is never fabricated):
 * - the file is fetched same-origin under the app's base path; 404, HTML (an SPA fallback), bad
 *   JSON, another schema, region, input time or scenario set → no file, no reason lines;
 * - an origin entry is used only when its verdict, deadline and next departure time match the
 *   planner's own result for that origin, its status is `explained` (or `explained_partial` with a
 *   usable item), and every number it carries is finite and inside the recorded scenario window;
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
const REASONS = ['flame_on_route', 'all_exits_blocked', 'dwell_at_destination', 'unresolved_next', 'window', 'no_later_offset', 'other'] as const;
const LABEL_SOURCES: readonly ExplanationLabelSource[] = ['osm_name', 'osm_ref', 'nearest_place', 'unnamed'];

/** Longest road label printed (longer ones make the item unusable rather than being cut). */
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
}

export type LmReason =
  | {
      kind: 'flame_on_route' | 'dwell_at_destination';
      road: RoadLabel;
      edgeId: string;
      /** first predicted flame contact on that road (s after input time) */
      flameS: number;
      /** scenario members with contact / members in the set */
      k: number;
      n: number;
      /** minutes of margin at the deadline (s), when given and consistent */
      slackS: number | null;
    }
  | {
      kind: 'all_exits_blocked';
      exits: RoadLabel[];
      /** every exit meets flames in at least kMin of n members */
      kMin: number;
      n: number;
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
  /** recorded scenario window (s) */
  horizonS: number;
}

function cleanLabel(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  const s = v.replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
  return s.length ? s : null;
}

/** Road label in both languages, or null when the item's label is unusable. */
export function roadLabel(it: Pick<ExplanationItem, 'label_ko' | 'label_en' | 'label_source'>): RoadLabel | null {
  const src = it.label_source;
  if (!LABEL_SOURCES.includes(src)) return null;
  const ko = cleanLabel(it.label_ko);
  const en = cleanLabel(it.label_en);
  if ((ko && ko.length > MAX_LABEL_CHARS) || (en && en.length > MAX_LABEL_CHARS)) return null;
  if (src === 'unnamed' || (!ko && !en)) return { source: 'unnamed', text: { ko: '이름 없는 도로', en: 'an unnamed road' } };
  const k = ko ?? en!;
  const e = en ?? ko!;
  if (src === 'osm_ref') {
    return {
      source: src,
      text: { ko: /^\d+$/.test(k) ? `${k}번 도로` : k, en: /^\d+$/.test(e) ? `Route ${e}` : e },
    };
  }
  if (src === 'nearest_place') {
    const kp = k.replace(/\s*(부근|근처|인근)$/, '');
    const ep = e.replace(/^near\s+/i, '');
    return { source: src, text: { ko: `${kp} 부근 도로`, en: `the road near ${ep}` } };
  }
  return { source: src, text: { ko: k, en: e } };
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
  if (!members.every((m) => Number.isInteger(m) && m >= 0 && m <= (total as number))) return false;
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
    // only a recorded "no route" at the next departure is explained by flames; never unresolved
    if (e.next_verdict !== 'model_no_route' || ctx.nextOffsetS === null) return null;
    if (e.reason_code !== 'flame_on_route' && e.reason_code !== 'dwell_at_destination') return null;
    const item = e.binding.find((it) => usableItem(it, ctx.horizonS, ctx.latestS));
    if (!item) return null;
    const road = roadLabel(item)!;
    return {
      kind: e.reason_code,
      road,
      edgeId: item.edge_id,
      flameS: item.flame_time_s,
      k: item.members.length,
      n: item.members_total,
      slackS: finite(item.slack_s) ? item.slack_s : null,
    };
  }
  if (ctx.kind === 'no_route') {
    if (e.verdict_summary !== 'model_no_route' || e.reason_code !== 'all_exits_blocked') return null;
    // "all n roads" is printed only when every exit item is usable
    if (e.exits.length === 0 || !e.exits.every((it) => usableItem(it, ctx.horizonS, null))) return null;
    const totals = new Set(e.exits.map((it) => it.members_total));
    if (totals.size !== 1) return null;
    return {
      kind: 'all_exits_blocked',
      exits: e.exits.map((it) => roadLabel(it)!),
      kMin: Math.min(...e.exits.map((it) => it.members.length)),
      n: e.exits[0]!.members_total,
    };
  }
  return null;
}
