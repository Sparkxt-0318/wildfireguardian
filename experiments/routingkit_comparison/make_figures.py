"""Render report figures from results/*.json (matplotlib, static PNG)."""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

from common import *
import exp2_fire_evacuation as X

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
GOOD, SERIOUS, CRITICAL, NEUTRAL = "#0ca30c", "#ec835a", "#d03b3b", "#b8b7b1"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                     "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def outcome_bars(path, title, strategies, labels, keys, out):
    s = json.loads((RESULTS / path).read_text())["summary"]
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(strategies) + 1.4))
    y = np.arange(len(strategies))[::-1]
    left = np.zeros(len(strategies))
    for key, colour, name in [(keys[0], GOOD, "safe arrival"), (keys[1], CRITICAL, "unsafe (hit fire)"), (keys[2], NEUTRAL, "no plan / refused")]:
        v = np.array([s[k][key] for k in strategies], float)
        ax.barh(y, v, left=left, color=colour, edgecolor=SURFACE, linewidth=2, height=0.62, label=name)
        for yi, l, w in zip(y, left, v):
            if w >= 8:
                ax.text(l + w / 2, yi, f"{int(w)}", ha="center", va="center", color="white" if colour != NEUTRAL else INK, fontsize=9)
        left += v
    ax.set_yticks(y, labels)
    ax.set_xlabel("evacuee × held-out-fire cases")
    fig.suptitle(title, x=0.02, ha="left", fontsize=11)
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.16), frameon=False, fontsize=9)
    ax.xaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(RESULTS / out, dpi=130)
    plt.close(fig)


def compute_chart(out):
    e1 = json.loads((RESULTS / "exp1_static_speed.json").read_text())
    e2 = json.loads((RESULTS / "exp2_fire_evacuation.json").read_text())["summary"]
    b = e1["routingkit_bench"]
    rows = [
        ("RoutingKit CCH query (static, turn-aware)", b["turn_cch_query"]["median_us"] / 1000),
        ("RoutingKit CH query (static, turn-aware)", b["turn_ch_query"]["median_us"] / 1000),
        ("RoutingKit Dijkstra (static, turn-aware)", b["turn_dijkstra"]["median_us"] / 1000),
        ("RoutingKit time-dependent Dijkstra, fire closures", e2["rk_td_hull"]["median_compute_ms"]),
        ("RoutingKit CCH re-customize after fire update", b["turn_cch_full_recustomize_ms"]),
        ("Ours exact A*, fire (incl. 0.5 s hazard validation)", e2["ours_exact"]["median_compute_ms"]),
        ("Ours exact A*, no fire, 1 h horizon", e1["ours_astar"]["median_ms"]),
        ("Ours default 'baseline', no fire, 1 h horizon", 60000.0),
    ]
    tb = e1["ours_baseline"]
    notes = {rows[-1][0]: f"≥60 s ({tb['timeouts']}/{tb['n']} hit the 60 s cap)"}
    rows = [r for r in rows if r[1]]
    fig, ax = plt.subplots(figsize=(10, 4))
    y = np.arange(len(rows))[::-1]
    cols = [BLUE if r[0].startswith("RoutingKit") else ORANGE for r in rows]
    ax.barh(y, [r[1] for r in rows], color=cols, height=0.6)
    for yi, (_, v) in zip(y, rows):
        ax.text(v * 1.15, yi, notes.get(_, f"{v:,.3g} ms"), va="center", fontsize=9, color=INK2)
    ax.set_xscale("log")
    ax.set_yticks(y, [r[0] for r in rows], fontsize=9)
    ax.set_xlabel("median compute per query (ms, log scale)")
    fig.suptitle("Compute time per query, full Nangok graph (5,765 nodes / 13,976 edges)", x=0.02, ha="left", fontsize=11)
    ax.set_xlim(right=max(r[1] for r in rows) * 3000)
    ax.xaxis.grid(True, color=GRID, which="major")
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(RESULTS / out, dpi=130)
    plt.close(fig)


def scenario_map(out):
    road, A, bps, raw, hull = X.setup()
    shelters, evac = X.pick_sites(road, A, hull)
    e3 = json.loads((RESULTS / "exp3_rendezvous_safezone.json").read_text())["config"]
    g = road.grid
    fig, ax = plt.subplots(figsize=(7.5, 7))
    segs = np.stack([road.xy[road.eu], road.xy[road.ev]], 1) / 1000
    ax.add_collection(LineCollection(segs, colors="#9a9993", linewidths=0.35))
    amin = A.min(0).reshape(g["height"], g["width"])
    ext = np.array([g["x0"], g["x0"] + g["width"] * 500, g["y0"], g["y0"] + g["height"] * 500]) / 1000
    im = ax.imshow(np.where(amin < X.H, amin / 60, np.nan), origin="lower", extent=ext, alpha=0.55,
                   cmap="YlOrRd_r", vmin=-40, vmax=90)
    cb = plt.colorbar(im, shrink=0.7)
    cb.set_label("earliest fire arrival, any member (min after planning)")
    ax.plot(*road.xy[shelters].T / 1000, "^", color=GOOD, ms=10, mec="white", label="designated shelter (exp 2)")
    ax.plot(*road.xy[evac].T / 1000, "o", color=BLUE, ms=4, label="vehicle evacuee origin (exp 2)")
    ax.plot(*road.xy[e3["stations"]].T / 1000, "s", color=INK, ms=8, mec="white", label="fire-vehicle staging (exp 3)")
    ax.set_aspect("equal")
    ax.set_xlabel("EPSG:5179 x (km)")
    ax.set_ylabel("y (km)")
    ax.set_title("Synthetic wind-driven fire on the Nangok (Gangneung) road graph", loc="left", fontsize=11)
    ax.legend(loc="upper right", fontsize=8, frameon=True)
    fig.tight_layout()
    fig.savefig(RESULTS / out, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    outcome_bars("exp2_fire_evacuation.json", "Vehicle evacuation, 30 origins × 5 held-out fires",
                 ["rk_static_now", "rk_replan_60s", "rk_static_fcst", "rk_td_hull", "ours_exact", "ours_monotone"],
                 ["RK static, current fire", "RK static, re-plan every 60 s", "RK static, close all forecast fire",
                  "RK time-dependent + our checker", "Ours exact (A*)", "Ours + cross-time dominance"],
                 ("safe", "unsafe", "no_route"), "fig_exp2_outcomes.png")
    outcome_bars("exp3_rendezvous_safezone.json", "Pedestrian evacuation with fire-vehicle pickup, 40 people × 5 held-out fires",
                 ["WALK_STATIC", "WALK", "DOOR", "MEET_STATIC", "MEET", "BEST"],
                 ["Walk, fire-agnostic route", "Walk, fire-aware route", "Truck to the door", "Meet, fire-agnostic point",
                  "Meet, fire-aware optimal point", "Best of walk / meet"],
                 ("safe", "unsafe", "no_plan"), "fig_exp3_outcomes.png")
    compute_chart("fig_compute.png")
    scenario_map("fig_scenario.png")
