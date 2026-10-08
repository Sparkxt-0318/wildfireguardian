#!/usr/bin/env python3
"""Verify this organized release and optionally compare preserved source bytes."""
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    release = json.loads((ROOT / "FILE_MANIFEST.json").read_text())
    failures = []
    for name, expected in release["hashes"].items():
        path = ROOT / name
        if not path.is_file() or sha256(path) != expected:
            failures.append("release file changed or missing: " + name)

    provenance = json.loads((ROOT / "verification/SOURCE_PROVENANCE.json").read_text())
    source = Path(provenance["source"])
    library_files = []
    copies = []
    source_status = "NOT_RUN_ORIGINAL_SOURCE_UNAVAILABLE"
    if source.is_dir():
        source_status = "PASS"
        for name, expected in provenance["source_hashes"].items():
            original = source / name
            if not original.is_file() or sha256(original) != expected:
                failures.append("original source changed or missing: " + name)
            organized = ROOT / provenance["path_mapping"][name]
            if name.startswith("routing/") and name.endswith(".py"):
                old_tree = ast.dump(
                    ast.parse(original.read_text()), include_attributes=False
                )
                new_tree = ast.dump(
                    ast.parse(organized.read_text()), include_attributes=False
                )
                if old_tree != new_tree:
                    failures.append("library syntax tree changed: " + name)
                library_files.append(name)
            elif sha256(organized) != expected:
                failures.append("archived/data/test copy changed: " + name)
            else:
                copies.append(name)
    result = {
        "status": "FAIL" if failures else "PASS",
        "release_files_checked": len(release["hashes"]),
        "original_source_verification": source_status,
        "unchanged_library_syntax_trees": library_files,
        "byte_identical_original_copies": len(copies),
        "failures": failures,
        "interpretation": "Preservation and packaging check; not physical or performance validation",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(verify())
