#!/usr/bin/env python
"""Run the repository's gates and record the result as one JSON file.

The autonomous loop (docs/auto/CHARTER.md) may push to ``auto/dev`` only when
this script exits 0. It never pipes a gate (docs/HANDOFF_ROUND3.md §5 and
scripts/check_gate_invocations.py): every step is a direct subprocess whose exit
status is read, not a shell pipeline.

    python scripts/auto/gates.py --mode quick     # make verify + boot/smoke tests
    python scripts/auto/gates.py --mode full      # + baseline, snapshot, env, full pytest

Writes .auto/gates.json and .auto/<step>.log. ``env-check`` is SOFT: recorded,
reported as a warning, but it does not fail the run — a sandbox that had to fall
back from the pins is still a valid place to run the suite, and env drift is
already visible in .auto/bootstrap.json. Pass --strict to make it hard.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTO = REPO / ".auto"


def run(name: str, cmd: list[str], hard: bool = True) -> dict:
    AUTO.mkdir(exist_ok=True)
    log = AUTO / f"{name}.log"
    t0 = time.time()
    with open(log, "w") as fh:
        proc = subprocess.run(cmd, cwd=REPO, stdout=fh, stderr=subprocess.STDOUT, text=True)
    secs = round(time.time() - t0, 1)
    tail = log.read_text(errors="replace").strip().splitlines()[-3:]
    ok = proc.returncode == 0
    status = "PASS" if ok else ("FAIL" if hard else "WARN")
    print(f"[gates] {status:4} {name:18} exit={proc.returncode} {secs:>7.1f}s  {' | '.join(t.strip() for t in tail[-1:])}")
    return {"name": name, "cmd": cmd, "exit": proc.returncode, "seconds": secs,
            "hard": hard, "passed": ok, "tail": tail, "log": str(log.relative_to(REPO))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["quick", "full"], default="full")
    ap.add_argument("--python", default=None, help="interpreter for make/pytest (default .auto/venv or this one)")
    ap.add_argument("--strict", action="store_true", help="make env-check a hard gate")
    args = ap.parse_args()

    py = args.python
    if py is None:
        cand = AUTO / "venv" / "bin" / "python"
        py = str(cand) if cand.exists() else sys.executable
    # make splices $(PYTHON) into shell recipes verbatim, so a path with spaces
    # (this repository lives under "Korea Code Fair" on the author's laptop) must
    # travel quoted.
    make = ["make", "PYTHON=" + (f'"{py}"' if any(c.isspace() for c in py) else py)]

    steps = [run("verify", make + ["verify"])]
    if args.mode == "full":
        # freeze_baseline.py --check also digests two git-ignored manifests under
        # data/raw/firms_data/ that exist only on the author's laptop (the
        # acquisition record, HANDOFF §5.9). In a clean clone they are MISSING by
        # construction, so the gate is hard only where they exist; elsewhere it
        # still runs and is recorded, but as a warning. The tracked-artifact
        # digests it also checks are covered by verify + snapshot-verify.
        manifest = REPO / "data" / "raw" / "firms_data" / "fire_manifest.json"
        steps.append(run("baseline-verify", make + ["baseline-verify"], hard=manifest.exists()))
        steps.append(run("snapshot-verify", make + ["snapshot-verify"]))
        steps.append(run("env-check", make + ["env-check"], hard=args.strict))
        steps.append(run("pytest-full", [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--durations=15"]))
    else:
        steps.append(run("pytest-quick", [py, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                                          "tests/test_smoke.py", "tests/test_clean_clone_boot.py"]))

    passed = all(s["passed"] or not s["hard"] for s in steps)
    pytest_line = next((s["tail"][-1] for s in steps if s["name"].startswith("pytest") and s["tail"]), "")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    result = {
        "written_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": args.mode, "python": py, "git_head": head, "git_branch": branch,
        "passed": passed, "pytest_summary": pytest_line, "steps": steps,
    }
    AUTO.mkdir(exist_ok=True)
    (AUTO / "gates.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"[gates] {'ALL GREEN' if passed else 'RED'}  mode={args.mode} head={head} ({branch})  -> .auto/gates.json")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
