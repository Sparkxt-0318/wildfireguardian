"""PROTOCOL_v3 Part A routing (sections 7-8). Run from this folder:

    python3 v3_route.py --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz --shard i/n     (per path, parallel)
    python3 v3_route.py --grid GRID_JSON --osm ... --merge                                         (merge + ensemble)

Reads export_v3/per_path.npz and counts.npz. Writes out_v3/shard_*.json, out_v3/summary_v3.json and, for the ensemble,
the blocking rasters and road-layer results under out_v3/ensemble/.
Runs whose blocking times are identical on every road cell to an earlier run of the same path are reused (marked).
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import osm_graph as G  # noqa: E402
import route as R  # noqa: E402
from run_v2 import origin_changes, write_raster  # noqa: E402

HEAT = {"residents": ("h1_res", "fed10"), "responders": ("h1_resp", "fed10")}
HEAT_S = {"residents": ("h1_res_s", "fed10_s"), "responders": ("h1_resp_s", "fed10_s")}
GAS, GAS_S = ("co", "acrolein", "hcn"), ("co_s", "acrolein_s", "hcn_s")
LEVELS = {"any": None, "p10": 0.1, "p50": 0.5, "p90": 0.9}


def need(level, n):
    v = LEVELS[level]
    return 1 if v is None else int(np.ceil(v * n - 1e-9))


class Runner:
    def __init__(self, a):
        self.grid = G.Grid.from_json(a.grid)
        self.graph, self.origins, self.exits, _ = G.build(a.osm, a.grid, "2024-08-23T00:00:00Z")
        z = np.load(HERE / "export_v3" / "per_path.npz")
        self.crit = [str(c) for c in z["criteria"]]
        self.fm = z["first_min"]
        self.lead = z["lead"]
        self.rr, self.cc = z["road_row"], z["road_col"]
        self.tmp = Path(tempfile.mkdtemp())
        self.shape = (self.grid.H, self.grid.W)
        self.runs = 0

    def raster(self, road_minutes):
        arr = np.full(self.shape, np.inf)
        arr[self.rr, self.cc] = road_minutes
        return arr

    def route(self, road_minutes, label, cache):
        key = np.asarray(road_minutes, float).tobytes()
        for k, rows, info in cache:
            if k == key:
                return rows, info, True
        p2 = self.tmp / ("%s.tif" % label)
        write_raster(p2, self.raster(road_minutes), self.grid, 6, "routing_link v3 " + label, {})
        rows, info, close = R.run(self.graph, self.origins, self.exits, p2, self.grid, workers=1)
        self.runs += 1
        cache.append((key, rows, info))
        return rows, info, False

    def c(self, pth, name):
        return self.fm[pth, self.crit.index(name)].astype(float)


def attribute(contact, heat, gas):
    """First cause per road cell; ties: flame contact, then heat, then gas."""
    first = np.minimum(contact, np.minimum(heat, gas))
    blocked = np.isfinite(first)
    cause = np.where(~blocked, "none", np.where(contact <= first, "flame", np.where(heat <= first, "heat", "gas")))
    return cause


def path_record(run, pth):
    cache = []
    contact = run.c(pth, "contact")
    rows0, info0, _ = run.route(contact, "p%d_contact" % pth, cache)
    L0 = {r["origin"]: r for r in rows0}
    H = info0["horizon_s"]
    rec = {"contact_only": {"road_cells_blocked": int(np.isfinite(contact).sum()),
                            "origins_with_cut": sum(1 for r in rows0 if r["refusal"] is None and r["cut_s"] is not None)}}
    wc = run.c(pth, "wholecell")
    rowsW, _, reusedW = run.route(wc, "p%d_wholecell" % pth, cache)
    rec["wholecell"] = {"road_cells_blocked": int(np.isfinite(wc).sum()),
                        "origins_with_cut": sum(1 for r in rowsW if r["refusal"] is None and r["cut_s"] is not None),
                        "contact_vs_wholecell": origin_changes({r["origin"]: r for r in rowsW}, rows0, H),
                        "wholecell_minus_contact_minutes_on_road_cells": (
                            [float(x) for x in (contact - wc)[np.isfinite(contact) & np.isfinite(wc)]])}
    for aud in ("residents", "responders"):
        for tag, heat_names, gas_names in (("", HEAT[aud], GAS), ("_surface_only", HEAT_S[aud], GAS_S)):
            heat = np.min(np.stack([run.c(pth, n) for n in heat_names]), axis=0)
            gas = np.min(np.stack([run.c(pth, n) for n in gas_names]), axis=0)
            comb = np.minimum(contact, np.minimum(heat, gas))
            rowsB, infoB, reusedB = run.route(comb, "p%d_%s%s" % (pth, aud, tag), cache)
            oc = origin_changes(L0, rowsB, H)
            cause = attribute(contact, heat, gas)
            r = {"road_cells_blocked": int(np.isfinite(comb).sum()), "reused": reusedB,
                 "because_of_heat": int(np.sum(cause == "heat")), "because_of_gas": int(np.sum(cause == "gas")),
                 "by_flame": int(np.sum(cause == "flame")),
                 "heat_before_contact_minutes": [float(x) for x in (contact - heat)[(cause == "heat") & np.isfinite(contact)]],
                 "heat_blocked_but_never_reached_by_flame": int(np.sum((cause == "heat") & ~np.isfinite(contact))),
                 "gas_blocked_but_never_reached_by_flame": int(np.sum((cause == "gas") & ~np.isfinite(contact))),
                 "by_criterion_first": {n: int(np.sum(np.isfinite(run.c(pth, n)) & (run.c(pth, n) < contact)))
                                        for n in heat_names + gas_names},
                 "origins": oc}
            if oc["n_changed"]:
                rowsH, _, _ = run.route(np.minimum(contact, heat), "p%d_%s%s_heat" % (pth, aud, tag), cache)
                rowsG, _, _ = run.route(np.minimum(contact, gas), "p%d_%s%s_gas" % (pth, aud, tag), cache)
                r["origins_heat_only"] = origin_changes(L0, rowsH, H)
                r["origins_gas_only"] = origin_changes(L0, rowsG, H)
            if tag == "":
                i_aud = 0 if aud == "residents" else 1
                ld = run.lead[pth, i_aud]
                m = (cause == "heat")
                r["heat_lead"] = [{"distance_m": float(ld[0, j]), "heat_min": float(ld[1, j]), "point_contact_min": float(ld[2, j])}
                                  for j in np.flatnonzero(m) if np.isfinite(ld[0, j])]
            rec[aud + tag] = r
    return rec


def ensemble(run, out):
    z = np.load(HERE / "export_v3" / "counts.npz")
    crit = [str(c) for c in z["criteria"]]
    counts, n = z["counts"], int(z["n_paths"])
    first = {}
    for lv in LEVELS:
        k = need(lv, n)
        first[lv] = {c: np.where((counts[i] >= k).any(axis=0), np.argmax(counts[i] >= k, axis=0).astype(float), np.inf)
                     for i, c in enumerate(crit)}
    ens = {"n_paths": n, "runs": {}}
    edir = out / "ensemble"
    edir.mkdir(parents=True, exist_ok=True)
    pairs = [("p50", "p50"), ("p10", "p50"), ("p90", "p50"), ("any", "any"), ("p50", "any"), ("any", "p50")]
    for fire_lv in ("p50", "any"):
        cache = []
        contact = first[fire_lv]["contact"]
        rows0, info0, _ = run.route(contact, "ens_contact_%s" % fire_lv, cache)
        L0 = {r["origin"]: r for r in rows0}
        H = info0["horizon_s"]
        ens["runs"]["contact_" + fire_lv] = {"road_cells_blocked": int(np.isfinite(contact).sum()),
                                             "origins_with_cut": sum(1 for r in rows0 if r["refusal"] is None and r["cut_s"] is not None)}
        for lv, fl in pairs:
            if fl != fire_lv:
                continue
            for aud in ("residents", "responders"):
                heat = np.min(np.stack([first[lv][c] for c in HEAT[aud]]), axis=0)
                gas = np.min(np.stack([first[lv][c] for c in GAS]), axis=0)
                comb = np.minimum(contact, np.minimum(heat, gas))
                label = "ens_%s_fire%s_%s" % (lv, fire_lv, aud)
                write_raster(edir / (label + ".tif"), run.raster(comb), run.grid, 6, "routing_link v3 ensemble " + label,
                             {"WFG_BLOCK_RULE": "PROTOCOL_v3 7: share %s, flame contact share %s, %s" % (lv, fire_lv, aud)})
                rows, info, reused = run.route(comb, label, cache)
                cause = attribute(contact, heat, gas)
                ens["runs"]["%s_fire%s_%s" % (lv, fire_lv, aud)] = {
                    "road_cells_blocked": int(np.isfinite(comb).sum()), "reused": reused,
                    "because_of_heat": int(np.sum(cause == "heat")), "because_of_gas": int(np.sum(cause == "gas")),
                    "by_criterion_first": {c: int(np.sum(first[lv][c] < contact)) for c in HEAT[aud] + GAS},
                    "origins": origin_changes(L0, rows, H)}
    ens["largest_share"] = {c: float(counts[i].max()) / n for i, c in enumerate(crit)}
    return ens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--osm", required=True)
    ap.add_argument("--out", default=str(HERE / "out_v3"))
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    run = Runner(a)
    n = run.fm.shape[0]
    if not a.merge:
        i, k = (int(v) for v in a.shard.split("/"))
        recs = {}
        for pth in range(i, n, k):
            recs[str(pth)] = path_record(run, pth)
        (out / ("shard_%d_of_%d.json" % (i, k))).write_text(json.dumps(recs))
        print("shard", a.shard, "paths", len(recs), "road-layer runs", run.runs)
        return
    P = {}
    for f in sorted(out.glob("shard_*.json")):
        P.update(json.loads(f.read_text()))
    assert sorted(int(x) for x in P) == list(range(n)), "shards incomplete"
    S = {"protocol": "PROTOCOL_v3.md Part A", "n_paths": n, "paths": P, "ensemble": ensemble(run, out)}
    T = {}
    for aud in ("residents", "responders", "residents_surface_only", "responders_surface_only"):
        recs = [P[str(i)][aud] for i in range(n)]
        T[aud] = {"paths_with_a_road_cell_blocked_because_of_heat": sum(1 for r in recs if r["because_of_heat"]),
                  "paths_with_a_road_cell_blocked_because_of_gas": sum(1 for r in recs if r["because_of_gas"]),
                  "road_cells_because_of_heat_total": sum(r["because_of_heat"] for r in recs),
                  "road_cells_because_of_gas_total": sum(r["because_of_gas"] for r in recs),
                  "paths_where_an_origin_changes": sum(1 for r in recs if r["origins"]["n_changed"]),
                  "origins_changed_total": sum(r["origins"]["n_changed"] for r in recs),
                  "largest_minutes_earlier": max([r["origins"]["earlier_by_min_largest"] for r in recs] + [0.0]),
                  "paths_where_heat_alone_changes_an_origin": sum(1 for r in recs if r.get("origins_heat_only", {}).get("n_changed")),
                  "paths_where_gas_alone_changes_an_origin": sum(1 for r in recs if r.get("origins_gas_only", {}).get("n_changed"))}
    T["contact_only_paths_with_a_cut_origin"] = sum(1 for i in range(n) if P[str(i)]["contact_only"]["origins_with_cut"])
    T["wholecell_paths_with_a_cut_origin"] = sum(1 for i in range(n) if P[str(i)]["wholecell"]["origins_with_cut"])
    T["paths_where_contact_differs_from_wholecell"] = sum(1 for i in range(n) if P[str(i)]["wholecell"]["contact_vs_wholecell"]["n_changed"])
    S["totals"] = T
    (out / "summary_v3.json").write_text(json.dumps(S))
    print(json.dumps(T, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "by_criterion_first"} for k, v in S["ensemble"]["runs"].items()}, indent=1))


if __name__ == "__main__":
    main()
