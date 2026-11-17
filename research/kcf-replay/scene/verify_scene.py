"""Independent check of planner/public/kcf-scene/data/scene.js (window.KCF.scene, schema kcf-scene/1).

Reads ONLY scene.js and the committed files it compares against (per_place.csv, fire_discs.json, the planner cache,
score.json, named_places_timeline.csv, SOURCES.md, RESULTS.md). Does not import build_scene.py. The witness re-walk is
analyze.py's own `recheck` fed with scene data only (edge D, seg [cell, end], close via roadCells, sh_cell, dwell_s,
horizon_s). Writes research/kcf-replay/scene/VERIFY.json; exits non-zero on any mismatch.

Usage (from the repository root): python3 research/kcf-replay/scene/verify_scene.py [--scene PATH]
"""
from __future__ import annotations

import argparse, csv, hashlib, io, json, re, subprocess, sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pyproj import Transformer

HERE = Path(__file__).resolve().parent
KCF = HERE.parent
ROOT = KCF.parents[1]
sys.path.insert(0, str(KCF))
from analyze import recheck  # noqa: E402  (the committed witness re-check rule)

KST = timezone(timedelta(hours=9))
PREFIX = "(window.KCF=window.KCF||{}).scene="
TOP_KEYS = {"schema", "built", "t0_utc", "issues_s", "issue_kst", "issue_utc", "horizon", "horizon_s", "dwell_s", "standins",
            "default_standin", "regions", "places", "named", "shelters", "hourly", "routes", "routeEdges", "roadCells",
            "close", "discs", "discCounts", "planner", "reported", "countyLog", "score", "src"}
HOURLY_FIELDS = {"step": "government_step", "state": "departure_state", "lsd": "latest_safe_departure_kst",
                 "last": "last_departure_in_horizon_kst", "shelter": "shelter_id", "arr": "arrival_kst",
                 "d_km": "dist_known_fire_km", "cut_before": "route_cut_before_departure",
                 "first_cut": "route_first_cut_by_reconstruction_kst", "pieces": "departure_set_pieces"}
NAMED = ["화매리", "지품리", "옥류리", "매정리", "노물리", "강구리"]


class Check:
    def __init__(self):
        self.counts = Counter()
        self.fail = []

    def eq(self, name, got, want, ctx=""):
        if got == want:
            self.counts[name] += 1
        else:
            self.counts[name + ":FAIL"] += 1
            if len(self.fail) < 50:
                self.fail.append(f"{name} {ctx}: got {str(got)[:200]!r} want {str(want)[:200]!r}")

    def true(self, name, cond, ctx=""):
        self.eq(name, bool(cond), True, ctx)


def kst(dt):
    return dt.astimezone(KST).strftime("%m-%d %H:%M")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scene", default=str(ROOT / "planner/public/kcf-scene/data/scene.js"))
    ap.add_argument("--out", default=str(HERE / "VERIFY.json"))
    a = ap.parse_args()
    C = Check()
    inputs = {}

    def read(p):
        b = Path(p).read_bytes()
        q = Path(p).resolve()
        inputs[q.relative_to(ROOT).as_posix() if q.is_relative_to(ROOT) else str(q)] = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        return b

    # ---------------------------------------------------------------- (5) file format, JSON payload, JS evaluation
    scene_path = Path(a.scene).resolve()
    raw = read(scene_path)
    text = raw.decode("ascii")
    lines = text.split("\n")
    C.eq("format:lines", (len(lines), lines[-1]), (3, ""))
    C.true("format:header", lines[0].startswith("//") and "research/kcf-replay/scene/build_scene.py" in lines[0])
    C.true("format:assignment", lines[1].startswith(PREFIX) and lines[1].endswith(";"))
    S = json.loads(lines[1][len(PREFIX):-1])
    C.eq("format:json_payload", type(S).__name__, "dict")
    js = ("const fs=require('fs'),vm=require('vm');const ctx={window:{}};"
          "vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),ctx,{filename:'scene.js'});"
          "process.stdout.write(JSON.stringify(ctx.window.KCF.scene));")
    r = subprocess.run(["node", "-e", js, str(scene_path)], capture_output=True, text=True)
    C.eq("format:js_eval_exit", r.returncode, 0, r.stderr[:300])
    C.true("format:js_equals_json", r.returncode == 0 and json.loads(r.stdout) == S)
    C.eq("schema", S.get("schema"), "kcf-scene/1")
    C.eq("top_keys_missing", sorted(TOP_KEYS - set(S)), [])

    # ---------------------------------------------------------------- time axis
    t0 = datetime.fromisoformat(S["t0_utc"].replace("Z", "+00:00"))
    C.eq("time:t0", S["t0_utc"], "2025-03-25T03:00:00Z")
    C.eq("time:issues_s", S["issues_s"], [3600 * k for k in range(13)])
    C.eq("time:issue_kst", S["issue_kst"], [f"{12 + k:02d}:00" for k in range(13)])
    C.eq("time:issue_utc", S["issue_utc"], [(t0 + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M:%SZ") for k in range(13)])
    C.eq("time:horizon", (S["horizon"], S["horizon_s"], S["dwell_s"]), ("8h", 28800, 120))
    issues = [t0 + timedelta(seconds=s) for s in S["issues_s"]]
    issue_kst_csv = [kst(T) for T in issues]
    H, DW = S["horizon_s"], S["dwell_s"]

    # ---------------------------------------------------------------- places, named
    ids = [p["id"] for p in S["places"]]
    C.eq("places:count", len(ids), 174)
    C.eq("places:sorted_unique", ids, sorted(set(ids)))
    region_of = {p["id"]: p["region"] for p in S["places"]}
    C.eq("named:names", [n["name"] for n in S["named"]], NAMED)
    C.eq("named:order", [n["order"] for n in S["named"]], list(range(1, 7)))
    C.eq("named:flags", sorted(p["id"] for p in S["places"] if p["named"]), sorted(n["id"] for n in S["named"]))

    # ---------------------------------------------------------------- (2) hourly == per_place.csv
    pp = list(csv.DictReader(io.StringIO(read(KCF / "per_place.csv").decode("utf-8"), newline="")))
    seen = Counter()
    for st, by_place in S["hourly"].items():
        C.eq("hourly:places", sorted(by_place), ids, st)
        for pid, lst in by_place.items():
            C.eq("hourly:len13", len(lst), 13, pid)
            for k, e in enumerate(lst):
                row = pp[e["row"] - 1]
                C.eq("hourly:row_key", (row["standin"], row["horizon"], row["place_id"], row["issue_kst"], row["region"]),
                     (st, "8h", pid, issue_kst_csv[k], region_of[pid]), f"{st} {pid} {k}")
                for f, col in HOURLY_FIELDS.items():
                    C.eq("hourly:field", e[f], row[col], f"{st} {pid} {k} {f}")
                seen[e["row"]] += 1
    rows8 = {n for n, r in enumerate(pp, 1) if r["horizon"] == "8h"}
    C.eq("hourly:covers_all_8h_rows_once", (set(seen) == rows8, max(seen.values())), (True, 1))
    C.counts["hourly:entries"] = sum(seen.values())

    # ---------------------------------------------------------------- road cells, edges
    pos = {}
    for region, rc in S["roadCells"].items():
        cells = rc["cells"]
        C.eq("roadCells:sorted_unique", cells, sorted(set(cells)), region)
        C.eq("roadCells:rings", len(rc["ring"]), len(cells), region)
        C.true("roadCells:ring_closed", all(len(g) == 5 and g[0] == g[4] for g in rc["ring"]), region)
        pos[region] = {c: i for i, c in enumerate(cells)}
        for e in S["routeEdges"][region]:
            C.true("routeEdges:seg_cells_in_roadCells", all(c in pos[region] for c, _ in e["seg"]), e["id"])
    for st, by_region in S["close"].items():
        for region, ks in by_region.items():
            C.eq("close:shape", [len(x) for x in ks], [len(S["roadCells"][region]["cells"])] * 13, f"{st} {region}")
            C.true("close:range", all(isinstance(v, int) and -1 <= v <= H for x in ks for v in x), f"{st} {region}")
    # same distance, faster stand-in closes no later: WORST <= RUNNING <= ORDINARY wherever the slower one closes
    for fast, slow in (("WORST", "RUNNING"), ("RUNNING", "ORDINARY")):
        for region in S["roadCells"]:
            for k in range(13):
                f, s = S["close"][fast][region][k], S["close"][slow][region][k]
                C.true("close:standin_order", all(b == -1 or (a != -1 and a <= b) for a, b in zip(f, s)), f"{fast}<{slow} {region} {k}")

    # ---------------------------------------------------------------- (1) witness re-walk with analyze.recheck
    walk = Counter()
    for st, by_place in S["routes"].items():
        C.eq("routes:runs_complete", S["built"]["runs"].get(st), "complete", st)
        for pid, lst in by_place.items():
            region = region_of[pid]
            E = S["routeEdges"][region]
            cells = S["roadCells"][region]["cells"]
            for k, w in enumerate(lst):
                h = S["hourly"][st][pid][k]
                has = h["state"] in ("LATEST_SAFE_DEPARTURE", "NOT_CUT_WITHIN_H")
                C.eq("routes:present_iff_departure", w is not None, has, f"{st} {pid} {k}")
                if w is None:
                    continue
                cl = S["close"][st][region][k]
                close_s = {str(c): b for c, b in zip(cells, cl) if b != -1}   # analyze.recheck looks cells up by str
                C.true("routes:sh_cell_in_roadCells", w["sh_cell"] in pos[region], f"{st} {pid} {k}")
                edges = {i: {"travel_ticks": E[i]["D"], "segments": [{"cell": c, "end": z} for c, z in E[i]["seg"]]}
                         for i in w["e"]}
                ok, arr = recheck(w["e"], edges, close_s, w["ld"], w["arr"], w["sh_cell"], H)
                C.eq("walk:pass_and_arrival", (ok, arr), (True, w["arr"]), f"{st} {pid} {k}")
                walk[f"{st}:PASS" if ok and arr == w["arr"] else f"{st}:FAIL"] += 1
                ok60, _ = recheck(w["e"], edges, close_s, w["ld"] + 60, None, w["sh_cell"], H)
                walk[f"{st}:ld+60:{'PASS' if ok60 else 'FAIL'}"] += 1
                T = issues[k]
                C.eq("routes:last_text", kst(T + timedelta(seconds=w["ld"])), h["last"], f"{st} {pid} {k}")
                C.eq("routes:arr_text", kst(T + timedelta(seconds=w["arr"])), h["arr"], f"{st} {pid} {k}")
                C.eq("routes:shelter", w["sh"], h["shelter"], f"{st} {pid} {k}")
                C.true("routes:chain", all(E[i]["c"][1] == E[j]["c"][0] for i, j in zip(w["e"], w["e"][1:])), f"{st} {pid} {k}")
                C.true("routes:shelter_known", w["sh"] in S["shelters"], w["sh"])
    for st, v in S["built"]["runs"].items():
        if v == "complete":
            C.true("routes:included_when_complete", st in S["routes"], st)

    # ---------------------------------------------------------------- (3) discs, discCounts
    fd = json.loads(read(KCF / "fire_discs.json"))["discs"]
    tr = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    fresh = []
    for d in fd:
        t = datetime.fromisoformat(d["t_utc"])
        lon, lat = tr.transform(d["x"], d["y"])
        fresh.append([int((t - t0).total_seconds()), round(lon, 6), round(lat, 6), d["r_m"], d["src"]])
    fresh.sort(key=lambda r: (r[0], r[4], r[1], r[2]))
    C.eq("discs:fields", S["discs"]["fields"], ["s", "lon", "lat", "r_m", "src"])
    C.eq("discs:count", len(S["discs"]["rows"]), len(fd))
    for a_, b_ in zip(S["discs"]["rows"], fresh):
        C.eq("discs:row", a_, b_)
    for k, T in enumerate(issues):
        before = [d for d in fd if datetime.fromisoformat(d["t_utc"]) < T]
        want = {"total": len(before), "AHI": sum(d["src"] == "AHI" for d in before),
                "FIRMS": sum(d["src"].startswith("FIRMS-") for d in before)}
        C.eq("discCounts", S["discCounts"][k], want, str(k))
        C.eq("discCounts:from_scene_rows", sum(r[0] < 3600 * k for r in S["discs"]["rows"]), want["total"], str(k))

    # ---------------------------------------------------------------- (4) planner strips == cache
    cache = {}
    for pid, lst in S["planner"].items():
        C.eq("planner:len13", len(lst), 13, pid)
        for k, e in enumerate(lst):
            if e["file"] not in cache:
                cache[e["file"]] = json.loads(read(ROOT / e["file"]))
            doc = cache[e["file"]]
            C.eq("planner:file_issue", (doc["region_id"], doc["input_time"]), (region_of[pid], S["issue_utc"][k]), f"{pid} {k}")
            (job,) = [j for j in doc["plans"] if j["result"]["plans"][0]["origin_id"] == pid]
            plan, req = job["result"]["plans"][0], job["request"]
            offs = req["depart_offsets_s"]
            C.eq("planner:offsets", offs, list(range(0, len(offs) * e["offsets_step_s"], e["offsets_step_s"])), f"{pid} {k}")
            v = {(x["destination_id"], x["depart_offset_s"]): x["verdict"] for x in plan["attempts"]}
            want = [[d["id"], "".join("1" if v[(d["id"], o)] == "checked_route" else "0" for o in offs)] for d in req["destinations"]]
            C.eq("planner:strips", e["shelters"], want, f"{pid} {k}")
            C.eq("planner:contiguous", e["contiguous_s"], plan["latest_contiguous_checked_depart_offset_s"], f"{pid} {k}")
            b = plan["best"]
            C.eq("planner:best", e["best"], None if b is None else
                 {"shelter": b["destination_id"], "off_s": b["depart_offset_s"], "arr_s": b["arrival_s"]}, f"{pid} {k}")
            for sid, _ in e["shelters"]:
                C.true("planner:shelter_known", sid in S["shelters"], sid)
    C.eq("planner:files", len(cache), 26)

    # ---------------------------------------------------------------- score, stand-ins
    C.eq("score", S["score"], json.loads(read(KCF / "score.json"))["score"])
    res = read(KCF / "RESULTS.md").decode("utf-8").split("\n")
    for st, v in S["standins"].items():
        (line,) = [l for l in res if l.startswith(f"| {st} |")]
        rh = line.split("|")[2].strip()
        m = re.fullmatch(r"(?:([\d.]+) km \+ )?([\d.]+) km/h × h", rh)
        C.eq("standins:a_v_vs_RESULTS", (v["a_m"], v["v_m_per_h"]),
             (round(float(m.group(1) or 0) * 1000), round(float(m.group(2)) * 1000)), st)
        C.eq("standins:basis_vs_RESULTS", v["basis"], line.split("|")[3].strip(), st)

    # ---------------------------------------------------------------- documented times
    src_lines = read(KCF / "SOURCES.md").decode("utf-8").split("\n")
    nt = list(csv.DictReader(io.StringIO(read(KCF / "named_places_timeline.csv").decode("utf-8"), newline="")))
    tbl = [i + 1 for i, l in enumerate(src_lines) if re.match(r"^\| \d\d:\d\d \| \"", l)]   # 뉴스로 county-log rows
    for n in S["named"]:
        rp = S["reported"][n["id"]]
        C.eq("reported:documented", {rp["documented"]}, {r["documented"] for r in nt if r["place"] == n["name"]}, n["name"])
        C.true("reported:rows", len(rp["rows"]) >= 1, n["name"])
        for r in rp["rows"]:
            src_line = src_lines[r["line"] - 1].replace("**", "")
            C.true("reported:line_has_kst_what", f"| {r['kst']} |" in src_line and r["what"] in src_line, f"{n['name']} {r['line']}")
            if r["line"] in tbl:   # county log row: URL on the table's "Source:" line
                url_line = S["countyLogSource"]["line"]
            else:                  # village row: its own Source cell, or the row above it while that cell says "same"
                url_line = r["line"]
                while src_lines[url_line - 1].split("|")[4].strip() == "same":
                    url_line -= 1
            C.true("reported:url_at_source", r["url"] and r["url"] in src_lines[url_line - 1], f"{n['name']} {r['line']}")
    C.eq("reported:places", sorted(S["reported"]), sorted(n["id"] for n in S["named"]))
    C.eq("countyLog:lines", [r["line"] for r in S["countyLog"]], tbl)
    for r in S["countyLog"]:
        C.true("countyLog:line_has_entry", src_lines[r["line"] - 1].replace("**", "").startswith(f"| {r['kst']} | {r['entry']} |"), str(r["line"]))
    C.true("countyLog:source_line", S["countyLogSource"]["text"] == src_lines[S["countyLogSource"]["line"] - 1])

    # ---------------------------------------------------------------- write VERIFY.json
    ok = not any(k.endswith(":FAIL") for k in C.counts)
    out = {"scene_js": scene_path.relative_to(ROOT).as_posix() if scene_path.is_relative_to(ROOT) else str(scene_path),
           "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
           "scene_built": {k: S["built"][k] for k in ("commit", "generated_utc", "runs", "script")},
           "ok": ok, "checks": dict(sorted(C.counts.items())), "witness_walk": dict(sorted(walk.items())),
           "failures": C.fail, "script": "research/kcf-replay/scene/verify_scene.py",
           "inputs": [{"path": k, **v} for k, v in sorted(inputs.items())]}
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("ok", "bytes", "sha256", "witness_walk", "failures")}, indent=1, ensure_ascii=False))
    print(json.dumps(out["checks"], indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
