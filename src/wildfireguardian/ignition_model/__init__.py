"""Data-driven per-cell ignition-probability model for Korean wildfires.

See :mod:`wildfireguardian.ignition_model.config` for the scientific framing.
The pipeline runs in deliverable order:

* :mod:`.audit`     -- Deliverable 0: data audit (incl. yeongdeok fuel check)
* :mod:`.grid`      -- Deliverable 1: projected grid, overpasses, burned masks
* :mod:`.features`  -- Deliverable 2: per-candidate-cell feature extraction
* :mod:`.model`     -- Deliverables 3-5: XGBoost, leave-one-fire-out CV,
                        baselines, conditional-by-distance AUC, importances
"""

from __future__ import annotations

from .config import PipelineConfig

__all__ = ["PipelineConfig"]
