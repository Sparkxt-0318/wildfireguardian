"""Yeongdeok 2025 smoke-plume demonstration (Session 3 Tier 2).

Generates ``docs/figures/smoke_plume_demo.png`` — a peninsula-scale
PM2.5 ground-level concentration snapshot for the Yeongdeok 2025 fire
under the reconstructed wind.

This is an ARCHITECTURE DEMONSTRATION, not validated science. The
emission rate is a coarse area×emission-factor estimate; the dispersion
uses textbook Pasquill-Gifford coefficients. A production smoke product
would couple to HYSPLIT / CMAQ.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pyproj import Transformer

from ..utils.regions import YEONGDEOK_2025
from .gaussian_plume import (
    PlumeConfig,
    StabilityClass,
    estimate_pm25_emission_rate_ug_s,
    plume_grid,
)

# Yeongdeok ignition (public-reported) and reconstructed peak wind.
IGNITION_LON, IGNITION_LAT = 129.37, 36.50
WIND_SPEED_MS = 12.0                 # peak 10-m wind during Foehn
WIND_TO_BEARING = 110.0              # blowing ESE (toward the coast)
ACTIVE_FIRE_AREA_HA = 800.0          # representative active-fire front area
EFFECTIVE_HEIGHT_M = 200.0           # plume rise from an intense fire front
STABILITY = StabilityClass.C         # slightly unstable (windy daytime)


def make_figure(out_path: Path) -> dict:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.font_manager import FontProperties, findfont

    for cjk in ("Noto Sans CJK KR", "Nanum Gothic", "WenQuanYi Zen Hei"):
        try:
            findfont(FontProperties(family=cjk), fallback_to_default=False)
            matplotlib.rcParams["font.sans-serif"] = [cjk, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            break
        except Exception:
            continue

    to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    to_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    src_x, src_y = to_5179.transform(IGNITION_LON, IGNITION_LAT)

    Q = estimate_pm25_emission_rate_ug_s(ACTIVE_FIRE_AREA_HA)
    cfg = PlumeConfig(
        emission_rate_ug_s=Q,
        wind_speed_ms=WIND_SPEED_MS,
        wind_to_bearing_deg=WIND_TO_BEARING,
        effective_height_m=EFFECTIVE_HEIGHT_M,
        stability=STABILITY,
    )
    X, Y, C = plume_grid((src_x, src_y), cfg, extent_m=40_000.0, resolution_m=400.0)

    # Reproject grid corners to WGS84 for axis labelling (approx; use centre row).
    lon_grid, lat_grid = to_4326.transform(X, Y)

    fig, ax = plt.subplots(figsize=(9, 8), dpi=120)
    C_masked = np.where(C > 0.1, C, np.nan)
    im = ax.pcolormesh(
        lon_grid, lat_grid, C_masked,
        cmap="inferno_r", norm=LogNorm(vmin=1.0, vmax=max(10.0, np.nanmax(C_masked))),
        shading="auto",
    )
    cbar = fig.colorbar(im, ax=ax, pad=0.02, shrink=0.9)
    cbar.set_label("Ground-level PM2.5 (µg/m³, log scale)\n지표 초미세먼지 농도")

    # WHO 24h guideline (15 µg/m³) and "very unhealthy" (75 µg/m³) contours.
    cs = ax.contour(
        lon_grid, lat_grid, C, levels=[15.0, 35.0, 75.0],
        colors=["#2ecc71", "#f39c12", "#c0392b"], linewidths=1.0,
    )
    ax.clabel(cs, inline=True, fontsize=8, fmt="%g µg/m³")

    ax.plot(IGNITION_LON, IGNITION_LAT, "*", color="#e74c3c",
            markersize=18, markeredgecolor="white", markeredgewidth=1.0,
            label="fire source (영덕 영해)")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(
        "Yeongdeok 2025 smoke plume — Gaussian dispersion (architecture demo)\n"
        "영덕 2025 연기 확산 (가우시안 플룸 — 구조 시연용)",
        fontsize=12, fontweight="bold",
    )
    ax.legend(loc="upper left")
    ax.set_aspect(1.25)

    fig.text(
        0.5, -0.02,
        f"DEMONSTRATION ONLY — not validated. Q≈{Q/1e6:.0f} g/s PM2.5 "
        f"({ACTIVE_FIRE_AREA_HA:.0f} ha active front), wind {WIND_SPEED_MS:.0f} m/s "
        f"toward {WIND_TO_BEARING:.0f}°, Pasquill-Gifford class {STABILITY.value}. "
        f"Production smoke needs HYSPLIT/CMAQ coupling.",
        ha="center", fontsize=8.5, style="italic", color="#666",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)

    return {
        "emission_rate_g_s": Q / 1e6,
        "max_pm25_ug_m3": float(np.nanmax(C)),
        "grid_cells": int(C.size),
    }


def main() -> None:  # pragma: no cover
    from rich.console import Console
    here = Path(__file__).resolve()
    repo_root = here.parents[3]
    out = repo_root / "docs" / "figures" / "smoke_plume_demo.png"
    console = Console()
    console.rule("[bold]Yeongdeok smoke plume demo (Session 3)")
    stats = make_figure(out)
    console.print(stats)
    console.print(f"[green]done[/green]: {out}")


if __name__ == "__main__":  # pragma: no cover
    main()
