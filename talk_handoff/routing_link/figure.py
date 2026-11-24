"""The one figure (PROTOCOL.md section 8): cells blocked by fire alone, cells exposure adds, and the roads.

Five colours only (ink 1A1A1A, grey 6B6B6B, blue 2F5D8A with light tints, deep red 8A362F), transparent background,
no title inside. Wording: a road is "blocked", never "closes".
"""
from __future__ import annotations

import numpy as np

INK, GREY, BLUE, RED = "#1A1A1A", "#6B6B6B", "#2F5D8A", "#8A362F"
BLUE_TINT = "#C5D3E3"  # light tint of 2F5D8A (about 27 % strength on white)


def make(graph, grid, fire_min, combined_min, stem, horizon_label=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D

    f = np.isfinite(np.asarray(fire_min, float))          # NaN and +inf: not blocked inside the horizon
    c = np.isfinite(np.asarray(combined_min, float))
    cls = np.where(f, 1, np.where(c, 2, 0)).astype(float)
    cls[cls == 0] = np.nan
    x0, res, ytop = grid.x0, grid.res, grid.ytop
    ext = [x0 / 1000, (x0 + grid.W * res) / 1000, (ytop - grid.H * res) / 1000, ytop / 1000]
    fig, ax = plt.subplots(figsize=(6.4, 8.2), dpi=300)
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    ax.imshow(cls, extent=ext, origin="upper", cmap=ListedColormap([BLUE_TINT, RED]), vmin=1, vmax=2,
              interpolation="nearest", zorder=1)
    xy = {n["id"]: (n["x"] / 1000, n["y"] / 1000) for n in graph["nodes"]}
    seen = set()
    for e in graph["edges"]:
        k = tuple(sorted((e["u"], e["v"])))
        if k in seen:
            continue
        seen.add(k)
        (xa, ya), (xb, yb) = xy[e["u"]], xy[e["v"]]
        ax.plot([xa, xb], [ya, yb], color=INK, lw=0.45, solid_capstyle="round", zorder=2)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_color(GREY)
    ax.tick_params(colors=GREY, labelsize=7)
    ax.set_xlabel("x (km, EPSG:5070)", color=GREY, fontsize=8)
    ax.set_ylabel("y (km, EPSG:5070)", color=GREY, fontsize=8)
    h = [Patch(facecolor=BLUE_TINT, edgecolor="none", label="Blocked by fire arrival"),
         Patch(facecolor=RED, edgecolor="none", label="Blocked by exposure only (residents, visibility p ≥ 0.5*)"),
         Line2D([0], [0], color=INK, lw=0.8, label="Road (OpenStreetMap)")]
    leg = ax.legend(handles=h, loc="upper left", bbox_to_anchor=(0.0, -0.07), ncol=1, fontsize=7, frameon=False)
    for t in leg.get_texts():
        t.set_color(INK)
    note = "*assumption: 10 m building-egress visibility; 0.5 level our choice"
    if horizon_label:
        note = horizon_label + "  ·  " + note
    fig.text(0.01, 0.005, note, color=GREY, fontsize=6)
    fig.tight_layout()
    for ext_ in ("png", "svg", "pdf"):
        fig.savefig("%s.%s" % (stem, ext_), transparent=True)
    plt.close(fig)
