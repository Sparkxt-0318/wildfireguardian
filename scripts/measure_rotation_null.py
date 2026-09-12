#!/usr/bin/env python
"""Is the 2.2x over the disc bought by getting the SHAPE right, or by not being a circle?

WFG-256. Reads TWO committed artifacts — ``data/processed/routing_demo_canonical.npz``
(the grids) and ``data/processed/disc_null_yeongdeok.json`` (the published disc
figures this compares against) — and writes ``data/processed/rotation_null_yeongdeok.json``.
It regenerates nothing and moves no committed number.

WHY THIS SCRIPT EXISTS
----------------------
``docs/disc_null.md`` and ``docs/auto/JUDGE_QA.md`` Q36 report that the
forward-simulated core beats an area-matched disc by ``dn_yeongdeok_bare_iou_ratio``
(2.2044, seed removed). Until this run, the repository could not say what that
ratio is made of. The statistician and ML-reviewer lenses both ask the same
question in one sentence — 「그 2.2배가 모양을 맞혀서입니까, 원이 아니라서입니까?」 — and
`WFG-254` had to strike 「모양」 off the card because no measurement supported it.
The disc differs from the core in two ways at once (where its mass sits, and being
a circle rather than an irregular blob), so the disc comparison alone cannot
separate them.

THE NULL, AND WHY IT HAS NO FREE PARAMETERS
-------------------------------------------
Hold the model's shape and cell count fixed and vary only its ORIENTATION about
the fire's own start. For each forward-simulation slice, take the model's own
predicted core (``haz_stack[i] >= p_cut``) and rotate that mask rigidly about the
centroid of the ``t = 0`` seed — the cells ``obs_stack[0] > 0`` and
``haz_stack[0] >= p_cut`` agree on exactly, the same centre
``scripts/measure_disc_null.py`` asserts and uses, and the only centre that uses no
information the model did not have — through every 15 degrees, 0 excluded, and
score each rotated mask against the same observation under the same
nearest-observation time-matching rule and the same ``p_cut``, raw and with the
shared seed removed.

The scorer is **imported** from ``scripts/measure_disc_null.py`` rather than copied,
so the disc numbers and the rotation numbers cannot drift apart.

⚠ WHAT THIS IS A NULL FOR, AND WHAT IT IS NOT
---------------------------------------------
Rotating the core varies **where the mass sits** while holding shape and area
fixed. So this is a reference spread for **orientation**, and it is NOT a
decomposition of the IoU gap into a shape term and a placement term: no
arithmetic here splits 2.2044 into two addends, and the document must not read as
though it does. What it can say is narrower, and is what the row asked for:
whether any orientation of this blob would have scored about as well, and whether
the WORST orientation still beats the circle. The second question is the one that
turns ``docs/disc_null.md`` §5's qualitative 「a circle scored against an elongated
fire is a weak opponent by construction」 into a measured statement.

⚠ Rotation on a grid does not preserve the cell count exactly. Every angle reports
the count it achieved beside the count it was supposed to have, and the cells that
fell off the grid edge. The residual is **stated, not resampled away**: nothing
here re-thresholds, re-fits or resamples to close it.

⚠ NO P-VALUE. 23 rotations of one fire on one canvas at one threshold is a
reference spread, not a test.

The rule above and the reading in ``docs/rotation_null.md`` §2b were written into
the WFG-256 claim commit before this script existed.

Run:  python scripts/measure_rotation_null.py
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_disc_null import _centroid, _score, disc_mask  # noqa: E402  (same code, not a copy)

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / "data/processed/routing_demo_canonical.npz"
DISC = REPO / "data/processed/disc_null_yeongdeok.json"
OUT = REPO / "data/processed/rotation_null_yeongdeok.json"

#: Pre-registered in the WFG-256 claim commit: every 15 degrees, 0 excluded.
ANGLES_DEG = list(range(15, 360, 15))
#: On a square lattice these three are exact permutations of the grid up to the
#: rounding of a non-integer centre, so they are the handle on how much of any
#: spread is rasterisation rather than placement.
LATTICE_EXACT_DEG = (90, 180, 270)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def rotate_mask(mask: np.ndarray, centre: tuple[float, float], deg: float) -> np.ndarray:
    """``mask`` rotated rigidly by ``deg`` about ``centre``, inverse nearest-neighbour.

    For each cell of the OUTPUT grid, rotate its centre by ``-deg`` about
    ``centre``, round to the nearest input cell and take that cell's membership.
    Inverse mapping is used because forward mapping leaves holes; neither
    preserves the cell count exactly, which is why the count is reported and not
    corrected.
    """
    n_rows, n_cols = mask.shape
    rr, cc = np.indices(mask.shape)
    dr = rr - centre[0]
    dc = cc - centre[1]
    a = np.deg2rad(-float(deg))
    ca, sa = np.cos(a), np.sin(a)
    src_r = np.rint(dr * ca - dc * sa + centre[0]).astype(int)
    src_c = np.rint(dr * sa + dc * ca + centre[1]).astype(int)
    inside = (src_r >= 0) & (src_r < n_rows) & (src_c >= 0) & (src_c < n_cols)
    out = np.zeros_like(mask, dtype=bool)
    out[inside] = mask[src_r[inside], src_c[inside]]
    return out


def _cells_off_grid(mask: np.ndarray, centre: tuple[float, float], deg: float) -> int:
    """How many of the mask's own cells land outside the canvas when rotated.

    Measured by FORWARD mapping, which is the question 「did the rotation push part
    of the fire off the map」 — separate from the inverse-mapped rasterisation
    above, and reported so a reader can tell a clipped rotation from a clean one.
    """
    rr, cc = np.nonzero(mask)
    dr = rr - centre[0]
    dc = cc - centre[1]
    a = np.deg2rad(float(deg))
    ca, sa = np.cos(a), np.sin(a)
    fr = np.rint(dr * ca - dc * sa + centre[0]).astype(int)
    fc = np.rint(dr * sa + dc * ca + centre[1]).astype(int)
    n_rows, n_cols = mask.shape
    outside = (fr < 0) | (fr >= n_rows) | (fc < 0) | (fc >= n_cols)
    return int(outside.sum())


def _iou_full(pred: np.ndarray, seen: np.ndarray) -> float:
    """IoU at FULL precision.

    ``_score`` rounds to 4 dp, which is the right precision to PUBLISH and the
    wrong precision to decide an ordering on: 「does this rotation beat the disc」
    answered on two 4-dp values is answered at a precision the stored numbers do
    not carry. This lap's independent reviewer caught exactly that — one 720-min
    rotation sits 2.7e-5 above the disc and was being counted as not beating it.
    So every comparison below is made here, and the published values stay rounded.
    """
    union = int((pred | seen).sum())
    return (int((pred & seen).sum()) / union) if union else 0.0


def _spread(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    return {
        "n": int(arr.size),
        "min": round(float(arr.min()), 4),
        "median": round(float(np.median(arr)), 4),
        "max": round(float(arr.max()), 4),
        "mean": round(float(arr.mean()), 4),
    }


def _rank_of(value: float, others: list[float]) -> dict:
    """Rank of ``value`` among ``[value] + others``, 1 = best, plus the tie count.

    Ties are reported rather than broken: a rank that depends on a tie-break rule
    is a rank that would move if the rule moved.
    """
    better = sum(1 for o in others if o > value)
    tied = sum(1 for o in others if o == value)
    return {
        "rank": better + 1,
        "of": len(others) + 1,
        "strictly_better_than_it": better,
        "tied_with_it": tied,
    }


def measure(npz_path: Path, disc_path: Path, p_cut: float) -> dict:
    z = np.load(npz_path, allow_pickle=True)
    haz, obs = z["haz_stack"], z["obs_stack"]
    haz_times, obs_times = z["haz_times"], z["obs_times"]
    shape = (int(haz.shape[1]), int(haz.shape[2]))
    cell_m = float(z["grid_extent"][4])

    # The same assertion measure_disc_null.py makes, for the same reason: the
    # centre is licensed ONLY because the two stacks agree at t=0. If they ever
    # stop agreeing, the centre is taking information from one side of a
    # comparison it is supposed to be neutral about, and this must fail loudly.
    seed_haz = haz[0] >= p_cut
    seed_obs = obs[0] > 0
    if not bool((seed_haz == seed_obs).all()):
        raise SystemExit(
            "the t=0 slices no longer agree cell-for-cell; the seed centroid is "
            "not a neutral centre of rotation and this null must be re-derived")
    centre = _centroid(seed_obs)

    disc_doc = json.loads(disc_path.read_text(encoding="utf-8"))
    disc_by_time = {float(s["haz_time_min"]): s for s in disc_doc["slices"]}

    slices = []
    for i, t in enumerate(haz_times):
        j = int(np.argmin(np.abs(obs_times - t)))
        model = haz[i] >= p_cut
        seen = obs[j] > 0
        target = int(model.sum())
        is_seed = i == 0

        unrotated_raw = _score(model, seen)
        unrotated_bare = _score(model & ~seed_obs, seen & ~seed_obs)

        rotations = []
        bare_full: list[float] = []
        for deg in ANGLES_DEG:
            rot = rotate_mask(model, centre, deg)
            achieved = int(rot.sum())
            raw = _score(rot, seen)
            bare = _score(rot & ~seed_obs, seen & ~seed_obs)
            bare_full.append(_iou_full(rot & ~seed_obs, seen & ~seed_obs))
            rotations.append({
                "angle_deg": deg,
                "is_lattice_exact": deg in LATTICE_EXACT_DEG,
                "target_cells": target,
                "achieved_cells": achieved,
                # Stated, never corrected: rotation on a grid does not preserve
                # the count and this run does not resample until it does.
                "cell_count_residual": achieved - target,
                "cell_count_residual_frac": round((achieved - target) / target, 4) if target else None,
                "cells_pushed_off_grid": _cells_off_grid(model, centre, deg),
                "iou": raw["iou"],
                "seed_removed_iou": bare["iou"],
                # How different this orientation actually is from the real one. A
                # rotation that still covers most of the original would make the
                # spread look tight for a trivial reason.
                "iou_with_the_unrotated_core": _score(rot, model)["iou"],
            })

        raw_ious = [r["iou"] for r in rotations]
        bare_ious = [r["seed_removed_iou"] for r in rotations]
        lattice = [r for r in rotations if r["is_lattice_exact"]]

        entry = {
            "haz_time_min": float(t),
            "obs_time_min": float(obs_times[j]),
            "time_gap_min": float(abs(obs_times[j] - t)),
            "is_seed_slice": is_seed,
            "n_cells": target,
            "unrotated": {"iou": unrotated_raw["iou"],
                          "seed_removed_iou": unrotated_bare["iou"]},
            "rotations": rotations,
            "rotated_iou_spread": _spread(raw_ious),
            "unrotated_rank_by_iou": _rank_of(unrotated_raw["iou"], raw_ious),
            # The rasterisation handle: the three lattice-exact angles, whose
            # counts should sit on the target if the mapping is behaving.
            "lattice_exact_angles": {
                "angles_deg": [r["angle_deg"] for r in lattice],
                "cell_count_residuals": [r["cell_count_residual"] for r in lattice],
                "iou_spread": _spread([r["iou"] for r in lattice]),
            },
            "worst_cell_count_residual_frac": round(
                max(abs(r["cell_count_residual_frac"]) for r in rotations), 4),
            "max_cells_pushed_off_grid": max(r["cells_pushed_off_grid"] for r in rotations),
        }

        if not is_seed:
            # The seed-removed figures are DEGENERATE at t=0 (taking the shared
            # seed out of the t=0 masks empties them), exactly as the disc
            # registrar records; so the fair comparison exists only off the seed.
            disc_slice = disc_by_time[float(t)]
            disc_bare = disc_slice["seed_removed"]["disc"]["iou"]
            worst = min(bare_ious)
            # ⚠ The disc mask is rebuilt here with the disc null's OWN disc_mask
            # function (imported, not copied) for one purpose only: to compare at
            # full precision. The PUBLISHED opponent stays disc_bare, the committed
            # 4-dp value, and the assertion below refuses to continue if the two
            # ever disagree at that precision.
            disc = disc_mask(shape, centre, target)
            disc_full = _iou_full(disc & ~seed_obs, seen & ~seed_obs)
            if round(disc_full, 4) != disc_bare:
                raise SystemExit(
                    f"the rebuilt disc at t={t:.0f} scores {round(disc_full, 4)} "
                    f"but the committed disc artifact says {disc_bare}; the two "
                    "nulls are no longer scoring the same object")
            beats = sum(1 for v in bare_full if v > disc_full)
            # A count that would flip on the 5th decimal is a count a judge can
            # read and we cannot defend, so the near-ties are named rather than
            # silently resolved either way.
            ties_at_4dp = sum(1 for v in bare_full if round(v, 4) == disc_bare)
            closest = min(range(len(bare_full)),
                          key=lambda k: abs(bare_full[k] - disc_full))
            entry["seed_removed"] = {
                "rotated_iou_spread": _spread(bare_ious),
                "unrotated_rank_by_iou": _rank_of(unrotated_bare["iou"], bare_ious),
                "comparison_precision": (
                    "every beats/does-not-beat decision below is made at FULL "
                    "precision on both sides; the reported IoUs are rounded to 4 dp"),
                "rotations_tied_with_the_disc_at_reported_precision": ties_at_4dp,
                "closest_rotation_to_the_disc": {
                    "angle_deg": ANGLES_DEG[closest],
                    "margin_over_the_disc": round(bare_full[closest] - disc_full, 8),
                    "indistinguishable_at_reported_precision":
                        bool(round(bare_full[closest], 4) == disc_bare),
                },
                # ⚠ THE NUMBER THE ROW ASKED FOR MOST DIRECTLY. If the WORST
                # orientation of the model's own blob still beats the circle, that
                # much of the ratio is bought by not being a circle rather than by
                # placement — and the disc's own "weak opponent by construction"
                # stops being a qualitative claim.
                "disc_iou": disc_bare,
                "worst_rotation_iou": worst,
                "worst_rotation_over_disc": round(worst / disc_bare, 4) if disc_bare else None,
                "worst_rotation_beats_the_disc": bool(min(bare_full) > disc_full),
                "rotations_beating_the_disc": beats,
                # Registered too, so no page has to subtract one registered key
                # from another in prose (CHARTER §3.3).
                "rotations_not_beating_the_disc": len(bare_full) - beats,
                "unrotated_over_disc": round(unrotated_bare["iou"] / disc_bare, 4) if disc_bare else None,
                "unrotated_beats_the_disc": bool(
                    _iou_full(model & ~seed_obs, seen & ~seed_obs) > disc_full),
            }
        slices.append(entry)

    # The same headline rule measure_disc_null.py fixes, and fixed here before the
    # run: exclude the t=0 seed slice, then smallest time gap.
    best = min((s for s in slices if not s["is_seed_slice"]),
               key=lambda s: s["time_gap_min"])

    return {
        "schema_version": 1,
        "title": "A rotation null for the forward simulation — 영덕 2025, canonical",
        "row": "WFG-256",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _head(),
        "source_artifacts": {
            str(npz_path.relative_to(REPO)): _sha256(npz_path),
            str(disc_path.relative_to(REPO)): _sha256(disc_path),
        },
        "p_cut": p_cut,
        "grid_shape": list(shape),
        "cell_size_m": cell_m,
        "null_rule": {
            "what_varies": "orientation only",
            "what_is_held_fixed": "the model's own shape and its cell count",
            "centre_row_col": [round(centre[0], 4), round(centre[1], 4)],
            "centre_from": "centroid of the t=0 seed, the 249 cells obs_stack[0]>0 "
                           "and haz_stack[0]>=p_cut agree on exactly — the same "
                           "centre scripts/measure_disc_null.py asserts and uses, "
                           "and the only centre that uses no information the model "
                           "did not have",
            "angles_deg": ANGLES_DEG,
            "n_rotations": len(ANGLES_DEG),
            "angle_step_deg": 15,
            "zero_excluded": True,
            "rasterisation": "inverse nearest-neighbour: each output cell is "
                             "rotated by -theta about the centre, rounded, and "
                             "takes that input cell's membership",
            "cell_count_is_not_resampled": True,
            "scorer": "imported from scripts/measure_disc_null.py (_score), not "
                      "copied, so the disc and rotation figures cannot drift",
            "time_matching": "argmin |obs_times - haz_time|, the same rule as "
                             "scripts/measure_oracle_gap.py and measure_disc_null.py",
            "free_parameters": 0,
            "p_value_reported": False,
            "pre_registered_in": "the WFG-256 claim commit, before this script existed",
        },
        "slices": slices,
        "headline": dict(best, note=(
            "the slice docs/oracle_gap.md §4 and docs/disc_null.md already quote — "
            "the 27-minute pair. Fixed by the same rule measure_disc_null.py uses, "
            "in the claim commit, before the answer was computed")),
        "what_this_is_not": (
            "A REFERENCE SPREAD FOR ORIENTATION ON ONE FIRE, NOT A TEST AND NOT A "
            "DECOMPOSITION. Rotating the model's own core about the t=0 seed "
            "centroid varies WHERE THE MASS SITS while holding shape and cell "
            "count fixed, so this spread says whether any orientation of this blob "
            "would have scored about as well. It does NOT split the model-over-disc "
            "ratio into a shape term and a placement term; no arithmetic here does "
            "that, and a reading that treats it as an additive decomposition is "
            "wrong. No p-value is reported: 23 rotations of one fire on one canvas "
            "at one p_cut is a reference spread. Rotation on a grid does not "
            "preserve the cell count exactly; the residual is reported per angle "
            "and is NOT resampled away. obs_stack is a FIRMS-derived observation "
            "with its own detection floor (docs/detection_floor.md), not ground "
            "truth. It re-routes nothing, produces no margin and moves no "
            "committed number."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--p-cut", type=float, default=0.5,
                    help="the committed routing impassability threshold")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    for path in (NPZ, DISC):
        if not path.exists():
            print(f"missing committed artifact: {path}", file=sys.stderr)
            return 2

    doc = measure(NPZ, DISC, args.p_cut)
    args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    h = doc["headline"]
    sr = h["seed_removed"]
    print(f"wrote {args.out.relative_to(REPO)}")
    print(f"  headline slice: haz {h['haz_time_min']:.0f} min vs obs "
          f"{h['obs_time_min']:.0f} min (gap {h['time_gap_min']:.0f} min), "
          f"{h['n_cells']} cells, {len(ANGLES_DEG)} rotations")
    print(f"  seed-removed: unrotated {h['unrotated']['seed_removed_iou']}  "
          f"rotated {sr['rotated_iou_spread']['min']} .. "
          f"{sr['rotated_iou_spread']['max']} "
          f"(median {sr['rotated_iou_spread']['median']})")
    print(f"  rank of the true orientation: "
          f"{sr['unrotated_rank_by_iou']['rank']} of {sr['unrotated_rank_by_iou']['of']}"
          f"  (tied with {sr['unrotated_rank_by_iou']['tied_with_it']})")
    print(f"  worst rotation {sr['worst_rotation_iou']} vs disc {sr['disc_iou']}"
          f"  -> beats the disc: {sr['worst_rotation_beats_the_disc']}"
          f"  ({sr['rotations_beating_the_disc']} of {len(ANGLES_DEG)} do)")
    print(f"  worst cell-count residual {h['worst_cell_count_residual_frac']}, "
          f"max cells pushed off grid {h['max_cells_pushed_off_grid']}")
    for s in doc["slices"]:
        if s["is_seed_slice"]:
            continue
        q = s["seed_removed"]
        print(f"  t={s['haz_time_min']:.0f}min n={s['n_cells']:>5}  "
              f"true {s['unrotated']['seed_removed_iou']}  "
              f"rank {q['unrotated_rank_by_iou']['rank']}/{q['unrotated_rank_by_iou']['of']}  "
              f"rot {q['rotated_iou_spread']['min']}..{q['rotated_iou_spread']['max']}  "
              f"disc {q['disc_iou']}  beaten by {q['rotations_beating_the_disc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
