"""Guards for the full-coverage re-run (Round-3 PHASE 3-B).

Two properties matter here and neither is about formatting:

1. The **committed** artifact must be byte-identical to what Round 2 shipped.
   A re-run that quietly rewrote it would destroy the baseline the whole
   provenance effort exists to protect.
2. The re-run's figures are **drift values**, not corrected values. They must
   match the independently-measured arm B, and they must never be presented as
   replacements for the committed ones.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COMMITTED = REPO / "data" / "processed" / "rescue_routing.json"
FULL = REPO / "data" / "processed" / "rescue_routing_full.json"
DRIFT = REPO / "data" / "processed" / "network_drift_experiment.json"
NUMBERS = REPO / "docs" / "NUMBERS.json"

#: The Round-2 committed artifact's digest, pinned.
COMMITTED_SHA256 = "92248e5a78f930cf68bdd6c48155da8f49a1a8f3c6cebc8c8dea2c5eb98ecc3b"

COMMITTED_VALUES = {"n_origins": 439, "n_need_rescue": 167, "n_unreachable": 24}
DRIFT_VALUES = {"n_origins": 441, "n_need_rescue": 174, "n_unreachable": 32}


def _needs(p: Path):
    if not p.exists():
        pytest.skip(f"{p.name} absent")


def test_committed_artifact_is_untouched():
    """THE guard: the full re-run must never modify the committed baseline."""
    _needs(COMMITTED)
    got = hashlib.sha256(COMMITTED.read_bytes()).hexdigest()
    assert got == COMMITTED_SHA256, (
        "data/processed/rescue_routing.json changed. The full-coverage re-run "
        "writes rescue_routing_full.json and must never touch this file.")


def test_committed_values_are_still_the_committed_values():
    _needs(COMMITTED)
    d = json.loads(COMMITTED.read_text())
    assert d["n_origins"] == COMMITTED_VALUES["n_origins"]
    assert d["responder_exposure"]["n_need_rescue"] == COMMITTED_VALUES["n_need_rescue"]
    assert d["responder_exposure"]["n_unreachable"] == COMMITTED_VALUES["n_unreachable"]


def test_full_rerun_reproduces_drift_arm_b():
    """A mismatch would mean the re-run conditions differ from the drift arm."""
    _needs(FULL)
    d = json.loads(FULL.read_text())
    got = {"n_origins": d["n_origins"],
           "n_need_rescue": d["responder_exposure"]["n_need_rescue"],
           "n_unreachable": d["responder_exposure"]["n_unreachable"]}
    assert got == DRIFT_VALUES


def test_full_rerun_agrees_with_the_drift_experiment_artifact():
    _needs(FULL)
    _needs(DRIFT)
    full = json.loads(FULL.read_text())
    drift = json.loads(DRIFT.read_text())
    by = {r["metric"]: r["arm_b_rerun"] for r in drift["metrics"]}
    assert full["n_origins"] == by["n_origins"]
    assert full["responder_exposure"]["n_unreachable"] == by["n_unreachable"]
    assert full["four_way_counts"]["no_safe_pedestrian_route"] == \
        by["no_safe_pedestrian_route"]


def test_every_origin_is_serialized_with_coordinates():
    _needs(FULL)
    d = json.loads(FULL.read_text())
    rows = d["origins_full"]
    assert len(rows) == d["n_origins"] == 441
    for r in rows:
        for k in ("origin_walk_node", "x_5179", "y_5179", "lon_wgs84",
                  "lat_wgs84", "four_way_class"):
            assert k in r, f"origin {r.get('origin_walk_node')} missing {k}"
        assert 128.0 < r["lon_wgs84"] < 131.0
        assert 35.0 < r["lat_wgs84"] < 38.0


def test_serialized_classes_partition_the_four_way_counts():
    _needs(FULL)
    d = json.loads(FULL.read_text())
    counts: dict[str, int] = {}
    for r in d["origins_full"]:
        counts[r["four_way_class"]] = counts.get(r["four_way_class"], 0) + 1
    assert counts == d["four_way_counts"]
    assert sum(counts.values()) == d["n_origins"]
    assert "unresolved" not in counts


def test_full_rerun_read_the_snapshot_not_the_cache():
    _needs(FULL)
    d = json.loads(FULL.read_text())
    prov = d["input_provenance"]
    assert "snapshots" in prov["source"]
    assert "NOT data/cache" in prov["source"]
    for cache_name, info in prov["files"].items():
        assert info["snapshot"].startswith("osm-")
        assert len(info["sha256_uncompressed"]) == 64


def test_the_artifact_states_it_does_not_replace_the_committed_values():
    _needs(FULL)
    d = json.loads(FULL.read_text())
    rel = d["relationship_to_committed"]
    assert rel["committed_values"] == COMMITTED_VALUES
    assert rel["this_run_values"] == DRIFT_VALUES
    assert "do_not" in rel
    assert "network_drift" in rel["why_they_differ"]
    assert "커밋값" in d["label_ko"] and "439" in d["label_ko"]


def test_registry_forbids_substituting_the_drift_values():
    _needs(NUMBERS)
    nums = json.loads(NUMBERS.read_text())["numbers"]
    keys = [k for k in nums if k.startswith("full_rerun_")]
    assert keys, "full-coverage figures must be registered"
    for k in keys:
        e = nums[k]
        joined = " ".join(e["forbidden_phrasings"])
        assert "커밋값" in joined or "replaces" in joined
        assert "커밋값" in e["caveat"]


@pytest.mark.parametrize("key,expected", [
    ("full_rerun_n_origins", 441),
    ("full_rerun_n_need_rescue", 174),
    ("full_rerun_n_unreachable", 32),
    ("full_rerun_origins_serialized", 441),
])
def test_registered_full_rerun_values(key, expected):
    _needs(NUMBERS)
    nums = json.loads(NUMBERS.read_text())["numbers"]
    assert nums[key]["value"] == expected


def test_committed_and_drift_values_are_never_equal():
    """A sanity check on the premise: if these coincided the label would be moot."""
    assert COMMITTED_VALUES != DRIFT_VALUES
