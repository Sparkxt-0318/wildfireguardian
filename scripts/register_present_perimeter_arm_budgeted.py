#!/usr/bin/env python
"""Register the BUDGET-CAPPED present-perimeter arm in docs/NUMBERS.json (WFG-114, NH-032 C).

The arm is produced by ``scripts/run_present_perimeter_arm_budgeted.py`` into
``data/processed/present_perimeter_arm_budgeted_uiseong_andong_2025.json``.
Every figure this project writes in prose has to re-derive from a committed
artifact through ``scripts/verify_numbers.py``, so each of these keys carries a
``json_path`` check straight into that file.

WHY A SECOND REGISTRAR AND A SECOND PREFIX. The pruned-graph build of the same
row is registered under ``pp_uiseong_*`` by ``scripts/register_present_perimeter.py``
and those values are committed; CHARTER §3 rule 2 says a registered value is
added to, never edited. The author chose the budget-capped build as the fair
opponent the project states (NH-032 option C, 2026-09-12), so it gets its own
prefix, ``ppb_``, and the two builds sit side by side in the registry.

ADDITIVE ON PURPOSE. ``scripts/build_numbers.py`` rebuilds the registry from its
own list and would drop the keys other registrars added; this script loads the
current file, replaces only the ``ppb_`` keys, and writes it back. (MEMO
2026-09-04: a lap that re-ran build_numbers.py wholesale lost 140 keys.)

    python scripts/register_present_perimeter_arm_budgeted.py          # upsert + report
    python scripts/register_present_perimeter_arm_budgeted.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/present_perimeter_arm_budgeted_uiseong_andong_2025.json"
COMMITTED = "data/processed/real_roads_real_hazard_uiseong_andong_2025.json"
PREFIX = "ppb_"
RUNNER = "scripts/run_present_perimeter_arm_budgeted.py"

#: The one caveat that has to travel with EVERY key here, because the whole
#: point of the row is that a number from this arm is easy to quote wrongly.
COMMON = (
    "BUDGET-CAPPED build of the fair opponent (NH-032 option C, author 2026-09-12): "
    "the SAME time-expanded router as the headline, run against a frozen binary "
    "mask (slice-0 perimeter dilated by the buffer), capped at the 600-minute "
    "budget, refusing departure from inside the buffer, and never re-planning. "
    "의성·안동 2025, ONE region, ONE ignition, ONE weather realisation, 368 "
    "road-network origins at stride 18 (NOT households). All three planners are "
    "graded against the SAME simulated hazard field, so this ranks planners on a "
    "common synthetic ground truth and validates no spread model. The "
    "present-aware planner is handed the TRUE slice-0 perimeter, which a real "
    "office does not have, so it is an UPPER bound on present-perimeter routing. "
    "⚠ The forecast-aware arm plans on the very field it is graded on, so it "
    "carries NO forecast error: every margin here is what a PERFECT forecast buys. "
    "⚠ The sibling pruned-graph build (pp_uiseong_* keys, no time budget, no "
    "refusal) reads 9 at 1 km; the two builds are different opponents, not a "
    "disagreement about one, and the pruned-graph keys are not superseded. "
    "⚠ Any figure at the sweep's BEST width is a post-hoc maximum over the six "
    "widths measured (WFG-201) and can only fall as the grid is refined; 750 / "
    "1250 / 1500 m have NOT been run for this build."
)

FORBIDDEN_COMMON = [
    "the forecast is unnecessary",
    "예보는 필요 없다",
    "예보가 불필요",
    "the forecast adds nothing",
    "1 km is the optimal buffer",
    "1 km가 최적",
]

#: key suffix -> (json_path into the artifact, unit, caveat, forbidden phrasings)
FIGURES = [
    ("n_origins", "n_origins_scanned", "origins",
     "The scan denominator, reproduced here from the snapshot graph and equal to "
     "the committed run's 368. " + COMMON, []),
    ("fa_only_n", "headline.fa_only_n", "origins",
     "The committed headline's 91 forecast-aware-only origins, RE-DERIVED on this "
     "machine node-for-node before the new arm ran (see "
     "committed_arm_reproduction.node_for_node_match). If that flag is ever false "
     "the ppb_ keys are not comparable to the committed ones. " + COMMON, []),
    ("recovered_1km", "headline.fa_only_recovered_by_present", "origins",
     "Of the 91, how many a present-perimeter + 1 km planner ALSO gets to a refuge "
     "safely under this build. " + COMMON,
     ["the forecast saves 91", "91 people the baseline would lose"]),
    ("forecast_only_1km", "headline.fa_only_still_forecast_only", "origins",
     "Of the 91, how many remain safe ONLY with the forecast at the author's 1 km "
     "buffer under this build. NONE of them is an origin the present-aware arm "
     "walks into the fire — at 1 km this arm produces zero unsafe routes. They "
     "split into two DIFFERENT failures, registered separately as "
     "ppb_forecast_only_refused_1km (refused at the origin because it is inside "
     "the buffer) and ppb_forecast_only_walled_1km (free to leave but cut off "
     "from every refuge by the static mask). The parked lap's first draft wrote "
     "'all 12 sit inside their own buffer'; that was never measured and is false. "
     + COMMON,
     ["sends into the fire", "walks into the fire",
      "12개 모두 자기 자신의 1 km 완충 안에"]),
    ("forecast_only_refused_1km",
     "arms_by_buffer_m.1000.fa_only_missed_because.refused_to_start", "origins",
     "Of the still-forecast-only origins at 1 km: refused at the origin. The node "
     "itself is inside the 1 km buffer, so the planner will not let anyone leave; "
     "the advice a resident gets is 'do not move'. Measured with the router's OWN "
     "refusal predicate (field.table[origin, 0] >= p_cut), not re-derived. " + COMMON,
     []),
    ("forecast_only_walled_1km",
     "arms_by_buffer_m.1000.fa_only_missed_because.walled_off_from_every_refuge",
     "origins",
     "Of the still-forecast-only origins at 1 km: walled off. The node is OUTSIDE "
     "the buffer and free to leave, but the static 1 km mask separates it from "
     "every refuge within the budget, so there is nowhere to go. A fixed margin "
     "drawn around a present perimeter can sever a village from all of its "
     "shelters. ⚠ Do NOT explain this as 'the forecast knows which side stays "
     "open': ppb_walled_escape_through_never_burning says most of these escapes "
     "cross ground that never burns. " + COMMON,
     ["knows which side stays open", "어느 쪽이 계속 열려 있을지 알기 때문에"]),
    ("refused_to_start_1km", "arms_by_buffer_m.1000.no_route_causes.refused_to_start",
     "origins",
     "All origins (not only the 91) the 1 km arm refuses to let leave. " + COMMON, []),
    ("walled_off_1km",
     "arms_by_buffer_m.1000.no_route_causes.walled_off_from_every_refuge", "origins",
     "All origins (not only the 91) the 1 km arm cuts off from every refuge. " + COMMON,
     []),
    ("safe_1km", "headline.present_safe", "origins",
     "Origins that reach a refuge safely, inside the budget, under present "
     "perimeter + 1 km. " + COMMON, []),
    ("enters_1km", "headline.present_enters", "origins",
     "Origins whose present + 1 km route enters the true hazard. Zero at 1 km in "
     "this build. " + COMMON, []),
    ("no_route_1km", "headline.present_no_route", "origins",
     "Origins the present + 1 km planner gives no route at all (refused at the "
     "origin, or walled off from every refuge inside the budget). This is the "
     "cost of the margin, and it is why a larger buffer is not simply safer. "
     + COMMON, []),
    ("safe_naive", "ladder_safe_counts.naive", "origins",
     "The fire-blind control: shortest path to the nearest refuge, scored against "
     "the hazard. both_safe (263) PLUS fa_exceeds_budget (2), because that bucket "
     "is entered only when the naive route did NOT enter the hazard and the "
     "forecast-aware one failed to reach — so those two are naive successes. "
     "⚠ The naive router carries no time budget at all, so this row answers a "
     "slightly easier question than the budgeted rows; the pruned-graph build "
     "applies the budget to this column and reads 263 (pp_uiseong_safe_fire_blind). "
     "Both figures stand; they answer different questions. " + COMMON, []),
    ("safe_forecast", "ladder_safe_counts.forecast_aware", "origins",
     "The forecast-aware arm, from the committed artifact (both_safe + "
     "naive_into_FA_safe). " + COMMON, []),
    ("safe_present_best", "ladder_safe_counts.present_500m", "origins",
     "The BEST present-aware setting found in this build's sweep (500 m), and the "
     "strongest form of the opponent. It is not the author's named 1 km and it is "
     "reported because the sweep found it. It buys its mobility with unsafe routes "
     "(ppb_sweep_500m_enters), which 1 km does not have. ⚠ A post-hoc maximum "
     "over the six widths measured. " + COMMON, []),
    ("recovered_best", "arms_by_buffer_m.500.fa_only_recovered_by_present", "origins",
     "At the sweep's best buffer (500 m) how many of the 91 the present-aware arm "
     "recovers. " + COMMON, []),
    ("best_buffer_m", "best_buffer_m", "m",
     "The width at which this build's opponent scores highest, read off the sweep "
     "AFTER the run. ⚠ A post-hoc choice over six widths. " + COMMON, []),
    ("final_core_covered_1km", "geometry_by_buffer_m.1000.final_core_fraction_covered",
     "fraction",
     "WHY the opponent nearly ties: the slice-0 perimeter dilated by 1 km already "
     "contains this fraction of the cells that are burning at the 720-minute "
     "horizon. On THIS fire the envelope grows by less than the margin, so a "
     "static buffer is a near-substitute for the forecast. A faster fire would not "
     "have this property, and that is a prediction this repository has not tested. "
     + COMMON, []),
    ("gap_1km", "gaps.forecast_minus_present_1km", "origins",
     "THE MARGIN THE PROJECT STATES (NH-032 C): the forecast-aware arm minus the "
     "present + 1 km arm under this build, 354 - 327. ⚠ An UPPER bound: the "
     "opponent never re-plans and the forecast arm is graded on the field it was "
     "shown. ⚠ At the author's named 1 km, NOT at the sweep's best width; the "
     "best-width figure is ppb_gap_best. " + COMMON, []),
    ("gap_best", "gaps.forecast_minus_present_best", "origins",
     "The forecast-aware arm minus the BEST present-aware arm in this build's "
     "sweep (500 m), 354 - 349. The number least favourable to this project. "
     "⚠ A post-hoc maximum over six widths (WFG-201), non-increasing under "
     "refinement. Same upper-bound caveat as ppb_gap_1km. " + COMMON, []),
    ("mask_1km_never_burns_frac",
     "mask_1km_vs_what_actually_burns.fraction_of_mask_that_never_burns", "fraction",
     "Of the cells the 1 km arm refuses, the fraction that NEVER reach p_cut at "
     "any slice. The 1 km margin is mostly margin over ground that does not burn, "
     "which is why 'the forecast knows which side stays open' is NOT the "
     "explanation for the walled-off origins. " + COMMON, []),
    ("mask_1km_cells", "mask_1km_vs_what_actually_burns.mask_cells", "cells",
     "Cells inside the 1 km mask. " + COMMON, []),
    ("mask_1km_cells_never_burn",
     "mask_1km_vs_what_actually_burns.mask_cells_that_never_burn", "cells",
     "Cells inside the 1 km mask that never reach p_cut at any slice. " + COMMON, []),
    ("walled_escape_n_analysed",
     "arms_by_buffer_m.1000.walled_off_escape_analysis.n_walled_off_with_a_forecast_route",
     "origins",
     "Of the origins the 1 km arm walls off, how many the forecast-aware arm "
     "does route out (the rest have no forecast-aware route either). " + COMMON, []),
    ("walled_escape_through_burning",
     "arms_by_buffer_m.1000.walled_off_escape_analysis."
     "n_whose_forecast_route_crosses_ground_that_does_burn", "origins",
     "Of those, how many escape across cells inside the refused mask that DO reach "
     "p_cut later — the only ones where knowing the TIMING is doing the work. This "
     "is the measurement that refuted the parked lap's own first explanation of "
     "the walled-off origins; see docs/present_perimeter_arm_budgeted.md §3. "
     + COMMON,
     ["knows which side stays open", "어느 쪽이 계속 열려 있을지 알기 때문에"]),
    ("walled_escape_through_never_burning",
     "arms_by_buffer_m.1000.walled_off_escape_analysis."
     "n_whose_forecast_route_only_crosses_ground_that_never_burns", "origins",
     "Of those, how many escape across ground that never burns at all, so no "
     "forecast is needed to know it is safe. The finding is that the 1 km buffer "
     "was TOO WIDE, not that the forecast was clever. " + COMMON, []),
]


#: Every row of the sweep tables in docs/present_perimeter_arm_budgeted.md,
#: generated rather than typed. CHARTER §3 rule 3 is "a number you cannot
#: register, you do not write", and the sweep is the evidence that the buffer
#: was not chosen, so it has to be gated like the headline is.
SWEEP_BUFFERS_M = (0, 500, 1000, 2000, 3000, 5000)
SWEEP_FIELDS = [
    ("safe", "counts.present_safe", "origins", "reaches a refuge safely"),
    ("enters", "counts.present_enters", "origins", "routes that enter the fire"),
    ("noroute", "counts.present_no_route", "origins", "given no route at all"),
    ("refused", "no_route_causes.refused_to_start", "origins",
     "refused at the origin (inside the buffer)"),
    ("walled", "no_route_causes.walled_off_from_every_refuge", "origins",
     "cut off from every refuge by the mask"),
    ("recovered", "fa_only_recovered_by_present", "origins",
     "of the 91 forecast-aware-only origins, also saved here"),
]


def sweep_figures():
    out = []
    for b in SWEEP_BUFFERS_M:
        for suffix, sub, unit, what in SWEEP_FIELDS:
            out.append((
                f"sweep_{b}m_{suffix}",
                f"arms_by_buffer_m.{b}.{sub}",
                unit,
                f"Buffer sweep row {b} m: {what}. The sweep exists so the headline "
                f"radius is read off a curve rather than chosen; ⚠ the fall in the "
                f"`recovered` column above 1 km is the OPPONENT breaking itself on "
                f"its own over-caution (no-route grows), NOT evidence for the "
                f"forecast. " + COMMON, []))
        out.append((
            f"sweep_{b}m_mask_km2", f"geometry_by_buffer_m.{b}.mask_area_km2", "km2",
            f"Buffer sweep row {b} m: area of the refused region. " + COMMON, []))
        out.append((
            f"sweep_{b}m_still_forecast_only",
            f"arms_by_buffer_m.{b}.fa_only_still_forecast_only", "origins",
            f"Buffer sweep row {b} m: of the 91, how many remain safe only with the "
            f"forecast. " + COMMON, []))
        out.append((
            f"sweep_{b}m_core_covered",
            f"geometry_by_buffer_m.{b}.final_core_fraction_covered", "fraction",
            f"Buffer sweep row {b} m: fraction of the cells burning at the "
            f"720-minute horizon that this buffer already contains. " + COMMON, []))
    return out


FIGURES = FIGURES + sweep_figures()


def dig(obj, path: str):
    """Identical semantics to scripts/verify_numbers.py:dig.

    An index is an index only when the node is a LIST. The keyed views in the
    artifact use string keys like "500", and a digit-sniffing dig would try to
    subscript a dict with an int and fail; worse, the two diggers would disagree
    about what a registered `json_path` means.
    """
    node = obj
    for part in path.split("."):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, jpath, unit, caveat, forbidden in FIGURES:
        out[PREFIX + suffix] = {
            "value": dig(art, jpath),
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": jpath,
            # ⚠ The trailing `Regenerate:` clause is read by
            # scripts/build_artifact_manifest.py and OVERRIDES its inference;
            # the registrar READS the artifact, the runner is what produces it.
            "derivation": (
                f"{RUNNER} — the committed 의성·안동 hazard field, the snapshot walk "
                "graph and DEM, the same 368 origins, refuges, p_cut 0.5, 600-minute "
                f"budget and 10-minute step as {COMMITTED}. Only what the planner is "
                "allowed to know differs. Regenerate: python " + RUNNER),
            "config_hash": doc_hash,
            "config_hash_at_production": art.get("config_hash"),
            "git_commit": head,
            "sample": "368 road-network origins, 의성·안동 2025",
            "caveat": caveat,
            "forbidden_phrasings": FORBIDDEN_COMMON + list(forbidden),
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (f"re-run {RUNNER}; it needs only data/snapshots/ and "
                             "data/processed/, both committed, and it re-derives the "
                             "committed 91 before it reports anything new. The parked "
                             "branch auto/red/20260905T2248Z produced the same counts "
                             "on 2026-09-05 from the same code."),
                "blocked_by": None,
            },
            "provenance": "pipeline",
            "arm": "present_perimeter_budgeted",
            "notes": ("WFG-114 / NH-027 option A / NH-032 option C. Documented in "
                      "docs/present_perimeter_arm_budgeted.md."),
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": ARTIFACT, "json_path": jpath}}},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    art = json.loads((REPO / ARTIFACT).read_text(encoding="utf-8"))
    if not art["committed_arm_reproduction"]["node_for_node_match"]:
        print("REFUSING: the run did not reproduce the committed 91 node-for-node, "
              "so its numbers are not comparable to the committed headline.")
        return 2
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    new = build_entries(art, head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items()
             if k not in cur or cur[k]["value"] != e["value"]]
    if args.check:
        if stale:
            print("STALE budgeted present-perimeter registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} budgeted present-perimeter entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"upserted {len(new)} budgeted present-perimeter entries ({len(stale)} new or "
          f"changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
