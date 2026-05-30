"""Session 7 D3: area-capture vs canopy base height (the fragility-as-finding)."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties, findfont

from wildfireguardian.data_io.raster import load_dem
from wildfireguardian.data_io.weather import load_aws_wind
from wildfireguardian.spread_model.wind import korean_pine_waf
from wildfireguardian.utils.regions import YEONGDEOK_2025

# import the run helper from the sweep script
import importlib.util
spec = importlib.util.spec_from_file_location(
    "cs", Path(__file__).resolve().parent / "crown_sensitivity.py")
cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)

for cjk in ("Noto Sans CJK KR", "Nanum Gothic", "WenQuanYi Zen Hei"):
    try:
        findfont(FontProperties(family=cjk), fallback_to_default=False)
        matplotlib.rcParams["font.sans-serif"] = [cjk, "DejaVu Sans"]; matplotlib.rcParams["axes.unicode_minus"] = False; break
    except Exception:
        continue

from wildfireguardian.validation import load_case
from wildfireguardian.validation.harness import load_observed_perimeter_series

repo = Path(__file__).resolve().parents[1]
case = load_case(repo / "data" / "validation_cases" / "yeongdeok_2025.json")
obs = load_observed_perimeter_series(case)
obs_final = min(obs, key=lambda p: abs(p.time_min - 1440.0)).polygon
dem = load_dem(YEONGDEOK_2025, source="srtm", cell_size_m=cs.CELL, use_cache=True)
s = load_aws_wind(YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)), source="auto")
smp = [s.at(datetime(2025, 3, 22, h, 0)) for h in range(12, 24)]
u10 = float(np.mean([x.speed_10m_ms for x in smp])); wdir = float(np.mean([x.direction_from_deg for x in smp]))
waf = korean_pine_waf()

cbhs = [2.0, 3.0, 4.0, 5.0]
cap119 = []
for cbh in cbhs:
    r = cs.run_one(cbh, 0.7, 119.0, dem, u10, wdir, waf, obs_final)
    cap119.append(r["capture"] * 100)
    print(f"FMC119 CBH {cbh}: capture {r['capture']*100:.0f}% IoU {r['iou']:.2f}")

# Artifact point (FMC 40 at CBH 4) — the Session-6 value, from the diagnostic.
artifact_cbh, artifact_cap = 4.0, 54.0

fig, ax = plt.subplots(figsize=(8.5, 6), dpi=120)
ax.plot(cbhs, cap119, "o-", color="#2980b9", lw=2.4, ms=8,
        label="corrected foliar moisture 119 % (measured)")
ax.axvspan(3.6, 5.2, color="#2ecc71", alpha=0.15, label="measured Korean CBH range (Lee 2018)")
ax.scatter([artifact_cbh], [artifact_cap], color="#c0392b", s=130, zorder=5, marker="X",
           label="Session-6 ARTIFACT (foliar moisture 40 %)")
ax.annotate("Session-6 '54%' used 40% foliar moisture\n(the surface drought-LFMC) —\nphysically wrong for live tree crowns",
            xy=(artifact_cbh, artifact_cap), xytext=(2.6, 44), fontsize=9, color="#c0392b",
            arrowprops=dict(arrowstyle="->", color="#c0392b", lw=0.9))
ax.set_xlabel("Canopy base height CBH (m)  /  수관 하단 높이")
ax.set_ylabel("24-h area-capture (% of observed)  /  관측 면적 포착률")
ax.set_title("Crown initiation is acutely sensitive to canopy base height\n"
             "수관화 개시는 수관 하단 높이에 매우 민감 (Session 7 진단)",
             fontsize=12, fontweight="bold")
ax.set_ylim(0, 60); ax.legend(loc="upper right", fontsize=8.5); ax.grid(True, alpha=0.3)
fig.text(0.5, -0.02,
         "At the measured stand structure (CBH 3.6-5.2 m) and measured foliar moisture (119%), "
         "area-capture is ~9% — the surface-only baseline. The Session-6 54% was an artifact of "
         "feeding the surface drought-LFMC (40%) into the tree-crown Van Wagner check.",
         ha="center", fontsize=8.3, style="italic", color="#555")
out = repo / "docs" / "figures" / "crown_initiation_vs_cbh.png"
fig.savefig(out, bbox_inches="tight", dpi=120)
print(f"wrote {out}")
