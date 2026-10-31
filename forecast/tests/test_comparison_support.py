"""Unknown long-horizon support must survive reporting as unavailable."""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np


def summary_function():
    path = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/pipeline.py"
    spec = importlib.util.spec_from_file_location("comparison_support_fixture", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.compare_fields


def test_empty_shared_support_is_unavailable_not_zero_rmse_or_brier():
    result = summary_function()(np.full((2, 2), np.nan), np.full((2, 2), np.nan),
                                np.zeros((2, 2), bool), np.zeros((2, 2)))
    assert result["status"] == "UNAVAILABLE_SHARED_SUPPORT"
    assert result["reference_status"] == "UNAVAILABLE_REFERENCE_SUPPORT"
    assert result["rmse_all"] is None
    assert result["brier_mc"] is None
    json.dumps(result, allow_nan=False)


def test_finite_field_with_no_reference_has_rmse_but_no_brier():
    result = summary_function()(np.array([[.2]]), np.array([[.3]]), np.ones((1, 1), bool),
                                np.array([[np.nan]]), np.zeros((1, 1), bool))
    assert abs(result["rmse_all"] - .1) < 1e-12
    assert result["reference_status"] == "UNAVAILABLE_REFERENCE_SUPPORT"
    assert result["brier_mc"] is None
