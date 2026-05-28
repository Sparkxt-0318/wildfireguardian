"""Rothermel (1972) surface fire spread model — single- and multi-class.

This package replaces the Session 1 single-file
``wildfireguardian.spread_model.rothermel`` module. It preserves the public
API for backwards compatibility while adding the multi-class machinery
(Andrews 2018 §3) and the Korean Pinus densiflora analog fuel model.

Quick reference
---------------

- Single-class (Session 1 style)::

      from wildfireguardian.spread_model.rothermel import (
          FUEL_MODELS, FuelModel, compute_spread_rate, SpreadResult,
      )
      r = compute_spread_rate("FM10", fuel_moisture=0.08, wind_speed_ms=2.0)

- Multi-class (new in Session 2)::

      from wildfireguardian.spread_model.rothermel import (
          ANDERSON_13, KOREAN_PINUS, MultiClassFuelModel,
          compute_spread_rate, compute_multi_class_spread_rate,
      )
      r = compute_spread_rate(
          ANDERSON_13["FM10"],
          dead_moisture=0.06, live_moisture=1.00,
          wind_speed_ms=2.0,
      )
      r_kp = compute_multi_class_spread_rate(
          KOREAN_PINUS, dead_moisture=0.10, live_moisture=0.40,
          wind_speed_ms=2.0,
      )

The sub-modules expose the building blocks for forestry-researcher
inspection:

- :mod:`.equations` — pure sub-equation functions, each citing Andrews 2018.
- :mod:`.fuel_model` — data structures (``FuelModel``, ``MultiClassFuelModel``,
  ``FuelClass``) and the Anderson 13 / Korean Pinus registries.
- :mod:`.spread` — the master rate-of-spread engine.

References cited in every sub-module:

- Rothermel, R.C. (1972). USDA FS RP INT-115.
- Albini, F.A. (1976). USDA FS GTR INT-30.
- Anderson, H.E. (1982). USDA FS GTR INT-122.
- Burgan, R.E. (1979). USDA FS RP INT-226.
- Andrews, P.L. (2018). USDA FS GTR RMRS-GTR-371.
"""

from __future__ import annotations

# Equations (Andrews 2018 §3 building blocks)
from .equations import (
    PARTICLE_DENSITY_LB_FT3,
    bulk_density,
    effective_heating_number,
    heat_of_preignition,
    live_moisture_of_extinction_burgan1979,
    mineral_damping_coefficient,
    moisture_damping_coefficient,
    optimum_packing_ratio,
    packing_ratio,
    propagating_flux_ratio,
    reaction_intensity_multi_class,
    reaction_intensity_single_class,
    reaction_velocities,
    slope_coefficient,
    wind_coefficient,
)

# Session 1 compatibility: `reaction_intensity` was the single-class form.
reaction_intensity = reaction_intensity_single_class

# Fuel-model data structures and registries
from .fuel_model import (
    ANDERSON_13,
    FUEL_MODELS,
    FuelCategory,
    FuelClass,
    FuelClassKind,
    FuelModel,
    FuelModelRegistry,
    KOREAN_PINUS,
    MultiClassFuelModel,
    REGISTRY,
)

# Spread engines
from .spread import (
    SpreadResult,
    compute_multi_class_spread_rate,
    compute_single_class_spread_rate,
    compute_spread_rate,
    rate_of_spread,
)


__all__ = [
    # constants
    "PARTICLE_DENSITY_LB_FT3",
    # equations
    "bulk_density",
    "packing_ratio",
    "optimum_packing_ratio",
    "mineral_damping_coefficient",
    "moisture_damping_coefficient",
    "reaction_velocities",
    "reaction_intensity",                  # back-compat alias
    "reaction_intensity_single_class",
    "reaction_intensity_multi_class",
    "propagating_flux_ratio",
    "wind_coefficient",
    "slope_coefficient",
    "effective_heating_number",
    "heat_of_preignition",
    "live_moisture_of_extinction_burgan1979",
    "rate_of_spread",
    # data structures
    "FuelCategory",
    "FuelClassKind",
    "FuelClass",
    "FuelModel",
    "MultiClassFuelModel",
    "FuelModelRegistry",
    # registries
    "FUEL_MODELS",
    "ANDERSON_13",
    "KOREAN_PINUS",
    "REGISTRY",
    # spread engines
    "SpreadResult",
    "compute_spread_rate",
    "compute_single_class_spread_rate",
    "compute_multi_class_spread_rate",
]
