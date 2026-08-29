"""Arm D leakage gate — these tests exist to be run BEFORE any Arm D model is.

Session 10 Phase 4a. An assimilation model that can see the future looks
spectacular and is worthless, and it is exactly the failure a technical judge
probes first. So the guarantee is asserted mechanically rather than argued:

1. a feature computed at time ``t`` is bit-identical whether or not
   observations at or after ``t`` exist in the input;
2. shuffling all future observations leaves every Arm D feature unchanged;
3. a case whose answer is knowable only from a future observation yields no
   predictive advantage.

If any of these fail, Arm D stops. They use synthetic overpasses so they run
without the FIRMS/ERA5/DEM bundle and can never be skipped into vacuity.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wildfireguardian.spread_v2.grid import Overpass
from wildfireguardian.spread_v2_armd import (
    ARM_D_FEATURE_COLUMNS,
    prior_observation_features,
)

CELL_M = 500.0
SHAPE = (24, 24)
T0 = pd.Timestamp("2025-03-22 03:00:00")


def _disc(center_rc, radius_cells, shape=SHAPE) -> np.ndarray:
    rr, cc = np.ogrid[: shape[0], : shape[1]]
    return ((rr - center_rc[0]) ** 2 + (cc - center_rc[1]) ** 2) <= radius_cells**2


def _overpass(index: int, hours: float, cumulative: np.ndarray,
              previous: np.ndarray | None) -> Overpass:
    new = cumulative & ~previous if previous is not None else cumulative.copy()
    return Overpass(
        index=index,
        time=T0 + pd.Timedelta(hours=hours),
        new_mask=new,
        cumulative_mask=cumulative.copy(),
        n_detections=int(cumulative.sum()),
    )


def _eastward_series(n: int = 6) -> list[Overpass]:
    """A fire whose observed front marches steadily east, 4 h between looks."""
    ops: list[Overpass] = []
    prev: np.ndarray | None = None
    for i in range(n):
        cum = _disc((12, 6 + i), 2 + 0.5 * i)
        ops.append(_overpass(i, 4.0 * i, cum, prev))
        prev = cum
    return ops


def _candidates() -> tuple[np.ndarray, np.ndarray]:
    rr, cc = np.meshgrid(np.arange(SHAPE[0]), np.arange(SHAPE[1]), indexing="ij")
    return rr.ravel(), cc.ravel()


def _features(ops, k):
    rows, cols = _candidates()
    return prior_observation_features(ops, k, rows, cols, cell_size_m=CELL_M)


def _assert_identical(a: dict, b: dict, why: str) -> None:
    assert set(a) == set(b) == set(ARM_D_FEATURE_COLUMNS), "feature set changed"
    for name in ARM_D_FEATURE_COLUMNS:
        # equal_nan: an undefined feature must stay undefined, not become a value.
        assert np.array_equal(a[name], b[name], equal_nan=True), (
            f"{why}: Arm D feature {name!r} changed")


# ---------------------------------------------------------------------------
# 1. Truncation invariance — the future may simply not exist yet.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("k", [0, 1, 2, 3, 4, 5])
def test_features_are_identical_when_the_future_does_not_exist(k):
    """Deleting every observation after t must change nothing at t.

    This is the operational case: at prediction time the later overpasses have
    not happened. If a feature moves when they are removed, the offline number
    was computed with information the live system will not have.
    """
    ops = _eastward_series()
    full = _features(ops, k)
    truncated = _features(ops[: k + 1], k)
    _assert_identical(full, truncated, f"k={k}: truncating the future")


def test_the_present_overpass_mask_is_not_read_either():
    """Overpass k is AT t, not before it, so its mask must not be an input.

    Only its timestamp defines the prediction time. Corrupting its mask while
    holding its time fixed must leave every Arm D feature untouched.
    """
    ops = _eastward_series()
    k = 4
    before = _features(ops, k)

    rng = np.random.default_rng(20250603)
    corrupted = list(ops)
    corrupted[k] = Overpass(
        index=ops[k].index,
        time=ops[k].time,                       # the one thing that may be read
        new_mask=rng.random(SHAPE) < 0.5,
        cumulative_mask=rng.random(SHAPE) < 0.5,
        n_detections=999999,
    )
    _assert_identical(before, _features(corrupted, k), "corrupting overpass k")


# ---------------------------------------------------------------------------
# 2. Shuffle invariance — the future may be arbitrary.
# ---------------------------------------------------------------------------


def test_shuffling_all_future_observations_changes_nothing():
    """Permute every observation after t; the features at t must not move."""
    ops = _eastward_series()
    k = 3
    before = _features(ops, k)

    rng = np.random.default_rng(20250603)
    tail = ops[k + 1:]
    for _ in range(8):
        shuffled = ops[: k + 1] + list(rng.permutation(np.array(tail, dtype=object)))
        _assert_identical(before, _features(shuffled, k), "shuffling the future")


def test_replacing_the_future_with_noise_changes_nothing():
    """A stronger form: the future is not merely reordered, it is fabricated."""
    ops = _eastward_series()
    k = 2
    before = _features(ops, k)

    rng = np.random.default_rng(7)
    fabricated = ops[: k + 1] + [
        _overpass(j, 4.0 * j, rng.random(SHAPE) < 0.3, None)
        for j in range(k + 1, len(ops))
    ]
    _assert_identical(before, _features(fabricated, k), "fabricating the future")


# ---------------------------------------------------------------------------
# 3. No predictive advantage from a future-only signal.
# ---------------------------------------------------------------------------


def test_a_future_only_answer_confers_no_advantage():
    """Two worlds identical up to t, with opposite labels decided after t.

    The label is knowable only from the future observation. If Arm D features
    carried any trace of it they would differ between the two worlds; because
    they are bit-identical, any classifier consuming them assigns both worlds
    the same probability, and the achievable AUC is exactly chance. Asserting
    the features rather than a trained model's score makes this deterministic
    instead of a question about how much noise a fitted model happened to find.
    """
    shared = _eastward_series(4)
    k = 3

    world_east = shared + [_overpass(4, 16.0, _disc((12, 16), 5), shared[-1].cumulative_mask)]
    world_west = shared + [_overpass(4, 16.0, _disc((12, 2), 5), shared[-1].cumulative_mask)]

    fe, fw = _features(world_east, k), _features(world_west, k)
    _assert_identical(fe, fw, "worlds differing only after t")

    # And the consequence, stated the way the model would experience it.
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    X = np.column_stack([fe[c] for c in ARM_D_FEATURE_COLUMNS])
    X = np.vstack([X, np.column_stack([fw[c] for c in ARM_D_FEATURE_COLUMNS])])
    y = np.r_[np.ones(len(fe["obs_alignment"])), np.zeros(len(fw["obs_alignment"]))]

    clf = HistGradientBoostingClassifier(random_state=20250603, max_iter=50).fit(X, y)
    auc = roc_auc_score(y, clf.predict_proba(X)[:, 1])
    assert auc == pytest.approx(0.5, abs=1e-12), (
        f"future-only label became learnable from Arm D features (AUC {auc})")


def test_arm_d_never_invents_a_value_for_a_cold_start():
    """At k=0 there is no history. Every feature must be NaN except the count.

    Filling these with zeros would be the quiet version of the leakage bug: a
    fabricated observation is still an observation the system did not have.
    """
    f = _features(_eastward_series(), 0)
    assert np.all(f["n_prior_overpasses"] == 0.0)
    for name in ARM_D_FEATURE_COLUMNS:
        if name == "n_prior_overpasses":
            continue
        assert np.all(np.isnan(f[name])), f"{name} was filled in at a cold start"
