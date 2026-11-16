"""F-3.1 certificate on sample replay instances: core.check_fixed_point (order-independent: every R[s] equals the
right-hand side of the set equation, which has a unique solution because the time-expanded graph is acyclic).

Usage: python3 verify_fixed_point.py out/fire_discs.json OUT.json
"""
import json, math, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import replay
from deadline_field import core


def main(discs, out):
    replay.init(["uiseong_andong_2025", "yeongdeok_2025"], discs)
    res = []
    for region, standin, hz, hour in (("uiseong_andong_2025", "RUNNING", "8h", 6), ("yeongdeok_2025", "WORST", "5h", 9),
                                      ("yeongdeok_2025", "RUNNING", "8h", 11)):
        R = replay.REG[region]; H = replay.HORIZONS[hz]
        T = datetime(2025, 3, 25, hour, tzinfo=timezone.utc)
        dist = R.cell_distance(replay.DISCS, T)
        close_s = {c: int(math.ceil(replay.closure_s(standin, float(dist[c])))) for c in range(len(dist))
                   if np.isfinite(dist[c]) and replay.closure_s(standin, float(dist[c])) <= H}
        inst = R.instance(close_s, H)
        oid, (o, near) = sorted(R.cands.items())[len(R.cands) // 2]
        sn = R.nidx[near[0]["properties"]["entry"]["node"]]
        acc = R.accept(close_s, sn, H)
        inst.A = [[] for _ in inst.tail]
        for j in R.inc_by_node.get(sn, []):
            inst.A[j] = list(acc)
        fld = core.backward(inst)
        n = core.check_fixed_point(fld)
        res.append({"region": region, "standin": standin, "horizon": hz, "issue_utc": T.isoformat(), "shelter_node": near[0]["properties"]["entry"]["node"],
                    "states_checked": n, "closed_cells": len(close_s), "fixed_point": "PASS"})
        print(res[-1], flush=True)
    Path(out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
