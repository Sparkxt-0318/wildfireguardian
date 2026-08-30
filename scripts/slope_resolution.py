#!/usr/bin/env python
"""Is the 500 m grid attenuating slope? (Session 12 Phase 1 — GATE)

Mean slope across the Session 11 label steps was 6.28 deg with a maximum of
13.34, in 울진·삼척 and 경북 mountain terrain. That is implausibly gentle, and
there are two smoothing steps that could explain it: elevation is AVERAGED from
~30 m SRTM into 500 m cells, and the gradient is then taken over a 500 m
baseline. This script measures how much relief those two steps remove, and
re-runs the Session 11 slope-conditioning result on the native-resolution
slope to see whether the one robust directional finding survives.

    python scripts/slope_resolution.py --write

Writes docs/slope_resolution.json. Changes no model, target or Arm A artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

OUT = REPO / "docs" / "slope_resolution.json"

#: Rothermel (1972) derived the slope factor from 12 laboratory fires at these
#: three angles. Everything measured here sits below the lowest of them.
ROTHERMEL_CALIBRATION_DEG = (14.0, 26.6, 36.9)


def dist(a: np.ndarray) -> dict:
    v = np.asarray(a, dtype="float64")
    v = v[np.isfinite(v)]
    if not len(v):
        return {"n": 0}
    q25, q75 = np.percentile(v, [25, 75])
    return {
        "n": int(len(v)),
        "mean": round(float(v.mean()), 3),
        "median": round(float(np.median(v)), 3),
        "iqr": round(float(q75 - q25), 3),
        "p25": round(float(q25), 3), "p75": round(float(q75), 3),
        "p90": round(float(np.percentile(v, 90)), 3),
        "max": round(float(v.max()), 3),
    }


def per_fire(fid: str) -> dict:
    from wildfireguardian.spread_v2 import data as datamod
    from wildfireguardian.spread_v2 import grid as gridmod
    from wildfireguardian.spread_v2_arme.terrain import (
        DEFAULT_SUBDIVISION, native_slope_stats)

    ev = datamod.load_event(fid)
    g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=gridmod.DEFAULT_CELL_M)
    elev = gridmod.elevation_on_grid(ev, g)
    slope500 = gridmod.slope_deg(elev, g.cell_size_m)
    nat = native_slope_stats(ev, g, DEFAULT_SUBDIVISION)

    # Restrict to cells the analysis actually touches: burnable land, not sea.
    land = np.isfinite(elev) & (elev > 5.0)
    out = {
        "fire_id": fid,
        "grid": {"nrows": g.nrows, "ncols": g.ncols,
                 "cell_size_m": g.cell_size_m,
                 "subdivision": DEFAULT_SUBDIVISION,
                 "fine_cell_m": round(g.cell_size_m / DEFAULT_SUBDIVISION, 3)},
        "n_land_cells": int(land.sum()),
        "slope_500m_baseline": dist(slope500[land]),
        "slope_native_mean": dist(nat["mean"][land]),
        "slope_native_median": dist(nat["median"][land]),
        "slope_native_p90": dist(nat["p90"][land]),
        "slope_native_max": dist(nat["max"][land]),
        "slope_native_effective": dist(nat["effective"][land]),
        "within_cell_iqr": dist(nat["iqr"][land]),
    }
    a = out["slope_500m_baseline"]["mean"]
    for key in ("mean", "effective", "p90", "max"):
        b = out[f"slope_native_{key}"]["mean"]
        out[f"attenuation_vs_native_{key}"] = {
            "native_over_500m": round(b / a, 3) if a > 1e-9 else None,
            "difference_deg": round(b - a, 3),
        }
    return out


def slope_conditioning_both(fires_native: dict) -> dict:
    """Re-run Session 11 Phase 5d with each slope definition, same 36 steps."""
    import direction_drivers as dd

    committed = json.loads(
        (REPO / "data/processed/spread_v2_lofo.json").read_text(encoding="utf-8"))
    fire_ids = sorted(committed["per_fire_auc"])
    model_pos = dd.model_positive_cells(fire_ids)

    results = {}
    for label, override in (("slope_500m_baseline", None),
                            ("slope_native_effective", fires_native)):
        fires = [dd.analyse_fire(f, model_pos,
                                 slope_field=None if override is None else override[f])
                 for f in fire_ids]
        results[label] = {
            "pooled_mean_slope_deg": dd.summarise(fires, "all")["pooled"]["mean_slope_deg"],
            "slope_conditioning": dd.slope_conditioning(fires, "all"),
        }
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from wildfireguardian.spread_v2 import data as datamod
    from wildfireguardian.spread_v2 import grid as gridmod
    from wildfireguardian.spread_v2_arme.terrain import (
        DEFAULT_SUBDIVISION, native_slope_stats)

    committed = json.loads(
        (REPO / "data/processed/spread_v2_lofo.json").read_text(encoding="utf-8"))
    fire_ids = sorted(committed["per_fire_auc"])

    fires = [per_fire(f) for f in fire_ids]

    # The effective-slope field per fire, for the conditioning re-run.
    native_fields = {}
    for fid in fire_ids:
        ev = datamod.load_event(fid)
        g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=gridmod.DEFAULT_CELL_M)
        native_fields[fid] = native_slope_stats(ev, g, DEFAULT_SUBDIVISION)["effective"]

    cond = slope_conditioning_both(native_fields)

    all_500 = float(np.mean([f["slope_500m_baseline"]["mean"] for f in fires]))
    all_eff = float(np.mean([f["slope_native_effective"]["mean"] for f in fires]))
    all_max = float(np.mean([f["slope_native_max"]["mean"] for f in fires]))

    payload = {
        "schema_version": 1,
        "title": "Slope resolution — 500 m baseline vs native ~30 m SRTM",
        "provenance": "derived",
        "arm": "A_geometry",
        "generated_by": "scripts/slope_resolution.py",
        "aggregation_choice": {
            "primary": "slope_native_effective",
            "definition": "arctan(sqrt(mean(tan(phi)^2))) over the sub-cells",
            "justification": (
                "Rothermel's slope factor is quadratic in tan(phi), so by Jensen's "
                "inequality the MEAN slope of a heterogeneous cell understates that "
                "cell's mean slope forcing. The effective slope is the single angle "
                "whose forcing equals the cell's mean forcing, so it is the aggregate "
                "that preserves the physics. Mean, median, IQR, p90 and max are all "
                "reported so the choice is visible rather than buried."),
            "not_max_because": (
                "The maximum of ~256 sub-cells is an extreme-value statistic: it rises "
                "with subdivision count and is dominated by DEM noise, so it measures "
                "the sampling rather than the terrain."),
        },
        "rothermel_calibration_deg": list(ROTHERMEL_CALIBRATION_DEG),
        "calibration_warning": (
            "Rothermel (1972) derived phi_s from 12 laboratory fires at 14.0, 26.6 and "
            "36.9 deg. EVERY slope measured here, at either resolution, sits BELOW the "
            "lowest calibrated angle, so the slope function is extrapolated downward "
            "throughout. This bounds how much slope forcing can be expected at all."),
        "pooled_over_fires": {
            "slope_500m_baseline_mean_deg": round(all_500, 3),
            "slope_native_effective_mean_deg": round(all_eff, 3),
            "slope_native_max_mean_deg": round(all_max, 3),
            "attenuation_factor_effective_over_500m": round(all_eff / all_500, 3),
            "fraction_of_lowest_rothermel_angle": round(
                all_eff / ROTHERMEL_CALIBRATION_DEG[0], 3),
        },
        "fires": fires,
        "slope_conditioning_recomputed": cond,
    }

    if args.write:
        OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}")

    print("\n=== per fire: land-cell slope (deg) ===")
    for f in fires:
        b = f["slope_500m_baseline"]; e = f["slope_native_effective"]
        m = f["slope_native_max"]
        print(f"  {f['fire_id']:24s} 500m mean={b['mean']:>6} med={b['median']:>6} "
              f"max={b['max']:>6} | native_eff mean={e['mean']:>6} med={e['median']:>6} "
              f"max={e['max']:>6} | native_max mean={m['mean']:>6} "
              f"| x{f['attenuation_vs_native_effective']['native_over_500m']}")
    print(f"\n  POOLED 500m={all_500:.2f} deg  native_effective={all_eff:.2f} deg  "
          f"x{all_eff/all_500:.2f}  (lowest Rothermel angle = 14.0 deg)")
    print("\n=== slope conditioning, same 36 steps, two slope definitions ===")
    for label, r in cond.items():
        sc = r["slope_conditioning"]
        print(f"  {label}:")
        print(f"    pooled mean slope = {r['pooled_mean_slope_deg']['mean']} deg, "
              f"median split at {sc['median_slope_deg']}")
        print(f"    gentle={sc['gentler_half']['mean_abs_angle_deg']} deg  "
              f"steep={sc['steeper_half']['mean_abs_angle_deg']} deg  "
              f"corr={sc['corr_slope_vs_angle']}")
        print(f"    terciles={[t['mean_abs_angle_deg'] for t in sc['terciles']]}")
        wf = {k: v.get('corr_slope_vs_angle') for k, v in
              sc["within_fire_control"].items() if 'corr_slope_vs_angle' in v}
        print(f"    within-fire corr={wf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
