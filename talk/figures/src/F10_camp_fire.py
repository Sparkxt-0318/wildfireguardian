"""F10 Camp Fire: road-closed reports caught early, and the cost.

Slide 10, full slide. Left: map of the 195 held-out road-closed reports (Paradise, California, 8 Nov 2018);
blue if the frozen spread margin R(h) had the road closed by the report (15 min tolerance), brick-red outline if not.
Right: minutes early for the caught reports, median marked. Beneath, in ochre: passable roads wrongly closed.
Source: research/kcf-camp/out/test1_road_state.csv and out/tests12.json (strict scoring, MR = frozen R(h)).

Road lines: the Paradise road graph is not committed (only OSM tile checksums are). If PARADISE_GRAPH points to
the graph.json made by research/kcf-camp/build_graph_osm.py, roads are drawn in grey; otherwise none are drawn.
"""
import io
import json
import math
import os

import numpy as np
import pandas as pd

import style as S
from figkit import add_caption, boxed_legend, grid, save
from prov import Ledger, git_show

C = "research/kcf-camp"
T = None


def read(L):
    df = pd.read_csv(io.BytesIO(git_show(f"{C}/out/test1_road_state.csv")))
    placed = df[df["match"] != "not_placed"]
    closed = placed[placed["class"] == "ROAD_CLOSED"].copy()
    passable = placed[placed["class"] == "ROAD_PASSABLE"]
    t = L.json(f"{C}/out/tests12.json")["test1"]["strict"]["MR"]
    hits = (closed["state_MR_strict"] == "HIT").sum()
    assert hits == t["hits"] and len(closed) == t["closed_scored"]
    fc = (passable["state_MR_strict"] == "FALSE_CLOSURE").sum()
    assert fc == t["false_closures"] and len(passable) == t["passable_scored"]
    L.add("Held-out road-closed reports placed on the map", len(closed), file=f"{C}/out/test1_road_state.csv",
          field="rows with class == ROAD_CLOSED and match != not_placed; lat, lon", expected="195")
    L.add("Reports where the method had the road closed by the report time", hits, shown=f"{hits} of {len(closed)}",
          file=f"{C}/out/tests12.json", field="test1.strict.MR.hits / closed_scored", n=f"{len(closed)} reports",
          expected="170 of 195", note="cross-checked against state_MR_strict == HIT in test1_road_state.csv")
    caught = closed[closed["state_MR_strict"] == "HIT"]
    early = -caught["err_MR_strict"].astype(float)
    med = float(np.median(early))
    L.add("Median minutes early, caught reports", med, unit="min", shown=f"{med:.0f} min",
          file=f"{C}/out/test1_road_state.csv", field="median of -err_MR_strict over rows with state_MR_strict == HIT",
          n=f"{len(caught)} reports", expected="119 min",
          note="DIFFERENT FROM EXPECTED. 119 min (numbers.json tests12.test1.strict.MR.time_error_min_closed_rows."
               f"median = {t['time_error_min_closed_rows']['median']}) is the median over all "
               f"{t['time_error_min_closed_rows']['n']} closed reports, caught and missed. The figure plots the caught "
               "reports only, as asked, so it marks their median.")
    L.add("Passable roads the method had closed", fc, shown=f"{fc} of {len(passable)}", file=f"{C}/out/tests12.json",
          field="test1.strict.MR.false_closures / passable_scored", n=f"{len(passable)} reports", expected="22 of 23")
    global T
    T = t
    return closed, caught, early, med, hits, fc, len(passable)


def project(lat, lon, lat0, lon0):
    kx = 111.320 * math.cos(math.radians(lat0))
    return (lon - lon0) * kx, (lat - lat0) * 110.574


def main():
    L = Ledger("F10", "Camp Fire: closures caught before the report, and the cost")
    closed, caught, early, med, hits, fc, npass = read(L)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    lat0, lon0 = closed["lat"].mean(), closed["lon"].mean()
    x, y = project(closed["lat"].to_numpy(), closed["lon"].to_numpy(), lat0, lon0)
    hit = (closed["state_MR_strict"] == "HIT").to_numpy()
    # ---------------- (a) map
    mx0, mx1 = x.min() - 0.6, x.max() + 0.6
    my0, my1 = y.min() - 0.6, y.max() + 1.8
    mh = 4.15
    mw = min(mh * (mx1 - mx0) / (my1 - my0), 6.6)
    axm = fig.add_axes([0.45 / W, 1 - (1.1 + mh) / H, mw / W, mh / H])
    axm.set_xlim(mx0, mx1)
    axm.set_ylim(my0, my1)
    axm.set_aspect("equal", adjustable="box")
    axm.set_xticks([])
    axm.set_yticks([])
    gpath = os.environ.get("PARADISE_GRAPH")
    if gpath and os.path.exists(gpath):
        L.note(f"Roads drawn from {gpath}")
    else:
        L.note("No road lines drawn: the Paradise road graph is not committed (DECISIONS.md D12).")
    axm.scatter(x[hit], y[hit], s=40, marker="o", color=S.OURS, linewidths=0, zorder=4,
                label=f"closed by the report time ({hits})")
    axm.scatter(x[~hit], y[~hit], s=55, marker="s", facecolors=S.WHITE, edgecolors=S.FIRE, linewidths=1.3, zorder=3,
                label=f"not yet closed ({len(closed) - hits})")
    sb = 2.0
    bx, by = mx1 - sb - 0.9, my0 + 0.6
    axm.plot([bx, bx + sb], [by, by], color=S.INK, lw=2.5, solid_capstyle="butt")
    axm.text(bx + sb / 2, by + 0.3, "2 km", ha="center", va="bottom")
    axm.annotate("", xy=(mx1 - 0.7, my1 - 0.5), xytext=(mx1 - 0.7, my1 - 1.7),
                 arrowprops=dict(arrowstyle="-|>,head_length=0.5,head_width=0.25", color=S.INK, lw=1.2))
    axm.text(mx1 - 1.0, my1 - 1.1, "N", ha="right", va="center")
    boxed_legend(axm, loc="lower left", bbox_to_anchor=(0.0, 1.03), borderaxespad=0.0, ncol=2, handletextpad=0.6,
                 columnspacing=1.2)
    S.panel_letter(fig, 0.45, 0.3, "a")
    # ---------------- (b) minutes early
    l, t, w, h = 9.0, 0.55, 3.6, 4.7
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    grid(ax, axis="y")
    rng = np.random.RandomState(5)
    xs = rng.uniform(-0.3, 0.3, len(early))
    ax.scatter(xs, early, s=22, marker="o", facecolors=S.WHITE, edgecolors=S.OURS, linewidths=0.9)
    ax.plot([-0.45, 0.45], [med, med], color=S.INK, lw=2)
    ax.annotate(f"median {med:.0f} min", (0.45, med), xytext=(8, 0), textcoords="offset points", va="center")
    ax.axhline(0, color=S.INK, lw=0.8, ls=(0, (3, 2)))
    ax.set_xlim(-0.55, 1.75)
    top = float(np.ceil(early.max() / 60) * 60)
    ax.set_ylim(-60, top + 30)
    ax.set_yticks(np.arange(0, top + 1, 240))
    ax.set_xticks([])
    ax.set_ylabel("Minutes closed before the report")
    S.panel_letter(fig, 7.55, 0.3, "b")
    hc = T["hit_ci95"]
    fcc = T["false_closure_ci95"]
    cap = add_caption(fig, (
        f"Figure 10. Camp Fire, Paradise, California, 8 November 2018. (a) The {len(closed)} held-out road-closed "
        f"reports from fire crews: the frozen spread margin had the road closed by the report time (within 15 min) "
        f"for {hits} of {len(closed)} ({hits / len(closed):.0%}, 95% interval {hc[0]:.0%}–{hc[1]:.0%}); road lines "
        f"are not drawn (graph not committed). (b) How early, for the {len(caught)} caught reports; dashed line: "
        f"report time. Cost: {fc} of {npass} roads that crews reported passable were also closed (95% interval "
        f"{fcc[0]:.0%}–{fcc[1]:.0%}). One fire; firefighter reports, not residents. Source: research/kcf-camp."),
        x_in=0.45, width_in=12.45, top_in=5.85)
    L.save()
    save(fig, "F10_camp_fire", caption=cap)


if __name__ == "__main__":
    main()
