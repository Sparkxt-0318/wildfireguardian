"""Headline numbers (PROTOCOL.md §3, §4) for families R and M -> numbers.json, per_unit.csv.gz.

Model output on reconstructed inputs. Not what happened to people.

Usage: python3 aggregate.py R_ROWS.json M_ROWS.json OUT_DIR
"""
from __future__ import annotations

import csv, gzip, json, statistics, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

LABEL = "Model output on reconstructed inputs. Not what happened to people."
KST = timezone(timedelta(hours=9))
THRESH_MIN = (0, 5, 15, 30, 60)
H_S = {"5h": 18000, "8h": 28800}


def q(v, p):
    return float(np.percentile(v, p)) if v else None


def m(s):
    return None if s is None else round(s / 60, 1)


def normalise(rows):
    """Common fields: T (issue), tv (T_village seconds after T or None), state, gap_s, lb_s, binding."""
    for x in rows:
        T = datetime.fromisoformat(x["issue_utc"])
        x["_T"] = T
        if x["family"] == "M":
            tv = datetime.fromisoformat(x["T_village_utc"]) if x["T_village_utc"] else None
            x["_tv_raw"] = (tv - T).total_seconds() if tv else None          # not censored (raster value)
            x["_tv"] = x["_tv_raw"] if (tv and x["T_village_state"] == "within_H") else None
            x["_troad"] = (datetime.fromisoformat(x["T_road_utc"]) - T).total_seconds() if x["T_road_utc"] else None
            st = x["_tv_raw"]
            x["_step"] = ("LEAVE_NOW" if x["state"] == "INSIDE" or (st is not None and st <= 5 * 3600) else
                          "PREPARE_VULNERABLE_FIRST" if st is not None and st <= 8 * 3600 else "NONE")
        else:
            x["_tv"] = x["T_village_s"]
            x["_troad"] = x["T_road_s"]
            x["_step"] = x["government_step_run"]       # == step_from_T_village on 8 h runs (checked)
    return rows


def summarise(rows):
    out = {}
    groups = defaultdict(list)
    for x in rows:
        groups[(x["family"], x["arm"], x["horizon"])].append(x)
    for (fam, arm, hz), xs in sorted(groups.items()):
        H = H_S[hz]
        st = Counter(x["state"] for x in xs)
        bd = Counter(x["binding"] for x in xs if x["state"] == "CUT") if fam == "R" else None
        exact = [x["gap_s"] for x in xs if x["gap_s"] is not None]
        lbs = [x["gap_lower_bound_s"] for x in xs if x["gap_lower_bound_s"] is not None]
        # count A (§2.4)
        if fam == "R":
            A = [x for x in xs if (x["state"] == "CUT" and x["binding"] == "ROAD_CELL") or x["state"] == "NO_WINDOW"]
            A_sh = [x for x in xs if x["state"] == "CUT" and x["binding"] == "SHELTER_CELL"]
        else:
            A, A_sh = [], []
        A5 = [x for x in xs if (x["gap_s"] is not None and x["gap_s"] >= 300) or
              (x["gap_lower_bound_s"] is not None and x["gap_lower_bound_s"] >= 300) or x["state"] == "NO_WINDOW"]
        thr = {}
        for t in THRESH_MIN:
            e = [g for g in exact if (g > 0 if t == 0 else g >= t * 60)]
            b = [g for g in lbs if (g > 0 if t == 0 else g >= t * 60)]
            thr[f">{t}" if t == 0 else f">={t}"] = {"exact": len(e), "exact_or_bound": len(e) + len(b)}
        holes = [x for x in xs if x["n_windows"] > 1]
        hl = [h for x in holes for h in x.get("holes_s", [])]
        # government reading (§4): P5 / P8
        def p5(x):
            return x["_step"] in ("PREPARE_VULNERABLE_FIRST", "NONE") and (
                (x["state"] == "CUT" and x["_troad"] is not None and x["_troad"] <= 5 * 3600) or x["state"] == "NO_WINDOW")

        def p8(x):
            return x["_step"] == "NONE" and ((x["state"] == "CUT" and x["_troad"] is not None and x["_troad"] <= 8 * 3600)
                                            or x["state"] == "NO_WINDOW")
        P5 = [x for x in xs if p5(x)]
        P8 = [x for x in xs if p8(x)] if hz == "8h" else []
        per_place = defaultdict(list)
        for x in xs:
            if x["gap_s"] is not None:
                per_place[x["place_id"]].append(x["gap_s"])
        out[f"{fam}/{arm}/{hz}"] = {
            "units": len(xs), "places": len({x["place_id"] for x in xs}),
            "states": dict(st), "binding_of_CUT": dict(bd) if bd is not None else "no witness routes in M",
            "count_A_road_cut_before_village": None if fam == "M" else {
                "place_hours": len(A), "of_which_NO_WINDOW": sum(x["state"] == "NO_WINDOW" for x in A),
                "places": len({x["place_id"] for x in A})},
            "count_A_shelter_cut_before_village_separate": None if fam == "M" else {
                "place_hours": len(A_sh), "places": len({x["place_id"] for x in A_sh})},
            "count_gap_ge_5min_or_NO_WINDOW": {"place_hours": len(A5), "places": len({x["place_id"] for x in A5})},
            "exact_gap_min": {"n": len(exact), "median": m(statistics.median(exact)) if exact else None,
                              "p10": m(q(exact, 10)), "p90": m(q(exact, 90)), "max": m(max(exact)) if exact else None,
                              "min": m(min(exact)) if exact else None,
                              "places_with_exact_gap": len(per_place)},
            "lower_bounds_min": {"n": len(lbs), "largest": m(max(lbs)) if lbs else None},
            "gap_thresholds_place_hours": thr,
            "holes": {"place_hours_with_holes": len(holes), "holes": len(hl),
                      "median_hole_min": m(statistics.median(hl)) if hl else None, "max_hole_min": m(max(hl)) if hl else None},
            "government_reading": {
                "P5_place_hours": len(P5), "P5_places": len({x["place_id"] for x in P5}),
                "P5_by_step": dict(Counter(x["_step"] for x in P5)),
                "P5_of_which_NO_WINDOW": sum(x["state"] == "NO_WINDOW" for x in P5),
                "P8_place_hours": len(P8) if hz == "8h" else "8 h runs only",
                "P8_places": len({x["place_id"] for x in P8}) if hz == "8h" else None,
                "P8_of_which_NO_WINDOW": sum(x["state"] == "NO_WINDOW" for x in P8) if hz == "8h" else None,
                "steps": dict(Counter(x["_step"] for x in xs)),
            },
        }
    return out


def place_level(rows, fam, arm, hz):
    by = defaultdict(list)
    for x in rows:
        if x["family"] == fam and x["arm"] == arm and x["horizon"] == hz:
            by[x["place_id"]].append(x)
    out = {}
    for p, xs in by.items():
        xs.sort(key=lambda x: x["_T"])
        g = [x["gap_s"] for x in xs if x["gap_s"] is not None]
        first = next((x for x in xs if x["state"] == "CUT"), None)
        out[p] = {"name": xs[0]["name"], "sigungu": xs[0]["sigungu"], "region": xs[0]["region"],
                  "n_exact": len(g), "min": m(min(g)) if g else None, "median": m(statistics.median(g)) if g else None,
                  "max": m(max(g)) if g else None,
                  "first_cut_issue_kst": first["_T"].astimezone(KST).strftime("%H:%M") if first else None,
                  "gap_at_first_cut_min": m(first["gap_s"]) if first and first["gap_s"] is not None else None,
                  "gap_lb_at_first_cut_min": m(first["gap_lower_bound_s"]) if first and first["gap_lower_bound_s"] is not None else None,
                  "binding_at_first_cut": first.get("binding") if first else None,
                  "states": dict(Counter(x["state"] for x in xs))}
    return out


def write_units(rows, path):
    cols = ["family", "region", "place_id", "name", "sigungu", "category", "vulnerable", "issue_kst", "arm", "horizon",
            "state", "government_step", "T_village_kst", "T_road_kst", "gap_min", "gap_lower_bound_min", "binding",
            "binding_slack_s", "n_windows", "hole_min", "windows_kst", "windows_by_shelter_s"]
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([f"# {LABEL} MEASURED_GUST (ERA5) is PROVISIONAL; the gust arms' >=20 m/s class rests on 9 fires."])
        w.writerow(cols)
        for x in rows:
            T = x["_T"]
            k = lambda s: (T + timedelta(seconds=s)).astimezone(KST).strftime("%m-%d %H:%M:%S") if s is not None else ""
            wins = ";".join(f"{k(a)}..{k(b)}" for a, b in x["windows_s"]) if x["windows_s"] and x["windows_s"][0][1] is not None else ""
            w.writerow([x["family"], x["region"], x["place_id"], x["name"], x["sigungu"], x["category"], x["vulnerable"],
                        T.astimezone(KST).strftime("%m-%d %H:%M"), x["arm"], x["horizon"], x["state"], x["_step"],
                        k(x["_tv"]) if x["_tv"] is not None else ("inside" if x["state"] == "INSIDE" else f"> T+{x['horizon']}"),
                        k(x["_troad"]) if x["_troad"] is not None else "",
                        m(x["gap_s"]) if x["gap_s"] is not None else "",
                        m(x["gap_lower_bound_s"]) if x["gap_lower_bound_s"] is not None else "",
                        x.get("binding") or "", x.get("binding_slack_s") if x.get("binding_slack_s") is not None else "",
                        x["n_windows"], m(x.get("hole_s") or 0), wins,
                        json.dumps(x.get("windows_by_shelter_s")) if x.get("windows_by_shelter_s") else ""])


def main(r_rows, m_rows, outdir):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    R = normalise(json.loads(Path(r_rows).read_text())["rows"])
    M = normalise(json.loads(Path(m_rows).read_text())["rows"])
    step_mismatch = sum(1 for x in R if x["horizon"] == "8h" and x["government_step_run"] != x["step_from_T_village"])
    m_conflict = sum(1 for x in M if x["state"] == "INSIDE" and x["split_class"] == "route")
    s = summarise(R + M)
    numbers = {"label": LABEL, "protocol": "research/kcf-roadcut/PROTOCOL.md (frozen e8947dc; amendments 1-2)",
               "primary": "R/MEASURED/8h", "configs": s,
               "checks": {"R_8h_step_from_T_village_vs_committed_step_mismatches": step_mismatch,
                          "M_rows_INSIDE_by_arrival_raster_but_route_in_run": m_conflict},
               "place_level_primary": place_level(R, "R", "MEASURED", "8h"),
               "place_level_M_kriged_mean_8h": place_level(M, "M", "kriged_mean", "8h"),
               "notes": ["MEASURED_GUST (ERA5) is PROVISIONAL", "gust arms' >=20 m/s class rests on 9 fires",
                         "exact gaps only in medians and maxima; bounds counted separately"]}
    (out / "numbers.json").write_text(json.dumps(numbers, ensure_ascii=False, indent=1))
    write_units(R + M, out / "per_unit.csv.gz")
    p = s.get("R/MEASURED/8h") or next(iter(s.values()))
    print(json.dumps({k: p[k] for k in ("states", "binding_of_CUT", "count_A_road_cut_before_village", "exact_gap_min",
                                         "holes", "government_reading")}, indent=1), step_mismatch, m_conflict)


if __name__ == "__main__":
    main(*sys.argv[1:4])
