"""Exchange format: round-trip I/O, validation rules, version handling."""
import json

import numpy as np
import pytest

from hazard_contract import CONTRACT_VERSION, ContractError, ScenarioSet, synthetic
from helpers import make_set

INF, NAN = np.inf, np.nan


def test_round_trip_preserves_arrays_and_meta(tmp_path):
    s = synthetic(K=3, height=12, width=10, seed=7,
                  unsupported_mask=np.pad(np.ones((2, 2), bool), ((0, 10), (0, 8))))
    s.write(tmp_path / "set")
    r = ScenarioSet.read(tmp_path / "set")
    for name in ("ignite_s", "extinguish_s", "supported"):
        np.testing.assert_array_equal(getattr(r, name), getattr(s, name))  # inf and nan compare equal
    assert r.meta == s.meta
    meta = json.loads((tmp_path / "set" / "meta.json").read_text())
    assert meta["contract_version"] == CONTRACT_VERSION and meta["synthetic"] is True
    assert meta["issue_time_utc"].endswith("Z")


def test_float32_rounds_outward(tmp_path):
    s = make_set([[0.1, 1.0 / 3.0], [INF, NAN]], ex=[[0.1 + 7e-9, 2.0 / 3.0], [INF, NAN]])
    s.write(tmp_path / "f32", dtype="float32")
    r = ScenarioSet.read(tmp_path / "f32")
    sup = s.supported
    assert np.all(r.ignite_s[sup] <= s.ignite_s[sup])
    assert np.all(r.extinguish_s[sup] >= s.extinguish_s[sup])
    assert np.isnan(r.ignite_s[0, 1, 1]) and not r.supported[0, 1, 1]


def test_refuses_unknown_major_version(tmp_path):
    make_set([[0.0]]).write(tmp_path / "v")
    meta = json.loads((tmp_path / "v" / "meta.json").read_text())
    meta["contract_version"] = "2.0"
    (tmp_path / "v" / "meta.json").write_text(json.dumps(meta))
    with pytest.raises(ContractError):
        ScenarioSet.read(tmp_path / "v")


def test_write_refuses_to_overwrite(tmp_path):
    s = make_set([[0.0]])
    s.write(tmp_path / "w")
    with pytest.raises(FileExistsError):
        s.write(tmp_path / "w")
    s.write(tmp_path / "w", overwrite=True)


def test_nan_must_be_unsupported():
    with pytest.raises(ContractError):
        make_set([[NAN]], sup=[[True]])
    s = make_set([[NAN, 0.0]])
    assert s.supported.tolist() == [[[False, True]]]


def test_validation_rules():
    with pytest.raises(ContractError):
        make_set([[10.0]], ex=[[5.0]])                       # extinguish before ignite
    with pytest.raises(ContractError):
        make_set([[INF]], ex=[[5.0]])                        # never burns but extinguishes
    with pytest.raises(ContractError):
        make_set([[-INF]], ex=[[-INF]])                      # extinguish = -inf
    s = make_set([[NAN]], ex=[[5.0]], sup=[[False]])       # anything goes in unsupported cells
    assert not s.supported.any()


def test_synthetic_must_be_labeled():
    s = make_set([[0.0]])
    with pytest.raises(ValueError):
        type(s.meta).model_validate({**s.meta.model_dump(), "synthetic": False})


def test_arrays_are_private_read_only_copies():
    ig = np.zeros((1, 2, 2))
    s = make_set(ig)
    ig[0, 0, 0] = 99.0
    assert s.ignite_s[0, 0, 0] == 0.0
    with pytest.raises(ValueError):
        s.ignite_s[0, 0, 0] = 1.0


def test_edge_burning_flags_members_that_reach_the_grid_edge():
    ig = np.full((2, 4, 4), INF)
    ig[0, 1, 1] = 0.0          # interior only
    ig[1, 0, 2] = 0.0          # edge cell burns
    assert make_set(ig).edge_burning().tolist() == [False, True]
