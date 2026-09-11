#!/usr/bin/env python
"""Is slice 0 of the canonical hazard field an observation or a model output? (WFG-260)

The paper's Abstract and §4.5 say the present-perimeter opponent 「needs no model at
all」. That sentence is only true if the thing the opponent plans on — slice 0 of
``data/processed/routing_demo_canonical.npz`` — is the observed FIRMS footprint and
not a simulated slice. Nothing in this repository said so, and
``docs/present_perimeter_yeongdeok.md`` §5 item 6 worded its own input so a reader
would conclude the opposite. This script measures it, so the sentence stops resting
on a reading of the build script and starts resting on a committed artifact.

What it measures, all four from the committed array and nothing else:

1. ``haz_times[0]`` is 0.0 — slice 0 is the field at the departure time the arms use.
2. ``haz_stack[0]`` is strictly binary. A forward-simulated slice is a probability
   field; slice 1 is, with thousands of distinct values. A mask is not.
3. ``haz_stack[0] >= p_cut`` and ``obs_stack[0] > 0`` are the SAME SET OF CELLS,
   compared cell for cell rather than by count. This is the load-bearing one: equal
   counts over different cells would not support the claim.
4. How many 8-connected components that set falls into, and the largest. This one
   does NOT support the claim — it qualifies it, and it is measured here because the
   qualification belongs beside the claim (see ``BAND`` in the registrar).

⚠ **What this does NOT show.** It says nothing about whether the OBSERVATION is
right — the canonical field's envelope-coverage caveat is untouched — and nothing
about the 의성·안동 arm, whose own input is not measured here. It does not re-run
any route, move any committed number, or regenerate any artifact.

    python scripts/measure_slice0_is_observation.py
    python scripts/measure_slice0_is_observation.py --check   # exit 1 if stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import ndimage

REPO = Path(__file__).resolve().parents[1]
CANON_NPZ = REPO / "data/processed/routing_demo_canonical.npz"
OUT = REPO / "data/processed/present_perimeter_yeongdeok_slice0_2025.json"

#: The same threshold the present-perimeter arm filters nodes with
#: (``scripts/measure_present_perimeter_yeongdeok.py``, ``hazard.prob_at(x, y, 0.0)
#: >= p_cut``). Not a free parameter here: it is read off the arm it explains.
P_CUT = 0.5

#: 8-connectivity. Stated rather than defaulted, because the component count is
#: convention-dependent and the artifact records which convention produced it:
#: the same set falls into 236 components at 4-connectivity.
STRUCT_8 = np.ones((3, 3), dtype=int)


def measure() -> dict:
    z = np.load(CANON_NPZ)
    haz, obs, times = z["haz_stack"], z["obs_stack"], z["haz_times"]
    burning = haz[0] >= P_CUT
    observed = obs[0] > 0
    labels_8, n_8 = ndimage.label(burning, structure=STRUCT_8)
    sizes_8 = np.bincount(labels_8.ravel())[1:]
    _, n_4 = ndimage.label(burning)
    return {
        "slice0_time_min": float(times[0]),
        "slice0_distinct_values": sorted(float(v) for v in np.unique(haz[0])),
        "slice1_distinct_values_n": int(np.unique(haz[1]).size),
        "p_cut": P_CUT,
        "slice0_burning_cells": int(burning.sum()),
        "obs0_observed_cells": int(observed.sum()),
        "slice0_equals_obs0_cell_for_cell": bool((burning == observed).all()),
        "slice0_components_8conn": int(n_8),
        "slice0_largest_component_cells": int(sizes_8.max()),
        "slice0_components_4conn": int(n_4),
        "grid_shape": [int(haz.shape[1]), int(haz.shape[2])],
    }


def build() -> dict:
    m = measure()
    # The claim is only made when every leg of it holds in THIS process.
    assert m["slice0_time_min"] == 0.0, m["slice0_time_min"]
    assert m["slice0_distinct_values"] == [0.0, 1.0], m["slice0_distinct_values"]
    assert m["slice0_equals_obs0_cell_for_cell"], "slice 0 is not the observed mask"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    return {
        "_readme": (
            "WFG-260. Evidence that the present-perimeter opponent's PLANNING side "
            "uses no model output. Slice 0 of the canonical hazard field is the "
            "seeded FIRMS observation, not a simulated slice: "
            "scripts/build_canonical_hazard.py:88 seeds forward_simulate from "
            "snaps[0].cumulative_mask, and src/wildfireguardian/routing/hazard.py:"
            "97-100 collapses the time bracket to i0 == i1 == 0 at t_min = 0.0, so "
            "prob_at(x, y, 0.0) samples that observed mask alone and mixes in no "
            "later slice. The model's first output is slice 1, at 180 min. ⚠ This "
            "measures the INPUT to the planning side only. The arm is still SCORED "
            "against the full forecast, which is the oracle "
            "docs/present_perimeter_yeongdeok.md §5 item 6 names, and that "
            "conclusion is unchanged and correct."),
        "written_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "region": "영덕 2025",
        "git_commit": head,
        "inputs": {
            "canonical_npz": str(CANON_NPZ.relative_to(REPO)),
            "sha256": hashlib.sha256(CANON_NPZ.read_bytes()).hexdigest(),
        },
        "connectivity": "8 (3x3 ones); the 4-connected count is recorded beside it",
        "measurements": m,
        "what_this_is_not": (
            "NOT a statement that the observation is CORRECT. The canonical field's "
            "envelope-coverage caveat applies unchanged, and a FIRMS cumulative mask "
            "at 375 m is a detection scatter rather than a mapped perimeter — 249 "
            "cells in 226 8-connected components, the largest 3 cells. So 「present "
            "perimeter」 is a generous word for the object, and the object is the "
            "more honest of the two. NOT a statement about 의성·안동, whose arm "
            "(docs/present_perimeter_arm.md) has a different input this script does "
            "not read. NOT a re-grading of any committed number: nothing here "
            "re-runs a route and the canonical 414 / 42 / 2 partition is untouched."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed artifact disagrees with the array")
    args = ap.parse_args()
    fresh = build()
    if args.check:
        if not OUT.exists():
            print(f"MISSING {OUT.relative_to(REPO)}")
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8"))["measurements"]
        diff = {k: (old.get(k), v) for k, v in fresh["measurements"].items()
                if old.get(k) != v}
        if diff:
            print("STALE slice-0 measurements: " + json.dumps(diff, ensure_ascii=False))
            return 1
        print("OK — the committed slice-0 artifact matches the canonical array")
        return 0
    OUT.write_text(json.dumps(fresh, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    m = fresh["measurements"]
    print(f"wrote {OUT.relative_to(REPO)} — slice 0 at t={m['slice0_time_min']} min, "
          f"{m['slice0_burning_cells']} cells, identical to obs slice 0: "
          f"{m['slice0_equals_obs0_cell_for_cell']}, "
          f"{m['slice0_components_8conn']} components (8-conn)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
