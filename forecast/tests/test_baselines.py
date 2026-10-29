"""Perimeter baselines and fire-paired scoring."""
import numpy as np

from wildfire.baselines import (
    choose_dilation, dilation, hand_features, paired_fire_bootstrap, persistence, score,
)


def _planar_front(hours, width=30, start=5):
    initial = np.broadcast_to(np.arange(width)[None, :] < start, (20, width)).copy()
    later = np.broadcast_to(np.arange(width)[None, :] < start + hours, (20, width)).copy()
    return initial, later


def test_dilation_one_cell_per_hour_on_planar_front_has_zero_brier():
    for hours in (1, 3, 7):
        initial, later = _planar_front(hours)
        forecast = dilation(initial, hours, 1)
        cells = ~initial
        result = score(later[cells].astype(float), forecast[cells])
        assert result["brier"] == 0.0
        assert result["positives"] == 20 * hours
    initial, later = _planar_front(4)
    slow = dilation(initial, 4, 2)
    assert score(later[~initial].astype(float), slow[~initial])["brier"] > 0


def test_persistence_brier_is_prevalence_and_skill_definition():
    y = np.array([0, 0, 1, 0], dtype=float)
    result = score(y, persistence(y))
    assert result["brier"] == 0.25 and result["bss_vs_persistence"] == 0.0
    assert score(y, y)["bss_vs_persistence"] == 1.0
    assert score(y, np.array([0.1, 0.2, 0.9, 0.3]))["average_precision"] == 1.0


def test_paired_bootstrap_resamples_fires():
    fire = np.repeat(np.arange(4), 50)
    y = (np.random.default_rng(0).random(200) < 0.2).astype(float)
    good = np.clip(y * 0.8 + 0.05, 0, 1)
    bad = np.full(200, 0.2)
    result = paired_fire_bootstrap(fire, y, good, bad, draws=500)
    assert result["fires"] == 4 and result["excludes_zero"] and result["point_difference"] < 0
    assert set(result["per_fire_difference"]) == {"0", "1", "2", "3"}


def test_hand_features_alignment_and_choice():
    initial = np.zeros((5, 5), bool)
    initial[2, 2] = True
    u, v = np.full((5, 5), 3.0), np.zeros((5, 5))
    features = hand_features(initial, 6.0, u, v, np.zeros((5, 5)), None, [])
    alignment = features[:, 2].reshape(5, 5)
    assert alignment[2, 4] == 1.0 and alignment[2, 0] == -1.0
    assert choose_dilation({1: 0.2, 2: 0.1, 4: 0.1, 8: 0.3}) == 4
