"""Session 7 D4: dR/dU vs midflame wind, marked at the real Yeongdeok wind."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties, findfont

from wildfireguardian.spread_model import interaction as I

for cjk in ("Noto Sans CJK KR", "Nanum Gothic", "WenQuanYi Zen Hei"):
    try:
        findfont(FontProperties(family=cjk), fallback_to_default=False)
        matplotlib.rcParams["font.sans-serif"] = [cjk, "DejaVu Sans"]; matplotlib.rcParams["axes.unicode_minus"] = False; break
    except Exception:
        continue

u = np.linspace(0.2, 5.0, 60)
dry = np.array([I.dR_dU(I.DRY_DEAD, float(x)) for x in u])
moist = np.array([I.dR_dU(I.MOIST_DEAD, float(x)) for x in u])
u_yd = I.YEONGDEOK_MIDFLAME_U

fig, ax = plt.subplots(figsize=(9, 6), dpi=120)
ax.plot(u, dry, color="#c0392b", lw=2.4, label=f"dry fuel (dead {I.DRY_DEAD*100:.0f}%)")
ax.plot(u, moist, color="#2980b9", lw=2.4, label=f"moist fuel (dead {I.MOIST_DEAD*100:.0f}%)")
ax.axvline(u_yd, color="#000", ls="--", lw=1.4)
dry_yd, moist_yd = I.dR_dU(I.DRY_DEAD, u_yd), I.dR_dU(I.MOIST_DEAD, u_yd)
ax.plot([u_yd], [dry_yd], "o", color="#c0392b", ms=9, zorder=5)
ax.plot([u_yd], [moist_yd], "o", color="#2980b9", ms=9, zorder=5)
ax.annotate(f"Yeongdeok actual midflame\nU = {u_yd:.2f} m/s\n"
            f"(10-m 13.9 × WAF 0.10)\n"
            f"∂R/∂U: dry {dry_yd:.2f}, moist {moist_yd:.2f} m/min per m/s",
            xy=(u_yd, dry_yd), xytext=(u_yd + 0.6, dry_yd + 0.3),
            fontsize=9, arrowprops=dict(arrowstyle="->", lw=0.8),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#888", alpha=0.95))
ax.set_xlabel("Midflame wind speed (m/s)  /  화염 중간높이 풍속")
ax.set_ylabel("∂R/∂U  (m/min per m/s)  /  풍속 한계효과")
ax.set_title("Marginal wind effect vs the wind the fire ACTUALLY feels (Session 7 D4)\n"
             "실제 화염이 겪는 풍속에서의 풍속 한계효과 (보정된 화염중심 풍속)",
             fontsize=11.5, fontweight="bold")
ax.legend(loc="upper left"); ax.grid(True, alpha=0.3)
fig.text(0.5, -0.02,
         f"The dry/moist ratio is {dry_yd/moist_yd:.2f}, constant across U (Rothermel is "
         "separable; Session 5). The headline is anchored to the realistic 1.39 m/s, not 4 m/s. "
         "Absolute marginal effects are modest because the WAF-corrected wind is low.",
         ha="center", fontsize=8.4, style="italic", color="#555")
out = Path(__file__).resolve().parents[1] / "docs" / "figures" / "dRdU_vs_wind.png"
fig.savefig(out, bbox_inches="tight", dpi=120)
print(f"at U={u_yd:.2f}: dry {dry_yd:.2f}, moist {moist_yd:.2f}, ratio {dry_yd/moist_yd:.3f}; wrote {out}")
