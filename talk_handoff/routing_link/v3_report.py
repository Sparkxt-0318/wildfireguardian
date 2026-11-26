"""v3 Part A numbers for RESULTS_v3.md and the v3 figure (PROTOCOL_v3 section 8). Run from this folder after the merge:

    python3 v3_report.py --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz

Reads export_v3/per_path.npz, export_v3/counts.npz, out_v3/summary_v3.json. Re-runs the road layer only for the
ensemble pairing where an origin changed, with heat alone and gas alone added, to name the criterion (section 8 item 3).
Writes out_v3/report_v3.json and fig_v3_heat_gas.{png,svg,pdf}. No threshold or level is set here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v3_route as RT  # noqa: E402
from run_v2 import origin_changes  # noqa: E402

INK, GREY, BLUE, RED = "#1A1A1A", "#6B6B6B", "#2F5D8A", "#8A362F"
TINT_LIGHT, TINT_MID = "#C5D3E3", "#7E9BBD"


def q(x):
    x = np.asarray(x, float)
    if x.size == 0:
        return None
    return {"n": int(x.size), "min": float(x.min()), "p25": float(np.percentile(x, 25)), "median": float(np.median(x)),
            "p75": float(np.percentile(x, 75)), "max": float(x.max())}


def per_criterion(fm, crit):
    contact = fm[:, crit.index("contact")]
    out = {}
    for i, c in enumerate(crit):
        b = np.isfinite(fm[:, i])
        before = b & (fm[:, i] < contact)
        nb, nf = b.sum(axis=1), before.sum(axis=1)
        out[c] = {"paths_with_any_road_cell": int((nb > 0).sum()), "road_cells_per_path": q(nb[nb > 0]),
                  "road_cells_total": int(nb.sum()),
                  "paths_with_a_road_cell_before_contact": int((nf > 0).sum()),
                  "road_cells_before_contact_total": int(nf.sum()),
                  "road_cells_before_contact_and_never_contacted": int((b & ~np.isfinite(contact)).sum())}
    return out


def causes(fm, crit, heat_names, gas_names):
    contact = fm[:, crit.index("contact")]
    heat = np.min(np.stack([fm[:, crit.index(n)] for n in heat_names]), axis=0)
    gas = np.min(np.stack([fm[:, crit.index(n)] for n in gas_names]), axis=0)
    first = np.minimum(contact, np.minimum(heat, gas))
    blk = np.isfinite(first)
    flame = blk & (contact <= first)
    h = blk & ~flame & (heat <= first)
    g = blk & ~flame & ~h
    return flame, h, g, contact, heat, gas


def figure(run, n_heat, n_gas, n_contact, bars, stem, n_paths, label="Fish Creek, cutoff 2024-08-23", n_routed=350):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    grid = run.grid
    x0, res, ytop = grid.x0, grid.res, grid.ytop
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.0, 7.2), dpi=300, gridspec_kw={"width_ratios": [1.35, 1.0]})
    fig.patch.set_alpha(0)
    for a in (ax, bx):
        a.patch.set_alpha(0)
        for s in a.spines.values():
            s.set_color(GREY)
        a.tick_params(colors=GREY, labelsize=7)
    xy = {n["id"]: (n["x"] / 1000, n["y"] / 1000) for n in run.graph["nodes"]}
    seen = set()
    for e in run.graph["edges"]:
        k = tuple(sorted((e["u"], e["v"])))
        if k in seen:
            continue
        seen.add(k)
        (xa, ya), (xb, yb) = xy[e["u"]], xy[e["v"]]
        ax.plot([xa, xb], [ya, yb], color=INK, lw=0.4, solid_capstyle="round", zorder=2)
    cx = (x0 + (run.cc + 0.5) * res) / 1000
    cy = (ytop - (run.rr + 0.5) * res) / 1000
    m = n_contact > 0
    ax.scatter(cx[m], cy[m], s=18, marker="s", color=TINT_LIGHT, edgecolor="none", zorder=1)
    for arr, col in ((n_heat, BLUE), (n_gas, RED)):
        k = arr > 0
        ax.scatter(cx[k], cy[k], s=4 + 60 * np.sqrt(arr[k] / max(1, max(n_heat.max(), n_gas.max()))), color=col,
                   alpha=0.85, edgecolor="none", zorder=3)
    sel = m | (n_heat > 0) | (n_gas > 0)
    pad = 2.0
    ax.set_xlim(cx[sel].min() - pad, cx[sel].max() + pad)
    ax.set_ylim(cy[sel].min() - pad, cy[sel].max() + pad)
    ax.set_aspect("equal")
    ax.set_xlabel("x (km, EPSG:5070)", color=GREY, fontsize=8)
    ax.set_ylabel("y (km, EPSG:5070)", color=GREY, fontsize=8)
    h = [Line2D([0], [0], marker="s", color="none", markerfacecolor=TINT_LIGHT, markersize=7,
                label="Road cell reached by the flame in ≥ 1 path: %d" % int(m.sum())),
         Line2D([0], [0], marker="o", color="none", markerfacecolor=BLUE, markersize=6,
                label="Blocked because of heat (before the flame) in ≥ 1 path: %d" % int((n_heat > 0).sum())),
         Line2D([0], [0], marker="o", color="none", markerfacecolor=RED, markersize=6,
                label="Blocked because of gas (before the flame) in ≥ 1 path: %d" % int((n_gas > 0).sum())),
         Line2D([0], [0], color=INK, lw=0.8, label="Road (OpenStreetMap)")]
    leg = ax.legend(handles=h, loc="upper left", bbox_to_anchor=(0.0, -0.08), fontsize=7, frameon=False)
    for t in leg.get_texts():
        t.set_color(INK)

    labels = [b[0] for b in bars][::-1]
    vals = [b[1] for b in bars][::-1]
    y = np.arange(len(bars))
    bx.barh(y, vals, color=[RED if v > 0 else TINT_MID for v in vals], height=0.6)
    for yi, (v, note) in enumerate(zip(vals, [b[2] for b in bars][::-1])):
        bx.text(max(v, 0) + 0.06, yi, ("%d" % v) + (("  " + note) if note else ""), va="center", fontsize=7, color=INK)
    bx.set_yticks(y)
    bx.set_yticklabels(labels, fontsize=7, color=INK)
    bx.set_xlim(0, max(3, max(vals) + 3.2))
    bx.set_xlabel("origins whose last safe departure changes (of %d routed)" % n_routed, color=GREY, fontsize=8)
    fig.text(0.01, 0.006, label + ", 6 h horizon, %d paths  ·  residents: 2.5 kW/m², FED 0.3 in 10 min, "
             "AEGL-2 CO/acrolein/HCN  ·  marker size: number of paths" % n_paths, color=GREY, fontsize=6)
    fig.tight_layout()
    for ext_ in ("png", "svg", "pdf"):
        fig.savefig("%s.%s" % (stem, ext_), transparent=True)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--export", help="per-path export folder (default export_v3, Part A)")
    ap.add_argument("--out-dir", help="routing output folder (default out_v3, Part A)")
    ap.add_argument("--snapshot", help="OSM snapshot date (default 2024-08-23T00:00:00Z, Part A)")
    ap.add_argument("--fig", help="figure stem (default fig_v3_heat_gas)")
    ap.add_argument("--label", default="Fish Creek, cutoff 2024-08-23")
    a = ap.parse_args()
    od = Path(a.out_dir) if a.out_dir else HERE / "out_v3"
    a.out = str(od)
    run = RT.Runner(a)
    crit, fm = run.crit, run.fm
    n = fm.shape[0]
    S = json.loads((od / "summary_v3.json").read_text())
    R = {"n_paths": n, "n_road_cells": int(fm.shape[2]), "per_criterion": per_criterion(fm, crit)}

    # attribution per audience, full and surface only (counts of path x road cell)
    att = {}
    for aud in ("residents", "responders"):
        for tag, hn, gn in (("", RT.HEAT[aud], RT.GAS), ("_surface_only", RT.HEAT_S[aud], RT.GAS_S)):
            fl, h, g, contact, heat, gas = causes(fm, crit, hn, gn)
            att[aud + tag] = {"path_cells_flame": int(fl.sum()), "path_cells_heat": int(h.sum()), "path_cells_gas": int(g.sum()),
                              "paths_with_heat_cause": int(h.any(axis=1).sum()), "paths_with_gas_cause": int(g.any(axis=1).sum()),
                              "paths_with_heat_or_gas_cause": int((h | g).any(axis=1).sum()),
                              "distinct_road_cells_heat": int(h.any(axis=0).sum()), "distinct_road_cells_gas": int(g.any(axis=0).sum()),
                              "heat_minutes_before_contact": q((contact - heat)[h & np.isfinite(contact)]),
                              "gas_minutes_before_contact": q((contact - gas)[g & np.isfinite(contact)]),
                              "heat_cells_never_contacted": int((h & ~np.isfinite(contact)).sum()),
                              "gas_cells_never_contacted": int((g & ~np.isfinite(contact)).sum())}
            if aud == "residents" and tag == "":
                n_heat, n_gas = h.sum(axis=0), g.sum(axis=0)
                n_contact = np.isfinite(contact).sum(axis=0)
            if tag == "":
                i_aud = 0 if aud == "residents" else 1
                ld = run.lead[:, i_aud]
                dist, pmin = ld[:, 0][h], (ld[:, 2] - ld[:, 1])[h]
                ok = np.isfinite(dist)
                att[aud]["heat_lead_distance_m"] = q(dist[ok])
                ok2 = np.isfinite(pmin)
                att[aud]["heat_lead_minutes_at_point"] = q(pmin[ok2])
                att[aud]["heat_lead_point_never_contacted"] = int((ok & ~ok2).sum())
    R["attribution"] = att

    # whole-cell vs contact (section 8 item 6)
    c, w = fm[:, crit.index("contact")], fm[:, crit.index("wholecell")]
    both = np.isfinite(c) & np.isfinite(w)
    R["contact_vs_wholecell"] = {"paths_contact": int(np.isfinite(c).any(axis=1).sum()), "paths_wholecell": int(np.isfinite(w).any(axis=1).sum()),
                                 "path_cells_contact": int(np.isfinite(c).sum()), "path_cells_wholecell": int(np.isfinite(w).sum()),
                                 "wholecell_earlier_minutes": q((c - w)[both]),
                                 "wholecell_only_path_cells": int((np.isfinite(w) & ~np.isfinite(c)).sum())}
    P = S["paths"]
    R["per_path_origins"] = {k: {"paths_where_an_origin_changes": sum(1 for r in P.values() if r[k]["origins"]["n_changed"]),
                                 "contact_paths_with_a_cut_origin": sum(1 for r in P.values() if r["contact_only"]["origins_with_cut"])}
                             for k in ("residents", "responders", "residents_surface_only", "responders_surface_only")}
    R["reused_runs"] = {k: sum(1 for r in P.values() if r[k]["reused"]) for k in ("residents", "responders")}

    # section 8 item 3 for the one pairing that changes origins: share 'any' against the median fire
    z = np.load(run.export / "counts.npz")
    counts = z["counts"]
    cr = [str(x) for x in z["criteria"]]
    first = lambda i, k: np.where((counts[i] >= k).any(axis=0), np.argmax(counts[i] >= k, axis=0).astype(float), np.inf)
    contact50 = first(cr.index("contact"), RT.need("p50", n))
    contact_any = first(cr.index("contact"), 1)
    pair = {}
    cache = []
    rows0, info0, _ = run.route(contact50, "rep_contact_p50", cache)
    rowsA, _, _ = run.route(contact_any, "rep_contact_any", cache)
    L0 = {r["origin"]: r for r in rows0}
    H = info0["horizon_s"]
    for aud in ("residents", "responders"):
        heat = np.min(np.stack([first(cr.index(x), 1) for x in RT.HEAT[aud]]), axis=0)
        gas = np.min(np.stack([first(cr.index(x), 1) for x in RT.GAS]), axis=0)
        rh, _, _ = run.route(np.minimum(contact50, heat), "rep_any_heat_" + aud, cache)
        rg, _, _ = run.route(np.minimum(contact50, gas), "rep_any_gas_" + aud, cache)
        rb, _, _ = run.route(np.minimum(contact50, np.minimum(heat, gas)), "rep_any_both_" + aud, cache)
        pair[aud] = {"heat_and_gas": origin_changes(L0, rb, H), "heat_alone": origin_changes(L0, rh, H),
                     "gas_alone": origin_changes(L0, rg, H),
                     "changed_origins": sorted(r["origin"] for r in rb if L0[r["origin"]]["refusal"] is None and r["refusal"] is None
                                               and (r["last_safe_departure_s"], r["cut_s"]) != (L0[r["origin"]]["last_safe_departure_s"], L0[r["origin"]]["cut_s"])),
                     "same_origins_cut_by_flame_contact_any_path": sorted(r["origin"] for r in rowsA if r["refusal"] is None and r["cut_s"] is not None)}
    R["any_share_vs_median_fire"] = pair
    R["contact_any_vs_median_fire"] = origin_changes(L0, rowsA, H)
    R["road_layer_runs_here"] = run.runs
    (od / "report_v3.json").write_text(json.dumps(R, indent=1))

    E = S["ensemble"]["runs"]
    pp = R["per_path_origins"]
    def per_path_bar(aud):
        ch = [r[aud]["origins"]["n_changed"] for r in P.values()]
        k = sum(1 for c in ch if c)
        return ("each path alone, %s (largest)" % aud, max(ch), "changes in %d of %s paths" % (k, "{:,}".format(n)))

    def main_note(key):
        return "no road cell blocked" if E[key]["road_cells_blocked"] == 0 else ""

    anyr = E["any_firep50_residents"]["origins"]
    flame_any = R["contact_any_vs_median_fire"]
    if anyr["n_changed"]:
        same = anyr["earlier_by_min"] == flame_any["earlier_by_min"]
        any_note = "%.0f min earlier (median);\n%s" % (anyr["earlier_by_min_median"],
                   "flame alone (any path)\ngives the same" if same else
                   "flame alone (any path):\n%d origins" % flame_any["n_changed"])
    else:
        any_note = ""
    bars = [per_path_bar("residents"), per_path_bar("responders"),
            ("ensemble: share 0.5, fire 0.5 (main)", E["p50_firep50_residents"]["origins"]["n_changed"], main_note("p50_firep50_residents")),
            ("ensemble: share 0.1, fire 0.5", E["p10_firep50_residents"]["origins"]["n_changed"], main_note("p10_firep50_residents")),
            ("ensemble: share 0.9, fire 0.5", E["p90_firep50_residents"]["origins"]["n_changed"], main_note("p90_firep50_residents")),
            ("ensemble: any path, fire any path", E["any_fireany_residents"]["origins"]["n_changed"], ""),
            ("ensemble: any path, fire 0.5", anyr["n_changed"], any_note)]
    assert all(b[1] >= 0 for b in bars)
    figure(run, n_heat, n_gas, n_contact, bars, Path(a.fig) if a.fig else HERE / "fig_v3_heat_gas", n, a.label, E["p50_firep50_residents"]["origins"]["n_origins_routed"])
    print(json.dumps({k: v for k, v in R.items() if k != "per_criterion"}, indent=1))
    print(json.dumps({c: {k: v for k, v in d.items() if k != "road_cells_per_path"} for c, d in R["per_criterion"].items()}, indent=1))


if __name__ == "__main__":
    main()
