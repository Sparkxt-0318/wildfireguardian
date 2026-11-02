"""E1b: E1's ALNS with incremental certification (the approved second iteration of E1).

Siyeong approved it on 2026-11-02 (``program/DECISIONS.md``, checkpoint 3, items 1 and 2): "incremental
certification. Cache oracle results per vehicle itinerary and re-check only vehicles whose itinerary changed", and
"Final certification stays outside every method's budget. In-loop oracle calls count."
Pre-registration: ``evacplan/experiments/E1b-incremental-cert/README.md`` and ``config.yaml``.

What changes against :mod:`evacplan.methods.e1_alns` (E1), and nothing else
-----------------------------------------------------------------------------
E1 caches the oracle's verdict per vehicle itinerary, keyed by (vehicle, trips), and checks only itineraries it has
not seen. On L its whole budget went into the first in-budget certification of the B1 warm start, whose itineraries
were all new to that cache (33-41 s of 60 s). E1b checks in the loop only itineraries the SEARCH changed:

* An itinerary equal to the warm start's itinerary of the same vehicle (same trips; the decode is a function of the
  vehicle and its trips, so same actions) is never sent to the oracle inside the budget. Wherever E1 would check it
  (its calibration check, the certification of the warm start, a certification of a candidate that kept it) E1b uses
  its RELAXED values instead: residents = its decoded residents, slack = its relaxed slack, no trip cut. Like every
  plan of every method (B2's whole plan, for one), it is then checked by the harness's oracle after the timed solve;
  that final certification is outside the budget (DECISIONS 2026-11-02, item 2).
* Every other itinerary of a candidate (one the search changed) goes through E1's unchanged path: E1's
  RelaxedContactCheck guard, then :meth:`Oracle.check_itinerary`, cached per itinerary, with E1's per-check time guard;
  a trip the oracle does not check (dose) is cut with the rest of the itinerary and the failing prefix is remembered.
* The certification estimate (and so the time E1 keeps free before it starts an iteration) counts only changed
  itineraries that are not in the cache, at E1's measured oracle seconds per leg times ``oracle_safety``.

Everything else is E1's code, inherited unchanged: the pre-registered parameters, operators, acceptance, cooling,
adaptive weights, objective, lazy certification schedule and per-check guards. The oracle is not changed.

Consequences, by construction
-----------------------------
* The incumbent's objective counts changed itineraries with the oracle's numbers and unchanged warm-start ones with
  their relaxed numbers, so candidates and the warm start are compared on the same footing. A candidate replaces the
  incumbent only if that objective is better, and a relaxed count is never below the oracle's count of the same
  itinerary, so the harness's delivered count for E1b's plan is never below B1's (the warm start's) on the same Reach.
* The search does not see an oracle rejection of a warm-start trip unless it changes that itinerary: such residents
  reach the harness and are reported unresolved or model_no_route there, as for B2 (on the SYNTHETIC dev set E1 found
  no such rejection in 50 runs: every warm start passed the oracle).
* Before the first changed itinerary is checked, the oracle's cost per leg is E1's prior ``oracle_s_per_leg0``
  (E1's calibration check was of a warm-start itinerary, which E1b does not check in the loop).
"""
from __future__ import annotations

from .base import MethodResult
from .e1_alns import E1ALNS, VDec, _Cert, _Run


class _WarmCert(_Cert):
    """Relaxed values of an unchanged warm-start itinerary (NOT an oracle verdict; it declares no state)."""

    __slots__ = ()


class _LazyActions:
    """The schema actions of a decoded vehicle plan, emitted on first use (only a returned plan needs them)."""

    __slots__ = ("net", "v", "d", "acts")

    def __init__(self, net, v: int, d: VDec):
        self.net, self.v, self.d, self.acts = net, v, d, None

    def __iter__(self):
        if self.acts is None:
            self.acts = self.net.emit(self.v, self.d)
        return iter(self.acts)


class _RunB(_Run):
    """E1's run with incremental certification: unchanged warm-start itineraries never reach the oracle in the loop."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.warm = None                 # E1's run sets it to the decoded warm start
        self.warm_relaxed = 0            # times an unchanged warm-start itinerary was valued without the oracle

    def is_warm(self, v: int, d: VDec) -> bool:
        """Is ``d`` vehicle v's warm-start itinerary, unchanged (same trips, hence the same decode and actions)?"""
        w = self.warm
        return w is not None and bool(d.outs) and d.trips == w.vd[v].trips

    def _estimate(self, st) -> float:
        """Seconds to certify ``st``: only its changed itineraries not yet checked, with the safety factor."""
        if st is None:
            return 0.0
        legs = sum(d.legs for v, d in enumerate(st.vd)
                   if d.outs and (v, d.trips) not in self.cert and not self.is_warm(v, d))
        return legs * self.s_per_leg * self.cfg["oracle_safety"]

    def _check(self, v: int, d: VDec, hard: float, prefix: bool = False) -> _Cert | None:
        if not self.is_warm(v, d):
            return super()._check(v, d, hard, prefix)       # a changed itinerary: E1's oracle path, cached
        key = (v, d.trips)
        got = self.cert.get(key)
        if got is None:
            got = _WarmCert()
            got.first_bad, got.cause, got.cut_residents = None, None, 0
            got.delivered, got.min_slack, got.legs = d.planned, d.slack, d.legs
            got.actions = _LazyActions(self.net, v, d)
            self.cert[key] = got
            self.warm_relaxed += 1
        return got

    def run(self) -> MethodResult:
        res = super().run()
        inc, net = self.inc, self.net
        kept = [v for v, d in enumerate(inc.vd) if d.outs and self.is_warm(v, d)]
        changed = [v for v, d in enumerate(inc.vd) if d.outs and not self.is_warm(v, d)]
        if not self.inc_certified:                           # only the warm start can be an uncertified incumbent
            kept, changed = kept + changed, []
        checked = sum(self.cert[(v, inc.vd[v].trips)].delivered or 0 for v in changed)
        unchecked = sum(inc.vd[v].planned for v in kept)
        all_checked = bool(self.inc_certified) and not kept
        diag = res.diagnostics
        diag["certified"] = all_checked                     # every returned itinerary checked by the oracle in the loop
        diag["delivered_certified"] = self.inc_delivered if all_checked else None
        diag["incremental"] = {
            "changed_vehicles": len(changed),               # returned itineraries the search changed (oracle-checked)
            "unchanged_warm_vehicles": len(kept),           # returned warm-start itineraries (checked by the harness)
            "delivered_checked_in_loop": checked,
            "planned_unchecked_warm": unchecked,
            "incumbent_value_residents": checked + unchecked,
            "warm_valued_relaxed": self.warm_relaxed,
        }
        res.solution = res.solution.model_copy(update={"provenance": {
            "seed": self.seed,
            "note": "E1b: E1 ALNS with incremental certification (SYNTHETIC instances)",
            "certified": all_checked,
            "checked_in_loop": [net.vid[v] for v in changed],
            "unchanged_warm_start": [net.vid[v] for v in kept],
        }})
        return res


class E1bALNS(E1ALNS):
    """E1 with incremental certification: the same pre-registered parameters (E1's ``DEFAULTS``)."""

    name = "e1b_alns"

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        return _RunB(self.cfg, self.name, instance, scenario_set, float(budget_s), int(seed), float(deadline)).run()


__all__ = ["E1bALNS"]
