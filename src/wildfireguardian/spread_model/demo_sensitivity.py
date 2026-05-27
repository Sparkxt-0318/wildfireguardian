"""Generate the LFMC-sensitivity figure used in the project writeup.

Run::

    python -m wildfireguardian.spread_model.demo_sensitivity

This writes ``docs/figures/lfmc_sensitivity.png``.

Scientific intent
-----------------

The figure should make one point: **the rate of spread is highly sensitive to
fuel moisture, and the March 2025 Yeongdeok event was deep inside the
fast-spread regime for the fuel types that dominated the affected stands.**

Two fuel-model archetypes are plotted:

1. **FM8 closed-timber litter** (dead-fuel dominated). Anderson 1982 reports
   moisture of extinction = 0.30, so the curve falls to zero at 30 % fuel
   moisture. This is appropriate for cured ground-litter beds where the
   "fuel moisture" axis means dead 1-h moisture (a few % to ~30 %).

2. **Korean Pinus densiflora analogue.** A custom single-class fuel
   representing Korean red-pine forest surface fuel (litter + understory).
   The live moisture of extinction follows Burgan & Rothermel (1984) and is
   set to 1.20, so the curve covers the full operational LFMC range
   (~ 50 % – 150 %). Fuel load is calibrated to give *physical* surface
   spread rates (< 50 m/min) under the chosen wind condition.

A logarithmic y-axis is used so both the slow-spread regime (FM8 closed
litter, ~ 0.1 m/min) and the fast-spread regime (Korean pine analogue at
low LFMC, ~ 10 m/min) are visible simultaneously.

The vertical reference line at 40 % marks the regional LFMC estimated by
KFS for the affected pine stands during the March 22–28, 2025 Yeongdeok
event.

Implementation note
-------------------

We deliberately do *not* call :mod:`matplotlib.pyplot` at import time. The
figure is generated only when this module is executed as ``__main__`` or
when :func:`make_figure` is called explicitly, so importing
``wildfireguardian.spread_model`` from a test or notebook does not pull in
``matplotlib`` unconditionally.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from .rothermel import FUEL_MODELS, FuelModel, compute_spread_rate

# March 25, 2025: KFS post-event LFMC estimate for Yeongdeok-affected stands.
# Cited as a rough field estimate; not a measured value.
MARCH_2025_LFMC: float = 0.40

# Wind / slope conditions assumed throughout the sensitivity sweep.
# 2 m/s is representative of stand-interior midflame wind in Korean
# Pinus densiflora forests during the March 2025 event. KMA Yeongdeok
# 10-m wind peaks were 10-15 m/s; the canopy reduction factor for closed
# conifer is roughly 0.15-0.20 (Andrews 2012), giving 1.5-3.0 m/s
# midflame.
WIND_SPEED_MS: float = 2.0      # midflame, m/s
SLOPE_DEGREES: float = 0.0


def _korean_pinus_fuel_model() -> FuelModel:
    """Korean Pinus densiflora analogue, single-class.

    Parameters chosen to represent the dominant surface fuel in the
    affected 영덕군 stands during the March 2025 event:

    - Modest litter + understory load (cured needles and grass).
    - Fine-fuel SAV typical of conifer needles.
    - High live moisture of extinction following Burgan & Rothermel 1984
      for live-dominated stands. This is **deliberately different** from the
      Anderson 13 FM10 ``m_x = 25 %`` (which is dead-fuel m_x) — we are
      using m_x here as the *characteristic* extinction for the live-foliage
      dominated regime that LFMC actually measures.

    This model is intentionally illustrative; production work in the
    validation module will derive site-specific parameters from the
    KFS 임상도 / fuel-classification rasters.
    """
    return FuelModel(
        code="KP_PINE",
        name="Korean Pinus densiflora analogue (illustrative)",
        w_o=0.15,        # lb/ft² ~ 0.73 kg/m²: modest needle litter + understory
        delta=0.5,       # ft  ~ 15 cm
        sigma=2200.0,    # 1/ft, characteristic fine-needle SAV
        m_x=1.20,        # 120 % live moisture of extinction
        description="Custom: not part of Anderson 13. For demo only.",
    )


def sweep_rate(fuel_model: FuelModel, moistures: np.ndarray) -> np.ndarray:
    """Compute rate of spread (m/min) across a vector of fuel moisture values."""
    return np.array([
        compute_spread_rate(
            fuel_model, fuel_moisture=float(m),
            wind_speed_ms=WIND_SPEED_MS,
            slope_degrees=SLOPE_DEGREES,
        ).rate_m_min
        for m in moistures
    ])


def make_figure(out_path: Path) -> dict:
    """Render the LFMC sensitivity figure and return a small summary dict.

    Parameters
    ----------
    out_path : Path
        Where to write the PNG. Parent directory is created if missing.

    Returns
    -------
    dict
        Summary statistics (min / max R for each curve), useful for the
        overnight report.
    """
    import matplotlib.pyplot as plt  # local import — see module docstring

    moistures = np.linspace(0.05, 2.00, 200)  # 5 % .. 200 %

    fm8 = FUEL_MODELS["FM8"]
    kp_pine = _korean_pinus_fuel_model()

    R_fm8 = sweep_rate(fm8, moistures)
    R_kp = sweep_rate(kp_pine, moistures)

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=120)

    # Plot with a small floor so log-scale doesn't crash on zeros; we
    # mask the floor to keep the visual clean.
    floor = 1e-3  # m/min, well below any physically interesting rate
    ax.plot(moistures * 100.0, np.maximum(R_kp, floor),
            label="Korean Pinus analogue ($m_x = 120\\%$)",
            color="#c0392b", linewidth=2.2)
    ax.plot(moistures * 100.0, np.maximum(R_fm8, floor),
            label="FM8 closed-timber litter ($m_x = 30\\%$)",
            color="#27ae60", linewidth=2.2)

    ax.set_yscale("log")
    ax.set_ylim(1e-3, max(R_kp.max(), R_fm8.max()) * 1.5)

    # March 2025 LFMC marker.
    ax.axvline(MARCH_2025_LFMC * 100.0, color="#34495e", linestyle="--",
               linewidth=1.4, alpha=0.85)
    R_kp_at_event = compute_spread_rate(
        kp_pine, fuel_moisture=MARCH_2025_LFMC, wind_speed_ms=WIND_SPEED_MS,
    ).rate_m_min
    ax.plot([MARCH_2025_LFMC * 100.0], [R_kp_at_event], "o",
            color="#34495e", markersize=7, zorder=5)
    ax.annotate(
        f"2025-03 Yeongdeok\nLFMC ≈ 40 %\n→ R ≈ {R_kp_at_event:.1f} m/min",
        xy=(MARCH_2025_LFMC * 100.0, R_kp_at_event),
        xytext=(60, R_kp_at_event * 1.8),
        fontsize=9, color="#34495e",
        arrowprops=dict(arrowstyle="->", color="#34495e", lw=0.8),
        bbox=dict(boxstyle="round,pad=0.3", fc="#ecf0f1", ec="#34495e",
                  lw=0.6, alpha=0.9),
    )

    # m_x markers as faint vertical lines.
    ax.axvline(30.0, color="#27ae60", linestyle=":", linewidth=0.9, alpha=0.5)
    ax.axvline(120.0, color="#c0392b", linestyle=":", linewidth=0.9, alpha=0.5)

    ax.set_xlabel("Fuel moisture content (% of dry mass)", fontsize=11)
    ax.set_ylabel("Rate of spread $R$ (m·min$^{-1}$, log scale)\n"
                  f"midflame wind = {WIND_SPEED_MS:.0f} m/s, "
                  f"slope = {SLOPE_DEGREES:.0f}°", fontsize=11)
    ax.set_title("LFMC sensitivity of Rothermel surface fire spread",
                 fontsize=13, fontweight="bold")
    ax.legend(loc="lower left", framealpha=0.95)
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xlim(0, 200)

    # Caption text below the plot.
    fig.text(
        0.5, -0.04,
        "Single-class Rothermel (1972) implementation. The Korean Pinus "
        "analogue uses $m_x = 120\\%$ following Burgan & Rothermel (1984) "
        "for live-fuel-dominated stands.\nFM8 follows the Anderson 1982 dead "
        "$m_x = 30\\%$. Absolute spread rates are single-class estimates; "
        "operational forecasts must use multi-class fuel weighting.",
        ha="center", fontsize=8.5, style="italic", color="#555",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)

    return {
        "FM8 R min m/min": float(R_fm8.min()),
        "FM8 R max m/min": float(R_fm8.max()),
        "KP-pine R min m/min": float(R_kp.min()),
        "KP-pine R max m/min": float(R_kp.max()),
        "KP-pine R at 40% LFMC m/min": R_kp_at_event,
        "FM8 R at 10% moisture m/min": float(
            compute_spread_rate(fm8, fuel_moisture=0.10,
                                wind_speed_ms=WIND_SPEED_MS).rate_m_min
        ),
    }


def main() -> None:  # pragma: no cover - CLI entry
    from rich.console import Console
    from rich.table import Table

    here = Path(__file__).resolve()
    repo_root = here.parents[3]
    out = repo_root / "docs" / "figures" / "lfmc_sensitivity.png"

    console = Console()
    console.rule("[bold]LFMC sensitivity demo")
    console.print(f"writing → {out}")
    stats = make_figure(out)

    table = Table(title="Sweep statistics")
    table.add_column("metric", style="bold")
    table.add_column("value m/min", justify="right")
    for k, v in stats.items():
        table.add_row(k, f"{v:.3f}")
    console.print(table)
    console.print(f"[green]done[/green]: figure written to {out}")


if __name__ == "__main__":  # pragma: no cover
    main()
