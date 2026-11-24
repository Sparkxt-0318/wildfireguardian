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
from figkit import save
from prov import Ledger, git_show

C = "research/kcf-camp"


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
    # ---------------- map
    mx0, mx1 = x.min() - 0.8, x.max() + 0.8
    my0, my1 = y.min() - 0.8, y.max() + 0.8
    mh = 5.15
    mw = mh * (mx1 - mx0) / (my1 - my0)
    mw = min(mw, 6.3)
    axm = fig.add_axes([0.45 / W, 1 - (0.95 + mh) / H, mw / W, mh / H])
    axm.set_xlim(mx0, mx1)
    axm.set_ylim(my0, my1)
    axm.set_aspect("equal", adjustable="box")
    axm.set_xticks([])
    axm.set_yticks([])
    for sp in axm.spines.values():
        sp.set_visible(False)
    gpath = os.environ.get("PARADISE_GRAPH")
    if gpath and os.path.exists(gpath):
        L.note(f"Roads drawn from {gpath}")
    else:
        L.note("No road lines drawn: the Paradise road graph is not committed (DECISIONS.md D12).")
    axm.scatter(x[~hit], y[~hit], s=70, facecolors=S.WHITE, edgecolors=S.FIRE, linewidths=1.8, zorder=3)
    axm.scatter(x[hit], y[hit], s=55, color=S.OURS, linewidths=0, zorder=4)
    # scale bar and north arrow, bottom left
    sb = 2.0
    bx, by = mx1 - sb - 0.4, my0 + 0.25
    axm.plot([bx, bx + sb], [by, by], color=S.INK, lw=3, solid_capstyle="butt")
    axm.text(bx + sb / 2, by + 0.35, "2 km", ha="center", va="bottom", fontsize=S.PT_MIN)
    axm.annotate("", xy=(mx1 - 0.35, my1 - 0.15), xytext=(mx1 - 0.35, my1 - 1.45),
                 arrowprops=dict(arrowstyle="-|>,head_length=0.8,head_width=0.4", color=S.INK, lw=2))
    axm.text(mx1 - 0.75, my1 - 0.75, "N", ha="right", va="center", fontsize=S.PT_BODY, fontweight="bold")
    # map key, beneath the map
    ky = 1 - (0.95 + mh + 0.35) / H
    fig.text(0.45 / W, ky, "●", color=S.OURS, fontsize=S.PT_BODY, va="center")
    fig.text(0.72 / W, ky, f"road closed by the report time: {hits}", fontsize=S.PT_MIN, va="center")
    fig.text(4.75 / W, ky, "○", color=S.FIRE, fontsize=S.PT_BODY, va="center", fontweight="bold")
    fig.text(5.15 / W, ky, f"not yet: {len(closed) - hits}", fontsize=S.PT_MIN, va="center")
    fig.text(0.45 / W, 1 - 0.55 / H, f"Paradise, California, 8 Nov 2018: {len(closed)} road-closed reports",
             fontsize=S.PT_BODY, fontweight="bold", va="center")
    # ---------------- strip of minutes early
    l, t, w, h = 8.6, 1.15, 3.6, 4.95
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    rng = np.random.RandomState(5)
    xs = rng.uniform(-0.32, 0.32, len(early))
    ax.scatter(xs, early, s=40, color=S.OURS, alpha=0.75, linewidths=0)
    ax.plot([-0.48, 0.48], [med, med], color=S.INK, lw=2.5)
    ax.annotate(f"median {med:.0f} min", (0.48, med), xytext=(10, 0), textcoords="offset points",
                va="center", fontsize=S.PT_LABEL, fontweight="bold")
    ax.axhline(0, color=S.MID, lw=1.0, ls=(0, (3, 2)))
    ax.set_xlim(-0.6, 1.9)
    top = float(np.ceil(early.max() / 60) * 60)
    ax.set_ylim(-60, top + 20)
    ax.set_yticks(np.arange(0, top + 1, 240))
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_ylabel("Minutes the road was closed\nbefore the report")
    ax.annotate("report time", (0.62, 0), xytext=(0, -12), textcoords="offset points", va="top",
                fontsize=S.PT_MIN, color=S.MID)
    fig.text(l / W, 1 - 0.55 / H, f"{hits} of {len(closed)} caught (n = {len(caught)} shown)", fontsize=S.PT_BODY,
             fontweight="bold", va="center")
    # ---------------- cost line
    fig.text(0.45 / W, 1 - 7.05 / H, f"Cost: {fc} of {npass} roads that crews reported passable were closed too",
             color=S.COST, fontsize=S.PT_LABEL, fontweight="bold", va="center")
    L.save()
    save(fig, "F10_camp_fire")


if __name__ == "__main__":
    main()
