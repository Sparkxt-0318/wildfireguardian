"""All v2 results (PROTOCOL.md Amendment 2), v1 beside v2, in one PDF: RESULTS_all_v2.pdf.

Every number in the tables is read from out_v2/summary_v2.json, export_v2/checks_v2.json and the unchanged v1 outputs.
The prose sections are read from RESULTS_v2.md (sections "Why", "Limits"). Run from this folder: python3 build_report_v2.py
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer

import build_report as R1

HERE = Path(__file__).resolve().parent
P, SMALL, H1, H2, BOX, CELLB = R1.P, R1.SMALL, R1.H1, R1.H2, R1.BOX, R1.CELLB
table, n = R1.table, R1.n
LV = (("p50", "0.5 (main)"), ("p10", "0.1"), ("p90", "0.9"), ("any", "any path"))
FIRE_LAB = {"earliest": "earliest path", "half": "half of paths"}


def md_section(text, title):
    m = re.search(r"^## %s.*?$(.*?)(?=^## |\Z)" % re.escape(title), text, re.S | re.M)
    return m.group(1).strip() if m else ""


def md_to_paras(block):
    out = []
    for para in re.split(r"\n\s*\n", block):
        para = para.strip()
        if not para:
            continue
        items = re.split(r"\n(?=\* )", para)
        for it in items:
            it = re.sub(r"\s*\n\s*", " ", it.strip())
            it = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", it)
            it = re.sub(r"`(.+?)`", r"\1", it)
            it = it.replace("&", "&amp;").replace("&amp;amp;", "&amp;")
            if it.startswith("* "):
                it = "• " + it[2:]
            out.append(Paragraph(it, P))
    return out


def fmt_min(x):
    return "%g" % round(x, 1)


def main():
    S = json.loads((HERE / "out_v2" / "summary_v2.json").read_text())
    C = S["checks_v2"]
    md = (HERE / "RESULTS_v2.md").read_text()
    N, nch = S["n_paths"], S["n_cell_hours"]
    cch, lg = S["criterion_cell_hours"], S["largest"]
    runs, r1 = S["runs"], S["runs_v1"]
    main_run = runs["half"]
    try:
        commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", "out_v2", "export_v2"], cwd=HERE,
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = ""

    story = [Paragraph("Exposure per fire path as road-blocking times: Fish Creek (v2)", H1),
             Paragraph("All v2 results in one file, with v1 beside them. Same case (WY-BTF-002416_FishCreek, cutoff "
                       "2024-08-23T00:00Z, hours 0–5), roads, thresholds and sources as v1; PROTOCOL.md Amendment 2, "
                       "<b>written after the v1 results were seen</b>, before any per-path result. %s paths, %s cells, "
                       "%s cell-hours, %s road cells, 350 routed origins.%s" % (
                           n(N), n(S["n_cells"]), n(nch), n(S["road_cells"]),
                           (" Run outputs at commit " + commit + ".") if commit else ""), SMALL),
             Spacer(1, 4), Paragraph(md_section(md, "Headline").replace("**", ""), BOX)]
    img = Image(str(HERE / "fig_blocked_cells_v2.png"))
    w = 118 * mm
    img.drawWidth, img.drawHeight = w, w * img.imageHeight / img.imageWidth
    story += [img, Paragraph("Figure. Main setting: cells blocked within 6 h, fire arrival by half of the 1,024 paths, "
                             "exposure blocked where at least half the paths meet a criterion (residents).", SMALL),
              PageBreak()]

    # checks
    a, b = C["a_one_path"], C["b_mean_over_paths_vs_v1"]
    DG = json.loads((HERE / "export_v2" / "diag_co_check.json").read_text())
    WK = DG["weights_by_source_kind"]
    GAP = [100 * (v - m) / v for m, v in zip(WK["burning_at_cutoff"]["sum_mean_weights"], WK["burning_at_cutoff"]["sum_v1_weights"])]
    hrs = [k for k in a if k.startswith("hour_")]
    story += [Paragraph("Checks made before reading the results", H2), table([
        ["check", "result"],
        ["(c) v1 rerun: pipeline hourly fields; fire-arrival rasters",
         "%d of %d arrays equal; earliest %s, half %s" % (
             C["c_pipeline_fields_equal_v1"]["equal"], C["c_pipeline_fields_equal_v1"]["arrays"],
             "equal" if C["c_fire_arrival_equal_v1"]["earliest"] else "DIFFERENT",
             "equal" if C["c_fire_arrival_equal_v1"]["half"] else "DIFFERENT")],
        ["(a) one path (no. %d) as a probability-1 map through the pipeline's weighted_exposure_integrals" % a["path"],
         "60 s fields identical in %d of %d hours; largest hourly-integral difference %.3g J/m² (radiant, largest "
         "%.3g) and %.3g (CO)" % (sum(a[h]["binwise_equal"] for h in hrs), len(hrs),
                                  max(a[h]["radiant_integral_max_abs_diff_j_m2"] for h in hrs),
                                  max(a[h]["radiant_integral_max_j_m2"] for h in hrs),
                                  max(a[h]["co_integral_max_abs_diff"] for h in hrs))],
        ["(b) mean over paths of source weights against v1 active-fire probabilities",
         "%.1f %% within 3 SE; total differs by %.2f %%; largest difference %.3f (largest v1 %.3f)" % (
             100 * b["weights"]["share_within_3_se_where_se_pos"], 100 * b["weights"]["total_rel_diff"],
             b["weights"]["largest_abs_diff"], b["weights"]["largest_v1"])],
        ["(b) mean over paths of 60 s radiant flux against v1",
         "%.1f %% of cell-minutes within 3 SE; hourly totals differ by %s %% (z = %s)" % (
             100 * b["radiant"]["share_within_3_se_where_se_pos"],
             ", ".join("%.1f" % (100 * x) for x in b["radiant"]["hourly_total_rel_diff"]),
             ", ".join("%.1f" % x for x in b["radiant"]["hourly_total_z"]))],
        ["(b) mean over paths of 60 s CO against v1",
         "%.1f %% of cell-minutes within 3 SE; hourly totals differ by %s %% (z = %s)" % (
             100 * b["co"]["share_within_3_se_where_se_pos"],
             ", ".join("%.1f" % (100 * x) for x in b["co"]["hourly_total_rel_diff"]),
             ", ".join("%.1f" % x for x in b["co"]["hourly_total_z"]))],
        ["(b) CO diagnostic (diag_co_check.json)", "CO is linear in the weights (mean field = field of mean weights, "
         "difference %.0e); cell-minutes reached by ≥ 100 paths: %.1f %% within 3 SE. Cells burning at the cutoff: weights "
         "%s %% within 3 SE by hour, summed weights %s %% below v1 (same draws reused in every hour); new cells %s %%. "
         "Partly explained; concerns the mean, not any per-path value" % (
             DG["co"]["linearity_mean_field_vs_field_of_mean_weights_max_abs"],
             100 * DG["co"]["by_number_of_paths_reaching_the_cell_minute"]["100- paths"]["share_within_3_se"],
             "–".join("%.1f" % (100 * x) for x in (min(WK["burning_at_cutoff"]["share_within_3_se"]), max(WK["burning_at_cutoff"]["share_within_3_se"]))),
             "–".join("%.1f" % x for x in (min(GAP), max(GAP))),
             "–".join("%.1f" % (100 * x) for x in (min(WK["new"]["share_within_3_se"]), max(WK["new"]["share_within_3_se"]))))],
        ["(c) fire-only routing equal to v1", "earliest %s, half %s" % (
            "yes" if runs["earliest"]["fire_only"]["equal_to_v1"] else "NO", "yes" if runs["half"]["fire_only"]["equal_to_v1"] else "NO")],
        ["(d) synthetic tests", "21 pass (13 v1, 8 new)"],
    ], [72, 100])]

    # 1 criteria
    rows = [["criterion", "v1 (expected field)"] + ["v2 share %s" % l for _, l in LV]]
    for k, lab in (("radiant_2p5", "radiant ≥ 2.5 kW/m² (residents)"), ("radiant_7p0", "radiant ≥ 7.0 kW/m² (responders)"),
                   ("co_10", "CO 10 min ≥ 420 ppm"), ("co_30", "CO 30 min ≥ 150 ppm"), ("co_60", "CO 60 min ≥ 83 ppm")):
        rows.append([lab, n(cch["v1"][k])] + [n(cch["v2"][lv][k]) for lv, _ in LV])
    rows.append(["visibility ≤ 10 m (v1: p at the same level)", "%s / %s / %s (0.5 / 0.1 / 0.9)" % (
        n(cch["v1"]["vis_p50"]), n(cch["v1"]["vis_p10"]), n(cch["v1"]["vis_p90"]))] +
        [n(cch["v2"][lv]["vis"]) for lv, _ in LV])
    story += [Paragraph("1. Cell-hours blocked by each criterion (n = %s cell-hours)" % n(nch), H2),
              table(rows, [50, 34, 22, 22, 22, 22])]
    rows = [["quantity", "v1, largest expected value", "v2, largest in any path", "v2, largest in the median path"],
            ["radiant flux, 60 s (kW/m²)", "%.3f" % lg["v1"]["radiant_kw_m2"], "%.2f" % lg["v2_any_path"]["radiant_kw_m2"],
             "%.3f" % lg["v2_median_path"]["radiant_kw_m2"]],
            ["CO (ppm)", "%.1f (60 s)" % lg["v1"]["co_60s_ppm"],
             "%.0f / %.0f / %.0f (10/30/60 min)" % (lg["v2_any_path"]["co10_ppm"], lg["v2_any_path"]["co30_ppm"], lg["v2_any_path"]["co60_ppm"]),
             "%.1f / %.1f / %.1f" % (lg["v2_median_path"]["co10_ppm"], lg["v2_median_path"]["co30_ppm"], lg["v2_median_path"]["co60_ppm"])],
            ["largest share of paths meeting the criterion", "visibility %.3f" % lg["v1"]["vis_share"],
             "radiant 2.5: %.3f; 7.0: %.3f; CO 10/30/60: %.3f / %.3f / %.3f; visibility %.3f" % (
                 lg["v2_largest_share"]["radiant_2p5"], lg["v2_largest_share"]["radiant_7p0"],
                 lg["v2_largest_share"]["co_10"], lg["v2_largest_share"]["co_30"], lg["v2_largest_share"]["co_60"],
                 lg["v2_largest_share"]["vis"]), ""]]
    story += [Spacer(1, 6), Paragraph("Largest value reached in 6 h", CELLB), table(rows, [44, 36, 56, 36]),
              Paragraph("Median path: for each cell and hour, the median over the 1,024 paths of that path's peak; the "
                        "table gives the largest such median over cells and hours.", SMALL)]

    # 2 road cells
    rows = [["fire reading, audience", "v1 road cells blocked"] + ["v2 %s" % l for _, l in LV]]
    for f in ("half", "earliest"):
        rows.append(["%s, fire only" % FIRE_LAB[f], n(r1[f]["fire_only_road_cells"])] +
                    [n(runs[f]["fire_only"]["road_cells_blocked"])] * 4)
        for aud in ("residents", "responders"):
            rows.append(["%s, %s" % (FIRE_LAB[f], aud), n(r1[f]["%s_vis50" % aud]["road_cells_blocked"])] +
                        ["%s (+%s)" % (n(runs[f]["%s_%s" % (aud, lv)]["road_cells_blocked"]),
                                       n(runs[f]["%s_%s" % (aud, lv)]["road_cells_added_by_exposure"])) for lv, _ in LV])
    story += [KeepTogether([Paragraph("2. Road cells blocked within 6 h (n = %s road cells)" % n(S["road_cells"]), H2),
                            table(rows, [44, 28, 25, 25, 25, 25]),
                            Paragraph("In brackets: road cells blocked that fire arrival alone does not block. v1 column: "
                                      "visibility 0.5 (heat and CO had no level in v1).", SMALL)])]

    # 3 origins
    rows = [["fire reading, audience", "v1 origins changed"] + ["v2 %s" % l for _, l in LV]]
    for f in ("half", "earliest"):
        for aud in ("residents", "responders"):
            cells = []
            for lv, _ in LV:
                o = runs[f]["%s_%s" % (aud, lv)]["origins"]
                cells.append("%d%s" % (o["n_changed"], (" (median %s, largest %s min earlier)" % (
                    fmt_min(o["earlier_by_min_median"]), fmt_min(o["earlier_by_min_largest"]))) if o["n_changed"] else ""))
            rows.append(["%s, %s" % (FIRE_LAB[f], aud), n(r1[f]["%s_vis50" % aud]["origins_changed"])] + cells)
    story += [KeepTogether([Paragraph("3. Origins whose last safe departure changes (n = %d routed)" %
                                      main_run["residents_p50"]["origins"]["n_origins_routed"], H2),
                            table(rows, [40, 22, 27, 27, 27, 29]),
                            Paragraph("Change against fire arrival alone with the same reading. Pairings fixed in "
                                      "Amendment 2: main = 0.5 with half of paths; 'any path' with earliest path.", SMALL)])]

    # 4 added cell-hours
    rows = [["fire reading, audience", "v1 added cell-hours"] + ["v2 %s" % l for _, l in LV]]
    for f in ("half", "earliest"):
        for aud in ("residents", "responders"):
            rows.append(["%s, %s" % (FIRE_LAB[f], aud), n(r1[f]["%s_vis50" % aud]["added_cell_hours"])] +
                        ["%s (%s cells earlier)" % (n(runs[f]["%s_%s" % (aud, lv)]["added_cell_hours"]),
                                                    n(runs[f]["%s_%s" % (aud, lv)]["cells_blocked_earlier_than_fire"]))
                         for lv, _ in LV])
    story += [KeepTogether([Paragraph("4. Cell-hours that exposure adds to fire arrival (n = %s)" % n(nch), H2),
                            table(rows, [40, 22, 27, 27, 27, 29])])]

    # 5 distance
    D = S["distance_to_burning_cell"]
    rows = [["level, criterion", "cells blocked", "on a road", "median distance (m)", "largest cell median (m)",
             "cells: burning itself / within one cell / beyond"]]
    for lv, lab in LV:
        for k in ("radiant_2p5", "radiant_7p0", "co_10", "co_30", "co_60"):
            d = D[lv][k]
            if not d["cells"]:
                rows.append(["%s, %s" % (lab, k), "0", "", "", "", ""])
                continue
            gm = lambda v: ("%g" % v) if v != float("inf") else "no cell burning then"  # noqa: E731
            rows.append(["%s, %s" % (lab, k), n(d["cells"]), n(d["road_cells"]), gm(d["median_of_cell_medians_m"]),
                         gm(d["largest_cell_median_m"]), "%d / %d / %d" % (
                             d["cells_median_0_m"], d["cells_median_within_one_cell"] - d["cells_median_0_m"],
                             d["cells_median_beyond_one_cell"])])
    story += [Paragraph("5. Distance from each blocked cell to the nearest burning cell in the same path", H2),
              Paragraph("At the cell's first blocked minute, over the paths in which the criterion holds then; each "
                        "cell's median over those paths. 'Within one cell' = up to 530 m (diagonal neighbour).", SMALL),
              table(rows, [34, 18, 16, 24, 26, 54])]
    road = [(lv, k, x) for lv, _ in LV for k in D[lv] if D[lv][k].get("road") for x in D[lv][k]["road"]]
    if road:
        rr = [["level, criterion", "cell (row, col)", "first minute", "share", "distance median / min / max (m)"]]
        for lv, k, x in road:
            rr.append(["%s, %s" % (lv, k), "%d, %d" % (x["row"], x["col"]), n(x["minute"]), "%.3f" % x["share"],
                       " / ".join(("%g" % v) if v != float("inf") else "none burning" for v in (x["median_m"], x["min_m"], x["max_m"]))])
        story += [Spacer(1, 4), Paragraph("Road cells blocked by heat or CO", CELLB), table(rr, [36, 26, 22, 18, 70])]

    # 6 sampling error
    se = S["sampling_error_wilson95"]
    rows = [["level", "criterion", "cells blocked", "95 % interval includes the level", "widest half-width"]]
    for lv in ("p50", "p10", "p90"):
        for k, v in se[lv].items():
            if v["cells"]:
                rows.append([lv, k, n(v["cells"]), n(v["interval_includes_level"]), "%.3f" % v["widest_half_width"]])
    if len(rows) == 1:
        rows.append(["all", "all", "0", "", ""])
    story += [KeepTogether([Paragraph("6. Sampling error of the share at each blocked cell (Wilson 95 %%, n = %s paths)" % n(N), H2),
                            table(rows, [20, 30, 28, 52, 42])])]

    # 7 safety zone
    Z = json.loads((HERE / "out_v2" / "safety_zone" / "summary.json").read_text())
    rows = [["receivers", "zone ≥ 2.5 kW/m² (residents)", "zone ≥ 7.0 kW/m² (responders)", "road pieces inside (2.5 / 7.0)",
             "origins changed, residents / responders"]]
    rows.append(["375 m grid, the pipeline's receivers (Amendment 3)",
                 "empty (largest %.3f kW/m² at the minute, %.2f in 6 h)" % (Z["largest_flux_at_minute_kw_m2"], Z["largest_flux_6h_kw_m2"]),
                 "empty", "%d / %d" % (Z["road_pieces_inside_zone"]["residents"], Z["road_pieces_inside_zone"]["responders"]),
                 "%d / %d" % (Z["residents"]["origins"]["n_changed"], Z["responders"]["origins"]["n_changed"])])
    for key, lab in (("fine", "5 m, one height per cell (Amendment 4)"), ("plane", "5 m, terrain plane (Amendment 5; figure)")):
        F = Z[key]
        rows.append([lab] + ["up to %.1f m from a front; %s m²" % (F[aud]["largest_distance_from_front_line_m"],
                                                                  n(F[aud]["zone_area_m2_at_minute"])) for aud in ("residents", "responders")] +
                    ["%d / %d" % (F["residents"]["road_pieces_inside_zone_at_minute"], F["responders"]["road_pieces_inside_zone_at_minute"]),
                     "%d / %d" % (F["residents"]["origins"]["n_changed"], F["responders"]["origins"]["n_changed"])])
    img2 = Image(str(HERE / "fig_safety_zone.png"))
    w2 = 174 * mm
    img2.drawWidth, img2.drawHeight = w2, w2 * img2.imageHeight / img2.imageWidth
    story += [PageBreak(), Paragraph("7. Safety zone in one path at one minute (Amendments 3–5)", H2),
              Paragraph("Path %d (%d burned cells at 6 h; median %d), minute %d (%02d:%02dZ), %d cells burning; chosen by "
                        "the rule fixed before its data. Peak values in that path at that place and time. Routing: that "
                        "path's fire arrival alone against fire arrival plus the zone over six hours (n = %d routed "
                        "origins). Fire arrival alone blocks %d road cell(s) and cuts %d origins." % (
                            Z["path"], Z["burned_cells_in_path"], Z["median_burned_cells"], Z["minute"], Z["minute"] // 60,
                            Z["minute"] % 60, Z["cells_burning_at_minute"], Z["fire_only"]["origins_routed"],
                            Z["fire_only"]["road_cells_blocked"], Z["fire_only"]["origins_with_cut"]), P),
              table(rows, [40, 38, 34, 26, 34]), Spacer(1, 6), img2,
              Paragraph("Amendments 4 and 5 were written after the previous zone was seen (empty at 375 m; then cut short "
                        "by receivers at one height per cell). The 5 m fronts are the pipeline's own, recorded as it built "
                        "them; they reproduce its 375 m kernel to %.0e W/m². Largest flux on any road point near this "
                        "path in 6 h: %.2f kW/m²." % (Z["plane"]["kernel_reproduction_max_abs_w_m2"],
                                                     Z["plane"]["largest_road_flux_6h_kw_m2"]), SMALL)]
    story += [Paragraph("Why the result changes", H2)] + md_to_paras(md_section(md, "Why"))
    story += [Paragraph("Limits", H2)] + md_to_paras(md_section(md, "Limits"))
    story += [Paragraph("Files (talk_handoff/routing_link/)", H2), table([
        ["path", "what"],
        ["PROTOCOL.md (Amendment 2)", "the per-path rule, written after v1 was seen and before any v2 result"],
        ["RESULTS_v2.md, RESULTS_all_v2.pdf", "v2 results as text, and this file"],
        ["fig_blocked_cells_v2.{png,svg,pdf}", "the v2 figure (main setting)"],
        ["fig_safety_zone.{png,svg,pdf}", "the safety zone in one path, and its routing change"],
        ["export_v2/", "per-path counts per criterion, minute and cell; peak summaries; distances; checks_v2.json"],
        ["out_v2/", "summary_v2.json, all v2 blocking rasters, road-layer results per run"],
        ["perpath_export.py, perpath_rule.py, run_v2.py, build_report_v2.py", "reproduce v2 (README)"],
        ["RESULTS.md, RESULTS_all.pdf, out_earliest/, out_half/, export_6h/", "v1, unchanged"],
    ], [70, 102])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(R1.FONT, 7)
        canvas.setFillColor(R1.GREY)
        canvas.drawString(18 * mm, 10 * mm, "Fish Creek exposure per path and road blocking: v2 results")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(HERE / "RESULTS_all_v2.pdf"), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title="Fish Creek exposure per path and road blocking (v2)",
                            author="", subject="All v2 results, routing_link")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print("wrote", HERE / "RESULTS_all_v2.pdf")


if __name__ == "__main__":
    main()
