"""View factors and solid angles against closed forms."""
import math

import numpy as np

from wfg_flamefront.solidflame import (box_solid_angle, corner_rectangle_view_factor, facing_panel_view_factor,
                                       infinite_wall_view_factor, lambert_vector, panel_vertices, rect_solid_angle)
from wfg_flamefront.law_v2 import view_factors_pairs


def test_receiver_facing_centre_of_square_emitter():
    # square of side 2s in the plane z = d, receiver at the origin facing +z: F = 4 * F_corner(s, s, d)
    for s, d in ((1.0, 1.0), (2.5, 7.0), (10.0, 3.0)):
        V = np.array([[-s, -s, d], [s, -s, d], [s, s, d], [-s, s, d]])
        v = lambert_vector(V[None])[0]
        expected = 4.0 * corner_rectangle_view_factor(s, s, d)
        assert abs(v[2] - expected) < 1e-12 * max(1.0, expected)
        assert abs(np.linalg.norm(v) - expected) < 1e-12   # worst case equals facing case by symmetry
    # closed form for s = d = 1: 4/(2 pi) * 2 * (1/sqrt2) atan(1/sqrt2)
    v = lambert_vector(np.array([[[-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1.]]]))[0]
    assert abs(v[2] - 4.0 / math.pi * math.atan(1 / math.sqrt(2)) / math.sqrt(2)) < 1e-12


def test_far_field_point_source_limit():
    # small tilted emitter of area A at distance d: F -> A cos(theta_e) cos(theta_r) / (pi d^2)
    a = 0.5
    for d in (50.0, 500.0, 5000.0):
        tilt = math.radians(30)
        n_e = np.array([0.0, -math.sin(tilt), -math.cos(tilt)])   # emitter normal, not facing the receiver squarely
        e1 = np.array([1.0, 0.0, 0.0]); e2 = np.cross(n_e, e1)
        c = np.array([0.0, 0.0, d])
        V = np.array([c - a * e1 - a * e2, c + a * e1 - a * e2, c + a * e1 + a * e2, c - a * e1 + a * e2])
        v = lambert_vector(V[None])[0]
        A = (2 * a) ** 2
        cos_e = abs(np.dot(n_e, -c / d))
        expected_facing = A * cos_e * 1.0 / (math.pi * d * d)   # receiver normal pointing at the emitter
        assert abs(np.linalg.norm(v) - expected_facing) / expected_facing < 3.0 * (a / d) ** 2 + 1e-9


def test_infinite_wall_limit_and_vertical_receiver():
    h, d = 3.0, 6.0
    V = panel_vertices(np.array([-1e5]), np.array([d]), np.array([1e5]), np.array([d]), np.array([h]))
    P3 = np.zeros((1, 3))
    F = view_factors_pairs(P3, V, ("vertical_facing", math.pi / 2))[0]   # receiver faces +y (north)
    assert abs(F - infinite_wall_view_factor(h, d)) < 1e-6
    assert abs(infinite_wall_view_factor(1.0, 2.0) - 0.2236) < 1e-4       # 0.22 at d = 2h
    # worst-case orientation of the infinite wall: sin(phi / 2), phi = atan(h / d)
    Fw = view_factors_pairs(P3, V, "worst_case")[0]
    assert abs(Fw - math.sin(0.5 * math.atan(h / d))) < 1e-6
    # 20 m x 20 m panel at d = 4h with h = 20 m: about 0.02
    assert 0.015 < facing_panel_view_factor(20.0, 20.0, 80.0) < 0.025


def test_panel_bisector_matches_corner_formula():
    w, h, d = 10.0, 2.5, 5.0
    V = panel_vertices(np.array([-w / 2]), np.array([d]), np.array([w / 2]), np.array([d]), np.array([h]))
    F = view_factors_pairs(np.zeros((1, 3)), V, ("vertical_facing", math.pi / 2))[0]
    assert abs(F - facing_panel_view_factor(w, h, d)) < 1e-12


def test_rectangle_and_box_solid_angles():
    # square of side 2 at distance 1 subtends 2 pi / 3
    assert abs(rect_solid_angle(-1, 1, -1, 1, 1.0) - 2 * math.pi / 3) < 1e-12
    # a cube around the origin: 4 pi; a distant box: ~ projected area / d^2
    assert box_solid_angle(np.array([-1., -1, -1]), np.array([1., 1, 1])) == 4 * math.pi
    lo, hi = np.array([1000., -1, -1]), np.array([1002., 1, 1])
    assert abs(box_solid_angle(lo, hi) - 4.0 / 1000.0 ** 2) / (4e-6) < 1e-2
    # a box seen from a corner direction sums three faces; compare with Monte Carlo
    rng = np.random.default_rng(1)
    lo, hi = np.array([1., 2., -0.5]), np.array([3., 4., 2.0])
    d = rng.normal(size=(400000, 3)); d /= np.linalg.norm(d, axis=1)[:, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        t0 = (lo - 0) / d; t1 = (hi - 0) / d
    tmin = np.nanmax(np.minimum(t0, t1), axis=1); tmax = np.nanmin(np.maximum(t0, t1), axis=1)
    hit = (tmax >= np.maximum(tmin, 0)).mean() * 4 * math.pi
    assert abs(box_solid_angle(lo, hi) - hit) < 0.02
