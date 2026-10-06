"""Strict JSON admission for the declared road/grid thermal adapter. No forecast conversion."""

from copy import deepcopy
from datetime import datetime, timedelta
import math
from fractions import Fraction


class ValidationError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def fail(code, message):
    raise ValidationError(code, message)


def number(x, name, minimum=None):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        fail("MALFORMED_NUMBER", name + " must be finite numeric")
    if minimum is not None and x < minimum:
        fail("NEGATIVE_QUANTITY", name + " below declared minimum")
    return float(x)


def integer(x, name, minimum=0):
    if isinstance(x, bool) or not isinstance(x, int) or x < minimum:
        fail("MALFORMED_INTEGER", name + " must be integer")
    return x


def obj(x, name):
    if not isinstance(x, dict):
        fail("MALFORMED_OBJECT", name + " must be object")
    return x


def seq(x, name, nonempty=False):
    if not isinstance(x, list) or (nonempty and not x):
        fail("MALFORMED_ARRAY", name + " must be list")
    return x


def text(x, name):
    if not isinstance(x, str) or not x.strip():
        fail("MISSING_FIELD", name + " must be nonempty text")
    return x


def boolean(x, name):
    if not isinstance(x, bool):
        fail("MALFORMED_BOOLEAN", name + " must be Boolean")
    return x


def timestamp(x, name):
    try:
        t = datetime.fromisoformat(text(x, name).replace("Z", "+00:00"))
        if t.tzinfo is None:
            fail("NAIVE_TIME", name + " requires timezone")
        return t
    except (TypeError, ValueError) as ex:
        if isinstance(ex, ValidationError):
            raise
        fail("MALFORMED_TIME", name + " requires ISO8601")


def grid_spec(grid):
    g = obj(grid, "grid")
    for k in ("x0", "y0"):
        number(g.get(k), "grid." + k)
    number(g.get("resolution"), "grid.resolution", 0)
    if g["resolution"] <= 0:
        fail("GRID_RESOLUTION", "positive resolution required")
    for k in ("width", "height"):
        integer(g.get(k), "grid." + k, 1)
    return g


def cell_at(grid, x, y):
    col = math.floor(
        (Fraction(x) - Fraction(grid["x0"])) / Fraction(grid["resolution"])
    )
    row = math.floor(
        (Fraction(y) - Fraction(grid["y0"])) / Fraction(grid["resolution"])
    )
    if not (0 <= col < grid["width"] and 0 <= row < grid["height"]):
        fail("SPATIAL_COVERAGE", "road coordinate outside grid")
    return row * grid["width"] + col


def chord_segments(grid, u, v):
    """Exact grid-line cuts of declared straight road chord (up to numeric tolerance)."""
    cuts = {Fraction(0), Fraction(1)}
    r = Fraction(grid["resolution"])
    for axis, base, extent in [
        ("x", grid["x0"], grid["width"]),
        ("y", grid["y0"], grid["height"]),
    ]:
        a, b = Fraction(u[axis]), Fraction(v[axis])
        base = Fraction(base)
        if a == b:
            continue
        for line in range(1, extent):
            z = (base + line * r - a) / (b - a)
            if 0 < z < 1:
                cuts.add(z)
    cuts = sorted(cuts)
    out = []
    for a, b in zip(cuts, cuts[1:]):
        m = (a + b) / 2
        c = cell_at(
            grid,
            Fraction(u["x"]) + (Fraction(v["x"]) - Fraction(u["x"])) * m,
            Fraction(u["y"]) + (Fraction(v["y"]) - Fraction(u["y"])) * m,
        )
        if out and out[-1]["cell"] == c:
            out[-1]["end"] = float(b)
        else:
            out.append({"cell": c, "start": float(a), "end": float(b)})
    return out


def _validate_graph(graph):
    g = obj(graph, "graph")
    text(g.get("revision"), "graph.revision")
    # Bounded supported projected CRSs; arbitrary/custom geographic CRS cannot pass as metres.
    if g.get("crs") not in {
        "EPSG:5179",
        "EPSG:5186",
        "EPSG:32651",
        "EPSG:32652",
        "EPSG:3857",
    }:
        fail("UNSUPPORTED_CRS", "adapter requires a supported projected metre CRS")
    grid = grid_spec(g.get("grid"))
    nodes = {}
    edges = {}
    for n in seq(g.get("nodes"), "nodes", True):
        obj(n, "node")
        nid = text(n.get("id"), "node.id")
        if nid in nodes:
            fail("DUPLICATE_NODE", "duplicate node id")
        for k in ("x", "y"):
            number(n.get(k), "node." + k)
        cell_at(grid, n["x"], n["y"])
        boolean(n.get("waitable"), "node.waitable")
        nodes[nid] = n
    for e in seq(g.get("edges"), "edges"):
        obj(e, "edge")
        eid = text(e.get("id"), "edge.id")
        if eid in edges:
            fail("DUPLICATE_EDGE", "duplicate edge id")
        if e.get("u") not in nodes or e.get("v") not in nodes:
            fail("UNKNOWN_NODE", "edge endpoint missing")
        integer(e.get("travel_ticks"), "edge.travel_ticks", 1)
        if e["travel_ticks"] > 2**53:
            fail(
                "UNSUPPORTED_TRAVEL_MAGNITUDE",
                "travel_ticks exceeds represented schedule envelope",
            )
        parts = seq(e.get("segments"), "edge.segments", True)
        expected = chord_segments(grid, nodes[e["u"]], nodes[e["v"]])
        if len(parts) != len(expected):
            fail("ROAD_ALIGNMENT", "cell intersections do not cover declared chord")
        for s, want in zip(parts, expected):
            obj(s, "segment")
            integer(s.get("cell"), "segment.cell")
            a = number(s.get("start"), "segment.start", 0)
            b = number(s.get("end"), "segment.end", 0)
            if (
                b <= a
                or b > 1
                or s["cell"] != want["cell"]
                or a != want["start"]
                or b != want["end"]
            ):
                fail("ROAD_ALIGNMENT", "segment mismatch or discontinuity")
        edges[eid] = e
    for e in edges.values():
        if e.get("reverse_edge") is not None:
            r = edges.get(e["reverse_edge"])
            if (
                not r
                or (r["u"], r["v"]) != (e["v"], e["u"])
                or r.get("reverse_edge") != e["id"]
            ):
                fail(
                    "REVERSE_GEOMETRY",
                    "reverse_edge must be explicit mutual reversed chord",
                )
    turns = seq(g.get("forbidden_turns"), "forbidden_turns")
    for pair in turns:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or any(e not in edges for e in pair)
        ):
            fail("TURN_RULE", "unknown turn edges")
        if edges[pair[0]]["v"] != edges[pair[1]]["u"]:
            fail("TURN_RULE", "turn edges do not meet")
    boolean(g.get("mid_edge_reversal"), "mid_edge_reversal")
    return deepcopy(g)


def validate_graph(graph):
    try:
        return _validate_graph(graph)
    except (KeyError, TypeError, OverflowError) as ex:
        fail("MALFORMED_GRAPH", str(ex))


def _validate_hazard(graph, hazard, as_of=None, _graph_validated=False):
    g = graph if _graph_validated else validate_graph(graph)
    h = obj(hazard, "hazard")
    if h.get("schema") != "wfg.routing.edgegrid/1":
        fail("UNSUPPORTED_SCHEMA", "schema unsupported")
    integer(h.get("version"), "version", 1)
    if h.get("graph_revision") != g["revision"]:
        fail("GRAPH_REVISION", "graph revision mismatch")
    if h.get("crs") != g["crs"] or h.get("grid") != g["grid"]:
        fail("GRID_ALIGNMENT", "CRS/grid mismatch")
    if h.get("channels") != ["flame_contact", "incident_heat_flux"]:
        fail(
            "UNSUPPORTED_QUANTITY",
            "flame + incident heat flux required; no silent conversions",
        )
    if h.get("units", {"time": "s", "flux": "kW/m2", "dose": "kJ/m2"}) != {
        "time": "s",
        "flux": "kW/m2",
        "dose": "kJ/m2",
    }:
        fail("UNSUPPORTED_UNITS", "schema units mismatch")
    unsupported = seq(h.get("unsupported_channels"), "unsupported_channels")
    if any(not isinstance(x, str) for x in unsupported):
        fail("MALFORMED_CHANNEL", "unsupported_channels text required")
    if h.get("evidence_class") not in ["LABELLED_FIXTURE", "MENTOR_FORECAST"]:
        fail("EVIDENCE_CLASS", "explicit fixture/mentor evidence required")
    provenance = obj(h.get("provenance"), "provenance")
    text(provenance.get("source"), "provenance.source")
    text(provenance.get("interpretation"), "provenance.interpretation")
    origin = timestamp(h.get("time_origin"), "time_origin")
    issue = timestamp(h.get("issued_at"), "issued_at")
    avail = timestamp(h.get("available_at"), "available_at")
    if avail < issue:
        fail("CAUSAL_TIME", "availability predates issue")
    if as_of is not None and avail > timestamp(as_of, "as_of"):
        fail("NOT_AVAILABLE", "forecast not yet available")
    start = number(h.get("valid_from"), "valid_from")
    end = number(h.get("valid_until"), "valid_until")
    if end <= start:
        fail("TEMPORAL_COVERAGE", "validity must have positive duration")
    dt = number(h.get("dt"), "dt", 0)
    if dt <= 0:
        fail("LATTICE", "positive dt required")
    if as_of is not None and timestamp(as_of, "as_of") > origin + timedelta(
        seconds=end
    ):
        fail("STALE_PAYLOAD", "validity ended before as_of")
    ids = set()
    cells = g["grid"]["width"] * g["grid"]["height"]
    for m in seq(h.get("members"), "members", True):
        obj(m, "member")
        mid = text(m.get("id"), "member.id")
        if mid in ids:
            fail("DUPLICATE_MEMBER", "duplicate member identity")
        ids.add(mid)
        bp = seq(m.get("breakpoints"), "breakpoints", True)
        if len(bp) < 2:
            fail("BREAKPOINTS", "at least two breakpoints")
        for b in bp:
            number(b, "breakpoint")
        if (
            any(b <= a for a, b in zip(bp, bp[1:]))
            or abs(bp[0] - start) > 1e-9
            or abs(bp[-1] - end) > 1e-9
        ):
            fail("BREAKPOINTS", "strict increasing breakpoints must cover validity")
        for channel in ["flux", "flame", "support"]:
            rows = seq(m.get(channel), channel)
            if len(rows) != len(bp) - 1:
                fail("ARRAY_SHAPE", channel + " interval dimension mismatch")
            for row in rows:
                if not isinstance(row, list) or len(row) != cells:
                    fail("ARRAY_SHAPE", channel + " cell dimension mismatch")
                for value in row:
                    if channel == "flux":
                        number(value, "flux", 0)
                    else:
                        boolean(value, channel)
    return deepcopy(h)


def validate_hazard(graph, hazard, as_of=None, *, _graph_validated=False):
    try:
        return _validate_hazard(graph, hazard, as_of, _graph_validated)
    except (KeyError, TypeError, OverflowError) as ex:
        fail("MALFORMED_HAZARD", str(ex))


def _validate_request(graph, hazard, request, _validated_inputs=False):
    g = graph if _validated_inputs else validate_graph(graph)
    h = (
        hazard
        if _validated_inputs
        else validate_hazard(g, hazard, _graph_validated=True)
    )
    q = obj(request, "request")
    integer(q.get("hazard_version"), "hazard_version", 1)
    if q.get("hazard_version") != h["version"]:
        fail("HAZARD_VERSION", "request forecast version mismatch")
    asof = timestamp(q.get("as_of"), "as_of")
    origin = timestamp(h["time_origin"], "time_origin")
    if timestamp(h["available_at"], "available_at") > asof:
        fail("NOT_AVAILABLE", "forecast unavailable at as_of")
    dep = number(q.get("departure"), "departure")
    hor = number(q.get("horizon"), "horizon")
    if asof > origin + timedelta(seconds=dep):
        fail("CAUSAL_TIME", "as_of later than departure")
    if hor < dep:
        fail("HORIZON", "horizon before departure")
    if dep < h["valid_from"] or hor > h["valid_until"]:
        fail("UNSUPPORTED_TIME", "request outside payload temporal coverage")

    def lattice(t, name):
        if (Fraction(t) / Fraction(h["dt"])).denominator != 1:
            fail(
                "UNSUPPORTED_LATTICE", name + " must exactly align with represented dt"
            )

    for t, n in [(dep, "departure"), (hor, "horizon")]:
        lattice(t, n)
    tick_bound = max(
        abs(int(Fraction(dep) / Fraction(h["dt"]))),
        abs(int(Fraction(hor) / Fraction(h["dt"]))),
    )
    if (abs(Fraction(h["dt"]).numerator) * tick_bound).bit_length() > 53:
        fail(
            "UNSUPPORTED_LATTICE",
            "time lattice arithmetic exceeds exact binary64 schedule envelope",
        )
    nodes = {n["id"]: n for n in g["nodes"]}
    edges = {e["id"]: e for e in g["edges"]}
    pos = obj(q.get("position"), "position")
    inc = q.get("incoming_edge")
    if set(pos) == {"node"}:
        if pos["node"] not in nodes:
            fail("UNKNOWN_NODE", "position node absent")
        if inc is not None and (inc not in edges or edges[inc]["v"] != pos["node"]):
            fail("TURN_CONTEXT", "incoming edge does not end at position")
    elif set(pos) == {"edge", "fraction"}:
        if pos["edge"] not in edges:
            fail("UNKNOWN_EDGE", "position edge absent")
        frac = number(pos["fraction"], "fraction", 0)
        if not 0 < frac <= 1:
            fail("POSITION", "directed fraction in (0,1]; use node at fraction0")
        if inc != pos["edge"]:
            fail("TURN_CONTEXT", "mid-edge incoming context must equal occupied edge")
        if (
            frac < 1
            and g["mid_edge_reversal"]
            and edges[pos["edge"]].get("reverse_edge")
            and Fraction(1 - frac) != Fraction(1) - Fraction(frac)
        ):
            fail(
                "UNSUPPORTED_REVERSE_FRACTION",
                "mirrored fraction must serialize exactly when reversal is permitted",
            )
    else:
        fail(
            "POSITION", "position must represent exactly node or directed edge fraction"
        )
    if q.get("objective") != "earliest_arrival":
        fail("UNSUPPORTED_OBJECTIVE", "only earliest arrival supported")
    if q.get("exposure_scope") not in ["route_only", "including_dwell"]:
        fail("EXPOSURE_SCOPE", "declare dose scope")
    ids = {m["id"] for m in h["members"]}
    spent = obj(q.get("incurred"), "incurred")
    bud = obj(q.get("budgets"), "budgets")
    dose = obj(bud.get("dose"), "dose")
    if set(spent) != ids or set(dose) != ids:
        fail(
            "UNSUPPORTED_MEMBER_MAPPING",
            "incurred and budgets require exact member identities",
        )
    for mid in ids:
        number(spent[mid], "incurred", 0)
        number(dose[mid], "dose budget", 0)
    number(bud.get("peak"), "peak budget", 0)
    destinations = seq(q.get("destinations"), "destinations", True)
    seen = set()
    for d in destinations:
        obj(d, "destination")
        if d.get("node") not in nodes:
            fail("UNKNOWN_NODE", "destination absent")
        if d["node"] in seen:
            fail("DUPLICATE_DESTINATION", "duplicate destination")
        seen.add(d["node"])
        dw = number(d.get("dwell"), "dwell", 0)
        lattice(dw, "dwell")
        for pair in seq(d.get("open_intervals"), "open_intervals"):
            if not isinstance(pair, list) or len(pair) != 2:
                fail("DESTINATION_INTERVAL", "interval needs start/end")
            a = number(pair[0], "opening")
            b = number(pair[1], "closing")
            if b < a:
                fail("DESTINATION_INTERVAL", "closing before opening")
            lattice(a, "opening")
            lattice(b, "closing")
        intervals = d["open_intervals"]
        if any(intervals[i][0] < intervals[i - 1][1] for i in range(1, len(intervals))):
            fail("DESTINATION_INTERVAL", "ordered disjoint openings required")
    limits = obj(q.get("limits"), "limits")
    number(limits.get("wall_s"), "wall limit", 0)
    if "rss_limit_mb" in limits:
        number(limits["rss_limit_mb"], "rss limit", 0)
        if limits["rss_limit_mb"] <= 0:
            fail("RESOURCE_LIMIT", "rss must be positive")
    for k in ["max_labels", "max_expansions", "frontier_width"]:
        integer(limits.get(k), k, 1)
    if q.get("solver", "baseline") not in [
        "baseline",
        "astar",
        "dijkstra",
        "activation",
    ]:
        fail("UNSUPPORTED_SOLVER", "unknown solver")
    result = deepcopy(q)
    if "edge" in pos and pos["fraction"] == 1:
        result["position"] = {"node": edges[pos["edge"]]["v"]}
    return result


def validate_request(graph, hazard, request, *, _validated_inputs=False):
    try:
        return _validate_request(graph, hazard, request, _validated_inputs)
    except (KeyError, TypeError, OverflowError) as ex:
        fail("MALFORMED_REQUEST", str(ex))
