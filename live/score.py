"""Score live records against what later records saw (PROTOCOL §10). Separate from the run; never edits a record.

    python3 live/score.py --log LOGROOT [--now 2026-11-21T00:00:00Z]

A record at issue time T is scored no earlier than T + 8 h + 24 h, from later records only:
  * margin: detections acquired in (T, T + h] (from the inputs stored with later records), persistent sources removed,
    grouped into 5 km-linked components; a component whose nearest member is within 5 km (edge gap) of the record's
    known area is spread. Reach S_h = the largest distance from a spread member's centre to the known area's edge
    (research/kcf-replay MEASURED_RULE distance). Held if S_h <= R(h), h = 5, 8.
  * villages: reached early when a spread member disc covers the village's road entry point before the record's fire
    arrival time for that village.
  * KFS: the first later record in which the fire is no longer listed as 진화중.
Writes LOGROOT/scores/<stamp>.json once per record.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wfg_live import area, common as C  # noqa: E402


def later_detections(log: Path, recs, T, T_end, late_h=3.0):
    seen, out, n_inputs, missing = set(), [], 0, []
    for r in recs:
        t = C.parse_iso(r["issue_utc"])
        if not (T < t <= T_end + timedelta(hours=late_h)):
            continue
        idir = log / "inputs" / C.stamp(t)
        if not (idir / "manifest.json").exists():
            missing.append(r["issue_utc"])
            continue
        man = json.loads((idir / "manifest.json").read_text())
        n_inputs += 1
        kept, _ = area.firms_rows(idir, man)
        for d in kept + area.ahi_hotspots(idir, man):
            k = (d["src"], C.iso(d["t"]), round(d["lat"], 5), round(d["lon"], 5))
            if k in seen or not (T <= d["t"] < T_end):
                continue
            seen.add(k)
            out.append(d)
    return out, n_inputs, missing


def components(D, link):
    n = len(D)
    lab = -np.ones(n, int)
    X = np.array([d["x"] for d in D]); Y = np.array([d["y"] for d in D]); R = np.array([d["r_m"] for d in D])
    c = 0
    for i in range(n):
        if lab[i] >= 0:
            continue
        lab[i] = c
        stack = [i]
        while stack:
            j = stack.pop()
            nb = np.flatnonzero((lab < 0) & (np.hypot(X - X[j], Y - Y[j]) - R - R[j] <= link))
            lab[nb] = c
            stack.extend(nb.tolist())
        c += 1
    return lab


def score_fire(F, dets, T, cells, places):
    cfg = C.settings()["area"]
    K = F["area"]["discs"]
    KX = np.array([d["x"] for d in K]); KY = np.array([d["y"] for d in K]); KR = np.array([d["r_m"] for d in K])
    res = {"fire": F["id"], "class": F["margin"]["class"], "r5_km": F["margin"]["r5_km"], "r8_km": F["margin"]["r8_km"],
           "published_numbers": F.get("publish_numbers"), "withheld": F.get("withheld")}
    for h in (5, 8):
        D = []
        for d in dets:
            if not (T <= d["t"] < T + timedelta(hours=h)) or area._in_persistent(d, cells, cfg["persistent_cell_deg"]):
                continue
            x, y = area.to5179(d["lon"], d["lat"])
            D.append(dict(d, x=x, y=y))
        reach, n_spread = 0.0, 0
        spread = []
        if D:
            lab = components(D, cfg["link_km"] * 1000.0)
            for c in set(lab.tolist()):
                mem = [D[i] for i in np.flatnonzero(lab == c)]
                gap = min(float((np.hypot(KX - m["x"], KY - m["y"]) - KR - m["r_m"]).min()) for m in mem)
                if gap <= cfg["link_km"] * 1000.0:
                    spread.extend(mem)
            for m in spread:
                reach = max(reach, max(0.0, float((np.hypot(KX - m["x"], KY - m["y"]) - KR).min())))
            n_spread = len(spread)
        R = F["margin"]["r%d_km" % h]
        res["h%d" % h] = {"new_detections": len(D), "spread_members": n_spread, "reach_km": round(reach / 1000.0, 3),
                          "R_km": R, "held": reach / 1000.0 <= R}
        if h == 8:
            res["_spread8"] = spread
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--now")
    ap.add_argument("--late-h", type=float, default=3.0, help="use inputs of records made up to this long after T + 8 h (FIRMS NRT latency)")
    a = ap.parse_args()
    log = Path(a.log)
    now = C.parse_iso(a.now) if a.now else C.utcnow()
    paths = sorted((log / "records").rglob("*.json"))
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    recs.sort(key=lambda r: r["issue_utc"])
    places = {}
    for rid in ("yeongdeok_2025", "uiseong_andong_2025"):
        for f in json.loads((C.REPO / "planner/public/data/regions" / rid / "places.geojson").read_text())["features"]:
            places[f["properties"]["id"]] = f["properties"].get("entry") or {}
    done = 0
    for r in recs:
        T = C.parse_iso(r["issue_utc"])
        out = log / "scores" / (C.stamp(T) + ".json")
        if out.exists() or T + timedelta(hours=32) > now:
            continue
        sc = {"schema": "wfg.live.score/1", "record_issue_utc": r["issue_utc"], "scored_utc": C.iso(now),
              "rule": "live/score.py (PROTOCOL §10)", "fires": []}
        dets, n_in, missing = later_detections(log, recs, T, T + timedelta(hours=8), a.late_h)
        sc["later_inputs_used"] = n_in
        sc["later_records_without_inputs"] = missing
        later = [x for x in recs if C.parse_iso(x["issue_utc"]) > T]
        for F in r.get("fires", []):
            if "area" not in F:
                sc["fires"].append({"fire": F["id"], "not_scored": "no known area in the record"})
                continue
            rep = C.parse_iso(F["report_utc"])
            own = log / "inputs" / C.stamp(T)
            firms_all = []
            if (own / "manifest.json").exists():
                _, firms_all = area.firms_rows(own, json.loads((own / "manifest.json").read_text()))
            cells = area.persistent_cells(firms_all, rep)
            s = score_fire(F, dets, T, cells, places)
            spread = s.pop("_spread8", [])
            early = []
            for rid in F.get("zone", {}).get("regions_reached", []):
                for v in r.get("regions", {}).get(rid, {}).get("affected", []):
                    e = places.get(v["place_id"]) or {}
                    if e.get("lat") is None or v.get("fire_arrival_s") is None:
                        continue
                    ex, ey = area.to5179(e["lon"], e["lat"])
                    due = T + timedelta(seconds=v["fire_arrival_s"])
                    for m in spread:
                        if m["t"] < due and math.hypot(m["x"] - ex, m["y"] - ey) <= m["r_m"]:
                            early.append({"place_id": v["place_id"], "name": v["name_ko"], "predicted_arrival_utc": C.iso(due),
                                          "reached_utc": C.iso(m["t"]), "by": m["src"]})
                            break
            s["villages_reached_early"] = early
            out_kfs = None
            for x in later:
                L = {y["id"]: y for y in x.get("listed", [])}
                if x.get("kfs_ok") and (F["id"] not in L or str(L[F["id"]].get("status_code")) != "02"):
                    out_kfs = {"first_record_utc": x["issue_utc"], "status": (L.get(F["id"]) or {}).get("status") or "no longer listed"}
                    break
            s["kfs_outcome"] = out_kfs
            sc["fires"].append(s)
        C.dump(out, sc)
        done += 1
    print("scored %d record(s)" % done)


if __name__ == "__main__":
    main()
