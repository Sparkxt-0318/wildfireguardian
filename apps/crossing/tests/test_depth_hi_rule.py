"""DEPTH-HI rule (depth.py module docstring, DESIGN 6.6 as built 2026-11-17): the depth upper end the dose uses.

depth.combine() is a log-space GLS mean; its upper end follows the narrowest estimator and fell BELOW the true depth
on the SIMULATED flame_front sample (combined [0.27, 1.4] m, true 3.0 m). The decision upper end ``hi_decision_m``
is therefore at least the largest upper end of the valid non-experimental estimators. The numbers below are
SYNTHETIC estimates; the limits are placeholders.
"""
import json
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossing import decision as dc
from crossing import depth as dp
from crossing.config import load_config
from crossing.depth import DepthResult
from test_decision import FE, NOW, cross_inputs

CAL = dict(calibrated=True, scale=1.0, trust_radar_ceiling=False)


def _est(name, v, s, kind="estimate"):
    return dp._lognormal(name, v, s, kind=kind)


def _cal(n, **kw):
    return SimpleNamespace(**{**CAL, "n_pairs": n, **kw})


# ------------------------------------------------------------------------------------------- max rule
def test_low_narrow_estimator_decision_upper_end_is_byrams_upper_end():
    sb = _est("spread_burn", 0.6, 0.2)              # narrow and low (as on the flame_front sample)
    by = _est("byram", 1.2, 0.8)                     # wide: hi = 1.2 * exp(1.645 * 0.8) = 4.47 m
    r = dp.combine([sb, by])
    assert r.valid
    assert r.hi_m < by.hi_m                          # the combined interval follows the narrow estimator ...
    assert r.hi_decision_m == pytest.approx(by.hi_m)  # ... the decision upper end does not
    assert r.hi_decision_from == "byram"
    # depth_m / lo_m / hi_m are unchanged (display): same as a plain combination
    mu, sig, _ = dp._gls([sb, by])
    assert r.depth_m == pytest.approx(math.exp(mu))
    assert r.hi_m == pytest.approx(math.exp(mu + dp.Z90 * sig * dp.UNCALIBRATED_SCALE))
    assert r.hi_decision_m >= max(sb.hi_m, by.hi_m, r.hi_m)


def test_decision_upper_end_never_below_combined_upper_end():
    # two similar estimators: the combined (scaled 1.5, uncalibrated) upper end is wider than each one
    r = dp.combine([_est("spread_burn", 2.0, 0.3), _est("byram", 2.0, 0.3)])
    assert r.hi_decision_from == "combined" and r.hi_decision_m == pytest.approx(r.hi_m)
    # single estimator: combined interval with scale 1.5 >= its own interval
    r1 = dp.combine([_est("byram", 1.0, 0.6)])
    assert r1.hi_decision_m == pytest.approx(r1.hi_m) and r1.hi_decision_m > _est("byram", 1.0, 0.6).hi_m


def test_radar_loss_depth_counts_once_valid():
    sb = _est("spread_burn", 0.6, 0.2)
    rl = dp.radar_loss_depth(10.0, 2.0)              # 5 m, sigma 0.5
    r = dp.combine([sb, rl])
    assert r.hi_decision_from == "radar_loss_depth" and r.hi_decision_m == pytest.approx(rl.hi_m)
    # not calibrated (no dB/m): invalid, never counts
    r2 = dp.combine([sb, dp.radar_loss_depth(10.0, None)])
    assert r2.hi_decision_from != "radar_loss_depth"


# ------------------------------------------------------------------------------------------- experimental d
@pytest.mark.parametrize("d_value", [0.05, 0.6, 40.0])
def test_experimental_flicker_extent_never_raises_or_lowers(d_value):
    base = [_est("spread_burn", 0.6, 0.2), _est("byram", 1.2, 0.8)]
    ref = dp.combine(base)
    d = _est("flicker_extent", d_value, dp.FLICKER_SIGMA_LOG, kind="experimental")
    for enabled in (None, ["spread_burn", "byram", "flicker_extent"]):     # off (default) and on for the mean
        r = dp.combine(base + [d], enabled=enabled)
        assert r.valid
        assert r.hi_decision_m == pytest.approx(ref.hi_decision_m), (d_value, enabled)
        assert r.hi_decision_from != "flicker_extent"
        assert r.disagree_ratio == pytest.approx(ref.disagree_ratio)       # d is not in the disagreement check
    # a flicker_extent estimate mislabelled kind="estimate" is still experimental by name
    d2 = _est("flicker_extent", 40.0, 0.8)
    r2 = dp.combine(base + [d2], enabled=["spread_burn", "byram", "flicker_extent"])
    assert r2.hi_decision_m == pytest.approx(ref.hi_decision_m)


# ------------------------------------------------------------------------------------------- disagreement
def test_estimators_disagree_flag_shown_not_closing():
    r = dp.combine([_est("spread_burn", 0.5, 0.2), _est("byram", 2.0, 0.6)])          # 4x > 3x
    flags = [f for f in r.flags if f.startswith(dp.DISAGREE_FLAG)]
    assert r.valid and len(flags) == 1 and r.disagree_ratio == pytest.approx(4.0)
    assert "byram" in flags[0] and "spread_burn" in flags[0]
    assert r.hi_decision_from == "byram"
    ok = dp.combine([_est("spread_burn", 0.5, 0.2), _est("byram", 1.2, 0.6)])         # 2.4x <= 3x
    assert ok.disagree_ratio == pytest.approx(2.4) and not any(f.startswith(dp.DISAGREE_FLAG) for f in ok.flags)
    # configurable factor
    tight = dp.combine([_est("spread_burn", 0.5, 0.2), _est("byram", 1.2, 0.6)], disagree_factor=2.0)
    assert any(f.startswith(dp.DISAGREE_FLAG) for f in tight.flags)
    # garbage factor falls back to the default (3x), never disables the flag
    for bad in (float("nan"), 0.5, None, True):
        g = dp.combine([_est("spread_burn", 0.5, 0.2), _est("byram", 2.0, 0.6)], disagree_factor=bad)
        assert any(f.startswith(dp.DISAGREE_FLAG) for f in g.flags), bad
    # one estimator: no ratio
    assert dp.combine([_est("byram", 2.0, 0.6)]).disagree_ratio is None


def test_disagree_does_not_close_the_decision_by_itself():
    d = dp.combine([_est("spread_burn", 0.5, 0.2), _est("byram", 2.0, 0.6)])
    assert any(f.startswith(dp.DISAGREE_FLAG) for f in d.flags)
    big = replace_vehicle_limit(FE, 1.0e6)
    v = dc.decide(cross_inputs(depth=d), big, None, NOW)
    assert v.state == dc.CROSS_FAST, v.reasons
    assert v.details["estimators_disagree"] is True
    assert v.details["depth_hi_m"] == pytest.approx(d.hi_decision_m)


# ------------------------------------------------------------------------------------------- radar ceiling
def test_radar_ceiling_never_lowers_decision_upper_end_unless_trusted():
    base = [_est("spread_burn", 0.6, 0.2), _est("byram", 1.2, 0.8)]
    ceil = dp.radar_ceiling(10.0, 12.0)                                      # 2.0 m < byram hi 4.47 m
    ref = dp.combine(base, _cal(12))
    un = dp.combine(base + [ceil], _cal(12))
    assert un.hi_decision_m == pytest.approx(ref.hi_decision_m)
    tr = dp.combine(base + [ceil], _cal(12, trust_radar_ceiling=True))
    assert tr.hi_decision_m == pytest.approx(2.0) and tr.hi_decision_from.startswith("radar_ceiling")
    big = dp.radar_ceiling(10.0, 30.0)                                       # a ceiling never raises
    assert dp.combine(base + [big], _cal(12, trust_radar_ceiling=True)).hi_decision_m == pytest.approx(
        ref.hi_decision_m)


# ------------------------------------------------------------------------------------------- narrow flag
def test_narrow_flag_needs_calibrated_pairs():
    base = [_est("spread_burn", 0.6, 0.2), _est("byram", 1.2, 0.8)]
    by_hi = base[1].hi_m
    assert dp.combine(base, _cal(40)).hi_decision_m == pytest.approx(by_hi)                       # default off
    assert dp.combine(base, _cal(29), narrow_decision_hi=True).hi_decision_m == pytest.approx(by_hi)   # n < 30
    assert dp.combine(base, None, narrow_decision_hi=True).hi_decision_m == pytest.approx(by_hi)       # uncal.
    uncal = SimpleNamespace(calibrated=False, scale=1.0, n_pairs=100, trust_radar_ceiling=False)
    assert dp.combine(base, uncal, narrow_decision_hi=True).hi_decision_m == pytest.approx(by_hi)
    assert dp.combine(base, _cal(40), narrow_decision_hi="yes").hi_decision_m == pytest.approx(by_hi)  # not True
    n = dp.combine(base, _cal(30), narrow_decision_hi=True)
    assert n.hi_decision_from == "combined" and n.hi_decision_m == pytest.approx(n.hi_m) and n.hi_m < by_hi
    assert any("narrowed" in f for f in n.flags)


def test_config_defaults_and_validation(tmp_path):
    cfg = load_config()
    assert cfg.depth.narrow_decision_hi is False
    assert cfg.depth.narrow_decision_hi_min_pairs >= 9 and cfg.depth.disagree_factor == pytest.approx(3.0)
    for bad in ({"narrow_decision_hi": "yes"}, {"narrow_decision_hi_min_pairs": 3},
                {"narrow_decision_hi_min_pairs": 12.5}, {"disagree_factor": 1.0}, {"disagree_factor": float("nan")}):
        with pytest.raises(ValueError):
            load_config(overrides={"depth": bad})


# ------------------------------------------------------------------------------------------- decision
def test_decision_dose_uses_decision_upper_end():
    d = DepthResult(valid=True, depth_m=1.5, lo_m=1.0, hi_m=2.2, sigma_log=0.25, hi_decision_m=4.5,
                    hi_decision_from="byram")
    big = replace_vehicle_limit(FE, 1.0e6)
    v = dc.decide(cross_inputs(depth=d), big, None, NOW)
    assert v.state == dc.CROSS_FAST, v.reasons
    assert v.time_in_flame_s == pytest.approx((4.5 + FE.length_m) / v.min_speed_m_s)
    assert v.details["depth_hi_m"] == pytest.approx(4.5) and v.details["depth_hi_combined_m"] == pytest.approx(2.2)
    assert v.details["depth_hi_from"] == "byram"
    # a decision upper end below the central value is inconsistent: fail closed
    bad = DepthResult(valid=True, depth_m=1.5, lo_m=1.0, hi_m=2.2, sigma_log=0.25, hi_decision_m=1.2)
    assert dc.decide(cross_inputs(depth=bad), big, None, NOW).state == dc.CLOSED
    nan = DepthResult(valid=True, depth_m=1.5, lo_m=1.0, hi_m=2.2, sigma_log=0.25, hi_decision_m=float("nan"))
    assert dc.decide(cross_inputs(depth=nan), big, None, NOW).state == dc.CLOSED
    # an object without hi_decision_m (hand-made / older) falls back to hi_m
    legacy = SimpleNamespace(valid=True, depth_m=1.5, lo_m=1.0, hi_m=2.2)
    assert dc.depth_hi_for_decision(legacy) == pytest.approx(2.2)
    json.dumps(v.to_dict())


def replace_vehicle_limit(veh, limit):
    """TEST-ONLY dose limit (absurd on purpose): says nothing about any real vehicle."""
    return replace(veh, dose_limit_tdu=limit)


# ------------------------------------------------------------------------------------------- sample replay
VU = Path(__file__).resolve().parents[3] / "hardware" / "vehicle-unit"


def test_flame_front_sample_decision_upper_end_covers_every_valid_estimator(tmp_path):
    """SIMULATED committed flame_front sample (true depth 3.0 m): in every State with a valid depth, the decision
    upper end is >= the combined upper end and >= every valid non-experimental estimator upper end, and the
    experimental flicker_extent never sets it."""
    d = VU / "samples" / "flame_front"
    if not (d / "session.json").exists():
        pytest.skip("no committed flame_front sample")
    import test_pipeline as tp
    from crossing import pipeline as pl
    pipe = tp.make_pipe(tmp_path)
    states = pl.run_virtual(pipe, pl.iter_source(d), hooks={3.0: lambda p, now: p.capture_baseline(now)})
    dv = [s["depth"] for _, s in states if isinstance(s.get("depth"), dict) and s["depth"].get("valid")]
    assert len(dv) > 50
    for dep in dv:
        hd = dep["hi_decision_m"]
        assert hd >= dep["hi_m"] - 1e-9 and hd >= dep["depth_m"]
        for e in dep["estimators"]:
            if e["valid"] and e["kind"] == "estimate" and e["name"] != "flicker_extent":
                assert hd >= e["hi_m"] - 1e-9, (e["name"], e["hi_m"], hd)
        assert dep["hi_decision_from"] != "flicker_extent"
    # measured on this sample (2026-11-17): the combined interval misses 3.0 m in most States, the decision
    # upper end covers it in most (not all: byram's upper end itself dips to ~2.6 m)
    cov_hi = sum(dep["lo_m"] <= 3.0 <= dep["hi_m"] for dep in dv) / len(dv)
    cov_hd = sum(dep["lo_m"] <= 3.0 <= dep["hi_decision_m"] for dep in dv) / len(dv)
    assert cov_hd > cov_hi


def test_disabled_estimator_still_raises_decision_upper_end():
    # `enabled` restricts the MEAN only; a valid non-experimental estimator left out of it still sets the floor of
    # the decision upper end (fail closed: a config change cannot hide a wide valid estimator from the dose)
    sb, by = _est("spread_burn", 0.6, 0.2), _est("byram", 1.2, 0.8)
    r = dp.combine([sb, by], enabled=("spread_burn",))
    assert r.used == ["spread_burn"] and r.hi_decision_m == pytest.approx(by.hi_m) and r.hi_decision_from == "byram"
