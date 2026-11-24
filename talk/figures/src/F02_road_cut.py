"""F02 the road is cut before the village.

Slide 2, right two thirds. Top: one village's time axis on 25 March 2025 (Samui-ri, 18:00 KST issue): the departure
window, "last road out cut", "fire reaches the village", and the gap. Bottom: histogram of the gap over all
place-hours where a road ends the window (primary configuration R / MEASURED / 8 h), with the place count.
Source: research/kcf-roadcut/per_unit.csv.gz and numbers.json; names from planner/public/data/regions/*/places.geojson.
"""
import gzip
import io
from datetime import datetime

import numpy as np
import pandas as pd

import style as S
from figkit import add_caption, grid, save
from prov import Ledger, git_show

RC = "research/kcf-roadcut"
PLACE = "osm:node/415158320"
ISSUE = "03-25 18:00"


def read(L):
    raw = gzip.decompress(git_show(f"{RC}/per_unit.csv.gz")).decode()
    df = pd.read_csv(io.StringIO(raw), comment="#", dtype=str)
    sel = df[(df.family == "R") & (df.arm == "MEASURED") & (df.horizon == "8h") & (df.binding == "ROAD_CELL")
             & df.gap_min.notna() & (df.gap_min != "")]
    gaps = sel.gap_min.astype(float).to_numpy()
    f_sel = "family == R, arm == MEASURED, horizon == 8h, binding == ROAD_CELL, gap_min present; column gap_min"
    L.add("Place-hours where a road ends the window (exact gap)", len(gaps), file=f"{RC}/per_unit.csv.gz",
          field=f_sel, n=f"{sel.place_id.nunique()} places", expected="97")
    med = float(np.median(gaps))
    L.add("Median gap", med, unit="min", shown=f"{med:.1f} min", file=f"{RC}/per_unit.csv.gz", field=f"median ({f_sel})",
          n=f"{len(gaps)} place-hours", expected="11.8 min", note="RESULTS.md line 32 states the same")
    L.add("Largest gap", gaps.max(), unit="min", shown=f"{gaps.max():.1f} min", file=f"{RC}/per_unit.csv.gz",
          field=f"max ({f_sel})", n=f"{len(gaps)} place-hours", expected="159.6 min")
    cfg = L.json(f"{RC}/numbers.json")["configs"]["R/MEASURED/8h"]
    ca = cfg["count_A_road_cut_before_village"]
    L.add("Places where the road out is cut before the village is reached", ca["places"],
          shown=f"{ca['places']} of {cfg['places']} places", file=f"{RC}/numbers.json",
          field="configs['R/MEASURED/8h'].count_A_road_cut_before_village.places / .places",
          n=f"{ca['place_hours']} place-hours (incl. {ca['of_which_NO_WINDOW']} with no window)", expected="68 of 174",
          note="This count (count A) is wider than the histogram's n = 97: it also includes place-hours with no "
               "departure window at all, and gaps known only as lower bounds.")
    row = df[(df.family == "R") & (df.arm == "MEASURED") & (df.horizon == "8h") & (df.place_id == PLACE)
             & (df.issue_kst == ISSUE)].iloc[0]
    for k in ("T_road_kst", "T_village_kst", "gap_min", "windows_kst"):
        L.add(f"Samui-ri, issue {ISSUE}: {k}", row[k], file=f"{RC}/per_unit.csv.gz",
              field=f"row place_id == {PLACE}, issue_kst == {ISSUE}, MEASURED 8h, family R; column {k}")
    pl = L.json("planner/public/data/regions/yeongdeok_2025/places.geojson")
    name_en = [f["properties"]["name_en"] for f in pl["features"] if f["properties"]["id"] == PLACE][0]
    return gaps, med, ca, cfg, row, name_en


def t(s):
    return datetime.strptime("2025-" + s, "%Y-%m-%d %H:%M:%S")


def main():
    L = Ledger("F02", "The road is cut before the village")
    gaps, med, ca, cfg, row, name_en = read(L)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    # ---------------- (a) one village
    l, w = 5.6, 7.3
    axt = fig.add_axes([l / W, 1 - 2.25 / H, w / W, 1.3 / H])
    t0 = t(ISSUE + ":00")
    hrs = lambda s: (t(s) - t0).total_seconds() / 3600  # noqa: E731
    w0, w1 = [hrs(x) for x in row.windows_kst.split("..")]
    tr, tv = hrs(row.T_road_kst), hrs(row.T_village_kst)
    axt.set_xlim(0, 6.0)
    axt.set_ylim(0, 1.25)
    grid(axt, axis="x")
    yb = 0.70
    axt.barh(yb, w1 - w0, left=w0, height=0.22, facecolor=S.SAFE, edgecolor=S.INK, linewidth=0.6)
    axt.barh(yb, tv - tr, left=tr, height=0.22, facecolor=S.WHITE, edgecolor=S.INK, hatch="////", linewidth=0.6)
    axt.plot([tr, tr], [0.48, 0.92], color=S.FIRE, lw=2)
    axt.plot([tv, tv], [0.48, 0.92], color=S.FIRE, lw=2, ls=(0, (2, 1.2)))
    axt.set_yticks([])
    axt.set_xticks(range(0, 7))
    axt.set_xticklabels([f"{18 + h:02d}:00" if 18 + h < 24 else "24:00" for h in range(0, 7)])
    axt.set_xlabel("25 March 2025, KST")
    axt.text(w0 + 0.05, 1.07, "departure window", ha="left", va="center")
    axt.text(tr - 0.06, 0.28, f"last road out cut {row.T_road_kst[6:11]}", ha="right", va="center")
    axt.text(tv - 0.06, 0.28, f"fire reaches the village {row.T_village_kst[6:11]}", ha="right", va="center")
    axt.text((tr + tv) / 2, 1.07, f"gap {float(row.gap_min):.1f} min", ha="center", va="center")
    S.panel_letter(fig, 4.55, 0.65, "a")
    fig.text(l / W, 1 - 0.65 / H, f"삼의리 {name_en} (영양군 Yeongyang), forecast issued 18:00 KST", va="center")
    # ---------------- (b) histogram
    lb, tb, wb, hb = 5.6, 3.3, 7.3, 1.55
    axh = fig.add_axes([lb / W, 1 - (tb + hb) / H, wb / W, hb / H])
    grid(axh, axis="y")
    edges = np.arange(0, 170, 10)
    counts, _ = np.histogram(gaps, bins=edges)
    axh.bar(edges[:-1] + 5, counts, width=10.0, facecolor=S.LIGHT, edgecolor=S.INK, linewidth=0.6)
    axh.axvline(med, color=S.INK, lw=1.2, ls=(0, (4, 2)))
    axh.annotate(f"median {med:.1f} min", (med, counts.max() * 1.12), xytext=(8, 0), textcoords="offset points",
                 va="center")
    axh.set_xlim(0, 160)
    axh.set_xticks([0, 40, 80, 120, 160])
    axh.set_xlabel("Minutes from road cut to fire at the village")
    axh.set_ylabel("Place-hours")
    ymax = int(np.ceil(counts.max() * 1.3 / 10) * 10)
    axh.set_ylim(0, ymax)
    axh.set_yticks([0, ymax // 2, ymax])
    axh.set_yticklabels(["", str(ymax // 2), str(ymax)])
    S.panel_letter(fig, 4.55, 3.05, "b")
    cap = add_caption(fig, (
        f"Figure 2. The last road out is cut before the fire reaches the village. (a) One village on 25 March 2025: "
        f"its departure window (teal) ends when a road cell closes, {float(row.gap_min):.1f} min before the fire "
        f"reaches the village (hatched). (b) That gap over all {len(gaps)} place-hours where a road cell ends the "
        f"window (median {med:.1f} min, maximum {gaps.max():.1f} min). Counting also place-hours with no window at "
        f"all, the road was cut first at {ca['places']} of {cfg['places']} places ({ca['place_hours']} place-hours). "
        "Model output on reconstructed fire inputs (MEASURED, 8 h). Source: research/kcf-roadcut."),
        x_in=0.45, width_in=12.45, top_in=5.82)
    L.save()
    spec = {"type": "column", "categories": [f"{a}" for a in edges[:-1]],
            "series": [{"name": "Place-hours", "values": [int(c) for c in counts], "color": S.MID}],
            "x_title": "Minutes from road cut to fire at the village (bin start)", "y_title": "Place-hours",
            "y_max": ymax, "y_major": ymax // 2, "gap_width": 10}
    save(fig, "F02_road_cut", charts=[(axh, spec)], caption=cap)


if __name__ == "__main__":
    main()
