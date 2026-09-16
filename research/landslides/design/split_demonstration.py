"""Demonstrate the pre-registered split call, and the trap inside it.

Owner: A4. Written for `research/landslides/PREREG_landslides_2026-09-16_v0.1.md`
section 12, item P6.

P6 asks for the exact call into `research/eval/splits.py` with its keyword
arguments and the fingerprint it returns. The real fingerprint cannot exist
yet: it is a function of the unit coordinates, and there is no DEM, so there
are no units. The roads direction hit the same wall and A6 accepted a pinned
fingerprint at a later version (`roads_v0.2.md` condition C8). This script does
the part that can be done now, which is to show that the call is executable,
that its keyword arguments are read from `PRIMARY_SPLITS` rather than retyped,
and that the fingerprint mechanism reproduces on a declared geometry.

It also demonstrates a defect in the registered keyword arguments that matters
for this direction specifically. `require_fire_disjoint=True` welds every block
that shares a fire identifier into one group. Unburned control units do not
belong to a fire. If they are all given one sentinel identifier, the weld joins
every control block in the country into a single group, the splitter cannot
fill five folds, and it raises. That is the splitter behaving correctly and it
is a design decision this pre-registration has to make in advance rather than
discover at fit time.

Run:  .auto/venv/bin/python research/landslides/design/split_demonstration.py
Writes: research/landslides/design/design_numbers.json (key path `split_demo`)
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from research.eval.splits import (  # noqa: E402
    LeakageRefusal,
    primary_split_spec,
    spatial_block_cv,
    splits_fingerprint,
)

#: The declared demonstration geometry. Projected metres, EPSG:5186-like, so
#: the splitter's degrees guard does not fire. Six fire clusters on a fixed
#: seed, so A6 reproduces the fingerprints byte for byte.
DEMO_SEED = 20260916
DEMO_CLUSTERS = 6
DEMO_UNITS_PER_CLUSTER = 200
DEMO_SPREAD_M = 12000.0
DEMO_CONTROLS = 1200
DEMO_CONTROL_SEED = 1

BLOCK_SIZE_GRID_M = (2000.0, 5000.0, 10000.0)


def build_fire_units():
    rng = random.Random(DEMO_SEED)
    xs, ys, fire_ids = [], [], []
    for c in range(DEMO_CLUSTERS):
        cx = 200000.0 + 60000.0 * c
        cy = 400000.0 + 37000.0 * ((c * 7) % 5)
        for _ in range(DEMO_UNITS_PER_CLUSTER):
            xs.append(cx + rng.uniform(-DEMO_SPREAD_M, DEMO_SPREAD_M))
            ys.append(cy + rng.uniform(-DEMO_SPREAD_M, DEMO_SPREAD_M))
            fire_ids.append("FIRE_%d" % c)
    return xs, ys, fire_ids


def build_controls():
    rng = random.Random(DEMO_CONTROL_SEED)
    xs, ys = [], []
    for _ in range(DEMO_CONTROLS):
        xs.append(rng.uniform(150000.0, 560000.0))
        ys.append(rng.uniform(300000.0, 700000.0))
    return xs, ys


def run(xs, ys, fire_ids, kwargs):
    try:
        splits = spatial_block_cv(xs, ys, fire_ids=fire_ids, **kwargs)
    except LeakageRefusal as exc:
        return {"outcome": "LeakageRefusal", "message": str(exc)}
    return {
        "outcome": "ok",
        "n_folds": len(splits),
        "fingerprint": splits_fingerprint(splits),
        "test_sizes": [len(s.test) for s in splits],
        "train_sizes": [len(s.train) for s in splits],
        "dropped_to_buffer": [s.meta["dropped_to_buffer"] for s in splits],
        "n_blocks_total": splits[0].meta["n_blocks_total"],
    }


def main() -> int:
    spec = primary_split_spec("landslides")
    kwargs = dict(spec["kwargs"])

    fx, fy, fids = build_fire_units()
    cx, cy = build_controls()

    out = {
        "generated_by": "research/landslides/design/split_demonstration.py",
        "purpose": ("demonstrates the call and the fingerprint mechanism on a "
                    "declared synthetic geometry. These fingerprints are NOT "
                    "the pre-registered split fingerprint and must never be "
                    "quoted as one."),
        "primary_split_spec": spec,
        "demo_geometry": {
            "seed": DEMO_SEED, "clusters": DEMO_CLUSTERS,
            "units_per_cluster": DEMO_UNITS_PER_CLUSTER,
            "spread_m": DEMO_SPREAD_M, "controls": DEMO_CONTROLS,
            "control_seed": DEMO_CONTROL_SEED,
            "crs_note": "projected metres, EPSG:5186-like; degrees would raise",
        },
        "A_fires_only": run(fx, fy, fids, kwargs),
        "B_controls_share_one_sentinel_id": run(
            fx + cx, fy + cy, fids + ["CONTROL"] * DEMO_CONTROLS, kwargs),
        "C_controls_carry_a_unique_id_each": run(
            fx + cx, fy + cy,
            fids + ["CONTROL_%d" % i for i in range(DEMO_CONTROLS)], kwargs),
        "D_block_size_sensitivity": {},
        "E_degrees_are_refused": None,
    }

    for block_size in BLOCK_SIZE_GRID_M:
        k = dict(kwargs)
        k["block_size_m"] = block_size
        out["D_block_size_sensitivity"]["block_size_m_%g" % block_size] = run(fx, fy, fids, k)

    try:
        spatial_block_cv([127.1, 127.2, 128.0], [36.1, 36.2, 37.0], **kwargs)
        out["E_degrees_are_refused"] = {"outcome": "ok", "message": "NOT REFUSED"}
    except LeakageRefusal as exc:
        out["E_degrees_are_refused"] = {"outcome": "LeakageRefusal", "message": str(exc)}

    dest = Path(__file__).resolve().parent / "design_numbers.json"
    existing = {}
    if dest.exists():
        existing = json.loads(dest.read_text(encoding="utf-8"))
    existing["split_demo"] = out
    dest.write_text(json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("wrote %s key path split_demo" % dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
