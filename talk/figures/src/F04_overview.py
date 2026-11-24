"""F04 method overview: one real case, Uiseong-Andong, 25 March 2025, 18:00 KST (the F02 issue hour), left to right.

(a) inputs: satellite fire detections before the issue hour, ECMWF IFS 10 m wind at the issue hour, OSM roads with
    the planner's villages and shelters;
(b) spread forecast: the finals checkpoint M548 ("mixed") run with PyTorch on the Uiseong event (build/F04_forecast.npz,
    made by F04_forecast.py): its four learned kernels at one cell and the next-hour burn probability, with the two
    model equations;
(c) exposure: active-burning fraction and radiant heat from the forecast workspace's saved M548 run on Fish Creek
    (no Korean fuel or canopy layers exist, NEEDS.md);
(d) safety distance: the known fire area widened by the calibrated 8 h reach (MEASURED arm), and the calibration gate
    with its "withhold" exit (kcf-abstain withheld 18:00 KST);
(e) routing: three roads of Wondang-ri's route with their blocked times, the backward pass from the three shelters
    (latest departure of every road node) and the route (build/F04_routing.json, made by F04_routing.py);
(f) output: the village card (route, last safe departure) and the certificate sent to a separate checker.

Canvas 17 x 7.6 in (wider than a slide, so six stages fit at 16 pt); delivered PNG 300 dpi, cropped, transparent.
"""
import io
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.colors as mc
import numpy as np
import tifffile
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle
from pyproj import Transformer

import style as S
from figkit import add_caption, grid, save
from prov import Ledger, git_show, sha256_file

WS = Path("/Users/jp/Desktop/wildfire")
FISH = "demonstration/heat_spatial_maps/20261013_fishcreek/spatial_matrices.npz"
WIND = "data/environment/regions/KFS_01/weather/ecmwf_ifs_native_nodes.npz"
TIF = "product/wfg-roadlayer/examples/fire_arrival_20250325T0900Z_MEASURED_8h.tif"
T_ISO = "2025-03-25T09:00:00+00:00"
W_FIG, H_FIG = 17.0, 8.8
STAGES = {  # x0, width (inches)
    "a": (0.20, 1.95), "b": (2.60, 2.45), "c": (5.50, 1.90), "d": (7.85, 2.40), "e": (10.70, 3.75), "f": (14.90, 1.95),
}
TOP = 0.70             # first picture row
BOTTOM = 6.75          # graphic ends here; caption below
RNG = np.random.default_rng(0)
PICTURES = []          # display boxes that arrows may not cross
ARROWS = []


def fx(x):
    return x / W_FIG


def fy(y):
    return 1 - y / H_FIG


def axes_in(fig, x, y, w, h, picture=True):
    ax = fig.add_axes([fx(x), fy(y + h), w / W_FIG, h / H_FIG])
    if picture:
        PICTURES.append(ax)
    return ax


def label(fig, x, y, s, **kw):
    kw.setdefault("va", "center")
    return fig.text(fx(x), fy(y), s, **kw)


def arrow(fig, p0, p1, name, lw=1.0, head=8):
    a = FancyArrowPatch((fx(p0[0]), fy(p0[1])), (fx(p1[0]), fy(p1[1])), transform=fig.transFigure,
                        arrowstyle=f"-|>,head_length={head / 18:.2f},head_width={head / 30:.2f}", mutation_scale=18,
                        color=S.INK, lw=lw, shrinkA=0, shrinkB=0)
    a.set_gid(f"arrow:{name}")
    fig.add_artist(a)
    ARROWS.append((a, p0, p1))
    return a


def map_axes(ax, bbox):
    lon0, lat0, lon1, lat1 = bbox
    k = math.cos(math.radians((lat0 + lat1) / 2))
    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_aspect(1 / k, adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.75)
    return k


def map_height(bbox, w):
    lon0, lat0, lon1, lat1 = bbox
    k = math.cos(math.radians((lat0 + lat1) / 2))
    return w * (lat1 - lat0) / ((lon1 - lon0) * k)


def load_js(b):
    s = b.decode()
    i = s.index("=", s.index("KCF") + 20)
    return json.loads(s[i + 1:].strip().rstrip(";"))


def raster_cells(arr, tp, ps, sel):
    tr = Transformer.from_crs(5179, 4326, always_xy=True)
    rr, cc = np.where(sel)
    cells = []
    for r, c in zip(rr, cc):
        xs = tp[3] + np.array([c, c + 1, c + 1, c]) * ps[0]
        ys = tp[4] - np.array([r, r, r + 1, r + 1]) * ps[1]
        lo, la = tr.transform(xs, ys)
        cells.append(np.column_stack([lo, la]))
    return cells


def kst(sec):
    return (datetime(2025, 3, 25, 18, 0) + timedelta(seconds=float(sec))).strftime("%H:%M")


def haversine_km(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


# ====================================================================== reading
def read(L):
    D = {}
    sc = load_js(git_show("planner/public/kcf-scene/data/scene.js"))
    k = sc["issue_utc"].index("2025-03-25T09:00:00Z")
    D["k"] = k
    D["bbox"] = sc["regions"]["uiseong_andong_2025"]["bbox"]
    L.add("Issue hour", sc["issue_kst"][k], file="planner/public/kcf-scene/data/scene.js",
          field=f"issue_kst[{k}] (issue_utc 2025-03-25T09:00:00Z)", shown="18:00 KST",
          note="The F02 issue hour (F02_road_cut.py ISSUE = '03-25 18:00').")
    D["places"] = [p for p in sc["places"] if p["region"] == "uiseong_andong_2025"]
    D["shelters"] = [s for s in sc["shelters"].values() if s["region"] == "uiseong_andong_2025"]
    states = [sc["hourly"]["MEASURED"][p["id"]][k]["state"] for p in D["places"]]
    L.add("Places in the region / inside the known fire area at 18:00 KST",
          [len(D["places"]), sum(s == "INSIDE_KNOWN_FIRE_AREA" for s in states)],
          file="planner/public/kcf-scene/data/scene.js",
          field=f"places (region uiseong_andong_2025); hourly.MEASURED[place][{k}].state", shown="(caption)")
    L.add("Shelters in the region", len(D["shelters"]), file="planner/public/kcf-scene/data/scene.js",
          field="shelters (region uiseong_andong_2025)", shown="(not printed)")
    # detections
    discs = L.json("research/kcf-replay/fire_discs.json")["discs"]
    T = datetime.fromisoformat(T_ISO)
    sel = [d for d in discs if datetime.fromisoformat(d["t_utc"]) < T]
    D["discs"] = sel
    n_ahi = sum(d["src"] == "AHI" for d in sel)
    L.add("Satellite detections before 18:00 KST (FIRMS, AHI)", [len(sel) - n_ahi, n_ahi],
          file="research/kcf-replay/fire_discs.json", field="discs with t_utc < 2025-03-25T09:00Z, by src",
          n=f"{len(sel)} detections", shown="(caption)",
          expected=f"scene.js discCounts[{k}] = {sc['discCounts'][k]}")
    assert len(sel) == sc["discCounts"][k]["total"]
    # basemap
    bm = load_js(git_show("planner/public/kcf-scene/data/basemap.js"))
    D["roads"] = []
    for f in bm["roads"]["features"]:
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        D["roads"] += [np.array(c) for c in parts]
    L.note(f"Roads: planner/public/kcf-scene/data/basemap.js ({bm['attribution']}).")
    # wind (forecast workspace, read only)
    z = np.load(WS / WIND)
    it = list(z["time_utc"]).index("2025-03-25T09:00:00Z")
    D["wind"] = (z["longitude"], z["latitude"], z["wind_eastward_10m"][it], z["wind_northward_10m"][it])
    spd = np.hypot(D["wind"][2], D["wind"][3])
    inb = ((z["longitude"] >= D["bbox"][0] - .06) & (z["longitude"] <= D["bbox"][2] + .06)
           & (z["latitude"] >= D["bbox"][1] - .06) & (z["latitude"] <= D["bbox"][3] + .06))
    L.add("ECMWF IFS 10 m wind at 09:00 UTC, nodes in the map (min, max speed)",
          [float(spd[inb].min()), float(spd[inb].max())], unit="m/s", repo=WS, file=WIND,
          field=f"wind_eastward_10m, wind_northward_10m at time_utc index {it} (2025-03-25T09:00:00Z)",
          n=f"{int(inb.sum())} nodes", shown="arrows")
    # reach raster
    t = tifffile.TiffFile(io.BytesIO(git_show(TIF))).pages[0]
    D["arr"], D["tp"], D["ps"] = t.asarray(), t.tags["ModelTiepointTag"].value, t.tags["ModelPixelScaleTag"].value
    tp, ps_, (hh, ww) = D["tp"], D["ps"], D["arr"].shape
    tx = Transformer.from_crs(5179, 4326, always_xy=True)
    xs = [tp[3], tp[3] + ww * ps_[0]]
    ys_ = [tp[4] - hh * ps_[1], tp[4]]
    lo, la = tx.transform([xs[0], xs[1], xs[0], xs[1]], [ys_[0], ys_[0], ys_[1], ys_[1]])
    D["strip"] = [max(lo[0], lo[2]), max(la[0], la[1]), min(lo[1], lo[3]), min(la[2], la[3])]
    L.note("Maps in (a), (b) and (d) show the extent of the committed reach raster (both planner regions of the "
           "Uiseong fire, 214 x 67 cells of 375 m); the Uiseong–Andong planner box alone lies wholly inside the "
           "known fire area at 18:00 KST.")
    # routing
    rt = json.loads((S.FIGDIR / "build/F04_routing.json").read_text())
    D["rt"] = rt
    rf = "talk/figures/build/F04_routing.json"
    L.add("Calibrated reach class and R(8 h)", [rt["measured_class"], rt["R8_m"] / 1000], unit="km", file=rf,
          field="measured_class, R8_m (research/kcf-replay measured_arms.curve at 09:00 UTC)",
          shown=f"+{rt['R8_m'] / 1000:.0f} km in 8 h",
          expected="MEASURED_RULE.md: running class R(8 h) = 10.0 km")
    pl = L.json("planner/public/data/regions/uiseong_andong_2025/places.geojson")["features"]
    D["name_en"] = [f["properties"]["name_en"] for f in pl if f["properties"]["id"] == rt["place_id"]][0]
    D["shelter_cat"] = rt["shelter_category"]
    L.add("Last safe departure of the village", rt["ld_at_origin_s"], unit="s after 18:00 KST", file=rf,
          field="ld_at_origin_s (max over the 3 shelters of the backward pass); equals route_ld_s from scene.js",
          shown=f"leave by {kst(rt['ld_at_origin_s'])}", n="1 place",
          expected="per_place.csv / scene.js hourly lsd 03-25 18:15",
          note="Computed with research/kcf-replay/replay.py's Region and deadline_field.core.backward (F04_routing.py).")
    L.add("Arrival at the shelter", rt["route_arr_s"], unit="s after 18:00 KST", file=rf, field="route_arr_s",
          shown="(caption)")
    route_km = sum(haversine_km(a, b) for a, b in zip(rt["route_lonlat"][:-1], rt["route_lonlat"][1:]))
    D["route_km"] = route_km
    L.add("Route length", route_km, unit="km", file=rf, field="sum of great-circle lengths of route_lonlat",
          shown=f"{route_km:.1f} km")
    roads = []
    seen = set()
    for w in rt["route_way_timing"]:
        if w["block_s"] in seen:
            continue
        seen.add(w["block_s"])
        roads.append(w)
        if len(roads) == 3:
            break
    D["roads3"] = roads
    for nm, w in zip("ABC", roads):
        L.add(f"Road {nm} (OSM way {w['way']}): blocked / car leaves it", [w["block_s"], round(w["exit_s"], 1)],
              unit="s after 18:00 KST", file=rf, field="route_way_timing[way].block_s, exit_s",
              shown=f"blocked {kst(w['block_s'])}")
    L.add("Backward pass: road nodes with a safe departure", int((np.array(rt["node_ld_s"]) >= 0).sum()), file=rf,
          field="node_ld_s >= 0", n=f"{len(rt['node_ld_s'])} nodes", shown="coloured roads")
    ps = rt["per_shelter"][rt["route_shelter"]]
    L.add("Certificate check of the attaining shelter's field", ps["fixed_point"], file=rf,
          field="per_shelter[route_shelter].fixed_point, states_checked", n=f"{ps['states_checked']} edge states",
          shown="accept", note="deadline_field.core.check_fixed_point; witness route also rechecked by "
                               "research/kcf-replay/analyze.py::recheck (accepted at the last safe departure, "
                               "rejected one second later: witness_recheck).")
    # abstain gate
    ab = L.json("research/kcf-abstain/numbers.json")["march25"]["hours_10_20_kst"]
    h18 = [h for h in ab if h["kst_hour"] == 18.0][0]
    D["abstain"] = h18
    L.add("Calibration gate at 18:00 KST", h18["abstain"], file="research/kcf-abstain/numbers.json",
          field="march25.hours_10_20_kst[kst_hour == 18].abstain (min_predictor, prior3_km)",
          shown="withhold", note=f"trigger {h18['min_predictor']} = {h18['prior3_km']:.1f} km")
    # forecast (M548)
    fp = S.FIGDIR / "build/F04_forecast.npz"
    D["fc"] = np.load(fp) if fp.exists() else None
    if D["fc"] is not None:
        meta = json.loads(str(D["fc"]["meta_json"]))
        D["fc_meta"] = meta
        ff = "talk/figures/build/F04_forecast.npz"
        L.add("M548 checkpoint SHA-256", meta["checkpoint_sha256"][:16], file=ff, field="meta_json.checkpoint_sha256",
              expected="runs/20261013_observed_merged/protocol.json checkpoint_sha256 (checked in F04_forecast.py)",
              shown="(SOURCES only)")
        L.add("Largest next-hour burn probability in the region", meta["max_probability_region"], file=ff,
              field="max(probability) over valid cells of the Uiseong-Andong region", shown="colour bar top")
        L.add("Kernel cell: rate and probability", [meta["cell_rate_per_h"], meta["cell_probability"]], file=ff,
              field="meta_json.cell_rate_per_h, cell_probability (rate rebuilt from the four kernels: "
                    f"{meta['rate_rebuilt_from_kernels']:.6g})", unit="h⁻¹, –", shown="(caption)")
        L.add("KFS_01 held out from M548 training", meta["kfs01_is_checkpoint_test_event"], file=ff,
              field="meta_json.kfs01_is_checkpoint_test_event (protocol.json checkpoint_test_events)",
              shown="(caption)")
    # Fish Creek exposure (forecast workspace, read only)
    fz = np.load(WS / FISH)
    D["fish"] = fz
    L.add("Fish Creek: peak mean active-burning fraction / radiant heat",
          [float(fz["mean_active_burning_probability"].max()), float(fz["mean_heat_flux_w_m2"].max())], repo=WS,
          file=FISH, field="mean_active_burning_probability, mean_heat_flux_w_m2 (full grid max)", unit="–, W/m²",
          shown="colour bars", note="Saved M548 output (summary.json checkpoint_sha256 c651f672…, the same "
                                    "checkpoint), cutoff 2024-08-23 00:00 UTC, interval 00:00–01:00 UTC.")
    return D


# ====================================================================== stages
def strip_map(fig, D, x, y, w, title):
    bb = D["strip"]
    h = map_height(bb, w)
    label(fig, x, y - 0.22, title)
    ax = axes_in(fig, x, y, w, h)
    map_axes(ax, bb)
    return ax, h


def stage_a(fig, D):
    x0, w = STAGES["a"]
    y = TOP + 0.62
    axs = []
    h0 = map_height(D["strip"], w)
    step = (BOTTOM - 0.6 - y - h0) / 2
    for t in ["Fire detections", "Forecast wind", "Roads and places"]:
        ax, h = strip_map(fig, D, x0, y, w, t)
        axs.append(ax)
        y += step
    lon, lat = Transformer.from_crs(5179, 4326, always_xy=True).transform(
        np.array([d["x"] for d in D["discs"]]), np.array([d["y"] for d in D["discs"]]))
    sc = axs[0].scatter(lon, lat, s=3, color=S.FIRE, linewidths=0)
    sc.set_gid("bg:detections")
    lo, la, u, v = D["wind"]
    q = axs[1].quiver(lo, la, u, v, color=S.INK, scale=50, scale_units="inches", width=0.006, headwidth=4,
                      headlength=4.5, headaxislength=4)
    q.set_gid("bg:wind")
    lc = LineCollection(D["roads"], colors=S.MID, linewidths=0.3)
    lc.set_gid("bg:roads")
    axs[2].add_collection(lc)
    p = axs[2].scatter([q_["lon"] for q_ in D["places"]], [q_["lat"] for q_ in D["places"]], s=5, color=S.INK,
                       linewidths=0, zorder=3)
    p.set_gid("bg:villages")
    s = axs[2].scatter([q_["lon"] for q_ in D["shelters"]], [q_["lat"] for q_ in D["shelters"]], s=10, marker="s",
                       facecolor=S.SAFE, edgecolor=S.INK, linewidths=0.3, zorder=4)
    s.set_gid("bg:shelters")


def stage_b(fig, D):
    x0, w = STAGES["b"]
    fc = D["fc"]
    y = TOP + 0.62
    label(fig, x0, y - 0.22, "Learned kernels, one cell")
    kw = 0.5
    gap = (w - 4 * kw) / 3
    if fc is not None:
        sizes = [int(s) for s in fc["kernel_sizes"]]
        vmax = max(float(np.nanmax(fc[f"kernel_{s}"])) for s in sizes)
        norm = mc.Normalize(0, vmax)
        for i, s in enumerate(sizes):
            ax = axes_in(fig, x0 + i * (kw + gap), y + 0.42, kw, kw)
            k = fc[f"kernel_{s}"].copy()
            k[s // 2, s // 2] = np.nan
            im = ax.imshow(k, cmap=S.CONTINUOUS_CMAP, norm=norm, interpolation="nearest")
            im.set_gid("bg:kernel")
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_linewidth(0.6)
            label(fig, x0 + i * (kw + gap) + kw / 2, y + 0.2, f"{s}×{s}", ha="center")
        cax = axes_in(fig, x0, y + 1.06, w, 0.1)
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        cb.set_ticks([0, vmax])
        cb.ax.set_xticklabels(["0", f"{vmax * 1e3:.1f}"])
        cb.ax.get_xticklabels()[0].set_ha("left")
        cb.ax.get_xticklabels()[-1].set_ha("right")
        cb.outline.set_linewidth(0.6)
        label(fig, x0 + w / 2, y + 1.38, "10$^{-3}$ h$^{-1}$", ha="center")
    ye = y + 2.0
    fig.text(fx(x0), fy(ye), r"$\mathrm{rate}_i=\sum_{\delta}\,K_i(\delta)\,B_{i+\delta}$", va="center")
    fig.text(fx(x0), fy(ye + 0.55), r"$p_i=1-\exp(-\mathrm{rate}_i)$", va="center")
    fig.text(fx(x0), fy(ye + 0.98), r"$B$: burned neighbour, 0 or 1", va="center")
    ym = ye + 1.75
    ax, mh = strip_map(fig, D, x0, ym, w, "Burn probability, next hour")
    if fc is not None:
        prob = fc["probability"].astype(float)
        valid = fc["valid"].astype(bool)
        burned = fc["burned"]
        tr = fc["affine"]
        H, Wd = prob.shape
        tx = Transformer.from_crs(5179, 4326, always_xy=True)
        cols, rows = np.meshgrid(np.arange(Wd + 1), np.arange(H + 1))
        LO, LA = tx.transform(tr[2] + cols * tr[0], tr[5] + rows * tr[4])
        pmax = float(D["fc_meta"]["max_probability_region"])
        show = np.ma.masked_where(~valid | (burned == 1) | (prob <= 0), prob)
        pm = ax.pcolormesh(LO, LA, show, cmap=S.CONTINUOUS_CMAP, norm=mc.Normalize(0, pmax), shading="flat",
                           rasterized=True)
        pm.set_gid("bg:probability")
        bu = np.ma.masked_where(burned != 1, np.ones_like(prob))
        pb = ax.pcolormesh(LO, LA, bu, cmap=mc.ListedColormap([S.LIGHT]), shading="flat", rasterized=True)
        pb.set_gid("bg:burned")
        r, c = fc["cell"]
        cx, cy = tx.transform(tr[2] + (c + 0.5) * tr[0], tr[5] + (r + 0.5) * tr[4])
        mk = ax.plot([cx], [cy], marker="s", ms=6, mfc="none", mec=S.FIRE, mew=1.4)[0]
        mk.set_gid("bg:kernel cell")
        cax = axes_in(fig, x0, ym + mh + 0.12, w, 0.1)
        cb = fig.colorbar(pm, cax=cax, orientation="horizontal")
        cb.set_ticks([0, pmax])
        cb.ax.set_xticklabels(["0", f"{pmax:.3f}"])
        cb.ax.get_xticklabels()[0].set_ha("left")
        cb.ax.get_xticklabels()[-1].set_ha("right")
        cb.outline.set_linewidth(0.6)
        yk = ym + mh + 0.9
        kax = axes_in(fig, x0, yk - 0.13, 0.3, 0.26, picture=False)
        kax.set_xlim(0, 1)
        kax.set_ylim(0, 1)
        kax.axis("off")
        r_ = Rectangle((0, 0), 1, 1, facecolor=S.LIGHT, edgecolor=S.INK, linewidth=0.6)
        r_.set_gid("bg:key")
        kax.add_patch(r_)
        label(fig, x0 + 0.42, yk, "burned (reconstruction)")


def stage_c(fig, D):
    x0, w = STAGES["c"]
    fz = D["fish"]
    r0, r1 = int(fz["crop_row_start"]), int(fz["crop_row_stop_exclusive"])
    c0, c1 = int(fz["crop_column_start"]), int(fz["crop_column_stop_exclusive"])
    label(fig, x0, TOP + 0.4, "Fish Creek, US, 2024")
    mw = 1.6
    mh = mw * (r1 - r0) / (c1 - c0)
    xm = x0 + (w - mw) / 2
    specs = [("Active-fire fraction", fz["mean_active_burning_probability"][r0:r1, c0:c1], mc.LogNorm(1e-3, 1),
              [1e-3, 1e-2, 1e-1, 1], ["10$^{-3}$", "", "", "1"]),
             ("Radiant heat, W m$^{-2}$", fz["mean_heat_flux_w_m2"][r0:r1, c0:c1], mc.LogNorm(1, 1e4),
              [1, 1e2, 1e4], ["1", "100", "10$^4$"])]
    y = TOP + 1.25
    for title, arr, norm, ticks, tl in specs:
        label(fig, x0, y - 0.22, title)
        ax = axes_in(fig, xm, y, mw, mh)
        im = ax.imshow(np.clip(arr, norm.vmin, None), cmap=S.CONTINUOUS_CMAP, norm=norm, interpolation="nearest")
        im.set_gid("bg:exposure")
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_linewidth(0.75)
        cax = axes_in(fig, xm, y + mh + 0.1, mw, 0.1)
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        cb.ax.minorticks_off()
        cb.set_ticks(ticks)
        cb.ax.set_xticklabels(tl)
        cb.outline.set_linewidth(0.6)
        y += mh + 1.15


def stage_d(fig, D):
    x0, w = STAGES["d"]
    y = TOP + 0.62
    ax, mh = strip_map(fig, D, x0, y, w, "Known fire, widened")
    arr, tp, ps = D["arr"], D["tp"], D["ps"]
    reach = PolyCollection(raster_cells(arr, tp, ps, np.isfinite(arr) & (arr > 0) & (arr <= 480)),
                           facecolors=S.WHITE, edgecolors=S.FIRE, linewidths=0, hatch="//////", zorder=1)
    reach.set_gid("bg:reach")
    ax.add_collection(reach)
    known = PolyCollection(raster_cells(arr, tp, ps, np.isfinite(arr) & (arr == 0)), facecolors=S.FIRE,
                           edgecolors=S.FIRE, linewidths=0.4, zorder=2)
    known.set_gid("bg:known fire")
    ax.add_collection(known)
    yk = y + mh + 0.4
    for i, (kind, txt) in enumerate([("known", "known fire, 18:00"),
                                      ("reach", f"+{D['rt']['R8_m'] / 1000:.0f} km in 8 h")]):
        kax = axes_in(fig, x0, yk + i * 0.42 - 0.13, 0.3, 0.26, picture=False)
        kax.set_xlim(0, 1)
        kax.set_ylim(0, 1)
        kax.axis("off")
        r = Rectangle((0, 0), 1, 1, facecolor=S.FIRE if kind == "known" else S.WHITE, edgecolor=S.FIRE,
                      hatch=None if kind == "known" else "////", linewidth=0.6)
        r.set_gid("bg:key")
        kax.add_patch(r)
        label(fig, x0 + 0.42, yk + i * 0.42, txt)
    gcx, gw, gh = x0 + w / 2, 2.4, 1.9
    gcy = max(yk + 0.42 + 0.45 + gh / 2, D["e_map_mid"])
    pts = [(gcx, gcy - gh / 2), (gcx + gw / 2, gcy), (gcx, gcy + gh / 2), (gcx - gw / 2, gcy)]
    dia = Polygon([(fx(px), fy(py)) for px, py in pts], closed=True, transform=fig.transFigure, facecolor=S.WHITE,
                  edgecolor=S.INK, linewidth=S.LW_THIN, zorder=-1)
    dia.set_gid("box:gate")
    fig.add_artist(dia)
    fig.text(fx(gcx), fy(gcy), "Inside\ncalibration\nrange?", ha="center", va="center", linespacing=1.05)
    D["gate_yes"] = (gcx + gw / 2, gcy)
    label(fig, gcx + gw / 2 + 0.04, gcy - 0.26, "yes")
    wy = gcy + gh / 2 + 0.42
    arrow(fig, (gcx, gcy + gh / 2), (gcx, wy), "gate no")
    label(fig, gcx + 0.2, gcy + gh / 2 + 0.16, "no")
    bw, bh = 1.3, 0.4
    box = Rectangle((fx(gcx - bw / 2), fy(wy + bh)), bw / W_FIG, bh / H_FIG, transform=fig.transFigure,
                    facecolor=S.LIGHT, edgecolor=S.INK, hatch="///", linewidth=S.LW_THIN, zorder=-1)
    box.set_gid("box:withhold")
    fig.add_artist(box)
    fig.text(fx(gcx), fy(wy + bh / 2), "withhold", ha="center", va="center",
             bbox=dict(boxstyle="square,pad=0.1", facecolor=S.LIGHT, edgecolor="none"))
    label(fig, gcx, wy + bh + 0.2, "taken at 18:00 KST", ha="center")


def stage_e(fig, D):
    x0, w = STAGES["e"]
    rt = D["rt"]
    roads = D["roads3"]
    y = TOP + 0.62
    label(fig, x0, y - 0.22, "When each road is blocked")
    lw_ = 1.05
    ax = axes_in(fig, x0 + lw_, y + 0.05, w - lw_ - 0.1, 1.2)
    tmax = 75 * 60
    for i, r in enumerate(roads):
        yy = 2 - i
        ax.barh(yy, r["block_s"], left=0, height=0.5, color=S.SAFE, edgecolor=S.INK, linewidth=0.6)
        ax.barh(yy, tmax - r["block_s"], left=r["block_s"], height=0.5, facecolor=S.WHITE, edgecolor=S.FIRE,
                hatch="////", linewidth=0.6)
        ax.plot([r["exit_s"], r["exit_s"]], [yy - 0.4, yy + 0.4], color=S.INK, lw=2.2, solid_capstyle="butt")
    ax.set_xlim(0, tmax)
    ax.set_ylim(-0.6, 2.6)
    ax.set_yticks([2, 1, 0])
    ax.set_yticklabels(["Road A", "Road B", "Road C"])
    ax.set_xticks([0, 1800, 3600])
    ax.set_xticklabels(["18:00", "18:30", "19:00"])
    ax.tick_params(axis="y", length=0)
    yk = y + 2.05
    rows = [[("open", "open"), ("blocked", "blocked")], [("car", "car leaves road")]]
    for j, items in enumerate(rows):
        xk = x0 + lw_
        for kind, txt in items:
            kax = axes_in(fig, xk, yk + j * 0.42 - 0.13, 0.3, 0.26, picture=False)
            kax.set_xlim(0, 1)
            kax.set_ylim(0, 1)
            kax.axis("off")
            if kind == "car":
                kax.plot([0.5, 0.5], [0.0, 1.0], color=S.INK, lw=2.2, solid_capstyle="butt")[0].set_gid("bg:key")
            else:
                r_ = Rectangle((0, 0.1), 1, 0.8, facecolor=S.SAFE if kind == "open" else S.WHITE,
                               edgecolor=S.INK if kind == "open" else S.FIRE, hatch=None if kind == "open" else "////",
                               linewidth=0.6)
                r_.set_gid("bg:key")
                kax.add_patch(r_)
            t = label(fig, xk + 0.4, yk + j * 0.42, txt)
            fig.canvas.draw()
            xk += 0.4 + t.get_window_extent().width / S.DPI + 0.35
    ym = yk + 1.05
    label(fig, x0, ym - 0.22, "Backward pass from shelters")
    lonlat = np.array(rt["node_lonlat"])
    ld = np.array(rt["node_ld_s"], dtype=float)
    route = np.array(rt["route_lonlat"])
    sh = np.array(rt["shelters_lonlat"])
    pts = np.vstack([route, sh, lonlat[ld >= 0]])
    lon0, lat0 = pts.min(0)
    lon1, lat1 = pts.max(0)
    padx, pady = (lon1 - lon0) * 0.05, (lat1 - lat0) * 0.08
    bb = [lon0 - padx, lat0 - pady, lon1 + padx, lat1 + pady]
    mw = w - 1.15
    mh = map_height(bb, mw)
    if mh > BOTTOM - ym:
        mh = BOTTOM - ym
        k = math.cos(math.radians((bb[1] + bb[3]) / 2))
        mw = mh * (bb[2] - bb[0]) * k / (bb[3] - bb[1])
    ax = axes_in(fig, x0, ym, mw, mh)
    map_axes(ax, bb)
    arr, tp, ps = D["arr"], D["tp"], D["ps"]
    known = PolyCollection(raster_cells(arr, tp, ps, np.isfinite(arr) & (arr == 0)), facecolors=S.LIGHT,
                           edgecolors=S.LIGHT, linewidths=0.5, zorder=0)
    known.set_gid("bg:known fire")
    ax.add_collection(known)
    pairs = np.array(rt["edge_pairs"])
    a, b = ld[pairs[:, 0]], ld[pairs[:, 1]]
    ok = (a >= 0) & (b >= 0)
    segs = np.stack([lonlat[pairs[:, 0]], lonlat[pairs[:, 1]]], axis=1)
    grey = LineCollection(segs[~ok], colors=S.MID, linewidths=0.35, zorder=1)
    grey.set_gid("bg:roads without departure")
    ax.add_collection(grey)
    col = LineCollection(segs[ok], array=np.minimum(a[ok], b[ok]), cmap=S.CONTINUOUS_CMAP, norm=mc.Normalize(0, 3600),
                         linewidths=1.6, zorder=2)
    col.set_gid("bg:deadline field")
    ax.add_collection(col)
    ax.plot(route[:, 0], route[:, 1], color=S.WHITE, lw=4.4, solid_capstyle="round", zorder=3)[0].set_gid("bg:h")
    ax.plot(route[:, 0], route[:, 1], color=S.INK, lw=2.0, solid_capstyle="round", zorder=4)[0].set_gid("bg:route")
    o = rt["origin_lonlat"]
    ax.plot([o[0]], [o[1]], marker="o", ms=9, mfc=S.WHITE, mec=S.INK, mew=1.4, zorder=5)[0].set_gid("bg:village")
    s = ax.scatter(sh[:, 0], sh[:, 1], s=60, marker="s", facecolor=S.SAFE, edgecolor=S.INK, linewidths=0.8, zorder=5)
    s.set_gid("bg:shelters")
    cx_ = x0 + mw + 0.2
    label(fig, cx_ - 0.05, ym + mh + 0.12, "leave by")
    cax = axes_in(fig, cx_, ym + 0.1, 0.12, mh - 0.45)
    D["e_map_mid"] = ym + 0.55
    cb = fig.colorbar(col, cax=cax, orientation="vertical")
    cb.set_ticks([0, 1800, 3600])
    cb.ax.set_yticklabels(["18:00", "18:30", "19:00"])
    cb.ax.invert_yaxis()
    cb.outline.set_linewidth(0.6)


def stage_f(fig, D):
    x0, w = STAGES["f"]
    rt = D["rt"]
    y = TOP + 0.62
    label(fig, x0, y - 0.22, "Village card")
    ch = 2.15
    card = Rectangle((fx(x0), fy(y + ch)), w / W_FIG, ch / H_FIG, transform=fig.transFigure, facecolor=S.WHITE,
                     edgecolor=S.INK, linewidth=S.LW_THIN, zorder=-1)
    card.set_gid("box:card")
    fig.add_artist(card)
    label(fig, x0 + 0.12, y + 0.27, D["name_en"])
    label(fig, x0 + 0.12, y + 0.65, f"Leave by {kst(rt['ld_at_origin_s'])}")
    label(fig, x0 + 0.12, y + 1.03, f"To {D['shelter_cat']} shelter")
    route = np.array(rt["route_lonlat"])
    tax = axes_in(fig, x0 + 0.15, y + 1.3, w - 0.3, 0.7, picture=False)
    tax.axis("off")
    k = math.cos(math.radians(route[:, 1].mean()))
    tax.plot(route[:, 0], route[:, 1], color=S.INK, lw=1.6)[0].set_gid("bg:route thumbnail")
    tax.plot([route[0, 0]], [route[0, 1]], marker="o", ms=6, mfc=S.WHITE, mec=S.INK, mew=1.0)[0].set_gid("bg:o")
    tax.plot([route[-1, 0]], [route[-1, 1]], marker="s", ms=6, mfc=S.SAFE, mec=S.INK, mew=0.8)[0].set_gid("bg:s")
    tax.set_aspect(1 / k, adjustable="datalim")
    yc = y + ch + 0.15
    ya = yc + 0.95
    arrow(fig, (x0 + 0.45, yc), (x0 + 0.45, ya), "certificate")
    label(fig, x0 + 0.58, yc + 0.45, "certificate")
    cb_h = 0.95
    chk = Rectangle((fx(x0), fy(ya + cb_h)), w / W_FIG, cb_h / H_FIG, transform=fig.transFigure,
                    facecolor=S.WHITE, edgecolor=S.INK, linewidth=S.LW_THIN, zorder=-1)
    chk.set_gid("box:checker")
    fig.add_artist(chk)
    fig.text(fx(x0 + w / 2), fy(ya + cb_h / 2), "Separate\nchecker", ha="center", va="center", linespacing=1.1)
    yo = ya + cb_h + 0.65
    arrow(fig, (x0 + 0.45, ya + cb_h), (x0 + 0.45, yo), "verdict")
    label(fig, x0, yo + 0.3, "accept / reject")


# ====================================================================== checks
def check_arrows(fig):
    """No arrow may cross a picture (map, kernel, colour bar, chart)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    probs = []
    from matplotlib.path import Path as MPath
    for a, p0, p1 in ARROWS:
        dpath = MPath(fig.transFigure.transform([(fx(p0[0]), fy(p0[1])), (fx(p1[0]), fy(p1[1]))]))
        for ax in PICTURES:
            bb = ax.get_window_extent(r)
            inner = bb.padded(-1)
            if dpath.intersects_bbox(inner, filled=False):
                probs.append({"arrow": a.get_gid(), "picture": ax.get_label() or str(ax.get_position().bounds)})
    return probs


def cvd_check():
    """Palette pairs that carry meaning stay distinct under simulated colour-vision deficiency (Machado 2009, full
    severity) and in greyscale: CIE76 distance in Lab."""
    M = {"protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
         "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
         "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]}

    def lin(c):
        c = np.array(mc.to_rgb(c))
        return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

    def lab(rgbl):
        X = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]) @ rgbl
        n = X / np.array([0.95047, 1.0, 1.08883])
        f = np.where(n > 216 / 24389, np.cbrt(n), (24389 / 27 * n + 16) / 116)
        return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])

    pairs = [("SAFE", "FIRE"), ("SAFE", "LIGHT"), ("FIRE", "LIGHT"), ("SAFE", "WHITE"), ("FIRE", "WHITE"),
             ("INK", "SAFE"), ("INK", "FIRE")]
    out = []
    for a, b in pairs:
        for kind in ("normal", "protan", "deutan", "tritan", "grey"):
            ca, cb = lin(getattr(S, a)), lin(getattr(S, b))
            if kind in M:
                ca, cb = np.clip(np.array(M[kind]) @ ca, 0, 1), np.clip(np.array(M[kind]) @ cb, 0, 1)
            if kind == "grey":
                ya, yb = (np.array([0.2126, 0.7152, 0.0722]) @ ca,) * 3, (np.array([0.2126, 0.7152, 0.0722]) @ cb,) * 3
                ca, cb = np.array(ya), np.array(yb)
            d = float(np.linalg.norm(lab(ca) - lab(cb)))
            out.append({"pair": f"{a}/{b}", "vision": kind, "deltaE": round(d, 1)})
    return out


# ====================================================================== main
def main():
    L = Ledger("F04", "Method overview: one case, Uiseong–Andong, 25 March 2025, 18:00 KST")
    D = read(L)
    fig = S.plt.figure(figsize=(W_FIG, H_FIG), dpi=S.DPI)
    heads = {"a": "(a) Inputs", "b": "(b) Spread forecast", "c": "(c) Exposure", "d": "(d) Safety distance",
             "e": "(e) Routing", "f": "(f) Output"}
    for k_, t in heads.items():
        label(fig, STAGES[k_][0], 0.3, t)
    stage_a(fig, D)
    stage_b(fig, D)
    stage_c(fig, D)
    stage_e(fig, D)
    stage_d(fig, D)
    stage_f(fig, D)
    # stage-to-stage arrows, in the gaps only
    ya = 3.0
    for s0, s1 in (("a", "b"), ("b", "c"), ("c", "d")):
        xa = STAGES[s0][0] + STAGES[s0][1] + 0.08
        xb = STAGES[s1][0] - 0.08
        arrow(fig, (xa, ya), (xb, ya), f"{s0}->{s1}")
    gx, gy = D["gate_yes"]
    arrow(fig, (gx, gy), (STAGES["e"][0] - 0.08, gy), "gate yes -> e")
    arrow(fig, (STAGES["e"][0] + STAGES["e"][1] + 0.08, 2.1), (STAGES["f"][0] - 0.08, 2.1), "e->f")
    rt = D["rt"]
    meta = D.get("fc_meta")
    cap = add_caption(fig, (
        f"Figure 4. One case through the method, Uiseong–Andong at 18:00 KST on 25 March 2025: the inputs (a); the "
        f"M548 forecast, its four learned kernels at one cell and the next-hour burn probability (b); exposure, shown on "
        f"Fish Creek because no Korean fuel maps exist (c); the known fire widened by the calibrated 8 h reach, which "
        f"the gate withheld at this hour (d); and the backward pass that gives {D['name_en']} a last safe departure of "
        f"{kst(rt['ld_at_origin_s'])} and a route that a separate checker accepted (e–f), where the road blockages "
        f"come from the detected fire and the reach, not from (b)."),
        x_in=0.2, width_in=16.6, top_in=BOTTOM + 0.6)
    probs = check_arrows(fig)
    cvd = cvd_check()
    worst = {}
    for r in cvd:
        worst[r["vision"]] = min(worst.get(r["vision"], 1e9), r["deltaE"])
    readable_px = S.PT_TEXT * 1700 / (W_FIG * 72)
    checks = {"arrows_crossing_pictures": probs, "cvd_min_deltaE": worst, "cvd_pairs": cvd,
              "smallest_text_pt": S.PT_TEXT, "smallest_text_px_at_1700px_wide": round(readable_px, 1),
              "rule": "arrows: none may cross a map, kernel, colour bar or chart; colour: every meaningful pair "
                      "keeps deltaE >= 10 under protan/deutan/tritan simulation; in greyscale open (solid teal) and "
                      "blocked (white with red hatching) differ by fill and hatching, not by grey level; text: at least 18 px tall when the figure is 1,700 px wide"}
    (S.CHECK / "F04_overview_checks.json").write_text(json.dumps(checks, indent=1))
    print("arrow check", "PASS" if not probs else probs)
    print("cvd min deltaE", worst, "text px at 1700", round(readable_px, 1))
    assert not probs
    assert min(v for k_, v in worst.items() if k_ != "grey") >= 10, worst
    assert readable_px >= 18
    L.save()
    save(fig, "F04_overview", caption=cap, png_dpi=300, tight=True, transparent=True)


if __name__ == "__main__":
    main()
