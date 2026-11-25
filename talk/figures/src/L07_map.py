"""Legible F07 map: forward search from one village against one backward pass (slot 1700 x 640; D48). Same data and
checks as F07_map.py (build/F07_map.json); larger place labels and legend, keys shortened."""
import numpy as np
from matplotlib.collections import LineCollection

import legible as G
import placenames as PN
import realmap as M
import style as S
from F07_map import BBOX, CLASSES, Z, in_view
from prov import Ledger


def main():
    L = Ledger("L07", "Legible F07 map")
    d = M.load()
    fw = d["forward"]
    shelter_id = PN.by_entry_node(fw["shelter_node"])
    vill = [v for v in d["villages"] if in_view(v["entry_lonlat"])]
    fig = G.figure("F07_map")
    W, H = fig._wh
    X0, MW, GAP, TOP = 0.3, 6.2, 0.3, 0.62
    axs, mh = [], None
    for i in range(2):
        x = X0 + i * (MW + GAP)
        ax = G.ax_in(fig, x, TOP, MW, 4.0)
        M.setup(ax, BBOX, Z)
        fig.canvas.draw()
        xl, yl = ax.get_xlim(), ax.get_ylim()
        mh = MW * (yl[1] - yl[0]) / (xl[1] - xl[0])
        ax.set_position([x / W, 1 - (TOP + mh) / H, MW / W, mh / H])
        M.fire(ax, d)
        M.blocked(ax, d, lw=2.4)
        axs.append(ax)
    G.text_in(fig, X0, 0.3, "Forward: one village, one start time")
    G.text_in(fig, X0 + MW + GAP, 0.3, "Backward: one pass, every village")
    # (a) forward
    ax = axs[0]
    lc = LineCollection(M.segs(d, d["forward_settled_pairs"]), colors=S.GREY, linewidths=2.6, zorder=4,
                        capstyle="round")
    lc.set_gid("bg:forward search")
    ax.add_collection(lc)
    M.line(ax, fw["route_lonlat"], S.INK, 3.2, 6, gid="bg:forward route")
    wd = [v for v in vill if v["id"] == fw["origin"]][0]
    sm = M.point(ax, fw["route_lonlat"][-1], "shelter", size=110)[0]
    om = M.point(ax, wd["entry_lonlat"], "village", size=160)[0]
    M.tag(ax, om, f"{PN.ko(fw['origin'])}\nleaves 18:00", dx=0, dy=14, ha="center", va="bottom")
    M.tag(ax, sm, f"{PN.ko(shelter_id)}\nreached {M.kst(fw['arrival_s'])}", dx=0, dy=14, ha="center", va="bottom")
    M.scale_bar(ax)
    # (b) backward
    ax = axs[1]
    ld = np.array(d["node_ld_s"], dtype=float)
    pairs = np.array(d["edge_pairs"])
    a, b = ld[pairs[:, 0]], ld[pairs[:, 1]]
    ok = (a >= 0) & (b >= 0)
    lo = np.minimum(a, b)
    allsegs = M.segs(d, pairs)
    for c0, c1, f, txt in CLASSES[::-1]:
        sel = ok & (lo >= c0) & (lo < c1)
        c = LineCollection(allsegs[sel], colors=S.tint(S.BLUE, f), linewidths=3.0, zorder=4, capstyle="round")
        c.set_gid(f"bg:leave by {txt}")
        ax.add_collection(c)
    for s in [s for s in d["shelters_lonlat"] if in_view(s)]:
        M.point(ax, s, "shelter", size=110)
        M.point(axs[0], s, "shelter", size=90, z=7)
    for v in vill:
        if v["ld_one_pass_s"] >= 0:
            m = M.point(ax, v["entry_lonlat"], "village", size=160)[0]
            M.tag(ax, m, f"{PN.ko(v['id'])}: leave by {M.kst(v['ld_one_pass_s'])}", dx=10, dy=16, ha="left",
                  va="bottom")
        else:
            M.point(ax, v["entry_lonlat"], "inside", size=90)
        if v["id"] != fw["origin"]:
            M.point(axs[0], v["entry_lonlat"], "village" if v["ld_one_pass_s"] >= 0 else "inside", size=90, z=7)
    M.attribution(axs[1])
    # keys: map symbols under the maps, place symbols and leave-by classes in the right column
    ky = TOP + mh + 0.4
    M.key_patch(fig, X0, ky, "fire area, 18:00", W, H, M.FIRE_TINT, w_in=0.5)
    M.key_line(fig, X0 + 3.55, ky, S.RED, 2.4, "blocked road", W, H, w_in=0.5)
    M.key_line(fig, X0, ky + 0.55, S.GREY, 2.6, f"{fw['edges_settled']} road pieces searched", W, H, w_in=0.5)
    M.key_line(fig, X0 + MW + GAP, ky + 0.55, S.INK, 3.2, "route found", W, H, w_in=0.5)
    xr = X0 + 2 * MW + 2 * GAP
    G.text_in(fig, xr, TOP + 0.2, "Leave by")
    for i, (c0, c1, f, txt) in enumerate(CLASSES):
        M.key_line(fig, xr, TOP + 0.72 + i * 0.52, S.tint(S.BLUE, f), 3.5, txt, W, H, w_in=0.5)
    yk = TOP + 0.72 + 4 * 0.52 + 0.25
    M.key_patch(fig, xr, yk, "shelter", W, H, S.PAPER, S.INK, marker="s", w_in=0.5)
    M.key_patch(fig, xr, yk + 0.52, "village", W, H, S.INK, S.PAPER, marker="o", w_in=0.5)
    M.key_patch(fig, xr, yk + 1.04, "in fire area", W, H, S.PAPER, S.INK, marker="o", w_in=0.5)
    L.add("Forward search: road pieces settled", fw["edges_settled"], file=M.DATA, field="forward.edges_settled",
          shown=f"{fw['edges_settled']} road pieces searched")
    L.save()
    M.back_labels(fig)
    G.save(fig, "F07_map")


if __name__ == "__main__":
    main()
