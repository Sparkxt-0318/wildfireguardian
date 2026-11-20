"""The heat closure with d* = 0 reproduces the road layer's contact-rule instance exactly; d* > 0 only moves
closures earlier; the old-law constants match research/kcf-heat (PROTOCOL.md 6)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from kcf_radiation import closure, oldlaw

ROOT = Path(__file__).resolve().parents[3]
GRAPH = ROOT / "data/routing/graphs/uiseong_andong_2025/graph.json"
RASTER = ROOT / "product/wfg-roadlayer/examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif"


def test_old_law_constants():
    # research/kcf-heat DERIVATION.md section 3: T*(10) = 84 s rounded, halo 7.96 m
    assert oldlaw.lead_s(10.0) == 84
    assert oldlaw.dstar_m(10.0) == pytest.approx(7.9567, abs=1e-3)
    assert oldlaw.lead_s(2.5) == 350


@pytest.mark.skipif(not GRAPH.is_file(), reason="routing inputs not fetched (tools/fetch_routing_inputs.py)")
def test_zero_heat_equals_engine_and_heat_is_earlier():
    from kcf_radiation import routing  # noqa: F401  (puts the product on sys.path)
    from wfg_roadlayer import engine, fireinput
    reg = routing.AnyRegion("uiseong_andong_2025", GRAPH)
    fire = fireinput.load_geotiff(RASTER, reg.road, issue_utc=datetime(2025, 3, 25, 3, tzinfo=timezone.utc), horizon_min=None)
    hc0 = closure.HeatClosure(reg.road, fire.arrival_s, {}, {}, H=fire.horizon_s)
    inst = engine.build_instance(reg.road, fire.arrival_s, fire.horizon_s)
    assert hc0.edge_blocks() == inst.B
    assert hc0.wait_blocks() == inst.W
    R = {c: 0.1 for c in fire.arrival_s}
    D = {c: 50.0 for c in fire.arrival_s}
    hc = closure.HeatClosure(reg.road, fire.arrival_s, R, D, H=fire.horizon_s)
    for b0, b in zip(inst.B, hc.edge_blocks()):
        if b0:
            assert b and b[0][0] <= b0[0][0]
    for v in range(len(reg.road.node_ids)):
        a, b = hc0.node_b(v), hc.node_b(v)
        if a is not None:
            assert b is not None and b <= a  # a burning neighbour can close it much earlier
