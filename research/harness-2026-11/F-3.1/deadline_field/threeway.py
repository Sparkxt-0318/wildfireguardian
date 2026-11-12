"""Three-way labels under unknown support (see unknown.py) for every route-check job of a planner cache file, and the
per-origin deadline interval [pessimistic, optimistic] (exact seconds, cert rule = router OR closed footprint).

Optimistic = frozen packet. Pessimistic = tier A, tier B at 1.5 and 8.2 km/h.
Note: the dose/peak precondition for pessimistic instances would need a radiation bound for hypothetical unknown
sources; it is NOT established here, so 'checked' under a pessimistic instance means contact-feasible only, and is
reported as such.
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.unknown import extra_blocks, summary  # noqa: E402

TIERS = (("optimistic", None, None), ("A", "A", None), ("B1.5", "B", 1.5), ("B8.2", "B", 8.2),
         ("R1.5", "R", 1.5), ("R8.2", "R", 8.2))


def run(cache_path: Path, data_root: Path):
    doc = json.loads(cache_path.read_text())
    region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
    gp = data_root / "graphs" / region / "graph.json"
    pd = data_root / "latest_inputs_try02" / "packets" / region / compact
    jobs = []
    for key, job in sorted(doc["route_checks"].items()):
        q, res = job["request"], job.get("result") or {}
        jobs.append({"job": key, "start": q["start"]["node_id"], "dest": q["destination"]["node_id"],
                     "dwell": q["dwell_s"], "window": tuple(q["destination_window"]), "offset": int(q["depart_offset_s"]),
                     "recorded": res.get("verdict"), "raw": res.get("raw_status"), "recheck": bool(job.get("recheck_of"))})
    specs = defaultdict(set)
    for j in jobs:
        specs[(j["dest"], j["dwell"], j["window"])].add(j["start"])
    base = PacketModel(gp, pd)
    cell_counts = summary(base.pk)
    out_t = {}
    feas = {}
    for name, tier, v in TIERS:
        t0 = time.perf_counter()
        pm = base if tier is None else PacketModel(gp, pd, extra_blocks=extra_blocks(base.pk, base.g.grid, base.H, tier, v))
        nb = len(pm.extra_blocks)
        for spec in sorted(specs, key=str):
            inst = pm.instance("cert", [{"node": spec[0], "dwell": spec[1], "window": list(spec[2])}], sorted(specs[spec]))
            fld = backward(inst)
            for o in specs[spec]:
                feas[(name, spec, o)] = issue_set(fld, pm.nidx[o])
        out_t[name] = {"wall_s": time.perf_counter() - t0, "extra_blocked_cells": nb}
    # per job labels
    lab = Counter()
    rows = []
    for j in jobs:
        spec = (j["dest"], j["dwell"], j["window"])
        opt = iv.contains(feas[("optimistic", spec, j["start"])], j["offset"])
        r = {"job": j["job"], "recorded": j["recorded"], "raw": j["raw"], "optimistic": opt}
        for name in ("A", "B1.5", "B8.2", "R1.5", "R8.2"):
            pes = iv.contains(feas[(name, spec, j["start"])], j["offset"])
            label = "checked(contact)" if pes else ("no_route" if not opt else "unresolved")
            r[name] = label
            lab[(name, j["recorded"], label)] += 1
        rows.append(r)
    # per origin (start node; planner origin ids map 1:1 to start nodes in these caches) deadline intervals
    origins = defaultdict(set)
    for j in jobs:
        origins[j["start"]].add((j["dest"], j["dwell"], j["window"]))
    widths = {}
    for o, sp in origins.items():
        d = {}
        for name, _, _ in TIERS:
            m = [feas[(name, s, o)][-1][1] for s in sp if feas[(name, s, o)]]
            d[name] = max(m) if m else None
        widths[o] = d
    return {"cache_file": str(cache_path.relative_to(ROOT)), "cells": cell_counts, "timing": out_t,
            "labels": {"%s|%s|%s" % k: v for k, v in sorted(lab.items(), key=str)}, "jobs": rows,
            "origin_deadlines": widths, "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cache", type=Path)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "routing")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = run(a.cache.resolve(), a.data_root)
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("cache_file", "cells", "timing", "labels", "peak_rss_mib")}, indent=1))


if __name__ == "__main__":
    main()
