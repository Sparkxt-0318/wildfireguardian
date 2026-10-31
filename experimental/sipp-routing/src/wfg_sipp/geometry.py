"""Exact frozen geometry functions copied with source hash in SOURCE_SHA256.json."""
import math
from fractions import Fraction

def node_cell(graph, node):
    g = graph["grid"]
    col = math.floor(
        (Fraction(node["x"]) - Fraction(g["x0"])) / Fraction(g["resolution"])
    )
    row = math.floor(
        (Fraction(node["y"]) - Fraction(g["y0"])) / Fraction(g["resolution"])
    )
    return row * g["width"] + col


def edge_occupancies(
    edge, start, end, from_fraction=0, to_fraction=1, graph=None, node_lookup=None
):
    """Exact rational chord/grid intersections, including every point contact.

    JSON segment fractions are canonical floating encodings for admission only;
    geometry is recomputed from represented coordinates to avoid cut rounding.
    """
    if graph is None:
        raise ValueError("graph required for exact geometry occupancy")
    ns = node_lookup or {n["id"]: n for n in graph["nodes"]}
    u, v = ns[edge["u"]], ns[edge["v"]]
    g = graph["grid"]
    f, q = Fraction(from_fraction), Fraction(to_fraction)
    cuts = {f, q}
    for axis, base, count in [("x", "x0", "width"), ("y", "y0", "height")]:
        a, b = Fraction(u[axis]), Fraction(v[axis])
        origin = Fraction(g[base])
        res = Fraction(g["resolution"])
        if a != b:
            for line in range(1, g[count]):
                c = (origin + line * res - a) / (b - a)
                if f < c < q:
                    cuts.add(c)
    cuts = sorted(cuts)

    def point(z):
        return {
            "x": Fraction(u["x"]) + z * (Fraction(v["x"]) - Fraction(u["x"])),
            "y": Fraction(u["y"]) + z * (Fraction(v["y"]) - Fraction(u["y"])),
        }

    def when(z):
        return (
            Fraction(start)
            if q == f
            else Fraction(start) + (Fraction(end) - Fraction(start)) * (z - f) / (q - f)
        )

    out = []
    for a, b in zip(cuts, cuts[1:]):
        out.append(
            {
                "cell": node_cell(graph, point((a + b) / 2)),
                "start": when(a),
                "end": when(b),
            }
        )
    for z in cuts:
        out.append(
            {"cell": node_cell(graph, point(z)), "start": when(z), "end": when(z)}
        )
    return out

