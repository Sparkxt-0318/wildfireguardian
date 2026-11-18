"""Rankings, stability, numbers.json, ranking.csv.gz (PROTOCOL §4, §6). Usage: python3 aggregate.py RUNS_DIR"""
from __future__ import annotations

import csv, gzip, json, re, sys
from collections import defaultdict
from pathlib import Path
from statistics import median

import numpy as np
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARMS = ["ORDINARY", "RUNNING", "WORST", "MEASURED", "MEASURED_GUST", "MEASURED_GUST_KMA"]
HZ = ["5h", "8h"]
HOURS = list(range(3, 16))
DELAYS = [30, 60, 120]
PRIMARY = ("MEASURED", "8h")
TO_LL = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

POP = {r["place_id"]: float(r["pop_hrsl_voronoi_2km"]) for r in csv.DictReader(open(HERE / "population.csv"))}
PLACE = {r["place_id"]: r for r in csv.DictReader(open(HERE / "population.csv"))}


def load(runs):
    J = {}
    for p in sorted(Path(runs).glob("*.json")):
        j = json.loads(p.read_text())
        J[(j["region"], j["arm"], j["horizon"], int(j["issue_utc"][11:13]))] = j
    return J


def merged(J, arm, hz, hour):
    """-> {cid: {"type", "meta", "regions", "gains": {D: {place_id: s}}}} over both regions (FRONT tiles summed)."""
    C = {}
    for region in ("yeongdeok_2025", "uiseong_andong_2025"):
        j = J.get((region, arm, hz, hour))
        if j is None:
            continue
        pid = [r["place_id"] for r in j["places"]]
        for c in j["candidates"]:
            e = C.setdefault(c["id"], {"type": c["type"], "meta": {}, "regions": [], "gains": {D: {} for D in DELAYS}})
            e["regions"].append(region)
            e["meta"][region] = {k: v for k, v in c.items() if k not in ("gains", "id", "type")}
            for D, g in c["gains"].items():
                for k, v in g.items():
                    e["gains"][int(D)][pid[int(k)]] = v
    return C


def score(gains):
    B = sum(POP[p] * s / 60 for p, s in gains.items())
    U = sum(s / 60 for s in gains.values())
    return B, U, len(gains)


def ranking(C, D, weighted=True):
    rows = []
    for cid, e in C.items():
        B, U, n = score(e["gains"][D])
        if n == 0:
            continue
        rows.append((cid, B, U, n))
    key = (lambda r: (-r[1], -r[2], -r[3], r[0])) if weighted else (lambda r: (-r[2], -r[3], -r[1], r[0]))
    return sorted(rows, key=key)


def main(runs):
    J = load(runs)
    R = {}  # (arm, hz, hour, D) -> ranking rows
    MERGED = {}
    for arm in ARMS:
        for hz in HZ:
            for h in HOURS:
                C = merged(J, arm, hz, h)
                MERGED[(arm, hz, h)] = C
                for D in DELAYS:
                    R[(arm, hz, h, D)] = ranking(C, D)
    # ranking.csv.gz
    with gzip.open(HERE / "ranking.csv.gz", "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["arm", "horizon", "issue_kst", "delay_min", "rank", "candidate", "type", "person_minutes",
                    "village_minutes", "villages_helped", "helped"])
        for (arm, hz, h, D), rows in R.items():
            C = MERGED[(arm, hz, h)]
            for i, (cid, B, U, n) in enumerate(rows, 1):
                g = C[cid]["gains"][D]
                w.writerow([arm, hz, f"{h + 9:02d}:00", D, i, cid, C[cid]["type"], round(B, 1), round(U, 2), n,
                            " ".join(f"{p}={s}" for p, s in sorted(g.items()))])
    # stability (§6)
    stab = {}
    for h in HOURS:
        top = lambda arm, hz=("8h"), D=60, wt=True: [r[0] for r in (R[(arm, hz, h, D)] if wt else ranking(MERGED[(arm, hz, h)], D, False))[:10]]
        P = top("MEASURED")
        ranks = {}
        for arm in ARMS:
            pos = {r[0]: i for i, r in enumerate(R[(arm, "8h", h, 60)], 1)}
            ranks[arm] = [pos.get(c) for c in P]
        ov = {arm: len(set(P) & set(top(arm))) for arm in ARMS if arm != "MEASURED"}
        stable = [c for c in P if sum(1 for arm in ARMS if arm != "MEASURED" and c in top(arm)) >= 4]
        stab[h] = {"primary_top10": P, "overlap_8h_d60": ov, "rank_in_arm": ranks,
                   "overlap_measured_5h": len(set(P) & set(top("MEASURED", "5h"))),
                   "overlap_unweighted": len(set(P) & set(top("MEASURED", wt=False))),
                   "overlap_d30": len(set(P) & set(top("MEASURED", D=30))),
                   "overlap_d120": len(set(P) & set(top("MEASURED", D=120))),
                   "stable": stable, "n_ranked_primary": len(R[("MEASURED", "8h", h, 60)])}
    summ = {}
    for arm in ARMS:
        if arm == "MEASURED":
            continue
        v = [stab[h]["overlap_8h_d60"][arm] for h in HOURS if stab[h]["primary_top10"]]
        summ[arm] = {"median": median(v) if v else None, "min": min(v) if v else None, "max": max(v) if v else None, "hours": len(v)}
    for k in ("overlap_measured_5h", "overlap_unweighted", "overlap_d30", "overlap_d120"):
        v = [stab[h][k] for h in HOURS if stab[h]["primary_top10"]]
        summ[k] = {"median": median(v) if v else None, "min": min(v) if v else None, "max": max(v) if v else None}
    # per configuration totals
    conf = {}
    for arm in ARMS:
        for hz in HZ:
            for D in DELAYS:
                tops = [R[(arm, hz, h, D)][0] if R[(arm, hz, h, D)] else None for h in HOURS]
                conf[f"{arm}/{hz}/{D}"] = {
                    "ranked_candidates_per_hour": [len(R[(arm, hz, h, D)]) for h in HOURS],
                    "top1_person_minutes_per_hour": [round(t[1], 1) if t else 0 for t in tops],
                    "top1_per_hour": [t[0] if t else None for t in tops]}
    states = {}
    for arm in ARMS:
        for hz in HZ:
            for h in HOURS:
                cnt = defaultdict(int)
                for region in ("yeongdeok_2025", "uiseong_andong_2025"):
                    for r in J[(region, arm, hz, h)]["places"]:
                        cnt[r["state"]] += 1
                states[f"{arm}/{hz}/{h + 9:02d}"] = dict(cnt)
    numbers = {"stability_by_hour": {f"{h + 9:02d}:00": v for h, v in stab.items()}, "stability_summary": summ,
               "configurations": conf, "place_states": states,
               "candidates_evaluated": {f"{a}/{z}/{h + 9:02d}": {"road": sum(J[(r, a, z, h)]["n_road_candidates"] for r in ("yeongdeok_2025", "uiseong_andong_2025")),
                                                                   "front_tiles": len([c for c in MERGED[(a, z, h)].values() if c["type"] == "FRONT"])}
                                        for a in ARMS for z in HZ for h in HOURS},
               "population_total": round(sum(POP.values()), 1)}
    (HERE / "numbers.json").write_text(json.dumps(numbers, indent=1, ensure_ascii=False))
    return J, R, MERGED, stab, numbers


if __name__ == "__main__":
    main(sys.argv[1])
