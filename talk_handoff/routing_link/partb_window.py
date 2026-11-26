"""PROTOCOL_v3 Amendment 1 item 5: the routing window for the chosen fire, written when the full grid is infeasible.

Window = bounding box of the 2 km buffered 6 h footprint (partb_roads.py) plus 10 km on every side, snapped outward
to the fire grid's cell lines and clipped to the grid. Writes partb/window/<event>_grid.json in the grid.json format,
with the window's row/column offset in the full grid. Run from this folder: python3 partb_window.py EVENT
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

import partb_roads as R

HERE = Path(__file__).resolve().parent
MARGIN_M = 10_000.0


def window(ev):
    g = json.loads((R.REGIONS / ev / "grid.json").read_text())
    a, _, x0, _, e, ytop = g["transform"][:6]
    res = float(a)
    poly = R.footprint_polygon(np.load(HERE / "partb" / "select" / ("%s.npz" % ev))).buffer(R.BUFFER_M)
    bx0, by0, bx1, by1 = poly.bounds
    c0 = max(0, math.floor((bx0 - MARGIN_M - x0) / res))
    c1 = min(g["width"], math.ceil((bx1 + MARGIN_M - x0) / res))
    r0 = max(0, math.floor((ytop - (by1 + MARGIN_M)) / res))
    r1 = min(g["height"], math.ceil((ytop - (by0 - MARGIN_M)) / res))
    w = {"transform": [res, 0.0, x0 + c0 * res, 0.0, float(e), ytop - r0 * res],
         "width": c1 - c0, "height": r1 - r0, "epsg": g["epsg"], "offset_row": r0, "offset_col": c0,
         "full_grid": {"width": g["width"], "height": g["height"]},
         "rule": "PROTOCOL_v3 Amendment 1 item 5: buffered footprint bounds + 10 km, snapped outward to cells, clipped to the grid",
         "clipped_by_grid_edge": {"west": c0 == 0, "east": c1 == g["width"], "north": r0 == 0, "south": r1 == g["height"]}}
    out = HERE / "partb" / "window" / ("%s_grid.json" % ev)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(w, indent=1))
    return w


if __name__ == "__main__":
    print(json.dumps(window(sys.argv[1])))
