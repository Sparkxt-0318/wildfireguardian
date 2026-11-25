"""Legible F14: fixed-bin reliability, our model against the other models (slot 760 x 600; DECISIONS.md D48).

Our model (mixed): the preprint table figure/revision/wapiti_calibration_table.tex (F14_reliability.read), with the
Wilson 95% intervals F14 computes from its counts. The other displayed forecasts (23 model variants, FARSITE and
"no new burn") have no data file on this machine; they are read from the vector paths of the preprint's
figure/revision/endpoint_reliability.pdf ("Fixed-bin reliability", left panel, axes 0 to 1): pdftocairo turns the
PDF into SVG, each stroked polyline is one model's bin points, mapped to data by the panel's own tick marks. The
check: the mixed model's polyline read the same way must equal the table to within 0.0005 on both axes.
"""
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import legible as G
import style as S
from F14_reliability import PRE, read, wilson
from prov import Ledger

PDF = "figure/revision/endpoint_reliability.pdf"
MIXED = "rgb(83.920288%, 25.881958%, 14.509583%)"
NO_NEW = "rgb(7.843018%, 18.431091%, 26.274109%)"


def _paths(svg):
    body = svg[svg.index("</defs>"):]
    out = []
    for p in re.findall(r"<path ([^>]*)/>", body):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', p))
        d = a.get("d", "")
        m = [float(x) for x in re.findall(r"-?\d+\.?\d*", a.get("transform", ""))] or [1, 0, 0, 1, 0, 0]
        if "C" in d:
            continue
        pts = np.array(list(map(float, re.findall(r"-?\d+\.?\d*", d)))).reshape(-1, 2)
        xy = np.c_[m[0] * pts[:, 0] + m[2] * pts[:, 1] + m[4], m[1] * pts[:, 0] + m[3] * pts[:, 1] + m[5]]
        out.append(dict(stroke=a.get("stroke"), fill=a.get("fill"), width=float(a.get("stroke-width", 1)),
                        closed="Z" in d, xy=xy))
    return out


def others(L, rows):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftocairo", "-svg", str(Path(PRE) / PDF), f"{td}/r.svg"], check=True)
        P = _paths(Path(td, "r.svg").read_text())
    black = [p for p in P if p["stroke"] == "rgb(0%, 0%, 0%)" and not p["closed"]]
    # left panel: the spines are the longest black lines starting at the leftmost origin
    xt = sorted({round(p["xy"][0, 0], 2) for p in black if len(p["xy"]) == 2 and p["xy"][0, 1] != p["xy"][1, 1]
                 and abs(p["xy"][1, 1] - p["xy"][0, 1]) < 5})
    yt = sorted({round(p["xy"][0, 1], 2) for p in black if len(p["xy"]) == 2 and p["xy"][0, 0] != p["xy"][1, 0]
                 and abs(p["xy"][1, 0] - p["xy"][0, 0]) < 5})
    xt = [v for v in xt if v < xt[0] + 460]          # the left panel's six x ticks (0, 0.2, ..., 1)
    yt0 = sorted({v for v in yt})[:6]
    assert len(xt) == 6 and len(yt0) == 6, (xt, yt0)
    x0, x1 = xt[0], xt[-1]
    y1, y0 = yt0[0], yt0[-1]                          # SVG y grows downward: y0 is data 0
    tox = lambda v: (v - x0) / (x1 - x0)             # noqa: E731
    toy = lambda v: (v - y0) / (y1 - y0)             # noqa: E731
    inside = lambda xy: ((xy[:, 0] >= x0 - 1) & (xy[:, 0] <= x1 + 1) & (xy[:, 1] <= y0 + 1)  # noqa: E731
                         & (xy[:, 1] >= y1 - 1)).all()
    lines = [p for p in P if not p["closed"] and p["stroke"] not in (None, "none", "rgb(0%, 0%, 0%)",
                                                                     "rgb(100%, 100%, 100%)")
             and not p["stroke"].startswith("rgb(90.97") and inside(p["xy"]) and len(p["xy"]) >= 2]
    diag = [p for p in lines if p["stroke"].startswith("rgb(54.998")]
    series = [p for p in lines if p not in diag]
    mixed = [p for p in series if p["stroke"] == MIXED]
    assert len(mixed) == 1
    mq, mo = tox(mixed[0]["xy"][:, 0]), toy(mixed[0]["xy"][:, 1])
    tq, to = np.array([r["q"] for r in rows]), np.array([r["o"] for r in rows])
    err = max(np.abs(mq - tq).max(), np.abs(mo - to).max())
    assert err < 5e-4, err
    rest = [(tox(p["xy"][:, 0]), toy(p["xy"][:, 1])) for p in series if p["stroke"] != MIXED]
    # "no new burn": a single marker (filled path), its centre
    nn = [p for p in P if p["fill"] == NO_NEW and p["stroke"] in (None, "none") and inside(p["xy"].mean(0)[None, :])]
    nn_pts = []
    if nn:
        c = np.mean([p["xy"].mean(0) for p in nn], axis=0)
        nn_pts = [(tox(c[0]), toy(c[1]))]
    L.add("Other displayed forecasts read from the vector figure (polylines / single points)",
          [len(rest), len(nn_pts)], file=PDF, repo=PRE,
          field="pdftocairo -svg; stroked polylines inside the left panel, mapped by its tick marks",
          shown="grey lines, one legend entry 'other models'",
          expected="26 displayed forecasts in the preprint caption = mixed + the others",
          note=f"mixed model read the same way equals wapiti_calibration_table.tex within {err:.5f}")
    return rest, nn_pts, err


def main():
    L = Ledger("L14", "Legible reliability: our model against the other models")
    rows, share, q0, o0 = read(L)
    rest, nn_pts, err = others(L, rows)
    assert len(rest) + len(nn_pts) + 1 == 26, (len(rest), len(nn_pts))
    fig = G.figure("F14_reliability")
    ax = G.ax_in(fig, 2.1, 0.25, 4.65, 4.65)
    for v in (0.2, 0.4, 0.6, 0.8):
        ax.axhline(v, color=S.tint(S.GREY, 0.18), lw=0.8, zorder=0).set_gid("bg:grid")
        ax.axvline(v, color=S.tint(S.GREY, 0.18), lw=0.8, zorder=0).set_gid("bg:grid")
    h_perf, = ax.plot([0, 1], [0, 1], ls=(0, (5, 3)), color=S.INK, lw=1.6, zorder=2)
    h_other = None
    for q, o in rest:
        h_other, = ax.plot(q, o, color=S.GREY, lw=1.2, alpha=0.55, marker="o", ms=3.5, mew=0, zorder=1)
    for q, o in nn_pts:
        ax.plot([q], [o], color=S.GREY, marker="P", ms=8, mew=0, alpha=0.8, zorder=1)
    q = np.array([r["q"] for r in rows])
    o = np.array([r["o"] for r in rows])
    ci = np.array([wilson(r["k"], r["n"]) for r in rows])
    ax.errorbar(q, o, yerr=[o - ci[:, 0], ci[:, 1] - o], fmt="none", ecolor=S.BLUE, elinewidth=1.4, capsize=4,
                zorder=3)
    h_ours, = ax.plot(q, o, color=S.BLUE, lw=3.0, marker="o", ms=9, mec=S.PAPER, mew=1.2, zorder=4)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    tk = [0, 0.2, 0.4, 0.6, 0.8, 1]
    ax.set_xticks(tk)
    ax.set_yticks(tk)
    ax.set_xticklabels([f"{v:g}" for v in tk])
    ax.set_yticklabels([""] + [f"{v:g}" for v in tk[1:]])
    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Observed frequency", labelpad=16)
    ax.text(0.985, 0.68, "perfect", ha="right", va="center")      # under the diagonal's top end
    leg = ax.legend([h_ours, h_other], ["our model", "other models"], loc="upper left",
                    frameon=False, borderaxespad=0.4, handlelength=1.3, labelspacing=0.7)
    for hnd in leg.legend_handles:
        hnd.set_gid("bg:legend handle")
    L.save()
    G.save(fig, "F14_reliability", notes=[f"others read from the vector PDF; mixed check error {err:.5f}"])


if __name__ == "__main__":
    main()
