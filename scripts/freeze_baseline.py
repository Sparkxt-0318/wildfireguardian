#!/usr/bin/env python
"""Freeze and re-check the Korean baseline — PHASE 13 PHASE 0.

WHY THIS EXISTS
---------------
The US port re-runs producing scripts on the KOREAN side (to re-derive the same
quantity under a new cluster threshold, a new observation-reference stamp, a new
permutation-importance pass). Every one of those scripts defaults to writing into
``data/processed``:

    run_routing_integration.py   spread_v2_lofo.json, yeongdeok_forward_sim.json,
                                 routing_demo.json, routing_demo.npz
    build_canonical_hazard.py    routing_demo_canonical.npz, canonical_hazard.json
    run_forward_sim_region.py    hazard_{region}.npz, forward_sim_regions.json
    ... and roughly twenty more

So the first careless re-run overwrites artifacts that are IRREPRODUCIBLE — the
OSM graph behind the 459 series was overwritten on 2026-07-24 and cannot be
rebuilt (``docs/DATA_LOSS_2026-07-24.md``). ``make verify`` would not catch it:
it re-derives each registered number FROM its artifact, so an artifact and its
registry entry can move together and still agree.

⚠ THE FOUR `PROTECTED` PATHS ARE NOT ENOUGH. ``run_multi_region_routing.py``
digests four files before and after a run and exits 4 if one moves. That covers
the 459 series and nothing else — not ``spread_v2_lofo.json`` (the headline AUC),
not ``routing_demo_canonical.npz`` (the canonical field), not the eight per-region
hazard fields. This records ALL of them.

WHAT IT DOES
------------
``--freeze``  writes ``docs/baseline_phase13.json``: the sha256 of every tracked
              file under ``data/processed``, the four PROTECTED paths called out
              separately, the config hash, the registry entry count, and the
              sha256 of the git-IGNORED ``fire_manifest.json`` — see below.
``--check``   re-computes and reports every difference, exit 1 if any.

⚠ THE MANIFEST CONTRACT. ``data/raw/firms_data/fire_manifest.json`` is git-ignored
but it IS the training-set definition: ``data.list_fires()`` returns every entry
with no filter, and that list feeds ``features.build_dataset`` in nine scripts.
Adding one US fire to it silently retrains every LOFO fold and rewrites the
headline AUC — with no diff, because the file is not tracked. Recording its
sha256 in a TRACKED file creates the contract the file itself cannot carry.

Run:  python scripts/freeze_baseline.py --check
      make baseline-verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash  # noqa: E402

OUT = REPO / "docs" / "baseline_phase13.json"

#: Digested before and after every routing run by run_multi_region_routing.py,
#: which exits 4 if one moves. Re-stated here because the freeze is a superset.
PROTECTED = (
    "data/processed/real_roads_real_hazard.json",
    "data/processed/real_roads_real_hazard_slope_60.json",
    "data/processed/routing_demo.npz",
    "data/processed/rescue_routing.json",
)

#: Git-ignored, but load-bearing. See the module docstring.
UNTRACKED_CONTRACTS = (
    "data/raw/firms_data/fire_manifest.json",
    "data/raw/firms_data/data_layers_manifest.json",
)

#: The invariant the whole Korean training set reduces to. Asserted by
#: build_canonical_hazard.py:117-127 (exit 2) and, from PHASE 0.5, by
#: run_routing_integration.py as well.
LOFO_SHAPE = {"n_rows": 151904, "n_positives": 2989}


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tracked_processed() -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-files", "data/processed"], cwd=REPO).decode()
    return sorted(p for p in out.splitlines() if p.strip())


def snapshot() -> dict:
    lofo = json.loads((REPO / "data/processed/spread_v2_lofo.json")
                      .read_text(encoding="utf-8"))
    numbers = json.loads((REPO / "docs/NUMBERS.json").read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "title": "Korean baseline freeze — PHASE 13 PHASE 0",
        "frozen_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip(),
        "config_hash": config_hash(),
        "registry_entries": len(numbers["numbers"]),
        "lofo_shape": {"n_rows": lofo["n_rows"],
                       "n_positives": lofo["n_positives"],
                       "pooled_auc": lofo["pooled_auc"],
                       "fires_used": sorted(lofo["fires_used"])},
        "protected": {p: sha256(REPO / p) for p in PROTECTED},
        "untracked_contracts": {p: sha256(REPO / p) for p in UNTRACKED_CONTRACTS},
        "tracked_processed": {p: sha256(REPO / p) for p in tracked_processed()},
    }


def diff(frozen: dict, live: dict) -> list[str]:
    problems: list[str] = []
    for key in ("config_hash", "registry_entries"):
        if frozen[key] != live[key]:
            problems.append(f"{key}: {frozen[key]!r} -> {live[key]!r}")
    for key in ("n_rows", "n_positives", "pooled_auc", "fires_used"):
        if frozen["lofo_shape"][key] != live["lofo_shape"][key]:
            problems.append(f"lofo_shape.{key}: {frozen['lofo_shape'][key]!r} "
                            f"-> {live['lofo_shape'][key]!r}")
    for group in ("protected", "untracked_contracts", "tracked_processed"):
        f, l = frozen[group], live[group]
        for path in sorted(set(f) | set(l)):
            a, b = f.get(path), l.get(path)
            if a == b:
                continue
            if a is None:
                problems.append(f"{group}: NEW {path}")
            elif b is None:
                problems.append(f"{group}: MISSING {path}")
            else:
                problems.append(f"{group}: MOVED {path}\n"
                                f"        {a}\n     -> {b}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--freeze", action="store_true",
                   help="write the baseline record (deliberate; overwrites)")
    g.add_argument("--check", action="store_true",
                   help="re-check the live tree against the record")
    args = ap.parse_args()

    live = snapshot()

    if args.freeze:
        OUT.write_text(json.dumps(live, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"froze {len(live['tracked_processed'])} tracked artifacts, "
              f"{len(PROTECTED)} protected, "
              f"{len(UNTRACKED_CONTRACTS)} untracked contracts")
        print(f"  config_hash      {live['config_hash'][:12]}…")
        print(f"  registry entries {live['registry_entries']}")
        print(f"  LOFO shape       n_rows={live['lofo_shape']['n_rows']:,} "
              f"n_positives={live['lofo_shape']['n_positives']:,}")
        print(f"wrote {OUT.relative_to(REPO)}")
        return 0

    if not OUT.exists():
        print(f"STOP: {OUT.relative_to(REPO)} absent — run --freeze first",
              file=sys.stderr)
        return 2
    frozen = json.loads(OUT.read_text(encoding="utf-8"))
    problems = diff(frozen, live)
    if not problems:
        print(f"baseline intact — {len(live['tracked_processed'])} artifacts, "
              f"config {live['config_hash'][:12]}…, "
              f"LOFO ({live['lofo_shape']['n_rows']:,}, "
              f"{live['lofo_shape']['n_positives']:,})")
        return 0
    print(f"BASELINE MOVED — {len(problems)} difference(s) against "
          f"{frozen['git_commit'][:12]}:", file=sys.stderr)
    for p in problems:
        print(f"  {p}", file=sys.stderr)
    print("\n  If this was deliberate, re-freeze and say so in the commit "
          "message. If it was not, you have overwritten a Korean artifact — "
          "several are IRREPRODUCIBLE (docs/DATA_LOSS_2026-07-24.md).",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
