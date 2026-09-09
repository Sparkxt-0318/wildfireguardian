#!/usr/bin/env python
"""How far is the field the router PLANS on from the field that actually burned?

WFG-125. Reads ONE committed artifact — ``data/processed/routing_demo_canonical.npz``
— and touches nothing.

WHY THIS SCRIPT EXISTS
----------------------
`docs/present_perimeter_arm.md` §5, the README TL;DR and the WFG-125 backlog row
all say the same thing: the forecast-aware arm plans on the same hazard field it
is scored against, so the margins it wins (42 of 458 on 영덕, 9 of 368 on
의성·안동) are what a **perfect** forecast buys, and what this project's own model
buys is smaller "by an amount no run here measures".

The row asked, as its first question, which of the committed fields is a
prediction and which is the graded truth. The answer is in the canonical npz and
it is not the one the row assumed:

* ``haz_stack`` — float32, the leave-one-fire-out forward simulation. This is
  **already a model output**: `scripts/run_forward_sim_region.py` fits on every
  fire EXCEPT the target. The router plans on it.
* ``obs_stack`` — uint8, the cumulative FIRMS-observed footprint on the SAME
  grid, in the SAME file, at its own observation times.

So the arm does **not** plan on truth. What makes it an oracle is that the
*grader* uses ``haz_stack`` as if it were truth. Removing the oracle therefore
does not need a new planning field (and so needs no fill rule over the cells the
out-of-fold sample never scores): it needs a different **grading** field, and
that field is committed, complete over the grid, and sitting beside the one in
use.

WHAT IT MEASURES
----------------
For each hazard slice, the predicted core (``p >= p_cut``) against the observed
cumulative footprint at the NEAREST observation time, reporting the time gap
rather than hiding it, and decomposing the disagreement into intersection,
false alarm (predicted, did not burn) and miss (burned, not predicted).

⚠ It does NOT re-route and does NOT produce a margin. It measures the gap
between the two fields; converting that into origins saved is the re-grading
run, which is a separate row.

Run:  python scripts/measure_oracle_gap.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / "data/processed/routing_demo_canonical.npz"
OUT = REPO / "data/processed/oracle_gap_yeongdeok.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def measure(npz_path: Path, p_cut: float) -> dict:
    z = np.load(npz_path, allow_pickle=True)
    haz, obs = z["haz_stack"], z["obs_stack"]
    haz_times, obs_times = z["haz_times"], z["obs_times"]

    # Both stacks are cumulative in the committed artifact; assert rather than
    # assume, because the decomposition below reads them as footprints-to-date.
    monotone_haz = all(int((((haz[i] >= p_cut) & ~(haz[i + 1] >= p_cut)).sum())) == 0
                       for i in range(haz.shape[0] - 1))
    monotone_obs = all(int((((obs[i] > 0) & ~(obs[i + 1] > 0)).sum())) == 0
                       for i in range(obs.shape[0] - 1))

    slices = []
    for i, t in enumerate(haz_times):
        j = int(np.argmin(np.abs(obs_times - t)))
        pred = haz[i] >= p_cut
        seen = obs[j] > 0
        inter = int((pred & seen).sum())
        union = int((pred | seen).sum())
        n_pred, n_obs = int(pred.sum()), int(seen.sum())
        slices.append({
            "haz_time_min": float(t),
            "obs_time_min": float(obs_times[j]),
            "time_gap_min": float(abs(obs_times[j] - t)),
            "predicted_cells": n_pred,
            "observed_cells": n_obs,
            "intersection_cells": inter,
            "union_cells": union,
            "false_alarm_cells": n_pred - inter,
            "missed_cells": n_obs - inter,
            "iou": round(inter / union, 4) if union else None,
            "size_ratio": round(n_pred / n_obs, 4) if n_obs else None,
        })

    last = slices[-1]
    # The slice to quote. t=0 is excluded because both stacks are seeded from the
    # same detection there (IoU 1.0 by construction, not by skill); of the rest,
    # the one whose observation is closest in time is the only fair comparison,
    # and the others are kept beside it so the choice is visible.
    best = min(slices[1:], key=lambda s: s["time_gap_min"])
    return {
        "schema_version": 1,
        "title": "The planning field vs the observed footprint — 영덕 2025, canonical",
        "row": "WFG-125",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _head(),
        "source_artifact": str(npz_path.relative_to(REPO)),
        "source_sha256": _sha256(npz_path),
        "p_cut": p_cut,
        "grid_shape": [int(x) for x in haz.shape[1:]],
        "grid_cells_per_slice": int(haz.shape[1] * haz.shape[2]),
        "cell_size_m": float(z["grid_extent"][4]),
        "stacks_are_cumulative": {"haz": monotone_haz, "obs": monotone_obs},
        "slices": slices,
        "headline": dict(best, note=(
            "the best time-matched slice: t=0 is excluded because both stacks "
            "are seeded from the same detection there, and of the rest this is "
            "the one whose observation is nearest in time")),
        "last_slice": last,
        "what_this_is_not": (
            "This is a field-to-field comparison, not a routing result. It "
            "produces no margin and moves no committed number. obs_stack is a "
            "FIRMS-derived observation with its own detection floor "
            "(docs/detection_floor.md), not ground truth."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--p-cut", type=float, default=0.5,
                    help="the committed routing impassability threshold")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    if not NPZ.exists():
        print(f"missing committed artifact: {NPZ}", file=sys.stderr)
        return 2

    doc = measure(NPZ, args.p_cut)
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    h = doc["headline"]
    print(f"wrote {args.out.relative_to(REPO)}")
    print(f"  haz {h['haz_time_min']:.0f} min vs obs {h['obs_time_min']:.0f} min "
          f"(gap {h['time_gap_min']:.0f} min): predicted {h['predicted_cells']} cells, "
          f"observed {h['observed_cells']}, agreeing on {h['intersection_cells']}")
    print(f"  IoU {h['iou']}  size ratio {h['size_ratio']}  "
          f"(false alarm {h['false_alarm_cells']}, missed {h['missed_cells']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
