"""Enclosure soundness and monotonicity on random boxes and intervals."""
import numpy as np
import pytest

import wfg_flamefront as W

N_CASES = 1000


def _random_cases(ff, rng, n):
    g = ff.grid
    H, Wd = ff.shape
    x_lo, x_hi = sorted([float(g.centre_x(0)), float(g.centre_x(Wd - 1))])
    y_lo, y_hi = sorted([float(g.centre_y(0)), float(g.centre_y(H - 1))])
    # bias the boxes toward flame pieces so that most cases see non-zero flux
    pts = []
    for t in np.linspace(100, 3500, 12):
        p = W.front_pieces(ff, t)
        if p["x0"].size:
            pts.append(np.column_stack([0.5 * (p["x0"] + p["x1"]), 0.5 * (p["y0"] + p["y1"])]))
    pts = np.concatenate(pts)
    cases = []
    for _ in range(n):
        if rng.random() < 0.8:
            cx, cy = pts[rng.integers(len(pts))] + rng.normal(scale=60.0, size=2)
        else:
            cx, cy = rng.uniform(x_lo, x_hi), rng.uniform(y_lo, y_hi)
        hw, hh = rng.exponential(8.0), rng.exponential(8.0)
        a = rng.uniform(0, 3500); b = a + rng.exponential(5.0)
        cases.append(((cx - hw, cx + hw, cy - hh, cy + hh), (a, min(b, 3600.0))))
    return cases


@pytest.mark.parametrize("which", ["synthetic"])
def test_point_values_inside_enclosure_and_nesting(synth, which):
    member, grid = synth
    ff = W.prepare(member, grid)
    fuel = W.FuelParameters()
    rng = np.random.default_rng(20261029)
    cases = _random_cases(ff, rng, N_CASES)
    nonzero = 0
    for box, (a, b) in cases:
        lo, up = W.flux_enclosure(box, (a, b), ff, grid, fuel)
        xs = rng.uniform(box[0], box[1], 4); ys = rng.uniform(box[2], box[3], 4)
        ts = np.unique(np.concatenate([[a, b], rng.uniform(a, b, 2)]))
        q = W.flux_at_points(np.column_stack([xs, ys]), ts, ff, grid, fuel)
        assert np.all(q >= lo - 1e-12), (box, a, b, lo, q.min())
        assert np.all(q <= up), (box, a, b, up, q.max())
        nonzero += q.max() > 0.1
        # nesting: a sub-box and sub-interval never widen the enclosure
        fx, fy = rng.uniform(0, 1, 2)
        sub = (box[0] + fx * (box[1] - box[0]) * 0.5, box[1] - (1 - fx) * (box[1] - box[0]) * 0.5,
               box[2] + fy * (box[3] - box[2]) * 0.5, box[3] - (1 - fy) * (box[3] - box[2]) * 0.5)
        sa = a + 0.3 * (b - a); sb = b - 0.3 * (b - a)
        lo2, up2 = W.flux_enclosure(sub, (sa, sb), ff, grid, fuel)
        assert up2 <= up * (1 + 1e-12) + 1e-15 and lo2 >= lo
    assert nonzero > N_CASES // 4


def test_enclosure_on_frozen_packet_if_available():
    from conftest import INPUTS
    pk = INPUTS / "latest_inputs_try02/packets/uiseong_andong_2025/20250325T170000Z"
    if not pk.exists():
        pytest.skip("frozen routing inputs not available")
    members, grid, _ = W.load_packet_members(pk)
    ff = W.prepare(members[2], grid)
    rng = np.random.default_rng(5)
    for box, (a, b) in _random_cases(ff, rng, 150):
        lo, up = W.flux_enclosure(box, (a, b), ff, grid, None)
        xs = rng.uniform(box[0], box[1], 3); ys = rng.uniform(box[2], box[3], 3)
        q = W.flux_at_points(np.column_stack([xs, ys]), [a, 0.5 * (a + b), b], ff, grid, None)
        assert np.all(q >= lo - 1e-12) and np.all(q <= up)


def test_engulfment_lower_bound():
    H, Wd = 8, 8
    g = W.Grid((375.0, 0, 0, 0, -375.0, 8 * 375.0), H, Wd)
    ign = np.full((H, Wd), np.inf)
    ign[3, 3] = 0.0
    ff = W.prepare({"ignition_time_s": ign}, g)
    fuel = W.FuelParameters(residence_s=600.0)
    p = W.front_pieces(ff, 1000.0)
    # a point just behind the front (inside the band) gets E; a tiny box around it has lower bound E
    mx, my = 0.5 * (p["x0"][0] + p["x1"][0]), 0.5 * (p["y0"][0] + p["y1"][0])
    x, y = mx - 2 * p["dir_x"][0], my - 2 * p["dir_y"][0]
    q = W.flux_at_points(np.array([[x, y]]), [1000.0], ff, g, fuel)
    assert q[0, 0] == 100.0
    lo, up = W.flux_enclosure((x - 0.1, x + 0.1, y - 0.1, y + 0.1), (1000.0, 1001.0), ff, g, fuel)
    assert lo == 100.0 and up >= 100.0


def test_untruncated_bound_dominates_truncated_and_long_cutoff_points(synth):
    member, grid = synth
    ff = W.prepare(member, grid)
    rng = np.random.default_rng(9)
    far = W.FuelParameters(cutoff_radius_m=1e7)
    for box, (a, b) in _random_cases(ff, rng, 120):
        lo, up_t = W.flux_enclosure(box, (a, b), ff, grid, None)
        _, up_u = W.flux_enclosure(box, (a, b), ff, grid, None, truncate=False)
        assert up_u >= up_t
        xs = rng.uniform(box[0], box[1], 2); ys = rng.uniform(box[2], box[3], 2)
        q_far = W.flux_at_points(np.column_stack([xs, ys]), [a, b], ff, grid, far)
        assert np.all(q_far <= up_u)


def test_flame_depth_emissivity_option_sound(synth):
    member, grid = synth
    ff = W.prepare(member, grid)
    fuel = W.FuelParameters(emissivity_model="flame_depth")
    rng = np.random.default_rng(17)
    for box, (a, b) in _random_cases(ff, rng, 150):
        lo, up = W.flux_enclosure(box, (a, b), ff, grid, fuel)
        xs = rng.uniform(box[0], box[1], 3); ys = rng.uniform(box[2], box[3], 3)
        q = W.flux_at_points(np.column_stack([xs, ys]), [a, b], ff, grid, fuel)
        assert np.all(q >= lo - 1e-12) and np.all(q <= up)
    from wfg_flamefront.intensity import panel_emissive_power
    E = panel_emissive_power(np.array([0.05, 0.5, 50.0]), np.array([0, 0, 0]), np.array([0, 0, 0]), fuel)
    assert E[0] < E[1] < E[2] <= 5.670374419e-8 * 1200.0 ** 4 / 1000 + 1e-9
