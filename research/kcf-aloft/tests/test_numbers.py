"""Independent recount of the main fire-set numbers from the committed tables (a second code path, plain pandas).
python3 -m pytest -q tests"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
N = json.load(open(HERE / "numbers.json"))
ABS = pd.read_csv(HERE.parent / "kcf-abstain" / "derived" / "hours.csv.gz", low_memory=False)
FH = pd.read_csv(HERE / "derived" / "fire_hours.csv.gz", low_memory=False)


def primary_rows():
    k = ABS[(ABS.country == "KR") & ABS.reach5_km.notna()].copy()
    k["kst"] = pd.to_datetime(k.t_utc) + pd.Timedelta(hours=9)
    k["day"] = k.kst.dt.strftime("%Y-%m-%d")
    det = k[k["product"] == "DET"]
    choi = k[(k["product"] == "CHOI") & ~((k.fire == "KFS_01") & (k.day == "2025-03-25"))]
    return pd.concat([choi, det])


def test_run_fire_days_and_run_hours():
    k = primary_rows()
    run = k[k.reach5_km > 3.75]
    days = run.groupby(["fire", "day"]).size()
    f = N["fire_set"]["G"]["full"]
    assert f["run_fire_days"] == len(days) == 9
    assert f["run_hours"] == len(run) == 55
    assert f["fires_with_run"] == run.fire.nunique() == 4
    assert f["fire_days"] == k.groupby(["fire", "day"]).ngroups
    assert f["fires"] == k.fire.nunique() == 12


def test_warned_counts_from_window_maxima():
    """A rules use the 8 h window maximum, which kcf-abstain committed as w850_ms: recount A-cal, A25, A30 from it."""
    k = primary_rows()
    first = k[k.reach5_km > 3.75].sort_values("t_utc").groupby(["fire", "day"]).head(1)
    for rule, test in (("A-cal", lambda w: w > 15.20023), ("A25", lambda w: w >= 25.0), ("A30", lambda w: w >= 30.0)):
        assert int(test(first.w850_ms).sum()) == N["fire_set"][rule]["full"]["warned"]["k"]
        missed = int((~test(k[k.reach5_km > 3.75].w850_ms)).sum())
        assert missed == N["fire_set"][rule]["full"]["run_hours_missed"]["k"]


def test_g_needs_two_consecutive_hours_and_is_within_any_hour_rule():
    d = FH[FH.timeline == "primary"]
    assert (d.g_k2 <= d.g_k1 + 1e-9).all() and (d.g_k3 <= d.g_k2 + 1e-9).all() and (d.g_k2sp <= d.g_k2 + 1e-9).all()
    assert (d.w_k2 <= d.w_k1 + 1e-9).all()
    s = N["sensitivity"]
    assert s["G k=2 (primary)"]["full"]["warned"] == N["fire_set"]["G"]["full"]["warned"]
    assert s["G k=1"]["full"]["warned"]["k"] >= s["G k=2 (primary)"]["full"]["warned"]["k"] >= s["G k=3"]["full"]["warned"]["k"]


def test_burden_counts():
    b = pd.read_csv(HERE / "derived" / "burden_days.csv.gz")
    ok = b[b.hours_evaluated == 24]
    assert N["burden_meta"]["point_days_complete"] == len(ok)
    g = ok.g_k2 >= 20.0
    assert int(g.sum()) == N["s_match"]["g_alarm_point_days"] == N["burden"]["G"]["alarm_point_days_all_evaluated"]
    thr = N["s_match"]["threshold_ms"]
    assert int((ok.w_k1 >= thr).sum()) <= int(g.sum()) < int((ok.w_k1 >= round(thr - 0.1, 1)).sum())
    full = ok[ok.season.isin([2022, 2023, 2024, 2025])]
    assert abs(float((full.w_k1 > 15.20023).sum()) / 40 - N["burden"]["A-cal"]["alarm_days_per_point_season"]["mean"]) < 0.006
    assert abs(float((full.g_k2 >= 20).sum()) / 40 - N["burden"]["G"]["alarm_days_per_point_season"]["mean"]) < 0.006


def test_combination_never_warns_less():
    for a, c in (("A-cal", "A+G"), ("A25", "A25+G"), ("A30", "A30+G")):
        for key in ("full", "without_25_march"):
            wa, wg, wc = (N["fire_set"][r][key]["warned"]["k"] for r in (a, "G", c))
            assert wc >= max(wa, wg)
