#!/usr/bin/env python
"""Forecast-error perturbation primitives + fixed-route re-scorer.

Robustness analysis for the evacuation router: the routes are computed ONCE on
the forecast hazard field (that step is done elsewhere and frozen into
``data/processed/routing_demo.npz``). Here we ask a different question — *if the
forecast were wrong, would the already-chosen routes still be safe?* We never
re-route. We take the FIXED node geometry and FIXED arrival clock of each route
and re-score its on-route hazard against deliberately perturbed hazard fields.

Runs entirely from ``routing_demo.npz`` — no raw FIRMS bundle, no package
import. The re-scorer reproduces :class:`wildfireguardian.routing.hazard.
HazardSequence` (bilinear in space, linear in time, clamp outside the horizon)
and the route scoring in ``routing.evacuation._evaluate_path`` (exposure =
sum of hazard * edge-time, max_hazard = worst node, enters_hazard = any node at
or above ``p_cut``) to <1e-6. Verified against the stored ``fa_node_haz`` /
``naive_node_haz`` arrays by :func:`self_check`.

Three perturbation axes are applied to the hazard field:

  (a) temporal shift  — the front arrives ``dt_earlier`` minutes EARLY. A route
      node at clock time ``t`` then sees the hazard the unperturbed forecast
      placed at ``t + dt_earlier``. Implemented by shifting the query clock.
  (b) spatial translation — the whole reach envelope is displaced by
      ``(dx, dy)`` metres. Hazard at ``(x, y)`` becomes the unperturbed hazard
      at ``(x - dx, y - dy)``. Implemented by shifting the query point.
  (c) probability scaling — every cell multiplied by ``k`` and clipped to
      [0, 1]. Implemented by scaling+clipping the stack, then sampling.

These magnitudes are EXPLORATORY ranges, not a calibrated forecast-error model.

This is a robustness analysis of the METHOD on ONE real route pair — the npz
naive(28 nodes)/future-aware(23 nodes) pair, whose origin differs from the
committed ``routing_demo.json`` headline (origin_node 3316, 23/23). It is NOT a
restatement of that headline.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DEFAULT_NPZ = REPO / "data" / "processed" / "routing_demo.npz"


# --------------------------------------------------------------------------- #
# Perturbable hazard field (standalone reimplementation of HazardSequence)     #
# --------------------------------------------------------------------------- #
@dataclass
class HazardField:
    """A time-stack of EPSG:5179 ignition-probability surfaces, sampleable
    under temporal-shift / spatial-translation / probability-scale perturbation.
    """

    minx: float
    miny: float
    maxx: float
    maxy: float
    cell: float
    times_min: np.ndarray          # ascending minutes
    stack: np.ndarray              # (T, nrows, ncols) float, in [0, 1]

    @property
    def nrows(self) -> int:
        return self.stack.shape[1]

    @property
    def ncols(self) -> int:
        return self.stack.shape[2]

    @classmethod
    def from_npz(cls, npz) -> "HazardField":
        minx, miny, maxx, maxy, cell = [float(v) for v in npz["grid_extent"]]
        return cls(minx, miny, maxx, maxy, cell,
                   np.asarray(npz["haz_times"], float),
                   np.asarray(npz["haz_stack"], float))

    # -- exact copy of HazardSequence._bilinear (vectorised) ---------------- #
    def _bilinear(self, surface: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        col_f = (x - self.minx) / self.cell - 0.5
        row_f = (self.maxy - y) / self.cell - 0.5
        c0 = np.floor(col_f).astype(int)
        r0 = np.floor(row_f).astype(int)
        dc = col_f - c0
        dr = row_f - r0
        c0c = np.clip(c0, 0, self.ncols - 1)
        c1c = np.clip(c0 + 1, 0, self.ncols - 1)
        r0c = np.clip(r0, 0, self.nrows - 1)
        r1c = np.clip(r0 + 1, 0, self.nrows - 1)
        v00 = surface[r0c, c0c]
        v01 = surface[r0c, c1c]
        v10 = surface[r1c, c0c]
        v11 = surface[r1c, c1c]
        top = v00 * (1 - dc) + v01 * dc
        bot = v10 * (1 - dc) + v11 * dc
        val = top * (1 - dr) + bot * dr
        inside = (x >= self.minx) & (x <= self.maxx) & (y >= self.miny) & (y <= self.maxy)
        return np.where(inside, val, 0.0)

    # -- exact copy of HazardSequence._time_bracket ------------------------- #
    def _time_bracket(self, t_min: float) -> tuple[int, int, float]:
        ts = self.times_min
        if t_min <= ts[0]:
            return 0, 0, 0.0
        if t_min >= ts[-1]:
            return len(ts) - 1, len(ts) - 1, 0.0
        j = int(np.searchsorted(ts, t_min, side="right"))
        i0, i1 = j - 1, j
        return i0, i1, (t_min - ts[i0]) / (ts[i1] - ts[i0])

    def _prob_stack(self, stack: np.ndarray, xs: np.ndarray, ys: np.ndarray,
                    t_min: float) -> np.ndarray:
        i0, i1, frac = self._time_bracket(t_min)
        v0 = self._bilinear(stack[i0], xs, ys)
        if i0 == i1:
            return np.clip(v0, 0.0, 1.0)
        v1 = self._bilinear(stack[i1], xs, ys)
        return np.clip(v0 * (1 - frac) + v1 * frac, 0.0, 1.0)


# --------------------------------------------------------------------------- #
# Route container                                                              #
# --------------------------------------------------------------------------- #
@dataclass
class FixedRoute:
    """A frozen route: node geometry + arrival clock never change under
    perturbation (we re-score, never re-route)."""

    name: str
    xy: np.ndarray            # (n, 2) EPSG:5179
    arrivals: np.ndarray      # (n,) minutes

    @property
    def edge_dt(self) -> np.ndarray:
        return np.diff(self.arrivals)


@dataclass
class RouteScore:
    max_hazard: float
    exposure: float
    enters_hazard: bool
    node_hazard: np.ndarray


# --------------------------------------------------------------------------- #
# Perturbed re-scoring                                                         #
# --------------------------------------------------------------------------- #
def score_route(field: HazardField, route: FixedRoute, p_cut: float,
                *, dt_earlier: float = 0.0, dx: float = 0.0, dy: float = 0.0,
                k: float = 1.0) -> RouteScore:
    """Re-score a FIXED route against a perturbed hazard field.

    (a) ``dt_earlier`` > 0 -> front arrives early -> query clock += dt_earlier.
    (b) ``(dx, dy)`` metres translate the front -> query point -= (dx, dy).
    (c) ``k`` scales every cell (clipped to [0, 1]) -> scale+clip the stack.
    """
    stack = field.stack if k == 1.0 else np.clip(field.stack * k, 0.0, 1.0)
    xs = route.xy[:, 0] - dx
    ys = route.xy[:, 1] - dy
    node_h = np.empty(len(route.xy), float)
    for i in range(len(route.xy)):
        clk = route.arrivals[i] + dt_earlier
        node_h[i] = field._prob_stack(stack, xs[i:i + 1], ys[i:i + 1], clk)[0]
    max_h = float(node_h.max())
    exposure = float(np.sum(node_h[:-1] * route.edge_dt))   # h[i] * dt[i]
    enters = bool(np.any(node_h >= p_cut))
    return RouteScore(max_h, exposure, enters, node_h)


# 8 compass directions (unit vectors), clockwise from East.
DIRECTIONS = {
    "E": (1.0, 0.0), "NE": (0.7071067811865476, 0.7071067811865476),
    "N": (0.0, 1.0), "NW": (-0.7071067811865476, 0.7071067811865476),
    "W": (-1.0, 0.0), "SW": (-0.7071067811865476, -0.7071067811865476),
    "S": (0.0, -1.0), "SE": (0.7071067811865476, -0.7071067811865476),
}


def load_routes(npz) -> dict[str, FixedRoute]:
    return {
        "naive": FixedRoute("naive", np.asarray(npz["naive_xy"], float),
                            np.asarray(npz["naive_arrivals"], float)),
        "fa": FixedRoute("fa", np.asarray(npz["fa_xy"], float),
                         np.asarray(npz["fa_arrivals"], float)),
    }


def npz_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def self_check(npz_path: Path = DEFAULT_NPZ, p_cut: float = 0.5, tol: float = 1e-6):
    """Assert the unperturbed re-score reproduces the stored node hazards."""
    npz = np.load(npz_path)
    field = HazardField.from_npz(npz)
    routes = load_routes(npz)
    for name, route in routes.items():
        sc = score_route(field, route, p_cut)
        stored = np.asarray(npz[f"{name}_node_haz"], float)
        err = float(np.max(np.abs(sc.node_hazard - stored)))
        assert err < tol, f"{name} re-score error {err} exceeds {tol}"
    return True


if __name__ == "__main__":
    ok = self_check()
    print("self_check passed:", ok)
