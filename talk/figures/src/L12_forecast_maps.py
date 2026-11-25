"""Legible F12 maps: Wapiti 2024, chance a cell burns and the mapped burns 36 h later (slot 900 x 520; D48).

Arrays, window and hours from F12_forecast_example.read (forecast workspace arrays checked against the preprint's
provenance hashes). Only the two maps, their colour bar and legend; the note under the maps and panel (c) are left
out as asked.
"""
import matplotlib.colors as mc
import numpy as np
from matplotlib.patches import Patch

import legible as G
import style as S
from F12_forecast_example import read
from prov import Ledger


def main():
    L = Ledger("L12", "Legible forecast maps: Wapiti 2024")
    ref, pred, prov, t, rows, cohort = read(L)
    b0 = ref["burned_area"][0, 0] > 0.5
    b1 = ref["burned_area"][1, 0] > 0.5
    valid = ref["pixel_valid"][0]
    prob = np.array(pred["probability"][0, 0], dtype=float)
    hours = round((t[1] - t[0]).total_seconds() / 3600)
    pad = int(round(prov["display_padding_km"] * 1000 / 375))
    rr, cc = np.where(b0)
    r0, r1 = max(rr.min() - pad, 0), min(rr.max() + pad + 1, b0.shape[0])
    c0, c1 = max(cc.min() - pad, 0), min(cc.max() + pad + 1, b0.shape[1])
    win = (slice(r0, r1), slice(c0, c1))
    cmap = S.ramp(S.BLUE)
    ink = np.array(mc.to_rgb(S.INK))
    fire = np.array(mc.to_rgb(S.RED))
    paper = np.array(mc.to_rgb(S.PAPER))
    fig = G.figure("F12_forecast_maps")
    side, top = 3.45, 0.6
    xs = [0.5, 4.95]
    heads = ["Chance a cell burns", f"Mapped burns, {hours} h later"]
    for k, x in enumerate(xs):
        ax = G.ax_in(fig, x, top, side, side)
        if k == 0:
            p = np.where(valid & ~b0, prob, np.nan)[win]
            img = cmap(np.nan_to_num(p))[..., :3]
        else:
            img = np.ones(b0[win].shape + (3,)) * paper
            img[(b1 & ~b0)[win]] = fire
        img[b0[win]] = ink
        ax.imshow(img, interpolation="nearest").set_gid("bg:map")
        G.strip(ax)
        G.text_in(fig, x, 0.3, heads[k])
        if k == 0:
            n5 = 5000 / 375
            h_, w_ = img.shape[:2]
            ax.plot([w_ - 2 - n5, w_ - 2], [h_ - 3, h_ - 3], color=S.INK, lw=4, solid_capstyle="butt")[0].set_gid(
                "bg:scale bar")
            ax.text(w_ - 2 - n5 / 2, h_ - 5, "5 km", ha="center", va="bottom")
            ax.annotate("", xy=(3, 2), xytext=(3, 11), arrowprops=dict(arrowstyle="-|>", color=S.INK, lw=1.6))
            ax.text(5.5, 7, "N", va="center", ha="left")
    yb = top + side
    cax = G.ax_in(fig, xs[0] + 0.1, yb + 0.22, side - 0.2, 0.17)
    sm = S.plt.cm.ScalarMappable(norm=mc.Normalize(0, 1), cmap=cmap)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal", ticks=[0, 0.5, 1])
    cb.ax.set_xticklabels(["0", "0.5", "1"])
    cb.outline.set_linewidth(0.8)
    W, H = fig._wh
    leg = fig.legend([Patch(facecolor=S.INK), Patch(facecolor=S.RED)], ["burned at cutoff", "new burn"],
                     loc="upper left", bbox_to_anchor=(xs[1] / W, 1 - (yb + 0.08) / H), frameon=False, ncol=1,
                     handlelength=1.0, handleheight=0.8, borderaxespad=0, borderpad=0, labelspacing=0.35)
    for hnd in leg.legend_handles:
        hnd.set_gid("bg:legend handle")
    L.save()
    G.save(fig, "F12_forecast_maps")


if __name__ == "__main__":
    main()
