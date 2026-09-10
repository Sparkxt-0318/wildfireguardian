#!/usr/bin/env python
"""Register the area-matched disc null figures in docs/NUMBERS.json (WFG-228).

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads
the current file, replaces only the `dn_yeongdeok_` keys, and writes it back.

    python scripts/register_disc_null.py          # upsert + report
    python scripts/register_disc_null.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/disc_null_yeongdeok.json"
PREFIX = "dn_yeongdeok_"

#: The caveat every one of these keys carries. Point (3) is the one this lap
#: went looking for and did NOT expect to find; it is in the band because the
#: IoU gap alone, quoted without it, says something the data does not support.
BAND = (
    "A FLOOR FOR ONE METRIC ON ONE FIRE, NOT A VALIDATION AND NOT A ROUTING "
    "RESULT. An area-matched disc — centred on the centroid of the t=0 seed the "
    "two stacks agree on exactly, holding exactly as many cells as that slice's "
    "own predicted core, ties broken by (row, col), zero free parameters, the "
    "rule pre-registered in the WFG-228 claim commit before the run — is scored "
    "against the SAME observed footprint under the SAME nearest-observation "
    "matching as scripts/measure_oracle_gap.py. Six facts travel together or "
    "none may be quoted: (1) it produces NO margin and moves no committed "
    "number — 42, 91, 9 and 27 are untouched, and no route was run; (2) THE DISC "
    "IS A FLOOR, NOT A COMPETITIVE BASELINE. It is a circle scored against an "
    "elongated fire, which is a weak opponent by construction, so clearing it is "
    "NECESSARY and not SUFFICIENT evidence of skill; the persistence and "
    "isotropic baselines in src/wildfireguardian/validation/baselines.py are NOT "
    "scored against this truth — validation/harness.py:703-704 does run them, but "
    "with a POLYGON IoU against an observed perimeter series the harness itself "
    "labels 'APPROXIMATE, reconstructed from public reporting', not against the "
    "FIRMS-derived obs_stack raster that produced 0.394, so the two IoU families "
    "are not comparable as they stand — and until one is, 'better than the null' "
    "means only 'better than THIS null'. (3) ⚠ THE GAP IS NOT "
    "DIRECTIONAL SKILL, and quoting it as though it were reverses what the "
    "centroids say. The observed footprint's centre of mass moves only 2.25 "
    "cells from the seed while the model's core moves 7.292, and the DISC's "
    "centre of mass ends up CLOSER to the observation (2.266 cells) than the "
    "model's does (5.34). So the model's advantage over the disc is in SHAPE and "
    "EXTENT — it reproduces an irregular, elongated footprint where the disc "
    "cannot — while its centre of mass OVERSHOOTS the fire. Quote the IoU gap "
    "and the centroid displacements together, or quote neither; (4) obs_stack is "
    "a FIRMS-derived observation with its own detection floor "
    "(docs/detection_floor.md) and 500 m resampling, so it is an observation and "
    "NOT ground truth; (5) the t=0 slice is excluded from the headline because "
    "both stacks are seeded from the same detection there, and three of the four "
    "remaining slices are graded against the SAME observation (obs_time_min 333) "
    "— quote each figure with its own dn_yeongdeok_t###min_time_gap_min or do "
    "not quote it; (6) ⚠⚠ THE RAW RATIO IS INFLATED BY AN INITIAL CONDITION, AND "
    "THE SEED-REMOVED FIGURES ARE THE FAIR ONES. obs_stack is CUMULATIVE, so the "
    "249-cell t=0 seed is a SUBSET of the 937-cell observation being scored. The "
    "model's core contains all 249 by construction — they are its initial "
    "condition, not a prediction — while the disc, being a circle, recovers only "
    "92. Remove the shared seed from all three masks and the headline goes from "
    "model 0.3941 / disc 0.1554 / ratio 2.536 to model 0.2577 / disc 0.1169 / "
    "ratio 2.2044. The finding survives in sign at every slice, but any quote of "
    "2.536 that does not carry 2.2044 beside it is quoting a number an initial "
    "condition helped produce. This was found by the row's independent reviewer, "
    "not by the row and not by the lap."
)

FORBIDDEN = [
    "the model gets the direction right",
    "the disc null validates the forecast",
    "0.394 is a good score",
    "the forecast beats the baseline",
    "모델이 확산 방향을 맞힙니다",
    "the null model proves the forecast works",
    "2.5 times more accurate",
    "the model is 2.5x better than a coin flip",
]

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("horizon_min", "headline.haz_time_min", "minutes",
     "the forward-simulation slice quoted — the same one docs/oracle_gap.md §4 "
     "quotes, fixed before the answer was computed"),
    ("obs_time_min", "headline.obs_time_min", "minutes",
     "the observation it is compared against"),
    ("time_gap_min", "headline.time_gap_min", "minutes",
     "how far apart in time the two compared slices are"),
    ("n_cells", "headline.n_cells", "cells",
     "cells in the forward-simulated core at this slice, and therefore also the "
     "cell count handed to the disc — the area match IS this number"),
    ("model_iou", "headline.model.iou", "ratio",
     "intersection over union of the forward-simulated core with the observed "
     "footprint — the 0.394 docs/oracle_gap.md §4 already reports, recomputed "
     "here so the two sides of the comparison come out of one run"),
    ("disc_iou", "headline.disc.iou", "ratio",
     "intersection over union of the AREA-MATCHED DISC with the same observed "
     "footprint — what 0.394 should be compared with"),
    ("iou_delta", "headline.iou_delta_model_minus_disc", "ratio",
     "model IoU minus disc IoU: joint placement-and-shape skill over the null, "
     "NOT directional skill (see the caveat)"),
    ("iou_ratio", "headline.iou_ratio_model_over_disc", "ratio",
     "model IoU divided by disc IoU, registered so the ratio is never computed "
     "in prose from two other keys"),
    ("disc_intersection_cells", "headline.disc.intersection_cells", "cells",
     "cells the disc and the observation agree burned"),
    ("disc_false_alarm_cells", "headline.disc.false_alarm_cells", "cells",
     "cells the disc puts in the fire that the observation does not record "
     "burning at the matched time"),
    ("disc_missed_cells", "headline.disc.missed_cells", "cells",
     "cells the observation records burning that the disc does not contain"),
    ("disc_radius_cells", "headline.disc_radius_cells", "cells",
     "the distance from the seed centroid to the farthest cell the disc took — "
     "the disc's effective radius at the quoted slice"),
    ("disc_vs_model_iou", "headline.disc_vs_model_iou", "ratio",
     "intersection over union of the disc with the MODEL's core: how much of the "
     "two masks is the same cells, which is what makes them different objects "
     "rather than the same mask twice"),
    ("seed_to_observed_cells", "headline.direction.seed_to_observed_cells", "cells",
     "how far the OBSERVED footprint's centre of mass moved from the seed "
     "centroid — how far the fire actually went, as a centre of mass"),
    ("seed_to_model_cells", "headline.direction.seed_to_model_cells", "cells",
     "how far the MODEL's core centre of mass moved from the seed centroid — how "
     "far the model sent the fire"),
    ("model_to_observed_cells", "headline.direction.model_to_observed_cells", "cells",
     "the distance between the model's centre of mass and the observation's — the "
     "model's centre-of-mass error, which is LARGER than the disc's"),
    ("disc_to_observed_cells", "headline.direction.disc_to_observed_cells", "cells",
     "the distance between the disc's centre of mass and the observation's — the "
     "null's centre-of-mass error, which is SMALLER than the model's"),
    # The same four in metres, registered so the page never multiplies a cell
    # count by 500 in prose (CHARTER §3.3).
    ("seed_to_observed_m", "headline.direction.seed_to_observed_m", "metres",
     "how far the OBSERVED footprint's centre of mass moved from the seed centroid"),
    ("seed_to_model_m", "headline.direction.seed_to_model_m", "metres",
     "how far the MODEL's core centre of mass moved from the seed centroid"),
    ("model_to_observed_m", "headline.direction.model_to_observed_m", "metres",
     "the model's centre-of-mass error"),
    ("disc_to_observed_m", "headline.direction.disc_to_observed_m", "metres",
     "the null's centre-of-mass error"),
    # ⚠ The seed-removed comparison. These exist because the raw figures above
    # hand the model a 249-cell intersection it did not predict.
    ("bare_model_iou", "headline.seed_removed.model.iou", "ratio",
     "model IoU with the shared t=0 seed removed from the model mask, the disc "
     "and the observation — the comparison with the model's free initial "
     "condition taken away"),
    ("bare_disc_iou", "headline.seed_removed.disc.iou", "ratio",
     "disc IoU with the shared t=0 seed removed from all three masks"),
    ("bare_iou_ratio", "headline.seed_removed.iou_ratio_model_over_disc", "ratio",
     "model IoU divided by disc IoU, seed removed — the HONEST ratio, and the one "
     "a fair reading quotes beside the raw one"),
    ("bare_iou_delta", "headline.seed_removed.iou_delta_model_minus_disc", "ratio",
     "model minus disc IoU with the shared seed removed"),
    ("seed_cells_in_model", "headline.seed_removed.seed_cells_in_model", "cells",
     "how many of the 249 shared seed cells the MODEL's core contains — all of "
     "them, by construction, because they are its initial condition"),
    ("seed_cells_in_disc", "headline.seed_removed.seed_cells_in_disc", "cells",
     "how many of the 249 shared seed cells the DISC contains — the asymmetry the "
     "seed_removed figures exist to remove"),
]


#: Every per-slice figure the document states in prose. CHARTER §3.3: a number
#: you cannot register, you do not write. The t=0 row is registered like the
#: rest because the document quotes it as the sanity anchor that the fire was
#: never disc-shaped in the first place.
SLICE_FIELDS = [
    ("disc_iou", "disc.iou", "ratio",
     "intersection over union of the area-matched disc with the observed footprint"),
    ("model_iou", "model.iou", "ratio",
     "intersection over union of the forward-simulated core with the same footprint"),
    ("iou_delta", "iou_delta_model_minus_disc", "ratio",
     "model IoU minus disc IoU at this slice"),
    ("iou_ratio", "iou_ratio_model_over_disc", "ratio",
     "model IoU divided by disc IoU at this slice"),
    ("time_gap_min", "time_gap_min", "minutes",
     "how far apart in time this pair of slices is"),
    ("obs_time_min", "obs_time_min", "minutes",
     "the observation time this slice was graded against — THREE of the four "
     "non-seed slices share one observation, which is why this key exists per "
     "slice and not once"),
    ("n_cells", "n_cells", "cells",
     "the predicted core count at this slice, which is also the disc's cell count"),
    # WFG-228's independent reviewer blocked on exactly this gap: docs/disc_null.md
    # quoted the LARGEST disc radius (18.162, the t=720 slice) while the only
    # registered radius was the headline's 17.355, and make verify's collision
    # gate caught it. A per-slice key is the fix; a per-slice quantity the prose
    # can reach needs a per-slice key.
    ("disc_radius_cells", "disc_radius_cells", "cells",
     "the distance from the seed centroid to the farthest cell the disc took at "
     "this slice — the disc's effective radius"),
    ("disc_intersection_cells", "disc.intersection_cells", "cells",
     "cells the disc and the observation agree burned at this slice"),
    ("bare_disc_iou", "seed_removed.disc.iou", "ratio",
     "disc IoU at this slice with the shared t=0 seed removed from all three masks"),
    ("bare_model_iou", "seed_removed.model.iou", "ratio",
     "model IoU at this slice with the shared t=0 seed removed from all three masks"),
    ("bare_iou_ratio", "seed_removed.iou_ratio_model_over_disc", "ratio",
     "model IoU divided by disc IoU at this slice, shared seed removed"),
]


def slice_figures(art: dict) -> list[tuple[str, str, str, str]]:
    """One key per per-slice quantity the prose quotes, named by hazard time."""
    out = []
    for i, row in enumerate(art["slices"]):
        tag = f"t{int(row['haz_time_min'])}min"
        for suffix, field, unit, derivation in SLICE_FIELDS:
            # The seed-removed figures are DEGENERATE at the seed slice: taking
            # the shared seed out of the t=0 masks leaves the model and the
            # observation with zero cells, so the IoU is undefined and the disc's
            # is a meaningless 0.0. Registering it would put a null quantity in
            # the registry and, on the first run, collided with paper/GAPS.md's
            # (correct) og_yeongdeok_t0min_iou = 1.0. A number that means nothing
            # does not get a key.
            if row["is_seed_slice"] and suffix.startswith("bare_"):
                continue
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
            "derivation": derivation + ". Regenerate: python scripts/measure_disc_null.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": "영덕 2025 · routing_demo_canonical.npz · 181x156 @ 500 m · p_cut 0.5",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_disc_null.py rebuilds the artifact "
                    "from the committed routing_demo_canonical.npz alone, with "
                    "no DEM, no network access and no fitted model — it reads "
                    "two arrays out of one file, sorts cells by distance and "
                    "counts overlaps."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "field_comparison",
            "notes": "docs/disc_null.md states the method, the pre-registration, "
                     "the result and what it does NOT show; docs/oracle_gap.md "
                     "§4c puts the two IoUs side by side. It is a field-to-field "
                     "comparison and produces no routing margin.",
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
            print("STALE disc-null registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} disc-null entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} disc-null entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
