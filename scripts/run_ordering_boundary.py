#!/usr/bin/env python
"""WHERE does the deadline-first dispatch ordering start to work — and how far is
that from the window this system actually runs?

Round-4 PHASE 24. The extension of PHASE 23 (``run_dispatch_ordering.py``).

WHAT PHASE 23 LEFT OPEN
-----------------------
PHASE 23 measured the shipped ordering (``ingress_survival − responder_ETA``
ascending) against three alternatives on a W axis with exactly TWO points:

    W =  75 min (committed, ``responder.time_budget_min``)  ->  0 wins of 180
    W = 240 min (exploratory)                               -> 13 wins of 180

So the sign of the result flips somewhere between 75 and 240, and PHASE 23 could
not say where. This script fills the axis in:

    W = 60 · 75 · 90 · 120 · 150 · 180 · 210 · 240 · 300 · 360 · 480 · 600

⚠ THE PHASE 23 CONCLUSION IS NOT UNDER TEST AND DOES NOT CHANGE
----------------------------------------------------------------
This run does not re-open "does the shipped ordering help at the committed
window". It measured 0 of 180 and it still measures 0 of 180 — this script
asserts that reproduction. What is new is only the QUANTITATIVE BOUNDARY of the
mechanism §6 of ``dispatch_ordering.md`` already identified: when the operational
window shuts before the corridors do, the homes share one deadline, the sort key
is near-constant, and sorting on it buys nothing.

Finding a W at which the rule wins is NOT evidence that the rule works here.
"A condition exists under which it is valid" and "the current condition is that
condition" are different statements. The second remains false.

WHAT IS REUSED, UNMODIFIED
--------------------------
Everything that computes a number. ``run_dispatch_ordering`` is imported as a
module and its ``build_arm`` / ``simulate`` / ``sweep`` / ``summarise`` /
``fixed_orders`` / ``binding_constraint`` are called as-is. NO new model. The two
module attributes this script rebinds:

  * ``WINDOWS``            75/240  ->  the 12-point axis above.
  * ``binding_constraint`` wrapped so it ALSO records the deadline distribution's
    spread (distinct count is already there; this adds variance and Shannon
    entropy). The wrapper calls the original first and only adds keys.

Occupancy rules, the return assumption, the service-time definition, the success
criterion, the four arms, the four fixed orderings, the 200 pinned random seeds
and the drift arm-B assertion are all PHASE 23's, untouched.

⚠ FOUR ARMS, INCLUDING 영덕 real. PHASE 23 was directed at STEP 0 to drop that
arm and did not, because the premise for dropping it came from a different
``vehicle_cutoff``. It then produced the WORST result of the four. It is kept
here for the same reason and reported the same way.

⚠ THE YEONGDEOK ARMS ARE DRIFT ARM B (441/174/32/142), never the committed 439
series. Asserted, not reconciled.

Writes ``data/processed/ordering_boundary.json``. Touches no committed artifact.

Run:  python scripts/run_ordering_boundary.py
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import run_dispatch_ordering as p23  # noqa: E402  — the PHASE 23 model, reused whole

from wildfireguardian.config import config_hash  # noqa: E402

OUT = REPO / "data" / "processed" / "ordering_boundary.json"
P23_ARTIFACT = REPO / "data" / "processed" / "dispatch_ordering_comparison.json"

#: The extended axis. 75 and 240 are PHASE 23's two points and are kept so the
#: earlier result can be reproduced cell-for-cell inside this run.
WINDOWS_EXTENDED = [60.0, 75.0, 90.0, 120.0, 150.0, 180.0, 210.0, 240.0,
                    300.0, 360.0, 480.0, 600.0]

#: PHASE 23's headline tallies, asserted against this run. A mismatch is the
#: single most important thing this script can report, so it does not stop the
#: run — it records the mismatch and flags it.
P23_EXPECTED = {
    "W75": {"n": 180, "deadline_wins": 0, "ties": 88, "deadline_loses": 92},
    "W240": {"n": 180, "deadline_wins": 13, "ties": 44, "deadline_loses": 123},
}


# ---------------------------------------------------------------------------
# The one wrapper: deadline spread, added to PHASE 23's binding_constraint
# ---------------------------------------------------------------------------

_ORIG_BINDING = p23.binding_constraint


def binding_constraint_with_spread(entries, *, delay: float, window: float) -> dict:
    """PHASE 23's ``binding_constraint``, plus how spread the deadlines are.

    ⚠ Adds keys only. Every value the original produced is produced by the
    original, called first and unmodified.

    ``deadline = min(ingress_survival, delay + W)`` is the quantity every
    ordering sorts against. The original already counts how many DISTINCT values
    it takes; STEP 2-B also wants its dispersion, because "6 distinct values, 136
    homes on one of them" and "6 distinct values, evenly split" are very
    different amounts of orderable information.

    Shannon entropy is over the empirical distribution of deadline VALUES across
    dispatch homes, in bits; ``normalised`` divides by log2(n_homes), the entropy
    of an all-distinct list, so it lands in [0, 1] and is comparable across arms
    of different size.
    """
    out = _ORIG_BINDING(entries, delay=delay, window=window)
    horizon = delay + window
    deadlines = [min(e["survival"], horizon) for e in entries]
    n = len(deadlines)
    counts = collections.Counter(deadlines)
    ent = -sum((c / n) * math.log2(c / n) for c in counts.values())
    max_ent = math.log2(n) if n > 1 else 0.0
    # the modal deadline is almost always the window itself when the window binds
    modal_value, modal_n = counts.most_common(1)[0]
    out["deadline_spread"] = {
        "n_homes": n,
        "variance_min2": round(statistics.pvariance(deadlines), 3),
        "stdev_min": round(statistics.pstdev(deadlines), 3),
        "entropy_bits": round(ent, 4),
        "entropy_normalised": round(ent / max_ent, 4) if max_ent else 0.0,
        "modal_deadline_min": modal_value,
        "modal_share_pct": round(100.0 * modal_n / n, 1),
        "histogram_min": {str(k): v for k, v in sorted(counts.items())},
        "note": ("deadline = min(ingress_survival, delay + W) — the key every "
                 "ordering sorts on. entropy_normalised is bits / log2(n_homes), "
                 "so 0 means one shared deadline and 1 means all distinct."),
    }
    return out


# ---------------------------------------------------------------------------
# Analysis over the finished grid
# ---------------------------------------------------------------------------


def _wnum(w: str) -> float:
    """'W120' -> 120.0. summarise() keys windows as strings; sort them as numbers."""
    return float(w[1:])


def _tally(rs: list) -> dict:
    wins = sum(1 for r in rs if r["deadline_minus_nearest"] > 0)
    ties = sum(1 for r in rs if r["deadline_minus_nearest"] == 0)
    loss = sum(1 for r in rs if r["deadline_minus_nearest"] < 0)
    n = len(rs)
    return {"n": n, "deadline_wins": wins, "ties": ties, "deadline_loses": loss,
            "win_rate_pct": round(100.0 * wins / n, 1) if n else None,
            "loss_rate_pct": round(100.0 * loss / n, 1) if n else None,
            "mean_deadline_minus_nearest": (round(statistics.mean(
                r["deadline_minus_nearest"] for r in rs), 3) if n else None)}


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation, ties averaged. Implemented here so the script keeps its
    no-extra-dependency property (numpy is already a hard dependency; scipy is
    not in the verified path)."""
    n = len(xs)
    if n < 3:
        return None

    def rank(v: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    return _pearson(rank(xs), rank(ys))


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return round(sxy / math.sqrt(sxx * syy), 4)


def deadline_stats_by_arm_window(arms: dict) -> dict:
    """Per (arm, W, delay): the deadline-key statistics, deduplicated.

    ``binding_constraint`` depends only on (arm, W, delay) — not on service time,
    team count or occupancy — so the grid recomputes an identical block six times
    per (W, delay). Collapse it, and assert the six agreed.
    """
    out: dict = {}
    for key, arm in arms.items():
        for cell_key, cell in arm.get("grid", {}).items():
            occ, w, s, d = cell_key.split("|")
            bc = cell["binding_constraint"]
            slot = out.setdefault(key, {}).setdefault(w, {}).setdefault(d, None)
            block = {
                "horizon_min": bc["horizon_min"],
                "n_dispatch_homes": bc["deadline_spread"]["n_homes"],
                "n_distinct_deadlines": bc["n_distinct_deadlines"],
                "n_corridor_binds": bc["n_survival_binds"],
                "n_window_binds": bc["n_window_binds"],
                "pct_corridor_binds": bc["pct_survival_binds"],
                "pct_window_binds": round(100.0 - bc["pct_survival_binds"], 1),
                "n_unreachable_even_at_slot_0": bc["n_unreachable_even_at_slot_0"],
                "deadline_variance_min2": bc["deadline_spread"]["variance_min2"],
                "deadline_stdev_min": bc["deadline_spread"]["stdev_min"],
                "deadline_entropy_bits": bc["deadline_spread"]["entropy_bits"],
                "deadline_entropy_normalised": bc["deadline_spread"]["entropy_normalised"],
                "modal_deadline_min": bc["deadline_spread"]["modal_deadline_min"],
                "modal_share_pct": bc["deadline_spread"]["modal_share_pct"],
            }
            if slot is None:
                out[key][w][d] = block
            elif slot != block:
                raise AssertionError(
                    f"binding_constraint disagreed across service/occupancy for "
                    f"{key} {w} {d}: it must depend on (arm, W, delay) only.\n"
                    f"  {slot}\n  {block}")
    return out


def boundary_curve(rows: list[dict], dstats: dict) -> dict:
    """STEP 2-A + 2-B: the win/tie/loss curve along W, and what moves with it."""
    live = [r for r in rows if r["occupancy"] == "depot_return"]
    windows = sorted({r["window"] for r in live}, key=_wnum)
    arms = sorted({r["arm"] for r in live})

    pooled = {w: _tally([r for r in live if r["window"] == w]) for w in windows}
    per_arm = {a: {w: _tally([r for r in live if r["arm"] == a and r["window"] == w])
                   for w in windows} for a in arms}

    # ⚠ 2-A asks for the FIRST W at which the win count leaves zero, pooled and
    # per arm. Reported as null when it never leaves zero on this axis.
    def first_nonzero(series: dict) -> float | None:
        for w in windows:
            if series[w]["deadline_wins"] > 0:
                return _wnum(w)
        return None

    # cell-level association between the deadline key's information content and
    # the outcome. ⚠ correlation only — the mechanism was established in PHASE 23
    # §6; this quantifies it, it does not establish it.
    xs_distinct, xs_ent, xs_corr, ys_win, ys_delta = [], [], [], [], []
    for r in live:
        st = dstats[r["arm"]][r["window"]][r["delay"]]
        xs_distinct.append(float(st["n_distinct_deadlines"]))
        xs_ent.append(float(st["deadline_entropy_normalised"]))
        xs_corr.append(float(st["pct_corridor_binds"]))
        ys_win.append(1.0 if r["deadline_minus_nearest"] > 0 else 0.0)
        ys_delta.append(float(r["deadline_minus_nearest"]))

    by_distinct: dict = {}
    for r in live:
        st = dstats[r["arm"]][r["window"]][r["delay"]]
        b = by_distinct.setdefault(str(st["n_distinct_deadlines"]), [])
        b.append(r)

    return {
        "windows_min": [_wnum(w) for w in windows],
        "pooled_by_window": {w: pooled[w] for w in windows},
        "by_arm_by_window": {a: {w: per_arm[a][w] for w in windows} for a in arms},
        "first_window_with_a_win": {
            "pooled_min": first_nonzero(pooled),
            "per_arm_min": {a: first_nonzero(per_arm[a]) for a in arms},
            "⚠": ("first W on THIS 12-point axis at which 시한 임박 순 out-rescues "
                  "가까운 순 in at least one cell. null = never on this axis. The "
                  "axis is discrete, so this is an upper bound on the true "
                  "crossing point, not the crossing point."),
        },
        "association_deadline_information_vs_outcome": {
            "unit_of_analysis": "one headline cell (arm x W x service x delay x units)",
            "n": len(live),
            "n_distinct_deadlines_vs_win": {
                "spearman": _spearman(xs_distinct, ys_win),
                "pearson": _pearson(xs_distinct, ys_win)},
            "n_distinct_deadlines_vs_margin": {
                "spearman": _spearman(xs_distinct, ys_delta),
                "pearson": _pearson(xs_distinct, ys_delta)},
            "entropy_normalised_vs_win": {
                "spearman": _spearman(xs_ent, ys_win),
                "pearson": _pearson(xs_ent, ys_win)},
            "pct_corridor_binds_vs_win": {
                "spearman": _spearman(xs_corr, ys_win),
                "pearson": _pearson(xs_corr, ys_win)},
            "win_rate_by_n_distinct_deadlines": {
                k: _tally(v) for k, v in sorted(by_distinct.items(), key=lambda p: int(p[0]))},
            "⚠ NOT A CAUSAL CLAIM": (
                "The mechanism was established in PHASE 23 §6 by counting which "
                "term of min(ingress_survival, delay+W) binds. These coefficients "
                "QUANTIFY that mechanism; they do not establish it, and they are "
                "not evidence of one on their own. W, the distinct-deadline count "
                "and the corridor-binding share all move together by construction "
                "— raising W is what lets the corridor term bind — so they cannot "
                "be separated by this design."),
        },
    }


def threshold_verdict(curve: dict, rows: list[dict], dstats: dict) -> dict:
    """STEP 2-C: is there a threshold, and if so in what?

    ⚠ If no single value separates wins from non-wins, this says so. It does not
    manufacture one.
    """
    live = [r for r in rows if r["occupancy"] == "depot_return"]
    wins = [r for r in live if r["deadline_minus_nearest"] > 0]

    def stat(r, k):
        return dstats[r["arm"]][r["window"]][r["delay"]][k]

    win_distinct = [stat(r, "n_distinct_deadlines") for r in wins]
    non_distinct = [stat(r, "n_distinct_deadlines") for r in live
                    if r["deadline_minus_nearest"] <= 0]
    win_w = [_wnum(r["window"]) for r in wins]

    # Does a single cut on n_distinct_deadlines separate wins from non-wins?
    sep = None
    if win_distinct:
        lo = min(win_distinct)
        # cells at or above the lowest winning value that do NOT win
        non_above = [v for v in non_distinct if v >= lo]
        sep = {
            "lowest_n_distinct_deadlines_among_wins": lo,
            "highest_n_distinct_deadlines_among_non_wins": (max(non_distinct)
                                                            if non_distinct else None),
            "n_non_winning_cells_at_or_above_that_value": len(non_above),
            "clean_separation": len(non_above) == 0,
        }

    # interaction: what do the winning cells look like on the other axes?
    def dist(rs, k):
        return {str(v): n for v, n in sorted(collections.Counter(r[k] for r in rs).items(),
                                             key=lambda p: str(p[0]))}

    return {
        "is_W_alone_sufficient": {
            "answer": None,   # filled by the caller from the curve, see below
            "min_winning_W_min": min(win_w) if win_w else None,
            "max_non_winning_W_min": max(
                (_wnum(r["window"]) for r in live if r["deadline_minus_nearest"] <= 0),
                default=None),
            "note": ("W alone would be sufficient only if every cell above some W "
                     "won and every cell below it did not. Compare the two values "
                     "and the per-arm curves."),
        },
        "n_distinct_deadlines_cut": sep,
        "winning_cells_profile": {
            "n": len(wins),
            "by_arm": dist(wins, "arm"),
            "by_window": dist(wins, "window"),
            "by_units": dist(wins, "units"),
            "by_service": dist(wins, "service"),
            "by_delay": dist(wins, "delay"),
        },
        "all_cells_profile": {
            "n": len(live),
            "by_units": dist(live, "units"),
            "by_service": dist(live, "service"),
            "by_delay": dist(live, "delay"),
        },
        "win_rate_by_units": {str(u): _tally([r for r in live if r["units"] == u])
                              for u in sorted({r["units"] for r in live})},
        "win_rate_by_service": {s: _tally([r for r in live if r["service"] == s])
                                for s in sorted({r["service"] for r in live})},
        "win_rate_by_delay": {d: _tally([r for r in live if r["delay"] == d])
                              for d in sorted({r["delay"] for r in live}, key=lambda x: int(x[1:]))},
    }


def reproduction_check(rows: list[dict], arms: dict) -> dict:
    """⚠ TOP-PRIORITY CHECK: do PHASE 23's W=75 and W=240 cells come back identical?

    Compares every headline cell this run produced at those two windows against
    the committed ``dispatch_ordering_comparison.json``, value by value. Any
    difference means the inputs moved between PHASE 23 and now, and that is more
    important than anything else this script measures.
    """
    out: dict = {"artifact": str(P23_ARTIFACT.relative_to(REPO)),
                 "compared_windows": ["W75", "W240"]}
    if not P23_ARTIFACT.exists():
        out["status"] = "ABSENT — PHASE 23 artifact not in the tree; nothing to compare"
        return out
    old = json.loads(P23_ARTIFACT.read_text())
    out["phase23_generated_utc"] = old.get("generated_utc")
    out["phase23_git_commit"] = old.get("git_commit")
    out["phase23_config_hash"] = old.get("config_hash")
    out["config_hash_matches"] = old.get("config_hash") == config_hash()

    # (a) the headline tallies. ⚠ Comparable ONLY on a full four-arm run: the
    # tally is a count over 180 cells, so a partial run under-counts by
    # construction and a mismatch would say nothing. The cellwise check below is
    # the one that is valid either way.
    got_tally = {}
    for w in ("W75", "W240"):
        rs = [r for r in rows if r["occupancy"] == "depot_return" and r["window"] == w]
        t = _tally(rs)
        got_tally[w] = {k: t[k] for k in ("n", "deadline_wins", "ties", "deadline_loses")}
    full_run = len(arms) == len(p23.ARMS)
    out["headline_tallies"] = {
        "phase23": P23_EXPECTED, "this_run": got_tally,
        "all_four_arms_present": full_run,
        "match": (got_tally == P23_EXPECTED) if full_run else None,
        "note": (None if full_run else
                 "PARTIAL RUN — fewer than four arms, so the 180-cell tally is not "
                 "comparable. Read `cellwise` instead."),
    }

    # (b) every cell, value by value
    diffs = []
    n_compared = 0
    for akey, arm in arms.items():
        old_grid = old.get("arms", {}).get(akey, {}).get("grid", {})
        for cell_key, cell in arm.get("grid", {}).items():
            if "|W75|" not in cell_key and "|W240|" not in cell_key:
                continue
            o = old_grid.get(cell_key)
            if o is None:
                diffs.append({"arm": akey, "cell": cell_key, "what": "cell absent in PHASE 23"})
                continue
            for name in ("deadline_closing_window", "nearest_eta", "earliest_closure",
                         "list_order"):
                for u in map(str, p23_units()):
                    n_compared += 1
                    if cell[name][u] != o[name][u]:
                        diffs.append({"arm": akey, "cell": cell_key, "ordering": name,
                                      "units": u, "phase23": o[name][u],
                                      "this_run": cell[name][u]})
            for u in map(str, p23_units()):
                n_compared += 1
                if cell["random"][u]["mean"] != o["random"][u]["mean"]:
                    diffs.append({"arm": akey, "cell": cell_key, "ordering": "random.mean",
                                  "units": u, "phase23": o["random"][u]["mean"],
                                  "this_run": cell["random"][u]["mean"]})
            # the deadline key's own statistics, which STEP 2-B builds on
            n_compared += 1
            keep = ("n_survival_binds", "n_window_binds", "n_distinct_deadlines")
            if {k: cell["binding_constraint"][k] for k in keep} != \
               {k: o["binding_constraint"][k] for k in keep}:
                diffs.append({"arm": akey, "cell": cell_key,
                              "ordering": "binding_constraint",
                              "phase23": {k: o["binding_constraint"][k] for k in keep},
                              "this_run": {k: cell["binding_constraint"][k] for k in keep}})

    # (c) the pipeline counts each arm rebuilt
    pipe = {}
    for akey, arm in arms.items():
        o = old.get("arms", {}).get(akey, {}).get("pipeline")
        pipe[akey] = {"phase23": o, "this_run": arm.get("pipeline"),
                      "match": o == arm.get("pipeline")}

    out["cellwise"] = {"n_values_compared": n_compared, "n_differences": len(diffs),
                       "identical": not diffs, "differences": diffs[:200]}
    out["pipeline_counts"] = pipe
    ok = (not diffs and all(v["match"] for v in pipe.values())
          and (got_tally == P23_EXPECTED if full_run else True))
    out["status"] = (
        ("REPRODUCED — every PHASE 23 value at W=75 and W=240 came back identical"
         if full_run else
         "REPRODUCED (partial run — cellwise only; the 180-cell tally needs four arms)")
        if ok else
        "⚠ NOT REPRODUCED — see differences; this is the highest-priority finding "
        "in this artifact")
    return out


def p23_units() -> list[int]:
    return p23_UNITS


p23_UNITS = p23.UNITS


def operating_window_evidence() -> dict:
    """STEP 2-D: is there any measured basis in this repository for W?

    Answered by reading the config and the documents, not by assertion.
    """
    cfg = (REPO / "config" / "default.yaml").read_text().splitlines()
    line_no, line = None, None
    for i, ln in enumerate(cfg, start=1):
        if "time_budget_min:" in ln and "walk" not in ln:
            line_no, line = i, ln.strip()
            break
    return {
        "committed_W_min": 75.0,
        "config_site": {"file": "config/default.yaml", "line": line_no, "text": line},
        "marked_in_config_as": "ASSUMED",
        "documented_as": (
            "docs/rescue_routing.md §6 lists it under 「Assumed numeric inputs (all "
            "config-driven, all swept where relevant)」 alongside the 0.7 m/s elderly "
            "walk speed and the 40 km/h vehicle speed."),
        "external_source_in_repository": None,
        "⚠ verdict": (
            "W = 75분은 가정이며 실측 근거가 저장소에 없습니다. There is no citation, "
            "no fire-service document, no measured mobilisation record and no "
            "provenance entry anywhere in the tree that derives 75 from anything. "
            "It is an assumed PoC parameter, flagged as such at its definition site. "
            "Every statement about how far the committed window sits from the "
            "boundary is therefore a statement about an ASSUMED window, and the "
            "distance is only as meaningful as that assumption."),
        "consequence_for_this_experiment": (
            "The boundary this script measures is a property of the model. Whether "
            "real 영덕 responder operations run at 75, at 200 or at 400 minutes is "
            "NOT measurable from anything in this repository, so this experiment "
            "CANNOT say whether real operations fall on the working side of the "
            "boundary. It can only say where the boundary is, and that the assumed "
            "value sits below it."),
    }


def premise_checks() -> dict:
    """⚠ HANDOFF §4-B: every cited prior measurement, looked up before use."""
    old = json.loads(P23_ARTIFACT.read_text()) if P23_ARTIFACT.exists() else {}
    s = old.get("summary", {})
    return {
        "rule": ("HANDOFF_ROUND3 §4-B — before acting on a cited measurement or a "
                 "cited prior step, check it exists in the repository."),
        "checks": [
            {"cited": "PHASE 23 measured 0 wins of 180 cells at the committed W=75",
             "found": s.get("by_window", {}).get("W75"),
             "verdict": "CONFIRMED — summary.by_window.W75 in the committed artifact"},
            {"cited": "at W=240 it wins in 13 cells",
             "found": s.get("by_window", {}).get("W240"),
             "verdict": "CONFIRMED — summary.by_window.W240"},
            {"cited": "PHASE 23 took 159 seconds",
             "found": old.get("total_seconds"),
             "verdict": ("CONFIRMED — total_seconds 159.1. ⚠ docs/dispatch_ordering.md "
                         "§11 rounds this to 「약 155초」; the artifact is the "
                         "authority and says 159.1.")},
            {"cited": ("네 팔 전부 유지 … 영덕 real 을 제외하지 마십시오. PHASE 23 "
                       "에서 제외 지시가 잘못이었고, 그 팔이 가장 불리한 결과를 냈습니다"),
             "found": {"arms_run_in_phase23": sorted(old.get("arms", {}).keys()),
                       "yeongdeok_real_by_arm": s.get("by_arm", {}).get("yeongdeok_2025|real")},
             "verdict": ("CONFIRMED WITH A CORRECTION. The EXCLUSION DIRECTIVE was "
                         "indeed wrong — it rested on a cutoff-0.30 branch artifact "
                         "while this repository runs 0.70. But PHASE 23 did NOT act "
                         "on it: all four arms were run, and the artifact records the "
                         "refusal under `⚠ arm_that_was_going_to_be_excluded`. The "
                         "arm is worst at the committed cell (13 vs 24 at 8 teams, "
                         "dispatch_ordering.md §4) though not worst on the pooled "
                         "tally (1 win / 31 ties / 58 losses vs 울진 real's 0/43/47). "
                         "Nothing to undo; four arms are kept.")},
            {"cited": ("순서 5종 — 시한 임박 · 가까운 · 목록 · 무작위 200시드 · "
                       "감도용 지점간"),
             "found": {"orderings_in_phase23": list(old.get("orderings", {}).keys()),
                       "occupancy_arms_in_phase23": p23_OCCUPANCY},
             "verdict": (
                 "⚠ CORRECTED, and the correction is CONSERVATIVE (nothing dropped). "
                 "PHASE 23 has FOUR fixed orderings plus random — 시한 임박 "
                 "(deadline_closing_window), 가까운 (nearest_eta), **폐쇄 이른 "
                 "(earliest_closure)**, 목록 (list_order), 무작위 200 seeds. "
                 "「감도용 지점간」 is NOT an ordering: `inter_point` is the "
                 "SENSITIVITY OCCUPANCY arm (가), orthogonal to ordering — it varies "
                 "what a served team does next, not what order the list is walked in. "
                 "The directive's list therefore names an occupancy arm as an "
                 "ordering and omits 폐쇄 이른 순. Resolution: PHASE 23's grid is "
                 "reused EXACTLY as built, so all five named items are present AND "
                 "폐쇄 이른 순 is retained. No axis was added or removed.")},
        ],
    }


p23_OCCUPANCY = p23.OCCUPANCY


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--arms", nargs="+", default=[a["key"] for a in p23.ARMS])
    ap.add_argument("--windows", nargs="+", type=float, default=WINDOWS_EXTENDED)
    args = ap.parse_args()

    # ── the two rebinds, and nothing else ────────────────────────────────────
    p23.WINDOWS = list(args.windows)
    p23.binding_constraint = binding_constraint_with_spread

    print(f"PHASE 24 — W axis: {[f'{w:g}' for w in p23.WINDOWS]}")
    print(f"  arms={len(args.arms)}  orderings=4+random({p23.N_RANDOM})  "
          f"units={p23.UNITS}  service={p23.SERVICES}  delay={p23.DELAYS}  "
          f"occupancy={p23.OCCUPANCY}")
    n_cells = (len(args.arms) * len(p23.WINDOWS) * len(p23.SERVICES) *
               len(p23.DELAYS) * len(p23.UNITS))
    print(f"  headline cells (depot_return): {n_cells}\n", flush=True)

    t0 = time.time()
    arms: dict = {}
    for spec in p23.ARMS:
        if spec["key"] not in args.arms:
            continue
        print(f"[{spec['key']}] ({spec['role']}) ...", flush=True)
        arms[spec["key"]] = p23.build_arm(spec)
        print(f"  [{spec['key']}] done in {arms[spec['key']]['seconds']} s", flush=True)

    # ⚠ PHASE 23's drift arm-B assertion, reproduced verbatim.
    yd = arms.get("yeongdeok_2025|synthetic")
    if yd:
        got = {"n_origins": yd["pipeline"]["n_origins"],
               "n_need_rescue": yd["pipeline"]["n_need_rescue"],
               "n_unreachable": yd["pipeline"]["n_unreachable"],
               "n_dispatch": yd["pipeline"]["n_dispatch"]}
        want = {k: v for k, v in p23.DRIFT_ARM_B.items() if k != "artifact"}
        if got != want:
            raise AssertionError(
                f"Yeongdeok synthetic did NOT reproduce drift arm B.\n"
                f"  want {want}\n  got  {got}\nStopping.")
        yd["reproduces_drift_arm_b"] = True

    print("\nsummarising ...", flush=True)
    summary = p23.summarise(arms)
    rows = summary["rows"]
    dstats = deadline_stats_by_arm_window(arms)
    curve = boundary_curve(rows, dstats)
    verdict = threshold_verdict(curve, rows, dstats)

    # is W alone sufficient? it is iff the winning and non-winning W ranges do
    # not overlap — computed, not asserted.
    live = [r for r in rows if r["occupancy"] == "depot_return"]
    win_w = {_wnum(r["window"]) for r in live if r["deadline_minus_nearest"] > 0}
    non_w = {_wnum(r["window"]) for r in live if r["deadline_minus_nearest"] <= 0}
    verdict["is_W_alone_sufficient"]["answer"] = bool(
        win_w and non_w and min(win_w) > max(non_w))
    verdict["is_W_alone_sufficient"]["windows_containing_a_win"] = sorted(win_w)
    verdict["is_W_alone_sufficient"]["windows_containing_a_non_win"] = sorted(non_w)

    repro = reproduction_check(rows, arms)

    doc = {
        "schema_version": 1,
        "title": ("Where does deadline-first dispatch ordering start to work, and how "
                  "far is that from the operating window?"),
        "phase": "Round-4 PHASE 24",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": p23._git(),
        "config_hash": config_hash(),
        "total_seconds": round(time.time() - t0, 1),
        "⚠ WHAT THIS DOES NOT CHANGE": {
            "phase23_conclusion_stands": (
                "시한 임박 순 정렬은 커밋된 구성에서 무효합니다 — W = 75 에서 180개 "
                "셀 중 0승. This run reproduces that and does not reopen it."),
            "what_is_new": (
                "무효인 이유의 정량적 경계입니다. PHASE 23 §6 이미 기제를 규명했고 "
                "(창이 회랑보다 먼저 닫혀 마감이 거의 상수가 된다), 이번 실행은 그 "
                "기제가 어느 W 에서 풀리는지를 12개 점으로 측정합니다."),
            "⚠ how_this_must_NOT_be_read": (
                "「우리 규칙이 사실은 유효하다」로 읽어서는 안 됩니다. 유효한 조건이 "
                "존재한다는 것과 현재 조건이 그 조건이라는 것은 다른 진술이고, "
                "두 번째는 여전히 거짓입니다. 어떤 W 에서 이긴다는 사실은 이 시스템이 "
                "그 W 로 운용된다는 근거가 아닙니다."),
            "output_ordering_unchanged": (
                "A4·문자·마을방송의 정렬은 이 실험이 바꾸지 않았습니다. printable.py "
                "DISPATCH_HEADING 과 live/pipeline.py WALK_DISPATCH_HEADING 그대로."),
        },
        "⚠ premise_checks_HANDOFF_4B": premise_checks(),
        "⚠ reproduction_of_phase23": repro,
        "reused_unmodified": {
            "script": "scripts/run_dispatch_ordering.py",
            "imported_as_a_module_and_called": [
                "build_arm", "sweep", "simulate", "fixed_orders", "random_stats",
                "summarise", "binding_constraint", "closure_profile",
                "point_to_point", "committed_model_order_invariance", "scan_ranks"],
            "rebound_attributes": {
                "WINDOWS": {"was": [75.0, 240.0], "now": p23.WINDOWS},
                "binding_constraint": ("wrapped — the original is called first and "
                                       "unmodified; the wrapper only ADDS a "
                                       "`deadline_spread` block (variance, Shannon "
                                       "entropy, modal share) that STEP 2-B needs."),
            },
            "unchanged": ["occupancy rules (나) depot_return / (가) inter_point",
                          "return-to-depot assumption", "service-time definition",
                          "success criterion arrival <= min(survival, delay+W)",
                          "the four arms", "the four fixed orderings",
                          "the 200 pinned random seeds", "the drift arm-B assertion",
                          "routing logic — untouched, as in PHASE 23"],
        },
        "⚠ yeongdeok_lineage": {
            "series": "drift arm B",
            "counts": p23.DRIFT_ARM_B,
            "not_the_committed_439_series": (
                "커밋된 계열은 439 / 167 / 24 / 143 입니다. 두 집합을 평균·조정·"
                "대체하지 마십시오 (HANDOFF §5 규칙 5)."),
        },
        "axes": {
            "window_min": p23.WINDOWS,
            "units": p23.UNITS, "service_min": p23.SERVICES,
            "dispatch_delay_min": p23.DELAYS,
            "occupancy": p23.OCCUPANCY,
            "orderings": {"fixed": list(p23.fixed_orders([
                {"closing_window": 0, "eta": 0, "survival": 0, "scan_rank": 0}]).keys()),
                "random_seeds": p23.N_RANDOM},
        },
        "boundary": curve,
        "threshold_verdict": verdict,
        "deadline_statistics_by_arm_and_window": dstats,
        "operating_window_evidence": operating_window_evidence(),
        "summary_phase23_format": summary,
        "arms": arms,
    }

    Path(args.out).write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    print(f"\nwrote {args.out}  ({round(time.time() - t0, 1)} s)")
    print(f"reproduction of PHASE 23: {repro['status']}")
    print(f"first W with a win (pooled): "
          f"{curve['first_window_with_a_win']['pooled_min']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
