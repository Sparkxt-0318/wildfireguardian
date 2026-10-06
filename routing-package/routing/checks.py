"""Explicit package verification, separate from the JSON command-line interface.

Historical experiment freezes live in archive/. REFRACTOR_FREEZE.json identifies
this development release, not a newly frozen scientific experiment.
"""

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def verify_release_hashes(root=PACKAGE_ROOT):
    """Fail before executing tests when a release input has changed."""
    root = Path(root)
    freeze = json.loads((root / "verification/REFRACTOR_FREEZE.json").read_text())
    for name, expected in freeze["hashes"].items():
        path = root / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("release hash mismatch " + name)
    return len(freeze["hashes"])


def check():
    """Run regressions, raw/prepared replay equality and the retained road witness."""
    started = time.perf_counter()
    count = verify_release_hashes()
    subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
        cwd=PACKAGE_ROOT,
        check=True,
    )
    from .replay import replay

    fixture = json.loads((PACKAGE_ROOT / "fixtures/continuity_replay.json").read_text())
    raw_a, raw_b = replay(fixture), replay(fixture)
    prepared_a, prepared_b = replay(fixture, prepare=True), replay(
        fixture, prepare=True
    )
    if raw_a != raw_b:
        raise RuntimeError("replay not deterministic")
    if prepared_a != prepared_b or raw_a != prepared_a:
        raise RuntimeError("prepared replay disagreement")

    witness_path = PACKAGE_ROOT / "verification/road_witness.json"
    from .independent import check_route

    road = json.loads(
        (PACKAGE_ROOT / "fixtures/nangok_full_graph_fixture.json").read_text()
    )
    witness = json.loads(witness_path.read_text())
    checked = check_route(
        road["graph"],
        road["hazard"],
        road["request"],
        witness["legs"],
        witness["destination"],
    )
    if not checked["ok"]:
        raise RuntimeError("packaged full-road witness refused")
    return {
        "status": "PASS",
        "candidate_hashes": count,
        "deterministic_replay": True,
        "full_road_witness_checked": True,
        "elapsed_s": time.perf_counter() - started,
        "forecast_integration": "NOT_AVAILABLE",
        "physical_safety_claim": False,
    }
