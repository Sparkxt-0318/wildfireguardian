"""Decisions per confirmed track: candidate, then method_accepted, rejected or insufficient_evidence.

Keys: (epoch, track_id) as the integer epoch * 10**9 + track_id (make_key), so the gate counter
never confuses a track of a new shot (the booth restarts the tracker at a cut, and track ids
with it) with an old one; in epoch 0 the key equals the track id.

Transitions (all at the time t of the analysed frame that causes them, from past and current
frames only):
- on_confirmed: a new candidate (t_first, t_confirm, confirm_idx: the record index of the
  confirming hit).
- checkpoint: a candidate whose window has at least the scorer's min_hits feature hits and no
  blocking flag is scored; a valid score at or above the scorer's threshold accepts it. An
  invalid score, a blocking flag or too few hits only records the reason.
- deadline: a candidate deadline_s after its confirmation is rejected (score_below_threshold)
  when a valid checkpoint happened, and otherwise gets insufficient_evidence with the first
  recorded reason in REASON_PRIORITY order.
- on_static: rejected (static); revoked when it had been accepted.
- on_finished: a final checkpoint (an acceptance then is retro), then the deadline rule at once.
t_decision and frame_decision hold the time of the latest transition (for a revoked track, its
rejection); t_accept and frame_accept are set once, at acceptance, and never change.
`accepted(key)` (accepted now) is the one predicate every high-precision consumer uses while
the stream runs; `ever_accepted` (accepted now, or accepted and then revoked) selects the tracks
of the output tables, since a revoked track was drawn and counted while it was accepted.
Finished decisions move to an archive: every one is kept in file mode (for the tables), the
last LIVE_ARCHIVE in the booth.

Fragments (report only): a new candidate that starts within FRAGMENT_GAP_S of an accepted
track's end, within FRAGMENT_SPEED_FACTOR x speed x gap px of its end point and within
FRAGMENT_ANGLE_DEG of its heading gets probable_fragment_of = that track's key; only within
one epoch (new_epoch forgets the ends at a cut: a new shot has other coordinates).
"""
from __future__ import annotations

import math
from collections import OrderedDict, deque
from dataclasses import dataclass, field, fields

import numpy as np

CANDIDATE = "candidate"
ACCEPTED = "method_accepted"
REJECTED = "rejected"
INSUFFICIENT = "insufficient_evidence"
STATES = (CANDIDATE, ACCEPTED, REJECTED, INSUFFICIENT)

REASON_PRIORITY = ("method_unavailable", "timebase_not_real_time", "camera_motion", "budget", "out_of_distribution",
                   "missing_feature", "too_few_hits")
BLOCKING = ("timebase_not_real_time", "camera_motion")   # flags that stop a gated scorer
ALWAYS_BLOCKING = ("timebase_not_real_time",)            # flags that stop every scorer
KEY_BASE = 10 ** 9
LIVE_ARCHIVE = 2000
FRAGMENT_GAP_S = 0.5
FRAGMENT_SPEED_FACTOR = 3.0
FRAGMENT_ANGLE_DEG = 30.0
_EPS = 1e-9


def make_key(epoch: int, track_id: int) -> int:
    return int(epoch) * KEY_BASE + int(track_id)


def split_key(key: int) -> tuple[int, int]:
    return int(key) // KEY_BASE, int(key) % KEY_BASE


@dataclass
class TrackDecision:
    key: int
    epoch: int
    track_id: int
    state: str = CANDIDATE
    reason: str = ""
    score: float = math.nan            # last valid score
    best_score: float = math.nan
    n_hits: int = 0                    # feature hits in the last window seen
    t_first: float = math.nan
    t_confirm: float = math.nan
    confirm_idx: int = -1
    t_decision: float = math.nan       # time of the latest transition
    frame_decision: int = -1
    t_accept: float = math.nan         # time of the acceptance (set once; kept when revoked)
    frame_accept: int = -1
    revoked: bool = False
    retro: bool = False
    ood: bool = False
    motion_tainted: bool = False
    over_budget: bool = False
    probable_fragment_of: int = -1
    reasons: set = field(default_factory=set, repr=False)    # bookkeeping, not exported
    valid_seen: bool = field(default=False, repr=False)


PUBLIC_FIELDS = tuple(f.name for f in fields(TrackDecision) if f.name not in ("reasons", "valid_seen"))


@dataclass
class Window:
    """What a checkpoint sees of a track: window features, patches of hits with features, the
    number of such hits, whether any hit lacked features or fell in motion-unsupported time,
    and the per-hit features (FEATURE_NAMES) of the hits with patches, row for row (patch
    models with hit scalars read them; None when not given)."""

    vec: np.ndarray
    patches: np.ndarray | None
    n_feature_hits: int
    over_budget: bool = False
    motion_tainted: bool = False
    hit_values: np.ndarray | None = None


def is_ever_accepted(d: TrackDecision) -> bool:
    """A decision that is accepted now, or was accepted and then revoked."""
    return d.state == ACCEPTED or bool(d.revoked)


def _first_reason(reasons: set) -> str:
    for p in REASON_PRIORITY:
        hit = sorted(r for r in reasons if r == p or r.startswith(p + ":"))
        if hit:
            return hit[0]
    return "too_few_hits"


class Ledger:
    def __init__(self, vcfg, keep_all: bool = True, archive_cap: int = LIVE_ARCHIVE):
        self.deadline_s = float(vcfg.deadline_s)
        self.keep_all = bool(keep_all)
        self.archive_cap = int(archive_cap)
        self.active: dict[int, TrackDecision] = {}
        self.archive: OrderedDict[int, TrackDecision] = OrderedDict()
        self.dropped = 0                    # archived decisions dropped from a bounded archive
        self._ends: deque = deque()         # (t_end, x, y, vx, vy, key) of accepted finished tracks

    # Queries -------------------------------------------------------------------------------
    def get(self, key: int) -> TrackDecision | None:
        return self.active.get(key) or self.archive.get(key)

    def __contains__(self, key: int) -> bool:
        return key in self.active or key in self.archive

    def accepted(self, key: int) -> bool:
        d = self.active.get(key)
        if d is None:
            d = self.archive.get(key)
        return d is not None and d.state == ACCEPTED

    def ever_accepted(self, key: int) -> bool:
        """Accepted now, or accepted and then revoked (static)."""
        d = self.get(key)
        return d is not None and is_ever_accepted(d)

    def pending(self) -> int:
        return sum(1 for d in self.active.values() if d.state == CANDIDATE)

    def decisions(self) -> list[TrackDecision]:
        return [*self.archive.values(), *self.active.values()]

    # Transitions ---------------------------------------------------------------------------
    def on_confirmed(self, key: int, track, t: float | None = None) -> TrackDecision:
        d = self.get(key)
        if d is not None:
            return d
        epoch, tid = split_key(key)
        recs = track.records
        r = recs[-1]
        d = TrackDecision(key=key, epoch=epoch, track_id=tid, t_first=float(track.t_first), t_confirm=float(r[1]),
                          confirm_idx=len(recs) - 1)
        d.probable_fragment_of = self._fragment_of(track, epoch)
        self.active[key] = d
        return d

    def checkpoint(self, key: int, t: float, window: Window, scorer, flags=(), frame: int = -1) -> bool:
        """Score a candidate's window at time t (frame: its index, for the record); True when this
        accepts it."""
        d = self.active.get(key)
        if d is None or d.state != CANDIDATE:
            return False
        d.n_hits = int(window.n_feature_hits)
        d.over_budget |= bool(window.over_budget)
        if not getattr(scorer, "available", True):
            d.reasons.add(scorer.reason)
            return False
        flags = set(flags)
        if window.motion_tainted:
            flags.add("camera_motion")
        block = [f for f in (BLOCKING if scorer.gated else ALWAYS_BLOCKING) if f in flags]
        if block:
            d.reasons.update(block)
            d.motion_tainted |= "camera_motion" in block
            return False
        if window.n_feature_hits < scorer.min_hits:
            d.reasons.add("budget" if window.over_budget else "too_few_hits")
            return False
        # A scorer that needs more of the window than its features and patches (a patch model with
        # hit scalars) reads the whole window.
        score_window = getattr(scorer, "score_window", None)
        s, valid, reason = score_window(window) if score_window is not None else scorer.score(window.vec, window.patches)
        if not valid:
            d.reasons.add(reason.split(":")[0] if reason.startswith("missing_feature") else reason)
            d.ood |= reason == "out_of_distribution"
            return False
        d.valid_seen = True
        d.score = float(s)
        d.best_score = float(s) if not math.isfinite(d.best_score) else max(d.best_score, float(s))
        if s >= scorer.threshold:
            d.state, d.reason, d.t_decision, d.frame_decision = ACCEPTED, "passed", float(t), int(frame)
            d.t_accept, d.frame_accept = float(t), int(frame)
            return True
        return False

    def _close(self, d: TrackDecision, t: float, frame: int, retro: bool) -> None:
        if d.valid_seen:
            d.state, d.reason = REJECTED, "score_below_threshold"
        else:
            d.state, d.reason = INSUFFICIENT, _first_reason(d.reasons)
        d.t_decision, d.frame_decision, d.retro = float(t), int(frame), bool(retro)

    def deadline(self, t: float, frame: int = -1) -> list[int]:
        """Close the candidates confirmed at least deadline_s ago; returns their keys."""
        out = []
        for key, d in self.active.items():
            if d.state == CANDIDATE and t - d.t_confirm >= self.deadline_s - _EPS:
                self._close(d, t, frame, retro=False)
                out.append(key)
        return out

    def on_static(self, key: int, since: float | None = None, t: float = math.nan, frame: int = -1) -> bool:
        """Rejected as static at time t (the track's slow window began at since); returns True when
        this revokes an acceptance."""
        d = self.get(key)
        if d is None or (d.state == REJECTED and d.reason == "static"):
            return False
        was = d.state == ACCEPTED
        d.state, d.reason, d.revoked = REJECTED, "static", d.revoked or was
        d.t_decision, d.frame_decision = float(t), int(frame)
        return was

    def on_finished(self, key: int, t_end: float, last_window: Window | None, scorer=None, flags=(),
                    t: float | None = None, frame: int = -1,
                    end: tuple[float, float, float, float, float] | None = None) -> bool:
        """The track ended at t_end (its last hit), learnt at time t (default t_end): a last
        checkpoint of last_window, then the deadline rule now. True on a retro acceptance. end is
        (t, x, y, vx, vy) of its last hit, for the fragment flag."""
        d = self.active.get(key)
        if d is None:
            return False
        t = float(t_end) if t is None else float(t)
        acc = False
        if d.state == CANDIDATE and last_window is not None and scorer is not None:
            acc = self.checkpoint(key, t, last_window, scorer, flags, frame)
            if acc:
                d.retro = True
        if d.state == CANDIDATE:
            self._close(d, t, frame, retro=True)
        if d.state == ACCEPTED and end is not None:
            self._ends.append((*end, key))
        self._archive(key)
        return acc

    def finalize(self, t: float, frame: int = -1) -> None:
        """End of the stream: close and archive everything still open."""
        for key in list(self.active):
            d = self.active[key]
            if d.state == CANDIDATE:
                self._close(d, t, frame, retro=True)
            self._archive(key)

    def new_epoch(self) -> None:
        """A cut: the ends of the previous shot's tracks no longer locate fragments."""
        self._ends.clear()

    # Internals -----------------------------------------------------------------------------
    def _archive(self, key: int) -> None:
        d = self.active.pop(key, None)
        if d is None:
            return
        d.reasons = set(d.reasons)
        self.archive[key] = d
        if not self.keep_all:
            while len(self.archive) > self.archive_cap:
                self.archive.popitem(last=False)
                self.dropped += 1

    def _fragment_of(self, track, epoch: int) -> int:
        recs = track.records
        if not recs or not self._ends:
            return -1
        t0, x0, y0 = recs[0][1], recs[0][2], recs[0][3]
        while self._ends and self._ends[0][0] < t0 - FRAGMENT_GAP_S - 1.0:
            self._ends.popleft()
        r = recs[-1]
        hx, hy = r[2] - x0, r[3] - y0
        if not (math.isfinite(hx) and math.isfinite(hy)) or math.hypot(hx, hy) < 1e-6:
            hx, hy = r[6], r[7]
        if not (math.isfinite(hx) and math.isfinite(hy)) or math.hypot(hx, hy) < 1e-6:
            return -1
        best, best_d = -1, math.inf
        for te, xe, ye, vx, vy, k in self._ends:
            if split_key(k)[0] != epoch:
                continue
            gap = t0 - te
            if not 0.0 < gap <= FRAGMENT_GAP_S:
                continue
            sp = math.hypot(vx, vy)
            dist = math.hypot(x0 - xe, y0 - ye)
            if not (math.isfinite(sp) and sp > 0) or dist > FRAGMENT_SPEED_FACTOR * sp * gap:
                continue
            ang = abs(math.degrees(math.atan2(hx * vy - hy * vx, hx * vx + hy * vy)))
            if ang <= FRAGMENT_ANGLE_DEG and dist < best_d:
                best, best_d = k, dist
        return best
