#!/usr/bin/env python
"""Sweep the two NEW Phase-1 assumptions: ``t_load_min`` × ``egress_policy``.

Session 8, Phase 1d. Both knobs are new ASSUMED inputs (the on-scene pickup
time has no measured value; same-route egress is stated doctrine from an N = 1
field consultation, not a measurement). This sweep reports which conclusions
are robust to them and which are not, in the direction-vs-point-estimate style
of docs/rescue_routing.md §4a/§4b.

For every (t_load, egress_policy) cell the DISPATCH LIST IS HELD FIXED (the
four-way split and the dispatch membership do not depend on the margin — the
margin layer is additive), and the round-trip margin + recommendation is
recomputed for every dispatchable home.

Output: data/processed/margin_sweep.json

Run:  python scripts/run_margin_sweep.py [--synthetic]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.margins import (  # noqa: E402
    advisory, recommend, round_trip_margin,
)
from wildfireguardian.routing.rescue import RescueConfig  # noqa: E402
from wildfireguardian.routing.rescue_demo import (  # noqa: E402
    build_real_demo, build_synthetic_demo, run_pipeline,
)

T_LOADS: list[float] = [float(v) for v in
                        _cfg("responder.t_load_sweep", (5.0, 10.0, 15.0, 20.0))]
POLICIES: tuple[str, str] = ("same_route", "free")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--synthetic", action="store_true",
                    help="force the fully-synthetic fallback (offline CI); "
                         "default is the REAL OSM partial-flip scenario")
    ap.add_argument("--out", default=str(REPO / "data" / "processed"))
    args = ap.parse_args()

    overrides = {} if args.synthetic else {"use_osm": True}
    cfg = RescueConfig(**overrides)
    scenario = (build_synthetic_demo(cfg) if args.synthetic
                else build_real_demo(cfg))
    print(f"[1/3] scenario sources: drive={scenario.drive_source} "
          f"hazard={scenario.hazard_source}")

    print("[2/3] fixed dispatch list from the committed pipeline ...")
    results = run_pipeline(scenario, cfg)
    dispatch = results.dispatch
    depot_nodes = [scenario.drive.nearest_node(d.x, d.y) for d in scenario.depots]
    print(f"      dispatch={len(dispatch)}, four_way={results.four_way_counts}")

    print(f"[3/3] sweeping t_load {T_LOADS} x egress_policy {list(POLICIES)} ...")
    cells: dict[str, dict] = {}
    for pol in POLICIES:
        for tl in T_LOADS:
            c = replace(cfg, t_load_min=tl, egress_policy=pol)
            recs = Counter()
            margins: list[float] = []
            n_neg = 0
            for e in dispatch:
                m = round_trip_margin(scenario.drive, depot_nodes[e.depot_index],
                                      e.home_node, scenario.hazard, c,
                                      depot_index=e.depot_index)
                recs[recommend(m.margin_minutes, c)] += 1
                if np.isfinite(m.margin_minutes):
                    margins.append(m.margin_minutes)
                if m.margin_minutes <= 0:
                    n_neg += 1
            key = f"{pol}/t_load={tl:g}"
            cells[key] = {
                "egress_policy": pol,
                "t_load_min": tl,
                "n_dispatch": len(dispatch),
                "recommendations": dict(recs),
                "n_margin_nonpositive": n_neg,
                "margin_finite": {
                    "n": len(margins),
                    "median_min": (float(np.median(margins)) if margins else None),
                    "min_min": (float(np.min(margins)) if margins else None),
                    "max_min": (float(np.max(margins)) if margins else None),
                },
            }
            print(f"      {key}: recs={dict(recs)} nonpositive={n_neg}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "title": "t_load × egress_policy margin sweep (Session 8 Phase 1d)",
        "config_hash": config_hash(),
        "baseline": {"t_load_min": cfg.t_load_min,
                     "egress_policy": cfg.egress_policy,
                     "vehicle_cutoff": cfg.vehicle_cutoff,
                     "dispatch_delay_min": cfg.responder_dispatch_delay_min,
                     "safety_margin_min": cfg.responder_safety_margin_min},
        "four_way_counts_fixed": results.four_way_counts,
        "n_origins": results.n_origins,
        "provenance_note": (
            "t_load_min is ASSUMED (no measured value exists); egress_policy "
            "same_route follows an N = 1 field consultation's stated doctrine "
            "(docs/firefighter_consultation.md §2 — a statement, not a "
            "measurement). The four-way split and dispatch membership are "
            "margin-independent by construction and held fixed across cells."),
        "cells": cells,
    }
    p = out / "margin_sweep.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    print(f"wrote {p}")

    # Baseline advisory feed (the human-facing records, incl. trigger-line
    # cells for the top-20 dispatch entries), as its OWN artifact with its own
    # lineage. ⚠ The committed data/processed/rescue_routing.json is the
    # 2026-07-19 arm-A network vintage (439-series) and CANNOT be reproduced
    # (docs/network_drift.md, DATA_LOSS_2026-07-24.md); this feed is computed
    # on the CURRENT (arm-B snapshot) network, so it is written separately
    # rather than into the committed artifact.
    advisories = []
    for rank, e in enumerate(dispatch):
        a = advisory(scenario.drive, depot_nodes[e.depot_index], e.home_node,
                     scenario.hazard, cfg, depot_index=e.depot_index,
                     with_trigger=(rank < 20))
        a["four_way_class"] = "no_safe_pedestrian_route"
        advisories.append(a)
    for h in results.unreachable_homes:
        di = h.get("nearest_depot_index")
        dn = (depot_nodes[di] if di is not None and di < len(depot_nodes)
              else depot_nodes[0])
        a = advisory(scenario.drive, dn, h["home_node"], scenario.hazard, cfg,
                     depot_index=di, with_trigger=False)
        a["four_way_class"] = "no_surviving_vehicle_ingress"
        advisories.append(a)
    from collections import Counter as _C
    feed = {
        "schema_version": 1,
        "title": "margin advisory feed (Session 8 Phase 1c, human-facing)",
        "config_hash": config_hash(),
        "lineage": {
            "network_vintage": ("current tree (arm B snapshot, 441-series); "
                                "NOT the committed 439-series arm-A artifact "
                                "— see docs/network_drift.md"),
            "four_way_counts": results.four_way_counts,
            "n_origins": results.n_origins,
        },
        "recommendation_counts": dict(_C(a["recommendation"] for a in advisories)),
        "advisories": advisories,
    }
    p2 = out / "margin_advisories.json"
    p2.write_text(json.dumps(feed, ensure_ascii=False, indent=2))
    print(f"wrote {p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
