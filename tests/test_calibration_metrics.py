"""Unit tests for the probability-calibration measurement layer.

Two kinds of test:

- **Pure-metric / synthetic tests** (always run, no real data): the Brier / ECE /
  reliability functions, the equal-count binning, the isotonic OOF, the rounded
  JSON assembly and the reliability figure — verified on a synthetic multi-fire
  frame exactly like ``tests/test_ml_baselines.py``.
- **Skip-if-absent regeneration determinism** (the Round-2 P2 deliverable): if
  the committed ``calibration_metrics.json`` AND the (git-ignored) FIRMS bundle
  are present, re-run the production compute path and assert it reproduces the
  committed numbers **byte-for-byte under the fixed seed**. Skips otherwise (the
  normal case in a fresh clone), so the suite stays green without the data.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from wildfireguardian.spread_v2.features import FEATURE_COLUMNS
from wildfireguardian.validation import calibration as cal

REPO = Path(__file__).resolve().parents[1]
COMMITTED_JSON = REPO / "data" / "processed" / "calibration_metrics.json"
SCRIPT = REPO / "scripts" / "calibration_metrics.py"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _synthetic_ds(n_fires: int = 4, n_per: int = 300, seed: int = 0) -> pd.DataFrame:
    """Multi-fire frame with a latent ignition probability (rare positives)."""
    rng = np.random.default_rng(seed)
    rows = []
    for f in range(n_fires):
        lin = rng.normal(0, 1, n_per)
        pz = 1.0 / (1.0 + np.exp(-(lin - 2.2)))  # ~10% base rate
        y = (rng.random(n_per) < pz).astype(int)
        data = {c: rng.normal(0, 1, n_per) for c in FEATURE_COLUMNS}
        data["dist_to_fire_m"] = np.abs(-lin * 500 + rng.normal(0, 200, n_per))
        data["days_since_rain"] = lin + rng.normal(0, 0.3, n_per)
        df = pd.DataFrame(data)
        df["label"] = y
        df["fire_id"] = f"fire_{f}"
        df["dist_band"] = np.where(df["dist_to_fire_m"] > 3000, "far", "near")
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def _load_script():
    spec = importlib.util.spec_from_file_location("calibration_metrics_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# equal-count binning
# ---------------------------------------------------------------------------


def test_equal_count_bins_are_equal_sized_and_robust_to_ties():
    rng = np.random.default_rng(1)
    p = rng.beta(2, 30, 3001)  # skewed toward 0, like the rare-positive regime
    b = cal.equal_count_bin_ids(p, 15)
    counts = np.bincount(b, minlength=15)
    assert b.min() == 0 and b.max() == 14
    assert counts.max() - counts.min() <= 1  # equal-count up to remainder

    # heavy ties (half the mass identical) must still yield 15 usable bins
    p_ties = np.concatenate([np.zeros(1500), rng.random(1500)])
    bt = cal.equal_count_bin_ids(p_ties, 15)
    assert set(np.unique(bt)) == set(range(15))
    ct = np.bincount(bt, minlength=15)
    assert ct.max() - ct.min() <= 1


# ---------------------------------------------------------------------------
# Brier / ECE / reliability correctness
# ---------------------------------------------------------------------------


def test_brier_matches_definition():
    y = np.array([0, 1, 1, 0])
    p = np.array([0.1, 0.9, 0.8, 0.3])
    assert cal.brier(y, p) == pytest.approx(np.mean((p - y) ** 2))


def test_ece_small_for_well_calibrated_large_bins():
    # 15 bins, each a constant prediction v_k with observed freq == v_k.
    g = 1000
    vals = np.linspace(0.02, 0.9, 15)
    p, y = [], []
    for v in vals:
        p.append(np.full(g, v))
        k = int(round(v * g))
        yy = np.zeros(g, dtype=int)
        yy[:k] = 1
        y.append(yy)
    p = np.concatenate(p)
    y = np.concatenate(y)
    ece = cal.expected_calibration_error(y, p, 15)
    assert ece < 1.0 / g + 1e-9  # rounding error only


def test_ece_detects_gross_miscalibration():
    rng = np.random.default_rng(3)
    y = (rng.random(5000) < 0.1).astype(int)   # 10% base rate
    p = np.full(5000, 0.5)                      # confidently wrong
    assert cal.expected_calibration_error(y, p, 15) > 0.3


def test_reliability_table_columns_and_length():
    ds = _synthetic_ds()
    oof = ds[["fire_id", "label"]].copy()
    rng = np.random.default_rng(4)
    oof["prob"] = np.clip(0.1 + 0.05 * rng.normal(size=len(oof)), 0, 1)
    rel = cal.reliability_table(oof["label"].to_numpy(), oof["prob"].to_numpy(), 15)
    assert len(rel) == 15
    for row in rel:
        assert set(row) == {"bin", "n", "positives", "mean_pred", "obs_freq", "p_lo", "p_hi"}
        assert 0.0 <= row["obs_freq"] <= 1.0


# ---------------------------------------------------------------------------
# determinism of the pure metric layer
# ---------------------------------------------------------------------------


def test_metric_functions_are_deterministic():
    rng = np.random.default_rng(5)
    y = (rng.random(4000) < 0.15).astype(int)
    p = np.clip(rng.beta(2, 12, 4000), 0, 1)
    assert cal.brier(y, p) == cal.brier(y, p)
    assert cal.expected_calibration_error(y, p, 15) == cal.expected_calibration_error(y, p, 15)
    assert cal.reliability_table(y, p, 15) == cal.reliability_table(y, p, 15)


def test_calibration_report_structure():
    ds = _synthetic_ds()
    oof = ds[["fire_id", "label", "dist_band"]].copy()
    rng = np.random.default_rng(6)
    oof["prob"] = np.clip(0.1 + 0.05 * rng.normal(size=len(oof)), 0, 1)
    rep = cal.calibration_report(oof, n_bins=15)
    assert set(rep) == {"pooled", "per_fold", "reliability"}
    assert set(rep["pooled"]) == {"n", "positives", "base_rate", "brier", "ece"}
    assert set(rep["per_fold"]["folds"]) == set(oof["fire_id"].unique())
    assert len(rep["reliability"]) == 15


# ---------------------------------------------------------------------------
# rounded JSON assembly
# ---------------------------------------------------------------------------


def test_assemble_metrics_is_rounded_and_deterministic():
    ds = _synthetic_ds()
    oof = ds[["fire_id", "label", "dist_band"]].copy()
    rng = np.random.default_rng(7)
    oof["prob"] = np.clip(0.1 + 0.05 * rng.normal(size=len(oof)), 0, 1)
    rep = {"hist_gbm": cal.calibration_report(oof)}
    iso = {"raw": {"pooled_brier": 0.123456789}, "post": {"pooled_brier": 0.111}}
    a = cal.assemble_metrics(rep, iso, meta={"dataset": {"n_rows": len(ds)}}, ndigits=6)
    b = cal.assemble_metrics(rep, iso, meta={"dataset": {"n_rows": len(ds)}}, ndigits=6)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    # rounding actually applied
    assert a["supplementary_isotonic_gbm"]["raw"]["pooled_brier"] == 0.123457


def test_round_floats_handles_nan_and_numpy():
    out = cal.round_floats({"a": np.float64(1.0 / 3.0), "b": float("nan"),
                            "c": np.int64(5), "d": [np.float32(0.5), "x"]}, 4)
    assert out["a"] == 0.3333
    assert out["b"] is None            # non-finite → null (JSON-safe)
    assert out["c"] == 5 and isinstance(out["c"], int)
    assert out["d"] == [0.5, "x"]


# ---------------------------------------------------------------------------
# supplementary isotonic (trains the real GBM on synthetic data)
# ---------------------------------------------------------------------------


def test_isotonic_oof_gbm_deterministic_and_valid():
    ds = _synthetic_ds(n_fires=4, n_per=250, seed=8)
    a = cal.isotonic_oof_gbm(ds, seed=20250603, n_splits=3)
    b = cal.isotonic_oof_gbm(ds, seed=20250603, n_splits=3)
    assert list(a.columns) == ["fire_id", "label", "prob_raw", "prob_iso"]
    assert (a["prob_iso"].to_numpy() >= 0).all() and (a["prob_iso"].to_numpy() <= 1).all()
    # calibrated probabilities are reproducible under the fixed seed
    assert np.allclose(a["prob_iso"].to_numpy(), b["prob_iso"].to_numpy())
    summ = cal.isotonic_summary(a)
    assert {"raw", "post", "delta", "reliability_post", "note"} <= set(summ)


# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------


def test_make_reliability_figure_writes_png(tmp_path):
    ds = _synthetic_ds()
    models = {}
    rng = np.random.default_rng(9)
    for name in ("hist_gbm", "random_forest", "logistic"):
        oof = ds[["fire_id", "label"]].copy()
        oof["prob"] = np.clip(0.1 + 0.05 * rng.normal(size=len(oof)), 0, 1)
        models[name] = cal.calibration_report(oof)
    out = tmp_path / "reliability.png"
    cal.make_reliability_figure(models, out)
    assert out.exists() and out.stat().st_size > 1000


# ---------------------------------------------------------------------------
# SKIP-IF-ABSENT — regeneration determinism (Round-2 P2 deliverable, task 7)
# ---------------------------------------------------------------------------


def test_calibration_metrics_regenerates_deterministically():
    """If the committed metrics AND the FIRMS bundle are present, the production
    compute path must reproduce ``calibration_metrics.json`` exactly under the
    fixed seed (and be stable across two runs). Skips when either is absent."""
    from wildfireguardian.spread_v2 import data, features

    if not COMMITTED_JSON.exists():
        # ⚠ Say WHY it is absent truthfully. The old parenthesis blamed the
        # bundle, which was present on the machine where this skip fired for
        # months — the artifact had simply never been generated, and the wrong
        # reason sent readers to the wrong remedy (Round-4 A1-2).
        pytest.skip("data/processed/calibration_metrics.json has not been "
                    "generated/committed (run scripts/calibration_metrics.py "
                    "where the FIRMS/ERA5/DEM bundle is present)")
    if not data.data_available():
        pytest.skip("FIRMS/ERA5/DEM bundle absent — cannot rebuild OOF to check "
                    "regeneration determinism")

    committed = json.loads(COMMITTED_JSON.read_text())
    seed = committed["seed"]
    n_bins = committed["binning"]["n_bins"]

    script = _load_script()
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=500.0, buffer_m=6000.0)

    regen = script.compute_payload(ds, seed=seed, n_bins=n_bins)["payload"]
    regen2 = script.compute_payload(ds, seed=seed, n_bins=n_bins)["payload"]

    # deterministic across runs, and reproduces the committed numbers
    assert regen == regen2, "compute_payload is not deterministic under the fixed seed"
    assert regen["models"] == committed["models"], "model calibration metrics drifted"
    assert regen["supplementary_isotonic_gbm"] == committed["supplementary_isotonic_gbm"]
    assert regen["dataset"] == committed["dataset"]
