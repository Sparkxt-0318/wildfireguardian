"""Paired-event evaluation equals the grid evaluation."""
import numpy as np

import wfg_flamefront as W


def test_events_equal_points_diagonal(synth):
    member, grid = synth
    ff = W.prepare(member, grid)
    rng = np.random.default_rng(11)
    p = W.front_pieces(ff, 1500.0)
    mid = np.column_stack([0.5 * (p["x0"] + p["x1"]), 0.5 * (p["y0"] + p["y1"])])
    pts = mid[rng.integers(len(mid), size=40)] + rng.normal(scale=40.0, size=(40, 2))
    ts = rng.uniform(1000, 2000, 40)
    q, eng = W.flux_at_events(pts, ts, ff, grid, None)
    for i in range(40):
        qi = W.flux_at_points(pts[i:i + 1], [ts[i]], ff, grid, None)[0, 0]
        assert abs(q[i] - qi) <= 1e-12 * max(1.0, qi)
    assert (q > 0).sum() > 20
