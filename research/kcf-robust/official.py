"""25 March 2025: each rule's order of cut-offs against the official alert and closure times (PROTOCOL.md 5.2.1).

Events: rows of research/kcf-validate/out/jaenan_replacement.csv with an official_kst, located exactly as
research/kcf-roadcut/validation.py locates them (its ROAD_RECORDS / road_cells for roads, its town assignment for
evacuation orders; Overture 2026-10-21.0 divisions and segments fetched with its own fetch_overture_theme.py).

    python3 official.py OUT OVERTURE_DIR
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "research/kcf-roadcut"))
import lib  # noqa: E402
import validation as V  # noqa: E402
from shapely.geometry import Point  # noqa: E402

UTC = timezone.utc
KST = timezone(timedelta(hours=9))
RULES = ("a", "b", "c", "d", "e")


def place_towns(regs):
    vt = json.loads((V.RAW / "village_towns.json").read_text())["towns"]
    out = {}
    for r, R in regs.items():
        for pid, p in R.places.items():
            lon, lat = V.TO_LL.transform(*R.xy[p["entry"]["node"]])
            town = next((n for n, g in V.LOCS if g.contains(Point(lon, lat))), None)
            sg = (p.get("sigungu") or {}).get("ko", "")
            if town is None and p.get("name"):
                town = next((k.split(" ")[1] for k, v in vt.items() if k.startswith(sg) and p["name"] in v), None)
            out[pid] = (sg, town, p.get("name") or "")
    return out


def main(out, odir):
    out = Path(out)
    ways = V.load_ways(odir)
    V.LOCS = V.localities(odir)
    regs = {r: V.Region(r, ways) for r in V.REGIONS}
    pt = place_towns(regs)
    off = {r["id"]: r for r in csv.DictReader(open(lib.REPO / "research/kcf-validate/out/jaenan_replacement.csv", encoding="utf-8-sig"))
           if r["official_kst"]}
    events = []
    for rid, what, t_s, spec, so in V.ROAD_RECORDS:
        if rid not in off:
            continue
        cells, note = V.road_cells(regs, spec)
        events.append({"id": rid, "kind": "road", "what": what, "official": off[rid]["official_kst"], "cells": cells, "note": note})
    for eid, county, scope, t_s, so in V.EVAC_RECORDS:
        if eid not in off:
            continue
        if scope[0] == "county":
            pids = [p for p, (sg, tw, nm) in pt.items() if sg == county]
        elif scope[0] == "towns":
            pids = [p for p, (sg, tw, nm) in pt.items() if sg == county and tw in scope[1]]
        else:
            pids = [p for p, (sg, tw, nm) in pt.items() if sg == county and nm in scope[1]]
        events.append({"id": eid, "kind": "evac", "what": "%s %s" % (county, scope[1] if len(scope) > 1 else "(whole county)"),
                       "official": off[eid]["official_kst"], "places": pids})
    # per rule, per region-hour: closures and place cuts
    data = {}
    for rid in lib.REGIONS:
        for T in lib.REPLAY_ISSUES:
            tag = "%s_%s" % (rid, T.strftime("%H"))
            res = json.loads((out / "replay" / (tag + ".json")).read_text())
            bc = json.loads((out / "replay" / (tag + "_bc.json")).read_text())
            cl = {"a": res["close_s"]["a"], "b": bc["close_s"]["b"], "c": bc["close_s"]["c"], "d": res["close_s"]["f50"],
                  "e": res["close_s"]["e"]}
            ru = {"a": res["rules"]["a"], "b": bc["rules"]["b"], "c": bc["rules"]["c"], "d": res["rules"]["d"], "e": res["rules"]["e"]}
            data[(rid, T)] = (cl, ru)
    end = lib.REPLAY_ISSUES[-1] + timedelta(seconds=lib.HORIZON_S)
    table = []
    for ev in events:
        t_off = datetime.fromisoformat(ev["official"]).replace(tzinfo=KST)
        row = {"id": ev["id"], "kind": ev["kind"], "what": ev["what"], "official_kst": ev["official"]}
        for k in RULES:
            if ev["kind"] == "road":
                tau = None
                for (rid, T), (cl, _) in data.items():
                    for c in ev["cells"].get(rid, []):
                        b = cl[k].get(str(c))
                        if b is not None:
                            t = T + timedelta(seconds=b)
                            tau = t if tau is None or t < tau else tau
                row[k] = tau
                row[k + "_n"] = sum(len(v) for v in ev["cells"].values())
            else:
                taus = []
                for p in ev["places"]:
                    tp = None
                    for (rid, T), (_, ru) in data.items():
                        r = ru[k].get(p)
                        if r and not r["refused"] and r["cut"] is not None:
                            t = T + timedelta(seconds=r["cut"])
                            tp = t if tp is None or t < tp else tp
                    if tp is not None:
                        taus.append(tp)
                row[k] = min(taus) if taus else None
                row[k + "_median"] = (datetime.fromtimestamp(statistics.median([t.timestamp() for t in taus]), UTC) if taus else None)
                row[k + "_n"] = len(ev["places"])
                row[k + "_n_cut"] = len(taus)
        table.append(row)

    def stats(rows, k, key):
        off_s = np.array([datetime.fromisoformat(r["official_kst"]).replace(tzinfo=KST).timestamp() for r in rows])
        mod = np.array([r[key].timestamp() if r[key] is not None else np.inf for r in rows])
        big = np.where(np.isfinite(mod), mod, end.timestamp() + 1e6)  # censored: ranked last (tied)
        from scipy.stats import spearmanr
        rho = float(spearmanr(off_s, big).statistic) if len(rows) > 2 else None
        rng = np.random.default_rng(20261119)
        bs = []
        for _ in range(2000):
            i = rng.integers(0, len(rows), len(rows))
            if len(set(off_s[i])) > 1 and len(set(big[i])) > 1:
                bs.append(spearmanr(off_s[i], big[i]).statistic)
        fin = np.isfinite(mod)
        diff = (mod[fin] - off_s[fin]) / 60.0
        return {"n": len(rows), "n_compared": int(fin.sum()), "censored": int((~fin).sum()), "spearman": rho,
                "spearman_ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))] if bs else None,
                "median_min_model_minus_official": float(np.median(diff)) if diff.size else None,
                "median_abs_min": float(np.median(np.abs(diff))) if diff.size else None}

    res = {}
    for k in RULES:
        res[k] = {"road": stats([r for r in table if r["kind"] == "road"], k, k),
                  "evac_first": stats([r for r in table if r["kind"] == "evac"], k, k),
                  "evac_median": stats([r for r in table if r["kind"] == "evac"], k, k + "_median"),
                  "pooled_first": stats(table, k, k)}
    with open(out / "official_events.csv", "w", newline="", encoding="utf-8") as f:
        cols = ["id", "kind", "what", "official_kst"] + [x for k in RULES for x in (k, k + "_median", k + "_n", k + "_n_cut")]
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        for r in table:
            w.writerow({c: (r.get(c).astimezone(KST).strftime("%Y-%m-%d %H:%M") if isinstance(r.get(c), datetime) else r.get(c, ""))
                        for c in cols})
    (out / "official_scores.json").write_text(json.dumps({"events": len(table), "locations": {e["id"]: e.get("note", "%d places" % len(e.get("places", [])))
                                                                                                for e in events}, "by_rule": res}, indent=1))
    for k in RULES:
        print(k, json.dumps(res[k]))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
