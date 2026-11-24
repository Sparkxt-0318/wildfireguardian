"""Export every figure three ways and check that no text collides with anything.

save(fig, "F09_speed", kind="picture") writes
  talk/figures/F09_speed.{svg,pdf,png}            complete
  talk/figures/F09_speed_notext.{png,svg}         same graphic, every word and number removed
  talk/figures/build/F09_speed_text.json          every text item with its box, for build_pptx.py
  talk/figures/check/F09_speed_grey.png           greyscale version for the greyscale check
  talk/figures/check/F09_speed_overlap.json       result of the collision check

Collision check (after layout, in display pixels):
  * every text box is grown by PAD_TEXT on each side; two grown boxes may not intersect
    (so two texts are at least 2 x PAD_TEXT apart = half a line at 16 pt)
  * a text box grown by PAD_MARK may not touch any data mark: lines, bars, markers, polygons,
    images and axis spines. Marks whose gid starts with "bg" (map roads, terrain, tints) are
    context and are skipped. Marks whose gid starts with "box" are containers: text may sit
    inside them but may not cross their outline.
  * every grown text box must lie inside the figure.
Artists can opt out individually with gid "nocheck" (used only where documented in DECISIONS.md).
"""
import json
import math

import numpy as np
from matplotlib.collections import Collection, PathCollection
from matplotlib.image import AxesImage
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.spines import Spine
from matplotlib.text import Text
from matplotlib.transforms import Bbox
from PIL import Image

from style import BUILD, CHECK, DPI, FIGDIR, H_IN, W_IN

PAD_TEXT_PT = 4.0
PAD_MARK_PT = 4.0


def _gid(a):
    g = a.get_gid()
    return g or ""


def _texts(fig):
    out = []
    for t in fig.findobj(Text):
        if not t.get_visible() or not t.get_text().strip():
            continue
        if t.axes is not None and not t.axes.get_visible():
            continue
        out.append(t)
    return out


def _grow(bb, px):
    return Bbox.from_extents(bb.x0 - px, bb.y0 - px, bb.x1 + px, bb.y1 + px)


def _marks(fig):
    marks = []
    for a in fig.findobj(lambda x: isinstance(x, (Line2D, Patch, Collection, AxesImage, Spine))):
        if not a.get_visible() or isinstance(a, Text):
            continue
        g = _gid(a)
        if g.startswith("bg") or g == "nocheck":
            continue
        ax = a.axes
        if isinstance(a, Patch) and not isinstance(a, Spine):
            if any(a is axx.patch for axx in fig.axes):
                continue
            if a is fig.patch:
                continue
            # skip text bounding-box patches and invisible patches
            if a.get_facecolor()[3] == 0 and (a.get_edgecolor()[3] == 0 or a.get_linewidth() == 0):
                continue
        if isinstance(a, Line2D) and ax is not None:
            # tick marks belong to axis machinery; the spine stands for the axis
            if a in ax.xaxis.get_ticklines(minor=False) or a in ax.yaxis.get_ticklines(minor=False):
                continue
            if a in ax.xaxis.get_ticklines(minor=True) or a in ax.yaxis.get_ticklines(minor=True):
                continue
            if a.get_parent() if hasattr(a, "get_parent") else False:
                pass
        marks.append(a)
    return marks


def _is_tickline(a):
    # tick lines are Line2D children of Tick objects; their transform is a blended axis transform
    return isinstance(a, Line2D) and a.get_marker() in (2, 3, 0, 1, "|", "_") and len(a.get_xdata()) == 1


def _hits(mark, bb, fig, renderer):
    """Does the mark intersect display-space box bb?"""
    g = _gid(mark)
    container = g.startswith("box")
    # respect clipping: only the visible part of a mark counts
    if mark.get_clip_on():
        cb = mark.get_clip_box()
        if cb is not None:
            if not cb.overlaps(bb):
                return False
            bb = Bbox.intersection(bb, cb)
            if bb is None:
                return False
    if isinstance(mark, AxesImage):
        ext = mark.get_window_extent(renderer)
        return ext.overlaps(bb)
    if isinstance(mark, Line2D):
        if _is_tickline(mark):
            return False
        path = mark.get_path()
        tr = mark.get_transform()
        dpath = tr.transform_path(path)
        if mark.get_linestyle() not in ("None", "none", "", " ") and len(dpath.vertices) > 1:
            if dpath.intersects_bbox(bb, filled=False):
                return True
        if mark.get_marker() not in (None, "None", "none", "", " "):
            r = mark.get_markersize() / 2 * DPI / 72
            for x, y in dpath.vertices:
                if _circle_rect(x, y, r, bb):
                    return True
        return False
    if isinstance(mark, Spine):
        dpath = mark.get_transform().transform_path(mark.get_path())
        return dpath.intersects_bbox(bb, filled=False)
    if isinstance(mark, Patch):
        dpath = mark.get_transform().transform_path(mark.get_path())
        if container:
            return dpath.intersects_bbox(bb, filled=False)
        return dpath.intersects_bbox(bb, filled=True)
    if isinstance(mark, PathCollection):
        offs = mark.get_offsets()
        if len(offs) == 0:
            return False
        trans = mark.get_offset_transform()
        pts = trans.transform(np.asarray(offs))
        sizes = mark.get_sizes()
        if len(sizes) == 0:
            sizes = [36]
        sizes = np.broadcast_to(np.asarray(sizes), (len(pts),))
        lw = (mark.get_linewidths() or [0])[0]
        for (x, y), s in zip(pts, sizes):
            r = (math.sqrt(s) / 2 + lw / 2) * DPI / 72
            if _circle_rect(x, y, r, bb):
                return True
        return False
    if isinstance(mark, Collection):
        tr = mark.get_transform()
        filled = len(mark.get_facecolor()) > 0 and np.any(np.asarray(mark.get_facecolor())[:, 3] > 0)
        offs = mark.get_offsets()
        otr = mark.get_offset_transform()
        paths = mark.get_paths()
        for i, p in enumerate(paths):
            dp = tr.transform_path(p)
            if offs is not None and len(offs) > 1 and len(offs) == len(paths):
                o = otr.transform(offs[i])
                dp.vertices[:] = dp.vertices + o
            if not dp.get_extents().overlaps(bb):
                continue
            if dp.intersects_bbox(bb, filled=bool(filled) and not container):
                return True
        return False
    return False


def _circle_rect(cx, cy, r, bb):
    nx = min(max(cx, bb.x0), bb.x1)
    ny = min(max(cy, bb.y0), bb.y1)
    return (cx - nx) ** 2 + (cy - ny) ** 2 <= r * r


def _owner_axis_labels(t):
    return None


def check_collisions(fig, allow_pairs=()):
    """Return a list of problems (empty = pass)."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ptpx = DPI / 72
    texts = _texts(fig)
    boxes = [t.get_window_extent(renderer) for t in texts]
    figbb = fig.bbox
    probs = []
    # text against figure edge
    for t, b in zip(texts, boxes):
        g = _grow(b, PAD_TEXT_PT * ptpx)
        if g.x0 < figbb.x0 or g.y0 < figbb.y0 or g.x1 > figbb.x1 or g.y1 > figbb.y1:
            probs.append({"type": "edge", "text": t.get_text()})
    # text against text
    for i in range(len(texts)):
        gi = _grow(boxes[i], PAD_TEXT_PT * ptpx)
        for j in range(i + 1, len(texts)):
            gj = _grow(boxes[j], PAD_TEXT_PT * ptpx)
            if gi.overlaps(gj):
                pair = (texts[i].get_text(), texts[j].get_text())
                if pair in allow_pairs or pair[::-1] in allow_pairs:
                    continue
                probs.append({"type": "text-text", "a": pair[0], "b": pair[1]})
    # text against marks
    marks = _marks(fig)
    for t, b in zip(texts, boxes):
        if _gid(t) == "nocheck":
            continue
        g = _grow(b, PAD_MARK_PT * ptpx)
        for m in marks:
            if _hits(m, g, fig, renderer):
                probs.append({"type": "text-mark", "text": t.get_text(),
                              "mark": f"{type(m).__name__}:{_gid(m) or m.get_label()}"})
    return probs


def _hex(c):
    from matplotlib.colors import to_hex
    return to_hex(c, keep_alpha=False)


def _axis_texts(ax):
    out = set(ax.get_xticklabels()) | set(ax.get_yticklabels())
    out |= {ax.xaxis.label, ax.yaxis.label}
    return out


def text_manifest(fig, native_axes=()):
    """Every visible text with its box in inches from the top-left corner, for PowerPoint.
    Tick and axis labels of axes that become native PowerPoint charts are left out (the chart draws its own)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    skip = set()
    for ax in native_axes:
        skip |= _axis_texts(ax)
    items = []
    for t in _texts(fig):
        if t in skip:
            continue
        rot = t.get_rotation()
        # unrotated box size: measure with rotation removed
        bb = t.get_window_extent(r)
        if rot % 180 != 0:
            t.set_rotation(0)
            ub = t.get_window_extent(r)
            t.set_rotation(rot)
            w, h = ub.width / DPI, ub.height / DPI
        else:
            w, h = bb.width / DPI, bb.height / DPI
        cx = (bb.x0 + bb.x1) / 2 / DPI
        cy = H_IN - (bb.y0 + bb.y1) / 2 / DPI
        fp = t.get_fontproperties()
        items.append({
            "text": t.get_text(),
            "cx": cx, "cy": cy, "w": w, "h": h,
            "rotation": rot,
            "size_pt": fp.get_size_in_points(),
            "bold": fp.get_weight() in ("bold", 700, "heavy", 800, 900, "black", "semibold", 600),
            "italic": fp.get_style() == "italic",
            "color": _hex(t.get_color()),
            "ha": t.get_horizontalalignment(),
            "multialign": t.get_multialignment() if hasattr(t, "get_multialignment") else None,
            "name": ("Caption" if _gid(t) == "caption" else (_gid(t) or t.get_text()[:40])).replace("\n", " "),
            "caption": _gid(t) == "caption",
        })
    return items


def _ax_box_in(ax):
    p = ax.get_position()
    return [p.x0 * W_IN, (1 - p.y1) * H_IN, p.width * W_IN, p.height * H_IN]


def wrap_to_width(fig, text, x_in, width_in, size):
    """Greedy word wrap measured with the renderer."""
    r = fig.canvas.get_renderer()
    words, lines, cur = text.split(), [], ""
    probe = fig.text(0, 0, "", fontsize=size)
    for w_ in words:
        trial = (cur + " " + w_).strip()
        probe.set_text(trial)
        if probe.get_window_extent(r).width / DPI > width_in and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = trial
    lines.append(cur)
    probe.remove()
    return "\n".join(lines)


def add_caption(fig, text, x_in=0.45, width_in=12.45, top_in=None):
    """Numbered caption beneath the figure, as its own text item (gid 'caption')."""
    from style import CAPTION_TOP, PT_TEXT
    fig.canvas.draw()
    wrapped = wrap_to_width(fig, text, x_in, width_in, PT_TEXT)
    t = fig.text(x_in / W_IN, 1 - (top_in or CAPTION_TOP) / H_IN, wrapped, fontsize=PT_TEXT, va="top", ha="left",
                 linespacing=1.2)
    t.set_gid("caption")
    return t


def save(fig, name, *, kind="picture", extra=None, allow_pairs=(), strict=True, charts=(), caption=None):
    """Export complete (with caption), without caption, text-free, and the PowerPoint manifest.
    charts: [(ax, spec)] axes to rebuild as native PowerPoint charts; spec is a dict with the chart data."""
    if caption is not None and not isinstance(caption, Text):
        raise TypeError("pass the Text returned by add_caption")
    probs = check_collisions(fig, allow_pairs)
    (CHECK / f"{name}_overlap.json").write_text(json.dumps(probs, indent=1, ensure_ascii=False))
    native_axes = [a for a, _ in charts]
    manifest = {"name": name, "kind": kind, "canvas_in": [W_IN, H_IN],
                "texts": text_manifest(fig, native_axes),
                "charts": [dict(spec, box_in=_ax_box_in(a)) for a, spec in charts]}
    if extra:
        manifest.update(extra)
    base = FIGDIR / name
    fig.savefig(f"{base}.svg")
    fig.savefig(f"{base}.pdf")
    fig.savefig(f"{base}.png", dpi=DPI)
    if caption is not None:
        caption.set_visible(False)
        fig.savefig(f"{base}_nocaption.svg")
        fig.savefig(f"{base}_nocaption.pdf")
        fig.savefig(f"{base}_nocaption.png", dpi=DPI)
        caption.set_visible(True)
    # greyscale check image
    Image.open(f"{base}.png").convert("L").save(CHECK / f"{name}_grey.png")
    # text-free version: hide every text, keep everything else in place
    hidden = []
    for t in _texts(fig):
        t.set_visible(False)
        hidden.append(t)
    fig.savefig(f"{base}_notext.png", dpi=DPI)
    fig.savefig(f"{base}_notext.svg")
    if native_axes:
        # background picture for PowerPoint: text-free and without the axes that become native charts
        for a in native_axes:
            a.set_visible(False)
        fig.savefig(BUILD / f"{name}_pptxbg.png", dpi=DPI)
        for a in native_axes:
            a.set_visible(True)
    for t in hidden:
        t.set_visible(True)
    (BUILD / f"{name}_layout.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    status = "PASS" if not probs else f"FAIL ({len(probs)} problems)"
    print(f"{name}: collision check {status}")
    for p in probs[:30]:
        print("   ", p)
    if probs and strict:
        raise SystemExit(f"{name}: text collides (see check/{name}_overlap.json)")
    return probs


def grid(ax, axis="both", which="major"):
    """Light grey gridlines, tagged as context so text may sit on them."""
    ax.grid(True, axis=axis, which=which)
    for ln in ax.get_xgridlines() + ax.get_ygridlines():
        ln.set_gid("bg:grid")


def boxed_legend(ax, *args, **kw):
    """Legend in a thin square-cornered box (frame tagged as a container)."""
    kw.setdefault("frameon", True)
    leg = ax.legend(*args, **kw)
    leg.get_frame().set_linewidth(0.6)
    leg.get_frame().set_gid("box:legend")
    return leg
