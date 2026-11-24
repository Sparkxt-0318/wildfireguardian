"""F10 Camp Fire: blocked roads the model flagged before the crew report, and the false-alarm side.

Slide 14, full slide. (a) map of the 195 held-out crew reports of a blocked road (Paradise, California, 8 Nov 2018):
blue dot if the frozen spread margin R(h) had flagged the road blocked by the report time (15 min tolerance), brick-red
square if not; the town label is the committed geocoder's Paradise reference point. (b) hours earlier for the reports
flagged in time, median labelled. (c) share flagged blocked, by what crews saw (blocked / passable), with 95% intervals.
Source: research/kcf-camp/out/test1_road_state.csv and out/tests12.json (strict scoring, MR = frozen R(h)).

No road lines and no fire area: the Paradise road graph is not committed (only OSM tile checksums are), and no fire-area
raster is committed (DECISIONS.md D12, D37). The data value ROAD_CLOSED is the source's class name.
"""
import io
import math
import re

import numpy as np
import pandas as pd

import style as S
from figkit import add_caption, grid, save
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
    L.add("Held-out crew reports of a blocked road (class ROAD_CLOSED) placed on the map", len(closed), file=f"{C}/out/test1_road_state.csv",
          field="rows with class == ROAD_CLOSED and match != not_placed; lat, lon", expected="195")
    L.add("Reports where the model had the road blocked by the report time (15 min tolerance)", hits, shown=f"{hits} of {len(closed)}",
          file=f"{C}/out/tests12.json", field="test1.strict.MR.hits / closed_scored", n=f"{len(closed)} reports",
          expected="170 of 195", note="cross-checked against state_MR_strict == HIT in test1_road_state.csv")
    caught = closed[closed["state_MR_strict"] == "HIT"]
    early = -caught["err_MR_strict"].astype(float)
    med = float(np.median(early))
    L.add("Median minutes early, reports flagged in time", med, unit="min", shown=f"{med:.0f} min",
          file=f"{C}/out/test1_road_state.csv", field="median of -err_MR_strict over rows with state_MR_strict == HIT",
          n=f"{len(caught)} reports", expected="119 min",
          note="DIFFERENT FROM EXPECTED. 119 min (numbers.json tests12.test1.strict.MR.time_error_min_closed_rows."
               f"median = {t['time_error_min_closed_rows']['median']}) is the median over all "
               f"{t['time_error_min_closed_rows']['n']} blocked-road reports, flagged in time or not. The figure plots "
               "the reports flagged in time only, so it marks their median.")
    L.add("Roads crews found passable that the model had blocked", fc, shown=f"{fc} of {len(passable)}", file=f"{C}/out/tests12.json",
          field="test1.strict.MR.false_closures / passable_scored", n=f"{len(passable)} reports", expected="22 of 23")
    global T
    T = t
    return closed, caught, early, med, hits, fc, len(passable)


def project(lat, lon, lat0, lon0):
    kx = 111.320 * math.cos(math.radians(lat0))
    return (lon - lon0) * kx, (lat - lat0) * 110.574


def paradise_point(L):
    """The town reference point of the committed Paradise geocoder (research/kcf-validate/paradise/geocode.py)."""
    src = "research/kcf-validate/paradise/geocode.py"
    m = re.search(r"PARADISE = Point\(\*TO_UTM\.transform\((-?[\d.]+), (-?[\d.]+)\)\)", L.text(src))
    lon, lat = float(m.group(1)), float(m.group(2))
    L.add("Paradise town label position (lon, lat)", [lon, lat], file=src, field="PARADISE = Point(...)",
          shown="'Paradise'", note="the geocoder's town reference point; no town outline or road graph is committed")
    return lat, lon


def main():
    L = Ledger("F10", "Camp Fire: blocked roads flagged before the crew report, and the cost")
    closed, caught, early, med, hits, fc, npass = read(L)
    plat, plon = paradise_point(L)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    lat0, lon0 = closed["lat"].mean(), closed["lon"].mean()
    x, y = project(closed["lat"].to_numpy(), closed["lon"].to_numpy(), lat0, lon0)
    hit = (closed["state_MR_strict"] == "HIT").to_numpy()
    head_y = 0.42
    # ---------------- (a) map
    mx0, mx1 = x.min() - 0.8, x.max() + 0.8
    my0, my1 = y.min() - 0.8, y.max() + 1.0
    top_m = 1.72
    mh = 3.33
    mw = mh * (mx1 - mx0) / (my1 - my0)
    axm = fig.add_axes([0.45 / W, 1 - (top_m + mh) / H, mw / W, mh / H])
    axm.set_xlim(mx0, mx1)
    axm.set_ylim(my0, my1)
    axm.set_aspect("equal", adjustable="box")
    axm.set_xticks([])
    axm.set_yticks([])
    L.note("No road lines and no fire area drawn: the Paradise road graph and any fire-area raster are not committed "
           "(DECISIONS.md D12, D37).")
    h1 = axm.scatter(x[hit], y[hit], s=40, marker="o", color=S.OURS, linewidths=0, zorder=4)
    h2 = axm.scatter(x[~hit], y[~hit], s=55, marker="s", facecolors=S.WHITE, edgecolors=S.FIRE, linewidths=1.3,
                     zorder=3)
    px, py = project(plat, plon, lat0, lon0)
    axm.scatter([px], [py], s=120, marker="*", color=S.INK, linewidths=0, zorder=5)
    axm.text(px - 0.9, py + 1.0, "Paradise", ha="right", va="center", zorder=6)
    sb = 2.0
    fx, fy = (mx1 - mx0) / 100, (my1 - my0) / 100    # 1 % of the map, for corner furniture
    bx, by = mx1 - sb - 5 * fx, my0 + 5 * fy
    axm.plot([bx, bx + sb], [by, by], color=S.INK, lw=2.5, solid_capstyle="butt")
    axm.text(bx + sb / 2, by + 2.5 * fy, "2 km", ha="center", va="bottom")
    axm.annotate("", xy=(mx1 - 5 * fx, my1 - 4 * fy), xytext=(mx1 - 5 * fx, my1 - 13 * fy),
                 arrowprops=dict(arrowstyle="-|>,head_length=0.5,head_width=0.25", color=S.INK, lw=1.2))
    axm.text(mx1 - 7 * fx, my1 - 8.5 * fy, "N", ha="right", va="center")
    leg = fig.legend([h1, h2], [f"flagged blocked before the crew report ({hits})",
                                f"not flagged in time ({len(closed) - hits})"],
                     loc="upper left", bbox_to_anchor=(0.45 / W, 1 - 0.68 / H), ncol=1, handletextpad=0.6, labelspacing=0.8,
                     borderaxespad=0.0)
    leg.get_frame().set_linewidth(0.6)
    leg.get_frame().set_gid("box:legend")
    for hnd in leg.legend_handles:
        hnd.set_gid("bg:legend handle")
    S.panel_letter(fig, 0.45, head_y, "a")
    fig.text(0.85 / W, 1 - head_y / H, "Where crews reported a road blocked", va="center")
    # ---------------- (b) hours early
    l, t, w, h = 6.6, 1.0, 2.5, 4.05
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    grid(ax, axis="y")
    hrs = early.to_numpy() / 60.0
    rng = np.random.RandomState(5)
    xs = rng.uniform(-0.3, 0.3, len(hrs))
    ax.scatter(xs, hrs, s=22, marker="o", facecolors=S.WHITE, edgecolors=S.OURS, linewidths=0.9)
    medh = med / 60.0
    floor_h = math.floor(medh * 10) / 10            # "at least" must hold, so round down
    L.add("Median hours early, reports flagged in time (rounded down for 'at least')", medh, unit="h",
          shown=f"≥ {floor_h:.1f} h", file=f"{C}/out/test1_road_state.csv",
          field="median of -err_MR_strict / 60 over rows with state_MR_strict == HIT", n=f"{len(caught)} reports")
    ax.plot([-0.45, 0.45], [medh, medh], color=S.INK, lw=2)
    ax.annotate(f"half flagged\n≥ {floor_h:.1f} h earlier", (0.45, medh), xytext=(10, 0), textcoords="offset points",
                va="center", ha="left")
    ax.axhline(0, color=S.INK, lw=0.8, ls=(0, (3, 2)))
    ax.text(2.25 - 0.08, -0.7, "crew report", ha="right", va="top")
    ax.set_xlim(-0.55, 2.25)
    topv = float(np.ceil(hrs.max() / 4) * 4)
    ax.set_ylim(-3.4, topv + 0.6)
    ax.set_yticks(np.arange(0, topv + 0.1, 4))
    ax.set_xticks([])
    ax.set_ylabel("Hours earlier than the crew report")
    S.panel_letter(fig, 5.6, head_y, "b")
    fig.text(6.0 / W, 1 - head_y / H, "How much earlier", va="center")
    # ---------------- (c) cost: share flagged blocked, by what crews saw
    hc = T["hit_ci95"]
    fcc = T["false_closure_ci95"]
    L.add("95% interval, reports flagged blocked in time", hc, file=f"{C}/out/tests12.json",
          field="test1.strict.MR.hit_ci95", shown="error bar")
    L.add("95% interval, passable roads also flagged blocked", fcc, file=f"{C}/out/tests12.json",
          field="test1.strict.MR.false_closure_ci95", shown="error bar")
    l, t, w, h = 10.4, 1.0, 2.45, 4.05
    axc = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    grid(axc, axis="y")
    vals = [hits / len(closed) * 100, fc / npass * 100]
    cis = [hc, fcc]
    cols = [S.OURS, S.COST]
    counts = [f"{hits}\nof {len(closed)}", f"{fc}\nof {npass}"]
    for i_, (v, ci, col, cnt) in enumerate(zip(vals, cis, cols, counts)):
        bars = axc.bar(i_, v, width=0.7, color=col, edgecolor=S.INK, linewidth=0.6)
        bars.patches[0].set_gid("box:bar")          # the count is written inside its own bar
        axc.errorbar(i_, v, yerr=[[v - ci[0] * 100], [ci[1] * 100 - v]], fmt="none", ecolor=S.INK, elinewidth=1.0,
                     capsize=4)
        axc.text(i_, 40, cnt, ha="center", va="center", color=S.WHITE if col == S.OURS else S.INK, linespacing=1.2)
    axc.set_xlim(-0.6, 1.6)
    axc.set_ylim(0, 110)
    axc.set_yticks([0, 25, 50, 75, 100])
    axc.set_xticks([0, 1])
    axc.set_xticklabels(["blocked", "passable"])
    axc.set_xlabel("What crews saw")
    axc.set_ylabel("Flagged blocked by the model (%)")
    S.panel_letter(fig, 9.4, head_y, "c")
    fig.text(9.8 / W, 1 - head_y / H, "Hits and false alarms", va="center")
    cap = add_caption(fig, (
        f"Figure 10. Camp Fire, Paradise, California, 8 Nov 2018; one fire, crew reports, not residents. (a) The "
        f"{len(closed)} held-out places where fire crews reported a road blocked; the frozen spread margin had flagged "
        f"{hits} of them blocked by the report time (within 15 min). No road lines or fire area: neither is committed. "
        f"(b) How much earlier, for those {len(caught)}. (c) Share flagged blocked, by what crews saw "
        f"(whiskers: 95% interval): {fc} of the {npass} roads crews drove through were flagged too."),
        x_in=0.45, width_in=12.45, top_in=6.12)
    L.save()
    save(fig, "F10_camp_fire", caption=cap)


if __name__ == "__main__":
    main()
