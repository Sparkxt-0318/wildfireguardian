"""F15 exposure (slide 7, left half): Fish Creek, 23 Aug 2024, 00:00–01:00 UTC, 375 m grid.

(a) probability that visibility falls to 10 m or less during the hour, (b) hourly mean PM2.5, (c) hourly mean CO,
with the reconstructed burned perimeter as a thin outline.

The saved arrays are not on this machine (NEEDS.md), so the values are rebuilt from the session screenshots in
"Oral Presentation Figure/Heat Physics" (DECISIONS.md D26):
  * screenshot 001 (exposure panels): the panel frames, the km tick marks and the colour-bar tick marks are found by
    script; each 21 px cell (375 m at 56 px/km) is read at its centre and matched to the nearest colour of its panel's
    colour bar; the value is interpolated between the colour-bar ticks.
  * the colour-bar TICK VALUES and the km TICK LABELS cannot be read by script (no OCR on this machine). They were read
    by eye from the screenshot and are typed below as HAND_ENTERED; SOURCES.md lists them.
  * screenshot 002 (active-fire panels), panel "Reconstructed burned footprint": burned cells (colour 71,85,105) give
    the perimeter; their count is compared with the 191 stated in that panel's title (also read by eye).
"""
from pathlib import Path

import matplotlib.colors as mc
import numpy as np
from PIL import Image

import style as S
from figkit import add_caption, save
from prov import Ledger

HP = "/Users/jp/Desktop/Korea Code Fair/Oral Presentation Figure/Heat Physics"
IMG1 = "KakaoTalk_Photo_2026-11-24-07-54-45 001.png"
IMG2 = "KakaoTalk_Photo_2026-11-24-07-54-45 002.png"

# ---- HAND_ENTERED: read by eye from the screenshots (see module docstring)
HAND_ENTERED = {
    "x_tick_labels_km": [-1136, -1134, -1132, -1130, -1128, -1126, -1124, -1122],
    "y_tick_labels_km": [2390, 2388, 2386, 2384, 2382, 2380, 2378],
    "vis_ticks_pct": [100, 50, 25, 10, 5, 1, 0],                        # top to bottom
    "pm_ticks_ug_m3": [4000, 3500, 3000, 2500, 2000, 1500, 1000, 500, 0],
    "co_ticks_mg_m3": [17.5, 15.0, 12.5, 10.0, 7.5, 5.0, 2.5, 0.0],
    "footprint_cells_in_title": 191,
}


def runs(mask):
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i != p + 1:
            out.append((s + p) / 2)
            s = i
        p = i
    out.append((s + p) / 2)
    return out


def load(name):
    return np.asarray(Image.open(Path(HP) / name).convert("RGB")).astype(float)


def panel_grid(im, x0, y0, tick_row, tick_col):
    """Pixel geometry of one exposure panel from its tick marks (x0, y0: frame corner)."""
    lum = im.mean(axis=2)
    xt = [v for v in runs(lum[tick_row, x0 - 15:x0 + 830] < 120)][:8]
    xt = [x0 - 15 + v for v in xt]
    yt = [y0 - 15 + v for v in runs(lum[y0 - 15:y0 + 700, tick_col] < 120)][:7]
    pxkm = (xt[-1] - xt[0]) / (HAND_ENTERED["x_tick_labels_km"][-1] - HAND_ENTERED["x_tick_labels_km"][0])
    return xt, yt, pxkm


def colour_bar(im, xc, y0, y1, tick_values, x_tick_col):
    lum = im.mean(axis=2)
    ticks = [y0 + v for v in runs(lum[y0:y1, x_tick_col] < 120)]
    assert len(ticks) == len(tick_values), (ticks, tick_values)
    rows = np.arange(int(ticks[0]), int(ticks[-1]) + 1)
    cols = im[rows, xc, :]
    return rows, cols, np.array(ticks), np.array(tick_values, dtype=float)


def decode(im, x0, y0, nx, ny, cell, cb, covered=None):
    """Median colour of each cell's centre window, leaving out the white/grey perimeter-line pixels."""
    rows, cols, tpos, tval = cb
    out = np.full((ny, nx), np.nan)
    order = np.argsort(tpos)
    for i in range(ny):
        for j in range(nx):
            if covered is not None and covered[i, j]:
                continue
            cx, cy = int(x0 + (j + 0.5) * cell), int(y0 + (i + 0.5) * cell)
            win = im[cy - 7:cy + 8, cx - 7:cx + 8].reshape(-1, 3)
            line = (win.mean(axis=1) > 170) & (win.max(axis=1) - win.min(axis=1) < 40)
            if (~line).sum() < 20:
                continue
            px = np.median(win[~line], axis=0)
            d = np.sqrt(((cols - px) ** 2).sum(axis=1))
            r = rows[int(np.argmin(d))]
            out[i, j] = np.interp(r, tpos[order], tval[order])
    return out


def main():
    L = Ledger("F15", "Fish Creek exposure maps (rebuilt from screenshots)")
    im = load(IMG1)
    lum = im.mean(axis=2)
    # panel frames (top-left inner corner) found from the frame spines; offsets between panels are fixed by layout
    frames = {"vis": (113, 189), "pm": (1199, 189), "co": (113, 1133)}
    for k, (x0, y0) in frames.items():
        assert (lum[y0 + 100:y0 + 600, x0] < 60).all(), f"{k}: frame not found at {x0}"
    xt, yt, pxkm = panel_grid(im, 113, 189, 886, 109)
    cell = 0.375 * pxkm
    nx = int(round((933 - 113) / cell))
    ny = int(round((883 - 189) / cell))
    x_km0 = HAND_ENTERED["x_tick_labels_km"][0] + (113 - xt[0]) / pxkm
    y_km0 = HAND_ENTERED["y_tick_labels_km"][0] - (189 - yt[0]) / pxkm
    L.add("Grid read from screenshot 001: cells, px per km, origin (km)", [nx, ny, round(pxkm, 2), round(x_km0, 3),
          round(y_km0, 3)], file=IMG1, repo=HP, field="tick-mark pixel positions (script) + tick labels (HAND_ENTERED)",
          note="375 m cells; 39 x 33 expected from the frame width (820 px) and height (694 px)")
    cbs = {
        "vis": colour_bar(im, 980, 160, 910, HAND_ENTERED["vis_ticks_pct"], 1000),
        "pm": colour_bar(im, 2066, 160, 910, HAND_ENTERED["pm_ticks_ug_m3"], 2086),
        "co": colour_bar(im, 980, 1104, 1855, HAND_ENTERED["co_ticks_mg_m3"], 1000),
    }
    # the source's legend box ("Reconstructed burned perimeter") covers part of panel (a): those cells are unknown
    lb = (122, 444, 847, 873)                     # legend box in pixels, found by script (light pixels)
    covered = np.zeros((ny, nx), bool)
    for i in range(ny):
        for j in range(nx):
            cx, cy = 113 + (j + 0.5) * cell, 189 + (i + 0.5) * cell
            covered[i, j] = lb[0] - 6 <= cx <= lb[1] + 6 and lb[2] - 6 <= cy <= lb[3] + 6
    fields = {k: decode(im, *frames[k], nx, ny, cell, cbs[k], covered if k == "vis" else None) for k in frames}
    L.add("Panel (a) cells covered by the source legend (unknown, hatched)", int(covered.sum()), file=IMG1, repo=HP,
          field="cells whose centre lies in the legend box at px (122-444, 847-873)")
    for k, unit in (("vis", "%"), ("pm", "µg/m³"), ("co", "mg/m³")):
        f = fields[k]
        L.add(f"{k}: decoded maximum, median of positive cells, unknown cells",
              [float(np.nanmax(f)), float(np.nanmedian(f[f > 0.01 * np.nanmax(f)])), int(np.isnan(f).sum())], unit=unit,
              file=IMG1, repo=HP, field=f"panel cells matched to its colour bar; ticks HAND_ENTERED {HAND_ENTERED[k + '_ticks_' + ('pct' if k == 'vis' else 'ug_m3' if k == 'pm' else 'mg_m3')]}",
              n=f"{nx * ny} cells")
    # burned footprint from screenshot 002
    im2 = load(IMG2)
    lum2 = im2.mean(axis=2)
    # the footprint panel shows the same 39 x 33 grid; its cells are placed from the panel's own frame spines
    cols2 = [x for x in range(50, 1100) if (lum2[300:800, x] < 80).all()]
    rows2 = [y for y in range(150, 1000) if (lum2[y, 200:900] < 80).all()]
    fx0, fx1, fy0, fy1 = cols2[1] + 0.5, cols2[-2] + 0.5, rows2[0] + 0.5, rows2[-1] - 0.5
    cw, ch = (fx1 - fx0) / nx, (fy1 - fy0) / ny
    # that panel's legend (bottom left) holds a swatch in the burned colour: find the legend text by script and
    # leave out every cell under the legend box (text bbox widened to the swatch on its left)
    sub = im2[int(fy1) - 120:int(fy1), int(fx0):int(fx0) + 600]
    ty, tx = np.where(sub.sum(axis=2) < 150)
    lx0, lx1 = int(fx0) + 6, int(fx0) + tx.max() + 8
    ly0, ly1 = int(fy1) - 120 + ty.min() - 8, int(fy1) - 120 + ty.max() + 8
    burned = np.zeros((ny, nx), bool)
    for i in range(ny):
        for j in range(nx):
            px, py = int(fx0 + (j + 0.5) * cw), int(fy0 + (i + 0.5) * ch)
            if lx0 <= px <= lx1 and ly0 <= py <= ly1:
                continue
            c = np.median(im2[py - 4:py + 5, px - 4:px + 5].reshape(-1, 3), axis=0)
            burned[i, j] = np.abs(c - [71, 85, 105]).sum() < 40
    nb = int(burned.sum())
    L.add("Burned footprint cells read from screenshot 002", nb, file=IMG2, repo=HP,
          field="cells whose colour matches the 'previously burned' colour (71, 85, 105)",
          expected=f"{HAND_ENTERED['footprint_cells_in_title']} (panel title, read by eye)")
    L.note("HAND_ENTERED values (read by eye): " + "; ".join(f"{k} = {v}" for k, v in HAND_ENTERED.items()))
    L.note("Values between colour-bar ticks are interpolated linearly in bar position; the source bars are non-linear "
           "between ticks too, so a value between two ticks may differ from the source value.")
    L.save()

    # ---------------- figure
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    pw = 1.72
    ph = pw * ny / nx
    top = 0.95
    specs = [("vis", "(a)", "visibility ≤ 10 m", "probability (%)", HAND_ENTERED["vis_ticks_pct"], [0, 10, 100]),
             ("pm", "(b)", "PM2.5", "µg m⁻³", HAND_ENTERED["pm_ticks_ug_m3"], [0, 1000, 4000]),
             ("co", "(c)", "CO", "mg m⁻³", HAND_ENTERED["co_ticks_mg_m3"], [0, 5, 17.5])]
    ext = (0, nx * 0.375, 0, ny * 0.375)
    cmap = S.plt.get_cmap(S.CONTINUOUS_CMAP)
    for n, (k, letter, title, unit, ticks, show) in enumerate(specs):
        x = 1.0 + n * (pw + 0.47)
        ax = fig.add_axes([x / W, 1 - (top + ph) / H, pw / W, ph / H])
        # the source's non-linear scale: tick value -> its fractional position on the source bar
        rows, cols, tpos, tval = cbs[k]
        frac = (tpos.max() - tpos) / (tpos.max() - tpos.min())
        o = np.argsort(tval)
        fwd = lambda v, tv=tval[o], fr=frac[o]: np.interp(v, tv, fr)  # noqa: E731
        inv = lambda u, tv=tval[o], fr=frac[o]: np.interp(u, fr, tv)  # noqa: E731
        norm = mc.FuncNorm((fwd, inv), vmin=tval.min(), vmax=tval.max())
        im_ = ax.imshow(fields[k], cmap=cmap, norm=norm, extent=ext, origin="upper", interpolation="nearest")
        im_.set_gid("bg:field")
        unk = np.isnan(fields[k])
        if unk.any():
            ax.contourf(np.arange(nx) * 0.375 + 0.1875, (ny - np.arange(ny)) * 0.375 - 0.1875, unk.astype(float),
                        levels=[0.5, 1.5], colors=[S.LIGHT], hatches=["////"]).set_gid("bg:unknown")
        # burned perimeter: cell edges between burned and unburned cells
        segs = []
        for i in range(ny):
            for j in range(nx):
                if not burned[i, j]:
                    continue
                x0k, x1k = j * 0.375, (j + 1) * 0.375
                y1k, y0k = (ny - i) * 0.375, (ny - i - 1) * 0.375
                if i == 0 or not burned[i - 1, j]:
                    segs.append([(x0k, y1k), (x1k, y1k)])
                if i == ny - 1 or not burned[i + 1, j]:
                    segs.append([(x0k, y0k), (x1k, y0k)])
                if j == 0 or not burned[i, j - 1]:
                    segs.append([(x0k, y0k), (x0k, y1k)])
                if j == nx - 1 or not burned[i, j + 1]:
                    segs.append([(x1k, y0k), (x1k, y1k)])
        from matplotlib.collections import LineCollection
        lc = LineCollection(segs, colors=S.WHITE, linewidths=0.8)
        lc.set_gid("bg:perimeter")
        ax.add_collection(lc)
        ax.set_xticks([0, 5, 10])
        ax.set_yticks([0, 5, 10])
        ax.set_xlabel("km")
        if n == 0:
            ax.set_ylabel("km")
            ax.set_yticklabels(["", "5", "10"])
        else:
            ax.set_yticklabels([])
        S.panel_letter(fig, x, top - 0.3, letter[1])
        fig.text((x + 0.38) / W, 1 - (top - 0.3) / H, title, va="center")
        cax = fig.add_axes([x / W, 1 - (top + ph + 1.05) / H, pw / W, 0.12 / H])
        cb = fig.colorbar(im_, cax=cax, orientation="horizontal", ticks=show)
        cb.ax.set_xticklabels([f"{v:g}" for v in show])
        cb.outline.set_linewidth(0.6)
        fig.text((x + pw / 2) / W, 1 - (top + ph + 1.7) / H, unit, ha="center", va="center")
    cap = add_caption(fig, (
        "Figure 15. Modelled exposure for one fire-hour, Fish Creek, 23 August 2024, 00:00–01:00 UTC, on the 375 m "
        "grid: (a) probability that visibility falls to 10 m or less during the hour, (b) hourly mean PM2.5, (c) hourly "
        "mean CO; white outline: reconstructed burned perimeter; hatched: covered by the source's legend. Non-linear colour scales as in the source. Rebuilt "
        "from the session screenshots (saved arrays not available); colour-bar values read by eye. One fire-hour; not "
        "calibrated against measurements; concentrations are not danger probabilities."),
        x_in=0.45, width_in=12.45, top_in=5.75)
    save(fig, "F15_exposure", caption=cap)


if __name__ == "__main__":
    main()
