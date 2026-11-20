"""Shared constants for the kcf-bench comparison (see PLAN.md). Standard library only."""
from __future__ import annotations

import json
import os
import platform
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("KCF_BENCH_DATA_ROOT", ROOT / "data" / "routing")).resolve()

# (short name, cache path relative to ROOT); order is the order of TALK_NUMBERS row 1
CACHES = [
    ("UA0323", "planner/cache/uiseong_andong_2025/20250323T010000Z.json"),
    ("UA0324", "planner/cache/uiseong_andong_2025/20250324T090000Z.json"),
    ("UA0325", "planner/cache/uiseong_andong_2025/20250325T170000Z.json"),
    ("YD0325T19", "planner/cache/yeongdeok_2025/20250325T190000Z.json"),
    ("YD0325T23", "planner/cache/yeongdeok_2025/20250325T230000Z.json"),
    ("YD0326", "planner/cache/yeongdeok_2025/20250326T080000Z.json"),
]
CACHE_PATH = dict(CACHES)
FULL_A_CACHE = "UA0324"      # smallest cache: fewest jobs (1,518) and least recorded compute (14,749 s)
SAMPLE_SEED = 20261120
SAMPLE_N = 500
REPEAT_N = 50


def load_cache(name: str) -> dict:
    return json.loads((ROOT / CACHE_PATH[name]).read_text())


def job_ids(doc: dict) -> list:
    return sorted(doc["route_checks"])


def sample_jobs(name: str, ids: list) -> dict:
    """Frozen sampling rule (PLAN.md 3): pass-1 set and the 50-job repeat subset, both fixed by SAMPLE_SEED and the
    cache name. Every job of the smallest cache is in its pass-1 set."""
    rnd = random.Random("%d:%s" % (SAMPLE_SEED, name))
    order = rnd.sample(sorted(ids), len(ids))  # a fixed random permutation of the sorted ids
    # Jobs are RUN in permutation order, so any prefix cut short by the hard stop is itself a random sample.
    pass1 = list(order) if name == FULL_A_CACHE else order[:SAMPLE_N]
    repeat = order[:REPEAT_N]                  # the first 50 of the same permutation (a subset of pass 1)
    return {"pass1": pass1, "repeat": repeat, "pass1_head": pass1[:SAMPLE_N], "pass1_tail": pass1[SAMPLE_N:]}


def host_info() -> dict:
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception as exc:  # recorded, not hidden
            return "unavailable: %s" % exc
    libs = {}
    for m in ("numpy", "pyproj", "scipy", "shapely"):
        try:
            libs[m] = __import__(m).__version__
        except Exception:
            libs[m] = None
    return {"platform": platform.platform(), "machine": platform.machine(), "python": sys.version,
            "python_executable": sys.executable, "cpu_count": os.cpu_count(),
            "cpu_model": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
            "cores_perf_eff": [sh(["sysctl", "-n", "hw.perflevel0.physicalcpu"]), sh(["sysctl", "-n", "hw.perflevel1.physicalcpu"])],
            "mem_bytes": sh(["sysctl", "-n", "hw.memsize"]), "os": sh(["sw_vers"]), "libs": libs,
            "git_head": sh(["git", "-C", str(ROOT), "rev-parse", "HEAD"])}
