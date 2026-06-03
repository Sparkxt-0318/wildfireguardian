#!/usr/bin/env python3
"""Deliverable 0 — AUDIT of the corrected firms_data bundle.

Proves the data fixes worked, per fire:
  - detections (total / snapped-into-grid), 60-min overpasses
  - fuel coverage (in-bounds fraction) + burnable coverage (gate fraction,
    mean burnable_frac, vs manifest)
  - ERA5 status (present / 0-byte-missing, timesteps, time range)
  - candidate/positive counts via the orientation-safe pipeline
  - capture of observed spread by the candidate gate (positives lost to gate)

Headline checks:
  * uljin_samcheok_2022 positives ≈ 880 (was ~120 under the orientation bug)
  * gangneung_donghae_2022 fuel/burnable coverage ≈ full bbox (was ~5%)

Run:  .venv/bin/python scripts/spread_v2/00_audit.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from wildfireguardian.spread_v2_xgb import SEED  # noqa: E402
from wildfireguardian.spread_v2_xgb.candidates import iter_transitions  # noqa: E402
from wildfireguardian.spread_v2_xgb.dataset import all_fires  # noqa: E402
from wildfireguardian.spread_v2_xgb.detections import (  # noqa: E402
    build_observed_sequence,
    load_detections,
)
from wildfireguardian.spread_v2_xgb.era5 import WeatherSeries  # noqa: E402
from wildfireguardian.spread_v2_xgb.grid import Grid, build_region  # noqa: E402
from wildfireguardian.spread_v2_xgb.layers import build_static_layers  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "processed" / "spread_v2" / "audit.json"


def audit_fire(fire) -> dict:
    region = build_region(fire)
    grid = Grid(region)

    df = load_detections(fire.detections_csv)
    seq = build_observed_sequence(fire.fire_id, df, grid)
    static = build_static_layers(fire, grid)

    n_cells = grid.nrows * grid.ncols
    n_inb = int(static.in_fuel_bounds.sum())
    n_gate = int(static.burnable_gate.sum())
    mean_bfrac = float(np.nanmean(static.burnable_frac_cell[static.in_fuel_bounds]))

    # Direct raster-level fuel coverage (fraction of fuel pixels that are NOT
    # nodata). This is the cleanest proof of the gangneung_donghae 5%→~100%
    # fix, independent of any grid/CRS-corner distortion.
    import rasterio  # local import keeps module import-time light
    with rasterio.open(fire.fuel_tif) as r:
        arr = r.read(1)
        nod = r.nodata if r.nodata is not None else 0
        fuel_raster_valid_frac = float((arr != nod).mean())

    transitions = iter_transitions(seq, static)
    total_cand = int(sum(t.rows.size for t in transitions))
    total_pos = int(sum(int(t.labels.sum()) for t in transitions))
    total_newly = int(sum(t.n_newly_total for t in transitions))
    total_newly_cap = int(sum(t.n_newly_captured for t in transitions))

    # ERA5
    era5_status = {"present": fire.has_era5}
    if fire.has_era5:
        try:
            ws = WeatherSeries.from_fire(fire)
            era5_status.update(ws.status())
        except Exception as exc:  # pragma: no cover
            era5_status.update({"present": True, "error": repr(exc)})
    else:
        era5_status["note"] = "0-byte / missing — weather handled as NaN downstream"

    return {
        "fire_id": fire.fire_id,
        "name_kr": fire.name_kr,
        "bbox_wgs84": list(fire.bbox_wgs84),
        "dates": [str(fire.start), str(fire.end)],
        "grid_shape": [grid.nrows, grid.ncols],
        "n_cells": n_cells,
        "detections_csv": int(len(df)),
        "detections_in_grid": int(seq.n_detections_in_grid),
        "n_overpasses_60min": int(seq.n_overpasses),
        "manifest_overpass_hours": int(fire.distinct_overpass_hours),
        "fuel_coverage_frac": round(n_inb / n_cells, 4),
        "fuel_raster_valid_frac": round(fuel_raster_valid_frac, 4),
        "burnable_gate_cells": n_gate,
        "burnable_gate_frac": round(n_gate / max(1, n_inb), 4),
        "mean_burnable_frac": round(mean_bfrac, 4),
        "manifest_burnable_frac": round(fire.burnable_frac, 4),
        "observed_area_ha": round(seq.observed_area_ha(), 1),
        "reported_ha": fire.reported_ha,
        "observed_vs_reported": round(seq.observed_area_ha() / fire.reported_ha, 3),
        "n_transitions": len(transitions),
        "total_candidates": total_cand,
        "total_positives": total_pos,
        "prevalence": round(total_pos / max(1, total_cand), 4),
        "spread_cells_total": total_newly,
        "spread_cells_captured_as_candidates": total_newly_cap,
        "capture_frac": round(total_newly_cap / max(1, total_newly), 3),
        "era5": era5_status,
    }


def main() -> None:
    np.random.seed(SEED)
    fires = all_fires()
    results = []
    # Process largest grids last is irrelevant; iterate manifest order.
    for fid, fire in fires.items():
        print(f"[audit] {fid} …", flush=True)
        try:
            results.append(audit_fire(fire))
        except Exception as exc:
            print(f"  !! {fid} failed: {exc!r}")
            results.append({"fire_id": fid, "error": repr(exc)})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"seed": SEED, "fires": results}, indent=2))

    # ---- Printed summary table ----
    cols = [
        ("fire_id", 22), ("det", 6), ("in_grid", 8), ("ovp", 4),
        ("cells", 7), ("fuelcov", 8), ("burn%", 7), ("man_burn", 9),
        ("obs_ha", 8), ("rep_ha", 7), ("trans", 6),
        ("cand", 8), ("POS", 6), ("prev", 7), ("cap%", 6), ("era5", 6),
    ]
    print("\n" + "=" * 130)
    print("DELIVERABLE 0 — AUDIT")
    print("=" * 130)
    print("".join(h.ljust(w) for h, w in cols))
    print("-" * 130)
    for r in results:
        if "error" in r:
            print(f"{r['fire_id']:22s} ERROR {r['error']}")
            continue
        row = [
            r["fire_id"], r["detections_csv"], r["detections_in_grid"],
            r["n_overpasses_60min"], r["n_cells"], r["fuel_coverage_frac"],
            r["burnable_gate_frac"], r["manifest_burnable_frac"],
            r["observed_area_ha"], r["reported_ha"], r["n_transitions"],
            r["total_candidates"], r["total_positives"], r["prevalence"],
            r["capture_frac"], "Y" if r["era5"]["present"] else "—",
        ]
        print("".join(str(v).ljust(w) for v, (_, w) in zip(row, cols)))
    print("-" * 130)

    by_id = {r["fire_id"]: r for r in results if "error" not in r}
    print("\nHEADLINE CHECKS")
    if "uljin_samcheok_2022" in by_id:
        u = by_id["uljin_samcheok_2022"]
        print(f"  uljin_samcheok_2022 POSITIVES = {u['total_positives']}  "
              f"(target ≈ 880; prior buggy run ≈ 120)")
        print(f"  uljin ERA5 = {u['era5']}")
    if "gangneung_donghae_2022" in by_id:
        g = by_id["gangneung_donghae_2022"]
        print(f"  gangneung_donghae_2022 burnable_gate_frac = {g['burnable_gate_frac']}, "
              f"mean_burnable_frac = {g['mean_burnable_frac']} (manifest {g['manifest_burnable_frac']}; was ~0.05)")
        print(f"  gangneung_donghae_2022 ERA5 present = {g['era5']['present']} "
              f"(expected missing/0-byte)")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
