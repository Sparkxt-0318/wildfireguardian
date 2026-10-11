"""Explain the actual FishCreek arrival support and current burned-state mask."""

from hashlib import sha256
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch, Rectangle
import numpy as np
import rasterio


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE = ROOT / "wildfire_burned_area_hourly/environmental_data/regions/WY-BTF-002416_FishCreek/arrival_time_hours.tif"
CUTOFF_HOURS = 48.0
POINTS = {"A": (22, 31), "B": (56, 29), "C": (30, 62), "D": (7, 19)}
COLORS = ["#d85b35", "#3b82bd", "#d9dde2"]


def main():
    with rasterio.open(SOURCE) as src:
        raw = src.read(1)
        masked = src.read(1, masked=True)
        known = ~np.ma.getmaskarray(masked) & np.isfinite(masked.data)
        nodata = src.nodata
        tags = src.tags()
        transform = tuple(src.transform)[:6]
        epsg = src.crs.to_epsg()
    burned = known & (raw <= CUTOFF_HOURS)
    unburned = known & (raw > CUTOFF_HOURS)
    state = np.full(raw.shape, 2, dtype=np.uint8)
    state[burned], state[unburned] = 0, 1
    assert (int(burned.sum()), int(unburned.sum()), int((~known).sum())) == (191, 2451, 4877)
    assert np.all(raw[~known] == nodata)
    for key, expected in [("A", 0), ("B", 1), ("C", 2), ("D", 1)]:
        assert state[POINTS[key]] == expected
    r, c = POINTS["D"]
    patch = state[r-2:r+3, c-2:c+3]
    assert int((patch == 2).sum()) == 8 and not (patch == 0).any()

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
                         "axes.titlesize": 14, "axes.labelsize": 11,
                         "figure.facecolor": "white", "axes.spines.top": False,
                         "axes.spines.right": False})
    fig = plt.figure(figsize=(15.5, 10.5))
    gs = fig.add_gridspec(2, 3, left=.045, right=.98, bottom=.11, top=.825,
                          width_ratios=[1, 1, .95], height_ratios=[1, .30],
                          hspace=.19, wspace=.23)
    left = gs[0, 0].subgridspec(2, 1, height_ratios=[1, .20], hspace=.21)
    middle = gs[0, 1].subgridspec(2, 1, height_ratios=[1, .20], hspace=.21)
    right = gs[0, 2].subgridspec(2, 1, height_ratios=[1, .29], hspace=.08)
    ax_arrival = fig.add_subplot(left[0])
    ax_colorbar = fig.add_subplot(left[1]); ax_colorbar.axis("off")
    ax_state = fig.add_subplot(middle[0])
    ax_legend = fig.add_subplot(middle[1]); ax_legend.axis("off")
    ax_patch = fig.add_subplot(right[0])
    ax_caption = fig.add_subplot(right[1]); ax_caption.axis("off")
    fig.suptitle("Why the loader leaves some burned states unclassified", fontsize=23, fontweight="bold", y=.965)
    fig.text(.5, .918, "FishCreek | 23 Aug 2024, 00:00 UTC | cutoff = 48 hours after the event origin", ha="center", fontsize=14)
    fig.text(.5, .886, "Actual 103 × 73 arrival raster; 375 m cells. The rectangular grid extends beyond the event footprint.", ha="center", color="#495565", fontsize=12)

    cm = plt.get_cmap("cividis").copy()
    cm.set_bad(COLORS[2])
    im = ax_arrival.imshow(np.ma.array(raw, mask=~known), cmap=cm, vmin=0, vmax=1400, interpolation="nearest")
    ax_arrival.set_title("1. Arrival-time reconstruction", loc="left", pad=13)
    cb = fig.colorbar(im, cax=ax_colorbar.inset_axes([0, .58, 1, .20]), orientation="horizontal",
                      ticks=[0, 400, 800, 1200])
    cb.set_label("Estimated arrival (hours after event origin)", fontsize=10)
    cb.ax.tick_params(labelsize=10)
    cmap_state = ListedColormap(COLORS)
    norm = BoundaryNorm([-.5, .5, 1.5, 2.5], 3)
    ax_state.imshow(state, cmap=cmap_state, norm=norm, interpolation="nearest")
    ax_state.set_title("2. Current state at the 48-hour cutoff", loc="left", pad=13)
    handles = [Patch(facecolor=COLORS[0], label="Burned by cutoff: 191"),
               Patch(facecolor=COLORS[1], label="Not yet burned: 2,451"),
               Patch(facecolor=COLORS[2], edgecolor="#aaa", label="No arrival value: 4,877")]
    ax_legend.legend(handles=handles, loc="center", frameon=False, fontsize=11)
    for ax in (ax_arrival, ax_state):
        ax.set(xlabel="Grid column", ylabel="Grid row")
        ax.tick_params(labelsize=10)
        ax.contour(known.astype(int), levels=[.5], colors="#344252", linewidths=.6)
        for key, (rr, cc) in POINTS.items():
            ax.scatter([cc], [rr], s=285, facecolor="white", edgecolor="#172536", linewidth=1.2, zorder=5)
            ax.text(cc, rr, key, color="#172536", fontsize=11, fontweight="bold", ha="center", va="center", zorder=6)
        ax.add_patch(Rectangle((c-2.5, r-2.5), 5, 5, fill=False, edgecolor="#e8a500", linewidth=2.4))

    ax_patch.imshow(patch, cmap=cmap_state, norm=norm, interpolation="nearest")
    ax_patch.set_title("3. D: a known-unburned edge cell", loc="left", pad=13)
    ax_patch.set_xticks(range(5), labels=range(c-2, c+3))
    ax_patch.set_yticks(range(5), labels=range(r-2, r+3))
    ax_patch.set(xlabel="Grid column", ylabel="Grid row")
    ax_patch.set_xticks(np.arange(-.5, 5, 1), minor=True)
    ax_patch.set_yticks(np.arange(-.5, 5, 1), minor=True)
    ax_patch.grid(which="minor", color="white", linewidth=2)
    ax_patch.tick_params(which="minor", bottom=False, left=False)
    for rr in range(5):
        for cc in range(5):
            label = "?" if patch[rr, cc] == 2 else str(int(patch[rr, cc] == 0))
            ax_patch.text(cc, rr, label, ha="center", va="center", fontsize=19,
                          fontweight="bold", color="#273747" if label == "?" else "white")
    ax_patch.add_patch(Rectangle((1.52, 1.52), .96, .96, fill=False, edgecolor="#ffcd33", linewidth=4))
    ax_caption.text(.5, .30, "Target D is unburned at the cutoff.\nIts 5 × 5 neighborhood has 8 unknown source cells.\nNo observed burned source therefore does not prove\nthat every source is unburned.",
                  transform=ax_caption.transAxes, ha="center", va="center", fontsize=11.5,
                  linespacing=1.35, color="#344252")

    descriptions = [
        ("A", COLORS[0], f"Arrival = {raw[POINTS['A']]:.2f} h ≤ 48 h", "Estimated already burned", "B = 1; validity = True"),
        ("B", COLORS[1], f"Arrival = {raw[POINTS['B']]:.2f} h > 48 h", "Estimated not yet burned", "B = 0; validity = True"),
        ("C", COLORS[2], "Arrival = −1: source NoData", "No reconstructed arrival time", "Stored B = 0; validity = False"),
    ]
    for j, (letter, color, line1, line2, line3) in enumerate(descriptions):
        ax = fig.add_subplot(gs[1, j]); ax.axis("off")
        ax.add_patch(Rectangle((0, .02), 1, .96, transform=ax.transAxes,
                               facecolor="#f5f7fa", edgecolor="#d9dfe7", linewidth=1))
        ax.text(.05, .76, letter, transform=ax.transAxes, fontsize=18, fontweight="bold",
                bbox=dict(boxstyle="circle,pad=.25", facecolor=color, edgecolor="none"),
                color="white" if letter != "C" else "#273747")
        ax.text(.19, .80, line1, transform=ax.transAxes, fontsize=12, fontweight="bold", va="center")
        ax.text(.05, .48, line2, transform=ax.transAxes, fontsize=12, va="center")
        ax.text(.05, .20, line3, transform=ax.transAxes, fontsize=11, color="#344252", va="center")
    fig.text(.045, .058, "Gray is outside the rasterized final-event reconstruction support, including small excluded holes; it is not a cloud-gap diagnosis.", fontsize=11, color="#344252")
    fig.text(.045, .030, "The footprint outline is the raster validity boundary, not an independently supplied survey polygon. All times and states are retrospective estimates.", fontsize=10.5, color="#5a6675")
    for suffix in ("png", "svg"):
        fig.savefig(OUT / f"burn_state_coverage.{suffix}", dpi=180, facecolor="white")
    plt.close(fig)
    np.savez_compressed(OUT / "figure_data.npz", arrival_hours=raw, arrival_valid=known,
                        state=state, cutoff_hours=CUTOFF_HOURS, state_class_names=np.array(["estimated_burned", "estimated_not_yet_burned", "source_nodata"]),
                        affine_transform=transform, epsg=epsg)
    result = dict(event_id=tags["event"], cutoff_utc="2024-08-23T00:00:00Z", t0_utc=tags["t0_utc"],
                  cutoff_hours=CUTOFF_HOURS, shape=list(raw.shape), nodata=nodata,
                  estimated_burned_cells=int(burned.sum()), estimated_not_yet_burned_cells=int(unburned.sum()),
                  source_nodata_cells=int((~known).sum()), source_path=str(SOURCE.relative_to(ROOT)),
                  source_sha256=sha256(SOURCE.read_bytes()).hexdigest(),
                  examples={key:dict(row=rr, column=cc, source_arrival_hours=float(raw[rr,cc]),
                                     arrival_valid=bool(known[rr,cc])) for key,(rr,cc) in POINTS.items()},
                  D_unknown_source_cells=8,
                  figure_semantics="Source reconstruction support and arrival-only loader states, not independent observed fire states")
    (OUT / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
