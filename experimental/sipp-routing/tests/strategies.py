"""Hypothesis strategies: random small abstract lattice instances (5 to 30 nodes, random turn restrictions, random
member activity intervals, random destination windows)."""
import sys
from pathlib import Path

from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wfg_sipp import sipp as S  # noqa: E402
from wfg_sipp.intervals import normalise  # noqa: E402


@st.composite
def interval_lists(draw, horizon, max_count=3):
    out = []
    for _ in range(draw(st.integers(0, max_count))):
        a = draw(st.integers(0, horizon))
        b = draw(st.integers(a, min(horizon, a + draw(st.integers(0, 12)))))
        out.append((a, b))
    return out


@st.composite
def members(draw, n_nodes, n_edges, horizon, max_members=4):
    out = []
    for _ in range(draw(st.integers(1, max_members))):
        eb = {}
        for j in draw(st.lists(st.integers(0, n_edges - 1), max_size=max(1, n_edges // 2), unique=True)):
            eb[j] = normalise(draw(interval_lists(horizon)))
        wb = {}
        for n in draw(st.lists(st.integers(0, n_nodes - 1), max_size=max(1, n_nodes // 3), unique=True)):
            wb[n] = normalise(draw(interval_lists(horizon)))
        out.append({"edge_block": eb, "wait_block": wb})
    return out


@st.composite
def instances(draw, with_members=False):
    V = draw(st.integers(5, 30))
    E = draw(st.integers(V - 1, min(3 * V, 70)))
    horizon = draw(st.integers(10, 80))
    departure = draw(st.integers(0, 5))
    tail, head, D = [], [], []
    for j in range(E):
        u = draw(st.integers(0, V - 1)) if j >= V - 1 else j % V
        v = draw(st.integers(0, V - 1)) if j >= V - 1 else (j + 1) % V
        tail.append(u)
        head.append(v)
        D.append(draw(st.integers(1, 6)))
    origin = draw(st.integers(0, V - 1))
    forbidden = set()
    for _ in range(draw(st.integers(0, E))):
        forbidden.add((draw(st.integers(0, E - 1)), draw(st.integers(0, E - 1))))
    waitable = [draw(st.booleans()) for _ in range(V)]
    dests = draw(st.lists(st.integers(0, V - 1), min_size=1, max_size=2, unique=True))
    accept = {d: normalise(draw(interval_lists(horizon, 2))) for d in dests}
    mems = draw(members(V, E, horizon)) if with_members else [draw(members(V, E, horizon, 1))[0]]
    eb, wb = {}, {}
    for m in mems:
        for j, v in m["edge_block"].items():
            eb.setdefault(j, []).extend(v)
        for n, v in m["wait_block"].items():
            wb.setdefault(n, []).extend(v)
    inst = S.make_instance(n_nodes=V, tail=tail, head=head, D=D, origin=origin, start_state=E, forbidden=forbidden,
                           waitable=waitable, edge_block=eb, wait_block=wb, accept=accept, departure=departure, horizon=horizon)
    return (inst, mems) if with_members else inst


def rebuild(inst, **changes):
    kw = dict(n_nodes=inst.n_nodes, tail=list(inst.tail), head=list(inst.head), D=list(inst.D), origin=inst.origin,
              start_state=inst.start_state, forbidden=set(inst.forbidden), waitable=list(inst.waitable),
              edge_block={j: list(v) for j, v in inst.edge_block.items()}, wait_block={n: list(v) for n, v in inst.wait_block.items()},
              accept={n: list(v) for n, v in inst.accept.items()}, departure=inst.departure, horizon=inst.horizon)
    kw.update(changes)
    return S.make_instance(**kw)
