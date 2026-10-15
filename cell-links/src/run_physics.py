"""Step 3: flame and plume propagation physics (modeled estimates).

Usage: .venv/bin/python src/run_physics.py
Outputs: results/physics/*.csv, figures/phys_*.png/svg, NUMBERS.json entries phys.*
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import OI, RESULTS, load_config, record, savefig, style
from physics import (FireColumn, byram_flame_length, column_loss_db, fresnel_radius,
                     invert_ne_from_loss, plume_cn2, rytov_logamp_std_db,
                     specific_attenuation_db_per_m)

CFG_NAME = "physics.json"
OUT = RESULTS / "physics"


def scenario_params(cfg):
    sc = {}
    for k, v in cfg["flame_scenarios"].items():
        if "ne" in v:
            sc[k] = dict(v)
        else:
            ne = invert_ne_from_loss(v["loss_db"], v["path_m"], v["f_ghz"] * 1e9, v["nu"])
            sc[k] = {"label": v["label"], "ne": float(ne), "nu": v["nu"]}
    return sc


def make_column(cfg, fire, scen, model="saha"):
    fp = cfg["fires"][fire]
    I = fp["intensity_kw_m"]
    H = float(byram_flame_length(I)) if fp["flame_height_m"] == "byram" else fp["flame_height_m"]
    return FireColumn(I, H, cfg["T_flame_K"], scen["ne"], scen["nu"], T_amb=cfg["T_amb_K"],
                      rh=cfg["rh_amb"], alpha_entr=cfg["alpha_entr"], conv_frac=cfg["conv_frac"],
                      plume_ne_model=model, x_K=cfg["x_K"])


JITTER = np.linspace(0.6, 1.4, 9)  # flame-tip intermittency: flame height varies about its mean
SAT_DB = 5.57                       # log-amplitude std of a Rayleigh-faded (saturated) signal


def mean_excess_db(col, f, d1, d2, clearance, depth):
    """Excess loss from the ensemble-mean received power over flame-height jitter.

    The flame tip is intermittent (McCaffrey 1979), so a single sharp flame top would give
    unphysical Fresnel ripples. Averaging power over heights 0.6 to 1.4 times the mean
    flame height gives a smooth mean loss."""
    H0, p_fire, p_gnd = col.H, 0.0, 0.0
    for j in JITTER:
        col.H = H0 * j
        lf, lg = column_loss_db(col, f, d1, d2, clearance, depth)
        p_fire += 10 ** (-lf / 10)
        p_gnd += 10 ** (-lg / 10)
    col.H = H0
    lf, lg = -10 * np.log10(p_fire / len(JITTER)), -10 * np.log10(p_gnd / len(JITTER))
    return lf, lg


def scint_db(col, f, d1, d2, clearance, depth, sigma_ratio):
    """Rytov log-amplitude std (dB), capped at the saturated (Rayleigh) value."""
    z = max(clearance, 0.1)
    cn2 = plume_cn2(col, np.array([z]), sigma_ratio)[0]
    thick = depth + 2 * col.alpha * z
    s_db, s2 = rytov_logamp_std_db(f, d1, d2, cn2, thick)
    return float(min(s_db, SAT_DB)), float(s2)


def main():
    cfg = load_config(CFG_NAME)
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    sc = scenario_params(cfg)
    nums = {}

    # ---- 3a. Specific attenuation versus frequency -------------------------------------
    f = np.linspace(*cfg["freq_ghz_grid"][:2], cfg["freq_ghz_grid"][2]) * 1e9
    spec = pd.DataFrame({"f_ghz": f / 1e9})
    for k, v in sc.items():
        spec[k] = specific_attenuation_db_per_m(f, v["ne"], v["nu"])
    spec.to_csv(OUT / "specific_attenuation.csv", index=False)
    for k, v in sc.items():
        for fb in cfg["bands_ghz"]:
            nums[f"phys.spec_att.{k}.{fb}GHz"] = (float(specific_attenuation_db_per_m(fb * 1e9, v["ne"], v["nu"])),
                                                  "dB/m", f"Drude specific attenuation, scenario {k}, {fb} GHz")
    nums["phys.field_bound.ne"] = (sc["field_bound"]["ne"], "m^-3",
                                   "Path-averaged ne giving 5 dB over 40 m at 10 GHz (Euroka upper bound)")

    # Mphale and Heron reproduction (consistency check: ne, nu were inverted from the same data)
    rows = []
    for p in cfg["mphale_2007_measured"]["points"]:
        for fg, db in zip(p["f_ghz"], p["db"]):
            pred = float(specific_attenuation_db_per_m(fg * 1e9, p["ne"], p["nu"]))
            rows.append({"source": "Mphale and Heron 2007", "t_s": p["t_s"], "f_ghz": fg, "measured": db,
                         "drude_db_per_m": pred, "drude_db_over_0.5m": pred * 0.5})
    q = cfg["mphale_2008_cf_pine_60s"]
    for fg, db in zip(q["f_ghz"], q["db_per_m"]):
        pred = float(specific_attenuation_db_per_m(fg * 1e9, q["ne"], q["nu"]))
        rows.append({"source": "Mphale et al. 2008 pine 60 s", "t_s": 60, "f_ghz": fg, "measured": db,
                     "drude_db_per_m": pred, "drude_db_over_0.5m": pred * 0.5})
    chk = pd.DataFrame(rows)
    chk["ratio_per_m"] = chk.drude_db_per_m / chk.measured
    chk.to_csv(OUT / "mphale_check.csv", index=False)
    print(chk.to_string())
    nums["phys.mphale_check.max_abs_err_pct"] = (float(100 * np.max(np.abs(chk.ratio_per_m - 1))), "%",
                                                 "Largest Drude-vs-reported mismatch when reported values are read as dB/m")
    nums["phys.mphale_check.min_pred"] = (float(chk.drude_db_per_m.min()), "dB/m", "Smallest Drude prediction at the reported points")
    nums["phys.mphale_check.max_pred"] = (float(chk.drude_db_per_m.max()), "dB/m", "Largest Drude prediction at the reported points")

    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    cols = {"lab_grass": OI["purple"], "lab_peak": OI["vermillion"], "lab_late": OI["orange"], "field_bound": OI["blue"]}
    for k in ["lab_grass", "lab_peak", "lab_late", "field_bound"]:
        v = sc[k]
        ax.plot(spec.f_ghz, spec[k], color=cols[k],
                label=f"{v['label']}: ne = {v['ne']:.2g} m$^{{-3}}$, nu = {v['nu']:.2g} s$^{{-1}}$")
    ax.scatter(chk.f_ghz, chk.measured, color="k", s=18, zorder=5, label="Reported lab values (read as dB/m)")
    for fb in cfg["bands_ghz"]:
        ax.axvline(fb, color=OI["grey"], lw=0.7, ls=":", zorder=0)
        ax.text(fb, 1.3e-3, f"{fb}", ha="center", va="bottom", fontsize=7.5, color="0.35")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, 80)
    ax.set_ylim(1e-3, 30)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 80], ["1", "2", "5", "10", "20", "50", "80"])
    ax.set_xlabel("Frequency (GHz); dotted lines mark the modeled backhaul bands")
    ax.set_ylabel("Specific attenuation (dB/m)")
    ax.set_title("Cold collisional plasma (Drude) attenuation of a weakly ionized flame")
    fig.tight_layout(rect=(0, 0.2, 1, 1))
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", fontsize=7.5, ncol=1, bbox_to_anchor=(0.5, 0.0))
    savefig(fig, "phys_specific_attenuation")

    # ---- 3b. Vertical profiles -----------------------------------------------------------
    z = np.logspace(-1, np.log10(500), 400)
    prof = {"z_m": z}
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.9), sharey=True)
    for fire, ls in [("surface", "-"), ("crown", "--")]:
        col = make_column(cfg, fire, sc["lab_peak"], "saha")
        colf = make_column(cfg, fire, sc["lab_peak"], "frozen")
        dN = col.N_thermal(z) - col.N_ambient()
        prof[f"{fire}_T"] = col.T(z)
        prof[f"{fire}_ne_saha"] = col.ne(z)
        prof[f"{fire}_ne_frozen"] = colf.ne(z)
        prof[f"{fire}_dN"] = dN
        lab = f"{fire.capitalize()} fire ({col.I/1e3:g} MW/m, flame {col.H:.1f} m)"
        axes[0].plot(col.T(z) - 273.15, z, color=OI["vermillion"], ls=ls, label=lab)
        axes[1].plot(np.maximum(col.ne(z), 1e6), z, color=OI["blue"], ls=ls, label=f"{fire}: Saha")
        axes[1].plot(np.maximum(colf.ne(z), 1e6), z, color=OI["skyblue"], ls=ls, label=f"{fire}: frozen ions bound")
        axes[2].plot(dN, z, color=OI["green"], ls=ls, label=lab)
        nums[f"phys.profile.{fire}.flame_height_m"] = (col.H, "m", f"Flame height used for the {fire} fire")
        nums[f"phys.profile.{fire}.T_ion_K"] = (col.T_ion, "K", f"Effective ionization temperature calibrated for {fire} column")
        for zz in [2 * col.H, 50.0, 100.0]:
            nums[f"phys.profile.{fire}.ne_frozen_at_{zz:.0f}m"] = (float(colf.ne(np.array([zz]))[0]), "m^-3",
                                                                   f"Frozen-ion upper bound ne at {zz:.0f} m, {fire} fire")
            nums[f"phys.profile.{fire}.dT_at_{zz:.0f}m"] = (float(col.dT(np.array([zz]))[0]), "K",
                                                            f"Calm-air plume excess temperature at {zz:.0f} m, {fire} fire")
    pd.DataFrame(prof).to_csv(OUT / "profiles.csv", index=False)
    axes[0].set_xlabel("Temperature (°C)")
    axes[0].set_ylabel("Height above ground (m)")
    axes[0].set_yscale("log")
    axes[0].set_ylim(0.1, 500)
    axes[1].set_xscale("log")
    axes[1].set_xlim(1e6, 1e17)
    axes[1].set_xlabel("Free electron density (m$^{-3}$)")
    axes[2].set_xlabel("Refractivity change (N-units)")
    axes[0].set_title("Mean temperature")
    axes[1].set_title("Electrons (flame anchored at lab peak)")
    axes[2].set_title("Thermal refractivity")
    axes[0].legend(fontsize=7.5, loc="upper right")
    axes[1].legend(fontsize=7, loc="lower left")
    fig.suptitle("Modeled vertical structure above a fireline (calm air, line plume)", fontsize=11)
    fig.tight_layout()
    savefig(fig, "phys_profiles")

    # ---- 3c. Mean loss and scintillation versus ray clearance ------------------------------
    ex = cfg["example_link"]
    L = ex["L_m"]
    cgrid = np.linspace(*cfg["clearance_grid_m"][:2], cfg["clearance_grid_m"][2])
    rows = []
    for fire in ["surface", "crown"]:
        depth = cfg["fires"][fire]["flaming_depth_m"]
        for scen in ["lab_peak", "field_bound"]:
            col = make_column(cfg, fire, sc[scen])
            for fg in cfg["bands_ghz"]:
                fz = fg * 1e9
                for d1 in ex["d1_m"]:
                    d2 = L - d1
                    for c in cgrid:
                        lf, lg = mean_excess_db(col, fz, d1, d2, c, depth)
                        s_db, s2 = scint_db(col, fz, d1, d2, c, depth, cfg["sigma_T_ratio"])
                        rows.append({"fire": fire, "scenario": scen, "f_ghz": fg, "d1_m": d1, "clearance_m": c,
                                     "rF1_m": fresnel_radius(fz, d1, d2), "loss_fire_db": lf, "loss_ground_db": lg,
                                     "excess_db": lf - lg, "scint_std_db": s_db, "rytov_var": s2})
    lc = pd.DataFrame(rows)
    # Remove deterministic Fresnel ripple from sharp model edges: average received power over a
    # ray-height window of +-1 F1 radius (real rays wander by metres as refractivity changes).
    lc["excess_smooth_db"] = np.nan
    for _, g in lc.groupby(["fire", "scenario", "f_ghz", "d1_m"]):
        r1 = g.rF1_m.iloc[0]
        c = g.clearance_m.to_numpy()
        pf, pg = 10 ** (-g.loss_fire_db.to_numpy() / 10), 10 ** (-g.loss_ground_db.to_numpy() / 10)
        sm = [np.mean(pf[np.abs(c - ci) <= r1]) / np.mean(pg[np.abs(c - ci) <= r1]) for ci in c]
        lc.loc[g.index, "excess_smooth_db"] = -10 * np.log10(sm)
    lc.to_csv(OUT / "loss_vs_clearance.csv", index=False)

    # Key numbers: excess loss once the ray clears the flame top by 0.6 F1 (a planned link)
    for fire in ["surface", "crown"]:
        H = make_column(cfg, fire, sc["lab_peak"]).H
        for scen in ["lab_peak", "field_bound"]:
            for fg in cfg["bands_ghz"]:
                sub = lc[(lc.fire == fire) & (lc.scenario == scen) & (lc.f_ghz == fg) & (lc.d1_m == ex["d1_m"][0])]
                r1 = sub.rF1_m.iloc[0]
                for tag, cl in [("ray_at_flame_top", H), ("clear_0.6F1", H + 0.6 * r1), ("clear_50m", 50.0), ("clear_150m", 150.0)]:
                    i = np.argmin(np.abs(sub.clearance_m - cl))
                    nums[f"phys.excess.{fire}.{scen}.{fg}GHz.{tag}"] = (float(sub.excess_smooth_db.iloc[i]), "dB",
                        f"Mean excess loss, {fire} fire, {scen}, {fg} GHz, 5 km link mid-span, clearance {tag}")
                    if scen == "lab_peak":
                        nums[f"phys.scint.{fire}.{fg}GHz.{tag}"] = (float(sub.scint_std_db.iloc[i]), "dB",
                            f"Plume scintillation std, {fire} fire, {fg} GHz, 5 km link mid-span, clearance {tag}")

    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    fcol = dict(zip(cfg["bands_ghz"], [OI["blue"], OI["skyblue"], OI["green"], OI["orange"], OI["vermillion"], OI["purple"]]))
    for j, fire in enumerate(["surface", "crown"]):
        H = make_column(cfg, fire, sc["lab_peak"]).H
        for fg in cfg["bands_ghz"]:
            for scen, ls in [("lab_peak", "-"), ("field_bound", "--")]:
                sub = lc[(lc.fire == fire) & (lc.scenario == scen) & (lc.f_ghz == fg) & (lc.d1_m == ex["d1_m"][0])]
                axes[0, j].plot(sub.clearance_m, np.clip(sub.excess_smooth_db, -5, 60), color=fcol[fg], ls=ls,
                                label=f"{fg} GHz" if scen == "lab_peak" else None)
            sub = lc[(lc.fire == fire) & (lc.scenario == "lab_peak") & (lc.f_ghz == fg) & (lc.d1_m == ex["d1_m"][0])]
            axes[1, j].plot(sub.clearance_m, sub.scint_std_db, color=fcol[fg], label=f"{fg} GHz")
        for ax in axes[:, j]:
            ax.axvspan(0, H, color=OI["vermillion"], alpha=0.12, lw=0)
        axes[0, j].axhspan(-0.3, 0.3, color=OI["grey"], alpha=0.25, lw=0,
                           label="+-0.3 dB: residual model ripple" if j == 0 else None)
        axes[0, j].set_title(f"{fire.capitalize()} fire, {cfg['fires'][fire]['intensity_kw_m']/1e3:g} MW/m, flame {H:.1f} m, "
                             f"depth {cfg['fires'][fire]['flaming_depth_m']} m", fontsize=10)
        axes[0, j].set_yscale("symlog", linthresh=0.1)
        axes[0, j].set_ylim(-1, 70)
        axes[0, j].set_xscale("symlog", linthresh=10)
        axes[0, j].set_xlim(0, 300)
        axes[1, j].set_yscale("log")
        axes[1, j].set_ylim(1e-3, 30)
        axes[1, j].set_xlabel("Ray height above ground at the fire (m)")
        axes[1, j].set_xscale("symlog", linthresh=10)
        axes[1, j].set_xlim(0, 300)
    axes[0, 0].set_ylabel("Mean excess loss (dB),\naveraged over +-1 F1 of ray height")
    axes[1, 0].set_ylabel("Scintillation std (dB), capped at 5.6 dB")
    axes[0, 0].plot([], [], color="k", ls="-", label="Lab peak ne")
    axes[0, 0].plot([], [], color="k", ls="--", label="Field bound ne")
    axes[0, 0].legend(fontsize=7.5, ncol=2, loc="upper right")
    fig.suptitle("Modeled excess loss and plume scintillation versus ray height; 5 km link, fire at mid-span, "
                 "calm-air plume (shading: flame band)", fontsize=10.5)
    fig.tight_layout()
    savefig(fig, "phys_loss_clearance")
    record(nums, "src/run_physics.py", f"configs/{CFG_NAME}")


if __name__ == "__main__":
    main()
