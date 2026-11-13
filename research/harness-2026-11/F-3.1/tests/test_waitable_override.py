"""waitable_override (WIDENED_GRAPH_RULE arm (a)): an override equal to the graph's own flags gives an identical
instance; flipping one node changes exactly that node's waitability; unknown ids and non-bool values are refused.
Requires data/routing (tools/fetch_routing_inputs.py)."""
from __future__ import annotations

import pytest

from deadline_field.real import ROOT, PacketModel

DATA = ROOT / "data" / "routing"
PK = sorted((DATA / "latest_inputs_try02" / "packets").glob("yeongdeok_2025/*")) if DATA.exists() else []
G = DATA / "graphs" / "yeongdeok_2025" / "graph.json"
pytestmark = pytest.mark.skipif(not PK or not G.exists(), reason="routing data not fetched")


def _inst(pm):
    return pm.instance("cert", [], [])


def test_identity_override_equals_graph():
    base = PacketModel(G, PK[0])
    ov = {n: bool(base.g.waitable[n]) for n in base.node_ids}
    pm = PacketModel(G, PK[0], waitable_override=ov)
    a, b = _inst(base), _inst(pm)
    assert a.waitable == b.waitable and a.W == b.W and a.B == b.B


def test_flip_one_node():
    base = PacketModel(G, PK[0])
    n = next(x for x in base.node_ids if not base.g.waitable[x])
    pm = PacketModel(G, PK[0], waitable_override={n: True})
    diff = [x for x in base.node_ids if base.g.waitable[x] != pm.g.waitable[x]]
    assert diff == [n]


def test_refuses_unknown_and_non_bool():
    with pytest.raises(ValueError) as e:
        PacketModel(G, PK[0], waitable_override={"osm:does-not-exist": True})
    assert "osm:does-not-exist" in str(e.value)
    base = PacketModel(G, PK[0])
    with pytest.raises(ValueError):
        PacketModel(G, PK[0], waitable_override={base.node_ids[0]: 1})
    with pytest.raises(ValueError):
        PacketModel(G, PK[0], waitable_override={}, waitable_all=True)
