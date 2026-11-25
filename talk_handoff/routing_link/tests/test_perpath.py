"""Synthetic checks of the Amendment 2 rule (perpath_rule.py) and the per-path pieces of perpath_export.py."""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import perpath_export as E  # noqa: E402
import perpath_rule as PR  # noqa: E402


def test_levels_fixed_before_results():
    assert PR.LEVELS == ("any", "p10", "p50", "p90") and PR.MAIN == "p50"
    assert PR.LEVEL_VALUE == {"any": None, "p10": 0.1, "p50": 0.5, "p90": 0.9}
    assert E.RAD_W_M2 == {"radiant_2p5": 2500.0, "radiant_7p0": 7000.0}
    assert E.CO_PPM == {"co_10": (10, 420.0), "co_30": (30, 150.0), "co_60": (60, 83.0)}


def test_need_counts():
    assert PR.need("any", 1024) == 1
    assert PR.need("p50", 1024) == 512 and PR.need("p10", 1024) == 103 and PR.need("p90", 1024) == 922
    assert PR.need("p50", 128) == 64


def test_first_minute_share_reaches_level():
    c = np.zeros((120, 1, 3), np.uint16)
    c[30:, 0, 0] = 512          # exactly 0.5 from minute 30
    c[10:, 0, 1] = 511          # just below 0.5, but above 'any'
    f50 = PR.first_minute(c, 1024, "p50")
    fany = PR.first_minute(c, 1024, "any")
    assert f50[0, 0] == 30 and np.isinf(f50[0, 1]) and np.isinf(f50[0, 2])
    assert fany[0, 0] == 30 and fany[0, 1] == 10 and np.isinf(fany[0, 2])


def test_visibility_blocks_from_start_of_hour():
    pv = np.zeros((3, 1, 2))
    pv[2, 0, 0] = 600 / 1024
    pv[1, 0, 1] = 1 / 1024
    assert PR.vis_first_minute(pv, "p50", 1024)[0, 0] == 120
    assert np.isinf(PR.vis_first_minute(pv, "p50", 1024)[0, 1])
    assert PR.vis_first_minute(pv, "any", 1024)[0, 1] == 60


def test_audience_rule_and_hours():
    inf = np.inf
    f = {k: np.full((1, 2), inf) for k in ("radiant_2p5", "radiant_7p0", "co_10", "co_30", "co_60", "vis")}
    f["radiant_2p5"][0, 0] = 70.0
    f["co_60"][0, 1] = 200.0
    assert list(PR.audience_first_minute(f, "residents")[0]) == [70.0, 200.0]
    assert list(PR.audience_first_minute(f, "responders")[0]) == [inf, 200.0]
    h = PR.minute_to_hours(PR.audience_first_minute(f, "residents"), 6)
    assert h[:, 0, 0].tolist() == [False, True, True, True, True, True]
    assert h[:, 0, 1].tolist() == [False, False, False, True, True, True]


def test_trailing_means_only_after_cutoff():
    x = np.zeros((1, 20, 1))
    x[0, 5:15, 0] = 10.0
    m = E.trailing_means(x, 10)
    assert np.all(np.isnan(m[0, :9, 0]))
    assert m[0, 14, 0] == 10.0 and m[0, 9, 0] == 5.0 and m[0, 19, 0] == 5.0


def test_path_weights_fraction_of_bin():
    pw = E.PathWeights.__new__(E.PathWeights)
    pw.onset = np.array([[90.0, 0.0]])          # source 0 ignites 30 s into the second minute
    pw.extinction = np.array([[250.0, 3600.0]])  # and goes out 10 s into the fifth minute
    pw.occurrence = np.array([[True, False]])    # source 1 does not burn in this path
    edges = np.arange(0.0, 361.0, 60.0)
    w = pw.weights(np.array([0]), 0, edges)
    assert np.allclose(w[0, :, 0], [0.0, 0.5, 1.0, 1.0, 1 / 6, 0.0])
    assert np.all(w[0, :, 1] == 0.0)
    # later hour: absolute times
    pw.onset, pw.extinction = np.array([[3630.0, 0.0]]), np.array([[3700.0, 0.0]])
    w = pw.weights(np.array([0]), 1, edges)
    assert np.allclose(w[0, :2, 0], [0.5, 40 / 60])


def test_wilson_interval():
    lo, hi = PR.wilson(512, 1024)
    assert lo < 0.5 < hi and abs((hi - lo) / 2 - 0.0306) < 0.001
