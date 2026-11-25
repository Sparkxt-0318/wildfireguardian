"""All results in one PDF: RESULTS_all_v3.pdf = v3 Part A (RESULTS_v3.md and its figure), then RESULTS_all_v2.pdf
(which already holds v2 beside v1) unchanged. Run from this folder: python3 build_report_v3.py

The v3 pages are typeset from RESULTS_v3.md (headings, paragraphs, bullets, tables); its numbers come from
out_v3/summary_v3.json and out_v3/report_v3.json through that file. The headline numbers are checked against those
JSON files before the PDF is written.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

import build_report as R1

HERE = Path(__file__).resolve().parent
P, SMALL, H1, H2, BOX = R1.P, R1.SMALL, R1.H1, R1.H2, R1.BOX
SUB = ParagraphStyle("sub", parent=P, leftIndent=12)


def inline(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    sup = str.maketrans("⁻⁰¹³⁴⁵⁶⁷⁸⁹", "-013456789")
    s = re.sub(r"[⁻⁰¹³⁴⁵⁶⁷⁸⁹]+", lambda m: "<super>%s</super>" % m.group(0).translate(sup), s)
    return s


def check_numbers():
    S = json.loads((HERE / "out_v3" / "summary_v3.json").read_text())
    R = json.loads((HERE / "out_v3" / "report_v3.json").read_text())
    E = S["ensemble"]["runs"]
    a = R["attribution"]["residents"]
    assert E["p50_firep50_residents"]["road_cells_blocked"] == 0 and E["p50_firep50_residents"]["origins"]["n_changed"] == 0
    assert (a["paths_with_heat_cause"], a["paths_with_gas_cause"], a["paths_with_heat_or_gas_cause"]) == (234, 73, 284)
    assert (a["path_cells_heat"], a["path_cells_gas"]) == (308, 75)
    assert all(v["paths_where_an_origin_changes"] == 0 for v in R["per_path_origins"].values())
    assert [round(x) for x in E["any_firep50_residents"]["origins"]["earlier_by_min"]] == [91, 92]
    assert [round(x) for x in R["any_share_vs_median_fire"]["residents"]["gas_alone"]["earlier_by_min"]] == [83, 84]
    assert R["per_criterion"]["hcn"]["paths_with_any_road_cell"] == 0
    assert abs(S["ensemble"]["largest_share"]["contact"] - 0.0810546875) < 1e-12


def story_from_md(md):
    story, para, tbl = [], [], []

    def flush_para():
        if para:
            txt = " ".join(x.strip() for x in para)
            if txt.startswith("* "):
                sub = para[0].startswith("  ")
                story.append(Paragraph(("– " if sub else "• ") + inline(txt[2:]), SUB if sub else P))
            else:
                story.append(Paragraph(inline(txt), P))
            para.clear()

    def flush_tbl():
        if tbl:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tbl if not re.match(r"^\|[\s:|-]+\|$", r.strip())]
            ncol = len(rows[0])
            widths = [174.0 / ncol] * ncol
            if ncol >= 4:
                widths = [174.0 * 0.28] + [174.0 * 0.72 / (ncol - 1)] * (ncol - 1)
            story.append(R1.table([[inline(c) for c in r] for r in rows], widths))
            story.append(Spacer(1, 6))
            tbl.clear()

    for line in md.splitlines():
        if line.startswith("|"):
            flush_para()
            tbl.append(line)
            continue
        flush_tbl()
        if line.startswith("# "):
            flush_para()
            story.append(Paragraph(inline(line[2:]), H1))
        elif line.startswith("## "):
            flush_para()
            story.append(Paragraph(inline(line[3:]), H2))
            if line.startswith("## Figure"):
                img = Image(str(HERE / "fig_v3_heat_gas.png"))
                w = 174 * mm
                img.drawHeight = w * img.imageHeight / img.imageWidth
                img.drawWidth = w
                story.append(img)
        elif not line.strip():
            flush_para()
        elif line.lstrip().startswith("* ") or re.match(r"^\d+\. ", line):
            flush_para()
            para.append(line)
        else:
            para.append(line)
    flush_para()
    flush_tbl()
    return story


def main():
    check_numbers()
    md = (HERE / "RESULTS_v3.md").read_text()
    story = story_from_md(md)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(R1.FONT, 7)
        canvas.setFillColor(R1.GREY)
        canvas.drawString(18 * mm, 10 * mm, "Fish Creek: heat and gases as the reason a road is blocked (v3 Part A)")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, str(doc.page))
        canvas.restoreState()

    tmp = HERE / "out_v3" / "_v3_pages.pdf"
    doc = SimpleDocTemplate(str(tmp), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title="Fish Creek: heat and gases as the reason a road is blocked (v3)",
                            author="", subject="All results, routing_link: v3 Part A, then v2 and v1")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    w = PdfWriter()
    for f in (tmp, HERE / "RESULTS_all_v2.pdf"):
        for pg in PdfReader(str(f)).pages:
            w.add_page(pg)
    w.add_metadata({"/Title": "Fish Creek routing_link: all results (v3 Part A, v2, v1)", "/Author": ""})
    with open(HERE / "RESULTS_all_v3.pdf", "wb") as fh:
        w.write(fh)
    n3 = len(PdfReader(str(tmp)).pages)
    tmp.unlink()
    print("wrote", HERE / "RESULTS_all_v3.pdf", "v3 pages", n3, "total", len(PdfReader(str(HERE / "RESULTS_all_v3.pdf")).pages))


if __name__ == "__main__":
    main()
