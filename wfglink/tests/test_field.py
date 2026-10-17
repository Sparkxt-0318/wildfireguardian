"""Ember velocity field: one sample per track per cell, outlier handling, display status."""
import numpy as np
import pandas as pd

from wfglink.config import load_config
from wfglink.measure.field import estimate_field, normalized_median_test, track_cell_samples


def _points(n_tracks_per_cell, u=100.0, v=20.0, size=(160, 90), grid=(16, 9), seed=0, bad_cell=None):
    rng = np.random.default_rng(seed)
    w, h = size
    cols, rows = grid
    rows_out = []
    tid = 0
    for r in range(rows):
        for c in range(cols):
            for _ in range(n_tracks_per_cell):
                tid += 1
                uu, vv = (u, v) if (r, c) != bad_cell else (-u, -v)
                for k in range(6):   # six points of one track in the cell; a slow lingerer counts once
                    rows_out.append({"track_id": tid, "t": k / 30, "x_meas": (c + 0.5) * w / cols,
                                     "y_meas": (r + 0.5) * h / rows, "vx_poly": uu + rng.normal(0, 5),
                                     "vy_poly": vv + rng.normal(0, 5), "static": False})
    return pd.DataFrame(rows_out)


def test_one_sample_per_track_per_cell():
    s = track_cell_samples(_points(3), (160, 90), (16, 9))
    assert len(s) == 3 * 16 * 9 and (s["points"] == 6).all()


def test_estimate_status_and_interval():
    cfg = load_config()
    f = estimate_field(_points(12), (160, 90), cfg)
    assert (f["status"] == "ci").all()
    assert np.allclose(f["u"], 100, atol=3) and np.allclose(f["v"], 20, atol=3)
    assert ((f["u_lo"] <= 100) & (100 <= f["u_hi"])).mean() > 0.8
    f6 = estimate_field(_points(6), (160, 90), cfg)
    assert (f6["status"] == "hatched").all() and f6["u_lo"].isna().all()
    f3 = estimate_field(_points(3), (160, 90), cfg)
    assert (f3["status"] == "hidden").all()


def test_normalized_median_test_flags_a_reversed_cell():
    cfg = load_config()
    f = estimate_field(_points(6, bad_cell=(4, 8)), (160, 90), cfg)
    flagged = f[f["status"] == "outlier"]
    assert list(zip(flagged["row"], flagged["col"])) == [(4, 8)]


def test_median_test_needs_three_neighbours():
    u = np.zeros((3, 3)); v = np.zeros((3, 3)); valid = np.zeros((3, 3), bool)
    valid[0, 0] = valid[0, 1] = True
    u[0, 1] = 1000
    assert not normalized_median_test(u, v, valid, 2.0, 3.0).any()
