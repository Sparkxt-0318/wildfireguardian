"""Production Yeongdeok 2025 validation run — writes the headline artifact.

Run::

    python scripts/run_yeongdeok_validation.py

Output: ``data/processed/yeongdeok_2025_validation_results.json``.

This is the script the writeup cites as the source of the headline
validation numbers. Every input is provenance-tagged in the output JSON.

Configuration (fixed for reproducibility)
----------------------------------------

- DEM source: SRTM (real, NASA SRTMGL1 1-arc-second)
- Fuel source: synthetic (100% Korean Pinus analog — KFS 임상도 pending Round 2)
- Wind: synthetic-historical reconstruction of March 22-24 KST conditions
  (mean midflame over Mar 22 12:00-24:00 KST, ~4 m/s)
- LFMC: 40 % (KFS post-event field estimate)
- Dead 1-h: 8 % (drought-ish spring)
- Cell size: 100 m
- Residence time: 60 min (defensible for Korean Pinus mixed dead+live load)
- Duration: 24 h
- dt: 1 min
- Snapshot: 60 min
- Horizons: 1 h, 3 h, 6 h, 24 h
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np

from wildfireguardian.data_io.weather import load_aws_wind
from wildfireguardian.utils.regions import YEONGDEOK_2025
from wildfireguardian.validation import (
    ModelConfig,
    load_case,
    run_validation_with_baselines,
)


def _mean_midflame_wind_mar22_evening() -> tuple[float, float]:
    """Mean midflame wind speed + dominant from-direction over the peak window."""
    series = load_aws_wind(
        YEONGDEOK_2025,
        (date(2025, 3, 22), date(2025, 3, 22)),
        source="auto",
    )
    # Mar 22 12:00 – 24:00 KST — the wind-driven phase
    samples = [series.midflame_at(datetime(2025, 3, 22, h, 0)) for h in range(12, 24)]
    speeds = [s[0] for s in samples]
    dirs = [s[1] for s in samples]
    return float(np.mean(speeds)), float(np.mean(dirs))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    case = load_case(repo_root / "data" / "validation_cases" / "yeongdeok_2025.json")

    mf_speed, mf_dir = _mean_midflame_wind_mar22_evening()
    print(f"mean midflame wind Mar 22 12-24 KST (synthetic-historical): "
          f"{mf_speed:.2f} m/s from {mf_dir:.1f}°")

    # Session 4: principled disc-ignition radius = steady head rate × 15-min
    # sub-grid establishment phase (see docs/methodology/spread_warmup.md).
    # NOT tuned to the observed perimeter.
    from wildfireguardian.spread_model.rothermel import (
        KOREAN_PINUS, compute_spread_rate,
    )
    r_steady = compute_spread_rate(
        KOREAN_PINUS, dead_moisture=0.08, live_moisture=0.40,
        wind_speed_ms=mf_speed,
    ).rate_m_min
    ignition_radius_m = r_steady * 15.0
    print(f"principled ignition disc radius = R({r_steady:.1f} m/min) × 15 min "
          f"= {ignition_radius_m:.0f} m  "
          f"({3.14159 * ignition_radius_m**2 / 1e4:.1f} ha initial)")

    cfg = ModelConfig(
        cell_size_m=100.0,
        wind_speed_midflame_ms=mf_speed,
        wind_from_deg=mf_dir,
        dead_moisture_1h=0.08,
        live_moisture_lfmc=0.40,
        residence_time_min=60.0,        # Korean Pinus mixed dead+live, defensible
        duration_min=1440.0,
        dt_min=1.0,
        snapshot_every_min=60.0,
        dem_source="srtm",
        fuel_source="synthetic",
        ignition_radius_m=ignition_radius_m,
    )

    print("running validation with baselines (~30s)...")
    result = run_validation_with_baselines(
        case, cfg, horizons_min=(60.0, 180.0, 360.0, 1440.0),
    )

    # Pretty print headline numbers.
    print()
    print(f"mean head-fire rate (R_max at case conditions): "
          f"{result.mean_head_rate_m_min:.2f} m/min")
    print()
    print("Per-horizon IoU / Dice (our model vs persistence vs isotropic):")
    print(f"{'horizon':>10} {'pred_ha':>8} {'obs_ha':>8} "
          f"{'IoU_model':>10} {'IoU_pers':>10} {'IoU_iso':>10} "
          f"{'Dice_model':>10}")
    for hm, hp, hi in zip(result.metrics_model,
                          result.metrics_persistence,
                          result.metrics_isotropic):
        print(f"{hm.horizon_min:>10.0f} {hm.predicted_area_ha:>8.0f} "
              f"{hm.observed_area_ha:>8.0f} "
              f"{(hm.iou or 0):>10.3f} {(hp.iou or 0):>10.3f} "
              f"{(hi.iou or 0):>10.3f} {(hm.sorensen_dice or 0):>10.3f}")

    # Save full artifact.
    out_path = repo_root / "data" / "processed" / "yeongdeok_2025_validation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result.as_dict(), indent=2, default=str))
    print()
    print(f"wrote {out_path}")
    print()
    print("Honest reading of these numbers:")
    print("  - Our model's IoU at 24h vs the approximate observed: see above.")
    print("  - Persistence IoU should be ~0 (always tiny single cell).")
    print("  - Isotropic IoU shows what a wind-ignorant baseline captures.")
    print("  - These numbers are NOT against real KFS perimeter — that's Round 2.")
    print("  - DEM is REAL (SRTMGL1); wind + observed perimeter are SYNTHETIC.")


if __name__ == "__main__":
    main()
