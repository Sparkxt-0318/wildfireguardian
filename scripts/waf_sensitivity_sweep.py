"""WAF sensitivity sweep on the Yeongdeok 2025 validation.

Companion to ``run_yeongdeok_validation.py``. That script fixes the Wind
Adjustment Factor at ``korean_pine_waf()`` (Andrews 2012, sheltered
regime). This script re-runs the same case at a small grid of WAF values —
``{0.10, 0.13, 0.16, 0.20}`` — holding everything else fixed, to show how
sensitive the surface Rothermel baseline and its crown-transition margin
are to the WAF choice.

Held fixed across the sweep:
- Canopy base height (CBH): read from
  ``rothermel.fuel_model.KOREAN_PINUS.canopy_base_height_m`` — the single
  source of truth for CBH (currently 4.4 m, the nominal midpoint of the
  Lee et al. 2018 Gyeongbuk measured range, 3.6-5.2 m — not itself a
  measured value). There is no longer a second, separately-maintained CBH
  constant in ``crown_fire`` — this script and every other consumer read
  the same fuel-model value.
- Foliar moisture content (FMC): 119 % — matches
  ``crown_fire.KOREAN_PINE_FOLIAR_MOISTURE_PCT`` exactly.
- Dead 1-h moisture 8 %, LFMC 40 %, cell 50 m, dt 1 min, 24 h duration —
  same as ``run_yeongdeok_validation.py``.

For each WAF this records:
- midflame wind (m/s)
- mean / max Byram surface fireline intensity I_B (kW/m) over every cell
  the fire ever occupied (read from ``FireGrid._R_cache``, the cached
  per-cell Rothermel rate-of-spread — see ``grid=grid`` now returned by
  ``run_validation_with_baselines``)
- the fraction of those cells whose I_B reaches the Van Wagner (1977)
  critical crowning intensity I_o at the fixed CBH/FMC above
- 24-h area capture (%) and footprint IoU vs the observed perimeter

Output: ``data/processed/waf_sensitivity.json``.

Run::

    python scripts/waf_sensitivity_sweep.py
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np

from wildfireguardian.data_io.weather import load_aws_wind
from wildfireguardian.spread_model.crown_fire import (
    KOREAN_PINE_FOLIAR_MOISTURE_PCT,
    KOREAN_PINE_HEAT_KJ_KG,
    byram_intensity,
    critical_surface_intensity,
)
from wildfireguardian.spread_model.rothermel import KOREAN_PINUS, compute_spread_rate
from wildfireguardian.spread_model.wind import korean_pine_waf, midflame_wind
from wildfireguardian.utils.regions import YEONGDEOK_2025
from wildfireguardian.validation import ModelConfig, load_case, run_validation_with_baselines

# ----- fixed sweep conditions (per the task) -----
WAF_VALUES: tuple[float, ...] = (0.10, 0.13, 0.16, 0.20)
#: Nominal CBH — single source of truth, read from the fuel model rather
#: than a separately-maintained literal. Not itself a measured value; see
#: the comment on ``KOREAN_PINUS.canopy_base_height_m``.
CBH_NOMINAL_M: float = KOREAN_PINUS.canopy_base_height_m
FMC_PCT: float = 119.0                  # matches KOREAN_PINE_FOLIAR_MOISTURE_PCT


def _mean_10m_wind_mar22_evening() -> tuple[float, float]:
    """Mean 10-m wind speed + dominant from-direction over the peak window.

    Duplicated from ``run_yeongdeok_validation.py`` rather than imported,
    since that module's logic lives inside ``main()`` and isn't exported.
    """
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)), source="auto",
    )
    samples = [series.at(datetime(2025, 3, 22, h, 0)) for h in range(12, 24)]
    speeds = [s.speed_10m_ms for s in samples]
    dirs = [s.direction_from_deg for s in samples]
    return float(np.mean(speeds)), float(np.mean(dirs))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    case = load_case(repo_root / "data" / "validation_cases" / "yeongdeok_2025.json")

    u10, wind_dir = _mean_10m_wind_mar22_evening()
    print(f"mean 10-m wind Mar 22 12-24 KST: {u10:.2f} m/s from {wind_dir:.0f}°")

    # --- check the actual WAF/CBH/FMC values currently in the repo ---
    waf_default = korean_pine_waf()
    print(f"\ncurrent korean_pine_waf() (Andrews 2012, sheltered, repo default): "
          f"{waf_default:.4f}")
    print(f"current rothermel.fuel_model.KOREAN_PINUS.canopy_base_height_m "
          f"(single source of truth for CBH): "
          f"{CBH_NOMINAL_M} m  (this sweep uses it directly)")
    print(f"current crown_fire.KOREAN_PINE_FOLIAR_MOISTURE_PCT: "
          f"{KOREAN_PINE_FOLIAR_MOISTURE_PCT} %  (sweep uses {FMC_PCT} %, "
          f"matches)")

    i_o = critical_surface_intensity(CBH_NOMINAL_M, FMC_PCT)
    fine_load = KOREAN_PINUS.fine_fuel_load_kg_m2
    print(f"\nVan Wagner I_o at CBH={CBH_NOMINAL_M} m, "
          f"FMC={FMC_PCT}%: {i_o:.1f} kW/m")

    results: list[dict] = []
    for waf in WAF_VALUES:
        u_mid = midflame_wind(u10, waf)

        r_mid = compute_spread_rate(
            KOREAN_PINUS, dead_moisture=0.08, live_moisture=0.40,
            wind_speed_ms=u_mid,
        )
        r_steady = r_mid.rate_m_min
        ignition_radius_m = r_steady * 15.0  # same convention as run_yeongdeok_validation.py

        cfg = ModelConfig(
            cell_size_m=50.0,
            wind_speed_midflame_ms=u_mid,
            wind_from_deg=wind_dir,
            dead_moisture_1h=0.08,
            live_moisture_lfmc=0.40,
            residence_time_min=60.0,
            duration_min=1440.0,
            dt_min=1.0,
            snapshot_every_min=60.0,
            dem_source="srtm",
            fuel_source="synthetic",
            ignition_radius_m=ignition_radius_m,
        )

        print(f"\n--- WAF={waf:.2f}  midflame={u_mid:.2f} m/s ---")
        res = run_validation_with_baselines(case, cfg, horizons_min=(1440.0,))

        # Per-cell Byram intensity from the cached Rothermel rate for every
        # cell the fire ever occupied (FireGrid._R_cache: {(i,j): (R_max,
        # ecc, wind_dir_to_deg)}).
        r_values_m_min = [v[0] for v in res.grid._R_cache.values()]
        i_b_values = [
            byram_intensity(r, fine_load, KOREAN_PINE_HEAT_KJ_KG)
            for r in r_values_m_min
        ]
        if i_b_values:
            mean_i_b = float(np.mean(i_b_values))
            max_i_b = float(np.max(i_b_values))
            frac_exceed_io = float(np.mean(np.array(i_b_values) >= i_o))
        else:
            mean_i_b = max_i_b = frac_exceed_io = float("nan")

        hm = res.metrics_model[-1]  # 1440-min horizon
        area_capture_pct = (
            hm.fraction_observed_captured * 100.0
            if hm.fraction_observed_captured is not None else None
        )

        row = {
            "waf": waf,
            "midflame_wind_ms": u_mid,
            "mean_byram_intensity_kw_m": mean_i_b,
            "max_byram_intensity_kw_m": max_i_b,
            "frac_cells_exceeding_Io": frac_exceed_io,
            "area_capture_24h_pct": area_capture_pct,
            "footprint_iou_24h": hm.iou,
            "n_cells_ever_burning": len(r_values_m_min),
        }
        results.append(row)
        print(f"  mean I_B={mean_i_b:.1f} kW/m  max I_B={max_i_b:.1f} kW/m  "
              f"frac>=I_o={frac_exceed_io:.3f}  "
              f"24h capture={area_capture_pct if area_capture_pct is not None else float('nan'):.1f}%  "
              f"IoU={(hm.iou or 0):.3f}")

    out_path = repo_root / "data" / "processed" / "waf_sensitivity.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "held_fixed": {
            "cbh_m": CBH_NOMINAL_M,
            "fmc_pct": FMC_PCT,
            "I_o_kw_m": i_o,
            "u_10m_ms": u10,
            "wind_from_deg": wind_dir,
            "dead_moisture_1h": 0.08,
            "live_moisture_lfmc": 0.40,
            "cell_size_m": 50.0,
            "duration_min": 1440.0,
        },
        "repo_current_values": {
            "korean_pine_waf_default": waf_default,
            "crown_fire_KOREAN_PINE_FOLIAR_MOISTURE_PCT": KOREAN_PINE_FOLIAR_MOISTURE_PCT,
            "rothermel_fuel_model_KOREAN_PINUS_canopy_base_height_m": (
                KOREAN_PINUS.canopy_base_height_m
            ),
        },
        "sweep": results,
    }, indent=2, default=str))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
