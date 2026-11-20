"""REQUIRED by the user: no single sensor failure, link loss or stale verdict can give CROSS FAST or REOPENED.

Two good SYNTHETIC scenarios (one giving CROSS FAST, one giving REOPENED) are each broken one fault at a time:
every required sensor made stale / missing / frozen / faulted / NaN / old / future-stamped, link down, verdict aged
5.01 s, radar UNKNOWN, no far echo, depth invalid, intake air over the limit, ... Each must give CLOSED. Then a
seeded randomised sweep (>= 5000 cases) injects >= 1 fault into randomly perturbed good scenarios and asserts no
CROSS FAST / SPRAY THEN RE-CHECK / REOPENED. SPRAY must never appear for a vehicle without water.

Required sensors (orchestrator decision D1, 2026-11-17): EVERY sensor (thermal, radar, tc_plate, tc_housing, tc_air,
imu, gnss, pi) is required for EVERY go verdict (CROSS FAST, SPRAY THEN RE-CHECK, REOPENED).
``test_every_single_sensor_failure_closes_every_go_verdict`` checks each single-sensor failure (stale, missing,
faulted, NaN, out of range, Pi status no_device / error, frozen, ...) against each candidate verdict. The ``pi``
sensor has no value in the decision inputs, so NaN / out-of-range do not apply to it (its failures act through
health, heartbeat and the under-voltage fault).
"""
import copy
import math
from dataclasses import replace

import numpy as np
import pytest

from crossing import decision as dc
from crossing.depth import DepthResult, IntensityResult
from crossing.vehicles import load_vehicles

NOW = 5000.0
SENSORS = ("thermal", "radar", "imu", "gnss", "tc_plate", "tc_air", "tc_housing", "pi")
VEHICLES = load_vehicles()
FE = VEHICLES["fire_engine"]
VALUE_FIELDS = {"thermal": ("flame_pixels",), "radar": ("far_echo_m",), "imu": ("imu_pitch_deg", "imu_roll_deg"),
                "gnss": ("lat", "lon", "speed_m_s"), "tc_plate": ("tc_plate_c", "plate_flux_kw_m2"),
                "tc_air": ("tc_air_c",), "tc_housing": ("tc_housing_c",)}
NAN = float("nan")


def good_cross(**kw):
    inp = dc.DecisionInputs(
        link_up=True, health={s: {"fresh": True, "reason": "", "age_s": 0.1} for s in SENSORS},
        faults={s: None for s in SENSORS}, input_times={s: NOW - 0.1 for s in SENSORS},
        flame_status="FLAME", radar_status="FLAME_EFFECT", near_edge_m=25.0, far_echo_m=29.0,
        depth=DepthResult(valid=True, depth_m=1.5, lo_m=1.0, hi_m=2.2, sigma_log=0.25),
        intensity=IntensityResult(valid=True, i_kw_m=500.0, lo=400.0, hi=600.0, sources=["byram_flame_height"]),
        tc_air_c=30.0, tc_plate_c=40.0, tc_housing_c=35.0, plate_flux_kw_m2=0.5, flame_pixels=1200,
        imu_roll_deg=1.0, imu_pitch_deg=-2.0, gnss_fix=1, lat=37.5, lon=128.9, utc="2026-11-17T10:00:00Z",
        speed_m_s=0.0, flame_held_s=5.0, near_edge_observed=True)
    return replace(inp, **kw)


def good_reopen(**kw):
    d = dict(passed=True, flame_status="NO_FLAME", radar_status="NO_EFFECT", far_echo_m=None, depth=None,
             intensity=None, plate_flux_kw_m2=0.2, flame_pixels=0, reopen_quiet_s=31.0, speed_m_s=0.0,
             flame_held_s=0.0, near_edge_m=None, near_edge_observed=None, crossing_in_view=True,
             crossing_hot_pixels=0)
    d.update(kw)
    return good_cross(**d)


def good_spray(**kw):
    """Dose at max speed 12 % over the fire engine's PLACEHOLDER limit: SPRAY THEN RE-CHECK (it has water)."""
    dm = dc.dose_model(1.0, 2.2, 600.0, FE.length_m)
    i_hi = 600.0 * (1.12 * FE.dose_limit_tdu / dm.dose(FE.max_safe_speed_m_s)) ** (3 / 4)
    return good_cross(intensity=IntensityResult(valid=True, i_kw_m=i_hi * 0.8, lo=i_hi * 0.6, hi=i_hi), **kw)


CANDIDATES = {"cross": (good_cross, dc.CROSS_FAST), "spray": (good_spray, dc.SPRAY),
              "reopen": (good_reopen, dc.REOPENED)}


def run(inp, vehicle=FE, at=NOW):
    return dc.decide(inp, vehicle, None, at)


def test_good_scenarios_are_go():
    for name, (make, state) in CANDIDATES.items():
        assert run(make()).state == state, (name, run(make()).reasons)


# ------------------------------------------------------------------------------------------- fault injection
def sensor_fault(inp, sensor, kind, field=None):
    inp = copy.deepcopy(inp)
    h, f, t = dict(inp.health), dict(inp.faults), dict(inp.input_times)
    if kind == "stale":
        h[sensor] = {"fresh": False, "reason": "stale", "age_s": 2.5}
    elif kind == "frozen":
        h[sensor] = {"fresh": False, "reason": "frozen", "age_s": 0.1}
    elif kind == "pi_error":
        h[sensor] = {"fresh": False, "reason": "Pi status error: x", "age_s": 0.1}
    elif kind == "no_device":
        h[sensor] = {"fresh": False, "reason": "Pi status no_device: unplugged", "age_s": 0.4}
    elif kind == "hb_stale":              # readings fine, the Pi heartbeat for the sensor is > 2 s old
        h[sensor] = {"fresh": False, "reason": "Pi heartbeat 2.1 s old", "age_s": 0.1}
    elif kind == "faulted":               # Pi heartbeat still "ok", but the reading carries a fault
        f[sensor] = "open" if sensor.startswith("tc_") else "error"
    elif kind == "missing":
        h.pop(sensor, None)
        t.pop(sensor, None)
        for fld in VALUE_FIELDS.get(sensor, ()):
            inp = replace(inp, **{fld: None})
        if sensor == "radar":
            inp = replace(inp, radar_status=None)
    elif kind == "health_old":            # says fresh but its own age is over stale_s
        h[sensor] = {"fresh": True, "reason": "", "age_s": 2.01}
    elif kind == "health_truthy":         # non-bool "fresh" must not count
        h[sensor] = {"fresh": "yes", "reason": "", "age_s": 0.1}
    elif kind == "input_old":
        t[sensor] = NOW - 5.01
    elif kind == "input_future":
        t[sensor] = NOW + 10.0
    elif kind == "nan":
        inp = replace(inp, **{field: NAN})
    elif kind == "inf":
        inp = replace(inp, **{field: float("inf")})
    elif kind == "out_of_range":
        inp = replace(inp, **{field: OUT_OF_RANGE[field]})
    else:
        raise AssertionError(kind)
    return replace(inp, health=h, faults=f, input_times=t)


KINDS = ("stale", "frozen", "pi_error", "no_device", "hb_stale", "faulted", "missing", "health_old",
         "health_truthy", "input_old", "input_future")
OUT_OF_RANGE = {"flame_pixels": -1, "far_echo_m": -5.0, "imu_pitch_deg": 60.0, "imu_roll_deg": -60.0, "lat": 95.0,
                "lon": 200.0, "speed_m_s": -1.0, "tc_plate_c": 2000.0, "plate_flux_kw_m2": 1e4, "tc_air_c": -100.0,
                "tc_housing_c": 400.0}


def test_all_sensors_required_for_every_verdict():
    assert set(dc.REQUIRED_CROSS) == set(dc.REQUIRED_REOPEN) == set(SENSORS) == set(dc.ALL_SENSORS)


def _single_failures(sensor):
    out = [(k, None) for k in KINDS]
    for fld in VALUE_FIELDS.get(sensor, ()):
        out += [("nan", fld), ("inf", fld), ("out_of_range", fld)]
    return out


@pytest.mark.parametrize("candidate", sorted(CANDIDATES))
@pytest.mark.parametrize("sensor", SENSORS)
def test_every_single_sensor_failure_closes_every_go_verdict(sensor, candidate):
    """D1: replaces the old test that pinned tc_housing / radar / tc_air failures as harmless for some verdicts."""
    make, state = CANDIDATES[candidate]
    assert run(make()).state == state
    for kind, fld in _single_failures(sensor):
        v = run(sensor_fault(make(), sensor, kind, fld))
        assert v.state == dc.CLOSED and v.reasons, (sensor, candidate, kind, fld, v.reasons)


ALL_FIELDS = [(s, fld) for s, flds in VALUE_FIELDS.items() for fld in flds]


@pytest.mark.parametrize("sensor,field", ALL_FIELDS)
@pytest.mark.parametrize("kind", ("nan", "inf"))
def test_nonfinite_value_closes_both(sensor, field, kind):
    for good in (good_cross(), good_reopen()):
        if getattr(good, field) is None:
            continue
        v = run(sensor_fault(good, sensor, kind, field))
        assert v.state == dc.CLOSED, (sensor, field, v.reasons)


def _both(fn):
    return [fn(good_cross()), fn(good_reopen())]


@pytest.mark.parametrize("name,fn", [
    ("link_down", lambda i: replace(i, link_up=False)),
    ("link_truthy", lambda i: replace(i, link_up=1)),
    ("intake_over", lambda i: replace(i, tc_air_c=FE.intake_air_limit_c + 0.1)),
    ("pitch_out_of_range", lambda i: replace(i, imu_pitch_deg=60.0)),
    ("lat_out_of_range", lambda i: replace(i, lat=95.0)),
    ("gnss_fix_garbage", lambda i: replace(i, gnss_fix=7)),
    ("flame_pixels_negative", lambda i: replace(i, flame_pixels=-1)),
    ("flame_pixels_fraction", lambda i: replace(i, flame_pixels=2.5)),
    ("plate_flux_out_of_range", lambda i: replace(i, plate_flux_kw_m2=1e4)),
    ("housing_nan", lambda i: replace(i, tc_housing_c=NAN)),
    ("health_none", lambda i: replace(i, health=None)),
    ("times_none", lambda i: replace(i, input_times=None)),
    ("flame_status_garbage", lambda i: replace(i, flame_status="flame")),
    ("passed_truthy_string", lambda i: replace(i, passed="yes")),
])
def test_generic_faults_close_both(name, fn):
    for inp in _both(fn):
        assert run(inp).state == dc.CLOSED, name


@pytest.mark.parametrize("name,inp", [
    ("radar_unknown", good_cross(radar_status="UNKNOWN")),
    ("radar_none", good_cross(radar_status=None)),
    ("flame_unknown", good_cross(flame_status="UNKNOWN")),
    ("smoke_only_no_flame", good_cross(flame_status="NO_FLAME", radar_status="NO_EFFECT")),
    ("flame_without_radar_effect", good_cross(radar_status="NO_EFFECT")),
    ("no_far_echo", good_cross(far_echo_m=None)),
    ("far_echo_before_edge", good_cross(far_echo_m=24.0)),
    ("no_near_edge", good_cross(near_edge_m=None)),
    ("depth_invalid", good_cross(depth=DepthResult(valid=False))),
    ("depth_none", good_cross(depth=None)),
    ("depth_nan", good_cross(depth=DepthResult(valid=True, depth_m=NAN, lo_m=1.0, hi_m=2.0))),
    ("depth_lo_gt_hi", good_cross(depth=DepthResult(valid=True, depth_m=1.5, lo_m=2.0, hi_m=1.0))),
    ("depth_zero", good_cross(depth=DepthResult(valid=True, depth_m=0.0, lo_m=0.0, hi_m=1.0))),
    ("intensity_invalid", good_cross(intensity=IntensityResult(valid=False))),
    ("intensity_inf", good_cross(intensity=IntensityResult(valid=True, i_kw_m=500.0, lo=1.0, hi=float("inf")))),
    ("gnss_no_fix", good_cross(gnss_fix=0)),
    ("dose_over", good_cross(intensity=IntensityResult(valid=True, i_kw_m=5e3, lo=4e3, hi=6e3))),
])
def test_cross_specific_faults_close(name, inp):
    v = run(inp)
    assert v.state == dc.CLOSED and v.reasons, name


@pytest.mark.parametrize("name,inp", [
    ("flame_held_short", good_cross(flame_held_s=2.9)),
    ("flame_held_missing", good_cross(flame_held_s=None)),
    ("near_edge_cut_off", good_cross(near_edge_observed=False)),
    ("near_edge_observed_unknown", good_cross(near_edge_observed=None)),
])
def test_flame_evidence_and_near_edge_close(name, inp):
    v = run(inp)
    assert v.state == dc.CLOSED and v.reasons, name


@pytest.mark.parametrize("name,inp", [
    ("plate_flux_at_threshold", good_reopen(plate_flux_kw_m2=1.0)),
    ("not_in_view", good_reopen(crossing_in_view=False)),
    ("in_view_unknown", good_reopen(crossing_in_view=None)),
    ("hot_column_over_crossing", good_reopen(crossing_hot_pixels=1)),
    ("crossing_hot_unknown", good_reopen(crossing_hot_pixels=None)),
    ("moving", good_reopen(speed_m_s=1.01)),
    ("speed_unknown", good_reopen(speed_m_s=None)),
    ("flame_pixels_present", good_reopen(flame_pixels=1)),
    ("hold_short", good_reopen(reopen_quiet_s=29.99)),
    ("hold_missing", good_reopen(reopen_quiet_s=None)),
    ("gnss_no_fix", good_reopen(gnss_fix=0)),
    ("gnss_no_position", good_reopen(lat=None)),
    ("flame_fused", good_reopen(flame_status="FLAME")),
    ("not_passed", good_reopen(passed=False)),
])
def test_reopen_specific_faults_close(name, inp):
    v = run(inp)
    assert v.state == dc.CLOSED and v.reasons, name


@pytest.mark.parametrize("age", [5.0, 5.01, 60.0])
def test_stale_verdict_closes(age):
    for inp in _both(lambda i: i):
        v = run(inp)
        assert v.state in dc.GO_STATES
        assert dc.effective(v, NOW + 4.99).state == v.state
        e = dc.effective(v, NOW + age)
        assert e.state == dc.CLOSED and e.reasons == ["VERDICT_EXPIRED"]


# ------------------------------------------------------------------------------------------- randomised sweep
def _cross_faults():
    out = [(lambda i, s=s, k=k: sensor_fault(i, s, k)) for s in dc.REQUIRED_CROSS for k in KINDS]
    out += [(lambda i, s=s, f=f: sensor_fault(i, s, "nan", f)) for s, flds in VALUE_FIELDS.items() for f in flds]
    out += [lambda i: replace(i, link_up=False), lambda i: replace(i, radar_status="UNKNOWN"),
            lambda i: replace(i, flame_status="UNKNOWN"), lambda i: replace(i, flame_status="NO_FLAME"),
            lambda i: replace(i, far_echo_m=None), lambda i: replace(i, far_echo_m=i.near_edge_m),
            lambda i: replace(i, depth=DepthResult(valid=False)),
            lambda i: replace(i, depth=DepthResult(valid=True, depth_m=NAN, lo_m=NAN, hi_m=NAN)),
            lambda i: replace(i, intensity=IntensityResult(valid=False)), lambda i: replace(i, gnss_fix=0),
            lambda i: replace(i, imu_pitch_deg=90.0), lambda i: replace(i, flame_pixels=-3),
            lambda i: replace(i, flame_held_s=2.5),
            lambda i: replace(i, near_edge_observed=False)]
    return out


def _reopen_faults():
    out = [(lambda i, s=s, k=k: sensor_fault(i, s, k)) for s in dc.REQUIRED_REOPEN for k in KINDS]
    out += [(lambda i, s=s, f=f: sensor_fault(i, s, "nan", f)) for s in dc.REQUIRED_REOPEN
            for f in VALUE_FIELDS.get(s, ())]
    out += [lambda i: replace(i, link_up=False), lambda i: replace(i, plate_flux_kw_m2=1.0),
            lambda i: replace(i, flame_pixels=5), lambda i: replace(i, reopen_quiet_s=12.0),
            lambda i: replace(i, gnss_fix=0), lambda i: replace(i, flame_status="FLAME"),
            lambda i: replace(i, tc_air_c=500.0), lambda i: replace(i, crossing_in_view=False),
            lambda i: replace(i, crossing_hot_pixels=2), lambda i: replace(i, speed_m_s=3.0)]
    return out


AGED = "aged"
INTAKE = "intake"


def _perturb(rng, base):
    """Random but plausible variation of a good scenario (may or may not still be a go state on its own)."""
    veh = VEHICLES[rng.choice(sorted(VEHICLES))]
    if base == "reopen":
        inp = good_reopen(plate_flux_kw_m2=float(rng.uniform(-0.5, 0.99)), reopen_quiet_s=float(rng.uniform(30, 600)),
                          imu_pitch_deg=float(rng.uniform(-10, 10)), tc_air_c=float(rng.uniform(-10, 60)))
        return inp, veh
    d = float(rng.uniform(0.5, 6.0))
    lo, hi = d / float(rng.uniform(1.0, 2.0)), d * float(rng.uniform(1.0, 2.0))
    i_hi = float(np.exp(rng.uniform(np.log(100), np.log(3000))))
    inp = good_cross(depth=DepthResult(valid=True, depth_m=d, lo_m=lo, hi_m=hi, sigma_log=0.3),
                     intensity=IntensityResult(valid=True, i_kw_m=i_hi * 0.7, lo=i_hi * 0.5, hi=i_hi),
                     tc_air_c=float(rng.uniform(-10, 60)), near_edge_m=float(rng.uniform(5, 60)),
                     imu_roll_deg=float(rng.uniform(-10, 10)), speed_m_s=float(rng.uniform(0, 3)))
    inp = replace(inp, far_echo_m=inp.near_edge_m + float(rng.uniform(0.5, 20)))
    return inp, veh


def test_randomised_sweep_no_go_with_any_fault():
    rng = np.random.default_rng(20261117)
    faults = {"cross": _cross_faults() + [AGED, INTAKE], "reopen": _reopen_faults() + [AGED, INTAKE]}
    n_cases, go_without_fault, by_state = 6000, 0, {}
    for case in range(n_cases):
        base = "reopen" if case % 3 == 0 else "cross"
        inp, veh = _perturb(rng, base)
        clean = dc.decide(inp, veh, None, NOW)
        go_without_fault += clean.state in dc.GO_STATES
        k = int(rng.integers(1, 4))
        chosen = [faults[base][j] for j in rng.choice(len(faults[base]), size=k, replace=False)]
        at = NOW
        aged = False
        for f in chosen:
            if f == AGED:
                aged = True
            elif f == INTAKE:
                inp = replace(inp, tc_air_c=veh.intake_air_limit_c + float(rng.uniform(0.01, 200)))
            else:
                inp = f(inp)
        v = dc.decide(inp, veh, None, at)
        if aged:
            v = dc.effective(v, at + 5.0 + float(rng.uniform(0.01, 100.0)))
        by_state[v.state] = by_state.get(v.state, 0) + 1
        assert v.state not in dc.GO_STATES, (case, base, v.state, v.reasons)
        assert v.state == dc.CLOSED and v.reasons
    assert by_state == {dc.CLOSED: n_cases}
    # the sweep is meaningful: a good share of the unfaulted variants were go states
    assert go_without_fault > 0.3 * n_cases, go_without_fault


def test_spray_never_without_water():
    rng = np.random.default_rng(7)
    dry = [v for v in VEHICLES.values() if not v.has_water]
    wet_equiv = 0
    states = set()
    for case in range(3000):
        inp, _ = _perturb(rng, "cross")
        veh = dry[case % len(dry)]
        v = dc.decide(inp, veh, None, NOW)
        states.add(v.state)
        assert v.state in (dc.CLOSED, dc.CROSS_FAST), v.state
        if "NO_WATER_FOR_SPRAY" in v.reasons:
            wet_equiv += 1
            assert dc.decide(inp, replace(veh, has_water=True), None, NOW).state == dc.SPRAY
    assert wet_equiv > 20 and dc.CROSS_FAST in states
