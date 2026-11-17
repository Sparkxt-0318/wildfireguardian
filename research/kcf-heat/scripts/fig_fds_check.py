"""The FDS_CHECK figure: radiant flux vs distance ahead of the C064 head, five laws on one axis.

    python scripts/fig_fds_check.py B2.json OUT.png

Series (fixed categorical order; palette validated with the dataviz validator, relief = direct labels + line styles):
FDS radiometers (samples and binned geometric mean), voxel sum on the same run, closed form, v2 (repo law, E = 100),
frozen cap. Curves for the closed form and v2 use the run-mean front parameters from B2.json.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat import law, v2_adapter  # noqa: E402

C = {"fds": "#2a78d6", "voxel": "#eb6834", "cf": "#1baf7a", "v2": "#eda100", "cap": "#e87ba4"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def main(b2_path, out):
    b = json.loads(Path(b2_path).read_text())
    s = b["samples"]
    d = np.array([x["d"] for x in s]); fds = np.array([x["fds"] for x in s]); req = np.array([x["requested"] for x in s])
    R, I, D, W, chi = b["spread_m_s"], b["mean_intensity_kw_m"], b["mean_depth_m"], b["mean_width_m"], b["radiant_fraction"]
    dd = np.geomspace(1.0, 60.0, 80)
    cf = [law.line_flux(x, chi, I / R, R, D / R, W / 2) for x in dd]
    v2 = [v2_adapter.v2_flux(x, D, W, I, receiver_height_m=1.5)[0] for x in dd]
    mids = [np.sqrt(r["d_bin_m"][0] * r["d_bin_m"][1]) for r in b["bins"]]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                         "xtick.color": INK2, "ytick.color": INK2})
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200)
    fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    ax.grid(True, which="major", color=GRID, lw=0.6); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.scatter(d[req], fds[req], s=9, color=C["fds"], alpha=0.45, lw=0, label="FDS radiometers, x = 102/105/108 m (samples)")
    ax.scatter(d[~req], fds[~req], s=9, facecolors="none", edgecolors=C["fds"], alpha=0.6, lw=0.6,
               label="FDS radiometers, x = 80/90 m (supplementary)")
    ax.plot(mids, [r["fds_geomean"] for r in b["bins"]], color=C["fds"], lw=2, marker="o", ms=4, label="FDS, binned geometric mean")
    ax.plot(mids, [r["voxel_geomean"] for r in b["bins"]], color=C["voxel"], lw=2, ls="-.", marker="s", ms=4,
            label="Voxel sum, same run (0.32 HRRPUV, no absorption)")
    ax.plot(dd, cf, color=C["cf"], lw=2, label="Closed form, finite front (this note)")
    ax.plot(dd, v2, color=C["v2"], lw=2, ls="--", label="v2 panel law, E = 100 kW/m² (repo)")
    ax.axhline(law.packet_frozen_cap(), color=C["cap"], lw=2, ls=":", label="Frozen law cap, 0.703 kW/m²")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(1, 60); ax.set_ylim(0.01, 200)
    ax.set_xticks([1, 2, 3, 5, 8, 12, 20, 30, 60]); ax.set_xticklabels(["1", "2", "3", "5", "8", "12", "20", "30", "60"])
    ax.set_xlabel("Distance ahead of the leading edge, d (m)   [edge: HRRPUV > 20 kW/m³ on the centreline]")
    ax.set_ylabel("Radiant flux to a receiver facing the fire (kW/m²)")
    lab = dict(fontsize=8, va="center", ha="left")
    ax.text(61, v2[-1], "v2", color=INK, **lab); ax.text(61, cf[-1] / 1.2, "closed form", color=INK, **lab)
    ax.text(61, b["bins"][-1]["voxel_geomean"] * 1.25, "voxel sum", color=INK, **lab)
    ax.text(61, b["bins"][-1]["fds_geomean"], "FDS", color=INK, **lab); ax.text(61, law.packet_frozen_cap(), "frozen cap", color=INK, **lab)
    for q, name in ((10, "10 kW/m² vehicle"), (2.5, "2.5 kW/m² people")):
        ax.axhline(q, color=INK2, lw=0.6, ls=(0, (1, 3)))
        ax.text(1.05, q * 1.12, name, color=INK2, fontsize=7)
    fig.suptitle("C064 head approach: radiant flux against distance to the front", x=0.02, ha="left", fontsize=11, color=INK)
    ax.set_title("Model-to-model only: FDS 6.11.1 at 1 m cells, one grass fire (head ~60 m wide). Receiver 1.5 m high, on the centreline.",
                 loc="left", fontsize=7.5, color=INK2)
    ax.legend(loc="lower left", fontsize=7, frameon=False)
    fig.subplots_adjust(left=0.1, right=0.86, top=0.88, bottom=0.11)
    fig.savefig(out, facecolor=SURF)
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
