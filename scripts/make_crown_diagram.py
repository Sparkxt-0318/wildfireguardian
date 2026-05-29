"""Crown transition diagram: R_surface vs R_crown across a wind sweep (D2.4)."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties, findfont

from wildfireguardian.spread_model.crown_fire import (
    byram_intensity, critical_surface_intensity, crown_spread_rate,
)
from wildfireguardian.spread_model.rothermel import KOREAN_PINUS, compute_spread_rate
from wildfireguardian.spread_model.wind import korean_pine_waf

for cjk in ("Noto Sans CJK KR", "Nanum Gothic", "WenQuanYi Zen Hei"):
    try:
        findfont(FontProperties(family=cjk), fallback_to_default=False)
        matplotlib.rcParams["font.sans-serif"] = [cjk, "DejaVu Sans"]; matplotlib.rcParams["axes.unicode_minus"] = False; break
    except Exception:
        continue

waf = korean_pine_waf()
FMC = 40.0          # drought foliar moisture (%)
CBH, CBD = 4.0, 0.47
fine_load = KOREAN_PINUS.fine_fuel_load_kg_m2
i_o = critical_surface_intensity(CBH, FMC)

u10 = np.linspace(0.5, 25.0, 80)
R_surf, R_crown, I_B = [], [], []
for u in u10:
    rs = compute_spread_rate(KOREAN_PINUS, dead_moisture=0.08, live_moisture=0.40,
                             wind_speed_ms=u * waf).rate_m_min
    R_surf.append(rs)
    I_B.append(byram_intensity(rs, fine_load))
    R_crown.append(crown_spread_rate(u, CBD, fine_fuel_moisture_pct=8.0))
R_surf, R_crown, I_B = map(np.array, (R_surf, R_crown, I_B))

# Transition wind: where I_B crosses I_o.
cross = np.where(I_B >= i_o)[0]
u_trans = u10[cross[0]] if len(cross) else None

fig, ax = plt.subplots(figsize=(9, 6), dpi=120)
ax.plot(u10, R_surf, color="#2980b9", lw=2.4, label="surface ROS (Rothermel, midflame=WAF·U₁₀)")
ax.plot(u10, R_crown, color="#c0392b", lw=2.4, label="active crown ROS (Cruz/Alexander 2005)")
if u_trans is not None:
    ax.axvline(u_trans, color="#000", ls="--", lw=1.3)
    ax.annotate(f"crown transition\n(I_B ≥ I_o, FMC {FMC:.0f}%)\nU₁₀ ≈ {u_trans:.1f} m/s",
                xy=(u_trans, crown_spread_rate(u_trans, CBD, 8.0)),
                xytext=(u_trans + 1.5, 25), fontsize=9,
                arrowprops=dict(arrowstyle="->", lw=0.8))
ax.set_xlabel("10-m wind speed U₁₀ (m/s)  /  10m 풍속")
ax.set_ylabel("Rate of spread (m/min)  /  확산 속도")
ax.set_title("Crown-fire regime switch — Korean pine (Session 6 D2)\n"
             "한국 소나무 수관화 전이: 지표화 vs 수관화 확산 속도\n"
             "(WAF crushes surface ROS; crown ROS bypasses it once transition is met)",
             fontsize=11.5, fontweight="bold")
ax.legend(loc="upper left")
ax.grid(True, alpha=0.3)
ax.set_ylim(0, max(R_crown.max() * 1.1, 5))
fig.text(0.5, -0.02,
         f"Drought foliar moisture {FMC:.0f}% → critical intensity I_o = {i_o:.0f} kW/m. "
         "Below transition the fire creeps as a surface fire; above it, it runs in the canopy. "
         "This is why surface-only Rothermel missed ~90% of the Yeongdeok area.",
         ha="center", fontsize=8.4, style="italic", color="#555")
out = Path(__file__).resolve().parents[1] / "docs" / "figures" / "crown_transition_diagram.png"
fig.savefig(out, bbox_inches="tight", dpi=120)
print(f"I_o={i_o:.0f} kW/m; transition at U10≈{u_trans:.1f} m/s; wrote {out}")
