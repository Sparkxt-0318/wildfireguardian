"""Build talk/figures/kcf_talk_figures.pptx: one figure per slide, everything editable.

* Schematics (scene manifests: F03, F07, F08) are native shapes, grouped by logical part and named.
* Native charts (F02 histogram, F05 panel a bar) are PowerPoint charts with their data in the embedded sheet.
* Every other figure: the text-free PNG as the picture, with every label, number and caption as a native text box
  at the position measured in the complete figure.
* Last slide: the palette.
"""
import json
import re

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.dml import MSO_LINE_DASH_STYLE, MSO_PATTERN
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

import style as S
from style import BUILD, FIGDIR

ORDER = ["F01_title_map", "F02_road_cut", "F03_comparison_grid", "F05_data_foundation", "F06_safety_distance",
         "F12_forecast_example", "F07_forward_backward", "F16_safety_zones", "F15_exposure",
         "F08_backward_step_checker", "F09_speed", "F09b_speed_fastpath", "F10_camp_fire", "F11a_village_card",
         "F13_kernels", "F14_reliability", "F17_heat_terrain"]

LATIN = S.FONT_LATIN
EA = S.FONT_KOREAN
SLACK = 1.08          # text boxes are a little wider than the measured text so other renderers do not wrap


def rgb(h):
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ------------------------------------------------------------------ text
MATH = [(r"\leq", "≤"), (r"\geq", "≥"), (r"^{\prime\prime}", "″"), (r"\prime\prime", "″"), (r"^{-2}", "⁻²"),
        (r"^{-1}", "⁻¹"), (r"^*", "*"), ("{", ""), ("}", ""), (r"\,", " ")]


def runs_of(text):
    """Split matplotlib mathtext into (text, italic) runs: letters inside $...$ are italic."""
    out = []
    parts = text.split("$")
    for i, p in enumerate(parts):
        if i % 2 == 0:
            if p:
                out.append((p, False))
        else:
            for a, b in MATH:
                p = p.replace(a, b)
            for tok in re.findall(r"[A-Za-z]+|[^A-Za-z]+", p):
                out.append((tok, tok.isalpha()))
    return out


def set_font(run, size, color, bold=False, italic=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.name = LATIN
    f.color.rgb = rgb(color)
    rpr = run._r.get_or_add_rPr()
    ea = rpr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rpr, qn("a:ea"))
    ea.set("typeface", EA)


def add_text(shapes, text, left, top, width, height, size, color, align="l", bold=False, italic=False,
             rotation=0, name=None, wrap=False, anchor=MSO_ANCHOR.MIDDLE):
    tb = shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    tf.auto_size = None
    al = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
    for k, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        p.alignment = al
        for chunk, it in runs_of(line):
            r = p.add_run()
            r.text = chunk
            set_font(r, size, color, bold, italic or it)
    if rotation:
        tb.rotation = rotation
    if name:
        tb.name = name[:120]
    return tb


def text_item(shapes, t):
    """Place one measured matplotlib text as a native text box."""
    ha = {"left": "l", "center": "c", "right": "r"}.get(t["ha"], "l")
    if t.get("multialign"):
        ha = {"left": "l", "center": "c", "right": "r"}.get(t["multialign"], ha)
    w, h = t["w"] * SLACK, t["h"]
    rot = (-t["rotation"]) % 360
    if rot in (90, 270):
        left, top = t["cx"] - w / 2, t["cy"] - h / 2
    else:
        left = {"l": t["cx"] - t["w"] / 2, "c": t["cx"] - w / 2, "r": t["cx"] + t["w"] / 2 - w}[ha]
        top = t["cy"] - h / 2
    return add_text(shapes, t["text"], left, top, w, h, t["size_pt"], t["color"], ha, t["bold"], t["italic"],
                    rotation=rot, name=t["name"], wrap=False)


def caption_item(shapes, t, default=(0.45, 6.0, 12.45)):
    cx, cy, w, h = t.get("cx"), t.get("cy"), t.get("w"), t.get("h")
    if cx is None:
        left, top, width, height = default[0], default[1], default[2], 1.3
    else:
        left, top, width, height = cx - w / 2, cy - h / 2, w * 1.02, h
    text = t["text"].replace("\n", " ")
    return add_text(shapes, text, left, top, width, height, S.PT_TEXT, S.INK, "l", wrap=True, name="Caption",
                    anchor=MSO_ANCHOR.TOP)


# ------------------------------------------------------------------ shapes for scenes
def line_ends(shape, arrow):
    ln = shape.line._get_or_add_ln()
    if arrow:
        tail = etree.SubElement(ln, qn("a:tailEnd"))
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")


def style_line(line, color, lw, dash=None):
    line.color.rgb = rgb(color)
    line.width = Pt(lw)
    if dash:
        line.dash_style = MSO_LINE_DASH_STYLE.DASH


def scene_shape(shapes, it):
    t = it["t"]
    if t == "rect":
        sh = shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(it["x"]), Inches(it["y"]), Inches(it["w"]), Inches(it["h"]))
        if it.get("hatch"):
            sh.fill.patterned()
            sh.fill.pattern = MSO_PATTERN.WIDE_UPWARD_DIAGONAL
            sh.fill.fore_color.rgb = rgb(S.MID)
            sh.fill.back_color.rgb = rgb(it["fill"] or S.WHITE)
        elif it.get("fill"):
            sh.fill.solid()
            sh.fill.fore_color.rgb = rgb(it["fill"])
        else:
            sh.fill.background()
        if it.get("edge"):
            style_line(sh.line, it["edge"], it["lw"])
        else:
            sh.line.fill.background()
        sh.shadow.inherit = False
    elif t == "circle":
        r = it["r"]
        sh = shapes.add_shape(MSO_SHAPE.OVAL, Inches(it["cx"] - r), Inches(it["cy"] - r), Inches(2 * r), Inches(2 * r))
        if it.get("fill"):
            sh.fill.solid()
            sh.fill.fore_color.rgb = rgb(it["fill"])
        else:
            sh.fill.background()
        if it.get("edge"):
            style_line(sh.line, it["edge"], it["lw"])
        else:
            sh.line.fill.background()
        sh.shadow.inherit = False
    elif t == "line":
        pts = it["pts"]
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            sh = shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x0), Inches(y0), Inches(x1), Inches(y1))
        else:
            fb = shapes.build_freeform(Inches(pts[0][0]), Inches(pts[0][1]), scale=1.0)
            fb.add_line_segments([(Inches(x), Inches(y)) for x, y in pts[1:]], close=False)
            sh = fb.convert_to_shape()
            sh.fill.background()
        style_line(sh.line, it["color"], it["lw"], it.get("dash"))
        line_ends(sh, it.get("arrow"))
        sh.shadow.inherit = False
    elif t == "text":
        x, y, w, h = it["box"]
        ha = {"left": "l", "center": "c", "right": "r"}[it["ha"]]
        ww = w * SLACK
        left = {"l": x, "c": x + w / 2 - ww / 2, "r": x + w - ww}[ha]
        sh = add_text(shapes, it["s"], left, y, ww, h, it["size"], it["color"], ha, it["bold"], it.get("italic", False))
    sh.name = (it.get("name") or t)[:120]
    return sh


def build_scene(slide, scene, layout):
    groups = {}
    order = []
    for it in scene["items"]:
        g = it.get("group") or it.get("name")
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(it)
    for g in order:
        items = groups[g]
        if len(items) == 1:
            scene_shape(slide.shapes, items[0])
        else:
            grp = slide.shapes.add_group_shape()
            for it in items:
                scene_shape(grp.shapes, it)
            grp.name = g[:120]
    # texts measured in the figure that are not scene items (panel letters, caption)
    names = {it.get("name") for it in scene["items"] if it["t"] == "text"}
    for t in layout["texts"]:
        if t.get("caption"):
            caption_item(slide.shapes, t)
        elif t["name"] not in names:
            text_item(slide.shapes, t)


# ------------------------------------------------------------------ native charts
def style_axis_text(axis, size=S.PT_TEXT):
    tp = axis.tick_labels
    tp.font.size = Pt(size)
    tp.font.name = LATIN
    tp.font.color.rgb = rgb(S.INK)


def axis_title(axis, text):
    axis.has_title = True
    tf = axis.axis_title.text_frame
    tf.text = text
    r = tf.paragraphs[0].runs[0]
    set_font(r, S.PT_TITLE, S.INK)


def add_chart(slide, spec):
    x, y, w, h = spec["box_in"]
    cd = CategoryChartData()
    cd.categories = spec["categories"]
    for s in spec["series"]:
        cd.add_series(s["name"], s["values"])
    if spec["type"] == "column":
        gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x - 0.9), Inches(y - 0.05),
                                    Inches(w + 1.0), Inches(h + 0.85), cd)
        ch = gf.chart
        plot = ch.plots[0]
        plot.gap_width = spec.get("gap_width", 10)
        ser = plot.series[0]
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = rgb(S.LIGHT)
        ser.format.line.color.rgb = rgb(S.INK)
        ser.format.line.width = Pt(0.6)
        ch.has_legend = False
        ch.has_title = False
        va = ch.value_axis
        va.maximum_scale = spec["y_max"]
        va.minimum_scale = 0
        va.major_unit = spec["y_major"]
        va.has_major_gridlines = True
        va.major_gridlines.format.line.color.rgb = rgb(S.GRID)
        style_axis_text(va)
        style_axis_text(ch.category_axis)
        cax = ch.category_axis._element
        skip = etree.Element(qn("c:tickLblSkip"))
        skip.set("val", "4")
        nml = cax.find(qn("c:noMultiLvlLbl"))      # schema order: tickLblSkip comes before noMultiLvlLbl
        if nml is not None:
            nml.addprevious(skip)
        else:
            cax.append(skip)
        axis_title(ch.category_axis, spec["x_title"])
        axis_title(va, spec["y_title"])
    elif spec["type"] == "bar_stacked":
        gf = slide.shapes.add_chart(XL_CHART_TYPE.BAR_STACKED, Inches(x - 0.2), Inches(y - 0.1), Inches(w + 0.4),
                                    Inches(h + 0.85), cd)
        ch = gf.chart
        plot = ch.plots[0]
        plot.gap_width = 20
        for ser, s in zip(plot.series, spec["series"]):
            if s["name"] == "probable":
                ser.format.fill.patterned()
                ser.format.fill.pattern = MSO_PATTERN.WIDE_UPWARD_DIAGONAL
                ser.format.fill.fore_color.rgb = rgb(S.INK)
                ser.format.fill.back_color.rgb = rgb(S.LIGHT)
            else:
                ser.format.fill.solid()
                ser.format.fill.fore_color.rgb = rgb(s["color"])
            ser.format.line.color.rgb = rgb(S.INK)
            ser.format.line.width = Pt(0.6)
        ch.has_title = False
        ch.has_legend = True
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(S.PT_TEXT)
        va = ch.value_axis
        va.maximum_scale = spec["x_max"]
        va.minimum_scale = 0
        va.major_unit = 100000
        va.tick_labels.number_format = '#,##0'
        va.tick_labels.number_format_is_linked = False
        style_axis_text(va)
        ch.category_axis.visible = False
    gf.name = f"chart: {spec.get('x_title', spec['type'])}"
    ch.font.name = LATIN
    return gf


# ------------------------------------------------------------------ slides
def build():
    prs = Presentation()
    prs.slide_width = Inches(S.W_IN)
    prs.slide_height = Inches(S.H_IN)
    layout_blank = prs.slide_layouts[6]
    built = []
    for name in ORDER:
        lp = BUILD / f"{name}_layout.json"
        if not lp.exists():
            continue
        L = json.loads(lp.read_text())
        slide = prs.slides.add_slide(layout_blank)
        sp = BUILD / f"{name}_scene.json"
        if L["kind"] == "scene" and sp.exists():
            build_scene(slide, json.loads(sp.read_text()), L)
        elif L["kind"] == "image":
            from PIL import Image
            im = Image.open(FIGDIR / L["image"])
            h_in = 5.6
            w_in = h_in * im.width / im.height
            pic = slide.shapes.add_picture(str(FIGDIR / L["image"]), Inches((S.W_IN - w_in) / 2), Inches(0.25),
                                           height=Inches(h_in))
            pic.name = "village card (as printed)"
            for t in L["texts"]:
                caption_item(slide.shapes, t, default=(0.45, 6.05, 12.45))
        else:
            bg = BUILD / f"{name}_pptxbg.png" if L.get("charts") else FIGDIR / f"{name}_notext.png"
            pic = slide.shapes.add_picture(str(bg), 0, 0, width=prs.slide_width, height=prs.slide_height)
            pic.name = "graphic (text-free)"
            for spec in L.get("charts", []):
                add_chart(slide, spec)
            for t in L["texts"]:
                if t.get("caption"):
                    caption_item(slide.shapes, t)
                else:
                    text_item(slide.shapes, t)
        built.append(name)
    # palette slide
    slide = prs.slides.add_slide(layout_blank)
    add_text(slide.shapes, "Palette (talk/figures/src/style.py)", 0.45, 0.35, 8, 0.4, S.PT_TITLE, S.INK,
             name="palette title")
    for i, (nm, hx, meaning) in enumerate(S.PALETTE):
        col, row = divmod(i, 6)
        x, y = 0.3 + col * 6.5, 1.1 + row * 0.95
        sq = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(0.6), Inches(0.6))
        sq.fill.solid()
        sq.fill.fore_color.rgb = rgb(hx)
        style_line(sq.line, S.INK, 0.75)
        sq.shadow.inherit = False
        sq.name = f"swatch {nm}"
        add_text(slide.shapes, f"{hx}  {nm}: {meaning}", x + 0.8, y + 0.05, 5.55, 0.5, S.PT_TEXT, S.INK,
                 name=f"label {nm}")
    out = FIGDIR / "kcf_talk_figures.pptx"
    prs.save(out)
    print(f"wrote {out.name}: {len(built)} figure slides + palette: {', '.join(built)}")


if __name__ == "__main__":
    build()
