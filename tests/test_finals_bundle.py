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


#: R9's own sentence, read into (name as R9 writes it, a predicate over the paths
#: the committed manifest lists, a written reason when the bundle deliberately does
#: not carry it). This is the `R7_ITEMS` shape from `tests/test_printables.py`, and
#: it is here for the reason WFG-151 was filed: the ONLY place R9's contents had
#: ever reached code was `test_the_bundle_carries_the_four_screens_the_booth_opens`
#: below, which transcribed four of R9's five names and dropped 「printables」. So
#: the bundle omitted the booth kit for a day after the kit shipped, and nothing went
#: red --- because the one test that checks the manifest's contents compares it to
#: `bfb.plan()`, the builder's own plan, and a manifest and its builder can agree
#: with each other forever while both omit the same file.
#:
#: The grounding runs R9's line -> these names -> paths in the COMMITTED MANIFEST.
#: Not the plan. The manifest is the artifact that ships on the USB stick; the plan
#: is a description of it, and a description checked against itself is the defect.
R9_ITEMS: tuple[tuple[str, object, str | None], ...] = (
    ("`web/` whole",
     lambda paths: {"web/finals.html", "web/console.html", "web/field_view.html",
                    "web/refuge_placement.html"} <= paths
     and any(p.startswith("web/assets/fonts/") for p in paths), None),
    ("printables",
     lambda paths: any(p.startswith("printables/") and p.endswith(".pdf")
                       for p in paths)
     and any(p.startswith("printables/") and p.endswith(".json")
             for p in paths), None),
    ("`README_KO.md` with the 10-line run recipe",
     lambda paths: "README_KO.md" in paths, None),
    ("`CITATION.cff`", lambda paths: "CITATION.cff" in paths, None),
    # R9's fifth clause is a property of the build rather than a file, and the
    # property is what `test_rebuilding_the_manifest_reproduces_the_committed_one`
    # and `test_every_hash_in_the_manifest_is_the_hash_of_the_source_file` assert.
    ("`make finals-bundle` rebuilds it byte-identically", None,
     "a property of the builder, not a file in the bundle; asserted by "
     "test_rebuilding_the_manifest_reproduces_the_committed_one"),
)


def test_r9_still_enumerates_the_contents_this_list_resolves() -> None:
    """If R9's wording moves, the mapping above is a reading of a line that changed.

    The same binding `tests/test_printables.py` puts on R7. Without it the list is
    a transcription, and a transcription is what dropped 「printables」.
    """
    readiness = (REPO / "docs" / "auto" / "KCF_READINESS.md").read_text(encoding="utf-8")
    r9 = [line for line in readiness.splitlines() if line.startswith("| R9 |")]
    assert len(r9) == 1, f"expected exactly one R9 row in KCF_READINESS.md, found {len(r9)}"
    missing = [name for name, _pred, _why in R9_ITEMS if name not in r9[0]]
    assert not missing, (
        "docs/auto/KCF_READINESS.md R9 no longer names " + str(missing)
        + ", so R9_ITEMS here is a reading of a line that has changed. Re-read R9 "
        "and rewrite the mapping; do not delete this test.")


def test_the_bundle_carries_every_content_r9_names(manifest):
    """R9 is the definition of done for the bundle; MANIFEST.json is what ships.

    Graded red by removing the printables entry from the plan (drop the
    `newest_printables()` call from `bfb.plan`, or the `printables/` pair from its
    result) and re-running: this fails naming 「printables」, which is the state the
    repository was actually in at `3f881f6`.
    """
    listed = {f["path"] for f in manifest["files"]}
    problems = []
    for name, predicate, why in R9_ITEMS:
        if predicate is None:
            assert why, f"R9 item {name!r} has neither a predicate nor a reason"
            continue
        if not predicate(listed):
            problems.append(name)
    assert not problems, (
        "release/kcf-finals-2026/MANIFEST.json does not carry everything R9 names, "
        "which is the defect WFG-151 was filed for --- the bundle was measured "
        "against the builder's own plan and never against R9:\n  "
        + "\n  ".join(problems)
        + "\nAdd the source to scripts/build_finals_bundle.py and re-run "
        "`make finals-bundle UPDATE=1`, or record here why it is not carried.")


def test_the_bundle_carries_the_newest_booth_kit_and_not_an_older_stamp(manifest):
    """A kit in the bundle is worth nothing if it is last week's kit.

    `docs/auto/finals/printables/` holds every stamp ever built, because CHARTER
    §3.2 forbids overwriting a committed artifact. The bundle must carry the newest,
    and this re-derives which that is from the tree rather than reading the manifest
    back to itself.
    """
    stamps = sorted(p.stem[len("WFG_printables_"):]
                    for p in bfb._tracked(bfb.PRINTABLES)
                    if p.name.startswith("WFG_printables_") and p.suffix == ".pdf")
    assert stamps, "no tracked booth printable in the tree at all"
    newest = stamps[-1]
    listed = {f["path"] for f in manifest["files"]}
    assert f"printables/WFG_printables_{newest}.pdf" in listed, (
        f"the newest booth kit in the tree is {newest} and the bundle does not "
        f"carry it; the bundle's printables are {sorted(p for p in listed if p.startswith('printables/'))}. "
        "Re-run `make finals-bundle UPDATE=1` and commit MANIFEST.json.")
    assert f"printables/manifest_{newest}.json" in listed, (
        f"the bundle carries the {newest} PDF and not the manifest that says what "
        "it was built from, so the sha256 of its sources does not travel with it")
    older = [p for p in listed
             if p.startswith("printables/") and newest not in p]
    assert not older, (
        f"the bundle carries a superseded booth kit beside the newest one: {older}. "
        "The student would have two PDFs on the stick and no way to tell which to "
        "print; docs/printables.md records why the earlier builds must not be.")


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
