/**
 * Pure view model of the "왜 이 시각인가요? / Why this time?" block: sentences are filled from the structured fields of
 * wfg.explanation/1 only. No free text from the file is ever shown (`notes` are audit codes). An explanation is shown
 * only when it describes exactly the results on screen (verdict, deadline and the route-check job of the shown
 * route); otherwise a fallback.
 *
 * Recorded vs computed: a template whose text carries COMPUTED_MARK (a sentence, or an exit-list item) states something
 * computed for the explanation (not a recorded check); using one sets `marked`, and the view then carries the note
 * that explains the mark (`computedNote` in the panel, `sheetNote` once per plan sheet). `host` says where the file
 * was computed (provenance.computed_on / evaluated_host) and that no new route checks were run.
 */
import { kstClock } from '../../domain/clock';
import { formatDistanceM } from '../shared/format';
import { pick, type L10n, type Lang } from '../shared/strings';
import { COMPUTED_MARK, EXPLAIN } from './strings';
import type { ExplFile, ExplItem, ExplOrigin, ExplReason, ExplShelter, ExplStatus, ShownPlan } from './types';

export type ExplainKind = 'loading' | 'absent' | 'missing_origin' | 'no_plan' | 'mismatch' | ExplStatus;

export interface ExplainDots {
  /** member suffixes (0-based) with contact; rendered as filled dots */
  members: number[];
  total: number;
  text: string;
}

export interface ExplainView {
  kind: ExplainKind;
  reason: ExplReason | null;
  title: string;
  statusLabel: string | null;
  lines: string[];
  dots: ExplainDots | null;
  list: string[];
  basis: string | null;
  provenance: string | null;
  /** some line or list item states a value computed for the explanation (marked with COMPUTED_MARK) */
  marked: boolean;
  /** panel: what the mark means (only when marked) */
  computedNote: string | null;
  /** panel: where the explanation was computed; recorded checks replayed, no new route checks */
  host: string | null;
  /** plan sheet: the mark's meaning with the computing host, printed once per sheet (only when marked) */
  sheetNote: string | null;
}

export function fill(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

function t(s: L10n, lang: Lang, vars: Record<string, string | number> = {}): string {
  return fill(pick(s, lang), vars);
}

type Provenance = ExplFile['provenance'];

/** "Linux x86_64" / "macOS arm64" from provenance.computed_on; null when the file does not record it. */
export function computedOnText(p: Provenance): string | null {
  const c = p.computed_on;
  const sys = typeof c?.system === 'string' && c.system ? (c.system === 'Darwin' ? 'macOS' : c.system) : null;
  const machine = typeof c?.machine === 'string' && c.machine ? c.machine : null;
  return sys && machine ? `${sys} ${machine}` : (sys ?? machine);
}

/** The evaluated host is claimed only for evaluated_host true on native macOS arm64 (what the generator enforces). */
export function onEvaluatedHost(p: Provenance): boolean {
  return p.evaluated_host === true && p.computed_on?.system === 'Darwin' && p.computed_on?.machine === 'arm64';
}

/** Panel line: where the explanation was computed; anything but a consistent evaluated-host record reads "not". */
export function hostText(p: Provenance, lang: Lang): string {
  const platform = computedOnText(p);
  if (onEvaluatedHost(p)) return t(EXPLAIN.hostOn, lang, { platform: platform ?? 'macOS arm64' });
  return platform ? t(EXPLAIN.hostOff, lang, { platform }) : pick(EXPLAIN.hostOffUnknown, lang);
}

/** Plan-sheet footer note for the mark (once per sheet), with the computing host. */
export function sheetNoteText(p: Provenance, lang: Lang): string {
  const platform = computedOnText(p);
  if (onEvaluatedHost(p)) return t(EXPLAIN.sheetNoteOn, lang, { platform: platform ?? 'macOS arm64' });
  return platform ? t(EXPLAIN.sheetNoteOff, lang, { platform }) : pick(EXPLAIN.sheetNoteOffUnknown, lang);
}

function cap(s: string): string {
  return s ? s[0]!.toUpperCase() + s.slice(1) : s;
}

/** Margin as a lower bound in whole minutes (rounded down: never overstates the time available). */
export function slackText(seconds: number, lang: Lang): string {
  if (!(seconds >= 60)) return pick(EXPLAIN.underMinute, lang);
  return t(EXPLAIN.atLeastMinutes, lang, { m: Math.floor(seconds / 60) });
}

/** Clock times of two moments, with seconds when they fall in the same minute (so they never read as equal). */
export function clockPair(inputTime: string, a: number, b: number): [string, string] {
  const same = kstClock(inputTime, a) === kstClock(inputTime, b);
  return [kstClock(inputTime, a, { seconds: same }), kstClock(inputTime, b, { seconds: same })];
}

const VILLAGE_KINDS = new Set(['village', 'hamlet', 'isolated_dwelling', 'locality', 'farm']);

export function whereText(it: ExplItem, lang: Lang): string {
  const name = lang === 'en' ? (it.label_en ?? it.label_ko) : (it.label_ko ?? it.label_en);
  if (it.label_source === 'nearest_place' && name) {
    const vars = { name, dist: formatDistanceM(it.place_distance_m ?? null, lang) };
    if (!it.place_is_origin) return t(EXPLAIN.wherePlace, lang, vars);
    return t(VILLAGE_KINDS.has(it.place_kind ?? '') ? EXPLAIN.wherePlaceOrigin : EXPLAIN.wherePlaceOriginOther, lang, vars);
  }
  if ((it.label_source === 'osm_name' || it.label_source === 'osm_ref') && name) return t(EXPLAIN.whereNamed, lang, { name });
  return t(EXPLAIN.whereUnnamed, lang, { node: it.near_node_id ?? it.edge_id ?? '—' });
}

/** The explanation applies only to the results it was made from (same verdict, deadline and checked route). */
export function matchesShown(rec: ExplOrigin, shown: ShownPlan | null): boolean {
  if (!shown) return false;
  if (rec.verdict_summary !== shown.bestVerdict) return false;
  if ((rec.deadline_offset_s ?? null) !== (shown.deadlineS ?? null)) return false;
  const dr = rec.deadline_route;
  // it names roads and times of one recorded route check: the route shown must be that check
  if (dr?.route_check_job_id && dr.route_check_job_id !== (shown.bestJobId ?? null)) return false;
  if (dr?.destination_id && shown.bestDestinationId && dr.destination_id !== shown.bestDestinationId) return false;
  return true;
}

function blank(kind: ExplainKind, title: string, line: string): ExplainView {
  return { kind, reason: null, title, statusLabel: null, lines: [line], dots: null, list: [], basis: null, provenance: null, marked: false, computedNote: null, host: null, sheetNote: null };
}

function short(h: string | null | undefined, n: number): string {
  return h ? h.slice(0, n) : '—';
}

/** Second part of an OSM edge id "w<way>:s<segment>:<f|r>" (direction along the way), when present. */
function edgeDirection(edgeId: string | null): string | null {
  const m = edgeId ? /:([fr])$/.exec(edgeId) : null;
  return m ? m[1]! : null;
}

export function explainView(args: {
  state: 'loading' | 'absent' | 'ready';
  file: ExplFile | null;
  originId: string;
  inputTime: string;
  lang: Lang;
  shown: ShownPlan | null;
}): ExplainView {
  const { state, file, originId, inputTime, lang, shown } = args;
  const titleTime = pick(EXPLAIN.titleTime, lang);
  if (state === 'loading') return blank('loading', titleTime, pick(EXPLAIN.loading, lang));
  if (state === 'absent' || !file) return blank('absent', titleTime, pick(EXPLAIN.absent, lang));
  const rec = file.origins[originId];
  if (!rec) return blank('missing_origin', titleTime, pick(EXPLAIN.missingOrigin, lang));
  const title = rec.verdict_summary === 'model_no_route' ? pick(EXPLAIN.titleNoRoute, lang) : titleTime;
  if (!shown) return blank('no_plan', title, pick(EXPLAIN.noPlan, lang));
  if (!matchesShown(rec, shown)) return blank('mismatch', title, pick(EXPLAIN.mismatch, lang));

  const at = (s: number | null | undefined) => (s === null || s === undefined ? '—' : kstClock(inputTime, s));
  const horizon = rec.window?.horizon_s ?? file.provenance.horizon_s ?? 3600;
  const total = rec.binding[0]?.members_total ?? rec.exits[0]?.members_total ?? file.provenance.members?.length ?? 4;
  const dwellMin = Math.round((rec.window?.dwell_s ?? rec.deadline_route?.dwell_s ?? 120) / 60);
  const lines: string[] = [];
  const list: string[] = [];
  let dots: ExplainDots | null = null;
  // a template carrying COMPUTED_MARK states a value computed for the explanation: using it marks the view
  let marked = false;
  const tm = (s: L10n, vars: Record<string, string | number> = {}): string => {
    const raw = pick(s, lang);
    if (raw.includes(COMPUTED_MARK)) marked = true;
    return fill(raw, vars);
  };
  const base = { deadline: at(rec.deadline_offset_s), next: at(rec.next_offset_s), end: at(horizon), dwell: dwellMin };
  const shelters: ExplShelter[] = rec.shelters_next ?? [];
  const shownDest = rec.deadline_route?.destination_id ?? null;
  const others = shelters.filter((x) => x.destination_id !== shownDest);
  const nChecked = rec.checked_at_deadline ?? 0;
  // every shelter with a checked route at the deadline is proven unreachable (stay included) from the next time
  const allCdProven = nChecked > 0 && rec.proven_unreachable_next === nChecked;
  /** "by 11:00" when the shelters concerned share one closing time, else "in time" */
  const by = (list_: { close_s: number | null }[], fallback?: number | null): string => {
    const closes = [...new Set(list_.map((x) => x.close_s))];
    const one = closes.length === 1 ? closes[0] : list_.length === 0 ? fallback : null;
    return one === null || one === undefined ? tm(EXPLAIN.inTime) : tm(EXPLAIN.byTime, { time: at(one) });
  };
  const cdLine = () => {
    const cd = shelters.filter((x) => x.checked_at_deadline);
    const vars = { ...base, n: nChecked, by: by(cd, rec.window?.close_s ?? null) };
    return tm(nChecked > 1 ? EXPLAIN.cdUnreachable : EXPLAIN.oneUnreachable, vars);
  };

  switch (rec.reason_code) {
    case 'no_later_offset':
      lines.push(tm(EXPLAIN.noLater, { ...base, hours: Math.round(horizon / 3600) }));
      break;
    case 'window': {
      const w = rec.window;
      if (rec.detail_code === 'outside_recorded_arrival_window' && w) {
        lines.push(tm(EXPLAIN.windowSkip, { ...base, open: at(w.open_s ?? 0), close: at(w.close_s) }));
      } else if (rec.detail_code === 'no_route_even_without_fire') {
        lines.push(tm(EXPLAIN.noRouteFireFree, { ...base, by: by([], w?.close_s ?? horizon) }));
      } else if (w && rec.detail_code === 'window_fire_free') {
        const arrival = w.limit === 'arrival_window';
        if (w.fastest_end_s === null) {
          lines.push(tm(EXPLAIN.windowFireFreeUnreachable, base));
        } else if (arrival) {
          const [fastestEnd, close] = clockPair(inputTime, w.fastest_end_s, w.close_s);
          lines.push(tm(EXPLAIN.windowArrivalFireFree, { ...base, fastestEnd, close }));
        } else {
          const [fastestEnd, end] = clockPair(inputTime, w.fastest_end_s, horizon);
          lines.push(tm(EXPLAIN.windowFireFree, { ...base, fastestEnd, end }));
        }
        // the other candidates, only when none of them would be reached in time even without fire
        const othersOut = others.length > 0 && others.every((x) => x.fire_free_fits === false);
        if (othersOut) lines.push(tm(others.length === 1 ? EXPLAIN.othersFireFreeOne : EXPLAIN.othersFireFree, { ...base, k: others.length, by: by(others) }));
        // the conclusion only when the file establishes that the time window alone sets the leave-by time; it names the
        // next checked departure, the only later time that was evaluated
        if (rec.deadline_cause === 'time_window' && (others.length === 0 || othersOut)) {
          const scenario = [w, ...others].every((x) => (x.close_s ?? 0) >= horizon);
          const single = others.length === 0;
          lines.push(tm(scenario ? (single ? EXPLAIN.rangeOne : EXPLAIN.rangeMany) : single && arrival ? EXPLAIN.arrivalOne : EXPLAIN.limitsMany, base));
        }
      }
      break;
    }
    case 'no_flame_avoiding_route': {
      const w = rec.window;
      if (rec.detail_code === 'no_flame_avoiding_route_fits_window') {
        lines.push(tm(EXPLAIN.noRouteFlames, { ...base, by: by([], w?.close_s ?? horizon) }));
      } else if (rec.detail_code === 'window_fire_detour' && w && w.fastest_end_s !== null) {
        const fa = w.flame_avoiding_arrival_s === null ? tm(EXPLAIN.faNone, base) : tm(EXPLAIN.faArrival, { time: at(w.flame_avoiding_arrival_s) });
        const [fastestEnd, close] = clockPair(inputTime, w.fastest_end_s, w.close_s);
        const detour = tm(EXPLAIN.windowDetour, { ...base, close, fa, fastestEnd });
        lines.push(rec.deadline_cause === 'flames' ? `${detour} ${tm(EXPLAIN.flamesConclusion)}` : detour);
        if (nChecked > 1 && allCdProven) lines.push(cdLine());
      } else if (rec.detail_code === 'other_shelters_flame_blocked' && w && rec.deadline_cause === 'flames') {
        const fl = others.filter((x) => x.fire_free_fits === true && x.proven);
        const ff = others.filter((x) => x.fire_free_fits === false);
        if (fl.length > 0) {
          const shownEnd =
            w.fastest_end_s === null
              ? tm(EXPLAIN.mixedShownNoRoad)
              : tm(EXPLAIN.mixedShownEnd, { time: clockPair(inputTime, w.fastest_end_s, w.close_s)[0] });
          const head = tm(w.limit === 'arrival_window' ? EXPLAIN.mixedShownArrival : EXPLAIN.mixedShownRange, { ...base, shownEnd });
          const all = fl.length === others.length;
          const flame = tm(
            all ? (fl.length === 1 ? EXPLAIN.mixedFlameAllOne : EXPLAIN.mixedFlameAll) : fl.length === 1 ? EXPLAIN.mixedFlameSomeOne : EXPLAIN.mixedFlameSome,
            { k: fl.length },
          );
          const also = ff.length ? ` ${tm(ff.length === 1 ? EXPLAIN.mixedAlsoOutOne : EXPLAIN.mixedAlsoOut, { k: ff.length })}` : '';
          lines.push(`${head} ${flame}${also} ${tm(EXPLAIN.flamesConclusion)}`);
        }
      }
      break;
    }
    case 'flame_on_route': {
      const b = rec.binding[0];
      if (!b) return blank('not_explainable', title, pick(EXPLAIN.other, lang));
      const members = tm(EXPLAIN.members, { k: b.members.length, total: b.members_total });
      dots = { members: b.members, total: b.members_total, text: members };
      lines.push(tm(EXPLAIN.flame, { ...base, where: whereText(b, lang), contact: at(b.contact_time_s), members }));
      if (b.pass_time_at_deadline_s !== null && b.slack_s !== null) {
        const [pass, flame] = clockPair(inputTime, b.pass_time_at_deadline_s, b.flame_time_s);
        const sameCell = b.contact_cell === undefined || b.slack_cell === undefined || b.contact_cell === b.slack_cell;
        const cell = tm(sameCell ? EXPLAIN.thatCell : EXPLAIN.aCellOnRoad);
        const tpl = b.members.length > 1 ? EXPLAIN.flameSlackMany : EXPLAIN.flameSlackOne;
        lines.push(tm(tpl, { ...base, pass, flame, cell, slack: slackText(b.slack_s, lang) }));
      }
      if (allCdProven) lines.push(cdLine());
      break;
    }
    case 'dwell_at_destination': {
      const b = rec.binding[0];
      if (!b) return blank('not_explainable', title, pick(EXPLAIN.other, lang));
      const members = tm(EXPLAIN.members, { k: b.members.length, total: b.members_total });
      dots = { members: b.members, total: b.members_total, text: members };
      lines.push(tm(EXPLAIN.dwell, { ...base, contact: at(b.contact_time_s), members }));
      break;
    }
    case 'all_exits_blocked': {
      if (rec.detail_code === 'entry_point_in_flame' || rec.exits.length === 0) {
        lines.push(tm(EXPLAIN.entryInFlame, { first: at(rec.first_offset_s) }));
        break;
      }
      const n = rec.exits.length;
      const kmin = Math.min(...rec.exits.map((e) => e.members.length));
      // one set of dots only when every exit is blocked in the same members; otherwise "at least k" and per-exit counts
      const sets = rec.exits.map((e) => [...e.members].sort((a, b) => a - b).join(','));
      const same = sets.every((x) => x === sets[0]);
      const members = same ? tm(EXPLAIN.members, { k: kmin, total }) : tm(EXPLAIN.membersAtLeast, { k: kmin, total });
      dots = same ? { members: [...rec.exits[0]!.members], total, text: members } : null;
      lines.push(tm(n === 1 ? EXPLAIN.exitsOne : n === 2 ? EXPLAIN.exitsTwo : EXPLAIN.exits, { n, members }));
      if (n === 2) {
        const [a, b] = rec.exits as [ExplItem, ExplItem];
        if (a.osm_way_id && a.osm_way_id === b.osm_way_id) {
          const da = edgeDirection(a.edge_id);
          const db = edgeDirection(b.edge_id);
          lines.push(tm(da && db && da !== db ? EXPLAIN.exitsSameWayBothDirections : EXPLAIN.exitsSameWay, { way: a.osm_way_id }));
        }
      }
      const one = n === 1;
      if (rec.exits.every((e) => e.flame_time_s === 0)) lines.push(tm(one ? EXPLAIN.exitsPresentOne : EXPLAIN.exitsPresent, { input: at(0) }));
      else lines.push(tm(one ? EXPLAIN.exitsLatestOne : EXPLAIN.exitsLatest, { latest: at(Math.max(...rec.exits.map((e) => e.contact_time_s ?? e.flame_time_s))) }));
      for (const e of rec.exits.slice(0, 3)) {
        const where = whereText(e, lang);
        list.push(tm(EXPLAIN.exitItem, { where: lang === 'en' ? cap(where) : where, k: e.members.length, total: e.members_total }));
      }
      if (n > 3) list.push(tm(EXPLAIN.exitsMore, { n: n - 3 }));
      break;
    }
    case 'unresolved_next':
      lines.push(tm(EXPLAIN.unresolvedNext, base));
      break;
    default:
      lines.push(tm(rec.detail_code === 'origin_unresolved' ? EXPLAIN.originUnresolved : EXPLAIN.other));
  }
  if (lines.length === 0) return blank('not_explainable', title, pick(EXPLAIN.other, lang));
  const explained = rec.status !== 'not_explainable';
  const checks = Object.values(rec.checks ?? {}).filter((v) => v === true).length;
  const shownMarked = explained && marked;
  return {
    kind: rec.status,
    reason: rec.reason_code,
    title,
    statusLabel: pick(EXPLAIN.status[rec.status], lang),
    lines,
    dots: explained ? dots : null,
    list: explained ? list : [],
    basis: explained ? t(EXPLAIN.basis, lang, { total }) : null,
    provenance: explained
      ? t(EXPLAIN.provenance, lang, {
          cache: short(file.provenance.cache_sha256, 8),
          hazard: short(file.provenance.packet_hashes?.['HAZARD.json'], 8),
          commit: short(file.provenance.code_commit ?? null, 7),
          checks,
        })
      : null,
    marked: shownMarked,
    computedNote: shownMarked ? pick(EXPLAIN.computedNote, lang) : null,
    host: explained ? hostText(file.provenance, lang) : null,
    sheetNote: shownMarked ? sheetNoteText(file.provenance, lang) : null,
  };
}
