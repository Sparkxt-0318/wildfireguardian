"""Per-member journey reports (Contract D) from the frozen centre checker.

Every member is checked by the unchanged `routing.independent.check_route` (structure, legal turns and waits, sampled
closed-span flame contact, support, centre peak and linear dose including the request's incurred dose, destination
opening and dwell) on a single-member view of the hazard. Member rows may be lists (HAZARD.json) or NumPy arrays (the
in-memory v2 construction); the checker only indexes them. In addition this module integrates the thermal dose unit
form TDU = integral of q^(4/3) dt (q in kW/m2, t in s) over the same occupancy spans and the same piecewise-constant
centre flux, as a reporting quantity.

`radiation_law` selects the radiation law of the check: "v1" (the frozen packet flux) or "v2" (track 1A's flame-front
law, `wfg_flamefront`), which is not yet integrated here and raises NotImplementedError("law v2 not available").
"""
from __future__ import annotations

import bisect
from fractions import Fraction as F

from . import kit

RADIATION_LAWS = ("v1", "v2")


def _require_law(radiation_law):
    if radiation_law not in RADIATION_LAWS:
        raise ValueError("radiation_law must be v1 or v2")
    if radiation_law == "v2":
        raise NotImplementedError("law v2 not available")


def journey_spans(graph, request, legs, destination):
    """Occupancy spans (cell, start, end) of the legs and of the destination dwell, using the checker's own geometry."""
    ind = kit.install()["independent"]
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    spans = []
    for leg in legs:
        spans.extend(ind._occupancy(graph, leg, nodes, edges))
    if legs:
        arrival = legs[-1]["end"]
    else:
        arrival = request["departure"]
    dwell = next(d["dwell"] for d in request["destinations"] if d["node"] == destination)
    spans.append((ind._cell(graph, nodes[destination]), arrival, arrival + dwell))
    return spans


def tdu(spans, member, including_dwell_span=True):
    """Integral of flux^(4/3) over the spans for one member (piecewise-constant centre flux), in (kW/m2)^(4/3) s."""
    bp = member["breakpoints"]
    total = 0.0
    for cell, a, b in spans:
        if b <= a:
            continue
        cuts = [F(a)] + [F(t) for t in bp if a < t < b] + [F(b)]
        for left, right in zip(cuts, cuts[1:]):
            k = min(bisect.bisect_right(bp, float(left)) - 1, len(member["flux"]) - 1)
            if k < 0:
                continue
            q = float(member["flux"][k][cell])
            total += (q ** (4.0 / 3.0)) * float(right - left)
    return total


def member_reports(graph, hazard, request, legs, destination, *, radiation_law="v1", per_member_runs=False):
    _require_law(radiation_law)
    ind = kit.install()["independent"]
    spans = journey_spans(graph, request, legs, destination) if destination is not None else []
    if per_member_runs or destination is None:
        return _per_member_runs(graph, hazard, request, legs, destination, spans, radiation_law)
    # One frozen check of all members: structure, support, aggregated contact, per-member peak and dose. The per-member
    # contact flag uses the checker's own sampling rule on the same spans (closed spans against the packet's half-open
    # flame bins); the union must agree with the frozen aggregated FLAME_CONTACT code, else every member is re-checked
    # alone by the frozen checker.
    r = ind.check_route(graph, hazard, request, legs, destination)
    codes = set(r["codes"])
    if r["status"] == "INVALID_ROUTE":
        return _per_member_runs(graph, hazard, request, legs, destination, spans, radiation_law)
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    issue = ind._position_spans(graph, request["position"], request["departure"], nodes, edges)
    contact = [_member_contact(issue + spans, m) for m in hazard["members"]]
    if any(contact) != ("FLAME_CONTACT" in codes):
        return _per_member_runs(graph, hazard, request, legs, destination, spans, radiation_law)
    peak_limit = request["budgets"]["peak"]
    out = []
    for m, c in zip(hazard["members"], contact):
        pm = r["per_member"][m["id"]]
        peak_ok = not pm["peak"] > peak_limit
        dose_ok = not F(pm["dose_exact"]) > F(request["budgets"]["dose"][m["id"]])
        structure_ok, support_ok = "ROUTE_STRUCTURE" not in codes, "MISSING_SUPPORT" not in codes
        mc = sorted(({"FLAME_CONTACT"} if c else set()) | ({"PEAK_BUDGET"} if not peak_ok else set())
                    | ({"DOSE_BUDGET"} if not dose_ok else set()) | (codes & {"ROUTE_STRUCTURE", "MISSING_SUPPORT"}))
        out.append({"id": m["id"], "contact": c, "peak_kw_m2": pm["peak"], "dose_kj_m2": pm["dose"], "dose_exact": pm["dose_exact"],
                    "dose_tdu": tdu(spans, m) if spans else None, "peak_ok": peak_ok, "dose_ok": dose_ok,
                    "structure_ok": structure_ok, "support_ok": support_ok, "passed": not mc,
                    "status": r["status"] if r["status"] == "AT_ISSUE_FAILURE" else ("CHECKED_ROUTE" if not mc else "REJECTED_ROUTE"),
                    "codes": mc, "radiation_law": radiation_law, "check_mode": "frozen_once_plus_member_contact"})
    return out


def _member_contact(spans, member):
    """The frozen checker's sampling rule for one member: a span (cell, a, b) meets flame iff some sample time in
    {a, b} or a member breakpoint strictly inside (a, b) falls in a bin whose flame row is true at that cell."""
    bp = member["breakpoints"]
    rows = member["flame"]
    for cell, a, b in spans:
        a, b = F(a), F(b)
        cuts = [a] + [F(t) for t in bp if a < t < b] + ([b] if b != a else [])
        for t in cuts:
            if t < bp[0] or t > bp[-1]:
                continue
            k = min(bisect.bisect_right(bp, t) - 1, len(rows) - 1)
            if k >= 0 and rows[k][cell]:
                return True
    return False


def _per_member_runs(graph, hazard, request, legs, destination, spans, radiation_law):
    ind = kit.install()["independent"]
    out = []
    for m in hazard["members"]:
        view = dict(hazard)
        view["members"] = [m]
        r = ind.check_route(graph, view, request, legs, destination)
        pm = r["per_member"][m["id"]]
        codes = set(r["codes"])
        out.append({"id": m["id"], "contact": "FLAME_CONTACT" in codes, "peak_kw_m2": pm["peak"], "dose_kj_m2": pm["dose"],
                    "dose_exact": pm["dose_exact"], "dose_tdu": tdu(spans, m) if spans else None,
                    "peak_ok": "PEAK_BUDGET" not in codes, "dose_ok": "DOSE_BUDGET" not in codes,
                    "structure_ok": "ROUTE_STRUCTURE" not in codes, "support_ok": "MISSING_SUPPORT" not in codes,
                    "passed": bool(r["ok"]), "status": r["status"], "codes": sorted(codes), "radiation_law": radiation_law,
                    "check_mode": "frozen_per_member"})
    return out


def single_member_hazard(hazard, index):
    view = dict(hazard)
    view["members"] = [hazard["members"][index]]
    return view
