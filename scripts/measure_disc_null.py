#!/usr/bin/env python
"""What should IoU 0.394 be compared with? An area-matched disc that knows nothing.

WFG-228. Reads ONE committed artifact — ``data/processed/routing_demo_canonical.npz``
— and touches nothing. It writes ``data/processed/disc_null_yeongdeok.json``.

WHY THIS SCRIPT EXISTS
----------------------
``docs/oracle_gap.md`` §4 concludes that the forward simulation "gets the size
nearly exactly right and the place substantially wrong" from **IoU 0.394**, and
that reading now stands on the README TL;DR, the finals screen's first 알려진 한계
card, ``docs/auto/JUDGE_QA.md`` Q36 at tier T0 and ``paper/manuscript.md``.
Nothing in the repository says what 0.394 should be compared with, so
「0.394는 무엇에 견준 값입니까?」 has no answer, and a judge cannot tell whether the
number is a criticism of the model or a compliment to it.

THE NULL, AND WHY IT HAS NO FREE PARAMETERS
-------------------------------------------
For each forward-simulation slice, the disc

  * is centred on the **centroid of the t = 0 seed** — the 249 cells that
    ``obs_stack[0] > 0`` and ``haz_stack[0] >= p_cut`` agree on exactly, so the
    centre uses only information the two stacks already SHARE, and nothing from
    the observation being scored **beyond that shared seed**. ⚠ That last clause
    is not a formality: ``obs_stack`` is cumulative, so the seed is a SUBSET of
    the later footprint being scored, and the model contains all of it by
    construction while the disc does not. See ``seed_removed`` below.
  * holds exactly as many cells as **that slice's own predicted core**, so the
    area the model got right is handed to the null for free;
  * is built by taking the N cells of smallest Euclidean distance from that
    centre in grid-index space, ties broken by ``(row, col)`` ascending so the
    mask is deterministic;
  * is scored against the **same** observed footprint under the **same**
    nearest-observation time-matching rule, the same ``p_cut`` and the same
    cumulative masks that ``scripts/measure_oracle_gap.py`` already applies.

No refit, no re-acquisition, no fill rule, no threshold sweep, no new free
parameter. The rule was written into the claim commit before the run.

⚠ WHAT THE DIFFERENCE IS, AND WHAT IT IS NOT
--------------------------------------------
The backlog row says the disc "destroys the one thing routing depends on
(direction), so the difference between the two IoUs is the model's directional
skill and nothing else". **That is not accepted here, and the artifact carries
the evidence for why.** A disc differs from the model's core in TWO ways at
once: where its mass sits (direction) AND that it is a circle rather than an
irregular, terrain- and wind-shaped blob (shape). A gap between the two IoUs is
therefore joint **placement-and-shape** skill, and this comparison alone cannot
split it. So the ``direction`` block computes the centroid displacements —
seed → observed, seed → model core, seed → disc — which ARE a direction-only
reading, and the document states which number answers which question.

⚠ It re-routes nothing and produces no margin. 42, 91, 9 and 27 are untouched.

Run:  python scripts/measure_disc_null.py
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
OUT = REPO / "data/processed/disc_null_yeongdeok.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _centroid(mask: np.ndarray) -> tuple[float, float]:
    """Mean (row, col) of the True cells. Unrounded, so no tie-break is needed."""
    rr, cc = np.nonzero(mask)
    return float(rr.mean()), float(cc.mean())


def disc_mask(shape: tuple[int, int], centre: tuple[float, float], n: int) -> np.ndarray:
    """The ``n`` cells nearest ``centre``, ties broken by (row, col) ascending.

    Deterministic by construction: ``np.lexsort`` is stable and the last key is
    the primary one, so equal distances fall back to row then column.
    """
    rows, cols = np.indices(shape)
    d2 = (rows - centre[0]) ** 2 + (cols - centre[1]) ** 2
    order = np.lexsort((cols.ravel(), rows.ravel(), d2.ravel()))
    mask = np.zeros(shape[0] * shape[1], dtype=bool)
    mask[order[:n]] = True
    return mask.reshape(shape)


def _score(pred: np.ndarray, seen: np.ndarray) -> dict:
    inter = int((pred & seen).sum())
    union = int((pred | seen).sum())
    n_pred, n_obs = int(pred.sum()), int(seen.sum())
    return {
        "predicted_cells": n_pred,
        "observed_cells": n_obs,
        "intersection_cells": inter,
        "union_cells": union,
        "false_alarm_cells": n_pred - inter,
        "missed_cells": n_obs - inter,
        "iou": round(inter / union, 4) if union else None,
        "size_ratio": round(n_pred / n_obs, 4) if n_obs else None,
    }


def _displacements(pairs: dict[str, tuple], cell_m: float) -> dict:
    """Centre-of-mass distances, in cells and in metres, for each named pair."""
    out = {}
    for name, (a, b) in pairs.items():
        cells = float(np.hypot(b[0] - a[0], b[1] - a[1]))
        out[f"{name}_cells"] = round(cells, 3)
        out[f"{name}_m"] = round(cells * cell_m, 1)
    return out


def _touches_border(mask: np.ndarray) -> bool:
    return bool(mask[0, :].any() or mask[-1, :].any()
                or mask[:, 0].any() or mask[:, -1].any())


def measure(npz_path: Path, p_cut: float) -> dict:
    z = np.load(npz_path, allow_pickle=True)
    haz, obs = z["haz_stack"], z["obs_stack"]
    haz_times, obs_times = z["haz_times"], z["obs_times"]
    shape = (int(haz.shape[1]), int(haz.shape[2]))
    cell_m = float(z["grid_extent"][4])

    # The centre is licensed only because the two stacks AGREE at t=0. Assert it
    # rather than assume it: if they ever stop agreeing, the centre would be
    # taking information from one side of a comparison it is supposed to be
    # neutral between, and this run must fail rather than quietly bias the null.
    seed_haz = haz[0] >= p_cut
    seed_obs = obs[0] > 0
    seed_agrees = bool((seed_haz == seed_obs).all())
    if not seed_agrees:
        raise SystemExit(
            "the t=0 slices no longer agree cell-for-cell; the seed centroid is "
            "not a neutral centre and this null must be re-derived, not re-run")
    centre = _centroid(seed_obs)

    slices = []
    for i, t in enumerate(haz_times):
        j = int(np.argmin(np.abs(obs_times - t)))
        model = haz[i] >= p_cut
        seen = obs[j] > 0
        n = int(model.sum())
        disc = disc_mask(shape, centre, n)

        model_c = _centroid(model)
        disc_c = _centroid(disc)
        obs_c = _centroid(seen)
        d2_sel = ((np.indices(shape)[0] - centre[0]) ** 2
                  + (np.indices(shape)[1] - centre[1]) ** 2)[disc]

        m_score = _score(model, seen)
        d_score = _score(disc, seen)
        both_iou = m_score["iou"] is not None and d_score["iou"] is not None

        # ⚠ THE SEED IS INSIDE THE OBSERVATION BEING SCORED, and it is not a
        # prediction. obs_stack is CUMULATIVE, so the 249 seed cells are a subset
        # of every later observed footprint; the model's mask contains all of them
        # by construction, because they are its initial condition. The disc, being
        # a circle, recovers only some. So the model collects a free intersection
        # the null was never given, and the raw ratio above is inflated by an
        # initial condition rather than by skill. Removing the shared seed from
        # all THREE masks is the version with that advantage taken away, and both
        # are published (the lap's independent reviewer found this; it was not in
        # the row).
        m_bare = _score(model & ~seed_obs, seen & ~seed_obs)
        d_bare = _score(disc & ~seed_obs, seen & ~seed_obs)
        bare_iou = m_bare["iou"] is not None and d_bare["iou"] is not None
        slices.append({
            "haz_time_min": float(t),
            "obs_time_min": float(obs_times[j]),
            "time_gap_min": float(abs(obs_times[j] - t)),
            "is_seed_slice": i == 0,
            "n_cells": n,
            "model": m_score,
            "disc": d_score,
            # The whole point of the row, in one number per slice.
            "iou_delta_model_minus_disc": (
                round(m_score["iou"] - d_score["iou"], 4) if both_iou else None),
            # Registered so the page can say "N times the null" without doing
            # arithmetic in prose on two registered keys (CHARTER §3.3).
            "iou_ratio_model_over_disc": (
                round(m_score["iou"] / d_score["iou"], 4)
                if both_iou and d_score["iou"] else None),
            # The same comparison with the shared seed removed from all three
            # masks: the model's free initial condition taken away.
            "seed_removed": {
                "model": m_bare,
                "disc": d_bare,
                "iou_delta_model_minus_disc": (
                    round(m_bare["iou"] - d_bare["iou"], 4) if bare_iou else None),
                "iou_ratio_model_over_disc": (
                    round(m_bare["iou"] / d_bare["iou"], 4)
                    if bare_iou and d_bare["iou"] else None),
                "seed_cells_in_model": int((model & seed_obs).sum()),
                "seed_cells_in_disc": int((disc & seed_obs).sum()),
            },
            "disc_radius_cells": round(float(np.sqrt(d2_sel.max())), 3),
            "disc_touches_grid_border": _touches_border(disc),
            "model_touches_grid_border": _touches_border(model),
            # Direction, on its own, free of the shape confound above. Distances
            # are between centres of mass, in cells AND in metres, so the page
            # can quote either without multiplying in prose.
            "direction": _displacements({
                "seed_to_observed": (centre, obs_c),
                "seed_to_model": (centre, model_c),
                "seed_to_disc": (centre, disc_c),
                "model_to_observed": (model_c, obs_c),
                "disc_to_observed": (disc_c, obs_c),
            }, cell_m),
            # How much of the gap is shape rather than place: if the disc and the
            # model cover nearly the same cells, they are in the same place and
            # any IoU difference is shape.
            "disc_vs_model_iou": _score(disc, model)["iou"],
        })

    # The headline is the slice docs/oracle_gap.md §4 ALREADY quotes, fixed in the
    # claim commit before the answer was computed and not re-chosen afterwards:
    # the same selection rule measure_oracle_gap.py uses (exclude the shared t=0
    # seed, then smallest time gap).
    best = min((s for s in slices if not s["is_seed_slice"]),
               key=lambda s: s["time_gap_min"])

    return {
        "schema_version": 1,
        "title": "An area-matched disc null for the forward simulation — 영덕 2025, canonical",
        "row": "WFG-228",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _head(),
        "source_artifact": str(npz_path.relative_to(REPO)),
        "source_sha256": _sha256(npz_path),
        "p_cut": p_cut,
        "grid_shape": list(shape),
        "cell_size_m": cell_m,
        "null_rule": {
            "centre_row_col": [round(centre[0], 4), round(centre[1], 4)],
            "centre_from": "centroid of the t=0 seed, the 249 cells obs_stack[0]>0 "
                           "and haz_stack[0]>=p_cut agree on exactly",
            "seed_cells": int(seed_obs.sum()),
            "seed_stacks_agree": seed_agrees,
            "area_matched_to": "that slice's own predicted core count",
            "tie_break": "(row, col) ascending",
            "free_parameters": 0,
            "pre_registered_in": "the WFG-228 claim commit, before the run",
        },
        "slices": slices,
        "headline": dict(best, note=(
            "the slice docs/oracle_gap.md §4 already quotes — the 27-minute pair. "
            "Fixed in the claim commit before the answer was computed; not "
            "re-chosen afterwards")),
        "what_this_is_not": (
            "This is a comparison of two FIELDS against an observation, not a "
            "routing result: it produces no margin and moves no committed number. "
            "The gap between the model's IoU and the disc's is joint "
            "PLACEMENT-AND-SHAPE skill, not directional skill alone, because a "
            "disc differs from the model's core both in where its mass sits and in "
            "being a circle rather than an irregular terrain-shaped blob; the "
            "`direction` block is the direction-only reading. obs_stack is a "
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
    print(f"  headline slice: haz {h['haz_time_min']:.0f} min vs obs "
          f"{h['obs_time_min']:.0f} min (gap {h['time_gap_min']:.0f} min), "
          f"{h['n_cells']} cells each")
    print(f"  model IoU {h['model']['iou']}   disc IoU {h['disc']['iou']}   "
          f"delta {h['iou_delta_model_minus_disc']}")
    for s in doc["slices"]:
        if s["is_seed_slice"]:
            continue
        print(f"  t={s['haz_time_min']:.0f}min  n={s['n_cells']:>5}  "
              f"model {s['model']['iou']}  disc {s['disc']['iou']}  "
              f"delta {s['iou_delta_model_minus_disc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
