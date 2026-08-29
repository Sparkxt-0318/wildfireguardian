"""Arm D — observed fire-front assimilation features for spread_v2.

**This package is EXPERIMENTAL and ADDITIVE. It does not modify Arm A.**

Arm A (the frozen configuration the 본선 posters cite) predicts the next
overpass from weather, terrain, fuel and geometry alone. Arm D asks a different
question: if the system is allowed to look at *the fire's own observed
progression so far*, does that make the next step more predictable?

The idea follows data-assimilation practice in wildfire spread forecasting,
where observed front positions are used to correct a running forecast rather
than only to score it after the fact (Rochoux et al. 2014, *NHESS* 14:1721-1740).

The FIRMS bundle already merges VIIRS_SNPP + VIIRS_NOAA20 + MODIS, so a fire is
observed roughly 4-6 times a day. Sub-daily observed progression is therefore
available from data already in the repository, with no new acquisition.

THE LEAKAGE RULE
----------------
Every Arm D feature for a prediction made at time ``t`` is computed **only from
overpasses whose timestamp is strictly earlier than ``t``**. At transition
``k -> k+1`` the prediction time is ``overpasses[k].time``, so Arm D may read
overpasses ``0 .. k-1`` and nothing else. Overpass ``k`` itself is excluded even
though Arm A legitimately uses its mask as the model's current-state input: the
point of Arm D is to measure what *history* adds, and the cheapest way to make
that measurement trustworthy is to give the history features no access to the
present at all.

This is enforced by :func:`prior_observation_features`, which slices the
overpass list before touching it, and is tested in
``tests/test_arm_d_leakage.py``. An assimilation model with leakage looks
spectacular and is worthless, so those tests gate the arm.
"""

from .features import (
    ARM_D_FEATURE_COLUMNS,
    ARM_D_PERSISTENCE_N,
    ARM_D_PERSISTENCE_RADIUS_M,
    prior_observation_features,
)

__all__ = [
    "ARM_D_FEATURE_COLUMNS",
    "ARM_D_PERSISTENCE_N",
    "ARM_D_PERSISTENCE_RADIUS_M",
    "prior_observation_features",
]
