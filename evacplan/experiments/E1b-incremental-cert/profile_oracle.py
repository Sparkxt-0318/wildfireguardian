"""E1b step 1: where the oracle's time goes on the two SYNTHETIC L dev instances (B1's plans, seed 0).

Profiling only: no method runs on these numbers, nothing is tuned to them, the oracle is not changed (rule 3).
Run from the worktree root under the shared bench lock (it builds Reach and runs B1 and the oracle):

    .venv/bin/python /home/user/wildfireguardian/program/benchlock.py --wait-max 1800 --label E1b-profile -- \
        .venv/bin/python evacplan/experiments/E1b-incremental-cert/profile_oracle.py

Per instance it measures
1. a cold ``Oracle.check_plan`` (a fresh Oracle, so an empty query cache) of B1's plan, simple timer;
2. the same check under cProfile (another fresh Oracle): cumulative time of the oracle's parts;
3. a warm re-check with the first Oracle (every hazard query is then a cache hit): what a check costs without the
   hazard_contract queries;
4. E1's in-loop path per vehicle on the same plan (E1's ``_check``: emit the actions, RelaxedContactCheck, then
   ``Oracle.check_itinerary`` on a fresh Oracle), each part timed;
5. scaling with the K = 8 members: cold ``check_plan`` with the first 1, 2, 4 and 8 members.
Writes ``profile/oracle_profile.json`` and ``profile/<instance>.pstats.txt`` next to this file. SYNTHETIC data only.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import platform
import pstats
import time
from pathlib import Path

import numpy as np

import hazard_contract as hc
from evacplan.harness import git_commit, host_string
from evacplan.instances import load_entry, load_split
from evacplan.methods import get_method
from evacplan.methods.dispatch import latest_departures
from evacplan.methods.e1_alns import DEFAULTS, VDec, _Net, _Run
from evacplan.oracle import Oracle, RelaxedContactCheck
from evacplan.reach import Reach
from evacplan.schema import Itinerary

HERE = Path(__file__).resolve().parent
INSTANCES = ("SYNTHETIC-L-grid-t50-s109", "SYNTHETIC-L-geo-t50-s110")

# (file suffix, function name, label): the oracle's parts, by cumulative time in the cProfile run
PARTS = [
    ("evacplan/oracle.py", "check_plan", "Oracle.check_plan (total)"),
    ("evacplan/validate.py", "validate_solution", "validator (validate_solution: simulate, shared capacities)"),
    ("evacplan/oracle.py", "_evaluate", "Oracle._evaluate (all legs of all vehicles)"),
    ("evacplan/oracle.py", "_hazard", "  hazard_contract queries (Oracle._hazard)"),
    ("hazard_contract/scenario.py", "query_uniform", "    ScenarioSet.query_uniform (drive legs)"),
    ("hazard_contract/scenario.py", "uniform_pieces", "      uniform_pieces (cut at grid lines)"),
    ("hazard_contract/scenario.py", "_point_burning", "      _point_burning (contact under uniform motion)"),
    ("hazard_contract/scenario.py", "query", "    ScenarioSet.query (every piece twice, and stays)"),
    ("hazard_contract/scenario.py", "_member_result", "      _member_result (per member: flux and dose bounds)"),
    ("hazard_contract/geometry.py", "polyline_rect_dmin", "      polyline_rect_dmin (near-box distances)"),
    ("hazard_contract/geometry.py", "solid_angle_rects", "      solid_angle_rects (exact kernels at probes)"),
    ("hazard_contract/geometry.py", "polyline_cells", "geometry: polyline_cells (all callers)"),
    ("evacplan/oracle.py", "_classify", "  Oracle._classify (states from the member results)"),
    ("evacplan/oracle.py", "leg_slack", "  Oracle.leg_slack (exact slack of checked legs)"),
    ("evacplan/oracle.py", "contact_records", "    contact_records"),
    ("pydantic/main.py", "__init__", "pydantic BaseModel.__init__ (result objects, all callers)"),
    ("hazard_contract/query.py", "__init__", "SegmentHazard dataclass (all callers)"),
]


def _key(stats: pstats.Stats, suffix: str, name: str):
    hits = [k for k in stats.stats if k[0].replace("\\", "/").endswith(suffix) and k[2] == name]
    return hits[0] if hits else None


def _cum(stats: pstats.Stats, key) -> tuple[float, int]:
    cc, nc, tt, ct, _ = stats.stats[key]
    return ct, nc


def _by_caller(stats: pstats.Stats, key) -> dict[str, float]:
    out: dict[str, float] = {}
    for caller, val in stats.stats[key][4].items():
        ct = val[3]
        out[f"{Path(caller[0]).name}:{caller[2]}"] = out.get(f"{Path(caller[0]).name}:{caller[2]}", 0.0) + ct
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def _subset(inst, ss: hc.ScenarioSet, k: int):
    meta = ss.meta.model_copy(update={"K": k})
    s = hc.ScenarioSet(ss.ignite_s[:k], ss.extinguish_s[:k], ss.supported[:k], meta)
    s._get_index()                                     # built before the timer, as in the harness (deadlines first)
    return s


def legs_of(plan) -> int:
    return sum(len(v.legs) for v in plan.vehicles)


def profile_instance(entry, out_dir: Path) -> dict:
    inst, ss = load_entry(entry)
    res: dict = {"instance": entry.id, "label": "SYNTHETIC", "K": ss.K, "vehicles": len(inst.vehicles),
                 "residents": inst.residents_total}
    t0 = time.perf_counter()
    ss._get_index()
    res["scenario_index_s"] = round(time.perf_counter() - t0, 3)

    # B1's plan, seed 0 (deterministic)
    t0 = time.monotonic()
    b1 = get_method("b1_greedy").solve(inst, ss, budget_s=60.0, seed=0, deadline=t0 + 60.0)
    res["b1_solve_s"] = round(time.monotonic() - t0, 3)
    sol = b1.solution

    # 1. cold check_plan, simple timer (fresh Oracle: empty query cache)
    t0 = time.perf_counter()
    oracle = Oracle(inst, ss)
    plan = oracle.check_plan(sol)
    cold = time.perf_counter() - t0
    legs = legs_of(plan)
    res.update(delivered=plan.delivered_total, unresolved=plan.unresolved_total, model_no_route=plan.model_no_route_total,
               legs=legs, legs_by_kind=dict(sorted(_kinds(plan).items())),
               trips=sum(len(v.trips) for v in plan.vehicles), cold_check_s=round(cold, 3),
               cold_ms_per_leg=round(1000 * cold / legs, 3), unique_hazard_queries=len(oracle._cache))

    # 3. warm re-check with the same Oracle: every hazard query is a cache hit
    t0 = time.perf_counter()
    plan2 = oracle.check_plan(sol)
    warm = time.perf_counter() - t0
    assert plan2.delivered_total == plan.delivered_total
    res.update(warm_recheck_s=round(warm, 3), warm_ms_per_leg=round(1000 * warm / legs, 3))

    # 2. cProfile of another cold check
    pr = cProfile.Profile()
    o2 = Oracle(inst, ss)
    t0 = time.perf_counter()
    pr.enable()
    o2.check_plan(sol)
    pr.disable()
    res["profiled_check_s"] = round(time.perf_counter() - t0, 3)
    st = pstats.Stats(pr)
    total_key = _key(st, "evacplan/oracle.py", "check_plan")
    total = _cum(st, total_key)[0]
    parts = []
    for suffix, name, label in PARTS:
        k = _key(st, suffix, name)
        if k is None:
            parts.append({"part": label, "cum_s": 0.0, "share": 0.0, "calls": 0})
            continue
        ct, nc = _cum(st, k)
        parts.append({"part": label, "cum_s": round(ct, 3), "share": round(ct / total, 4), "calls": nc})
    res["profile_parts"] = parts
    res["polyline_cells_by_caller_s"] = {c: round(t, 3) for c, t in
                                         _by_caller(st, _key(st, "hazard_contract/geometry.py", "polyline_cells")).items()}
    res["pydantic_init_by_caller_s"] = {c: round(t, 3) for c, t in
                                        _by_caller(st, _key(st, "pydantic/main.py", "__init__")).items()}
    buf = io.StringIO()
    ps = pstats.Stats(pr, stream=buf)
    ps.sort_stats("cumulative").print_stats(30)
    ps.sort_stats("tottime").print_stats(30)
    (out_dir / f"{entry.id}.pstats.txt").write_text(
        f"# SYNTHETIC {entry.id}: cProfile of a cold Oracle.check_plan of B1's plan (seed 0)\n" + buf.getvalue())

    # 4. E1's in-loop path per vehicle: emit + RelaxedContactCheck + Oracle.check_itinerary (fresh Oracle)
    run = _Run({**DEFAULTS}, "e1_alns", inst, ss, 60.0, 0, time.monotonic() + 60.0)
    rh = Reach(inst, ss)
    D = latest_departures(inst, rh)
    net = run.net = _Net(inst, rh, D)
    dsp = run._warm_start(rh, D, time.monotonic() + 60.0)
    o3 = Oracle(inst, ss)
    relaxed = RelaxedContactCheck(inst, ss)
    per_v = []
    same = True
    for v, vid in enumerate(net.vid):
        keys = [(((net.fidx[tr.facility], tuple(int(x) for x in tr.counts)),), net.sidx[tr.delivery.shelter])
                for tr in dsp.vs[vid].trips]
        vd = VDec(net, v, net.decode(v, net.vnode[v], net.vstart[v], keys))
        if not vd.outs:
            continue
        t0 = time.perf_counter()
        acts = net.emit(v, vd)
        t1 = time.perf_counter()
        it = Itinerary(vehicle=vid, actions=acts)
        rx = relaxed.itinerary(it)
        t2 = time.perf_counter()
        r = o3.check_itinerary(it)
        t3 = time.perf_counter()
        same &= it in sol.itineraries
        per_v.append({"vehicle": vid, "trips": len(vd.outs), "decoded_legs": vd.legs, "oracle_legs": len(r.legs),
                      "emit_s": round(t1 - t0, 3), "relaxed_s": round(t2 - t1, 3), "oracle_s": round(t3 - t2, 3),
                      "relaxed_blocked": rx.first_blocked is not None})
    tot = {k: round(sum(p[k] for p in per_v), 3) for k in ("emit_s", "relaxed_s", "oracle_s")}
    dl = sum(p["decoded_legs"] for p in per_v)
    res["e1_check_path"] = {"vehicles": per_v, "totals": tot, "decoded_legs": dl,
                            "oracle_legs": sum(p["oracle_legs"] for p in per_v),
                            "s_per_decoded_leg": round(sum(tot.values()) / dl, 5),
                            "itineraries_equal_b1": bool(same)}

    # 5. scaling with K: cold check_plan with the first k members
    scal = []
    for k in (1, 2, 4, 8):
        sk = _subset(inst, ss, k) if k < ss.K else ss
        t0 = time.perf_counter()
        pk = Oracle(inst, sk).check_plan(sol)
        dt = time.perf_counter() - t0
        scal.append({"K": k, "check_s": round(dt, 3), "ms_per_leg": round(1000 * dt / legs_of(pk), 3),
                     "delivered": pk.delivered_total})
    ks = np.array([s["K"] for s in scal], dtype=float)
    ys = np.array([s["ms_per_leg"] for s in scal])
    slope, icpt = np.polyfit(ks, ys, 1)
    res["k_scaling"] = {"runs": scal, "fit_ms_per_leg": {"intercept": round(float(icpt), 3),
                                                          "per_member": round(float(slope), 3)}}
    return res


def _kinds(plan) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in plan.vehicles:
        for lg in v.legs:
            out[lg.kind] = out.get(lg.kind, 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=HERE / "profile")
    ap.add_argument("--instances", nargs="+", default=list(INSTANCES))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    split = load_split()
    dev = {e.id: e for e in split.entries("dev")}
    out = {"label": "SYNTHETIC", "commit": git_commit(), "host": host_string(), "python": platform.python_version(),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "instances": []}
    for iid in args.instances:
        r = profile_instance(dev[iid], args.out)
        out["instances"].append(r)
        print(json.dumps({k: v for k, v in r.items() if k not in ("e1_check_path",)}, indent=1), flush=True)
        print(json.dumps(r["e1_check_path"]["totals"]), r["e1_check_path"]["s_per_decoded_leg"], flush=True)
    out["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (args.out / "oracle_profile.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"-> {args.out / 'oracle_profile.json'}")


if __name__ == "__main__":
    main()
