"""Fire spread modelling subpackage.

Two complementary implementations live here:

- :mod:`wildfireguardian.spread_model.rothermel` — the Rothermel (1972)
  surface fire spread *point* model. Given a fuel model, fuel moisture,
  midflame wind, and slope, returns a single scalar rate of spread plus all
  intermediate quantities.

- :mod:`wildfireguardian.spread_model.cellular_automaton` — a 2D Huygens
  elliptical-wavelet cellular automaton (Finney 1998 style) that uses the
  Rothermel point model as its kernel and propagates a fire perimeter over
  a gridded landscape.

Both are unit-tested under ``tests/``.
"""

from __future__ import annotations

from .rothermel import (
    FUEL_MODELS,
    FuelModel,
    SpreadResult,
    compute_spread_rate,
    rate_of_spread,
)

__all__ = [
    "FUEL_MODELS",
    "FuelModel",
    "SpreadResult",
    "compute_spread_rate",
    "rate_of_spread",
]
