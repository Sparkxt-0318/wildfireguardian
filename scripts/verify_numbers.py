#!/usr/bin/env python
"""Re-derive every entry in docs/NUMBERS.json from its artifact. Exit 1 on drift.

Round-3 PHASE 1-D.

This script holds NO knowledge of any specific number. It executes the ``check``
block each entry carries, so the registry stays the single source of truth and
this file never has to be edited when a number is added.

    kind = "json_path"    read one path from one artifact
    kind = "expression"   evaluate `expr` over the named `operands`
    kind = "file_sha256"  digest a file

Expressions are evaluated with builtins available but no module globals, which
is adequate for a repo-local integrity check on a file we author ourselves. It
is NOT a sandbox: never point this at an untrusted NUMBERS.json.

Also enforced, because a registry that disagrees with itself is worse than none:

* every ``source_file`` exists;
* declared ``cross_check`` relations hold;
* an entry marked ``reproducible: true`` must not carry a ``blocked_by``.

Run:  python scripts/verify_numbers.py
      python scripts/verify_numbers.py --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"

_CACHE: dict[str, object] = {}


def load(rel: str):
    if rel not in _CACHE:
        p = REPO / rel
        if not p.exists():
            raise FileNotFoundError(rel)
        _CACHE[rel] = json.loads(p.read_text(encoding="utf-8"))
    return _CACHE[rel]


def dig(obj, jpath: str):
    node = obj
    for part in jpath.split("."):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def resolve(spec: dict):
    """Resolve one operand spec to a value."""
    if "json_path" in spec and spec["json_path"] is not None:
        return dig(load(spec["file"]), spec["json_path"])
    p = REPO / spec["file"]
    return hashlib.sha256(p.read_bytes()).hexdigest()


def evaluate(check: dict):
    kind = check["kind"]
    ops = {k: resolve(v) for k, v in check.get("operands", {}).items()}
    if kind in ("json_path", "file_sha256"):
        return ops[check.get("expr", "a")] if check.get("expr", "a") in ops \
            else eval(check["expr"], {}, ops)  # noqa: S307 - repo-local registry
    if kind == "expression":
        return eval(check["expr"], {"__builtins__": __builtins__}, ops)  # noqa: S307
    raise ValueError(f"unknown check kind {kind!r}")


def equal(expected, got, tol: float) -> bool:
    if isinstance(expected, bool) or isinstance(got, bool):
        return bool(expected) == bool(got)
    if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
        return abs(float(expected) - float(got)) <= tol
    return expected == got


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--numbers", default=str(NUMBERS))
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    doc = json.loads(Path(args.numbers).read_text(encoding="utf-8"))
    nums = doc["numbers"]
    fails: list[str] = []
    n_ok = 0

    print(f"verifying {len(nums)} entries in "
          f"{Path(args.numbers).relative_to(REPO)} "
          f"(config_hash {doc.get('config_hash', '?')[:12]}...)\n")

    width = max(len(k) for k in nums)
    for key, e in nums.items():
        # -- source file must exist ------------------------------------------
        src = e.get("source_file")
        if src and not (REPO / src).exists():
            fails.append(f"{key}: source_file missing: {src}")
            print(f"  MISSING  {key:{width}s}  {src}")
            continue

        # -- re-derive --------------------------------------------------------
        try:
            got = evaluate(e["check"])
        except Exception as exc:  # noqa: BLE001
            fails.append(f"{key}: check raised {type(exc).__name__}: {exc}")
            print(f"  ERROR    {key:{width}s}  {type(exc).__name__}: {exc}")
            continue

        tol = float(e["check"].get("tolerance", 0.0))
        if equal(e["value"], got, tol):
            n_ok += 1
            if args.verbose:
                rep = "repro" if e.get("reproducible") else "NOT-repro"
                print(f"  ok       {key:{width}s}  {e['value']!r}   [{rep}]")
        else:
            fails.append(f"{key}: registry {e['value']!r} != artifact {got!r}")
            print(f"  MISMATCH {key:{width}s}\n"
                  f"           registry: {e['value']!r}\n"
                  f"           artifact: {got!r}\n"
                  f"           source  : {src} :: {e.get('json_path')}")

        # -- declared cross-checks -------------------------------------------
        xc = e.get("cross_check")
        if xc:
            other = dig(load(xc["file"]), xc["json_path"])
            if other != e["value"]:
                fails.append(f"{key}: cross_check {xc['file']}::{xc['json_path']} "
                             f"= {other!r} != {e['value']!r}")
                print(f"  XCHECK   {key:{width}s}  {xc['file']}::{xc['json_path']} "
                      f"disagrees")
            elif args.verbose:
                print(f"           cross-check ok: {xc['file']}::{xc['json_path']}")

        # -- internal consistency of the reproducibility claim ---------------
        rep = e.get("reproducibility") or {}
        if e.get("reproducible") and rep.get("blocked_by"):
            fails.append(f"{key}: reproducible=true but blocked_by is set")
            print(f"  INCOHERENT {key}: reproducible=true yet blocked_by is set")

    n_rep = sum(1 for e in nums.values() if e.get("reproducible"))
    print(f"\n  {n_ok}/{len(nums)} entries match their artifacts")
    print(f"  {n_rep}/{len(nums)} are reproducible from the current inputs "
          f"({len(nums) - n_rep} verified-but-not-reproducible)")

    if fails:
        print(f"\nFAILED ({len(fails)}):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nOK — every registered number still matches its artifact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
