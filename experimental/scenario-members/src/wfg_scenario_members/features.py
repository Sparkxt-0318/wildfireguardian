"""Road features under the copied contact checker's exact chord occupancy law.

The feature is the earliest *integer departure* in [departure, horizon-D]
whose full directed traversal intersects activity [b,e). A represented unit
occupancy [za,zb] blocks ceil(b-D*zb) through ceil(e-D*za)-1, including point
contacts. Never unsafe is +inf, capped to horizon for reduction; unknown is NaN.
This is a contact distance feature, not a radiation or whole-policy certificate.
"""
from fractions import Fraction as F
import math
import numpy as np
from pyproj import CRS
from wfg_sipp.geometry import edge_occupancies


def road_arrival_features(graph, model, *, departure=0, horizon=3600, unknown_native=None):
    """Return raw/capped [member,edge] seconds and metre chord weights.

    Native arrays are north-up, graph rows south-up. Unknown emitting cells
    outside the road do not affect this contact-only feature. A globally
    unsupported model without a supplied spatial mask is wholly unknown.
    """
    if any(isinstance(x, bool) or not isinstance(x, int) for x in (departure, horizon)) or not 0 <= departure < horizon:
        raise ValueError("Integer nonnegative departure < horizon required")
    crs = CRS.from_user_input(graph["crs"])
    if not crs.is_projected or any(a.unit_conversion_factor != 1 for a in crs.axis_info[:2]):
        raise ValueError("Projected metre coordinates required")
    g = graph["grid"]
    H, W = model.shape
    if (g["height"], g["width"]) != (H, W) or not math.isfinite(float(g["resolution"])) or g["resolution"] <= 0:
        raise ValueError("Grid shape/resolution mismatch")
    nodes = {n["id"]: n for n in graph["nodes"]}
    if len(nodes) != len(graph["nodes"]):
        raise ValueError("Duplicate node identity")
    for n in nodes.values():
        for axis, origin, count in (("x", "x0", W), ("y", "y0", H)):
            z = (F(n[axis]) - F(g[origin])) / F(g["resolution"])
            if not 0 <= z < count:
                raise ValueError("Outside/nonfinite graph coordinate")
    N = len(model.ids)
    if unknown_native is None:
        unknown = np.full((N, H, W), getattr(model, "supported", True) is not True, dtype=bool)
    else:
        unknown = np.asarray(unknown_native)
        if unknown.dtype != np.bool_ or unknown.shape not in ((H, W), (N, H, W)):
            raise ValueError("Boolean native unknown mask shape required")
        unknown = np.broadcast_to(unknown, (N, H, W))
    edges = graph["edges"]
    if len({e["id"] for e in edges}) != len(edges):
        raise ValueError("Duplicate edge identity")
    raw = np.full((N, len(edges)), np.inf)
    lengths = []
    for j, edge in enumerate(edges):
        D = edge["travel_ticks"]
        if isinstance(D, bool) or not isinstance(D, int) or not 0 < D <= horizon-departure:
            raise ValueError("Positive integer travel seconds within horizon required")
        u, v = nodes[edge["u"]], nodes[edge["v"]]
        lengths.append(math.hypot(float(v["x"])-float(u["x"]), float(v["y"])-float(u["y"])))
        occ = edge_occupancies(edge, 0, 1, graph=graph, node_lookup=nodes)
        for s in range(N):
            cells = model.member_cell_intervals(s)
            for o in occ:
                c = o["cell"]
                if unknown[s].ravel()[model.native_index(c)]:
                    raw[s, j] = np.nan
                    break
                for b, e in cells.get(c, ()):
                    lo = max(departure, math.ceil(b-D*o["end"]))
                    hi = min(horizon-D, math.ceil(e-D*o["start"])-1)
                    if lo <= hi:
                        raw[s, j] = min(raw[s, j], lo)
    return {"first_unsafe_departure_s": raw, "capped_arrival_s": np.minimum(raw, horizon),
            "known": ~np.isnan(raw), "edge_ids": [e["id"] for e in edges],
            "member_ids": list(model.ids), "edge_lengths_m": np.asarray(lengths),
            "departure_s": departure, "horizon_s": horizon,
            "definition": "first unsafe integer departure for full traversal, copied contact occupancy",
            "cap": "never or after domain -> horizon; unknown -> NaN"}
