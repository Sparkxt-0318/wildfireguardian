"""Two figures for RESULTS.md: held-out frontier (area vs miss) and the learning curve. Light surface, reference palette slots 1-3."""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from lib import *

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C = {"FIXED": "#52514e", "QUANTILE": "#2a78d6", "META": "#eb6834", "KALMAN": "#6250d6", "PERSIST": "#1baf7a", "M_ref": "#2a78d6"}
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF, "text.color": INK})


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)


D = Data(5, "/tmp/w/work")
dev = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
idx = D.rows_of(dev)
fig, ax = plt.subplots(figsize=(6.6, 4.2))
ends = {}
for m in ("FIXED", "KALMAN", "META", "QUANTILE"):
    z = np.load(f"derived/step2/{m}_h5.npz")
    fl, mi, ar = evaluate(D, idx, z["s"], z["kappa"])
    x, y = 100 * mi.mean(0), ar.mean(0)
    o = np.argsort(x)
    ax.plot(x[o], y[o], color=C[m], lw=2.0, ls="--" if m == "FIXED" else "-")
    ax.plot([x[L1]], [y[L1]], "o", color=C[m], ms=7, mec=SURF, mew=2)
    ends[m] = (x[o][-1], y[o][-1])
ax.set_xlim(4, 20); ax.set_ylim(150, 700)
ax.axvline(10, color=INK2, lw=1, ls=":")
ax.text(10.15, 690, "10% target", color=INK2, fontsize=9, va="top")
lab = {"FIXED": (13.6, 305, "FIXED margin"), "QUANTILE": (11.2, 188, "QUANTILE (GBM)"),
       "META": (12.0, 440, "META (Reptile, adapted)"), "KALMAN": (11.6, 610, "KALMAN (per-fire, adapted)")}
for m, (x, y, t) in lab.items():
    ax.text(x, y, t, color=C[m], fontsize=9.5, fontweight="bold")
ax.set_xlabel("held-out miss rate, % of issue hours (fire-weighted)")
ax.set_ylabel("flagged area, km2 (fire-weighted mean)")
ax.set_title("Equal-miss comparison, 28 held-out California fires, 5 h ahead", fontsize=11, loc="left", color=INK)
fig.text(0.01, -0.02, "Dots: the margin each method calibrated to 10% on training fires. Curves: the same margin scaled 0.25x to 4x on the held-out fires.",
         fontsize=8, color=INK2, va="top")
style(ax); fig.tight_layout(); fig.savefig("fig/fig1_frontier.png", dpi=200, bbox_inches="tight"); plt.close(fig)

c = json.load(open("derived/step1_curve.json"))
ns = sorted(int(k) for k in c)
fig, ax = plt.subplots(figsize=(6.6, 4.0))
for m, lab_ in (("PERSIST", "PERSIST"), ("FIXED", "FIXED margin"), ("M_ref", "M_ref (GBM, all features)")):
    ax.plot(ns, [c[str(n)][m]["frontier"] for n in ns], "-o", color=C[m], lw=2.0, ms=6, mec=SURF, mew=1.5)
ax.text(16.2, 515, "PERSIST", color=C["PERSIST"], fontsize=9.5, fontweight="bold")
ax.text(12.5, 357, "FIXED margin", color=C["FIXED"], fontsize=9.5, fontweight="bold")
ax.text(12.5, 262, "M_ref (GBM, all features)", color=C["M_ref"], fontsize=9.5, fontweight="bold")
ax.set_xlabel("number of training fires"); ax.set_ylabel("area at 10% held-out miss, km2")
ax.set_xticks(ns); ax.set_ylim(200, 560)
ax.set_title("Learning curve: skill is flat from 4 to 24 training fires", fontsize=11, loc="left", color=INK)
style(ax); fig.tight_layout(); fig.savefig("fig/fig2_learning_curve.png", dpi=200, bbox_inches="tight"); plt.close(fig)
print("ok")
