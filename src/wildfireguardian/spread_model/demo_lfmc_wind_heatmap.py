"""LFMC × Wind 2D sensitivity heatmap — Session 3 writeup centerpiece.

Generates ``docs/figures/lfmc_wind_sensitivity_heatmap.png``.

Scientific intent
-----------------

Rather than a one-dimensional LFMC sweep (which shows only the moisture
effect in isolation), this figure shows the **multiplicative coupling**
between LFMC and midflame wind speed in the multi-class Rothermel +
Korean Pinus + Burgan 1979 system.

The headline finding (reported in OVERNIGHT_REPORT_SESSION3.md):

    R(LFMC=80 %, midflame 2 m/s)  vs  R(LFMC=40 %, midflame 12 m/s)
    -----------------------------------------------------------------
    ~ X-fold ratio between typical-summer-quiet and drought-Foehn
    conditions. Same fuel model, same dead 1-h moisture (12 %).

That ratio is what makes the March 2025 Yeongdeok event so different
from a typical Korean Pinus fire.

Conventions
-----------

- X axis: midflame wind speed (m/s), 0 to 15. Note: KMA reports 10-m
  winds; the midflame conversion divides by ~3.3 (Andrews 2012 closed-
  canopy Pinus). KMA 10-15 m/s 10-m → midflame ~3-4.5 m/s.
- Y axis: live fuel moisture content (% of dry mass), 30 to 200.
- Colour: rate of spread (m/min), log-scaled.
- Dead 1-h moisture is fixed at 12 % (typical Korean spring).
- Slope is fixed at 0°.
- A labelled point shows estimated 영덕 2025 conditions
  (LFMC≈40 %, midflame ≈ 4 m/s).
- A labelled point shows typical Korean spring "quiet" conditions
  (LFMC ≈ 80 %, midflame ≈ 2 m/s) for the headline ratio.

KR + EN title.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .rothermel import KOREAN_PINUS, compute_spread_rate

# Fixed background conditions.
DEAD_1H_FRACTION: float = 0.12      # 12 % — typical Korean spring
SLOPE_DEGREES: float = 0.0

# Sweep ranges.
LFMC_MIN, LFMC_MAX, LFMC_N = 0.30, 2.00, 86      # 30 % → 200 %, 2 % steps
WIND_MIN, WIND_MAX, WIND_N = 0.0, 15.0, 76       # 0 → 15 m/s, 0.2 m/s steps

# Labelled scenarios.
YEONGDEOK_MARCH_2025 = {
    "label": "Yeongdeok 2025-03\nLFMC≈40 %, midflame ≈ 4 m/s",
    "label_kr": "영덕 2025-03",
    "lfmc": 0.40,
    "midflame_ms": 4.0,
}
TYPICAL_SUMMER_QUIET = {
    "label": "Typical summer quiet\nLFMC≈80 %, midflame ≈ 2 m/s",
    "label_kr": "여름 평년 약풍",
    "lfmc": 0.80,
    "midflame_ms": 2.0,
}


def sweep() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (lfmc grid, wind grid, R grid in m/min)."""
    lfmcs = np.linspace(LFMC_MIN, LFMC_MAX, LFMC_N)
    winds = np.linspace(WIND_MIN, WIND_MAX, WIND_N)
    R = np.zeros((len(lfmcs), len(winds)), dtype=np.float64)
    for i, lfmc in enumerate(lfmcs):
        for j, wind in enumerate(winds):
            r = compute_spread_rate(
                KOREAN_PINUS,
                dead_moisture=DEAD_1H_FRACTION,
                live_moisture=float(lfmc),
                wind_speed_ms=float(wind),
                slope_degrees=SLOPE_DEGREES,
            )
            R[i, j] = r.rate_m_min
    return lfmcs, winds, R


def headline_ratio() -> dict:
    """Compute the writeup headline number: drought-Foehn vs summer-quiet ratio."""
    quiet = compute_spread_rate(
        KOREAN_PINUS,
        dead_moisture=DEAD_1H_FRACTION,
        live_moisture=TYPICAL_SUMMER_QUIET["lfmc"],
        wind_speed_ms=TYPICAL_SUMMER_QUIET["midflame_ms"],
    ).rate_m_min
    drought_foehn = compute_spread_rate(
        KOREAN_PINUS,
        dead_moisture=DEAD_1H_FRACTION,
        live_moisture=0.40,
        wind_speed_ms=12.0,
    ).rate_m_min
    yeongdeok = compute_spread_rate(
        KOREAN_PINUS,
        dead_moisture=DEAD_1H_FRACTION,
        live_moisture=YEONGDEOK_MARCH_2025["lfmc"],
        wind_speed_ms=YEONGDEOK_MARCH_2025["midflame_ms"],
    ).rate_m_min
    return {
        "R_quiet_summer (LFMC 80%, mid 2 m/s)": quiet,
        "R_yeongdeok_2025 (LFMC 40%, mid 4 m/s)": yeongdeok,
        "R_drought_foehn (LFMC 40%, mid 12 m/s)": drought_foehn,
        "ratio_drought_foehn_over_quiet": drought_foehn / max(quiet, 1e-9),
        "ratio_yeongdeok_over_quiet": yeongdeok / max(quiet, 1e-9),
    }


def make_figure(out_path: Path) -> dict:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.font_manager import FontProperties, findfont

    # CJK font fallback (Korean labels).
    for cjk in ("Noto Sans CJK KR", "Nanum Gothic", "WenQuanYi Zen Hei"):
        try:
            findfont(FontProperties(family=cjk), fallback_to_default=False)
            matplotlib.rcParams["font.sans-serif"] = [cjk, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            break
        except Exception:
            continue

    lfmcs, winds, R = sweep()
    # Mask zeros (above m_x_live for very wet conditions); log-scale demands > 0.
    R_pos = np.where(R > 1e-3, R, 1e-3)

    fig, ax = plt.subplots(figsize=(10.5, 7.0), dpi=120)
    cmap = "YlOrRd"
    norm = LogNorm(vmin=max(0.05, R_pos.min()), vmax=R_pos.max())
    im = ax.pcolormesh(
        winds, lfmcs * 100.0, R_pos, cmap=cmap, norm=norm, shading="auto",
    )
    cbar = fig.colorbar(im, ax=ax, pad=0.02, shrink=0.92)
    cbar.set_label(
        "Rate of spread $R$  (m·min$^{-1}$, log scale)\n확산 속도",
        fontsize=11,
    )

    # Contour lines at key thresholds.
    contour_levels = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
    cs = ax.contour(
        winds, lfmcs * 100.0, R_pos, levels=contour_levels,
        colors="black", linewidths=0.6, alpha=0.55,
    )
    ax.clabel(cs, inline=True, fontsize=8, fmt="%g m/min")

    # Labelled scenarios.
    scenarios = [TYPICAL_SUMMER_QUIET, YEONGDEOK_MARCH_2025]
    marker_colors = ["#2c3e50", "#c0392b"]
    for sc, color in zip(scenarios, marker_colors):
        ax.plot([sc["midflame_ms"]], [sc["lfmc"] * 100.0],
                "o", color=color, markersize=10, markeredgecolor="white",
                markeredgewidth=1.5, zorder=5)
        ax.annotate(
            sc["label"],
            xy=(sc["midflame_ms"], sc["lfmc"] * 100.0),
            xytext=(sc["midflame_ms"] + 1.0, sc["lfmc"] * 100.0 + 15),
            color=color, fontsize=9.5,
            arrowprops=dict(arrowstyle="->", color=color, lw=0.9),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, lw=0.7, alpha=0.9),
        )

    ax.set_xlabel(
        "Midflame wind speed (m/s)\n"
        "(unfurled canopy reduction ≈ 0.3; KMA 10-m → multiply by ~0.3)",
        fontsize=11,
    )
    ax.set_ylabel("Live fuel moisture content (LFMC, % dry mass)\n생체 연료 수분량", fontsize=11)
    ax.set_title(
        "LFMC × Wind sensitivity — Korean Pinus densiflora "
        "(multi-class Rothermel + Burgan 1979)\n"
        "한국 소나무림 LFMC × 풍속 결합 민감도 분석",
        fontsize=12.5, fontweight="bold",
    )

    fig.text(
        0.5, -0.04,
        f"Dead 1-h moisture = {DEAD_1H_FRACTION*100:.0f} %, slope = 0°. "
        f"Live moisture of extinction is dynamic per Burgan (1979). "
        f"Multi-class Andrews 2018 §3 weighting on the Korean Pinus analog fuel.",
        ha="center", fontsize=8.8, style="italic", color="#555",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)

    return headline_ratio()


def main() -> None:  # pragma: no cover
    from rich.console import Console
    from rich.table import Table

    here = Path(__file__).resolve()
    repo_root = here.parents[3]
    out = repo_root / "docs" / "figures" / "lfmc_wind_sensitivity_heatmap.png"

    console = Console()
    console.rule("[bold]LFMC × Wind sensitivity heatmap (Session 3)")
    console.print(f"writing → {out}")
    summary = make_figure(out)

    table = Table(title="Headline R values")
    table.add_column("scenario", style="bold")
    table.add_column("R (m/min)", justify="right")
    for k, v in summary.items():
        table.add_row(k, f"{v:.3f}")
    console.print(table)


if __name__ == "__main__":
    main()
