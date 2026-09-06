#!/usr/bin/env python
"""Register the present-perimeter arm's figures in docs/NUMBERS.json (WFG-114).

The fair-opponent experiment (`scripts/run_present_perimeter_arm.py`) produces the
one set of numbers that qualifies the project's headline, so every one of them is
registered and re-derived by `scripts/verify_numbers.py` like any other number.

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads the
current file, replaces only the `pp_` keys, and writes it back.

    python scripts/register_present_perimeter.py          # upsert + report
    python scripts/register_present_perimeter.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/present_perimeter_arm_uiseong_andong_2025.json"
PREFIX = "pp_uiseong_"

#: The caveat every one of these keys carries. It is long because the result is
#: the kind that is quoted out of context: it both weakens and defends the
#: headline, and either half alone is a false statement about the experiment.
BAND = (
    "FAIR-OPPONENT ARM, ONE FIRE, CANONICAL (slope 60 m / DiGraph) TIMING. The "
    "opponent is the fire-blind objective on a network with every node within a "
    "fixed buffer of the slice-0 perimeter (p >= 0.5) refused — what an operator "
    "can do with no model at all. Four facts travel together or none of them may "
    "be quoted: (1) at a 1 km buffer the present-aware arm recovers 86 of the 91 "
    "origins that were safe only on the forecast-aware route, so the forecast's "
    "margin on this fire is 9 origins of 368 (fire-blind 263, present 345, forecast-aware 354), not 91; (2) 1 km is not a "
    "discovered constant but the best of five widths tried on ONE fire, and it "
    "sits on the crossing of two failure regimes — at 250 m and 500 m the arm "
    "walks 91 and 80 origins into the fire as it grows (non-monotonically: 1 km to 2 km puts more in, 3 to 5), at 2 km and 3 km it "
    "leaves 80 and 73 unable to finish inside the 600-minute budget; (3) an "
    "operator on the day cannot know which width they are on, and the "
    "forecast-aware arm reaches 354 with no width to choose; (4) the margin "
    "depends on a modelling convention by MORE than its own size — under the "
    "'strict' origin rule (an origin inside the buffer may not move within it) "
    "the same run gives 19 rather than 9, so the primary 'walk_out' rule is the "
    "one reported and both are in the artifact. "
    "⚠ The forecast-aware arm is scored on the SAME hazard field it plans on, so "
    "it carries NO forecast error here; 9 is the margin a PERFECT forecast buys "
    "over a present-perimeter policy, and the real-model margin is smaller by an "
    "amount this run does not measure. (5) All three columns are scored under ONE "
    "rule including the 600-minute budget; the committed classification does not "
    "budget the fire-blind route, and that unbudgeted figure is 265."
)

FORBIDDEN = [
    "the forecast is unnecessary",
    "예보는 필요 없다",
    "예보가 불필요",
    "the forecast adds nothing",
    "present-perimeter routing is equivalent to forecasting",
    "1 km is the optimal buffer",
    "1 km가 최적",
    "optimal buffer width",
    "the fair opponent matches the forecast",
]

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("forecast_only", "headline.forecast_only", "origins",
     "origins whose fire-blind route enters the predicted hazard and whose "
     "forecast-aware route reaches a refuge without entering it, on the "
     "committed CANONICAL (slope 60 m / DiGraph) arm reproduced by this run"),
    ("recovered_1km", "headline.recovered_by_present_perimeter", "origins",
     "of those, the ones that are ALSO safe when the fire-blind router is run "
     "on the network minus the slice-0 perimeter dilated by 1 km"),
    ("still_forecast_only_1km", "headline.still_forecast_only", "origins",
     "forecast-only origins the 1 km present-aware arm does not recover"),
    ("broken_1km", "headline.already_safe_broken_by_buffer", "origins",
     "origins the fire-blind control got to safety under the SAME budgeted rule "
     "that the 1 km buffer then costs. They do not all fail the same way: see "
     "failure_modes.already_safe_broken_by_buffer for the split between losing "
     "every route, being pushed into the fire, and arriving past the budget"),
    ("safe_fire_blind", "headline.safe_fire_blind", "origins",
     "origins whose fire-blind route reaches a refuge without entering the hazard"),
    ("safe_present_1km", "headline.safe_present_perimeter", "origins",
     "origins the present-perimeter + 1 km arm gets to a refuge safely and "
     "inside the 600-minute budget"),
    ("safe_forecast_aware", "headline.safe_forecast_aware", "origins",
     "origins the forecast-aware router gets to a refuge without entering the hazard"),
    ("forecast_margin_1km", "headline.forecast_margin_over_present", "origins",
     "safe_forecast_aware - safe_present_1km: what the forecast buys OVER the "
     "best present-aware buffer tried, on this fire"),
    ("max_detour_recovered_m", "cost.on_recovered_origins.max_detour_m", "m",
     "the largest paired detour over the recovered origins"),
    ("refuges_before_buffer", "perimeter.refuges_before", "refuge nodes",
     "refuge nodes on the walk graph before the buffer is applied"),
    ("refuges_after_1km", "perimeter.refuges_after", "refuge nodes",
     "refuge nodes surviving the 1 km buffer; a refuge inside the buffer is not "
     "a refuge and is dropped"),
    ("origins_inside_buffer_1km", "perimeter.origins_inside_buffer", "origins",
     "scanned origins standing inside the 1 km buffer — outside the fire at "
     "slice 0 but within a kilometre of it"),
    ("strict_rule_margin_1km", "origin_rule_comparison.strict.forecast_margin",
     "origins",
     "the forecast's margin under the STRICT origin rule, reported beside the "
     "primary walk_out margin because the convention is worth more than the "
     "margin itself"),
    ("strict_rule_safe_1km", "origin_rule_comparison.strict.safe_total", "origins",
     "origins the present-aware arm saves under the strict origin rule"),
    ("flat_arm_forecast_only", "flat_arm_crosswalk.flat_forecast_only", "origins",
     "the same bucket on the committed FLAT/DiGraph arm, quoted for the "
     "crosswalk; the canonical arm is this run's denominator"),
    ("canonical_ids_also_in_flat", "flat_arm_crosswalk.ids_in_both", "origins",
     "canonical forecast-only origins that are also forecast-only on the flat arm"),
    ("fire_blind_unbudgeted", "headline.safe_fire_blind_unbudgeted", "origins",
     "the committed classification's fire-blind safe count, which applies NO "
     "time budget; kept beside the budgeted 263 so the correction is visible"),
    ("fire_blind_late_past_budget", "headline.fire_blind_late_past_budget",
     "origins",
     "fire-blind routes that reach a refuge without entering the hazard but "
     "arrive after the 600-minute budget the other two columns enforce"),
    ("broken_1km_unreachable", "headline.broken_by_mode.unreachable", "origins",
     "of the origins the 1 km buffer costs, those that lose every route to a refuge"),
    ("broken_1km_enters_hazard", "headline.broken_by_mode.enters_hazard", "origins",
     "of the origins the 1 km buffer costs, those pushed onto a detour that "
     "walks into the fire"),
    ("broken_1km_over_budget", "headline.broken_by_mode.over_budget", "origins",
     "of the origins the 1 km buffer costs, those that arrive past the budget"),
    ("control_late_arrival_earliest_min", "headline.fire_blind_late_arrivals_min.0",
     "minutes",
     "arrival time of the earlier of the two fire-blind routes that miss the "
     "600-minute budget the other two columns enforce"),
    ("control_late_arrival_latest_min", "headline.fire_blind_late_arrivals_min.1",
     "minutes", "arrival time of the later of the two"),
    ("repro_id_buckets_graded", "reproduction_gate.n_id_buckets_graded", "buckets",
     "buckets of the committed canonical arm whose origin ids this run graded "
     "(the ones the committed artifact stores a list for)"),
    ("repro_ids_graded", "reproduction_gate.n_ids_graded", "origin ids",
     "origin ids graded against the committed canonical arm"),
    ("nodes_refused_1km", "perimeter.n_nodes_refused", "nodes",
     "walk-graph nodes inside the 1 km buffer, of 6,678"),
    ("mean_detour_recovered_m", "cost.on_recovered_origins.mean_detour_m", "m",
     "paired mean of (present-aware route length - fire-blind route length) "
     "over the 86 recovered origins"),
]

#: EVERY cell of the sensitivity table in `docs/present_perimeter_arm.md` §4, not
#: just the five the prose names. That table is the whole argument of the doc —
#: it is what turns "93 of 96" from a tuned number into a crossing between two
#: failure regimes — so all six counts at all five widths are registered rather
#: than left to the doc-vs-artifact test alone. CHARTER §3.3: a number you cannot
#: register, you do not write.
SWEEP_FIELDS = [
    ("recovered", "recovered_of_forecast_only", "origins",
     "forecast-only origins the present-aware arm also gets to safety"),
    ("broken", "already_safe_broken", "origins",
     "origins the fire-blind control already had safe that this buffer breaks"),
    ("safe", "safe_total", "origins",
     "origins the present-aware arm gets to a refuge safely and inside budget"),
    ("burns", "failed_enters_hazard", "origins",
     "origins whose present-aware route still stands on a cell at p >= 0.5 while "
     "it is at p >= 0.5 — the fire grows past the buffer"),
    ("unreachable", "failed_unreachable", "origins",
     "origins with no route to any refuge — safety bought by telling people "
     "there is no way out"),
    ("late", "failed_over_budget", "origins",
     "origins that reach a refuge safely but outside the 600-minute budget"),
]


def sweep_figures(art: dict) -> list[tuple[str, str, str, str]]:
    """One registry key per cell of the buffer band, named by width."""
    out = []
    for i, row in enumerate(art["buffer_sensitivity"]):
        w = row["buffer_m"]
        tag = f"w{int(w)}m"
        for suffix, field, unit, derivation in SWEEP_FIELDS:
            out.append((f"{tag}_{suffix}", f"buffer_sensitivity.{i}.{field}",
                        unit, f"{derivation} (buffer {w:.0f} m)"))
    return out


def _dig(doc: dict, path: str):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, path, unit, derivation in FIGURES + sweep_figures(art):
        out[PREFIX + suffix] = {
            "value": _dig(art, path),
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": path,
            # ⚠ The trailing `Regenerate:` clause is read by
            # scripts/build_artifact_manifest.py and OVERRIDES its inference,
            # which otherwise names this registrar as the producer: the full
            # artifact path appears as a literal here and only as an f-string in
            # the runner, so the basename heuristic picks the wrong script. The
            # registrar READS the artifact and writes docs/NUMBERS.json; the
            # runner is what produces it. A wrong regeneration command looks like
            # provenance and is not (that manifest's own docstring).
            "derivation": derivation + ". Regenerate: python scripts/run_present_perimeter_arm.py",
            "config_hash": doc_hash,
            "config_hash_at_production": art.get("config_hash"),
            "git_commit": head,
            "sample": "의성·안동 2025 · 368곳 주사 · slope 60 m / DiGraph (canonical)",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/run_present_perimeter_arm.py rebuilds the "
                    "artifact from the hash-verified snapshot walk graph, the "
                    "committed hazard npz and the committed refuge snapshot, "
                    "with no DEM and no network access. It refuses to write "
                    "unless it first reproduces the committed canonical arm "
                    "of real_roads_real_hazard_uiseong_andong_2025.json exactly "
                    "(--verify-only runs that check alone)."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "present_perimeter",
            "notes": "docs/present_perimeter_arm.md states the method, the "
                     "buffer band and what the arm does not show. WFG-114, "
                     "author decision NH-027 option A.",
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
            print("STALE present-perimeter registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} present-perimeter entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} present-perimeter entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
