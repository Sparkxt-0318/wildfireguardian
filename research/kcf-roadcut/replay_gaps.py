"""Family R (PROTOCOL.md §1.1, §2): gap = T_village - T_road on the rerun kcf-replay field outputs.

Per place-hour: merged window set over the 3 shelters, holes, T_road, T_village (= closure second of the place's own
entry cell, i.e. close_s of that cell: the arm's own curve, ceil to the second, absent if beyond H), state, gap or bound,
and the binding cell of the witness route at T_road (§2.4).

Usage: python3 replay_gaps.py RUNS_DIR OUT.json
"""
from __future__ import annotations

import json, sys
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
H_S = {"5h": 18000, "8h": 28800}
DWELL = 120
SLACK_MAX = 60


def merge(sets):
    iv = sorted((int(a), int(b)) for s in sets for a, b in s)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


class G:
    def __init__(self, region):
        raw = json.loads((ROOT / f"data/routing/graphs/{region}/graph.json").read_text())
        g = raw["grid"]
        self.x0, self.y0, self.res, self.W = g["x0"], g["y0"], g["resolution"], g["width"]
        self.xy = {n["id"]: (n["x"], n["y"]) for n in raw["nodes"]}
        self.edges = {e["id"]: e for e in raw["edges"]}
        self.places = {}
        for f in json.loads((ROOT / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"]:
            self.places[f["properties"]["id"]] = f["properties"]

    def cell(self, node):
        x, y = self.xy[node]
        return int((y - self.y0) // self.res) * self.W + int((x - self.x0) // self.res)


def binding(g, route_edges, close_s, ld, shelter_cell, origin_cell):
    """Minimum-slack closure along the witness departing at ld (analyze.recheck walk)."""
    t = F(ld)
    best = None
    for eid in route_edges:
        e = g.edges[eid]
        D = e["travel_ticks"]
        for s in e["segments"]:
            b = close_s.get(str(s["cell"]))
            if b is not None:
                sl = F(b) - (t + D * F(str(s["end"])))
                if best is None or sl < best[0]:
                    best = (sl, int(s["cell"]), "seg")
        t += D
    b = close_s.get(str(shelter_cell))
    if b is not None:
        sl = F(b) - (t + DWELL)
        if best is None or sl < best[0]:
            best = (sl, shelter_cell, "dwell")
    if best is None:
        return "UNCLEAR", None, None
    sl, c, kind = best
    if sl > SLACK_MAX:
        cat = "UNCLEAR"
    elif kind == "dwell":
        cat = "SHELTER_CELL"
    elif c == origin_cell:
        cat = "ORIGIN_CELL"
    else:
        cat = "ROAD_CELL"
    return cat, c, float(sl)


def main(runs, out):
    gs = {r: G(r) for r in ("yeongdeok_2025", "uiseong_andong_2025")}
    rows = []
    for p in sorted(Path(runs).glob("*.json")):
        job = json.loads(p.read_text())
        region, arm, hz = job["region"], job["standin"], job["horizon"]
        g = gs[region]
        T = datetime.fromisoformat(job["issue_utc"])
        H = H_S[hz]
        cs = job["close_s"]
        for r in job["rows"]:
            pr = g.places[r["place_id"]]
            oc = g.cell(pr["entry"]["node"])
            win = merge(r["sets_by_shelter_node"].values())
            per_shelter = {k: merge([v]) for k, v in r["sets_by_shelter_node"].items()}
            holes = [win[i + 1][0] - win[i][1] - 1 for i in range(len(win) - 1)]
            tv_s = cs.get(str(oc))
            inside = r["dist_known_fire_m"] == 0.0
            ld = r.get("ld_s")
            row = {"family": "R", "region": region, "place_id": r["place_id"], "name": pr.get("name") or "",
                   "sigungu": (pr.get("sigungu") or {}).get("ko", ""), "category": pr["category"],
                   "vulnerable": bool(pr.get("vulnerable")), "issue_utc": T.isoformat(), "arm": arm, "horizon": hz,
                   "dist_km": None if r["dist_known_fire_m"] is None else r["dist_known_fire_m"] / 1000,
                   "government_step_run": r["step"], "windows_s": win, "n_windows": len(win),
                   "holes_s": holes, "hole_s": sum(holes), "windows_by_shelter_s": per_shelter,
                   "T_village_s": tv_s, "T_road_s": None, "state": None, "gap_s": None, "gap_lower_bound_s": None,
                   "binding": None, "binding_cell": None, "binding_slack_s": None, "origin_cell": oc,
                   "ld_s_run": ld, "shelter_id": r.get("shelter_id")}
            tv_in = tv_s is not None
            if inside:
                row["state"] = "INSIDE"
            elif ld is None:
                row["state"] = "NO_WINDOW"
                row["gap_lower_bound_s"] = tv_s if tv_in else H
            else:
                assert win and win[-1][1] == ld, (p.name, r["place_id"], win, ld)
                row["T_road_s"] = ld
                if r["cut_within_H"]:
                    row["state"] = "CUT"
                    if tv_in:
                        row["gap_s"] = tv_s - ld
                    else:
                        row["gap_lower_bound_s"] = H - ld
                    sh = g.places[r["shelter_id"]]
                    cat, c, sl = binding(g, r["route_edges"], cs, ld, g.cell(sh["entry"]["node"]), oc)
                    row.update(binding=cat, binding_cell=c, binding_slack_s=sl)
                else:
                    row["state"] = "NOT_CUT_WITHIN_H"
            # step from T_village (check against the run's step; 8 h runs only, PROTOCOL §4)
            if inside or (tv_in and tv_s <= 5 * 3600):
                st = "LEAVE_NOW"
            elif tv_in and tv_s <= 8 * 3600:
                st = "PREPARE_VULNERABLE_FIRST"
            else:
                st = "NONE"
            row["step_from_T_village"] = st
            rows.append(row)
    Path(out).write_text(json.dumps({"rows": rows}))
    print(len(rows), "rows")


if __name__ == "__main__":
    main(*sys.argv[1:3])
