"""Whole-fire bootstrap on SYNTHETIC fires: agreement with wildfire.baselines and whole-fire behaviour."""
import numpy as np
import pytest
from wildfire import baselines

from firecast_lab import metrics as m


def _fires(seed, n_fires=8, size=300, edge=0.0):
    """SYNTHETIC entries: outcome, a candidate forecast, a reference forecast, fire ids."""
    rng = np.random.default_rng(seed)
    fire = np.repeat([f"SYNTHETIC_{i}" for i in range(n_fires)], size)
    rate = np.repeat(rng.uniform(0.02, 0.3, n_fires), size)
    y = (rng.random(fire.size) < rate).astype(float)
    reference = np.clip(rate + rng.normal(0, 0.05, fire.size), 0, 1)
    candidate = np.clip(reference + edge * (y - reference) + rng.normal(0, 0.02, fire.size), 0, 1)
    return fire, y, candidate, reference


def test_generic_bootstrap_reproduces_paired_fire_bootstrap():
    fire, y, c, r = _fires(0)
    expected = baselines.paired_fire_bootstrap(fire, y, c, r, draws=2000, seed=11)
    terms = np.stack([(c - y) ** 2 - (r - y) ** 2, np.ones_like(y)], axis=1)
    got = m.fire_bootstrap(fire, terms, lambda s: s[..., 0] / s[..., 1], draws=2000, seed=11)
    assert got["point"] == pytest.approx(expected["point_difference"], rel=1e-12)
    assert got["interval"] == pytest.approx(expected["percentile_95_interval"], rel=1e-9)
    assert got["excludes_zero"] == expected["excludes_zero"] and got["fires"] == expected["fires"] == 8
    wrapped = m.paired_brier_bootstrap(fire, y, c, r, np.ones(y.size, bool), draws=2000, seed=11)
    assert wrapped["percentile_95_interval"] == expected["percentile_95_interval"]


def test_one_fire_gives_a_degenerate_interval():
    fire, y, c, r = _fires(1, n_fires=1)
    out = m.brier_skill_bootstrap(fire, y, c, r, np.ones(y.size, bool), draws=500)
    assert out["interval"][0] == pytest.approx(out["point"]) and out["interval"][1] == pytest.approx(out["point"])


def test_repeating_windows_inside_fires_does_not_narrow_the_interval():
    fire, y, c, r = _fires(2)
    mask = np.ones(y.size, bool)
    once = m.brier_skill_bootstrap(fire, y, c, r, mask, draws=1000, seed=3)
    twice = m.brier_skill_bootstrap(np.tile(fire, 3), np.tile(y, 3), np.tile(c, 3), np.tile(r, 3),
                                    np.ones(3 * y.size, bool), draws=1000, seed=3)
    assert twice["interval"] == pytest.approx(once["interval"]) and twice["point"] == pytest.approx(once["point"])


@pytest.mark.parametrize("edge", [0.5, -0.5])
def test_skill_and_brier_difference_agree_on_the_decision(edge):
    fire, y, c, r = _fires(4, edge=edge)
    mask = np.ones(y.size, bool)
    skill = m.brier_skill_bootstrap(fire, y, c, r, mask, draws=3000, seed=5)
    diff = m.paired_brier_bootstrap(fire, y, c, r, mask, draws=3000, seed=5)
    assert skill["point"] == pytest.approx(m.brier_skill(y, c, r, mask))
    assert skill["excludes_zero"] and diff["excludes_zero"]
    assert (skill["point"] > 0) == (diff["point_difference"] < 0) == (edge > 0)


def test_masked_entries_are_not_scored_and_undefined_draws_are_counted():
    fire, y, c, r = _fires(5, n_fires=2)
    keep = np.ones(y.size, bool)
    y2 = y.copy()
    y2[:10], keep[:10] = np.nan, False
    a = m.brier_skill_bootstrap(fire, y2, c, r, keep, draws=500, seed=1)
    b = m.brier_skill_bootstrap(fire[10:], y[10:], c[10:], r[10:], np.ones(y.size - 10, bool), draws=500, seed=1)
    assert a == b
    # Fire 1 has no positives and a perfect reference: draws holding only fire 1 have an undefined skill.
    y3, r3 = y.copy(), r.copy()
    y3[fire == "SYNTHETIC_1"], r3[fire == "SYNTHETIC_1"] = 0.0, 0.0
    out = m.brier_skill_bootstrap(fire, y3, c, r3, np.ones(y.size, bool), draws=2000, seed=2)
    assert 300 < out["undefined_draws"] < 700 and np.isfinite(out["interval"]).all()   # about 1 in 4


def test_fire_ids_must_match_the_entries():
    fire, y, c, r = _fires(6, n_fires=2)
    with pytest.raises(ValueError, match="fire id"):
        m.brier_skill_bootstrap(fire[:-1], y, c, r, np.ones(y.size, bool))
    with pytest.raises(ValueError, match="fire id"):
        m.paired_brier_bootstrap(fire[:-1], y, c, r, np.ones(y.size, bool))
