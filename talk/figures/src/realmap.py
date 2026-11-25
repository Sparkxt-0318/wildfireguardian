"""Shared drawing for the real-map figures F07_map and F08_map (Wondang-ri, Uiseong-Andong, 18:00 KST 25 March 2025).

Everything drawn comes from build/F07_map.json (made by F07_map_data.py with the replay's own code) and the committed
planner files; the basemap from basemap.py. Coordinates are Web Mercator metres (EPSG:3857).
"""
import json
import math
from datetime import datetime, timedelta

import numpy as np
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

import style as S
from basemap import ATTRIBUTION, basemap, to_m
from prov import git_show

DATA = "talk/figures/build/F07_map.json"
PLACES = "planner/public/data/regions/uiseong_andong_2025/places.geojson"


def kst(sec, seconds=False):
    t = datetime(2025, 3, 25, 18, 0) + timedelta(seconds=float(sec))
    return t.strftime("%H:%M:%S" if seconds else "%H:%M")


def load():
    d = json.loads((S.FIGDIR / "build/F07_map.json").read_text())
    pl = json.loads(git_show(PLACES))["features"]
    entry = {f["properties"]["id"]: (f["properties"]["entry"]["lon"], f["properties"]["entry"]["lat"]) for f in pl}
    for v in d["villages"]:
        v["entry_lonlat"] = entry[v["id"]]
    d["node_m"] = to_m(np.array(d["node_lonlat"]))
    return d


def setup(ax, bbox, z, fade=0.55):
    img, ext = basemap(bbox, z, fade)
    im = ax.imshow(img, extent=ext, origin="upper", interpolation="lanczos", zorder=0)
    im.set_gid("bg:basemap")
    (x0, y0), (x1, y1) = to_m(np.array([[bbox[0], bbox[1]], [bbox[2], bbox[3]]]))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.75)
        sp.set_color(S.INK)
    return (x0, x1, y0, y1)


FIRE_ALPHA = 0.32
FIRE_TINT = S.tint(S.RED, FIRE_ALPHA)   # the fire fill as it looks on paper, for keys


def attribution(ax):
    t = ax.text(0.99, 0.015, ATTRIBUTION, transform=ax.transAxes, ha="right", va="bottom", fontsize=S.PT_TEXT,
                color=S.INK, zorder=13, bbox=dict(boxstyle="square,pad=0.15", facecolor=S.PAPER, edgecolor="none",
                                                  alpha=0.92))
    t.set_gid("attribution")
    return t


def fire(ax, d, max_block_s=0, alpha=FIRE_ALPHA):
    polys = [to_m(np.array(c["lonlat"])) for c in d["cells"] if c["block_s"] <= max_block_s]
    pc = PolyCollection(polys, facecolors=S.RED, edgecolors="none", alpha=alpha, zorder=1)
    pc.set_gid("bg:fire area")
    ax.add_collection(pc)
    return len(polys)


def segs(d, pairs):
    p = np.array(pairs)
    return np.stack([d["node_m"][p[:, 0]], d["node_m"][p[:, 1]]], axis=1)


def blocked(ax, d, lw=1.8):
    lc = LineCollection(segs(d, d["blocked_at_issue_pairs"]), colors=S.RED, linewidths=lw, zorder=3,
                        capstyle="round")
    lc.set_gid("bg:blocked roads")
    ax.add_collection(lc)


def line(ax, lonlat, color, lw, z, halo=True, gid="bg:route"):
    m = to_m(np.array(lonlat))
    if halo:
        ax.plot(m[:, 0], m[:, 1], color=S.PAPER, lw=lw + 2.6, solid_capstyle="round", zorder=z - 0.1)[0].set_gid(
            gid + " halo")
    ax.plot(m[:, 0], m[:, 1], color=color, lw=lw, solid_capstyle="round", zorder=z)[0].set_gid(gid)
    return m


def point(ax, lonlat, kind, size=None, z=8, gid=None):
    m = to_m(np.array(lonlat)).reshape(-1, 2)
    if kind == "shelter":
        a = ax.scatter(m[:, 0], m[:, 1], s=size or 70, marker="s", facecolor=S.PAPER, edgecolor=S.INK,
                       linewidths=1.4, zorder=z)
    elif kind == "village":
        a = ax.scatter(m[:, 0], m[:, 1], s=size or 110, marker="o", facecolor=S.INK, edgecolor=S.PAPER,
                       linewidths=1.4, zorder=z)
    else:  # village inside the fire area
        a = ax.scatter(m[:, 0], m[:, 1], s=size or 55, marker="o", facecolor=S.PAPER, edgecolor=S.INK,
                       linewidths=1.2, zorder=z)
    a.set_gid(gid or f"bg:{kind}")
    return m


def tag(ax, xy, text, dx=0, dy=0, ha="left", va="center"):
    """Label on a map, on a paper backing."""
    t = ax.annotate(text, xy=xy, xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=S.PT_TEXT,
                    color=S.INK, zorder=12,
                    bbox=dict(boxstyle="square,pad=0.18", facecolor=S.PAPER, edgecolor="none", alpha=0.92))
    return t


def scale_bar(ax, km=1.0, where=(0.04, 0.07)):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    lat = math.degrees(2 * math.atan(math.exp(((y0 + y1) / 2) / 6378137.0)) - math.pi / 2)
    L = km * 1000 / math.cos(math.radians(lat))         # Web Mercator metres for km on the ground
    bx = x0 + where[0] * (x1 - x0)
    by = y0 + where[1] * (y1 - y0)
    ax.add_patch(Rectangle((bx - 0.012 * (x1 - x0), by - 0.05 * (y1 - y0)), L + 0.024 * (x1 - x0) + 0.11 * (x1 - x0),
                           0.115 * (y1 - y0), facecolor=S.PAPER, edgecolor="none", alpha=0.92, zorder=11,
                           gid="bg:scale backing"))
    ax.plot([bx, bx + L], [by, by], color=S.INK, lw=3, solid_capstyle="butt", zorder=12)[0].set_gid("bg:scale bar")
    ax.text(bx + L + 0.015 * (x1 - x0), by, f"{km:g} km", va="center", ha="left", fontsize=S.PT_TEXT, zorder=13)
    return L


def key_line(fig, x_in, y_in, color, lw, text, W, H, w_in=0.45, alpha=1.0):
    ln = Line2D([x_in / W, (x_in + w_in) / W], [1 - y_in / H] * 2, transform=fig.transFigure, color=color, lw=lw,
                solid_capstyle="butt", alpha=alpha)
    ln.set_gid("bg:key")
    fig.add_artist(ln)
    return fig.text((x_in + w_in + 0.15) / W, 1 - y_in / H, text, va="center", ha="left")


def key_patch(fig, x_in, y_in, text, W, H, face, edge="none", alpha=1.0, marker=None, w_in=0.45, hatch=None):
    if marker:
        m = Line2D([(x_in + w_in / 2) / W], [1 - y_in / H], transform=fig.transFigure, marker=marker, ms=10,
                   mfc=face, mec=edge, mew=1.3, ls="none")
        m.set_gid("bg:key")
        fig.add_artist(m)
    else:
        r = Rectangle((x_in / W, 1 - (y_in + 0.13) / H), w_in / W, 0.26 / H, transform=fig.transFigure,
                      facecolor=face, edgecolor=edge, alpha=alpha, linewidth=0.6 if not hatch else 1.2,
                      hatch=hatch)
        r.set_gid("bg:key")
        fig.add_artist(r)
    return fig.text((x_in + w_in + 0.15) / W, 1 - y_in / H, text, va="center", ha="left")


__all__ = ["ATTRIBUTION", "attribution", "FIRE_TINT", "kst", "load", "setup", "fire", "segs", "blocked", "line", "point", "tag", "scale_bar",
           "key_line", "key_patch", "DATA", "PLACES"]


def back_labels(fig):
    """Copy the paper backing of every map label into the picture as a rectangle, so it stays when the words become
    PowerPoint text boxes (the text-free background keeps the backing). Call after the layout is final."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    for ax in fig.axes:
        for t in list(ax.texts):
            p = t.get_bbox_patch()
            if p is None or not t.get_visible():
                continue
            bb = p.get_window_extent(r).transformed(ax.transData.inverted())
            rect = Rectangle((bb.x0, bb.y0), bb.width, bb.height, facecolor=p.get_facecolor(), edgecolor="none",
                             zorder=t.get_zorder() - 0.5, clip_on=False)
            rect.set_gid("bg:label backing")
            ax.add_patch(rect)
