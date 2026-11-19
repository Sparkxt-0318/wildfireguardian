"""REOPENED end to end, in process, over the committed SIMULATED samples ``crossing_return`` and ``crossing_return_hot``.

Both sessions were written by ``wfgvu.synth`` (illustrative toy physics; hardware/vehicle-unit/samples/README.md):
a line fire across the road, the vehicle crosses it at 5 m/s (plate-flux pulse -> recorded near/far edge), drives
on, turns round FORWARD at 3 m/s (teardrop turnaround, GNSS course follows the heading), comes back on the other
lane and stops 25 m past the far edge FACING the crossed road. The flame burns out at 16 s and the burnt strip
cools. ``crossing_return_hot`` is identical except that a 600 C hot area stays in the middle of the crossed strip.
Each session carries its own SIMULATED DEM (``dem.npz``, named in session.json ``dem``): REOPENED needs DEM line of
sight (FS-8), so the replay loads it as ``--dem`` would.

The replay is ``pipeline.iter_source`` (Pi t_mono spacing, synthesised hello with the session's mount) through
``pipeline.run_virtual`` at the 5 Hz tick on a virtual clock; no sockets, no hardware. Nothing here says the
pipeline works on a real vehicle: it shows the REOPENED path can be reached (and refused) on these synthetic scenes.
Every limit involved (reopen hold 30 s, flux 1 kW/m2, 0 hot pixels, 1 m/s, 40 m view) is a placeholder.
"""
import json
import math
from pathlib import Path

import pytest

from crossing import decision as dc
from crossing import pipeline as pl
from crossing.config import load_config
from crossing.terrain import Dem

SAMPLES = Path(__file__).resolve().parents[3] / "hardware" / "vehicle-unit" / "samples"
EARTH_R = 6371008.8


def _info(name):
    return json.loads((SAMPLES / name / "session.json").read_text())


def _replay(name, with_dem, tmp):
    d = SAMPLES / name
    info = _info(name)
    cfg = load_config(overrides={"paths": {"records_dir": str(tmp), "pairs_path": str(Path(tmp) / "pairs.jsonl"),
                                           "sim_pairs_path": str(Path(tmp) / "pairs_sim.jsonl"),
                                           "replay_pairs_path": str(Path(tmp) / "pairs_replay.jsonl")}})
    dem = Dem.load(d / info["dem"]["file"]) if with_dem else None
    pipe = pl.Pipeline(cfg, "fire_engine", "DEFAULT", dem=dem, mode="replay", source="test_reopen_e2e")
    states = pl.run_virtual(pipe, pl.iter_source(d))
    return pipe, states


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    out = {}
    for name in ("crossing_return", "crossing_return_hot"):
        out[name] = _replay(name, True, str(tmp_path_factory.mktemp(name)))
    return out


def _speed(s):
    return (s.get("gnss") or {}).get("speed_m_s")


def _state(s):
    return s["verdict"]["state"]


def _dist_m(lat1, lon1, lat2, lon2):
    k = math.pi / 180.0 * EARTH_R
    return math.hypot((lon2 - lon1) * k * math.cos(math.radians(lat1)), (lat2 - lat1) * k)


def verdict_runs(states):
    """[(state, first tick s, last tick s)] of consecutive equal verdicts (for the report and the checks)."""
    out = []
    for t, s in states:
        if out and out[-1][0] == _state(s):
            out[-1][2] = t
        else:
            out.append([_state(s), t, t])
    return [tuple(r) for r in out]


def test_samples_carry_a_dem_and_the_return_truth():
    for name in ("crossing_return", "crossing_return_hot"):
        info = _info(name)
        assert info["sim"] is True and info["dem"]["file"] == "dem.npz" and info["dem"]["crs"] == "local-enu"
        dem = Dem.load(SAMPLES / name / "dem.npz")
        tr = info["truth"]
        rp = tr["return_path"]
        # the DEM is the session's ground plane: stop point vs start point differ by grade * X
        z0 = dem.elevation(info["params"]["lat0"], info["params"]["lon0"])
        zs = dem.elevation(rp["stop_lat"], rp["stop_lon"])
        assert zs - z0 == pytest.approx(info["params"]["grade"] * rp["x_stop_m"], abs=0.05)
        assert rp["t_stop_s"] < info["params"]["duration_s"] - 30.0       # room for the 30 s hold
        assert tr["burn_out"]["flame_out_s"] < rp["t_turn_start_s"]
    assert _info("crossing_return")["truth"]["hot_spot"] is None
    assert _info("crossing_return_hot")["truth"]["hot_spot"]["temp_c"] >= 550.0


def test_crossing_return_reaches_reopened_only_after_the_hold_facing_the_crossing(runs):
    pipe, states = runs["crossing_return"]
    tr = _info("crossing_return")["truth"]
    rp = tr["return_path"]
    hold = pipe.cfg.decision.reopen_hold_s
    vmax = pipe.cfg.decision.reopen_max_speed_m_s
    assert pipe.crossing_ref is not None and pipe.far_edge_ref is not None      # recorded by the flux pulse
    reo = [(t, s) for t, s in states if _state(s) == dc.REOPENED]
    assert reo, verdict_runs(states)
    t_first = reo[0][0]
    # every REOPENED tick: stopped/slow, passed, crossing in view with zero hot pixels over it, quiet >= hold,
    # facing from the GNSS course of the last forward travel (back towards the crossing), GNSS stamp
    for t, s in reo:
        assert _speed(s) is not None and _speed(s) <= vmax, (t, _speed(s))
        r = s["reopen"]
        v = r["view"]
        assert r["passed"] is True and r["quiet_s"] >= hold, (t, r["quiet_s"])
        assert v["in_view"] is True and v["hot_pixels"] == 0 and v["d_max_m"] <= pipe.cfg.geometry.reopen_max_view_m
        assert v["heading_source"].startswith("gnss course")
        assert abs(((v["heading_deg"] - rp["heading_at_stop_deg"]) + 180.0) % 360.0 - 180.0) < 10.0
        stamp = s["verdict"]["details"]["stamp"]
        assert stamp["utc"] and stamp["utc"].endswith("Z")
        assert _dist_m(stamp["lat"], stamp["lon"], rp["stop_lat"], rp["stop_lon"]) < 3.0     # GNSS noise ~0.5 m
        assert s["verdict"]["reasons"] == ["REOPEN_CONDITIONS_HELD"]
    # only after the vehicle stopped, and only after hold_s of CONTINUOUS in-view quiet ending at t_first
    assert t_first >= rp["t_stop_s"]
    quiet_start = max(t for t, s in states if t <= t_first and not s["reopen"]["view"]["in_view"])
    assert t_first - quiet_start >= hold - 0.2 - 1e-6
    assert all(_state(s) != dc.REOPENED for t, s in states if t < t_first)
    # never while moving: on the way back the crossing comes into view before the stop; those ticks are CLOSED
    # with REOPEN_VEHICLE_MOVING (the quiet hold itself does not include speed, so it already runs here)
    rolling = [(t, s) for t, s in states if s["reopen"]["passed"] and s["reopen"]["view"]["in_view"]
               and _speed(s) is not None and _speed(s) > vmax]
    assert rolling and all(_state(s) == dc.CLOSED and "REOPEN_VEHICLE_MOVING" in s["verdict"]["reasons"]
                           for _, s in rolling)
    # never with the crossing out of view: driving away after the crossing and through the turn
    away = [(t, s) for t, s in states if tr["crossing"]["t_exit_flame_s"] + 1.0 <= t <= rp["t_turn_end_s"]]
    assert away and all(not s["reopen"]["view"]["in_view"] for _, s in away)
    away_passed = [s for _, s in away if s["reopen"]["passed"]]
    assert away_passed and all("REOPEN_CROSSING_NOT_IN_VIEW" in s["verdict"]["reasons"] for s in away_passed)
    # the run of REOPENED lasts to the end of the session (conditions keep holding)
    assert verdict_runs(states)[-1][0] == dc.REOPENED


def test_crossing_return_hot_never_reopens(runs):
    pipe, states = runs["crossing_return_hot"]
    rp = _info("crossing_return_hot")["truth"]["return_path"]
    assert pipe.crossing_ref is not None
    assert all(_state(s) != dc.REOPENED for _, s in states), verdict_runs(states)
    late = [(t, s) for t, s in states if t >= rp["t_stop_s"] + 1.0]
    assert late
    for t, s in late:
        r, v = s["reopen"], s["reopen"]["view"]
        assert r["passed"] is True and r["quiet_s"] == 0.0
        # facing the crossing exactly as in crossing_return, but flame-temperature pixels over it
        assert v["in_view"] is True and v["hot_pixels"] > 0
        assert "CROSSING_HOT_PIXELS_PRESENT" in s["verdict"]["reasons"]
        assert _state(s) == dc.CLOSED


def test_crossing_return_without_dem_never_reopens(tmp_path):
    """FS-8: the same session replayed without its DEM cannot show line of sight: never REOPENED."""
    pipe, states = _replay("crossing_return", False, str(tmp_path))
    assert all(_state(s) != dc.REOPENED for _, s in states)
    late = [s for t, s in states if t >= _info("crossing_return")["truth"]["return_path"]["t_stop_s"] + 1.0]
    assert late and all("no DEM" in s["reopen"]["view"]["reason"] for s in late)
