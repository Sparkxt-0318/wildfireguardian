# forbidden-ok: XGBoost
"""LFMC retrieval — feature engineering + XGBoost regression (methodology scaffold).

This module implements the END-TO-END structure of a Live Fuel Moisture
Content (LFMC) retrieval model for Korean pine forests, following the
published methodology of Rao et al. (2020) and Wang et al. (2019). It is
a **methodology scaffold**: real Sentinel-1 SAR + Sentinel-2 optical +
MODIS NDVI data ingestion is Round 2 work.

For demonstration, the module:

1. Defines the feature set published in the LFMC retrieval literature.
2. Generates a clearly-labelled **synthetic** training dataset that
   mimics the published feature → LFMC relationships.
# forbidden-ok: XGBoost
3. Trains an XGBoost regressor on the synthetic data.
4. Reports feature importances as a methodology illustration.

**The trained model in this module is NOT a real Korean LFMC retrieval
# forbidden-ok: XGBoost
model.** It is the same XGBoost regression you would use for a real
deployment, fitted on synthetic data. Replacing the synthetic dataset
with real Sentinel-1/2 + MODIS observations and field LFMC labels
recovers the production pipeline without changing call sites.

Features used
-------------

Per Rao et al. 2020 "SAR-enhanced LFMC retrieval" (DOI: 10.1016/j.rse.2020.111797):

- ``sar_vv_db``     — Sentinel-1 VV polarisation backscatter (dB)
- ``sar_vh_db``     — Sentinel-1 VH polarisation backscatter (dB)
- ``vh_vv_ratio``   — VH/VV ratio (proxy for biomass moisture)
- ``ndvi``          — MODIS / Sentinel-2 NDVI
- ``ndmi``          — Normalised Difference Moisture Index (B8 - B11) / (B8 + B11)
- ``precip_acc_30d``— accumulated precipitation, 30-day window (mm)
- ``elevation_m``   — terrain altitude
- ``slope_deg``     — terrain slope
- ``aspect_deg``    — terrain aspect
- ``forest_type_code`` — KFS 임상도 stand-species code (or 1 = Pinus densiflora here)

References
----------
- Rao, K., Williams, A.P., Flefil, J.F., Konings, A.G. (2020). *SAR-enhanced
  mapping of live fuel moisture content.* Remote Sens. Environ. 245: 111797.
- Wang, L., Quan, X., He, B., Yebra, M. et al. (2019). *Estimation of live
  fuel moisture content from MODIS measurements...* Remote Sens. 11(7): 858.
- Yebra, M. et al. (2018). *Globe-LFMC, a global plant water content
  database for vegetation models.* Sci. Data 6: 155.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np


FEATURE_NAMES: Final[tuple[str, ...]] = (
    "sar_vv_db",
    "sar_vh_db",
    "vh_vv_ratio",
    "ndvi",
    "ndmi",
    "precip_acc_30d",
    "elevation_m",
    "slope_deg",
    "aspect_deg",
    "forest_type_code",
)


@dataclass
class LFMCRetrievalModel:
    # forbidden-ok: XGBoost
    """Wrapper around an XGBoost regressor for LFMC retrieval.

    Attributes
    ----------
    model : xgboost.Booster | None
        # forbidden-ok: XGBoost
        The trained XGBoost model. ``None`` before :meth:`fit` is called.
    feature_names : tuple[str, ...]
        Order of features expected by the model.
    feature_importances_ : dict[str, float]
        Populated after :meth:`fit`.
    metadata : dict
        Provenance metadata — synthetic vs real, training-set size, etc.
    """

    feature_names: tuple[str, ...] = FEATURE_NAMES
    model: object | None = None
    feature_importances_: dict[str, float] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def fit(self, X: np.ndarray, y: np.ndarray, **xgb_kwargs) -> "LFMCRetrievalModel":
        # forbidden-ok: XGBoost
        """Train the underlying XGBoost regressor.

        Parameters
        ----------
        X : np.ndarray, shape (N, n_features)
            Feature matrix; columns must match ``feature_names``.
        y : np.ndarray, shape (N,)
            LFMC labels (% of dry mass).
        **xgb_kwargs
            Passed through to ``xgb.XGBRegressor``.
        """
        try:
            import xgboost as xgb
        except ImportError:  # pragma: no cover
            raise ImportError(
                "LFMCRetrievalModel.fit requires xgboost. "
                "Install via `pip install xgboost`."
            ) from None
        if X.shape[1] != len(self.feature_names):
            raise ValueError(
                f"feature dim mismatch: X has {X.shape[1]} cols, "
                f"expected {len(self.feature_names)}"
            )
        defaults = dict(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            objective="reg:squarederror", random_state=42,
        )
        defaults.update(xgb_kwargs)
        booster = xgb.XGBRegressor(**defaults)
        booster.fit(X, y)
        self.model = booster
        # Importance by gain (default)
        importances = booster.feature_importances_
        self.feature_importances_ = {
            name: float(imp)
            for name, imp in zip(self.feature_names, importances)
        }
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict LFMC for a feature matrix."""
        if self.model is None:
            raise RuntimeError("model not fitted; call .fit() first")
        return np.asarray(self.model.predict(X), dtype=np.float64)

    def save(self, path: Path) -> None:
        """Persist model to JSON (sidecar metadata + xgboost booster)."""
        if self.model is None:
            raise RuntimeError("nothing to save; .fit() first")
        out_dir = Path(path)
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        # forbidden-ok: XGBoost
        # XGBoost saves to .json natively.
        booster_path = out_dir.with_suffix(".xgb.json")
        self.model.save_model(str(booster_path))
        meta = {
            "feature_names": list(self.feature_names),
            "feature_importances": self.feature_importances_,
            "metadata": self.metadata,
            "booster_path": booster_path.name,
        }
        path.write_text(json.dumps(meta, indent=2))


# ---------------------------------------------------------------------------
# Synthetic training-data generator
# ---------------------------------------------------------------------------


def generate_synthetic_training_set(
    n_samples: int = 2000, random_seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Generate a CLEARLY-LABELLED synthetic LFMC training set.

    The synthetic LFMC field is built to mimic the published relationships:

    - LFMC decreases with VH/VV ratio decrease (vegetation drying).
    - LFMC increases with NDMI (more moisture → higher NDMI).
    - LFMC increases with recent precipitation (30-day accumulation).
    - LFMC weakly depends on terrain (slope, aspect — south-facing
      slopes dry faster).

    The synthetic relationship is intentionally noisy (Gaussian σ ≈ 15 %
    on top of the deterministic mean) so feature importances reflect a
    realistic, not over-fit, regression.

    Returns ``(X, y, metadata)`` where ``y`` is LFMC in percent (15-200).
    """
    rng = np.random.default_rng(random_seed)
    N = n_samples

    # Sample features in plausible ranges for Korean Pinus stands.
    sar_vv_db = rng.uniform(-15.0, -5.0, N)
    sar_vh_db = rng.uniform(-22.0, -10.0, N)
    vh_vv_ratio = sar_vh_db - sar_vv_db                      # in dB space, ratio = difference
    ndvi = rng.uniform(0.30, 0.85, N)
    ndmi = rng.uniform(-0.10, 0.55, N)
    precip_acc_30d = rng.uniform(0.0, 200.0, N)              # mm
    elevation_m = rng.uniform(50.0, 900.0, N)
    slope_deg = rng.uniform(0.0, 30.0, N)
    aspect_deg = rng.uniform(0.0, 360.0, N)
    forest_type_code = np.ones(N, dtype=np.float64)          # all Pinus densiflora here

    # Synthetic LFMC formula (clearly NOT a real Korean calibration).
    lfmc = (
        85.0
        + 5.0 * (vh_vv_ratio + 12.0)         # higher VH/VV ratio → wetter
        + 80.0 * ndmi                         # higher NDMI → wetter
        + 25.0 * (ndvi - 0.5)                 # NDVI weakly positive
        + 0.4 * precip_acc_30d                # 200mm in 30d → +80 LFMC
        - 0.05 * elevation_m * 0.0            # near-zero direct elevation effect
        - 0.5 * slope_deg * np.cos(np.radians(aspect_deg - 180.0))  # S-facing dries
    )
    # Inject Gaussian noise.
    lfmc += rng.normal(0.0, 15.0, N)
    # Clip to physical range.
    lfmc = np.clip(lfmc, 15.0, 200.0)

    X = np.column_stack([
        sar_vv_db, sar_vh_db, vh_vv_ratio, ndvi, ndmi,
        precip_acc_30d, elevation_m, slope_deg, aspect_deg, forest_type_code,
    ])
    metadata = {
        "n_samples": N,
        "random_seed": random_seed,
        "synthetic": True,
        "provenance": (
            "SYNTHETIC training set — feature ranges and LFMC formulae "
            "approximate the published Rao et al. 2020 / Wang et al. 2019 "
            "feature-LFMC relationships. NOT real Korean field data. "
            "For methodology demonstration only."
        ),
        "lfmc_range": (float(lfmc.min()), float(lfmc.max())),
        "lfmc_mean": float(lfmc.mean()),
    }
    return X, lfmc, metadata


# ---------------------------------------------------------------------------
# Demonstration runner
# ---------------------------------------------------------------------------


def demo_train_synthetic(n_samples: int = 2000, random_seed: int = 42) -> LFMCRetrievalModel:
    """Train an LFMCRetrievalModel on the synthetic dataset; return it.

    The result's ``.metadata`` is tagged ``synthetic=True`` so downstream
    code can refuse to use it for production predictions.
    """
    X, y, meta = generate_synthetic_training_set(n_samples, random_seed)
    model = LFMCRetrievalModel()
    model.fit(X, y)
    model.metadata = {
        **meta,
        "fitted_on": "SYNTHETIC dataset (NOT real Korean field data)",
        "do_not_use_for_production": True,
    }
    return model


__all__ = [
    "FEATURE_NAMES",
    "LFMCRetrievalModel",
    "generate_synthetic_training_set",
    "demo_train_synthetic",
]
