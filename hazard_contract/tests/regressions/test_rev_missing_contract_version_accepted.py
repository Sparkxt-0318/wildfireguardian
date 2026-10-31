# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""CLAUDE.md: "Readers refuse a major version they do not know." ScenarioSet.read validates
meta.json with ScenarioMeta, whose contract_version field DEFAULTS to the reader's own "1.0". A
meta.json that declares no version at all (an unversioned or foreign producer) is therefore read
as v1 instead of being refused: the version gate only fires when a version is written.
"""
import json

import numpy as np
import pytest

import hazard_contract as hc


def test_unversioned_meta_is_refused(tmp_path):
    hc.synthetic(K=1, height=4, width=4, seed=0).write(tmp_path / "s")
    meta = json.loads((tmp_path / "s" / "meta.json").read_text())
    del meta["contract_version"]
    (tmp_path / "s" / "meta.json").write_text(json.dumps(meta))
    with pytest.raises(hc.ContractError):
        hc.ScenarioSet.read(tmp_path / "s")
