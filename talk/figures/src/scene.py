"""Schematics as a list of simple shapes, drawn twice from the same description:
once with matplotlib (SVG, PDF, PNG) and once as native PowerPoint shapes (build_pptx.py).

Coordinates are inches from the top-left corner of the 13.333 x 7.5 in slide.
Every shape has a `name` (shown in PowerPoint's selection pane) and a `group`
(shapes with the same group are grouped in PowerPoint so they move together).
"""
import json

import matplotlib.patches as mp
from matplotlib.lines import Line2D
from matplotlib.path import Path

import style as S
from style import BUILD, H_IN, W_IN


class Scene:
    def __init__(self, name):
        self.name = name
        self.items = []

    # ----------------------------------------------------------- primitives
    def rect(self, x, y, w, h, *, fill=None, edge=None, lw=1.0, hatch=None, name, group=None,
             role="mark", radius=0.0):
        """role: mark (data, may not touch text) | box (container, text may sit inside) | bg (context)."""
        self.items.append(dict(t="rect", x=x, y=y, w=w, h=h, fill=fill, edge=edge, lw=lw,
                               hatch=hatch, name=name, group=group, role=role, radius=radius))

    def circle(self, cx, cy, r, *, fill=None, edge=None, lw=1.0, name, group=None, role="mark"):
        self.items.append(dict(t="circle", cx=cx, cy=cy, r=r, fill=fill, edge=edge, lw=lw,
                               name=name, group=group, role=role))

    def line(self, pts, *, color=S.INK, lw=1.5, arrow=False, dash=None, name, group=None,
             role="mark", head=0.12):
        """Polyline through pts [(x, y), ...]; arrow=True puts a head at the last point."""
        self.items.append(dict(t="line", pts=[list(p) for p in pts], color=color, lw=lw,
                               arrow=arrow, dash=dash, name=name, group=group, role=role, head=head))

    def text(self, x, y, s, *, size=S.PT_BODY, color=S.INK, bold=False, ha="left", va="center",
             name=None, group=None, italic=False):
        self.items.append(dict(t="text", x=x, y=y, s=s, size=size, color=color, bold=bold,
                               ha=ha, va=va, name=name or s[:40], group=group, italic=italic))

    def tick(self, cx, cy, size, *, color=S.SAFE, lw=3, name, group=None):
        """A check mark drawn as a two-segment line."""
        pts = [(cx - size * 0.5, cy), (cx - size * 0.15, cy + size * 0.35), (cx + size * 0.5, cy - size * 0.45)]
        self.line(pts, color=color, lw=lw, name=name, group=group)

    # ----------------------------------------------------------- matplotlib
    def draw(self, fig):
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, W_IN)
        ax.set_ylim(H_IN, 0)
        ax.set_axis_off()
        texts = []
        for z, it in enumerate(self.items):
            gid = {"box": "box", "bg": "bg", "mark": None}.get(it.get("role"), None)
            gid = f"{gid}:{it['name']}" if gid else it.get("name")
            if it["t"] == "rect":
                if it["radius"] > 0:
                    p = mp.FancyBboxPatch((it["x"], it["y"]), it["w"], it["h"],
                                          boxstyle=f"round,pad=0,rounding_size={it['radius']}",
                                          facecolor=it["fill"] or "none", edgecolor=it["edge"] or "none",
                                          linewidth=it["lw"] if it["edge"] else 0, hatch=it["hatch"])
                else:
                    p = mp.Rectangle((it["x"], it["y"]), it["w"], it["h"],
                                     facecolor=it["fill"] or "none", edgecolor=it["edge"] or "none",
                                     linewidth=it["lw"] if it["edge"] else 0, hatch=it["hatch"])
                p.set_gid(gid)
                p.set_zorder(z)
                ax.add_patch(p)
            elif it["t"] == "circle":
                p = mp.Circle((it["cx"], it["cy"]), it["r"], facecolor=it["fill"] or "none",
                              edgecolor=it["edge"] or "none", linewidth=it["lw"] if it["edge"] else 0)
                p.set_gid(gid)
                p.set_zorder(z)
                ax.add_patch(p)
            elif it["t"] == "line":
                xs = [p[0] for p in it["pts"]]
                ys = [p[1] for p in it["pts"]]
                if it["arrow"]:
                    # shaft stops at the base of the head
                    (x0, y0), (x1, y1) = it["pts"][-2], it["pts"][-1]
                    import math
                    L = math.hypot(x1 - x0, y1 - y0)
                    hl = it["head"]
                    ux, uy = (x1 - x0) / L, (y1 - y0) / L
                    xs[-1] = x1 - ux * hl * 0.9
                    ys[-1] = y1 - uy * hl * 0.9
                    bx, by = x1 - ux * hl, y1 - uy * hl
                    hw = hl * 0.55
                    head = mp.Polygon([(x1, y1), (bx - uy * hw, by + ux * hw), (bx + uy * hw, by - ux * hw)],
                                      closed=True, facecolor=it["color"], edgecolor="none")
                    head.set_gid(gid)
                    head.set_zorder(z + 0.5)
                    ax.add_patch(head)
                ln = Line2D(xs, ys, color=it["color"], linewidth=it["lw"],
                            linestyle=(0, it["dash"]) if it["dash"] else "-",
                            solid_capstyle="butt", solid_joinstyle="round")
                ln.set_gid(gid)
                ln.set_zorder(z)
                ax.add_line(ln)
            elif it["t"] == "text":
                t = ax.text(it["x"], it["y"], it["s"], fontsize=it["size"], color=it["color"],
                            fontweight="bold" if it["bold"] else "normal",
                            fontstyle="italic" if it["italic"] else "normal",
                            ha=it["ha"], va=it["va"], linespacing=1.15)
                t.set_gid(it["name"])
                t.set_zorder(10000)
                texts.append((t, it))
        return ax

    def save_spec(self, fig):
        """Write the shape list plus measured text boxes for build_pptx.py."""
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        items = []
        for it in self.items:
            it = dict(it)
            if it["t"] == "text":
                # find the matplotlib text by gid and measure it
                for t in fig.findobj(lambda a: hasattr(a, "get_text") and a.get_gid() == it["name"]
                                     and a.get_text() == it["s"]):
                    bb = t.get_window_extent(r)
                    it["box"] = [bb.x0 / S.DPI, H_IN - bb.y1 / S.DPI, bb.width / S.DPI, bb.height / S.DPI]
                    break
            items.append(it)
        (BUILD / f"{self.name}_scene.json").write_text(json.dumps({"name": self.name, "items": items},
                                                                  indent=1, ensure_ascii=False))
