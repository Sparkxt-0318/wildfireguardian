"""PROTOCOL_v3 Amendment 1 item 4: fire-specific inputs by the recipe of the archived Fish Creek run.

The archive (demonstration/heat_spatial_maps/20261013_fishcreek) records its recipe in README.md and summary.json; its
generator script is not in the workspace. This module rebuilds the same quantities for any region with the pipeline's
own constructors. Run in the pipeline environment (workspace root on PYTHONPATH):

    python partb_inputs.py --check-fishcreek     # compare the recipe with the archived Fish Creek arrays
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

FALLBACK_FUEL_KG_M2 = 10.0                  # summary.json physical_assumptions.missing_fuel_fallback_kg_m2
FALLBACK_SAV_FT_INV = 2000.0                # README: unsupported/nonburnable codes use 2000 ft^-1
SPREAD_RATE_M_S = 0.09472222222222222       # summary.json physical_assumptions.spread_rate_m_s (341 m/h)
SPREAD_DIRECTION_DEG = 0.0
FLAMING_FRACTION = 0.1
HEAT_OF_COMBUSTION_J_KG = 18_000_000.0      # summary.json physical_assumptions.heat_of_combustion_j_kg


def build(region_dir, grid, shape, epsg):
    """Whole-cell scenario fuel, point residence, cell duration and flame height for one region."""
    from wildfire import CellBurningDuration, EcologicalFuelMaps, FlameResidenceTime
    from wildfire.flame_height import FlameHeightEstimate
    from wildfire.heat import CombustionParameters

    fuel_dir = Path(region_dir) / "fuel"
    maps = EcologicalFuelMaps.from_fccs_rasters(fuel_dir / "total_available_fuel_loading_tons_per_acre_375m.tif",
                                                fuel_dir / "fuel_loading_lookup_coverage_fraction_375m.tif",
                                                grid=grid, expected_shape=shape)
    mapped, cov = np.asarray(maps.fuel_load_kg_m2, float), np.asarray(maps.coverage_fraction, float)
    readable = np.isfinite(mapped) & np.isfinite(cov)
    fuel = np.where(readable, cov * np.where(readable, mapped, 0.0) + (1.0 - np.where(readable, cov, 0.0)) * FALLBACK_FUEL_KG_M2,
                    FALLBACK_FUEL_KG_M2)
    residence = FlameResidenceTime.from_fbfm40_raster(fuel_dir / "landfire_2016_fbfm40_375m.tif", grid=grid,
                                                      expected_shape=shape, epsg=epsg,
                                                      fallback_sav_m_inv=FALLBACK_SAV_FT_INV / 0.3048)
    cell = CellBurningDuration.from_front_crossing(residence, grid=grid, spread_rate_m_s=SPREAD_RATE_M_S,
                                                   spread_direction_deg=SPREAD_DIRECTION_DEG,
                                                   provenance={"recipe": "PROTOCOL_v3 Amendment 1 item 4",
                                                               "archive": "demonstration/heat_spatial_maps/20261013_fishcreek"})
    height = FlameHeightEstimate.from_combustion(
        CombustionParameters(fuel, HEAT_OF_COMBUSTION_J_KG, cell.duration_s, FLAMING_FRACTION),
        spread_rate_m_s=SPREAD_RATE_M_S, tilt_from_vertical_deg=0.)
    return dict(fuel_kg_m2=fuel, mapped_kg_m2=mapped, coverage=cov, residence=residence, cell=cell,
                flame_height_m=np.asarray(height.flame_height_m, float))


def check_fishcreek(workspace):
    from wildfire import AffineGrid
    ws = Path(workspace)
    region = ws / "data/environment/regions/WY-BTF-002416_FishCreek"
    z = np.load(ws / "demonstration/heat_spatial_maps/20261013_fishcreek/spatial_matrices.npz")
    v = np.load(ws / "demonstration/flame_danger/pipeline_verification.npz")
    grid = AffineGrid(tuple(float(x) for x in z["affine_transform"]))
    shape = z["whole_cell_scenario_fuel_kg_m2"].shape
    b = build(region, grid, shape, int(z["epsg"]))

    def cmp(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        both = np.isfinite(x) & np.isfinite(y)
        return {"n": int(x.size), "finite_pattern_equal": bool(np.array_equal(np.isfinite(x), np.isfinite(y))),
                "max_abs_diff": float(np.max(np.abs(x[both] - y[both]))) if both.any() else None,
                "max_rel_diff": float(np.max(np.abs(x[both] - y[both]) / np.maximum(np.abs(y[both]), 1e-300))) if both.any() else None,
                "exactly_equal": bool(np.array_equal(np.where(both, x, 0), np.where(both, y, 0)) and np.array_equal(np.isfinite(x), np.isfinite(y)))}
    out = {"whole_cell_scenario_fuel_kg_m2": cmp(b["fuel_kg_m2"], z["whole_cell_scenario_fuel_kg_m2"]),
           "reference_mapped_fuel_kg_m2": cmp(b["mapped_kg_m2"], z["reference_mapped_fuel_kg_m2"]),
           "reference_fuel_coverage_fraction": cmp(b["coverage"], z["reference_fuel_coverage_fraction"]),
           "residence_duration_s": cmp(b["residence"].duration_s, z["residence_duration_s"]),
           "cell_burning_duration_s": cmp(b["cell"].duration_s, z["cell_burning_duration_s"]),
           "flame_height_m_vs_pipeline_verification": cmp(b["flame_height_m"], v["flame_height_m"]),
           "fuel_vs_pipeline_verification": cmp(b["fuel_kg_m2"], v["fuel_load_kg_m2"])}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-fishcreek", action="store_true")
    ap.add_argument("--workspace", default=".")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.check_fishcreek:
        r = check_fishcreek(a.workspace)
        print(json.dumps(r, indent=1))
        if a.out:
            Path(a.out).write_text(json.dumps(r, indent=1))
