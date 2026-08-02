#!/usr/bin/env python
"""Build the CANONICAL Yeongdeok hazard field — the one the npz should have been.

Round-3, follow-up to the routing_demo.npz investigation
(``data/processed/routing_demo_divergence.json``).

WHY
---
``data/processed/routing_demo.npz`` is the surviving output of the 2026-07-20
run that commits 2f7f555 / ccb0865 reverted the next day. That run's own
validation figures — pooled AUC 0.867, 138,619 rows, 2,731 positives — are on
the HARD forbidden list as retired pre-correction values. Its field is also
truncated: the outer ring is exactly 0.0 on all four sides while column 1
reaches p = 1.0.

This builds the field from the current canonical dataset (151,904 rows / 2,989
positives — the run behind ``spread_v2_lofo.json``) and the corrected DEMs.

    ⚠ ``routing_demo.npz`` is NEVER written, and its digest is checked before
      and after. The submission documents cite that digest. Output goes to
      ``data/processed/routing_demo_canonical.npz``.

THE CANVAS
----------
Parameters are the ones the committed npz recorded — 4 advance steps of 3 h
(5 slices, horizon 720 min), advance_threshold 0.3, 500 m cells,
``bbox.fire_acquisition``. On that canvas the canonical envelope **reaches the
western edge at p = 1.000**, so the grid is extended westward until
``assert_envelope_within_grid`` passes. The extension is searched, not guessed,
and the smallest sufficient value is used and recorded.

That makes the canonical grid larger than the committed 181x147. **That is
correct, not a discrepancy**: the committed field was clipped, and a clipped
envelope under-reports area, breadth and drift.

Run:  python scripts/build_canonical_hazard.py
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
from wildfireguardian.spread_v2.extent import (  # noqa: E402
    GridBoundaryError, assert_envelope_within_grid, boundary_contact,
    resolve_simulation_bbox,
)
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.forward_sim import (  # noqa: E402
    envelope_breadth_deg, forward_simulate,
)
from wildfireguardian.spread_v2.model import IgnitionModelV2  # noqa: E402
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402
from pyproj import Transformer  # noqa: E402

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

PROTECTED = REPO / "data/processed/routing_demo.npz"
#: The committed npz's core, for the side-by-side. Quoted, never recomputed.
COMMITTED_CELLS = [241, 241, 241, 242, 244]


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def simulate(model, ev, ws, bbox, args):
    hg = gridmod.build_grid(bbox, cell_size_m=args.cell_m)
    snaps = gridmod.overpass_snapshots(ev, hg, gap_minutes=90.0)
    hstatic = StaticLayers.from_event(ev, hg)
    sim = forward_simulate(model, ev, hg, hstatic, snaps[0].cumulative_mask,
                           snaps[0].time, ws, n_steps=args.n_steps,
                           step_hours=args.step_hours,
                           advance_threshold=args.advance_threshold)
    return hg, snaps, sim, HazardSequence.from_forward_sim(sim)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fire", default=_cfg("project.region_name", "yeongdeok_2025"))
    ap.add_argument("--seed", type=int, default=int(_cfg("seeds.canonical", 20250603)))
    ap.add_argument("--cell-m", type=float,
                    default=float(_cfg("grid.routing_integration_hazard_cell_m", 500.0)))
    ap.add_argument("--n-steps", type=int, default=int(_cfg("time.forward_sim_n_steps", 4)))
    ap.add_argument("--step-hours", type=float,
                    default=float(_cfg("time.forward_sim_step_hours", 3.0)))
    ap.add_argument("--advance-threshold", type=float,
                    default=float(_cfg("time.forward_sim_advance_threshold", 0.3)))
    ap.add_argument("--west-extend-candidates", type=float, nargs="+",
                    default=[0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50])
    ap.add_argument("--npz-out", default=str(REPO / "data/processed/routing_demo_canonical.npz"))
    ap.add_argument("--json-out", default=str(REPO / "data/processed/canonical_hazard.json"))
    args = ap.parse_args()

    before = hashlib.sha256(PROTECTED.read_bytes()).hexdigest()
    print(f"protected routing_demo.npz sha256 {before[:16]}... (must not change)")

    print("[1/4] building the canonical dataset ...")
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=args.cell_m,
                                buffer_m=float(_cfg("grid.feature_buffer_m", 6000.0)))
    n_rows, n_pos = int(len(ds)), int(ds["label"].sum())
    print(f"      {n_rows:,} rows, {n_pos:,} positives, "
          f"{len(sorted(ds['fire_id'].unique()))} fires")
    if (n_rows, n_pos) != (151904, 2989):
        print(f"STOP: dataset is {n_rows}/{n_pos}, not the canonical "
              "151,904/2,989. Refusing to label this field canonical.",
              file=sys.stderr)
        return 2

    print("[2/4] fitting leave-the-target-fire-out ...")
    model = IgnitionModelV2(seed=args.seed).fit(ds[ds["fire_id"] != args.fire])
    ev = data.load_event(args.fire)
    ws = weather_series_from_event(ev)
    base_bbox, prov = resolve_simulation_bbox(fallback=ev.meta.bbox_wgs84)
    print(f"      base canvas {base_bbox}  [{prov}]")

    print("[3/4] searching the smallest westward extension that clears the guard ...")
    trials, chosen = [], None
    for ext in args.west_extend_candidates:
        bbox = (base_bbox[0] - ext, base_bbox[1], base_bbox[2], base_bbox[3])
        hg, snaps, sim, hazard = simulate(model, ev, ws, bbox, args)
        stack = np.array(hazard.surfaces, dtype=np.float32)
        try:
            assert_envelope_within_grid(hazard.surfaces, grid=hg,
                                        context=f"{args.fire} canonical field")
            clear = True
        except GridBoundaryError:
            clear = False
        reports = [dict(boundary_contact(stack[i]), slice=i) for i in range(stack.shape[0])]
        edges = sorted({e for r in reports for e in r["edges_reached"]})
        cells = [int((stack[i] >= 0.5).sum()) for i in range(stack.shape[0])]
        trials.append({"west_extend_deg": ext, "bbox_wgs84": list(bbox),
                       "grid": [hg.nrows, hg.ncols], "boundary_clear": clear,
                       "edges_reached": edges, "cells_ge_0.5": cells})
        print(f"      +{ext:.2f} deg west -> grid {hg.nrows}x{hg.ncols}  "
              f"cells {cells}  boundary {'CLEAR' if clear else 'REACHED ' + '/'.join(edges)}")
        if clear:
            chosen = (ext, bbox, hg, snaps, sim, hazard, stack, reports)
            break

    if chosen is None:
        print(f"STOP: no candidate extension up to "
              f"{max(args.west_extend_candidates):g} deg cleared the boundary "
              "guard. Widen --west-extend-candidates; do NOT ship a clipped "
              "field.", file=sys.stderr)
        return 3

    ext, bbox, hg, snaps, sim, hazard, stack, reports = chosen
    ha = hg.cell_size_m * hg.cell_size_m / 10_000.0
    cells05 = [int((stack[i] >= 0.5).sum()) for i in range(stack.shape[0])]
    cells03 = [int((stack[i] >= 0.3).sum()) for i in range(stack.shape[0])]
    ign_xy = np.array(_TO_5179.transform(*ev.meta.ignition_lonlat), float)

    print("[4/4] writing ...")
    obs_stack = np.array([op.cumulative_mask for op in snaps], dtype=np.uint8)
    obs_times = np.array([(op.time - snaps[0].time).total_seconds() / 60.0
                          for op in snaps], float)
    np.savez_compressed(
        args.npz_out,
        grid_extent=np.array([hg.minx, hg.miny, hg.maxx, hg.maxy, hg.cell_size_m], float),
        haz_times=hazard.times_min,
        haz_stack=stack,
        obs_times=obs_times,
        obs_stack=obs_stack,
        ign_xy=ign_xy,
    )
    npz_sha = hashlib.sha256(Path(args.npz_out).read_bytes()).hexdigest()

    doc = {
        "schema_version": 1,
        "title": "Canonical Yeongdeok forward-simulated hazard field",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(), "config_hash": config_hash(),
        "npz_path": str(Path(args.npz_out).relative_to(REPO)),
        "npz_sha256": npz_sha,
        "npz_arrays": ["grid_extent", "haz_times", "haz_stack", "obs_times",
                       "obs_stack", "ign_xy"],
        "npz_arrays_note": (
            "The routing-demo route arrays (naive_xy, fa_xy, origin_xy, ...) are "
            "deliberately NOT reproduced here: they belong to the origin scan, "
            "not to the hazard field, and shipping a look-alike of "
            "routing_demo.npz would invite the two to be confused."),
        "does_not_supersede": (
            "data/processed/routing_demo.npz is UNTOUCHED and its digest is "
            "unchanged. Which field is published is a separate decision."),
        "dataset": {"n_rows": n_rows, "n_positives": n_pos,
                    "fires": sorted(ds["fire_id"].unique()),
                    "matches_spread_v2_lofo_json": True},
        "parameters": {
            "seed": args.seed, "cell_size_m": args.cell_m,
            "n_advance_steps": args.n_steps, "n_slices": int(stack.shape[0]),
            "step_hours": args.step_hours,
            "advance_threshold": args.advance_threshold,
            "horizon_min": float(hazard.times_min[-1]),
            "source": "as recorded in the committed npz's run "
                      "(yeongdeok_forward_sim.json at 01099bf: n_steps 5 slices, "
                      "step_hours 3.0, advance 0.3, horizon 720)",
        },
        "canvas": {
            "base_bbox_wgs84": list(base_bbox), "base_provenance": prov,
            "west_extend_deg": ext,
            "final_bbox_wgs84": list(bbox),
            "grid": {"nrows": hg.nrows, "ncols": hg.ncols,
                     "cell_size_m": hg.cell_size_m,
                     "extent_5179": [hg.minx, hg.miny, hg.maxx, hg.maxy]},
            "committed_npz_grid": {"nrows": 181, "ncols": 147},
            "why_the_grid_differs": (
                "On the unextended canvas the canonical envelope reaches the "
                "WESTERN edge at p = 1.000. The committed npz did not, because "
                "its outer ring is exactly 0.0 on all four sides — it was "
                "truncated. Extending the canvas is what lets the envelope be "
                "measured instead of cut off; a larger grid here is the fix, "
                "not a discrepancy."),
            "extension_search": trials,
        },
        "boundary_check": {
            "clear": True, "per_slice": reports,
            "max_edge_p": max(max(r["max_p_per_edge"].values()) for r in reports),
        },
        "field": {
            "times_min": [float(t) for t in hazard.times_min],
            "cells_ge_0.5": cells05,
            "cells_ge_0.3": cells03,
            "envelope_area_ha_p05": [c * ha for c in cells05],
            "core_growth_pct_first_to_last": (cells05[-1] / max(cells05[0], 1) - 1.0) * 100.0,
            "envelope_breadth_deg": [envelope_breadth_deg(sim, s, tuple(ign_xy), p_cut=0.3)
                                     for s in range(sim.n_steps)],
        },
        "side_by_side_vs_committed_npz": {
            "committed_cells_ge_0.5": COMMITTED_CELLS,
            "committed_envelope_area_ha": [c * 25.0 for c in COMMITTED_CELLS],
            "committed_grid": "181x147 (truncated ring)",
            "committed_provenance": "output of the 2026-07-20 run reverted by "
                                    "2f7f555 / ccb0865; its LOFO figures 0.867 / "
                                    "138,619 / 2,731 are HARD-forbidden retired "
                                    "values (data/processed/routing_demo_divergence.json)",
            "canonical_cells_ge_0.5": cells05,
            "canonical_envelope_area_ha": [c * ha for c in cells05],
        },
    }
    Path(args.json_out).write_text(json.dumps(doc, indent=2, ensure_ascii=False,
                                              default=str) + "\n", encoding="utf-8")

    after = hashlib.sha256(PROTECTED.read_bytes()).hexdigest()
    if before != after:
        print("STOP (exit 4): routing_demo.npz changed during this run.", file=sys.stderr)
        return 4
    print(f"      wrote {Path(args.npz_out).relative_to(REPO)}  sha256 {npz_sha[:16]}...")
    print(f"      wrote {Path(args.json_out).relative_to(REPO)}")
    print(f"      grid {hg.nrows}x{hg.ncols}, west +{ext:g} deg, "
          f"cells {cells05}, boundary clear")
    print(f"protected routing_demo.npz unchanged ({after[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
