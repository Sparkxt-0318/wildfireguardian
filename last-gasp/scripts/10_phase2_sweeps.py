"""Phase 2 sweeps (SYNTHETIC): receive side (item 1), utility trip logs (item 2), tag spacing (item 3).

Usage: .venv/bin/python scripts/10_phase2_sweeps.py [--fire-seeds 5] [--obs-seeds 2] [--workers 4] [--only NAME]
Writes results/phase2_sweeps.csv and results/phase2_sweeps_meta.json.
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

from lastgasp.phase2 import load_config2, run_tags  # noqa: E402
from lastgasp.pipeline import get_fire  # noqa: E402
from lastgasp.provenance import git_info  # noqa: E402
from lastgasp.trips import run_trips  # noqa: E402


RECEIVE_SPACING = {"phase2.layout.spacing_m": 200}  # item 1 uses tags every 200 m of road (about 12 per km2)


def receive_jobs():
    jobs = []
    for mode in ("star", "mesh", "mesh_sf"):
        for hardened in (False, True):
            for g in (1, 2, 3, 4, 6, 8, 12):
                jobs.append(("receive", f"{mode}|{'hardened' if hardened else 'exposed'}|{g}",
                             {**RECEIVE_SPACING, "phase2.reception.mode": mode, "phase2.gateways.hardened": hardened,
                              "phase2.gateways.count": g}))
    for radio in ("ble", "lora_sf9", "lora_pessimistic"):
        for g in (1, 2, 4, 8, 12):
            jobs.append((f"receive_{radio}", f"mesh|exposed|{g}",
                         {**RECEIVE_SPACING, "phase2.radio": radio, "phase2.reception.mode": "mesh",
                          "phase2.gateways.count": g}))
    for power in ("grid",):
        jobs.append(("receive_gridpower", f"mesh_sf|exposed|4|{power}",
                     {**RECEIVE_SPACING, "phase2.gateways.power": power, "phase2.gateways.count": 4}))
    for name, ov in {"none": {}, "fail40_restore100_buffer": {"phase2.gateways.backhaul_fail_min": 40,
                                                              "phase2.gateways.backhaul_restore_min": 100},
                     "fail40_restore100_nobuffer": {"phase2.gateways.backhaul_fail_min": 40,
                                                    "phase2.gateways.backhaul_restore_min": 100,
                                                    "phase2.gateways.buffer": False},
                     "fail40_never": {"phase2.gateways.backhaul_fail_min": 40}}.items():
        jobs.append(("backhaul", name, {**RECEIVE_SPACING, **ov, "phase2.gateways.count": 4}))
    for hb in (10, 30, 60, 120):
        jobs.append(("heartbeat", str(hb), {**RECEIVE_SPACING, "phase2.reception.heartbeat_s": hb}))
    return jobs


def spacing_jobs():
    jobs = []
    for kind in ("roads", "edge"):
        for s in (50, 100, 200, 400, 800, 1600):
            jobs.append(("spacing", f"{kind}|{s}", {"phase2.layout.kind": kind, "phase2.layout.spacing_m": s}))
    return jobs


def trips_jobs():
    jobs = []
    for kinds in (["breaker", "recloser"], ["breaker", "recloser", "fuse"]):
        for s in (200, 400, 800, 1600):
            jobs.append(("trips_spacing", f"{'+'.join(kinds)}|{s}",
                         {"phase2.trips.logged_kinds": kinds, "phase2.trips.tag_spacing_m": s}))
    scen = {
        "no_precaution": {},
        "blanket60_typed": {"phase2.trips.precaution.mode": "blanket", "phase2.trips.precaution.time_min": 60},
        "blanket60_untyped": {"phase2.trips.precaution.mode": "blanket", "phase2.trips.precaution.time_min": 60,
                              "phase2.trips.p_type_logged": 0.0},
        "proximity_typed": {"phase2.trips.precaution.mode": "proximity"},
        "proximity_untyped": {"phase2.trips.precaution.mode": "proximity", "phase2.trips.p_type_logged": 0.0},
        "untyped_no_precaution": {"phase2.trips.p_type_logged": 0.0},
        "reactive_untyped": {"phase2.trips.precaution.mode": "proximity", "phase2.trips.precaution.distance_m": 0,
                             "phase2.trips.p_type_logged": 0.0},
        "logging_stops_40": {"phase2.trips.logging_stops_min": 40},
    }
    for name, ov in scen.items():
        jobs.append(("trips_precaution", name, ov))
    return jobs


def job(args):
    sweep, value, ov, fs, os_ = args
    cfg = load_config2(ov)
    t0 = time.time()
    try:
        out = (run_trips if sweep.startswith("trips") else run_tags)(cfg, fs, os_)
        out["error"] = ""
    except Exception as exc:  # keep the sweep going and record the failure
        out = {"fire_seed": fs, "obs_seed": os_, "error": repr(exc)}
    out.update({"sweep": sweep, "value": value, "runtime_s": round(time.time() - t0, 2)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire-seeds", type=int, default=5)
    ap.add_argument("--obs-seeds", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default=None, help="receive, spacing or trips")
    ap.add_argument("--out", default="results/phase2_sweeps.csv")
    a = ap.parse_args()
    prov = git_info()  # recorded at the start of the run
    base = load_config2()
    for fs in range(a.fire_seeds):
        get_fire(base, fs)
    groups = {"receive": receive_jobs, "spacing": spacing_jobs, "trips": trips_jobs}
    jobs = []
    for name, fn in groups.items():
        if a.only and a.only != name:
            continue
        for sweep, value, ov in fn():
            for fs in range(a.fire_seeds):
                for os_ in range(a.obs_seeds):
                    jobs.append((sweep, value, ov, fs, os_))
    t0 = time.time()
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(job, jobs, chunksize=2)):
            rows.append(r)
            if (i + 1) % 50 == 0:
                print(f"{i + 1}/{len(jobs)} done, {time.time() - t0:.0f} s", flush=True)
    keys = sorted({k for r in rows for k in r})
    with open(ROOT / a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    meta = {**prov, "script": "scripts/10_phase2_sweeps.py", "config": "configs/default.json + configs/phase2.json",
            "fire_seeds": a.fire_seeds, "obs_seeds": a.obs_seeds, "n_runs": len(rows),
            "n_errors": sum(1 for r in rows if r.get("error")), "wall_s": round(time.time() - t0, 1)}
    (ROOT / a.out.replace(".csv", "_meta.json")).write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
