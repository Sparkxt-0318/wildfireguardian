"""Tractable matched bridge to the frozen repaired vector engine.

Not a replacement or claim about the established full road SIPP/activation arm.
Every incompatible case stays UNAVAILABLE. Admission restricts all possible dose
increments so binary64 cumulative addition is exact; candidate integration uses
rational resource arithmetic and does not inherit this historical restriction.
"""

from pathlib import Path
from types import SimpleNamespace
from fractions import Fraction
import hashlib, math, time, resource, sys


def solve(graph, hazard, request):
    started = time.perf_counter()

    def unavailable(reason):
        return {
            "status": "UNAVAILABLE",
            "reason": reason,
            "arrival": None,
            "legs": [],
            "metrics": {"wall_s": time.perf_counter() - started},
        }

    from .validation import validate_request, ValidationError

    try:
        request = validate_request(graph, hazard, request)
    except ValidationError as e:
        return unavailable(e.code)
    mids = [m["id"] for m in hazard["members"]]
    if (
        "node" not in request["position"]
        or request["incoming_edge"] is not None
        or request["departure"] != 0
        or any(request["incurred"].values())
        or request["exposure_scope"] != "route_only"
        or len(set(request["budgets"]["dose"].values())) != 1
    ):
        return unavailable(
            "HISTORICAL_API_NO_CURRENT_CONTEXT_OR_VARIABLE_INCURRED_BUDGETS"
        )
    if request["position"]["node"] in {d["node"] for d in request["destinations"]}:
        return unavailable("HISTORICAL_ZERO_LEG_ADMISSION_NOT_IMPLEMENTED")
    if not all(all(row) for m in hazard["members"] for row in m["support"]):
        return unavailable("HISTORICAL_COMPLETE_SUPPORT_REQUIRED")
    if not graph["edges"]:
        return unavailable("HISTORICAL_EMPTY_EDGE_SET_UNSUPPORTED")
    # The frozen vector engine imports numpy and two rpipe names only. Bind
    # those names to local measurement shims in memory; vendored bytes untouched.
    import numpy as np

    source = Path(__file__).resolve().parent.parent / "vendor/r3_sparse.py"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != "7e56ef8f49e5dd21a6397d25c1e18d80f629d9a245cf89f9af2f3677f6ecd9a9":
        return unavailable("FROZEN_SOURCE_HASH_MISMATCH")

    def rss():
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
            1048576 if sys.platform == "darwin" else 1024
        )

    namespace = {
        "EN": SimpleNamespace(cur_rss_mb=rss),
        "R3Result": dict,
        "__name__": "frozen_r3_local",
    }
    text = (
        source.read_text()
        .replace("from rpipe import engines as EN\n", "")
        .replace("from rpipe.joint import R3Result\n", "")
    )
    exec(compile(text, str(source), "exec"), namespace)
    from .independent import _charge, _occupancy, _cell, check_route

    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    nids = list(nodes)
    eids = list(edges)
    ni = {n: i for i, n in enumerate(nids)}
    ei = {e: i for i, e in enumerate(eids)}
    dt = hazard["dt"]
    K = int(Fraction(request["horizon"]) / Fraction(dt))
    budget = next(iter(request["budgets"]["dose"].values()))
    if K > 10000:
        return unavailable("BRIDGE_TRACTABLE_PREPARATION_ONLY_K_LIMIT_NOT_A_SOLVER_CAP")

    def charge(spans):
        stats = {m: {"dose": Fraction(0), "peak": 0} for m in mids}
        codes = set()
        _charge(spans, hazard, stats, True, codes)
        return stats, bool(codes) or any(
            s["peak"] > request["budgets"]["peak"] for s in stats.values()
        )

    issue, issue_bad = charge(
        [(_cell(graph, nodes[request["position"]["node"]]), 0, 0)]
    )
    if issue_bad:
        return {
            "status": "AT_ISSUE_FAILURE",
            "reason": "CURRENT_OCCUPANCY_FAILURE",
            "arrival": None,
            "legs": [],
            "metrics": {"wall_s": time.perf_counter() - started},
        }
    E = [[{} for _ in eids] for _ in mids]
    W = [[{} for _ in nids] for _ in mids]
    edgebad = {}
    waitbad = {}
    exacts = [Fraction(budget)]
    max_inc = Fraction(0)
    for k in range(K + 1):
        t = k * dt
        if time.perf_counter() - started >= request["limits"]["wall_s"]:
            return {
                "status": "TIMEOUT",
                "reason": "PREPARATION_WALL_CLOCK",
                "arrival": None,
                "legs": [],
                "metrics": {"wall_s": time.perf_counter() - started},
            }
        for eidx, eid in enumerate(eids):
            edge = edges[eid]
            end = t + edge["travel_ticks"] * dt
            if end > request["horizon"]:
                edgebad[eidx, k] = True
                continue
            leg = {
                "kind": "EDGE",
                "edge": eid,
                "start": t,
                "end": end,
                "from_fraction": 0,
                "to_fraction": 1,
            }
            stats, bad = charge(_occupancy(graph, leg, nodes, edges))
            edgebad[eidx, k] = bad
            for j, mid in enumerate(mids):
                v = stats[mid]["dose"]
                E[j][eidx][k] = v
                exacts.append(v)
                max_inc = max(max_inc, v)
        for nidx, nid in enumerate(nids):
            if t + dt > request["horizon"]:
                waitbad[nidx, k] = True
                continue
            stats, bad = charge([(_cell(graph, nodes[nid]), t, t + dt)])
            waitbad[nidx, k] = bad
            for j, mid in enumerate(mids):
                v = stats[mid]["dose"]
                W[j][nidx][k] = v
                exacts.append(v)
                max_inc = max(max_inc, v)
    denominator = max(v.denominator for v in exacts)
    if denominator & (denominator - 1) or any(
        denominator % v.denominator for v in exacts
    ):
        return unavailable("NONDYADIC_EXPOSURE_OUTSIDE_MATCHED_NUMERICAL_SUBSET")
    if int(max_inc * denominator) * max(1, K) >= 2**52 or any(
        Fraction(float(v)) != v for v in exacts
    ):
        return unavailable("HISTORICAL_FLOAT_RESOURCE_ADDITION_NOT_EXACT")

    class Mask:
        def __init__(self, data):
            self.data = data

        def query(self, ids, k):
            return np.array(
                [self.data.get((int(i), int(k)), True) for i in ids], dtype=bool
            )

    class Table:
        def __init__(self, data):
            self.data = data

        def reset(self):
            pass

        def eval(self, ids, k):
            return np.array([float(self.data[int(i)].get(int(k), 0)) for i in ids])

    out = [[] for _ in nids]
    for eid, e in edges.items():
        out[ni[e["u"]]].append(ei[eid])
    forbidden = {tuple(x) for x in graph["forbidden_turns"]}
    succ = [
        [f for f in out[ni[edges[eid]["v"]]] if (eid, eids[f]) not in forbidden]
        for eid in eids
    ]
    dests = {ni[d["node"]]: d for d in request["destinations"]}

    def dest_ok(n, k):
        d = dests.get(n)
        if not d:
            return False
        t = k * dt
        end = t + d["dwell"]
        if end > request["horizon"] or not any(
            a <= t and end <= b for a, b in d["open_intervals"]
        ):
            return False
        _, bad = charge([(_cell(graph, nodes[nids[n]]), t, end)])
        return not bad

    pb = SimpleNamespace(
        n_edges=len(eids),
        m_ticks=np.array([edges[e]["travel_ticks"] for e in eids]),
        ev=np.array([ni[edges[e]["v"]] for e in eids]),
        waitable=np.array([nodes[n]["waitable"] for n in nids]),
    )
    cp = SimpleNamespace(
        pb=pb,
        K=K,
        out_by_node=out,
        succ=succ,
        edge_forbid=Mask(edgebad),
        wait_forbid=Mask(waitbad),
        dest_ok=dest_ok,
    )
    raw = namespace["r3_bounded_exact"](
        cp,
        [Table(x) for x in E],
        [Table(x) for x in W],
        ni[request["position"]["node"]],
        list(dests),
        budget,
        k_limit=K,
        frontier_width=request["limits"]["frontier_width"],
        max_pops=request["limits"]["max_expansions"],
        time_limit_s=max(
            0, request["limits"]["wall_s"] - (time.perf_counter() - started)
        ),
        rss_limit_mb=request["limits"].get("rss_limit_mb", 3072),
    )
    result = {
        "status": (
            "TIMEOUT"
            if raw["status"] == "CAP"
            else (
                "PROVEN_INFEASIBLE"
                if raw["status"] == "REFUSED"
                else ("CHECKED_ROUTE" if raw["truncated"] else "CONDITIONAL_OPTIMUM")
            )
        ),
        "reason": raw.get("cap"),
        "legs": [],
        "arrival": None,
        "solver_status": raw["status"],
        "metrics": {
            "wall_s": time.perf_counter() - started,
            "expansions": raw["pops"],
            "labels": raw["n_records"],
            "peak_rss_mb": rss(),
        },
        "provenance": {
            "baseline": "FROZEN_REPAIRED_VECTOR_ENGINE_TRACTABLE_BRIDGE",
            "source_sha256": digest,
            "not_full_historical_road_arm": True,
        },
    }
    if raw["status"] == "ROUTE":
        legs = [
            {
                "kind": kind,
                ("edge" if kind == "EDGE" else "node"): (
                    eids[index] if kind == "EDGE" else nids[index]
                ),
                "start": a * dt,
                "end": b * dt,
                **({"from_fraction": 0, "to_fraction": 1} if kind == "EDGE" else {}),
            }
            for kind, index, a, b in raw["legs"]
        ]
        destination = nids[int(pb.ev[raw["dest_state"]])]
        checked = check_route(graph, hazard, request, legs, destination)
        result.update(
            legs=legs,
            arrival=raw["t_arr_tick"] * dt,
            destination=destination,
            checker=checked,
            per_member=checked["per_member"],
        )
        if not checked["ok"]:
            result["status"] = "UNSUPPORTED"
            result["reason"] = "INDEPENDENT_CHECK_DISAGREEMENT"
    result["metrics"]["wall_s"] = time.perf_counter() - started
    if raw["n_records"] > request["limits"]["max_labels"] or rss() > request[
        "limits"
    ].get("rss_limit_mb", 3072):
        result.update(
            status="TIMEOUT", reason="RESOURCE_CAP_AFTER_SOLVER", arrival=None, legs=[]
        )
    if result["metrics"]["wall_s"] >= request["limits"]["wall_s"]:
        result.update(status="TIMEOUT", reason="END_TO_END_WALL_CLOCK")
    return result
