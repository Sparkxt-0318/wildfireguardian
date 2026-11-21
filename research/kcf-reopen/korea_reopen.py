"""Step 5 (PROTOCOL §6): when traffic returned on each closed expressway section vs when the model would reopen it.
Usage: python3 -I korea_reopen.py OSM_EXPRESSWAYS.json OUT_DIR
  OSM_EXPRESSWAYS.json: Overpass, highway=motorway(_link) ways and motorway_junction nodes in 36.15-36.95 N,
  128.10-129.45 E (fetched 2026-11-21; SHA-256 in out/korea_reopen.json). Section geometry: mainline (highway=motorway)
  ways with ref 30 (서산영덕선 / 청주영덕선) or 55 (중앙선), shortest path between the mainline nodes nearest the two
  named junctions (name base: IC / JC / TG / 나들목 / 분기점 stripped), sampled every 50 m, cells of the KFS_01 375 m lattice.
  Fire arrival A per cell: earliest detection disc of research/kcf-replay/fire_discs.json covering the cell centre
  (primary); Choi reconstruction arrival_time_hours.tif (secondary). Traffic return per conzone-direction: the run of
  research/kcf-validate/out/vds/vds2_closure_runs.csv in effect at the official closure or starting within 6 h after it
  (onset <= official + 6 h, reopen > official), its reopen_kst (first 15-min slot back at >= 25 % of baseline)."""
import csv, hashlib, heapq, json, math, re, statistics as st, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "research/kcf-robust")); sys.path.insert(0, str(REPO / "research/kcf-replay"))
sys.path.insert(0, str(REPO / "product/wfg-roadlayer"))
import lib  # noqa: E402
import analyze as AN  # noqa: E402
from wfg_roadlayer import geotiff  # noqa: E402

OSM, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
KST = timezone(timedelta(hours=9)); UTC = timezone.utc
TO5179 = Transformer.from_crs(4326, 5179, always_xy=True)
TAU = json.load(open(HERE / "out/tau.json"))["frozen"]
TAUS = {"low": TAU["tau_low_min"], "frozen": TAU["tau_min"], "high": TAU["tau_high_min"]}
ROUTE_REF = {"서산영덕선": "30", "청주영덕선": "30", "중앙선": "55"}
VDS_ROUTE = {"30": "서산영덕선", "55": "중앙선"}
CHAIN = {"30": ["상주", "동상주", "서의성", "안동", "북의성", "동안동", "청송", "영양", "영덕"],
         "55": ["군위", "의성", "안동", "남안동", "서안동", "예천", "영주", "풍기"]}
ALIAS = {"영양": ["동청송영양"]}


def base(n):
    n = re.sub(r"\s+", "", n)
    return re.sub(r"(IC|JCT|JC|TG|Hi|나들목|분기점|요금소)$", "", n)


# ---------------------------------------------------------------- OSM mainline graphs
raw = OSM.read_bytes()
el = json.loads(raw)["elements"]
node = {e["id"]: TO5179.transform(e["lon"], e["lat"]) for e in el if e["type"] == "node"}
junc = {}
for e in el:
    if e["type"] == "node" and e.get("tags", {}).get("highway") == "motorway_junction" and e["tags"].get("name"):
        junc.setdefault(base(e["tags"]["name"]), []).append(node[e["id"]])
adj = {"30": {}, "55": {}}
for e in el:
    if e["type"] != "way" or e.get("tags", {}).get("highway") not in ("motorway", "motorway_link"):
        continue  # links join the two carriageways (each is its own component in OSM); they cost 5x like untagged pieces
    refs = set(e["tags"].get("ref", "").split(";"))
    for ref in adj:  # all motorway mainline; pieces without this ref cost 5x (OSM gaps in the ref tag), share reported
        on = ref in refs and e["tags"]["highway"] == "motorway"
        ns = e["nodes"]
        for a, b in zip(ns[:-1], ns[1:]):
            d = math.dist(node[a], node[b])
            adj[ref].setdefault(a, []).append((b, d, on)); adj[ref].setdefault(b, []).append((a, d, on))


def anchor(ref, name):
    """Mainline node of `ref` nearest any junction node whose name base is `name` (or an alias)."""
    pts = [p for nm in [name] + ALIAS.get(name, []) for p in junc.get(nm, [])]
    if not pts:
        return None, "junction '%s' not in OSM extract" % name
    ids = [i for i, nb in adj[ref].items() if any(o for _, _, o in nb)]; xy = np.array([node[i] for i in ids])
    best = None
    for p in pts:
        d = np.hypot(xy[:, 0] - p[0], xy[:, 1] - p[1]); k = int(np.argmin(d))
        if best is None or d[k] < best[1]:
            best = (ids[k], float(d[k]))
    return (best[0], "junction %s, mainline node %.0f m away" % (name, best[1])) if best[1] <= 2500 else (None, "junction %s %.0f m from route %s" % (name, best[1], ref))


def path(ref, a, b):
    dist, prev, h = {a: 0.0}, {}, [(0.0, a)]
    while h:
        d, v = heapq.heappop(h)
        if v == b:
            break
        if d > dist[v]:
            continue
        for w, l0, on in adj[ref].get(v, []):
            l = l0 if on else 5 * l0
            if d + l < dist.get(w, math.inf):
                dist[w] = d + l; prev[w] = v; heapq.heappush(h, (d + l, w))
    if b not in dist:
        return None
    out, v = [b], b
    while v != a:
        v = prev[v]; out.append(v)
    return out[::-1]


def samples(nodes, step=50.0):
    pts = []
    for a, b in zip(nodes[:-1], nodes[1:]):
        (x1, y1), (x2, y2) = node[a], node[b]
        n = max(1, int(math.dist(node[a], node[b]) // step))
        pts += [(x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n) for k in range(n)]
    return pts + [node[nodes[-1]]]


# ---------------------------------------------------------------- fire arrival
discs = json.loads((REPO / "research/kcf-replay/fire_discs.json").read_text())["discs"]
for d in discs:
    d["ts"] = datetime.fromisoformat(d["t_utc"]).timestamp()
cx, cy = lib.cell_centres()
A_disc = AN.first_cut_times(discs, cx, cy)
disc_end = max(d["ts"] for d in discs)
choi = []
for rid in ("uiseong_andong_2025", "yeongdeok_2025"):
    p = Path("/Users/jp/Desktop/wildfire/data/regions/%s/arrival_time_hours.tif" % rid)
    if p.is_file():
        g = geotiff.read(p)
        m = json.loads((p.parent / "metadata.json").read_text())
        choi.append((g, datetime.fromisoformat(m["t0_utc"].replace("Z", "+00:00")).timestamp(), rid))


def lattice_cell(x, y):
    c = int((x - lib.X0) // lib.RES); r = int((y - lib.Y0) // lib.RES)
    return r * lib.W + c if 0 <= c < lib.W and 0 <= r < lib.HH else None


def choi_at(x, y):
    for g, t0, rid in choi:
        a, b, c0, d, e, f = g.affine
        col = int(math.floor((x - c0) / a)); row = int(math.floor((y - f) / e))
        if 0 <= row < g.shape[0] and 0 <= col < g.shape[1]:
            v = float(g.data[row][col])
            if math.isfinite(v) and v >= 0:
                return t0 + v * 3600.0
    return None


def ts_kst(t):
    return datetime.fromtimestamp(t, KST).strftime("%m-%d %H:%M") if t is not None and math.isfinite(t) else ""


# ---------------------------------------------------------------- VDS runs
runs = {}
for r in csv.DictReader(open(REPO / "research/kcf-validate/out/vds/vds2_closure_runs.csv", encoding="utf-8-sig")):
    a, b = [base(x) for x in r["name"].split("-")]
    runs.setdefault((r["route"], r["conzone"], r["dir"], a, b), []).append(r)


def kst(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=KST)


def traffic_return(ref, A, B, off):
    ch = CHAIN[ref]
    if A not in ch or B not in ch:
        return [], "interchange not on the VDS chain"
    lo, hi = sorted((ch.index(A), ch.index(B)))
    out = []
    for (route, cz, dr, a, b), rs in runs.items():
        if route != VDS_ROUTE[ref] or a not in ch or b not in ch:
            continue
        i, j = sorted((ch.index(a), ch.index(b)))
        if i < lo or j > hi:
            continue
        cand = [r for r in rs if kst(r["onset_kst"]) <= off + timedelta(hours=6) and r["reopen_kst"] and kst(r["reopen_kst"]) > off]
        if cand:
            r = min(cand, key=lambda r: kst(r["onset_kst"]))
            out.append({"conzone": cz, "dir": dr, "name": "%s-%s" % (a, b), "onset": r["onset_kst"], "reopen": r["reopen_kst"]})
    return out, ""


# ---------------------------------------------------------------- sections
ev = list(csv.DictReader(open(REPO / "research/kcf-validate/out/kec_official_closure_events.csv", encoding="utf-8-sig")))
reopen_msgs = [e for e in ev if e["action"] == "reopen"]
rows, seen_geom = [], {}
for e in ev:
    if e["action"] != "closure":
        continue
    off = kst(e["effective_kst"])
    for s in e["sections_parsed"].split(" ; "):
        if not s.strip() or " " not in s:
            continue
        rt, ab = s.split(" ", 1)
        if rt not in ROUTE_REF or "~" not in ab:
            continue
        ref = ROUTE_REF[rt]; A, B = [base(x) for x in ab.split("~")]
        key = (ref, A, B)
        if key not in seen_geom:
            na, why_a = anchor(ref, A); nb, why_b = anchor(ref, B)
            p = path(ref, na, nb) if na and nb else None
            pts = samples(p) if p else []
            cells = sorted({c for c in (lattice_cell(x, y) for x, y in pts) if c is not None})
            onref = {(a, b) for a in adj[ref] for b, _, o in adj[ref][a] if o}
            seen_geom[key] = {"note": "%s; %s; %.0f %% of length on ref %s" % (why_a, why_b, 100 * (sum(math.dist(node[a], node[b]) for a, b in zip(p[:-1], p[1:]) if (a, b) in onref) / max(1e-9, sum(math.dist(node[a], node[b]) for a, b in zip(p[:-1], p[1:])))) if p else 0, ref), "length_km": round(sum(math.dist(node[a], node[b]) for a, b in zip(p[:-1], p[1:])) / 1000, 1) if p else None,
                              "samples": len(pts), "samples_in_lattice": sum(lattice_cell(x, y) is not None for x, y in pts), "cells": cells,
                              "choi": [t for t in (choi_at(x, y) for x, y in pts) if t is not None]}
        gm = seen_geom[key]
        Ad = [float(A_disc[c]) for c in gm["cells"] if math.isfinite(A_disc[c])]
        tr, why = traffic_return(ref, A, B, off)
        tr_med = st.median([kst(x["reopen"]).timestamp() for x in tr]) if tr else None
        later_reopen = [r for r in reopen_msgs if kst(r["effective_kst"]) > off and any(
            (ROUTE_REF.get(x.split(" ", 1)[0]) == ref and set(base(y) for y in x.split(" ", 1)[1].split("~")) & {A, B})
            for x in r["sections_parsed"].split(" ; ") if " " in x and "~" in x)]
        row = {"official_closure_kst": e["effective_kst"], "time_basis": e["time_basis"], "section": s, "route_ref": ref,
               "geometry": gm["note"], "length_km": gm["length_km"], "lattice_cells": len(gm["cells"]),
               "share_of_length_in_lattice": round(gm["samples_in_lattice"] / gm["samples"], 2) if gm["samples"] else None,
               "cells_with_fire_disc": len(Ad), "fire_first_kst": ts_kst(min(Ad)) if Ad else "", "fire_last_kst": ts_kst(max(Ad)) if Ad else "",
               "official_reopen_message_kst": "; ".join("%s %s" % (r["effective_kst"], r["sections_parsed"]) for r in later_reopen),
               "traffic_conzone_directions": len(tr), "traffic_return_median_kst": ts_kst(tr_med) if tr_med else "",
               "traffic_detail": "; ".join("%s %s %s-%s" % (x["name"], x["dir"], x["onset"][5:], x["reopen"][5:]) for x in tr) or why}
        for lab, tau in TAUS.items():
            R = max(Ad) + tau * 60 if Ad else None
            row["model_reopen_%s_kst" % lab] = ts_kst(R) if R else ""
            row["model_minus_traffic_%s_min" % lab] = round((R - tr_med) / 60) if R and tr_med else ""
        # secondary, added after seeing the primary column (amendment 1): the model's closed spell on the section that
        # covers the official closure time (union over cells of [A_c, A_c + tau)); its end; "open" if none covers it
        for lab, tau in (("frozen", TAUS["frozen"]),):
            spans = sorted((a, a + tau * 60) for a in Ad)
            merged = []
            for a, b in spans:
                if merged and a <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            o = off.timestamp()
            cov = [m for m in merged if m[0] <= o < m[1]]
            row["episode_model_state_at_closure"] = "closed" if cov else "open"
            row["episode_model_reopen_kst"] = ts_kst(cov[0][1]) if cov else ""
            row["episode_model_minus_traffic_min"] = round((cov[0][1] - tr_med) / 60) if cov and tr_med else ""
            nxt = [m for m in merged if m[0] > o]
            row["episode_next_model_closure_kst"] = ts_kst(nxt[0][0]) if (nxt and not cov) else ""
        Ac = gm["choi"]
        row["choi_samples"] = len(Ac)
        row["choi_fire_last_kst"] = ts_kst(max(Ac)) if Ac else ""
        Rc = max(Ac) + TAUS["frozen"] * 60 if Ac else None
        row["choi_model_reopen_frozen_kst"] = ts_kst(Rc) if Rc else ""
        row["choi_model_minus_traffic_frozen_min"] = round((Rc - tr_med) / 60) if Rc and tr_med else ""
        rows.append(row)
with open(OUT / "korea_reopen_sections.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
res = {"osm_sha256": hashlib.sha256(raw).hexdigest(), "disc_record_ends_kst": ts_kst(disc_end), "tau_min": TAUS, "rows": rows}
(OUT / "korea_reopen.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
for r in rows:
    print(r["official_closure_kst"], r["section"], "| cells", r["lattice_cells"], "fire", r["cells_with_fire_disc"], r["fire_first_kst"], r["fire_last_kst"],
          "| traffic", r["traffic_return_median_kst"], "n", r["traffic_conzone_directions"], "| model", r["model_reopen_frozen_kst"], "diff", r["model_minus_traffic_frozen_min"],
          "| choi", r["choi_model_reopen_frozen_kst"], r["choi_model_minus_traffic_frozen_min"], "| episode", r["episode_model_state_at_closure"], r["episode_model_reopen_kst"], r["episode_model_minus_traffic_min"], r["episode_next_model_closure_kst"], "|", r["official_reopen_message_kst"][:60])
