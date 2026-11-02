/**
 * Pure view model of the "왜 이 시각인가요? / Why this time?" block: sentences are filled from the structured fields of
 * wfg.explanation/1 only. No free text from the file is ever shown (`notes` are audit codes). An explanation is shown
 * only when it describes exactly the results on screen (verdict, deadline and the shown route); otherwise a fallback.
 */
import { kstClock } from '../../domain/clock';
import { formatDistanceM } from '../shared/format';
import { pick, type L10n, type Lang } from '../shared/strings';
import { EXPLAIN } from './strings';
import type { ExplFile, ExplItem, ExplOrigin, ExplReason, ExplStatus, ShownPlan } from './types';

export type ExplainKind = 'loading' | 'absent' | 'missing_origin' | 'mismatch' | ExplStatus;

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
}

export function fill(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

function t(s: L10n, lang: Lang, vars: Record<string, string | number> = {}): string {
  return fill(pick(s, lang), vars);
}

/** Margin as a lower bound in whole minutes (rounded down: never overstates the time available). */
export function slackText(seconds: number, lang: Lang): string {
  if (!(seconds >= 60)) return pick(EXPLAIN.underMinute, lang);
  return t(EXPLAIN.atLeastMinutes, lang, { m: Math.floor(seconds / 60) });
}

export function whereText(it: ExplItem, lang: Lang): string {
  const name = lang === 'en' ? (it.label_en ?? it.label_ko) : (it.label_ko ?? it.label_en);
  if (it.label_source === 'nearest_place' && name) {
    return t(EXPLAIN.wherePlace, lang, { name, dist: formatDistanceM(it.place_distance_m ?? null, lang) });
  }
  if ((it.label_source === 'osm_name' || it.label_source === 'osm_ref') && name) return t(EXPLAIN.whereNamed, lang, { name });
  return t(EXPLAIN.whereUnnamed, lang, { node: it.near_node_id ?? it.edge_id ?? '—' });
}

/** The explanation applies only to the results it was made from. */
export function matchesShown(rec: ExplOrigin, shown: ShownPlan | null): boolean {
  if (!shown) return false;
  if (rec.verdict_summary !== shown.bestVerdict) return false;
  if ((rec.deadline_offset_s ?? null) !== (shown.deadlineS ?? null)) return false;
  const dr = rec.deadline_route;
  if (dr?.route_check_job_id && shown.bestJobId && dr.route_check_job_id !== shown.bestJobId) return false;
  if (dr?.destination_id && shown.bestDestinationId && dr.destination_id !== shown.bestDestinationId) return false;
  return true;
}

function blank(kind: ExplainKind, title: string, line: string): ExplainView {
  return { kind, reason: null, title, statusLabel: null, lines: [line], dots: null, list: [], basis: null, provenance: null };
}

function short(h: string | null | undefined, n: number): string {
  return h ? h.slice(0, n) : '—';
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
  if (!matchesShown(rec, shown)) return blank('mismatch', title, pick(EXPLAIN.mismatch, lang));

  const at = (s: number | null | undefined) => (s === null || s === undefined ? '—' : kstClock(inputTime, s));
  const horizon = rec.window?.horizon_s ?? file.provenance.horizon_s ?? 3600;
  const total = rec.binding[0]?.members_total ?? rec.exits[0]?.members_total ?? 4;
  const dwellMin = Math.round((rec.window?.dwell_s ?? rec.deadline_route?.dwell_s ?? 120) / 60);
  const lines: string[] = [];
  const list: string[] = [];
  let dots: ExplainDots | null = null;
  const base = { deadline: at(rec.deadline_offset_s), next: at(rec.next_offset_s), end: at(horizon), dwell: dwellMin };
  const nChecked = rec.checked_at_deadline ?? 0;
  // every shelter checked at the deadline is proven unreachable (stay included) from the next time by flame-avoiding roads
  const allProven = nChecked > 0 && rec.proven_unreachable_next === nChecked;

  switch (rec.reason_code) {
    case 'no_later_offset':
      lines.push(t(EXPLAIN.noLater, lang, { ...base, hours: Math.round(horizon / 3600) }));
      break;
    case 'window': {
      const w = rec.window;
      const classes = Object.values(rec.destination_classes ?? {});
      const allFireFree = classes.length === nChecked && classes.every((c) => c === 'window_fire_free');
      if (rec.detail_code === 'outside_recorded_arrival_window' && w) {
        lines.push(t(EXPLAIN.windowSkip, lang, { ...base, open: at(w.open_s ?? 0), close: at(w.close_s) }));
      } else if (rec.verdict_summary === 'model_no_route') {
        lines.push(t(EXPLAIN.windowNoRoute, lang, { ...base, close: at(w?.close_s ?? horizon) }));
      } else if (w && w.fire_free) {
        if (w.limit === 'arrival_window' && w.fastest_end_s !== null) {
          lines.push(t(EXPLAIN.windowArrivalFireFree, lang, { ...base, fastestEnd: at(w.fastest_end_s), close: at(w.close_s) }));
        } else if (w.fastest_end_s === null) {
          lines.push(t(EXPLAIN.windowFireFreeUnreachable, lang, base));
        } else {
          lines.push(t(EXPLAIN.windowFireFree, lang, { ...base, fastestEnd: at(w.fastest_end_s) }));
        }
      } else if (w) {
        const fa = w.flame_avoiding_arrival_s === null ? t(EXPLAIN.faNone, lang, base) : t(EXPLAIN.faArrival, lang, { time: at(w.flame_avoiding_arrival_s) });
        lines.push(t(EXPLAIN.windowDetour, lang, { ...base, close: at(w.close_s), fa, fastestEnd: at(w.fastest_end_s) }));
      }
      if (rec.verdict_summary === 'checked_route' && nChecked > 1 && allProven && rec.detail_code !== 'outside_recorded_arrival_window') {
        lines.push(t(allFireFree ? EXPLAIN.allUnreachableFireFree : EXPLAIN.allUnreachable, lang, { ...base, n: nChecked }));
      }
      break;
    }
    case 'flame_on_route': {
      const b = rec.binding[0];
      if (!b) return blank('not_explainable', title, pick(EXPLAIN.other, lang));
      const members = t(EXPLAIN.members, lang, { k: b.members.length, total: b.members_total });
      dots = { members: b.members, total: b.members_total, text: members };
      lines.push(t(EXPLAIN.flame, lang, { ...base, where: whereText(b, lang), contact: at(b.contact_time_s), members }));
      if (b.pass_time_at_deadline_s !== null && b.slack_s !== null) {
        lines.push(t(EXPLAIN.flameSlack, lang, { ...base, pass: at(b.pass_time_at_deadline_s), slack: slackText(b.slack_s, lang), flame: at(b.flame_time_s) }));
      }
      if (allProven) lines.push(nChecked > 1 ? t(EXPLAIN.allUnreachable, lang, { ...base, n: nChecked }) : t(EXPLAIN.oneUnreachable, lang, base));
      break;
    }
    case 'dwell_at_destination': {
      const b = rec.binding[0];
      if (!b) return blank('not_explainable', title, pick(EXPLAIN.other, lang));
      const members = t(EXPLAIN.members, lang, { k: b.members.length, total: b.members_total });
      dots = { members: b.members, total: b.members_total, text: members };
      lines.push(t(EXPLAIN.dwell, lang, { ...base, contact: at(b.contact_time_s), members }));
      break;
    }
    case 'all_exits_blocked': {
      if (rec.detail_code === 'entry_point_in_flame' || rec.exits.length === 0) {
        lines.push(pick(EXPLAIN.entryInFlame, lang));
        break;
      }
      const kmin = Math.min(...rec.exits.map((e) => e.members.length));
      // one set of dots only when every exit is blocked in the same members; otherwise "at least k" and per-exit counts
      const sets = rec.exits.map((e) => [...e.members].sort((a, b) => a - b).join(','));
      const same = sets.every((x) => x === sets[0]);
      const members = same ? t(EXPLAIN.members, lang, { k: kmin, total }) : t(EXPLAIN.membersAtLeast, lang, { k: kmin, total });
      dots = same ? { members: [...rec.exits[0]!.members], total, text: members } : null;
      const one = rec.exits.length === 1;
      lines.push(t(one ? EXPLAIN.exitsOne : EXPLAIN.exits, lang, { n: rec.exits.length, members }));
      if (rec.exits.every((e) => e.flame_time_s === 0)) lines.push(t(one ? EXPLAIN.exitsPresentOne : EXPLAIN.exitsPresent, lang, { input: at(0) }));
      else lines.push(t(one ? EXPLAIN.exitsLatestOne : EXPLAIN.exitsLatest, lang, { latest: at(Math.max(...rec.exits.map((e) => e.contact_time_s ?? e.flame_time_s))) }));
      for (const e of rec.exits.slice(0, 3)) list.push(t(EXPLAIN.exitItem, lang, { where: whereText(e, lang), k: e.members.length, total: e.members_total }));
      if (rec.exits.length > 3) list.push(t(EXPLAIN.exitsMore, lang, { n: rec.exits.length - 3 }));
      break;
    }
    case 'unresolved_next':
      lines.push(t(EXPLAIN.unresolvedNext, lang, base));
      break;
    default:
      lines.push(pick(rec.detail_code === 'origin_unresolved' ? EXPLAIN.originUnresolved : EXPLAIN.other, lang));
  }
  if (lines.length === 0) return blank('not_explainable', title, pick(EXPLAIN.other, lang));
  const explained = rec.status !== 'not_explainable';
  const checks = Object.values(rec.checks ?? {}).filter((v) => v === true).length;
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
  };
}
