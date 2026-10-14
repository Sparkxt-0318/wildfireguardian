"""Parameter sweeps over node density, delivery probability, timing noise, grid failure
rate, device type and an upstream substation trip. All results are SYNTHETIC.

Usage: .venv/bin/python scripts/03_sweeps.py [--fire-seeds 5] [--obs-seeds 2] [--workers 4] [--only NAME]
Writes results/sweeps.csv and results/sweeps_meta.json.
"""
import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lastgasp.pipeline import get_fire, load_config, run_one  # noqa: E402
from lastgasp.provenance import git_info  # noqa: E402

SWEEPS = {
    "meter_density": ("observe.meter_fraction", [0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0], {}),
    "delivery": ("observe.meter.p_deliver", [0.2, 0.4, 0.6, 0.8, 0.95, 1.0], {}),
    "timing_noise": ("observe.timing_noise_multiplier", [0.1, 0.25, 0.5, 1.0, 2.0, 4.0], {}),
    "grid_failure": ("grid.grid_failure_multiplier", [0.0, 0.25, 0.5, 1.0, 2.0, 4.0], {}),
    "tag_density": ("observe.tag_fraction", [0.01, 0.02, 0.05, 0.1, 0.2, 0.5],
                    {"observe.meter_fraction": 0.0}),
    "substation_trip": ("grid.substation_trip_min", [None, 80, 60, 40, 20], {}),
}
SCENARIOS = {
    "meters_50pct": {},
    "routers_50pct": {"observe.meter_fraction": 0.0, "observe.router_fraction": 0.5},
    "tags_50pct": {"observe.meter_fraction": 0.0, "observe.tag_fraction": 0.5},
    "meters_no_grid_faults": {"grid.grid_failure_multiplier": 0.0},
    "meters_plus_tags_10pct": {"observe.tag_fraction": 0.1},
}


def job(args):
    sweep, value, ov, fs, os_ = args
    cfg = load_config(overrides=ov)
    t0 = time.time()
    try:
        out = run_one(cfg, fs, os_)
        out["error"] = ""
    except Exception as exc:  # record failures instead of losing the sweep
        out = {"fire_seed": fs, "obs_seed": os_, "error": repr(exc)}
    out.update({"sweep": sweep, "value": "none" if value is None else value, "runtime_s": round(time.time() - t0, 1)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire-seeds", type=int, default=5)
    ap.add_argument("--obs-seeds", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default=None)
    ap.add_argument("--out", default="results/sweeps.csv")
    a = ap.parse_args()
    prov = git_info()  # recorded at the start of the run
    base = load_config()
    for fs in range(a.fire_seeds):  # build fire truth caches serially first
        get_fire(base, fs)
    jobs = []
    for name, (key, values, extra) in SWEEPS.items():
        if a.only and a.only != name:
            continue
        for v in values:
            ov = dict(extra)
            ov[key] = v
            for fs in range(a.fire_seeds):
                for os_ in range(a.obs_seeds):
                    jobs.append((name, v, ov, fs, os_))
    for name, ov in SCENARIOS.items():
        if a.only and a.only != "scenarios":
            continue
        for fs in range(a.fire_seeds):
            for os_ in range(a.obs_seeds):
                jobs.append(("scenario", name, ov, fs, os_))
    t0 = time.time()
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(job, jobs, chunksize=1)):
            rows.append(r)
            if (i + 1) % 20 == 0:
                print(f"{i + 1}/{len(jobs)} done, {time.time() - t0:.0f} s", flush=True)
    keys = sorted({k for r in rows for k in r})
    out = ROOT / a.out
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    meta = {**prov, "script": "scripts/03_sweeps.py", "config": "configs/default.json",
            "fire_seeds": a.fire_seeds, "obs_seeds": a.obs_seeds, "n_runs": len(rows),
            "n_errors": sum(1 for r in rows if r.get("error")), "wall_s": round(time.time() - t0, 1),
            "sweeps": {k: {"key": v[0], "values": v[1], "extra": v[2]} for k, v in SWEEPS.items()},
            "scenarios": SCENARIOS}
    (ROOT / a.out.replace(".csv", "_meta.json")).write_text(json.dumps(meta, indent=2))
    print(json.dumps({k: meta[k] for k in ("n_runs", "n_errors", "wall_s")}))


if __name__ == "__main__":
    main()
