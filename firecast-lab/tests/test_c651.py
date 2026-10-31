"""c651 SMOKE wrapper. The trajectory bookkeeping is pure numpy and tested on SYNTHETIC states; running the
checkpoint needs PyTorch and the real data root, so those tests skip cleanly when either is missing."""
import os

import numpy as np
import pytest

import synthetic as syn
from firecast_lab import c651
from firecast_lab import data as fd


def test_recorder_keeps_the_first_burn_hour_per_member_across_blocks():
    burned = np.array([[True, False, False]])
    known = np.array([[True, True, False]])
    rec = c651.TrajectoryRecorder(burned, known, K=5, batch_size=2)       # blocks of 2, 2 and 1 members
    for hour in (1, 2):
        for block, size in ((0, 2), (1, 2), (2, 1)):
            states = np.zeros((size, 1, 1, 3), bool)
            states[:, 0, 0, 0] = True                                      # present fire stays burned
            members = np.arange(block * 2, block * 2 + size)
            states[:, 0, 0, 1] = (members % 2 == 0) if hour == 1 else True # even members ignite in hour 1
            rec(block, states, hour)
    assert rec.first[:, 0, 0].tolist() == [c651.AT_CUTOFF] * 5
    assert rec.first[:, 0, 1].tolist() == [1, 2, 1, 2, 1]
    assert rec.first[:, 0, 2].tolist() == [c651.UNKNOWN] * 5


def test_lattice_codes_become_member_hours():
    first = np.array([[[c651.UNKNOWN, c651.NOT_BURNED, c651.AT_CUTOFF, 1, 24]],
                      [[c651.UNKNOWN, c651.NOT_BURNED, c651.AT_CUTOFF, 3, 2]]], dtype=np.int16)
    initial = np.array([[np.nan, np.nan, -2.5, np.nan, np.nan]])
    hours = c651.lattice_to_hours(first, initial, np.array([1.0, 0.25]))
    expected = np.array([[[np.nan, np.inf, -2.5, 1.0, 24.0]], [[np.nan, np.inf, -2.5, 2.25, 1.25]]])
    assert np.array_equal(hours, expected, equal_nan=True)
    with pytest.raises(ValueError, match="offset"):
        c651.lattice_to_hours(first, initial, np.array([0.0, 0.5]))


def test_c651_refuses_to_run_without_the_data_root(monkeypatch):
    monkeypatch.delenv(fd.ENV_VAR, raising=False)
    w = syn.window(np.eye(3, dtype=bool), np.full((3, 3), np.inf))
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        c651.c651_members(None, w, K=4, seed=0)
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        c651.C651(None)


def test_c651_explains_a_missing_torch(tmp_path):
    try:
        import torch  # noqa: F401
        pytest.skip("torch is installed here")
    except ImportError:
        pass
    root = syn.write_root(tmp_path, {"SYNTHETIC_A": syn.fire(seed=0)})
    w = syn.windows("SYNTHETIC_A", *syn.fire(seed=0))[0]
    with pytest.raises(ModuleNotFoundError, match="PyTorch"):
        c651.c651_members(root, w, K=4, seed=0)


def test_case_seed_matches_the_forecast_package():
    pytest.importorskip("torch")
    from wildfire.cumulative_report import case_seed
    assert fd.case_seed(3, "KFS_02", "2022-03-05T02:00:00Z") == case_seed(3, "KFS_02", "2022-03-05T02:00:00Z")


def test_c651_members_on_the_real_data_root():
    pytest.importorskip("torch")
    root = os.environ.get(fd.ENV_VAR)
    if not root:
        pytest.skip(f"set {fd.ENV_VAR} to the real data root to run c651")
    fire = "KFS_02"                                     # a dev fire (c651 in-sample); one window, small K
    w = next(iter(fd.load_windows(root, fire, 24)))
    hours, facts = c651.c651_members(root, w, K=8, seed=0)
    assert hours.shape == (8, *w.inputs.shape) and facts["boundary"] == "zero"
    burned = w.inputs.burned
    assert (hours[:, burned] == w.inputs.initial_h[burned]).all()
