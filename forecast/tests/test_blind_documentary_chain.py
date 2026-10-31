"""Tiny synthetic raw-inventory/documentary chain without recursive self hashes."""
import copy
import json
import pytest

from .test_blind_forecast_protocol import blind, registered, complete_inventory_fixture, documentary_fixture


def pre_run_chain(blind, fixture):
    repo, release, rp, cp, registry, cohort = fixture
    root = release.root
    # The inventory fixture's default2027 release is future at this host date.
    # Set a synthetic release after its July surveys but before documentary review.
    release.manifest["release"]["public_release_utc"] = "2026-10-01T00:00:00Z"
    release.pin()
    cohort["source_release_utc"] = release.manifest["release"]["public_release_utc"]
    cohort["inventory"]["sha256"] = release.pinned_manifest_sha
    for name in ("attestation.json", "inventory-input.json"):
        cohort["input_sha256"][name] = blind.sha(root / name)
    original_inputs = copy.deepcopy(cohort["input_sha256"])
    bindings = blind.clearance_bindings(registry, cohort)
    review = documentary_fixture(blind, root, registry, cohort)
    path = root / "review/pre_run_clearance.json"
    path.parent.mkdir()
    blind.write(path, review)
    cohort["documentary_clearance"] = dict(path=str(path.relative_to(root)), sha256=blind.sha(path))
    blind.write(cp, cohort)
    assert cohort["input_sha256"] == original_inputs
    assert blind.clearance_bindings(registry, cohort) == bindings == review["bindings"]
    return root, rp, cp, registry, cohort, path, bindings


def test_actual_raw_inventory_accepts_separately_pinned_pre_and_post_review_receipts(blind, complete_inventory_fixture):
    root, rp, cp, registry, cohort, path, bindings = pre_run_chain(blind, complete_inventory_fixture)
    repo = complete_inventory_fixture[0]
    _, admitted, references = blind.validate(rp, cp, repo, root)
    clearance = admitted["_documentary_clearance"]
    assert len(references) == 2
    assert clearance["machine_authentication"] is False
    assert clearance["sha256"] == blind.sha(path)
    assert str(path.relative_to(root)) not in cohort["input_sha256"]
    assert "attestation.json" in cohort["input_sha256"]  # Publisher inventory evidence stays pinned.
    original_pre_receipt = path.read_bytes()
    post = documentary_fixture(blind, root, registry, cohort, "post_score_independent_relocated_replay_and_claim")
    post_path = root / "review/post_score_clearance.json"
    blind.write(post_path, post)
    verified = blind.documentary_review(root, str(post_path.relative_to(root)), blind.sha(post_path), registry, admitted,
                                       "post_score_independent_relocated_replay_and_claim")
    assert verified["machine_authentication"] is False
    assert verified["scope"] == "post_score_independent_relocated_replay_and_claim"
    assert post["bindings"] == bindings
    assert path.read_bytes() == original_pre_receipt
    assert str(post_path.relative_to(root)) not in cohort["input_sha256"]
    assert cohort["input_sha256"] == json.loads(cp.read_text())["input_sha256"]
    # Added documentary files remain admitted by actual raw inventory, not a mocked adapter.
    _, again, _ = blind.validate(rp, cp, repo, root)
    assert again["_documentary_clearance"] == clearance


def test_naive_self_inclusion_changes_the_bound_input_closure_and_refuses(blind, complete_inventory_fixture):
    root, rp, cp, registry, cohort, path, bindings = pre_run_chain(blind, complete_inventory_fixture)
    cohort["input_sha256"][str(path.relative_to(root))] = blind.sha(path)
    assert blind.clearance_bindings(registry, cohort) != bindings
    blind.write(cp, cohort)
    with pytest.raises(ValueError, match="complete scope-specific human documentary clearance"):
        blind.validate(rp, cp, complete_inventory_fixture[0], root)
