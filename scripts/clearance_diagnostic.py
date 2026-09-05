#!/usr/bin/env python
"""Session 18, Phase 5 — is the vulnerability score's second clause ever live?

The Layer 0 vulnerability score is documented as **"no survivable route, OR a
clearance margin below 10 minutes."** In Session 17 the second clause fired
**0 times in 2,496 failure events**, and two causes were not distinguished:

  (A) the elliptical hazard's reach is too small for any route to pass near
      burning ground; or
  (B) ``clearance`` almost never becomes finite BY CONSTRUCTION.

The difference matters. Under (A) the clause is dormant on this data and would
wake on a fiercer fire. Under (B) it is close to dead in every run, and the
documented definition of the score promises something the code does not deliver.

``routing/evacuation.py::_evaluate_path`` computes, over the nodes of a found
route::

    clearance = min over path nodes of ( time_to_cutoff(node) - arrival(node) )

and ``time_to_cutoff`` returns ``inf`` when the node never reaches ``p_cut``
within ``hazard.times_min``. ``clearance`` therefore stays ``inf`` — and is
reported as ``None`` — unless **at least one node on the route burns inside the
horizon**. A route that successfully flees the fire tends to have no such node,
so success and a finite margin pull against each other.

THIS IS A DIAGNOSTIC, NOT AN EXPERIMENT. The router, the threshold and the
hazard are not modified. Nothing here is tuned to make the clause fire.

    python scripts/clearance_diagnostic.py --horizon 240
    python scripts/clearance_diagnostic.py --collect
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

OUT = REPO / "data" / "processed" / "vulnerability"
CACHE = OUT / "clearance_cache"
HORIZONS = (30.0, 60.0, 120.0, 180.0, 240.0, 360.0)


def run_horizon(horizon: float, n_ign: int = 4) -> dict:
    import vulnerability_layer as vlm
    from vulnerability_sensitivity import load_yeongdeok

    from wildfireguardian.routing.evacuation import (
        build_time_expanded_field, future_aware_route)
    from wildfireguardian.vulnerability.hazard_sources import (
        EllipticalHazard, Weather)
    from wildfireguardian.vulnerability.ignition import IgnitionSampler
    from wildfireguardian.vulnerability.refuge import surviving_shelters

    res, _ = load_yeongdeok()
    net = res["net"]
    uniq = [int(n) for n in res["uniq_nodes"]]
    all_shelters = set(net.shelters)
    hp = vlm.human_points(res)
    igs = IgnitionSampler(prior="human_proximity").sample(
        res["grid"], res["burnable"], hp, n_ign, res["buildings"].xy)
    times = np.linspace(0.0, horizon, vlm.N_TIME_SLICES)
    src = EllipticalHazard()

    n_routes = n_reached = n_finite = n_below = 0
    finite_vals: list[float] = []
    t0 = time.time()
    for ig in igs:
        for name, spd, toward in vlm.SCENARIOS:
            hz = src.build(res["grid"], (ig.x, ig.y), Weather(spd, toward, name),
                           times_min=times, elevation=res["elevation"],
                           burnable_frac=res["burnable"])
            keep, _ = surviving_shelters(net, hz, p_cut=vlm.P_CUT, buffer_min=0.0)
            if not keep:
                continue
            net.shelters = keep
            field = build_time_expanded_field(
                net, hz, departure_min=0.0, time_budget_min=horizon,
                p_cut=vlm.P_CUT, time_step_min=vlm.TIME_STEP_MIN)
            for node in uniq:
                r = future_aware_route(net, node, hz, departure_min=0.0,
                                       time_budget_min=horizon, p_cut=vlm.P_CUT,
                                       time_step_min=vlm.TIME_STEP_MIN,
                                       field=field)
                n_routes += 1
                if not r.reached:
                    continue
                n_reached += 1
                m = r.clearance_margin_min
                if m is not None and np.isfinite(m):
                    n_finite += 1
                    finite_vals.append(float(m))
                    if m < vlm.MARGIN_FAIL_MIN:
                        n_below += 1
    net.shelters = all_shelters

    v = np.asarray(finite_vals, dtype="float64")
    return {
        "horizon_min": horizon,
        "n_route_evaluations": n_routes,
        "n_reached": n_reached,
        "n_clearance_finite": n_finite,
        "n_clearance_infinite": n_reached - n_finite,
        "share_finite_of_reached": (round(n_finite / n_reached, 6)
                                    if n_reached else None),
        "n_below_margin_threshold": n_below,
        "margin_threshold_min": vlm.MARGIN_FAIL_MIN,
        "finite_values": ({"min": round(float(v.min()), 2),
                           "median": round(float(np.median(v)), 2),
                           "max": round(float(v.max()), 2),
                           "n_negative": int((v < 0).sum())} if len(v) else None),
        "seconds": round(time.time() - t0, 1),
    }


def committed_artifact_scan() -> dict:
    """Every ``clearance_margin_min`` value in a committed artifact."""
    vals: list = []
    where: dict[str, dict] = {}

    def walk(o, sink):
        if isinstance(o, dict):
            for k, x in o.items():
                if k == "clearance_margin_min":
                    sink.append(x)
                else:
                    walk(x, sink)
        elif isinstance(o, list):
            for x in o:
                walk(x, sink)

    for f in sorted((REPO / "data" / "processed").rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            continue
        got: list = []
        walk(d, got)
        if not got:
            continue
        fin = [x for x in got if isinstance(x, (int, float))]
        where[str(f.relative_to(REPO))] = {
            "n": len(got), "n_finite": len(fin), "n_null": len(got) - len(fin),
            "range": ([round(min(fin), 2), round(max(fin), 2)] if fin else None)}
        vals += got
    fin = [x for x in vals if isinstance(x, (int, float))]
    return {"files": where, "n_values": len(vals), "n_finite": len(fin),
            "n_null": len(vals) - len(fin)}


def collect() -> dict:
    rows = []
    for h in HORIZONS:
        p = CACHE / f"h{int(h)}.json"
        if p.exists():
            rows.append(json.loads(p.read_text(encoding="utf-8")))
    tot_reached = sum(r["n_reached"] for r in rows)
    tot_finite = sum(r["n_clearance_finite"] for r in rows)
    tot_below = sum(r["n_below_margin_threshold"] for r in rows)
    out = {
        "site": "yeongdeok_2025",
        "question": (
            "Does clearance_margin_min ever take a finite value, and is the "
            "vulnerability score's 'margin < 10 min' clause live or inert?"),
        "mechanism": (
            "clearance = min over route nodes of (time_to_cutoff(node) - "
            "arrival(node)); time_to_cutoff returns inf when the node never "
            "reaches p_cut within hazard.times_min. So clearance is finite ONLY "
            "when at least one node ON THE ROUTE burns inside the horizon — and "
            "a route that successfully flees the fire tends to have no such "
            "node. Success and a finite margin pull against each other."),
        "by_horizon": rows,
        "totals": {
            "n_reached": tot_reached,
            "n_clearance_finite": tot_finite,
            "n_clearance_infinite": tot_reached - tot_finite,
            "share_finite": (round(tot_finite / tot_reached, 6)
                             if tot_reached else None),
            "n_below_margin_threshold": tot_below,
        },
        "committed_artifacts": committed_artifact_scan(),
    }
    (OUT / "clearance_diagnostic.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"totals": out["totals"],
                      "by_horizon": [{k: r[k] for k in
                                      ("horizon_min", "n_reached",
                                       "n_clearance_finite",
                                       "share_finite_of_reached",
                                       "n_below_margin_threshold",
                                       "finite_values")} for r in rows],
                      "committed": {k: v for k, v in
                                    out["committed_artifacts"].items()
                                    if k != "files"}},
                     indent=2, ensure_ascii=False))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=float, default=None)
    ap.add_argument("--collect", action="store_true")
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    if a.horizon is not None:
        p = CACHE / f"h{int(a.horizon)}.json"
        if p.exists():
            print(f"  cached {p.name}")
        else:
            d = run_horizon(a.horizon)
            p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
            print(f"  H={a.horizon:>5.0f} reached={d['n_reached']:>5} "
                  f"finite={d['n_clearance_finite']:>5} "
                  f"below={d['n_below_margin_threshold']:>4}  {d['seconds']}s")
    if a.collect:
        collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
