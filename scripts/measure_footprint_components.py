#!/usr/bin/env python
"""Measure the connected-component structure of the footprint everything is graded against (WFG-255).

WHAT THIS MEASURES AND WHY IT IS A ROW
--------------------------------------
Every IoU this project publishes scores a forward-simulated core against a slice
of ``obs_stack`` in ``data/processed/routing_demo_canonical.npz``. Two published
sentences read that slice as **one advancing fire**: ``docs/disc_null.md`` says
the model 「puts cells along the arms the fire actually ran down」, and
``docs/oracle_gap.md`` §4's centroid reading turns on how far 「the fire」 moved.

Nothing in the repository has ever said what that object's geometry is. This
script says it, from the committed array, and registers the numbers.

⚠⚠ THE HEADLINE OF THIS MEASUREMENT IS NOT A COMPONENT COUNT
------------------------------------------------------------
A count of connected pieces is **a reading of a rule**, not a property of the
fire. The same committed mask at the headline slice is:

    101 pieces under 4-connectivity
     55 pieces under 8-connectivity
      6 pieces when cells within 500 m are joined
      2 pieces when cells within 1.0 km are joined
      1 piece  when cells within 2.0 km are joined

Nobody has justified one of those rules over the others, so **the stability
profile is the result and any single number is a parameter**. This script
therefore computes the whole sweep and the registry carries it, so that a page
quoting 「55」 has to quote the rule beside it or quote nothing.

⚠ IT SAYS NOTHING ABOUT HOW MANY FIRES THERE ARE. FIRMS gaps fragment a single
perimeter and the 2025 경북 event was a multi-fire complex; this repository
cannot presently tell those apart, and the sweep above is exactly why. No output
of this script licenses 「여러 개의 산불」 or any count of fires.

BOUNDING-BOX CONVENTION, STATED BECAUSE TWO ARE DEFENSIBLE
----------------------------------------------------------
``span_km`` is the union of the cells' own footprints, ``(max - min + 1) * cell``.
``centre_span_km`` is the distance between the extreme cell CENTRES,
``(max - min) * cell``. They differ by exactly one cell (500 m) and both are
registered, because the WFG-255 row was filed quoting the second convention and
a later lap reading only the first would think the row's number was wrong.

Nothing here refits, re-acquires, re-routes or regenerates anything: it reads one
committed array and writes one new file.

    python scripts/measure_footprint_components.py
    python scripts/measure_footprint_components.py --out <path>
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
NPZ = REPO / "data" / "processed" / "routing_demo_canonical.npz"
OUT_DIR = REPO / "data" / "processed" / "footprint_components"

#: The impassability threshold the committed routing uses and every other null on
#: this fire scores at. Imported as a literal rather than re-derived so this
#: script cannot quietly score a different core than docs/disc_null.md does.
P_CUT = 0.5

#: How far apart two cells may be and still be called one piece, in cells. 0 is
#: plain connectivity; k joins anything within k cells by dilating before
#: labelling and counting the labels on the ORIGINAL mask's cells.
LINK_SWEEP = (0, 1, 2, 3, 4)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


S8 = np.ones((3, 3), dtype=bool)
S4 = ndimage.generate_binary_structure(2, 1)


def _component_sizes(mask: np.ndarray, structure: np.ndarray) -> list[int]:
    lab, n = ndimage.label(mask, structure=structure)
    if n == 0:
        return []
    sizes = np.bincount(lab.ravel())[1:]
    return sorted((int(s) for s in sizes), reverse=True)


def _link_count(mask: np.ndarray, k: int) -> int:
    """Pieces when any two cells within `k` cells of each other are one piece.

    The dilation is a JOINING RULE and not a redrawing of the fire: it is used
    only to decide which original cells share a label, and no dilated cell is
    ever counted, measured or reported as burnt area.
    """
    if not mask.any():
        return 0
    grown = mask if k == 0 else ndimage.binary_dilation(mask, structure=S8,
                                                        iterations=k)
    lab, _ = ndimage.label(grown, structure=S8)
    return int(len(set(lab[mask].tolist()) - {0}))


def _span(mask: np.ndarray, cell_m: float) -> dict:
    rows, cols = np.nonzero(mask)
    dr = int(rows.max() - rows.min())
    dc = int(cols.max() - cols.min())
    return {
        "span_km": [round((dr + 1) * cell_m / 1000.0, 3),
                    round((dc + 1) * cell_m / 1000.0, 3)],
        "centre_span_km": [round(dr * cell_m / 1000.0, 3),
                           round(dc * cell_m / 1000.0, 3)],
    }


def describe(mask: np.ndarray, cell_m: float) -> dict:
    """Everything this row asks about one binary mask."""
    n_cells = int(mask.sum())
    if n_cells == 0:
        return {"n_cells": 0}
    s8 = _component_sizes(mask, S8)
    s4 = _component_sizes(mask, S4)
    out = {
        "n_cells": n_cells,
        "n_components_8conn": len(s8),
        "n_components_4conn": len(s4),
        "largest_component_cells": s8[0],
        "second_component_cells": s8[1] if len(s8) > 1 else 0,
        "largest_component_share": round(s8[0] / n_cells, 4),
        # How much of the mask is NOT in its dominant piece. This is the number
        # that says whether 「one fire with arms」 is a reading of most of the
        # object or of a part of it.
        "cells_outside_largest": n_cells - s8[0],
        "singleton_components_8conn": int(sum(1 for s in s8 if s == 1)),
        "link_sweep": {str(k): _link_count(mask, k) for k in LINK_SWEEP},
    }
    out.update(_span(mask, cell_m))
    lab, _ = ndimage.label(mask, structure=S8)
    biggest = lab == (int(np.argmax(np.bincount(lab.ravel())[1:])) + 1)
    out["largest_component_span_km"] = _span(biggest, cell_m)["span_km"]
    return out


def measure(npz_path: Path, p_cut: float) -> dict:
    z = np.load(npz_path, allow_pickle=True)
    haz, obs = z["haz_stack"], z["obs_stack"]
    haz_times, obs_times = z["haz_times"], z["obs_times"]
    cell_m = float(z["grid_extent"][4])

    observations = []
    prev = None
    for i, t in enumerate(obs_times):
        mask = obs[i] > 0
        entry = {"obs_time_min": float(t), "is_seed_slice": i == 0}
        entry.update(describe(mask, cell_m))
        # obs_stack is CUMULATIVE. The cells this slice adds to the previous one
        # are the only thing in it that is news, and they are reported so a later
        # reader cannot mistake a stable component count for a stable fire.
        entry["cells_added_since_previous"] = (
            None if prev is None else int(mask.sum() - prev.sum()))
        observations.append(entry)
        prev = mask

    cores = []
    for i, t in enumerate(haz_times):
        mask = haz[i] >= p_cut
        entry = {"haz_time_min": float(t), "is_seed_slice": i == 0}
        entry.update(describe(mask, cell_m))
        cores.append(entry)

    # The headline slice: the same pairing docs/disc_null.md and
    # docs/oracle_gap.md §4 quote — the 360-minute core against its nearest
    # observation, which is the 333-minute one.
    hi = int(np.argmin(np.abs(haz_times - 360.0)))
    oi = int(np.argmin(np.abs(obs_times - haz_times[hi])))
    core = haz[hi] >= p_cut
    seen = obs[oi] > 0
    inter = core & seen
    lab, n_obs_comp = ndimage.label(seen, structure=S8)
    big_label = int(np.argmax(np.bincount(lab.ravel())[1:])) + 1
    touched = sorted(set(lab[inter].tolist()) - {0})
    headline = {
        "haz_time_min": float(haz_times[hi]),
        "obs_time_min": float(obs_times[oi]),
        "time_gap_min": float(abs(obs_times[oi] - haz_times[hi])),
        "intersection_cells": int(inter.sum()),
        # Does the overlap sit in the one dominant piece, or is it spread over
        # the scatter? This is the measurement that tests the 「arms」 sentence.
        "intersection_in_largest_obs_component": int((inter & (lab == big_label)).sum()),
        "intersection_share_in_largest_obs_component": round(
            float((inter & (lab == big_label)).sum()) / float(inter.sum()), 4),
        "obs_components_touched_by_core": len(touched),
        "obs_components_total": int(n_obs_comp),
    }

    return {
        "schema": "footprint_components/1",
        "written_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ"),
        "git_commit": _head(),
        "row": "WFG-255",
        "source": {
            "npz": npz_path.relative_to(REPO).as_posix(),
            "sha256": _sha256(npz_path),
            "cell_m": cell_m,
            "grid_shape": [int(haz.shape[1]), int(haz.shape[2])],
        },
        "rule": {
            "p_cut": p_cut,
            "connectivity": "component counts are reported under BOTH 4- and "
                            "8-connectivity; every other field labelled with no "
                            "connectivity uses 8",
            "link_sweep_cells": list(LINK_SWEEP),
            "link_sweep_meaning": "cells within k cells of one another are "
                                  "counted as one piece; the dilation decides "
                                  "labels only and no dilated cell is counted "
                                  "as burnt",
            "span_convention": "span_km is the union of cell footprints "
                               "((max-min+1)*cell); centre_span_km is between "
                               "extreme cell centres ((max-min)*cell); they "
                               "differ by exactly one cell",
        },
        "observations": observations,
        "forecast_cores": cores,
        "headline": headline,
        # obs_stack is cumulative, so the component count standing still across
        # four consecutive slices is the RECORD standing still and not the fire.
        # This is the arithmetic that says so, computed here rather than left for
        # a prose sentence to do.
        "cumulative": {
            "graded_slice_cells": int((obs[oi] > 0).sum()),
            "last_slice_min": float(obs_times[-1]),
            "last_slice_cells": int((obs[-1] > 0).sum()),
            "cells_added_graded_to_last": int((obs[-1] > 0).sum()
                                              - (obs[oi] > 0).sum()),
        },
        "what_this_does_not_show": [
            "It does not say how many fires are in the mask. A component count "
            "is a reading of the connectivity rule and the 500 m grid, and the "
            "same mask is 101, 55, 6, 2 or 1 pieces as that rule loosens. FIRMS "
            "gaps fragment a single perimeter and the 2025 Gyeongbuk event was a "
            "multi-fire complex; this repository cannot tell those apart.",
            "It moves no IoU and produces no margin. Nothing was refit, "
            "re-acquired, re-routed or regenerated; one committed array was read.",
            "obs_stack is a FIRMS-derived observation with its own detection "
            "floor (docs/detection_floor.md) and 500 m resampling, so the "
            "geometry measured here is the geometry of a DETECTION FIELD and not "
            "of a fire perimeter.",
            "It is one fire at one set of slices. Nothing here generalises to "
            "another event, and no rate, frequency or typical value is implied.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p-cut", type=float, default=P_CUT,
                    help="the committed routing impassability threshold")
    ap.add_argument("--out", type=Path, default=None,
                    help="output path; defaults to a new stamped file")
    args = ap.parse_args()

    doc = measure(NPZ, args.p_cut)
    out = args.out
    if out is None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"footprint_components_{doc['stamp']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    h = doc["headline"]
    print(f"wrote {out.relative_to(REPO).as_posix()}")
    for e in doc["observations"]:
        print(f"  obs t={e['obs_time_min']:7.0f}  {e['n_cells']:5d} cells  "
              f"8conn {e['n_components_8conn']:4d}  4conn {e['n_components_4conn']:4d}  "
              f"largest {e['largest_component_cells']:4d} "
              f"({e['largest_component_share']:.1%})  "
              f"link {e['link_sweep']}")
    for e in doc["forecast_cores"]:
        print(f"  core t={e['haz_time_min']:7.0f}  {e['n_cells']:5d} cells  "
              f"8conn {e['n_components_8conn']:4d}  4conn {e['n_components_4conn']:4d}  "
              f"largest {e['largest_component_cells']:4d} "
              f"({e['largest_component_share']:.1%})")
    print(f"  headline: core touches {h['obs_components_touched_by_core']} of "
          f"{h['obs_components_total']} observed pieces; "
          f"{h['intersection_share_in_largest_obs_component']:.1%} of the "
          f"{h['intersection_cells']}-cell overlap is in the dominant piece")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
