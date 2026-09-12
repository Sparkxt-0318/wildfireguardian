#!/usr/bin/env python
"""Register the rotation-null figures in docs/NUMBERS.json (WFG-256).

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads
the current file, replaces only the `rn_yeongdeok_` keys, and writes it back.

    python scripts/register_rotation_null.py          # upsert + report
    python scripts/register_rotation_null.py --check   # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/rotation_null_yeongdeok.json"
PREFIX = "rn_yeongdeok_"

#: The caveat every one of these keys carries. Point (2) is the one a later lap
#: will want to drop, because it is the half that keeps the result from being
#: read as「방향을 맞혔습니다」, which the centroid finding in docs/disc_null.md §4
#: contradicts and which this measurement does not license.
BAND = (
    "A REFERENCE SPREAD FOR ORIENTATION ON ONE FIRE, NOT A TEST, NOT A "
    "VALIDATION AND NOT A DECOMPOSITION. The model's own predicted core is "
    "rotated rigidly about the centroid of the t=0 seed — the same centre "
    "scripts/measure_disc_null.py asserts and uses — through every 15 degrees "
    "with 0 excluded (23 rotations), re-rasterised on the canonical 181x156 / "
    "500 m grid by inverse nearest-neighbour mapping, and scored against the "
    "SAME observation under the SAME nearest-observation matching and the SAME "
    "p_cut as the disc null, raw and with the shared seed removed. Shape and "
    "cell count are the model's own by construction, so the only thing that "
    "varies is ORIENTATION. The rule and the reading were pre-registered in the "
    "WFG-256 claim commit before the script existed. Six facts travel together "
    "or none may be quoted: (1) IT PRODUCES NO MARGIN AND MOVES NO COMMITTED "
    "NUMBER — 42, 91, 9 and 27 are untouched, nothing was routed and no "
    "committed artifact was regenerated; (2) ⚠⚠ IT IS NOT A DECOMPOSITION AND "
    "IT DOES NOT SAY THE MODEL GETS THE DIRECTION RIGHT. No arithmetic here "
    "splits the 2.2044 seed-removed ratio into a shape term and a placement "
    "term. What it supports is narrower: the overlap is not explained by the "
    "core's irregularity or by its being anchored at the seed, because 20 of "
    "the 23 rotations of that same irregular shape score BELOW the "
    "area-matched disc. The centroid finding in docs/disc_null.md §4 stands "
    "unchanged and points the other way — the model's centre of mass ends up "
    "FARTHER from the observation (5.34 cells) than the stationary disc's does "
    "(2.266) — so the honest joint reading is that the axis is right and the "
    "distance along it is overrun; (3) 23 ROTATIONS OF ONE FIRE IS NOT A TEST. "
    "No p-value is computed or quotable, one fire on one canvas at p_cut 0.5, "
    "and a rank of 1 of 24 is a rank among 23 deliberately misoriented copies "
    "of the model's own mask and NOT a rank against opponents anyone would "
    "build; (4) ROTATION ON A GRID DOES NOT PRESERVE THE CELL COUNT. The "
    "residual is reported per angle and NOT resampled away — worst case 1.26 "
    "per cent at the headline slice, no cells pushed off the canvas — and the "
    "three lattice-exact angles (90, 180, 270) carry a residual of exactly 0 "
    "while scoring among the LOWEST of the 23, which is how we know the spread "
    "is placement and not rasterisation; (5) obs_stack is a FIRMS-derived "
    "observation with its own detection floor (docs/detection_floor.md) and "
    "500 m resampling, so it is an observation and NOT ground truth; (6) the "
    "t=0 seed slice has no seed-removed figures at all, because removing the "
    "shared seed from the t=0 masks empties them — every seed-removed key here "
    "is an off-seed slice; and (7) EVERY BEATS / DOES-NOT-BEAT COUNT IS DECIDED "
    "AT FULL PRECISION ON BOTH SIDES while the published IoUs are rounded to 4 "
    "dp, because an ordering decided on two rounded values is decided at a "
    "precision the numbers do not carry. This lap's independent reviewer caught "
    "that: at t=720 one rotation (210 degrees) sits 2.66e-05 ABOVE the disc and "
    "is indistinguishable from it at the reported precision, so that slice's "
    "count is 4 and not the 3 a rounded comparison gave. Each slice registers "
    "its nearest rotation's signed margin so a count that would flip on the "
    "fifth decimal is visible rather than asserted."
)

FORBIDDEN = [
    "the rotation null validates the forecast",
    "the model gets the direction right",
    "the rotation null proves the model is skilful",
    "the model beats 23 baselines",
    "significantly better than chance",
    "p < 0.05",
    "모델이 확산 방향을 맞힙니다",
    "회전 대조군이 예보가 맞다는 것을 증명합니다",
]

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("n_rotations", "null_rule.n_rotations", "count",
     "the angles swept, pre-registered in the claim commit: every 15 degrees "
     "with 0 excluded"),
    ("angle_step_deg", "null_rule.angle_step_deg", "degrees",
     "the pre-registered sweep step"),
    ("horizon_min", "headline.haz_time_min", "minutes",
     "the forward-simulation slice quoted — the same one docs/oracle_gap.md §4 "
     "and docs/disc_null.md quote, fixed before the answer was computed"),
    ("obs_time_min", "headline.obs_time_min", "minutes",
     "the observation it is compared against"),
    ("time_gap_min", "headline.time_gap_min", "minutes",
     "how far apart in time the two compared slices are"),
    ("n_cells", "headline.n_cells", "cells",
     "cells in the forward-simulated core at this slice — the count every "
     "rotation is supposed to preserve and does not exactly"),
    # The headline comparison, seed removed, which is the fair one.
    ("bare_true_iou", "headline.unrotated.seed_removed_iou", "ratio",
     "seed-removed IoU of the model's core AS ORIENTED — the same 0.2577 the "
     "disc null registers as dn_yeongdeok_bare_model_iou, recomputed here so "
     "both sides of this comparison come out of one run"),
    ("bare_rotated_iou_min", "headline.seed_removed.rotated_iou_spread.min", "ratio",
     "the WORST of the 23 rotations, seed removed — the floor of the spread"),
    ("bare_rotated_iou_median", "headline.seed_removed.rotated_iou_spread.median", "ratio",
     "the median of the 23 rotations, seed removed"),
    ("bare_rotated_iou_max", "headline.seed_removed.rotated_iou_spread.max", "ratio",
     "the BEST of the 23 rotations, seed removed — what the best wrong "
     "orientation of the model's own shape achieves"),
    ("bare_true_rank", "headline.seed_removed.unrotated_rank_by_iou.rank", "rank",
     "the rank of the true orientation among all 24 orientations by seed-removed "
     "IoU, 1 = best. ⚠ A rank among 23 deliberately misoriented copies of the "
     "model's own mask, NOT a rank against opponents anyone would build"),
    ("bare_true_rank_of", "headline.seed_removed.unrotated_rank_by_iou.of", "count",
     "how many orientations that rank is out of — the 23 rotations plus the "
     "true one"),
    ("bare_true_rank_ties", "headline.seed_removed.unrotated_rank_by_iou.tied_with_it", "count",
     "how many rotations tie with the true orientation, reported so a rank that "
     "depended on a tie-break rule would be visible"),
    # The number that answers the row's question most directly.
    ("bare_disc_iou", "headline.seed_removed.disc_iou", "ratio",
     "the area-matched disc's seed-removed IoU at the same slice, read from the "
     "committed data/processed/disc_null_yeongdeok.json — the opponent the "
     "rotations are placed beside"),
    ("bare_worst_over_disc", "headline.seed_removed.worst_rotation_over_disc", "ratio",
     "the worst rotation's seed-removed IoU divided by the disc's: BELOW 1, so "
     "the worst orientation of the model's own irregular shape is a WORSE "
     "opponent than a circle"),
    ("rotations_beating_the_disc", "headline.seed_removed.rotations_beating_the_disc", "count",
     "how many of the 23 rotations score above the area-matched disc, seed "
     "removed — the measured form of 「a circle is a weak opponent by "
     "construction」, and it is a minority"),
    ("rotations_not_beating_the_disc", "headline.seed_removed.rotations_not_beating_the_disc", "count",
     "how many of the 23 rotations score at or below the area-matched disc, seed "
     "removed — misorientations of the model's OWN irregular shape that are a "
     "worse opponent than a circle, and they are the majority"),
    ("bare_true_over_disc", "headline.seed_removed.unrotated_over_disc", "ratio",
     "the true orientation's seed-removed IoU over the disc's — the same ratio "
     "the disc null registers as dn_yeongdeok_bare_iou_ratio, recomputed here"),
    # Rasterisation honesty, registered because the doc quotes it.
    ("centre_row", "null_rule.centre_row_col.0", "grid row",
     "the row of the centre of rotation: the t=0 seed centroid, the same centre "
     "scripts/measure_disc_null.py uses"),
    ("centre_col", "null_rule.centre_row_col.1", "grid column",
     "the column of the centre of rotation: the t=0 seed centroid"),
    ("rotated_iou_median", "headline.rotated_iou_spread.median", "ratio",
     "the median of the 23 rotations, seed KEPT — registered so the raw family "
     "is never represented on a page by its extremes alone"),
    ("bare_iou_at_345deg", "headline.rotations.22.seed_removed_iou", "ratio",
     "seed-removed IoU at 345 degrees, the other rotation adjacent to the true "
     "orientation — quoted because the spread decaying away from the truth on "
     "BOTH sides is what distinguishes an orientation signal from noise"),
    ("bare_iou_at_225deg", "headline.rotations.14.seed_removed_iou", "ratio",
     "seed-removed IoU at 225 degrees, the third-highest of the 23 and the only "
     "high one that is not adjacent to the true orientation"),
    ("headline_worst_cell_count_residual_frac", "headline.worst_cell_count_residual_frac", "ratio",
     "the largest absolute cell-count change any rotation caused AT THE HEADLINE "
     "SLICE, as a fraction of that slice's target — reported and NOT resampled "
     "away. ⚠ Scoped in the key's own name because it is NOT the worst across the "
     "run: the t=0 seed slice reaches 0.0522 and the 180-minute slice 0.0188, and "
     "an unqualified name invited that misreading"),
    ("headline_rotations_tied_with_the_disc", "headline.seed_removed.rotations_tied_with_the_disc_at_reported_precision", "count",
     "how many rotations are indistinguishable from the disc at the reported 4 dp "
     "at the headline slice — 0, which is why that slice's 3-and-20 split does not "
     "depend on the precision the comparison is made at"),
    ("headline_closest_rotation_angle_deg", "headline.seed_removed.closest_rotation_to_the_disc.angle_deg", "degrees",
     "the rotation closest to the disc at the headline slice"),
    ("headline_closest_rotation_margin", "headline.seed_removed.closest_rotation_to_the_disc.margin_over_the_disc", "ratio",
     "that rotation's signed full-precision margin over the disc — negative, so "
     "the headline count has room under it"),
    ("max_cells_pushed_off_grid", "headline.max_cells_pushed_off_grid", "cells",
     "the most cells any rotation pushed off the canvas at the headline slice — "
     "0, so no rotation was clipped and the rule executed as written"),
    ("lattice_exact_iou_max", "headline.lattice_exact_angles.iou_spread.max", "ratio",
     "the best raw IoU among the three lattice-exact angles (90, 180, 270), "
     "whose cell-count residual is exactly 0 — the handle on how much of the "
     "spread is rasterisation rather than placement"),
    # Raw (seed-kept) figures, so the page never quotes one family alone.
    ("true_iou", "headline.unrotated.iou", "ratio",
     "raw IoU of the model's core as oriented — the committed 0.3941, seed kept"),
    ("rotated_iou_min", "headline.rotated_iou_spread.min", "ratio",
     "the worst of the 23 rotations, seed kept"),
    ("rotated_iou_max", "headline.rotated_iou_spread.max", "ratio",
     "the best of the 23 rotations, seed kept"),
    ("nearest_rotation_overlap_with_true", "headline.rotations.0.iou_with_the_unrotated_core", "ratio",
     "IoU of the SMALLEST rotation (15 degrees) with the unrotated core itself: "
     "the nearest alternative orientation is mostly DIFFERENT cells, so the "
     "spread is not built out of near-copies of the true mask"),
    ("true_rank_raw", "headline.unrotated_rank_by_iou.rank", "rank",
     "the rank of the true orientation among all 24 by RAW IoU, 1 = best — "
     "registered so the seed-removed rank is never the only one on the page"),
]

#: Per-slice figures the document states in prose. CHARTER §3.3: a number you
#: cannot register, you do not write. The seed slice has no seed-removed block,
#: for the reason the disc registrar records.
SLICE_FIELDS = [
    ("bare_true_iou", "unrotated.seed_removed_iou", "ratio",
     "seed-removed IoU of the model's core as oriented at this slice"),
    ("bare_rotated_iou_min", "seed_removed.rotated_iou_spread.min", "ratio",
     "the worst of the 23 rotations at this slice, seed removed"),
    ("bare_rotated_iou_max", "seed_removed.rotated_iou_spread.max", "ratio",
     "the best of the 23 rotations at this slice, seed removed"),
    ("bare_true_rank", "seed_removed.unrotated_rank_by_iou.rank", "rank",
     "the rank of the true orientation among all 24 at this slice, 1 = best"),
    ("rotations_beating_the_disc", "seed_removed.rotations_beating_the_disc", "count",
     "how many of the 23 rotations beat the area-matched disc at this slice"),
    ("bare_disc_iou", "seed_removed.disc_iou", "ratio",
     "the disc's seed-removed IoU at this slice, from the committed disc artifact"),
    ("rotations_tied_with_the_disc", "seed_removed.rotations_tied_with_the_disc_at_reported_precision", "count",
     "rotations indistinguishable from the disc at the reported 4 dp at this "
     "slice — 1 at t=720, 0 everywhere else"),
    ("closest_rotation_angle_deg", "seed_removed.closest_rotation_to_the_disc.angle_deg", "degrees",
     "the rotation nearest the disc at this slice"),
    ("closest_rotation_margin", "seed_removed.closest_rotation_to_the_disc.margin_over_the_disc", "ratio",
     "that rotation's signed FULL-PRECISION margin over the disc at this slice, "
     "registered so a count that would flip on the fifth decimal is visible"),
]


def slice_figures(art: dict) -> list[tuple[str, str, str, str]]:
    out = []
    for i, row in enumerate(art["slices"]):
        if row["is_seed_slice"]:
            # Nothing here is defined at t=0: the seed-removed masks are empty
            # and every rotation of the seed is scored against its own seed.
            continue
        tag = f"t{int(row['haz_time_min'])}min"
        for suffix, field, unit, derivation in SLICE_FIELDS:
            out.append((f"{tag}_{suffix}", f"slices.{i}.{field}", unit,
                        f"{derivation} (forward-sim slice {row['haz_time_min']:.0f} min "
                        f"vs observation {row['obs_time_min']:.0f} min)"))
    return out


def _dig(doc: dict, path: str):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, path, unit, derivation in FIGURES + slice_figures(art):
        out[PREFIX + suffix] = {
            "value": _dig(art, path),
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": path,
            "derivation": derivation + ". Regenerate: python scripts/measure_rotation_null.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": "영덕 2025 · routing_demo_canonical.npz · 181x156 @ 500 m · p_cut 0.5",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_rotation_null.py rebuilds the "
                    "artifact from the committed routing_demo_canonical.npz and "
                    "the committed disc_null_yeongdeok.json alone, with no DEM, "
                    "no network access and no fitted model — it rotates one mask "
                    "23 times and counts overlaps, and it imports its scorer from "
                    "scripts/measure_disc_null.py rather than copying it."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "field_comparison",
            "notes": "docs/rotation_null.md states the method, the "
                     "pre-registration, the result and what it does NOT show; "
                     "docs/disc_null.md §5b puts the spread beside the disc it "
                     "refines. It is a field-to-field comparison and produces no "
                     "routing margin.",
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": ARTIFACT, "json_path": path}}},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    art = json.loads((REPO / ARTIFACT).read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    new = build_entries(art, head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items()
             if k not in cur or cur[k]["value"] != e["value"]
             or cur[k].get("caveat") != e.get("caveat")]
    if args.check:
        if stale:
            print("STALE rotation-null registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} rotation-null entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} rotation-null entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
