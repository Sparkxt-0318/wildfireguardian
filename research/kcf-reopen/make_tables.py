"""Markdown tables for RESULTS.md from out/ (no number typed by hand). Usage: python3 -I make_tables.py > out/tables.md"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
VN = {"M0": "no margin", "M30": "30-min card margin", "MR": "spread margin R(h)", "MR_running": "running-class R(h)"}
RN = {"perm": "permanent (kcf-camp)", "w105": "window, τ 105", "w240": "**window, τ 240 (frozen)**", "w465": "window, τ 465",
      "res240": "residents, confirmed only, τ 240", "nbr240": "window τ 240, neighbour arrival (exploratory)"}
RULES = list(RN)


def ci(c):
    return "%.2f–%.2f" % tuple(c) if c and c[0] is not None else "n/a"


tau = json.load(open(OUT / "tau.json"))
print("### Step 1: burn-out time from the Camp Fire workbook (per road cell, minutes after first fire evidence)\n")
print("| quantity | cells | min | p25 | median | p75 | p80 | p90 | p95 | max |")
print("|---|---|---|---|---|---|---|---|---|---|")
for k, lab in (("g_block_all", "last blocked report (all cells with one)"), ("g_block_positive", "last blocked report, blocked again after first fire (**sets τ**)"),
               ("g_open", "first passable or vehicle-present after first fire"), ("g_open_passable_only", "same, cells with a passable report"),
               ("g_open_after_block", "first passable or vehicle-present after the last blocked report")):
    d = tau[k]
    print("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (lab, d["n"], d["min"], d["p25"], d["median"], d["p75"], d["p80"], d["p90"], d["p95"], d["max"]))
f = tau["frozen"]
b = tau["bracketed_cells"]
print("\nFrozen (PROTOCOL §2.2): **τ = %d min**, low %d, high %d (n = %d cells). Cross-fit halves: west %d, east %d min. "
      "Cells with both a last blocked report and later open evidence: %d; the open evidence came before 240 min in %d of them, "
      "the bracket contains 240 in %d, lies above it in %d.\n" % (
          f["tau_min"], f["tau_low_min"], f["tau_high_min"], f["n"], tau["crossfit"]["halves"]["west"]["tau_min"], tau["crossfit"]["halves"]["east"]["tau_min"],
          len(b), sum(1 for x in b if x["hi_min"] <= 240), sum(1 for x in b if x["lo_min"] <= 240 < x["hi_min"]), sum(1 for x in b if x["lo_min"] > 240)))

T = json.load(open(OUT / "camp_tests12.json"))
M = json.load(open(OUT / "camp_test41_movements.json"))
print("### Test 4.1: the two documented movements (2 h horizon, dwell 120 s)\n")
print("| movement, issue | variant | rule | road cells closed / reopening within 2 h / burned over at issue | origin closed (s after issue) | feasible at issue | departures feasible (s) | route at issue: share on documented roads (incl. OSM 'New Skyway') | pass |")
print("|---|---|---|---|---|---|---|---|---|")
for c in M["cases"]:
    for v in ("M0", "MR"):
        for r in ("perm", "w105", "w240", "w465", "res240", "nbr240"):
            x = c["variants"]["%s_%s" % (v, r)]
            ri = x.get("route_at_issue") or {}
            S = x["issue_set_s"]
            sets = "; ".join("%s–%s" % (a, b) for a, b in S) if S else "none"
            share = ("%.0f%% (%.0f%%)" % (100 * ri["share_on_documented"], 100 * ri["share_incl_osm_alias"])) if ri else "—"
            print("| (%s) %s | %s | %s | %d / %d / %d | %s | %s | %s | %s | %s |" % (
                c["movement"], c["issue"], VN[v], RN[r], x["closed_cells"], x["reopening_cells_within_H"], x["burned_over_at_issue"],
                "; ".join("%s–%s" % tuple(w) for w in x["origin_window_s"]) or "open", "yes" if x["feasible_at_issue"] else "**no**", sets, share,
                "PASS" if x["pass"] else "FAIL"))
print("\nWitness routes checked by research/kcf-theorem/checker.py: %d, invalid %d.\n" % (M["witness_checks"]["witnesses"], M["witness_checks"]["invalid"]))

for key, title in (("t42_passable", "Test 4.2a: the 23 passable reports (state at the reported time, ±15 min)"),
                   ("t42_vehicle", "Test 4.2b: vehicle-present observations (AVL-located rows on a road cell; one field per row)")):
    print("### %s\n" % title)
    print("| variant | rule | open | burned over | closed | closed share (95% CI) | distinct cells (not closed) | verdict (closed ≤ 20 %) |")
    print("|---|---|---|---|---|---|---|---|")
    for v in ("M0", "MR", "MR_running"):
        for r in RULES:
            x = T[key]["%s_%s" % (v, r)]
            print("| %s | %s | %d | %d | %d | %.0f%% (%s) | %d (%d) | **%s** |" % (VN[v], RN[r], x["open"], x["burned_over"], x["closed"], 100 * x["closed_share"],
                                                                         ci(x["closed_ci95"]), x["distinct_cells"], x["distinct_cells_not_closed"], x["verdict"]))
    print()
print("Vehicle-present rows by their own class (spread margin, frozen τ): " + "; ".join(
    "%s %d of %d closed" % (c, v["MR_w240"]["closed"], v["MR_w240"]["n"]) for c, v in T["t42_vehicle_by_class"].items()) + ".\n")

print("### Test 4.3a: guard, the 195 road-blocked reports\n")
print("| variant | rule | hits | hits under permanent closure | reopened too early | verdict (no loss) |")
print("|---|---|---|---|---|---|")
for v in ("M0", "MR", "MR_running"):
    for r in RULES:
        x = T["t43_blocked"]["%s_%s" % (v, r)]
        print("| %s | %s | %d / %d | %d | %d | **%s** |" % (VN[v], RN[r], x["hits"], x["n"], x["hits_perm"], x["reopened_too_early"], x["verdict"]))
print("\nCross-fit (each half scored with the other half's τ, %s): reopened too early %s.\n" % (
    T["t43_crossfit"]["MR"]["tau_used"], ", ".join("%s %d" % (VN[v], T["t43_crossfit"][v]["reopened_too_early"]) for v in ("M0", "MR"))))
print("### Test 4.3b: guard, the 23 burnovers (closed or inside the 30-min margin)\n")
print("| variant | rule | at t − 60 | at t − 30 | at t | permanent (t − 60 / t − 30 / t) | burnovers lost | verdict (no loss) |")
print("|---|---|---|---|---|---|---|---|")
for v in ("M0", "MR", "MR_running"):
    for r in RULES:
        x = T["t43_burnovers"]["%s_%s" % (v, r)]
        d, p = x["closed_or_unsafe"], x["perm"]
        print("| %s | %s | %d | %d | %d | %d / %d / %d | %s | **%s** |" % (VN[v], RN[r], d["t-60"], d["t-30"], d["t"], p["t-60"], p["t-30"], p["t"],
                                                                  ", ".join("BO %s" % b for b in x["lost_burnovers"]) or "none", x["verdict"]))
print()

K = json.load(open(OUT / "korea_reopen.json"))
print("### Step 5: Korean expressway sections, traffic return (15-min VDS) and model reopening (KST)\n")
print("| official closure | section | km (share in lattice) | cells with fire (discs) | fire on section, first – last | official reopening message | traffic returned (median, n conzone-dirs) | model reopen τ 105 / 240 / 465 | model − traffic at τ 240, min | Choi: model reopen, − traffic | closed spell at closure → ends, − traffic (secondary) |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for r in K["rows"]:
    print("| %s | %s | %s (%s) | %d / %d | %s – %s | %s | %s (%d) | %s / %s / %s | %s | %s, %s | %s %s |" % (
        r["official_closure_kst"], r["section"], r["length_km"], r["share_of_length_in_lattice"], r["cells_with_fire_disc"], r["lattice_cells"],
        r["fire_first_kst"], r["fire_last_kst"], r["official_reopen_message_kst"] or "—", r["traffic_return_median_kst"] or "none", r["traffic_conzone_directions"],
        r["model_reopen_low_kst"], r["model_reopen_frozen_kst"], r["model_reopen_high_kst"], r["model_minus_traffic_frozen_min"],
        r["choi_model_reopen_frozen_kst"], r["choi_model_minus_traffic_frozen_min"], r["episode_model_state_at_closure"],
        ("→ %s, %s" % (r["episode_model_reopen_kst"], r["episode_model_minus_traffic_min"])) if r["episode_model_reopen_kst"] else ""))
print("\nFire-disc record ends %s KST; fire that first reached a cell later is not in the discs.\n" % K["disc_record_ends_kst"])

R = OUT / "robust_window.json"
if R.exists():
    W = json.load(open(R))
    NM = {"a": "CURRENT", "b": "TIME-ROBUST", "c": "REACH-ROBUST", "d": "FASTEST", "e": "FORECAST-AWARE"}
    for kind in ("twin", "replay"):
        if kind not in W:
            continue
        w = W[kind]
        print("### Step 6: kcf-robust's comparison with responder windows, %s (%d cases)\n" % (kind, w["cases"]))
        print("| rule | failed evacuations / advised | missed cut-offs / true cut | false cut-offs / true not cut | lead time given up, median (min) | failed − CURRENT (95% CI) |")
        print("|---|---|---|---|---|---|")
        for k in "abcde":
            s = w["summary_window"][k]
            bt = w["bootstrap_window"]["diff_vs_a"].get(k)
            print("| %s. %s | %d / %d | %d / %d | %d / %d | %s | %s |" % (k, NM[k], s["failed"], s["advised"], s["missed"], s["true_cut"], s["false"], s["true_not_cut"],
                                                                 "%.1f" % s["lead_median_min"] if s["lead_median_min"] is not None else "n/a",
                                                                 ("%+d [%+d, %+d]" % (bt["failed_diff_point"], bt["failed_diff_ci95"][0], bt["failed_diff_ci95"][1])) if bt else "—"))
        p = w["a_perm_vs_perm_truth"]
        print("\nCURRENT with permanent closures against the permanent truth (reproduction check): failed %d / %d, missed %d / %d, false %d / %d.\n" % (
            p["failed"], p["advised"], p["missed"], p["true_cut"], p["false"], p["true_not_cut"]))
        print("Margin field vs plain slack at departure 0 (per place and shelter, feasible at 0):\n")
        print("| closures | pairs | margin = slack | margin = horizon cap | differ | margin below slack | largest difference (s) |")
        print("|---|---|---|---|---|---|---|")
        for m, lab in (("a_perm", "permanent"), ("a", "responder windows")):
            x = w["margin_vs_slack"][m]
            print("| %s | %d | %d | %d | %d | %d | %d |" % (lab, x["pairs_feasible_at_0"], x["mu0_eq_L0"], x["mu0_eq_M"], x["differ"], x["mu0_below_L0"], x["max_abs_diff_s"]))
        lw = w["later_windows"]
        print("\nStep 7, later windows (rule CURRENT): %d place-issues (%d places)." % (lw["place_issues"], lw["places"]))
        for k, lab in (("a", "responders"), ("a_res", "residents (confirmed only)")):
            if k in lw:
                x = lw[k]
                print("* %s: %d place-issues gain a later window (%d places); %d place-issues with more than one window; %d gain a departure where there was none; median gain %s min." % (
                    lab, x["place_issues_with_later_window"], x["places_with_later_window"], x["place_issues_with_more_than_one_window"],
                    x["place_issues_gaining_any_departure"], "%.0f" % x["median_gain_min"] if x["median_gain_min"] is not None else "n/a"))
        print()
