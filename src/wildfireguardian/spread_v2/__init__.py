"""spread_v2 — the data-driven, per-cell next-overpass ignition model.

Built (this session) from the real Korean FIRMS + ERA5 + DEM + WorldCover
dataset to predict, for each ~0.5 km cell, P(detected as burning by the next
satellite overpass). It is the probabilistic hazard the evacuation router
consumes (see :mod:`wildfireguardian.routing`).

Pipeline
--------
``data``        load FIRMS detections / DEM / fuel / ERA5 per fire (+ provenance)
``grid``        coarse EPSG:5179 grid; reproject layers; cluster overpasses
``weather``     ERA5 -> fire-weather-severity features (dryness, RH, VPD, wind)
``features``    per-cell supervised rows for overpass transitions
``model``       gradient-boosted classifier + leave-one-fire-out validation
``forward_sim`` iterate the model into a time-sequenced hazard surface

Honesty notes
-------------
- FIRMS is a *detection* product, not a burn-scar map; labels are an observed
  lower bound and the coarse cell footprint over-counts area.
- Fire-weather severity is spatially ~uniform at ERA5's 0.25 deg resolution,
  so it sets the *magnitude* of the reach across days/fires while the
  geometry/terrain features place it spatially.
- Forward simulation compounds error each step.
"""

from __future__ import annotations

__all__ = ["data", "grid", "weather", "features", "model", "forward_sim"]
