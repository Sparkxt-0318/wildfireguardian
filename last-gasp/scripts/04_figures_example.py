"""Figures from the recorded example runs (scripts/02_example_run.py). SYNTHETIC.

Usage: .venv/bin/python scripts/04_figures_example.py
Writes figures/fig1_world.*, fig2_arrival_maps.*, fig3_deaths_vs_fire.*
"""
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from lastgasp import style  # noqa: E402
from lastgasp.pipeline import get_world, sample_T  # noqa: E402

FIG = ROOT / "figures"
style.apply()


def load(tag):
    return pickle.loads((ROOT / f"results/runs/example_{tag}.pkl").read_bytes())


def km(v):
    return np.asarray(v) / 1000.0


def draw_roads(ax, world, color="#d9d9d9", lw=0.5):
    segs = [km(np.asarray(r["xy"])) for r in world["roads"]]
    ax.add_collection(LineCollection(segs, colors=color, linewidths=lw, zorder=1))


def fig_world(ex):
    cfg = ex["config"]
    world, bxy, net = get_world(cfg)
    fire = ex["artifacts"]["fire"]
    W, H = km(world["width_m"]), km(world["height_m"])
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.35), constrained_layout=True)
    ax = axes[0]
    draw_roads(ax, world)
    # Feeder of each pole: first breaker among its ancestor devices.
    breakers = [i for i, d in enumerate(net.devices) if d["kind"] == "breaker"]
    pal = [style.OKABE_ITO[k] for k in ("blue", "vermillion", "green", "orange", "purple", "skyblue", "yellow")]
    feeder_color = {}
    for k, d in enumerate(breakers):
        feeder_color[d] = pal[k % len(pal)]
    segs, cols, lws = [], [], []
    for p in range(net.n_poles):
        q = net.parent[p]
        if q < 0:
            continue
        anc = net.pole_ancestors[p]
        f = anc[0] if anc and net.devices[anc[0]]["kind"] == "breaker" else None
        segs.append(km(np.vstack([net.pole_xy[q], net.pole_xy[p]])))
        cols.append(feeder_color.get(f, "#555555"))
        lws.append(0.4 + 1.6 * np.log10(1 + net.load[p]) / np.log10(1 + net.load.max()))
    ax.add_collection(LineCollection(segs, colors=cols, linewidths=lws, zorder=2))
    osm = np.array([b["source"] == "osm" for b in world["buildings"]])
    ax.scatter(km(bxy[~osm, 0]), km(bxy[~osm, 1]), s=1.2, c="#4d4d4d", lw=0, zorder=3)
    ax.scatter(km(bxy[osm, 0]), km(bxy[osm, 1]), s=6, c="none", edgecolors="k", lw=0.5, zorder=3)
    for kind, mk, sz in (("recloser", "s", 18), ("breaker", "D", 18)):
        pts = np.array([net.pole_xy[d["pole"]] for d in net.devices if d["kind"] == kind])
        ax.scatter(km(pts[:, 0]), km(pts[:, 1]), marker=mk, s=sz, c="white", edgecolors="k", lw=0.8, zorder=4)
    sub = world["substation"]
    ax.scatter(km(sub["x"]), km(sub["y"]), marker="*", s=120, c=style.OKABE_ITO["yellow"], edgecolors="k", lw=0.8, zorder=5)
    handles = [
        Line2D([], [], color="#d9d9d9", lw=1.2, label="Road (OSM)"),
        Line2D([], [], color=pal[0], lw=1.8, label="Feeder line (synthetic, one color per feeder)"),
        Line2D([], [], marker="o", ls="", ms=2, color="#4d4d4d", label="Building (synthetic)"),
        Line2D([], [], marker="o", ls="", ms=4, mfc="none", mec="k", label="Building (OSM)"),
        Line2D([], [], marker="D", ls="", ms=4, mfc="white", mec="k", label="Feeder breaker"),
        Line2D([], [], marker="s", ls="", ms=4, mfc="white", mec="k", label="Recloser"),
        Line2D([], [], marker="*", ls="", ms=9, mfc=style.OKABE_ITO["yellow"], mec="k", label="Substation (OSM)"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.02, -0.17), ncol=2, frameon=False,
              fontsize=6.5, handletextpad=0.3, columnspacing=0.6)
    ax.set_title("(a) Buildings and synthetic power network")
    ax = axes[1]
    T = np.where(fire["T"] <= cfg["fire"]["t_end_min"], fire["T"], np.nan)
    im = ax.imshow(T, origin="lower", extent=[0, W, 0, H], cmap="viridis", vmin=0, vmax=cfg["fire"]["t_end_min"])
    cs = ax.contour(np.linspace(0, W, T.shape[1]), np.linspace(0, H, T.shape[0]), T, levels=np.arange(15, 150, 15),
                    colors="white", linewidths=0.4, alpha=0.7)
    sig = [s for s in fire["spots"] if s["significant"]]
    other = [s for s in fire["spots"] if not s["significant"]]
    for s in other:
        ax.plot(km(s["x"]), km(s["y"]), marker="o", ms=3, mfc="white", mec="k", mew=0.5, ls="")
    for s in sig:
        ax.annotate("", xy=(km(s["x"]), km(s["y"])), xytext=(km(s["launch_x"]), km(s["launch_y"])),
                    arrowprops=dict(arrowstyle="-|>", color="white", lw=0.9, mutation_scale=7))
        ax.plot(km(s["x"]), km(s["y"]), marker="*", ms=9, mfc=style.OKABE_ITO["orange"], mec="k", mew=0.6, ls="")
    ax.annotate("Wind", xy=(0.93, 0.06), xytext=(0.75, 0.06), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color="white", lw=1.2), color="white", va="center", ha="right", fontsize=8)
    handles = [Line2D([], [], marker="*", ls="", ms=8, mfc=style.OKABE_ITO["orange"], mec="k",
                      label="Spot fire with lead of 10 min or more\n(arrow from launch point)"),
               Line2D([], [], marker="o", ls="", ms=4, mfc="white", mec="k", label="Smaller spot fire")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.02, -0.17), frameon=False, fontsize=6.5)
    cb = fig.colorbar(im, ax=ax, shrink=0.62, pad=0.03, aspect=25)
    cb.set_label("True fire arrival time (min)")
    ax.set_title("(b) Ground-truth arrival time (world 0)")
    for a in axes:
        a.set_xlim(0, W)
        a.set_ylim(0, H)
        a.set_aspect("equal")
        a.set_xlabel("Easting (km)")
        a.set_ylabel("Northing (km)")
    fig.suptitle("Yeongdeok-eup test area. Real OSM roads and substation; buildings, power network and fire\n"
                 "are synthetic. Synthetic simulation, not real-world data.", fontsize=9)
    return style.save(fig, FIG, "fig1_world")


def fig_maps(examples):
    from scipy.spatial import cKDTree
    rows = [("default", "Smart meters, 50%\nof buildings"), ("tags50", "Battery tags, 50%\nof buildings")]
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 5.9), constrained_layout=True)
    for r, (tag, rowlab) in enumerate(rows):
        ex = examples[tag]
        a = ex["artifacts"]
        m = ex["metrics"]
        cfg = ex["config"]
        world, bxy, _ = get_world(cfg)
        t_end = cfg["observe"]["t_end_min"]
        gx, gy = a["grid_xy"]
        GX, GY = np.meshgrid(gx, gy)
        near = (cKDTree(bxy).query(np.c_[GX.ravel(), GY.ravel()])[0] <= 250).reshape(GX.shape)
        ext = [0, km(gx[-1] + gx[0]), 0, km(gy[-1] + gy[0])]
        T = np.where(a["T_grid"] <= t_end, a["T_grid"], np.nan)
        show = np.isfinite(T) & near
        panels = [(f"True arrival\n(dots: {len(a['acc_rows'])} deaths used)", T, None),
                  ("IDW after grid filtering", a["fields"]["idw_topology"], "idw_topology"),
                  ("Huygens fit after grid filtering", a["fields"]["huygens"], "huygens")]
        obs = a["obs"]
        acc = a["acc_rows"]
        for c, (name, F, key) in enumerate(panels):
            ax = axes[r, c]
            ax.set_facecolor("#ececec")
            im = ax.imshow(np.where(show, F, np.nan), origin="lower", extent=ext, cmap="viridis", vmin=0, vmax=t_end)
            if key is None:
                ax.scatter(km(obs["x"][acc]), km(obs["y"][acc]), s=1.2, c="white", lw=0)
                ax.set_title(name, fontsize=8)
            else:
                ax.set_title(f"{name}\nmedian {m[key + '_bldg_med']:.1f} min, P90 {m[key + '_bldg_p90']:.1f} min",
                             fontsize=8)
            ax.set_xticks([0, 1, 2, 3])
            ax.set_yticks([0, 1, 2, 3])
            for side in ("top", "right"):
                ax.spines[side].set_visible(True)
            if r == 1:
                ax.set_xlabel("Easting (km)")
            if c == 0:
                ax.set_ylabel(f"{'ab'[r]}) {rowlab}\n\nNorthing (km)", fontsize=8.5)
    cb = fig.colorbar(im, ax=axes, shrink=0.55, pad=0.02, aspect=25)
    cb.set_label("Fire arrival time (min)")
    fig.suptitle("True versus reconstructed arrival time, world 0. Synthetic simulation, not real-world data.\n"
                 "Errors are over all burned buildings. Grey: unburned, or more than 250 m from any building.",
                 fontsize=8.5)
    return style.save(fig, FIG, "fig2_arrival_maps")


def fig_deaths(ex):
    a = ex["artifacts"]
    obs = a["obs"]
    cfg = ex["config"]
    t_end = cfg["observe"]["t_end_min"]
    seen = obs["delivered"] & np.isfinite(obs["t_rep"])
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.5), constrained_layout=True)
    ax = axes[0]
    bins = np.arange(0, t_end + 2.5, 2.5)
    causes = [c for c in style.CAUSE_LABELS if np.any(obs["cause"][seen] == c)]
    data = [obs["t_rep"][seen & (obs["cause"] == c)] for c in causes]
    ax.hist(data, bins=bins, stacked=True, color=[style.CAUSE_COLORS[c] for c in causes],
            label=[style.CAUSE_LABELS[c] for c in causes], edgecolor="none")
    ax.set_xlabel("Reported death time (min)")
    ax.set_ylabel("Delivered last-gasp messages per 2.5 min")
    ax.set_xlim(0, t_end)
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    ax.set_title("(a) Reported meter deaths by true cause")
    ax = axes[1]
    Tf = obs["T_fire_building"]
    lab = a["label"]
    for c in causes:
        m = seen & (obs["cause"] == c)
        x = np.where(np.isfinite(Tf[m]) & (Tf[m] <= t_end), Tf[m], np.nan)
        ax.scatter(x, obs["t_rep"][m], s=5, c=style.CAUSE_COLORS[c], lw=0, alpha=0.8)
    mis = seen & (lab != "fire") & np.isin(obs["cause"], ["fire", "fire_local"])
    ax.scatter(Tf[mis], obs["t_rep"][mis], s=16, facecolors="none", edgecolors="k", lw=0.5,
               label="Fire death labelled non-fire")
    mis2 = seen & (lab == "fire") & ~np.isin(obs["cause"], ["fire", "fire_local"])
    ax.scatter(np.where(Tf[mis2] <= t_end, Tf[mis2], np.nan), obs["t_rep"][mis2], s=16, marker="s",
               facecolors="none", edgecolors=style.OKABE_ITO["purple"], lw=0.5, label="Non-fire death labelled fire")
    ax.plot([0, t_end], [0, t_end], color="k", lw=0.6, ls="--", label="Death at fire arrival")
    ax.set_xlim(0, t_end)
    ax.set_ylim(0, t_end)
    ax.set_xlabel("True fire arrival at the building (min)")
    ax.set_ylabel("Reported death time (min)")
    ax.legend(frameon=False, fontsize=7, loc="upper left", title="Dot colors as in (a)", title_fontsize=7,
              alignment="left")
    ax.set_title("(b) Most grid deaths precede the fire")
    m = ex["metrics"]
    fig.suptitle(f"Smart meters on 50% of buildings, world 0: {100 * m['frac_fire_censored_by_grid']:.0f}% of meters in "
                 "buildings the fire reached had already lost power upstream.\n"
                 f"No messages arrive after about 70 min although the fire burns on. {style.SYNTH_NOTE}.", fontsize=8.5)
    return style.save(fig, FIG, "fig3_deaths_vs_fire")


if __name__ == "__main__":
    ex = {t: load(t) for t in ("default", "tags50")}
    for p in (fig_world(ex["default"]), fig_maps(ex), fig_deaths(ex["default"])):
        print(p)
