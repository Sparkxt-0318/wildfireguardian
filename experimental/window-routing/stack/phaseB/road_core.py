"""Bounded exact lattice search with per-member additive exposure labels.

All claims concern the supplied edge-grid forecast and discrete model only.
Search caps fail closed; the separately implemented checker gates every route.

road_core (Phase B, road-dose alignment): a copy of the candidate core
(routing-package/routing/core.py sha256 8a54c615...) with ONE injected change.
An ``exposure`` object supplies the per-member dose (exact Fraction, kJ/m^2)
and peak (kW/m^2) of every EDGE / PARTIAL / WAIT / DWELL occupancy and of the
issue point, in one declared ``mode``:
  'centre' (exposure None): the original cell-centre packet values, unchanged;
  'lo'   : outward lower road bounds  (a relaxation of the whole-road model);
  'hi'   : outward upper road bounds  (conservative);
  'zero' : dose and peak relaxed to 0 (contact-only relaxation).
Flame contact and support keep exactly the hazard's cell semantics (the
unchanged code path); labels, Pareto dominance on per-member dose vectors,
budget pruning, the opening-aware bound, waits, turn rules, destination
admission and dwell are unchanged. In a non-centre mode the in-search
check_route is replaced by a separately coded mode-consistent route
re-integration (check_route_mode). Each mode is its own RCSP; one search never
mixes modes. In 'lo'/'zero' a flame sample at a non-binary64 occupancy endpoint
inside an extinction-rounding gap withdraws the global (optimality/refusal)
claim of that search (see MATH_PROOF.md, obligation 7).
"""

import bisect
import heapq
import math
import resource
import sys
import time
from fractions import Fraction


def node_cell(graph, node):
    g = graph["grid"]
    col = math.floor(
        (Fraction(node["x"]) - Fraction(g["x0"])) / Fraction(g["resolution"])
    )
    row = math.floor(
        (Fraction(node["y"]) - Fraction(g["y0"])) / Fraction(g["resolution"])
    )
    return row * g["width"] + col


def edge_occupancies(
    edge, start, end, from_fraction=0, to_fraction=1, graph=None, node_lookup=None
):
    """Exact rational chord/grid intersections, including every point contact.

    JSON segment fractions are canonical floating encodings for admission only;
    geometry is recomputed from represented coordinates to avoid cut rounding.
    """
    if graph is None:
        raise ValueError("graph required for exact geometry occupancy")
    ns = node_lookup or {n["id"]: n for n in graph["nodes"]}
    u, v = ns[edge["u"]], ns[edge["v"]]
    g = graph["grid"]
    f, q = Fraction(from_fraction), Fraction(to_fraction)
    cuts = {f, q}
    for axis, base, count in [("x", "x0", "width"), ("y", "y0", "height")]:
        a, b = Fraction(u[axis]), Fraction(v[axis])
        origin = Fraction(g[base])
        res = Fraction(g["resolution"])
        if a != b:
            for line in range(1, g[count]):
                c = (origin + line * res - a) / (b - a)
                if f < c < q:
                    cuts.add(c)
    cuts = sorted(cuts)

    def point(z):
        return {
            "x": Fraction(u["x"]) + z * (Fraction(v["x"]) - Fraction(u["x"])),
            "y": Fraction(u["y"]) + z * (Fraction(v["y"]) - Fraction(u["y"])),
        }

    def when(z):
        return (
            Fraction(start)
            if q == f
            else Fraction(start) + (Fraction(end) - Fraction(start)) * (z - f) / (q - f)
        )

    out = []
    for a, b in zip(cuts, cuts[1:]):
        out.append(
            {
                "cell": node_cell(graph, point((a + b) / 2)),
                "start": when(a),
                "end": when(b),
            }
        )
    for z in cuts:
        out.append(
            {"cell": node_cell(graph, point(z)), "start": when(z), "end": when(z)}
        )
    return out


def evaluate_occupancy(graph, hazard, occupancies):
    """Internal independent-of-search integration, not the delivery checker."""
    codes = set()
    per_member = {}
    for member in hazard["members"]:
        bp = member["breakpoints"]
        dose_exact, peak = Fraction(0), 0.0
        for occ in occupancies:
            cell, lo, hi = occ["cell"], occ["start"], occ["end"]
            if lo < bp[0] or hi > bp[-1] or hi < lo:
                codes.add("UNSUPPORTED")
                continue
            points = [lo, hi] + [p for p in bp[1:-1] if lo < p < hi]
            for p in points:
                i = min(len(bp) - 2, bisect.bisect_right(bp, p) - 1)
                if not member["support"][i][cell]:
                    codes.add("UNSUPPORTED")
                if member["flame"][i][cell]:
                    codes.add("FLAME_CONTACT")
                peak = max(peak, member["flux"][i][cell])
            first = max(0, bisect.bisect_right(bp, lo) - 1)
            for i in range(first, len(bp) - 1):
                a, b = max(lo, bp[i]), min(hi, bp[i + 1])
                if b > a:
                    dose_exact += (Fraction(b) - Fraction(a)) * Fraction(
                        member["flux"][i][cell]
                    )
                if bp[i + 1] >= hi:
                    break
        try:
            reported_dose = float(dose_exact)
        except OverflowError:
            reported_dose = None
        per_member[member["id"]] = {
            "dose": reported_dose,
            "dose_exact": dose_exact,
            "peak": peak,
        }
    return {"ok": not codes, "codes": sorted(codes), "per_member": per_member}


def member_ids_of(hazard):
    return [m["id"] for m in hazard["members"]]


def _bin_index(bp, p):
    # Identical to the sampling index used by evaluate_occupancy.
    return min(len(bp) - 2, bisect.bisect_right(bp, p) - 1)


class _ExactReuse:
    """CANDIDATE N: reuse of immutable geometry and unchanged exact work.

    For an occupancy whose whole time span [t, t+D] lies in one hazard bin
    (same sampling index at both ends, inside [bp0, bpN]) evaluate_occupancy
    reads exactly one bin per member; its codes/peaks are time-independent and
    its exact dose is sum_k D*(z_{k+1}-z_k)*Fraction(flux). Results are
    therefore cached per (geometry, D, bin). Otherwise the unchanged original
    evaluate_occupancy is called. Outputs are value-identical by construction
    and by differential test.
    """

    def __init__(self, graph, hazard, nodes):
        self.graph, self.hazard, self.nodes = graph, hazard, nodes
        self.members = hazard["members"]
        self.geometry, self.results = {}, {}
        self.flux_frac = {}
        self.stats = {"fast": 0, "fallback": 0, "geometry_built": 0, "result_built": 0}

    def edge_geometry(self, edge):
        g = self.geometry.get(edge["id"])
        if g is None:
            # Unchanged original geometry evaluated once on the unit clock:
            # with start=0,end=1,f=0,q=1 every returned time equals z exactly.
            occ = edge_occupancies(edge, 0, 1, 0, 1, self.graph, self.nodes)
            pieces = [(o["cell"], o["start"], o["end"]) for o in occ if o["start"] != o["end"]]
            points = [o["cell"] for o in occ if o["start"] == o["end"]]
            pieces_all = [(o["cell"], o["start"], o["end"]) for o in occ]
            g = (pieces, points, pieces_all)
            self.geometry[edge["id"]] = g
            self.stats["geometry_built"] += 1
        return g

    def _single_bin(self, t, D):
        bps = [m["breakpoints"] for m in self.members]
        out = []
        for bp in bps:
            lo, hi = t, t + D
            if lo < bp[0] or hi > bp[-1]:
                return None
            i0, i1 = _bin_index(bp, lo), _bin_index(bp, hi)
            if i0 != i1:
                return None
            out.append(i0)
        return tuple(out)

    def _frac(self, value):
        f = self.flux_frac.get(value)
        if f is None:
            f = self.flux_frac[value] = Fraction(value)
        return f

    def evaluate(self, kind, ident, pieces, points, t, D):
        bins = self._single_bin(t, D)
        if bins is None:
            return None
        key = (kind, ident, D, bins)
        r = self.results.get(key)
        if r is not None:
            self.stats["fast"] += 1
            return r
        codes = set()
        per_member = {}
        Dq = Fraction(D)
        for member, i in zip(self.members, bins):
            sup, fl, fx = member["support"][i], member["flame"][i], member["flux"][i]
            dose_exact, peak = Fraction(0), 0.0
            for cell, za, zb in pieces:
                # two samples (lo, hi) per piece in the original, same cell
                for _ in (0, 1):
                    if not sup[cell]:
                        codes.add("UNSUPPORTED")
                    if fl[cell]:
                        codes.add("FLAME_CONTACT")
                    peak = max(peak, fx[cell])
                dose_exact += (Dq * Fraction(zb) - Dq * Fraction(za)) * self._frac(fx[cell])
            for cell in points:
                for _ in (0, 1):
                    if not sup[cell]:
                        codes.add("UNSUPPORTED")
                    if fl[cell]:
                        codes.add("FLAME_CONTACT")
                    peak = max(peak, fx[cell])
            try:
                reported_dose = float(dose_exact)
            except OverflowError:
                reported_dose = None
            per_member[member["id"]] = {"dose": reported_dose, "dose_exact": dose_exact, "peak": peak}
        r = {"ok": not codes, "codes": sorted(codes), "per_member": per_member}
        self.results[key] = r
        self.stats["result_built"] += 1
        return r


def check_route(graph, hazard, request, legs, destination):
    """Every public check delegates to the independently authored checker."""
    from routing.independent import check_route as independent_check

    return independent_check(graph, hazard, request, legs, destination)


def check_route_mode(graph, hazard, request, legs, destination, exposure):
    """Mode-consistent route re-integration (separate summation path).

    Structure, flame contact and support: the independent checker's own
    hazard-cell sampling (dose disabled). Dose and peak: the exposure model's
    plain per-sub-box summation (ExposureView.*_plain), never the search's
    fast-path sums or cost cache. Exact rationals make the totals independent
    of summation order, so a correct search and this path agree exactly.
    """
    from routing import independent as ind

    member_ids = [m["id"] for m in hazard["members"]]
    totals = {m: Fraction(request["incurred"][m]) for m in member_ids}
    peaks = {m: 0.0 for m in member_ids}
    stats = {m: {"dose": Fraction(0), "peak": 0.0} for m in member_ids}
    codes = set()

    def add(values):
        for m, (d, p) in zip(member_ids, values):
            totals[m] += d
            peaks[m] = max(peaks[m], p)

    try:
        nodes, edges, arrival, finish = ind._shape(graph, hazard, request, legs, destination)
        pos = request["position"]
        ind._charge(ind._position_spans(graph, pos, request["departure"], nodes, edges), hazard, stats, False, codes)
        if "node" in pos:
            add(exposure.node_plain(pos["node"], request["departure"], request["departure"]))
        else:
            add(exposure.partial(pos["edge"], request["departure"], request["departure"], pos["fraction"], pos["fraction"]))
        issue_failure = bool(codes & {"FLAME_CONTACT"}) or any(
            peaks[m] > request["budgets"]["peak"] or totals[m] > Fraction(request["budgets"]["dose"][m])
            for m in member_ids)
        for leg in legs:
            ind._charge(ind._occupancy(graph, leg, nodes, edges), hazard, stats, False, codes)
            if leg["kind"] == "WAIT":
                add(exposure.node_plain(leg["node"], leg["start"], leg["end"]))
            elif Fraction(leg["from_fraction"]) == 0 and Fraction(leg["to_fraction"]) == 1:
                add(exposure.edge_plain(leg["edge"], leg["start"], leg["end"]))
            else:
                add(exposure.partial(leg["edge"], leg["start"], leg["end"], leg["from_fraction"], leg["to_fraction"]))
        ind._charge([(ind._cell(graph, nodes[destination]), arrival, finish)], hazard, stats, False, codes)
        dwell = exposure.node_plain(destination, arrival, finish)
        if request["exposure_scope"] == "including_dwell":
            add(dwell)
        else:
            add([(Fraction(0), p) for _, p in dwell])
        if any(peaks[m] > request["budgets"]["peak"] for m in member_ids):
            codes.add("PEAK_BUDGET")
        if any(totals[m] > Fraction(request["budgets"]["dose"][m]) for m in member_ids):
            codes.add("DOSE_BUDGET")
        status = ("AT_ISSUE_FAILURE" if issue_failure else
                  ("UNSUPPORTED" if "MISSING_SUPPORT" in codes else ("CHECKED_ROUTE" if not codes else "REJECTED_ROUTE")))
        out_arrival = arrival
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
        codes.add("ROUTE_STRUCTURE")
        status, out_arrival = "INVALID_ROUTE", None
    per_member = {}
    for m in member_ids:
        try:
            shown = float(totals[m])
        except OverflowError:
            shown = None
        per_member[m] = {"dose": shown, "dose_exact": str(totals[m]), "peak": peaks[m]}
    return {"ok": not codes, "status": status, "codes": sorted(codes), "per_member": per_member,
            "arrival": out_arrival, "exposure_mode": exposure.mode,
            "path": "independent structure/contact sampling + plain per-sub-box exposure summation"}


def _globally_supported(hazard, request):
    # Deliberately conservative: unsupported cells outside this route withhold
    # a global optimality/infeasibility claim, even if no search label used them.
    # REPAIR (coverage gap): admission tolerates |bp - validity| <= 1e-9, but
    # occupancy outside a member's own breakpoints is UNSUPPORTED. Global claims
    # therefore also require every member's exact breakpoint coverage.
    return (
        hazard["valid_from"] <= request["departure"] <= request["horizon"] <= hazard["valid_until"]
        and all(m["breakpoints"][0] <= request["departure"] and request["horizon"] <= m["breakpoints"][-1] for m in hazard["members"])
        and all(all(row) for m in hazard["members"] for row in m["support"])
    )


def _lower_bounds(graph, destinations, dt):
    reverse = {n["id"]: [] for n in graph["nodes"]}
    for e in graph["edges"]:
        reverse[e["v"]].append((e["u"], e["travel_ticks"] * dt))
    distance = {v: math.inf for v in reverse}
    heap = []
    for d in destinations:
        distance[d["node"]] = 0
        heapq.heappush(heap, (0, d["node"]))
    while heap:
        cost, node = heapq.heappop(heap)
        if cost != distance[node]:
            continue
        for u, length in reverse[node]:
            candidate = cost + length
            if candidate < distance[u]:
                distance[u] = candidate
                heapq.heappush(heap, (candidate, u))
    return distance


def solve(graph, hazard, request, *, prepared=None, exposure=None, mode="centre", arrival_bound=None):
    """Exact vector search; optional explicit prepared graph admission reuse.

    Pass a PreparedGraph as graph, or a raw graph with prepared= to require
    exact contents equality. Forecast/request admission and checker still run.
    """
    from routing import validation
    from routing.prepared import PreparedGraph

    if mode not in ("centre", "lo", "hi", "zero"):
        raise ValueError("mode must be centre, lo, hi or zero")
    if mode != "centre" and (exposure is None or getattr(exposure, "mode", None) != mode):
        raise ValueError("a non-centre mode requires an exposure view of that same mode")
    exposure_active = exposure is not None
    gap_hits = []  # extinction-rounding gap samples (lo/zero): withdraw global claims

    start_clock = time.perf_counter()
    reuse_holder = []  # per-solve only (review finding: no cross-solve retention)
    metrics = {
        "labels": 0,
        "expansions": 0,
        "dominated": 0,
        "peak_frontier": 0,
        "edge_candidates": 0,
        "wait_candidates": 0,
        "occupancy_evaluations": 0,
    }
    solver = (
        request.get("solver", "baseline") if isinstance(request, dict) else "baseline"
    )

    def finish(status, reason, **extra):
        metrics["wall_s"] = time.perf_counter() - start_clock
        if reuse_holder:
            metrics["reuse"] = dict(reuse_holder[-1].stats)
        result = {
            "status": status,
            "reason": reason,
            "legs": [],
            "arrival": None,
            "destination": None,
            "per_member": {},
            "solver_status": status,
            "metrics": dict(metrics),
            "hazard_version": (
                hazard.get("version") if isinstance(hazard, dict) else None
            ),
            "provenance": {
                "solver": solver,
                "evidence_class": (
                    hazard.get("evidence_class") if isinstance(hazard, dict) else None
                ),
                "model": "EXACT_LATTICE_EDGEGRID",
                "physical_safety_claim": False,
            },
            "certificate_conditions": [],
        }
        result.update(extra)
        result["exposure_mode"] = mode
        result["provenance"]["exposure_mode"] = mode
        if exposure_active and hasattr(exposure, "stats"):
            result["exposure_stats"] = exposure.stats()
        if gap_hits:
            result["extinction_gap_hits"] = len(gap_hits)
            if result["status"] in ("CONDITIONAL_OPTIMUM", "PROVEN_INFEASIBLE"):
                result["mode_raw_status"] = result["status"]
                result["status"] = "CHECKED_ROUTE" if result["status"] == "CONDITIONAL_OPTIMUM" else "UNSUPPORTED"
                result["reason"] = "EXTINCTION_GAP_SAMPLE_NO_GLOBAL_CLAIM"
                result["solver_status"] = "ADMISSIBLE_ONLY" if result["status"] == "CHECKED_ROUTE" else "SUPPORT_INCOMPLETE"
        return result

    try:
        if prepared is not None:
            if type(prepared) is not PreparedGraph:
                raise validation.ValidationError(
                    "PREPARED_GRAPH_TYPE", "prepared must be a PreparedGraph"
                )
            if not prepared.matches(graph):
                raise validation.ValidationError(
                    "PREPARED_GRAPH_MISMATCH",
                    "graph contents changed; prepare the replacement explicitly",
                )
            graph = prepared.snapshot()
        elif type(graph) is PreparedGraph:
            graph = graph.snapshot()
        else:
            graph = validation.validate_graph(graph)
        hazard = validation.validate_hazard(
            graph, hazard, as_of=request.get("as_of"), _graph_validated=True
        )
        request = validation.validate_request(
            graph, hazard, request, _validated_inputs=True
        )
    except validation.ValidationError as exc:
        return finish(
            (
                "UNSUPPORTED"
                if "UNSUPPORTED" in exc.code or "IDENTIT" in exc.code
                else "INVALID_INPUT"
            ),
            exc.code,
            message=str(exc),
        )
    except (AttributeError, TypeError, KeyError) as exc:
        return finish("INVALID_INPUT", "REQUEST_SHAPE", message=str(exc))
    if solver == "activation":
        return finish("UNSUPPORTED", "ACTIVATION_NOT_PROMOTED")
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    outgoing = {n: [] for n in nodes}
    for e in graph["edges"]:
        outgoing[e["u"]].append(e)
    forbidden = set(tuple(t) for t in graph["forbidden_turns"])
    dt, departure, horizon = hazard["dt"], request["departure"], request["horizon"]
    member_ids = [m["id"] for m in hazard["members"]]
    # Exact arithmetic over the represented JSON numeric inputs. A positive
    # dose must never disappear when added to a large already-incurred dose.
    budgets = tuple(Fraction(request["budgets"]["dose"][m]) for m in member_ids)
    incurred = tuple(Fraction(request["incurred"][m]) for m in member_ids)
    peak_budget = request["budgets"]["peak"]
    limits = request["limits"]
    complete = _globally_supported(hazard, request)
    position, incoming = request["position"], request["incoming_edge"]
    partial = None
    if "node" in position:
        origin = position["node"]
        issue = [
            {
                "cell": node_cell(graph, nodes[origin]),
                "start": departure,
                "end": departure,
            }
        ]
    else:
        partial = edges[position["edge"]]
        origin = partial["v"]
        issue = edge_occupancies(
            partial,
            departure,
            departure,
            position["fraction"],
            position["fraction"],
            graph,
            nodes,
        )
    metrics["occupancy_evaluations"] += 1
    issue_check = evaluate_occupancy(graph, hazard, issue)
    if exposure_active:
        issue_values = (
            exposure.node(origin, departure, departure)
            if partial is None
            else exposure.partial(partial["id"], departure, departure, position["fraction"], position["fraction"])
        )
        for mid, (d, p) in zip(member_ids_of(hazard), issue_values):
            issue_check["per_member"][mid] = {"dose": float(d), "dose_exact": d, "peak": p}
        if mode in ("lo", "zero") and "FLAME_CONTACT" in issue_check["codes"] and exposure.gap_probe(issue):
            # router-only flame at the issue point (possible only at the clamped horizon bin): no AT_ISSUE claim
            gap_hits.append(("ISSUE", True))
            return finish("UNSUPPORTED", "EXTINCTION_GAP_SAMPLE_AT_ISSUE")
    if "UNSUPPORTED" in issue_check["codes"]:
        return finish("UNSUPPORTED", "AT_ISSUE_MISSING_SUPPORT")
    if (
        issue_check["codes"]
        or any(v > b for v, b in zip(incurred, budgets))
        or any(v["peak"] > peak_budget for v in issue_check["per_member"].values())
    ):
        for mid, spent in zip(member_ids, incurred):
            issue_check["per_member"][mid]["dose"] = request["incurred"][mid]
            issue_check["per_member"][mid].pop("dose_exact", None)
        return finish(
            "AT_ISSUE_FAILURE",
            "AT_ISSUE_CONSTRAINT_VIOLATION",
            per_member=issue_check["per_member"],
        )
    # Static turn-aware disconnect is independent of the forecast/support mask.
    if time.perf_counter() - start_clock >= limits["wall_s"]:
        return finish("TIMEOUT", "WALL_CLOCK", solver_status="INCOMPLETE_CAP")
    structural_seeds = [(origin, incoming)]
    if (
        partial is not None
        and graph.get("mid_edge_reversal")
        and 0 < position["fraction"] < 1
        and Fraction(1 - position["fraction"])
        == Fraction(1) - Fraction(position["fraction"])
        and partial.get("reverse_edge") in edges
        and (incoming, partial["reverse_edge"]) not in forbidden
    ):
        rev = edges[partial["reverse_edge"]]
        structural_seeds.append((rev["v"], rev["id"]))
    reachable, pending = set(structural_seeds), list(structural_seeds)
    destination_nodes = {d["node"] for d in request["destinations"]}
    while pending:
        if (
            len(reachable) % 64 == 0
            and time.perf_counter() - start_clock >= limits["wall_s"]
        ):
            return finish(
                "TIMEOUT", "WALL_CLOCK_PREPROCESS", solver_status="INCOMPLETE_CAP"
            )
        n, inc = pending.pop()
        for e in outgoing[n]:
            next_state = (e["v"], e["id"])
            if (inc, e["id"]) not in forbidden and next_state not in reachable:
                reachable.add(next_state)
                pending.append(next_state)
    if not any(n in destination_nodes for n, _ in reachable):
        if time.perf_counter() - start_clock >= limits["wall_s"]:
            return finish(
                "TIMEOUT", "WALL_CLOCK_PREPROCESS", solver_status="INCOMPLETE_CAP"
            )
        return finish(
            "DISCONNECTED",
            "TURN_GRAPH_DISCONNECTED",
            solver_status="STRUCTURAL_DISCONNECT",
            certificate_conditions=[
                "declared directed graph and turn rules",
                "independent of forecast",
                "no physical safety claim",
            ],
        )
    distance = (
        _lower_bounds(graph, request["destinations"], dt)
        if solver == "astar"
        else {n: 0 for n in nodes}
    )
    # CANDIDATE O: destination-opening-aware admissible bound (astar_opening).
    # For a label (node, t) every accepted arrival tau satisfies
    # tau >= t + h_d(node) (static turn-unaware travel relaxation per
    # destination d), a <= tau and tau + dwell <= min(b, horizon) for some
    # open interval [a, b] of d. key_bound returns the least such tau, or inf
    # when no destination window can be met, in which case the label cannot
    # lead to any accepted arrival and is not stored. Ties prefer larger t.
    opening_aware = solver == "astar_opening"
    if opening_aware:
        metrics["opening_pruned"] = 0
        per_destination = {}
        for d in request["destinations"]:
            if d["node"] not in per_destination:
                per_destination[d["node"]] = _lower_bounds(graph, [d], dt)
        windows = [
            (per_destination[d["node"]], d["dwell"], sorted((a, b) for a, b in d["open_intervals"]))
            for d in request["destinations"]
        ]

        def key_bound(node, t):
            best = math.inf
            for dist, dwell, intervals in windows:
                lb = t + dist[node]
                if lb == math.inf:
                    continue
                for a, b in intervals:
                    tau = lb if lb >= a else a
                    if tau + dwell <= b and tau + dwell <= horizon:
                        if tau < best:
                            best = tau
                        break
            return best
    cost_cache = {}
    reuse = _ExactReuse(graph, hazard, nodes)
    reuse_holder.append(reuse)

    def cost(key, occupancy, fast=None, expo=None):
        if key not in cost_cache:
            metrics["occupancy_evaluations"] += 1
            c = fast() if fast is not None else None
            if c is None:
                reuse.stats["fallback"] += 1
                c = evaluate_occupancy(graph, hazard, occupancy())
            c = dict(c)
            if exposure_active:
                # THE injected change: dose/peak from the declared exposure mode;
                # flame contact and support codes above are untouched.
                values = expo()
                pm = {}
                for mid, (d, p) in zip(member_ids, values):
                    try:
                        shown = float(d)
                    except OverflowError:
                        shown = None
                    pm[mid] = {"dose": shown, "dose_exact": d, "peak": p}
                c["per_member"] = pm
                if mode in ("lo", "zero") and "FLAME_CONTACT" in c["codes"]:
                    hit = exposure.gap_probe(occupancy())
                    if hit:
                        gap_hits.append((key, hit))
            c["admissible"] = c["ok"] and all(
                v["peak"] <= peak_budget for v in c["per_member"].values()
            )
            cost_cache[key] = c
        return cost_cache[key]

    # Record: node, incoming edge, absolute time, admission flag, dose, parent, leg.
    # Admission is part of the dominance key: a WAIT is never a fresh admission.
    records, front, heap = [], {}, []
    cap = None

    def add(node, edge, t, admission, dose, parent, leg):
        nonlocal cap
        if any(v > b for v, b in zip(dose, budgets)):
            return
        if opening_aware:
            bound = key_bound(node, t)
            if arrival_bound is not None and bound != math.inf:
                # Optional admissible tightening (Phase B deviation D2): contact-only earliest arrival from this
                # exact label state; max of two lower bounds is a lower bound; +inf proves no admissible completion.
                eb = arrival_bound.bound(node, edge, t, admission)
                if eb > bound:
                    metrics["arrival_bound_raised"] = metrics.get("arrival_bound_raised", 0) + 1
                    bound = eb
            if bound == math.inf:
                metrics["opening_pruned"] += 1
                return
        key = (node, edge, t, admission)
        old = front.get(key, [])
        if any(all(a <= b for a, b in zip(records[j][4], dose)) for j in old):
            metrics["dominated"] += 1
            return
        keep = [j for j in old if not all(a <= b for a, b in zip(dose, records[j][4]))]
        if len(keep) >= limits["frontier_width"]:
            cap = "FRONTIER_WIDTH"
            return
        if len(records) >= limits["max_labels"]:
            cap = "MAX_LABELS"
            return
        idx = len(records)
        records.append((node, edge, t, admission, dose, parent, leg))
        front[key] = keep + [idx]
        if opening_aware:
            heapq.heappush(heap, (bound, -t, idx))
        else:
            heapq.heappush(heap, (t + distance[node], t, idx))
        metrics["labels"] = len(records)
        metrics["peak_frontier"] = max(metrics["peak_frontier"], len(keep) + 1)

    if partial is not None and position["fraction"] < 1:
        choices = [(partial, position["fraction"])]
        if (
            graph.get("mid_edge_reversal")
            and 0 < position["fraction"] < 1
            and Fraction(1 - position["fraction"])
            == Fraction(1) - Fraction(position["fraction"])
            and partial.get("reverse_edge") in edges
            and (incoming, partial["reverse_edge"]) not in forbidden
        ):
            choices.append((edges[partial["reverse_edge"]], 1 - position["fraction"]))
        for first_edge, fraction in choices:
            # Literal IEEE float multiplication + ceil is the declared residual
            # computational rule; no tolerance silently shortens traversal.
            end = (
                departure
                + math.ceil(
                    (Fraction(1) - Fraction(fraction)) * first_edge["travel_ticks"]
                )
                * dt
            )
            if end > horizon:
                continue
            leg = {
                "kind": "EDGE",
                "edge": first_edge["id"],
                "start": departure,
                "end": end,
                "from_fraction": fraction,
                "to_fraction": 1,
            }
            c = cost(
                ("PARTIAL", first_edge["id"], departure, fraction),
                lambda: edge_occupancies(first_edge, departure, end, fraction, 1, graph, nodes),
                expo=lambda: exposure.partial(first_edge["id"], departure, end, fraction, 1),
            )
            if c["admissible"]:
                initial_dose = tuple(
                    a + c["per_member"][m]["dose_exact"]
                    for a, m in zip(incurred, member_ids)
                )
                add(first_edge["v"], first_edge["id"], end, True, initial_dose, -1, leg)
    else:
        add(origin, incoming, departure, True, incurred, -1, None)

    def route_legs(idx):
        legs = []
        while idx >= 0:
            rec = records[idx]
            if rec[6] is not None:
                legs.append(rec[6])
            idx = rec[5]
        return list(reversed(legs))

    destinations = {}
    for d in request["destinations"]:
        destinations.setdefault(d["node"], []).append(d)
    while heap:
        if cap:
            return finish("TIMEOUT", cap, solver_status="INCOMPLETE_CAP")
        if time.perf_counter() - start_clock >= limits["wall_s"]:
            return finish("TIMEOUT", "WALL_CLOCK", solver_status="INCOMPLETE_CAP")
        if metrics["expansions"] % 64 == 0:
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
                1048576 if sys.platform == "darwin" else 1024
            )
            metrics["peak_rss_mb"] = rss
            if rss > limits.get("rss_limit_mb", 3072):
                return finish("TIMEOUT", "RSS_LIMIT", solver_status="INCOMPLETE_CAP")
        _, _, idx = heapq.heappop(heap)
        node, incoming, t, admission, dose, parent, previous_leg = records[idx]
        if idx not in front.get((node, incoming, t, admission), []):
            continue
        if admission:
            for d in destinations.get(node, []):
                end = t + d["dwell"]
                if end > horizon or not any(
                    a <= t and end <= b for a, b in d["open_intervals"]
                ):
                    continue
                c = cost(
                    ("DWELL", node, t, end),
                    lambda: [{"cell": node_cell(graph, nodes[node]), "start": t, "end": end}],
                    lambda: reuse.evaluate("NODE", node, [(node_cell(graph, nodes[node]), 0, 1)], [], t, end - t),
                    expo=lambda: exposure.node(node, t, end),
                )
                if not c["admissible"]:
                    continue
                final_dose = (
                    tuple(
                        v + c["per_member"][m]["dose_exact"]
                        for v, m in zip(dose, member_ids)
                    )
                    if request["exposure_scope"] == "including_dwell"
                    else dose
                )
                if any(v > b for v, b in zip(final_dose, budgets)):
                    continue
                legs = route_legs(idx)
                checked = (
                    check_route_mode(graph, hazard, request, legs, node, exposure)
                    if exposure_active
                    else check_route(graph, hazard, request, legs, node)
                )
                if not checked["ok"]:
                    return finish(
                        "UNSUPPORTED",
                        "INDEPENDENT_CHECK_DISAGREEMENT",
                        checker=checked,
                        solver_status="CHECK_FAILURE",
                    )
                if time.perf_counter() - start_clock >= limits["wall_s"]:
                    return finish(
                        "TIMEOUT",
                        "WALL_CLOCK_AFTER_CHECK",
                        solver_status="INCOMPLETE_CAP",
                        checked_incumbent={
                            "status": "CHECKED_ROUTE",
                            "legs": legs,
                            "arrival": t,
                            "destination": node,
                            "per_member": checked["per_member"],
                            "checker": checked,
                            "hazard_version": hazard["version"],
                            "proof_level": "independently checked supplied-scenario witness; optimum unresolved under cap",
                            "physical_safety_claim": False,
                        },
                    )
                return finish(
                    "CONDITIONAL_OPTIMUM" if complete else "CHECKED_ROUTE",
                    "EXACT_SEARCH_CHECKED" if complete else "PARTIAL_GLOBAL_SUPPORT",
                    legs=legs,
                    arrival=t,
                    destination=node,
                    per_member=checked["per_member"],
                    checker=checked,
                    solver_status="EXACT_OPTIMUM" if complete else "ADMISSIBLE_ONLY",
                    certificate_conditions=(
                        [
                            "supplied ensemble only",
                            "declared lattice and geometry",
                            "complete search before caps",
                            "independent route check",
                            "no physical safety claim",
                        ]
                        if complete
                        else ["independent route check", "no global optimality claim"]
                    ),
                )
        if metrics["expansions"] >= limits["max_expansions"]:
            return finish("TIMEOUT", "MAX_EXPANSIONS", solver_status="INCOMPLETE_CAP")
        metrics["expansions"] += 1
        if t >= horizon:
            continue
        for e in outgoing[node]:
            if (incoming, e["id"]) in forbidden:
                continue
            end = t + e["travel_ticks"] * dt
            if end > horizon:
                continue
            metrics["edge_candidates"] += 1
            c = cost(
                ("EDGE", e["id"], t),
                lambda: edge_occupancies(e, t, end, graph=graph, node_lookup=nodes),
                lambda: reuse.evaluate("EDGE", e["id"], *reuse.edge_geometry(e)[:2], t, end - t),
                expo=lambda: exposure.edge(e["id"], t, end),
            )
            if c["admissible"]:
                ndose = tuple(
                    v + c["per_member"][m]["dose_exact"]
                    for v, m in zip(dose, member_ids)
                )
                add(
                    e["v"],
                    e["id"],
                    end,
                    True,
                    ndose,
                    idx,
                    {
                        "kind": "EDGE",
                        "edge": e["id"],
                        "start": t,
                        "end": end,
                        "from_fraction": 0,
                        "to_fraction": 1,
                    },
                )
                if cap:
                    break
        if cap:
            continue
        if nodes[node]["waitable"] and t + dt <= horizon:
            metrics["wait_candidates"] += 1
            c = cost(
                ("WAIT", node, t),
                lambda: [{"cell": node_cell(graph, nodes[node]), "start": t, "end": t + dt}],
                lambda: reuse.evaluate("NODE", node, [(node_cell(graph, nodes[node]), 0, 1)], [], t, dt),
                expo=lambda: exposure.node(node, t, t + dt),
            )
            if c["admissible"]:
                ndose = tuple(
                    v + c["per_member"][m]["dose_exact"]
                    for v, m in zip(dose, member_ids)
                )
                add(
                    node,
                    incoming,
                    t + dt,
                    False,
                    ndose,
                    idx,
                    {"kind": "WAIT", "node": node, "start": t, "end": t + dt},
                )
    if cap:
        return finish("TIMEOUT", cap, solver_status="INCOMPLETE_CAP")
    return finish(
        "PROVEN_INFEASIBLE" if complete else "UNSUPPORTED",
        "EXACT_FRONTIER_EXHAUSTED" if complete else "MISSING_GLOBAL_SUPPORT",
        solver_status="EXHAUSTED" if complete else "SUPPORT_INCOMPLETE",
        certificate_conditions=(
            [
                "complete supported lattice search",
                "supplied ensemble only",
                "no physical safety claim",
            ]
            if complete
            else []
        ),
    )


class CentreExposure:
    """Cell-centre packet values supplied THROUGH the exposure injection (mode 'centre'). Used by the differential test:
    road_core.solve(..., exposure=CentreExposure(graph, hazard), mode='centre') must reproduce core.solve exactly."""

    mode = "centre"

    def __init__(self, graph, hazard):
        self.graph, self.hazard = graph, hazard
        self.nodes = {n["id"]: n for n in graph["nodes"]}
        self.edges = {e["id"]: e for e in graph["edges"]}
        self.ids = [m["id"] for m in hazard["members"]]
        self.calls = 0

    def _values(self, occ):
        self.calls += 1
        r = evaluate_occupancy(self.graph, self.hazard, occ)
        return tuple((r["per_member"][m]["dose_exact"], r["per_member"][m]["peak"]) for m in self.ids)

    def node(self, node, t, end):
        return self._values([{"cell": node_cell(self.graph, self.nodes[node]), "start": t, "end": end}])

    node_plain = node

    def edge(self, edge_id, t, end):
        return self._values(edge_occupancies(self.edges[edge_id], t, end, graph=self.graph, node_lookup=self.nodes))

    edge_plain = edge

    def partial(self, edge_id, start, end, f, q):
        return self._values(edge_occupancies(self.edges[edge_id], start, end, f, q, self.graph, self.nodes))

    def stats(self):
        return {"mode": "centre", "calls": self.calls}
