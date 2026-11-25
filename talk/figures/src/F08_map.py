"""F08 on a real map: one backward step on one real road of Wondang-ri's route, 18:00 KST, 25 March 2025.

The road is the first edge of the stored route (OSM way 672449436, 315 m, leaving Wondang-ri), the edge whose fire
blocking sets the village's leave-by time (build/F07_map.json f08_step, F07_map_data.py). Beside it, its four times:
  * safe arrival at the far end: the latest second at which arriving there over this road still reaches a shelter
    (the deadline field's G of the edge);
  * drive time: the edge's travel ticks (seconds);
  * when fire reaches the road: the blocking second of the router cell the road starts in (MEASURED arm), and how long
    the car needs to clear that cell;
  * leave by = the earlier of (arrival limit - drive time) and the last whole second from which the car clears the
    burning cell before it is blocked. It must equal the village's leave-by time from the field; checked.
"""
import math
import os

import numpy as np
from matplotlib.patches import Polygon

import labelcheck
import placenames as PN
import realmap as M
import style as S
from basemap import tiles_used, to_m
from figkit import add_caption, save
from prov import Ledger

W, H = S.W_IN, S.H_IN
BBOX = [128.6650, 36.3388, 128.6800, 36.3460]
Z = 17
X0, MW, TOP = 0.35, 6.7, 0.6


def main():
    L = Ledger("F08m", "One backward step on a real road: 원당리 (Wondang-ri), 18:00 KST")
    d = M.load()
    vid = d["forward"]["origin"]          # F07_map_data.PLACE: the stored route and the forward search share it
    vname = PN.ko(vid)
    s = d["f08_step"]
    far, drive, block = s["latest_arrival_far_end_s"], s["drive_s"], s["fire_cell"]["block_s"]
    clear = drive * s["fire_cell"]["end_fraction"]
    fire_limit = math.ceil(block - clear) - 1
    leave = min(far - drive, fire_limit)
    assert leave == s["latest_departure_via_edge_s"] == s["tail_node_ld_s"] == d["route_ld_s"], (leave, s)
    F = M.DATA
    L.add("Road: OSM way, edge, length", [s["way"], s["edge"], s["length_m"]], unit="m", file=F,
          field="f08_step.way, edge, length_m", shown=f"{s['length_m']:.0f} m",
          note="The first edge of Wondang-ri's stored route (scene.js routes.MEASURED, 18:00 KST); the first route "
               "edge whose fire blocking, not its arrival limit, sets the time.")
    L.add("Safe arrival at the far end (latest)", far, unit="s after 18:00 KST", file=F,
          field="f08_step.latest_arrival_far_end_s (max of the field's G for this edge)",
          shown=f"by {M.kst(far, True)}")
    L.add("Drive time", drive, unit="s", file=F, field="f08_step.drive_s (travel_ticks)", shown=f"{drive} s")
    L.add("Fire blocks the road's first cell", block, unit="s after 18:00 KST", file=F,
          field="f08_step.fire_cell.block_s (router cell 175, MEASURED arm)", shown=M.kst(block, True))
    L.add("Car clears that cell after", round(clear, 3), unit="s", file=F,
          field="drive_s * fire_cell.end_fraction", shown=f"{clear:.0f} s")
    L.add("Leave by (earlier of the two limits)", leave, unit="s after 18:00 KST", file=F,
          field="min(far - drive, ceil(block - clear) - 1)", shown=M.kst(leave, True),
          expected=f"field leave-by at the near end {s['tail_node_ld_s']} s; stored route ld {d['route_ld_s']} s "
                   "(checked equal)")
    PN.ledger_rows(L, [vid], region=False)
    L.add("Basemap tiles", tiles_used(Z, BBOX), file="talk/figures/build/osm_tiles/TILES.json",
          field=f"OpenStreetMap standard tiles, zoom {Z}", shown=M.ATTRIBUTION)

    fig = S.plt.figure(figsize=(W, H), dpi=S.DPI)
    ax = fig.add_axes([X0 / W, 0, MW / W, 0.5])
    M.setup(ax, BBOX, Z, fade=0.5)
    fig.canvas.draw()
    xl, yl = ax.get_xlim(), ax.get_ylim()
    mh = MW * (yl[1] - yl[0]) / (xl[1] - xl[0])
    ax.set_position([X0 / W, 1 - (TOP + mh) / H, MW / W, mh / H])
    M.fire(ax, d)
    M.blocked(ax, d, lw=2.4)
    cell = [c for c in d["cells"] if c["cell"] == s["fire_cell"]["cell"]][0]
    pg = Polygon(to_m(np.array(cell["lonlat"])), closed=True, facecolor="none", edgecolor=S.RED, hatch="////",
                 linewidth=1.6, zorder=2)
    pg.set_gid("bg:fire cell")
    ax.add_patch(pg)
    M.line(ax, d["route_lonlat"], S.INK, 1.6, 4, halo=False, gid="bg:rest of route")
    rm = M.line(ax, s["lonlat"], S.BLUE, 5.0, 6, gid="bg:the road")
    M.point(ax, s["lonlat"][0], "village", size=130, z=8)
    fm = to_m(np.array(s["lonlat"][1]))
    ax.scatter([fm[0]], [fm[1]], s=90, marker="o", facecolor=S.PAPER, edgecolor=S.BLUE, linewidths=2.2,
               zorder=8).set_gid("bg:far end")
    M.tag(ax, rm[0], f"{vname}: leave by {M.kst(leave, True)}", dx=0, dy=12, ha="center", va="bottom")
    M.tag(ax, fm, f"Safe arrival here\nby {M.kst(far, True)}", dx=10, dy=8, ha="left", va="bottom")
    mid = rm.mean(0)
    M.tag(ax, mid, f"Drive {drive} s, {s['length_m']:.0f} m", dx=-6, dy=-14, ha="right", va="top")
    cm = to_m(np.array(cell["lonlat"]))
    M.tag(ax, (cm[:, 0].min(), cm[:, 1].min()), f"Fire reaches road {M.kst(block, True)}", dx=4, dy=8, ha="left",
          va="bottom")
    M.scale_bar(ax, km=0.2, where=(0.70, 0.92))
    M.attribution(ax)

    # the backward step, written out
    x = X0 + MW + 0.4
    y = TOP + 0.3
    fig.text(x / W, 1 - y / H, "One backward step on this road", va="center")
    rows = [
        (f"Far end: {M.kst(far, True)} − {drive} s = {M.kst(far - drive, True)}", S.INK),
        (f"Fire: clear the cell before {M.kst(block, True)}", S.INK),
        (f"car clears it {clear:.0f} s after leaving", S.INK),
        (f"so latest start {M.kst(fire_limit, True)}", S.INK),
        (f"Leave by: earlier = {M.kst(leave, True)}", S.BLUE),
    ]
    yy = y + 0.75
    for i, (txt, col) in enumerate(rows):
        indent = 0.3 if i in (2, 3) else 0.0
        fig.text((x + indent) / W, 1 - yy / H, txt, va="center", color=col)
        yy += 0.42 if i in (1, 2) else 0.62
    ky = TOP + mh + 0.4
    M.key_patch(fig, X0, ky, "fire area, 18:00", W, H, M.FIRE_TINT)
    M.key_line(fig, X0 + 3.4, ky, S.RED, 2.4, "road blocked at 18:00", W, H)
    M.key_patch(fig, X0, ky + 0.42, "fire reaches cell later", W, H, S.PAPER, S.RED, hatch="////")
    M.key_line(fig, X0 + 3.4, ky + 0.42, S.INK, 1.6, "rest of the route", W, H)
    cap = add_caption(fig, (
        f"Figure 8 (map). One backward step on the first road of the route from {vname} ({s['length_m']:.0f} m), 18:00 KST, "
        f"25 March 2025. Arriving at the far end by {M.kst(far, True)} still reaches a shelter; the drive takes "
        f"{drive} s; fire reaches the start of the road at {M.kst(block, True)}. The leave-by time is the earlier "
        f"limit, {M.kst(leave, True)}, set by the fire; it equals the village's leave-by time from the field."),
        x_in=X0, width_in=12.6, top_in=ky + 0.92)
    L.save()
    M.back_labels(fig)
    strict = not os.environ.get("DRAFT")
    labelcheck.run(fig, "F08_map", strict)
    save(fig, "F08_map", caption=cap, transparent=True, strict=strict)
    labelcheck.verify_files("F08_map")
    PN.record_missing("F08_map")


if __name__ == "__main__":
    main()
