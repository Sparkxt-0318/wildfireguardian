#!/usr/bin/env python
"""Build ``docs/artifact_manifest.json`` — every artifact a document cites.

Session 18, Phase 2. The provenance rule says a cited number must be traceable
to an artifact. It was being broken at the root: 41 registry entries pointed at
files under ``data/processed/**`` that were gitignored, so they existed only on
the machine the work was done on. Nobody else — a collaborator, a judge at a
booth, John on a different laptop — could check them.

The fix has two halves. Small text artifacts are COMMITTED (the gitignore was
narrowed, not removed). This manifest is the other half: for every cited
artifact, whether committed or not, it records

    path, sha256, bytes, kind, git-tracked?, regeneration command,
    and the commit at which the file was last generated

so that even a file too large to commit is verifiable — you regenerate it and
compare the digest.

    python scripts/build_artifact_manifest.py            # write the manifest
    python scripts/build_artifact_manifest.py --check    # gate: does it match?

⚠ WHAT THE REGENERATION COMMANDS ARE, AND ARE NOT. Where NUMBERS.json states an
explicit ``Regenerate: ...`` line, that string is used verbatim. Where it does
not, the command is inferred from which script writes the path, and where even
that is ambiguous the field is the literal string ``UNKNOWN`` rather than a
plausible guess. A wrong regeneration command is worse than an absent one: it
looks like provenance and is not.

⚠ THE DIGEST IS OF THE FILE AS IT STANDS, not a claim that re-running the
command reproduces it byte-for-byte. Several of these artifacts embed a
timestamp or a host string. The digest detects that a file CHANGED; it does not
by itself certify determinism.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
MANIFEST = REPO / "docs" / "artifact_manifest.json"

TEXT_SUFFIXES = (".json", ".csv", ".md", ".txt", ".yaml", ".yml", ".geojson")
PATH_RE = re.compile(r"data/processed/[A-Za-z0-9_./\-]+")


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                       env={"GIT_DISCOVERY_ACROSS_FILESYSTEM": "1",
                            "PATH": "/usr/bin:/bin:/usr/local/bin"})
    return r.stdout.strip()


def cited_paths() -> dict[str, dict]:
    """Every data/processed path a registry entry or a committed .md cites."""
    out: dict[str, dict] = {}

    nums = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    for key, e in nums.items():
        paths = set()
        if e.get("source_file"):
            paths.add(e["source_file"])
        for op in (e.get("check", {}).get("operands", {}) or {}).values():
            if isinstance(op, dict) and op.get("file"):
                paths.add(op["file"])
        if e.get("cross_check", {}).get("file"):
            paths.add(e["cross_check"]["file"])
        regen = None
        m = re.search(r"Regenerate:\s*(.+?)(?:\.\s|\.$|$)", e.get("derivation", ""),
                      re.S)
        if m:
            regen = " ".join(m.group(1).split())
        for p in paths:
            r = out.setdefault(p, {"registry_entries": [], "cited_by_docs": [],
                                   "regenerate": None})
            r["registry_entries"].append(key)
            if regen and not r["regenerate"]:
                r["regenerate"] = regen

    for f in _git("ls-files", "*.md").splitlines():
        try:
            text = (REPO / f).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for p in set(PATH_RE.findall(text)):
            p = p.rstrip("./")
            out.setdefault(p, {"registry_entries": [], "cited_by_docs": [],
                               "regenerate": None})["cited_by_docs"].append(f)
    return out


def _writers() -> tuple[dict[str, str], dict[str, set[str]]]:
    """Which script writes which artifact, inferred two ways.

    1. FULL PATH in a string literal — unambiguous, taken directly.
    2. BASENAME in a string literal — most scripts build their output as
       ``OUT / "name.json"``, so the full path never appears. A basename match
       is accepted ONLY when exactly one script mentions it; a basename claimed
       by two scripts is left UNKNOWN rather than resolved by guessing.
    """
    by_path: dict[str, str] = {}
    by_base: dict[str, set[str]] = {}
    for script in sorted((REPO / "scripts").glob("*.py")):
        if script.name == "build_artifact_manifest.py":
            continue
        try:
            tree = ast.parse(script.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)):
                continue
            v = node.value
            for p in PATH_RE.findall(v):
                by_path.setdefault(p.rstrip("./"), f"python scripts/{script.name}")
            if "/" not in v and v.endswith(TEXT_SUFFIXES + (".npz", ".csv.gz")):
                by_base.setdefault(v, set()).add(f"python scripts/{script.name}")
    return by_path, by_base


def build() -> dict:
    cited = cited_paths()
    by_path, by_base = _writers()
    tracked = set(_git("ls-files").splitlines())

    entries = []
    for p in sorted(cited):
        f = REPO / p
        if not (f.exists() and f.is_file()):
            continue
        b = f.read_bytes()
        base_hits = by_base.get(Path(p).name, set())
        regen = (cited[p]["regenerate"]
                 or by_path.get(p)
                 or (next(iter(base_hits)) if len(base_hits) == 1 else None)
                 or "UNKNOWN")
        entries.append({
            "path": p,
            "bytes": len(b),
            "sha256": hashlib.sha256(b).hexdigest(),
            "kind": "text" if p.endswith(TEXT_SUFFIXES) else "binary",
            "git_tracked": p in tracked,
            "n_registry_entries": len(cited[p]["registry_entries"]),
            "cited_by_docs": sorted(set(cited[p]["cited_by_docs"])),
            "regenerate": regen,
        })

    total = sum(e["bytes"] for e in entries)
    untracked = [e for e in entries if not e["git_tracked"]]
    return {
        "_README": (
            "Every artifact under data/processed/ that a committed document or "
            "a NUMBERS.json entry cites. A registry entry must resolve to a "
            "file that is EITHER git-tracked OR listed here with a digest and "
            "a regeneration command; scripts/verify_numbers.py enforces that. "
            "The digest is of the file as it stands and detects change; it is "
            "not by itself a determinism claim. 'regenerate' is UNKNOWN where "
            "the command could not be established, never a guess."),
        "generated_at_git_commit": _git("rev-parse", "HEAD"),
        "n_artifacts": len(entries),
        "total_bytes": total,
        "total_mib": round(total / 1048576, 2),
        "n_git_tracked": len(entries) - len(untracked),
        "n_untracked_manifest_only": len(untracked),
        "n_regenerate_unknown": sum(1 for e in entries
                                    if e["regenerate"] == "UNKNOWN"),
        "artifacts": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the manifest is stale or a digest moved")
    a = ap.parse_args()

    fresh = build()
    if not a.check:
        MANIFEST.write_text(json.dumps(fresh, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"wrote {MANIFEST.relative_to(REPO)}: {fresh['n_artifacts']} "
              f"artifacts, {fresh['total_mib']} MiB, "
              f"{fresh['n_git_tracked']} tracked, "
              f"{fresh['n_regenerate_unknown']} with UNKNOWN regeneration")
        return 0

    if not MANIFEST.exists():
        print(f"missing {MANIFEST.relative_to(REPO)}", file=sys.stderr)
        return 1
    old = json.loads(MANIFEST.read_text(encoding="utf-8"))
    a_old = {e["path"]: e for e in old["artifacts"]}
    a_new = {e["path"]: e for e in fresh["artifacts"]}
    problems = []
    for p in sorted(set(a_old) | set(a_new)):
        if p not in a_old:
            problems.append(f"cited but not in the manifest: {p}")
        elif p not in a_new:
            problems.append(f"in the manifest but no longer present/cited: {p}")
        elif a_old[p]["sha256"] != a_new[p]["sha256"]:
            problems.append(f"digest moved: {p}\n"
                            f"      manifest {a_old[p]['sha256'][:16]}...\n"
                            f"      on disk  {a_new[p]['sha256'][:16]}...")
    if problems:
        print("ARTIFACT MANIFEST IS STALE:\n")
        for x in problems:
            print(f"  - {x}")
        print("\nIf the change was intended, re-run "
              "`python scripts/build_artifact_manifest.py` and say so in the "
              "commit message.")
        return 1
    print(f"OK — {len(a_new)} cited artifacts match the manifest "
          f"({old['total_mib']} MiB).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
