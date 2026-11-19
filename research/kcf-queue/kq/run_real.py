"""Main run: every village x issue hour x parameter set x scenario (PROTOCOL 1, 3.7, 4)."""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

from . import cert as certmod
from . import real, solver

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import checker  # noqa: E402  (independent; imports nothing from kq)

MID = dict(hh=1.0, vph=1.198, W=1800, rho=0.85, cap_other=800)
LOW = dict(hh=0.7, vph=0.9, W=900, rho=1.0, cap_other=1000)
HIGH = dict(hh=1.4, vph=1.5, W=3600, rho=0.70, cap_other=600)
PARAMS = {"LOW": LOW, "MID": MID, "HIGH": HIGH}
for _k in ("hh", "vph", "W", "rho", "cap_other"):
    for _n, _v in (("low", LOW), ("high", HIGH)):
        PARAMS["OAT_%s_%s" % (_k, _n)] = dict(MID, **{_k: _v[_k]})
CERT_DIR = Path(os.environ.get("KQ_CERT_DIR", "/tmp/kq_certs"))
_R = {}


def reg(rid):
    if rid not in _R:
        _R[rid] = real.Reg(rid)
    return _R[rid]


def job(arg):
    rid, hu, pnames, check_policy = arg
    t0 = time.time()
    R = reg(rid)
    T = datetime(2025, 3, 25, hu, tzinfo=timezone.utc)
    close, dist = R.closure(T)
    nets = {}
    for pn in pnames:
        p = PARAMS[pn]
        nets[pn] = R.net(close, real.cap_table(p["cap_other"]), p["rho"])
    anynet = next(iter(nets.values()))
    vill = []
    for o, node, sh in R.village_ctx_args(close):
        h = R.hh.get(o["id"])
        if h is None or h["kind"] != "village" or dist[R.road.node_cell[node]] <= 0:
            continue
        ctx = solver.Ctx(anynet, node, sh)
        L0 = ctx.L0(anynet)
        if L0 is None:
            continue
        vill.append({"o": o, "node": node, "sh": sh, "ctx": ctx, "L0": L0, "hh": float(h["households"])})
    # first-vehicle free-flow route at release 0 -> edge sets (neighbour definition, PROTOCOL 3.7)
    byedge = {}
    for v in vill:
        p = solver.route(anynet, v["ctx"], 0, {})
        v["edges0"] = {e for e, _ in p} if p else set()
        for e in v["edges0"]:
            byedge.setdefault(e, set()).add(v["o"]["id"])
    byid = {v["o"]["id"]: v for v in vill}
    for v in vill:
        v["nb"] = sorted({u for e in v["edges0"] for u in byedge[e]} - {v["o"]["id"]})
    rows = []
    for pn in pnames:
        p, net = PARAMS[pn], nets[pn]
        cap_vph = real.cap_table(p["cap_other"])
        for v in vill:
            v["N"] = max(1, round(v["hh"] * p["hh"] * p["vph"]))
        lim = int(os.environ.get("KQ_LIMIT", "0")) or len(vill)
        for v in vill[:lim]:
            vid, N, W = v["o"]["id"], v["N"], p["W"]
            rel_last = solver.releases(N, 0, W)[-1]
            row = {"region": rid, "issue_utc": hu, "param": pn, "place_id": vid, "name": v["o"]["name"], "sigungu": v["o"]["sigungu"],
                   "eupmyeon": v["o"]["eupmyeon"], "N": N, "W": W, "L0": v["L0"], "S_free": v["L0"] - rel_last if v["L0"] >= rel_last else None,
                   "neighbours": len(v["nb"])}
            for scen in ("ISOLATED", "CONTESTED"):
                base, nbr_unrouted, nb_owners = {}, 0, []
                if scen == "CONTESTED":
                    items = []
                    for u in v["nb"]:
                        w = byid[u]
                        for k, r in enumerate(solver.releases(w["N"], 0, W)):
                            items.append((r, u, k))
                    items.sort()
                    npaths = {u: [None] * byid[u]["N"] for u in v["nb"]}
                    for r, u, k in items:
                        pth = solver.route(net, byid[u]["ctx"], r, base)
                        if pth is None:
                            nbr_unrouted += 1
                            continue
                        solver.reserve(net, pth, base)
                        npaths[u][k] = pth
                    nb_owners = [(u, npaths[u]) for u in v["nb"]]
                s, paths = solver.latest_start(net, v["ctx"], N, W, base, v["L0"])
                key = scen.lower()
                row[key + "_s"] = s
                row[key + "_nb_unrouted"] = nbr_unrouted
                if s is None:
                    continue
                rel = solver.releases(N, s, W)
                amax_of = {n: R.amax(close, n) for n in v["sh"]}
                bd = certmod.binding(net, amax_of, paths, rel, vid)
                way = R.sources[bd["id"]] if bd["kind"] == "edge" else None
                row[key + "_bind"] = {**bd, "way": way}
                if check_policy(pn, scen, vid):
                    owners = [{"id": vid, "origin": v["node"], "N": N, "start": s, "spread": W, "role": "subject", "paths": paths,
                               "shelters": list(v["sh"])}]
                    for u, pl in nb_owners:
                        w = byid[u]
                        ok = [(k, q) for k, q in enumerate(pl) if q is not None]
                        if not ok:
                            continue
                        owners.append({"id": u, "origin": w["node"], "N": w["N"], "start": 0, "spread": W, "role": "neighbour",
                                       "paths": [q for _, q in ok], "shelters": list(w["sh"]), "ks": [k for k, _ in ok]})
                    c = certmod.build(R, net, close, cap_vph, p["rho"], owners, vid, bd)
                    res = checker.check(c)
                    row[key + "_cert_valid"] = res["valid"]
                    if not res["valid"]:
                        row[key + "_cert_fail"] = [f["code"] for f in res["failures"][:5]]
                    if check_policy(pn, scen, vid) == "store":
                        CERT_DIR.mkdir(parents=True, exist_ok=True)
                        fn = CERT_DIR / ("%s__%02d__%s__%s__%s.json.gz" % (rid, hu, pn, scen, vid.replace("/", "_").replace(":", "_")))
                        with gzip.open(fn, "wt") as f:
                            json.dump(c, f, separators=(",", ":"))
            rows.append(row)
    return {"rid": rid, "hu": hu, "rows": rows, "wall_s": round(time.time() - t0, 1)}
