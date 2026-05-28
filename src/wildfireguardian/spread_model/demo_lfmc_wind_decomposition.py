"""Decompose the LFMC×wind spread-rate amplification into its factors.

Session 4 Deliverable 2. The Session 3 headline — rate of spread 18.3×
higher under drought-Föhn (LFMC 40 %, wind 12 m/s) than benign conditions
(LFMC 80 %, wind 2 m/s) — bundles a moisture effect and a wind effect. This
script decomposes it and demonstrates that the two factors combine
**multiplicatively**, which is a structural property of the Rothermel
equation (η_M and (1+φ_w) are separate multiplicative factors).

Run::

    python -m wildfireguardian.spread_model.demo_lfmc_wind_decomposition

Writes ``docs/figures/lfmc_wind_decomposition.png``.
"""

from __future__ import annotations

from pathlib import Path

from .rothermel import KOREAN_PINUS, compute_spread_rate

DEAD_1H = 0.12          # typical Korean spring dead-fuel moisture

# Four corners of the (LFMC, wind) box.
CORNERS = {
    "A": {"lfmc": 0.80, "wind": 2.0, "label": "benign\n(LFMC 80%, 2 m/s)", "label_kr": "평년"},
    "B": {"lfmc": 0.40, "wind": 2.0, "label": "drought only\n(LFMC 40%, 2 m/s)", "label_kr": "가뭄만"},
    "C": {"lfmc": 0.80, "wind": 12.0, "label": "wind only\n(LFMC 80%, 12 m/s)", "label_kr": "강풍만"},
    "D": {"lfmc": 0.40, "wind": 12.0, "label": "drought + Föhn\n(LFMC 40%, 12 m/s)", "label_kr": "가뭄+강풍"},
}


def compute_decomposition() -> dict:
    def R(lfmc: float, wind: float) -> float:
        return compute_spread_rate(
            KOREAN_PINUS, dead_moisture=DEAD_1H, live_moisture=lfmc,
            wind_speed_ms=wind,
        ).rate_m_min

    rates = {k: R(v["lfmc"], v["wind"]) for k, v in CORNERS.items()}
    A, B, C, D = rates["A"], rates["B"], rates["C"], rates["D"]
    return {
        "rates_m_min": rates,
        "moisture_alone_BA": B / A,
        "wind_alone_CA": C / A,
        "combined_DA": D / A,
        "product_of_alones": (B / A) * (C / A),
        "interaction_ratio": (D / A) / ((B / A) * (C / A)),
    }


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

    d = compute_decomposition()
    rates = d["rates_m_min"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=120)

    # ----- left: the four corners as bars -----
    keys = ["A", "B", "C", "D"]
    vals = [rates[k] for k in keys]
    colors = ["#27ae60", "#f39c12", "#2980b9", "#c0392b"]
    bars = ax1.bar(range(4), vals, color=colors, edgecolor="black", linewidth=0.8)
    ax1.set_xticks(range(4))
    ax1.set_xticklabels([CORNERS[k]["label"] for k in keys], fontsize=9)
    ax1.set_ylabel("Rate of spread $R$ (m/min)\n확산 속도")
    ax1.set_title("Four-corner spread rates (Korean Pinus, dead 1-h = 12%)")
    for b, k in zip(bars, keys):
        ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
                 f"{rates[k]:.1f}\n({rates[k]/rates['A']:.1f}×)",
                 ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax1.set_ylim(0, max(vals) * 1.18)

    # ----- right: multiplicative waterfall A→B→D and A→C→D -----
    moisture = d["moisture_alone_BA"]
    wind = d["wind_alone_CA"]
    combined = d["combined_DA"]
    ax2.bar([0], [1.0], color="#27ae60", edgecolor="black", label="baseline (A)")
    ax2.bar([1], [moisture], color="#f39c12", edgecolor="black")
    ax2.bar([2], [wind], color="#2980b9", edgecolor="black")
    ax2.bar([3], [combined], color="#c0392b", edgecolor="black")
    ax2.set_xticks(range(4))
    ax2.set_xticklabels([
        "baseline\n1.0×",
        f"× moisture\n{moisture:.2f}×",
        f"× wind\n{wind:.2f}×",
        f"= combined\n{combined:.1f}×",
    ], fontsize=9)
    ax2.set_ylabel("Amplification factor vs benign (×)\n평년 대비 증폭 배율")
    ax2.set_yscale("log")
    ax2.set_title(
        f"Multiplicative coupling: {moisture:.2f} × {wind:.2f} = "
        f"{moisture*wind:.1f} ≈ {combined:.1f}\n"
        f"(interaction ratio {d['interaction_ratio']:.3f}; 1.0 = perfectly multiplicative)",
        fontsize=10,
    )
    for i, v in enumerate([1.0, moisture, wind, combined]):
        ax2.text(i, v * 1.05, f"{v:.2f}×", ha="center", va="bottom",
                 fontsize=9, fontweight="bold")
    ax2.set_ylim(0.8, combined * 2.0)

    fig.suptitle(
        "Decomposing the 18× drought-Föhn spread amplification — "
        "Korean Pinus densiflora\n"
        "가뭄·강풍 결합에 의한 확산 속도 18배 증폭의 요인 분해",
        fontsize=12.5, fontweight="bold",
    )
    fig.text(
        0.5, -0.03,
        "Wind dominates (×12.8); drought adds ×1.4 on top. They couple "
        "multiplicatively because in Rothermel (1972) eq. 52 the moisture "
        "damping η_M and the wind factor (1+φ_w) are separate multiplicative "
        "terms. Multi-class Rothermel + Burgan 1979, dead 1-h = 12%, slope 0°.",
        ha="center", fontsize=8.6, style="italic", color="#555",
    )

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)
    return d


def main() -> None:  # pragma: no cover
    from rich.console import Console
    from rich.table import Table

    here = Path(__file__).resolve()
    out = here.parents[3] / "docs" / "figures" / "lfmc_wind_decomposition.png"
    console = Console()
    console.rule("[bold]LFMC×wind decomposition (Session 4)")
    d = make_figure(out)
    t = Table(title="Decomposition")
    t.add_column("quantity", style="bold")
    t.add_column("value", justify="right")
    t.add_row("moisture-alone (B/A)", f"{d['moisture_alone_BA']:.3f}×")
    t.add_row("wind-alone (C/A)", f"{d['wind_alone_CA']:.3f}×")
    t.add_row("combined (D/A)", f"{d['combined_DA']:.3f}×")
    t.add_row("product (B/A)(C/A)", f"{d['product_of_alones']:.3f}×")
    t.add_row("interaction ratio", f"{d['interaction_ratio']:.4f}")
    console.print(t)
    console.print(f"[green]done[/green]: {out}")


if __name__ == "__main__":  # pragma: no cover
    main()
