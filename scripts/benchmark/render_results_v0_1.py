#!/usr/bin/env python
"""Append §8 of ``docs/benchmark/results_v0.1.md`` from the committed benchmark artifacts.

The repository's rule is that a number in prose traces to an artifact. The way this
repository keeps that true for a results page is the one ``scripts/regrade_three_way.py``
uses: the page's argument is written by hand and frozen, and its numbers are appended by a
script that reads the artifact. Nothing above the marker line is touched.

    python scripts/benchmark/render_results_v0_1.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs/benchmark/results_v0.1.md"
BENCH = REPO / "data/processed/benchmark"
MARKER = "_(appended by `scripts/benchmark/render_results_v0_1.py`; nothing above this line is edited after the run)_"
HORIZON_KEYS = ("180min", "300min", "480min")
HORIZON_LABEL = {"180min": "T0 + 3 h", "300min": "T0 + 5 h", "480min": "T0 + 8 h"}


def f(v, nd=4):
    return "—" if v is None else f"{v:.{nd}f}"


def i(v):
    return "—" if v is None else f"{v:,}"


def main() -> int:
    board = json.loads((BENCH / "leaderboard.json").read_text(encoding="utf-8"))
    rows = {track: [(e, json.loads((BENCH / e["entrant"] / f"{ev}.json").read_text(encoding="utf-8")))
                    for e in entries for ev in e["per_event"]]
            for track, entries in board["tracks"].items()}
    any_ev = next(d for track in rows for _, d in rows[track])

    L: list[str] = ["",
                    f"_Run {board['generated_utc']} at `{board['git_commit'][:7]}`; protocol "
                    f"`{board['protocol_version']}`; scorer `{board['scorer']}`; artifacts "
                    f"`data/processed/benchmark/`; {board['seconds']:.0f} s._", ""]

    L += ["### 8.1 What the observation can and cannot separate", "",
          "Truth on the 영덕 500 m canvas at each horizon, under `docs/regrade_three_way.md` §2 "
          "with *m* = 0. 「unscorable」 is the indeterminate class, which enters neither the AUC "
          "nor the IoU.", "",
          "| horizon | detected cells | indeterminate (unscorable) | not detected |",
          "|---|---:|---:|---:|"]
    for k in HORIZON_KEYS:
        c = any_ev["horizons"][k]["m0"]["cells_by_truth_class"]
        L.append(f"| {HORIZON_LABEL[k]} | {c['detected']:,} | {c['indeterminate']:,} | {c['not_detected']:,} |")
    ops = ", ".join(f"{v:.0f}" for v in any_ev["overpass_times_min"])
    L += ["",
          f"The overpasses are at {ops} minutes after T0. Nothing observes 영덕 between T0 and the "
          "second overpass, so the 3 h and 5 h horizons have **identical truth**, and every cell "
          "first seen at the second overpass is unscorable at both. A score at 3 h in 영덕 is "
          "therefore not evidence about a 3-hour forecast; it is evidence about the T0 footprint. "
          "That is a property of the observation, not of any entrant, and it is the first thing "
          "this benchmark established.", ""]

    L += ["### 8.2 Metrics 1 and 2, by track", "",
          "The two tables are not to be read against each other (protocol §3).", ""]
    for track in ("forecast", "hindcast"):
        if not rows[track]:
            continue
        L += [f"**{track} track**", "",
              "| entrant | horizon | ROC-AUC | IoU at p ≥ 0.5 | predicted positive | unscorable |",
              "|---|---|---:|---:|---:|---:|"]
        for e, d in rows[track]:
            for k in HORIZON_KEYS:
                h = d["horizons"][k]["m0"]
                L.append(f"| {e['name']} | {HORIZON_LABEL[k]} | "
                         f"{f(h['roc_auc'])} | {f(h['iou_at_p_ge_0.5'])} | "
                         f"{h['cells_predicted_positive']:,} | {h['cells_unscorable_indeterminate']:,} |")
        L.append("")

    L += ["### 8.3 Metric 3 — arrival-time error at the road nodes (the one that matters)", "",
          f"Node set: {board['metric3_node_set']['rule']} --- "
          f"{board['metric3_node_set']['n_nodes']:,} nodes, identical for every entrant, with the "
          f"{board['metric3_node_set']['origins_subset_n']}-origin subset reported beside each row. "
          "Cell membership (A5). The window is the "
          "entrant's own last surface; `whole_observation_record` in the artifact repeats every "
          "count against the full observation. Signed error is model minus observation, so "
          "**positive is late** — the direction that strands people.", "",
          "| entrant | track | nodes | observation burns | entrant burns | both | median abs error | "
          "false-safe | false-safe rate | false alarms |",
          "|---|---|---:|---:|---:|---:|---:|---|---:|---:|"]
    for track in ("forecast", "hindcast"):
        for e, d in rows[track]:
            a = d["arrival_time_error"]
            L.append(f"| {e['name']} | {track} | {a['nodes_scanned']:,} | "
                     f"{a['nodes_observation_burns']:,} | {a['nodes_model_burns']:,} | "
                     f"{a['nodes_both_burn']:,} | {f(a['median_abs_error_min'], 1)} min | "
                     f"{a['false_safe_nodes']:,} of {a['nodes_model_calls_safe']:,} | "
                     f"{f(a['false_safe_rate'])} | {a['false_alarm_nodes']:,} |")
    L += ["", "Beside the headline, per entrant:", ""]
    for track in ("forecast", "hindcast"):
        for e, d in rows[track]:
            a = d["arrival_time_error"]
            b, o = a["bilinear_variant"], a["canonical_scan_origins_subset"]
            L.append(f"- **{e['name']}** ({track}): of the "
                     f"{a['nodes_both_burn']:,} nodes both call burned, {a['nodes_model_late']:,} are "
                     f"late, {a['nodes_model_early']:,} early and {a['nodes_model_exact']:,} exact; "
                     f"{a['nodes_observation_indeterminate_at_window']:,} more nodes are "
                     f"indeterminate at the window and are charged to neither side. "
                     f"{a['nodes_called_safe_with_nonzero_p_at_last_surface']:,} of the nodes it "
                     f"calls safe still carry a non-zero probability at its last surface "
                     f"({a['last_surface_min']:.0f} min), so C1's clamp may be hiding a later "
                     f"crossing for them. Read through the router's bilinear sampler instead of "
                     f"cell membership the false-safe count is {b['false_safe_nodes']:,} of "
                     f"{b['nodes_model_calls_safe']:,}; on the {o['nodes_scanned']:,}-origin "
                     f"subset it is {o['false_safe_nodes']:,} of {o['nodes_model_calls_safe']:,}.")
    cc = any_ev["arrival_time_error"]["cell_coverage"]
    L += ["",
          f"**Why the two entrants land within three nodes of each other.** The canonical walk "
          f"network touches {cc['cells_with_a_road_node']:,} of the canvas's "
          f"{cc['cells_total']:,} cells, so most of the map has no road node in it at all. "
          f"Per entrant, of the cells it calls burned within its horizon:", ""]
    for track in ("forecast", "hindcast"):
        for e, d in rows[track]:
            c = d["arrival_time_error"]["cell_coverage"]
            L.append(f"- **{e['name']}**: {c['cells_entrant_burns']:,} cells, of which "
                     f"{c['cells_entrant_burns_with_a_road_node']:,} contain a road node, holding "
                     f"{c['road_nodes_in_cells_entrant_burns']:,} nodes. The observation burns "
                     f"{c['cells_observation_burns_in_window']:,} cells in the same window, of which "
                     f"{c['cells_observation_burns_in_window_with_a_road_node']:,} contain a road "
                     f"node, holding {c['road_nodes_in_cells_observation_burns_in_window']:,}.")
    L.append("")

    m4 = [(track, e, d) for track in ("forecast", "hindcast") for e, d in rows[track]
          if "not_run" not in d["decision_shift"]]
    L += ["### 8.4 Metric 4 — decision shift (영덕 주건물)", ""]
    if not m4:
        L += ["Not run in this pass. `score_kspread.py --with-decision-shift` computes it.", ""]
    else:
        L += ["Buildings whose last-safe-departure class differs between the entrant's field and "
              "the observation-graded field, under the committed time-aware policy with only the "
              "field changed. ⚠ Both sweeps read their field through the router's **bilinear** "
              "sampler, which on a binary footprint is the softer reading "
              "(`docs/regrade_three_way.md` §A5, §6); metrics 1–3 do not.", "",
              "| entrant | track | buildings scored | class changed | entrant more optimistic |",
              "|---|---|---:|---:|---:|"]
        for track, e, d in m4:
            s = d["decision_shift"]
            L.append(f"| {e['name']} | {track} | {s['buildings_scored']:,} | "
                     f"{s['buildings_class_changed']:,} | {s['buildings_entrant_more_optimistic']:,} |")
        L.append("")
        closes = ("closes_before_5h", "closes_after_5h")
        for track, e, d in m4:
            s = d["decision_shift"]
            tr = s["lsd_class_buildings_truth"]
            truth_closing = sum(tr.get(c, 0) for c in closes)
            tab = s["class_table_entrant_given_truth"]
            flagged = sum(w for k, w in tab.items() if k.split("|")[0] in closes)
            caught = sum(w for k, w in tab.items()
                         if k.split("|")[0] in closes and k.split("|")[1] in closes)
            exact = sum(w for k, w in tab.items()
                        if k.split("|")[0] in closes and k.split("|")[0] == k.split("|")[1])
            L.append(f"- **{e['name']}**: the observation-graded field says "
                     f"{truth_closing:,} buildings have a window that closes inside 600 min; this "
                     f"entrant flags {flagged:,} as closing, of which {caught:,} do "
                     f"({exact:,} in exactly the right class). Entrant classes "
                     f"{s['lsd_class_buildings_entrant']}; observation-graded classes {tr}.")
        L.append("")

    L += ["### 8.5 What could not be run", "",
          "| protocol item | why |", "|---|---|"]
    for ev, why in sorted(board["events_unscorable"].items()):
        L.append(f"| event {ev} | {why} in this repository |")
    for track in ("forecast", "hindcast"):
        for e, _ in rows[track]:
            for ev, why in sorted(e["events_not_scored"].items()):
                if ev not in board["events_unscorable"]:
                    L.append(f"| {e['protocol_entrant']} on {ev} | {why} |")
    L += ["| entrants E1, E2, E4 | 임상도 1:5000 and KMA station data absent from `data/raw/`, no `MANIFEST.json` |",
          "| entrant E5 | the 정보공개청구 to 국립산림과학원 has not returned |",
          "| protocol §5 mean and worst event | one event scored; a mean over one event is that event |",
          ""]

    text = DOC.read_text(encoding="utf-8")
    head = text.split(MARKER)[0] + MARKER
    DOC.write_text(head + "\n" + "\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote §8 of {DOC.relative_to(REPO)} ({len(L)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
