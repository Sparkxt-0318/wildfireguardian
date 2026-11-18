"""Fill RESULTS.template.md with tables built from numbers.json, validation.json/csv and the R rows -> RESULTS.md.

Model output on reconstructed inputs. Not what happened to people.

Usage: python3 build_results.py R_ROWS.json
"""
from __future__ import annotations

import csv, json, statistics as st, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))
L = "*Model output on reconstructed inputs. Not what happened to people.*"
ARMS = ["MEASURED", "ORDINARY", "RUNNING", "WORST", "MEASURED_GUST_KMA", "MEASURED_GUST"]
ORDER = [f"R/{a}/{h}" for a in ARMS for h in ["8h", "5h"]] + \
        [f"M/{a}/{h}" for a in ["kriged_mean", "firms_early", "envelope"] for h in ["8h", "5h"]]


def f(x):
    return "–" if x is None else x


def nm(k):
    return k.replace("/", " / ") + (" †" if "/MEASURED_GUST/" in k else "")


def t1(C):
    o = [L, "", "| family / arm / horizon | place-hours (places) | INSIDE | NOT_CUT_WITHIN_H | CUT | NO_WINDOW | CUT ending on road / village / shelter | count A: place-hours (places) | gap ≥ 5 min or NO_WINDOW: place-hours (places) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k in ORDER:
        c = C[k]; s = c["states"]; b = c["binding_of_CUT"]; A = c["count_A_road_cut_before_village"]
        A5 = c["count_gap_ge_5min_or_NO_WINDOW"]
        bb = f'{b.get("ROAD_CELL", 0)} / {b.get("ORIGIN_CELL", 0)} / {b.get("SHELTER_CELL", 0)}' if isinstance(b, dict) else "no witness routes"
        aa = f'{A["place_hours"]} ({A["places"]})' if A else "–"
        o.append(f'| {nm(k)} | {c["units"]} ({c["places"]}) | {s.get("INSIDE", 0)} | {s.get("NOT_CUT_WITHIN_H", 0)} | {s.get("CUT", 0)} | {s.get("NO_WINDOW", 0)} | {bb} | {aa} | {A5["place_hours"]} ({A5["places"]}) |')
    return "\n".join(o)


def t2(C):
    o = [L, "", "| family / arm / horizon | exact gaps n (places) | median | p10 | p90 | max | lower bounds n | largest lower bound | > 0 | ≥ 5 | ≥ 15 | ≥ 30 | ≥ 60 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in ORDER:
        c = C[k]; e = c["exact_gap_min"]; lb = c["lower_bounds_min"]; t = c["gap_thresholds_place_hours"]
        tt = " | ".join(f'{t[x]["exact"]} / {t[x]["exact_or_bound"]}' for x in [">0", ">=5", ">=15", ">=30", ">=60"])
        o.append(f'| {nm(k)} | {e["n"]} ({e["places_with_exact_gap"]}) | {f(e["median"])} | {f(e["p10"])} | {f(e["p90"])} | {f(e["max"])} | {lb["n"]} | {f(lb["largest"])} | {tt} |')
    o.append("\nThreshold columns: place-hours with an exact gap at or above the threshold / the same plus lower bounds at or "
             "above it (a lower bound at or above a threshold means the true gap is too).")
    return "\n".join(o)


def t3(C):
    o = [L, "", "| family / arm / horizon | P5 place-hours (places) | P5 by step | P5 of which NO_WINDOW | P8 place-hours (places) | P8 of which NO_WINDOW | all steps LEAVE_NOW / PREPARE / NONE |",
         "|---|---|---|---|---|---|---|"]
    for k in ORDER:
        g = C[k]["government_reading"]; s = g["steps"]
        p8 = f'{g["P8_place_hours"]} ({g["P8_places"]})' if k.endswith("8h") else "8 h runs only"
        by = ", ".join(f'{a.replace("_VULNERABLE_FIRST", "")} {b}' for a, b in sorted(g["P5_by_step"].items())) or "–"
        o.append(f'| {nm(k)} | {g["P5_place_hours"]} ({g["P5_places"]}) | {by} | {g["P5_of_which_NO_WINDOW"]} | {p8} | {f(g["P8_of_which_NO_WINDOW"])} | {s.get("LEAVE_NOW", 0)} / {s.get("PREPARE_VULNERABLE_FIRST", 0)} / {s.get("NONE", 0)} |')
    return "\n".join(o)


def kst(x):
    return datetime.fromisoformat(x["issue_utc"]).astimezone(KST).strftime("%H:%M")


def tb(R):
    o = [L, "", "| arm / horizon | road cell: n, median, max | village's own cell: n, median, max | shelter: n, median, max |",
         "|---|---|---|---|"]
    for a in ARMS:
        for h in ["8h", "5h"]:
            xs = [x for x in R if x["arm"] == a and x["horizon"] == h and x["state"] == "CUT" and x["gap_s"] is not None]
            cells = []
            for b in ["ROAD_CELL", "ORIGIN_CELL", "SHELTER_CELL"]:
                g = [x["gap_s"] / 60 for x in xs if x["binding"] == b]
                cells.append(f"{len(g)}, {round(st.median(g), 1)}, {round(max(g), 1)}" if g else "0")
            o.append(f'| {a}{" †" if a == "MEASURED_GUST" else ""} / {h} | ' + " | ".join(cells) + " |")
    o.append("\nNo CUT place-hour had binding UNCLEAR (minimum slack > 60 s) in any configuration.")
    return "\n".join(o)


def tp(R):
    xs = [x for x in R if x["arm"] == "MEASURED" and x["horizon"] == "8h" and x["gap_s"] is not None]
    best = {}
    for x in xs:
        if x["place_id"] not in best or x["gap_s"] > best[x["place_id"]]["gap_s"]:
            best[x["place_id"]] = x
    top = sorted(best.values(), key=lambda x: -x["gap_s"])[:10]
    o = [L, "", "Ten places with the largest exact gap (R, MEASURED, 8 h), each at the issue hour of its largest gap:", "",
         "| place (시군) | issue (KST) | T_road − issue (min) | T_village − issue (min) | gap (min) | last window ends on | exact gaps at this place: n, median |",
         "|---|---|---|---|---|---|---|"]
    for x in top:
        g = [y["gap_s"] / 60 for y in xs if y["place_id"] == x["place_id"]]
        o.append(f'| {x["name"] or x["category"]} ({x["sigungu"]}) | {kst(x)} | {round(x["T_road_s"] / 60, 1)} | {round(x["T_village_s"] / 60, 1)} | {round(x["gap_s"] / 60, 1)} | {x["binding"]} | {len(g)}, {round(st.median(g), 1)} |')
    return "\n".join(o)


def tg(R):
    xs = [x for x in R if x["arm"] == "MEASURED" and x["horizon"] == "8h"]

    def p5(x):
        return x["government_step_run"] in ("PREPARE_VULNERABLE_FIRST", "NONE") and (
            (x["state"] == "CUT" and x["T_road_s"] <= 18000) or x["state"] == "NO_WINDOW")

    def p8(x):
        return x["government_step_run"] == "NONE" and ((x["state"] == "CUT" and x["T_road_s"] <= 28800) or x["state"] == "NO_WINDOW")
    o = [L, "", "| place (시군) | category | issue (KST) | step under the reading | T_road − issue (min) | T_village − issue (min) | last window ends on | in |",
         "|---|---|---|---|---|---|---|---|"]
    for x in sorted([x for x in xs if p5(x) or p8(x)], key=lambda x: (x["issue_utc"], x["name"])):
        tv = f'{round(x["T_village_s"] / 60)}' if x["T_village_s"] is not None else "> 480 (beyond 8 h)"
        o.append(f'| {x["name"] or "–"} ({x["sigungu"]}) | {x["category"]}{" (vulnerable)" if x["vulnerable"] else ""} | {kst(x)} | {x["government_step_run"].replace("_VULNERABLE_FIRST", "")} | {round(x["T_road_s"] / 60)} | {tv} | {x["binding"]} | {", ".join(n for n, fn in (("P5", p5), ("P8", p8)) if fn(x))} |')
    return "\n".join(o)


def v1(rows):
    o = [L + " Records are REPORTED (news; search-snippet text unless 'full page'). Error = model − recorded, minutes.", "",
         "| id | record | recorded (KST, 2025) | source (access; retrieved UTC) | issue used (KST) | where on the model graph | MEASURED | RUNNING | ORDINARY | WORST | GUST_KMA | GUST † | hotspot reconstruction | Choi TOA (M input) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def cell(r, a):
        m, e = r[f"{a}_model_kst"], r[f"{a}_error_min_or_status"]
        if e.startswith("closed at issue"):
            rec = datetime.strptime(r["recorded_kst"], "%Y-%m-%d %H:%M")
            iss = datetime.strptime(r["recorded_kst"][:5] + r["issue_used_kst"], "%Y-%m-%d %H:%M")
            e = f"closed at issue: error ≤ {int((iss - rec).total_seconds() // 60):+d}"
        if m and e.lstrip("-").isdigit():
            e = f"{int(e):+d}"
        return (f"{m} ({e})" if m else e).replace("|", "/")
    for r in rows:
        if not r["id"].startswith(("RD", "VA")):
            continue
        src = r["source_outlet"].split(". ")[0].replace("|", "/")
        url = r["source_url"].split(" ")[0]
        acc = "full page" if "full page" in r["source_access"] else "snippet"
        rc = f'{r["reconstruction_kst"]} ({r["reconstruction_error_min"]})' if r["reconstruction_kst"] else "–"
        tc = f'{r["choi_toa_kst"]} ({r["choi_toa_error_min"]})' if r["choi_toa_kst"] else "–"
        o.append(f'| {r["id"]} | {r["what"]} | {r["recorded_kst"][5:]} | {src} {"<" + url + ">" if url.startswith("http") else ""} ({acc}; {r["retrieved"][:16]}) | {r["issue_used_kst"] or "–"} | {r["location / n places"]} | '
                 + " | ".join(cell(r, a) for a in ["MEASURED", "RUNNING", "ORDINARY", "WORST", "MEASURED_GUST_KMA", "MEASURED_GUST"]) + f" | {rc} | {tc} |")
    return "\n".join(o)


def v2(v, rows):
    o = [L + " Records are REPORTED.", "",
         "| id | order | recorded (KST, 2025) | source (access) | issue used | places | MEASURED: steps; states; median T_road; order − median T_road (min) | RUNNING: same |",
         "|---|---|---|---|---|---|---|---|"]
    for e in v["evacuation"]:
        r = next(x for x in rows if x["id"] == e["id"])

        def s(a):
            d = e[a]
            t = lambda dd: ", ".join(f"{k.replace('_VULNERABLE_FIRST', '')} {n}" for k, n in dd.items()) or "–"
            return f'{t(d["steps"])}; {t(d["states"])}; {d["median_T_road_kst"] or "–"}; {f(d["order_minus_median_T_road_min"])}'
        acc = "full page" if "full page" in r["source_access"] else "snippet"
        what = e["what"].replace("['", "").replace("']", "").replace("', '", ", ")
        o.append(f'| {e["id"]} | {what} | {e["recorded_kst"][5:]} | {r["source_outlet"][:45]} <{r["source_url"].split(" ")[0]}> ({acc}) | {e.get("issue_kst", "")} | {e["n_places"]} | {s("MEASURED")} | {s("RUNNING")} |')
    return "\n".join(o)


def v3(v):
    o = [L, "", "| comparison | hit | miss | false alarm | correct negative | not assessable |", "|---|---|---|---|---|---|"]
    for grp in ["places", "cells"]:
        for k, d in v["burned_area"][grp].items():
            o.append(f'| {grp}: {k} | {d.get("hit", 0)} | {d.get("miss", 0)} | {d.get("false_alarm", 0)} | {d.get("correct_negative", 0)} | {d.get("not_assessable", 0)} |')
    o.append("\nhit = model reached & burned; miss = not reached & burned; false alarm = reached & not burned; correct "
             "negative = neither. Places: 174 entry cells. Cells: all cells of both grids.")
    return "\n".join(o)


def main(r_rows):
    C = json.loads((HERE / "numbers.json").read_text())["configs"]
    v = json.loads((HERE / "validation.json").read_text())
    raw = list(csv.reader(open(HERE / "validation_table.csv", encoding="utf-8")))[1:]
    rows = [dict(zip(raw[0], r)) for r in raw[1:]]
    R = json.loads(Path(r_rows).read_text())["rows"]
    s = (HERE / "RESULTS.template.md").read_text()
    for key, val in {"T1": t1(C), "T2": t2(C), "T3": t3(C), "TB": tb(R), "TP": tp(R), "TG": tg(R),
                     "V1": v1(rows), "V2": v2(v, rows), "V3": v3(v)}.items():
        assert "{{" + key + "}}" in s, key
        s = s.replace("{{" + key + "}}", val)
    assert "{{" not in s
    (HERE / "RESULTS.md").write_text(s)
    print("RESULTS.md", len(s))


if __name__ == "__main__":
    main(sys.argv[1])
