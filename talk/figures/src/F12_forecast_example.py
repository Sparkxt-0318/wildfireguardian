"""F12 forecast example: Wapiti 2024, forecast map against the mapped burns, and scores of three rules.

Slide 7 (full width). (a) forecast chance that each unburned cell burns by the endpoint (1,024 trajectories), with the
extent burned at the cutoff; (b) what was mapped as burned by the endpoint, new burns in red; (c) average precision
(0 to 1 axis) and Brier score of our forecast, FARSITE and "no new burn" over all 25 intervals. The maps carry the
selection warning as their own line. Regenerated from the archived arrays in the forecast workspace (read only), whose SHA-256
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
from matplotlib.patches import Patch

from figkit import add_caption, grid, save
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
    hours = round((t[1] - t[0]).total_seconds() / 3600)
    L.add("Hours from cutoff to endpoint", hours, file=f"{CASE}/reference.npz", repo=WS,
          field="time_utc[1] - time_utc[0], rounded", shown=f"{hours} h",
          note=f"{t[0]:%Y-%m-%d %H:%M} to {t[1]:%Y-%m-%d %H:%M} UTC")
    # display window: initial extent plus 6 km padding (provenance), north up
    pad = int(round(prov["display_padding_km"] * 1000 / 375))
    rr, cc = np.where(b0)
    r0, r1 = max(rr.min() - pad, 0), min(rr.max() + pad + 1, b0.shape[0])
    c0, c1 = max(cc.min() - pad, 0), min(cc.max() + pad + 1, b0.shape[1])
    win = (slice(r0, r1), slice(c0, c1))
    side, top, head_y = 3.5, 0.85, 0.42
    xs = [0.45, 0.45 + side + 0.3]
    ink = np.array(mc.to_rgb(S.INK))
    fire = np.array(mc.to_rgb(S.FIRE))
    cmap = mc.LinearSegmentedColormap.from_list("blue1", [S.WHITE, S.OURS])
    heads = ["Forecast: chance a cell burns", f"Mapped burns, {hours} h later"]
    for k, x in enumerate(xs):
        ax = fig.add_axes([x / W, 1 - (top + side) / H, side / W, side / H])
        if k == 0:
            p = np.where(valid & ~b0, prob, np.nan)[win]
            img = cmap(np.nan_to_num(p))[..., :3]
        else:
            img = np.ones(b0[win].shape + (3,))
            img[(b1 & ~b0)[win]] = fire
        img[b0[win]] = ink
        im = ax.imshow(img, interpolation="nearest")
        im.set_gid("bg:map")
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_linewidth(0.8)
        S.panel_letter(fig, x, head_y, "ab"[k])
        fig.text((x + 0.42) / W, 1 - head_y / H, heads[k], va="center")
        if k == 0:
            n5 = 5000 / 375
            h_, w_ = img.shape[:2]
            ax.plot([w_ - 2 - n5, w_ - 2], [h_ - 3, h_ - 3], color=S.INK, lw=3, solid_capstyle="butt")
            ax.text(w_ - 2 - n5 / 2, h_ - 4.5, "5 km", ha="center", va="bottom")
            ax.annotate("", xy=(3, 2), xytext=(3, 9), arrowprops=dict(arrowstyle="-|>", color=S.INK, lw=1.2))
            ax.text(5, 6.5, "N", va="center", ha="left")
    yb = top + side
    # colour bar under (a)
    cax = fig.add_axes([(xs[0] + 0.1) / W, 1 - (yb + 0.38) / H, (side - 0.2) / W, 0.15 / H])
    sm = S.plt.cm.ScalarMappable(norm=mc.Normalize(0, 1), cmap=cmap)
    cb = fig.colorbar(sm, cax=cax, orientation="horizontal", ticks=[0, 0.5, 1])
    cb.ax.set_xticklabels(["0", "0.5", "1"])
    cb.outline.set_linewidth(0.6)
    cb.ax.tick_params(labelsize=S.PT_TEXT)
    # legend under (b)
    fig.legend([Patch(facecolor=S.INK), Patch(facecolor=S.FIRE)],
               [f"burned at {t[0]:%d %b %H:%M} UTC", f"new burn by {t[1]:%d %b %H:%M} UTC"],
               loc="upper left", bbox_to_anchor=(xs[1] / W, 1 - (yb + 0.12) / H), frameon=False,
               handlelength=1.0, handleheight=0.9, borderaxespad=0, borderpad=0, labelspacing=0.8)
    fig.text(xs[0] / W, 1 - (yb + 1.25) / H, "Most favourable interval, chosen after results", va="center")
    # (c) scores over all intervals, absolute scales
    xc = 8.75
    S.panel_letter(fig, xc, head_y, "c")
    fig.text((xc + 0.42) / W, 1 - head_y / H, f"Scores over all {nint} intervals", va="center")
    names = {"ours": "our forecast", "FARSITE": "FARSITE", "no new burn": "no new burn"}
    cols = {"ours": S.OURS, "FARSITE": S.MID, "no new burn": S.LIGHT}
    xax, wax = 10.45, 1.85
    for j, (idx, label, xmax, ticks, fmt) in enumerate((
            (2, "Average precision (1 = perfect)", 1.0, [0, 0.5, 1], "{:.3f}"),
            (1, "Brier score (0 = perfect)", 0.045, [0, 0.02, 0.04], "{:.4f}"))):
        ya, ha_ = 1.0 + j * 2.35, 1.2
        a = fig.add_axes([xax / W, 1 - (ya + ha_) / H, wax / W, ha_ / H])
        for i, r in enumerate(rows):
            a.barh(i, r[idx], height=0.6, facecolor=cols[r[0]], edgecolor=S.INK, linewidth=0.6)
            a.annotate(fmt.format(r[idx]), (r[idx], i), xytext=(6, 0), textcoords="offset points", va="center",
                       color=S.OURS if r[0] == "ours" else S.INK)
        a.set_ylim(len(rows) - 0.4, -0.6)
        a.set_xlim(0, xmax)
        a.set_xticks(ticks)
        a.set_xticklabels([f"{v:g}" for v in ticks])
        grid(a, axis="x")
        a.set_yticks(range(len(rows)))
        a.set_yticklabels([names[r[0]] for r in rows])
        for tl, r in zip(a.get_yticklabels(), rows):
            tl.set_color(S.OURS if r[0] == "ours" else S.INK)
        a.set_xlabel(label, labelpad=S.LABEL_PAD)
    cap = add_caption(fig, (
        f"Figure 12. One Wapiti (2024) interval, picked after inspecting results as the most favourable, so it is an "
        f"illustration, not a validation. (a) Forecast chance that an unburned 375\u00a0m cell burns by the endpoint "
        f"({prov['n_samples']:,} trajectories); black: burned at the cutoff. (b) Mapped burns at the endpoint. "
        f"(c) Scores over all {nint} Wapiti intervals ({nent} cells, {nburn} new burns) on their full scales. "
        "Source: preprint, regenerated from the archived arrays."),
        x_in=0.45, width_in=12.45, top_in=5.95)
    L.save()
    save(fig, "F12_forecast_example", caption=cap)


if __name__ == "__main__":
    main()
