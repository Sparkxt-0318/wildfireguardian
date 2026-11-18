"""The worked example equals research/kcf-replay/per_place.csv (MEASURED arm, 8 h) at the same issue hours: the same
state for every place and the same latest departure to the minute. Shelters may differ only between equally late
shelters (the replay keeps the first in its loop order; this tool the earliest arrival)."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
PER_PLACE = REPO / "research/kcf-replay/per_place.csv"
CASES = {"uiseong_andong_20250325_1200KST": ("uiseong_andong_2025", "03-25 12:00", datetime(2025, 3, 25, 3, tzinfo=timezone.utc)),
         "yeongdeok_20250325_1800KST": ("yeongdeok_2025", "03-25 18:00", datetime(2025, 3, 25, 9, tzinfo=timezone.utc))}


@pytest.mark.parametrize("case", sorted(CASES))
def test_equals_kcf_replay(example_out, case):
    region, hour, T = CASES[case]
    want = {r["place_id"]: r for r in csv.DictReader(open(PER_PLACE, encoding="utf-8"))
            if r["region"] == region and r["standin"] == "MEASURED" and r["horizon"] == "8h" and r["issue_kst"] == hour}
    got = {r["place id"]: r for r in csv.DictReader(open(example_out["path"] / case / ("en/villages_road_cut_%s.csv" % region),
                                                         encoding="utf-8-sig"))}
    assert want and set(want) <= set(got)
    kst = timezone(timedelta(hours=9))
    for pid, w in want.items():
        g = got[pid]
        L = g["departure windows (s after issue)"]
        last = int(L.split(";")[-1].split("-")[1]) if L else None
        mine_last = (T + timedelta(seconds=last)).astimezone(kst).strftime("%m-%d %H:%M") if last is not None else ""
        assert mine_last == w["last_departure_in_horizon_kst"], (pid, mine_last, w["last_departure_in_horizon_kst"])
        if last is None:
            state = "INSIDE_KNOWN_FIRE_AREA" if g["fire arrival (s after issue)"] == "0" else "NO_SAFE_DEPARTURE"
        else:
            state = "NOT_CUT_WITHIN_H" if g["road status"] == "not cut within the horizon" else "LATEST_SAFE_DEPARTURE"
        assert state == w["departure_state"], (pid, state, w["departure_state"])
        step = {"Execute now": "LEAVE_NOW", "Standby": "PREPARE_VULNERABLE_FIRST", "Prepare": "NONE"}[g["stage now"]]
        assert step == w["government_step"], (pid, step, w["government_step"])
