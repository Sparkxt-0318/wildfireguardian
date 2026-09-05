"""`scripts/check_bundle_copy.py` — graded against the ways a bundle copy goes wrong.

WFG-037. The script exists because `make finals-bundle` cannot answer the question the
booth actually asks (it overwrites the folder from the repository before hashing it),
so the value of this file is entirely in the mutations: a checker that returns "fine"
on a corrupted stick is worse than no checker, because the student would trust it.

Every test builds its own bundle folder under `tmp_path`. Nothing here reads
`release/kcf-finals-2026/`, which is git-ignored and absent in a clean clone.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "check_bundle_copy.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_bundle_copy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mod = _load()


def _bundle(root: Path, files: dict[str, bytes]) -> Path:
    """Write ``files`` under ``root`` and the MANIFEST.json that describes them."""
    entries = []
    for rel, payload in sorted(files.items()):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        entries.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
                "source": rel,
            }
        )
    (root / "MANIFEST.json").write_text(
        json.dumps({"bundle": "test", "files": entries}, indent=2), encoding="utf-8"
    )
    return root


@pytest.fixture()
def bundle(tmp_path: Path) -> Path:
    return _bundle(
        tmp_path / "kcf-finals-2026",
        {
            "README_KO.md": "실행 방법\n".encode("utf-8"),
            "web/finals.html": b"<html>screen</html>",
            "web/assets/fonts/a.woff2": b"\x00\x01font",
        },
    )


def test_an_intact_copy_passes(bundle: Path):
    assert mod.check(bundle) == []


def test_a_corrupted_file_of_the_same_length_is_caught(bundle: Path):
    # The failure that has no other detector: a byte flipped in place. Size is
    # unchanged, so anything short of a hash reports the folder as fine.
    target = bundle / "web" / "finals.html"
    payload = bytearray(target.read_bytes())
    payload[3] ^= 0x20
    target.write_bytes(bytes(payload))
    problems = mod.check(bundle)
    assert len(problems) == 1
    assert problems[0].startswith("CORRUPT")
    assert "web/finals.html" in problems[0]


def test_a_truncated_file_is_caught_and_named_by_size(bundle: Path):
    (bundle / "web" / "finals.html").write_bytes(b"<html>")
    problems = mod.check(bundle)
    assert len(problems) == 1
    assert problems[0].startswith("SIZE")


def test_a_missing_file_is_caught(bundle: Path):
    (bundle / "web" / "assets" / "fonts" / "a.woff2").unlink()
    problems = mod.check(bundle)
    assert len(problems) == 1
    assert problems[0].startswith("MISSING")
    assert "web/assets/fonts/a.woff2" in problems[0]


def test_an_extra_file_is_caught(bundle: Path):
    # A stray file is how a payload the manifest does not describe reaches the booth,
    # and it is the same class the repository-side builder refuses.
    (bundle / "web" / "extra.html").write_bytes(b"x")
    problems = mod.check(bundle)
    assert len(problems) == 1
    assert problems[0].startswith("EXTRA")


def test_the_manifest_itself_is_not_reported_as_extra(bundle: Path):
    assert not any("MANIFEST.json" in p for p in mod.check(bundle))


def test_a_folder_without_a_manifest_fails_rather_than_passing_vacuously(tmp_path: Path):
    empty = tmp_path / "not-the-bundle"
    empty.mkdir()
    problems = mod.check(empty)
    assert len(problems) == 1
    assert "MANIFEST.json" in problems[0]


def test_an_unreadable_manifest_fails_rather_than_raising(bundle: Path):
    (bundle / "MANIFEST.json").write_text("{ not json", encoding="utf-8")
    problems = mod.check(bundle)
    assert len(problems) == 1
    assert "unreadable" in problems[0]


def test_the_check_never_writes_to_the_folder(bundle: Path):
    """The whole point against `make finals-bundle`, so it is asserted and not assumed."""
    before = {
        p.relative_to(bundle).as_posix(): (p.stat().st_size, p.read_bytes())
        for p in sorted(bundle.rglob("*"))
        if p.is_file()
    }
    (bundle / "web" / "finals.html").write_bytes(b"<html>corrupt but same len!!</html>")
    mod.check(bundle)
    after = {
        p.relative_to(bundle).as_posix(): (p.stat().st_size, p.read_bytes())
        for p in sorted(bundle.rglob("*"))
        if p.is_file()
    }
    assert set(before) == set(after)
    # every file except the one this test corrupted is byte-identical
    for rel in before:
        if rel != "web/finals.html":
            assert before[rel] == after[rel], rel


def test_main_exits_zero_on_an_intact_copy_and_one_on_a_broken_one(bundle: Path):
    assert mod.main([str(bundle)]) == 0
    (bundle / "README_KO.md").unlink()
    assert mod.main([str(bundle)]) == 1


def test_main_refuses_a_path_that_is_not_a_folder(tmp_path: Path):
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    assert mod.main([str(f)]) == 1


def test_the_script_imports_nothing_outside_the_standard_library():
    """It has to run on a borrowed machine with a bare python3 and no repository."""
    source = SCRIPT.read_text(encoding="utf-8")
    imported = {
        line.split()[1].split(".")[0]
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    }
    assert imported <= {"argparse", "hashlib", "json", "sys", "pathlib", "__future__"}, imported
