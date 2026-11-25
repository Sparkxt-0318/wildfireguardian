"""F18: a real fire that no standard satellite label covered, found and verified by caught v0.1
(wildfireguardiandata release caught-v0.1), and F18b: six more, drawn by a fixed seed.

Everything is read from talk/figures/build/caught/ (F18_caught_data.py: release files checked against SHA256SUMS,
copied unchanged). Chips are the release's own scar-pair chips: Sentinel-2 L2A at 20 m, false colour R = B12,
G = B8A, B = mean(B02, B03, B04), on the scar finder's grid (UTM, `grid_epsg`, `grid_bounds` in meta.json). The scar
outline is the edge of the accepted scar pixels (mask.png); the box is their pixel extent; the tag gives the label
tier, the released scar area (`scar_area_ha`), the FPA FOD record ID (`FOD_ID`) and the discovery date
(`t0` + the record window's one-day margin, protocol section 4, config window.pre_days).
"""
import json
import math
import os
from datetime import date, timedelta

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.patches import FancyArrow, Rectangle
from PIL import Image
from pyproj import Transformer

import style as S
from figkit import save
from prov import Ledger
from realmap import back_labels

W, H = S.W_IN, S.H_IN
DIR = S.BUILD / "caught"
F = "talk/figures/build/caught/fires.json"
SMALL = S.PT_TEXT - 2                    # credit and scale text (14 pt, the set's minimum)
CREDIT = "Contains modified Copernicus Sentinel data {yr} (Sentinel-2 L2A, 20 m; false colour B12, B8A, visible)"


def load():
    d = json.loads((DIR / "fires.json").read_text())
    for rid, f in d["fires"].items():
        f["meta"] = json.loads((DIR / rid / "meta.json").read_text())
        f["pre"] = np.asarray(Image.open(DIR / rid / "pre.png").convert("RGB"))
        f["post"] = np.asarray(Image.open(DIR / rid / "post.png").convert("RGB"))
        f["mask"] = np.asarray(Image.open(DIR / rid / "mask.png")) > 0
        assert f["mask"].shape == f["post"].shape[:2] == f["pre"].shape[:2]
        f["discovery"] = (date.fromisoformat(f["t0"][:10])
                          + timedelta(days=d["standard"]["record_window"]["pre_days"])).isoformat()
        f["scene"] = {role: [i[0] for i in f["meta"]["inputs"] if i[0].split("_")[2][:8] == f["meta"][f"{role}_date"].replace("-", "")]
                      for role in ("pre", "post")}
        for role in ("pre", "post"):
            assert len(set(f["scene"][role])) == 1, (rid, role, set(f["scene"][role]))
            f["scene"][role] = f["scene"][role][0]
    return d


def extent_m(f):
    x0, y0, x1, y1 = f["meta"]["grid_bounds"]
    return [0.0, x1 - x0, 0.0, y1 - y0]


def res_m(f):
    x0, y0, x1, y1 = f["meta"]["grid_bounds"]
    n = f["mask"].shape[1]
    r = (x1 - x0) / n
    assert abs(r - 20.0) < 1e-6 and abs((y1 - y0) / f["mask"].shape[0] - 20.0) < 1e-6, r
    return r


def outline_segments(mask, r):
    """Pixel-edge boundary of the mask (no smoothing), in chip metres (origin bottom-left)."""
    m = np.pad(mask, 1)
    nr = mask.shape[0]
    segs = []
    for i in range(1, m.shape[0] - 1):
        for j in range(1, m.shape[1] - 1):
            if not m[i, j]:
                continue
            row, col = i - 1, j - 1
            top, bot = (nr - row) * r, (nr - row - 1) * r
            left, right = col * r, (col + 1) * r
            if not m[i - 1, j]:
                segs.append([(left, top), (right, top)])
            if not m[i + 1, j]:
                segs.append([(left, bot), (right, bot)])
            if not m[i, j - 1]:
                segs.append([(left, bot), (left, top)])
            if not m[i, j + 1]:
                segs.append([(right, bot), (right, top)])
    return segs


def bbox_m(mask, r):
    rows, cols = np.nonzero(mask)
    nr = mask.shape[0]
    return (cols.min() * r, (nr - rows.max() - 1) * r, (cols.max() + 1) * r, (nr - rows.min()) * r)


def north_angle(f):
    """Angle (degrees, counter-clockwise from the chip's up) of true north at the chip centre (UTM convergence)."""
    x0, y0, x1, y1 = f["meta"]["grid_bounds"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    inv = Transformer.from_crs(f"EPSG:{f['meta']['grid_epsg']}", "EPSG:4326", always_xy=True)
    fwd = Transformer.from_crs("EPSG:4326", f"EPSG:{f['meta']['grid_epsg']}", always_xy=True)
    lon, lat = inv.transform(cx, cy)
    nx, ny = fwd.transform(lon, lat + 0.01)
    return math.degrees(math.atan2(-(nx - cx), ny - cy))


def nice_bar(width_m):
    for v in (2000, 1000, 500, 250, 100):
        if v <= width_m * 0.3:
            return v
    return 100


def chip(fig, x_in, y_in, side_in):
    ax = fig.add_axes([x_in / W, 1 - (y_in + side_in) / H, side_in / W, side_in / H])
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.75)
        sp.set_color(S.INK)
    return ax


def furniture(ax, f, arrow_xy=(0.9, 0.8)):
    """Scale bar (bottom left) and north arrow (top right), on paper backings."""
    ext = extent_m(f)
    wm = ext[1]
    L = nice_bar(wm)
    bx, by = 0.05 * wm, 0.09 * ext[3]
    ax.add_patch(Rectangle((bx - 0.025 * wm, by - 0.065 * ext[3]), L + 0.27 * wm, 0.13 * ext[3],
                           facecolor=S.PAPER, edgecolor="none", alpha=0.9, zorder=8, gid="bg:scale backing"))
    ax.plot([bx, bx + L], [by, by], color=S.INK, lw=3, solid_capstyle="butt", zorder=9)[0].set_gid("bg:scale bar")
    ax.text(bx + L + 0.025 * wm, by, f"{L / 1000:g} km" if L >= 1000 else f"{L:g} m", va="center", ha="left",
            fontsize=SMALL, zorder=10)
    a = math.radians(north_angle(f))
    cx, cy = arrow_xy[0] * wm, arrow_xy[1] * ext[3]
    ln = 0.11 * ext[3]
    ax.add_patch(Rectangle((cx - 0.06 * wm, cy - 0.075 * ext[3]), 0.12 * wm, 0.235 * ext[3], facecolor=S.PAPER,
                           edgecolor="none", alpha=0.9, zorder=8, gid="bg:north backing"))
    dx, dy = -math.sin(a) * ln, math.cos(a) * ln
    ax.add_patch(FancyArrow(cx - dx / 2, cy - dy / 2, dx, dy, width=0.004 * wm, head_width=0.045 * wm,
                            head_length=0.05 * ext[3], length_includes_head=True, color=S.INK, zorder=9,
                            gid="bg:north arrow"))
    ax.text(cx, cy + dy / 2 + 0.065 * ext[3], "N", ha="center", va="center", fontsize=SMALL, zorder=10)


def wrap(fig, text, width_in, fontsize):
    """Split text into lines no wider than width_in (measured with the renderer)."""
    r = fig.canvas.get_renderer()
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        t = fig.text(0, 0, trial, fontsize=fontsize)
        wide = t.get_window_extent(r).width / S.DPI
        t.remove()
        if wide > width_in and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    return lines + [cur]


def overlay(ax, f, fs=S.PT_TEXT):
    """The pipeline's output drawn like a detector's: scar outline, bounding box, tag."""
    r = res_m(f)
    ext = extent_m(f)
    lc = LineCollection(outline_segments(f["mask"], r), colors=S.BLUE, linewidths=1.8, zorder=5, capstyle="round")
    lc.set_gid("bg:scar outline")
    ax.add_collection(lc)
    x0, y0, x1, y1 = bbox_m(f["mask"], r)
    pad = 2 * r
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="none", edgecolor=S.BLUE, linewidth=1.6,
                           linestyle=(0, (4, 2)), zorder=6, gid="bg:bounding box"))
    txt = f"{f['tier']}, {f['scar_area_ha']:.1f} ha\nFPA FOD {f['FOD_ID']}\nfire {f['discovery']}"
    fig = ax.figure
    r_ = fig.canvas.get_renderer()
    fig.canvas.draw()
    pt = S.DPI / 72
    keep_out = [p.get_window_extent(r_) for p in ax.patches if "backing" in (p.get_gid() or "")]
    box = ax.bbox
    # like a detector's tag: on the box's edge; the first of four places that stays in the chip and off the
    # scale bar and north arrow
    for xy, ha, va, dy in [((x0, y1), "left", "bottom", 3), ((x0, y0), "left", "top", -3),
                           ((x1, y1), "right", "bottom", 3), ((x1, y0), "right", "top", -3)]:
        t = ax.annotate(txt, xy=xy, xytext=(0, dy), textcoords="offset points", ha="left", va=va, fontsize=fs,
                        color=S.PAPER, zorder=11, annotation_clip=False,
                        bbox=dict(boxstyle="square,pad=0.25", facecolor=S.BLUE, edgecolor="none"))
        fig.canvas.draw()
        bb = t.get_bbox_patch().get_window_extent(r_)
        # left-aligned text everywhere (PowerPoint text boxes follow the anchor); a right-corner tag ends at the corner
        dx = -bb.width if ha == "right" else 0.0
        dx += max(0.0, box.x0 + 8 * pt - (bb.x0 + dx)) + min(0.0, box.x1 - 8 * pt - (bb.x1 + dx))   # slide along
        if dx:
            t.set_position((dx / pt, dy))
            fig.canvas.draw()
            bb = t.get_bbox_patch().get_window_extent(r_)
        inside = (bb.x0 > box.x0 + 6 * pt and bb.x1 < box.x1 - 6 * pt and bb.y0 > box.y0 + 6 * pt
                  and bb.y1 < box.y1 - 6 * pt)
        clear = not any(_near(bb, k, 6 * pt) for k in keep_out)
        if inside and clear:
            return t
        t.remove()
    raise SystemExit(f"{f['rid']}: no place for the tag")


def _near(a, b, d):
    return not (a.x1 + d < b.x0 or b.x1 + d < a.x0 or a.y1 + d < b.y0 or b.y1 + d < a.y0)


def ledger_rows(L, d, rid, role):
    f = d["fires"][rid]
    rel = d["release"]
    kw = dict(commit=rel["commit"], repo_name=rel["repo"], ref=rel["tag"])
    lab = f"caught_labels_v0.1_{f['FIRE_YEAR']}.parquet"
    L.add(f"{role}: record", f["FOD_ID"], file=lab, field=f"rid={rid}: FOD_ID, STATE {f['STATE']}",
          shown=f"FPA FOD {f['FOD_ID']}", note=f"release asset sha256 {rel['sha256'][lab]}", **kw)
    L.add(f"{role}: tier / standard label", [f["tier"], f["std_label"], f["std_witnesses"]], file=lab,
          field="tier, std_label, std_witnesses", shown=f"{f['tier']}; no standard label", **kw)
    L.add(f"{role}: discovery date", f["discovery"], file=lab, field="t0 + config window.pre_days (protocol 4)",
          shown=f["discovery"], **kw)
    L.add(f"{role}: scar area", f["scar_area_ha"], unit="ha", file=lab, field="scar_area_ha",
          shown=f"{f['scar_area_ha']:.1f} ha",
          expected=f"mask.png {f['mask_px']} px x 400 m2 = {f['mask_px'] * 0.04:.2f} ha", **kw)
    for role_ in ("pre", "post"):
        L.add(f"{role}: Sentinel-2 {role_} scene", f["scene"][role_], file=f"scar_pairs.zip:{rid}/meta.json",
              field=f"inputs[] on {role_}_date; label scar_{role_} {f['scar_' + role_][:10]}",
              shown=f["meta"][f"{role_}_date"], **kw)


def re_short(name):
    """'MODIS C6.1 (MCD14ML)' -> 'MCD14ML'."""
    return name.split("(")[-1].rstrip(")")


def std_line(d):
    s = d["standard"]
    p = s["params"]
    b = s["s2"]
    prods = ", ".join(list(s["firms_products"].values()) + [s["burned_area"], s["perimeters"]])
    line1 = f"Standard labels (none in the record window): {prods}. {s['firececci_note']}"
    line2 = (f"Burn scar: Sentinel-2 dNBR = NBR before − NBR after, NBR = ({b['nir']} − {b['swir2']}) / "
             f"({b['nir']} + {b['swir2']}); dNBR ≥ max({p['t_abs']:.2f}, median + {p['k_sigma']:g} robust sd outside "
             f"the record disc); {b['nir']} falls > {-p['dnir']:g}, visible rises < {p['dvis']:g}, {b['swir1']} rises "
             f"< {p['dswir1_max']:g}; ≥ {p['n_min']} connected {b['res_m']:g} m pixels touching the disc; looks ≤ "
             f"{p['pre_days']} days before discovery − {s['record_window']['pre_days']} day and ≤ {p['post_days']} days "
             f"after containment + {s['record_window']['post_days']} day, disc ≥ {p['min_clear']:.0%} clear.")
    return line1, line2


def fig_main(d):
    rid = d["main"]
    f = d["fires"][rid]
    L = Ledger("F18", f"A fire no standard satellite label covered: FPA FOD {f['FOD_ID']}")
    ledger_rows(L, d, rid, "main")
    L.add("Standard-label products and scar test", d["standard"]["params"], file=d["standard"]["files"]["scar"],
          field="PARAMS, S2.bands, scar_search; config/us.json firms.products, mcd64a1, window",
          shown="line under the chips", commit=d["release"]["commit"], repo_name=d["release"]["repo"],
          ref=d["release"]["tag"])
    L.add("Selection", [d["selection"]["eligible"], d["selection"]["pairs_in_release"]], file=F,
          field="selection", shown="(SOURCES only)", note=d["selection"]["main_rule"])
    fig = S.plt.figure(figsize=(W, H), dpi=S.DPI)
    side, gap, top = 3.45, 0.3, 1.62
    x0 = (W - 3 * side - 2 * gap) / 2
    ext = extent_m(f)
    axs = [chip(fig, x0 + i * (side + gap), top, side) for i in range(3)]
    # (1) the standard label layer: nothing, over a faint grey copy of the before image so the place reads
    grey = f["pre"].mean(axis=2)
    faint = 0.82 + 0.18 * grey / 255.0
    axs[0].imshow(faint, extent=ext, cmap="gray", vmin=0, vmax=1, origin="upper", interpolation="nearest",
                  zorder=0).set_gid("bg:backdrop")
    axs[0].text(ext[1] / 2, ext[3] / 2, "no label", ha="center", va="center", color=S.INK, zorder=10,
                bbox=dict(boxstyle="square,pad=0.3", facecolor=S.PAPER, edgecolor="none"))
    axs[1].imshow(f["pre"], extent=ext, origin="upper", interpolation="nearest", zorder=0).set_gid("bg:before")
    axs[2].imshow(f["post"], extent=ext, origin="upper", interpolation="nearest", zorder=0).set_gid("bg:after")
    for ax in axs:
        ax.set_xlim(0, ext[1])
        ax.set_ylim(0, ext[3])
        furniture(ax, f)
    overlay(axs[2], f)
    s = d["standard"]
    names = [re_short(v) for v in s["firms_products"].values()] + [s["burned_area"].split()[0], s["perimeters"]]
    win = f"record window {f['t0'][:10]} to {f['t1'][5:10]}"
    titles = [["Standard satellite labels", ", ".join(names[:3]) + ",", ", ".join(names[3:]), win],
              ["Before the fire", "Sentinel-2 L2A, 20 m", None, f["meta"]["pre_date"]],
              ["After, with the pipeline output", "Sentinel-2 L2A, 20 m", None, f["meta"]["post_date"]]]
    for i, tl in enumerate(titles):
        xx = (x0 + i * (side + gap)) / W
        fig.text(xx, 1 - (top - 1.32) / H, tl[0], va="center")
        fig.text(xx, 1 - (top - 1.05) / H, "\n".join(t for t in tl[1:3] if t), va="top", fontsize=SMALL,
                 linespacing=1.25)
        fig.text(xx, 1 - (top - 0.2) / H, tl[3], va="center", fontsize=SMALL, color=S.GREY)
    width = 3 * side + 2 * gap
    yb = top + side + 0.38
    lines = [ln for para in std_line(d) for ln in wrap(fig, para, W - x0 - 0.45, SMALL)]
    t = fig.text(x0 / W, 1 - yb / H, "\n".join(lines), va="top", fontsize=SMALL, linespacing=1.3)
    fig.canvas.draw()
    yend = (fig.bbox.y1 - t.get_window_extent(fig.canvas.get_renderer()).y0) / S.DPI
    yr = f["meta"]["post_date"][:4]
    fig.text((x0 + width) / W, 1 - (yend + 0.25) / H, CREDIT.format(yr=yr), va="center",
             ha="right", fontsize=SMALL, color=S.GREY)
    L.save()
    back_labels(fig)        # tag boxes and backings stay in the text-free picture and the pptx background
    save(fig, "F18_caught", transparent=True, strict=not os.environ.get("DRAFT"))


def fig_grid(d):
    L = Ledger("F18b", "Six more verified fires with no standard label (fixed seed)")
    for rid in d["grid"]:
        ledger_rows(L, d, rid, rid)
    L.add("Grid draw", d["grid"], file=F, field="selection.grid_rule, seed",
          shown=f"seed {d['selection']['seed']}", note=d["selection"]["grid_rule"])
    fig = S.plt.figure(figsize=(W, H), dpi=S.DPI)
    side, gapx, gapy, top = 2.8, 0.4, 0.3, 0.95
    x0 = (W - 3 * side - 2 * gapx) / 2
    years = set()
    for k, rid in enumerate(d["grid"]):
        f = d["fires"][rid]
        years.add(f["meta"]["post_date"][:4])
        r_, c_ = divmod(k, 3)
        ax = chip(fig, x0 + c_ * (side + gapx), top + r_ * (side + gapy), side)
        ext = extent_m(f)
        ax.imshow(f["post"], extent=ext, origin="upper", interpolation="nearest", zorder=0).set_gid("bg:after")
        ax.set_xlim(0, ext[1])
        ax.set_ylim(0, ext[3])
        furniture(ax, f)
        overlay(ax, f, fs=SMALL)
    head = (f"Six more verified fires with no standard label, drawn with random seed {d['selection']['seed']} from the "
            f"{d['selection']['eligible'] - 1} other eligible released scar pairs; Sentinel-2 after the fire")
    fig.text(x0 / W, 1 - 0.18 / H, "\n".join(wrap(fig, head, 3 * side + 2 * gapx, S.PT_TEXT)), va="top",
             linespacing=1.25)
    fig.text((x0 + 3 * side + 2 * gapx) / W, 1 - (top + 2 * side + gapy + 0.3) / H,
             CREDIT.format(yr=", ".join(sorted(years))), va="center", ha="right", fontsize=SMALL, color=S.GREY)
    L.save()
    back_labels(fig)        # tag boxes and backings stay in the text-free picture and the pptx background
    save(fig, "F18b_caught_grid", transparent=True, strict=not os.environ.get("DRAFT"))


def main():
    d = load()
    fig_main(d)
    fig_grid(d)


if __name__ == "__main__":
    main()
