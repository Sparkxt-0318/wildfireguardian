"""The Korean baseline freeze — PHASE 13 PHASE 0.

WHAT THIS GUARDS, AND WHY `make verify` DOES NOT
------------------------------------------------
`make verify` re-derives every registered number FROM its artifact. So if a
re-run moves an artifact AND `build_numbers.py` is re-run over the moved
artifact, the two agree and `make verify` passes — while the number has silently
changed. The registry is a consistency check, not a fixity check.

That is exactly the failure the US port invites: the port re-runs Korean
producing scripts (to re-derive the same quantity under a new cluster threshold,
a new observation-reference stamp, a new permutation-importance pass), and every
one of those scripts defaults to writing into `data/processed`. Several of the
artifacts there are IRREPRODUCIBLE — the OSM graph behind the 459 series was
overwritten on 2026-07-24 (`docs/DATA_LOSS_2026-07-24.md`).

⚠ AND THE MANIFEST. `data/raw/firms_data/fire_manifest.json` is git-ignored but
it IS the training-set definition: `data.list_fires()` returns every entry with
no filter, and that feeds `features.build_dataset` in nine scripts. Adding one US
fire silently retrains every LOFO fold — with no diff, because the file is not
tracked. Its sha256 is recorded in a TRACKED file so the contract exists even
though the file cannot carry it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

RECORD = REPO / "docs" / "baseline_phase13.json"


@pytest.fixture(scope="module")
def frozen() -> dict:
    assert RECORD.exists(), "run `make baseline-freeze` first"
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_the_record_exists_and_is_tracked():
    """A freeze in an untracked file guards nothing."""
    out = subprocess.check_output(
        ["git", "ls-files", "--error-unmatch", str(RECORD.relative_to(REPO))],
        cwd=REPO, stderr=subprocess.STDOUT).decode()
    assert "baseline_phase13.json" in out


@pytest.mark.skipif(
    not (REPO / "data" / "raw" / "firms_data" / "fire_manifest.json").exists(),
    reason="laptop-only acquisition manifests absent (git-ignored)")
def test_the_live_tree_matches_the_record():
    """The headline assertion. `make baseline-verify` in test form.

    Carries the same condition as the gate itself: `freeze_baseline.py --check`
    digests two git-ignored manifests under data/raw/firms_data/ that a clean
    clone cannot have (HANDOFF §5.9), so scripts/auto/gates.py runs the gate as
    hard only where they exist. This is that gate in test form and it is scoped
    the same way, rather than failing every clone by construction.
    """
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "freeze_baseline.py"), "--check"],
        cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"baseline moved:\n{r.stderr}"


def test_the_four_protected_paths_are_all_covered(frozen):
    """PROTECTED is what run_multi_region_routing.py digests. The freeze is a
    superset of it, not a replacement — both must agree on the same four."""
    import run_multi_region_routing as mr

    assert set(frozen["protected"]) == set(mr.PROTECTED)
    for path, digest in frozen["protected"].items():
        assert digest is not None, f"{path} is protected but absent"
        assert path in frozen["tracked_processed"], (
            f"{path} is protected but not in the tracked sweep — the freeze must "
            f"be a superset")


def test_the_freeze_covers_what_protected_does_not(frozen):
    """⚠ The four PROTECTED paths cover the 459 series and nothing else.

    Not spread_v2_lofo.json (the headline AUC). Not routing_demo_canonical.npz
    (the canonical field). Not the per-region hazard fields. Those are precisely
    the artifacts the port re-runs.
    """
    import run_multi_region_routing as mr

    tracked = set(frozen["tracked_processed"])
    for path in ("data/processed/spread_v2_lofo.json",
                 "data/processed/routing_demo_canonical.npz",
                 "data/processed/hazard_uiseong_andong_2025.npz",
                 "data/processed/hazard_uljin_samcheok_2022.npz",
                 "data/processed/multi_region_comparison.json",
                 "data/processed/osm_completeness.json"):
        assert path in tracked, f"{path} escapes the freeze"
        assert path not in set(mr.PROTECTED), (
            f"{path} is in PROTECTED now — update this test's premise")


def test_the_git_ignored_manifest_has_a_tracked_contract(frozen):
    """The manifest defines the training set and produces no diff when edited."""
    manifest = "data/raw/firms_data/fire_manifest.json"
    assert manifest in frozen["untracked_contracts"]
    assert frozen["untracked_contracts"][manifest] is not None

    # It really is untracked — if that ever changes, this contract is redundant
    # and should be retired rather than left as a second source of truth.
    r = subprocess.run(["git", "ls-files", "--error-unmatch", manifest],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode != 0, (
        "fire_manifest.json is now tracked; retire the sha256 contract")


def test_the_lofo_shape_is_pinned(frozen):
    """(151904, 2989) is what the entire Korean training set reduces to.

    build_canonical_hazard.py:117-127 hard-stops on it. Nothing else does yet —
    PHASE 0.5 adds the same check to run_routing_integration.py.
    """
    assert frozen["lofo_shape"]["n_rows"] == 151904
    assert frozen["lofo_shape"]["n_positives"] == 2989
    assert len(frozen["lofo_shape"]["fires_used"]) == 6
    assert "mckinney_2022" not in frozen["lofo_shape"]["fires_used"]


def test_a_moved_artifact_is_actually_detected(tmp_path, frozen):
    """A guard nobody has seen fail is a guard nobody should trust.

    Mutate the frozen record rather than the artifact, so the working tree is
    never touched — same comparison, opposite side.
    """
    import freeze_baseline as fb

    live = fb.snapshot()
    tampered = json.loads(json.dumps(frozen))
    key = "data/processed/spread_v2_lofo.json"
    tampered["tracked_processed"][key] = "0" * 64

    problems = fb.diff(tampered, live)
    assert any(key in p and "MOVED" in p for p in problems)

    tampered2 = json.loads(json.dumps(frozen))
    tampered2["lofo_shape"]["n_rows"] = 999999
    assert any("lofo_shape.n_rows" in p for p in fb.diff(tampered2, live))

    # Everything above needs no git-ignored input and so runs in every clone —
    # that is the half that actually proves the guard bites. The two below need
    # a tree that HAS the laptop-only acquisition manifests (HANDOFF §5.9): in a
    # clean clone the third would pass on the MISSING line rather than on the
    # tamper it means to detect, which is a green nobody should trust, and the
    # last compares the whole record against a tree missing two entries.
    m = "data/raw/firms_data/fire_manifest.json"
    if not (REPO / m).exists():
        pytest.skip("laptop-only acquisition manifests absent (git-ignored)")

    tampered3 = json.loads(json.dumps(frozen))
    tampered3["untracked_contracts"][m] = "0" * 64
    assert any(m in p for p in fb.diff(tampered3, live))

    assert fb.diff(frozen, live) == [], "the untampered record must still match"


def test_all_checks_runs_the_baseline_gate():
    """A gate that is not wired into the standard target will not be run."""
    mk = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "baseline-verify" in mk
    for line in mk.splitlines():
        if line.startswith("all-checks:"):
            assert "baseline-verify" in line, (
                "make all-checks must include the baseline gate")
            break
    else:
        pytest.fail("no all-checks target found")
