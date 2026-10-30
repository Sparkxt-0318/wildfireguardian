"""Reproduce software-fixture and unchanged-evidence checks, never a campaign."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = "f9d8cd503170a148c845b1592a6b7c1c74ece92d"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(out):
    if out.exists():
        raise ValueError("Write-once receipt, choose a fresh --out")
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(str(ROOT / ("experimental/" + x + "/src")) for x in
                                   ("sipp-routing", "scenario-members", "synthetic-truth"))
    topology_receipt = ROOT / "research/sipp-routing/known-footprint-topology-20261030/RECEIPT.json"
    prior = json.loads(topology_receipt.read_text())
    pins = dict(prior["immutable_prior_source_and_result_pins"])
    for name, expected in prior["outputs"].items():
        pins["research/sipp-routing/known-footprint-topology-20261030/" + name] = expected
    for name in ("KNOWN_FOOTPRINT_CONTACT_PLAN.md", "KNOWN_FOOTPRINT_TOPOLOGY_RESULT.md",
                 "KNOWN_FOOTPRINT_SOURCE_SCOPE.md", "KNOWN_FOOTPRINT_SOURCE_PRECONDITIONS.json",
                 "known-footprint-topology-20261030/RECEIPT.json"):
        path = "research/sipp-routing/" + name
        original = subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)
        pins[path] = hashlib.sha256(original).hexdigest()
    for path, expected in pins.items():
        if digest(ROOT / path) != expected:
            raise ValueError("Prior source/evidence changed: " + path)
    manifest_path = ROOT / "experimental/sipp-routing/SOURCE_SHA256.json"
    manifest = json.loads(manifest_path.read_text())
    source_paths = list(manifest["current_overlay_sources"]) + [str(Path(__file__).relative_to(ROOT))]
    hashes = {path: digest(ROOT / path) for path in source_paths}
    if any(hashes[p] != h for p, h in manifest["current_overlay_sources"].items()):
        raise ValueError("Overlay source manifest mismatch")
    commands = [
        [sys.executable, "-m", "pytest", "experimental/sipp-routing/tests/test_known_footprint.py", "--collect-only", "-q"],
        [sys.executable, "-m", "pytest", "experimental/sipp-routing/tests", "experimental/scenario-members/tests",
         "experimental/synthetic-truth/tests", "-q"],
    ]
    rows = []
    for command in commands:
        p = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180)
        rows.append(dict(command=command, exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr))
        if p.returncode:
            raise RuntimeError("Fixture command failed:\n" + p.stdout + p.stderr)
    for path, expected in {**pins, **hashes}.items():
        if digest(ROOT / path) != expected:
            raise ValueError("Source/evidence changed during checks: " + path)
    target_count = int(re.search(r"(\d+) tests collected", rows[0]["stdout"]).group(1))
    suite = re.search(r"(\d+) passed(?:, (\d+) skipped)?", rows[1]["stdout"])
    out.parent.mkdir(parents=True, exist_ok=True)
    result = dict(schema="wfg.next.known-footprint-contact-adapter/1", status="PASS_SOFTWARE_FIXTURE_SCOPE_REVIEW_PENDING",
                  base_head=BASE, recorded_utc=datetime.now(timezone.utc).isoformat(), producer_sha256=digest(__file__),
                  host=platform.platform(), python=sys.version, numpy=np.__version__, commands=rows,
                  targeted_fixture_cases=target_count, overlay_tests_passed=int(suite.group(1)),
                  overlay_tests_skipped=int(suite.group(2) or 0),
                  overlay_skip_scope="Optional torch export/GIS dependencies remain separate when unavailable.",
                  source_sha256=hashes, manifest_sha256=digest(manifest_path), preserved_evidence_sha256=pins,
                  frozen_sweep_sha256=digest(ROOT / "experimental/sipp-routing/src/wfg_sipp/frozen_sweep.py"),
                  frozen_geometry_sha256=digest(ROOT / "experimental/sipp-routing/src/wfg_sipp/geometry.py"),
                  timing_compatibility_reference=dict(
                    sources={p:digest(ROOT / p) for p in ("experimental/scenario-members/bridge_v2.py", "integration/src/wfg_latest/packets.py")},
                    full_grid_ignition_rule="experimental/scenario-members/bridge_v2.py:41-65",
                    full_construction_and_events="experimental/scenario-members/bridge_v2.py:68-147",
                    full_event_then_exact_window_rule="integration/src/wfg_latest/packets.py:47-71",
                    fixture_K=[4, 8, 16, 32], full_construct_crop_and_prefix_equal=True,
                    independently_cropped_construction_changes_draw_positions=True,
                    scope="Tiny bridge construction only. Compatibility is full native construction followed by exact window restriction, not a new independently cropped construction. No native search or simulation."),
                  graph_evidence=dict(project="wfg-next-1c-audit-e68123d81-20261030", generation="2026-10-30T03:54:43Z",
                    limitation="New adapter/test/report paths missing from immutable graph, docs excluded; direct full-source inspection and executable tests used. Existing core source metadata matched before edits."),
                  checks=dict(prior_evidence_byte_preserved=True, original_graph_geometry_preserved=True,
                              original_frozen_sweep_preserved=True, strict_bridge_default_preserved=True,
                              unknown_values_not_filled=True, histories_not_rebound=True),
                  native_timed_campaign="NOT_RUN_REQUIRES_INDEPENDENT_REVIEW", no_new_trajectories=True,
                  no_simulation=True, no_physical_safety_claim=True, peak_dose_risk="UNKNOWN",
                  limits="Tiny fixtures and ordinary software regression only. No native temporal feasibility, K scaling, thermal policy or risk result. Command runtimes are test-run bookkeeping, not solver performance.")
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(status=result["status"], targeted=target_count,
                          passed=result["overlay_tests_passed"], skipped=result["overlay_tests_skipped"], receipt=str(out))))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    main(p.parse_args().out)
