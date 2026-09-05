"""The finals release bundle is what the student carries, so it is checked, not trusted.

WFG-036 v1, KCF_READINESS R9. `release/kcf-finals-2026/` is assembled by
`scripts/build_finals_bundle.py` from files already in the tree, and the claim the
row makes is that `make finals-bundle` rebuilds it byte-identically. A claim about
bytes is worth exactly the test that re-derives them, so these tests hash the source
files themselves and compare, rather than reading the builder's own report.

The root objection this lap recorded against its own plan was that a `release/`
directory is a second place for `web/` to go stale. The answer is that no payload
file is authored here and none is committed: the manifest is the committed artifact,
and these tests are what make it one.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import build_finals_bundle as bfb  # noqa: E402

BUNDLE = REPO / "release" / "kcf-finals-2026"
MANIFEST = BUNDLE / "MANIFEST.json"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_the_manifest_is_committed_and_covers_every_planned_file(manifest):
    """A manifest that lists fewer files than the bundle holds proves nothing."""
    planned = {dst for _, dst in bfb.plan()}
    listed = {f["path"] for f in manifest["files"]}
    assert listed == planned, (
        "MANIFEST.json and the builder's plan disagree about what is in the bundle; "
        f"only in the manifest: {sorted(listed - planned)}; "
        f"only in the plan: {sorted(planned - listed)}"
    )
    assert len(listed) >= 12, f"the bundle lost files: {len(listed)}"


def test_every_hash_in_the_manifest_is_the_hash_of_the_source_file(manifest):
    """The bundle equals the tree, re-derived here rather than read from the builder.

    This is the byte-identical rebuild R9 asks for, stated as the property it means:
    a payload file in the bundle is the repository's file, unchanged. It is also the
    check that catches a USB copy corrupting silently, which is the booth failure
    with no recovery.
    """
    wrong = []
    for entry in manifest["files"]:
        src = REPO / entry["source"]
        assert src.is_file(), f"{entry['source']} is gone; the bundle has a hole"
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        if digest != entry["sha256"] or src.stat().st_size != entry["bytes"]:
            wrong.append(entry["path"])
    assert not wrong, (
        "the manifest's hashes are stale against the tree they claim to describe. "
        "Run `make finals-bundle UPDATE=1` and commit MANIFEST.json: " + str(wrong)
    )


def test_the_bundle_carries_the_four_screens_the_booth_opens(manifest):
    """R9 names `web/` whole. The screens are the product; the rest is packaging."""
    listed = {f["path"] for f in manifest["files"]}
    for screen in ("web/finals.html", "web/console.html", "web/field_view.html",
                   "web/refuge_placement.html"):
        assert screen in listed, f"the bundle does not carry {screen}"
    assert any(p.startswith("web/assets/fonts/") for p in listed), (
        "the bundle carries no fonts, so the screens would fall back to system faces "
        "on the booth laptop"
    )
    for named in ("CITATION.cff", "LICENSE", "README_KO.md"):
        assert named in listed, f"the bundle does not carry {named}"


def test_the_run_recipe_exists_and_is_ten_numbered_steps():
    """R9 asks for a ten-line run recipe, and a judge's laptop is not the place to
    discover that it is nine steps or twenty."""
    text = (BUNDLE / "README_KO.md").read_text(encoding="utf-8")
    recipe = text.split("## 실행 방법", 1)[1].split("\n## ", 1)[0]
    numbered = re.findall(r"^(\d+)\. ", recipe, re.M)
    assert numbered == [str(n) for n in range(1, 11)], (
        f"the run recipe is not ten numbered steps 1-10 but {numbered}"
    )
    assert "Wi-Fi" in text and "file://" in text, (
        "the recipe no longer says to turn Wi-Fi off and open the file directly, which "
        "is the whole claim the screen makes at the booth"
    )


def test_the_payload_is_not_committed():
    """The bundle's reason to exist is that it is derived. A committed payload would be
    a second copy of `web/` drifting beside the first (CHARTER §3.2) — one copy plus a
    hash instead of two copies.

    An earlier version of this docstring gave a second reason, that a committed copy
    would put a duplicate of every retired figure into `check_forbidden.py`'s prose
    scope. It is false: that scan's `is_authored_prose()` is `endswith(".md")`, so no
    `.html` copy could add a finding. Withdrawn here and in `docs/finals_bundle.md`
    rather than quietly dropped.

    `.gitignore` is the thing that enforces the choice, so `.gitignore` is what is
    asserted.
    """
    ignored = (REPO / ".gitignore").read_text(encoding="utf-8")
    for rule in ("release/kcf-finals-2026/web/",
                 "release/kcf-finals-2026/CITATION.cff",
                 "release/kcf-finals-2026/LICENSE"):
        assert rule in ignored, f".gitignore no longer ignores the bundle payload {rule}"


def test_rebuilding_the_manifest_reproduces_the_committed_one(manifest):
    """Two runs on the same tree agree, or 'byte-identical' is a word not a property."""
    built = bfb.manifest_of(bfb.plan())
    assert not bfb.differences(built, manifest), (
        "a fresh manifest differs from the committed one: "
        + str(bfb.differences(built, manifest))
    )
    again = bfb.manifest_of(bfb.plan())
    assert built == again, "two manifests of the same tree differ; the builder is not pure"


def test_the_makefile_exposes_the_target_the_readme_tells_the_student_to_run():
    make = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "\nfinals-bundle:" in make, "make finals-bundle is gone"
    assert "make finals-bundle" in (BUNDLE / "README_KO.md").read_text(encoding="utf-8")
