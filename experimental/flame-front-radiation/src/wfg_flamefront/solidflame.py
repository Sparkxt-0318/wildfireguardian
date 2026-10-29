"""Solid-flame radiation from flame panels to differential receivers.

Emitter: each flame piece is a planar quadrilateral standing on its ground segment p0-p1 (z = 0), with top edge
p0 + lean, p1 + lean at height h (h = flame height, lean = horizontal flame reach in the wind direction; lean = 0 for
a vertical flame). Both faces emit uniformly with emissive power E (kW/m2). Receiver: a differential element at
height ``receiver_height_m`` (default 0 m, as in v1).

View factor. For a differential element with unit normal n and a planar polygon with vertices V_i (relative to the
element), the Lambert contour form gives F(n) = n . v with

    v = (1 / (2 pi)) sum_i gamma_i u_i,   u_i = (R_i x R_i+1) / |R_i x R_i+1|,   gamma_i = angle(R_i, R_i+1),

exact whenever the whole polygon lies in front of the receiver plane (Howell, Menguc and Siegel, contour
integration; the corner-rectangle case is Howell catalogue configuration B-3 and is a unit test). The receiver modes:

* ``worst_case``: F = |v| per panel, the maximum of the unclipped integral over orientations. Because the clipped
  configuration factor satisfies |v| <= max_n F_true(n) <= Omega / pi (Omega: solid angle of the panel), the
  enclosure in ``law_v2`` uses min(1, Omega_box / pi) and therefore bounds every real orientation; the point value is
  the per-panel worst orientation and is exact in the far field and for panels that face the receiver.
* ``vertical_facing(theta)``: n = (cos theta, sin theta, 0) with theta the azimuth in radians counter-clockwise from
  +x (east); F = max(0, n . v') with v' oriented toward the panel.

Flux q = tau_a E F, summed over panels within ``cutoff_radius_m`` (ground distance from the receiver to the segment).

Truncation error at the cutoff radius (default 500 m). For a straight front (any height h, emissive power E) at
perpendicular distance d from the receiver, the part of the front beyond ground radius Rc lies at |y| > Y with
Y = sqrt(Rc^2 - d^2). With r^2 = d^2 + y^2 and h << r, each element h dy contributes at most E h d^2 / (pi r^4) dy
(both cosines equal d / r for a facing receiver) and the worst-case orientation adds at most the factor r / d, so the
omitted part is at most 2 E h d / pi * integral_Y^inf dy / r^3 <= E h d / (pi Y^2). The whole front gives at least
E h / (2 sqrt(h^2 + d^2)) ~ E h / (2 d) (infinite wall, facing receiver), so the relative error is at most
2 d^2 / (pi Y^2). For d <= 50 m and Rc = 500 m this is <= 0.0065 (0.65 %); for d <= 100 m it is <= 0.027. The
enclosure in ``law_v2`` is not truncated, so a checker that uses it never relies on this estimate.
"""
from __future__ import annotations

import math

import numpy as np

TWO_PI = 2.0 * math.pi


def panel_vertices(x0, y0, x1, y1, height, lean_x=0.0, lean_y=0.0, z0=0.0):
    """[S, 4, 3] quadrilaterals: base p0, base p1, top p1, top p0."""
    x0, y0, x1, y1, h = (np.asarray(v, float) for v in (x0, y0, x1, y1, height))
    lx = np.broadcast_to(np.asarray(lean_x, float), x0.shape)
    ly = np.broadcast_to(np.asarray(lean_y, float), x0.shape)
    z = np.broadcast_to(np.asarray(z0, float), x0.shape)
    V = np.empty(x0.shape + (4, 3))
    V[..., 0, :] = np.stack([x0, y0, z], -1)
    V[..., 1, :] = np.stack([x1, y1, z], -1)
    V[..., 2, :] = np.stack([x1 + lx, y1 + ly, z + h], -1)
    V[..., 3, :] = np.stack([x0 + lx, y0 + ly, z + h], -1)
    return V


def lambert_vector(R):
    """R: [..., n, 3] polygon vertices relative to the receiver. Returns v [..., 3] (dimensionless)."""
    Rn = np.roll(R, -1, axis=-2)
    cr = np.cross(R, Rn)
    cn = np.linalg.norm(cr, axis=-1)
    dot = np.einsum("...k,...k->...", R, Rn)
    gamma = np.arctan2(cn, dot)                      # angle between consecutive vertex directions, in [0, pi]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = np.where(cn[..., None] > 0, cr / cn[..., None], 0.0)
    return (gamma[..., None] * u).sum(axis=-2) / TWO_PI


def view_factors(points_xyz, V, receiver="worst_case"):
    """View factors [P, S] from receivers [P, 3] to panels [S, 4, 3]."""
    P = np.asarray(points_xyz, float)
    R = V[None, :, :, :] - P[:, None, None, :]
    v = lambert_vector(R)
    if receiver == "worst_case":
        F = np.linalg.norm(v, axis=-1)
    else:
        kind, theta = receiver
        if kind != "vertical_facing":
            raise ValueError("receiver must be 'worst_case' or ('vertical_facing', theta)")
        centre = V.mean(axis=-2)[None, :, :] - P[:, None, :]
        sgn = np.sign(np.einsum("psk,psk->ps", v, centre))
        n = np.array([math.cos(theta), math.sin(theta), 0.0])
        F = np.maximum(0.0, sgn * (v @ n))
    return np.minimum(F, 1.0)


def point_to_segment_distance(px, py, x0, y0, x1, y1):
    """Ground distance [P, S] from points to segments."""
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(L2 > 0, ((px[:, None] - x0) * dx + (py[:, None] - y0) * dy) / L2, 0.0)
    t = np.clip(t, 0.0, 1.0)
    qx, qy = x0 + t * dx, y0 + t * dy
    return np.hypot(px[:, None] - qx, py[:, None] - qy)


# ---- closed-form bounding geometries (validation and tests) ------------------------------------------------------

def infinite_wall_view_factor(h, d):
    """Vertical receiver at the base facing an infinitely wide wall of height h at distance d."""
    h, d = np.asarray(h, float), np.asarray(d, float)
    return 0.5 * h / np.sqrt(h * h + d * d)


def corner_rectangle_view_factor(a, b, c):
    """Howell catalogue B-3: element to a parallel rectangle a x b at distance c, normal through a corner."""
    A, B = a / c, b / c
    return (A / math.sqrt(1 + A * A) * math.atan(B / math.sqrt(1 + A * A))
            + B / math.sqrt(1 + B * B) * math.atan(A / math.sqrt(1 + B * B))) / TWO_PI


def facing_panel_view_factor(width, height, d, receiver_z=0.0):
    """Element on the ground-level perpendicular bisector facing a vertical panel (width x height, base at z = 0)."""
    w2 = width / 2.0
    up = max(height - receiver_z, 0.0)
    down = max(receiver_z, 0.0)
    f = 0.0
    for hh in (up, down):
        if hh > 0:
            f += 2.0 * corner_rectangle_view_factor(w2, hh, d)
    return f


# ---- solid angles of axis-aligned rectangles and boxes ------------------------------------------------------------

def _corner_term(X, Y, d):
    return np.arctan2(X * Y, d * np.sqrt(d * d + X * X + Y * Y))


def rect_solid_angle(x0, x1, y0, y1, d):
    """Solid angle of the axis-aligned rectangle [x0, x1] x [y0, y1] in a plane at distance d > 0 from the origin
    (origin's projection at (0, 0))."""
    d = np.abs(d)
    return (_corner_term(x1, y1, d) - _corner_term(x0, y1, d) - _corner_term(x1, y0, d) + _corner_term(x0, y0, d))


def box_solid_angle(lo, hi):
    """Solid angle of the axis-aligned box [lo, hi] (arrays [..., 3]) seen from the origin; 4 pi if the origin is inside
    or on the box. Exact: sum of the visible faces."""
    lo = np.asarray(lo, float); hi = np.asarray(hi, float)
    inside = np.all((lo <= 0) & (hi >= 0), axis=-1)
    total = np.zeros(lo.shape[:-1])
    axes = [(0, 1, 2), (1, 2, 0), (2, 0, 1)]
    for k, i, j in axes:
        for face, vis in ((lo[..., k], lo[..., k] > 0), (hi[..., k], hi[..., k] < 0)):
            d = np.where(vis, face, 1.0)
            om = rect_solid_angle(lo[..., i], hi[..., i], lo[..., j], hi[..., j], d)
            total = total + np.where(vis, np.abs(om), 0.0)
    return np.where(inside, 4.0 * math.pi, total)
