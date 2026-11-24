"""F14 reliability (backup): predicted against observed new-burn frequency, reported (mixed) model only.

Panels: (a) all bins; (b) the low-probability region enlarged. Values from the preprint table
figure/revision/wapiti_calibration_table.tex (input in template.tex as tab:endpointbins); the lowest-bin share from
template.tex. Error bars: Wilson 95% intervals computed from each bin's entries and new burns (the table gives the
counts; no interval is published).
"""
import math
import re

import numpy as np

import style as S
from figkit import add_caption, boxed_legend, grid, save
from prov import Ledger

PRE = "/Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint"
TAB = "figure/revision/wapiti_calibration_table.tex"


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def read(L):
    txt = L.local_text(TAB, PRE)
    rows = []
    for m in re.finditer(r"\$\[([\d.]+),([\d.]+)[\)\]]\$ & ([\d,]+) & ([\d,]+) & ([\d.]+) & ([\d.]+)", txt):
        lo, hi, n, k, q, o = m.groups()
        rows.append(dict(lo=float(lo), hi=float(hi), n=int(n.replace(",", "")), k=int(k.replace(",", "")),
                         q=float(q) / 100, o=float(o) / 100))
    assert len(rows) == 7
    for r in rows:
        L.add(f"Bin [{r['lo']}, {r['hi']}): mean prediction, observed frequency, entries, new burns",
              [r["q"], r["o"], r["n"], r["k"]], file=TAB, repo=PRE, field="row of the tabular (Mean q %, Observed %)",
              n=f"{r['n']:,} entries")
    tex = L.local_text("template.tex", PRE)
    m = re.search(r"lowest mixed bin contains ([\d.]+)\\% of entries, with mean prediction\s+([\d.]+)\\% and mapped "
                  r"new-burn frequency ([\d.]+)\\%", tex)
    share, q0, o0 = (float(x) for x in m.groups())
    L.add("Lowest bin: share of entries / mean prediction / observed frequency (%)", [share, q0, o0],
          shown=f"{share:.2f}%, {q0:.4f}%, {o0:.4f}%", file="template.tex", repo=PRE,
          field="sentence 'The lowest mixed bin contains ...'", expected="93.91%, 0.0131%, 0.3642%",
          n=f"{sum(r['n'] for r in rows):,} entries")
    L.note("Error bars are Wilson 95% intervals computed here from the table's entries and new burns; the preprint "
           "applies no interval (its caption says so).")
    return rows, share, q0, o0


def main():
    L = Ledger("F14", "Reliability, reported model")
    rows, share, q0, o0 = read(L)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    q = np.array([r["q"] for r in rows])
    o = np.array([r["o"] for r in rows])
    ci = np.array([wilson(r["k"], r["n"]) for r in rows])
    specs = [((0.45 + 1.1, 0.40, 4.25, 4.25), 0.62, [0, 0.2, 0.4, 0.6], "a"),
             ((7.4 + 1.1, 0.40, 4.25, 4.25), 0.062, [0, 0.02, 0.04, 0.06], "b")]
    for (l, t, w, h), lim, ticks, letter in specs:
        ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
        grid(ax)
        ax.plot([0, lim], [0, lim], ls=(0, (4, 3)), color=S.MID, lw=1.0, label="perfect reliability")
        sel = (q <= lim) & (o <= lim)
        ax.errorbar(q[sel], o[sel], yerr=[o[sel] - ci[sel, 0], ci[sel, 1] - o[sel]], fmt="o", ms=7,
                    color=S.OURS, mec=S.INK, mew=0.6, ecolor=S.INK, elinewidth=1.0, capsize=3,
                    label="reported model (bins)")
        ax.set_xlim(0, lim)
        ax.set_ylim(0, lim)
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        fmt = (lambda v: f"{v:.0%}") if lim > 0.1 else (lambda v: f"{v:.0%}")
        ax.set_xticklabels([fmt(v) for v in ticks])
        ax.set_yticklabels([""] + [fmt(v) for v in ticks[1:]])
        ax.set_xlabel("Predicted new-burn probability")
        ax.set_ylabel("Observed new-burn frequency")
        S.panel_letter(fig, l - 1.05, t - 0.05, letter)
        if letter == "a":
            boxed_legend(ax, loc="upper left", labelspacing=0.8)
            # the enlarged region of panel b
            ax.add_patch(S.plt.Rectangle((0, 0), 0.062, 0.062, fill=False, edgecolor=S.INK, lw=0.8, ls=(0, (2, 2))))
        else:
            pass

    n = sum(r["n"] for r in rows)
    cap = add_caption(fig, (
        "Figure 14. Reliability of the reported (mixed) model on the Wapiti survey-endpoint cohort: mean predicted "
        "new-burn probability against mapped new-burn frequency in seven fixed bins (edges 0, 0.01, 0.02, 0.05, 0.1, "
        f"0.2, 0.5, 1; {n:,} initially unburned cell-interval entries, one fire). (b) enlarges the dashed region of "
        f"(a). The lowest bin holds {share:.2f}% of entries, with mean prediction {q0:.4f}% and observed frequency "
        f"{o0:.4f}%. Error bars: Wilson 95% intervals from the bin counts, computed for this figure. Source: preprint "
        "Table tab:endpointbins (wapiti_calibration_table.tex) and template.tex."), x_in=0.45, width_in=12.45,
        top_in=5.78)
    L.save()
    save(fig, "F14_reliability", caption=cap)


if __name__ == "__main__":
    main()
