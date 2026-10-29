"""Isochrones on synthetic arrival-time fields."""
import math

import numpy as np
import pytest

import wfg_flamefront as W


def _all_active(member):
    ff = W.prepare(member, member["grid"])
    ff.frames = np.ones((1,) + ff.shape, bool)
    ff.breakpoints = np.array([-1e9, 1e9])
    return ff


def _grid(H, W_, cell=30.0):
    return W.Grid((cell, 0.0, 0.0, 0.0, -cell, H * cell), H, W_)


def test_planar_front_recovers_rate_and_direction():
    H, Wd, cell, R0 = 20, 24, 30.0, 0.5
    g = _grid(H, Wd, cell)
    cols = np.arange(Wd)[None, :].repeat(H, 0)
    x = g.centre_x(cols)
    tau = (x - x.min()) / R0                 # spreads toward +x (east)
    ff = _all_active({"ignition_time_s": tau, "grid": g})
    for t in (100.0, 500.0, 900.0):
        p = W.front_pieces(ff, t)
        assert p["x0"].size > 0
        assert np.allclose(p["R"], R0, rtol=0.01)
        assert np.allclose(p["dir_x"], 1.0, atol=0.01) and np.allclose(p["dir_y"], 0.0, atol=0.01)
        assert np.allclose(p["x0"], x.min() + R0 * t, atol=1e-6)
        segs = W.front_segments(tau, t, g, 11.52, never_arrival_s=1e9)
        lead = [s for s in segs if s["edge"] == "leading"]
        trail = [s for s in segs if s["edge"] == "trailing"]
        assert abs(sum(s["length_m"] for s in lead) - (H - 1) * cell) < 1e-6
        assert all(abs(s["p0"][0] - (x.min() + R0 * (t - 11.52))) < 1e-6 for s in trail)


def test_circular_fire_closed_loops_and_radius_growth():
    H = Wd = 41
    cell, R0 = 25.0, 0.4
    g = _grid(H, Wd, cell)
    r, c = np.indices((H, Wd))
    cx, cy = g.centre_x(20), g.centre_y(20)
    dist = np.hypot(g.centre_x(c) - cx, g.centre_y(r) - cy)
    tau = dist / R0
    ff = _all_active({"ignition_time_s": tau, "grid": g})
    for t in (600.0, 1200.0):
        p = W.front_pieces(ff, t)
        ends = np.concatenate([np.column_stack([p["x0"], p["y0"]]), np.column_stack([p["x1"], p["y1"]])])
        rad = np.hypot(ends[:, 0] - cx, ends[:, 1] - cy)
        assert abs(rad.mean() / (R0 * t) - 1) < 0.02        # radius grows at R0
        # closed: every end point is shared by exactly two pieces
        key = np.round(ends, 6)
        _, counts = np.unique(key, axis=0, return_counts=True)
        assert np.all(counts == 2)
        assert np.allclose(np.median(p["R"]), R0, rtol=0.05)


def test_unknown_cell_is_excluded_not_zero():
    H, Wd = 10, 10
    g = _grid(H, Wd, 375.0)
    tau = np.full((H, Wd), 2000.0)
    tau[5, 5] = 100.0
    m_nan = {"ignition_time_s": tau.copy(), "grid": g}
    m_nan["ignition_time_s"][5, 6] = np.nan
    ff = _all_active(m_nan)
    assert ff.unsupported_cells() == 1
    p = W.front_pieces(ff, 500.0)
    assert not np.any((p["sq_r"] >= 4) & (p["sq_r"] <= 5) & (p["sq_c"] >= 5) & (p["sq_c"] <= 6))
    # the same cell set to zero would create fronts there: excluded is not zero
    m_zero = {"ignition_time_s": tau.copy(), "grid": g}
    m_zero["ignition_time_s"][5, 6] = 0.0
    p0 = W.front_pieces(_all_active(m_zero), 500.0)
    assert np.any((p0["sq_c"] >= 5) & (p0["sq_c"] <= 6) & (p0["sq_r"] >= 4) & (p0["sq_r"] <= 5))
    q_nan = W.flux_at_points(np.array([[g.centre_x(6), g.centre_y(5)]]), [500.0], ff, g, None)
    q_zero = W.flux_at_points(np.array([[g.centre_x(6), g.centre_y(5)]]), [500.0], _all_active(m_zero), g, None)
    assert q_nan[0, 0] != q_zero[0, 0]


def test_isolated_burning_cell_gives_closed_loop_inside_the_cell():
    H, Wd = 9, 9
    g = _grid(H, Wd, 375.0)
    ign = np.full((H, Wd), np.inf)
    ign[4, 4] = 200.0
    member = {"ignition_time_s": ign, "horizon_s": 3600.0, "burning_duration_s": 3970.4642815249267}
    ff = W.prepare(member, g)
    p = W.front_pieces(ff, 1500.0)
    assert p["x0"].size == 8                                  # 4 squares x 2 halves, one loop around the centre
    assert np.all((p["host_r"] == 4) & (p["host_c"] == 4))
    ends = np.round(np.concatenate([np.column_stack([p["x0"], p["y0"]]), np.column_stack([p["x1"], p["y1"]])]), 6)
    _, counts = np.unique(ends, axis=0, return_counts=True)
    assert np.all(counts == 2)
    assert W.front_pieces(ff, 100.0)["x0"].size == 0          # not yet ignited (v1 activity clipping)


def test_simultaneous_neighbours_and_rate_clip():
    H, Wd = 6, 6
    g = _grid(H, Wd, 375.0)
    tau = np.full((H, Wd), 3000.0)
    tau[2, 2] = tau[2, 3] = 500.0                              # simultaneous neighbours
    ff = _all_active({"ignition_time_s": tau, "grid": g})
    p = W.front_pieces(ff, 1000.0)
    # no crossing on the edge between the two simultaneous cells; fronts surround both
    assert p["x0"].size > 0
    tau2 = np.full((H, Wd), 1000.0)
    tau2[2, 2] = 1000.0 + 1e-3                                  # nearly flat: |grad tau| tiny, rate clipped
    p2 = W.front_pieces(_all_active({"ignition_time_s": tau2, "grid": g}), 1000.0005)
    assert p2["x0"].size > 0 and np.all(p2["clipped"]) and np.allclose(p2["R"], 3.0)


def test_present_fire_interior_has_no_front_and_perimeter_does():
    H, Wd = 12, 12
    g = _grid(H, Wd, 375.0)
    ign = np.full((H, Wd), np.inf)
    cur = np.zeros((H, Wd), bool)
    cur[3:9, 3:9] = True
    member = {"ignition_time_s": ign, "current_active": cur, "remaining_s": 3000.0, "horizon_s": 3600.0,
              "burning_duration_s": 3970.4642815249267}
    ff = W.prepare(member, g)
    assert np.allclose(ff.tau[cur], 3000.0 - 3970.4642815249267)
    p = W.front_pieces(ff, 600.0)
    assert p["x0"].size > 0
    interior = (p["sq_r"] >= 3) & (p["sq_r"] <= 7) & (p["sq_c"] >= 3) & (p["sq_c"] <= 7)
    assert not np.any(interior)
    assert np.all(cur[p["host_r"], p["host_c"]])               # flames only inside v1 flaming cells
    assert W.front_pieces(ff, 3100.0)["x0"].size == 0          # after R_max the present fire is inactive in v1
