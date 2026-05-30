"""Session 6 integrated Yeongdeok ablation: surface → +topo → +crown → +spotting.

Each row adds ONE physics module so we can attribute every change. Run::

    python scripts/run_ablation.py [a b c d]

Honesty: this reports per-horizon front accuracy (area-capture, IoU,
front-position error) for each configuration. No tuning to a target.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np

from wildfireguardian.data_io.weather import load_aws_wind
from wildfireguardian.spread_model.rothermel import KOREAN_PINUS, compute_spread_rate
from wildfireguardian.spread_model.wind import korean_pine_waf, midflame_wind
from wildfireguardian.utils.regions import YEONGDEOK_2025
from wildfireguardian.validation import ModelConfig, load_case, run_validation_with_baselines

HORIZONS = (60.0, 180.0, 360.0, 720.0, 1440.0)


def _ambient_10m() -> tuple[float, float]:
    s = load_aws_wind(YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)), source="auto")
    smp = [s.at(datetime(2025, 3, 22, h, 0)) for h in range(12, 24)]
    return float(np.mean([x.speed_10m_ms for x in smp])), float(np.mean([x.direction_from_deg for x in smp]))


# Session 7: crown_foliar_moisture_pct=119 is the MEASURED Korean value
# (Lee et al. 2018) — the physically-correct tree-crown moisture. Session 6
# used None (= the surface drought-LFMC 40%), which was the conflation bug
# that produced the artifact 54% capture. With the corrected 119%, crown
# fire barely triggers (capture ~9%). Set CROWN_FMC=None below to reproduce
# the Session-6 (buggy) numbers for provenance.
CROWN_FMC = 119.0
CONFIGS = {
    "a_uniform_surface": dict(use_topographic_wind=False),
    "b_topo_surface": dict(use_topographic_wind=True),
    "c_topo_crown": dict(use_topographic_wind=True, use_crown_fire=True,
                         crown_foliar_moisture_pct=CROWN_FMC),
    "d_topo_crown_spot": dict(use_topographic_wind=True, use_crown_fire=True,
                              use_spotting=True, crown_foliar_moisture_pct=CROWN_FMC),
}


def build_cfg(extra: dict, u10: float, wind_dir: float, waf: float) -> ModelConfig:
    u_mid = midflame_wind(u10, waf)
    r_steady = compute_spread_rate(KOREAN_PINUS, dead_moisture=0.08,
                                   live_moisture=0.40, wind_speed_ms=u_mid).rate_m_min
    return ModelConfig(
        cell_size_m=50.0, wind_speed_midflame_ms=u_mid, wind_from_deg=wind_dir,
        wind_10m_ms=u10, waf=waf,
        dead_moisture_1h=0.08, live_moisture_lfmc=0.40, residence_time_min=60.0,
        duration_min=1440.0, dt_min=1.0, snapshot_every_min=60.0,
        dem_source="srtm", fuel_source="synthetic",
        ignition_radius_m=r_steady * 15.0, **extra,
    )


def main() -> None:
    args = sys.argv[1:]
    alias = {"a": "a_uniform_surface", "b": "b_topo_surface",
             "c": "c_topo_crown", "d": "d_topo_crown_spot"}
    which = [alias.get(x, x) for x in args] or list(CONFIGS)
    repo = Path(__file__).resolve().parents[1]
    case = load_case(repo / "data" / "validation_cases" / "yeongdeok_2025.json")
    u10, wind_dir = _ambient_10m()
    waf = korean_pine_waf()
    print(f"ambient 10-m {u10:.1f} m/s from {wind_dir:.0f}°; WAF {waf:.3f} → "
          f"uniform midflame {midflame_wind(u10, waf):.2f} m/s\n")

    results = {}
    for name in which:
        cfg = build_cfg(CONFIGS[name], u10, wind_dir, waf)
        res = run_validation_with_baselines(case, cfg, horizons_min=HORIZONS)
        results[name] = res
        # crown/active fraction if grid recorded it
        print(f"=== {name} ===")
        if "crown_active_frac" in res.data_provenance:
            print(f"  regime among burned: active-crown "
                  f"{res.data_provenance['crown_active_frac']*100:.0f}%, "
                  f"passive {res.data_provenance['crown_passive_frac']*100:.0f}%, "
                  f"surface {res.data_provenance['surface_frac']*100:.0f}%")
        print(f"{'h':>4} {'pred_ha':>8} {'obs_ha':>8} {'capture':>8} {'IoU':>6} {'front_mean_m':>12}")
        for hm in res.metrics_model:
            cap = hm.fraction_observed_captured
            print(f"{hm.horizon_min/60:>4.0f} {hm.predicted_area_ha:>8.0f} "
                  f"{hm.observed_area_ha:>8.0f} "
                  f"{(f'{cap*100:.0f}%' if cap==cap else 'NA'):>8} "
                  f"{(hm.iou or 0):>6.3f} {(hm.front_mean_boundary_m or float('nan')):>12.0f}")
        print()

    out = repo / "data" / "processed" / "yeongdeok_2025_ablation.json"
    out.write_text(json.dumps({k: v.as_dict() for k, v in results.items()},
                              indent=2, default=str))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
