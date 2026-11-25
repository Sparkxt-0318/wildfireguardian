"""Label check for figures with Hangul place names (F04_overview, F07_map, F08_map). Writes check/{name}_labels.json.

1. Glyphs: every character of every visible text must have a glyph in the font matplotlib picks for it (the first font
   of the family list that has one); Hangul must come from the Korean font of style.py, never from a last-resort font.
   A character with no glyph would print as an empty box.
2. Marks: no text box (with its paper backing) may touch a point marker (village, shelter, far end, key symbols) or
   the route / highlighted road line, grown by half the marker size or line width plus 1 pt.
3. Files (after saving): every Hangul text appears in the SVG as text with the Korean font in its font list, and the
   PDF embeds the Korean font. Missing-glyph warnings during saving are caught by figkit.save.
"""
import json
import re

import matplotlib.font_manager as fm
import numpy as np
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox

import style as S
from figkit import CHECK, FIGDIR, _texts

HANGUL = re.compile("[가-힣ᄀ-ᇿ㄰-㆏]")
LINE_GIDS = ("route", "the road")
_face_cache = {}


def _faces(fp):
    out = []
    for p in fm.fontManager._find_fonts_by_props(fp):
        key = (p.path, p.face_index)
        if key not in _face_cache:
            _face_cache[key] = fm.get_font([p])
        out.append(_face_cache[key])
    return out


def _plain(s):
    return re.sub(r"\$[^$]*\$", "", s)       # mathtext is drawn by the math font set, not the text fonts


def glyph_problems(fig):
    probs, hangul = [], []
    for t in _texts(fig):
        s = _plain(t.get_text())
        faces = _faces(t.get_fontproperties())
        for c in sorted(set(s) - set(" \n\t")):
            face = next((f for f in faces if f.get_char_index(ord(c)) != 0), None)
            if face is None:
                probs.append({"type": "no glyph", "char": c, "text": t.get_text()})
            elif HANGUL.match(c) and face.family_name != S.FONT_KOREAN:
                probs.append({"type": "Hangul from another font", "char": c, "font": face.family_name,
                              "text": t.get_text()})
        if HANGUL.search(s):
            hangul.append(s)
    return probs, hangul


def _gid(a):
    return a.get_gid() or ""


def _clip(a):
    """The visible region of an artist (its clip box in display units), or None if unclipped."""
    cb = a.get_clip_box() if a.get_clip_on() else None
    return Bbox(cb.get_points()) if cb is not None else None


def _marks(fig, r):
    """(kind, gid, display Bbox or display Path, pad px)"""
    px = S.DPI / 72
    out = []
    arts = list(fig.artists) + list(fig.lines)
    for ax in fig.axes:
        if ax.get_visible():
            arts += list(ax.lines) + list(ax.collections)
    for a in arts:
        if not a.get_visible():
            continue
        g = _gid(a)
        if isinstance(a, Line2D):
            m = a.get_marker()
            xy = a.get_transform().transform(a.get_xydata())
            if m not in (None, "None", "", " ") and len(xy):
                rad = (a.get_markersize() / 2 + a.get_markeredgewidth() / 2) * px
                for x, y in xy:
                    out.append(("marker", g, Bbox([[x - rad, y - rad], [x + rad, y + rad]]), px, _clip(a)))
            if any(k in g for k in LINE_GIDS) and "halo" not in g and a.get_linestyle() not in ("None", ""):
                path = a.get_transform().transform_path(a.get_path())
                out.append(("line", g, path, (a.get_linewidth() / 2 + 1) * px, _clip(a)))
        elif isinstance(a, PathCollection):
            offs = a.get_offset_transform().transform(a.get_offsets())
            sizes = a.get_sizes()
            lws = a.get_linewidths()
            for i, (x, y) in enumerate(offs):
                rad = (np.sqrt(sizes[i % len(sizes)]) / 2 + lws[i % len(lws)] / 2) * px
                out.append(("marker", g, Bbox([[x - rad, y - rad], [x + rad, y + rad]]), px, _clip(a)))
        elif isinstance(a, LineCollection) and any(k in g for k in LINE_GIDS) and "halo" not in g:
            for p in a.get_paths():
                out.append(("line", g, a.get_transform().transform_path(p), (a.get_linewidths()[0] / 2 + 1) * px,
                            _clip(a)))
    return out


def _text_box(t, r):
    b = t.get_window_extent(r)
    p = t.get_bbox_patch()
    if p is not None:
        b = Bbox.union([b, p.get_window_extent(r)])
    return b


def mark_problems(fig):
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    marks = _marks(fig, r)
    probs = []
    for t in _texts(fig):
        tb = _text_box(t, r)
        for kind, g, geom, pad, clip in marks:
            grown = Bbox([[tb.x0 - pad, tb.y0 - pad], [tb.x1 + pad, tb.y1 + pad]])
            if clip is not None:                   # only the drawn part of a clipped mark counts
                grown = Bbox.intersection(grown, clip)
                if grown is None:
                    continue
            hit = grown.overlaps(geom) if kind == "marker" else geom.intersects_bbox(grown, filled=False)
            if hit:
                probs.append({"type": f"text on {kind}", "text": t.get_text(), "mark": g})
    return probs, len(marks)


def run(fig, name, strict=True):
    gp, hangul = glyph_problems(fig)
    mp, nmarks = mark_problems(fig)
    res = {"figure": name, "korean_font": S.FONT_KOREAN, "latin_font": S.FONT_LATIN,
           "texts_with_hangul": hangul, "marks_checked": nmarks, "glyph_problems": gp, "mark_problems": mp}
    (CHECK / f"{name}_labels.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    status = "PASS" if not gp and not mp else f"FAIL ({len(gp)} glyph, {len(mp)} mark)"
    print(f"{name}: label check {status} ({len(hangul)} texts with Hangul, {nmarks} marks)")
    for p in (gp + mp)[:20]:
        print("   ", p)
    if (gp or mp) and strict:
        raise SystemExit(f"{name}: label check failed (check/{name}_labels.json)")
    return res


def verify_files(name):
    """After save: Hangul texts are text in the SVG with the Korean font listed; the PDF embeds the Korean font."""
    p = CHECK / f"{name}_labels.json"
    res = json.loads(p.read_text())
    svg = (FIGDIR / f"{name}.svg").read_text()
    pdf = (FIGDIR / f"{name}.pdf").read_bytes()
    probs = []
    for s in res["texts_with_hangul"]:
        for line in s.split("\n"):
            for word in re.findall(r"\S*[가-힣]\S*", line):
                if word not in svg:
                    probs.append({"type": "Hangul missing from SVG", "word": word})
    if res["texts_with_hangul"]:
        if S.FONT_KOREAN not in svg:
            probs.append({"type": "SVG font list lacks the Korean font"})
        if S.FONT_KOREAN.replace(" ", "").encode() not in pdf:
            probs.append({"type": "PDF does not embed the Korean font"})
    res["file_problems"] = probs
    p.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"{name}: file check {'PASS' if not probs else probs}")
    if probs:
        raise SystemExit(f"{name}: file check failed")
