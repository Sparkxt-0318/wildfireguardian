"""Instance generators. Everything they produce is SYNTHETIC and labelled so.

* :mod:`evacplan.generators.synthetic`: road graph + care facilities + fleet + shelters + a
  ``hazard_contract.synthetic`` fire that threatens the facilities, deterministic from
  ``(size, tightness, graph, seed)``.
* :mod:`evacplan.generators.graphs`: the grid and random geometric road layouts.

Real regions (OSM roads, CMS facilities, observed perimeters) are built by :mod:`evacplan.regions`.
"""
from .synthetic import (
    GENERATOR, GENERATOR_VERSION, LABEL, SIZES, GeneratedInstance, SyntheticConfig, generate, summary,
    tightness_params,
)

__all__ = ["GENERATOR", "GENERATOR_VERSION", "LABEL", "SIZES", "GeneratedInstance", "SyntheticConfig", "generate",
           "summary", "tightness_params"]
