"""Label every request that is ROUTE under no_reentry/1 and NO_ROUTE under no_reentry/2 (the default) with the adopted
split wording (orchestrator, 2026-11-13). Method follows the independent verifier's nora_fbase_nr2_lost.py, extended
from 4 UA h5 packets to all 24:
  B0 = cells closed at second 0 on the /2 packet and open at second 0 on the /1 packet (burned out before the start).
  The origin's INSTANCE entry node (INSTANCE.json) is located in the packet grid.
Labels (verbatim):
  origin cell in B0   -> "start point on ground the model shows as burned before the start: not evaluated"
  otherwise           -> "depends on the no-re-entry rule" (the route is lost through a corridor closed by B0;
                          sub-tagged with whether the origin cell is open at 0 on /2)

    python classify_lost_nr2.py --fbase F-BASE --v37 <F-DYN _data v3.7> --v36 <F-DYN _data v3.6> --out LOST_nr2.json
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
from pathlib import Path

import numpy as np

L_B0 = "start point on ground the model shows as burned before the start: not evaluated"
L_RULE = "depends on the no-re-entry rule"


def rows(d):
    out = {}
    for f in glob.glob(str(d / "*.jsonl")):
        ls = [json.loads(l) for l in open(f)]
        for r in ls[1:]:
            out[(ls[0]["packet"], r["origin"], r["departure"])] = r["no_reentry"]["exact"][0]
    return out


def z0(p):
    h = json.loads((p / "HAZARD.json").read_text())
    m = h["members"][0]
    return np.array(m["flame"][0], bool) & (float(m["breakpoints"][0]) == 0), h["grid"]


def main():
    ap = argparse.ArgumentParser()
    for k in ("--fbase", "--v37", "--v36", "--out"):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args()
    n1, n2 = rows(a.fbase / "fdyn_f_nr1"), rows(a.fbase / "fdyn_f_nr2")
    inst = json.load(open(a.v37 / "INSTANCE.json"))["instances"]
    entry = {(i["region"], i["start_tag"], o["origin_id"].replace(":", "_").replace("/", "_")): o["entry_node"]
             for i in inst for o in i["origins"]}
    xy, cache, out, counts = {}, {}, [], collections.Counter()
    for k in sorted(n2):
        if not (n1[k] == "ROUTE" and n2[k] == "NO_ROUTE"):
            continue
        pk, o, dep = k
        r, s, h, v = pk.split(":")
        if r not in xy:
            g = json.load(open(a.v37 / f"graphs_interim/{r}/graph.json"))
            xy[r] = {n["id"]: (n["x"], n["y"]) for n in g["nodes"]}
        rel = f"{r}/{s}_h{h}_{v}_central_q300"
        if rel not in cache:
            c2, g = z0(a.v37 / "packets_v37_noreentry2" / rel)
            c1, _ = z0(a.v36 / "packets_v36_noreentry" / rel)
            cache[rel] = (c2 & ~c1, c2, g)
        b0, closed2, g = cache[rel]
        x, y = xy[r][entry[(r, s, o)]]
        i = int((y - g["y0"]) // g["resolution"]) * g["width"] + int((x - g["x0"]) // g["resolution"])
        if b0[i]:
            lab, sub = L_B0, "origin in B0"
        else:
            lab, sub = L_RULE, ("origin closed at 0, not B0" if closed2[i] else "origin open at 0 (corridor through B0)")
        counts[(r, lab)] += 1
        out.append(dict(packet=pk, origin=o, departure=dep, label=lab, detail=sub))
    res = dict(method="verifier's nora_fbase_nr2_lost.py, all 24 packets", lost=len(out),
               by_label=collections.Counter(x["label"] for x in out),
               by_detail=collections.Counter(x["detail"] for x in out),
               by_region_label={f"{r} | {l}": c for (r, l), c in sorted(counts.items())}, rows=out)
    a.out.write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
