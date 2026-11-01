"""E1: adaptive large neighbourhood search with the oracle in the loop (Ropke & Pisinger 2006).

"Search cheaply, check expensively". The search runs on a RELAXED model; only :mod:`evacplan.oracle`
certifies, and only certified plans become incumbents (program rule 3).

Representation
--------------
Per vehicle an ordered list of trips; a trip = up to ``max_stops`` facility stops (facility, residents
per class boarded there), then one shelter where everything is unloaded. A plan is DECODED as soon as
possible on the POSITIVE masks of :mod:`evacplan.reach` with the validator's rules, exactly like
:class:`evacplan.methods.dispatch.Dispatcher` (B1's trip machinery): earliest-arrival time-dependent
route to each stop (the free-flow shortest path when it is usable at once, else time-dependent A*), wait
for the release at waitable sites, board, leave right after boarding, route to the shelter, wait for its
window, unload. A stop that cannot be served at its turn is skipped (its residents go back to the pool),
a trip whose unloading fails is dropped. Decoded plans therefore respect vehicle space, shelter
capacity, residents per facility, release times, windows, shifts, waits, turn rules and the horizon,
and every leg is contact-free and supported in all K members by construction: the POSITIVE masks are
this search's relaxed contact check (the same occupancies and closed cells as the oracle's contact rule;
they also require support and the horizon, so they imply :class:`evacplan.oracle.RelaxedContactCheck`'s
"not blocked"). They do not model peak flux or dose: those are left entirely to the oracle (no dose
weights, penalties or thresholds anywhere in this module).

Objective (lexicographic, maximised): 1) residents in decoded trips (the relaxed count of delivered),
2) the plan's minimum safety slack (relaxed: for a drive leg the time to the end of the usable departure
interval of its edge, for a stay the time to the next burning interval of its node, capped at the
horizon; the oracle's slack is exact and at most ~1 s larger), 3) vehicle time; scalarised as
``A * delivered + B * min(slack, Hi) - vehicle_time`` with ``B > vehicles * Hi`` and ``A > B * Hi`` so
the order is strict.

ALNS (parameters fixed a priori from Ropke & Pisinger 2006, see ``config()`` and
``evacplan/experiments/E1-alns/config.yaml``)
-------------------------------------------------------------------------------------------------------
* Requests are chunks of one facility and class, sized by B2's rule (``q`` = the smallest space for the
  class among vehicles with room for at least two, else 1; capped so a chunk boards between release and
  deadline; remainders in powers of two). Each iteration removes ``q`` in [10 %, 40 %] of the planned
  requests with one destroy operator, then inserts from the pool of unplanned residents with one repair
  operator, chosen by roulette wheel on adaptive weights.
* Destroy: random; worst-slack (requests on the trips with the smallest slack, randomised with
  ``p_worst``); related (Shaw: relatedness from facility and shelter distance, boarding and unloading
  times, size and the vehicles that can carry the class, weights 9/3/2/5, randomised with ``p_shaw``);
  whole trips; whole vehicle routes.
* Repair: greedy, regret-2 and regret-3 insertion, each with or without noise (adaptive). An insertion
  tops up an existing stop, adds a stop to a trip, or adds a new trip at any position of a vehicle's trip
  list; the shelter of the new or changed trip is the one where unloading ends first, among those with
  room. An option is valued on the vehicle re-decoded from the change onward (residents gained net of any
  later trip it pushes out, the plan's slack, the vehicle time); the latest-safe departures of
  :func:`evacplan.methods.dispatch.latest_departures` prune options that cannot leave the facility in time.
* Acceptance: simulated annealing on the scalarised objective in units of residents; start temperature
  such that a solution 5 % worse than the warm start is accepted with probability 0.5; cooling
  ``c = 0.99975`` per iteration over Ropke & Pisinger's 25,000 iterations, applied as the same overall
  decay over this run's search time (or over ``max_iterations`` when set, which makes runs deterministic).
* Adaptive weights: segments of 100 iterations, reaction factor 0.1, scores 33 (new best), 9 (better than
  the current solution, not seen before), 13 (worse but accepted, not seen before).

Oracle in the loop
------------------
* The incumbent (the plan returned) is always a plan whose every itinerary the oracle checked
  (:meth:`Oracle.check_itinerary`, cached per itinerary). The warm start (B1, greedy EDF insertion, run
  inside the budget on the same :class:`Reach`) is the initial solution; it is certified only when needed.
* Lazy certification (Dellin & Srinivasa 2016): the best relaxed candidate is certified at the end of each
  segment, when the time left would no longer suffice to certify it (estimated from the measured oracle seconds
  per leg; the search then goes on with what remains, and a later certification needs only the itineraries that
  changed) and at the end of the search. Each itinerary first goes through
  :class:`RelaxedContactCheck` (a cheap guard; a block would be a decoder bug and is cut).
* A trip the oracle does not check (in practice dose: ``DOSE_UNRESOLVED`` / ``DOSE_ABOVE_BUDGET``) is cut
  together with the rest of its itinerary (a vehicle's state never improves); its residents return to the
  pool. The failing itinerary prefix is remembered, and any later plan that repeats it is cut the same
  way, so the search sees the oracle's verdicts wherever it has them.
* The certified objective uses the oracle's numbers (delivered, ``min_slack_s``); a certified candidate
  replaces the incumbent only if it is better. If no certified plan exists at the end, the warm start is
  returned (the harness checks every plan in any case); a certified candidate replaces the uncertified warm
  start only if it beats the warm start's optimistic bound (relaxed residents), so E1 never delivers fewer
  residents than its warm start.
"""
from __future__ import annotations

import math
import random
import time
from array import array
from bisect import bisect_right
from collections import Counter

import numpy as np

from ..oracle import Oracle, RelaxedContactCheck, State
from ..reach import Reach
from ..schema import Board, ClassCounts, Itinerary, Solution, Unload, Wait
from .b1_greedy import B1Greedy
from .b2_vrptw import chunk_sizes
from .base import Method, MethodResult
from .dispatch import Dispatcher, latest_departures

INF = math.inf
_MISSING = object()
_TD_CACHE_MAX = 400_000

# Parameters fixed a priori (Ropke & Pisinger 2006 unless stated); committed before any dev run.
DEFAULTS: dict = {
    "segment": 100,                  # iterations per weight-update segment
    "reaction": 0.1,                 # reaction factor r
    "scores": (33, 9, 13),           # sigma_1 (new best), sigma_2 (better, new), sigma_3 (worse, accepted, new)
    "remove_min": 0.1,               # destroy size: q in [remove_min, remove_max] x planned requests
    "remove_max": 0.4,
    "p_shaw": 6,                     # determinism of related (Shaw) removal
    "p_worst": 3,                    # determinism of worst(-slack) removal
    "shaw_weights": (9, 3, 2, 5),    # phi (distance), chi (time), psi (size), omega (vehicles)
    "noise": 0.025,                  # eta: insertion noise amplitude = eta x max site-to-site free-flow time
    "start_worse": 0.05,             # T0: a solution 5 % worse than the warm start accepted with probability 0.5
    "cooling": 0.99975,              # c per iteration ...
    "cooling_iterations": 25000,     # ... over Ropke & Pisinger's iteration count (overall decay c^25000)
    "regret_k": (2, 3),              # repair heuristics: greedy, regret-2, regret-3
    "max_stops": 3,                  # facility stops per trip (bounds the insertion neighbourhood; not tuned)
    "max_iterations": None,          # iteration cap (deterministic runs); None = until the time budget
    "reserve_s": None,               # kept free at the end; None = 0.5 + 3 % of the budget (B2's reserve)
    "oracle_safety": 1.5,            # oracle time estimates are multiplied by this before a check starts
    "oracle_s_per_leg0": 0.01,       # oracle seconds per leg assumed before the first measurement
}


class E1ALNS(Method):
    name = "e1_alns"

    def __init__(self, **config):
        unknown = sorted(set(config) - set(DEFAULTS))
        if unknown:
            raise ValueError(f"unknown e1_alns option(s): {unknown}")
        cfg = {**DEFAULTS, **config}
        cfg["scores"] = tuple(float(x) for x in cfg["scores"])
        cfg["shaw_weights"] = tuple(float(x) for x in cfg["shaw_weights"])
        cfg["regret_k"] = tuple(int(x) for x in cfg["regret_k"])
        if not 0 < cfg["remove_min"] <= cfg["remove_max"] <= 1:
            raise ValueError("need 0 < remove_min <= remove_max <= 1")
        if int(cfg["segment"]) < 1 or int(cfg["max_stops"]) < 1:
            raise ValueError("segment and max_stops must be >= 1")
        if cfg["max_iterations"] is not None and int(cfg["max_iterations"]) < 0:
            raise ValueError("max_iterations must be >= 0")
        if len(cfg["scores"]) != 3 or len(cfg["shaw_weights"]) != 4:
            raise ValueError("scores needs 3 values, shaw_weights 4")
        super().__init__(**{k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.items()})
        self.cfg = cfg

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        return _Run(self.cfg, self.name, instance, scenario_set, float(budget_s), int(seed), float(deadline)).run()


# ======================================================================================== decoding
class TripOut:
    """A decoded trip: the stops served (facility index, counts), the shelter, its load and times."""

    __slots__ = ("stops", "shelter", "load", "count", "node", "t", "slack", "legs", "times", "u0")

    def __init__(self, stops, shelter, load, node, t, slack, legs, times, u0):
        self.stops, self.shelter, self.load = stops, shelter, load
        self.count = load[0] + load[1] + load[2]
        self.node, self.t, self.slack, self.legs, self.times, self.u0 = node, t, slack, legs, times, u0


class VDec:
    """A vehicle's decoded plan (immutable) with prefix and suffix summaries for insertion."""

    __slots__ = ("outs", "trips", "starts", "pre_count", "pre_slack", "suf_count", "suf_slack", "planned",
                 "slack", "end", "vtime", "legs")

    def __init__(self, net: "_Net", v: int, outs):
        self.outs = outs = tuple(outs)
        self.trips = tuple((o.stops, o.shelter) for o in outs)
        st = [(net.vnode[v], net.vstart[v])]
        pc, ps, legs = [0], [INF], 0
        for o in outs:
            st.append((o.node, o.t))
            pc.append(pc[-1] + o.count)
            ps.append(min(ps[-1], o.slack))
            legs += o.legs
        n = len(outs)
        sc, ss = [0] * (n + 1), [INF] * (n + 1)
        for i in range(n - 1, -1, -1):
            sc[i] = sc[i + 1] + outs[i].count
            ss[i] = min(ss[i + 1], outs[i].slack)
        self.starts, self.pre_count, self.pre_slack, self.suf_count, self.suf_slack = st, pc, ps, sc, ss
        self.planned, self.slack, self.end, self.legs = pc[-1], ps[-1], st[-1][1], legs
        self.vtime = self.end - net.vstart[v] if n else 0


class _Net:
    """Instance data as integers, POSITIVE-mask routing (``Reach.route`` with a precomputed fast path for the
    static path), trip decoding (Dispatcher semantics) and action emission."""

    def __init__(self, instance, rh: Reach, D: dict):
        self.inst, self.rh = instance, rh
        self.Hi, self.H = rh.Hi, rh.H
        F, S, V = instance.facilities, instance.shelters, instance.vehicles
        self.nF, self.nS, self.nV = len(F), len(S), len(V)
        self.fid = [f.id for f in F]
        self.fidx = {f.id: i for i, f in enumerate(F)}
        self.fnode = [rh.node(f.node) for f in F]
        self.rel = [int(math.ceil(f.release_s - 1e-6)) for f in F]
        self.board = [tuple(int(x) for x in f.boarding_s.vector()) for f in F]
        self.res = [tuple(int(x) for x in f.residents.vector()) for f in F]
        self.sid = [s.id for s in S]
        self.sidx = {s.id: i for i, s in enumerate(S)}
        self.snode = [rh.node(s.node) for s in S]
        self.unload = [tuple(int(x) for x in s.unloading_s.vector()) for s in S]
        self.windows = [[(int(math.ceil(a - 1e-6)), int(math.floor(b + 1e-6))) for a, b in s.open_windows] for s in S]
        self.scap = [tuple(int(x) for x in s.capacity.vector()) for s in S]
        self.vid = [v.id for v in V]
        self.vcap = [tuple(int(x) for x in v.capacity()) for v in V]
        self.vstart = [int(v.start_s) for v in V]
        self.vnode = [rh.node(v.depot) for v in V]
        self.vend = [rh.Hi if v.shift_limit_s is None else min(rh.Hi, int(math.floor(v.start_s + v.shift_limit_s + 1e-6)))
                     for v in V]
        self.D = {(self.fidx[f], c): int(d) for (f, c), d in D.items()}
        self.waitable = [bool(x) for x in rh.waitable]
        self.uns = [bool(x) for x in rh.node_unsupported]
        self.nlo = [list(lo) for lo, _ in rh.node_iv]
        self.nhi = [list(hi) for _, hi in rh.node_iv]
        self._pairs: dict = {}
        self._rem: dict = {}
        self._td: dict = {}
        self._lb: dict = {}
        self.td_calls = 0
        self.pair_count = 0

    # ------------------------------------------------------------------ primitives
    def stay_ok(self, v: int, a: float, b: float) -> bool:
        """Reach.stay_ok: a stationary occupancy of node v over [a, b] is usable."""
        if self.uns[v] or b > self.H + 1e-9 or a > b:
            return False
        hi = self.nhi[v]
        i = bisect_right(hi, a)
        return not (i < len(hi) and self.nlo[v][i] <= b)

    def stay_slack(self, v: int, b: float) -> float:
        """Relaxed slack of a usable stay at v ending at b: time to the node's next burning interval, capped at
        the horizon."""
        lo = self.nlo[v]
        i = bisect_right(lo, b)
        s = self.H - b
        if i < len(lo) and lo[i] - b < s:
            s = lo[i] - b
        return s

    def lb(self, dst: int) -> list:
        """Free-flow time from every node to ``dst`` ignoring turn rules (a lower bound)."""
        got = self._lb.get(dst)
        if got is None:
            got = self._lb[dst] = self.rh.lower_bound_to(dst).tolist()
        return got

    def _rem_arr(self, e: int) -> np.ndarray:
        r = self._rem.get(e)
        if r is None:
            r = np.full(self.Hi + 1, -1, dtype=np.int32)
            for a, b in zip(self.rh.free_lo[e], self.rh.free_hi[e]):
                r[a:b + 1] = np.arange(b - a, -1, -1, dtype=np.int32)
            self._rem[e] = r
        return r

    def _pair(self, src: int, dst: int):
        """For the turn-aware free-flow shortest path src -> dst: per departure second, is it usable at once
        (Reach.route's first test) and its relaxed slack; plus its travel time and number of legs."""
        key = (src, dst)
        got = self._pairs.get(key, _MISSING)
        if got is not _MISSING:
            return got
        sp = self.rh.static_path(src, dst)
        if sp is None:
            self._pairs[key] = None
            return None
        path, T = sp
        Hi, okT, Tl = self.Hi, self.rh.okT, self.rh.Tl
        ok = np.ones(Hi + 1, dtype=bool)
        sl = np.full(Hi + 1, np.iinfo(np.int32).max, dtype=np.int32)
        off = 0
        for e in path:
            if off > Hi:
                ok[:] = False
                break
            n = Hi + 1 - off
            ok[:n] &= okT[off:, e]
            ok[n:] = False
            np.minimum(sl[:n], self._rem_arr(e)[off:], out=sl[:n])
            off += Tl[e]
        slack = array("i")
        slack.frombytes(sl.tobytes())
        got = (bytes(ok.view(np.uint8)), slack, int(T), len(path))
        self._pairs[key] = got
        self.pair_count += 1
        return got

    def _route_summary(self, r, src: int):
        rh = self.rh
        s, legs, v, t = INF, 0, src, r.start
        for e, d in r.steps:
            if d > t:
                s = min(s, self.stay_slack(v, d))
                legs += 1
            lo, hi = rh.free_lo[e], rh.free_hi[e]
            s = min(s, hi[bisect_right(lo, d) - 1] - d)
            legs += 1
            t, v = d + rh.Tl[e], rh.headl[e]
        return s, legs

    def arrive(self, src: int, t: int, dst: int):
        """(arrival, relaxed slack, legs) of ``Reach.route(src, t, dst)``, or None if there is no route."""
        if src == dst:
            return (t, INF, 0)
        if t > self.Hi:
            return None
        p = self._pairs.get((src, dst), _MISSING)
        if p is _MISSING:
            p = self._pair(src, dst)
        if p is None:
            return None
        if p[0][t]:
            return (t + p[2], p[1][t], p[3])
        key = (src, t, dst)
        got = self._td.get(key, _MISSING)
        if got is _MISSING:
            self.td_calls += 1
            r = self.rh.route(src, t, dst)
            if r is None:
                got = None
            else:
                s, legs = self._route_summary(r, src)
                got = (r.arrival, s, legs)
            if len(self._td) >= _TD_CACHE_MAX:
                self._td.clear()
            self._td[key] = got
        return got

    # ---------------------------------------------------------------------- trips
    def trip(self, v: int, node: int, t: int, stops, shelters) -> TripOut | None:
        """Decode one trip from state (node, t): serve the stops in order (a stop that cannot be served is
        skipped), then unload everything at the shelter of ``shelters`` where unloading ends first."""
        vend = self.vend[v]
        done, times = [], []
        l0 = l1 = l2 = 0
        slack, legs = INF, 0
        for f, cnt in stops:
            fn = self.fnode[f]
            r = self.arrive(node, t, fn)
            if r is None:
                continue
            a, rs, rl = r
            rel = self.rel[f]
            s0 = a if a >= rel else rel
            if s0 > a and not (self.waitable[fn] and self.stay_ok(fn, a, s0)):
                continue
            b = self.board[f]
            e = s0 + cnt[0] * b[0] + cnt[1] * b[1] + cnt[2] * b[2]
            if e > vend or not self.stay_ok(fn, s0, e):
                continue
            ss = self.stay_slack(fn, e)
            if rs < slack:
                slack = rs
            if ss < slack:
                slack = ss
            legs += rl + 1 + (s0 > a)
            done.append((f, cnt))
            times.append((s0, e))
            l0 += cnt[0]
            l1 += cnt[1]
            l2 += cnt[2]
            node, t = fn, e
        if not done:
            return None
        lim = vend if vend < self.Hi else self.Hi
        best = None
        for s in shelters:
            sn = self.snode[s]
            r = self.arrive(node, t, sn)
            if r is None:
                continue
            a, rs, rl = r
            u = self.unload[s]
            U = l0 * u[0] + l1 * u[1] + l2 * u[2]
            u0 = None
            for lo, hi in self.windows[s]:
                st = a if a >= lo else lo
                if st + U <= (hi if hi < lim else lim):
                    u0 = st
                    break
            if u0 is None:
                continue
            if u0 > a and not (self.waitable[sn] and self.stay_ok(sn, a, u0)):
                continue
            end = u0 + U
            if not self.stay_ok(sn, u0, end):
                continue
            if best is None or end < best[0]:
                best = (end, s, u0, min(rs, self.stay_slack(sn, end)), rl + 1 + (u0 > a))
        if best is None:
            return None
        end, s, u0, ds, dl = best
        return TripOut(tuple(done), s, (l0, l1, l2), self.snode[s], end, min(slack, ds), legs + dl, tuple(times), u0)

    def decode(self, v: int, node: int, t: int, keys) -> list:
        """Decode trips (``(stops, shelter)`` keys) from state (node, t); infeasible ones are dropped."""
        outs = []
        for stops, s in keys:
            r = self.trip(v, node, t, stops, (s,))
            if r is not None:
                outs.append(r)
                node, t = r.node, r.t
        return outs

    def tail(self, v: int, node: int, t: int, vd: VDec, i0: int):
        """Re-decode ``vd``'s trips from index ``i0`` starting at state (node, t). Returns (outs, residents,
        min slack, end time). Stops early when a trip starts in the same state as before (the rest is unchanged)."""
        outs, count, slack = [], 0, INF
        starts, old = vd.starts, vd.outs
        for i in range(i0, len(old)):
            st = starts[i]
            if st[1] == t and st[0] == node:
                outs.extend(old[i:])
                count += vd.suf_count[i]
                if vd.suf_slack[i] < slack:
                    slack = vd.suf_slack[i]
                return outs, count, slack, vd.end
            o = old[i]
            r = self.trip(v, node, t, o.stops, (o.shelter,))
            if r is None:
                continue
            outs.append(r)
            count += r.count
            if r.slack < slack:
                slack = r.slack
            node, t = r.node, r.t
        return outs, count, slack, t

    # ------------------------------------------------------------------- actions
    def emit(self, v: int, vd: VDec) -> list:
        """Schema actions of a decoded vehicle plan (the routes of ``Reach.route``; the times must match the decode)."""
        rh = self.rh
        node, t = self.vnode[v], self.vstart[v]
        acts: list = []
        for o in vd.outs:
            for (f, cnt), (s0, e) in zip(o.stops, o.times):
                fn = self.fnode[f]
                r = rh.route(node, t, fn)
                if r is None:
                    raise AssertionError(f"e1: no route to facility {self.fid[f]} at {t} while emitting")
                acts += rh.actions(r, node)
                a = r.arrival
                s = max(a, self.rel[f])
                if s > a:
                    acts.append(Wait(node=rh.node_ids[fn], duration_s=float(s - a)))
                acts.append(Board(facility=self.fid[f], counts=ClassCounts.of(cnt)))
                b = self.board[f]
                t2 = s + cnt[0] * b[0] + cnt[1] * b[1] + cnt[2] * b[2]
                if (s, t2) != (s0, e):
                    raise AssertionError(f"e1: boarding at {self.fid[f]} emitted at {(s, t2)}, decoded {(s0, e)}")
                node, t = fn, t2
            sn = self.snode[o.shelter]
            r = rh.route(node, t, sn)
            if r is None:
                raise AssertionError(f"e1: no route to shelter {self.sid[o.shelter]} at {t} while emitting")
            acts += rh.actions(r, node)
            a = r.arrival
            if o.u0 > a:
                acts.append(Wait(node=rh.node_ids[sn], duration_s=float(o.u0 - a)))
            elif o.u0 < a:
                raise AssertionError("e1: unloading before arrival")
            acts.append(Unload(shelter=self.sid[o.shelter], counts=ClassCounts.of(o.load)))
            u = self.unload[o.shelter]
            if o.u0 + o.load[0] * u[0] + o.load[1] * u[1] + o.load[2] * u[2] != o.t:
                raise AssertionError("e1: unloading end differs from the decode")
            node, t = sn, o.t
        return acts


# ========================================================================================= state
class _St:
    """A solution: decoded vehicle plans, the pool of unplanned residents and the shelters' room left."""

    __slots__ = ("vd", "pool", "room")

    def __init__(self, vd, pool, room):
        self.vd, self.pool, self.room = vd, pool, room

    def copy(self) -> "_St":
        return _St(list(self.vd), dict(self.pool), [list(r) for r in self.room])

    def key(self) -> tuple:
        return tuple(d.trips for d in self.vd)


class _Opt:
    __slots__ = ("ty", "v", "j", "outs", "dp", "sl", "dvt", "val", "shelter", "load", "old_shelter", "old_load")


class _Cert:
    __slots__ = ("first_bad", "delivered", "min_slack", "actions", "legs", "cause", "cut_residents")


# =========================================================================================== run
class _Run:
    def __init__(self, cfg: dict, name: str, instance, ss, budget_s: float, seed: int, deadline: float):
        self.cfg, self.name, self.inst, self.ss = cfg, name, instance, ss
        self.budget, self.seed, self.deadline = budget_s, seed, deadline
        self.rng = random.Random(seed)
        self.reserve = cfg["reserve_s"] if cfg["reserve_s"] is not None else 0.5 + 0.03 * budget_s
        self.max_it = None if cfg["max_iterations"] is None else int(cfg["max_iterations"])
        self.max_stops = int(cfg["max_stops"])
        self.t_oracle = 0.0
        self.oracle_checks = 0
        self.oracle_legs = 0
        self.relaxed_blocks = 0
        self.cert: dict = {}
        self.bad_prefix: set = set()
        self.cut_by_cause: Counter = Counter()
        self.s_per_leg = float(cfg["oracle_s_per_leg0"])

    # ------------------------------------------------------------- objective
    def _term(self, slack: float) -> int:
        if slack == INF:
            return self.Hi
        return min(self.Hi, max(0, int(math.floor(slack))))

    def _F(self, delivered: int, slack: float, vtime: int) -> int:
        return self.A * delivered + self.B * self._term(slack) - vtime

    def F(self, st: _St) -> int:
        planned, slack, vt = 0, INF, 0
        for d in st.vd:
            if d.outs:
                planned += d.planned
                vt += d.vtime
                if d.slack < slack:
                    slack = d.slack
        return self._F(planned, slack, vt)

    @staticmethod
    def planned(st: _St) -> int:
        return sum(d.planned for d in st.vd)

    # -------------------------------------------------------------- ledgers
    def _set_vehicle(self, st: _St, v: int, vd: VDec) -> None:
        """Replace vehicle v's plan, cutting any itinerary prefix the oracle already rejected, and update the
        pool and the shelters' room."""
        if self.bad_prefix and vd.outs:
            trips = vd.trips
            for k in range(len(trips)):
                if (v, trips[:k + 1]) in self.bad_prefix:
                    vd = VDec(self.net, v, vd.outs[:k])
                    self.known_cuts += 1
                    break
        pool, room = st.pool, st.room
        for o in st.vd[v].outs:
            r = room[o.shelter]
            for f, cnt in o.stops:
                for c in range(3):
                    if cnt[c]:
                        pool[(f, c)] += cnt[c]
                        r[c] += cnt[c]
        for o in vd.outs:
            r = room[o.shelter]
            for f, cnt in o.stops:
                for c in range(3):
                    if cnt[c]:
                        pool[(f, c)] -= cnt[c]
                        r[c] -= cnt[c]
                        if pool[(f, c)] < 0 or r[c] < 0:  # pragma: no cover - insertion checks room and pool
                            raise AssertionError("e1: plan beyond residents or shelter capacity")
        st.vd[v] = vd

    # -------------------------------------------------------------- requests
    def _requests(self, st: _St) -> list:
        out = []
        for v, d in enumerate(st.vd):
            for j, o in enumerate(d.outs):
                for i, (f, cnt) in enumerate(o.stops):
                    for c in range(3):
                        if cnt[c]:
                            for size in chunk_sizes(cnt[c], self.q.get((f, c), 1)):
                                out.append((v, j, i, c, size))
        return out

    def _remove(self, st: _St, reqs: list) -> None:
        byv: dict = {}
        for v, j, i, c, size in reqs:
            k = (j, i, c)
            m = byv.setdefault(v, {})
            m[k] = m.get(k, 0) + size
        net = self.net
        for v in sorted(byv):
            d, rm = st.vd[v], byv[v]
            keys, first = [], None
            for j, o in enumerate(d.outs):
                stops, changed = [], False
                for i, (f, cnt) in enumerate(o.stops):
                    x = (rm.get((j, i, 0), 0), rm.get((j, i, 1), 0), rm.get((j, i, 2), 0))
                    if x[0] or x[1] or x[2]:
                        changed = True
                        cnt = (cnt[0] - x[0], cnt[1] - x[1], cnt[2] - x[2])
                    if cnt[0] or cnt[1] or cnt[2]:
                        stops.append((f, cnt))
                if changed and first is None:
                    first = j
                if stops:
                    keys.append((tuple(stops), o.shelter))
            if first is None:
                continue
            outs = list(d.outs[:first]) + net.decode(v, *d.starts[first], keys[first:])
            self._set_vehicle(st, v, VDec(net, v, outs))

    # ---------------------------------------------------------------- destroy
    def _pick(self, p: float, order: list) -> int:
        """Ropke & Pisinger's randomised choice from a ranked list: the element at floor(y^p |L|), y ~ U[0, 1)."""
        y = self.rng.random()
        return order.pop(int(y ** p * len(order)))

    def d_random(self, st: _St, q: int) -> None:
        reqs = self._requests(st)
        if reqs:
            idx = sorted(self.rng.sample(range(len(reqs)), min(q, len(reqs))))
            self._remove(st, [reqs[i] for i in idx])

    def d_worst_slack(self, st: _St, q: int) -> None:
        reqs = self._requests(st)
        if not reqs:
            return
        order = sorted(range(len(reqs)), key=lambda r: (st.vd[reqs[r][0]].outs[reqs[r][1]].slack, r))
        chosen = [self._pick(self.cfg["p_worst"], order) for _ in range(min(q, len(reqs)))]
        self._remove(st, [reqs[i] for i in sorted(chosen)])

    def d_related(self, st: _St, q: int) -> None:
        reqs = self._requests(st)
        if not reqs:
            return
        net = self.net
        att = []
        for v, j, i, c, size in reqs:
            o = st.vd[v].outs[j]
            f = o.stops[i][0]
            att.append((net.fnode[f], net.snode[o.shelter], o.times[i][0], o.u0, size, self.kmask[c]))
        w1, w2, w3, w4 = self.cfg["shaw_weights"]
        maxd, Hi, qmax = self.maxd, float(self.Hi), float(self.qmax)

        def rel(a, b) -> float:
            fa, sa, ta, ua, na, ka = att[a]
            fb, sb, tb, ub, nb, kb = att[b]
            both = bin(ka & kb).count("1")
            small = min(bin(ka).count("1"), bin(kb).count("1")) or 1
            return (w1 * (self._dist(fa, fb) + self._dist(sa, sb)) / maxd
                    + w2 * (abs(ta - tb) + abs(ua - ub)) / Hi
                    + w3 * abs(na - nb) / qmax
                    + w4 * (1.0 - both / small))

        first = self.rng.randrange(len(reqs))
        chosen, rest = [first], [r for r in range(len(reqs)) if r != first]
        while len(chosen) < min(q, len(reqs)) and rest:
            r = chosen[self.rng.randrange(len(chosen))]
            rest.sort(key=lambda x: (rel(r, x), x))
            chosen.append(self._pick(self.cfg["p_shaw"], rest))
        self._remove(st, [reqs[i] for i in sorted(chosen)])

    def _by_group(self, st: _St, group) -> dict:
        out: dict = {}
        for r in self._requests(st):
            out.setdefault(group(r), []).append(r)
        return out

    def d_trips(self, st: _St, q: int) -> None:
        groups = self._by_group(st, lambda r: (r[0], r[1]))
        keys = sorted(groups)
        self.rng.shuffle(keys)
        sel = []
        for k in keys:
            if len(sel) >= q:
                break
            sel += groups[k]
        self._remove(st, sel)

    def d_vehicles(self, st: _St, q: int) -> None:
        groups = self._by_group(st, lambda r: r[0])
        keys = sorted(groups)
        self.rng.shuffle(keys)
        sel = []
        for k in keys:
            if len(sel) >= q:
                break
            sel += groups[k]
        self._remove(st, sel)

    def _dist(self, a: int, b: int) -> float:
        if a == b:
            return 0.0
        key = (a, b) if a < b else (b, a)
        got = self._dists.get(key)
        if got is None:
            x, y = self.net.lb(b)[a], self.net.lb(a)[b]
            big = 1 << 59
            got = self.maxd if (x >= big or y >= big) else 0.5 * (x + y)
            self._dists[key] = got
        return got

    # ------------------------------------------------------------------ repair
    def _types(self, st: _St) -> dict:
        out = {}
        for fc in self.insertable:
            n = st.pool[fc]
            if n > 0:
                for size, k in sorted(Counter(chunk_sizes(n, self.q[fc])).items(), reverse=True):
                    out[(fc[0], fc[1], size)] = k
        return out

    def _best_option(self, st: _St, v: int, ty: tuple, amp: float, m_other: float, cur_term: int) -> _Opt | None:
        f, c, n = ty
        net = self.net
        cap = net.vcap[v]
        if cap[c] < n:
            return None
        d = st.vd[v]
        outs = d.outs
        ntr = len(outs)
        Dfc = net.D[(f, c)]
        fn = net.fnode[f]
        lbf = net.lb(fn)
        relf = net.rel[f]
        bnf = net.board[f][c] * n
        if max(net.vstart[v] + lbf[net.vnode[v]], relf) + bnf > Dfc:
            return None
        cv = (n if c == 0 else 0, n if c == 1 else 0, n if c == 2 else 0)
        room = st.room
        nS = net.nS
        old_planned, old_vt, vstart = d.planned, d.vtime, net.vstart[v]
        A, B, Hi = self.A, self.B, self.Hi
        rng = self.rng
        best: _Opt | None = None
        best_val = -INF
        starts, pre_count, pre_slack = d.starts, d.pre_count, d.pre_slack
        bad = self.bad_prefix

        suf_count = d.suf_count

        def consider(j, o, nxt, shelter, load, old_shelter, old_load):
            nonlocal best, best_val
            # exact pruning: the later trips cannot gain residents, and residents dominate the scalarisation
            up = pre_count[j] + o.count + suf_count[nxt] - old_planned
            if up <= 0 or (best is not None and up < best.dp):
                return
            touts, tcnt, tsl, tend = net.tail(v, o.node, o.t, d, nxt)
            dp = pre_count[j] + o.count + tcnt - old_planned
            if dp <= 0:
                return
            if bad:                             # an itinerary prefix the oracle already rejected
                keys = d.trips[:j] + ((o.stops, o.shelter),) + tuple((x.stops, x.shelter) for x in touts)
                if any((v, keys[:kk + 1]) in bad for kk in range(j, len(keys))):
                    return
            sl = pre_slack[j]
            if o.slack < sl:
                sl = o.slack
            if tsl < sl:
                sl = tsl
            dvt = (tend - vstart) - old_vt
            if amp:
                dvt += rng.uniform(-amp, amp)
            m = m_other if m_other < sl else sl
            term = Hi if m == INF else min(Hi, max(0, int(m)))
            val = A * dp + B * (term - cur_term) - dvt
            if val > best_val:
                best_val = val
                opt = _Opt()
                opt.ty, opt.v, opt.j, opt.outs = ty, v, j, [o] + touts
                opt.dp, opt.sl, opt.dvt, opt.val = dp, sl, dvt, val
                opt.shelter, opt.load, opt.old_shelter, opt.old_load = shelter, load, old_shelter, old_load
                best = opt

        new_shelters = [s for s in range(nS) if room[s][c] >= n]
        # (C) a new trip at position k
        if new_shelters:
            stops = ((f, cv),)
            for k in range(ntr + 1):
                node, t = starts[k]
                if max(t + lbf[node], relf) + bnf > Dfc:
                    break                       # later positions start no earlier (triangle inequality)
                o = net.trip(v, node, t, stops, new_shelters)
                if o is None or o.count < n:
                    continue
                consider(k, o, k, o.shelter, cv, None, None)
        # (A) top up a stop at f / (B) add a stop at f, in trip j
        for j in range(ntr):
            node, t = starts[j]
            if max(t + lbf[node], relf) + bnf > Dfc:
                break
            oj = outs[j]
            load = oj.load
            if load[c] + n > cap[c]:
                continue
            new_load = (load[0] + cv[0], load[1] + cv[1], load[2] + cv[2])
            so = oj.shelter
            shel = [s for s in range(nS)
                    if all(room[s][x] + (load[x] if s == so else 0) >= new_load[x] for x in range(3))]
            if not shel:
                continue
            stops = oj.stops
            pos = next((i for i, (g, _) in enumerate(stops) if g == f), -1)
            variants = []
            if pos >= 0:
                if oj.times[pos][1] + bnf > Dfc:
                    continue
                g, cnt = stops[pos]
                variants.append(stops[:pos] + ((g, (cnt[0] + cv[0], cnt[1] + cv[1], cnt[2] + cv[2])),) + stops[pos + 1:])
            elif len(stops) < self.max_stops:
                for p in range(len(stops) + 1):
                    if p == 0:
                        pn, pt = node, t
                    else:
                        pn, pt = net.fnode[stops[p - 1][0]], oj.times[p - 1][1]
                    if max(pt + lbf[pn], relf) + bnf > Dfc:
                        break
                    variants.append(stops[:p] + ((f, cv),) + stops[p:])
            for new_stops in variants:
                o = net.trip(v, node, t, new_stops, shel)
                if o is None:
                    continue
                consider(j, o, j + 1, o.shelter, new_load, so, load)
        return best

    def _room_ok(self, st: _St, o: _Opt) -> bool:
        r = st.room[o.shelter]
        if o.old_shelter is None:
            return all(r[x] >= o.load[x] for x in range(3))
        add = o.old_load if o.shelter == o.old_shelter else (0, 0, 0)
        return all(r[x] + add[x] >= o.load[x] for x in range(3))

    def repair(self, st: _St, k: int, noise: bool, stop_at: float) -> int:
        """Greedy (k = 1) or regret-k insertion of the pool's chunks; returns the number of chunks inserted."""
        net = self.net
        amp = self.noise_amp if noise else 0.0
        types = self._types(st)
        if not types:
            return 0
        V = range(net.nV)
        slacks = [d.slack if d.outs else INF for d in st.vd]

        def plan_terms():
            lo1, lo2, arg = INF, INF, -1
            for v, s in enumerate(slacks):
                if s < lo1:
                    lo1, lo2, arg = s, lo1, v
                elif s < lo2:
                    lo2 = s
            mo = [lo2 if v == arg else lo1 for v in V]
            return mo, self._term(lo1)

        m_other, cur_term = plan_terms()
        best: dict = {}
        for ty in types:
            for v in V:
                best[(ty, v)] = self._best_option(st, v, ty, amp, m_other[v], cur_term)
        inserted = 0
        taboo: set = set()                      # (type, vehicle) whose applied option did not hold (guard)
        A, B, Hi = self.A, self.B, self.Hi
        while types:
            if time.monotonic() > stop_at:
                self.repairs_cut_short += 1
                break
            choice, ckey = None, None
            for ty in types:
                vals = []
                for v in V:
                    o = best[(ty, v)]
                    if o is not None:
                        m = m_other[v] if m_other[v] < o.sl else o.sl
                        term = Hi if m == INF else min(Hi, max(0, int(m)))
                        vals.append((A * o.dp + B * (term - cur_term) - o.dvt, -v, o))
                if not vals:
                    continue
                vals.sort(key=lambda x: (x[0], x[1]), reverse=True)
                if k <= 1:
                    key = (vals[0][0],)
                else:
                    nf = len(vals)
                    reg = sum(vals[0][0] - vals[j][0] for j in range(1, min(k, nf)))
                    key = (k - nf if nf < k else 0, reg, vals[0][0])
                if ckey is None or key > ckey:
                    ckey, choice = key, vals[0][2]
            if choice is None:
                break
            v = choice.v
            if not self._room_ok(st, choice):
                best[(choice.ty, v)] = self._best_option(st, v, choice.ty, amp, m_other[v], cur_term)
                continue
            d = st.vd[v]
            expected = d.planned + choice.dp
            self._set_vehicle(st, v, VDec(net, v, list(d.outs[:choice.j]) + choice.outs))
            if st.vd[v].planned != expected:     # pragma: no cover - options already skip known-bad prefixes
                taboo.add((choice.ty, v))
            inserted += 1
            slacks[v] = st.vd[v].slack if st.vd[v].outs else INF
            m_other, cur_term = plan_terms()
            new_types = self._types(st)
            for key in list(best):
                if key[0] not in new_types:
                    del best[key]
            for ty in new_types:
                if ty not in types:
                    for u in V:
                        if u != v:
                            best[(ty, u)] = (None if (ty, u) in taboo
                                             else self._best_option(st, u, ty, amp, m_other[u], cur_term))
                best[(ty, v)] = None if (ty, v) in taboo else self._best_option(st, v, ty, amp, m_other[v], cur_term)
            types = new_types
        return inserted

    # --------------------------------------------------------------- oracle
    def _estimate(self, st: _St | None) -> float:
        """Seconds to certify ``st`` (its itineraries not yet checked), with the safety factor."""
        if st is None:
            return 0.0
        legs = sum(d.legs for v, d in enumerate(st.vd) if d.outs and (v, d.trips) not in self.cert)
        return legs * self.s_per_leg * self.cfg["oracle_safety"]

    def _check(self, v: int, d: VDec, hard: float, prefix: bool = False) -> _Cert | None:
        """The oracle's verdict on vehicle v's itinerary (cached); None if it would not finish before ``hard``.
        ``prefix``: the itinerary is a prefix of one just checked (every hazard query is in the oracle's cache)."""
        key = (v, d.trips)
        got = self.cert.get(key)
        if got is not None:
            return got
        if not prefix and time.monotonic() + d.legs * self.s_per_leg * self.cfg["oracle_safety"] > hard:
            return None
        t0 = time.monotonic()
        got = _Cert()
        got.cut_residents = 0
        try:
            acts = self.net.emit(v, d)
        except AssertionError:                    # pragma: no cover - a decode/emit mismatch is a bug: keep it out
            self.emit_errors += 1
            got.actions, got.first_bad, got.delivered, got.min_slack, got.legs = [], 0, None, None, 0
            got.cause = "EMIT_MISMATCH"
            self.cert[key] = got
            return got
        got.actions = acts
        it = Itinerary(vehicle=self.net.vid[v], actions=acts)
        rx = self.relaxed.itinerary(it)
        if rx.first_blocked is not None:          # the oracle would reject a leg: a decoder bug; cut there
            self.relaxed_blocks += 1
            act = rx.segments[rx.first_blocked].action
            got.first_bad = sum(1 for a in acts[:act] if isinstance(a, Unload))
            got.delivered, got.min_slack, got.legs, got.cause = None, None, 0, "RELAXED_CONTACT_BLOCK"
        else:
            res = self.oracle.check_itinerary(it)
            if len(res.trips) != len(d.outs):  # pragma: no cover - one unloading per trip
                raise AssertionError("e1: oracle trips do not match the decoded trips")
            ok = [t.state is State.CHECKED for t in res.trips]
            bad = next((k for k, x in enumerate(ok) if not x), None)
            got.first_bad = bad
            got.delivered = sum(t.counts.total for t, x in zip(res.trips, ok) if x)
            got.min_slack = res.min_slack_s
            got.legs = len(res.legs)
            got.cause = None if bad is None else res.trips[bad].cause
            self.oracle_checks += 1
            self.oracle_legs += got.legs
        dt = time.monotonic() - t0
        self.t_oracle += dt
        if not prefix:                           # prefixes are cheap re-checks: keep them out of the cost estimate
            self.t_oracle_new += dt
            self.t_oracle_legs += max(1, d.legs)
            self.s_per_leg = self.t_oracle_new / self.t_oracle_legs
        self.cert[key] = got
        return got

    def certify(self, st: _St, hard: float):
        """Check every itinerary of ``st`` with the oracle; cut each before its first trip that is not checked.
        Returns (the cut plan, its certified objective, residents cut) or None if the time does not allow it."""
        cut = st.copy()
        removed = 0
        for v in range(self.net.nV):
            prefix = False
            while cut.vd[v].outs:
                d = cut.vd[v]
                r = self._check(v, d, hard, prefix)
                if r is None:
                    return None
                if r.first_bad is None:
                    break
                lost = sum(o.count for o in d.outs[r.first_bad:])
                removed += lost
                self.cut_by_cause[r.cause or "unknown"] += lost
                r.cut_residents = lost
                self.bad_prefix.add((v, d.trips[:r.first_bad + 1]))
                self._set_vehicle(cut, v, VDec(self.net, v, d.outs[:r.first_bad]))
                prefix = True
        delivered, slack, vt = 0, INF, 0
        for v, d in enumerate(cut.vd):
            if d.outs:
                r = self.cert[(v, d.trips)]
                delivered += r.delivered
                if r.min_slack is not None and r.min_slack < slack:
                    slack = r.min_slack
                vt += d.vtime
        self.certifications += 1
        return cut, self._F(delivered, slack, vt), removed, delivered

    def _apply_known(self, st: _St) -> _St:
        """A copy of ``st`` with every itinerary prefix the oracle rejected cut."""
        out = st.copy()
        for v, d in enumerate(st.vd):
            if d.outs:
                self._set_vehicle(out, v, d)
        return out

    def _try_certify(self, st: _St, hard: float, why: str) -> bool:
        """Certify ``st``; make it the incumbent if it is better. Returns True if the certification ran."""
        got = self.certify(st, hard)
        if got is None:
            self.cert_skipped += 1
            return False
        cut, Fc, removed, delivered = got
        self.dose_cut_residents += removed
        better = Fc > self.inc_F
        if not better and not self.inc_certified and self.warm is not None:
            # the incumbent is the uncertified warm start: certify it so the comparison is between certified plans
            wg = self.certify(self.warm, hard)
            if wg is not None:
                wcut, wF, wrem, wdel = wg
                self.dose_cut_residents += wrem
                self.inc, self.inc_F, self.inc_certified, self.inc_delivered = wcut, wF, True, wdel
                self.history.append((self.it, round(time.monotonic() - self.t0, 2), wdel, "warm"))
                better = Fc > self.inc_F
        if better:
            self.inc, self.inc_F, self.inc_certified, self.inc_delivered = cut, Fc, True, delivered
            self.history.append((self.it, round(time.monotonic() - self.t0, 2), delivered, why))
        return True

    # ------------------------------------------------------------------- run
    def _warm_start(self, rh: Reach, D: dict, stop_at: float) -> Dispatcher:
        """B1 (greedy earliest-deadline-first insertion, ``B1Greedy`` with its default rule) on this run's Reach."""
        b1 = B1Greedy()
        dsp = Dispatcher(self.inst, rh)
        dead: set = set()
        self.warm_complete = True
        while True:
            if time.monotonic() > stop_at:
                self.warm_complete = False
                break
            jobs = [(dl, fid, c) for (fid, c), dl in D.items() if (fid, c) not in dead and dsp.left[fid][c] > 0]
            if not jobs:
                break
            _, fid, c = min(jobs)
            best, best_key = None, None
            for vs in dsp.vs.values():
                tr = b1._trip(dsp, vs, fid, c, D)
                if tr is not None and (best is None or b1._key(dsp, tr) < best_key):
                    best, best_key = tr, b1._key(dsp, tr)
            if best is None:
                dead.add((fid, c))
                continue
            dsp.commit(best)
        return dsp

    def _alns(self, st: _St, hard: float) -> dict:
        """The ALNS loop and the final certification; returns the search statistics (also kept up to date in
        ``self.ad`` so that a failure still reports how far the search got)."""
        cfg, t0 = self.cfg, self.t0
        ad = self.ad
        destroy = [("random", self.d_random), ("worst_slack", self.d_worst_slack), ("related", self.d_related),
                   ("trips", self.d_trips), ("vehicles", self.d_vehicles)]
        ks = [1] + [k for k in cfg["regret_k"] if k >= 2]
        repair_names = ["greedy"] + [f"regret{k}" for k in ks[1:]]
        w_d, w_r, w_z = [1.0] * len(destroy), [1.0] * len(ks), [1.0, 1.0]
        pi_d, pi_r, pi_z = [0.0] * len(destroy), [0.0] * len(ks), [0.0, 0.0]
        th_d, th_r, th_z = [0] * len(destroy), [0] * len(ks), [0, 0]
        used_d, used_r = [0] * len(destroy), [0] * len(ks)
        s1, s2, s3 = cfg["scores"]
        seg, react = int(cfg["segment"]), float(cfg["reaction"])
        cur, F_cur = st, self.F(st)
        best_F = max(F_cur, self.inc_F)
        best_planned = self.planned(cur)
        pending = None
        visited = {hash(cur.key())}
        D0 = F_cur / self.A
        T0 = cfg["start_worse"] * D0 / math.log(2) if D0 > 0 else 0.0
        decay = math.log(cfg["cooling"]) * cfg["cooling_iterations"]
        t_search0 = time.monotonic()
        span = max(1e-9, hard - t_search0)
        n_acc = n_better = n_best = 0
        it_times: list[float] = []
        stop = "budget"

        def roulette(w):
            x = self.rng.random() * sum(w)
            for i, wi in enumerate(w):
                x -= wi
                if x < 0:
                    return i
            return len(w) - 1

        while True:
            now = time.monotonic()
            if self.max_it is not None and self.it >= self.max_it:
                stop = "max_iterations"
                break
            est_it = 2.0 * (sum(it_times[-20:]) / len(it_times[-20:])) if it_times else 0.0
            need = self._estimate(pending if pending is not None else (None if self.inc_certified else self.warm))
            if now + est_it + need >= hard:
                # the time left only suffices to certify: certify the pending candidate now, then go on searching
                # with what remains (a later certification needs only the itineraries that changed)
                if pending is not None and self.F(pending) <= self.inc_F:
                    pending = None
                    continue
                if pending is not None and self._try_certify(pending, hard, "time"):
                    pending = None
                    if self.bad_prefix:
                        cur = self._apply_known(cur)
                        F_cur = self.F(cur)
                    best_F = max(self.inc_F, F_cur)
                    continue
                break
            self.it += 1
            frac = (self.it / self.max_it) if self.max_it else (now - t_search0) / span
            T = T0 * math.exp(decay * min(1.0, frac))
            di, ri, zi = roulette(w_d), roulette(w_r), roulette(w_z)
            used_d[di] += 1
            used_r[ri] += 1
            c = cur.copy()
            n_req = len(self._requests(c))
            if n_req:
                lo = max(1, math.ceil(cfg["remove_min"] * n_req))
                hi = max(lo, int(cfg["remove_max"] * n_req))
                destroy[di][1](c, self.rng.randint(lo, hi))
            self.repair(c, ks[ri], zi == 1, hard - need)
            Fc = self.F(c)
            kc = hash(c.key())
            score = 0.0
            if Fc > best_F:
                best_F, pending, score = Fc, c, s1
                best_planned = self.planned(c)
                n_best += 1
            if Fc >= F_cur or (T > 0 and self.rng.random() < math.exp((Fc - F_cur) / self.A / T)):
                if kc not in visited:
                    if score == 0.0:
                        score = s2 if Fc > F_cur else (s3 if Fc < F_cur else 0.0)
                    visited.add(kc)
                if Fc > F_cur:
                    n_better += 1
                cur, F_cur = c, Fc
                n_acc += 1
            pi_d[di] += score
            pi_r[ri] += score
            pi_z[zi] += score
            th_d[di] += 1
            th_r[ri] += 1
            th_z[zi] += 1
            it_times.append(time.monotonic() - now)
            ad.update(iterations=self.it, accepted=n_acc, improvements=n_better, new_best=n_best,
                      relaxed_best=best_planned)
            if self.it % seg == 0:
                for w, pi, th in ((w_d, pi_d, th_d), (w_r, pi_r, th_r), (w_z, pi_z, th_z)):
                    for i in range(len(w)):
                        if th[i]:
                            w[i] = w[i] * (1 - react) + react * pi[i] / th[i]
                        pi[i], th[i] = 0.0, 0
                if pending is not None and self.F(pending) > self.inc_F:
                    if self._try_certify(pending, hard, "segment"):
                        pending = None
                        if self.bad_prefix:
                            cur = self._apply_known(cur)
                            F_cur = self.F(cur)
                        best_F = max(self.inc_F, F_cur)
                elif pending is not None:
                    pending = None
        t_search = time.monotonic() - t_search0

        # ---- final certification
        t_f0 = time.monotonic()
        if pending is not None and self.F(pending) > self.inc_F:
            self._try_certify(pending, hard, "final")
        if not self.inc_certified and self.warm is not None and any(d.outs for d in self.warm.vd):
            got = self.certify(self.warm, hard)
            if got is not None:
                wcut, wF, wrem, wdel = got
                self.dose_cut_residents += wrem
                self.inc, self.inc_F, self.inc_certified, self.inc_delivered = wcut, wF, True, wdel
                self.history.append((self.it, round(time.monotonic() - t0, 2), wdel, "warm"))
        t_final_cert = time.monotonic() - t_f0
        ad.update(iterations=self.it, accepted=n_acc, improvements=n_better, new_best=n_best, stop=stop,
                  relaxed_best=best_planned, T0=T0,
                  weights={"destroy": {n: round(w, 3) for (n, _), w in zip(destroy, w_d)},
                           "repair": {n: round(w, 3) for n, w in zip(repair_names, w_r)},
                           "noise": {"off": round(w_z[0], 3), "on": round(w_z[1], 3)}},
                  used={"destroy": {n: u for (n, _), u in zip(destroy, used_d)},
                        "repair": {n: u for n, u in zip(repair_names, used_r)}},
                  t_search=t_search, t_final_cert=t_final_cert)
        return ad

    def run(self) -> MethodResult:
        self.t0 = t0 = time.monotonic()
        cfg, inst = self.cfg, self.inst
        hard = self.deadline - self.reserve
        rh = Reach(inst, self.ss)
        D = latest_departures(inst, rh)
        net = self.net = _Net(inst, rh, D)
        self.Hi = net.Hi
        self.B = net.nV * (net.Hi + 1) + 1
        self.A = self.B * (net.Hi + 1) + 1
        # requests: B2's chunk rule
        self.q = {}
        for f, fac in enumerate(inst.facilities):
            for c in range(3):
                caps = [cap[c] for cap in net.vcap if cap[c] > 0]
                big = [x for x in caps if x >= 2]
                qq = min(big) if big else 1
                b = net.board[f][c]
                if (f, c) in net.D and b > 0:
                    qq = max(1, min(qq, (net.D[(f, c)] - net.rel[f]) // b))
                self.q[(f, c)] = qq
        self.qmax = max(self.q.values(), default=1)
        self.insertable = sorted((f, c) for (f, c) in net.D if net.res[f][c] > 0
                                 and any(cap[c] > 0 for cap in net.vcap) and any(s[c] > 0 for s in net.scap))
        self.kmask = [sum(1 << v for v, cap in enumerate(net.vcap) if cap[c] > 0) for c in range(3)]
        sites = sorted(set(net.fnode) | set(net.snode) | set(net.vnode))
        big = 1 << 59
        self.maxd = float(max([net.lb(b)[a] for a in sites for b in sites if net.lb(b)[a] < big] or [1])) or 1.0
        self.noise_amp = cfg["noise"] * self.maxd
        self._dists: dict = {}
        self.oracle = Oracle(inst, self.ss)
        self.relaxed = RelaxedContactCheck(inst, self.ss)
        self.t_oracle_legs = 0
        self.t_oracle_new = 0.0
        self.known_cuts = self.repairs_cut_short = self.certifications = self.cert_skipped = self.emit_errors = 0
        self.dose_cut_residents = 0
        self.history: list = []
        self.it = 0

        # ---- warm start (B1) and its decode
        dsp = self._warm_start(rh, D, hard)
        pool = {(f, c): net.res[f][c] for f in range(net.nF) for c in range(3)}
        room = [list(s) for s in net.scap]
        st = _St([VDec(net, v, ()) for v in range(net.nV)], pool, room)
        warm_trips = 0
        for v, vid in enumerate(net.vid):
            keys = [(((net.fidx[tr.facility], tuple(int(x) for x in tr.counts)),), net.sidx[tr.delivery.shelter])
                    for tr in dsp.vs[vid].trips]
            warm_trips += len(keys)
            self._set_vehicle(st, v, VDec(net, v, net.decode(v, net.vnode[v], net.vstart[v], keys)))
        warm_drops = warm_trips - sum(len(d.outs) for d in st.vd)
        self.warm = st
        warm_planned = self.planned(st)
        Fw = self.F(st)
        slack_w = min((d.slack for d in st.vd if d.outs), default=INF)
        # optimistic bound on the warm start's certified objective (the oracle's slack is < relaxed + 1 s)
        self.inc, self.inc_certified, self.inc_delivered = st, False, None
        self.inc_F = self._F(warm_planned, slack_w + 2 if slack_w != INF else INF, sum(d.vtime for d in st.vd))
        if not any(d.outs for d in st.vd):
            self.inc_certified, self.inc_delivered, self.inc_F = True, 0, Fw
        t_warm = time.monotonic() - t0

        # ---- calibrate the oracle's cost on the warm start's shortest itinerary
        cand = [(d.legs, v) for v, d in enumerate(st.vd) if d.outs]
        if cand:
            _, v = min(cand)
            r = self._check(v, st.vd[v], hard)
            if r is not None and r.first_bad is not None:
                lost = sum(o.count for o in st.vd[v].outs[r.first_bad:])
                self.cut_by_cause[r.cause or "unknown"] += lost
                self.dose_cut_residents += lost
                self.bad_prefix.add((v, st.vd[v].trips[:r.first_bad + 1]))
                st = self._apply_known(st)
        t_cal = time.monotonic() - t0 - t_warm

        self.ad = {"iterations": 0, "accepted": 0, "improvements": 0, "new_best": 0, "stop": "error",
                   "relaxed_best": warm_planned, "T0": None, "weights": {}, "used": {}, "t_search": 0.0,
                   "t_final_cert": 0.0}
        error = None
        try:
            ad = self._alns(st, hard)
        except Exception as exc:  # pragma: no cover - a bug must not cost a timed run: keep the incumbent, report it
            ad, error = self.ad, f"{type(exc).__name__}: {exc}"
        # ---- the plan returned: the certified incumbent (or the warm start if nothing could be certified)
        its = []
        for v, d in enumerate(self.inc.vd):
            if d.outs:
                r = self.cert.get((v, d.trips)) if self.inc_certified else None
                acts = r.actions if r is not None else net.emit(v, d)
                its.append(Itinerary(vehicle=net.vid[v], actions=list(acts)))
        sol = Solution(instance=inst.name, method=self.name, itineraries=its,
                       provenance={"seed": self.seed, "note": "E1 ALNS with the oracle in the loop (SYNTHETIC instances)",
                                   "certified": bool(self.inc_certified)})
        total = time.monotonic() - t0
        diag = {
            "iterations": ad["iterations"], "accepted": ad["accepted"], "improvements": ad["improvements"],
            "new_best": ad["new_best"], "stop": ad["stop"],
            "certified": bool(self.inc_certified), "delivered_certified": self.inc_delivered,
            "warm_planned": warm_planned, "warm_drops": warm_drops, "warm_complete": self.warm_complete,
            "relaxed_best": ad["relaxed_best"],
            "certifications": self.certifications, "certifications_skipped": self.cert_skipped,
            "oracle_calls": self.oracle_checks, "oracle_legs": self.oracle_legs,
            "oracle_s_per_leg": round(self.s_per_leg, 5), "relaxed_blocks": self.relaxed_blocks,
            "emit_errors": self.emit_errors,
            "oracle_cut_residents": self.dose_cut_residents, "oracle_cut_by_cause": dict(sorted(self.cut_by_cause.items())),
            "known_prefix_cuts": self.known_cuts, "repairs_cut_short": self.repairs_cut_short,
            "td_routes": net.td_calls, "static_pairs": net.pair_count,
            "weights": ad["weights"], "used": ad["used"],
            "time_s": {"warm_start": round(t_warm, 3), "calibration": round(t_cal, 3),
                       "search": round(ad["t_search"], 3), "oracle": round(self.t_oracle, 3),
                       "final_certification": round(ad["t_final_cert"], 3), "total": round(total, 3)},
            "incumbents": [list(h) for h in self.history[-12:]],
        }
        if error is not None:
            diag["error"] = error
        info = {"deadlines": {f"{net.fid[f]}/{c}": dl for (f, c), dl in sorted(net.D.items())}, "T0": ad["T0"]}
        return MethodResult(sol, info=info, diagnostics=diag)


__all__ = ["DEFAULTS", "E1ALNS", "TripOut", "VDec"]
