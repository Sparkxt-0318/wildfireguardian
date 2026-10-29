"""The journey-safety predicate of docs/JOURNEY_SAFETY_PREDICATE.md, written directly from the mathematics on abstract
instances, independently of the search. Requirement identifiers (JS-1 ... JS-12) are returned with every violation.

A member is a dict with
  "edge_block": {j: [(lo, hi), ...]}   departure seconds at which a traversal of j meets flame in this member
  "wait_block": {node: [(lo, hi), ...]} wait-start seconds t at which waiting [t, t + 1] meets flame
  "issue_contact": bool                the issue position is in flame at departure
  "edge_flux": {j: q}, "wait_flux": {node: q}, "dwell_flux": {node: q}  constant flux (kW/m2) during a leg
  "incurred": dose already received (kJ/m2)
The abstract instance supplies graph structure, travel times, waitability, acceptance seconds and the horizon.
A journey is a list of legs ("EDGE", j, start, end) or ("WAIT", node, start, end) and an arrival second.
"""
from __future__ import annotations

from fractions import Fraction as F

from .intervals import contains

REQUIREMENTS = {
    "JS-1": "departure at or after issue: the first leg starts at the request departure",
    "JS-2": "legs are contiguous: each leg starts when the previous one ends",
    "JS-3": "times are monotone: every leg has end > start, and end <= horizon",
    "JS-4": "an EDGE leg lasts exactly the edge travel time D_j",
    "JS-5": "turn restrictions: (incoming edge, next edge) is not forbidden and the edge leaves the current node",
    "JS-6": "waits happen only at waitable nodes",
    "JS-7": "node waits lie inside node safe intervals of every member in S",
    "JS-8": "no traversal window meets a member's unsafe interval of that edge (flame contact)",
    "JS-9": "flux stays at or below the peak limit for every member in S",
    "JS-10": "the dose sum (incurred plus journey, including dwell when requested) is within the member's budget",
    "JS-11": "the journey ends with an admission arrival at a destination accepted at that second (opening, dwell, horizon, no contact while dwelling)",
    "JS-12": "at issue: the issue position is not in contact and the incurred dose is within budget",
}


def violations(inst, legs, arrival, members, *, peak_limit=None, dose_budget=None, dwell_s=0, include_dwell=True):
    """List of (requirement id, member index or None, detail). Empty iff the journey is safe under every member given."""
    out = []
    succ = inst.successors()
    s, t, admission = inst.start_state, inst.departure, True
    for k, m in enumerate(members):
        if m.get("issue_contact"):
            out.append(("JS-12", k, "issue contact"))
        if dose_budget is not None and F(m.get("incurred", 0)) > F(dose_budget):
            out.append(("JS-12", k, "incurred above budget"))
    dose = [F(m.get("incurred", 0)) for m in members]
    for i, (kind, ident, a, b) in enumerate(legs):
        if i == 0 and a != inst.departure:
            out.append(("JS-1", None, "first leg at %s" % a))
        if a != t:
            out.append(("JS-2", None, "gap at leg %d" % i))
        if not b > a or b > inst.horizon:
            out.append(("JS-3", None, "leg %d times" % i))
        if kind == "WAIT":
            node = inst.state_head(s)
            if ident != node or not inst.waitable[node]:
                out.append(("JS-6", None, "wait at %s" % ident))
            for k, m in enumerate(members):
                for w in range(a, b):
                    if contains(m.get("wait_block", {}).get(node, []), w):
                        out.append(("JS-7", k, "wait second %d" % w))
                q = F(m.get("wait_flux", {}).get(node, 0))
                dose[k] += q * (b - a)
                if peak_limit is not None and q > F(peak_limit):
                    out.append(("JS-9", k, "wait flux"))
            admission = False
        else:
            j = ident
            if j not in succ[s]:
                out.append(("JS-5", None, "edge %d after state %d" % (j, s)))
            if b - a != inst.D[j]:
                out.append(("JS-4", None, "edge %d duration" % j))
            for k, m in enumerate(members):
                if contains(m.get("edge_block", {}).get(j, []), a):
                    out.append(("JS-8", k, "edge %d at %d" % (j, a)))
                q = F(m.get("edge_flux", {}).get(j, 0))
                dose[k] += q * (b - a)
                if peak_limit is not None and q > F(peak_limit):
                    out.append(("JS-9", k, "edge flux"))
            s, admission = j, True
        t = b
    node = inst.state_head(s)
    if not (t == arrival and admission and contains(inst.accept.get(node, []), t)):
        out.append(("JS-11", None, "end state"))
    for k, m in enumerate(members):
        q = F(m.get("dwell_flux", {}).get(node, 0))
        if include_dwell:
            dose[k] += q * dwell_s
        if peak_limit is not None and q > F(peak_limit):
            out.append(("JS-9", k, "dwell flux"))
        if dose_budget is not None and dose[k] > F(dose_budget):
            out.append(("JS-10", k, "dose %s" % dose[k]))
    return out


def safe(inst, legs, arrival, members, **kw):
    return not violations(inst, legs, arrival, members, **kw)


def union_member(members):
    """The member whose unsafe sets are the unions of the given members (what the planner plans against)."""
    eb, wb = {}, {}
    for m in members:
        for j, ivs in m.get("edge_block", {}).items():
            eb.setdefault(j, []).extend(ivs)
        for n, ivs in m.get("wait_block", {}).items():
            wb.setdefault(n, []).extend(ivs)
    from .intervals import normalise
    return {"edge_block": {j: normalise(v) for j, v in eb.items()}, "wait_block": {n: normalise(v) for n, v in wb.items()},
            "issue_contact": any(m.get("issue_contact") for m in members)}
