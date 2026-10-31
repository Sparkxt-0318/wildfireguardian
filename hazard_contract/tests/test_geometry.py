"""Geometry: closed-cell coverage against an independent brute force, distances, solid angles."""
import numpy as np
import pytest

from hazard_contract import Grid
from hazard_contract.geometry import (
    points_rect_dmax, polyline_cells, polyline_rect_dmin, rasterize_polygons, solid_angle_cap,
    solid_angle_lower, solid_angle_rects, solid_angle_upper,
)
from hazard_contract.scenario import uniform_pieces
from helpers import brute_cells, make_set


def cells_of(s, g):
    r, c, out = polyline_cells(s.grid, g)
    return set(zip(r.tolist(), c.tolist())), out


@pytest.mark.parametrize("seed", range(6))
def test_supercover_matches_brute_force_on_random_polylines(seed):
    rng = np.random.default_rng(seed)
    s = make_set(np.zeros((7, 9)))
    for _ in range(40):
        n = int(rng.integers(1, 5))
        g = rng.uniform(-150, 1050, size=(n, 2))
        assert cells_of(s, g) == brute_cells(s, g)


@pytest.mark.parametrize("g", [
    [[50.0, 300.0], [650.0, 300.0]],          # along a horizontal grid line
    [[200.0, 50.0], [200.0, 650.0]],          # along a vertical grid line
    [[100.0, 100.0], [500.0, 500.0]],         # through grid corners
    [[300.0, 300.0]],                         # point at a corner: four cells
    [[250.0, 300.0]],                         # point on an edge: two cells
    [[0.0, 350.0], [150.0, 350.0]],           # starts on the outer edge
])
def test_supercover_boundary_cases(g):
    s = make_set(np.zeros((7, 9)))
    g = np.asarray(g)
    assert cells_of(s, g) == brute_cells(s, g)


def test_corner_point_touches_four_cells():
    s = make_set(np.zeros((7, 9)))
    cells, out = cells_of(s, np.array([[300.0, 300.0]]))
    assert len(cells) == 4 and not out


def test_dmin_and_dmax_against_dense_sampling():
    rng = np.random.default_rng(1)
    rects = np.array([[0.0, 100.0, 0.0, 100.0], [300.0, 375.0, -50.0, 20.0], [-80.0, -10.0, 150.0, 400.0]])
    x0, x1, y0, y1 = rects.T
    for _ in range(30):
        g = rng.uniform(-200, 500, size=(3, 2))
        t = np.linspace(0, 1, 400)[:, None]
        pts = np.concatenate([g[i] + t * (g[i + 1] - g[i]) for i in range(2)])
        u = np.linspace(0, 1, 60)
        for j in range(3):
            rx, ry = np.meshgrid(x0[j] + u * (x1[j] - x0[j]), y0[j] + u * (y1[j] - y0[j]))
            rp = np.stack([rx.ravel(), ry.ravel()], 1)
            dists = np.hypot(pts[:, None, 0] - rp[None, :, 0], pts[:, None, 1] - rp[None, :, 1])
            dmin = polyline_rect_dmin(g, x0[j:j + 1], x1[j:j + 1], y0[j:j + 1], y1[j:j + 1])[0]
            dmax = points_rect_dmax(g, x0[j:j + 1], x1[j:j + 1], y0[j:j + 1], y1[j:j + 1]).max()
            assert dmin <= dists.min() + 1e-9 and dists.min() <= dmin + 12.0
            assert dists.max() <= dmax + 1e-9 and dmax <= dists.max() + 1e-9


def test_solid_angle_matches_quadrature_and_bounds_hold():
    rng = np.random.default_rng(2)
    h, L = 5.0, 375.0
    cap = solid_angle_cap(L, L, h)
    assert cap == pytest.approx(solid_angle_rects(np.array([[L / 2, L / 2]]), np.array([0.0]), np.array([L]),
                                                  np.array([0.0]), np.array([L]), h)[0, 0], rel=1e-12)
    n = 800
    u = (np.arange(n) + 0.5) / n * L
    X, Y = np.meshgrid(u, u)
    for _ in range(25):
        p = rng.uniform(-600, 1000, size=2)
        om = solid_angle_rects(p[None, :], np.array([0.0]), np.array([L]), np.array([0.0]), np.array([L]), h)[0, 0]
        r2 = (X - p[0]) ** 2 + (Y - p[1]) ** 2
        quad = float(np.sum(h / (r2 + h * h) ** 1.5) * (L / n) ** 2)
        if np.hypot(*(p - np.clip(p, 0, L))) > 20:            # quadrature is accurate away from the cell
            assert om == pytest.approx(quad, rel=2e-3)
        dmin = np.hypot(max(0 - p[0], 0, p[0] - L), max(0 - p[1], 0, p[1] - L))
        dmax = np.hypot(max(abs(p[0]), abs(p[0] - L)), max(abs(p[1]), abs(p[1] - L)))
        assert solid_angle_lower(np.array([dmax]), L * L, h)[0] <= om * (1 + 1e-12)
        assert om <= solid_angle_upper(np.array([dmin]), L * L, h, cap)[0] * (1 + 1e-12)


def test_rasterize_all_touched():
    grid = Grid((100.0, 0, 0, 0, -100.0, 500.0), 5, 5)
    tri = np.array([[110.0, 110.0], [390.0, 110.0], [250.0, 390.0]])
    m = rasterize_polygons(grid, tri)
    # every cell whose centre is inside is included, plus cells crossed by the boundary
    assert m[3, 1] and m[3, 2] and m[3, 3] and m[1, 2]
    assert not m[0, 0] and not m[4, 4]


def test_uniform_pieces_cover_the_path_in_time_order():
    s = make_set(np.zeros((5, 5)))
    g = np.array([[10.0, 10.0], [260.0, 140.0], [480.0, 470.0]])
    pieces = uniform_pieces(s.grid, g, 100.0, 200.0, max_len_m=40.0)
    assert pieces[0][1] == 100.0 and pieces[-1][2] == pytest.approx(200.0)
    for (pg, ta, tb), (pg2, ta2, _tb2) in zip(pieces, pieces[1:]):
        assert ta < tb and tb == pytest.approx(ta2) and np.allclose(pg[1], pg2[0])
        assert np.hypot(*(pg[1] - pg[0])) <= 40.0 + 1e-9
