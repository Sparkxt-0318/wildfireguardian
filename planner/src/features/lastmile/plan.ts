/**
 * What the messages of one origin may say, decided from the planner's own result (and, when it
 * agrees, the deadline explanation). Pure; unit-tested in tests/planner/lastmile.test.ts.
 *
 * - `leave_by`: the origin's verdict is checked_route AND every requested departure time from the
 *   first one up to T has a checked route (T = the contract's contiguous basis
 *   `latest_contiguous_checked_depart_offset_s`). The message says "leave by T". When later times
 *   are also checked but some time in between is not, T stays the contiguous basis (more
 *   conservative than the planner's headline deadline) and the message says why.
 * - `partial`: checked somewhere, but not at the first departure time (no contiguous basis): no
 *   departure time is given; follow official guidance.
 * - `no_route`: model_no_route — contact 119 / 읍·면사무소 now; no departure time, no tactical advice.
 * - `unresolved`: not checked — follow official evacuation guidance; never a departure time.
 */
import type { Verdict } from '../../domain/types';
import { selectReason, type LmReason } from './explanation';
import type { ExplanationFile, ExplanationNextVerdict, LastMileInput, LmCell, LmText } from './types';

export type MessageKind = 'leave_by' | 'no_route' | 'unresolved' | 'partial';

/**
 * What happens after T (leave_by only): `horizon` = T is the last departure the recorded window
 * allows (nothing later was requested — only window-closed times or none); `none_checked` = later
 * requested departure times have no checked route; `gap` = some later times are checked but not
 * all, so the message stops at T.
 */
export type AfterKind = 'horizon' | 'none_checked' | 'gap';

export interface PlannedDestination {
  id: string;
  name: LmText | null;
  display: LmText;
  category: LmText;
  /** arrival when leaving at T (s after input time) */
  arrivalS: number | null;
}

export interface MessagePlan {
  input: LastMileInput;
  kind: MessageKind;
  /** the planner's best verdict (unresolved when there is no result) */
  verdict: Verdict;
  /** departure deadline T of the message (leave_by only) */
  leaveByS: number | null;
  /** destination of the route checked at T (leave_by only) */
  destination: PlannedDestination | null;
  /** true when no single destination is checked at every departure time up to T */
  destinationVaries: boolean;
  after: AfterKind | null;
  /** next requested departure after the planner's deadline (explanation consistency) */
  nextOffsetS: number | null;
  nextVerdict: ExplanationNextVerdict;
  /** reason from the deadline explanation, only when it agrees with the planner */
  reason: LmReason | null;
}

function sorted(cells: LmCell[]): LmCell[] {
  return [...cells].sort((a, b) => a.offsetS - b.offsetS);
}

/** Road entry points farther than this from the village are named in the spoken scripts. */
export const ENTRY_SPOKEN_MIN_M = 500;

/**
 * How the card labels the leave-by time: `last_checked` when T is simply the last departure the
 * model checked (nothing later was requested) or when later departures cannot finish within the
 * recorded range even ignoring the fire (explanation `window_fire_free`) — never a fire deadline;
 * `deadline` otherwise ("출발 마감 / Leave by").
 */
export function bigLabelKind(p: MessagePlan): 'deadline' | 'last_checked' {
  return p.after === 'horizon' || p.reason?.kind === 'window_fire_free' ? 'last_checked' : 'deadline';
}

export function messagePlan(input: LastMileInput, explanation: ExplanationFile | null = null): MessagePlan {
  const p = input.plan;
  const verdict: Verdict = p?.bestVerdict ?? 'unresolved';
  const horizonS = input.scenario.horizonS;
  const entry = explanation?.origins ? (explanation.origins as Record<string, unknown>)[input.origin.id] : undefined;
  const base: Omit<MessagePlan, 'kind'> = {
    input,
    verdict,
    leaveByS: null,
    destination: null,
    destinationVaries: false,
    after: null,
    nextOffsetS: null,
    nextVerdict: null,
    reason: null,
  };
  if (!p || verdict === 'unresolved') return { ...base, kind: 'unresolved' };
  if (verdict === 'model_no_route') {
    const reason = selectReason(entry, { kind: 'no_route', latestS: null, leaveByS: null, nextOffsetS: null, nextVerdict: null, destinationId: null, horizonS });
    return { ...base, kind: 'no_route', reason };
  }

  // checked_route
  const latest = p.latestSafeDepartureS;
  const contiguous = p.contiguousSafeDepartureS;
  const cells = sorted(p.sweep);
  const requested = cells.filter((c) => c.verdict !== 'window_closed');
  if (latest === null || contiguous === null || contiguous > latest) return { ...base, kind: 'partial' };
  const upTo = requested.filter((c) => c.offsetS <= contiguous);
  // the contiguous basis must hold in the sweep itself (fail closed on any inconsistency)
  if (upTo.length === 0 || upTo.some((c) => c.verdict !== 'checked_route') || upTo[upTo.length - 1]!.offsetS !== contiguous) {
    return { ...base, kind: 'partial' };
  }
  const leaveByS = contiguous;
  const atT = upTo[upTo.length - 1]!;
  const checkedAt = (c: LmCell, d: string) => c.attempts.find((a) => a.destinationId === d && a.verdict === 'checked_route') ?? null;
  const ids = [...new Set(atT.attempts.filter((a) => a.verdict === 'checked_route').map((a) => a.destinationId))];
  const covering = ids.filter((d) => upTo.every((c) => checkedAt(c, d)));
  const pool = covering.length ? covering : ids;
  const byArrival = (a: string, b: string) => {
    const aa = checkedAt(atT, a)?.arrivalS ?? Number.POSITIVE_INFINITY;
    const bb = checkedAt(atT, b)?.arrivalS ?? Number.POSITIVE_INFINITY;
    return aa - bb || a.localeCompare(b);
  };
  const chosen = [...pool].sort(byArrival)[0] ?? null;
  const dest = chosen ? input.destinations[chosen] : undefined;
  const destination: PlannedDestination | null = chosen
    ? {
        id: chosen,
        name: dest?.name ?? null,
        // a destination the places file does not list keeps its id (never a made-up name)
        display: dest?.display ?? { ko: chosen, en: chosen },
        category: dest?.category ?? { ko: '도착지', en: 'destination' },
        arrivalS: checkedAt(atT, chosen)?.arrivalS ?? null,
      }
    : null;

  // window-closed times after T were never requested: like the end of the window, they were not checked
  const laterRequested = requested.filter((c) => c.offsetS > leaveByS);
  const after: AfterKind = contiguous < latest ? 'gap' : laterRequested.length === 0 ? 'horizon' : 'none_checked';
  const next = cells.find((c) => c.offsetS > latest) ?? null;
  const nextVerdict: ExplanationNextVerdict = !next ? null : next.verdict === 'window_closed' ? 'window' : next.verdict === 'checked_route' ? null : next.verdict;
  const reason = selectReason(entry, { kind: 'leave_by', latestS: latest, leaveByS, nextOffsetS: next?.offsetS ?? null, nextVerdict, destinationId: destination?.id ?? null, horizonS });
  return {
    ...base,
    kind: 'leave_by',
    leaveByS,
    destination,
    destinationVaries: covering.length === 0,
    after,
    nextOffsetS: next?.offsetS ?? null,
    nextVerdict,
    reason,
  };
}
