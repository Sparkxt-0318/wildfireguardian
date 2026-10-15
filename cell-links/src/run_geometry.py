"""Step 4: plausible ridge-top microwave links on real terrain and how much of each path a
surface fire, a crown fire or the hot plume could intersect.

Usage: .venv/bin/python src/run_geometry.py
Outputs: results/geometry/{sites.csv,links.csv,summary.csv}, figures/geom_*.png/svg
All outputs are modeled estimates on hypothetical (not real) tower sites.
"""
from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LightSource
from scipy.ndimage import maximum_filter, uniform_filter

from common import OI, RESULTS, load_config, record, savefig, style
from physics import line_plume_dT
from terrain import DEM, fresnel_r1, link_profile

CFG_NAME = "geometry.json"
OUT = RESULTS / "geometry"


def plume_height(threshold_K, intensity, T_amb=288.0):
    """Height (m) at which the calm-air line-plume centreline excess temperature equals threshold."""
    return float(line_plume_dT(1.0, intensity, T_amb) / threshold_K)  # dT ~ 1/z


def pick_sites(dem, cfg):
    sc = cfg["site_search"]
    z = np.nan_to_num(dem.z, nan=0.0)
    w = int(sc["window_m"] / dem.res) | 1
    tw = int(2 * sc["tpi_radius_m"] / dem.res) | 1
    tpi = z - uniform_filter(z, tw)
    peak = (z == maximum_filter(z, w)) & (tpi > sc["min_tpi_m"])
    # keep away from raster edges so link profiles stay inside the DEM
    m = int(1500 / dem.res)
    peak[:m], peak[-m:], peak[:, :m], peak[:, -m:] = False, False, False, False
    r, c = np.nonzero(peak)
    order = np.argsort(-tpi[r, c])
    xs, ys = dem.xy(r[order], c[order])
    chosen = []
    for x, y, zz, t in zip(xs, ys, z[r[order], c[order]], tpi[r[order], c[order]]):
        if all(np.hypot(x - a, y - b) >= sc["min_separation_m"] for a, b, *_ in chosen):
            chosen.append((x, y, zz, t))
        if len(chosen) >= sc["max_sites"]:
            break
    return pd.DataFrame(chosen, columns=["x", "y", "elev_m", "tpi_m"])


def build_links(dem, sites, cfg):
    h, k, R = cfg["antenna_height_m"], cfg["k_factor"], cfg["earth_radius_m"]
    frac, step = cfg["clearance_rule_f1_fraction"], cfg["profile_step_m"]
    P = sites[["x", "y"]].to_numpy()
    D = np.hypot(P[:, None, 0] - P[None, :, 0], P[:, None, 1] - P[None, :, 1])
    rows = []
    for band in cfg["bands"]:
        f = band["f_ghz"] * 1e9
        deg = np.zeros(len(P), int)
        pairs = [(D[i, j], i, j) for i in range(len(P)) for j in range(i + 1, len(P))
                 if band["min_km"] * 1e3 <= D[i, j] <= band["max_km"] * 1e3]
        n_cand, n_los = len(pairs), 0
        for dist, i, j in sorted(pairs):  # planners prefer the shortest feasible hops
            if deg[i] >= cfg["max_links_per_site"] or deg[j] >= cfg["max_links_per_site"]:
                continue
            pr = link_profile(dem, P[i], P[j], h, step, k, R)
            r1 = fresnel_r1(f, pr["x"], pr["L"])
            if np.all(pr["clearance"] >= frac * r1):
                n_los += 1
                deg[i] += 1
                deg[j] += 1
                rows.append({"band": band["name"], "f_ghz": band["f_ghz"], "i": i, "j": j,
                             "x1": P[i, 0], "y1": P[i, 1], "x2": P[j, 0], "y2": P[j, 1],
                             "L_m": pr["L"]})
        print(f"{band['name']}: {n_cand} candidate pairs, {n_los} links accepted")
    return pd.DataFrame(rows)


def intersect_metrics(dem, links, cfg):
    fh = cfg["fire_heights"]
    h, k, R, step = cfg["antenna_height_m"], cfg["k_factor"], cfg["earth_radius_m"], cfg["profile_step_m"]
    heights = {
        "surface_flame": fh["surface_flame_m"],
        "surface_flame_high": fh["surface_flame_high_m"],
        "crown_flame": fh["crown_flame_above_dsm_m"],
        "crown_flame_high": fh["crown_flame_above_dsm_high_m"],
    }
    for thr in fh["plume_threshold_K"]:
        heights[f"plume_surface_{thr}K"] = plume_height(thr, fh["surface_intensity_kw_m"])
        heights[f"plume_crown_{thr}K"] = plume_height(thr, fh["crown_intensity_kw_m"])
    out = []
    for _, ln in links.iterrows():
        pr = link_profile(dem, (ln.x1, ln.y1), (ln.x2, ln.y2), h, step, k, R)
        r1 = fresnel_r1(ln.f_ghz * 1e9, pr["x"], pr["L"])
        c = pr["clearance"]
        mid = (pr["x"] > cfg["tower_zone_m"]) & (pr["x"] < pr["L"] - cfg["tower_zone_m"])
        row = {"min_clear_over_r1": float(np.min((c / np.maximum(r1, 1e-3))[1:-1])),
               "median_clearance_m": float(np.median(c)),
               "frac_clear_lt_50m": float(np.mean(c < 50))}
        for name, H in heights.items():
            if name.startswith("plume"):
                row[f"frac_{name}"] = float(np.mean(c <= H))         # ray inside hot plume
                row[f"frac_{name}_mid"] = float(np.mean((c <= H) & mid))
            else:
                row[f"frac_{name}_F1"] = float(np.mean(c - r1 <= H))  # flame enters 1st Fresnel zone
                row[f"frac_{name}_ray"] = float(np.mean(c <= H))      # flame reaches the ray
                row[f"frac_{name}_F1_mid"] = float(np.mean((c - r1 <= H) & mid))  # excluding tower zones
        out.append(row)
    return pd.concat([links.reset_index(drop=True), pd.DataFrame(out)], axis=1), heights


def figures(dem, sites, links, m, cfg, heights, fire_pts=None):
    style()
    band_colors = dict(zip([b["name"] for b in cfg["bands"]],
                           [OI["blue"], OI["skyblue"], OI["green"], OI["orange"], OI["vermillion"], OI["purple"]]))
    # Map: one small panel per band
    z = np.nan_to_num(dem.z, nan=np.nanmean(dem.z))
    zs = z[::3, ::3]  # 90 m display resolution keeps files small
    hs = LightSource(azdeg=315, altdeg=45).hillshade(zs, vert_exag=2, dx=3 * dem.res, dy=3 * dem.res)
    ext = np.array(dem.extent()) / 1e3
    fig, axes = plt.subplots(3, 2, figsize=(10, 7.4), sharex=True, sharey=True)
    for ax, b in zip(axes.ravel(), cfg["bands"]):
        ax.imshow(hs, cmap="gray", extent=ext, origin="upper", vmin=0, vmax=1.3)
        sub = links[links.band == b["name"]]
        for _, ln in sub.iterrows():
            ax.plot([ln.x1 / 1e3, ln.x2 / 1e3], [ln.y1 / 1e3, ln.y2 / 1e3], color=band_colors[b["name"]], lw=0.9)
        ax.scatter(sites.x / 1e3, sites.y / 1e3, s=3, c="k", zorder=3, lw=0)
        if fire_pts:
            for lab, (fx, fy), mk in fire_pts:
                ax.scatter(fx / 1e3, fy / 1e3, s=40, marker=mk, facecolor=OI["yellow"], edgecolor="k", lw=0.8, zorder=4)
        ax.set_title(f"{b['name']}: {len(sub)} links, {b['min_km']:g} to {b['max_km']:g} km", fontsize=10)
        ax.grid(False)
        ax.set_aspect("equal")
    for ax in axes[-1]:
        ax.set_xlabel("UTM 52N easting (km)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Northing (km)")
    fig.suptitle("Hypothetical ridge-top links (black dots: candidate sites) on the Copernicus GLO-30 DSM", fontsize=11)
    fig.tight_layout()
    savefig(fig, "geom_map")

    # Example clearance profiles: the 18 GHz and 7 GHz links with the most crown-flame overlap
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    h, k, R, step = cfg["antenna_height_m"], cfg["k_factor"], cfg["earth_radius_m"], cfg["profile_step_m"]
    for ax, bname in zip(axes, ["18 GHz", "7 GHz"]):
        sub = m[m.band == bname]
        ln = sub.sort_values("frac_crown_flame_F1_mid").iloc[-1]
        pr = link_profile(dem, (ln.x1, ln.y1), (ln.x2, ln.y2), h, step, k, R)
        r1 = fresnel_r1(ln.f_ghz * 1e9, pr["x"], pr["L"])
        x, c = pr["x"] / 1e3, pr["clearance"]
        ax.fill_between(x, c - r1, c + r1, color=OI["skyblue"], alpha=0.45, lw=0, label="1st Fresnel zone")
        ax.plot(x, c, color=OI["black"], lw=1.2, label="Direct ray")
        ax.axhspan(0, heights["surface_flame"], color=OI["orange"], alpha=0.9, lw=0, label="Surface flame (2 m)")
        ax.axhline(heights["crown_flame"], color=OI["vermillion"], lw=1.2, label="Crown flame top (20 m)")
        ax.axhline(heights["crown_flame_high"], color=OI["vermillion"], lw=1.2, ls="--", label="Crown flame top (35 m)")
        ax.axhline(heights["plume_crown_100K"], color=OI["blue"], lw=1.2, ls=":", label="Crown plume dT = 100 K")
        ax.set_title(f"{bname}, {pr['L']/1e3:.1f} km link")
        ax.set_xlabel("Distance along link (km)")
        ax.set_ylim(0, 260)
        ax.set_xlim(0, x[-1])
    axes[0].set_ylabel("Height above DSM + Earth bulge (m)")
    hnd, lab = axes[0].get_legend_handles_labels()
    fig.suptitle("Ray clearance above the surface (axis clipped at 260 m), with flame and plume heights", fontsize=11)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.legend(hnd, lab, loc="lower center", ncol=6, fontsize=8, bbox_to_anchor=(0.5, 0.0))
    savefig(fig, "geom_profiles")

    # Fractions of link length by band
    cats = [("frac_surface_flame_F1", "Surface flame (2 m) in F1"),
            ("frac_crown_flame_F1", "Crown flame (20 m) in F1"),
            ("frac_crown_flame_high_F1_mid", "Crown flame (35 m) in F1, outside tower zones"),
            ("frac_plume_crown_100K", "Calm-air crown plume, dT >= 100 K, at the ray"),
            ("frac_plume_crown_30K", "Calm-air crown plume, dT >= 30 K, at the ray")]
    bands = [b["name"] for b in cfg["bands"] if (m.band == b["name"]).any()]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    wbar = 0.8 / len(cats)
    cols = [OI["orange"], OI["vermillion"], OI["purple"], OI["blue"], OI["skyblue"]]
    for i, (key, lab) in enumerate(cats):
        vals = [100 * np.average(m[m.band == b][key], weights=m[m.band == b]["L_m"]) for b in bands]
        ax.bar(np.arange(len(bands)) + (i - (len(cats) - 1) / 2) * wbar, vals, wbar, color=cols[i], label=lab)
    ax.set_xticks(np.arange(len(bands)), bands)
    ax.set_ylabel("Share of total link length (%)")
    ax.set_title("Share of link length a fire could reach (hypothetical links, length weighted)")
    ax.set_ylim(0, 75)
    ax.legend(ncol=2, fontsize=8, loc="upper left")
    fig.tight_layout()
    savefig(fig, "geom_fractions")


def main():
    cfg = load_config(CFG_NAME)
    OUT.mkdir(parents=True, exist_ok=True)
    dem = DEM.load(cfg["dem_tiles"], cfg["bbox_lonlat"], cfg["utm_epsg"], cfg["grid_m"])
    print("DEM", dem.z.shape, np.nanmin(dem.z), np.nanmax(dem.z))
    sites = pick_sites(dem, cfg)
    print("sites", len(sites))
    links = build_links(dem, sites, cfg)
    m, heights = intersect_metrics(dem, links, cfg)
    sites.to_csv(OUT / "sites.csv", index_label="site")
    m.to_csv(OUT / "links.csv", index=False)
    frac_cols = [c for c in m.columns if c.startswith("frac_")]
    summ = m.groupby("band", sort=False).apply(
        lambda g: pd.Series({"n_links": len(g), "median_L_km": g.L_m.median() / 1e3,
                             "median_clearance_m": g.median_clearance_m.median(),
                             **{c: np.average(g[c], weights=g.L_m) for c in frac_cols},
                             **{"links_any_" + c[5:]: float(np.mean(g[c] > 0)) for c in frac_cols}}),
        include_groups=False)
    allrow = pd.Series({"n_links": len(m), "median_L_km": m.L_m.median() / 1e3,
                        "median_clearance_m": m.median_clearance_m.median(),
                        **{c: np.average(m[c], weights=m.L_m) for c in frac_cols},
                        **{"links_any_" + c[5:]: float(np.mean(m[c] > 0)) for c in frac_cols}}, name="All")
    summ = pd.concat([summ, allrow.to_frame().T])
    summ.to_csv(OUT / "summary.csv")
    (OUT / "plume_heights.json").write_text(json.dumps(heights, indent=1))
    print(summ.T.to_string(float_format=lambda v: f"{v:.3f}"))
    print("heights", heights)
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{cfg['utm_epsg']}", always_xy=True)
    fire_pts = [(p["label"], tr.transform(p["lon"], p["lat"]), p["marker"]) for p in cfg.get("fire_points", [])]
    figures(dem, sites, links, m, cfg, heights, fire_pts)

    ent = {"geom.n_sites": (len(sites), "count", "Hypothetical ridge-top sites selected on the DSM"),
           "geom.n_links": (len(m), "count", "Hypothetical links meeting 0.6 F1 clearance (k=4/3)")}
    for b, r in summ.iterrows():
        tag = b.replace(" ", "")
        for key in ["n_links", "median_L_km", "median_clearance_m", "frac_surface_flame_F1",
                    "frac_surface_flame_high_F1", "frac_crown_flame_F1", "frac_crown_flame_high_F1",
                    "frac_crown_flame_ray", "frac_crown_flame_F1_mid", "frac_crown_flame_high_F1_mid",
                    "frac_plume_crown_100K", "frac_plume_crown_100K_mid", "frac_plume_crown_30K",
                    "frac_plume_crown_10K", "frac_plume_surface_30K", "links_any_surface_flame_F1",
                    "links_any_crown_flame_F1", "links_any_plume_crown_30K"]:
            unit = "count" if key == "n_links" else ("km" if key.endswith("km") else ("m" if key.endswith("_m") else "fraction"))
            ent[f"geom.{tag}.{key}"] = (float(r[key]), unit, f"{key} for band {b} (length-weighted where a fraction)")
    for name, H in heights.items():
        ent[f"geom.height.{name}"] = (H, "m", f"Height above DSM used for {name}")
    record(ent, "src/run_geometry.py", f"configs/{CFG_NAME}")


if __name__ == "__main__":
    main()
