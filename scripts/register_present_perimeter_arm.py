#!/usr/bin/env python
"""Register the present-perimeter arm's numbers in docs/NUMBERS.json (WFG-114).

The arm is produced by ``scripts/run_present_perimeter_arm.py`` into
``data/processed/present_perimeter_arm_uiseong_andong_2025.json``. Every figure
this project writes in prose has to re-derive from a committed artifact through
``scripts/verify_numbers.py``, so each of these keys carries a ``json_path``
check straight into that file.

ADDITIVE ON PURPOSE. ``scripts/build_numbers.py`` rebuilds the registry from its
own list and would drop the keys other registrars added; this script loads the
current file, replaces only the ``ppa_`` keys, and writes it back. (MEMO
2026-09-04: a lap that re-ran build_numbers.py wholesale lost 140 keys.)

    python scripts/register_present_perimeter_arm.py          # upsert + report
    python scripts/register_present_perimeter_arm.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/present_perimeter_arm_uiseong_andong_2025.json"
COMMITTED = "data/processed/real_roads_real_hazard_uiseong_andong_2025.json"
PREFIX = "ppa_"

#: The one caveat that has to travel with EVERY key here, because the whole
#: point of the row is that a number from this arm is easy to quote wrongly.
COMMON = (
    "의성·안동 2025, ONE region, ONE ignition, ONE weather realisation, 368 "
    "road-network origins at stride 18 (NOT households). All three planners are "
    "graded against the SAME simulated hazard field, so this ranks planners on a "
    "common synthetic ground truth and validates no spread model. The "
    "present-aware planner is handed the TRUE slice-0 perimeter, which a real "
    "office does not have, so it is an UPPER bound on present-perimeter routing."
)

#: key suffix -> (json_path into the artifact, unit, caveat, forbidden phrasings)
FIGURES = [
    ("n_origins", "n_origins_scanned", "origins",
     "The scan denominator, reproduced here from the snapshot graph and equal to "
     "the committed run's 368. " + COMMON, []),
    ("fa_only_n", "headline.fa_only_n", "origins",
     "The committed headline's 91 forecast-aware-only origins, RE-DERIVED on this "
     "machine node-for-node before the new arm ran (see "
     "committed_arm_reproduction.node_for_node_match). If that flag is ever false "
     "the ppa_ keys are not comparable to the committed ones. " + COMMON, []),
    ("recovered_1km", "headline.fa_only_recovered_by_present", "origins",
     "Of the 91, how many a present-perimeter + 1 km planner ALSO gets to a refuge "
     "safely. This is the fair opponent recovering most of the headline gap. " + COMMON,
     ["the forecast saves 91", "91 people the baseline would lose"]),
    ("forecast_only_1km", "headline.fa_only_still_forecast_only", "origins",
     "Of the 91, how many remain safe ONLY with the forecast at the author's 1 km "
     "buffer. NONE of them is an origin the present-aware arm walks into the fire "
     "— at 1 km that arm produces zero unsafe routes. They split into two "
     "DIFFERENT failures, registered separately as ppa_forecast_only_refused_1km "
     "(4, refused at the origin because it is inside the buffer) and "
     "ppa_forecast_only_walled_1km (8, free to leave but cut off from every "
     "refuge by the static mask). An earlier draft of this lap wrote 'all 12 sit "
     "inside their own buffer'; that was never measured and is false. " + COMMON,
     ["sends into the fire", "walks into the fire",
      "12개 모두 자기 자신의 1 km 완충 안에"]),
    ("forecast_only_refused_1km", "arms_by_buffer_m.1000.fa_only_missed_because.refused_to_start",
     "origins",
     "Of the 12: refused at the origin. The node itself is inside the 1 km buffer, "
     "so the planner will not let anyone leave; the advice a resident gets is 'do "
     "not move'. Measured with the router's OWN refusal predicate "
     "(field.table[origin, 0] >= p_cut), not re-derived. " + COMMON, []),
    ("forecast_only_walled_1km",
     "arms_by_buffer_m.1000.fa_only_missed_because.walled_off_from_every_refuge",
     "origins",
     "Of the 12: walled off. The node is OUTSIDE the buffer and free to leave, but "
     "the static 1 km mask separates it from every refuge within the budget, so "
     "there is nowhere to go. This is the larger half and the more interesting "
     "one: a fixed margin drawn around a present perimeter can sever a village "
     "from all of its shelters, and the forecast-aware planner routes these "
     "origins out because it knows which side will still be open. " + COMMON, []),
    ("refused_to_start_1km", "arms_by_buffer_m.1000.no_route_causes.refused_to_start",
     "origins",
     "All origins (not only the 91) the 1 km arm refuses to let leave. " + COMMON, []),
    ("walled_off_1km",
     "arms_by_buffer_m.1000.no_route_causes.walled_off_from_every_refuge", "origins",
     "All origins (not only the 91) the 1 km arm cuts off from every refuge. " + COMMON, []),
    ("safe_1km", "headline.present_safe", "origins",
     "Origins that reach a refuge safely under present perimeter + 1 km. " + COMMON, []),
    ("no_route_1km", "headline.present_no_route", "origins",
     "Origins the present + 1 km planner gives no route at all — almost all of them "
     "sit inside its own buffer, so the plan is 'do not move'. This is the cost of "
     "the margin, and it is why a larger buffer is not simply safer. " + COMMON, []),
    ("safe_naive", "ladder_safe_counts.naive", "origins",
     "The fire-blind control: shortest path to the nearest refuge, scored against "
     "the hazard. both_safe (263) PLUS fa_exceeds_budget (2), because that bucket "
     "is entered only when the naive route did NOT enter the hazard and the "
     "forecast-aware one failed to reach — so those two are naive successes. "
     "Reporting 263 here would understate the opponent by 2, in this project's own "
     "favour. ⚠ The naive router carries no time budget at all, so this row "
     "answers a slightly easier question than the budgeted rows. " + COMMON, []),
    ("safe_forecast", "ladder_safe_counts.forecast_aware", "origins",
     "The forecast-aware arm, from the committed artifact (both_safe + "
     "naive_into_FA_safe). " + COMMON, []),
    ("safe_present_500m", "ladder_safe_counts.present_500m", "origins",
     "The BEST present-aware setting found in the sweep, and the strongest form of "
     "the opponent: 349 of 368, five short of the forecast-aware arm. It is not the "
     "author's named 1 km and it is reported because the sweep found it. It buys "
     "that mobility with 5 unsafe routes, which 1 km does not have. " + COMMON, []),
    ("recovered_500m", "arms_by_buffer_m.500.fa_only_recovered_by_present", "origins",
     "At the sweep's best buffer the present-aware arm recovers 90 of the 91. " + COMMON, []),
    ("final_core_covered_1km", "geometry_by_buffer_m.1000.final_core_fraction_covered", "fraction",
     "WHY the opponent nearly ties: the slice-0 perimeter dilated by 1 km already "
     "contains 93.9 % of the cells that are burning at the 720-minute horizon. On "
     "THIS fire the envelope grows by less than the margin, so a static buffer is a "
     "near-substitute for the forecast. A faster fire would not have this property, "
     "and that is a prediction this repository has not tested. " + COMMON, []),
]


#: Every row of the sweep tables in docs/present_perimeter_arm.md, generated
#: rather than typed. CHARTER §3 rule 3 is "a number you cannot register, you do
#: not write", and the sweep is the evidence that the buffer was not chosen, so
#: it has to be gated like the headline is. The lap's reviewer counted ~20 such
#: figures in prose with no key; these are them.
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


EXTRA_FIGURES = [
    ("gap_1km", "gaps.forecast_minus_present_1km", "origins",
     "The forecast-aware arm minus the present + 1 km arm, 354 - 327. The most "
     "quotable number in the doc's §5 and in NH-031's title, so it gets a key. "
     "⚠ An UPPER bound: the opponent never re-plans and the forecast arm is graded "
     "on the field it was shown. " + COMMON, []),
    ("gap_best", "gaps.forecast_minus_present_best", "origins",
     "The forecast-aware arm minus the BEST present-aware arm in the sweep, "
     "354 - 349. The number least favourable to this project, and the honest one "
     "to lead with. Same upper-bound caveat as ppa_gap_1km. " + COMMON, []),
    ("mask_1km_never_burns_frac",
     "mask_1km_vs_what_actually_burns.fraction_of_mask_that_never_burns", "fraction",
     "Of the 203 cells the 1 km arm refuses, the fraction that NEVER reach p_cut at "
     "any slice: 80 of 203. The 1 km margin is mostly margin over ground that does "
     "not burn, which is why 'the forecast knows which side stays open' is NOT the "
     "explanation for the walled-off origins. " + COMMON, []),
    ("walled_escape_n_analysed",
     "arms_by_buffer_m.1000.walled_off_escape_analysis.n_walled_off_with_a_forecast_route",
     "origins",
     "Of the 25 origins the 1 km arm walls off, how many the forecast-aware arm "
     "does route out (the rest have no forecast-aware route either). " + COMMON, []),
    ("walled_escape_through_burning",
     "arms_by_buffer_m.1000.walled_off_escape_analysis."
     "n_whose_forecast_route_crosses_ground_that_does_burn", "origins",
     "Of those, how many escape across cells inside the refused mask that DO reach "
     "p_cut later — the only ones where knowing the TIMING is doing the work. It is "
     "1. This is the measurement that refuted this lap's own first explanation of "
     "the walled-off origins; see docs/present_perimeter_arm.md §3. " + COMMON,
     ["knows which side stays open", "어느 쪽이 계속 열려 있을지 알기 때문에"]),
    ("walled_escape_through_never_burning",
     "arms_by_buffer_m.1000.walled_off_escape_analysis."
     "n_whose_forecast_route_only_crosses_ground_that_never_burns", "origins",
     "Of those, how many escape across ground that never burns at all, so no "
     "forecast is needed to know it is safe. It is 10 of 11. The finding is that "
     "the 1 km buffer was TOO WIDE, not that the forecast was clever. " + COMMON, []),
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


FIGURES = FIGURES + EXTRA_FIGURES + sweep_figures()


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
            "derivation": (
                "scripts/run_present_perimeter_arm.py — the committed 의성·안동 hazard "
                "field, the snapshot walk graph and DEM, the same 368 origins, "
                "refuges, p_cut 0.5, 600-minute budget and 10-minute step as "
                f"{COMMITTED}. Only what the planner is allowed to know differs."),
            "config_hash": doc_hash,
            "config_hash_at_production": art.get("config_hash"),
            "git_commit": head,
            "sample": "368 road-network origins, 의성·안동 2025",
            "caveat": caveat,
            "forbidden_phrasings": forbidden,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": ("re-run scripts/run_present_perimeter_arm.py; it needs only "
                             "data/snapshots/ and data/processed/, both committed, and it "
                             "re-derives the committed 91 before it reports anything new. "
                             "Two independent runs on 2026-09-05 gave identical counts."),
                "blocked_by": None,
            },
            "provenance": "pipeline",
            "arm": "present_perimeter",
            "notes": "WFG-114 / NH-027 option A. Documented in docs/present_perimeter_arm.md.",
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
            print("STALE present-perimeter registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} present-perimeter entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"upserted {len(new)} present-perimeter entries ({len(stale)} new or changed); "
          f"registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
