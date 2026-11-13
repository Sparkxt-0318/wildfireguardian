"""Synthetic tests for run_leakbound_L.py stages fit/score/report (no part-a data; the extract stage needs real inputs
and is smoke-run by the executor with --limit 2 before the full run)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_leakbound_L as R  # noqa: E402


def test_keep_draw_equals_one_global_draw():
    ys = [np.zeros(7, np.int8), np.array([1, 0, 0], np.int8), np.zeros(11, np.int8)]
    per = np.concatenate(R.draw_keep(ys))
    g = np.random.default_rng(0).random(21) < 0.05
    y = np.concatenate(ys)
    assert np.array_equal(per, (y == 1) | g)


def test_f1_f2():
    assert R.f1_value("2020-07-08T01:10:00+00:00", "2020-07-14T02:20:00+00:00") == np.log1p((6 * 86400 + 4200) / 86400)
    assert R.f1_value("2020-07-15T00:00:00+00:00", "2020-07-14T00:00:00+00:00") == 0.0
    assert R.f2_value("2020-07-08T00:00:00+00:00", "2020-07-08T06:00:00+00:00", 3) == np.log1p(3.0)  # span < 1 day -> 1


def test_fit_same_rows_and_columns():
    rng = np.random.default_rng(1)
    n = 4000
    x = rng.normal(size=(n, 21))
    f1 = rng.normal(size=n)
    y = (rng.random(n) < 1 / (1 + np.exp(-(x[:, 0] + 2 * f1)))).astype(np.int8)
    fitted = R.fit_models(dict(x=x, y=y, f1=f1, f2=np.zeros(n)))
    assert fitted["base"][1].coef_.shape[1] == 21 and fitted["L"][1].coef_.shape[1] == 22 and fitted["L2"][1].coef_.shape[1] == 23
    assert fitted["L"][1].coef_[0][21] > 0  # the informative synthetic F1 gets a positive coefficient


def test_aggregate_and_bootstrap_point():
    y = np.array([0, 1, 0, 1], np.int8)
    band = np.array([True, True, False, False])
    pb, pa = np.array([.2, .6, .1, .3]), np.array([.05, .9, .1, .3])  # 0.1 is NOT in [0, 0.1)
    agg = R.aggregate(y, band, dict(base=pb, L=pa, L2=pa))
    assert agg["band"]["n"] == 2 and abs(agg["band"]["base"]["sse"] - (.04 + .16)) < 1e-12
    assert agg["full"]["L"]["calib_n"] == 1
    pf = {"a": agg, "b": agg}
    b = R.bootstrap(pf, "L", "band", B=50)
    assert abs(b["delta_brier"] - ((.0025 + .01) - (.04 + .16)) / 2) < 1e-12
    assert b["ci95"][0] <= b["delta_brier"] <= b["ci95"][1] and b["material"]
