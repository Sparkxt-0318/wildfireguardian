#!/usr/bin/env python
"""How much of the E1 ceiling's road-node advantage survives NOT knowing the wind.

The Stage 2 oracles (`docs/benchmark/stage2_proxy_rules.md`) pick their wind against the
observation, so their metric-3 rows are upper bounds. The question that bound leaves open is
the operational one: **an operator does not have the oracle's wind.** This script answers it
by running protocol §5.3 --- the false-safe rate at the canonical walk network --- at EVERY
one of the 720 declared grid points, not only at the best one, and reporting the
distribution. Metric 3 alone; metric 4 costs minutes per field and is not swept.

Reads only committed artifacts plus the Stage 2 sweep's own construction, writes
``data/processed/benchmark/stage2_wind_sensitivity.json``. Nothing committed is modified.

    python scripts/benchmark/stage2_wind_sensitivity.py
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_entrants_stage2 as B  # noqa: E402
from kspread_metrics import arrival_time_error, crossing_grid  # noqa: E402
from kspread_truth import first_seen_grid, node_truth  # noqa: E402
from score_kspread import canonical_scene  # noqa: E402

OUT = REPO / "data/processed/benchmark/stage2_wind_sensitivity.json"
P_CUT = 0.5


def main() -> int:
    t_start = time.monotonic()
    cv = B.canvas()
    fs, t = first_seen_grid(cv["z"])
    elev, _ = B.elevation_on_canvas(cv)
    extent7 = (cv["x0"], cv["y0"], cv["x1"], cv["y1"], cv["cell"], cv["nrow"], cv["ncol"])

    print("canonical scene + 458-origin scan ...", flush=True)
    scene = canonical_scene()
    net = scene["net"]
    nodes = list(net.graph.nodes)
    xs = np.array([net.node_xy(n)[0] for n in nodes], float)
    ys = np.array([net.node_xy(n)[1] for n in nodes], float)
    # node truth is fixed --- it depends on the observation, never on an entrant
    truth = [node_truth(float(xs[i]), float(ys[i]), fs, t, extent7, 0) for i in range(len(nodes))]
    rowi = np.floor((extent7[3] - ys) / extent7[4]).astype(int)
    coli = np.floor((xs - extent7[0]) / extent7[4]).astype(int)
    window = float(B.TIMES_MIN[-1])

    out = {}
    for kind in ("e1", "e2"):
        rows = []
        for j, bg in enumerate(B.BEARINGS):
            unit = B.unit_cost(cv, bg, None if kind == "e1" else elev)
            print(f"  [{kind}] bearing {bg:5.1f}° ({j + 1}/{len(B.BEARINGS)})", flush=True)
            for r in B.RATES:
                stack = B.stack_from_unit_cost(cv, unit, r)
                cross = crossing_grid(stack, B.TIMES_MIN, P_CUT)
                model = cross[rowi, coli]
                recs = [{"node": int(nodes[i]), "supported": truth[i]["supported"],
                         "observed_min": truth[i]["observed_min"],
                         "earliest_min": truth[i]["earliest_min"],
                         "model_min": float(model[i]) if truth[i]["supported"] else math.inf}
                        for i in range(len(nodes))]
                a = arrival_time_error(recs, window)
                rows.append({"bearing_deg": float(bg), "head_rate_m_per_30min": float(r),
                             "false_safe_rate": a["false_safe_rate"],
                             "false_safe_nodes": a["false_safe_nodes"],
                             "nodes_model_calls_safe": a["nodes_model_calls_safe"],
                             "nodes_model_burns": a["nodes_model_burns"],
                             "false_alarm_nodes": a["false_alarm_nodes"],
                             "median_abs_error_min": a["median_abs_error_min"]})
        # A grid point whose front covers every node calls NOTHING safe, so the rate is
        # undefined rather than zero. Those points are counted, never folded in as 0.0: a
        # field that burns the whole canvas has no false-safe node and no value either.
        defined = [x for x in rows if x["false_safe_rate"] is not None]
        undefined = len(rows) - len(defined)
        fsr = np.array([x["false_safe_rate"] for x in defined], float)
        out[kind] = {
            "grid_points": len(rows),
            "grid_points_with_a_defined_rate": len(defined),
            "grid_points_that_call_no_node_safe": undefined,
            "false_safe_rate": {"min": float(fsr.min()), "p25": float(np.percentile(fsr, 25)),
                                "median": float(np.median(fsr)), "p75": float(np.percentile(fsr, 75)),
                                "max": float(fsr.max())},
            "grid_points_beating_e3_false_safe_rate": int((fsr < 0.1830).sum()),
            "grid_points_beating_e0_false_safe_rate": int((fsr < 0.1833).sum()),
            "rows": rows,
        }
        print(f"  [{kind}] false-safe rate min {fsr.min():.4f} median {np.median(fsr):.4f} "
              f"max {fsr.max():.4f}; {int((fsr < 0.1830).sum())}/{len(defined)} beat E3; "
              f"{undefined} points call no node safe", flush=True)

    OUT.write_text(json.dumps({
        "schema_version": 1,
        "title": "K-SPREAD-2025 Stage 2 — metric 3 across the whole declared wind grid",
        "question": ("The oracle rows are upper bounds because they choose the wind against the "
                     "observation. This asks what the same proxies do at every OTHER wind in the "
                     "declared grid, which is the operational case."),
        "rule_page": "docs/benchmark/stage2_proxy_rules.md",
        "metric": "protocol §5.3 false-safe rate at the canonical walk network, m = 0, cell membership",
        "reference_rows": {"e0_persistence_false_safe_rate": 0.1833,
                           "e3_wfg_canonical_false_safe_rate": 0.1830,
                           "source": "data/processed/benchmark/leaderboard_v0_2.json"},
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "seconds": round(time.monotonic() - t_start, 1),
        "entrants": out,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
