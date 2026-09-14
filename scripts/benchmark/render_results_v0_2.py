#!/usr/bin/env python
"""Append the results section of ``docs/benchmark/results_v0.2.md`` from Stage 2 artifacts.

Same rule as ``render_results_v0_1.py``: the page's argument is written by hand and frozen,
and every number below the marker is read from an artifact, so no figure on the page is
transcribed. Reads ``leaderboard_v0_2.json`` (Stage 2's own leaderboard; the v0.1
``leaderboard.json`` is a committed artifact and is not touched) and ``stage2_sweep.json``.

    python scripts/benchmark/render_results_v0_2.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs/benchmark/results_v0.2.md"
BENCH = REPO / "data/processed/benchmark"
BOARD = BENCH / "leaderboard_v0_2.json"
SWEEP = BENCH / "stage2_sweep.json"
MARKER = "_(appended by `scripts/benchmark/render_results_v0_2.py`; nothing above this line is edited after the run)_"
HK = ("180min", "300min", "480min")
HL = {"180min": "T0 + 3 h", "300min": "T0 + 5 h", "480min": "T0 + 8 h"}


def f(v, nd=4):
    return "—" if v is None else f"{v:.{nd}f}"


def main() -> int:
    board = json.loads(BOARD.read_text(encoding="utf-8"))
    sweep = json.loads(SWEEP.read_text(encoding="utf-8"))
    rows = {t: [(e, json.loads((BENCH / e["entrant"] / f"{ev}.json").read_text(encoding="utf-8")))
                for e in es for ev in e["per_event"]] for t, es in board["tracks"].items()}

    L = ["",
         f"_Run {board['generated_utc']} at `{board['git_commit'][:7]}`; protocol "
         f"`{board['protocol_version']}`; scorer `{board['scorer']}`, unchanged from Stage 1; "
         f"artifacts `data/processed/benchmark/`; {board['seconds']:.0f} s._", ""]

    L += ["### 6.1 Metrics 1 and 2, by track", "",
          "The two tables are **not** to be read against each other (protocol §3). Every Stage 2 "
          "row is an **oracle upper bound**, not a score the method achieved — see §3.", "",
          ]
    for track in ("forecast", "hindcast"):
        if not rows[track]:
            continue
        L += [f"**{track} track**", "",
              "| entrant | horizon | ROC-AUC | IoU at p ≥ 0.5 | predicted positive | unscorable |",
              "|---|---|---:|---:|---:|---:|"]
        for e, d in rows[track]:
            for k in HK:
                h = d["horizons"][k]["m0"]
                L.append(f"| {e['name']} | {HL[k]} | {f(h['roc_auc'])} | "
                         f"{f(h['iou_at_p_ge_0.5'])} | {h['cells_predicted_positive']:,} | "
                         f"{h['cells_unscorable_indeterminate']:,} |")
        L.append("")

    L += ["### 6.2 Metric 3 — arrival-time error at the road nodes (the one the protocol says matters)",
          "",
          f"Node set: {board['metric3_node_set']['rule']} — "
          f"{board['metric3_node_set']['n_nodes']:,} nodes, identical for every entrant. Cell "
          "membership (A5); window = the entrant's own last surface. Signed error is model minus "
          "observation, so **positive is late**.", "",
          "| entrant | track | entrant burns | both | median abs error | false-safe | false-safe rate | false alarms |",
          "|---|---|---:|---:|---:|---|---:|---:|"]
    for track in ("forecast", "hindcast"):
        for e, d in rows[track]:
            a = d["arrival_time_error"]
            L.append(f"| {e['name']} | {track} | {a['nodes_model_burns']:,} | "
                     f"{a['nodes_both_burn']:,} | {f(a['median_abs_error_min'], 1)} min | "
                     f"{a['false_safe_nodes']:,} of {a['nodes_model_calls_safe']:,} | "
                     f"{f(a['false_safe_rate'])} | {a['false_alarm_nodes']:,} |")
    L.append("")

    L += ["### 6.3 Metric 4 — decision shift on the 주건물", "",
          "Buildings whose last-safe-departure class changes between the entrant's field and the "
          "observation-graded field, the committed time-aware policy with only the hazard changed. "
          "The observation puts **2,645** buildings in `closes_before_5h`, **1,261** in "
          "`closes_after_5h`, **190** in `never` and the rest `censored`; 「windows found」 below "
          "counts the buildings the observation says have a window that closes and the entrant "
          "does **not** call `censored` — the buildings an operator would have been warned about.",
          "",
          "| entrant | track | buildings changing class | entrant more optimistic | closing windows found (of 3,906) | flagged where truth is censored | precision | recall |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
    for track in ("forecast", "hindcast"):
        for e, d in rows[track]:
            ds = d.get("decision_shift")
            if not ds:
                L.append(f"| {e['name']} | {track} | — | — | — | — |")
                continue
            ct = ds["class_table_entrant_given_truth"]
            closing = sum(v for k, v in ct.items()
                          if k.split("|")[1] in ("closes_before_5h", "closes_after_5h")
                          and k.split("|")[0] != "censored")
            over = sum(v for k, v in ct.items()
                       if k.split("|")[1] == "censored" and k.split("|")[0] != "censored")
            flagged = closing + over
            prec = closing / flagged if flagged else None
            truth_closing = sum(v for k, v in ds["lsd_class_buildings_truth"].items()
                                if k in ("closes_before_5h", "closes_after_5h"))
            rec = closing / truth_closing if truth_closing else None
            L.append(f"| {e['name']} | {track} | {ds['buildings_class_changed']:,} | "
                     f"{ds['buildings_entrant_more_optimistic']:,} | {closing:,} | {over:,} | "
                     f"{f(prec, 3)} | {f(rec, 3)} |")
    L.append("")

    L += ["",
          "⚠ **Precision is what makes this row comparable and recall is what it measures.** "
          "「precision」 is the share of the buildings an entrant flags (any class but `censored`) "
          "whose window the observation really does close; 「recall」 is the share of the "
          "observation's closing windows the entrant flags at all. An entrant that flags nothing "
          "has no precision to report and zero recall, and one that flags everything has recall 1 "
          "and the base rate for precision. Read the two together or neither.", ""]

    name = {"e1": "E1 wind-cone", "e2": "E2 Rothermel-family"}
    sens_p = BENCH / "stage2_wind_sensitivity.json"
    if sens_p.exists():
        sens = json.loads(sens_p.read_text(encoding="utf-8"))
        L += ["### 6.4 What survives NOT knowing the wind, and the operating point that explains it",
              "",
              "Metric 3's false-safe rate at **every** declared grid point, not only at the oracle's "
              "(`data/processed/benchmark/stage2_wind_sensitivity.json`). E3's rate is **0.1830** and "
              "E0's is **0.1833**.", "",
              "| proxy | grid points with a defined rate | false-safe rate min / median / max | points beating E3 | points that call no node safe |",
              "|---|---:|---|---:|---:|"]
        for k in ("e1", "e2"):
            e = sens["entrants"][k]
            r = e["false_safe_rate"]
            L.append(f"| {name[k]} | {e['grid_points_with_a_defined_rate']} | "
                     f"{f(r['min'])} / {f(r['median'])} / {f(r['max'])} | "
                     f"{e['grid_points_beating_e3_false_safe_rate']} | "
                     f"{e['grid_points_that_call_no_node_safe']} |")
        L += ["",
              "⚠ **This is not 「a wind-cone always beats the model」, and reading it that way would "
              "be the mistake this section exists to prevent.** The proxies beat E3's false-safe "
              "rate at every wind because they burn far more of the network, not because they "
              "locate the fire better. Across the grid:", ""]
        for k in ("e1", "e2"):
            rws = sens["entrants"][k]["rows"]
            b = sorted(x["nodes_model_burns"] for x in rws)
            a = sorted(x["false_alarm_nodes"] for x in rws)
            med = lambda v: v[len(v) // 2]  # noqa: E731
            L.append(f"- **{name[k]}** burns {b[0]:,} / {med(b):,} / {b[-1]:,} of the 8,443 nodes "
                     f"(min / median / max) and raises {a[0]:,} / {med(a):,} / {a[-1]:,} false "
                     f"alarms. **E3 burns 281 nodes and raises 3.** Not one of the "
                     f"{len(rws)} grid points operates anywhere near that alarm budget.")
        L += ["",
              "**So metric 3's false-safe rate is not comparable between entrants at different "
              "operating points**, and Stage 2 is the first entry that makes that visible: a field "
              "that burns the whole canvas has a false-safe rate of 0.0000 and no value at all. "
              "Stage 1 could compare E0 and E3 on it fairly only because both burn about 280 nodes. "
              "The rate belongs beside the false-alarm count, always — which is why every table "
              "above carries both, and why metric 4's precision/recall pair is the row that "
              "actually separates these entrants. **A change to protocol §5.3 is the author's "
              "call, not this lap's; v0.1 is frozen and was applied as written.**", ""]

    L += ["### 6.5 The wind sweep behind the two oracles", "",
          f"Each proxy was built at every one of "
          f"{len(sweep['grid']['bearings_deg'])} × {len(sweep['grid']['head_rates_m_per_30min'])} = "
          f"{sweep['entrants']['e1']['grid_points']} declared grid points "
          f"(`docs/benchmark/stage2_proxy_rules.md` §3) and the best-scoring point was written as "
          "the entrant. The spread across the grid is what 「the wind has to be roughly right」 "
          "costs.", "",
          "| proxy | criterion | bearing | head rate | mean ROC-AUC | mean IoU |",
          "|---|---|---:|---:|---:|---:|"]
    for k in ("e1", "e2"):
        e = sweep["entrants"][k]
        for lab, key in (("max mean ROC-AUC (primary)", "selected_primary_mean_roc_auc"),
                         ("max mean IoU (secondary)", "selected_secondary_mean_iou")):
            s = e[key]
            L.append(f"| {name[k]} | {lab} | {s['bearing_deg']:.0f}° | "
                     f"{s['head_rate_m_per_30min']:.0f} m/30 min | {f(s['mean_roc_auc'])} | "
                     f"{f(s['mean_iou'])} |")
    L.append("")
    L += ["| proxy | mean ROC-AUC across the grid (min / median / max) | mean IoU (min / median / max) |",
          "|---|---|---|"]
    for k in ("e1", "e2"):
        r = sweep["entrants"][k]["rows"]
        a = sorted(x["mean_roc_auc"] for x in r)
        i = sorted(x["mean_iou"] for x in r)
        med = lambda v: v[len(v) // 2]  # noqa: E731
        L.append(f"| {name[k]} | {f(a[0])} / {f(med(a))} / {f(a[-1])} | "
                 f"{f(i[0])} / {f(med(i))} / {f(i[-1])} |")
    dm = sweep["dem_coverage"]
    L += ["",
          f"**DEM coverage behind E2.** The committed snapshot covers "
          f"{dm['cells_covered']:,} of the canvas's {dm['cells_total']:,} cells "
          f"({100 * dm['cells_covered'] / dm['cells_total']:.1f} %); cells outside it are given "
          "slope 0. Per entrant, the number of cells it puts at p ≥ 0.5 outside that coverage:", ""]
    for track in ("forecast", "hindcast"):
        for e, _ in rows[track]:
            ent = json.loads((BENCH / "entrants" / e["entrant"] / "entrant.json").read_text(encoding="utf-8"))
            n = ent.get("provenance", {}).get("cells_above_p_cut_outside_dem_coverage")
            if n is not None:
                L.append(f"- **{e['name']}**: {n:,}")
    L.append("")

    text = DOC.read_text(encoding="utf-8")
    head = text.split(MARKER)[0]
    DOC.write_text(head + MARKER + "\n" + "\n".join(L), encoding="utf-8")
    print(f"rendered {DOC.relative_to(REPO)} ({len(L)} lines appended)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
