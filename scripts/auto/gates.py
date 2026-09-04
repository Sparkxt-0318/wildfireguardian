#!/usr/bin/env python
"""Run the repository's gates and record the result as one JSON file.

The autonomous loop (docs/auto/CHARTER.md) may push to ``auto/dev`` only when
this script exits 0. It never pipes a gate (docs/HANDOFF_ROUND3.md §5 and
scripts/check_gate_invocations.py): every step is a direct subprocess whose exit
status is read, not a shell pipeline.

    python scripts/auto/gates.py --mode quick     # make verify + boot/smoke tests
    python scripts/auto/gates.py --mode full      # + baseline, snapshot, env, full pytest
    python scripts/auto/gates.py --assert-head    # run nothing; answer one question

``--assert-head`` runs no gate. It reads the record the last run left and answers
the only question CHARTER §4 step 8 actually cares about: **is the commit you are
about to push the commit the gates read?** It exits 0 only when ``.auto/gates.json``
says ``passed``, was written in the required mode (``full`` unless ``--mode quick``
says otherwise), names the current ``HEAD``, and the working tree is clean. Twice in
the loop's first three laps a lap ran the gates, then committed 200-plus more lines,
then pushed under an ALL GREEN headline (critic #3, F14); this is the check that
makes that impossible rather than merely discouraged.

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


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def assert_head(required_mode: str) -> int:
    """Exit 0 only if the last gate run passed, in `required_mode`, at this exact tree.

    Reads only .auto/gates.json and git. Runs nothing, so it costs a second and
    can sit immediately before every push.
    """
    record = AUTO / "gates.json"
    if not record.exists():
        print("[gates] ASSERT-HEAD FAIL: no .auto/gates.json — the gates have not run in this sandbox.")
        return 1
    try:
        g = json.loads(record.read_text())
    except json.JSONDecodeError as exc:
        print(f"[gates] ASSERT-HEAD FAIL: .auto/gates.json is not readable JSON ({exc}).")
        return 1

    head, dirty = git("rev-parse", "--short", "HEAD"), git("status", "--porcelain")
    problems = []
    if not g.get("passed"):
        problems.append(f"the recorded run did not pass (mode {g.get('mode')!r}, head {g.get('git_head')!r})")
    if g.get("mode") != required_mode:
        problems.append(f"the recorded run was mode {g.get('mode')!r}, not {required_mode!r}")
    if g.get("git_head") != head:
        problems.append(f"the gates read {g.get('git_head')!r}; HEAD is {head!r}")
    if dirty:
        n = len(dirty.splitlines())
        problems.append(f"the working tree has {n} uncommitted change(s), so HEAD is not what was tested")
    if problems:
        print("[gates] ASSERT-HEAD FAIL — do not push:")
        for p in problems:
            print(f"  - {p}")
        print(f"  fix: re-run `python scripts/auto/gates.py --mode {required_mode}` on the commit you mean to push.")
        return 1
    print(f"[gates] ASSERT-HEAD OK  mode={required_mode} head={head} written_at={g.get('written_at_utc')}")
    return 0


#: Paths a lap may push without a report accompanying them: the report machinery's own
#: outputs, and the backlog claim a lap pushes before it builds (CHARTER §4 step 3).
REPORT_ONLY = ("docs/auto/reports/", "docs/auto/images/", "docs/auto/STATE.json", "docs/auto/dashboard.html")
CLAIM_ONLY = ("docs/auto/BACKLOG.md",)


def assert_reported(base: str) -> int:
    """Exit 0 only if every commit about to be pushed is covered by a report.

    12b8ac7 rewrote the judge-facing README in two languages and closed three
    NEEDS_HUMAN entries with no report, no reviewer and no STATE.json update, and every
    gate passed on it because the numbers it typed had no key (critic #4, F19; WFG-049).
    This check reads ``git diff --name-only <base>..HEAD``: if anything outside
    REPORT_ONLY changed, a new file under docs/auto/reports/ must be part of the same
    range. A push that only claims a backlog row (BACKLOG.md alone) is allowed, because
    the claim is pushed before there is anything to report.
    """
    changed = [l for l in git("diff", "--name-only", f"{base}..HEAD").splitlines() if l.strip()]
    if not changed:
        print(f"[gates] ASSERT-REPORTED OK  nothing to push beyond {base}")
        return 0
    substantive = [f for f in changed if not f.startswith(REPORT_ONLY)]
    reports = [f for f in changed if f.startswith("docs/auto/reports/") and f != "docs/auto/reports/README.md"]
    if not substantive:
        print(f"[gates] ASSERT-REPORTED OK  only report machinery changed since {base}")
        return 0
    if all(f in CLAIM_ONLY for f in substantive):
        print(f"[gates] ASSERT-REPORTED OK  a backlog claim only ({', '.join(substantive)})")
        return 0
    if reports:
        print(f"[gates] ASSERT-REPORTED OK  {len(substantive)} substantive path(s) travel with report {reports[-1]}")
        return 0
    print(f"[gates] ASSERT-REPORTED FAIL — {len(substantive)} path(s) changed since {base} and no report covers them:")
    for f in substantive[:40]:
        print(f"  - {f}")
    print("  fix: write .auto/summary.md and run scripts/auto/report.py, commit the report with the work, then push.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["quick", "full"], default="full")
    ap.add_argument("--python", default=None, help="interpreter for make/pytest (default .auto/venv or this one)")
    ap.add_argument("--strict", action="store_true", help="make env-check a hard gate")
    ap.add_argument("--assert-reported", action="store_true",
                    help="run nothing; fail if commits since --base touch substantive paths with no report")
    ap.add_argument("--base", default="origin/auto/dev", help="for --assert-reported: the ref already pushed")
    ap.add_argument("--assert-head", action="store_true",
                    help="run no gate; exit 0 only if .auto/gates.json records a pass in --mode at this exact HEAD with a clean tree")
    args = ap.parse_args()

    if args.assert_reported:
        return assert_reported(args.base)
    if args.assert_head:
        return assert_head(args.mode)

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
    head, branch = git("rev-parse", "--short", "HEAD"), git("rev-parse", "--abbrev-ref", "HEAD")
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
