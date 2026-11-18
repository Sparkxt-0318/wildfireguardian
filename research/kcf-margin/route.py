"""Pixel-valid is not route-valid (PROTOCOL.md step 6), h = 5 h, 90% level, leave-one-fire-out.

For each held-out GOFER fire:
  * R_pix = fire-weighted 90% quantile of spread-cell distances to K_t, pooled over the OTHER 27 fires' hours;
  * R_iss = the per-issue-time conformal R (class all, alpha 0.10) from the other 27 fires (calibrate.py lofo_R.pkl);
  * sample up to 40 issue hours with spread; zone Z = K_t dilated by R; missed pixels = spread cells outside Z;
  * 4-neighbour road lattice, 1.5 km spacing, over the box around K_{t+h} padded 5 km beyond the zone; edges touching
    Z are closed; up to 30 random node pairs outside Z whose straight segment crosses Z; shortest open path (Dijkstra);
    a route fails if any cell on it is a missed pixel.

    python route.py --work WORK --out route.json
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, str(Path(__file__).parent))
from reach import CELL_KM, NEVER, component_reach, dist_km, weighted_quantile_by_fire  # noqa: E402

H = 5
SPACING = 4                    # cells (1.5 km)
HOURS_PER_FIRE, PAIRS_PER_HOUR = 40, 30
SEED = 20261116


def lattice_routes(Z, missed, rng, n_pairs, spacing=SPACING):
    """Returns (n_routes, n_failed, n_unreachable) on a lattice over the whole array Z."""
    nr, nc = (Z.shape[0] - 1) // spacing + 1, (Z.shape[1] - 1) // spacing + 1
    nid = np.arange(nr * nc).reshape(nr, nc)
    rows, cols, w, fail = [], [], [], {}
    for i in range(nr):
        for j in range(nc):
            for di, dj in ((0, 1), (1, 0)):
                i2, j2 = i + di, j + dj
                if i2 >= nr or j2 >= nc:
                    continue
                r0, c0, r1, c1 = i * spacing, j * spacing, i2 * spacing, j2 * spacing
                cells = (slice(r0, r1 + 1), slice(c0, c1 + 1))
                if Z[cells].any():
                    continue
                a, b = nid[i, j], nid[i2, j2]
                rows += [a, b]; cols += [b, a]; w += [1.0, 1.0]
                f = bool(missed[cells].any())
                fail[(a, b)] = fail[(b, a)] = f
    G = coo_matrix((w, (rows, cols)), shape=(nr * nc, nr * nc)).tocsr()
    nodes_out = [(i, j) for i in range(nr) for j in range(nc) if not Z[i * spacing, j * spacing]]
    if len(nodes_out) < 2:
        return 0, 0, 0
    done = fail_n = unreach = tries = 0
    while done + unreach < n_pairs and tries < 50 * n_pairs:
        tries += 1
        p, q = rng.choice(len(nodes_out), 2, replace=False)
        (i0, j0), (i1, j1) = nodes_out[p], nodes_out[q]
        ts = np.linspace(0, 1, 200)
        rr = np.rint((i0 + (i1 - i0) * ts) * spacing).astype(int)
        cc = np.rint((j0 + (j1 - j0) * ts) * spacing).astype(int)
        if not Z[rr, cc].any():
            continue                       # no detour needed
        s, t = nid[i0, j0], nid[i1, j1]
        _, pred = dijkstra(G, indices=s, return_predecessors=True)
        if pred[t] < 0:
            unreach += 1
            continue
        failed, v = False, t
        while v != s:
            u = pred[v]
            failed |= fail[(u, v)]
            v = u
        done += 1
        fail_n += failed
    return done, fail_n, unreach


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--numbers", help="also store the summary under 'pixel_vs_route' in this numbers.json")
    a = ap.parse_args()
    work = Path(a.work)
    pix = np.load(work / "gofer_pixdist.npz")
    pixd = {k.split("|")[0]: pix[k] for k in pix.files if k.endswith(f"|{H}")}
    lofoR = pd.read_pickle(work / "lofo_R.pkl")[("all28", H, 0.1)]
    reach = pd.read_csv(work / "gofer_reach.csv.gz")
    reach = reach[(reach.h == H) & (reach.reach_km > 0)]
    rng = np.random.default_rng(SEED)
    per_fire = {}
    for fire in sorted(pixd):
        R_pix = weighted_quantile_by_fire([v for f, v in pixd.items() if f != fire], 0.9)
        R_iss = lofoR[fire]
        z = np.load(work / "gofer_arrival" / f"{fire}.npz")
        A0 = z["A"]
        pad = int(math.ceil((max(R_pix, R_iss) + 5) / CELL_KM)) + SPACING
        A = np.full((A0.shape[0] + 2 * pad, A0.shape[1] + 2 * pad), NEVER, np.int32)
        A[pad:-pad, pad:-pad] = A0
        ts = reach[reach.fire == fire].t_idx.to_numpy()
        if len(ts) > HOURS_PER_FIRE:
            ts = rng.choice(ts, HOURS_PER_FIRE, replace=False)
        acc = {k: dict(pix_spread=0, pix_missed=0, routes=0, failed=0, unreachable=0, hours=0, hours_any_missed=0,
                        routes_in_missed_hours=0, failed_in_missed_hours=0)
               for k in ("pixel90", "issue90")}
        for t in sorted(ts):
            known = A <= t
            new = (A > t) & (A <= t + H)
            dist = dist_km(known)
            _, _, spread = component_reach(known, new, (5.0,), dist=dist)
            if not spread.any():
                continue
            box = np.argwhere(known | spread)
            for key, R in (("pixel90", R_pix), ("issue90", R_iss)):
                Z = dist <= R
                missed = spread & ~Z
                m = int(math.ceil((R + 5) / CELL_KM))
                r0, c0 = np.maximum(box.min(0) - m, 0)
                r1, c1 = np.minimum(box.max(0) + m + 1, A.shape)
                sub = (slice(r0, r1), slice(c0, c1))
                n, f, u = lattice_routes(Z[sub], missed[sub], rng, PAIRS_PER_HOUR)
                ac = acc[key]
                ac["pix_spread"] += int(spread.sum()); ac["pix_missed"] += int(missed.sum())
                ac["routes"] += n; ac["failed"] += f; ac["unreachable"] += u
                ac["hours"] += 1
                ac["hours_any_missed"] += int(missed.any())
                if missed.any():
                    ac["routes_in_missed_hours"] += n; ac["failed_in_missed_hours"] += f
        for ac in acc.values():
            ac["pixel_miss"] = ac["pix_missed"] / ac["pix_spread"] if ac["pix_spread"] else math.nan
            ac["route_fail"] = ac["failed"] / ac["routes"] if ac["routes"] else math.nan
            ac["hour_any_missed"] = ac["hours_any_missed"] / ac["hours"] if ac["hours"] else math.nan
            ac["route_fail_given_missed_hour"] = (ac["failed_in_missed_hours"] / ac["routes_in_missed_hours"]
                                                  if ac["routes_in_missed_hours"] else math.nan)
        per_fire[fire] = dict(R_pix_km=R_pix, R_iss_km=R_iss, hours=int(len(ts)), **acc)
        print(fire, f"Rpix={R_pix:.2f} Riss={R_iss:.2f}",
              {k: (round(v["pixel_miss"], 3), round(v["route_fail"], 3), v["routes"]) for k, v in acc.items()},
              flush=True)
    summary = {}
    for key in ("pixel90", "issue90"):
        pm = np.array([p[key]["pixel_miss"] for p in per_fire.values()])
        rf = np.array([p[key]["route_fail"] for p in per_fire.values()])
        ok = ~np.isnan(rf)
        hm = np.array([p[key]["hour_any_missed"] for p in per_fire.values()])
        rg = np.array([p[key]["route_fail_given_missed_hour"] for p in per_fire.values()])
        summary[key] = dict(pixel_miss_fire_weighted=float(np.nanmean(pm)), route_fail_fire_weighted=float(rf[ok].mean()),
                            spread_hours_with_any_missed_pixel_fire_weighted=float(np.nanmean(hm)),
                            route_fail_in_hours_with_a_miss_fire_weighted=float(np.nanmean(rg)),
                            n_fires_with_a_missed_hour=int((~np.isnan(rg)).sum()),
                            n_fires=int(ok.sum()), routes=int(sum(p[key]["routes"] for p in per_fire.values())),
                            label="MEASURED (synthetic grid road network: ASSUMED)")
    Path(a.out).write_text(json.dumps(dict(h=H, summary=summary, per_fire=per_fire), indent=1, default=float))
    print(json.dumps(summary, indent=1))
    if a.numbers:
        num = json.loads(Path(a.numbers).read_text())
        num["pixel_vs_route"] = dict(h=H, spacing_km=SPACING * CELL_KM, summary=summary,
                                     road_network=dict(value="synthetic 4-neighbour grid, 1.5 km", label="ASSUMED"))
        Path(a.numbers).write_text(json.dumps(num, indent=1, default=float))


if __name__ == "__main__":
    main()
