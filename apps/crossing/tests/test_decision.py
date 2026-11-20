"""decision.py and vehicles.yaml: dose model, min speed, CROSS FAST / SPRAY / REOPENED / CLOSED, expiry, trackers.

The scenarios are SYNTHETIC input snapshots; limits are the PLACEHOLDER values in vehicles.yaml.
"""
import json
import math
from dataclasses import replace

import pytest

from crossing import decision as dc
from crossing import heat
from crossing.depth import DepthResult, IntensityResult
from crossing.vehicles import PLACEHOLDER_NOTE, get_vehicle, load_vehicles

NOW = 1000.0
SENSORS = ("thermal", "radar", "imu", "gnss", "tc_plate", "tc_air", "tc_housing", "pi")
FE = get_vehicle("fire_engine")


def cross_inputs(**kw):
    base = dc.DecisionInputs(
        link_up=True, health={s: {"fresh": True, "reason": "", "age_s": 0.1} for s in SENSORS},
        faults={s: None for s in SENSORS}, input_times={s: NOW - 0.1 for s in SENSORS},
        flame_status="FLAME", radar_status="FLAME_EFFECT", near_edge_m=25.0, far_echo_m=29.0,
        depth=DepthResult(valid=True, depth_m=1.5, lo_m=1.0, hi_m=2.2, sigma_log=0.25),
        intensity=IntensityResult(valid=True, i_kw_m=500.0, lo=400.0, hi=600.0, sources=["byram_flame_height"]),
        tc_air_c=30.0, tc_plate_c=40.0, tc_housing_c=35.0, plate_flux_kw_m2=0.5, flame_pixels=1200,
        imu_roll_deg=1.0, imu_pitch_deg=-2.0, gnss_fix=1, lat=37.5, lon=128.9, utc="2026-11-17T10:00:00Z",
        speed_m_s=0.0, flame_held_s=5.0, near_edge_observed=True)
    return replace(base, **kw)


def reopen_inputs(**kw):
    good = dict(passed=True, flame_status="NO_FLAME", radar_status="NO_EFFECT", far_echo_m=None, depth=None,
                intensity=None, plate_flux_kw_m2=0.2, flame_pixels=0, reopen_quiet_s=31.0, speed_m_s=0.0,
                crossing_in_view=True, crossing_hot_pixels=0)
    good.update(kw)
    return cross_inputs(**good)


# ------------------------------------------------------------------------------------------------ vehicles
def test_vehicles_yaml_complete_and_placeholder():
    v = load_vehicles()
    assert set(v) == {"fire_engine", "water_tanker", "pickup", "command_car", "evacuation_minibus", "custom"}
    assert all(x.placeholder for x in v.values())
    assert (FE.length_m, FE.width_m, FE.height_m) == (8.5, 2.5, 3.3)
    assert FE.has_water and v["water_tanker"].has_water and not v["pickup"].has_water
    assert FE.to_dict()["placeholder_note"] == PLACEHOLDER_NOTE
    text = (dc.__file__.rsplit("/", 1)[0] + "/vehicles.yaml")
    assert "PLACEHOLDER FOR A FIRE SERVICE TO SET" in open(text).read()


# ---------------------------------------------------------------------------------------------------- dose
def test_leg_integral_matches_analytic_long_front():
    cfg = dc.DecisionConfig(leg_points=2000)
    dm = dc.dose_model(1.0, 2.2, 600.0, 8.5, cfg)
    c = 0.3 * 600.0 / (2 * math.pi)
    analytic = c ** (4 / 3) * 3 * ((0.5) ** (-1 / 3) - (30.5) ** (-1 / 3))
    assert dm.leg_integral == pytest.approx(analytic, rel=1e-4)
    assert dm.q_in_kw_m2 == pytest.approx(heat.in_flame_flux(1.0, 600.0))


def test_dose_conservative_ends_and_inverse_speed():
    dm = dc.dose_model(1.0, 2.2, 600.0, 8.5)
    assert dm.dose(4.0) == pytest.approx(2 * dm.dose(8.0))
    assert dm.time_in_flame(5.0) == pytest.approx((2.2 + 8.5) / 5.0)
    assert dc.dose_model(1.0, 3.0, 600.0, 8.5).dose(5) > dm.dose(5)       # larger depth_hi: longer
    assert dc.dose_model(0.8, 2.2, 600.0, 8.5).dose(5) > dm.dose(5)       # smaller depth_lo: hotter
    assert dc.dose_model(1.0, 2.2, 700.0, 8.5).dose(5) > dm.dose(5)       # larger I_hi: hotter
    q0 = dc.dose_model(1.0, 2.2, 600.0, 8.5, dc.DecisionConfig(q0_kw_m2=1000.0))
    assert q0.dose(5) == 0.0


def test_min_speed_bisection_rounded_up():
    dm = dc.dose_model(1.0, 2.2, 600.0, 8.5)
    v = dc.min_speed(dm.dose, 500.0, 8.3, 0.1)
    assert v == pytest.approx(round(v, 1)) and dm.dose(v) <= 500.0
    assert dm.dose(v - 0.1) > 500.0
    exact = (dm.in_flame_rate * 10.7 + 2 * dm.leg_integral) / 500.0
    assert v == pytest.approx(math.ceil(exact * 10) / 10)
    assert dc.min_speed(dm.dose, 1.0, 8.3) is None


# ------------------------------------------------------------------------------------------------ verdicts
def test_cross_fast():
    v = dc.decide(cross_inputs(), FE, None, NOW)
    assert v.state == dc.CROSS_FAST, v.reasons
    assert v.dose_tdu <= v.dose_limit_tdu == FE.dose_limit_tdu
    assert v.min_speed_m_s <= FE.max_safe_speed_m_s
    assert v.time_in_flame_s == pytest.approx((2.2 + 8.5) / v.min_speed_m_s)
    assert v.dose_fds_ref_tdu > 0 and v.details["fds_label"] == heat.FDS_LABEL
    assert v.expires_mono == NOW + 5.0 and v.advisory
    json.dumps(v.to_dict())


def _spray_inputs():
    # dose at max speed just over the limit: scale I_hi up until 1 < dose/limit < 1.25
    dm = dc.dose_model(1.0, 2.2, 600.0, FE.length_m)
    ratio = dm.dose(FE.max_safe_speed_m_s) / FE.dose_limit_tdu
    i_hi = 600.0 * (1.12 / ratio) ** (3 / 4)
    return cross_inputs(intensity=IntensityResult(valid=True, i_kw_m=i_hi * 0.8, lo=i_hi * 0.6, hi=i_hi))


def test_spray_only_with_water():
    inp = _spray_inputs()
    v = dc.decide(inp, FE, None, NOW)
    assert v.state == dc.SPRAY, v.reasons
    assert FE.dose_limit_tdu < v.dose_tdu <= 1.25 * FE.dose_limit_tdu
    dry = replace(FE, has_water=False)
    v2 = dc.decide(inp, dry, None, NOW)
    assert v2.state == dc.CLOSED and "DOSE_OVER_LIMIT" in v2.reasons and "NO_WATER_FOR_SPRAY" in v2.reasons
    over = cross_inputs(intensity=IntensityResult(valid=True, i_kw_m=3000.0, lo=2000.0, hi=4000.0))
    v3 = dc.decide(over, FE, None, NOW)
    assert v3.state == dc.CLOSED and "DOSE_OVER_LIMIT" in v3.reasons and v3.dose_tdu > 1.25 * FE.dose_limit_tdu


def test_min_flame_evidence():
    """D4: CROSS FAST / SPRAY need FLAME held for min_flame_evidence_s (3.0 s default, placeholder)."""
    assert dc.DecisionConfig().min_flame_evidence_s == 3.0
    for held, state in ((None, dc.CLOSED), (0.0, dc.CLOSED), (0.38, dc.CLOSED), (2.99, dc.CLOSED),
                        (3.0, dc.CROSS_FAST), (60.0, dc.CROSS_FAST)):
        v = dc.decide(cross_inputs(flame_held_s=held), FE, None, NOW)
        assert v.state == state, (held, v.reasons)
        if state == dc.CLOSED:
            assert "FLAME_EVIDENCE_TOO_SHORT" in v.reasons
    assert dc.decide(cross_inputs(flame_held_s=0.5), FE, {"min_flame_evidence_s": 0.5}, NOW).state == dc.CROSS_FAST
    sp = _spray_inputs()
    assert dc.decide(replace(sp, flame_held_s=1.0), FE, None, NOW).state == dc.CLOSED


def test_near_edge_not_observed_closes():
    """D5: a flame base cut off by the image (near_edge_observed False) closes CROSS FAST and SPRAY."""
    for inp in (cross_inputs(near_edge_observed=False), replace(_spray_inputs(), near_edge_observed=False)):
        v = dc.decide(inp, FE, None, NOW)
        assert v.state == dc.CLOSED and "NEAR_EDGE_NOT_OBSERVED" in v.reasons
    v = dc.decide(cross_inputs(near_edge_observed=None, near_edge_m=None), FE, None, NOW)
    assert v.state == dc.CLOSED and "NO_NEAR_EDGE" in v.reasons


def test_reopen_needs_crossing_in_view_slow_and_cool_columns():
    """D3: REOPENED only with the recorded crossing in the camera view, the vehicle stopped/slow and no flame pixels
    in the crossing's image columns."""
    v = dc.decide(reopen_inputs(crossing_in_view=False, crossing_view_reason="behind the vehicle"), FE, None, NOW)
    assert v.state == dc.CLOSED and "REOPEN_CROSSING_NOT_IN_VIEW" in v.reasons
    assert v.details["reopen_view_reason"] == "behind the vehicle"
    v = dc.decide(reopen_inputs(crossing_hot_pixels=3), FE, None, NOW)
    assert v.state == dc.CLOSED and "CROSSING_HOT_PIXELS_PRESENT" in v.reasons
    v = dc.decide(reopen_inputs(speed_m_s=2.0), FE, None, NOW)
    assert v.state == dc.CLOSED and "REOPEN_VEHICLE_MOVING" in v.reasons
    assert dc.decide(reopen_inputs(speed_m_s=1.0), FE, None, NOW).state == dc.REOPENED


@pytest.mark.parametrize("age,fresh", [(0.0, True), (-1e-9, True), (-1e-4, True), (-1e-3, True), (-0.0011, False),
                                       (-0.5, False), (-0.51, False), (-10.0, False), (2.0, True), (2.01, False)])
def test_fresh_age_tolerance(age, fresh):
    """D6: a float-rounding negative age down to -1e-3 s is fresh; a clearly future time is not."""
    ok, _ = dc._fresh({"x": {"fresh": True, "reason": "", "age_s": age}}, "x", 2.0)
    assert ok is fresh


def test_smoke_only_never_crosses():
    v = dc.decide(cross_inputs(flame_status="NO_FLAME", radar_status="NO_EFFECT"), FE, None, NOW)
    assert v.state == dc.CLOSED and "FLAME_NOT_CONFIRMED" in v.reasons


def test_reopened_and_hold():
    v = dc.decide(reopen_inputs(), FE, None, NOW)
    assert v.state == dc.REOPENED, v.reasons
    assert v.details["stamp"] == {"lat": 37.5, "lon": 128.9, "utc": "2026-11-17T10:00:00Z"}
    v2 = dc.decide(reopen_inputs(reopen_quiet_s=29.9), FE, None, NOW)
    assert v2.state == dc.CLOSED and "REOPEN_HOLD_NOT_MET" in v2.reasons
    v3 = dc.decide(reopen_inputs(passed=False), FE, None, NOW)
    assert v3.state == dc.CLOSED


def test_closed_always_has_reason_codes():
    for inp in (cross_inputs(link_up=False), dc.DecisionInputs(), reopen_inputs(flame_pixels=3)):
        v = dc.decide(inp, FE, None, NOW)
        assert v.state == dc.CLOSED and v.reasons and all(isinstance(r, str) and r for r in v.reasons)


def test_garbage_never_raises():
    for bad in (None, "x", 5, cross_inputs(tc_air_c="hot"), cross_inputs(depth="deep"),
                cross_inputs(health="ok"), cross_inputs(input_times=None), cross_inputs(flame_status=["FLAME"])):
        v = dc.decide(bad, FE, None, NOW)
        assert v.state == dc.CLOSED
    assert dc.decide(cross_inputs(), {"bad": 1}, None, NOW).reasons == ["VEHICLE_INVALID"]
    assert dc.decide(cross_inputs(), FE, None, float("nan")).state == dc.CLOSED


def test_config_mapping_and_object():
    v = dc.decide(cross_inputs(), FE, {"verdict_ttl_s": 3.0}, NOW)
    assert v.expires_mono == NOW + 3.0


# --------------------------------------------------------------------------------------------- expiry etc.
def test_effective_expiry():
    v = dc.decide(cross_inputs(), FE, None, NOW)
    assert dc.effective(v, NOW + 4.99).state == dc.CROSS_FAST
    for t in (NOW + 5.0, NOW + 5.01, NOW + 1e6, NOW - 1.0, float("nan")):
        e = dc.effective(v, t)
        assert e.state == dc.CLOSED and e.reasons in (["VERDICT_EXPIRED"], ["NO_VERDICT"])
    assert dc.effective(None, NOW).state == dc.CLOSED


def test_reopen_tracker_continuity():
    tr = dc.ReopenTracker()
    t = 0.0
    ok = dict(in_view=True, crossing_hot_pixels=0)
    for _ in range(160):                      # samples at 0 .. 31.8 s, 5 Hz
        q = tr.update(t, 0.2, 0, True, **ok)
        t += 0.2
    assert q == pytest.approx(31.8)
    assert tr.update(t, 1.5, 0, True, **ok) == 0.0                     # flux spike restarts
    assert tr.update(t + 0.2, 0.2, 0, True, **ok) == 0.0
    assert tr.update(t + 0.4, 0.2, 0, True, **ok) == pytest.approx(0.2)
    assert tr.update(t + 5.0, 0.2, 0, True, **ok) == 0.0               # 4.6 s gap > stale_s restarts
    assert tr.update(t + 5.2, 0.2, 2, True, **ok) == 0.0               # hot pixels
    assert tr.update(t + 5.4, 0.2, 0, False, **ok) == 0.0              # sensors not ok
    assert tr.update(t + 5.6, float("nan"), 0, True, **ok) == 0.0
    tr.update(t + 5.8, 0.2, 0, True, **ok)
    assert tr.update(t + 5.0, 0.2, 0, True, **ok) == 0.0               # time backwards
    assert tr.update(t + 6.2, 0.2, 0, True, **ok) == pytest.approx(1.2)          # held since t + 5.0
    assert tr.update(t + 6.4, 0.2, 0, True, in_view=False, crossing_hot_pixels=0) == 0.0    # D3: not in view
    tr.update(t + 6.6, 0.2, 0, True, **ok)
    assert tr.update(t + 6.8, 0.2, 0, True, in_view=True, crossing_hot_pixels=1) == 0.0     # hot column
    tr.update(t + 7.0, 0.2, 0, True, **ok)
    assert tr.update(t + 7.2, 0.2, 0, True) == 0.0                     # view not supplied: not quiet (fail closed)


def test_reopen_hold_counts_only_while_stopped():
    """The quiet hold is time spent stopped (speed <= reopen_max_speed_m_s); unknown speed counts as moving."""
    tr = dc.ReopenTracker()
    ok = dict(in_view=True, crossing_hot_pixels=0)
    assert tr.update(0.0, 0.2, 0, True, speed_m_s=2.9, **ok) == 0.0          # rolling towards the crossing
    assert tr.update(0.2, 0.2, 0, True, speed_m_s=1.5, **ok) == 0.0
    assert tr.update(0.4, 0.2, 0, True, speed_m_s=0.0, **ok) == 0.0          # stopped: hold starts here
    assert tr.update(0.6, 0.2, 0, True, speed_m_s=0.3, **ok) == pytest.approx(0.2)
    assert tr.update(0.8, 0.2, 0, True, speed_m_s=1.0, **ok) == pytest.approx(0.4)   # limit is inclusive
    for bad in (None, float("nan"), float("inf"), -0.5, 1.01):
        tr.update(1.0, 0.2, 0, True, speed_m_s=0.0, **ok)
        assert tr.update(1.2, 0.2, 0, True, speed_m_s=bad, **ok) == 0.0, bad


def test_hold_tracker_for_flame_evidence():
    h = dc.HoldTracker(max_gap_s=2.0)
    assert h.update(10.0, True) == 0.0
    assert h.update(13.0, True) == 0.0                           # 3 s gap > max_gap_s restarts
    assert h.update(13.2, True) == pytest.approx(0.2)
    assert h.update(13.4, False) == 0.0
    assert h.update(13.6, True) == 0.0
    assert h.update(16.6, True) == 0.0                           # gap
    for k in range(1, 16):
        held = h.update(16.6 + 0.2 * k, True)
    assert held == pytest.approx(3.0)
    assert h.update(16.0, True) == 0.0                           # time backwards
    assert h.update(float("nan"), True) == 0.0
    assert h.update(20.0, "yes") == 0.0                          # only True counts


def test_has_passed():
    assert dc.has_passed((0.0, 12.0), (0.0, 0.0), (0.0, 1.0), 10.7)
    assert not dc.has_passed((0.0, 10.0), (0.0, 0.0), (0.0, 1.0), 10.7)
    assert not dc.has_passed((float("nan"), 12.0), (0.0, 0.0), (0.0, 1.0), 10.7)
    assert not dc.has_passed((0.0, 12.0), (0.0, 0.0), (0.0, 0.0), 10.7)


def test_dose_uses_depth_hi_decision_not_display_hi():
    # DEPTH-HI rule: time in flame and dose use depth.hi_decision_m; hi_m (display) only when it is absent
    d = DepthResult(valid=True, depth_m=1.5, lo_m=1.0, hi_m=2.2, sigma_log=0.25, hi_decision_m=3.0,
                    hi_decision_from="byram")
    assert dc.depth_hi_for_decision(d) == 3.0 and dc.depth_hi_for_decision(cross_inputs().depth) == 2.2
    v_hd = dc.decide(cross_inputs(depth=d), FE, None, NOW)
    v = dc.decide(cross_inputs(), FE, None, NOW)
    assert v_hd.dose_tdu > 0 and v.dose_tdu > 0
    assert v_hd.details["depth_hi_m"] == 3.0 and v_hd.details["depth_hi_combined_m"] == 2.2
    if v_hd.state == dc.CROSS_FAST and v.state == dc.CROSS_FAST:
        assert v_hd.min_speed_m_s >= v.min_speed_m_s
