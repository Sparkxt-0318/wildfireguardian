"""Legible F04, split in two (slots 1700 x 620 each; DECISIONS.md D48).

F04a: (a) inputs at 18:00, (b) where fire may spread (learned kernels, burn chance next hour), (c) heat near the fire
      (Fish Creek). F04b: (d) margin and gate, (e) when roads are blocked (three roads, leave-by map), (f) leave-by card
      and checker. All data from F04_overview.read (same files, same checks); Hangul place names kept. Changes are
layout and text only: the input maps become two (detections with wind, roads and villages), the rate formula and the
card's route thumbnail are left out, keys are shortened.
"""
import math

import matplotlib.colors as mc
import numpy as np
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle
from pyproj import Transformer

import F04_overview as O
import legible as G
import style as S
from prov import Ledger

LIGHTG = O.LIGHTG


def arrow(fig, p0, p1, gid):
    W, H = fig._wh
    a = FancyArrowPatch((p0[0] / W, 1 - p0[1] / H), (p1[0] / W, 1 - p1[1] / H), transform=fig.transFigure,
                        arrowstyle="-|>,head_length=0.6,head_width=0.3", mutation_scale=22, color=S.INK, lw=1.6,
                        shrinkA=0, shrinkB=0)
    a.set_gid(f"arrow:{gid}")
    fig.add_artist(a)


def bracket(fig, x0, x1, text, y=0.62):
    W, H = fig._wh
    ln = S.plt.Line2D([x0 / W, x0 / W, x1 / W, x1 / W], [1 - (y + 0.1) / H, 1 - y / H, 1 - y / H, 1 - (y + 0.1) / H],
                      transform=fig.transFigure, color=S.INK, lw=1.0)
    ln.set_gid("bracket")
    fig.add_artist(ln)
    G.text_in(fig, (x0 + x1) / 2, y - 0.3, text, ha="center")


def map_in(fig, D, x, y, w, bbox=None):
    bb = bbox or D["strip"]
    h = O.map_height(bb, w)
    ax = G.ax_in(fig, x, y, w, h)
    O.map_axes(ax, bb)
    for sp in ax.spines.values():
        sp.set_linewidth(1.0)
    return ax, h


def key_box(fig, x, y, face, edge, hatch=None, w=0.45, h=0.3):
    W, H = fig._wh
    r = Rectangle((x / W, 1 - (y + h / 2) / H), w / W, h / H, transform=fig.transFigure, facecolor=face,
                  edgecolor=edge, hatch=hatch, linewidth=1.0)
    r.set_gid("bg:key")
    fig.add_artist(r)


def key_line(fig, x, y, color, lw, w=0.45, vertical=False):
    W, H = fig._wh
    if vertical:
        ln = S.plt.Line2D([(x + w / 2) / W] * 2, [1 - (y - 0.17) / H, 1 - (y + 0.17) / H], transform=fig.transFigure,
                          color=color, lw=lw, solid_capstyle="butt")
    else:
        ln = S.plt.Line2D([x / W, (x + w) / W], [1 - y / H] * 2, transform=fig.transFigure, color=color, lw=lw,
                          solid_capstyle="butt")
    ln.set_gid("bg:key")
    fig.add_artist(ln)


# ====================================================================== F04a
def f04a(D):
    fig = G.figure("F04a_overview_forecast")
    A, B, C = (0.3, 4.3), (5.4, 5.25), (11.55, 5.15)
    bracket(fig, B[0], C[0] + C[1], "Forecast model")
    for (x, _), t in zip((A, B, C), ("(a) Inputs at 18:00", "(b) Where fire may spread", "(c) Heat near the fire")):
        G.text_in(fig, x, 0.98, t)
    # (a) two input maps
    x0, w = A
    G.text_in(fig, x0, 1.5, "Fire detections, wind")
    ax1, h = map_in(fig, D, x0, 1.78, w)
    lon, lat = Transformer.from_crs(5179, 4326, always_xy=True).transform(
        np.array([d["x"] for d in D["discs"]]), np.array([d["y"] for d in D["discs"]]))
    ax1.scatter(lon, lat, s=6, color=S.RED, linewidths=0).set_gid("bg:detections")
    lo, la, u, v = D["wind"]
    ax1.quiver(lo, la, u, v, color=S.INK, scale=45, scale_units="inches", width=0.005, headwidth=4, headlength=4.5,
               headaxislength=4).set_gid("bg:wind")
    G.text_in(fig, x0, 1.78 + h + 0.5, "Roads and villages")
    ax2, _ = map_in(fig, D, x0, 1.78 + h + 0.77, w)
    lc = LineCollection(D["roads"], colors=S.GREY, linewidths=0.4)
    lc.set_gid("bg:roads")
    ax2.add_collection(lc)
    ax2.scatter([q["lon"] for q in D["places"]], [q["lat"] for q in D["places"]], s=9, color=S.INK, linewidths=0,
                zorder=3).set_gid("bg:villages")
    ax2.scatter([q["lon"] for q in D["shelters"]], [q["lat"] for q in D["shelters"]], s=16, marker="s",
                facecolor=S.PAPER, edgecolor=S.INK, linewidths=0.6, zorder=4).set_gid("bg:shelters")
    # (b) kernels and burn chance
    x0, w = B
    fc = D["fc"]
    G.text_in(fig, x0, 1.5, "Learned spread kernels")
    kw, kg, ky = 0.66, 0.36, 1.75
    sizes = [int(s) for s in fc["kernel_sizes"]]
    vmax = max(float(np.nanmax(fc[f"kernel_{s}"])) for s in sizes)
    norm = mc.Normalize(0, vmax)
    for i, s in enumerate(sizes):
        ax = G.ax_in(fig, x0 + i * (kw + kg), ky, kw, kw)
        k = fc[f"kernel_{s}"].copy()
        k[s // 2, s // 2] = np.nan
        im = ax.imshow(k, cmap=S.ramp(S.BLUE), norm=norm, interpolation="nearest")
        im.set_gid("bg:kernel")
        G.strip(ax)
        G.text_in(fig, x0 + i * (kw + kg) + kw / 2, ky + kw + 0.3, f"{s}×{s}", ha="center")
    cw = 4 * kw + 3 * kg
    cax = G.ax_in(fig, x0, ky + kw + 0.62, cw, 0.13)
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_ticks([0, vmax])
    cb.ax.set_xticklabels(["0", f"{vmax * 1e3:.1f}"])
    cb.ax.get_xticklabels()[0].set_ha("left")
    cb.ax.get_xticklabels()[-1].set_ha("right")
    cb.outline.set_linewidth(0.8)
    G.text_in(fig, x0 + cw + 0.2, ky + kw + 0.685, "10$^{-3}$ h$^{-1}$")
    ym = ky + kw + 1.87
    G.text_in(fig, x0, ym - 0.27, "Burn chance, next hour")
    mw = 3.3
    ax, mh = map_in(fig, D, x0, ym, mw)
    prob = fc["probability"].astype(float)
    valid = fc["valid"].astype(bool)
    burned = fc["burned"]
    tr = fc["affine"]
    Hh, Ww = prob.shape
    tx = Transformer.from_crs(5179, 4326, always_xy=True)
    cols, rows = np.meshgrid(np.arange(Ww + 1), np.arange(Hh + 1))
    LO, LA = tx.transform(tr[2] + cols * tr[0], tr[5] + rows * tr[4])
    pmax = float(D["fc_meta"]["max_probability_region"])
    show = np.ma.masked_where(~valid | (burned == 1) | (prob <= 0), prob)
    pm = ax.pcolormesh(LO, LA, show, cmap=S.ramp(S.RED), norm=mc.Normalize(0, pmax), shading="flat", rasterized=True)
    pm.set_gid("bg:probability")
    ax.set_facecolor(S.PAPER)
    bu = np.ma.masked_where(burned != 1, np.ones_like(prob))
    ax.pcolormesh(LO, LA, bu, cmap=mc.ListedColormap([LIGHTG]), shading="flat", rasterized=True).set_gid("bg:burned")
    cax = G.ax_in(fig, x0, ym + mh + 0.15, mw, 0.13)
    cb = fig.colorbar(pm, cax=cax, orientation="horizontal")
    cb.set_ticks([0, pmax])
    cb.ax.set_xticklabels(["0", f"{pmax:.3f}"])
    cb.ax.get_xticklabels()[0].set_ha("left")
    cb.ax.get_xticklabels()[-1].set_ha("right")
    cb.outline.set_linewidth(0.8)
    key_box(fig, x0 + mw + 0.25, ym + 0.3, LIGHTG, S.INK)
    G.text_in(fig, x0 + mw + 0.25, ym + 0.85, "already\nburned", va="center", linespacing=1.0)
    # (c) heat near the fire
    x0, w = C
    fz = D["fish"]
    G.text_in(fig, x0, 1.5, "Fish Creek fire, US")
    key_line(fig, x0, 2.0, S.INK, 2.0)
    G.text_in(fig, x0 + 0.6, 2.0, f"burned by {D['fish_cutoff'][11:16]} UTC")
    q0, q1 = int(fz["crop_row_start"]), int(fz["crop_row_stop_exclusive"])
    p0, p1 = int(fz["crop_column_start"]), int(fz["crop_column_stop_exclusive"])
    act = fz["mean_active_burning_probability"][q0:q1, p0:p1].astype(float)
    heat = fz["mean_heat_flux_w_m2"][q0:q1, p0:p1].astype(float)
    burnedf = fz["current_burned_state"][q0:q1, p0:p1].astype(float)
    specs = []
    for title, arr in (("Share of hour\nburning", act), ("Radiant heat,\nW m$^{-2}$", heat)):
        pos = arr[arr > 0]
        vmin = 10.0 ** math.floor(math.log10(np.percentile(pos, 25)))
        specs.append((title, arr, mc.LogNorm(vmin, float(arr.max()))))
    on = np.zeros(act.shape, bool)
    for _, arr, nrm in specs:
        on |= arr >= nrm.vmin
    rr, cc = np.where(on | (burnedf > 0.5))
    r0, r1 = max(rr.min() - 1, 0), min(rr.max() + 2, act.shape[0])
    c0, c1 = max(cc.min() - 1, 0), min(cc.max() + 2, act.shape[1])
    mw2 = 2.35
    mh2 = mw2 * (r1 - r0) / (c1 - c0)
    for j, (title, arr, nrm) in enumerate(specs):
        xm = x0 + j * (mw2 + 0.45)
        G.text_in(fig, xm, 3.12, title, va="bottom", linespacing=1.0)
        ax = G.ax_in(fig, xm, 3.22, mw2, mh2)
        im = ax.imshow(np.ma.masked_less(arr[r0:r1, c0:c1], nrm.vmin), cmap=S.ramp(S.RED), norm=nrm,
                       interpolation="nearest")
        im.set_gid("bg:exposure")
        ax.set_facecolor(S.PAPER)
        ax.contour(burnedf[r0:r1, c0:c1], levels=[0.5], colors=S.INK, linewidths=2.0).set_gid("bg:fire outline")
        G.strip(ax)
        cax = G.ax_in(fig, xm, 3.22 + mh2 + 0.13, mw2, 0.13)
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        cb.ax.minorticks_off()
        lo_, hi_ = math.ceil(math.log10(nrm.vmin)), math.floor(math.log10(nrm.vmax))
        step = max(1, math.ceil((hi_ - lo_) / 2))
        ks = list(range(lo_, hi_ + 1, step))
        cb.set_ticks([10.0 ** k for k in ks])
        cb.ax.set_xticklabels(["1" if k == 0 else ("10" if k == 1 else f"10$^{{{k}}}$") for k in ks])
        cb.outline.set_linewidth(0.8)
    ya = 4.0
    arrow(fig, (A[0] + A[1] + 0.12, ya), (B[0] - 0.12, ya), "a->b")
    arrow(fig, (B[0] + B[1] + 0.05, ya), (C[0] - 0.12, ya), "b->c")
    return fig


# ====================================================================== F04b
def f04b(D):
    fig = G.figure("F04b_overview_roads")
    Dd, E, F = (0.3, 4.3), (5.25, 6.75), (12.65, 4.15)
    bracket(fig, Dd[0], F[0] + F[1], "Road plan from the detected fire", y=0.55)
    for (x, _), t in zip((Dd, E, F), ("(d) Margin and gate", "(e) When roads are blocked", "(f) Leave-by card")):
        G.text_in(fig, x, 0.93, t)
    rt = D["rt"]
    # (d) known fire plus margin, and the gate
    x0, w = Dd
    ax, mh = map_in(fig, D, x0, 1.22, w)
    arr, tp, ps = D["arr"], D["tp"], D["ps"]
    reach = PolyCollection(O.raster_cells(arr, tp, ps, np.isfinite(arr) & (arr > 0) & (arr <= 480)),
                           facecolors=S.PAPER, edgecolors=S.RED, linewidths=0, hatch="//////", zorder=1)
    reach.set_gid("bg:reach")
    ax.add_collection(reach)
    known = PolyCollection(O.raster_cells(arr, tp, ps, np.isfinite(arr) & (arr == 0)), facecolors=S.RED,
                           edgecolors=S.RED, linewidths=0.4, zorder=2)
    known.set_gid("bg:known fire")
    ax.add_collection(known)
    yk = 1.22 + mh + 0.36
    key_box(fig, x0, yk, S.RED, S.RED)
    G.text_in(fig, x0 + 0.6, yk, "known fire, 18:00")
    key_box(fig, x0, yk + 0.5, S.PAPER, S.RED, hatch="////")
    G.text_in(fig, x0 + 0.6, yk + 0.5, f"margin: {rt['R8_m'] / 1000:.0f} km in 8 h")
    W, H = fig._wh
    gy0, gh, gw = yk + 0.86, 0.95, 4.0
    gcx, gcy = x0 + gw / 2, gy0 + gh / 2
    pts = [(x0, gcy), (x0 + 0.35, gy0), (x0 + gw - 0.35, gy0), (x0 + gw, gcy), (x0 + gw - 0.35, gy0 + gh),
           (x0 + 0.35, gy0 + gh)]
    hexa = Polygon([(px / W, 1 - py / H) for px, py in pts], closed=True, transform=fig.transFigure,
                   facecolor=S.PAPER, edgecolor=S.INK, linewidth=1.0, zorder=-1)
    hexa.set_gid("box:gate")
    fig.add_artist(hexa)
    G.text_in(fig, gcx, gcy, "Within the calibration\nrange?", ha="center", linespacing=1.0)
    arrow(fig, (x0 + gw, gcy), (E[0] - 0.1, gcy), "gate yes -> e")
    G.text_in(fig, x0 + gw + 0.14, gcy - 0.42, "yes")
    wy = gy0 + gh + 0.62
    arrow(fig, (x0 + 0.9, gy0 + gh), (x0 + 0.9, wy), "gate no")
    G.text_in(fig, x0 + 1.12, gy0 + gh + 0.31, "no")
    bw, bh = 1.6, 0.56
    box = Rectangle(((x0 + 0.9 - bw / 2) / W, 1 - (wy + bh) / H), bw / W, bh / H, transform=fig.transFigure,
                    facecolor=LIGHTG, edgecolor=S.INK, hatch="///", linewidth=1.0, zorder=-1)
    box.set_gid("box:withhold")
    fig.add_artist(box)
    back = Rectangle(((x0 + 0.9 - 0.68) / W, 1 - (wy + bh / 2 + 0.18) / H), 1.36 / W, 0.36 / H,
                     transform=fig.transFigure, facecolor=LIGHTG, edgecolor="none", zorder=-0.5)
    back.set_gid("bg:label backing")
    fig.add_artist(back)
    G.text_in(fig, x0 + 0.9, wy + bh / 2, "withheld", ha="center")
    G.text_in(fig, x0 + 0.9 + bw / 2 + 0.2, wy + bh / 2, "18:00 KST\ntook this exit", linespacing=1.0)
    # (e) three roads, then the leave-by map
    x0, w = E
    roads = D["roads3"]
    lw_ = 1.45
    ax = G.ax_in(fig, x0 + lw_, 1.22, 3.0, 1.45)
    tmax = 75 * 60
    for i, r in enumerate(roads):
        yy = 2 - i
        ax.barh(yy, r["block_s"], left=0, height=0.55, color=S.BLUE, edgecolor=S.INK, linewidth=0.8)
        ax.barh(yy, tmax - r["block_s"], left=r["block_s"], height=0.55, facecolor=S.PAPER, edgecolor=S.RED,
                hatch="////", linewidth=0.8)
        ax.plot([r["exit_s"]] * 2, [yy - 0.42, yy + 0.42], color=S.INK, lw=3.0, solid_capstyle="butt")
    ax.set_xlim(0, tmax)
    ax.set_ylim(-0.6, 2.6)
    ax.set_yticks([2, 1, 0])
    ax.set_yticklabels(["Road A", "Road B", "Road C"])
    ax.set_xticks([0, 1800, 3600])
    ax.set_xticklabels(["18:00", "18:30", "19:00"])
    ax.tick_params(axis="y", length=0)
    xk = x0 + lw_ + 3.25
    key_box(fig, xk, 1.42, S.BLUE, S.INK)
    G.text_in(fig, xk + 0.6, 1.42, "open")
    key_box(fig, xk, 1.95, S.PAPER, S.RED, hatch="////")
    G.text_in(fig, xk + 0.6, 1.95, "blocked")
    key_line(fig, xk, 2.62, S.INK, 3.0, vertical=True)
    G.text_in(fig, xk + 0.6, 2.62, "car leaves\nthe road", linespacing=1.0)
    yk = 2.62
    # leave-by map
    ym = 3.32
    mw, mh_ = 4.1, 6.2 - ym - 0.1
    lonlat = np.array(rt["node_lonlat"])
    ld = np.array(rt["node_ld_s"], dtype=float)
    route = np.array(rt["route_lonlat"])
    sh = np.array(rt["route_shelter_lonlat"])
    o = rt["origin_lonlat"]
    pts = np.vstack([route, [o]])
    lon0, lat0 = pts.min(0)
    lon1, lat1 = pts.max(0)
    pady = (lat1 - lat0) * 0.8
    la0, la1 = lat0 - pady, lat1 + pady
    k_ = math.cos(math.radians((la0 + la1) / 2))
    half_lon = max((la1 - la0) * mw / mh_ / k_ / 2, (lon1 - lon0) * 0.62)
    cx_ = (lon0 + lon1) / 2
    bb = [cx_ - half_lon, la0, cx_ + half_lon, la1]
    ax, mh2 = map_in(fig, D, x0, ym, mw, bbox=bb)
    known = PolyCollection(O.raster_cells(arr, tp, ps, np.isfinite(arr) & (arr == 0)), facecolors=S.tint(S.RED, 0.32),
                           edgecolors=S.tint(S.RED, 0.32), linewidths=0.5, zorder=0)
    known.set_gid("bg:known fire")
    ax.add_collection(known)
    pairs = np.array(rt["edge_pairs"])
    ways = np.array(rt["edge_pair_way"])
    a, b = ld[pairs[:, 0]], ld[pairs[:, 1]]
    segs = np.stack([lonlat[pairs[:, 0]], lonlat[pairs[:, 1]]], axis=1)
    inside = np.all((segs[..., 0] >= bb[0]) & (segs[..., 0] <= bb[2]) & (segs[..., 1] >= bb[1]) &
                    (segs[..., 1] <= bb[3]), axis=1)
    kk = math.cos(math.radians((bb[1] + bb[3]) / 2))
    seg_m = np.hypot((segs[:, 1, 0] - segs[:, 0, 0]) * kk, segs[:, 1, 1] - segs[:, 0, 1]) * 111_320
    way_m = {}
    for wy_, m_, i_ in zip(ways, seg_m, inside):
        if i_:
            way_m[wy_] = way_m.get(wy_, 0.0) + m_
    keep = np.array([way_m.get(wy_, 0.0) >= O.MIN_WAY_M for wy_ in ways]) & inside
    ok = (a >= 0) & (b >= 0) & keep
    lo = np.minimum(a, b)
    for c0, c1, f, txt in O.LEAVE_CLASSES[::-1]:
        sel = ok & (lo >= c0) & (lo < c1)
        col = LineCollection(segs[sel], colors=S.tint(S.BLUE, f), linewidths=3.4, zorder=2, capstyle="round")
        col.set_gid(f"bg:leave by {txt}")
        ax.add_collection(col)
    ax.plot(route[:, 0], route[:, 1], color=S.PAPER, lw=6.0, solid_capstyle="round", zorder=3)[0].set_gid("bg:h")
    ax.plot(route[:, 0], route[:, 1], color=S.INK, lw=2.8, solid_capstyle="round", zorder=4)[0].set_gid("bg:route")
    ax.plot([o[0]], [o[1]], marker="o", ms=12, mfc=S.INK, mec=S.PAPER, mew=1.4, zorder=5)[0].set_gid("bg:village")
    ax.plot([sh[0]], [sh[1]], marker="s", ms=12, mfc=S.PAPER, mec=S.INK, mew=1.4, zorder=5)[0].set_gid("bg:shelter")
    bbx = dict(boxstyle="square,pad=0.12", facecolor=S.PAPER, edgecolor="none", alpha=0.9)
    ax.annotate(D["name_ko"], xy=o, xytext=(0, 13), textcoords="offset points", ha="center", va="bottom", bbox=bbx,
                zorder=6)
    ax.annotate("shelter", xy=sh, xytext=(0, 13), textcoords="offset points", ha="center", va="bottom",
                bbox=bbx, zorder=6)
    xl = x0 + mw + 0.3
    G.text_in(fig, xl, ym + 0.12, "Leave by")
    for i, (c0, c1, f, txt) in enumerate(O.LEAVE_CLASSES):
        key_line(fig, xl, ym + 0.62 + i * 0.5, S.tint(S.BLUE, f), 4.0)
        G.text_in(fig, xl + 0.6, ym + 0.62 + i * 0.5, txt)
    # (f) card and checker
    x0, w = F
    cy0, ch = 1.22, 1.6
    W, H = fig._wh
    card = Rectangle((x0 / W, 1 - (cy0 + ch) / H), w / W, ch / H, transform=fig.transFigure, facecolor=S.PAPER,
                     edgecolor=S.INK, linewidth=1.0, zorder=-1)
    card.set_gid("box:card")
    fig.add_artist(card)
    G.text_in(fig, x0 + 0.18, cy0 + 0.3, D["name_ko"])
    G.text_in(fig, x0 + 0.18, cy0 + 0.81, f"Leave by {O.kst(rt['ld_at_origin_s'])}")
    G.text_in(fig, x0 + 0.18, cy0 + 1.32, f"To {D['shelter_label']}")
    ya = cy0 + ch
    yb = ya + 0.58
    arrow(fig, (x0 + 0.5, ya + 0.05), (x0 + 0.5, yb), "certificate")
    G.text_in(fig, x0 + 0.7, (ya + yb) / 2, "certificate")
    cbh = 0.92
    chk = Rectangle((x0 / W, 1 - (yb + cbh) / H), w / W, cbh / H, transform=fig.transFigure, facecolor=S.PAPER,
                    edgecolor=S.INK, linewidth=1.0, zorder=-1)
    chk.set_gid("box:checker")
    fig.add_artist(chk)
    G.text_in(fig, x0 + w / 2, yb + cbh / 2, "Independent\nchecker", ha="center", linespacing=1.0)
    yo = yb + cbh + 0.42
    arrow(fig, (x0 + 0.5, yb + cbh), (x0 + 0.5, yo), "verdict")
    verdict = "route accepted" if D["checked"] else "route rejected"
    tail = ",\nbut the gate withheld\nthis hour" if D["abstain"]["abstain"] else ""
    G.text_in(fig, x0, yo + 0.08, verdict + tail, va="top", linespacing=1.0)
    arrow(fig, (E[0] + E[1] + 0.02, 2.0), (F[0] - 0.1, 2.0), "e->f")
    return fig


def main():
    L = Ledger("L04", "Legible F04 (two halves)")
    D = O.read(L)
    L.save()
    fa = f04a(D)
    G.save(fa, "F04a_overview_forecast")
    fb = f04b(D)
    from realmap import back_labels
    back_labels(fb)
    G.save(fb, "F04b_overview_roads")


if __name__ == "__main__":
    main()
