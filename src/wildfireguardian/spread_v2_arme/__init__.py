"""Arm E — a directional slope feature for spread_v2.

**EXPERIMENTAL and ADDITIVE. Arm A is not modified.**

Session 11 measured the only robust directional result this project has: the
observed spread bearing agrees with the local upslope bearing on steep terrain
(51.8 deg) and not on gentle terrain (88.4 deg, which is chance), monotone
across slope terciles. The model cannot use that. It carries ``wind_alignment``
— a projection of the wind onto the cell's bearing from the fire — and a scalar
``slope_deg``, but no projection of the terrain gradient.

That asymmetry is not incidental. In the level-set formulation used by
WRF-Fire, wind and terrain enter the spread rate the same way, as projections
onto the fire-front normal: ``a (v . n)^b`` for wind and ``d (grad z . n)`` for
terrain. The feature set has the first and lacks the second.

Arm E adds it:

* ``upslope_alignment`` — cosine between each cell's bearing from the nearest
  active cell (the SAME reference frame ``wind_alignment`` uses) and the local
  upslope bearing.
* ``slope_forcing`` — ``tan(slope)^2``, Rothermel's functional form, as a
  MAGNITUDE term beside the directional one. It sits next to ``slope_deg``, not
  in place of it, and is evaluated as a separate feature.

Pre-registered expectation (written before training, Session 12 Phase 2b):
Session 11 predicts a gain on STEEP terrain and none on gentle terrain. A
pooled null is therefore not a refutation on its own — the stratified result
is the test.
"""

from .terrain import (
    DEFAULT_SUBDIVISION,
    fine_grid,
    native_slope_stats,
    rothermel_slope_factor,
    upslope_bearing_field,
)

__all__ = [
    "DEFAULT_SUBDIVISION",
    "fine_grid",
    "native_slope_stats",
    "rothermel_slope_factor",
    "upslope_bearing_field",
]
