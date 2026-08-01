"""Live Fuel Moisture Content (LFMC) retrieval.

# forbidden-ok: XGBoost
Session 3 adds a methodology scaffold: the feature engineering + XGBoost
regression structure from Rao et al. (2020) / Wang et al. (2019),
demonstrated on a CLEARLY-LABELLED synthetic training set. Real
Sentinel-1/2 + MODIS ingestion and Korean field-LFMC labels are Round 2.

See :mod:`.retrieval` and ``docs/methodology/lfmc.md``.
"""

from __future__ import annotations

from .retrieval import (
    FEATURE_NAMES,
    LFMCRetrievalModel,
    demo_train_synthetic,
    generate_synthetic_training_set,
)

__all__ = [
    "FEATURE_NAMES",
    "LFMCRetrievalModel",
    "generate_synthetic_training_set",
    "demo_train_synthetic",
]
