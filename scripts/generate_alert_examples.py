#!/usr/bin/env python
"""Generate the filled alert-loop message examples from REAL model output.

Session 8, Phase 3. docs/alert_loop.md §2 requires the filled examples to be
generated, not hand-written: the landmark comes from the village-cluster
naming rules (nearest named OSM refuge), and the time-to-arrival is the
hazard field's earliest walk-cutoff crossing at the cluster centroid,
rounded DOWN to the forecast slice.

Lineage: current-tree (arm B) network vintage; hazard/terrain synthetic —
every minute quoted is a model output on labelled-synthetic hazard, not a
measurement.

Output: data/processed/alert_examples.json
Run:  python scripts/generate_alert_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash  # noqa: E402
from wildfireguardian.delivery.alert_loop import (  # noqa: E402
    build_broadcast_lines, build_sms_alert, build_tts_call,
)
from wildfireguardian.delivery.villages import cluster_points, named_refuges  # noqa: E402
from wildfireguardian.routing.rescue import RescueConfig, node_survival_time  # noqa: E402
from wildfireguardian.routing.rescue_demo import build_real_demo, run_pipeline  # noqa: E402


def main() -> int:
    cfg = RescueConfig(use_osm=True)
    print("[1/3] building REAL scenario (arm-B networks; synthetic hazard) ...")
    scenario = build_real_demo(cfg)
    results = run_pipeline(scenario, cfg)

    dests = [a.as_dict() for a in results.dest_assessments]
    points = [{"x": e.x, "y": e.y, "home_node": e.home_node}
              for e in results.dispatch]
    villages = cluster_points(points, dests)
    print(f"[2/3] {len(villages)} village clusters from {len(points)} dispatch homes")

    refuges = named_refuges(dests)

    examples = []
    for v in sorted(villages, key=lambda v: -v.n_points)[:3]:
        cx, cy = v.centroid
        arrival = node_survival_time(scenario.hazard, cx, cy, cfg.walk_cutoff)
        if not (arrival < float("inf")):
            continue                      # a cluster the hazard never reaches
        # nearest named refuge = both the landmark basis and the destination
        import numpy as np
        rxy = np.array([[r["x"], r["y"]] for r in refuges])
        j = int(np.argmin(np.hypot(rxy[:, 0] - cx, rxy[:, 1] - cy)))
        refuge_name = refuges[j]["name"].strip()
        landmark = v.name
        examples.append({
            "village": v.name,
            "name_basis": v.name_basis,
            "n_dispatch_homes": v.n_points,
            "arrival_min_walk_cutoff": arrival,
            "refuge_name": refuge_name,
            "sms": build_sms_alert(landmark, arrival),
            "tts_call": build_tts_call(landmark, arrival, refuge_name),
            "broadcast_lines": build_broadcast_lines(landmark, arrival, refuge_name),
        })

    doc = {
        "schema_version": 1,
        "title": "alert-loop filled examples, generated from real model output "
                 "(Session 8 Phase 3)",
        "config_hash": config_hash(),
        "lineage": {
            "network_vintage": "current tree (arm B snapshot)",
            "hazard": "synthetic (labelled)",
            "note": "every arrival minute is a model output on "
                    "labelled-synthetic hazard; landmark names are real OSM "
                    "POI names via the village naming rules",
        },
        "examples": examples,
    }
    out = REPO / "data" / "processed" / "alert_examples.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    print(f"[3/3] wrote {out} ({len(examples)} examples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
