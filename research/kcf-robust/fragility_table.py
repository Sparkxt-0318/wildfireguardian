"""Fragility table, 174 places x 13 issue hours of 25 March 2025 (PROTOCOL.md sections 4 and 6), produced with the
product's own optional code (product/wfg-roadlayer/wfg_roadlayer/fragility.py: forward search per closure level) and
compared with the research pass of replay.py (backward latest-departure pass over the whole grid).

    python3 fragility_table.py OUT
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib  # noqa: E402
from wfg_roadlayer import fmt, fragility, pipeline  # noqa: E402


def main(out):
    out = Path(out)
    discs = lib.load_discs()
    rows, agree = [], {"reach": 0, "timing": 0, "n": 0, "reach_road": 0, "timing_road": 0, "road_n_reach": 0, "road_n_timing": 0}
    for rid in lib.REGIONS:
        for T in lib.REPLAY_ISSUES:
            tag = "%s_%s" % (rid, T.strftime("%H"))
            d = lib.known_distance_m(discs, T)
            r5, r8, cls, _ = lib.MA.curve("MEASURED", discs, T, 8)
            p = Path("/tmp/claude-0/frag_%s.tif" % tag)
            lib.write_tif(p, lib.minutes_r90(d, r5, r8), T, "kcf-robust R90 replay")
            iso = T.strftime("%Y-%m-%dT%H:%M+00:00")
            c = pipeline.compute(region_name=rid, issue_time=iso, raster=str(p), as_of=iso, out="/tmp/claude-0/frag_unused",
                                 workers=4, log=lambda *a: None)
            fr = fragility.compute(c, str(p), lib.PRODUCT, log=lambda *a: None)
            res = json.loads((out / "replay" / (tag + ".json")).read_text())
            research = res["fragility"]
            for row in c["rows"]:
                o = row["origin"]
                base = {"region": rid, "issue_kst": fmt.full(fmt.kst(T)), "place_id": o["id"], "name": o["name"],
                        "county": o.get("sigungu", ""), "town": o.get("eupmyeon", "")}
                if row["refusal"]:
                    rows.append(dict(base, status="refused: " + row["refusal"][0]))
                    continue
                f = fr[o["id"]]
                cut = row["cut"]
                lb = "already cut" if cut == 0 else ("not cut within 8 h" if cut is None else fmt.full(fmt.t_floor(T, row["leave_by"])))
                rb, tb = f.get("reach_binding"), f.get("timing_binding")
                rows.append(dict(base, status="ok", leave_by_kst=lb,
                                 tolerated_reach_km=("" if f["reach_km"] is None else f["reach_km"]),
                                 reach_censored_ge15=f["reach_censored"],
                                 road_fails_first_reach=(rb["label"] if rb and not f["reach_censored"] else ""),
                                 road_fails_first_reach_way=(rb["way"] if rb and not f["reach_censored"] else ""),
                                 tolerated_timing_min=("" if f["timing_s"] is None else f["timing_s"] // 60),
                                 timing_censored_horizon=f["timing_censored"],
                                 road_fails_first_timing=(tb["label"] if tb and not f["timing_censored"] else ""),
                                 road_fails_first_timing_way=(tb["way"] if tb and not f["timing_censored"] else ""),
                                 method="product fragility.py (forward search, bisection); equals research backward pass: see fragility_check.json"))
                q = research.get(o["id"])
                agree["n"] += 1
                agree["reach"] += (q["R_tol_km"] == f["reach_km"])
                agree["timing"] += ((q["T_tol_s"] if q["T_tol_s"] >= 0 else None) == f["timing_s"])
                if rb and q["reach_binding"] and not f["reach_censored"]:
                    agree["road_n_reach"] += 1
                    agree["reach_road"] += (q["reach_binding"].get("way") == rb["way"])
                if tb and q["timing_binding"] and not f["timing_censored"]:
                    agree["road_n_timing"] += 1
                    agree["timing_road"] += (q["timing_binding"].get("way") == tb["way"])
            print(tag, agree, flush=True)
    cols = ["region", "issue_kst", "county", "town", "place_id", "name", "status", "leave_by_kst", "tolerated_reach_km",
            "reach_censored_ge15", "road_fails_first_reach", "road_fails_first_reach_way", "tolerated_timing_min",
            "timing_censored_horizon", "road_fails_first_timing", "road_fails_first_timing_way", "method"]
    with open(out / "fragility_174.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    (out / "fragility_check.json").write_text(json.dumps(agree, indent=1))
    print(agree)


if __name__ == "__main__":
    main(sys.argv[1])
