"""F13 learned kernels (backup): the four mean effective kernels and their embedded sum, units h^-1.

No saved kernel matrices exist (searched the preprint folder and the forecast workspace), so the values are rebuilt
from the vector PDF figure/revision/named/kernel_matrix_overview.pdf (DECISIONS.md D24):
  1. the five matrix images and their five colour-bar images are extracted with pdfimages;
  2. every panel shows the 9 x 9 offset grid; each cell's colour is matched to the nearest colour of its own colour bar,
     giving a fraction f in [0, 1] of the bar (grey cells outside a native support and the zero centre are left empty);
  3. each bar is linear from 0 (its bottom tick label is 0), so value = f * vmax, with vmax chosen so that the kernel's
     sum equals the 'Sum' column of named/kernel_matrix_summary_table.tex;
  4. the rebuilt minimum, maximum and mean are compared with the same table row (SOURCES.md).
"""
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import style as S
from figkit import add_caption, save
from prov import Ledger

PRE = "/Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint"
PDF = "figure/revision/named/kernel_matrix_overview.pdf"
TAB = "figure/revision/named/kernel_matrix_summary_table.tex"
NAMES = ["3×3", "5×5", "7×7", "9×9", "Combined"]
TEXN = [r"$3\times3$", r"$5\times5$", r"$7\times7$", r"$9\times9$", "Combined"]


def extract():
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdfimages", "-png", str(Path(PRE) / PDF), f"{td}/img"], check=True)
        ims = [np.asarray(Image.open(p).convert("RGB")).astype(float) for p in sorted(Path(td).glob("img-*.png"))]
    panels = [im for im in ims if im.shape[0] == im.shape[1]]
    bars = [im for im in ims if im.shape[1] < 20]
    assert len(panels) == 5 and len(bars) == 5
    return panels, bars


def decode(panel, bar):
    cb = bar[::-1, bar.shape[1] // 2, :]          # bottom (0) to top (vmax)
    n = 9
    cs = panel.shape[0] / n
    f = np.full((n, n), np.nan)
    for r in range(n):
        for c in range(n):
            if r == 4 and c == 4:
                continue                            # fixed zero centre
            y0, y1 = int(r * cs + cs * 0.3), int(r * cs + cs * 0.7)
            x0, x1 = int(c * cs + cs * 0.3), int(c * cs + cs * 0.7)
            px = np.median(panel[y0:y1, x0:x1].reshape(-1, 3), axis=0)
            d = np.sqrt(((cb - px) ** 2).sum(axis=1))
            k = int(np.argmin(d))
            if d[k] > 25:                           # not on the colour bar: grey outside the native support
                continue
            f[r, c] = k / (len(cb) - 1)
    return f


def main():
    L = Ledger("F13", "Learned kernels (rebuilt from the vector PDF)")
    panels, bars = extract()
    tab = L.local_text(TAB, PRE)
    mats = []
    for name, tn, p, b in zip(NAMES, TEXN, panels, bars):
        row = re.search(re.escape(f"mixed & {tn} & ") + r"([\d.e-]+) & ([\d.e-]+)--([\d.e-]+) & [\d.e-]+ & ([\d.e-]+)",
                        tab)
        mean_t, lo_t, hi_t, sum_t = (float(x) for x in row.groups())
        f = decode(p, b)
        vmax = sum_t / np.nansum(f)
        m = f * vmax
        mats.append((name, m, vmax))
        L.add(f"{name}: sum used to scale the colour bar", sum_t, file=TAB, repo=PRE,
              field=f"row 'mixed & {tn}', column Sum", unit="h⁻¹")
        L.add(f"{name}: rebuilt min / max / mean against the table", [float(np.nanmin(m)), float(np.nanmax(m)),
              float(np.nanmean(m))], file=PDF, repo=PRE, field="decoded cell colours x vmax",
              unit="h⁻¹", n=f"{int(np.isfinite(m).sum())} cells",
              expected=f"table: {lo_t} / {hi_t} / {mean_t}",
              note=f"rebuilt vmax {vmax:.3g}; max differs from the table by "
                   f"{(np.nanmax(m) - hi_t) / hi_t * 100:+.1f}%, min by {(np.nanmin(m) - lo_t) / lo_t * 100:+.1f}%")
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    side, gap = 1.8, 0.66
    x0 = 1.15
    for i, (name, m, vmax) in enumerate(mats):
        x = x0 + i * (side + gap)
        ax = fig.add_axes([x / W, 1 - (0.95 + side) / H, side / W, side / H])
        im = ax.imshow(m * 1e4, cmap=S.CONTINUOUS_CMAP, vmin=0, vmax=np.nanmax(m) * 1e4, interpolation="nearest",
                       extent=(-4.5, 4.5, 4.5, -4.5))
        im.set_gid("bg:matrix")
        nanmask = ~np.isfinite(m)
        nanmask[4, 4] = False
        ax.imshow(np.where(nanmask, 1.0, np.nan), cmap="Greys", vmin=0, vmax=4, interpolation="nearest",
                  extent=(-4.5, 4.5, 4.5, -4.5)).set_gid("bg:outside")
        ax.plot([0], [0], marker="+", ms=9, mew=1.5, color=S.INK)
        ax.set_xticks([-4, 0, 4])
        ax.set_yticks([-3, 0, 3])
        if i:
            ax.set_yticklabels([])
        ax.set_xlabel("column offset")
        if i == 0:
            ax.set_ylabel("row offset")
        S.panel_letter(fig, x, 0.6, "abcde"[i])
        fig.text((x + 0.42) / W, 1 - 0.6 / H, name, va="center")
        cax = fig.add_axes([x / W, 1 - (0.95 + side + 1.05) / H, side / W, 0.13 / H])
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        top = np.nanmax(m) * 1e4
        cb.set_ticks([0, top])
        cb.ax.set_xticklabels(["0", f"{top:.1f}"])
        cb.outline.set_linewidth(0.6)
    fig.text(x0 / W, 1 - 4.55 / H, "colour bars: 10⁻⁴ h⁻¹", va="center")
    cap = add_caption(fig, (
        "Figure 13. Population-weighted mean effective kernels of the mixed model on the matched one-hour validation "
        "cohort: (a)–(d) the 3×3, 5×5, 7×7 and 9×9 branches and (e) their embedded sum, on the 9×9 grid of 375 m "
        "source offsets (grey: outside the branch's support; plus: the fixed zero centre). Each panel has its own "
        "linear colour bar, in 10⁻⁴ h⁻¹. Rebuilt from the preprint's vector figure (no saved matrices): cell colours "
        "read against each colour bar and scaled so each kernel's sum equals the preprint table; rebuilt minima and "
        "maxima are compared with the table in SOURCES.md. Source: preprint Figure fig:results:kernel-matrices and "
        "Table kernel_matrix_summary_table."), x_in=0.45, width_in=12.45, top_in=5.05)
    L.save()
    save(fig, "F13_kernels", caption=cap)


if __name__ == "__main__":
    main()
