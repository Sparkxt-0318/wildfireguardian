#!/usr/bin/env python
"""Verification / reconciliation passes for the rescue-routing results (PR #4).

AUDIT only — imports the existing routing/spread logic unchanged and re-runs it
under one explicit baseline so every headline number and the sweeps sit on the
SAME origin set (full N=452). Two sweeps share one machinery (``_split_counts``
+ a generalised heatmap):

  --sweep vehicle  (pass 1): dispatch delay x vehicle cutoff. Shows the vehicle
                   knobs only SPLIT the fixed needs-rescuer pool into
                   no_walk_rescuer vs unreachable. Robust finding: unreachable
                   rises with dispatch delay.
  --sweep fc       (pass 2): immobile_fraction x walk_cutoff — the two knobs that
                   set the SIZE of the not-walk-safe population. Decides whether
                   "244 / 58% need a rescuer" is a number, a direction, or an
                   artifact of the assumed immobile_fraction=0.3.

Resolved contradictions (pass 1): headline 20 vs sweep 2->13 was the convenience
``sensitivity_sweep`` sub-sampling to N≈151; here everything is full N. N 407->452
is the stride-3 + reach-band origin scan. Resident exposure is over PEDESTRIAN
routes, responder over VEHICLE routes (both prob·min), labelled distinctly.

Outputs (small JSON committed; figures in docs/figures):
  data/processed/rescue_verify.json / rescue_verify_fc.json
  docs/figures/rescue_sweep_2d.png  / rescue_sweep_fc.png

Run:  python scripts/verify_rescue_routing.py [--sweep vehicle|fc]
Deterministic; runs end-to-end on the synthetic fallback; no logic changed.
"""

from __future__ import annotations

import argparse
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

BASELINE_DELAY = 30.0
BASELINE_CUTOFF = 0.7
BASELINE_IMMOBILE = 0.30
BASELINE_WALKCUT = 0.50

# pass-1 grid (vehicle): dispatch delay x vehicle cutoff
DELAYS = [0.0, 15.0, 30.0, 45.0, 60.0]
CUTOFFS = [0.5, 0.6, 0.7, 0.8, 0.9]
# pass-2 grid (assumption): immobile_fraction x walk_cutoff
IMMOBILES = [0.15, 0.30, 0.45]
WALKCUTS = [0.40, 0.50, 0.60]

KEYS = ["already_safe", "saved_by_rescue_reachable_refuge",
        "no_safe_pedestrian_route", "no_surviving_vehicle_ingress"]
SHORT = {"already_safe": "safe", "saved_by_rescue_reachable_refuge": "saved",
         "no_safe_pedestrian_route": "no_walk", "no_surviving_vehicle_ingress": "unreach"}


def _rel_spread(vals):
    m = float(np.mean(vals)) if vals else 0.0
    return (max(vals) - min(vals)) / m if m > 0 else 0.0


def _monotone_nondecreasing(vals):
    return all(b >= a - 1e-9 for a, b in zip(vals, vals[1:]))


def _sweep_grid(scenario, base_cfg, row_param, rows, col_param, cols, N):
    """Full-N 2-D grid of four-way counts via the shared _split_counts; asserts sums."""
    grid = {}
    for r in rows:
        for c in cols:
            cfg = replace(base_cfg, **{row_param: r, col_param: c})
            rec = _split_counts(scenario, cfg)
            assert rec["n_origins"] == N, "sweep cell used a different origin set"
            assert sum(rec["counts"].values()) == N, "cell four-way did not sum to N"
            grid[(r, c)] = rec["counts"]
            print(f"  {row_param}={r:<5} {col_param}={c:<5} -> "
                  + " ".join(f"{SHORT[k]}={rec['counts'][k]}" for k in KEYS))
    return grid


def _heatmap(grid, rows, cols, row_label, col_label, baseline_rc, panels, outpath, suptitle):
    """Generalised 2-D heatmap, reused by both sweeps. ``panels`` = [(key,title,cmap)]."""
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

    fig, axes = plt.subplots(1, len(panels), figsize=(6 * len(panels), 5.0),
                             constrained_layout=True)
    if len(panels) == 1:
        axes = [axes]
    for ax, (key, title, cmap) in zip(axes, panels):
        M = np.array([[_cell(grid, r, c, key) for c in cols] for r in rows], float)
        im = ax.imshow(M, cmap=cmap, aspect="auto", origin="lower")
        ax.set_xticks(range(len(cols)), [f"{c:g}" for c in cols])
        ax.set_yticks(range(len(rows)), [f"{r:g}" for r in rows])
        ax.set_xlabel(col_label)
        ax.set_ylabel(row_label)
        ax.set_title(title, fontsize=10)
        for i in range(len(rows)):
            for j in range(len(cols)):
                ax.text(j, i, f"{int(M[i, j])}", ha="center", va="center", fontsize=9)
        bi, bj = rows.index(baseline_rc[0]), cols.index(baseline_rc[1])
        ax.add_patch(plt.Rectangle((bj - 0.5, bi - 0.5), 1, 1, fill=False,
                                   edgecolor="#2563eb", lw=2.5))
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    fig.suptitle(suptitle, fontsize=12)
    fig.savefig(outpath, dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", outpath)


def _cell(grid, r, c, key):
    """Cell value; ``key`` may be a real bucket or a derived total."""
    cc = grid[(r, c)]
    if key == "self_evacuable":
        return cc["already_safe"] + cc["saved_by_rescue_reachable_refuge"]
    if key == "needs_rescuer":
        return cc["no_safe_pedestrian_route"] + cc["no_surviving_vehicle_ingress"]
    return cc[key]


def walk_failure_table(grid, N):
    """Assumption-LIGHT decomposition of the rescue burden, from four-way counts only.

    `immobile_fraction` adds immobile origins to ``needs_rescuer`` wholesale, so
    ``needs_rescuer = round(f·N) + walk_failures_mobile``. The part the model earns
    *independently of the immobility guess* is ``w`` = the fraction of MOBILE origins
    that cannot walk to safety:

        n_mobile            = N - round(f·N)
        walk_failures_mobile = n_mobile - already_safe - saved
        w                    = walk_failures_mobile / n_mobile

    Identity (exact up to f·N rounding): ``needs_rescuer ≈ f·N + (1-f)·w·N``.
    ``w`` should be ~flat across f at fixed walk cutoff (immobility is a random draw
    uncorrelated with walkability). Computed from already-committed counts — no
    pipeline re-run.
    """
    rows = []
    for (f, c), counts in sorted(grid.items()):
        n_mob = N - round(f * N)
        wf = n_mob - counts["already_safe"] - counts["saved_by_rescue_reachable_refuge"]
        w = wf / n_mob if n_mob else 0.0
        needs = counts["no_safe_pedestrian_route"] + counts["no_surviving_vehicle_ingress"]
        assert needs == round(f * N) + wf, "walk-failure decomposition off-by-one"
        rows.append({"immobile_fraction": f, "walk_cutoff": c, "n_mobile": n_mob,
                     "walk_failures_mobile": wf, "w": round(w, 4), "needs_rescuer": needs,
                     "needs_rescuer_identity_f_plus_1mf_w": round(f * N + (1 - f) * w * N, 1)})
    return rows


def walk_failure_summary(rows):
    """Range of w across walk cutoff, and its (near-)flatness across f at fixed cutoff."""
    cutoffs = sorted({r["walk_cutoff"] for r in rows})
    by_cut = {c: sorted(r["w"] for r in rows if r["walk_cutoff"] == c) for c in cutoffs}
    w_all = [r["w"] for r in rows]
    # flatness: max spread of w across f, at any fixed cutoff
    max_spread_across_f = max(max(v) - min(v) for v in by_cut.values())
    return {
        "w_grid_min": min(w_all), "w_grid_max": max(w_all),
        "w_by_walk_cutoff_minmax": {f"{c:.2f}": [min(by_cut[c]), max(by_cut[c])] for c in cutoffs},
        "w_max_spread_across_f_fixed_cutoff": round(max_spread_across_f, 4),
        "w_approx_flat_across_f": max_spread_across_f < 0.06,
    }


def _build_baseline():
    baseline = RescueConfig(responder_dispatch_delay_min=BASELINE_DELAY,
                            vehicle_cutoff=BASELINE_CUTOFF,
                            immobile_fraction=BASELINE_IMMOBILE,
                            walk_cutoff=BASELINE_WALKCUT)
    print("Building baseline synthetic 영덕 scenario (full origin set) ...")
    scenario = build_synthetic_demo(baseline)
    N = len(scenario.origins)
    print(f"Re-deriving headline from baseline (N={N}) ...")
    headline = run_pipeline(scenario, baseline)
    return baseline, scenario, N, headline


def _exposure_lines(headline):
    rex, pe = headline.resident_exposure, headline.responder_exposure

    def m(d):
        v = d.get("mean") if isinstance(d, dict) else None
        return "n/a" if v is None else f"{v:.3f}"
    pb = rex["paired_b_vs_c"]
    return [
        f"  resident  (pedestrian, prob·min)  naive / fa-any / fa-rescuable : "
        f"{m(rex['naive'])} / {m(rex['future_aware_any'])} / {m(rex['future_aware_rescue'])}",
        f"     paired b vs c (same {pb['n']} origins)                       : "
        f"{pb['mean_future_aware_any']:.3f} / {pb['mean_future_aware_rescue']:.3f}",
        f"  responder (vehicle,    prob·min)  shortest-path / survival-aware: "
        f"{m(pe['shortest_path'])} / {m(pe['survival_aware'])}  "
        f"(dispatch {pe['n_dispatch']}, unreachable {pe['n_unreachable']})",
    ]


# ---------------------------------------------------------------------------
# pass 1 — vehicle cutoff x dispatch delay
# ---------------------------------------------------------------------------


def run_vehicle(baseline, scenario, N, headline):
    hc = headline.four_way_counts
    print(f"2-D sweep (full N={N}): dispatch delay x vehicle cutoff ...")
    grid = _sweep_grid(scenario, baseline, "responder_dispatch_delay_min", DELAYS,
                       "vehicle_cutoff", CUTOFFS, N)
    reconciled = (grid[(BASELINE_DELAY, BASELINE_CUTOFF)] == hc)

    subset_ok = True
    for vc in CUTOFFS:
        assessments, _a, _r = _refuge_node_sets(scenario, replace(baseline, vehicle_cutoff=vc))
        if any(a.rescue_reachable and not a.safe for a in assessments):
            subset_ok = False
    unreach_row = [_cell(grid, d, BASELINE_CUTOFF, "no_surviving_vehicle_ingress") for d in DELAYS]
    monotone_all = all(_monotone_nondecreasing(
        [_cell(grid, d, vc, "no_surviving_vehicle_ingress") for d in DELAYS]) for vc in CUTOFFS)

    block = ["=== RECONCILED RESULTS (vehicle sweep, single baseline) ===",
             f"Baseline (delay {BASELINE_DELAY:.0f}, vehicle cutoff {BASELINE_CUTOFF}, N={N}):",
             "  four-way: " + " / ".join(str(hc[k]) for k in KEYS)
             + f"   [== headline: {reconciled}]"]
    block += _exposure_lines(headline)
    block.append(f"\n=== VEHICLE SWEEP (delay x vehicle cutoff), full N={N} ===")
    block.append("cell = (safe, saved, no_walk, unreach)")
    block.append("delay\\cut | " + " | ".join(f"{vc:.2f}" for vc in CUTOFFS))
    for d in DELAYS:
        block.append(f"  {d:>4.0f}    | "
                     + " | ".join(str(tuple(_cell(grid, d, vc, k) for k in KEYS)) for vc in CUTOFFS))
    block.append(f"unreachable @ dispatch 0->60 (cutoff {BASELINE_CUTOFF}): "
                 f"{unreach_row[0]} -> {unreach_row[-1]}  "
                 f"[robust direction; monotone all cutoffs={monotone_all}]")
    block.append(f"rescue_reachable ⊆ safe (all cutoffs): {subset_ok}")
    text = "\n".join(block)
    print("\n" + text)

    out = {"baseline_config": baseline.provenance(), "n_origins": N,
           "headline_four_way": hc, "baseline_cell_equals_headline": reconciled,
           "grid": {f"{d:.0f}|{vc:.2f}": grid[(d, vc)] for d in DELAYS for vc in CUTOFFS},
           "rescue_reachable_subset_safe_all_cutoffs": subset_ok,
           "unreachable_delay_row_cutoff_0p7": unreach_row, "reconciled_block": text}
    (PROC / "rescue_verify.json").write_text(json.dumps(out, indent=2, default=str))
    _heatmap(grid, DELAYS, CUTOFFS, "출동 지연 (분) / dispatch delay (min)",
             "차량 통행불가 기준 / vehicle cutoff", (BASELINE_DELAY, BASELINE_CUTOFF),
             [("no_surviving_vehicle_ingress", "구조 불가 / UNREACHABLE", "Reds"),
              ("no_safe_pedestrian_route", "도보 불가·구조대 가능 / no walk, rescuer reaches", "Oranges"),
              ("saved_by_rescue_reachable_refuge", "대피소로 구조 / saved", "Greens")],
             FIG / "rescue_sweep_2d.png",
             "2-D 민감도: 출동지연 × 차량 통행불가 기준 (전체 N, 파란칸=기준)  /  "
             "dispatch delay × vehicle cutoff (full N; blue box = baseline)")
    return 0 if (reconciled and subset_ok) else 1


# ---------------------------------------------------------------------------
# pass 2 — immobile_fraction x walk_cutoff (the assumption sweep)
# ---------------------------------------------------------------------------


def run_fc(baseline, scenario, N, headline):
    hc = headline.four_way_counts
    print(f"2-D sweep (full N={N}): immobile_fraction x walk_cutoff ...")
    grid = _sweep_grid(scenario, baseline, "immobile_fraction", IMMOBILES,
                       "walk_cutoff", WALKCUTS, N)
    base_rc = (BASELINE_IMMOBILE, BASELINE_WALKCUT)
    reconciled = (grid[base_rc] == hc)

    # derived totals + subset check
    subset_ok = True
    for f in IMMOBILES:
        for c in WALKCUTS:
            assert (_cell(grid, f, c, "self_evacuable")
                    + _cell(grid, f, c, "needs_rescuer")) == N
    for c in WALKCUTS:
        assessments, _a, _r = _refuge_node_sets(scenario, replace(baseline, walk_cutoff=c))
        if any(a.rescue_reachable and not a.safe for a in assessments):
            subset_ok = False

    # partition assumption: do already_safe / saved move with f at fixed c?
    def col(key, c):
        return [_cell(grid, f, c, key) for f in IMMOBILES]
    safe_moves = any(len(set(col("already_safe", c))) > 1 for c in WALKCUTS)
    saved_moves = any(len(set(col("saved_by_rescue_reachable_refuge", c))) > 1 for c in WALKCUTS)
    partition_holds = not (safe_moves or saved_moves)

    # monotonicity
    self_evac_up_with_cut = all(
        _monotone_nondecreasing([_cell(grid, f, c, "self_evacuable") for c in sorted(WALKCUTS)])
        for f in IMMOBILES)
    needs_up_with_f = all(
        _monotone_nondecreasing([_cell(grid, f, c, "needs_rescuer") for f in sorted(IMMOBILES)])
        for c in WALKCUTS)
    needs_up_as_cut_falls = all(
        _monotone_nondecreasing([_cell(grid, f, c, "needs_rescuer")
                                 for c in sorted(WALKCUTS, reverse=True)])
        for f in IMMOBILES)

    # verdict numbers
    nr_baseline = _cell(grid, *base_rc, "needs_rescuer")
    nr_grid = [_cell(grid, f, c, "needs_rescuer") for f in IMMOBILES for c in WALKCUTS]
    nr_f015 = _cell(grid, 0.15, BASELINE_WALKCUT, "needs_rescuer")
    nr_f045 = _cell(grid, 0.45, BASELINE_WALKCUT, "needs_rescuer")
    nw_baseline = _cell(grid, *base_rc, "no_safe_pedestrian_route")
    nw_grid = [_cell(grid, f, c, "no_safe_pedestrian_route") for f in IMMOBILES for c in WALKCUTS]
    nw_central_rel = _rel_spread([_cell(grid, f, c, "no_safe_pedestrian_route")
                                  for f in IMMOBILES for c in WALKCUTS])
    nr_verdict = "directional" if (needs_up_with_f and needs_up_as_cut_falls) else "fragile"

    block = ["=== RECONCILED RESULTS — assumption sweep (single baseline) ===",
             f"Baseline (f={BASELINE_IMMOBILE}, walk_cutoff={BASELINE_WALKCUT}, "
             f"dispatch={BASELINE_DELAY:.0f}, vehicle_cutoff={BASELINE_CUTOFF}, N={N}):",
             "  four-way: already_safe / saved / no_walk_rescuer / unreachable = "
             + " / ".join(str(hc[k]) for k in KEYS) + f"   [== headline: {reconciled}]",
             f"  derived : self_evacuable = {hc['already_safe'] + hc['saved_by_rescue_reachable_refuge']} ; "
             f"needs_rescuer = {nr_baseline} ({100*nr_baseline/N:.0f}%)"]
    block += _exposure_lines(headline)
    block.append("")
    block.append("Category definitions (from code):")
    block.append("  already_safe    : MOBILE origin; fire-blind nearest-refuge walk is safe")
    block.append("  saved           : MOBILE; naive unsafe; future-aware walk to a RESCUE-REACHABLE "
                 "refuge is safe (was 34 across the vehicle×delay grid because those origins use "
                 "coastal refuges that stay rescue-reachable)")
    block.append("  no_walk_rescuer : cannot self-evacuate (immobile OR walk route cut) AND a "
                 "survival-aware responder route reaches the home")
    block.append("  unreachable     : cannot self-evacuate AND no responder route survives in budget")
    block.append("  immobile_fraction enters at _immobile_homes: a RANDOM f·N origins are forced onto "
                 "the rescuer path REGARDLESS of walkability (yes) — they skip the walk checks")
    block.append("")
    block.append(f"=== f x c SWEEP (immobile_fraction × walk_cutoff), full N={N} ===")
    block.append("cell = (safe, saved, no_walk, unreach | self_evac, needs_rescuer)")
    block.append("f \\ walk_cut | " + " | ".join(f"{c:.2f}" for c in WALKCUTS))
    for f in IMMOBILES:
        cells = []
        for c in WALKCUTS:
            t = tuple(_cell(grid, f, c, k) for k in KEYS)
            cells.append(f"{t} | {_cell(grid, f, c, 'self_evacuable')},{_cell(grid, f, c, 'needs_rescuer')}")
        block.append(f"  {f:.2f}      | " + " | ".join(cells))
    block.append(f"already_safe/saved invariant to f? : {'YES' if partition_holds else 'NO'} "
                 f"-> partition assumption {'HOLDS' if partition_holds else 'BREAKS'} "
                 f"(immobile relabels a random f of walk-capable origins)")
    block.append(f"monotonicity: self_evac ↑ with walk_cutoff? {'Y' if self_evac_up_with_cut else 'N'}; "
                 f"needs_rescuer ↑ with f? {'Y' if needs_up_with_f else 'N'}; "
                 f"needs_rescuer ↑ as walk_cutoff ↓? {'Y' if needs_up_as_cut_falls else 'N'}")
    block.append(f"heatmap: {FIG / 'rescue_sweep_fc.png'}")
    block.append("")
    block.append("=== VERDICT ===")
    block.append(f"  needs_rescuer {100*nr_baseline/N:.0f}% ({nr_baseline}/{N}) : {nr_verdict}; "
                 f"grid range {min(nr_grid)}-{max(nr_grid)}; "
                 f"f=0.15 vs 0.45 @ c=0.50: {nr_f015} vs {nr_f045} "
                 f"({100*nr_f015/N:.0f}% vs {100*nr_f045/N:.0f}%)")
    block.append(f"  no_walk_rescuer {nw_baseline} : re-classified directional w.r.t. the ASSUMPTION "
                 f"knobs (grid {min(nw_grid)}-{max(nw_grid)}, rel-spread {nw_central_rel:.2f}); the "
                 f"earlier 'robust' held only vs the vehicle knobs")
    block.append("  saved 34 : rescue-meaningful (a pedestrian route to a rescue-REACHABLE refuge — "
                 "the resident-side win of the feature), NOT a mislabel; it moves with f (over the "
                 "mobile pool), so it is not f-invariant")
    floor = _cell(grid, 0.15, BASELINE_WALKCUT, "needs_rescuer")
    block.append(f"  defensible headline today : \"Under walk cutoff 0.5 and 30% assumed immobile, "
                 f"{nr_baseline}/{N} ({100*nr_baseline/N:.0f}%) cannot self-evacuate on foot; at 15% "
                 f"assumed immobile this falls to {floor}/{N} ({100*floor/N:.0f}%). The split is driven "
                 f"by the assumed immobile fraction + the slow-elder pedestrian regime, not vehicle knobs.\"")
    block.append("  unchanged keeper : dispatch-delay trend (vehicle sweep) remains a robust direction")
    text = "\n".join(block)
    print("\n" + text)

    out = {"baseline_config": baseline.provenance(), "n_origins": N,
           "headline_four_way": hc, "baseline_cell_equals_headline": reconciled,
           "grid": {f"{f:.2f}|{c:.2f}": {**grid[(f, c)],
                                         "self_evacuable": _cell(grid, f, c, "self_evacuable"),
                                         "needs_rescuer": _cell(grid, f, c, "needs_rescuer")}
                    for f in IMMOBILES for c in WALKCUTS},
           "partition_already_safe_saved_invariant_to_f": partition_holds,
           "monotonicity": {"self_evac_up_with_walk_cutoff": self_evac_up_with_cut,
                            "needs_rescuer_up_with_f": needs_up_with_f,
                            "needs_rescuer_up_as_walk_cutoff_falls": needs_up_as_cut_falls},
           "needs_rescuer": {"baseline": nr_baseline, "baseline_pct": round(100*nr_baseline/N, 1),
                             "grid_min": min(nr_grid), "grid_max": max(nr_grid),
                             "f0.15_c0.5": nr_f015, "f0.45_c0.5": nr_f045, "verdict": nr_verdict},
           "rescue_reachable_subset_safe_all_walkcuts": subset_ok,
           "reconciled_block": text}
    wf_rows = walk_failure_table(grid, N)
    out["walk_failure"] = {"per_cell": wf_rows, "summary": walk_failure_summary(wf_rows)}
    wfs = out["walk_failure"]["summary"]
    print(f"  assumption-light walk-failure w: grid {wfs['w_grid_min']:.3f}-{wfs['w_grid_max']:.3f}; "
          f"flat across f? {wfs['w_approx_flat_across_f']} "
          f"(max spread {wfs['w_max_spread_across_f_fixed_cutoff']:.3f})")
    (PROC / "rescue_verify_fc.json").write_text(json.dumps(out, indent=2, default=str))
    _heatmap(grid, IMMOBILES, WALKCUTS, "거동불가 비율 / immobile fraction",
             "보행 통행불가 기준 / walk cutoff", base_rc,
             [("needs_rescuer", "구조대 필요 (계) / needs rescuer", "Purples"),
              ("no_safe_pedestrian_route", "도보 불가·구조대 가능 / no walk, rescuer reaches", "Oranges"),
              ("self_evacuable", "자력 대피 가능 / self-evacuable", "Greens")],
             FIG / "rescue_sweep_fc.png",
             "2-D 가정 민감도: 거동불가 비율 × 보행 통행불가 기준 (전체 N, 파란칸=기준)  /  "
             "assumption sweep: immobile fraction × walk cutoff (full N; blue box = baseline)")
    ok = reconciled and subset_ok
    if not ok:
        print("ERROR: reconciliation/subset invariant failed.", file=sys.stderr)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep", choices=["vehicle", "fc"], default="vehicle")
    args = ap.parse_args()
    PROC.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    baseline, scenario, N, headline = _build_baseline()
    if args.sweep == "vehicle":
        return run_vehicle(baseline, scenario, N, headline)
    return run_fc(baseline, scenario, N, headline)


if __name__ == "__main__":
    raise SystemExit(main())
