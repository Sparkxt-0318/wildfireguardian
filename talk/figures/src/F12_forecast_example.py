"""F12 forecast example: Wapiti 2024, three map panels and a three-rule score table.

Slide 6 (full width). (a) initial mapped extent at the cutoff, (b) predicted new-burn probability (1,024 trajectories),
(c) later mapped extent. Regenerated from the archived arrays in the forecast workspace (read only), whose SHA-256
match figure/revision/wapiti_spatial_provenance.json. Scores from figure/revision/wapiti_scores_table.tex; cohort
counts from template.tex.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.colors as mc
import numpy as np

import style as S
from figkit import add_caption, save
from prov import Ledger

PRE = "/Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint"
WS = "/Users/jp/Desktop/wildfire"
CASE = "runs/20261013_observed_stored_validation/cases/859cddc0f28778a02134"


def read(L):
    prov = json.loads(L.local_text("figure/revision/wapiti_spatial_provenance.json", PRE))
    arrays = {}
    for f in ("reference.npz", "m548_prediction.npz"):
        p = Path(WS) / CASE / f
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert h == prov["source_sha256"][f], f"{f} does not match the provenance hash"
        arrays[f] = np.load(p, allow_pickle=False)
    ref = arrays["reference.npz"]
    pred = arrays["m548_prediction.npz"]
    t = [datetime.fromtimestamp(int(x) / (1e9 if int(x) > 1e12 else 1), tz=timezone.utc) for x in ref["time_utc"]]
    L.add("Wapiti case arrays (initial and later extent, probability)", prov["case_id"],
          file=f"{CASE}/m548_prediction.npz", repo=WS,
          field="reference.burned_area[0|1, 0], m548_prediction.probability[0, 0]; SHA-256 equal to "
                "wapiti_spatial_provenance.json source_sha256", n=f"grid {prov['grid_shape']}, {prov['n_samples']} "
                                                                    "trajectories")
    L.add("Trajectories", prov["n_samples"], file="figure/revision/wapiti_spatial_provenance.json", repo=PRE,
          field="n_samples", expected="1,024")
    tab = L.local_text("figure/revision/wapiti_scores_table.tex", PRE)
    rows = []
    for lab, pat in (("ours", r"Our model & ([\d.]+) & ([\d.]+)"), ("FARSITE", r"FARSITE & ([\d.]+) & ([\d.]+)"),
                     ("no new burn", r"No-new-burn & ([\d.]+) & ([\d.]+)")):
        b, ap = re.search(pat, tab).groups()
        rows.append((lab, float(b), float(ap)))
        L.add(f"{lab}: Brier, average precision", [float(b), float(ap)], file="figure/revision/wapiti_scores_table.tex",
              repo=PRE, field=f"row '{pat.split(' &')[0]}', columns Brier, AP", n="25 intervals, 275,961 entries")
    tex = L.local_text("template.tex", PRE)
    m = re.search(r"Evaluation uses (\d+) available Wapiti survey intervals containing ([\d,]+) initially unburned "
                  r"cell-interval entries and ([\d,]+) newly mapped burns", tex.replace("\n", " "))
    nint, nent, nburn = m.groups()
    L.add("Cohort: intervals, entries, new burns", [nint, nent, nburn], file="template.tex", repo=PRE,
          field="sentence 'Evaluation uses 25 available Wapiti survey intervals ...'",
          expected="25 intervals, 275,961 cells, 2,525 new burns")
    L.note("Selection (provenance json): " + prov["selection"])
    return ref, pred, prov, t, rows, (nint, nent, nburn)


def main():
    L = Ledger("F12", "Forecast example: Wapiti 2024")
    ref, pred, prov, t, rows, (nint, nent, nburn) = read(L)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    b0 = ref["burned_area"][0, 0] > 0.5
    b1 = ref["burned_area"][1, 0] > 0.5
    valid = ref["pixel_valid"][0]
    prob = np.array(pred["probability"][0, 0], dtype=float)
    # display window: initial extent plus 6 km padding (provenance), north up
    pad = int(round(prov["display_padding_km"] * 1000 / 375))
    rr, cc = np.where(b0)
    r0, r1 = max(rr.min() - pad, 0), min(rr.max() + pad + 1, b0.shape[0])
    c0, c1 = max(cc.min() - pad, 0), min(cc.max() + pad + 1, b0.shape[1])
    win = (slice(r0, r1), slice(c0, c1))
    side = 2.7
    top = 0.6
    xs = [0.45, 0.45 + side + 0.25, 0.45 + 2 * (side + 0.25)]
    burned_rgb = np.array(mc.to_rgb(S.INK))
    grey = np.array(mc.to_rgb(S.MID))
    cmap = mc.LinearSegmentedColormap.from_list("blue1", [S.WHITE, S.OURS])
    labels = [f"initial mapped extent\n{t[0]:%d %b %Y, %H:%M} UTC",
              f"new-burn probability\n({prov['n_samples']:,} trajectories)",
              f"later mapped extent\n{t[1]:%d %b %Y, %H:%M} UTC"]
    for k, x in enumerate(xs):
        ax = fig.add_axes([x / W, 1 - (top + side) / H, side / W, side / H])
        img = np.ones(b0[win].shape + (3,))
        if k == 1:
            p = np.where(valid & ~b0, prob, np.nan)[win]
            img = cmap(np.nan_to_num(p))[..., :3]
            img[b0[win]] = grey
        else:
            bb = (b0 if k == 0 else b1)[win]
            img[bb] = burned_rgb if k == 0 else grey
            if k == 2:
                img[b0[win]] = burned_rgb
        im = ax.imshow(img, interpolation="nearest")
        im.set_gid("bg:map")
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_linewidth(0.8)
        S.panel_letter(fig, x, top - 0.25, "abc"[k])
        # panel label beneath, as separate text
        fig.text(x / W, 1 - (top + side + 0.15) / H, labels[k], fontsize=S.PT_TEXT, va="top", ha="left",
                 linespacing=1.2)
        if k == 0:
            n5 = 5000 / 375
            h_, w_ = img.shape[:2]
            ax.plot([w_ - 2 - n5, w_ - 2], [h_ - 3, h_ - 3], color=S.INK, lw=3, solid_capstyle="butt")
            ax.text(w_ - 2 - n5 / 2, h_ - 4.5, "5 km", ha="center", va="bottom", fontsize=S.PT_TEXT)
            ax.annotate("", xy=(3, 2), xytext=(3, 9), arrowprops=dict(arrowstyle="-|>", color=S.INK, lw=1.2))
            ax.text(5, 6.5, "N", fontsize=S.PT_TEXT, va="center", ha="left")
    # probability colour bar under panel b
    cax = fig.add_axes([xs[1] / W, 1 - (top + side + 1.12) / H, side / W, 0.15 / H])
    sm = S.plt.cm.ScalarMappable(norm=mc.Normalize(0, 1), cmap=cmap)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal", ticks=[0, 0.5, 1])
    cb.ax.set_xticklabels(["0", "0.5", "1"])
    cb.outline.set_linewidth(0.6)
    cb.ax.tick_params(labelsize=S.PT_TEXT)
    fig.text(xs[2] / W, 1 - (top + side + 0.95) / H, "black: burned at cutoff\ngrey in (c): burned by endpoint"
             "\ngrey in (b): burned at cutoff", fontsize=S.PT_TEXT, va="top", linespacing=1.2, color=S.INK)
    # three-rule table at the right
    tx = 9.95
    ty = 1.15
    colx = [tx, tx + 1.55, tx + 2.45]
    fig.add_artist(S.plt.Line2D([tx / W, 12.95 / W], [1 - ty / H] * 2, color=S.INK, lw=1.2))
    fig.text(colx[0] / W, 1 - (ty + 0.27) / H, "forecast", fontsize=S.PT_TEXT, va="center")
    fig.text((colx[1] + 0.55) / W, 1 - (ty + 0.27) / H, "Brier ↓", fontsize=S.PT_TEXT, va="center", ha="right")
    fig.text((colx[2] + 0.5) / W, 1 - (ty + 0.27) / H, "AP ↑", fontsize=S.PT_TEXT, va="center", ha="right")
    fig.add_artist(S.plt.Line2D([tx / W, 12.95 / W], [1 - (ty + 0.54) / H] * 2, color=S.INK, lw=0.7))
    for i, (lab, b, ap) in enumerate(rows):
        yy = ty + 0.54 + 0.42 * (i + 0.6)
        col = S.OURS if lab == "ours" else S.INK
        fig.text(colx[0] / W, 1 - yy / H, lab, fontsize=S.PT_TEXT, va="center", color=col)
        fig.text((colx[1] + 0.55) / W, 1 - yy / H, f"{b:.4f}", fontsize=S.PT_TEXT, va="center", ha="right", color=col)
        fig.text((colx[2] + 0.5) / W, 1 - yy / H, f"{ap:.3f}", fontsize=S.PT_TEXT, va="center", ha="right", color=col)
    yb = ty + 0.54 + 0.42 * 3 + 0.1
    fig.add_artist(S.plt.Line2D([tx / W, 12.95 / W], [1 - yb / H] * 2, color=S.INK, lw=1.2))
    fig.text(tx / W, 1 - (yb + 0.25) / H, f"{nint} intervals, {nent} cells,\n{nburn} new burns, one fire",
             fontsize=S.PT_TEXT, va="top", linespacing=1.2)
    fig.text(12.95 / W, 1 - (top - 0.25) / H, "selected example; Wapiti 2024", fontsize=S.PT_TEXT, va="center",
             ha="right", color=S.MID)
    cap = add_caption(fig, (
        f"Figure 12. One selected Wapiti (2024) interval: (a) mapped extent at the cutoff, (b) predicted probability "
        f"that an unburned 375\u00a0m cell burns by the endpoint (mean of {prov['n_samples']:,} recursive trajectories), "
        "(c) mapped extent at the endpoint. The interval was chosen after inspecting results, as the most favourable "
        f"Wapiti interval, so it is an illustration, not a validation. Table: scores over all {nint} Wapiti intervals "
        f"({nent} entries, {nburn} new burns; lower Brier and higher average precision, AP, are better). "
        "Source: preprint Figure fig:spatialprediction and Table wapiti_scores_table, regenerated from the archived arrays."),
        x_in=0.45, width_in=12.45, top_in=5.82)
    L.save()
    save(fig, "F12_forecast_example", caption=cap)


if __name__ == "__main__":
    main()
