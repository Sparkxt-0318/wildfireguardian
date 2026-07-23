#!/usr/bin/env python
"""Render the S2->S3 divergence frame of the offline demo to a 1920x1080 PNG.

This is a STATIC frame render built from the SAME committed bundle the offline
page inlines (``data/processed/demo_data.json`` -> ``scenario_geometry``) using
the demo's own colour language and drawing rules (fronts by isochrone timestep,
naive route split at the real ``failure_point`` into a live + an ash segment,
future-aware route bending to a shelter). It draws ONLY real npz geometry — no
smoothing, no fabricated lines. Use when a headless browser is unavailable.

Run:  python scripts/render_divergence_frame.py
Out:  demo/s2_s3_divergence_1920x1080.png
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Polygon, Circle, FancyBboxPatch
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parents[1]
DATA = json.loads((REPO / "data/processed/demo_data.json").read_text())
OUT = REPO / "demo/s2_s3_divergence_1920x1080.png"

# demo palette
BG = "#05070A"; NAIVE = "#E6A23C"; ASH = "#6B6257"; FUTURE = "#33C4B5"
INK = "#E8EDF2"; SAFE = "#4C9A6A"; HAIR = "#1E2A36"; MUTE = "#6C7787"
FIRE = ["#F2C14E", "#E8752B", "#C1361E"]

# Korean-capable font
for cand in ["Noto Sans CJK KR", "Noto Sans CJK JP", "NanumGothic"]:
    try:
        fm.findfont(cand, fallback_to_default=False); KR = cand; break
    except Exception:
        KR = "DejaVu Sans"
plt.rcParams["font.family"] = KR

def _hex(h): return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))
def fire_color(tn):
    s = max(0.0, min(1.0, tn)) * 2; i = min(1, int(s)); f = s - i
    a, b = _hex(FIRE[i]), _hex(FIRE[min(i + 1, 2)])
    return tuple((a[j] + (b[j] - a[j]) * f) / 255 for j in range(3))
def mix(h1, h2, f):
    a, b = _hex(h1), _hex(h2); return tuple((a[j] + (b[j] - a[j]) * f) / 255 for j in range(3))

g = DATA["scenario_geometry"]
assert g and g.get("present"), "scenario_geometry missing — run export_demo_data.py with routing_demo.npz present"
fronts = g["fire_fronts"]; naive = np.array(g["routes"]["naive"]); fa = np.array(g["routes"]["future_aware"])
origin = np.array(g["origin"]); fail = np.array(g["failure_point"]); shelters = np.array(g["shelters"])

# split naive at nearest vertex to failure_point (demo rule)
fi = int(np.argmin(((naive - fail) ** 2).sum(1)))
preN, doomN = naive[:fi + 1], naive[fi:]

fig = plt.figure(figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(BG)
# map axis (left square) + panel axis (right)
axm = fig.add_axes([0.02, 0.06, 0.60, 0.88]); axp = fig.add_axes([0.64, 0.06, 0.34, 0.88])
for ax in (axm, axp):
    ax.set_facecolor(BG)
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
axm.set_xlim(0, 1); axm.set_ylim(1, 0); axm.set_aspect("equal")  # y flipped: north=top

# graticule
for i in range(1, 8):
    axm.plot([i/8, i/8], [0, 1], color=HAIR, lw=0.6, zorder=1)
    axm.plot([0, 1], [i/8, i/8], color=HAIR, lw=0.6, zorder=1)

# hazard HEAT FIELD (probability) — decoded from the same PNG the demo inlines,
# placed at the same normalized box. Honest to the unthresholded haz_stack field.
import base64 as _b64, io as _io
n = len(g["heat_frames"])
hb = g["heat_box"]
_himg = g["heat_frames"][-1]["img"].split(",", 1)[1]
_harr = plt.imread(_io.BytesIO(_b64.b64decode(_himg)))
axm.imshow(_harr, extent=[hb[0], hb[2], hb[3], hb[1]], origin="upper",
           interpolation="bilinear", zorder=2)

# shelters (real OSM refuge candidates) — faint
axm.scatter(shelters[:, 0], shelters[:, 1], s=9, c=SAFE, alpha=0.28, edgecolors="none", zorder=3)

# routes (casing then stroke)
def route(pts, color, lw=3.2, alpha=1.0, z=5):
    axm.plot(pts[:, 0], pts[:, 1], color=BG, lw=lw + 3, solid_capstyle="round", solid_joinstyle="round", zorder=z)
    axm.plot(pts[:, 0], pts[:, 1], color=color, lw=lw, alpha=alpha, solid_capstyle="round", solid_joinstyle="round", zorder=z + 0.1)
route(fa, FUTURE, 3.4, 1.0, 6)                      # teal bends around
route(preN, NAIVE, 3.2, 1.0, 5)                     # amber live segment
route(doomN, mix(NAIVE, ASH, 1.0), 3.2, 0.5, 4.5)   # amber walks in -> ash

# origin, ignition, failure, shelter reached
axm.add_patch(Circle(origin, 0.010, fill=False, ec=INK, lw=2, zorder=8))
if g.get("ignition"):
    ig = g["ignition"]; axm.scatter([ig[0]], [ig[1]], marker="^", s=110, c=FIRE[0], edgecolors=BG, lw=1.4, zorder=8)
okpt = fa[-1]
axm.scatter([okpt[0]], [okpt[1]], s=150, marker="o", facecolor=SAFE, edgecolors=INK, lw=1.6, zorder=9)
axm.scatter([fail[0]], [fail[1]], s=90, marker="X", c=ASH, edgecolors=INK, lw=1.2, zorder=9)

# in-map labels + verdicts
def tag(xy, text, fc, ec, tcol, dx=0.0, dy=0.0, fs=15, weight="bold"):
    axm.annotate(text, xy=(xy[0]+dx, xy[1]+dy), color=tcol, fontsize=fs, weight=weight,
                 ha="center", va="center", zorder=12,
                 bbox=dict(boxstyle="round,pad=0.35", fc=fc, ec=ec, lw=1.2, alpha=0.95))
tag((preN[len(preN)//2][0], preN[len(preN)//2][1]), "주민 대피 경로(화재 예측 없음)", "#0A0F14", NAIVE, NAIVE, dy=-0.055, fs=14)
tag(okpt, "미래 인지 경로", "#0A0F14", FUTURE, FUTURE, dy=0.06, dx=-0.02, fs=14)
tag(fail, "→ 대피 실패", (0.42,0.38,0.34), ASH, "#F1D2C6", dx=0.085, dy=-0.02, fs=13)
tag(okpt, "→ 대피 성공", (0.30,0.60,0.42), SAFE, "#DDF3E7", dx=0.02, dy=-0.05, fs=13)

# ---- right panel: scene + narrative + legend ----
def T(y, s, col=INK, fs=20, weight="normal", ha="left", x=0.0, family=KR):
    axp.text(x, y, s, color=col, fontsize=fs, weight=weight, ha=ha, va="top", transform=axp.transAxes, family=family)
axp.set_xlim(0,1); axp.set_ylim(0,1)
T(0.99, "S2 → S3", MUTE, 18, "bold")
T(0.955, "갈림길  →  결과", INK, 30, "bold")
axp.plot([0,1],[0.905,0.905], color=HAIR, lw=1, transform=axp.transAxes)
T(0.87, "동일 출발점, 두 갈래.", INK, 20)
T(0.828, "예측 확률장을 모르는 주민 대피 경로는", NAIVE, 17)
T(0.792, "미래 고위험 영역 속으로 들어가 실패하고,", "#AEB6BF", 16)
T(0.75, "미래 인지 경로는 고위험 영역을 우회해", FUTURE, 17)
T(0.714, "대피소에 도달합니다.", "#AEB6BF", 16)

# legend
ly = 0.60
items = [("주민 대피 경로(화재 예측 없음)", NAIVE, "-"),
         ("  · 진입 구간 → 소실(ash)", ASH, "-"),
         ("미래 인지 경로", FUTURE, "-"),
         ("대피소 도달 (실제 OSM 후보)", SAFE, "o"),
         ("예측 화재 확률장 (haz_stack, 실측)", FIRE[1], "s")]
for lab, col, mk in items:
    if mk == "-":
        axp.add_line(Line2D([0.0,0.06],[ly+0.012,ly+0.012], color=col, lw=4, transform=axp.transAxes, solid_capstyle="round"))
    else:
        axp.scatter([0.03],[ly+0.012], s=90, marker=mk, c=col, edgecolors=INK, lw=1, transform=axp.transAxes)
    T(ly+0.03, lab, "#D4DAE1", 15, x=0.09)
    ly -= 0.062

axp.plot([0,1],[0.235,0.235], color=HAIR, lw=1, transform=axp.transAxes)
nnodes = len(naive); fnodes = len(fa)
T(0.205, f"실측 지오메트리 · routing_demo.npz", MUTE, 14, "bold")
T(0.165, f"naive {nnodes}노드 · fire-aware {fnodes}노드 · 대피소 {len(shelters)}", "#AEB6BF", 14)
T(0.128, f"화재 확률장 {n}개 시점 · 실측 spread_v2 (out-of-sample)", "#AEB6BF", 14)
T(0.09, "실패 지점 = naive_node_haz ≥ 0.5 최초 노드", "#AEB6BF", 14)

fig.text(0.02, 0.005, "WildfireGuardian · S2–S3 divergence frame (t≈0.72) — rendered from committed demo_data.json geometry",
         color=MUTE, fontsize=12, ha="left")
fig.savefig(OUT, facecolor=BG, dpi=100)
print("wrote", OUT, "size", OUT.stat().st_size)
