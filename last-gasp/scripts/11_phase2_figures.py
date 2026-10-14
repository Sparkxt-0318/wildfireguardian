"""Phase 2 figures and summary from results/phase2_sweeps.csv. SYNTHETIC.

Usage: .venv/bin/python scripts/11_phase2_figures.py
Writes figures/fig9_receive_example.*, fig10_gateways.*, fig11_trips.*, fig12_spacing_cost.* and
results/phase2_summary.json.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from lastgasp import economics, style  # noqa: E402
from lastgasp.deploy import edge_length_m, edge_polylines, road_length_m  # noqa: E402
from lastgasp.phase2 import load_config2, run_tags  # noqa: E402
from lastgasp.pipeline import get_world  # noqa: E402

FIG = ROOT / "figures"
style.apply()
C = style.OKABE_ITO


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def load():
    rows = [r for r in csv.DictReader(open(ROOT / "results/phase2_sweeps.csv")) if not r.get("error")]
    meta = json.loads((ROOT / "results/phase2_sweeps_meta.json").read_text())
    return rows, meta


def agg(rows, sweep, value, key, how="median"):
    a = np.array([num(r.get(key)) for r in rows if r["sweep"] == sweep and r["value"] == value])
    a = a[np.isfinite(a)]
    if not a.size:
        return np.nan
    if how == "sum":
        return float(a.sum())
    if how == "q25":
        return float(np.percentile(a, 25))
    if how == "q75":
        return float(np.percentile(a, 75))
    return float(np.median(a))


def pooled(rows, sweep, value, num_key, den_key):
    n = agg(rows, sweep, value, num_key, "sum")
    d = agg(rows, sweep, value, den_key, "sum")
    return n / d if d else np.nan


def summarise(rows):
    S = {}
    keys = ["n_tags", "tags_per_km2", "frac_deaths_observed", "frac_deaths_realtime", "delivery_lag_med_min",
            "frac_gateways_lost", "frac_tags_direct_link", "mean_tag_degree", "received_bldg_med", "received_bldg_p90",
            "perfect_bldg_med", "perfect_bldg_p90", "trips_bldg_med", "trips_bldg_p90", "tags_bldg_med",
            "tags_bldg_p90", "tags_trips_bldg_med", "tags_trips_bldg_p90", "n_log", "trips_n_obs", "n_tags",
            "cls_log_only_acc", "cls_with_tags_acc", "cls_log_only_precaution_recall",
            "cls_with_tags_precaution_recall", "cls_log_only_fire_recall", "cls_with_tags_fire_recall",
            "n_log_precaution_true", "n_log_fire_true"]
    pairs = sorted({(r["sweep"], r["value"]) for r in rows})
    for sw, v in pairs:
        d = {"n_runs": sum(1 for r in rows if r["sweep"] == sw and r["value"] == v)}
        for k in keys:
            m = agg(rows, sw, v, k)
            if np.isfinite(m):
                d[k] = m
        for p in ("perfect", "received"):
            if any(f"{p}_spot_n_true" in r for r in rows if r["sweep"] == sw):
                d[f"{p}_spot_precision"] = pooled(rows, sw, v, f"{p}_spot_n_matched_det", f"{p}_spot_n_detected")
                d[f"{p}_spot_recall"] = pooled(rows, sw, v, f"{p}_spot_n_matched_true", f"{p}_spot_n_true")
                d[f"{p}_spot_recall_observable"] = pooled(rows, sw, v, f"{p}_spot_n_matched_true",
                                                          f"{p}_spot_n_observable")
                d[f"{p}_spot_n_detected"] = agg(rows, sw, v, f"{p}_spot_n_detected", "sum")
                d[f"{p}_spot_n_true"] = agg(rows, sw, v, f"{p}_spot_n_true", "sum")
        for k in ("received_bldg_med", "received_bldg_p90", "frac_deaths_observed"):
            d[k + "_q25"] = agg(rows, sw, v, k, "q25")
            d[k + "_q75"] = agg(rows, sw, v, k, "q75")
        S.setdefault(sw, {})[v] = d
    return S


def fig_example():
    cfg = load_config2({"phase2.layout.spacing_m": 200})
    world, bxy, net = get_world(cfg)
    outs = {}
    for mode in ("star", "mesh"):
        c2 = load_config2({"phase2.layout.spacing_m": 200, "phase2.reception.mode": mode})
        outs[mode] = run_tags(c2, 0, 0, keep=True)
    W, H = world["width_m"] / 1000, world["height_m"] / 1000
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.2), constrained_layout=True, sharey=True)
    a = outs["mesh"]["_artifacts"]
    tag = a["tag_xy"] / 1000
    segs = [[tag[i], tag[j]] for i, j in zip(*a["tt"].nonzero()) if i < j]
    for ax in axes:
        ax.add_collection(LineCollection([np.asarray(r["xy"]) / 1000 for r in world["roads"]], colors="#e3e3e3",
                                         linewidths=0.5))
        ax.set_xlim(-0.1, W + 0.1)
        ax.set_ylim(-0.1, H + 0.1)
        ax.set_aspect("equal")
        ax.set_xlabel("Easting (km)")
    axes[0].set_ylabel("Northing (km)")
    ax = axes[0]
    ax.add_collection(LineCollection(segs, colors=C["skyblue"], linewidths=0.4, alpha=0.6))
    ax.scatter(tag[:, 0], tag[:, 1], s=4, c=C["blue"], lw=0)
    gw = a["gw_xy"] / 1000
    ax.scatter(gw[:, 0], gw[:, 1], marker="^", s=55, c=C["yellow"], edgecolors="k", lw=0.7, zorder=5, clip_on=False)
    ax.set_title(f"(a) {len(tag)} tags (200 m), 4 gateways,\ntag-to-tag LoRa links", fontsize=8.5)
    for ax, mode, lab in ((axes[1], "star", "(b) Star: direct to gateway"), (axes[2], "mesh", "(c) Mesh relaying")):
        o = outs[mode]
        aa = o["_artifacts"]
        died = np.isfinite(aa["t_death"])
        obs = np.isfinite(aa["rec"]["obs_time"])
        ax.scatter(tag[died & obs, 0], tag[died & obs, 1], s=6, c=C["vermillion"], lw=0, label="Death heard")
        ax.scatter(tag[died & ~obs, 0], tag[died & ~obs, 1], s=9, marker="x", c=C["grey"], lw=0.6,
                   label="Death not heard")
        g = aa["gw_xy"] / 1000
        ax.scatter(g[:, 0], g[:, 1], marker="^", s=55, c=C["yellow"], edgecolors="k", lw=0.7, zorder=5, clip_on=False)
        ax.set_title(f"{lab}\n{100 * o['frac_deaths_observed']:.0f}% of fire deaths heard", fontsize=8.5)
    axes[2].legend(loc="lower right", fontsize=7, frameon=True, framealpha=0.9, markerscale=1.8)
    fig.suptitle("Receive side, world 0, 4 gateways in a spread layout, exposed to the fire (triangles). "
                 f"{style.SYNTH_NOTE}.", fontsize=8.5)
    return style.save(fig, FIG, "fig9_receive_example")


def fig_gateways(S):
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 5.6), constrained_layout=True)
    G = [1, 2, 3, 4, 6, 8, 12]
    colors = {"star": C["grey"], "mesh": C["vermillion"]}
    labels = {"star": "Star (direct to gateway)", "mesh": "Mesh relaying"}
    ax = axes[0, 0]
    for mode in ("star", "mesh"):
        for hard, ls in (("exposed", "-"), ("hardened", "--")):
            y = [S["receive"].get(f"{mode}|{hard}|{g}", {}).get("frac_deaths_observed", np.nan) for g in G]
            ax.plot(G, y, ls=ls, marker="o", ms=3, color=colors[mode],
                    label=f"{labels[mode]}, {'hardened' if hard == 'hardened' else 'fire-exposed'} gateways")
    Gb = [1, 2, 4, 8, 12]
    for radio, col, lab in (("lora_pessimistic", C["orange"], "Mesh, pessimistic LoRa fit, exposed"),
                            ("ble", C["purple"], "BLE mesh, exposed")):
        yb = [S.get(f"receive_{radio}", {}).get(f"mesh|exposed|{g}", {}).get("frac_deaths_observed", np.nan) for g in Gb]
        ax.plot(Gb, yb, ls=":", marker="s", ms=3, color=col, label=lab)
    ax.set_ylabel("Fraction of fire deaths heard")
    ax.set_title("(a) Relaying and gateway exposure (spread layout)", fontsize=8.5, loc="left")
    ax = axes[0, 1]
    for pl, col, lab in (("coverage", C["grey"], "Coverage-greedy (clustered)"), ("spread", C["vermillion"], "Spread"),
                         ("perimeter", C["blue"], "Spread along the area edge")):
        y = [S["placement"].get(f"{pl}|{g}", {}).get("frac_deaths_observed", np.nan) for g in G]
        ax.plot(G, y, marker="o", ms=3, color=col, label=lab)
    ax.set_ylabel("Fraction of fire deaths heard")
    ax.set_title("(b) Gateway layout, mesh, fire-exposed gateways", fontsize=8.5, loc="left")
    ax.legend(fontsize=6.5, frameon=True, framealpha=0.95, edgecolor="none", loc="lower right")
    ax = axes[1, 0]
    for mode in ("star", "mesh"):
        for hard, ls in (("exposed", "-"), ("hardened", "--")):
            y2 = [S["receive"].get(f"{mode}|{hard}|{g}", {}).get("received_bldg_p90", np.nan) for g in G]
            ax.plot(G, y2, ls=ls, marker="o", ms=3, color=colors[mode])
    p_perf = S["receive"]["mesh|exposed|4"].get("perfect_bldg_p90", np.nan)
    ax.axhline(p_perf, color="k", lw=0.8, ls=":", label="Perfect reception")
    ax.set_ylabel("90th percentile error (min)")
    ax.set_ylim(bottom=0)
    ax.set_title("(c) Arrival-time error (lines as in a)", fontsize=8.5, loc="left")
    ax.legend(fontsize=6.5, frameon=False, loc="upper right")
    for a_ in (axes[0, 0], axes[0, 1], axes[1, 0]):
        a_.set_xticks([1, 2, 4, 6, 8, 12])
        a_.set_xlabel("Gateways in 10.4 km²")
    axes[0, 0].set_ylim(0, 1.02)
    axes[0, 1].set_ylim(0, 1.02)
    ax = axes[1, 1]
    cats = [("Battery\ngateways", S["receive"]["mesh_sf|exposed|4"]),
            ("Grid-\npowered", S.get("receive_gridpower", {}).get("mesh_sf|exposed|4|grid", {})),
            ("Backhaul\noutage,\nbuffered", S.get("backhaul", {}).get("fail40_restore100_buffer", {})),
            ("Backhaul\noutage,\nno buffer", S.get("backhaul", {}).get("fail40_restore100_nobuffer", {}))]
    x = np.arange(len(cats))
    ax.bar(x - 0.18, [c[1].get("frac_deaths_observed", np.nan) for c in cats], 0.36, color=C["blue"],
           label="Heard by end of event")
    ax.bar(x + 0.18, [c[1].get("frac_deaths_realtime", np.nan) for c in cats], 0.36, color=C["skyblue"],
           label="Heard within 5 min")
    ax.set_xticks(x)
    ax.set_xticklabels([c[0] for c in cats], fontsize=7)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Fraction of fire deaths heard")
    ax.set_title("(d) Mesh, 4 exposed gateways: power and backhaul\n(backhaul out from 40 to 100 min)", fontsize=8,
                 loc="left")
    ax.legend(fontsize=6.5, frameon=False, loc="upper right", ncol=2)
    for a_ in axes.ravel():
        a_.grid(axis="y", color="#e5e5e5", lw=0.6)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=6.8, bbox_to_anchor=(0.5, -0.075),
               handlelength=3.2)
    fig.suptitle("Receive side: LoRa tags every 200 m of road (about 12 per km²), medians over 10 runs.\n"
                 f"{style.SYNTH_NOTE}.", fontsize=8.5)
    return style.save(fig, FIG, "fig10_gateways")


def fig_trips(S):
    fig = plt.figure(figsize=(7.4, 3.9), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1, 0.8])
    axes = [fig.add_subplot(gs[0, i]) for i in range(3)]
    sp = [200, 400, 800, 1600]
    T = S["trips_spacing"]
    for kinds, mk, col, lab in (("breaker+recloser", "o", C["vermillion"], "SCADA devices"),
                                ("breaker+recloser+fuse", "s", C["orange"], "plus fuses")):
        tags_n = [T[f"{kinds}|{s}"]["n_tags"] / 10.4 for s in sp]
        axes[0].plot(tags_n, [T[f"{kinds}|{s}"]["tags_trips_bldg_p90"] for s in sp], marker=mk, ms=3.5,
                     color=col, label=f"Tags + trips ({lab})")
        axes[0].axhline(T[f"{kinds}|200"]["trips_bldg_p90"], ls="--", lw=1, color=col, label=f"Trips only ({lab})")
    tags_n = [T[f"breaker+recloser|{s}"]["n_tags"] / 10.4 for s in sp]
    axes[0].plot(tags_n, [T[f"breaker+recloser|{s}"]["tags_bldg_p90"] for s in sp], marker="^", ms=3.5,
                 color=C["blue"], label="Tags only")
    from matplotlib.ticker import FixedLocator, NullLocator
    axes[0].set_xscale("log")
    axes[0].xaxis.set_major_locator(FixedLocator([0.5, 1, 2, 5, 10]))
    axes[0].set_xticklabels(["0.5", "1", "2", "5", "10"])
    axes[0].xaxis.set_minor_locator(NullLocator())
    axes[0].set_xlabel("Tags per km² (along roads)")
    axes[0].set_ylabel("90th percentile error (min)")
    axes[0].set_ylim(bottom=0)
    axes[0].set_title("(a) Trip logs added to sparse tags", fontsize=8.5, loc="left")
    axes[0].legend(fontsize=6.2, frameon=False, loc="upper right")
    P = S["trips_precaution"]
    names = [("no_precaution", "No shutoff"), ("untyped_no_precaution", "No shutoff, type missing"),
             ("blanket60_typed", "Blanket shutoff 60 min"), ("blanket60_untyped", "Blanket, type missing"),
             ("proximity_typed", "Shutoff ahead of fire"), ("proximity_untyped", "Ahead of fire, type missing"),
             ("reactive_untyped", "Reactive cut, type missing"), ("logging_stops_40", "Logging stops at 40 min")]
    y = np.arange(len(names))[::-1]
    fire_n = np.array([P[n].get("n_log_fire_true", 0.0) for n, _ in names])
    pre_n = np.array([P[n].get("n_log_precaution_true", 0.0) for n, _ in names])
    axes[1].barh(y, fire_n, color=C["vermillion"], label="Fire-caused trips")
    axes[1].barh(y, pre_n, left=fire_n, color=C["skyblue"], label="Precautionary opens")
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([l for _, l in names], fontsize=6.8)
    axes[1].set_xlabel("Entries per fire")
    axes[1].set_title("(b) What the log contains", fontsize=8.5, loc="left")
    axes[1].legend(fontsize=6.3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=1)
    a1 = np.array([P[n].get("cls_log_only_acc", np.nan) for n, _ in names])
    a2 = np.array([P[n].get("cls_with_tags_acc", np.nan) for n, _ in names])
    axes[2].barh(y + 0.2, a1, 0.4, color=C["grey"], label="Log only")
    axes[2].barh(y - 0.2, a2, 0.4, color=C["blue"], label="Log + tags (400 m)")
    axes[2].set_yticks(y)
    axes[2].set_yticklabels([])
    axes[2].set_xlim(0, 1.05)
    axes[2].set_xlabel("Accuracy")
    axes[2].set_title("(c) Fire or shutoff?", fontsize=8.5, loc="left")
    axes[2].legend(fontsize=6.3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=1)
    for ax in axes:
        ax.grid(axis="x" if ax is not axes[0] else "y", color="#e5e5e5", lw=0.6)
    fig.suptitle("Utility protection-device trip logs as a coarse layer (medians over 10 runs). "
                 f"{style.SYNTH_NOTE}.", fontsize=8.5)
    return style.save(fig, FIG, "fig11_trips")


def fig_spacing(S, econ, lengths):
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.1), constrained_layout=True)
    sp = [50, 100, 200, 400, 800, 1600]
    for kind, col, lab in (("roads", C["blue"], "Along roads"), ("edge", C["green"], "Along forest edge")):
        R = S["spacing"]
        L = lengths[kind]
        per_km = np.array([R[f"{kind}|{s}"]["n_tags"] / L for s in sp])
        for key, ls, sfx in (("perfect", "--", "perfect reception"), ("received", "-", "4 exposed gateways, mesh")):
            y = [R[f"{kind}|{s}"].get(f"{key}_bldg_p90", np.nan) for s in sp]
            axes[0].plot(per_km, y, ls=ls, marker="o", ms=3, color=col, label=f"{lab}, {sfx}")
            r = [R[f"{kind}|{s}"].get(f"{key}_spot_recall", np.nan) for s in sp]
            axes[1].plot(per_km, r, ls=ls, marker="o", ms=3, color=col)
        cost = [econ["cost_per_km_by_spacing"][kind][str(s)]["upfront_usd_per_km"] for s in sp]
        y = [R[f"{kind}|{s}"].get("received_bldg_p90", np.nan) for s in sp]
        axes[2].plot(cost, y, marker="o", ms=3, color=col, label=lab)
        for c_, y_, s in zip(cost, y, sp):
            if s in (100, 400, 1600):
                axes[2].annotate(f"{s} m", (c_, y_), textcoords="offset points", xytext=(4, 3), fontsize=6.5)
    from matplotlib.ticker import FixedLocator, NullLocator
    for ax, ticks in zip(axes, ([0.1, 0.3, 1, 3, 10], [0.1, 0.3, 1, 3, 10], [100, 200, 400, 800])):
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.set_xticklabels([f"{t:g}" for t in ticks])
        ax.xaxis.set_minor_locator(NullLocator())
        ax.grid(axis="y", color="#e5e5e5", lw=0.6)
    axes[0].set_xlabel("Tags per km of line")
    axes[0].set_ylabel("90th percentile error (min)")
    axes[0].set_ylim(bottom=0)
    axes[0].set_title("(a) Arrival-time error", fontsize=8.5, loc="left")
    axes[1].set_xlabel("Tags per km of line")
    axes[1].set_ylabel("Spot fire recall (pooled)")
    axes[1].set_ylim(0, 1.02)
    axes[1].set_title("(b) Significant spot fires found", fontsize=8.5, loc="left")
    axes[2].set_xlabel("Up-front cost per km of line (USD)")
    axes[2].set_ylabel("90th percentile error (min)")
    axes[2].set_ylim(bottom=0)
    axes[2].set_title("(c) Cost versus error", fontsize=8.5, loc="left")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, fontsize=7, bbox_to_anchor=(0.5, -0.14))
    fig.suptitle("Tag spacing, accuracy and cost (medians over 10 runs; costs are estimates from cited part prices). "
                 f"{style.SYNTH_NOTE}.", fontsize=8.2)
    return style.save(fig, FIG, "fig12_spacing_cost")


def economics_table(S, lengths):
    cfg = load_config2()
    e = cfg["phase2"]["economics"]
    life = economics.battery_life_years(e)
    out = {"battery": life, "tag_unit_usd": economics.tag_unit_cost(e), "cost_per_km_by_spacing": {}}
    for kind in ("roads", "edge"):
        out["cost_per_km_by_spacing"][kind] = {}
        for s in (50, 100, 200, 400, 800, 1600):
            d = S["spacing"][f"{kind}|{s}"]
            tpk = d["n_tags"] / lengths[kind]
            gpk = 4 / lengths[kind]
            out["cost_per_km_by_spacing"][kind][str(s)] = {"tags_per_km": tpk, "gateways_per_km": gpk,
                                                           **economics.cost_per_km(tpk, gpk, e, life["life_years"])}
    area = 10.4027
    out["cost_per_km2_roads"] = {}
    for s in (50, 100, 200, 400, 800, 1600):
        n = S["spacing"][f"roads|{s}"]["n_tags"]
        c = economics.cost_per_km(n, 4, e, life["life_years"])
        out["cost_per_km2_roads"][str(s)] = {"tags_per_km2": n / area, "upfront_usd_per_km2": c["upfront_usd_per_km"] / area,
                                             "annual_usd_per_km2": c["annual_usd_per_km"] / area}
    alt = {}
    for interval in (10, 30, 60, 120):
        alt[str(interval)] = economics.battery_life_years({**e, "beacon_interval_s": interval})["life_years"]
    out["battery_life_years_by_interval"] = alt
    alt_sf = {}
    for sf in (7, 9, 12):
        alt_sf[str(sf)] = economics.battery_life_years({**e, "lora_sf": sf})["life_years"]
    out["battery_life_years_by_sf"] = alt_sf
    out["battery_life_years_ble"] = economics.battery_life_years({**e, "radio": "ble"})["life_years"]
    return out


if __name__ == "__main__":
    rows, meta = load()
    S = summarise(rows)
    world, bxy, _ = get_world(load_config2())
    lengths = {"roads": road_length_m(world) / 1000, "edge": edge_length_m(edge_polylines(world, bxy, 100)) / 1000}
    econ = economics_table(S, lengths)
    out = {"summary": S, "economics": econ, "line_length_km": lengths,
           "_provenance": {**{k: meta[k] for k in ("commit", "code_dirty", "script", "config", "fire_seeds",
                                                   "obs_seeds", "n_runs", "n_errors", "wall_s") if k in meta},
                           "summary_script": "scripts/11_phase2_figures.py"}}
    (ROOT / "results/phase2_summary.json").write_text(json.dumps(out, indent=1, default=float))
    for p in (fig_example(), fig_gateways(S), fig_trips(S), fig_spacing(S, econ, lengths)):
        print(p)
