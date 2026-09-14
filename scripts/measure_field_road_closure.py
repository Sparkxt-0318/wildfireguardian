#!/usr/bin/env python
"""How much of the forecast field's road-closure content is dynamic, and how much is
already true at minute 0.

Written 2026-09-14 after `docs/benchmark/results_v0.1.md` reported that at the road nodes
the canonical scan uses, the committed field differs from 「nothing spreads」 by three nodes
at p >= 0.5. The truck-crew replay's central quantities — the corridor closing minute, the
margin and the abort rule — are all statements about **roads over time**, so the same
question has to be asked at the **vehicle** cutoff on the **drive** network before those
quantities can be read as a timeline.

Counts, per field and per cutoff: cells and drive-network nodes already at or above the
cutoff at t = 0, and those the field adds at any later slice inside the window.

Writes data/processed/field_road_closure_yeongdeok.json. Reads only committed inputs.

    python scripts/measure_field_road_closure.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.rescue import RescueConfig  # noqa: E402

from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402

PROC = REPO / "data/processed"
OUT = PROC / "field_road_closure_yeongdeok.json"
FIELDS = {"canonical": "routing_demo_canonical.npz",
          "leakfree": "routing_demo_leakfree.npz"}
CUTOFFS = (0.5, 0.7)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="wfg-frc-"))
    try:
        materialise_snapshots(tmp / "yeongdeok_2025")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp),
                           scan_stride=REAL_OSM_SCAN_STRIDE)
        sc = build_scenario(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    g = sc.hazard.grid

    def cell(x, y):
        c = int((x - g.minx) // g.cell_size_m)
        r = int((g.maxy - y) // g.cell_size_m)
        return (r, c) if 0 <= r < g.nrows and 0 <= c < g.ncols else None

    drive_cells: dict[tuple[int, int], list[int]] = {}
    for n in sc.drive.graph.nodes():
        rc = cell(*sc.drive.node_xy(n))
        if rc is not None:
            drive_cells.setdefault(rc, []).append(int(n))

    results: dict = {}
    for fname, fn in FIELDS.items():
        haz = np.load(PROC / fn)["haz_stack"].astype(float)
        per_cut = {}
        for cut in CUTOFFS:
            at0 = haz[0] >= cut
            ever = haz.max(axis=0) >= cut
            added = ever & ~at0
            per_cut[str(cut)] = {
                "cells_at_t0": int(at0.sum()),
                "cells_added_later": int(added.sum()),
                "drive_nodes_at_t0": sum(len(v) for rc, v in drive_cells.items() if at0[rc]),
                "drive_nodes_added_later": sum(
                    len(v) for rc, v in drive_cells.items() if added[rc]),
            }
        results[fname] = {"npz": f"data/processed/{fn}", "by_cutoff": per_cut}

    doc = {
        "schema_version": 1,
        "title": "How much of the field's road-closure content is dynamic (영덕)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "why": "docs/benchmark/results_v0.1.md §2 put the committed field in the hindcast "
               "track and measured that at road nodes it barely differs from persistence at "
               "p >= 0.5. The truck-crew replay's corridor closing minute, margin and abort "
               "rule are statements about roads over time, so the same question is asked "
               "here at the vehicle cutoff on the drive network.",
        "networks": {
            "drive_nodes": sc.drive.graph.number_of_nodes(),
            "distinct_cells_holding_a_drive_node": len(drive_cells),
            "grid_cells": g.nrows * g.ncols,
        },
        "vehicle_cutoff_used_by_the_replay": 0.7,
        "results": results,
        "reading": "A drive node 「added later」 is one the field says closes DURING the "
                   "window; a node 「at t = 0」 is already closed before the replay starts. "
                   "The replay's abort rule can only ever fire on the former.",
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for fname, r in results.items():
        for cut, c in r["by_cutoff"].items():
            print(f"{fname} cut={cut}: drive nodes at t=0 {c['drive_nodes_at_t0']}, "
                  f"added later {c['drive_nodes_added_later']} "
                  f"(cells {c['cells_at_t0']} / {c['cells_added_later']})")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
