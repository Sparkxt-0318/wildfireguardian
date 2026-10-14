"""Tabletop demo simulation: 25 battery tags in a 1 km x 1 km village, front rebuilt live. SYNTHETIC.

The live estimator uses only what a receiver knows at time t: which tags are
still heard (alive) and which went silent (dead, with last-heard time).
Burned probability at x = IDW of the alive (0) / dead (1) indicator over the
k nearest tags; the estimated front is the 0.5 contour. This uses surviving
nodes directly, unlike the arrival-time interpolators, and is cheap enough to
run on every heartbeat.

Usage: .venv/bin/python scripts/06_demo_sim.py [--n-tags 25] [--seeds 10]
Writes figures/fig8_demo_live.* and results/demo_metrics.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib import pyplot as plt  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

from lastgasp import style  # noqa: E402
from lastgasp.pipeline import get_fire, get_world, load_config, sample_T  # noqa: E402
from lastgasp.provenance import git_info  # noqa: E402

style.apply()
BOX = (1200.0, 1000.0, 2200.0, 2000.0)  # x0, y0, x1, y1 in metres: a dense part of the test area


def farthest_point(xy, n, rng):
    idx = [int(rng.integers(len(xy)))]
    d = np.hypot(*(xy - xy[idx[0]]).T)
    for _ in range(n - 1):
        j = int(np.argmax(d))
        idx.append(j)
        d = np.minimum(d, np.hypot(*(xy - xy[j]).T))
    return np.array(idx)


def live_burned_prob(node_xy, dead, q, k=4, power=2.0):
    tree = cKDTree(node_xy)
    d, j = tree.query(q, k=min(k, len(node_xy)))
    w = 1.0 / np.maximum(d, 5.0) ** power
    return (w * dead[j]).sum(1) / w.sum(1)


def run(seed_fire, seed_obs, n_tags, cfg, times):
    world, bxy, _ = get_world(cfg)
    fire = get_fire(cfg, seed_fire)
    x0, y0, x1, y1 = BOX
    inbox = np.where((bxy[:, 0] >= x0) & (bxy[:, 0] <= x1) & (bxy[:, 1] >= y0) & (bxy[:, 1] <= y1))[0]
    rng = np.random.default_rng(seed_obs)
    sel = inbox[farthest_point(bxy[inbox], n_tags, rng)]
    nxy = bxy[sel]
    T = sample_T(fire, nxy)
    tc = cfg["observe"]["tag"]
    dies = rng.random(n_tags) < tc["p_die_given_fire"]
    t_death = np.where(dies, T + rng.uniform(*tc["death_delay_min"], n_tags), np.inf)
    hb = tc["heartbeat_s"] / 60.0
    t_last = t_death - rng.uniform(0, hb, n_tags) - (rng.geometric(tc["p_heartbeat"], n_tags) - 1) * hb
    timeout = 3 * hb  # declared dead after three missed heartbeats
    gx = np.arange(x0 + 5, x1, 10.0)
    gy = np.arange(y0 + 5, y1, 10.0)
    GX, GY = np.meshgrid(gx, gy)
    q = np.c_[GX.ravel(), GY.ravel()]
    Tq = sample_T(fire, q)
    out = []
    snaps = {}
    for t in times:
        dead = (t_last + timeout <= t).astype(float)
        p = live_burned_prob(nxy, dead, q)
        est = p >= 0.5
        true = Tq <= t
        inter = np.sum(est & true)
        union = np.sum(est | true)
        iou = inter / union if union else np.nan
        out.append({"t": t, "true_burned_frac": float(true.mean()), "est_burned_frac": float(est.mean()),
                    "iou": float(iou), "n_dead": int(dead.sum())})
        snaps[t] = (p.reshape(GX.shape), true.reshape(GX.shape), dead.copy())
    # Detection latency: time from true arrival to "declared dead" for tags that died.
    lat = (t_last + timeout - T)[np.isfinite(t_death)]
    return out, snaps, nxy, (gx, gy), lat, int(np.sum(~dies & (T <= t_end_of(cfg))))


def t_end_of(cfg):
    return cfg["observe"]["t_end_min"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-tags", type=int, default=25)
    ap.add_argument("--seeds", type=int, default=10)
    a = ap.parse_args()
    cfg = load_config()
    times = [10, 20, 30, 40, 50, 60]
    allres, lats = [], []
    keep = None
    for s in range(a.seeds):
        res, snaps, nxy, (gx, gy), lat, n_surv = run(s % 5, 100 + s, a.n_tags, cfg, times)
        allres.append(res)
        lats.extend(lat.tolist())
        if keep is None and n_surv <= 1:  # show a typical run: at most one tag survives the fire
            keep = (snaps, nxy, gx, gy, s)
    iou = np.array([[r["iou"] for r in res] for res in allres])
    tf = np.array([[r["true_burned_frac"] for r in res] for res in allres])
    summary = {"n_tags": a.n_tags, "box_m": BOX, "area_km2": 1.0, "n_runs": a.seeds, "times_min": times,
               "iou_median_by_time": [None if np.isnan(v) else round(float(v), 3) for v in np.nanmedian(iou, 0)],
               "iou_median_while_front_inside": float(np.nanmedian(iou[(tf > 0.05) & (tf < 0.95)])),
               "true_burned_frac_median_by_time": np.median(tf, 0).round(3).tolist(),
               "detection_latency_median_min": float(np.median(lats)),
               "detection_latency_p90_min": float(np.percentile(lats, 90)),
               "provenance": {**git_info(), "script": "scripts/06_demo_sim.py", "config": "configs/default.json"}}
    snaps, nxy, gx, gy, shown = keep
    summary["figure_run_index"] = shown
    (ROOT / "results/demo_metrics.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "provenance"}))
    show = [20, 30, 40, 50]
    fig, axes = plt.subplots(1, 4, figsize=(7.4, 2.5), constrained_layout=True, sharey=True)
    ext = [gx[0] / 1000 - 0.005, gx[-1] / 1000 + 0.005, gy[0] / 1000 - 0.005, gy[-1] / 1000 + 0.005]
    for ax, t in zip(axes, show):
        p, true, dead = snaps[t]
        ax.imshow(np.where(true, 1.0, np.nan), origin="lower", extent=ext, cmap="Greys", vmin=0, vmax=2.5)
        ax.contourf(gx / 1000, gy / 1000, p, levels=[0.5, 1.01], colors=[style.OKABE_ITO["vermillion"]], alpha=0.18)
        ax.contour(gx / 1000, gy / 1000, p, levels=[0.5], colors=[style.OKABE_ITO["vermillion"]], linewidths=1.4)
        ax.scatter(nxy[dead > 0, 0] / 1000, nxy[dead > 0, 1] / 1000, s=16, marker="X",
                   c=style.OKABE_ITO["vermillion"], edgecolors="k", lw=0.4, zorder=3)
        ax.scatter(nxy[dead == 0, 0] / 1000, nxy[dead == 0, 1] / 1000, s=14, c=style.OKABE_ITO["skyblue"],
                   edgecolors="k", lw=0.4, zorder=3)
        ax.set_title(f"t = {t} min", fontsize=8.5)
        ax.set_xlabel("Easting (km)")
        ax.set_aspect("equal")
    axes[0].set_ylabel("Northing (km)")
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    h = [Patch(color="#9a9a9a", label="True burned area"),
         Patch(facecolor=style.OKABE_ITO["vermillion"], alpha=0.35, edgecolor=style.OKABE_ITO["vermillion"],
               label="Estimated burned area (live)"),
         Line2D([], [], marker="X", ls="", mfc=style.OKABE_ITO["vermillion"], mec="k", label="Tag declared dead"),
         Line2D([], [], marker="o", ls="", mfc=style.OKABE_ITO["skyblue"], mec="k", label="Tag still heard")]
    fig.legend(handles=h, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.1), fontsize=7.5)
    fig.suptitle(f"Tabletop demo analogue: {a.n_tags} battery tags in 1 km², front rebuilt from alive or dead state "
                 f"(run {shown}).\n{style.SYNTH_NOTE}.", fontsize=8)
    print(style.save(fig, ROOT / "figures", "fig8_demo_live"))


if __name__ == "__main__":
    main()
