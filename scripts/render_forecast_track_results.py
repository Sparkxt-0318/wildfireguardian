#!/usr/bin/env python
"""Render docs/forecast_track.md §4 from the F1 artifact. Never from retyped numbers.

Every number in §4 comes out of data/processed/forecast_track/forecast_track_f1.json, so
the page cannot drift from the run that produced it, and a reader can re-derive any figure
by opening the artifact. Re-runnable: it replaces §4 wholesale each time.

    python scripts/render_forecast_track_results.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ART = REPO / "data/processed/forecast_track/forecast_track_f1.json"
DOC = REPO / "docs/forecast_track.md"
START, END = "## 4. Results", "## 5. What could not run"
BUCKETS = ("both_safe", "naive_into_FA_safe", "no_safe_route", "other")
CLASSES = ("admissible_all", "indeterminate", "inadmissible_all", "not_reached")


def row(label, d, keys):
    return "| " + label + " | " + " | ".join(f"{d.get(k, 0):,}" for k in keys) + " |"


def main() -> int:
    if not ART.exists():
        print(f"STOP: {ART.relative_to(REPO)} is missing — run F1 first.", file=sys.stderr)
        return 2
    a = json.loads(ART.read_text(encoding="utf-8"))
    f, o, b = a["field"], a["origins_458"], a["buildings"]
    fw = f["frozen_weather"]
    cells = f["cells_ge_0.5_per_slice"]

    L = [START, "",
         f"_Rendered from `{ART.relative_to(REPO)}` by `scripts/render_forecast_track_results.py`; "
         f"run {a['generated_utc']} at `{a['git_commit'][:7]}`. Entrant **{a.get('entrant', 'F1')}**, "
         f"{a['track']} track. Nothing here is registered in `docs/NUMBERS.json` and nothing is on "
         "a judge surface._", ""]

    L += ["### 4.1 The field", "",
          f"T0 **{fw['t0']}**; frozen sample **{fw['sample_time']}** (index {fw['sample_index']}), "
          f"the rule being {fw['rule']}. Held values: wind "
          f"{fw['values']['wind_speed_ms']:.2f} m/s toward {fw['values']['wind_toward_deg']:.0f}°, "
          f"VPD {fw['values']['vpd_kpa']:.3f} kPa, RH {fw['values']['rh_pct']:.1f} %.", "",
          "| core cells p ≥ 0.5 | " + " | ".join(f"slice {i}" for i in range(len(cells["f1_frozen"]))) + " |",
          "|---|" + "---|" * len(cells["f1_frozen"]),
          "| **F1 frozen** | " + " | ".join(f"{c:,}" for c in cells["f1_frozen"]) + " |",
          "| leak-free (E3, hindcast) | " + " | ".join(f"{c:,}" for c in cells["leakfree"]) + " |",
          "| canonical (hindcast) | " + " | ".join(f"{c:,}" for c in cells["canonical"]) + " |", ""]

    shared = [i for i in range(len(cells["f1_frozen"]))
              if cells["f1_frozen"][i] == cells["leakfree"][i]]
    if shared:
        L += [f"⚠ **F1 and E3 agree exactly at slice(s) {', '.join(map(str, shared))}, and that is "
              "PARTLY BY CONSTRUCTION rather than a finding.** `forward_simulate`'s first step is "
              "evaluated at T0 itself, and the frozen series holds the T0 values, so the first "
              "advance uses the same weather in both fields. Any agreement in the early slices is "
              "therefore guaranteed, not discovered; only the later slices, where the fields "
              "genuinely diverge, carry information about what the forecast was worth.", ""]

    L += ["### 4.2 The 458 canonical origins", "",
          "| field | " + " | ".join(BUCKETS) + " |", "|---|" + "---|" * len(BUCKETS),
          row("canonical (hindcast)", o["partition_canonical"], BUCKETS),
          row("leak-free E3 (hindcast)", o["partition_leakfree"], BUCKETS),
          row("**F1 frozen (forecast track)**", o["partition_f1_frozen"], BUCKETS), "",
          "Graded on the **observation** (`docs/regrade_three_way.md`, *m* = 0), forecast-aware arm:", "",
          "| field | " + " | ".join(CLASSES) + " |", "|---|" + "---|" * len(CLASSES),
          row("canonical", o["observed_canonical"]["forecast_aware"], CLASSES),
          row("leak-free E3", o["observed_leakfree"]["forecast_aware"], CLASSES),
          row("**F1 frozen**", o["observed_f1_frozen"]["forecast_aware"], CLASSES), ""]

    L += ["### 4.3 The 주건물 population", "",
          f"{b['n_routable']:,} buildings on {b['n_nodes']:,} walk-network nodes "
          f"(canonical routable set, so the rows are paired).", "",
          "| field | " + " | ".join(BUCKETS) + " |", "|---|" + "---|" * len(BUCKETS),
          row("canonical (hindcast)", b["partition_canonical"], BUCKETS),
          row("leak-free E3 (hindcast)", b["partition_leakfree"], BUCKETS),
          row("**F1 frozen (forecast track)**", b["partition_f1_frozen"], BUCKETS), ""]

    lsd = b.get("last_safe_departure_5h_rule")
    if lsd:
        k = ("never", "closes_before_5h", "closes_after_5h", "censored")
        L += ["### 4.4 Last safe departure, the 5-hour rule", "", f"_Cuts: {lsd['cuts']}._", "",
              "| field | " + " | ".join(k) + " |", "|---|" + "---|" * len(k),
              row("canonical", lsd["canonical"], k), row("leak-free E3", lsd["leakfree"], k),
              row("**F1 frozen**", lsd["f1_frozen"], k), ""]

    nh = a.get("nh057_four_way_split_f1") or {}
    if nh.get("ran"):
        c = nh["four_way_counts"]
        L += ["### 4.5 The NH-057 four-way rescue split, on the F1 field", "",
              f"{nh['n_origins']:,} sampled walk-network origins (not households; walk timing "
              "flat — every caveat in `docs/rescue_routing_real_hazard.md` §4 applies).", "",
              "| bucket | count |", "|---|---:|"] + \
             [f"| {kk} | {vv:,} |" for kk, vv in c.items()] + [""]
    elif nh:
        L += ["### 4.5 The NH-057 four-way rescue split", "",
              f"⚠ **Did not run:** `{nh.get('error', 'unknown')}`. Every section above was written "
              "before this stage and is unaffected.", ""]

    L += ["### 4.6 What these rows do and do not say", "",
          "- **F1 is a floor, not an estimate of what a forecast buys** (§3). It assumes no "
          "forecast at all — the weather at ignition held flat for twelve hours.",
          "- The comparison is **one fire, one ignition, one start time**. Nothing here is "
          "evidence about another fire, region or country.",
          "- The observed grading is the row that does not depend on which field planned the "
          "route, which is why §2 step 3 makes it the number to carry forward.", ""]

    t = DOC.read_text(encoding="utf-8")
    i, j = t.index(START), t.index(END)
    DOC.write_text(t[:i] + "\n".join(L) + "\n" + t[j:], encoding="utf-8")
    print(f"rendered §4 of {DOC.relative_to(REPO)} from {ART.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
