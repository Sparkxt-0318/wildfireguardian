"""Reporting runs retain authenticated original predictions through reuse chains."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from tests.test_observed_reuse import stored, save, sha, snapshot, resign_case
from wildfire.observed_reuse import authenticate_reuse


def second_generation(stored, tmp_path, historical=True):
    current = deepcopy(stored.target)
    if historical:
        current["implementation_sha256"].update({"rollout.py": "optimized current rollout",
            "observed_evaluation.py": "optimized current runner", "rollout_cache.py": "current cache"})
    first = authenticate_reuse(stored.config, current)
    child = stored.config.output_dir
    case_dir = child / "cases" / stored.case["case_id"]
    first.copy_case(stored.case, case_dir)
    child_protocol = deepcopy(current)
    child_protocol["configuration"]["output_dir"] = str(child)
    save(child / "protocol.json", child_protocol)
    save(child / "report.json", dict(status="complete", protocol=child_protocol,
        models=json.loads((case_dir / "report.json").read_text())["models"]))
    config = SimpleNamespace(**{**vars(stored.config), "reuse_results": child,
        "output_dir": tmp_path / "third"})
    target = deepcopy(child_protocol)
    target["configuration"]["output_dir"] = str(config.output_dir)
    return SimpleNamespace(config=config, target=target, child=child, case_dir=case_dir)


@pytest.mark.parametrize("historical", [False, True])
def test_second_generation_retains_original_exports_and_origin(stored, tmp_path, historical):
    chain = second_generation(stored, tmp_path, historical)
    before_original, before_child = snapshot(stored.source), snapshot(chain.child)
    source = authenticate_reuse(chain.config, chain.target)
    validated = source.validate_case(stored.case)
    assert validated["origin_directory"] == stored.source
    assert validated["prediction_origin"] == ("historical" if historical else "current")
    assert len(validated["reuse_ancestry"]) == 1
    destination = chain.config.output_dir / "cases" / stored.case["case_id"]
    proof = source.copy_case(stored.case, destination)
    assert proof["source_directory"] == str(chain.child)
    assert proof["origin_directory"] == str(stored.source)
    assert proof["origin_prediction_kind"] == ("historical" if historical else "current")
    assert proof["models_reexecuted"] is False
    assert (destination / "m548_prediction.npz").read_bytes() == (stored.case_dir / "m548_prediction.npz").read_bytes()
    assert snapshot(stored.source) == before_original
    assert snapshot(chain.child) == before_child


def test_third_generation_recursively_authenticates_every_ancestor(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    source = authenticate_reuse(chain.config, chain.target)
    grandchild = chain.config.output_dir
    source.copy_case(stored.case, grandchild / "cases" / stored.case["case_id"])
    grandchild_protocol = deepcopy(chain.target)
    save(grandchild / "protocol.json", grandchild_protocol)
    save(grandchild / "report.json", dict(status="complete", protocol=grandchild_protocol,
        models=source.report["models"]))
    config = SimpleNamespace(**{**vars(chain.config), "reuse_results": grandchild,
        "output_dir": tmp_path / "fourth"})
    validated = authenticate_reuse(config, grandchild_protocol).validate_case(stored.case)
    assert len(validated["reuse_ancestry"]) == 2
    assert validated["origin_directory"] == stored.source
    assert validated["prediction_origin"] == "historical"


@pytest.mark.parametrize("field,value", [
    ("source_protocol_sha256", "wrong parent root"),
    ("source_report_sha256", "wrong parent report"),
    ("source_prediction_implementation", {}),
    ("prediction_origin", "current"),
    ("models_reexecuted", True),
    ("source_case_directory", "/wrong/case"),
    ("copied_exports", ["report.json"]),
    ("source_manifest", {}),
])
def test_tampered_parent_provenance_is_rejected(stored, tmp_path, field, value):
    chain = second_generation(stored, tmp_path)
    path = chain.case_dir / "reuse_provenance.json"
    proof = json.loads(path.read_text())
    proof[field] = value
    save(path, proof)
    source = authenticate_reuse(chain.config, chain.target)
    with pytest.raises(ValueError, match="authenticated parent"):
        source.validate_case(stored.case)
    assert not chain.config.output_dir.exists()


def test_parent_root_changed_after_copy_is_rejected(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    path = stored.source / "protocol.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="authenticated parent run"):
        authenticate_reuse(chain.config, chain.target).validate_case(stored.case)


def test_resigned_parent_export_cannot_change_a_copied_prediction(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    path = stored.case_dir / "report.json"
    path.write_text(path.read_text() + " ")
    resign_case(stored.case_dir)
    with pytest.raises(ValueError, match="exports differ"):
        authenticate_reuse(chain.config, chain.target).validate_case(stored.case)


def test_parent_export_corruption_is_never_missing_or_fallback(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    path = stored.case_dir / "m548_prediction.npz"
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="checksum manifest"):
        authenticate_reuse(chain.config, chain.target).validate_case(stored.case)


def test_missing_parent_run_cannot_authorize_descendant(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    (stored.source / "protocol.json").unlink()
    with pytest.raises(FileNotFoundError):
        authenticate_reuse(chain.config, chain.target).validate_case(stored.case)


def test_missing_original_case_is_corruption_rather_than_a_missing_descendant(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    (stored.case_dir / "report.json").unlink()
    with pytest.raises(ValueError, match="no authentic completed parent case"):
        authenticate_reuse(chain.config, chain.target).validate_case(stored.case)


def test_reuse_provenance_symlink_is_rejected(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    path = chain.case_dir / "reuse_provenance.json"
    moved = tmp_path / "elsewhere.json"
    path.rename(moved)
    path.symlink_to(moved)
    with pytest.raises(ValueError, match="must not be symlinks"):
        authenticate_reuse(chain.config, chain.target).validate_case(stored.case)


def test_reuse_cycle_is_rejected_before_recursive_authentication(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    path = chain.case_dir / "reuse_provenance.json"
    proof = json.loads(path.read_text())
    proof["source_directory"] = str(chain.child)
    save(path, proof)
    with pytest.raises(ValueError, match="cycle"):
        authenticate_reuse(chain.config, chain.target).validate_case(stored.case)


def test_older_proof_without_parent_report_hash_remains_authentic(stored, tmp_path):
    chain = second_generation(stored, tmp_path)
    path = chain.case_dir / "reuse_provenance.json"
    proof = json.loads(path.read_text())
    proof.pop("source_report_sha256")
    save(path, proof)
    assert authenticate_reuse(chain.config, chain.target).validate_case(stored.case)["origin_directory"] == stored.source
