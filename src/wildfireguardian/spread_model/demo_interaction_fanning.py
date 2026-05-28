"""Generate the moisture-wind interaction "fanning" figure.

R vs midflame wind for dry and moist fuel; the two curves fan apart, and
the gap between their slopes (∂R/∂U) IS the dimensional interaction. This
replaces the retired (tautological) four-corner ratio figure.

Run::

    python -m wildfireguardian.spread_model.demo_interaction_fanning

Writes ``docs/figures/interaction_fanning.png``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import interaction as I


def make_figure(out_path: Path) -> dict:
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

    u = np.linspace(0.0, 4.0, 81)   # midflame wind, m/s (realistic under canopy)
    R_dry = np.array([I.spread_rate(I.DRY_DEAD, float(x)) for x in u])
    R_moist = np.array([I.spread_rate(I.MOIST_DEAD, float(x)) for x in u])

    rep = I.REPRESENTATIVE_MIDFLAME_U
    slope_dry = I.dR_dU(I.DRY_DEAD, rep)
    slope_moist = I.dR_dU(I.MOIST_DEAD, rep)

    fig, ax = plt.subplots(figsize=(9, 6), dpi=120)
    ax.plot(u, R_dry, color="#c0392b", lw=2.4,
            label=f"dry fuel (dead 1-h = {I.DRY_DEAD*100:.0f}%)")
    ax.plot(u, R_moist, color="#2980b9", lw=2.4,
            label=f"moist fuel (dead 1-h = {I.MOIST_DEAD*100:.0f}%)")

    # Annotate the two slopes at the representative midflame wind.
    for slope, dead, color, dy in [
        (slope_dry, I.DRY_DEAD, "#c0392b", 0.6),
        (slope_moist, I.MOIST_DEAD, "#2980b9", -0.9),
    ]:
        R0 = I.spread_rate(dead, rep)
        ax.plot([rep], [R0], "o", color=color, ms=8, zorder=5)
        ax.annotate(
            f"∂R/∂U = {slope:.2f} m/min per m/s",
            xy=(rep, R0), xytext=(rep + 0.4, R0 + dy),
            color=color, fontsize=10,
            arrowprops=dict(arrowstyle="->", color=color, lw=0.9),
        )

    ax.axvline(rep, color="#7f8c8d", ls=":", lw=1.0, alpha=0.7)
    ax.set_xlabel("Midflame wind speed (m/s)\n화염 중간높이 풍속")
    ax.set_ylabel("Rate of spread $R$ (m/min)\n확산 속도")
    ax.set_title(
        "Moisture × wind interaction — the fanning gap is ∂²R/∂M∂U\n"
        "수분-풍속 상호작용: 두 기울기의 차이가 교차 편미분",
        fontsize=12.5, fontweight="bold",
    )
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.text(
        0.5, -0.02,
        "Korean Pinus (Gyeongbuk; surface bed provisional), live moisture 119%. "
        "Wind adds more spread per m/s on drier fuel: the slopes differ "
        f"({slope_dry:.2f} vs {slope_moist:.2f}). Their RATIO is constant in U "
        "(Rothermel is separable) — the dimensional GAP, not a ratio, is the "
        "honest interaction measure.",
        ha="center", fontsize=8.4, style="italic", color="#555",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)

    return I.marginal_wind_effect_report(rep)


def main() -> None:  # pragma: no cover
    from rich.console import Console
    from rich.table import Table

    out = Path(__file__).resolve().parents[3] / "docs" / "figures" / "interaction_fanning.png"
    console = Console()
    console.rule("[bold]Moisture-wind interaction (Session 5)")
    rep = make_figure(out)
    t = Table(title="Marginal wind effect ∂R/∂U")
    t.add_column("quantity", style="bold")
    t.add_column("value", justify="right")
    t.add_row("midflame U (m/s)", f"{rep['u_midflame_ms']:.2f}")
    t.add_row("∂R/∂U dry (dead 6%)", f"{rep['dR_dU_dry_m_min_per_ms']:.3f} m/min per m/s")
    t.add_row("∂R/∂U moist (dead 20%)", f"{rep['dR_dU_moist_m_min_per_ms']:.3f} m/min per m/s")
    t.add_row("extra effect when dry", f"{rep['extra_wind_effect_when_dry']:.3f}")
    t.add_row("∂²R/∂M∂U", f"{rep['d2R_dM_dU']:.3f}")
    console.print(t)
    console.print(f"[green]done[/green]: {out}")


if __name__ == "__main__":  # pragma: no cover
    main()
