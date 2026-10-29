"""Adapter regression: frozen copies are byte-identical and law v1 through the adapter reproduces recorded exposures."""
import hashlib
import json
from pathlib import Path

import pytest

from conftest import INPUTS, REPO, ROOT


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_frozen_copies_are_byte_identical_and_listed():
    manifest = json.loads((ROOT / "SOURCE_SHA256.json").read_text())
    for rec in manifest["frozen_copies"]:
        copy, source = ROOT / rec["copy"], REPO / rec["source"]
        assert sha(copy) == rec["sha256"]
        if source.exists():
            assert sha(source) == rec["sha256"]


def test_v1_adapter_reproduces_recorded_uljin_centre_exposure():
    if not (INPUTS / "graphs/uljin_2022/graph.json").exists():
        pytest.skip("frozen routing inputs not available")
    import journey_check as JC
    from journeys import load_returned_journeys
    js = [j for j in load_returned_journeys() if j["case_id"] == "20220304T030000Z_FX1"]
    assert len(js) == 1 and js[0]["arrival"] == 3119 and len(js[0]["legs"]) == 512
    j = js[0]
    case = JC.Case(INPUTS, j["cohort"], j["case_id"])
    out = JC.check_journey(case, j["legs"], j["destination"], radiation_law="v1")
    assert out["ok"] and out["status"] == "CHECKED_ROUTE"
    for mid, rec in j["recorded_centre_per_member"].items():
        assert abs(out["per_member"][mid]["dose"] - rec["dose"]) <= 1e-9 * abs(rec["dose"])
        assert abs(out["per_member"][mid]["peak"] - rec["peak"]) <= 1e-9 * abs(rec["peak"])


def test_v2_adapter_keeps_contact_and_certifies_far_route():
    if not (INPUTS / "graphs/uljin_2022/graph.json").exists():
        pytest.skip("frozen routing inputs not available")
    import journey_check as JC
    from journeys import load_returned_journeys
    j = [j for j in load_returned_journeys() if j["case_id"] == "20220304T030000Z_FX1"][0]
    case = JC.Case(INPUTS, j["cohort"], j["case_id"])
    out = JC.check_journey(case, j["legs"], j["destination"], radiation_law="v2", max_dt_s=2.0, max_ds_m=20.0)
    assert out["contact_ok"]
    for rec in out["per_member"].values():
        assert rec["peak_kw_m2"] <= rec["peak_upper_kw_m2"] + 1e-12
        assert rec["dose_kj_m2"] <= rec["dose_upper_kj_m2"] + 1e-9
