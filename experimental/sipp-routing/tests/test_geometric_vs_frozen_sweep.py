"""SIPP through its geometry front end versus the FROZEN contact sweep on random small geometric instances.

Random road graphs on a small grid, random exact activity intervals per cell (several members, present fire), random
waitability, turn restrictions, departures, horizons and destination windows. Both planners read the same contact model
and must return the same status and the same arrival second.
"""
import os
import sys
from fractions import Fraction as F
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scenario-members" / "src"))
sys.path.insert(0, str(HERE.parent / "src"))
from wfg_members import planner  # noqa: E402
from wfg_sipp import frontend  # noqa: E402

CASES = int(os.environ.get("WFG_SIPP_GEOMETRIC_CASES", "2000"))


class Model:
    def __init__(self, cell_intervals):
        self.cell_intervals = cell_intervals


@st.composite
def geometric_case(draw):
    W, H, res = draw(st.integers(2, 5)), draw(st.integers(2, 5)), 100
    n = draw(st.integers(4, 12))
    nodes = []
    for i in range(n):
        nodes.append({"id": "n%d" % i, "x": float(draw(st.integers(1, W * res - 1))) + 0.25,
                      "y": float(draw(st.integers(1, H * res - 1))) + 0.5, "waitable": draw(st.booleans())})
    edges = []
    for k in range(draw(st.integers(n - 1, 3 * n))):
        u = k % n if k < n - 1 else draw(st.integers(0, n - 1))
        v = (k + 1) % n if k < n - 1 else draw(st.integers(0, n - 1))
        if u == v:
            v = (u + 1) % n
        edges.append({"id": "e%d" % k, "u": "n%d" % u, "v": "n%d" % v, "travel_ticks": draw(st.integers(1, 30))})
    forbidden = []
    for _ in range(draw(st.integers(0, len(edges)))):
        a, b = draw(st.sampled_from(edges)), draw(st.sampled_from(edges))
        if a["v"] == b["u"]:
            forbidden.append([a["id"], b["id"]])
    graph = {"nodes": nodes, "edges": edges, "forbidden_turns": forbidden,
             "grid": {"x0": 0.0, "y0": 0.0, "resolution": float(res), "width": W, "height": H}}
    horizon = draw(st.integers(40, 200))
    T = F(draw(st.integers(5, 120)), draw(st.integers(1, 7)))
    cells = {}
    for _ in range(draw(st.integers(0, 8))):
        c = draw(st.integers(0, W * H - 1))
        b = F(draw(st.integers(0, horizon * 8)), 8)
        cells.setdefault(c, []).append((b, b + T))
    if draw(st.booleans()):
        R = F(draw(st.integers(1, horizon)), 3)
        cells.setdefault(draw(st.integers(0, W * H - 1)), []).append((F(0), R))
    cells = {c: sorted(set(v)) for c, v in cells.items()}
    origin = draw(st.integers(0, n - 1))
    dest = draw(st.integers(0, n - 1))
    a = draw(st.integers(0, horizon))
    b = draw(st.integers(a, horizon))
    dwell = draw(st.integers(0, 20))
    dep = draw(st.integers(0, 10))
    request = {"position": {"node": "n%d" % origin}, "incoming_edge": None, "departure": dep, "horizon": float(horizon),
               "destinations": [{"node": "n%d" % dest, "dwell": dwell, "open_intervals": [[a, b]]}],
               "incurred": {"m0": 0}, "budgets": {"peak": 10, "dose": {"m0": 100}}, "hazard_version": 1}
    return graph, request, Model(cells)


@settings(max_examples=CASES, deadline=None, derandomize=True, database=None, suppress_health_check=list(HealthCheck))
@given(geometric_case())
def test_sipp_front_end_matches_the_frozen_sweep(case):
    graph, request, model = case
    a = frontend.sipp_plan(graph, request, model)
    b = planner.sweep_plan(graph, request, model)
    assert (a["raw_status"], a["arrival"]) == (b["raw_status"], b["arrival"]), (a, b)
