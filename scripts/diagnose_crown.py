"""Session 7 Deliverable 1: instrument the Yeongdeok crown run and reconcile.

Runs the Session-6 config-c (topo + crown) with the crown-transition logger
on, then reports the distribution of the quantities driving the Van Wagner
check for cells that did vs did not crown. Answers: why did 32% crown?
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import numpy as np

from wildfireguardian.data_io.raster import load_dem, load_fuel_type, populate_firegrid
from wildfireguardian.data_io.weather import load_aws_wind
from wildfireguardian.spread_model.cellular_automaton import (
    CellState, FireGrid, GriddedWindField,
)
from wildfireguardian.spread_model.rothermel import KOREAN_PINUS, compute_spread_rate
from wildfireguardian.spread_model.topo_wind import topographic_wind_field
from wildfireguardian.spread_model.wind import korean_pine_waf, midflame_wind
from wildfireguardian.utils.regions import YEONGDEOK_2025

CELL = 50.0
DURATION, DT = 1440.0, 1.0


def _ambient():
    s = load_aws_wind(YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)), source="auto")
    smp = [s.at(datetime(2025, 3, 22, h, 0)) for h in range(12, 24)]
    return float(np.mean([x.speed_10m_ms for x in smp])), float(np.mean([x.direction_from_deg for x in smp]))


def build_grid(crown_fmc: float | None):
    dem = load_dem(YEONGDEOK_2025, source="srtm", cell_size_m=CELL, use_cache=True)
    fuel = load_fuel_type(YEONGDEOK_2025, source="synthetic", cell_size_m=CELL, use_cache=True)
    grid = FireGrid.from_region(YEONGDEOK_2025, cell_size_m=CELL, residence_time_min=60.0)
    populate_firegrid(grid, dem, fuel_type=fuel, fuel_code_to_model={1: KOREAN_PINUS})
    grid.fuel_moisture[:] = 0.40
    grid.enable_crown_fire = True
    grid.crown_foliar_moisture_pct = crown_fmc      # None = Session-6 behaviour
    grid._crown_log = []
    return grid, dem


def run(crown_fmc, with_log=True):
    u10, wdir = _ambient()
    waf = korean_pine_waf()
    grid, dem = build_grid(crown_fmc)
    u10f, thf = topographic_wind_field(u10, (wdir + 180) % 360, grid.elevation_m, CELL)
    wind = GriddedWindField.from_topographic(u10f, thf, waf)
    # principled disc radius from Session 4 (not tuned)
    rst = compute_spread_rate(KOREAN_PINUS, dead_moisture=0.08, live_moisture=0.40,
                              wind_speed_ms=midflame_wind(u10, waf)).rate_m_min
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    x, y = t.transform(129.37, 36.50)
    a, _b, c, _d, e, f = grid.affine
    gi, gj = int((y - f) / e), int((x - c) / a)
    grid.ignite_disc(gi, gj, radius_m=rst * 15.0)
    tt = 0.0
    while tt < DURATION - 1e-9:
        grid.step(DT, wind, current_time_min=tt)
        tt += DT
    burned = grid.state >= CellState.BURNING
    nb = int(burned.sum())
    active = int((grid.regime[burned] == 2).sum())
    return grid, nb, active


def main():
    repo = Path(__file__).resolve().parents[1]
    print("=== Session-6 reproduction (crown FMC = surface LFMC 40%) ===")
    grid, nb, active = run(crown_fmc=None)
    log = grid._crown_log
    print(f"burned cells {nb}, active-crown {active} ({100*active/max(nb,1):.0f}%), "
          f"transition records {len(log)}")

    crowned = [r for r in log if r["regime"] == 2]
    notc = [r for r in log if r["regime"] != 2]

    def stats(rows, key):
        v = np.array([r[key] for r in rows]) if rows else np.array([0.0])
        return f"min {v.min():6.1f} | med {np.median(v):6.1f} | max {v.max():6.1f}"

    print(f"\n  CROWNED cells (n={len(crowned)}):")
    for k in ("R_surf", "midflame_ms", "u10_ms", "slope_deg", "I_B", "I_o", "fmc_pct"):
        print(f"    {k:12s}: {stats(crowned, k)}")
    print(f"  NON-crowned cells (n={len(notc)}):")
    for k in ("R_surf", "midflame_ms", "u10_ms", "slope_deg", "I_B", "I_o"):
        print(f"    {k:12s}: {stats(notc, k)}")

    # What fraction of crowned cells would crown on FLAT ground (slope<5)?
    flat_crowned = [r for r in crowned if r["slope_deg"] < 5.0]
    print(f"\n  crowned cells on near-flat ground (<5deg): {len(flat_crowned)}/{len(crowned)}")
    steep_crowned = [r for r in crowned if r["slope_deg"] >= 20.0]
    print(f"  crowned cells on steep ground (>=20deg): {len(steep_crowned)}/{len(crowned)}")
    hiwind = [r for r in crowned if r["midflame_ms"] > 2.0]
    print(f"  crowned cells with topo-boosted midflame >2 m/s: {len(hiwind)}/{len(crowned)}")

    # save the scatter data
    out = repo / "data" / "processed" / "crown_diagnostic_log.json"
    out.write_text(json.dumps(log, indent=1, default=float))
    print(f"\n  wrote {out} ({len(log)} records)")

    # Counterfactual: realistic crown FMC (measured 119%, and a drought 90%)
    print("\n=== Counterfactual: realistic crown foliar moisture (decoupled) ===")
    for fmc in (90.0, 119.0):
        _g, nb2, ac2 = run(crown_fmc=fmc, with_log=False)
        print(f"  crown FMC {fmc:.0f}%: burned {nb2}, active-crown {ac2} "
              f"({100*ac2/max(nb2,1):.0f}%)")


if __name__ == "__main__":
    main()
