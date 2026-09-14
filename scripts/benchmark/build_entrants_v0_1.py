#!/usr/bin/env python
"""Write the K-SPREAD-2025 v0.1 entrant bundles E0 and E3 from COMMITTED data alone.

An entrant bundle is what ``score_kspread.py`` reads (build brief, Stage 1):
``entrant.json`` plus one ``<event>.npz`` per event carrying ``grid_extent``,
``times_min`` and ``stack``. Nothing here fits a model; both v0.1 entrants already
exist as committed artifacts and this script only republishes them in the
benchmark's own shape, with the source path and sha256 recorded so a stranger can
check that the republished field is the committed one.

E0 persistence — 「fire-affected at T0 stays; nothing spreads」 (protocol §6).
    The T0 fire-affected set is ``obs_stack[0]`` of ``routing_demo_canonical.npz``:
    the cumulative FIRMS detections at the first overpass, which is the same slice
    the canonical model is initialised from (``haz_stack[0] >= 0.5`` is the same 249
    cells, asserted below). p = 1 there and 0 elsewhere, constant over the horizon.
    Inputs: FIRMS to T0 only. Track: FORECAST.

E3 WFG canonical — the committed spread_v2 GBM at 500 m, leave-one-complex-out.
    ``routing_demo_leakfree.npz``'s ``haz_stack``: the field
    ``scripts/run_leakfree_yeongdeok_fold.py`` simulated from a model fitted with BOTH
    영덕 and 의성·안동 held out, which is the protocol §2 complex rule. The canonical
    ``routing_demo_canonical.npz`` field is NOT the entrant: it was fitted with
    의성·안동 in the training set and violates that rule.
    Track: HINDCAST, and this is not a detail. ``forward_simulate`` advances each step
    「with the next step's real weather」 — ERA5 reanalysis at times AFTER T0. Protocol §3
    says an entrant using any observation after T0 is hindcast-track and is never
    reported beside a forecast-track score. The model architecture could be run
    forecast-track by substituting a KMA 초단기예보 issued before T0 for those steps;
    the committed field was not, so it is scored where it belongs.

Only 영덕 2025 is written. Truth needs a committed per-cell observed detection stack and
영덕 is the only event that has one (``routing_demo_canonical.npz``); the other five
events of protocol §2 have no committed ``obs_stack``, and refitting them needs the
git-ignored raw FIRMS/ERA5/DEM bundle.

    python scripts/benchmark/build_entrants_v0_1.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data/processed/benchmark/entrants"
CANON_NPZ = REPO / "data/processed/routing_demo_canonical.npz"
LEAKFREE_NPZ = REPO / "data/processed/routing_demo_leakfree.npz"
EVENT = "yeongdeok_2025"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def write_entrant(entrant: dict, stacks: dict[str, tuple]) -> Path:
    d = OUT / entrant["id"]
    d.mkdir(parents=True, exist_ok=True)
    files = {}
    for event, (extent, times, stack) in stacks.items():
        p = d / f"{event}.npz"
        np.savez_compressed(p, grid_extent=np.asarray(extent, float),
                            times_min=np.asarray(times, float),
                            stack=np.asarray(stack, np.float32))
        files[event] = {"npz": str(p.relative_to(REPO)), "sha256": sha256(p)}
    entrant = dict(entrant, events=files, generated_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   git_commit=_commit())
    (d / "entrant.json").write_text(json.dumps(entrant, indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    return d


def main() -> int:
    zc, zf = np.load(CANON_NPZ), np.load(LEAKFREE_NPZ)
    extent = [float(v) for v in zc["grid_extent"]]
    times = [float(v) for v in zc["haz_times"]]
    if not np.array_equal(zf["grid_extent"], zc["grid_extent"]):
        print("STOP: leak-free field is on a different canvas", file=sys.stderr)
        return 2
    t0_mask = zc["obs_stack"][0].astype(bool)
    if int(t0_mask.sum()) != int((zc["haz_stack"][0] >= 0.5).sum()) or \
            not bool((t0_mask == (zc["haz_stack"][0] >= 0.5)).all()):
        print("STOP: the T0 observed mask is not the canonical field's initial state",
              file=sys.stderr)
        return 3

    e0_stack = np.repeat(t0_mask.astype(np.float32)[None, :, :], len(times), axis=0)
    d0 = write_entrant({
        "id": "e0_persistence", "protocol_entrant": "E0", "name": "E0 persistence",
        "protocol_version": "v0.1", "track": "forecast", "resolution_m": 500.0,
        "inputs_used": ["FIRMS cumulative detections at T0"],
        "what_it_is": "fire-affected at T0 stays; nothing spreads",
        "provenance": {"source": str(CANON_NPZ.relative_to(REPO)), "array": "obs_stack[0]",
                       "source_sha256": sha256(CANON_NPZ),
                       "t0_cells": int(t0_mask.sum())},
    }, {EVENT: (extent, times, e0_stack)})

    d3 = write_entrant({
        "id": "e3_wfg_canonical", "protocol_entrant": "E3", "name": "E3 WFG canonical (leave-one-complex-out)",
        "protocol_version": "v0.1", "track": "hindcast", "resolution_m": 500.0,
        "inputs_used": ["FIRMS cumulative detections at T0", "SRTM/5 m DEM", "land cover",
                        "ERA5 reanalysis at each forward step (AFTER T0)"],
        "track_reason": ("forward_simulate advances each step with ERA5 weather at that step, "
                         "which is an observation after T0; protocol §3 puts that in the "
                         "hindcast track. The same model run on a KMA forecast issued before "
                         "T0 would be forecast-track and is not committed."),
        "what_it_is": "the committed spread_v2 GBM at 500 m, fitted with 영덕 and 의성·안동 both held out",
        "provenance": {"source": str(LEAKFREE_NPZ.relative_to(REPO)), "array": "haz_stack",
                       "source_sha256": sha256(LEAKFREE_NPZ),
                       "fold_artifact": "data/processed/leakfree_yeongdeok_fold.json",
                       "fitted_by": "scripts/run_leakfree_yeongdeok_fold.py"},
    }, {EVENT: (extent, times, zf["haz_stack"])})

    print(f"wrote {d0.relative_to(REPO)} and {d3.relative_to(REPO)}")
    print(f"  E0 cells at p>=0.5 per slice: {[int((e0_stack[i] >= 0.5).sum()) for i in range(len(times))]}")
    print(f"  E3 cells at p>=0.5 per slice: {[int((zf['haz_stack'][i] >= 0.5).sum()) for i in range(len(times))]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
