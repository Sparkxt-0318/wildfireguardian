"""Write-once source/clock repair receipt; only ordinary software fixtures run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
REVIEWED = "fd8bf2e78532b76d2dd2cfd094d3499def90fc23"
PRESERVED = (
    "experimental/sipp-routing/tests/test_known_footprint.py",
    "experimental/sipp-routing/docs/KNOWN_FOOTPRINT_CONTACT.md",
    "research/sipp-routing/KNOWN_FOOTPRINT_ADAPTER_RECEIPT.json",
    "research/sipp-routing/verify_known_footprint_adapter.py",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(out):
    if out.exists():
        raise ValueError("Write-once repair receipt, choose a fresh --out")
    preserved = {}
    for path in PRESERVED:
        reviewed = subprocess.check_output(["git", "show", REVIEWED + ":" + path], cwd=ROOT)
        expected = hashlib.sha256(reviewed).hexdigest()
        if sha(ROOT / path) != expected:
            raise ValueError("Reviewed artifact changed: " + path)
        preserved[path] = expected
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(str(ROOT / ("experimental/" + p + "/src")) for p in
                                   ("sipp-routing", "scenario-members", "synthetic-truth"))
    collect = [sys.executable, "-m", "pytest", "experimental/sipp-routing/tests/test_known_footprint_boundaries.py", "--collect-only", "-q"]
    p = subprocess.run(collect, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=30)
    if p.returncode:
        raise RuntimeError(p.stdout + p.stderr)
    repair_cases = int(re.search(r"(\d+) tests collected", p.stdout).group(1))
    # Reuse the unchanged verifier for full overlay tests, all source-manifest
    # checks and the original 35 immutable source/census evidence checks.
    with tempfile.TemporaryDirectory(prefix="known-footprint-repair-") as tmp:
        receipt = Path(tmp) / "fixture-regression.json"
        command = [sys.executable, "research/sipp-routing/verify_known_footprint_adapter.py", "--out", str(receipt)]
        verified = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=240)
        if verified.returncode:
            raise RuntimeError(verified.stdout + verified.stderr)
        result = json.loads(receipt.read_text())
    for path, expected in preserved.items():
        if sha(ROOT / path) != expected:
            raise ValueError("Reviewed artifact changed during verification: " + path)
    result.update(schema="wfg.next.known-footprint-contact-adapter-repair/1",
                  status="PASS_SOURCE_CLOCK_REPAIR_FIXTURES_RECHECK_PENDING", reviewed_head=REVIEWED,
                  repair_producer_sha256=sha(__file__), repair_recorded_utc=datetime.now(timezone.utc).isoformat(),
                  reviewed_artifacts_preserved_sha256=preserved,
                  repair_fixture_cases=repair_cases, total_contact_fixture_cases=result["targeted_fixture_cases"] + repair_cases,
                  repair_collect=dict(command=collect, exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr),
                  repaired_boundaries=["Canonical consumed cutoff-state consistency before current-fire construction",
                                       "Fractional member validity refused; exclusive terminal requires integer dwell",
                                       "Unrepresentable timestamp precision refused before datetime parsing"],
                  source_admission_reference=dict(path="integration/src/wfg_latest/contract.py", lines="185-241",
                                                  sha256=sha(ROOT / "integration/src/wfg_latest/contract.py")),
                  exact_clock_contract="RFC3339 seconds with 0..6 fractional digits and Z or HH:MM offset; no fractional offset seconds",
                  clock_domain="Source and member validity whole seconds; inclusive terminal permits exact fractional dwell, exclusive terminal requires integer dwell",
                  graph_evidence=dict(project="wfg-next-1c-audit-fd8bf2e7-20261030", generation="2026-10-30T07:47:04Z",
                    limitation="Reviewed source/tests/verifier metadata matched before repair; edited/new paths inspected directly. Canonical integration subtree excluded, direct exact-source fallback used."),
                  native_timed_campaign="NOT_RUN_REQUIRES_INDEPENDENT_RECHECK", no_new_trajectories=True,
                  no_simulation=True, no_physical_safety_claim=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(status=result["status"], original_contact_cases=result["targeted_fixture_cases"],
                          repair_cases=repair_cases, passed=result["overlay_tests_passed"],
                          skipped=result["overlay_tests_skipped"], receipt=str(out))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    main(parser.parse_args().out)
