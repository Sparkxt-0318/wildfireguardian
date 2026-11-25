"""F07 on a real map: Uiseong-Andong, 25 March 2025, 18:00 KST, around Wondang-ri, on an OpenStreetMap basemap.

(a) Forward: one search from Wondang-ri leaving at 18:00:00, edge by edge in order of arrival, until it reaches a
    shelter; every road piece it settled is drawn grey, the route it found in ink. It answers one village for one
    departure time.
(b) Backward: one pass of the deadline field from every shelter of the region at once; every road with a safe
    departure is coloured by its leave-by time (four classes), and both villages outside the fire area get their
    leave-by time from the same pass.
Both panels draw the same fire area (router cells inside the known fire at 18:00) and the same roads blocked at
18:00 (edges whose blocked starts begin at 0 s), all from build/F07_map.json (F07_map_data.py).
"""
import os

import numpy as np
from matplotlib.collections import LineCollection

import labelcheck
import placenames as PN
import realmap as M
import style as S
from basemap import tiles_used
from figkit import add_caption, save
from prov import Ledger

W, H = S.W_IN, S.H_IN
BBOX = [128.650, 36.3265, 128.722, 36.3635]
Z = 15
CLASSES = [(0, 900, 1.0, "18:00–18:15"), (900, 1800, 0.72, "18:15–18:30"), (1800, 3600, 0.48, "18:30–19:00"),
           (3600, 8 * 3600 + 1, 0.28, "after 19:00")]
X0, MW, GAP = 0.35, 6.2, 0.23
TOP = 0.78


def in_view(lonlat):
    return BBOX[0] <= lonlat[0] <= BBOX[2] and BBOX[1] <= lonlat[1] <= BBOX[3]


def main():
    L = Ledger("F07m", "Forward against backward on the real map: 원당리 (Wondang-ri), 18:00 KST")
    d = M.load()
    fw, bw = d["forward"], d["backward"]
    shelter_id = PN.by_entry_node(fw["shelter_node"])
    L.add("Forward search from Wondang-ri leaving 18:00: road edges settled / looked at",
          [fw["edges_settled"], fw["edges_looked_at"]], file=M.DATA, field="forward.edges_settled, edges_looked_at",
          shown=f"{fw['edges_settled']} road pieces searched",
          note="Time-dependent search in order of arrival, turn restrictions and blocked edge starts of the replay "
               "instance, no waiting; stops at the first accepted arrival at a shelter (F07_map_data.py). It is the "
               "repository's illustration of one forward search, not the earlier method's code.")
    L.add("Forward search: arrival at the first shelter", fw["arrival_s"], unit="s after 18:00 KST", file=M.DATA,
          field="forward.arrival_s", shown=f"shelter reached {M.kst(fw['arrival_s'])}",
          expected="leaving at 18:00:00 lies in Wondang-ri's departure set of the field (checked)")
    L.add("Backward: passes / shelter nodes accepting", [bw["passes"], bw["shelter_nodes"]], file=M.DATA,
          field="backward.passes, shelter_nodes", shown="one pass from every shelter",
          note="deadline_field.core.backward with every shelter used by any village of the region accepting at once; "
               f"fixed-point check {bw['fixed_point']} on {bw['states_checked']:,} edge states.")
    L.add("Backward: road junctions with a safe departure / all junctions", [bw["nodes_with_departure"], bw["nodes"]],
          file=M.DATA, field="backward.nodes_with_departure, nodes", shown="coloured roads (SOURCES only for counts)")
    vill = [v for v in d["villages"] if in_view(v["entry_lonlat"])]
    dep = [v for v in vill if v["ld_one_pass_s"] >= 0]
    for v in dep:
        L.add(f"Leave-by time of {v['name_en']} from the one pass", v["ld_one_pass_s"], unit="s after 18:00 KST",
              file=M.DATA, field="villages[].ld_one_pass_s", shown=f"{PN.ko(v['id'])}: leave by {M.kst(v['ld_one_pass_s'])}",
              expected=f"stored replay (scene.js hourly lsd, 3 nearest shelters): {v['lsd_stored']} (checked)")
    L.add("Villages in view: with a leave-by time / inside the fire area",
          [len(dep), sum(v["state"] == "INSIDE_KNOWN_FIRE_AREA" for v in vill)], file=M.DATA,
          field="villages[] with entry inside the map, by state", shown="village markers")
    L.add("Router cells inside the known fire area at 18:00 (drawn)", sum(c["block_s"] == 0 for c in d["cells"]),
          file=M.DATA, field="cells[].block_s == 0 (375 m cells, MEASURED arm)", shown="red area")
    L.add("Road edges blocked at 18:00 (whole region)", len(d["blocked_at_issue_pairs"]), file=M.DATA,
          field="blocked_at_issue_pairs (edges whose blocked starts begin at 0 s)", shown="red roads")
    PN.ledger_rows(L, [fw["origin"], shelter_id] + [v["id"] for v in dep if v["id"] != fw["origin"]])
    L.add("Basemap tiles", tiles_used(Z, BBOX), file="talk/figures/build/osm_tiles/TILES.json",
          field=f"OpenStreetMap standard tiles, zoom {Z}", shown=M.ATTRIBUTION)

    fig = S.plt.figure(figsize=(W, H), dpi=S.DPI)
    mh = None
    axs = []
    for i in range(2):
        x = X0 + i * (MW + GAP)
        ax = fig.add_axes([x / W, 0, MW / W, 0.5])
        M.setup(ax, BBOX, Z)
        fig.canvas.draw()
        # height from the equal-aspect box
        xl, yl = ax.get_xlim(), ax.get_ylim()
        mh = MW * (yl[1] - yl[0]) / (xl[1] - xl[0])
        ax.set_position([x / W, 1 - (TOP + mh) / H, MW / W, mh / H])
        M.fire(ax, d)
        M.blocked(ax, d)
        axs.append(ax)
    fig.text(X0 / W, 1 - (TOP - 0.28) / H, "(a) Forward: one village, one start time", va="center")
    fig.text((X0 + MW + GAP) / W, 1 - (TOP - 0.28) / H, "(b) Backward: one pass, every village", va="center")

    # (a) forward search
    ax = axs[0]
    lc = LineCollection(M.segs(d, d["forward_settled_pairs"]), colors=S.GREY, linewidths=2.0, zorder=4,
                        capstyle="round")
    lc.set_gid("bg:forward search")
    ax.add_collection(lc)
    M.line(ax, fw["route_lonlat"], S.INK, 2.6, 6, gid="bg:forward route")
    wd = [v for v in vill if v["id"] == fw["origin"]][0]
    sm = M.point(ax, fw["route_lonlat"][-1], "shelter")[0]
    om = M.point(ax, wd["entry_lonlat"], "village")[0]
    M.tag(ax, om, f"{PN.ko(fw['origin'])},\nleaves 18:00", dx=-8, dy=10, ha="right", va="bottom")
    M.tag(ax, sm, f"{PN.ko(shelter_id)},\nreached {M.kst(fw['arrival_s'])}", dx=-8, dy=12, ha="right", va="bottom")
    M.scale_bar(ax)
    # (b) backward pass
    ax = axs[1]
    ld = np.array(d["node_ld_s"], dtype=float)
    pairs = np.array(d["edge_pairs"])
    a, b = ld[pairs[:, 0]], ld[pairs[:, 1]]
    ok = (a >= 0) & (b >= 0)
    lo = np.minimum(a, b)
    allsegs = M.segs(d, pairs)
    for c0, c1, f, txt in CLASSES[::-1]:
        sel = ok & (lo >= c0) & (lo < c1)
        lc = LineCollection(allsegs[sel], colors=S.tint(S.BLUE, f), linewidths=2.4, zorder=4, capstyle="round")
        lc.set_gid(f"bg:leave by {txt}")
        ax.add_collection(lc)
    sh = [s for s in d["shelters_lonlat"] if in_view(s)]
    for s in sh:
        M.point(ax, s, "shelter")
    for v in vill:
        if v["ld_one_pass_s"] >= 0:
            m = M.point(ax, v["entry_lonlat"], "village")[0]
            low = v["entry_lonlat"][1] < 36.34
            M.tag(ax, m, f"{PN.ko(v['id'])}: leave by {M.kst(v['ld_one_pass_s'])}", dx=8, dy=-16 if low else 14,
                  ha="left", va="top" if low else "bottom")
        else:
            M.point(ax, v["entry_lonlat"], "inside")
    for s in [s for s in d["shelters_lonlat"] if in_view(s)]:
        M.point(axs[0], s, "shelter", size=70, z=7)
    for v in vill:
        if v["id"] != fw["origin"]:
            M.point(axs[0], v["entry_lonlat"], "village" if v["ld_one_pass_s"] >= 0 else "inside", size=70, z=7)

    # keys under the maps
    ky = TOP + mh + 0.4
    xa = X0
    M.key_patch(fig, xa, ky, "fire area, 18:00", W, H, M.FIRE_TINT)
    M.key_line(fig, xa + 2.55, ky, S.RED, 2.0, "road blocked at 18:00", W, H)
    M.key_line(fig, xa, ky + 0.42, S.GREY, 2.0, f"searched: {fw['edges_settled']} road pieces", W, H)
    M.key_line(fig, xa + 3.55, ky + 0.42, S.INK, 2.6, "route found", W, H)
    M.key_patch(fig, xa, ky + 0.84, "shelter", W, H, S.PAPER, S.INK, marker="s", w_in=0.3)
    M.key_patch(fig, xa + 1.35, ky + 0.84, "village", W, H, S.INK, S.PAPER, marker="o", w_in=0.3)
    xb = X0 + MW + GAP
    fig.text(xb / W, 1 - ky / H, "leave by", va="center")
    for i, (c0, c1, f, txt) in enumerate(CLASSES):
        col, row = i % 2, i // 2
        M.key_line(fig, xb + 1.0 + col * 2.35, ky + row * 0.42, S.tint(S.BLUE, f), 3.0, txt, W, H, w_in=0.4)
    M.key_patch(fig, xa + 2.65, ky + 0.84, "village inside fire area", W, H, S.PAPER, S.INK, marker="o", w_in=0.3)
    M.attribution(axs[1])

    v_dep = sorted(dep, key=lambda v: v["ld_one_pass_s"])
    cap = add_caption(fig, (
        f"Figure 7 (map). {PN.region_ko()}, 18:00 KST, 25 March 2025. (a) Leaving {PN.ko(fw['origin'])} at 18:00, a "
        f"forward search settles {fw['edges_settled']} road pieces before reaching a shelter at "
        f"{M.kst(fw['arrival_s'], True)}: "
        "one village, one departure time. (b) One backward pass from every shelter gives every road its leave-by "
        f"time, including both villages outside the fire area ({PN.ko(v_dep[0]['id'])} "
        f"{M.kst(v_dep[0]['ld_one_pass_s'])}, {PN.ko(v_dep[1]['id'])} {M.kst(v_dep[1]['ld_one_pass_s'])})."
        ), x_in=0.35, width_in=12.6, top_in=ky + 1.12)
    L.save()
    M.back_labels(fig)
    strict = not os.environ.get("DRAFT")
    labelcheck.run(fig, "F07_map", strict)
    save(fig, "F07_map", caption=cap, transparent=True, strict=strict)
    labelcheck.verify_files("F07_map")
    PN.record_missing("F07_map")


if __name__ == "__main__":
    main()
