#!/usr/bin/env python
"""How far is the disc null's centre from the ignition point the array records?

WFG-254. Reads TWO committed artifacts and writes one:

  * ``data/processed/routing_demo_canonical.npz`` — for ``ign_xy``, ``grid_extent``
    and ``obs_stack``;
  * ``data/processed/disc_null_yeongdeok.json`` — for the centre the null actually
    used and for every slice's disc radius;
  * out: ``data/processed/disc_null_centre_vs_ignition.json``.

It refits nothing, re-runs nothing and changes no committed value.

WHY THIS SCRIPT EXISTS
----------------------
Seven surfaces said the area-matched disc is placed **at the ignition point**:
``docs/auto/JUDGE_QA.md`` Q36 (tier T0, said from memory to all five judges and
printed in the booth kit), ``docs/disc_null.md`` §6's spoken draft,
``docs/oracle_gap.md`` §4c, ``paper/manuscript.md`` §6, ``paper/README.md`` and the
bar-group heading ``paper/make_figures.py`` renders into ``F10_disc_null.png``.

It is not. ``scripts/measure_disc_null.py`` never reads ``ign_xy``, and it is right
not to: the null's own rule, stated in its artifact as ``null_rule.centre_from``, is
「centroid of the t=0 seed」. Critic #65 measured the gap in its own process on
2026-09-11 and no file held the measurement afterwards, which is the shape of defect
this project keeps paying for — **the repository reasons about a measurement faster
than it commits one.** So the number gets an artifact, a registry key and a gate.

WHAT IT MEASURES, AND THE ONE AMBIGUITY IT RESOLVES FROM THE DATA
------------------------------------------------------------------
``grid_extent`` is ``(xmin, ymin, xmax, ymax, cell_size)`` and ``obs_stack`` is
``(T, nrow, ncol)``. The column of ``ign_xy`` is unambiguous. The ROW is not: row 0
may sit at ``ymin`` or at ``ymax``, and the two conventions put the ignition at two
different cells. **This script does not assume one.** It computes both, then asks
the observation which is right: the recorded ignition must be burning in the
``t = 0`` frame, and exactly one of the two candidates is. The other is not observed
at ANY slice. The answer is reported with both candidates beside it so a reader can
see that the finding does not rest on the convention — under the losing convention
the gap is smaller but still larger than every disc radius in the artifact.

WHAT IT DOES NOT SHOW
---------------------
Nothing here says the null is sited wrongly. The centroid rule is the honest one:
it uses only information the two stacks already share, and a centre taken from the
recorded ignition point would be a **different and worse** null, because the seed is
not a point — it is a scatter of components across the grid — and one cell of it is
not a summary of it. What the measurement shows is only that 「발화점」 and 「the
ignition」 are the wrong WORDS for the centre this null used. No measured value in
``disc_null_yeongdeok.json`` is wrong and none is touched.

It also says nothing about how many fires the footprint holds, or how many pieces it
is in. That is row WFG-255 and this artifact deliberately does not answer it.

    python scripts/measure_disc_centre_vs_ignition.py          # write the artifact
    python scripts/measure_disc_centre_vs_ignition.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
CANON = REPO / "data" / "processed" / "routing_demo_canonical.npz"
DISC = REPO / "data" / "processed" / "disc_null_yeongdeok.json"
OUT = REPO / "data" / "processed" / "disc_null_centre_vs_ignition.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure() -> dict:
    d = np.load(CANON, allow_pickle=True)
    disc = json.loads(DISC.read_text(encoding="utf-8"))

    ign_x, ign_y = (float(v) for v in d["ign_xy"])
    xmin, ymin, xmax, ymax, res = (float(v) for v in d["grid_extent"])
    obs = np.asarray(d["obs_stack"])
    nrow, ncol = int(obs.shape[1]), int(obs.shape[2])

    col = (ign_x - xmin) / res
    candidates = {
        "row0_at_ymin": (ign_y - ymin) / res,
        "row0_at_ymax": (ymax - ign_y) / res,
    }

    t0 = obs[0] > 0
    ever = (obs > 0).any(axis=0)
    resolved = None
    rows = {}
    ci = int(round(col))
    for name, row in candidates.items():
        ri = int(round(row))
        inside = 0 <= ri < nrow and 0 <= ci < ncol
        rows[name] = {
            "row_float": round(row, 4),
            "cell": [ri, ci],
            "in_grid": inside,
            "burning_at_t0": bool(t0[ri, ci]) if inside else False,
            "burning_at_any_slice": bool(ever[ri, ci]) if inside else False,
        }
        if rows[name]["burning_at_t0"]:
            resolved = name

    centre_row, centre_col = (float(v) for v in disc["null_rule"]["centre_row_col"])
    for name, row in candidates.items():
        gap = math.hypot(centre_row - row, centre_col - col)
        rows[name]["gap_from_disc_centre_cells"] = round(gap, 4)
        rows[name]["gap_from_disc_centre_m"] = round(gap * res, 1)

    radii = {f"{int(s['haz_time_min'])}min": float(s["disc_radius_cells"])
             for s in disc["slices"]}
    largest = max(radii.values())
    resolved_gap = rows[resolved]["gap_from_disc_centre_cells"] if resolved else None

    return {
        "schema_version": 1,
        "title": "The disc null's centre against the ignition point the canonical array records — 영덕 2025",
        "row": "WFG-254",
        "sources": {
            "canonical": {"path": str(CANON.relative_to(REPO)), "sha256": _sha256(CANON)},
            "disc_null": {"path": str(DISC.relative_to(REPO)), "sha256": _sha256(DISC)},
        },
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "grid": {"shape": [nrow, ncol], "cell_size_m": res,
                 "extent": [xmin, ymin, xmax, ymax]},
        "ignition_xy": [ign_x, ign_y],
        "ignition_col_float": round(col, 4),
        "disc_centre_row_col": [centre_row, centre_col],
        "disc_centre_from": disc["null_rule"]["centre_from"],
        "row_conventions": rows,
        "resolved_by": "the recorded ignition must be burning in the t=0 frame; exactly "
                       "one candidate cell is, and the other is not observed at any slice",
        "resolved_convention": resolved,
        "gap_cells": resolved_gap,
        "gap_m": rows[resolved]["gap_from_disc_centre_m"] if resolved else None,
        "disc_radius_cells_by_slice": radii,
        "largest_disc_radius_cells": largest,
        "ignition_inside_any_disc": bool(resolved_gap is not None and resolved_gap <= largest),
        "holds_under_both_conventions": bool(
            all(r["gap_from_disc_centre_cells"] > largest for r in rows.values())),
        "seed_cells": int(t0.sum()),
        "note": "The centroid rule is NOT withdrawn by this measurement and no value in "
                "disc_null_yeongdeok.json changes. Only the WORDS 「발화점」 / 「the "
                "ignition」 for this centre are withdrawn (WC-017).",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fresh = measure()
    if args.check:
        if not OUT.exists():
            print(f"MISSING {OUT.relative_to(REPO)}")
            return 1
        have = json.loads(OUT.read_text(encoding="utf-8"))
        drift = [k for k in ("gap_cells", "gap_m", "resolved_convention",
                             "largest_disc_radius_cells", "ignition_inside_any_disc",
                             "holds_under_both_conventions")
                 if have.get(k) != fresh.get(k)]
        if drift:
            print("STALE disc-centre measurement: " + ", ".join(drift))
            return 1
        print(f"OK — gap {have['gap_cells']} cells ({have['gap_m']} m), "
              f"largest disc radius {have['largest_disc_radius_cells']} cells")
        return 0
    OUT.write_text(json.dumps(fresh, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: gap {fresh['gap_cells']} cells "
          f"({fresh['gap_m']} m) under {fresh['resolved_convention']}; "
          f"inside any disc: {fresh['ignition_inside_any_disc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
