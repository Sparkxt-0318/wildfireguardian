"""Tests for the staging file and for the eval tree's own house rules.

The staging file is the audit trail between a modeling agent's claim and
``docs/NUMBERS.json``, which is a human gate. If it can hold a malformed entry,
it is not an audit trail.
"""

import json
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
STAGING = EVAL / "numbers_staging.json"
DOCS = ["SIGNOFF.md", "LEAKAGE.md", "KILLSHOT_TEMPLATE.md", "NUMBERS_PROTOCOL.md"]


@pytest.fixture(scope="module")
def staging():
    return json.loads(STAGING.read_text(encoding="utf-8"))


def test_the_staging_file_parses_and_declares_its_schema(staging):
    assert staging["schema_version"] == 1
    assert staging["owner"] == "A6"
    assert staging["protocol"] == "research/eval/NUMBERS_PROTOCOL.md"
    assert isinstance(staging["entries"], list)


def test_the_declared_states_and_levels_match_the_protocol(staging):
    assert set(staging["states"]) == {
        "staged", "verified", "disputed", "withdrawn",
        "withdrawn_pending_condition", "promoted"}
    assert staging["rerun_levels"] == ["L0", "L1", "L2", "L3"]


def test_no_number_exists_yet_because_no_direction_is_signed_off(staging):
    assert staging["entries"] == [], (
        "an entry appeared before any direction was signed off; check the "
        "sign-off ledger before accepting it")


def test_every_entry_carries_every_required_field(staging):
    required = set(staging["required_fields"])
    for entry in staging["entries"]:
        missing = required - set(entry)
        assert not missing, "entry %r is missing %r" % (entry.get("id"), sorted(missing))
        assert entry["state"] in staging["states"]
        assert entry["rerun"]["level"] in staging["rerun_levels"]


def test_the_registrar_shape_matches_scripts_build_numbers(staging):
    """The fourteen fields of ``entry()`` in ``scripts/build_numbers.py``.

    Staging in the registrar's own shape is what makes the eventual promotion a
    mechanical patch rather than a re-derivation. If that helper's signature
    moves, this test is the thing that notices.
    """
    assert staging["registrar_entry_fields"] == [
        "value", "unit", "source_file", "json_path", "derivation",
        "config_hash", "config_hash_at_production", "git_commit", "sample",
        "caveat", "forbidden_phrasings", "check", "reproducibility",
        "reproducible"]
    assert staging["direction_staging_file"] == "research/<direction>/numbers_staged.json"
    for entry in staging["entries"]:
        missing = set(staging["registrar_entry_fields"]) - set(entry["registrar_entry"])
        assert not missing, "entry %r registrar block is missing %r" % (
            entry.get("id"), sorted(missing))


def test_a_registered_number_names_a_committed_json_artifact(staging):
    for entry in staging["entries"]:
        block = entry["registrar_entry"]
        if entry["state"] in ("verified", "promoted"):
            assert block["source_file"].endswith(".json"), (
                "entry %r cannot be registered: source_file must be a committed "
                "JSON artifact that dig() can resolve" % entry.get("id"))
            assert block["json_path"], "entry %r has no json_path" % entry.get("id")
            assert block["forbidden_phrasings"], (
                "entry %r is verified with no forbidden phrasings, so nothing "
                "stops it being written bare" % entry.get("id"))


def test_a_verified_entry_was_actually_re_run(staging):
    for entry in staging["entries"]:
        if entry["state"] in ("verified", "promoted"):
            assert entry["rerun"]["level"] != "L0", (
                "entry %r is marked verified on an L0 re-run, which is reading "
                "the author's own output" % entry.get("id"))
            assert entry["split"]["fingerprint"], (
                "entry %r is verified without a split fingerprint" % entry.get("id"))


def test_the_protocol_documents_all_exist():
    for name in DOCS:
        path = EVAL / name
        assert path.is_file(), "%s is missing" % name
        assert path.read_text(encoding="utf-8").strip(), "%s is empty" % name


def test_the_ledger_records_all_three_directions():
    text = (EVAL / "signoffs" / "LEDGER.md").read_text(encoding="utf-8")
    for direction in ("roads", "landslides", "suppression"):
        assert direction in text


def test_the_eval_tree_carries_no_em_dash():
    """Program scope rule 5. No pragma, no exemption, checked locally.

    ``research/shared/check_research_claims.py`` only scans files git already
    tracks, so a brand new file passes that gate for free until it is committed.
    This test closes that window for the tree A6 owns.
    """
    em_dash = chr(0x2014)          # built at runtime so this file has none
    offenders = []
    for path in sorted(EVAL.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".py", ".json"}:
            continue
        if "__pycache__" in path.parts:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if em_dash in line:
                offenders.append("%s:%d" % (path.relative_to(EVAL), i))
    assert not offenders, "em dash found at %r" % offenders
