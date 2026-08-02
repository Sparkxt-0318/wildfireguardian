#!/usr/bin/env python
"""What does the corrected DEM do to Yeongdeok's forward-simulated hazard?

Round-3, follow-up to the 2026-08-02 DEM defect
(``docs/dem_defect_2026-08-02.md``).

Yeongdeok's own raster was **not** re-acquired — it is an input to committed
artifacts. But its hazard field is produced by a model fitted leave-Yeongdeok-
out on the other five fires, and two of those had their rasters replaced. So the
field can move without its own terrain moving at all.

DESIGN
------
Two arms, one variable:

    old   the pre-2026-08-02 rasters (reproduces the committed configuration)
    new   the corrected rasters

Everything else — seed, cell size, canvas, steps, thresholds — is identical and
comes from ``config/default.yaml``. The committed ``routing_demo.npz`` is read
only for comparison and is **never written**; outputs go to new filenames.

WHY THIS ISN'T JUST `run_routing_integration.py --out <dir>`
------------------------------------------------------------
It cannot be. On the config canvas (``bbox.fire_acquisition``) the Yeongdeok
envelope **touches the western edge in every slice at p = 1.000**, so
``assert_envelope_within_grid`` raises — correctly. That guard postdates the
committed npz, and the committed field is clipped on the west. To measure the
DEM's effect at all, the boundary contact has to be *recorded* rather than
raised on, which is what this script does. **That is a reporting choice for this
measurement only; it does not make the clipping acceptable and it is written
into the output.**

Run:  python scripts/measure_yeongdeok_dem_sensitivity.py --old-dem-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.spread_v2 import data, features, grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.extent import (  # noqa: E402
    boundary_contact, resolve_simulation_bbox,
)
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.forward_sim import forward_simulate  # noqa: E402
from wildfireguardian.spread_v2.model import IgnitionModelV2  # noqa: E402
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402

COMMITTED_NPZ = REPO / "data/processed/routing_demo.npz"


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def run_arm(name: str, data_dir: str | None, args) -> dict:
    prev = os.environ.get("WFG_FIRMS_DIR")
    if data_dir:
        os.environ["WFG_FIRMS_DIR"] = str(data_dir)
    try:
        print(f"\n=== arm: {name} ===")
        fire_ids = [m.id for m in data.list_fires()]
        ds = features.build_dataset(fire_ids, cell_size_m=args.cell_m,
                                    buffer_m=float(_cfg("grid.feature_buffer_m", 6000.0)))
        model = IgnitionModelV2(seed=args.seed).fit(ds[ds["fire_id"] != args.fire])
        ev = data.load_event(args.fire)
        ws = weather_series_from_event(ev)
        sim_bbox, prov = resolve_simulation_bbox(fallback=ev.meta.bbox_wgs84)
        hg = gridmod.build_grid(sim_bbox, cell_size_m=args.cell_m)
        snaps = gridmod.overpass_snapshots(ev, hg, gap_minutes=90.0)
        hstatic = StaticLayers.from_event(ev, hg)
        sim = forward_simulate(model, ev, hg, hstatic, snaps[0].cumulative_mask,
                               snaps[0].time, ws, n_steps=args.n_steps,
                               step_hours=args.step_hours,
                               advance_threshold=args.advance_threshold)
        hazard = HazardSequence.from_forward_sim(sim)
    finally:
        if prev is None:
            os.environ.pop("WFG_FIRMS_DIR", None)
        else:
            os.environ["WFG_FIRMS_DIR"] = prev

    stack = np.stack([np.asarray(s, float) for s in hazard.surfaces])
    ha = hg.cell_size_m * hg.cell_size_m / 10_000.0
    cells05 = [int((stack[i] >= 0.5).sum()) for i in range(stack.shape[0])]
    cells03 = [int((stack[i] >= 0.3).sum()) for i in range(stack.shape[0])]
    edge = [dict(boundary_contact(stack[i]), slice=i) for i in range(stack.shape[0])]

    print(f"  grid {hg.nrows}x{hg.ncols} @ {hg.cell_size_m:g} m   canvas {sim_bbox} [{prov}]")
    print(f"  cells >= 0.5 : {cells05}")
    print(f"  envelope ha  : {[round(c * ha) for c in cells05]}")
    print(f"  boundary contact: "
          f"{'REACHED ' + '/'.join(sorted({e for r in edge for e in r['edges_reached']})) if any(r['reached'] for r in edge) else 'clear'}")

    return {
        "arm": name,
        "firms_dir": str(data_dir) if data_dir else "repo default (data/raw/firms_data)",
        "grid": {"nrows": hg.nrows, "ncols": hg.ncols, "cell_size_m": hg.cell_size_m,
                 "extent_5179": [hg.minx, hg.miny, hg.maxx, hg.maxy]},
        "simulation_bbox_wgs84": list(sim_bbox),
        "simulation_bbox_provenance": prov,
        "fire_manifest_bbox_wgs84": list(ev.meta.bbox_wgs84),
        "times_min": [float(t) for t in hazard.times_min],
        "cells_ge_0.5": cells05,
        "cells_ge_0.3": cells03,
        "envelope_area_ha_p05": [c * ha for c in cells05],
        "core_growth_pct_first_to_last": (cells05[-1] / max(cells05[0], 1) - 1.0) * 100.0,
        "boundary_contact": {
            "per_slice": edge,
            "any_slice_reached_edge": any(r["reached"] for r in edge),
            "edges_reached": sorted({e for r in edge for e in r["edges_reached"]}),
            "max_edge_p": max(max(r["max_p_per_edge"].values()) for r in edge),
        },
    }


def committed_reference() -> dict | None:
    if not COMMITTED_NPZ.exists():
        return None
    z = np.load(COMMITTED_NPZ)
    h = z["haz_stack"].astype(np.float32)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    ha = cell * cell / 10_000.0
    cells05 = [int((h[i] >= 0.5).sum()) for i in range(h.shape[0])]
    edge = [dict(boundary_contact(h[i]), slice=i) for i in range(h.shape[0])]
    return {
        "source": "data/processed/routing_demo.npz (COMMITTED, read-only)",
        "sha256": hashlib.sha256(COMMITTED_NPZ.read_bytes()).hexdigest(),
        "grid": {"nrows": int(h.shape[1]), "ncols": int(h.shape[2]),
                 "cell_size_m": cell, "extent_5179": [xmin, ymin, xmax, ymax]},
        "times_min": [float(t) for t in z["haz_times"]],
        "cells_ge_0.5": cells05,
        "cells_ge_0.3": [int((h[i] >= 0.3).sum()) for i in range(h.shape[0])],
        "envelope_area_ha_p05": [c * ha for c in cells05],
        "core_growth_pct_first_to_last": (cells05[-1] / max(cells05[0], 1) - 1.0) * 100.0,
        "boundary_contact": {
            "per_slice": edge,
            "any_slice_reached_edge": any(r["reached"] for r in edge),
            "edges_reached": sorted({e for r in edge for e in r["edges_reached"]}),
            "max_edge_p": max(max(r["max_p_per_edge"].values()) for r in edge),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-dem-dir", required=True)
    ap.add_argument("--fire", default=_cfg("project.region_name", "yeongdeok_2025"))
    ap.add_argument("--seed", type=int, default=int(_cfg("seeds.canonical", 20250603)))
    ap.add_argument("--cell-m", type=float,
                    default=float(_cfg("grid.routing_integration_hazard_cell_m", 500.0)))
    ap.add_argument("--n-steps", type=int, default=int(_cfg("time.forward_sim_n_steps", 4)))
    ap.add_argument("--step-hours", type=float,
                    default=float(_cfg("time.forward_sim_step_hours", 3.0)))
    ap.add_argument("--advance-threshold", type=float,
                    default=float(_cfg("time.forward_sim_advance_threshold", 0.3)))
    ap.add_argument("--out",
                    default=str(REPO / "data/processed/yeongdeok_dem_sensitivity.json"))
    args = ap.parse_args()

    before = hashlib.sha256(COMMITTED_NPZ.read_bytes()).hexdigest() if COMMITTED_NPZ.exists() else None

    ref = committed_reference()
    old = run_arm("old_dem", args.old_dem_dir, args)
    new = run_arm("corrected_dem", None, args)

    def _delta(a, b, key):
        return [y - x for x, y in zip(a[key], b[key])]

    doc = {
        "schema_version": 1,
        "title": "Yeongdeok forward-sim sensitivity to the corrected DEMs",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git(),
        "config_hash": config_hash(),
        "fire": args.fire,
        "why": ("Yeongdeok's own DEM was NOT re-acquired. Its hazard field is "
                "produced by a model fitted leave-Yeongdeok-out on the other "
                "five fires, two of which had their rasters replaced, so the "
                "field can move without its terrain moving."),
        "does_not_supersede": (
            "data/processed/routing_demo.npz is UNTOUCHED and is read here only "
            "for comparison. This is additive evidence."),
        "boundary_guard_note": (
            "assert_envelope_within_grid RAISES on this configuration: the "
            "envelope touches the WESTERN edge at p = 1.000 in every slice, on "
            "both arms. This script records the contact instead of raising so "
            "the DEM contrast can be measured at all. The clipping is real, it "
            "predates the guard, and it applies to the committed field too."),
        "parameters": {"seed": args.seed, "cell_m": args.cell_m,
                       "n_steps": args.n_steps, "step_hours": args.step_hours,
                       "advance_threshold": args.advance_threshold,
                       "source": "config/default.yaml"},
        "committed_reference": ref,
        "arms": {"old_dem": old, "corrected_dem": new},
        "delta_corrected_minus_old": {
            "cells_ge_0.5": _delta(old, new, "cells_ge_0.5"),
            "envelope_area_ha_p05": _delta(old, new, "envelope_area_ha_p05"),
            "core_growth_pct": new["core_growth_pct_first_to_last"]
                               - old["core_growth_pct_first_to_last"],
        },
    }
    if ref:
        doc["delta_old_arm_minus_committed"] = {
            "cells_ge_0.5": [y - x for x, y in zip(ref["cells_ge_0.5"], old["cells_ge_0.5"])],
            "grid_identical": ref["grid"]["nrows"] == old["grid"]["nrows"]
                              and ref["grid"]["ncols"] == old["grid"]["ncols"],
            "note": ("If this is non-zero the old arm does not reproduce the "
                     "committed field, and something OTHER than the DEM has "
                     "also moved since it was written — read it before "
                     "attributing anything to the DEM."),
        }

    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False,
                                         default=str) + "\n", encoding="utf-8")
    after = hashlib.sha256(COMMITTED_NPZ.read_bytes()).hexdigest() if COMMITTED_NPZ.exists() else None
    if before != after:
        print("STOP (exit 4): routing_demo.npz changed during this run.", file=sys.stderr)
        return 4
    print(f"\nwrote {Path(args.out).relative_to(REPO)}")
    print(f"routing_demo.npz unchanged ({after[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
