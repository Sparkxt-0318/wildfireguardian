"""Booth figure: smart meters only versus an off-grid tag mesh, same synthetic fire (world 0). SYNTHETIC.

Renders existing configurations; no new parameters.
- Left: phase 1 default (smart meters on 50% of buildings, default grid faults), IDW after grid filtering.
- Right: phase 2 tags every 200 m of road, mesh relaying, 3 spread fire-exposed gateways, IDW of heard deaths.
Colour = reconstructed arrival time; white lines = true arrival every 15 min.

Usage: .venv/bin/python scripts/13_booth_figure.py
Writes figures/fig13_booth.png/.svg and results/booth_figure_metrics.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

from lastgasp import style  # noqa: E402
from lastgasp.phase2 import load_config2, run_tags  # noqa: E402
from lastgasp.pipeline import get_fire, get_world, load_config, run_one, sample_T  # noqa: E402
from lastgasp.provenance import git_info  # noqa: E402
from lastgasp.reconstruct import idw  # noqa: E402

style.apply()
FIRE_SEED = 0
prov = git_info()

cfg1 = load_config()
world, bxy, _ = get_world(cfg1)
t_end = cfg1["observe"]["t_end_min"]
fire = get_fire(cfg1, FIRE_SEED)
T_b = sample_T(fire, bxy)
burned_b = T_b <= t_end

# Evaluation grid (20 m), masked to burned cells within 250 m of a building.
ge = cfg1["reconstruct"]["eval_cell_m"]
gx = np.arange(ge / 2, world["width_m"], ge)
gy = np.arange(ge / 2, world["height_m"], ge)
GX, GY = np.meshgrid(gx, gy)
q = np.c_[GX.ravel(), GY.ravel()]
T_g = sample_T(fire, q)
near = cKDTree(bxy).query(q)[0] <= 250
show = (T_g <= t_end) & near

# Left: meters (phase 1 default).
m1 = run_one(cfg1, FIRE_SEED, 0, keep=True)
a1 = m1.pop("_artifacts")
obs = a1["obs"]
acc = a1["acc_rows"]
rc = cfg1["reconstruct"]
xy_m = np.c_[obs["x"], obs["y"]][acc]
t_m = a1["t_c"][acc]
F_m = np.clip(idw(xy_m, t_m, q, rc["idw_power"], rc["idw_k"]), 0, t_end)
e_m = np.abs(np.clip(idw(xy_m, t_m, bxy, rc["idw_power"], rc["idw_k"]), 0, t_end) - T_b)[burned_b]

# Right: tag mesh.
cfg2 = load_config2({"phase2.layout.spacing_m": 200, "phase2.reception.mode": "mesh", "phase2.gateways.count": 3})
m2 = run_tags(cfg2, FIRE_SEED, 0, keep=True)
a2 = m2.pop("_artifacts")
obs2 = np.isfinite(a2["rec"]["obs_time"])
hb = cfg2["phase2"]["reception"]["heartbeat_s"] / 60.0
delay = 0.5 * sum(cfg2["phase2"]["tag"]["death_delay_min"]) - hb / 2
xy_t = a2["tag_xy"][obs2]
t_t = a2["rec"]["obs_time"][obs2] - delay
F_t = np.clip(idw(xy_t, t_t, q, rc["idw_power"], rc["idw_k"]), 0, t_end)
e_t = np.abs(np.clip(idw(xy_t, t_t, bxy, rc["idw_power"], rc["idw_k"]), 0, t_end) - T_b)[burned_b]

metrics = {
    "fire_seed": FIRE_SEED,
    "meters_n_devices": int(len(obs["kind"])),
    "meters_n_fire_deaths_used": int(len(acc)),
    "meters_frac_fire_censored_by_grid": float(m1["frac_fire_censored_by_grid"]),
    "meters_bldg_med": float(np.median(e_m)), "meters_bldg_p90": float(np.percentile(e_m, 90)),
    "tags_n_tags": int(m2["n_tags"]), "tags_per_km2": float(m2["tags_per_km2"]),
    "tags_n_gateways": int(m2["n_gateways"]), "tags_frac_deaths_heard": float(m2["frac_deaths_observed"]),
    "tags_bldg_med": float(np.median(e_t)), "tags_bldg_p90": float(np.percentile(e_t, 90)),
    "provenance": {**prov, "script": "scripts/13_booth_figure.py",
                   "config": "configs/default.json; configs/phase2.json with spacing 200 m, mesh, 3 gateways"},
}
(ROOT / "results/booth_figure_metrics.json").write_text(json.dumps(metrics, indent=2))

# Figure.
ext = [0, gx[-1] / 1000 + ge / 2000, 0, gy[-1] / 1000 + ge / 2000]
fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.3), constrained_layout=True, sharey=True)
levels = np.arange(15, t_end, 15)
for ax, F, title, sub in (
        (axes[0], F_m, "(a) Smart meters only:", f"{metrics['meters_frac_fire_censored_by_grid'] * 100:.0f}% of fire signals lost "
                                            f"to grid failure\nerror median {metrics['meters_bldg_med']:.1f} min, "
                                            f"90th percentile {metrics['meters_bldg_p90']:.0f} min"),
        (axes[1], F_t, "(b) Off-grid tag mesh:", f"{metrics['tags_frac_deaths_heard'] * 100:.0f}% of tag deaths heard, "
                                            f"{metrics['tags_n_gateways']} gateways\nerror median "
                                            f"{metrics['tags_bldg_med']:.1f} min, 90th percentile "
                                            f"{metrics['tags_bldg_p90']:.1f} min")):
    ax.set_facecolor("#ececec")
    im = ax.imshow(np.where(show, F, np.nan).reshape(GX.shape), origin="lower", extent=ext, cmap="viridis",
                   vmin=0, vmax=t_end)
    ax.contour(gx / 1000, gy / 1000, np.where(show, T_g, np.nan).reshape(GX.shape), levels=levels,
               colors="white", linewidths=0.8)
    ax.set_title(f"{title}\n{sub}", fontsize=8.3, loc="left")
    ax.set_xlabel("Easting (km)")
    ax.set_xlim(-0.12, world["width_m"] / 1000 + 0.15)
    ax.set_ylim(-0.08, world["height_m"] / 1000 + 0.08)
    ax.set_aspect("equal")
    ax.set_xticks([0, 1, 2, 3])
    for s in ("top", "right"):
        ax.spines[s].set_visible(True)
axes[0].set_ylabel("Northing (km)")
axes[0].scatter(xy_m[:, 0] / 1000, xy_m[:, 1] / 1000, s=2, c="k", lw=0, alpha=0.6)
axes[1].scatter(xy_t[:, 0] / 1000, xy_t[:, 1] / 1000, s=4, c="k", lw=0, alpha=0.7)
g = a2["gw_xy"] / 1000
axes[1].scatter(g[:, 0], g[:, 1], marker="^", s=60, c=style.OKABE_ITO["yellow"], edgecolors="k", lw=0.8,
                zorder=5, clip_on=False)
cb = fig.colorbar(im, ax=axes, shrink=0.75, pad=0.02, aspect=25)
cb.set_label("Reconstructed fire arrival time (min)")
handles = [Line2D([], [], color="#555555", lw=1.2, label="True arrival every 15 min (white lines)"),
           Line2D([], [], marker="o", ls="", ms=3, color="k", label="Device deaths used"),
           Line2D([], [], marker="^", ls="", ms=7, mfc=style.OKABE_ITO["yellow"], mec="k", label="Gateway (can burn)")]
fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=7.5, bbox_to_anchor=(0.45, -0.07))
fig.suptitle("One simulated fire (world 0), two sensor networks; errors at burned buildings for this run.\n"
             "Synthetic simulation, not real-world data.", fontsize=9)
print(style.save(fig, ROOT / "figures", "fig13_booth"))
print(json.dumps({k: v for k, v in metrics.items() if k != "provenance"}))
