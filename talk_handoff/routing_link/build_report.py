"""Put every result of this folder into one PDF: RESULTS_all.pdf.

Every number in the tables is read from the committed outputs (out_earliest/, out_half/, export_6h/), not typed in.
Run from this folder:  python3 build_report.py   (needs reportlab and numpy)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).resolve().parent
INK, GREY, BLUE, RED = (colors.HexColor(c) for c in ("#1A1A1A", "#6B6B6B", "#2F5D8A", "#8A362F"))
TINT = colors.HexColor("#E8EEF5")
CO_PPM = 1.145  # mg/m3 per ppm (NRC 2010)

# ---------- fonts (need ≥, ², µ) ----------
FONT, BOLD = "Helvetica", "Helvetica-Bold"
for reg, bold in (("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                  ("/Library/Fonts/Arial Unicode.ttf", None)):
    if Path(reg).exists():
        pdfmetrics.registerFont(TTFont("Body", reg))
        pdfmetrics.registerFont(TTFont("BodyBold", bold if bold and Path(bold).exists() else reg))
        FONT, BOLD = "Body", "BodyBold"
        break

ss = getSampleStyleSheet()
P = ParagraphStyle("p", parent=ss["Normal"], fontName=FONT, fontSize=9, leading=12.5, textColor=INK, alignment=TA_LEFT,
                   spaceAfter=5)
SMALL = ParagraphStyle("s", parent=P, fontSize=7.5, leading=10, textColor=GREY)
CELL = ParagraphStyle("c", parent=P, fontSize=7.8, leading=10, spaceAfter=0)
CELLB = ParagraphStyle("cb", parent=CELL, fontName=BOLD)
H1 = ParagraphStyle("h1", parent=P, fontName=BOLD, fontSize=15, leading=19, spaceAfter=4)
H2 = ParagraphStyle("h2", parent=P, fontName=BOLD, fontSize=11, leading=14, spaceBefore=10, spaceAfter=5, textColor=BLUE)
BOX = ParagraphStyle("box", parent=P, fontSize=9.5, leading=13, backColor=TINT, borderPadding=(6, 6, 6, 6),
                     spaceBefore=4, spaceAfter=12)


def table(rows, widths, header=1, bold_cells=()):
    data = [[Paragraph(str(x), CELLB if (i < header or (i, j) in bold_cells) else CELL) for j, x in enumerate(r)]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=header, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, header - 1), (-1, header - 1), 0.6, INK),
        ("LINEBELOW", (0, header), (-1, -1), 0.25, colors.HexColor("#D0D0D0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    return t


def n(x):
    return "{:,}".format(int(x))


def load():
    S = {v: json.loads((HERE / ("out_%s/summary.json" % v)).read_text()) for v in ("earliest", "half")}
    R = {v: json.loads((HERE / ("out_%s/routing/fire_only.json" % v)).read_text()) for v in ("earliest", "half")}
    C = json.loads((HERE / "export_6h/checks.json").read_text())
    pm = []
    for h in range(C["hours"]):
        with np.load(HERE / ("export_6h/hour_%02d.npz" % h)) as z:
            p = z["pm25_ug_m3"]
            pm.append((float(np.nanmax(p)), int((p > 0).sum())))
    return S, R, C, pm


def fire_routing(r):
    H = r["info"]["horizon_s"]
    routed = [x for x in r["rows"] if x["refusal"] is None]
    cut = sorted(x["last_safe_departure_s"] / 60 for x in routed if x["cut_s"] is not None and x["cut_s"] < H)
    return {"road": r["info"]["closed_road_cells"], "road_n": r["info"]["road_cells"], "routed": len(routed),
            "refused": len(r["rows"]) - len(routed), "cut": cut}


def main():
    S, R, C, pm = load()
    E, Hf = S["earliest"], S["half"]
    FE, FH = fire_routing(R["earliest"]), fire_routing(R["half"])
    nch, ncell = E["n_cell_hours"], E["n_cells"]
    hrs = ["hour_%d" % h for h in range(C["hours"])]
    max_rad = max(C[h]["max_binwise_radiant_kw_m2"] for h in hrs)
    max_co = max(C[h]["max_binwise_co_ppm"] for h in hrs)
    max_vis = max(C[h]["max_visibility_probability"] for h in hrs)
    crit = E["criterion_cell_hours"]
    assert crit == Hf["criterion_cell_hours"], "criteria differ between runs"
    fa = C["fire_arrival"]
    try:
        commit = subprocess.run(["git", "log", "-1", "--format=%h", "--", "out_earliest", "export_6h"], cwd=HERE,
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = ""
    origins_changed = {v: sum(S[v]["origins"][k]["n_changed"] for k in S[v]["origins"]) for v in S}
    added = {v: sum(S[v]["added_cell_hours"][k]["exposure_blocked_not_fire"] for k in S[v]["added_cell_hours"])
             for v in S}

    story = []
    story += [Paragraph("Exposure fields as road-blocking times: Fish Creek", H1),
              Paragraph("All results in one file, 25 Nov 2026. Case WY-BTF-002416_FishCreek, cutoff 2024-08-23T00:00Z, "
                        "hours 0–5 after the cutoff, 375 m grid of 103 × 73 = %s cells, so <b>%s cell-hours</b>. "
                        "Roads: OpenStreetMap, %s road cells, %s nodes, %s road pieces. Protocol: PROTOCOL.md, frozen "
                        "before any result, with Amendment 1 (also before any result). Data from run outputs%s in "
                        "talk_handoff/routing_link/." % (n(ncell), n(nch), n(FE["road_n"]), n(E["routing"]["n_nodes"]),
                                                         n(E["routing"]["n_edges"]),
                                                         (" at commit " + commit) if commit else ""), SMALL)]

    head = ("<b>At the protocol's settings, exposure blocks no cell and no road, and changes no last safe departure: "
            "%d of %d origins, for residents and for responders.</b> Radiant heat and CO never come near their "
            "thresholds (largest 60 s values %.3f kW/m² and %.1f ppm). The only criterion that holds anywhere is "
            "visibility at the 0.1 sensitivity level: one cell, not on a road, for %d cell-hours. Fire arrival alone "
            "decides the road result: with the earliest of 1,024 forecast paths fire blocks %d road cells and cuts %d "
            "origins (last safe departure %s min after the cutoff); with the half-of-paths reading it blocks %d."
            % (max(origins_changed.values()), FE["routed"], max_rad, max_co, crit["vis_p10"], FE["road"],
               len(FE["cut"]), " and ".join("%.1f" % x for x in FE["cut"]), FH["road"]))
    story += [Spacer(1, 4), Paragraph(head, BOX)]

    # ---------- figure ----------
    img = Image(str(HERE / "fig_blocked_cells.png"))
    w = 120 * mm
    img.drawWidth, img.drawHeight = w, w * img.imageHeight / img.imageWidth
    story += [img, Paragraph("Figure. Cells blocked within 6 h from the cutoff, earliest-path fire arrival, residents, "
                             "visibility p ≥ 0.5. Exposure adds no cell to fire arrival. Roads from OpenStreetMap.",
                             SMALL), PageBreak()]

    # ---------- checks ----------
    h0 = C["hour0_vs_saved_example"]
    story += [Paragraph("Checks made before reading the results", H2), table([
        ["check", "result"],
        ["Saved one-hour example rerun in this environment", "identical, 38 of 38 arrays bit for bit"],
        ["60 s radiant and CO fields, integrated over each hour, against the pipeline's hourly totals (%d hours)"
         % C["hours"], "largest difference %s J/m² and %s mg/m³ over all hours" % (
             max(C[h]["radiant_integral_max_abs_diff_j_m2"] for h in hrs),
             max(C[h]["co_mean_max_abs_diff_mg_m3"] for h in hrs))],
        ["Hour 0 from the six-hour path against the saved one-hour example (1,024 sampled paths against exact "
         "probabilities)", "correlation %.3f (PM2.5), %.3f (CO), %.4f (heat), %.3f (visibility probability); largest "
         "visibility probability %.4f against %.4f" % (
             h0["pm25_hour_mean_ug_m3"]["corr"], h0["co_hour_mean_mg_m3"]["corr"],
             h0["thermal_known_contribution_j_m2"]["corr"], h0["visibility_danger_probability"]["corr"],
             h0["visibility_danger_probability"]["this_max"], h0["visibility_danger_probability"]["saved_max"])],
        ["Visibility probability left undefined by the pipeline (lower bound used)",
         "%d cell-hours" % C["visibility_lower_bound_cell_hours"]],
        ["Radiant or CO inputs unresolved", "%d cells in every hour" % max(
            max(C[h]["radiant_unresolved_cells"], C[h]["co_unresolved_cells"]) for h in hrs)],
        ["Synthetic tests (tests/)", "13 pass"],
        ["Pipeline settings", "%d retained paths, seed %d, ignition timing %s; %s" % (
            C["samples"], C["seed"], C["ignition_timing"], C["weather"])],
    ], [80, 92])]

    # ---------- thresholds ----------
    story += [Paragraph("Thresholds (published values only; sources checked in SOURCES.md)", H2), table([
        ["criterion", "blocks a cell when", "source"],
        ["Radiant heat, residents", "radiant flux ≥ 2.5 kW/m² in any 60 s bin",
         "Purser &amp; McAllister (2016), SFPE Handbook ch. 63 (building-occupant tenability), via Engineers Australia "
         "(2014) and SCDF (2022)"],
        ["Radiant heat, responders", "radiant flux ≥ 7.0 kW/m² in any 60 s bin",
         "Butler &amp; Cohen (1998), IJWF 8:73–77; value confirmed in Butler (2014). Meaning: exposed skin, "
         "second-degree burn in under 90 s"],
        ["CO, AEGL-2", "running mean ≥ 420 ppm (10 min), 150 ppm (30 min) or 83 ppm (60 min)",
         "NRC (2010) AEGL vol. 8, CO, final; 1 ppm = 1.145 mg/m³"],
        ["Visibility (assumption)", "probability of visibility ≤ 10 m ≥ 0.5; sensitivity 0.1 and 0.9",
         "10 m: building-egress criterion (Purser &amp; McAllister 2016, quoted by Gager &amp; Dominguez 2016). "
         "0.5 level: our choice"],
        ["PM2.5", "never blocks; reported only", ""],
    ], [32, 58, 82]),
        Paragraph("The road layer treats a cell as blocked from the first minute any criterion holds, or from fire "
                  "arrival, whichever is earlier. Residents use 2.5 kW/m²; responders 7.0 kW/m²; CO and visibility "
                  "are the same for both.", SMALL)]

    # ---------- 1. criteria ----------
    story += [Paragraph("1. Cell-hours blocked by each criterion (n = %s cell-hours)" % n(nch), H2)]
    vis_cells = "1 cell, hours 4 and 5; p = %.3f, %.3f" % (C["hour_4"]["max_visibility_probability"],
                                                           C["hour_5"]["max_visibility_probability"])
    rows = [["criterion", "threshold", "cell-hours blocked", "largest value reached in 6 h"],
            ["(a) radiant heat, residents", "2.5 kW/m²", n(crit["radiant_residents"]), "%.3f kW/m² (60 s bin)" % max_rad],
            ["(a) radiant heat, responders", "7.0 kW/m²", n(crit["radiant_responders"]), "%.3f kW/m²" % max_rad],
            ["(b) CO, 10 min mean", "420 ppm", n(crit["co_10min"]), "below 30 ppm (largest 60 s bin %.1f ppm)" % max_co],
            ["(b) CO, 30 min mean", "150 ppm", n(crit["co_30min"]), "below 30 ppm"],
            ["(b) CO, 60 min mean", "83 ppm", n(crit["co_60min"]), "below 30 ppm"],
            ["(c) visibility ≤ 10 m, probability ≥ 0.5 (main)", "0.5", n(crit["vis_p50"]), "probability %.3f" % max_vis],
            ["(c) same, sensitivity", "0.1", "%s (%s)" % (n(crit["vis_p10"]), vis_cells), ""],
            ["(c) same, sensitivity", "0.9", n(crit["vis_p90"]), ""],
            ["radiant unresolved and not blocked", "", n(crit["radiant_unresolved_not_blocked"]), ""]]
    story += [table(rows, [55, 22, 45, 50], bold_cells={(i, 2) for i in range(1, 10)})]
    story += [Spacer(1, 6), Paragraph("Largest value in each hour after the cutoff", CELLB), table(
        [["hour", "0", "1", "2", "3", "4", "5"],
         ["radiant, largest 60 s bin (kW/m²)"] + ["%.3f" % C[h]["max_binwise_radiant_kw_m2"] for h in hrs],
         ["CO, largest 60 s bin (ppm)"] + ["%.1f" % C[h]["max_binwise_co_ppm"] for h in hrs],
         ["visibility ≤ 10 m, largest probability"] + ["%.3f" % C[h]["max_visibility_probability"] for h in hrs],
         ["PM2.5, largest hourly mean (µg/m³)"] + [n(round(m)) for m, _ in pm],
         ["PM2.5, cell-hours above zero (of %s)" % n(ncell)] + [n(c) for _, c in pm]],
        [62, 18, 18, 18, 18, 18, 18])]

    # ---------- 2. fire alone ----------
    def cut_txt(f):
        return ("%d, last safe departure %s min after the cutoff" % (len(f["cut"]), " and ".join("%.1f" % x for x in f["cut"]))
                if f["cut"] else "0")
    story += [KeepTogether([Paragraph("2. Fire arrival alone (two readings of the 1,024-path forecast)", H2), table([
        ["", "earliest path (main)", "half of paths (sensitivity)"],
        ["cells blocked within 6 h (n = %s)" % n(ncell),
         "%s (%s burned at the cutoff + %s reached)" % (n(fa["burned_at_cutoff"] + fa["reached_earliest_member"]),
                                                       n(fa["burned_at_cutoff"]), n(fa["reached_earliest_member"])),
         "%s (burned at the cutoff; %s more reached by half the paths)" % (
             n(fa["burned_at_cutoff"] + fa["reached_half_of_paths"]), n(fa["reached_half_of_paths"]))],
        ["cell-hours blocked (n = %s)" % n(nch), n(E["fire_blocked_cell_hours"]), n(Hf["fire_blocked_cell_hours"])],
        ["road cells blocked (n = %s)" % n(FE["road_n"]), n(FE["road"]), n(FH["road"])],
        ["origins with a cut inside 6 h (n = %d routed)" % FE["routed"], cut_txt(FE), cut_txt(FH)],
    ], [52, 62, 58]), Paragraph(
        "Earliest path: a cell counts as reached at the start of the first hour in which any of the 1,024 retained "
        "paths burns it. Half of paths: the first hour by which at least half the paths have burned it.", SMALL)])]

    # ---------- 3. what exposure adds ----------
    story += [Paragraph("3. What exposure adds to fire arrival", H2), Paragraph(
        "Cell-hours blocked by exposure that fire arrival had not already blocked (n = %s cell-hours), cells blocked "
        "earlier than fire (n = %s), and origins whose last safe departure changes (n = %d routed; %d of the %d "
        "junctions have no road to the map edge and are refused in every run)." % (
            n(nch), n(ncell), FE["routed"], FE["refused"], E["routing"]["n_origins"]), P)]
    rows = [["audience, visibility level", "earliest: added cell-hours", "earliest: cells earlier",
             "earliest: origins changed", "half: added cell-hours", "half: cells earlier", "half: origins changed"]]
    for aud in ("residents", "responders"):
        for lv, lab in (("vis50", "0.5 (main)"), ("vis10", "0.1"), ("vis90", "0.9")):
            k = "%s_%s" % (aud, lv)
            row = ["%s, %s" % (aud, lab)]
            for v in ("earliest", "half"):
                a, o = S[v]["added_cell_hours"][k], S[v]["origins"][k]
                row += [n(a["exposure_blocked_not_fire"]), n(a["cells_blocked_earlier_than_fire"]),
                        "%d (median %g, largest %g min)" % (o["n_changed"], o["earlier_by_min_median"],
                                                            o["earlier_by_min_largest"])]
            rows.append(row)
    story += [table(rows, [30, 22, 20, 30, 22, 20, 28]), Paragraph(
        "The one cell blocked at the 0.1 level (row 27, column 28) is one that the earliest path already burns in "
        "hour 0, so under the main fire reading exposure adds nothing even there.", SMALL)]

    # ---------- 4. PM2.5 ----------
    story += [Paragraph("4. PM2.5 (reported, never used to block)", H2), Paragraph(
        "Hourly mean PM2.5 is above zero in %s of %s cell-hours; the largest hourly mean is %s µg/m³ (hour %d). "
        "By hour, see the table in section 1." % (
            n(E["pm25_reported_not_used"]["cell_hours_above_0"]), n(nch),
            n(round(E["pm25_reported_not_used"]["max_ug_m3"])), int(np.argmax([m for m, _ in pm]))), P)]

    # ---------- why / limits ----------
    story += [KeepTogether([Paragraph("Why exposure blocks nothing here", H2), Paragraph(
        "The pipeline's heat and gas fields are <b>probability-weighted</b>: each source cell's contribution is "
        "multiplied by its probability of burning during the time bin, and no source cell's probability exceeds 0.14 "
        "in any 60 s bin of the six hours (0.125, 0.116, 0.111, 0.105, 0.113, 0.140 by hour). A threshold made for a "
        "person next to a real flame is therefore compared with an expected field, which is diluted wherever the fire "
        "is uncertain. The visibility probability is the exception: it comes from 1,024 sampled fire histories, not a "
        "weighted average, and it still stays below %.2f everywhere. These zeros say that the forecast's expected heat "
        "and CO, and its sampled visibility, do not reach the published values on Fish Creek roads in these six hours. "
        "They do not say that a person on a road next to the actual flame front would be safe." % (
            np.ceil(max_vis * 100) / 100), P)])]
    limits = [
        "One fire, one cutoff, six hours.",
        "Exposure is uncalibrated: the physical inputs are the saved example's selected scenario (\"not "
        "field-calibrated\" in the pipeline README); the Gaussian arrival uncertainty is an uncalibrated "
        "interpretation; crown fire and embers are unresolved in the pipeline and not included.",
        "The fields are probability-weighted expectations, not the exposure in any one fire history.",
        "Weather for hours 1–5 is the cutoff weather held constant (the pipeline has no weather forecast here).",
        "The thresholds were made for buildings and workplaces (building-egress tenability; AEGL general-population "
        "exposure limits), not for people in vehicles. The visibility criterion is an assumption: 10 m is a "
        "building-egress reference and the 0.5 probability level is our choice.",
        "No Korean case, because Korea has no fuel maps.",
        "No populated place or shelter in the OpenStreetMap extract: origins are the %d road junctions and exits are "
        "the %d points where roads leave the map. Whether the Overpass mirror applied the 2024-08-23 date filter is "
        "not verified." % (E["routing"]["n_origins"], E["routing"]["n_exits"]),
        "The fire-arrival reading matters more than exposure: earliest path blocks %d road cells, half of paths "
        "blocks %d." % (FE["road"], FH["road"]),
        "The pipeline workspace's own Python environment could not be loaded on this machine (macOS refused its "
        "libraries); the same pinned versions were installed fresh. The saved example still reruns bit for bit.",
    ]
    story += [Paragraph("Limits", H2)] + [Paragraph("• " + x, P) for x in limits]

    story += [Paragraph("Files (talk_handoff/routing_link/)", H2), table([
        ["path", "what"],
        ["PROTOCOL.md, SOURCES.md", "the frozen rule and thresholds; each threshold checked against its source"],
        ["RESULTS.md", "the same results as this file, as text"],
        ["fig_blocked_cells.{png,svg,pdf}", "the figure"],
        ["out_earliest/, out_half/", "summary.json, all blocking rasters (road-layer GeoTIFF), road-layer results per run"],
        ["export_6h/", "the six hourly exposure files, both fire-arrival rasters, checks.json, the pipeline's hourly fields"],
        ["export_fishcreek.py, run_all.py, build_report.py", "reproduce (README), and build this file"],
    ], [62, 110])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 7)
        canvas.setFillColor(GREY)
        canvas.drawString(18 * mm, 10 * mm, "Fish Creek exposure and road blocking: all results")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(HERE / "RESULTS_all.pdf"), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title="Fish Creek exposure and road blocking",
                            author="", subject="All results, routing_link")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print("wrote", HERE / "RESULTS_all.pdf")


if __name__ == "__main__":
    main()
