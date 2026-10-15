"""Step 5: move a simulated fire across the Uiseong terrain and compute, for every hypothetical
link it crosses, the fire-induced mean attenuation A(t) and scintillation std S(t).

Usage: .venv/bin/python src/run_crossings.py
Outputs: results/crossings/{arrival_<scen>.npy, signatures_<scen>.npz, links_<scen>.csv},
         figures/cross_*.png/svg. Everything here is simulated, not observed.
"""
from __future__ import annotations

import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LightSource
from pyproj import Transformer
from scipy.ndimage import map_coordinates

from common import OI, RESULTS, load_config, record, savefig, style
from physics import (FireColumn, byram_flame_length, plume_cn2, rytov_logamp_std_db,
                     thomas_flame_length)
from run_physics import SAT_DB, mean_excess_db, scenario_params
from spread import arrival_times, local_ros
from terrain import DEM, fresnel_r1, link_profile

CFG_NAME = "crossings.json"
OUT = RESULTS / "crossings"


class Signature:
    def __init__(self, cfg, pcfg, sc):
        self.cfg, self.pcfg, self.sc = cfg, pcfg, sc
        self.cache, self.cols = {}, {}

    def fire_props(self, ros):
        c = self.cfg
        I_s = c["heat_content_kj_kg"] * c["fuel_consumed_surface_kg_m2"] * ros
        crown = I_s > c["crown_threshold_kw_m"]
        I = np.where(crown, c["heat_content_kj_kg"] * c["fuel_consumed_crown_kg_m2"] * ros, I_s)
        H = np.where(crown, np.minimum(thomas_flame_length(I), c["crown_flame_max_above_dsm_m"]),
                     byram_flame_length(I))
        tres = np.where(crown, c["residence_time_crown_s"], c["residence_time_surface_s"])
        return I, H, tres, crown

    def column(self, I, H, scen):
        key = (round(float(np.log10(I)), 2), round(float(H), 1), scen)
        if key not in self.cols:
            self.cols[key] = self._column(10 ** key[0], key[1], scen)
        return self.cols[key]

    def _column(self, I, H, scen):
        p = self.pcfg
        v = self.sc[scen]
        return FireColumn(I, H, p["T_flame_K"], v["ne"], v["nu"], T_amb=p["T_amb_K"], rh=p["rh_amb"],
                          alpha_entr=p["alpha_entr"], conv_frac=p["conv_frac"], x_K=p["x_K"])

    def excess(self, f, d1, L, c, I, H, seg, scen):
        """Mean excess loss (dB), cached on rounded inputs; zero when the flame is far below F1."""
        r1 = float(fresnel_r1(f, d1, L))
        if c - r1 > 1.4 * H + 2 * r1:
            return 0.0
        key = (f, round(d1 / L, 2), round(c * 2) / 2, round(H * 2) / 2, round(seg / 5) * 5,
               round(np.log10(I), 1), scen)
        if key not in self.cache:
            col = self.column(I, H, scen)
            lf, lg = mean_excess_db(col, f, d1, L - d1, max(c, 0.0), max(seg, 1.0))
            self.cache[key] = max(lf - lg, 0.0)
        return self.cache[key]

    def scint_var(self, f, d1, L, c, I, H, seg):
        col = self.column(I, H, "lab_peak")  # ne does not enter the thermal Cn2
        z = max(c, 0.1)
        cn2 = plume_cn2(col, np.array([z]), self.pcfg["sigma_T_ratio"])[0]
        s_db, _ = rytov_logamp_std_db(f, d1, L - d1, cn2, seg + 2 * col.alpha * z)
        return s_db**2


def segments(mask):
    """Start/stop indices of contiguous True runs."""
    d = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]))


def main():
    cfg = load_config(CFG_NAME)
    gcfg, pcfg = load_config(cfg["geometry_config"]), load_config(cfg["physics_config"])
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    sc = scenario_params(pcfg)
    dem = DEM.load(gcfg["dem_tiles"], gcfg["bbox_lonlat"], gcfg["utm_epsg"], gcfg["grid_m"])
    k = cfg["spread_grid_m"] // gcfg["grid_m"]
    ny, nx = dem.ny // k * k, dem.nx // k * k
    zc = np.nan_to_num(dem.z[:ny, :nx], nan=0.0).reshape(ny // k, k, nx // k, k).mean(axis=(1, 3))
    res = cfg["spread_grid_m"]
    tr = Transformer.from_crs("EPSG:4326", f"EPSG:{gcfg['utm_epsg']}", always_xy=True)
    ix, iy = tr.transform(*cfg["ignition_lonlat"])
    ign = (int((dem.y0 - iy) // res), int((ix - dem.x0) // res))
    links = pd.read_csv(RESULTS / "geometry" / "links.csv")
    sig = Signature(cfg, pcfg, sc)
    t_end = cfg["t_end_h"] * 3600
    nums = {}

    def to_grid_rc(x, y):
        return (dem.y0 - y) / res - 0.5, (x - dem.x0) / res - 0.5

    for scen, sp in cfg["scenarios"].items():
        t, LB = arrival_times(zc, res, ign, sp["r_head_m_s"], cfg["wind_to_deg"], sp["u10_kmh"],
                              burnable=zc > 1.0)
        np.save(OUT / f"arrival_{scen}.npy", t.astype("float32"))
        ros = local_ros(np.where(np.isfinite(t), t, np.nan), res)
        burned = np.isfinite(t) & (t <= t_end)
        area_ha = burned.sum() * res**2 / 1e4
        print(f"{scen}: LB={LB:.2f}, burned {area_ha:.0f} ha in {cfg['t_end_h']} h")
        nums[f"cross.{scen}.burned_ha_24h"] = (area_ha, "ha", f"Simulated area burned in 24 h, {scen} scenario")
        nums[f"cross.{scen}.LB"] = (LB, "ratio", f"Fire ellipse length-to-breadth ratio, {scen}")

        sigs, meta = {}, []
        for li, ln in links.iterrows():
            pr = link_profile(dem, (ln.x1, ln.y1), (ln.x2, ln.y2), gcfg["antenna_height_m"],
                              gcfg["profile_step_m"], gcfg["k_factor"], gcfg["earth_radius_m"])
            r, c = to_grid_rc(pr["xs"], pr["ys"])
            ta = map_coordinates(np.where(np.isfinite(t), t, 1e12), [r, c], order=1, mode="nearest")
            if ta.min() > t_end:
                continue
            R = map_coordinates(np.nan_to_num(ros, nan=0.01), [r, c], order=1, mode="nearest")
            I, H, tres, crown = sig.fire_props(np.clip(R, 0.005, 5.0))
            f = ln.f_ghz * 1e9
            L, x, clr = pr["L"], pr["x"], pr["clearance"]
            step = x[1] - x[0]
            t0 = max(ta.min() - cfg["pad_before_s"], 0)
            t1 = min(max(ta[ta <= t_end].max() + tres.max(), ta.min()), t_end) + cfg["pad_after_s"]
            times = np.arange(t0, t1, cfg["dt_s"])
            # A slow front can cross a profile sample faster than the sample spacing allows us to
            # see it; keep each sample burning at least step / R and rescale the flame path.
            tres_eff = np.maximum(tres, step / np.clip(R, 0.005, 5.0))
            A = {s: np.zeros(len(times)) for s in cfg["flame_ne_scenarios"]}
            S2 = np.zeros(len(times))
            for ti, tt in enumerate(times):
                m = (tt >= ta) & (tt < ta + tres_eff)
                if not m.any():
                    continue
                for a, b in segments(m):
                    j = (a + b - 1) // 2
                    j = int(np.clip(j, 1, len(x) - 2))
                    seg = (b - a) * step * float(np.mean(tres[a:b] / tres_eff[a:b]))
                    d1 = float(x[j])
                    for s in cfg["flame_ne_scenarios"]:
                        A[s][ti] += sig.excess(f, d1, L, clr[j], I[j], H[j], seg, s)
                    S2[ti] += sig.scint_var(f, d1, L, clr[j], I[j], H[j], seg)
            S = np.minimum(np.sqrt(S2), SAT_DB)
            key = f"link{li}"
            sigs[key + "_t"] = times.astype("float32")
            for s in cfg["flame_ne_scenarios"]:
                sigs[key + f"_A_{s}"] = A[s].astype("float32")
            sigs[key + "_S"] = S.astype("float32")
            jx = int(np.argmin(ta))
            meta.append({"link": li, "band": ln.band, "f_ghz": ln.f_ghz, "L_m": L,
                         "t_first_s": float(ta.min()), "x_first_m": float(x[jx]),
                         "x_first_utm": float(pr["xs"][jx]), "y_first_utm": float(pr["ys"][jx]),
                         "frac_burned": float(np.mean(ta <= t_end)),
                         "crown_frac": float(np.mean(crown[ta <= t_end])),
                         "min_clear_burned_m": float(clr[ta <= t_end].min()),
                         **{f"maxA_{s}": float(A[s].max()) for s in cfg["flame_ne_scenarios"]},
                         "maxS": float(S.max()),
                         "t_S03_s": float(times[np.argmax(S >= 0.3)]) if (S >= 0.3).any() else np.nan,
                         **{f"t_A1_{s}_s": float(times[np.argmax(A[s] >= 1.0)]) if (A[s] >= 1.0).any() else np.nan
                            for s in cfg["flame_ne_scenarios"]}})
            if li % 200 == 0:
                print(f"  link {li}: {len(meta)} crossed so far, cache {len(sig.cache)}")
        md = pd.DataFrame(meta)
        md.to_csv(OUT / f"links_{scen}.csv", index=False)
        np.savez_compressed(OUT / f"signatures_{scen}.npz", **sigs)
        print(md.groupby("band")[["maxA_lab_peak", "maxA_field_bound", "maxS"]].describe().T.to_string())
        nums[f"cross.{scen}.n_links_crossed"] = (len(md), "count", f"Hypothetical links reached by the simulated fire in 24 h, {scen}")
        for thr in [1.0, 3.0]:
            for s in cfg["flame_ne_scenarios"]:
                nums[f"cross.{scen}.frac_maxA_ge_{thr:g}dB_{s}"] = (float(np.mean(md[f"maxA_{s}"] >= thr)), "fraction",
                    f"Share of crossed links with peak mean excess loss >= {thr:g} dB, {scen}, {s}")
        for thr in [0.3, 1.0]:
            nums[f"cross.{scen}.frac_maxS_ge_{thr:g}dB"] = (float(np.mean(md.maxS >= thr)), "fraction",
                f"Share of crossed links with peak scintillation std >= {thr:g} dB, {scen}")
        for b, g in md.groupby("band"):
            tag = b.replace(" ", "")
            nums[f"cross.{scen}.{tag}.n_crossed"] = (len(g), "count", f"Crossed links, {b}, {scen}")
            nums[f"cross.{scen}.{tag}.frac_maxA_ge_1dB_lab_peak"] = (float(np.mean(g.maxA_lab_peak >= 1)), "fraction",
                f"Share with peak mean loss >= 1 dB, {b}, {scen}, lab peak ne")
            nums[f"cross.{scen}.{tag}.frac_maxS_ge_0.3dB"] = (float(np.mean(g.maxS >= 0.3)), "fraction",
                f"Share with peak scintillation std >= 0.3 dB, {b}, {scen}")
        figures(dem, t, res, links, md, sigs, scen, cfg, zc)
    record(nums, "src/run_crossings.py", f"configs/{CFG_NAME}")


def figures(dem, t, res, links, md, sigs, scen, cfg, zc):
    style()
    hs = LightSource(azdeg=315, altdeg=45).hillshade(zc, vert_exag=2, dx=res, dy=res)
    ext = np.array([dem.x0, dem.x0 + zc.shape[1] * res, dem.y0 - zc.shape[0] * res, dem.y0]) / 1e3
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.imshow(hs, cmap="gray", extent=ext, origin="upper", vmin=0, vmax=1.3)
    th = np.where(t <= cfg["t_end_h"] * 3600, t / 3600, np.nan)
    im = ax.imshow(th, cmap="viridis", extent=ext, origin="upper", alpha=0.55, vmin=0, vmax=cfg["t_end_h"])
    ax.contour(np.flipud(th), levels=np.arange(2, cfg["t_end_h"] + 1, 2), extent=ext, colors="k", linewidths=0.4, origin="lower")
    crossed = set(md.link)
    for li, ln in links.iterrows():
        if li in crossed:
            row = md[md.link == li].iloc[0]
            strong = row.maxS >= 0.3 or row.maxA_lab_peak >= 1
            ax.plot([ln.x1 / 1e3, ln.x2 / 1e3], [ln.y1 / 1e3, ln.y2 / 1e3],
                    color=OI["vermillion"] if strong else OI["orange"], lw=1.0 if strong else 0.6)
    ax.plot([], [], color=OI["vermillion"], label="Crossed, peak loss >= 1 dB or scintillation >= 0.3 dB")
    ax.plot([], [], color=OI["orange"], lw=0.6, label="Crossed, weaker signature")
    ax.scatter(*np.array(Transformer.from_crs("EPSG:4326", "EPSG:32652", always_xy=True).transform(*cfg["ignition_lonlat"])) / 1e3,
               marker="*", s=120, color=OI["yellow"], edgecolor="k", zorder=5, label="Ignition (approximate)")
    ax.set_xlabel("UTM 52N easting (km)")
    ax.set_ylabel("UTM 52N northing (km)")
    ax.set_aspect("equal")
    ax.grid(False)
    sp = cfg["scenarios"][scen]
    ax.set_title(f"Simulated spread, '{scen}' scenario (head ROS {sp['r_head_m_s']} m/s on flat, wind {sp['u10_kmh']} km/h toward {cfg['wind_to_deg']:g} deg); 2 h contours")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("Arrival time (h after ignition)")
    ax.legend(loc="upper left", fontsize=7.5, framealpha=0.85, frameon=True)
    fig.tight_layout()
    savefig(fig, f"cross_map_{scen}")

    # Example signatures: strongest, median-strength and a typical weak crossing at 18 GHz or nearest band
    sub = md[md.band.isin(["18 GHz", "23 GHz", "13 GHz"])].sort_values("maxS", ascending=False)
    picks = [sub.iloc[0], sub.iloc[len(sub) // 4], sub.iloc[len(sub) // 2]] if len(sub) >= 3 else [r for _, r in sub.iterrows()]
    fig, axes = plt.subplots(len(picks), 1, figsize=(8, 2.2 * len(picks) + 0.6), sharex=False)
    axes = np.atleast_1d(axes)
    for ax, row in zip(axes, picks):
        kk = f"link{int(row.link)}"
        tt = (sigs[kk + "_t"] - row.t_first_s) / 60
        S = sigs[kk + "_S"]
        A = sigs[kk + "_A_lab_peak"]
        Af = sigs[kk + "_A_field_bound"]
        ax.fill_between(tt, -A - 2 * S, -A + 2 * S, color=OI["skyblue"], alpha=0.5, lw=0, label="Mean +- 2 x scintillation std")
        ax.plot(tt, -A, color=OI["vermillion"], label="Mean change, lab-peak ne")
        ax.plot(tt, -Af, color=OI["blue"], ls="--", label="Mean change, field-bound ne")
        ax.set_ylabel("RSL change (dB)")
        ax.set_title(f"{row.band}, {row.L_m/1e3:.1f} km link; peak mean loss {row.maxA_lab_peak:.1f} dB, "
                     f"peak scintillation {row.maxS:.2f} dB", fontsize=9.5)
        ax.set_xlim(-30, max(tt.max(), 30))
    axes[-1].set_xlabel("Minutes after the fire first reaches the ground track of the link")
    axes[0].legend(fontsize=7.5, loc="lower right", ncol=3)
    fig.suptitle(f"Simulated fire signatures without receiver noise ('{scen}' scenario)", fontsize=11)
    fig.tight_layout()
    savefig(fig, f"cross_examples_{scen}")


if __name__ == "__main__":
    main()
