#!/usr/bin/env python3
"""Check every tracked document against the registry of WITHDRAWN CLAIMS (WFG-062).

Why this script exists
----------------------
Before it, a withdrawn claim was gated by naming the files it was allowed to be absent
from.  ``tests/test_detection_ordering_is_not_claimed.py`` carries four claim families and
five hand-written guard lists between them, covering **11 files** out of the 988 tracked
``.md`` and ``.html`` files in this repository.  Every escape the loop has actually paid
for was a FILE nobody had listed, not a spelling nobody had patterned:

* WFG-063 found the withdrawn ordering table alive in ``docs/SESSION19_REPORT.md``, "a
  session report nobody had listed";
* WFG-070 found the same claim alive in English in ``docs/auto/research/`` — two files at
  first, and a third (``R7_rubric_gap.md``) that the row itself did not know about.

So this checker inverts the default.  Its scope is **every tracked file with a registered
extension**, and the exception class is written down in the registry with a reason per
entry: the loop's own record surfaces, whose job is to quote a withdrawn claim in order to
record that it was withdrawn.  A new document asserting a registered claim tomorrow is
caught without anyone editing a list, which is the sentence WFG-062 was filed on.

What it does NOT do
-------------------
It reads **spellings**, not meaning.  It is a copy-paste ratchet, exactly like the string
families it draws its patterns from, and its sensitivity to a REWORDING of a withdrawn
claim is unchanged by construction: the patterns are the same patterns.  The structural
rules (``priority_violations``, ``english_ordering_violations``) that try to catch
rewordings are NOT driven from here — they need per-language sentence reconstruction and
stay in their own file.  Read ``docs/withdrawn_claims.md`` before quoting any number about
this gate at a booth.

Usage
-----
    python scripts/check_withdrawn_claims.py            # exit 1 on any unlicensed hit
    python scripts/check_withdrawn_claims.py --json     # machine-readable report
    python scripts/check_withdrawn_claims.py --coverage # what is gated, and what is not
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "docs" / "auto" / "withdrawn_claims.json"

#: The same pragma `scripts/check_forbidden.py` and the claim families use.  A gate with
#: its own private escape hatch is a gate people learn to route around.
PRAGMA = re.compile(r"(?:#|//|<!--)\s*forbidden-ok:\s*(.*?)\s*(?:-->|$)")


def load_registry(path: Path = REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tracked_files(registry: dict) -> list[str]:
    """Every tracked file with a registered extension, in `git ls-files` order.

    `git ls-files` rather than a filesystem walk: an untracked scratch file is not part of
    the repository and a lap should not be blocked by one, and the ignored `data/raw/**`
    bundle must never be read (CHARTER §4, sandbox facts).
    """
    exts = tuple(registry["scope"]["extensions"])
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout
    return [f for f in out.split("\0") if f and f.endswith(exts)]


def record_paths(registry: dict) -> list[str]:
    return [e["path"] for e in registry["scope"]["record_prefixes"]]


def is_record(rel: str, registry: dict) -> bool:
    """True when `rel` is inside the registry's one exception class.

    A prefix ending in `/` matches a directory; anything else must match the path exactly,
    so `docs/auto/MEMO.md` cannot silently exempt `docs/auto/MEMO_v2.md`.
    """
    for p in record_paths(registry):
        if p.endswith("/"):
            if rel.startswith(p):
                return True
        elif rel == p:
            return True
    return False


def gated_files(registry: dict) -> list[str]:
    return [f for f in tracked_files(registry) if not is_record(f, registry)]


def _pragma_tokens(line: str) -> set[str]:
    out: set[str] = set()
    for m in PRAGMA.finditer(line):
        out |= {t.strip() for t in m.group(1).split(",") if t.strip()}
    return out


def _compiled(registry: dict) -> list[tuple[str, str, str, re.Pattern[str]]]:
    """(claim id, token, why, compiled pattern) for every registered spelling."""
    out = []
    for claim in registry["claims"]:
        for s in claim["spellings"]:
            flags = re.IGNORECASE if "i" in s.get("flags", "") else 0
            out.append((claim["id"], s["token"], s["why"], re.compile(s["pattern"], flags)))
    return out


def scan_text(text: str, registry: dict) -> list[dict]:
    """Every registered spelling in `text` that no `forbidden-ok:` pragma licenses.

    The pragma may sit on the offending line or the line directly above it, matching
    `scripts/check_forbidden.py`: a caveat is naturally written above the thing it caveats.
    """
    lines = text.splitlines()
    rules = _compiled(registry)
    found: list[dict] = []
    for i, line in enumerate(lines):
        allowed = _pragma_tokens(line)
        if i:
            allowed |= _pragma_tokens(lines[i - 1])
        for claim_id, token, why, rx in rules:
            if rx.search(line) and token not in allowed:
                found.append(
                    {"line": i + 1, "claim": claim_id, "token": token,
                     "why": why, "text": line.strip()}
                )
    return found


def scan_repo(registry: dict) -> dict[str, list[dict]]:
    hits: dict[str, list[dict]] = {}
    for rel in gated_files(registry):
        path = REPO / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found = scan_text(text, registry)
        if found:
            hits[rel] = found
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--coverage", action="store_true", help="print what is gated and what is not")
    args = ap.parse_args(argv)

    registry = load_registry()
    all_files = tracked_files(registry)
    gated = gated_files(registry)

    if args.coverage:
        print(f"registry           : {REGISTRY.relative_to(REPO)} v{registry['version']}")
        print(f"claims             : {len(registry['claims'])}")
        print(f"spellings          : {sum(len(c['spellings']) for c in registry['claims'])}")
        print(f"tracked in scope   : {len(all_files)} files {tuple(registry['scope']['extensions'])}")
        print(f"gated              : {len(gated)}")
        print(f"record class       : {len(all_files) - len(gated)} files, "
              f"{len(record_paths(registry))} declared paths")
        for e in registry["scope"]["record_prefixes"]:
            print(f"  - {e['path']:<34} {e['why']}")
        return 0

    hits = scan_repo(registry)
    if args.json:
        print(json.dumps({"gated": len(gated), "files_with_hits": len(hits), "hits": hits},
                         ensure_ascii=False, indent=2))
        return 1 if hits else 0

    if not hits:
        print(f"=== check_withdrawn_claims: PASSED === "
              f"{len(registry['claims'])} claims over {len(gated)} gated files")
        return 0

    print(f"=== check_withdrawn_claims: FAILED === {sum(len(v) for v in hits.values())} "
          f"unlicensed mention(s) of a withdrawn claim in {len(hits)} file(s)\n")
    for rel, found in sorted(hits.items()):
        for h in found:
            print(f"  {rel}:{h['line']}  [{h['claim']} · {h['token']}]  {h['text'][:110]}")
    print("\nEach of these claims was withdrawn because no committed artifact supports it.")
    print("If you are naming one in order to withdraw, quote or record it, license the line")
    print("with its own token, e.g.  <!-- forbidden-ok: 신고 일차 -->  on the line above.")
    print(f"The claims, and what to say instead, are in {REGISTRY.relative_to(REPO)}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
