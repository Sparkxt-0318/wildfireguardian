#!/usr/bin/env python
"""Register the planning-field-vs-observation figures in docs/NUMBERS.json (WFG-125).

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads
the current file, replaces only the `og_yeongdeok_` keys, and writes it back.

    python scripts/register_oracle_gap.py          # upsert + report
    python scripts/register_oracle_gap.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/oracle_gap_yeongdeok.json"
PREFIX = "og_yeongdeok_"

#: The caveat every one of these keys carries. These figures are quotable ONLY
#: as a statement about two fields; the moment one is read as a routing result
#: it is false, because no route was run to produce it.
BAND = (
    "FIELD-TO-FIELD COMPARISON, ONE FIRE, NOT A ROUTING RESULT. This compares "
    "the hazard field the canonical router PLANS on (`haz_stack`, the "
    "leave-one-fire-out forward simulation) against the cumulative FIRMS-observed "
    "footprint (`obs_stack`) in the SAME committed npz and on the SAME 500 m "
    "grid. Six facts travel together or none may be quoted: (1) it produces NO "
    "margin and moves no committed number — 42, 91, 9 and 27 are untouched by it, "
    "and converting this gap into origins saved requires the re-grading run that "
    "has not been done; (2) the two stacks are compared at the nearest available "
    "times, not identical ones, and the quoted slice is the best-matched pair "
    "(27 minutes apart) with every other pair in the artifact; (3) `obs_stack` is "
    "a FIRMS-derived observation with its own detection floor "
    "(docs/detection_floor.md) and 500 m resampling, so it is an observation and "
    "NOT ground truth — a missed cell may be a cell FIRMS did not see; (4) the "
    "t=0 slice agrees perfectly by construction, because both stacks are seeded "
    "from the same detection, and is excluded from the headline for that reason. "
    "(5) The IoU here is NOT an independent confirmation of the ~0.40 footprint "
    "figure docs/MODEL_CARD.md reports: it recomputes the SAME quantity as "
    "spread_v2/forward_sim.py's drift_vs_observed — same p_cut, same "
    "nearest-observation matching, same estimator, same leave-target-out fit, "
    "same fire — differing only in the canvas (181x147 -> 181x156). The "
    "agreement is close to mechanical and is a consistency check on the canvas "
    "change, not corroboration. (6) The size agreement is a property of the "
    "quoted slice, not of the model, AND the other three slices are not readings "
    "of the model at all, because they are not time-matched: their time_gap_min "
    "are 153 / 207 / 285 against the quoted 27, and the slices at 180, 360 and "
    "540 minutes are all graded against the SAME observation (obs_time_min 333). "
    "So the area-ratio series runs over a CONSTANT observed denominator for three "
    "of its four terms and measures the matching, not forecast bias. Quote each "
    "ratio and each IoU with its own og_yeongdeok_t###min_time_gap_min or do not "
    "quote it. The earlier reading of that series as forecast behaviour is "
    "WITHDRAWN as WC-014 (docs/auto/withdrawn_claims.json); what stands is the "
    "PLACE disagreement at the well-matched pair, which a time gap cannot "
    "manufacture because a longer gap grows the intersection and the union "
    "together."
)

FORBIDDEN = [
    "the model is wrong about where the fire goes",
    "the forecast is useless",
    "예보가 쓸모없다",
    "the model gets the fire wrong",
    "IoU 0.39 is the routing margin",
    "the oracle gap is measured",
    "this measures what the model buys",
]

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("horizon_min", "headline.haz_time_min", "minutes",
     "the forward-simulation slice quoted: the one whose observation is nearest "
     "in time, excluding t=0"),
    ("obs_time_min", "headline.obs_time_min", "minutes",
     "the observation time it is compared against"),
    ("time_gap_min", "headline.time_gap_min", "minutes",
     "how far apart in time the two compared slices are — the residual "
     "unfairness of the comparison, reported rather than hidden"),
    ("predicted_cells", "headline.predicted_cells", "cells",
     "cells in the forward-simulated core (p >= 0.5) at the quoted slice"),
    ("observed_cells", "headline.observed_cells", "cells",
     "cells in the cumulative FIRMS-observed footprint at the matched time"),
    ("intersection_cells", "headline.intersection_cells", "cells",
     "cells that are in BOTH — predicted to burn and observed to burn"),
    ("false_alarm_cells", "headline.false_alarm_cells", "cells",
     "cells the simulation put in the fire core that the observation does not "
     "record burning at the matched time"),
    ("missed_cells", "headline.missed_cells", "cells",
     "cells the observation records burning that the simulation's core does not "
     "contain — a miss against FIRMS, which is not the same as a miss against "
     "the ground"),
    ("iou", "headline.iou", "ratio",
     "intersection over union of the two footprints at the quoted slice"),
    ("size_ratio", "headline.size_ratio", "ratio",
     "predicted cells / observed cells — how close the simulation gets to the "
     "right AREA, which is the half of the problem it does well"),
]


#: Every per-slice figure the document states in prose. CHARTER §3.3: a number
#: you cannot register, you do not write — and §4's IoU series and §7's
#: 285-minute gap are both prose numbers that live only in `slices`.
SLICE_FIELDS = [
    ("iou", "iou", "ratio",
     "intersection over union of the predicted core and the observed footprint"),
    ("time_gap_min", "time_gap_min", "minutes",
     "how far apart in time this pair of slices is"),
    ("size_ratio", "size_ratio", "ratio",
     "predicted cells / observed cells at this slice"),
    # WFG-215's registry half, added 2026-09-10. Without this key the observation
    # a slice was graded against is unwritable, and §4's table can print the gap
    # but not the thing the gap is a gap TO. That is not a hypothetical: the lap
    # that added the gap column omitted this column and told the reader the
    # registry forbade it, which was false — the HEADLINE obs_time_min has been
    # registered all along and the page already prints it twice. Its own
    # independent reviewer blocked on exactly that. Registering the per-slice
    # value removes the argument instead of restating it.
    ("obs_time_min", "obs_time_min", "minutes",
     "the observation time this slice was graded against — THREE of the five "
     "slices share one observation, which is why this key exists per slice and "
     "not once"),
]


def slice_figures(art: dict) -> list[tuple[str, str, str, str]]:
    """One key per per-slice quantity the prose quotes, named by hazard time."""
    out = []
    for i, row in enumerate(art["slices"]):
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
            # The registrar READS the artifact; the measurement script is what
            # produces it, so the regeneration command names that script (see
            # scripts/build_artifact_manifest.py, which reads this clause).
            "derivation": derivation + ". Regenerate: python scripts/measure_oracle_gap.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": "영덕 2025 · routing_demo_canonical.npz · 181x156 @ 500 m · p_cut 0.5",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_oracle_gap.py rebuilds the artifact "
                    "from the committed routing_demo_canonical.npz alone, with "
                    "no DEM, no network access and no fitted model — it reads "
                    "two arrays out of one file and counts cells."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "field_comparison",
            "notes": "docs/oracle_gap.md states the method, what it answers for "
                     "WFG-125 and what it does NOT show. It is a field-to-field "
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
            print("STALE oracle-gap registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} oracle-gap entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} oracle-gap entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
