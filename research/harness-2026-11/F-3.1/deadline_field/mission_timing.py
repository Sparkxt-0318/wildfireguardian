"""Time the F-3.1 deadline-field search on the research missions (data/routing/latest_inputs_try02/requests), with
build and search reported separately. No verification, no witness.

  build  = PacketModel(graph, packet): read graph + packet, blocked-start intervals of every edge (both rules)
  search = pm.instance('cert', ...) + backward(...) + issue_set(origin): the full feasible-departure set of the
           mission's origin for its first destination (cert = router rule OR closed whole-road rule; contact field)

Run from research/harness-2026-11/F-3.1 after `python3 tools/fetch_routing_inputs.py` at the repo root:
  python3 -m deadline_field.mission_timing                         # all 20 missions
  python3 -m deadline_field.mission_timing --only uiseong_andong_2025/20250323T010000Z_FD1 --repeat 3
Output: one JSON line per mission (build_s, search_s, latest departure, feasible set).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field.core import backward, issue_set  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "routing")
    ap.add_argument("--only", action="append", help="region/tag, e.g. uiseong_andong_2025/20250323T010000Z_FD1")
    ap.add_argument("--repeat", type=int, default=1, help="repeat the search (build once)")
    a = ap.parse_args()
    for f in sorted((a.data_root / "latest_inputs_try02" / "requests").glob("*/*.json")):
        name = "%s/%s" % (f.parent.name, f.stem)
        if a.only and name not in a.only:
            continue
        q = json.loads(f.read_text())
        region, compact = f.parent.name, f.stem.split("_")[0]
        t0 = time.perf_counter()
        pm = PacketModel(a.data_root / "graphs" / region / "graph.json",
                         a.data_root / "latest_inputs_try02" / "packets" / region / compact)
        build = time.perf_counter() - t0
        o, d = q["position"]["node"], q["destinations"][0]
        searches = []
        for _ in range(a.repeat):
            t1 = time.perf_counter()
            fld = backward(pm.instance("cert", [{"node": d["node"], "dwell": d["dwell"],
                                                 "window": list(d["open_intervals"][0])}], [o]))
            fs = issue_set(fld, pm.nidx[o])
            searches.append(time.perf_counter() - t1)
        print(json.dumps({"mission": name, "build_s": round(build, 3), "search_s": [round(s, 3) for s in searches],
                          "latest_departure_s": fs[-1][1] if fs else None, "feasible_set": fs}), flush=True)


if __name__ == "__main__":
    main()
