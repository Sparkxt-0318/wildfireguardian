"""Diagnose the slow-initial-spread warm-up in the cellular automaton.

Session 4 Deliverable 1. Instruments the CA over the first 60 minutes on a
uniform grid (no terrain/fuel heterogeneity) and measures the effective
head-fire rate vs the theoretical Rothermel steady-state rate, to identify
exactly why early spread lags.

Run::

    python scripts/diagnose_spread_warmup.py

Writes ``docs/figures/spread_warmup_diagnostic.png`` and prints the table
that seeds ``docs/methodology/spread_warmup.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from wildfireguardian.spread_model.cellular_automaton import (
    CellState,
    FireGrid,
    WindField,
)
from wildfireguardian.spread_model.rothermel import KOREAN_PINUS, compute_spread_rate

# Fixed conditions for the diagnostic.
CELL_SIZE_M = 100.0
DEAD_MOISTURE = 0.10
LFMC = 0.40
WIND_MIDFLAME_MS = 4.0
WIND_FROM_DEG = 270.0          # from west → head fire goes east
DT_MIN = 1.0
DURATION_MIN = 60.0
GRID_N = 121                   # odd so there's a clean centre
SEED = 12345


@dataclass
class WarmupTrace:
    times: list[float]
    n_burning: list[int]
    n_touched: list[int]          # burning + burned
    area_ha: list[float]
    head_extent_m: list[float]    # max east displacement of any touched cell
    effective_head_rate: list[float]   # head_extent / time


def _theoretical_rate() -> float:
    r = compute_spread_rate(
        KOREAN_PINUS, dead_moisture=DEAD_MOISTURE, live_moisture=LFMC,
        wind_speed_ms=WIND_MIDFLAME_MS, slope_degrees=0.0,
    )
    return r.rate_m_min


def _make_uniform_grid(ignite: str = "point", radius_m: float = 0.0) -> FireGrid:
    grid = FireGrid(
        nrows=GRID_N, ncols=GRID_N, cell_size_m=CELL_SIZE_M,
        residence_time_min=60.0,
    )
    grid.fuel_model_id[:] = KOREAN_PINUS
    grid.fuel_moisture[:] = LFMC
    grid.slope_degrees[:] = 0.0
    ci, cj = GRID_N // 2, GRID_N // 2
    if ignite == "point":
        grid.ignite_point(ci, cj, time_min=0.0)
    elif ignite == "disc":
        grid.ignite_disc(ci, cj, radius_m=radius_m, time_min=0.0)
    else:
        raise ValueError(ignite)
    return grid


def trace_run(ignite: str = "point", radius_m: float = 0.0) -> WarmupTrace:
    grid = _make_uniform_grid(ignite=ignite, radius_m=radius_m)
    wind = WindField.from_meteo(WIND_MIDFLAME_MS, WIND_FROM_DEG)
    ci, cj = GRID_N // 2, GRID_N // 2

    tr = WarmupTrace([], [], [], [], [], [])
    t = 0.0
    while t <= DURATION_MIN + 1e-9:
        touched = grid.state >= CellState.BURNING
        n_touched = int(touched.sum())
        n_burning = int((grid.state == CellState.BURNING).sum())
        area_ha = n_touched * (CELL_SIZE_M ** 2) / 1e4
        # Head extent: max east displacement (column index > cj) of touched cells.
        if n_touched > 0:
            jj = np.where(touched)[1]
            head_cols = jj.max() - cj
            head_extent = max(0.0, head_cols * CELL_SIZE_M)
        else:
            head_extent = 0.0
        eff_rate = head_extent / t if t > 0 else 0.0
        tr.times.append(t)
        tr.n_burning.append(n_burning)
        tr.n_touched.append(n_touched)
        tr.area_ha.append(area_ha)
        tr.head_extent_m.append(head_extent)
        tr.effective_head_rate.append(eff_rate)
        grid.step(DT_MIN, wind, current_time_min=t)
        t += DT_MIN
    return tr


def make_figure(out_path: Path, traces: dict[str, WarmupTrace], R_theory: float) -> None:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties, findfont

    for cjk in ("Noto Sans CJK KR", "Nanum Gothic", "WenQuanYi Zen Hei"):
        try:
            findfont(FontProperties(family=cjk), fallback_to_default=False)
            matplotlib.rcParams["font.sans-serif"] = [cjk, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            break
        except Exception:
            continue

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), dpi=120)
    colors = {"point": "#c0392b", "disc": "#2980b9"}
    labels = {
        "point": "single-cell ignition (Session 3)",
        "disc": "disc ignition (Session 4 fix)",
    }

    for name, tr in traces.items():
        c = colors.get(name, "#555")
        ax1.plot(tr.times, tr.effective_head_rate, color=c, lw=2.0, label=labels.get(name, name))
        ax2.plot(tr.times, tr.area_ha, color=c, lw=2.0, label=labels.get(name, name))

    ax1.axhline(R_theory, color="#27ae60", ls="--", lw=1.6,
                label=f"Rothermel steady-state R = {R_theory:.1f} m/min")
    ax1.set_xlabel("Time since ignition (min)\n발화 후 경과 시간")
    ax1.set_ylabel("Effective head-fire rate (m/min)\n유효 전파 속도")
    ax1.set_title("Effective vs theoretical head-fire rate")
    ax1.legend(fontsize=8.5)
    ax1.grid(True, alpha=0.3)

    ax2.set_xlabel("Time since ignition (min)\n발화 후 경과 시간")
    ax2.set_ylabel("Burned area (ha)\n연소 면적")
    ax2.set_title("Burned-area growth in the first hour")
    ax2.legend(fontsize=8.5)
    ax2.grid(True, alpha=0.3)

    fig.suptitle(
        "Cellular-automaton spread warm-up diagnostic — Korean Pinus, "
        f"midflame {WIND_MIDFLAME_MS:.0f} m/s, LFMC {LFMC*100:.0f}%\n"
        "셀룰러 오토마타 초기 전파 지연 진단",
        fontsize=12, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)


def main() -> None:
    R_theory = _theoretical_rate()
    print(f"Theoretical Rothermel steady-state head rate: {R_theory:.2f} m/min")
    print(f"At {CELL_SIZE_M:.0f} m cells, one cell-ring takes "
          f"{CELL_SIZE_M / R_theory:.1f} min to ignite.\n")

    point = trace_run(ignite="point")
    # Disc radius = distance the fire would cover in ~15 min at steady rate.
    disc_radius = R_theory * 15.0
    disc = trace_run(ignite="disc", radius_m=disc_radius)

    print(f"{'t(min)':>7} {'pt_area_ha':>11} {'pt_rate':>9} {'disc_area_ha':>13} {'disc_rate':>10}")
    for k in range(0, len(point.times), 5):
        print(f"{point.times[k]:>7.0f} {point.area_ha[k]:>11.1f} "
              f"{point.effective_head_rate[k]:>9.2f} "
              f"{disc.area_ha[k]:>13.1f} {disc.effective_head_rate[k]:>10.2f}")

    repo = Path(__file__).resolve().parents[1]
    out = repo / "docs" / "figures" / "spread_warmup_diagnostic.png"
    make_figure(out, {"point": point, "disc": disc}, R_theory)
    print(f"\nwrote {out}")

    # Summary statistics for the methodology doc.
    print("\n--- summary ---")
    print(f"point-ignition effective rate at t=10min: {point.effective_head_rate[10]:.2f} m/min "
          f"({100*point.effective_head_rate[10]/R_theory:.0f}% of steady-state)")
    print(f"point-ignition effective rate at t=60min: {point.effective_head_rate[60]:.2f} m/min "
          f"({100*point.effective_head_rate[60]/R_theory:.0f}% of steady-state)")
    print(f"disc-ignition  effective rate at t=10min: {disc.effective_head_rate[10]:.2f} m/min "
          f"({100*disc.effective_head_rate[10]/R_theory:.0f}% of steady-state)")
    print(f"disc-ignition  effective rate at t=60min: {disc.effective_head_rate[60]:.2f} m/min "
          f"({100*disc.effective_head_rate[60]/R_theory:.0f}% of steady-state)")


if __name__ == "__main__":
    main()
