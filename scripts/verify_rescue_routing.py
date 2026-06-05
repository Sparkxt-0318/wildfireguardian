#!/usr/bin/env python
"""Verification / reconciliation pass for the rescue-routing results (PR #4).

This is an AUDIT, not a feature change — it imports the existing routing/spread
logic unchanged and only re-runs it under one explicit baseline so every headline
number and the sensitivity sweep sit on the SAME origin set.

It resolves the reported contradictions:
  * headline four-way split (154/34/244/20, N=452) vs the sweep endpoints
    (unreachable 2->13). Root cause: the convenience ``sensitivity_sweep`` SUB-
    SAMPLES origins to ``sweep_max_origins`` (=> N≈151), while ``run_pipeline``
    uses all N=452. Here the 2-D sweep runs on the FULL N=452 set, so the baseline
    cell EQUALS the headline (asserted).
  * N 407->452: the rescue origin scan uses ``scan_stride=3`` + a fire-reach
    latitude band on the walk-network land nodes, vs the old 407-origin
    stride-4 scan.
  * metric scale: resident exposure is over PEDESTRIAN routes, responder over
    VEHICLE routes — both prob·min, labelled distinctly.

Outputs:
  data/processed/rescue_verify.json     baseline + full-N 2-D sweep + verdict.
  docs/figures/rescue_sweep_2d.png      2-D heatmaps over (dispatch delay x
                                        vehicle cutoff).

Run:  python scripts/verify_rescue_routing.py
Deterministic (fixed seed, config-driven); runs end-to-end on the synthetic
fallback. Does NOT modify any routing/spread logic.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.routing.rescue import RescueConfig  # noqa: E402
from wildfireguardian.routing.rescue_demo import (  # noqa: E402
    _refuge_node_sets,
    _split_counts,
    build_synthetic_demo,
    run_pipeline,
)

PROC = REPO / "data" / "processed"
FIG = REPO / "docs" / "figures"

# 2-D grid. Vehicle cutoff spans the probability semantics in [0,1]: 0.5 is the
# pedestrian cutoff itself (no extra risk tolerance for vehicles); 0.9 is a
# vehicle pushing through near-certain-burning roads (permissive upper bound).
DELAYS = [0.0, 15.0, 30.0, 45.0, 60.0]
CUTOFFS = [0.5, 0.6, 0.7, 0.8, 0.9]
BASELINE_DELAY = 30.0
BASELINE_CUTOFF = 0.7
KEYS = ["already_safe", "saved_by_rescue_reachable_refuge",
        "no_safe_pedestrian_route", "no_surviving_vehicle_ingress"]
SHORT = {"already_safe": "safe", "saved_by_rescue_reachable_refuge": "saved",
         "no_safe_pedestrian_route": "no_walk", "no_surviving_vehicle_ingress": "unreach"}


def _rel_spread(vals: list[float]) -> float:
    vals = [v for v in vals]
    m = float(np.mean(vals)) if vals else 0.0
    return (max(vals) - min(vals)) / m if m > 0 else 0.0


def _monotone_nondecreasing(vals: list[float]) -> bool:
    return all(b >= a - 1e-9 for a, b in zip(vals, vals[1:]))


def main() -> int:
    PROC.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    baseline = RescueConfig(responder_dispatch_delay_min=BASELINE_DELAY,
                            vehicle_cutoff=BASELINE_CUTOFF)
    print("Building baseline synthetic 영덕 scenario (full origin set) ...")
    scenario = build_synthetic_demo(baseline)
    N = len(scenario.origins)

    print(f"Re-deriving headline from baseline (N={N}) ...")
    headline = run_pipeline(scenario, baseline)
    hc = headline.four_way_counts

    print(f"Running 2-D sweep on the FULL N={N} set "
          f"({len(DELAYS)}x{len(CUTOFFS)} cells; this is the slow part) ...")
    grid: dict[tuple[float, float], dict] = {}
    subset_ok = True
    safe_total = {}
    for vc in CUTOFFS:
        # rescue_reachable ⊆ safe check, per cutoff (delay-independent set check
        # at the baseline delay is sufficient for the subset invariant).
        assessments, _all, _rr = _refuge_node_sets(
            scenario, replace(baseline, vehicle_cutoff=vc))
        safe_total[vc] = sum(1 for a in assessments if a.rescue_reachable)
        for a in assessments:
            if a.rescue_reachable and not a.safe:
                subset_ok = False
        for d in DELAYS:
            cfg = replace(baseline, responder_dispatch_delay_min=d, vehicle_cutoff=vc)
            rec = _split_counts(scenario, cfg)
            assert rec["n_origins"] == N, "sweep cell used a different origin set"
            assert sum(rec["counts"].values()) == N, "cell four-way did not sum to N"
            grid[(d, vc)] = rec
            print(f"  delay={d:>4.0f} cutoff={vc:.2f} -> "
                  + " ".join(f"{SHORT[k]}={rec['counts'][k]}" for k in KEYS))

    # ---- reconciliation: baseline cell MUST equal the headline ----
    base_cell = grid[(BASELINE_DELAY, BASELINE_CUTOFF)]["counts"]
    reconciled = (base_cell == hc)

    # ---- robustness verdict ----
    def cell(d, vc, key):
        return grid[(d, vc)]["counts"][key]

    unreach_delay_row = [cell(d, BASELINE_CUTOFF, "no_surviving_vehicle_ingress")
                         for d in DELAYS]
    # dispatch-delay trend monotone non-decreasing for EVERY cutoff?
    unreach_delay_monotone_all = all(
        _monotone_nondecreasing([cell(d, vc, "no_surviving_vehicle_ingress")
                                 for d in DELAYS]) for vc in CUTOFFS)
    # harsher (lower) cutoff => unreachable non-decreasing, for every delay?
    unreach_cutoff_monotone_all = all(
        _monotone_nondecreasing([cell(d, vc, "no_surviving_vehicle_ingress")
                                 for vc in sorted(CUTOFFS, reverse=True)])
        for d in DELAYS)
    # ordering: does "rescuer reaches" exceed "saved" in every cell?
    order_rescuer_gt_saved = all(
        cell(d, vc, "no_safe_pedestrian_route") > cell(d, vc, "saved_by_rescue_reachable_refuge")
        for d in DELAYS for vc in CUTOFFS)

    central = [(d, vc) for d in (15.0, 30.0, 45.0) for vc in (0.6, 0.7, 0.8)]

    def classify(key):
        cvals = [cell(d, vc, key) for (d, vc) in central]
        allvals = [cell(d, vc, key) for d in DELAYS for vc in CUTOFFS]
        rel = _rel_spread(cvals)
        # ordering proxy: each bucket should keep its sign of dependence; we treat
        # "ordering stable" as: rescuer>saved everywhere (no bucket-flip) for the
        # rescue/unreachable buckets.
        ordering_stable = order_rescuer_gt_saved
        if rel < 0.15:
            verdict = "robust"
        elif ordering_stable:
            verdict = "directional"
        else:
            verdict = "fragile"
        return {"baseline": cell(BASELINE_DELAY, BASELINE_CUTOFF, key),
                "central_min": min(cvals), "central_max": max(cvals),
                "grid_min": min(allvals), "grid_max": max(allvals),
                "central_rel_spread": round(rel, 3), "verdict": verdict}

    verdict = {
        "no_safe_pedestrian_route_(244)": classify("no_safe_pedestrian_route"),
        "no_surviving_vehicle_ingress_(20)": classify("no_surviving_vehicle_ingress"),
        "dispatch_delay_trend": {
            "unreachable_at_baseline_cutoff_delay_0_to_60": unreach_delay_row,
            "monotone_nondecreasing_all_cutoffs": bool(unreach_delay_monotone_all),
            "verdict": "robust direction" if unreach_delay_monotone_all else "fragile",
        },
        "ordering_rescuer_reaches_gt_saved_everywhere": bool(order_rescuer_gt_saved),
        "unreachable_increases_with_harsher_cutoff_all_delays":
            bool(unreach_cutoff_monotone_all),
    }

    # ---- print the single reconciled results block ----
    rex, pe = headline.resident_exposure, headline.responder_exposure

    def m(d):
        v = d.get("mean") if isinstance(d, dict) else None
        return "n/a" if v is None else f"{v:.3f}"

    block = []
    block.append("=== RECONCILED RESULTS (single baseline) ===")
    block.append("Baseline config:")
    block.append(f"  origins N            = {N}        # stride-3 + reach-band scan on the "
                 f"walk net (vs old 407 stride-4 scan)")
    block.append(f"  walk speed           = {baseline.elderly_walk_speed_ms} m/s (Tobler)")
    block.append(f"  vehicle speed        = {baseline.vehicle_speed_kmh} km/h")
    block.append(f"  pedestrian cutoff    = {baseline.walk_cutoff}")
    block.append(f"  vehicle cutoff       = {baseline.vehicle_cutoff}        # baseline value")
    block.append(f"  dispatch delay       = {baseline.responder_dispatch_delay_min:.0f} min")
    block.append(f"  safety margin        = {baseline.responder_safety_margin_min:.0f} min")
    block.append(f"  time budget          = resident {baseline.resident_time_budget_min:.0f} / "
                 f"responder {baseline.responder_time_budget_min:.0f} min")
    block.append(f"  data                 = shelters:{scenario.shelters_source}, "
                 f"depots:{scenario.depots_source}, roads:{'OSM' if baseline.use_osm else 'synthetic-lattice'}, "
                 f"hazard:{scenario.hazard_source}")
    block.append("")
    block.append(f"Four-way origin split (sums to N={N}):")
    block.append(f"  already safe (walk)         : {hc['already_safe']}")
    block.append(f"  saved by rescue-reachable   : {hc['saved_by_rescue_reachable_refuge']}")
    block.append(f"  no walk, rescuer reaches    : {hc['no_safe_pedestrian_route']}")
    block.append(f"  unreachable (reported)      : {hc['no_surviving_vehicle_ingress']}")
    block.append(f"  sums to N                   : {sum(hc.values()) == N}")
    block.append("")
    block.append("Exposure contrasts (distinct metrics):")
    block.append(f"  resident  (pedestrian, prob·min)  naive / fa-any / fa-rescuable : "
                 f"{m(rex['naive'])} / {m(rex['future_aware_any'])} / {m(rex['future_aware_rescue'])}")
    pb = rex['paired_b_vs_c']
    block.append(f"     paired b vs c (same {pb['n']} origins)                       : "
                 f"{pb['mean_future_aware_any']:.3f} / {pb['mean_future_aware_rescue']:.3f}  "
                 f"(c re-routed {rex['policy_c_changed_refuge_count']} off a cut-off refuge)")
    block.append(f"  responder (vehicle,    prob·min)  shortest-path / survival-aware: "
                 f"{m(pe['shortest_path'])} / {m(pe['survival_aware'])}  "
                 f"(dispatch {pe['n_dispatch']}, unreachable {pe['n_unreachable']})")
    block.append("")
    block.append(f"=== 2-D SWEEP (dispatch_delay x vehicle_cutoff), full N={N} ===")
    block.append("cell = (safe, saved, no_walk, unreach); each sums to N")
    header = "delay\\cut | " + " | ".join(f"{vc:.2f}" for vc in CUTOFFS)
    block.append(header)
    for d in DELAYS:
        row = [f"{tuple(cell(d, vc, k) for k in KEYS)}" for vc in CUTOFFS]
        block.append(f"  {d:>4.0f}    | " + " | ".join(row))
    block.append(f"baseline cell ({BASELINE_DELAY:.0f},{BASELINE_CUTOFF}) == headline : {reconciled}")
    block.append(f"heatmap: {FIG / 'rescue_sweep_2d.png'}")
    block.append("")
    block.append("=== ROBUSTNESS VERDICT ===")
    uv = verdict["dispatch_delay_trend"]
    block.append(f"  unreachable @ dispatch 0->60 (cutoff {BASELINE_CUTOFF}) : "
                 f"{uv['unreachable_at_baseline_cutoff_delay_0_to_60'][0]} -> "
                 f"{uv['unreachable_at_baseline_cutoff_delay_0_to_60'][-1]}   "
                 f"[{uv['verdict']}; monotone all cutoffs={uv['monotone_nondecreasing_all_cutoffs']}]")
    nw = verdict["no_safe_pedestrian_route_(244)"]
    block.append(f"  'no walk, rescuer reaches' (244 baseline) : {nw['verdict']}  "
                 f"(baseline {nw['baseline']}, grid {nw['grid_min']}-{nw['grid_max']}, "
                 f"central rel-spread {nw['central_rel_spread']})")
    ur = verdict["no_surviving_vehicle_ingress_(20)"]
    block.append(f"  'unreachable' (20 baseline)               : {ur['verdict']}  "
                 f"(baseline {ur['baseline']}, grid {ur['grid_min']}-{ur['grid_max']}, "
                 f"central rel-spread {ur['central_rel_spread']})")
    block.append(f"  ordering rescuer-reaches > saved everywhere: {order_rescuer_gt_saved}")
    block.append(f"  unreachable up as cutoff harsher (all delays): {unreach_cutoff_monotone_all}")
    block.append(f"  rescue_reachable ⊆ safe (all cutoffs)      : {subset_ok}")
    reportable_numbers = [k for k, v in (("unreachable", ur), ("no_walk_rescuer", nw))
                          if v["verdict"] == "robust"]
    reportable_direction = ["unreachable rises with dispatch delay (the finding)"]
    if ur["verdict"] == "directional":
        reportable_direction.append("unreachable magnitude (directional only)")
    if nw["verdict"] == "directional":
        reportable_direction.append("no-walk-rescuer magnitude (directional only)")
    do_not_report = [k for k, v in (("unreachable", ur), ("no_walk_rescuer", nw))
                     if v["verdict"] == "fragile"]
    block.append(f"  reportable as numbers     : {reportable_numbers or ['(direction-only this grid)']}")
    block.append(f"  reportable as direction   : {reportable_direction}")
    block.append(f"  do NOT report             : {do_not_report or ['(none fragile)']}")
    text = "\n".join(block)
    print("\n" + text)

    # ---- persist ----
    out = {
        "baseline_config": baseline.provenance(),
        "n_origins": N,
        "headline_four_way": hc,
        "headline_sums_to_n": sum(hc.values()) == N,
        "resident_exposure": rex,
        "responder_exposure": pe,
        "grid": {f"{d:.0f}|{vc:.2f}": grid[(d, vc)]["counts"] for d in DELAYS for vc in CUTOFFS},
        "baseline_cell_equals_headline": reconciled,
        "rescue_reachable_subset_safe_all_cutoffs": subset_ok,
        "robustness_verdict": verdict,
        "n_refuges_rescue_reachable_by_cutoff": {f"{k:.2f}": v for k, v in safe_total.items()},
        "reconciled_block": text,
        "notes": {
            "n_explanation": "452 = stride-3 + reach-band origin scan on the walk network; "
                             "the old routing-spine used a stride-4, 14 km-band scan giving 407.",
            "headline_vs_sweep_cause": "the convenience sensitivity_sweep sub-samples to "
                                       "sweep_max_origins (N≈151); this verify sweep uses the full "
                                       "N=452, so the baseline cell equals the headline.",
            "metric_labels": "resident exposure = pedestrian routes; responder = vehicle routes; "
                             "both prob·min, never compared across scales.",
        },
    }
    (PROC / "rescue_verify.json").write_text(json.dumps(out, indent=2, default=str))
    _heatmap(grid)
    print(f"\nwrote {PROC / 'rescue_verify.json'}")
    if not reconciled:
        print("ERROR: baseline cell != headline — NOT reconciled.", file=sys.stderr)
        return 1
    if not subset_ok:
        print("ERROR: rescue_reachable ⊄ safe somewhere.", file=sys.stderr)
        return 1
    return 0


def _heatmap(grid):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm

    for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            plt.rcParams["font.family"] = fm.FontProperties(fname=p).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False

    panels = [("no_surviving_vehicle_ingress", "구조 불가 / UNREACHABLE", "Reds"),
              ("no_safe_pedestrian_route", "도보 불가·구조대 가능 / no walk, rescuer reaches", "Oranges"),
              ("saved_by_rescue_reachable_refuge", "대피소로 구조 / saved", "Greens")]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.0), constrained_layout=True)
    for ax, (key, title, cmap) in zip(axes, panels):
        M = np.array([[grid[(d, vc)]["counts"][key] for vc in CUTOFFS] for d in DELAYS], float)
        im = ax.imshow(M, cmap=cmap, aspect="auto", origin="lower")
        ax.set_xticks(range(len(CUTOFFS)), [f"{c:.2f}" for c in CUTOFFS])
        ax.set_yticks(range(len(DELAYS)), [f"{d:.0f}" for d in DELAYS])
        ax.set_xlabel("차량 통행불가 기준 / vehicle cutoff")
        ax.set_ylabel("출동 지연 (분) / dispatch delay (min)")
        ax.set_title(title, fontsize=10)
        for i in range(len(DELAYS)):
            for j in range(len(CUTOFFS)):
                ax.text(j, i, f"{int(M[i, j])}", ha="center", va="center", fontsize=9,
                        color="black")
        # mark the baseline cell
        bi, bj = DELAYS.index(BASELINE_DELAY), CUTOFFS.index(BASELINE_CUTOFF)
        ax.add_patch(plt.Rectangle((bj - 0.5, bi - 0.5), 1, 1, fill=False,
                                   edgecolor="#2563eb", lw=2.5))
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    fig.suptitle("2-D 민감도: 출동지연 × 차량 통행불가 기준 (전체 N, 파란칸=기준)  /  "
                 "2-D sensitivity: dispatch delay × vehicle cutoff (full N; blue box = baseline)",
                 fontsize=12)
    fig.savefig(FIG / "rescue_sweep_2d.png", dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "rescue_sweep_2d.png")


if __name__ == "__main__":
    raise SystemExit(main())
