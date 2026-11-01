#!/usr/bin/env python3
"""E3 pilot: cost measurements before the main run (no result is read from it but timings and sizes).

Run from the worktree root through the shared bench lock (program rule 6):

    .venv/bin/python program/benchlock.py --label E3-pilot -- \\
        .venv/bin/python evacplan/experiments/E3-scenario-robustness/e3_pilot.py

For every dev instance (frozen split, fingerprints verified; never test, refused when
EVACPLAN_MILESTONE is set): regenerate the instance's SYNTHETIC hazard model with more members and
check that the first 8 reproduce the instance's members bit for bit; plan B1 with the instance's own
8 members; time two single-member oracle checks of that plan on fresh members. For three instances
(one S, one M, one L) also: B1 with 1 member and with 32 fresh members, and one oracle check against
32 fresh members at once. Writes ``evacplan/runs/E3-scenario-robustness/pilot.json`` (git-ignored).
Nothing here declares a state (rule 3): every verdict comes from ``evacplan.oracle``.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

import hazard_contract as hc
from evacplan.generators import synthetic as syn
from evacplan.harness import host_string
from evacplan.instances import load_entry, load_split
from evacplan.methods import get_method
from evacplan.oracle import Oracle, State

EVACPLAN_DIR = Path(__file__).resolve().parents[2]
RUNS_DIR = EVACPLAN_DIR / "runs" / "E3-scenario-robustness"
K_INSTANCE = 8
P_PLAN = 32            # fresh planning members (indices 8 .. 39)
N_CHECK = 256          # fresh check members (indices 40 .. 295)
DETAIL = ("SYNTHETIC-S-geo-t25-s102", "SYNTHETIC-M-geo-t75-s108", "SYNTHETIC-L-geo-t50-s110")


def extended_members(entry, ss, k_total: int):
    """The instance's SYNTHETIC hazard model with ``k_total`` members: same ignition, rate, direction, grid,
    seed and post-processing; the first 8 must equal the instance's members bit for bit."""
    cfg = syn.SyntheticConfig.model_validate(entry.config)
    fire = syn._Fire(cfg, syn.SIZES[cfg.size], np.zeros(2))
    pv = ss.meta.provenance
    if int(fire.seed) != int(pv["seed"]):
        raise RuntimeError(f"{entry.id}: hazard seed {fire.seed} != provenance {pv['seed']}")
    raw = hc.synthetic(K=k_total, height=fire.height, width=fire.width, cell_m=syn.CELL_M, x0=fire.x0, y0=fire.y0,
                       crs_epsg=syn.CRS_EPSG, ignition_xy=(float(pv["ignition_xy"][0]), float(pv["ignition_xy"][1])),
                       t_ignition_s=syn.T_IGNITION_S, ros_m_s=float(pv["ros_m_s"]),
                       spread_dir_deg=float(pv["spread_dir_deg"]), horizon_s=fire.horizon,
                       burn_duration_s=syn.PERSIST_S, issue_time_utc=syn.ISSUE_TIME_UTC, heat=fire.heat,
                       seed=fire.seed)
    ig = np.floor(raw.ignite_s)
    ex = np.where(np.isfinite(ig), ig + syn.PERSIST_S, np.inf)
    sup = np.array(raw.supported, dtype=bool)
    k = K_INSTANCE
    same = (ig[:k].tobytes() == np.ascontiguousarray(ss.ignite_s, dtype=np.float64).tobytes()
            and ex[:k].tobytes() == np.ascontiguousarray(ss.extinguish_s, dtype=np.float64).tobytes()
            and sup[:k].tobytes() == np.ascontiguousarray(ss.supported, dtype=bool).tobytes())
    return ig, ex, sup, same


def member_set(ss, ig, ex, sup, ks, role: str) -> hc.ScenarioSet:
    ks = [int(k) for k in ks]
    meta = hc.ScenarioMeta(**{**ss.meta.model_dump(), "K": len(ks), "provenance": {
        **ss.meta.provenance, "e3_role": role, "e3_members": ks,
        "e3_note": "SYNTHETIC: members of the instance's hazard model regenerated with more draws (E3)"}})
    return hc.ScenarioSet(ig[ks], ex[ks], sup[ks], meta)


def plan_b1(inst, pset):
    t0 = time.monotonic()
    res = get_method("b1_greedy").solve(inst, pset, budget_s=60.0, seed=0, deadline=time.monotonic() + 60.0)
    return res, time.monotonic() - t0


def size(plan) -> dict:
    return {"vehicles": len(plan.vehicles), "trips": sum(len(v.trips) for v in plan.vehicles),
            "legs": sum(len(v.legs) for v in plan.vehicles),
            "drive_legs": sum(1 for v in plan.vehicles for lg in v.legs if lg.kind == "drive"),
            "delivered": plan.delivered_total, "unresolved": plan.unresolved_total,
            "model_no_route": plan.model_no_route_total, "min_slack_s": plan.min_slack_s}


def single_checks(inst, ss, ig, ex, sup, solution, members, delivered_in: int) -> list[dict]:
    out = []
    for j in members:
        t0 = time.monotonic()
        p = Oracle(inst, member_set(ss, ig, ex, sup, [j], "check")).check_plan(solution)
        out.append({"member": int(j), "seconds": round(time.monotonic() - t0, 4), "delivered": p.delivered_total,
                    "lost": delivered_in - p.delivered_total,
                    "trips_not_checked": sum(1 for v in p.vehicles for t in v.trips if t.state != State.CHECKED)})
    return out


def main() -> int:
    if os.environ.get("EVACPLAN_MILESTONE"):
        raise SystemExit("refused: EVACPLAN_MILESTONE is set (E3 uses the dev set only; program rule 5)")
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    split = load_split()
    report = {"host": host_string(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
              "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "instances": {}}
    t_all = time.monotonic()
    k_total = K_INSTANCE + P_PLAN + N_CHECK
    check0 = K_INSTANCE + P_PLAN
    for e in split.entries("dev"):
        rec: dict = {}
        t0 = time.monotonic()
        inst, ss = load_entry(e)
        rec["load_s"] = round(time.monotonic() - t0, 3)
        t0 = time.monotonic()
        ig, ex, sup, same = extended_members(e, ss, k_total)
        rec["extend_s"] = round(time.monotonic() - t0, 3)
        rec["first8_bit_identical"] = bool(same)
        if not same:
            report["instances"][e.id] = rec
            print(f"{e.id}: first 8 members NOT bit-identical; skipped", flush=True)
            continue
        oracle8 = Oracle(inst, ss)
        res, rt = plan_b1(inst, ss)
        t0 = time.monotonic()
        p8 = oracle8.check_plan(res.solution)
        rec["b1_k8"] = {"runtime_s": round(rt, 3), "stopped_at_budget": res.info.get("stopped_at_budget"),
                        "oracle_k8_s": round(time.monotonic() - t0, 3), **size(p8)}
        rec["b1_k8"]["single"] = single_checks(inst, ss, ig, ex, sup, res.solution, [check0, check0 + 1],
                                               p8.delivered_total)
        if e.id in DETAIL:
            t0 = time.monotonic()
            pall = Oracle(inst, member_set(ss, ig, ex, sup, range(check0, check0 + 32), "check")).check_plan(
                res.solution)
            rec["b1_k8"]["batch32"] = {"seconds": round(time.monotonic() - t0, 3), "delivered": pall.delivered_total}
            rec["b1_k8"]["single"] += single_checks(inst, ss, ig, ex, sup, res.solution,
                                                    range(check0 + 2, check0 + 6), p8.delivered_total)
            for name, ks in (("b1_k1", [0]), ("b1_k32_fresh", list(range(K_INSTANCE, K_INSTANCE + P_PLAN)))):
                pset = member_set(ss, ig, ex, sup, ks, "plan")
                r2, rt2 = plan_b1(inst, pset)
                t0 = time.monotonic()
                pin = Oracle(inst, pset).check_plan(r2.solution)
                rec[name] = {"runtime_s": round(rt2, 3), "stopped_at_budget": r2.info.get("stopped_at_budget"),
                             "oracle_in_sample_s": round(time.monotonic() - t0, 3), **size(pin),
                             "single": single_checks(inst, ss, ig, ex, sup, r2.solution, [check0, check0 + 1, check0 + 2],
                                                     pin.delivered_total)}
        report["instances"][e.id] = rec
        print(e.id, json.dumps(rec), flush=True)
    report["total_s"] = round(time.monotonic() - t_all, 1)
    (RUNS_DIR / "pilot.json").write_text(json.dumps(report, indent=1) + "\n")
    print(f"[E3 pilot] total {report['total_s']} s -> {RUNS_DIR / 'pilot.json'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
