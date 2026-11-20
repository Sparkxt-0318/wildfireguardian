"""PROTOCOL A7: no cell inside the known fire at issue may receive the capped spread rate as a stand-in for a flat
arrival field. Fails if any known-fire cell with a zero or undefined gradient has the default-cap provenance, or
(synthetic) a flat known-fire block next to a front of 15 m/min gets anything but a rate taken from that front."""
import math
import os
from pathlib import Path

import numpy as np
import pytest

from kcf_radiation import ros
from kcf_radiation.protocol import R_MAX_M_S, R_MIN_M_S

ROOT = Path(__file__).resolve().parents[3]


def _block(n=11, k=5, s_per_cell=1500.0):
    """Known fire (t = 0) in the top-left k x k block; outside it the arrival grows by s_per_cell per cell."""
    t = np.zeros((n, n))
    for r in range(n):
        for c in range(n):
            if r >= k or c >= k:
                t[r, c] = s_per_cell * (max(r - k + 1, 0) + max(c - k + 1, 0))
    return t


def test_old_behaviour_is_the_cap():
    t = _block()
    R, info = ros.rate_of_spread(t, 375.0, R_MIN_M_S, R_MAX_M_S)
    assert R[1, 1] == R_MAX_M_S and info["undefined_set_to_r_max"] > 0     # the artefact A7 removes


def test_flat_known_fire_cells_do_not_get_the_cap():
    t = _block()
    known = t == 0
    R, info, src = ros.rate_of_spread_with_source(t, 375.0, R_MIN_M_S, R_MAX_M_S, known_fire=known)
    flat_known = known & (src != ros.SRC_GRADIENT)
    assert flat_known.any()
    assert not np.any(src[known] == ros.SRC_DEFAULT_CAP), "a known-fire cell took the default cap"
    assert np.all(R[known] < R_MAX_M_S)
    # the donors are front cells at ~15-30 m/min (375 m per 1500 s = 15 m/min), nowhere near 150
    assert np.all(R[flat_known] * 60 < 40) and np.all(R[flat_known] * 60 > 10)
    assert info["known_fire_flat"] == int(flat_known.sum()) and info["known_fire_flat_no_donor"] == 0


def test_cells_outside_known_fire_keep_the_cap():
    t = _block()
    t[9, 9] = 5000.0
    t[8, 9] = t[9, 8] = t[10, 9] = t[9, 10] = np.nan   # an isolated reached cell, not in the known fire
    R, info, src = ros.rate_of_spread_with_source(t, 375.0, R_MIN_M_S, R_MAX_M_S, known_fire=(t == 0))
    assert src[9, 9] == ros.SRC_DEFAULT_CAP and R[9, 9] == R_MAX_M_S


def test_no_donor_gives_no_rate_not_the_cap():
    t = np.zeros((5, 5))
    R, info, src = ros.rate_of_spread_with_source(t, 375.0, R_MIN_M_S, R_MAX_M_S, known_fire=t == 0)
    assert np.all(src == ros.SRC_NONE) and np.all(np.isnan(R)) and info["known_fire_flat_no_donor"] == 25


def test_known_fire_none_is_the_old_rule():
    t = _block()
    R0, _ = ros.rate_of_spread(t, 375.0, R_MIN_M_S, R_MAX_M_S)
    R1, _, _ = ros.rate_of_spread_with_source(t, 375.0, R_MIN_M_S, R_MAX_M_S, known_fire=None)
    assert np.array_equal(R0, R1, equal_nan=True)


def _check_grid(t):
    known = np.isfinite(t) & (t == 0)
    R, info, src = ros.rate_of_spread_with_source(t, 375.0, R_MIN_M_S, R_MAX_M_S, known_fire=t == 0)
    assert not np.any(src[known] == ros.SRC_DEFAULT_CAP)
    flat = known & (src == ros.SRC_DONOR)
    # a donor-assigned cell is capped only if its donors are themselves capped by a real gradient: report, don't hide
    return int(known.sum()), int(flat.sum()), int(np.sum(R[flat] >= R_MAX_M_S))


@pytest.mark.parametrize("name", ["fire_arrival_20250325T0300Z_MEASURED_8h.tif", "fire_arrival_20250325T0900Z_MEASURED_8h.tif"])
def test_committed_replay_rasters(name):
    pytest.importorskip("rasterio")
    import sys
    sys.path.insert(0, str(ROOT / "product/wfg-roadlayer"))
    from wfg_roadlayer import geotiff
    r = geotiff.read(ROOT / "product/wfg-roadlayer/examples" / name)
    data = np.asarray(r.data, dtype=float)
    H = float(r.metadata["WFG_HORIZON_MIN"]) * 60.0
    t = np.where(np.isfinite(data), np.where(data <= 0, 0.0, np.floor(60.0 * data + 1e-6)), data)
    t = np.where(np.isfinite(t) & (t > H), np.inf, t)
    n_known, n_flat_donor, n_capped_by_donor = _check_grid(t)
    assert n_known > 0 and n_flat_donor > 0


@pytest.mark.skipif(not os.environ.get("WFG_ROUTING_INPUTS"), reason="set WFG_ROUTING_INPUTS to the fetched data/routing directory")
def test_all_finals_packets():
    import json
    base = Path(os.environ["WFG_ROUTING_INPUTS"]) / "latest_inputs_try02/packets"
    packets = sorted(p for rid in base.iterdir() for p in rid.iterdir())
    assert len(packets) == 15
    for p in packets:
        H = float(json.loads((p / "REPORT.json").read_text())["native_metadata"]["construction"]["assumptions"]["horizon_s"])
        with np.load(p / "constructed_arrays.npz", allow_pickle=False) as z:
            ev = np.array(z["ignition_time_s"], dtype=float)
            cur = np.array(z["current_active"], dtype=bool)
            kb = np.array(z["mask__known_burned"], dtype=bool)
        first = np.where(np.isfinite(ev), ev, np.inf).min(axis=0)
        first = np.where(cur | kb, 0.0, first)
        first = np.where(np.isfinite(first), np.floor(first + 1e-9), np.inf)
        first = np.where(first > math.floor(H), np.inf, first)
        _check_grid(np.where(np.isfinite(first), first, np.nan))
