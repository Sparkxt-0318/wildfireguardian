"""Legible F08 map: one backward step on one real road (slot 760 x 600; D48). Same data, checks and wording as
F08_map.py (build/F07_map.json, f08_step); the written-out step becomes one line under the map."""
import math

import numpy as np
from matplotlib.patches import Polygon

import legible as G
import placenames as PN
import realmap as M
import style as S
from basemap import to_m
from prov import Ledger

BBOX = [128.6650, 36.3388, 128.6800, 36.3460]
Z = 17


def main():
    L = Ledger("L08", "Legible F08 map: one backward step on a real road")
    d = M.load()
    s = d["f08_step"]
    far, drive, block = s["latest_arrival_far_end_s"], s["drive_s"], s["fire_cell"]["block_s"]
    clear = drive * s["fire_cell"]["end_fraction"]
    fire_limit = math.ceil(block - clear) - 1
    leave = min(far - drive, fire_limit)
    assert leave == s["latest_departure_via_edge_s"] == s["tail_node_ld_s"] == d["route_ld_s"], (leave, s)
    vname = PN.ko(d["forward"]["origin"])
    fig = G.figure("F08_map")
    W, H = fig._wh
    X0, MW, TOP = 0.35, 6.9, 0.1
    ax = G.ax_in(fig, X0, TOP, MW, 3.0)
    M.setup(ax, BBOX, Z, fade=0.5)
    fig.canvas.draw()
    xl, yl = ax.get_xlim(), ax.get_ylim()
    mh = MW * (yl[1] - yl[0]) / (xl[1] - xl[0])
    ax.set_position([X0 / W, 1 - (TOP + mh) / H, MW / W, mh / H])
    M.fire(ax, d)
    M.blocked(ax, d, lw=3.0)
    cell = [c for c in d["cells"] if c["cell"] == s["fire_cell"]["cell"]][0]
    pg = Polygon(to_m(np.array(cell["lonlat"])), closed=True, facecolor="none", edgecolor=S.RED, hatch="////",
                 linewidth=2.0, zorder=2)
    pg.set_gid("bg:fire cell")
    ax.add_patch(pg)
    M.line(ax, d["route_lonlat"], S.INK, 2.2, 4, halo=False, gid="bg:rest of route")
    rm = M.line(ax, s["lonlat"], S.BLUE, 6.0, 6, gid="bg:the road")
    M.point(ax, s["lonlat"][0], "village", size=180, z=8)
    fm = to_m(np.array(s["lonlat"][1]))
    ax.scatter([fm[0]], [fm[1]], s=130, marker="o", facecolor=S.PAPER, edgecolor=S.BLUE, linewidths=2.6,
               zorder=8).set_gid("bg:far end")
    M.tag(ax, rm[0], f"{vname}: leave by {M.kst(leave, True)}", dx=-20, dy=22, ha="center", va="bottom")
    M.tag(ax, fm, f"Safe arrival\nby {M.kst(far, True)}", dx=14, dy=4, ha="left", va="bottom")
    M.tag(ax, rm.mean(0), f"Drive {drive} s, {s['length_m']:.0f} m", dx=-8, dy=-16, ha="right", va="top")
    cm = to_m(np.array(cell["lonlat"]))
    M.tag(ax, (cm[:, 0].min(), cm[:, 1].min()), f"Fire reaches road {M.kst(block, True)}", dx=4, dy=8, ha="left",
          va="bottom")
    M.scale_bar(ax, km=0.2, where=(0.66, 0.9))
    M.attribution(ax)
    ky = TOP + mh + 0.36
    M.key_patch(fig, X0, ky, "fire area, 18:00", W, H, M.FIRE_TINT)
    M.key_line(fig, X0 + 3.75, ky, S.RED, 3.0, "road blocked", W, H)
    M.key_patch(fig, X0, ky + 0.5, "fire reaches cell later", W, H, S.PAPER, S.RED, hatch="////")
    M.key_line(fig, X0 + 3.75, ky + 0.5, S.INK, 2.2, "rest of the route", W, H)
    G.text_in(fig, X0, ky + 1.02, f"Leave by = earlier of {M.kst(far - drive, True)} and {M.kst(fire_limit, True)}")
    L.add("Leave by (earlier of the two limits)", leave, unit="s after 18:00 KST", file=M.DATA,
          field="min(far - drive, ceil(block - clear) - 1)", shown=M.kst(leave, True),
          expected=f"equals tail_node_ld_s {s['tail_node_ld_s']} and route_ld_s {d['route_ld_s']} (checked)")
    L.save()
    M.back_labels(fig)
    G.save(fig, "F08_map")


if __name__ == "__main__":
    main()
