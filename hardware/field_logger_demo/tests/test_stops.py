"""Stop detector (spec section 6, test 3). Rows are built second by second in a local metric frame."""
from app import stops
from app.geo import spread_p90
from fakes.tracks import LOC, build


LEAD = [("stop", 60, 0.8)]
TAIL = [("stop", 30, 0.8)]


def test_clean_stop():
    r = stops.analyse(build(LEAD + [("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3)] + TAIL), "WALK")
    assert len(r["stops"]) == 1
    s = r["stops"][0]
    assert abs(s["t0"] - 120) <= 2 and abs(s["dur"] - 30) <= 2
    assert abs(s["t_detect"] - (s["t0"] + 9)) < 1e-6        # announced when it reaches T_min


def test_jitter_while_standing_is_still_one_stop():
    r = stops.analyse(build(LEAD + [("move", 60, 1.3), ("stop", 40, 4.0), ("move", 60, 1.3)] + TAIL, seed=3), "WALK")
    assert len(r["stops"]) == 1 and r["stops"][0]["dur"] >= 35


def test_slow_walking_is_not_a_stop():
    r = stops.analyse(build(LEAD + [("move", 60, 1.3), ("move", 60, 0.5), ("move", 60, 1.3)] + TAIL), "WALK")
    assert r["stops"] == []


def test_single_outlier_inside_a_stop():
    rows = build(LEAD + [("move", 60, 1.3), ("stop", 40, 0.5), ("move", 60, 1.3)] + TAIL)
    k = next(i for i, r in enumerate(rows) if r["t"] == 140)
    lat, lon = LOC.ll(78 + 30.0, 0.0)            # 30 m away, one row
    rows[k].update(lat=lat, lon=lon)
    r = stops.analyse(rows, "WALK")
    assert len(r["stops"]) == 1 and r["stops"][0]["dur"] >= 35


def test_one_far_outlier_does_not_delete_a_stop_of_minimum_length():
    """Spec 6.7: a single outlier must not delete a real stop, also when the stop has only T_min worth of fixes (a
    linear 90th percentile of 10 fixes would give the farthest one 10 % of the weight: 300 m becomes about 30 m)."""
    rows = build(LEAD + [("move", 60, 1.3), ("stop", 10, 0.5), ("move", 60, 1.3)] + TAIL)
    before = stops.analyse(rows, "WALK")["stops"]
    assert len(before) == 1 and before[0]["n_rows"] == 10
    k = next(i for i, r in enumerate(rows) if r["t"] == before[0]["t0"] + 4)
    lat, lon = LOC.ll(78 + 300.0, 0.0)           # 300 m away: more than 10 x R_max
    rows[k].update(lat=lat, lon=lon)
    after = stops.analyse(rows, "WALK")["stops"]
    assert len(after) == 1 and after[0]["dur"] == before[0]["dur"]


def test_spread_percentile_ignores_one_far_value_but_not_two():
    assert spread_p90([1.0] * 9 + [300.0]) == 1.0
    assert spread_p90([1.0] * 5 + [300.0]) == 1.0
    assert spread_p90([1.0] * 18 + [300.0, 300.0]) == 1.0     # 20 values: the 18th by nearest rank
    assert spread_p90([1.0] * 8 + [300.0, 300.0]) == 300.0     # 10 values with two far ones: not a stop
    assert spread_p90([2.0]) == 2.0 and spread_p90([]) is None


def test_short_no_fix_inside_a_stop_is_bridged():
    plan = LEAD + [("move", 60, 1.3), ("stop", 20, 0.5), ("nofix", 3, None), ("stop", 20, 0.5), ("move", 60, 1.3)] + TAIL
    r = stops.analyse(build(plan), "WALK")
    assert len(r["stops"]) == 1 and r["stops"][0]["dur"] >= 41
    assert r["gaps"] == []


def test_long_no_fix_is_a_gap_and_splits_the_stop():
    plan = LEAD + [("move", 60, 1.3), ("stop", 20, 0.5), ("nofix", 30, None), ("stop", 20, 0.5), ("move", 60, 1.3)] + TAIL
    r = stops.analyse(build(plan), "WALK")
    assert len(r["gaps"]) == 1 and abs(r["gaps"][0]["dur"] - 30) <= 1
    assert len(r["stops"]) == 2
    m = r["metrics"]
    assert abs(m["moving"] - (m["elapsed"] - m["stopped"] - m["gap"])) < 1e-6


def test_lead_in_and_lead_out_are_excluded():
    r = stops.analyse(build(LEAD + [("move", 90, 1.3)] + TAIL), "WALK")
    assert r["stops"] == []
    a0, a1 = r["span"]
    assert 58 <= a0 <= 64 and 145 <= a1 <= 152
    assert r["metrics"]["lead_in"] >= 58 and r["metrics"]["lead_out"] >= 28


def test_vehicle_thresholds():
    plan = LEAD + [("move", 60, 12.0), ("move", 30, 0.8), ("move", 60, 12.0)] + TAIL
    assert len(stops.analyse(build(plan, jitter=0.3), "VEHICLE")["stops"]) == 1
    assert stops.analyse(build(plan, jitter=0.3), "WALK")["stops"] == []


def test_one_to_one_validation():
    plan = LEAD + [("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3)] + TAIL
    rows = build(plan)
    det = stops.analyse(rows, "WALK")["stops"]
    assert len(det) == 2
    events = [{"event_no": 1, "t_press": det[0]["t0"] + 2}, {"event_no": 2, "t_press": det[0]["t0"] + 5},
              {"event_no": 3, "t_press": det[1]["t0"] - 4}, {"event_no": 4, "t_press": 20.0}]
    r = stops.analyse(rows, "WALK", events=events, marks_are_stops=True)
    v = r["validation"]
    assert v["presses"] == 4 and v["detected"] == 2 and v["matched"] == 2
    assert r["stops"][0]["match_event"] == 1 and r["stops"][1]["match_event"] == 3
    assert abs(v["recall"] - 0.5) < 1e-9 and abs(v["precision"] - 1.0) < 1e-9


def test_sensitivity_reports_ranges():
    plan = LEAD + [("move", 60, 1.3), ("stop", 12, 0.5), ("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3)] + TAIL
    sens = stops.analyse(build(plan), "WALK")["sensitivity"]
    assert sens["stops_min"] <= sens["stops_max"] and sens["stopped_min"] <= sens["stopped_max"]
    assert sens["t_min_values"] == [7.0, 10.0, 13.0] and sens["v_factors"] == [0.7, 1.0, 1.3]
    assert sens["stops_min"] == 1 and sens["stops_max"] == 2     # the 12 s stop is lost with T_min 13 s


def test_live_detection_matches_replay():
    """LIVE runs the same detector over the rows up to 2 s ago: once the session is over, both agree."""
    rows = build(LEAD + [("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3)] + TAIL)
    full = stops.analyse(rows, "WALK", sensitivity=False)
    late = stops.analyse(rows, "WALK", sensitivity=False, until_t=rows[-1]["t"] + 5)
    assert [(s["t0"], s["t1"]) for s in full["stops"]] == [(s["t0"], s["t1"]) for s in late["stops"]]


def test_clock_jump_leaves_durations_unchanged():
    """Durations use mono_ms only: a CLOCK JUMP inside a stop moves the UTC labels, not the stop or the metrics."""
    from app import session
    from fakes.tracks import to_wfg
    rows = build(LEAD + [("move", 60, 1.3), ("stop", 30, 0.5), ("move", 60, 1.3)] + TAIL)
    plain = session.load_wfg_bytes(to_wfg(rows))
    jumped = session.load_wfg_bytes(to_wfg(rows, jump_at_t=130.0))
    assert plain.integrity["ok"] and jumped.integrity["ok"]
    assert [c["kind"] for c in jumped.clocks] == ["FIRST_UTC", "JUMP"]
    a, b = stops.analyse(plain.rows, "WALK"), stops.analyse(jumped.rows, "WALK")
    assert len(a["stops"]) == 1
    assert [(s["t0"], s["t1"], s["dur"]) for s in a["stops"]] == [(s["t0"], s["t1"], s["dur"]) for s in b["stops"]]
    assert a["metrics"] == b["metrics"] and a["sensitivity"] == b["sensitivity"]
    k = next(i for i, r in enumerate(jumped.rows) if r["t"] >= 140)
    assert plain.rows[k]["utc_ms"] - jumped.rows[k]["utc_ms"] == 3_600_000     # the labels did move
