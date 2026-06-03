"""Time-varying probabilistic hazard the evacuation router consumes.

This is the bridge between :mod:`wildfireguardian.spread_v2.forward_sim` and
the router. It wraps the forward-simulated sequence of per-cell ignition
*probability* surfaces (EPSG:5179) and answers one question the router asks
repeatedly:

    ``prob_at(x, y, t_min)`` -> P(this location has ignited by clock time
    ``t_min``), in [0, 1].

It is consumed **as-is**: a probabilistic, severity-scaled reach envelope that
grows with time — NOT a binarised front and NOT a thin directional jet. The
router weights edges by this probability (risk cost) and treats locations
above a high-probability cutoff as impassable.

Sampling is bilinear in space (over coarse cell centres) and linear in time
between the two bracketing forecast surfaces; before the first / after the
last surface it clamps to that surface (the hazard is monotone, so clamping
after the horizon is the conservative choice).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..spread_v2.grid import CoarseGrid


@dataclass
class HazardSequence:
    """A sequence of EPSG:5179 ignition-probability surfaces over time."""

    grid: CoarseGrid
    times_min: np.ndarray          # ascending minutes from t0
    surfaces: list[np.ndarray]     # each (nrows, ncols) in [0, 1]

    def __post_init__(self) -> None:
        self.times_min = np.asarray(self.times_min, dtype=float)
        if len(self.times_min) != len(self.surfaces):
            raise ValueError("times_min and surfaces length mismatch")
        if any(s.shape != (self.grid.nrows, self.grid.ncols) for s in self.surfaces):
            raise ValueError("a surface shape does not match the grid")

    @classmethod
    def from_forward_sim(cls, sim) -> "HazardSequence":
        return cls(grid=sim.grid, times_min=np.asarray(sim.step_minutes, dtype=float),
                   surfaces=[s.copy() for s in sim.hazard])

    # -- spatial sampling --------------------------------------------------
    def _bilinear(self, surface: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        g = self.grid
        col_f = (x - g.minx) / g.cell_size_m - 0.5
        row_f = (g.maxy - y) / g.cell_size_m - 0.5
        c0 = np.floor(col_f).astype(int)
        r0 = np.floor(row_f).astype(int)
        dc = col_f - c0
        dr = row_f - r0
        c0c = np.clip(c0, 0, g.ncols - 1)
        c1c = np.clip(c0 + 1, 0, g.ncols - 1)
        r0c = np.clip(r0, 0, g.nrows - 1)
        r1c = np.clip(r0 + 1, 0, g.nrows - 1)
        v00 = surface[r0c, c0c]
        v01 = surface[r0c, c1c]
        v10 = surface[r1c, c0c]
        v11 = surface[r1c, c1c]
        top = v00 * (1 - dc) + v01 * dc
        bot = v10 * (1 - dc) + v11 * dc
        val = top * (1 - dr) + bot * dr
        # Points outside the grid carry zero hazard.
        inside = (x >= g.minx) & (x <= g.maxx) & (y >= g.miny) & (y <= g.maxy)
        return np.where(inside, val, 0.0)

    def _time_bracket(self, t_min: float) -> tuple[int, int, float]:
        ts = self.times_min
        if t_min <= ts[0]:
            return 0, 0, 0.0
        if t_min >= ts[-1]:
            return len(ts) - 1, len(ts) - 1, 0.0
        j = int(np.searchsorted(ts, t_min, side="right"))
        i0, i1 = j - 1, j
        frac = (t_min - ts[i0]) / (ts[i1] - ts[i0])
        return i0, i1, frac

    def prob_at_points(self, xs, ys, t_min: float) -> np.ndarray:
        """Hazard probability at EPSG:5179 points ``(xs, ys)`` at ``t_min``."""
        xs = np.atleast_1d(np.asarray(xs, dtype=float))
        ys = np.atleast_1d(np.asarray(ys, dtype=float))
        i0, i1, frac = self._time_bracket(t_min)
        v0 = self._bilinear(self.surfaces[i0], xs, ys)
        if i0 == i1:
            return np.clip(v0, 0.0, 1.0)
        v1 = self._bilinear(self.surfaces[i1], xs, ys)
        return np.clip(v0 * (1 - frac) + v1 * frac, 0.0, 1.0)

    def prob_at(self, x: float, y: float, t_min: float) -> float:
        """Scalar hazard probability at one point/time."""
        return float(self.prob_at_points([x], [y], t_min)[0])

    def prob_grid_at(self, t_min: float) -> np.ndarray:
        """Full interpolated surface at ``t_min`` (for plotting/analysis)."""
        i0, i1, frac = self._time_bracket(t_min)
        if i0 == i1:
            return self.surfaces[i0].copy()
        return self.surfaces[i0] * (1 - frac) + self.surfaces[i1] * frac

    @property
    def horizon_min(self) -> float:
        return float(self.times_min[-1])


__all__ = ["HazardSequence"]
