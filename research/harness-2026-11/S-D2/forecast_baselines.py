"""Thin import shim: forecast/wildfire/baselines.py (no sklearn needed until the logistic is fitted)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "forecast"))
from wildfire.baselines import choose_dilation, dilation, fit_logistic, predict_logistic  # noqa: E402,F401
