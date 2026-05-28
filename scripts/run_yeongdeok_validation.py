"""Production Yeongdeok 2025 validation run — writes the headline artifact.

Run::

    python scripts/run_yeongdeok_validation.py

Output: ``data/processed/yeongdeok_2025_validation_results.json``.

Session 5 changes (mentor refocus):
- Wind now goes 10-m → **midflame** via the proper Andrews 2012 Wind
  Adjustment Factor (``spread_model.wind.korean_pine_waf``), not the
  ad-hoc 0.30 factor.
- Fuel is the literature-anchored Korean Pinus (live moisture measured;
  surface bed provisional).
- Reporting reframed around **per-horizon front accuracy** (fraction of
  observed area captured, front-position error) — NOT the 24 h total.
- The 24 h area is reported WITH and WITHOUT disc ignition to expose the
  Session-4 cancellation honestly.

Configuration (fixed for reproducibility):
- DEM: SRTM (real). Fuel raster: synthetic 100% Korean Pinus (KFS 임상도 pending).
- Wind: synthetic-historical March 2025 reconstruction (no KMA key), 10-m
  → midflame via WAF. Dead 1-h 8%; LFMC 40%. Cell 100 m; dt 1 min; 24 h.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np

from wildfireguardian.data_io.weather import load_aws_wind
from wildfireguardian.spread_model.rothermel import KOREAN_PINUS, compute_spread_rate
from wildfireguardian.spread_model.wind import korean_pine_waf, midflame_wind
from wildfireguardian.utils.regions import YEONGDEOK_2025
from wildfireguardian.validation import (
    ModelConfig,
    load_case,
    run_validation_with_baselines,
)


def _mean_10m_wind_mar22_evening() -> tuple[float, float]:
    """Mean 10-m wind speed + dominant from-direction over the peak window."""
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)), source="auto",
    )
    samples = [series.at(datetime(2025, 3, 22, h, 0)) for h in range(12, 24)]
    speeds = [s.speed_10m_ms for s in samples]
    dirs = [s.direction_from_deg for s in samples]
    return float(np.mean(speeds)), float(np.mean(dirs))


def _run(cfg: ModelConfig, case):
    return run_validation_with_baselines(
        case, cfg, horizons_min=(60.0, 180.0, 360.0, 720.0, 1440.0),
    )


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    case = load_case(repo_root / "data" / "validation_cases" / "yeongdeok_2025.json")

    # --- WIND: 10-m → midflame via Andrews 2012 WAF (the Session-5 fix) ---
    u10, wind_dir = _mean_10m_wind_mar22_evening()
    waf = korean_pine_waf()
    u_midflame = midflame_wind(u10, waf)
    print(f"mean 10-m wind Mar 22 12-24 KST: {u10:.2f} m/s from {wind_dir:.0f}°")
    print(f"Korean pine WAF (Andrews 2012, sheltered): {waf:.3f}")
    print(f"  → midflame wind = {u_midflame:.2f} m/s "
          f"(old ad-hoc 0.30 factor gave {u10*0.30:.2f} m/s)")

    # Wind factor (1 + φ_w) before vs after the WAF fix, for the report.
    r_mid = compute_spread_rate(KOREAN_PINUS, dead_moisture=0.08, live_moisture=0.40,
                                wind_speed_ms=u_midflame)
    r_raw = compute_spread_rate(KOREAN_PINUS, dead_moisture=0.08, live_moisture=0.40,
                                wind_speed_ms=u10)
    print(f"  wind factor (1+φ_w): WAF-corrected midflame = {1 + r_mid.phi_w:.2f}; "
          f"raw 10-m (the old bug) = {1 + r_raw.phi_w:.2f}")

    r_steady = r_mid.rate_m_min
    ignition_radius_m = r_steady * 15.0   # principled (Session 4), not tuned

    # Cell size must satisfy R·residence ≥ cell_size for the CA front to
    # propagate (a CFL-like resolution requirement). With the WAF-corrected
    # slow midflame wind, R·τ ≈ 1.4·60 ≈ 86 m, so 100 m cells (Session 4)
    # would artificially STALL the fire. We use 50 m here so we report the
    # surface model's true (slow) behaviour, not a discretisation artifact.
    base = dict(
        cell_size_m=50.0,
        wind_speed_midflame_ms=u_midflame,
        wind_from_deg=wind_dir,
        dead_moisture_1h=0.08,
        live_moisture_lfmc=0.40,
        residence_time_min=60.0,
        duration_min=1440.0,
        dt_min=1.0,
        snapshot_every_min=60.0,
        dem_source="srtm",
        fuel_source="synthetic",
    )

    # Run WITH disc ignition (warm-up physics) and WITHOUT (single-cell), to
    # expose the Session-4 cancellation between too-slow spread and disc
    # area injection.
    print("\nrunning validation (disc ignition) ...")
    res_disc = _run(ModelConfig(**base, ignition_radius_m=ignition_radius_m), case)
    print("running validation (single-cell, no disc) ...")
    res_point = _run(ModelConfig(**base, ignition_radius_m=0.0), case)

    print(f"\nmean head-fire rate at WAF-corrected midflame: {r_steady:.2f} m/min")
    print("\nPER-HORIZON FRONT ACCURACY (disc-ignition run):")
    print(f"{'h':>4} {'pred_ha':>8} {'obs_ha':>8} {'area_err':>9} "
          f"{'captured':>9} {'IoU':>6} {'front_mean_m':>12} {'front_haus_m':>12}")
    for hm in res_disc.metrics_model:
        ae = hm.area_error_frac
        cap = hm.fraction_observed_captured
        print(f"{hm.horizon_min/60:>4.0f} {hm.predicted_area_ha:>8.0f} "
              f"{hm.observed_area_ha:>8.0f} "
              f"{(f'{ae*100:+.0f}%' if ae is not None else 'NA'):>9} "
              f"{(f'{cap*100:.0f}%' if cap==cap else 'NA'):>9} "
              f"{(hm.iou or 0):>6.3f} "
              f"{(hm.front_mean_boundary_m or float('nan')):>12.0f} "
              f"{(hm.front_hausdorff_m or float('nan')):>12.0f}")

    # The cancellation, exposed: 24 h area with vs without disc.
    area24_disc = res_disc.metrics_model[-1].predicted_area_ha
    area24_point = res_point.metrics_model[-1].predicted_area_ha
    obs24 = res_disc.metrics_model[-1].observed_area_ha
    print(f"\n24 h burned area — observed-approx {obs24:.0f} ha")
    print(f"  WITH disc ignition:    {area24_disc:.0f} ha "
          f"({(area24_disc-obs24)/obs24*100:+.0f}%)")
    print(f"  WITHOUT (single-cell): {area24_point:.0f} ha "
          f"({(area24_point-obs24)/obs24*100:+.0f}%)")

    out_path = repo_root / "data" / "processed" / "yeongdeok_2025_validation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "wind": {
            "u_10m_ms": u10, "waf": waf, "u_midflame_ms": u_midflame,
            "wind_factor_midflame": 1 + r_mid.phi_w,
            "wind_factor_raw_10m_OLD_BUG": 1 + r_raw.phi_w,
        },
        "disc_ignition": res_disc.as_dict(),
        "single_cell": res_point.as_dict(),
        "cancellation_check": {
            "obs_24h_ha": obs24,
            "pred_24h_ha_with_disc": area24_disc,
            "pred_24h_ha_single_cell": area24_point,
        },
    }, indent=2, default=str))
    print(f"\nwrote {out_path}")
    print("\nHonest reading:")
    print("  - WAF cut the wind factor materially; spread is now slower and the")
    print("    surface model UNDER-predicts early front area (it cannot capture")
    print("    the crown/spotting run). The wind fix did NOT rescue early area.")
    print("  - The Session-4 24h '+25%' was disc-injection masking the slow front.")
    print("  - DEM real (SRTM); wind + fuel raster + observed perimeter synthetic/approx.")


if __name__ == "__main__":
    main()
