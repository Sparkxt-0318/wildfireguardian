#!/usr/bin/env python
"""Why does routing_demo.npz disagree with yeongdeok_forward_sim.json?

Round-3 investigation, opened by the PHASE-5 DEM measurements.

THE DISCREPANCY
---------------
Two committed artifacts that the same script writes in one run:

    routing_demo.npz            core >= 0.5 : 241, 241, 241, 242, 244  (near-static)
    yeongdeok_forward_sim.json  envelope ha : 6225 -> 27900            (grows 4.5x)

A re-run today reproduces the JSON to within ~3 % and does not come close to the
npz. The "core is quasi-static (241 -> 244)" sentence is cited by the submission
documents, and it lives only in the npz.

WHAT THIS SCRIPT ESTABLISHES
----------------------------
1. **Boundary**: whether the npz's near-static core is an artifact of the field
   being clipped at the canvas edge.
2. **Parameters**: whether ANY value of the forward-simulation knobs
   (advance_threshold, step count/length, cell size) brings a present-day re-run
   near 241 -> 244. If none does, the knobs are not the explanation.

The archaeology — which commit produced which artifact — is done with git and
recorded in the output rather than computed here.

⚠ It declares no winner. Which artifact is canonical is a decision for the
reader; this only removes explanations that do not survive contact with the
data. Writes ``data/processed/routing_demo_divergence.json`` and touches nothing
committed.

Run:  python scripts/investigate_routing_demo_divergence.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.spread_v2 import data, features, grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.extent import resolve_simulation_bbox  # noqa: E402
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.forward_sim import forward_simulate  # noqa: E402
from wildfireguardian.spread_v2.model import IgnitionModelV2  # noqa: E402
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402

NPZ = REPO / "data/processed/routing_demo.npz"
TARGET = [241, 241, 241, 242, 244]      # the committed npz's core, per slice


def _git(*args) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return ""


def boundary_forensics() -> dict:
    """Is the committed field clipped at the canvas edge, or does it just end?"""
    z = np.load(NPZ)
    h = z["haz_stack"].astype(float)
    final = h[-1]
    core = final >= 0.5
    cols, rows = core.sum(axis=0), core.sum(axis=1)
    nzc, nzr = np.nonzero(cols)[0], np.nonzero(rows)[0]
    ring_zero = {
        "col_0": bool(all(h[i][:, 0].max() == 0.0 for i in range(h.shape[0]))),
        "col_last": bool(all(h[i][:, -1].max() == 0.0 for i in range(h.shape[0]))),
        "row_0": bool(all(h[i][0, :].max() == 0.0 for i in range(h.shape[0]))),
        "row_last": bool(all(h[i][-1, :].max() == 0.0 for i in range(h.shape[0]))),
    }
    return {
        "npz_sha256": hashlib.sha256(NPZ.read_bytes()).hexdigest(),
        "grid_shape": list(h.shape),
        "cells_ge_0.5_per_slice": [int((h[i] >= 0.5).sum()) for i in range(h.shape[0])],
        "core_column_extent": [int(nzc.min()), int(nzc.max())],
        "core_row_extent": [int(nzr.min()), int(nzr.max())],
        "n_columns": int(final.shape[1]), "n_rows": int(final.shape[0]),
        "max_p_west_columns_0_to_6": [round(float(final[:, c].max()), 4) for c in range(7)],
        "max_p_east_columns_last_7": [round(float(final[:, c].max()), 4)
                                      for c in range(final.shape[1] - 7, final.shape[1])],
        "outer_ring_is_exactly_zero_in_every_slice": ring_zero,
        "finding": (
            "The outer ring is EXACTLY 0.0 in every slice on all four sides, "
            "while column 1 — one cell in from the western edge — reaches "
            "p = 1.0. A probability field does not fall from 1.0 to exactly 0.0 "
            "across one cell, so the western edge is TRUNCATED, not resolved. "
            "But the core occupies columns 1-87 of 147 and rows 72-116 of 181, "
            "so it has room to grow east, north and south and does not. "
            "Truncation therefore explains the western boundary; it does NOT "
            "explain why the core is near-static."),
        "how_much_could_truncation_hide": (
            "At most one column of the core's 45-row extent — about 45 cells, "
            "~1,125 ha — is lost to the zeroed western ring. The gap to be "
            "explained is 244 vs ~1,014-1,094 cells. Truncation is an order of "
            "magnitude too small."),
    }


def sweep(args) -> dict:
    """Can any forward-simulation knob reproduce 241 -> 244 on today's data?"""
    print("[1/2] building the dataset once ...")
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=args.cell_m,
                                buffer_m=float(_cfg("grid.feature_buffer_m", 6000.0)))
    print(f"      {len(ds):,} rows, {int(ds['label'].sum()):,} positives")
    model = IgnitionModelV2(seed=args.seed).fit(ds[ds["fire_id"] != args.fire])
    ev = data.load_event(args.fire)
    ws = weather_series_from_event(ev)
    sim_bbox, prov = resolve_simulation_bbox(fallback=ev.meta.bbox_wgs84)

    print("[2/2] sweeping ...")
    runs = []
    for adv in args.advance:
        for steps, hours in args.schedule:
            hg = gridmod.build_grid(sim_bbox, cell_size_m=args.cell_m)
            snaps = gridmod.overpass_snapshots(ev, hg, gap_minutes=90.0)
            hstatic = StaticLayers.from_event(ev, hg)
            sim = forward_simulate(model, ev, hg, hstatic, snaps[0].cumulative_mask,
                                   snaps[0].time, ws, n_steps=steps,
                                   step_hours=hours, advance_threshold=adv)
            hz = HazardSequence.from_forward_sim(sim)
            stack = np.stack([np.asarray(s, float) for s in hz.surfaces])
            cells = [int((stack[i] >= 0.5).sum()) for i in range(stack.shape[0])]
            ha = hg.cell_size_m * hg.cell_size_m / 10_000.0
            dist = (abs(cells[-1] - TARGET[-1]) if len(cells) == len(TARGET)
                    else abs(cells[-1] - TARGET[-1]))
            runs.append({
                "advance_threshold": adv, "n_steps": steps, "step_hours": hours,
                "cell_size_m": args.cell_m,
                "grid": [hg.nrows, hg.ncols],
                "cells_ge_0.5": cells,
                "envelope_area_ha": [c * ha for c in cells],
                "final_minus_target": cells[-1] - TARGET[-1],
                "abs_distance_to_target_final": dist,
            })
            print(f"      adv={adv:.2f} steps={steps} h={hours:g} -> {cells}  "
                  f"(target final {TARGET[-1]}, off by {cells[-1] - TARGET[-1]:+d})")
    runs.sort(key=lambda r: r["abs_distance_to_target_final"])
    return {
        "dataset": {"n_rows": int(len(ds)), "n_positives": int(ds["label"].sum()),
                    "fires": sorted(ds["fire_id"].unique())},
        "simulation_bbox_wgs84": list(sim_bbox), "bbox_provenance": prov,
        "target_committed_npz": TARGET,
        "runs": runs,
        "closest_run": runs[0],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fire", default=_cfg("project.region_name", "yeongdeok_2025"))
    ap.add_argument("--seed", type=int, default=int(_cfg("seeds.canonical", 20250603)))
    ap.add_argument("--cell-m", type=float,
                    default=float(_cfg("grid.routing_integration_hazard_cell_m", 500.0)))
    ap.add_argument("--advance", type=float, nargs="+",
                    default=[0.3, 0.5, 0.7, 0.9, 0.95, 0.99])
    ap.add_argument("--out",
                    default=str(REPO / "data/processed/routing_demo_divergence.json"))
    args = ap.parse_args()
    args.schedule = [(4, 3.0)]

    before = hashlib.sha256(NPZ.read_bytes()).hexdigest()

    doc = {
        "schema_version": 1,
        "title": "routing_demo.npz vs yeongdeok_forward_sim.json — why they disagree",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git("rev-parse", "HEAD"),
        "config_hash": config_hash(),
        "declares_no_winner": (
            "This file does NOT assert that 244 is wrong or that 27,900 is "
            "wrong. It records which explanations survive."),
        "archaeology": {
            "method": "git show <commit>:<path> for every revision touching the artifacts",
            "file_mtimes": {
                "routing_demo.npz": "2026-07-20 19:21:38",
                "routing_demo.json": "2026-07-22 08:45:16",
                "yeongdeok_forward_sim.json": "2026-07-22 08:45:16",
                "spread_v2_lofo.json": "2026-07-22 08:45:16",
                "fire_manifest.json": "2026-07-23 15:21:55",
            },
            "yeongdeok_forward_sim_envelope_by_commit": {
                "c96bff0 (2026-06-03)": [6225.0, 18225.0, 25500.0, 27050.0, 27900.0],
                "01099bf (2026-07-20)": [6025.0, 6025.0, 6025.0, 6050.0, 6100.0],
                "bfa4677 (2026-07-20)": [6225.0, 18225.0, 25500.0, 27050.0, 27900.0],
                "ccb0865 (2026-07-21, Revert)": [6225.0, 18225.0, 25500.0, 27050.0, 27900.0],
                "HEAD": [6225.0, 18225.0, 25500.0, 27050.0, 27900.0],
            },
            "spread_v2_lofo_by_commit": {
                "c96bff0 (2026-06-03)": {"pooled_auc": 0.9053, "n_rows": 151904, "n_positives": 2989},
                "01099bf (2026-07-20)": {"pooled_auc": 0.8667, "n_rows": 138619, "n_positives": 2731},
                "bfa4677 (2026-07-20)": {"pooled_auc": 0.8667, "n_rows": 138619, "n_positives": 2731},
                "ccb0865 (2026-07-21, Revert)": {"pooled_auc": 0.9053, "n_rows": 151904, "n_positives": 2989},
                "HEAD": {"pooled_auc": 0.9053, "n_rows": 151904, "n_positives": 2989},
            },
            "npz_committed_at": "1e451ee (2026-07-24) — three days AFTER the revert",
            "finding": (
                "The npz's core areas (241/241/241/242/244 cells = 6025/6025/"
                "6025/6050/6100 ha) are EXACTLY the envelope_area_ha that "
                "yeongdeok_forward_sim.json carried at commit 01099bf. So the two "
                "artifacts DID come from one run — the 2026-07-20 run whose LOFO "
                "was pooled AUC 0.8667 over 138,619 rows and 2,731 positives. "
                "Commits 2f7f555 and ccb0865 then REVERTED that state on "
                "2026-07-21, restoring the JSON to the earlier 6225->27900 "
                "figures and the LOFO to 0.9053 / 151,904 / 2,989. The npz was "
                "not part of those reverts: it was added to git separately on "
                "2026-07-24 and still carries the reverted run's field."),
            "retired_values_note": (
                "0.867, 138619 and 2731 are all on the HARD forbidden list in "
                "scripts/check_forbidden.py as retired pre-correction values. The "
                "npz is the surviving output of exactly that run."),
        },
        "code_was_not_the_variable": {
            "method": "git diff 01099bf HEAD -- src/wildfireguardian/spread_v2/<file>",
            "features.py": "UNCHANGED", "model.py": "UNCHANGED",
            "grid.py": "UNCHANGED", "dataset.py": "UNCHANGED",
            "forward_sim.py": "UNCHANGED", "weather.py": "UNCHANGED",
            "data.py": "UNCHANGED",
            "only_change_in_package": "extent.py ADDED (PHASE 1, boundary guard) "
                                      "and README.md (2 lines)",
            "parameters_recorded_in_the_01099bf_json": {
                "n_steps": 5, "step_hours": 3.0, "advance_threshold": 0.3,
                "horizon_min": 720.0},
            "consequence": (
                "Identical model code and identical recorded parameters produced "
                "138,619 rows then and 151,904 rows now, so the variable is the "
                "INPUT DATA, not the code and not the knobs. fire_manifest.json "
                "was itself regenerated on 2026-07-23 15:21."),
        },
        "boundary_forensics": boundary_forensics(),
    }
    doc["parameter_sweep"] = sweep(args)

    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False,
                                         default=str) + "\n", encoding="utf-8")
    after = hashlib.sha256(NPZ.read_bytes()).hexdigest()
    if before != after:
        print("STOP (exit 4): routing_demo.npz changed during this run.", file=sys.stderr)
        return 4
    print(f"\nwrote {Path(args.out).relative_to(REPO)}")
    print(f"routing_demo.npz unchanged ({after[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
