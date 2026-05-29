"""Side-by-side ambient vs topographic wind speed over Yeongdeok (Session 6 D1)."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties, findfont

from wildfireguardian.data_io.raster import load_dem
from wildfireguardian.spread_model.topo_wind import topographic_wind_field
from wildfireguardian.utils.regions import YEONGDEOK_2025

for cjk in ("Noto Sans CJK KR", "Nanum Gothic", "WenQuanYi Zen Hei"):
    try:
        findfont(FontProperties(family=cjk), fallback_to_default=False)
        matplotlib.rcParams["font.sans-serif"] = [cjk, "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue

U_AMB = 13.9   # 10-m ambient (Mar 22 mean)
THETA_TO = (282.0 + 180.0) % 360.0   # blowing toward (wind from 282°)

dem = load_dem(YEONGDEOK_2025, source="srtm", cell_size_m=100.0, use_cache=True)
Z = dem.values
U, theta = topographic_wind_field(U_AMB, THETA_TO, Z, 100.0)

fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), dpi=120)
im0 = axes[0].imshow(Z, cmap="terrain", origin="upper")
axes[0].set_title("Yeongdeok SRTM terrain (m)\n영덕 지형")
plt.colorbar(im0, ax=axes[0], shrink=0.8)

im1 = axes[1].imshow(np.full_like(Z, U_AMB), cmap="viridis", origin="upper",
                     vmin=U.min(), vmax=U.max())
axes[1].set_title(f"Ambient (uniform) 10-m wind = {U_AMB:.1f} m/s\n균일 바람")
plt.colorbar(im1, ax=axes[1], shrink=0.8)

im2 = axes[2].imshow(U, cmap="viridis", origin="upper", vmin=U.min(), vmax=U.max())
axes[2].set_title("Topographic 10-m wind field (m/s)\n지형 효과 반영 바람\n"
                  f"(range {U.min():.1f}–{U.max():.1f}, valleys accelerate)")
plt.colorbar(im2, ax=axes[2], shrink=0.8)

for ax in axes:
    ax.set_xlabel("east →"); ax.set_ylabel("← north (row)")

fig.suptitle("Topographic wind heuristic over Yeongdeok — Föhn slope/channel/lee "
             "(Session 6 D1)\n지형 기반 풍속장 (양강지풍 효과: 경사·협곡·풍하측)",
             fontsize=12, fontweight="bold")
fig.tight_layout(rect=(0, 0, 1, 0.93))
out = Path(__file__).resolve().parents[1] / "docs" / "figures" / "topo_wind_yeongdeok.png"
fig.savefig(out, bbox_inches="tight", dpi=120)
print(f"ambient {U_AMB:.1f} m/s → topo field {U.min():.1f}–{U.max():.1f} m/s "
      f"(mean {U.mean():.1f}); wrote {out}")
