"""Session 7 Deliverable 2: sensitivity of area-capture to CBH × surface load.

Holds foliar moisture at the corrected/measured value (default 119%; also
runs 40% for the Session-6 contrast). Sweeps canopy base height and surface
fine-fuel load across plausible Korean pine ranges and reports 24h
area-capture % and IoU vs the observed-approx perimeter.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import numpy as np
from pyproj import Transformer

from wildfireguardian.data_io.raster import load_dem, load_fuel_type, populate_firegrid
from wildfireguardian.data_io.weather import load_aws_wind
from wildfireguardian.spread_model.cellular_automaton import (
    CellState, FireGrid, GriddedWindField,
)
from wildfireguardian.spread_model.rothermel import KOREAN_PINUS, compute_spread_rate
from wildfireguardian.spread_model.rothermel.fuel_model import FuelClass, FuelClassKind
from wildfireguardian.spread_model.topo_wind import topographic_wind_field
from wildfireguardian.spread_model.wind import korean_pine_waf, midflame_wind
from wildfireguardian.utils import units as U
from wildfireguardian.utils.regions import YEONGDEOK_2025
from wildfireguardian.validation import load_case
from wildfireguardian.validation.harness import load_observed_perimeter_series
from wildfireguardian.validation.metrics import (
    fraction_of_observed_captured, perimeter_iou,
)

CELL, DURATION, DT = 50.0, 1440.0, 1.0
CBH_VALUES = (2.0, 3.0, 4.0, 5.0)
LOAD_VALUES = (0.5, 0.7, 0.9)   # total fine-fuel load kg/m²
LIVE_KG = 0.15                  # KP live understory load (held)


def make_kp_variant(cbh_m: float, fine_load_kg_m2: float):
    """KOREAN_PINUS variant with given CBH and target fine load (scale 1-h dead)."""
    dead1h_kg = max(0.05, fine_load_kg_m2 - LIVE_KG)
    parts = []
    for p in KOREAN_PINUS.particles:
        if p.kind is FuelClassKind.DEAD_1H:
            parts.append(FuelClass(p.kind, w_o=dead1h_kg * U.LBFT2_PER_KGM2, sigma=p.sigma))
        else:
            parts.append(p)
    return replace(KOREAN_PINUS, particles=tuple(parts), canopy_base_height_m=cbh_m)


def _ambient():
    s = load_aws_wind(YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)), source="auto")
    smp = [s.at(datetime(2025, 3, 22, h, 0)) for h in range(12, 24)]
    return float(np.mean([x.speed_10m_ms for x in smp])), float(np.mean([x.direction_from_deg for x in smp]))


def run_one(cbh, load, fmc, dem, u10, wdir, waf, obs_final):
    fm = make_kp_variant(cbh, load)
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=CELL, residence_time_min=60.0)
    grid.elevation_m[:] = dem.values
    from wildfireguardian.data_io.raster import compute_slope_aspect
    sl, asp = compute_slope_aspect(dem.values, CELL)
    grid.slope_degrees[:] = sl
    grid.aspect_degrees[:] = asp
    grid.fuel_model_id[:] = fm
    grid.fuel_moisture[:] = 0.40
    grid.enable_crown_fire = True
    grid.crown_foliar_moisture_pct = fmc
    u10f, thf = topographic_wind_field(u10, (wdir + 180) % 360, grid.elevation_m, CELL)
    wind = GriddedWindField.from_topographic(u10f, thf, waf)
    rst = compute_spread_rate(KOREAN_PINUS, dead_moisture=0.08, live_moisture=0.40,
                              wind_speed_ms=midflame_wind(u10, waf)).rate_m_min
    t = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    x, y = t.transform(129.37, 36.50)
    a, _b, c, _d, e, f = grid.affine
    grid.ignite_disc(int((y - f) / e), int((x - c) / a), radius_m=rst * 15.0)
    tt = 0.0
    while tt < DURATION - 1e-9:
        grid.step(DT, wind, current_time_min=tt)
        tt += DT
    burned = grid.state >= CellState.BURNING
    nb = int(burned.sum())
    active = int((grid.regime[burned] == 2).sum())
    peri = grid.perimeter()
    iou = perimeter_iou(peri, obs_final)
    cap = fraction_of_observed_captured(peri, obs_final)
    return dict(cbh=cbh, load=load, fmc=fmc, burned=nb, active_frac=active / max(nb, 1),
                area_ha=nb * CELL * CELL / 1e4, iou=iou, capture=cap)


def main():
    fmcs = [float(x) for x in sys.argv[1:]] or [119.0]
    repo = Path(__file__).resolve().parents[1]
    case = load_case(repo / "data" / "validation_cases" / "yeongdeok_2025.json")
    obs = load_observed_perimeter_series(case)
    obs_final = min(obs, key=lambda p: abs(p.time_min - 1440.0)).polygon
    dem = load_dem(YEONGDEOK_2025, source="srtm", cell_size_m=CELL, use_cache=True)
    u10, wdir = _ambient()
    waf = korean_pine_waf()

    all_rows = []
    for fmc in fmcs:
        print(f"\n========== crown foliar moisture = {fmc:.0f}% ==========")
        header = "CBH\\load"
        print(f"{header:>8} " + " ".join(f"{l:>14.1f}" for l in LOAD_VALUES))
        for cbh in CBH_VALUES:
            cells = []
            for load in LOAD_VALUES:
                r = run_one(cbh, load, fmc, dem, u10, wdir, waf, obs_final)
                all_rows.append(r)
                cells.append(f"{r['capture']*100:4.0f}% IoU{r['iou']:.2f}")
            print(f"{cbh:>6.0f}m  " + " ".join(f"{c:>14}" for c in cells))
        caps = [r["capture"] for r in all_rows if r["fmc"] == fmc]
        print(f"  capture range at FMC {fmc:.0f}%: {min(caps)*100:.0f}% – {max(caps)*100:.0f}%")

    out = repo / "data" / "processed" / "crown_sensitivity.json"
    out.write_text(json.dumps(all_rows, indent=1, default=float))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
