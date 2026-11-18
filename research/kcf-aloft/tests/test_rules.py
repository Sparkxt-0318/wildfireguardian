"""Unit tests of the rule and metric code against brute force (no data needed).  python3 -m pytest -q tests"""
import itertools
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rules as R  # noqa: E402


def brute_fires(x, thr, k):
    """x >= thr at k consecutive entries."""
    return any(all(v >= thr for v in x[i:i + k]) for i in range(len(x) - k + 1))


def test_level_equals_consecutive_rule():
    rng = np.random.default_rng(1)
    for _ in range(400):
        x = rng.uniform(0, 30, 8).round(1)
        for k in (1, 2, 3, 4, 6):
            for thr in (10.0, 15.0, 20.0, 25.0):
                assert (R.level(x, k) >= thr) == brute_fires(x, thr, k)


def test_level_nan_and_short():
    assert math.isnan(R.level([1, np.nan, 3], 2))
    assert math.isnan(R.level([1.0], 2))
    assert R.level([5, 21, 22, 3], 2) == 21


def test_levels_fire_wide_and_same_point():
    g = np.zeros((8, 4))
    g[2, 0] = 25
    g[3, 1] = 24          # 20+ at consecutive hours, but at different points
    w = np.full((8, 4), 10.0)
    w[7, 3] = 31
    lv = R.levels(g, w)
    assert lv["g_k1"] == 25 and lv["g_k2"] == 24 and lv["g_k2sp"] == 0 and lv["g_k3"] == 0
    assert lv["g_k2w5"] == 24 and lv["w_k1"] == 31 and lv["w_k2"] == 10
    g2 = g.copy()
    g2[6:8, 2] = 22       # persistent only outside the first 5 valid hours
    lv2 = R.levels(g2, w)
    assert lv2["g_k2sp"] == 22 and lv2["g_k2w5"] == 24


def test_fires_strict_and_missing():
    s = R.fires([15.20023, 15.21336, np.nan, 14.0], R.A_CAL, strict=True)
    assert s[0] == 0 and s[1] == 1 and math.isnan(s[2]) and s[3] == 0
    assert list(R.fires([20.0, 19.99], 20.0)) == [1.0, 0.0]


def test_either():
    e = R.either([1, 0, np.nan, np.nan, 0], [0, 0, 1, 0, np.nan])
    assert e[0] == 1 and e[1] == 0 and e[2] == 1 and math.isnan(e[3]) and math.isnan(e[4])


def test_cycle_of():
    assert R.cycle_of("2025-03-25 01:00") == pd.Timestamp("2025-03-24 18:00")   # 10 KST uses the 24 March 18 UTC run
    assert R.cycle_of("2025-03-25 05:00") == pd.Timestamp("2025-03-25 00:00")   # 14 KST uses the 25 March 00 UTC run
    assert R.cycle_of("2025-03-25 04:00") == pd.Timestamp("2025-03-24 18:00")
    for h in range(48):
        t = pd.Timestamp("2022-03-04") + pd.Timedelta(hours=h)
        c = R.cycle_of(t)
        assert c.hour % 6 == 0 and pd.Timedelta(hours=5) <= t - c < pd.Timedelta(hours=11)


def test_lead_hours():
    s = np.array([0, 1, 1, 1, np.nan, 1, 1, 0], float)
    assert R.lead_hours(s, 3) == 2
    assert R.lead_hours(s, 6) == 1            # stops at the unknown hour
    assert R.lead_hours(s, 7) is None
    assert R.lead_hours(s, 1) == 0
    assert R.lead_hours(np.ones(40), 39) == 24            # cap
    assert R.lead_hours(np.ones(40), 39, floor_i=30) == 9  # not before the first issue hour


def timeline(run_flags, issue_from, state):
    n = len(run_flags)
    t = pd.date_range("2022-03-03 15:00", periods=n, freq="1h")   # 00 KST on 4 March
    kst = t + pd.Timedelta(hours=9)
    tl = pd.DataFrame(dict(t_utc=t, kst_day=kst.strftime("%Y-%m-%d"), kst_hour=kst.hour,
                           issue=np.arange(n) >= issue_from, run=np.array(run_flags, bool)))
    tl["run"] = tl.run & tl.issue
    return tl, np.array(state, float)


def test_fire_metrics_against_brute_force():
    rng = np.random.default_rng(7)
    for _ in range(200):
        n = 72
        run = rng.random(n) < 0.08
        state = (rng.random(n) < 0.5).astype(float)
        issue_from = 24
        tl, st = timeline(run, issue_from, state)
        rows = R.fire_metrics(tl, st)
        for r in rows:
            idx = np.flatnonzero((tl.kst_day == r["kst_day"]).values & tl.issue.values)
            runs = [i for i in idx if tl.run.iloc[i]]
            assert r["run_hours"] == len(runs) and r["issue_hours"] == len(idx)
            if runs:
                i1 = runs[0]
                assert r["warned"] == bool(st[i1] == 1)
                if r["warned"]:
                    L = 0
                    while i1 - 1 - L >= 0 and L < 24 and st[i1 - 1 - L] == 1:
                        L += 1
                    assert r["lead_h"] == L
                    assert r["lead_h_since_ignition"] == min(L, i1 - issue_from)
                else:
                    assert r["lead_h"] is None
                assert r["run_hours_missed"] == sum(st[i] != 1 for i in runs)
                assert r["warned_lapsed"] == bool(st[max(0, i1 - 12):i1 + 1].sum() > 0)
            else:
                assert r["alarm_no_run"] == bool(st[idx].sum() > 0)


def test_exact_intervals():
    lo, hi = R.clopper_pearson(0, 9)
    assert lo == 0 and abs(hi - 0.3363) < 2e-4          # the kcf-margin "0 of 9: 0-34%"
    lo, hi = R.clopper_pearson(9, 9)
    assert hi == 1 and abs(lo - 0.6637) < 2e-4
    lo, hi = R.garwood(0)
    assert lo == 0 and abs(hi - 3.6889) < 1e-3
    lo, hi = R.garwood(10)
    assert abs(lo - 4.7954) < 1e-3 and abs(hi - 18.3904) < 1e-3
    assert R.sign_test(0, 0) == 1.0 and abs(R.sign_test(5, 0) - 0.0625) < 1e-12 and R.sign_test(3, 3) == 1.0
    # brute force two-sided sign test
    for b, c in itertools.product(range(6), repeat=2):
        n = b + c
        if n:
            p = sum(math.comb(n, i) for i in range(n + 1) if i <= min(b, c) or i >= max(b, c)) / 2 ** n
            assert abs(R.sign_test(b, c) - min(1.0, p)) < 1e-12
