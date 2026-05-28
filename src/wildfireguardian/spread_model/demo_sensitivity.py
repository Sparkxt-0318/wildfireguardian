"""Generate the LFMC-sensitivity figure used in the project writeup.

Run::

    python -m wildfireguardian.spread_model.demo_sensitivity

This writes ``docs/figures/lfmc_sensitivity.png``.

Scientific intent
-----------------

The figure makes one point for forestry reviewers and competition judges:

  **The rate of spread of Korean Pinus densiflora surface fire is highly
  sensitive to live fuel moisture content (LFMC), and the March 2025
  Yeongdeok event happened inside the fast-spread regime.**

Two curves are plotted, both using the multi-class :class:`KoreanPinusFuelModel`
(Andrews 2018 §3 weighting) at 2 m/s midflame wind, no slope:

1. Dead 1-h moisture at **6 %** — extreme drought conditions.
2. Dead 1-h moisture at **12 %** — typical Korean spring conditions.

The X-axis sweeps LFMC from 30 % to 200 % and a vertical marker
highlights the ~40 % LFMC estimated for the affected pine stands during
the March 22–28, 2025 Yeongdeok event.

The multi-class engine computes a dynamic live moisture of extinction
m_x_live via Burgan (1979). Under dry dead conditions m_x_live is high
(spread continues at LFMC ~ 200 %), while under wet dead conditions
m_x_live collapses toward m_x_dead and the live fuel acts as a heat sink.

Implementation note
-------------------

We deliberately do *not* call :mod:`matplotlib.pyplot` at import time. The
figure is generated only when this module is executed as ``__main__`` or
when :func:`make_figure` is called explicitly, so importing
``wildfireguardian.spread_model`` from a test or notebook does not pull in
``matplotlib`` unconditionally.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .rothermel import KOREAN_PINUS, compute_spread_rate

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

# Two dead-fuel-moisture scenarios.
DEAD_DROUGHT: float = 0.06      # 6 % — extreme drought / late-summer Korea
DEAD_SPRING: float = 0.12       # 12 % — typical late-March / April Korea


def sweep_lfmc(dead_moisture: float, lfmcs: np.ndarray) -> np.ndarray:
    """Spread rate (m/min) for Korean Pinus at varying LFMC, fixed dead moisture."""
    return np.array([
        compute_spread_rate(
            KOREAN_PINUS,
            dead_moisture=dead_moisture,
            live_moisture=float(m),
            wind_speed_ms=WIND_SPEED_MS,
            slope_degrees=SLOPE_DEGREES,
        ).rate_m_min
        for m in lfmcs
    ])


def make_figure(out_path: Path) -> dict:
    """Render the LFMC sensitivity figure and return a small summary dict.

    Parameters
    ----------
    out_path : Path
        Where to write the PNG.

    Returns
    -------
    dict
        Spread rate at key LFMC values for both dead-moisture scenarios.
    """
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import findfont, FontProperties

    # Pick a CJK-capable font for the Korean labels if one is available.
    for cjk_candidate in ("Noto Sans CJK KR", "Nanum Gothic", "WenQuanYi Zen Hei", "Unifont"):
        try:
            font_path = findfont(FontProperties(family=cjk_candidate), fallback_to_default=False)
            if font_path:
                matplotlib.rcParams["font.sans-serif"] = [cjk_candidate, "DejaVu Sans"]
                matplotlib.rcParams["axes.unicode_minus"] = False
                break
        except Exception:
            continue

    lfmcs = np.linspace(0.30, 2.00, 200)   # 30 % – 200 %

    R_drought = sweep_lfmc(DEAD_DROUGHT, lfmcs)
    R_spring = sweep_lfmc(DEAD_SPRING, lfmcs)

    fig, ax = plt.subplots(figsize=(9.5, 5.8), dpi=120)

    floor = 1e-3  # m/min — log-scale floor
    ax.plot(
        lfmcs * 100.0, np.maximum(R_drought, floor),
        label=f"Dead 1-h = {DEAD_DROUGHT*100:.0f} % (drought)",
        color="#c0392b", linewidth=2.4,
    )
    ax.plot(
        lfmcs * 100.0, np.maximum(R_spring, floor),
        label=f"Dead 1-h = {DEAD_SPRING*100:.0f} % (typical spring)",
        color="#e67e22", linewidth=2.4, linestyle="--",
    )

    ax.set_yscale("log")
    ymax = max(R_drought.max(), R_spring.max()) * 1.5
    ax.set_ylim(0.05, ymax)
    ax.set_xlim(30, 200)

    # March 2025 event marker.
    ax.axvline(
        MARCH_2025_LFMC * 100.0, color="#34495e", linestyle="--",
        linewidth=1.5, alpha=0.85, zorder=1,
    )
    R_drought_event = compute_spread_rate(
        KOREAN_PINUS,
        dead_moisture=DEAD_DROUGHT, live_moisture=MARCH_2025_LFMC,
        wind_speed_ms=WIND_SPEED_MS,
    ).rate_m_min
    R_spring_event = compute_spread_rate(
        KOREAN_PINUS,
        dead_moisture=DEAD_SPRING, live_moisture=MARCH_2025_LFMC,
        wind_speed_ms=WIND_SPEED_MS,
    ).rate_m_min
    ax.plot(
        [MARCH_2025_LFMC * 100.0], [R_drought_event],
        "o", color="#c0392b", markersize=8, zorder=5,
    )
    ax.plot(
        [MARCH_2025_LFMC * 100.0], [R_spring_event],
        "o", color="#e67e22", markersize=8, zorder=5,
    )

    ax.annotate(
        "2025-03 Yeongdeok\n"
        "영덕 산불 / LFMC ≈ 40 %\n"
        f"→ drought-dry: R ≈ {R_drought_event:.1f} m/min\n"
        f"→ spring-typical: R ≈ {R_spring_event:.1f} m/min",
        xy=(MARCH_2025_LFMC * 100.0, R_drought_event),
        xytext=(80, R_drought_event * 0.55),
        fontsize=9.5, color="#34495e",
        arrowprops=dict(arrowstyle="->", color="#34495e", lw=0.9),
        bbox=dict(boxstyle="round,pad=0.35", fc="#ecf0f1", ec="#34495e",
                  lw=0.7, alpha=0.95),
    )

    ax.set_xlabel(
        "Live fuel moisture content (LFMC, % of dry mass)\n"
        "산림 살아있는 연료의 수분 함량",
        fontsize=11,
    )
    ax.set_ylabel(
        "Rate of spread $R$  (m·min$^{-1}$, log scale)\n"
        "확산 속도",
        fontsize=11,
    )
    ax.set_title(
        "LFMC sensitivity — Korean Pinus densiflora (multi-class Rothermel)\n"
        "한국 소나무림 LFMC 민감도 분석 (다중 연료층 Rothermel)",
        fontsize=13, fontweight="bold",
    )
    ax.legend(loc="upper right", framealpha=0.95, fontsize=10)
    ax.grid(True, which="both", alpha=0.3)

    fig.text(
        0.5, -0.05,
        f"Multi-class Rothermel (Andrews 2018 §3) with the Korean Pinus densiflora "
        f"analog fuel model. Midflame wind = {WIND_SPEED_MS:.0f} m/s, slope = 0°. "
        f"Live moisture of extinction is computed dynamically via Burgan (1979).",
        ha="center", fontsize=8.8, style="italic", color="#555",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)

    # Spot values for the report.
    spot = {}
    for dead, name in [(DEAD_DROUGHT, "drought_6%"), (DEAD_SPRING, "spring_12%")]:
        for lfmc in (0.40, 0.60, 0.80, 1.00, 1.50):
            r = compute_spread_rate(
                KOREAN_PINUS,
                dead_moisture=dead, live_moisture=lfmc,
                wind_speed_ms=WIND_SPEED_MS,
            ).rate_m_min
            spot[f"R [{name}, LFMC={lfmc*100:.0f}%]  m/min"] = r
    return spot


def main() -> None:  # pragma: no cover - CLI entry
    from rich.console import Console
    from rich.table import Table

    here = Path(__file__).resolve()
    repo_root = here.parents[3]
    out = repo_root / "docs" / "figures" / "lfmc_sensitivity.png"

    console = Console()
    console.rule("[bold]LFMC sensitivity demo  (Session 2 — multi-class)")
    console.print(f"writing → {out}")
    stats = make_figure(out)

    table = Table(title="Spread-rate spot values")
    table.add_column("scenario", style="bold")
    table.add_column("R (m/min)", justify="right")
    for k, v in stats.items():
        table.add_row(k, f"{v:.3f}")
    console.print(table)
    console.print(f"[green]done[/green]: figure written to {out}")


if __name__ == "__main__":  # pragma: no cover
    main()
