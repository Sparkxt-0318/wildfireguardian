"""Configuration (view) factors from a flame surface to a small receiver (METHOD.md section 5.3).

Geometry, used throughout: the fire front lies along the x axis, centred on x = 0, with front width W. The receiver
is a small plane element at horizontal distance d from the flame base (y = d), height z_r above the ground, facing
the fire (its normal points along -y). The flame is a flat radiating sheet of length L rising from the base line,
tilted by angle theta from the vertical toward the receiver. The flame height is H = L cos(theta) and the tip is
d - L sin(theta) from the receiver horizontally (must be > 0).

Functions:
* ``planar_mcguire``: vertical rectangle (theta = 0), receiver parallel, by the closed-form corner-rectangle
  formula (McGuire 1953; Howell's catalogue, config. B-3), summed over the four sub-rectangles around the foot of the
  receiver's normal. This is the view factor of the Butler and Cohen (1998) model.
* ``tilted_numeric``: the tilted sheet by direct numerical integration of F = int cos(b1) cos(b2) / (pi r^2) dA
  (Gauss-Legendre in both directions). It reduces to ``planar_mcguire`` at theta = 0 (tested).
* ``tilted_max``: the tilt in [0, theta_max] that maximises the view factor (the AS 3959 Method 2 rule of taking the
  flame angle that gives the highest radiant heat flux).
* ``cylinder_mudan``: a vertical cylinder of diameter D and height H seen by a vertical target at distance X from
  its axis (Mudan 1984; Mudan and Croce, SFPE Handbook). A shape comparator, not the line-fire geometry.
"""
from __future__ import annotations

import math

import numpy as np


def _corner(a, b, c):
    """View factor from a differential element to a parallel rectangle a x b whose corner lies on the element's
    normal at distance c (McGuire 1953; Howell config. B-3)."""
    if a <= 0 or b <= 0:
        return 0.0
    X, Y = a / c, b / c
    sx, sy = math.sqrt(1 + X * X), math.sqrt(1 + Y * Y)
    return (X / sx * math.atan(Y / sx) + Y / sy * math.atan(X / sy)) / (2 * math.pi)


def planar_mcguire(d, H, W, z_r=0.0):
    """Vertical flame rectangle of height H and width W, receiver at distance d and height z_r on the centreline,
    parallel to the flame. Sum of corner rectangles (receiver may be below, inside or above the flame's height
    span; parts above or below z_r are handled separately)."""
    half = W / 2.0
    up = max(H - z_r, 0.0)
    down = min(max(z_r, 0.0), H)
    return 2.0 * (_corner(half, up, d) + _corner(half, down, d))


_GL = {}


def _gauss(n):
    if n not in _GL:
        _GL[n] = np.polynomial.legendre.leggauss(n)
    return _GL[n]


def tilted_numeric(d, L, W, theta, z_r=0.0, n=96):
    """Flat flame sheet of length L tilted theta (rad) from vertical toward a vertical receiver; numerical
    integration of the configuration factor. Contributions with either cosine <= 0 are dropped."""
    st, ct = math.sin(theta), math.cos(theta)
    if d - L * st <= 1e-9:
        return float("nan")  # receiver under or inside the flame
    xg, wg = _gauss(n)
    # s along the flame (0..L), u across the front (-W/2..W/2); integrand is even in u, integrate 0..W/2 and double
    s = 0.5 * L * (xg + 1.0)
    ws = 0.5 * L * wg
    u = 0.25 * W * (xg + 1.0)
    wu = 0.25 * W * wg
    S, U = np.meshgrid(s, u, indexing="ij")
    Wt = np.outer(ws, wu)
    ry = d - S * st          # receiver minus flame point
    rz = z_r - S * ct
    rx = -U
    r2 = rx * rx + ry * ry + rz * rz
    r = np.sqrt(r2)
    # flame normal facing the receiver side: (0, cos t, -sin t); receiver normal (0, -1, 0)
    c1 = (ry * ct - rz * st) / r
    c2 = ry / r
    f = np.where((c1 > 0) & (c2 > 0), c1 * c2 / (math.pi * r2), 0.0)
    return float(2.0 * np.sum(f * Wt))


def tilted_max(d, L, W, z_r=0.0, theta_max=math.radians(80.0), n=96, steps=33):
    """Maximum of ``tilted_numeric`` over tilt angles 0..theta_max that keep the flame tip ahead of the receiver
    (coarse grid, then golden-section refinement). Returns (F_max, theta_at_max)."""
    lim = theta_max
    if L > 0 and d < L:
        lim = min(lim, math.asin(min(d / L, 1.0)) - 1e-6)
    if lim <= 0:
        return tilted_numeric(d, L, W, 0.0, z_r, n), 0.0
    th = np.linspace(0.0, lim, steps)
    vals = np.array([tilted_numeric(d, L, W, t, z_r, n) for t in th])
    k = int(np.nanargmax(vals))
    a, b = th[max(k - 1, 0)], th[min(k + 1, steps - 1)]
    g = (math.sqrt(5) - 1) / 2
    for _ in range(30):
        c1, c2 = b - g * (b - a), a + g * (b - a)
        if tilted_numeric(d, L, W, c1, z_r, n) >= tilted_numeric(d, L, W, c2, z_r, n):
            b = c2
        else:
            a = c1
    t = 0.5 * (a + b)
    v = tilted_numeric(d, L, W, t, z_r, n)
    if vals[k] > v:
        return float(vals[k]), float(th[k])
    return v, t


def cylinder_mudan(X, D, H):
    """Vertical target facing a vertical cylinder (diameter D, height H), target at ground level a distance X from
    the cylinder axis (X > D/2). Mudan (1984), Prog. Energy Combust. Sci. 10:59-80; SFPE Handbook (Mudan and Croce):
    S = 2X/D, h = 2H/D, A = (h^2 + S^2 + 1)/(2S), B = (1 + S^2)/(2S),
    F_v = (1/(pi S)) atan(h/sqrt(S^2-1)) - (h/(pi S)) atan(sqrt((S-1)/(S+1)))
          + (A h / (pi S sqrt(A^2-1))) atan(sqrt((A+1)(S-1)/((A-1)(S+1))))."""
    S = 2.0 * X / D
    h = 2.0 * H / D
    if S <= 1.0:
        return float("nan")
    A = (h * h + S * S + 1.0) / (2.0 * S)
    return ((1.0 / (math.pi * S)) * math.atan(h / math.sqrt(S * S - 1.0))
            - (h / (math.pi * S)) * math.atan(math.sqrt((S - 1.0) / (S + 1.0)))
            + (A * h / (math.pi * S * math.sqrt(A * A - 1.0)))
            * math.atan(math.sqrt((A + 1.0) * (S - 1.0) / ((A - 1.0) * (S + 1.0)))))
