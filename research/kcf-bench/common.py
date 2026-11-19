"""Shared paths and loaders for the kcf-bench harness (plan: BENCH_PLAN.md)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_ROOT = ROOT / "data" / "routing"
CACHES = ["uiseong_andong_2025/20250323T010000Z", "uiseong_andong_2025/20250324T090000Z",
          "uiseong_andong_2025/20250325T170000Z", "yeongdeok_2025/20250325T190000Z",
          "yeongdeok_2025/20250325T230000Z", "yeongdeok_2025/20250326T080000Z"]
SEED = 20261119
SAMPLE_N = 200
MARGIN_ONE = 60
MARGINS_TEN = [round(600 * i / 9) for i in range(10)]


def short(cache: str) -> str:
    reg, stamp = cache.split("/")
    return {"uiseong_andong_2025": "UA", "yeongdeok_2025": "YD"}[reg] + " " + stamp[4:8] + " " + stamp[9:11] + "Z"


def cases_path(cache: str) -> Path:
    return HERE / "cases" / (cache.replace("/", "__") + ".json")


def load_cases(cache: str) -> dict:
    return json.loads(cases_path(cache).read_text())


def packet_paths(region: str, input_time: str):
    compact = input_time.replace("-", "").replace(":", "")
    return (DATA_ROOT / "graphs" / region / "graph.json",
            DATA_ROOT / "latest_inputs_try02" / "packets" / region / compact)


def specs_of(cases: list) -> dict:
    """{(dest, dwell, window): sorted list of case indices} in a fixed order."""
    out: dict = {}
    for i, c in enumerate(cases):
        out.setdefault((c["dest"], c["dwell"], tuple(c["window"])), []).append(i)
    return dict(sorted(out.items(), key=lambda kv: str(kv[0])))


def add_paths():
    for p in (ROOT, ROOT / "research/harness-2026-11/F-3.1", ROOT / "research/kcf-idea-routing",
              ROOT / "integration/src"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


def vm_kb(field: str) -> int:
    """VmRSS (current) or VmHWM (peak) of this process in kB."""
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith(field + ":"):
                return int(line.split()[1])
    return -1


def cpu_probe() -> float:
    """Fixed pure-Python workload (best of 3), seconds. Logged around every block to show machine speed drift."""
    import time
    best = 1e9
    for _ in range(3):
        t0 = time.perf_counter()
        s = 0
        for i in range(1_500_000):
            s += i * i % 7
        best = min(best, time.perf_counter() - t0)
    return best


def load_state() -> dict:
    """Load average and the steal / total jiffies of /proc/stat."""
    la = open("/proc/loadavg").read().split()[:3]
    cpu = [int(x) for x in open("/proc/stat").readline().split()[1:]]
    return {"loadavg": [float(x) for x in la], "cpu_jiffies": cpu}
