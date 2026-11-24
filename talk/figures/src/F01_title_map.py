"""F01 title map: the Gyeongbuk replay area at one issue hour, 25 March 2025.

Slide 1, right half. Roads in grey, the forecast fire (next 8 h) in brick red, villages coloured by the time left
before their last road out closes (cividis), hatched grey for "no safe route". No numbers.
Sources: research/kcf-replay/per_place.csv (MEASURED, 8 h); product/wfg-roadlayer/examples/
fire_arrival_20250325T0300Z_MEASURED_8h.tif (forecast arrival, minutes after issue, EPSG:5179);
planner/public/kcf-scene/data/basemap.js (OSM roads and water, built by research/kcf-replay/scene/build_basemap.py).
"""
import io
import json
import math
from datetime import datetime

import matplotlib.colors as mc
import numpy as np
import pandas as pd
import tifffile
from matplotlib.collections import LineCollection, PolyCollection
from pyproj import Transformer

import style as S
from figkit import add_caption, save
from prov import Ledger, git_show

ISSUE = "03-25 12:00"
TIF = "product/wfg-roadlayer/examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif"
BASEMAP = "planner/public/kcf-scene/data/basemap.js"


def load_js(b):
    s = b.decode()
    i = s.index("=", s.index("KCF") + 20)
    return json.loads(s[i + 1:].strip().rstrip(";"))


def read(L):
    d = pd.read_csv(io.BytesIO(git_show("research/kcf-replay/per_place.csv")))
    states = {}
    for h in ("03-25 12:00", "03-25 18:00"):
        s = d[(d.standin == "MEASURED") & (d.horizon == "8h") & (d.issue_kst == h)]
        states[h] = s.departure_state.nunique()
    p = d[(d.standin == "MEASURED") & (d.horizon == "8h") & (d.issue_kst == ISSUE)].copy()
    L.add("Places on the map", len(p), file="research/kcf-replay/per_place.csv",
          field=f"rows standin == MEASURED, horizon == 8h, issue_kst == {ISSUE}; lon, lat, departure_state, "
                "latest_safe_departure_kst", expected="174",
          note=f"Issue hour chosen for variety: 12:00 KST shows {states['03-25 12:00']} departure states, 18:00 KST "
               f"{states['03-25 18:00']}; these are the two hours with a committed forecast raster.")
    tif = tifffile.TiffFile(io.BytesIO(git_show(TIF))).pages[0]
    arr = tif.asarray()
    tp = tif.tags["ModelTiepointTag"].value
    ps = tif.tags["ModelPixelScaleTag"].value
    L.add("Forecast fire cells (arrival within 8 h, 375 m)", int(np.isfinite(arr).sum() - (arr == np.inf).sum()),
          file=TIF, field="cells with finite arrival minutes (0 = burning at the issue hour)", shown="(not printed)")
    bm = load_js(git_show(BASEMAP))
    L.note(f"Roads and water: {BASEMAP} ({bm['attribution']}).")
    return p, arr, tp, ps, bm


REGION_BBOX = None


def main():
    global REGION_BBOX
    L = Ledger("F01", "Title map: Gyeongbuk replay area, 25 March 2025 12:00 KST")
    p, arr, tp, ps, bm = read(L)
    sc_js = load_js(git_show("planner/public/kcf-scene/data/scene.js"))
    REGION_BBOX = sc_js["regions"]["uiseong_andong_2025"]["bbox"]
    L.note("Map extent: the Uiseong–Andong region box from scene.js regions.uiseong_andong_2025.bbox; Yeongdeok is "
           "left out because at 12:00 KST no Yeongdeok place is affected (DECISIONS.md D15).")
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    bb = REGION_BBOX
    lon0, lon1, lat0, lat1 = bb[0], bb[2], bb[1], bb[3]
    kx = math.cos(math.radians((lat0 + lat1) / 2))
    mh = 4.0
    mw = mh * ((lon1 - lon0) * kx) / (lat1 - lat0)
    top = 0.5
    mx = 13.0 - mw
    ax = fig.add_axes([mx / W, 1 - (top + mh) / H, mw / W, mh / H])
    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_aspect(1 / kx)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.8)
    # water and roads
    polys, wlines = [], []
    for f in bm["water"]["features"]:
        g = f["geometry"]
        if g["type"] == "Polygon":
            polys.append(np.array(g["coordinates"][0])[:, :2])
        elif g["type"] == "MultiPolygon":
            polys += [np.array(poly[0])[:, :2] for poly in g["coordinates"]]
        elif g["type"] == "LineString":
            wlines.append(np.array(g["coordinates"])[:, :2])
        elif g["type"] == "MultiLineString":
            wlines += [np.array(c)[:, :2] for c in g["coordinates"]]
    wl = LineCollection(wlines, colors=S.LIGHT, linewidths=1.2)
    wl.set_gid("bg:water lines")
    ax.add_collection(wl)
    pc = PolyCollection(polys, facecolors=S.LIGHT, edgecolors="none", alpha=0.6)
    pc.set_gid("bg:water")
    ax.add_collection(pc)
    segs = []
    for f in bm["roads"]["features"]:
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        segs += [np.array(c) for c in parts]
    lc = LineCollection(segs, colors=S.MID, linewidths=0.6, zorder=1)
    lc.set_gid("bg:roads")
    ax.add_collection(lc)
    # forecast fire: cells with arrival within 8 h, drawn as 375 m squares in lon/lat
    tr = Transformer.from_crs(5179, 4326, always_xy=True)
    x0, y0 = tp[3], tp[4]
    rr, cc = np.where(np.isfinite(arr))
    cells = []
    for r, c in zip(rr, cc):
        xs = x0 + np.array([c, c + 1, c + 1, c]) * ps[0]
        ys = y0 - np.array([r, r, r + 1, r + 1]) * ps[1]
        lo, la = tr.transform(xs, ys)
        cells.append(np.column_stack([lo, la]))
    pink = mc.to_hex(0.45 * np.array(mc.to_rgb(S.FIRE)) + 0.55 * np.ones(3))
    fc = PolyCollection(cells, facecolors=pink, edgecolors=pink, linewidths=0.8, zorder=0.5)
    fc.set_gid("bg:forecast fire")
    ax.add_collection(fc)
    # villages
    t0 = datetime.strptime("2025-" + ISSUE, "%Y-%m-%d %H:%M")
    left = []
    for _, r in p.iterrows():
        if r.departure_state == "LATEST_SAFE_DEPARTURE":
            left.append((datetime.strptime("2025-" + r.latest_safe_departure_kst, "%Y-%m-%d %H:%M")
                         - t0).total_seconds() / 3600)
        elif r.departure_state == "NOT_CUT_WITHIN_H":
            left.append(8.0)
        else:
            left.append(np.nan)
    p["left_h"] = left
    cmap = mc.ListedColormap(S.plt.get_cmap(S.CONTINUOUS_CMAP)(np.linspace(0, 1, 256))[::-1])
    norm = mc.Normalize(0, 8)
    ok = p[p.left_h.notna()]
    sc = ax.scatter(ok.lon, ok.lat, c=ok.left_h, cmap=cmap, norm=norm, s=70, edgecolors=S.INK, linewidths=0.7,
                    zorder=5)
    sc.set_gid("bg:villages")
    ns = p[p.departure_state == "NO_SAFE_DEPARTURE"]
    hs = ax.scatter(ns.lon, ns.lat, s=120, marker="s", facecolors=S.LIGHT, edgecolors=S.INK, hatch="////",
                    linewidths=0.8, zorder=6)
    hs.set_gid("bg:no safe route")
    ins = p[p.departure_state == "INSIDE_KNOWN_FIRE_AREA"]
    ic = ax.scatter(ins.lon, ins.lat, s=18, color=S.INK, zorder=5)
    ic.set_gid("bg:inside fire")
    # scale bar (10 km) and north arrow
    km_per_deg = 111.320 * kx
    sbx, sby = lon0 - 0.012 - 5 / km_per_deg, lat1 - 0.075
    ax.plot([sbx, sbx + 5 / km_per_deg], [sby, sby], color=S.INK, lw=3, solid_capstyle="butt", clip_on=False)
    ax.text(sbx + 2.5 / km_per_deg, sby - 0.006, "5 km", ha="center", va="top", fontsize=S.PT_MIN)
    ax.annotate("", xy=(lon0 - 0.025, lat1), xytext=(lon0 - 0.025, lat1 - 0.02),
                arrowprops=dict(arrowstyle="-|>,head_length=0.7,head_width=0.35", color=S.INK, lw=2),
                annotation_clip=False)
    ax.text(lon0 - 0.025, lat1 - 0.03, "N", ha="center", va="top", fontsize=S.PT_BODY)
    # key below the map, one row
    ky = top + mh + 0.42
    kx0 = 6.75
    fig.text(kx0 / W, 1 - (ky - 0.05) / H, "time left before the\nlast road out closes", fontsize=S.PT_MIN,
             va="center", linespacing=1.1)
    cax = fig.add_axes([kx0 / W, 1 - (ky + 0.62) / H, 2.0 / W, 0.18 / H])
    cb = fig.colorbar(sc, cax=cax, orientation="horizontal")
    cb.set_ticks([])
    cb.outline.set_linewidth(0.6)
    fig.text(kx0 / W, 1 - (ky + 0.90) / H, "less", fontsize=S.PT_MIN, va="center", color=S.MID)
    fig.text((kx0 + 2.0) / W, 1 - (ky + 0.90) / H, "more", fontsize=S.PT_MIN, va="center", ha="right", color=S.MID)
    kx2 = 9.45
    items = [("fire", "forecast fire"), ("ns", "no safe route"), ("in", "already inside the fire")]
    for i, (kind, lab) in enumerate(items):
        yy = ky - 0.15 + i * 0.45
        kax = fig.add_axes([kx2 / W, 1 - (yy + 0.15) / H, 0.3 / W, 0.3 / H])
        kax.set_xlim(0, 1)
        kax.set_ylim(0, 1)
        kax.axis("off")
        if kind == "fire":
            r = S.plt.Rectangle((0.0, 0.1), 1.0, 0.8, facecolor=pink, edgecolor="none")
            r.set_gid("bg:key")
            kax.add_patch(r)
        elif kind == "ns":
            k = kax.scatter([0.5], [0.5], s=120, marker="s", facecolors=S.LIGHT, edgecolors=S.INK, hatch="////",
                            linewidths=0.8)
            k.set_gid("bg:key")
        else:
            k = kax.scatter([0.5], [0.5], s=18, color=S.INK)
            k.set_gid("bg:key")
        fig.text((kx2 + 0.45) / W, 1 - yy / H, lab, fontsize=S.PT_MIN, va="center")
    cap = add_caption(fig, (
        "Figure 1. The Uiseong–Andong replay area at the 12:00 KST forecast of 25 March 2025: roads (grey), the "
        "forecast fire for the next 8 hours (red tint), and villages coloured by the time left before their last road "
        "out closes; hatched squares: no safe route; small dots: already inside the fire. Model output on "
        "reconstructed inputs, not what happened. Source: research/kcf-replay, product/wfg-roadlayer."),
        x_in=0.45, width_in=12.45, top_in=6.12)
    L.save()
    save(fig, "F01_title_map", caption=cap)


if __name__ == "__main__":
    main()
