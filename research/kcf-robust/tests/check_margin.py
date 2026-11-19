"""Timing tolerance by closure shift (this study) against the committed margin field of research/kcf-idea-routing
(keep variant), on shelters whose own cell does not burn within the horizon (where the two definitions coincide),
and the relation of mu_o(t) to the slack L_o - t (PROTOCOL.md section 7).

    python3 research/kcf-robust/tests/check_margin.py
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lib  # noqa: E402
import reachpass as RP  # noqa: E402
from replay import one_shelter  # noqa: E402
from twin import shift_array  # noqa: E402
from margin_field import field as MF, pl  # noqa: E402
from wfg_roadlayer import engine  # noqa: E402
from wfg_roadlayer.vendor.deadline_field import core  # noqa: E402

rng = random.Random(5)
discs = lib.load_discs()
out = []
for rid, hh in (("uiseong_andong_2025", 3), ("uiseong_andong_2025", 9), ("yeongdeok_2025", 9), ("yeongdeok_2025", 12)):
    T = lib.REPLAY_ISSUES[hh - 3]
    reg = lib.region(rid)
    g = RP.Graph(reg.road)
    d = lib.known_distance_m(discs, T)
    r5, r8, cls, _ = lib.MA.curve("MEASURED", discs, T, 8)
    m = lib.minutes_r90(d, r5, r8)
    close = lib.close_s_from_minutes(rid, m)
    arr = lib.close_array_from_minutes(rid, m)
    inst = engine.build_instance(reg.road, close, lib.HORIZON_S)
    by = {}
    for o in reg.origins:
        if o["node"] is None or not o["checkable"]:
            continue
        for s in reg.cands[o["id"]]:
            by.setdefault(s["node"], []).append(o["node"])
    cand = [sn for sn in sorted(by) if reg.road.node_cell[sn] not in close]
    for sn in rng.sample(cand, min(4, len(cand))):
        inst.A = [[] for _ in range(len(inst.tail))]
        for j in reg.road.inc_by_node.get(sn, []):
            inst.A[j] = engine.accept(reg.road, close, sn, lib.HORIZON_S, lib.DWELL)
        inst.IB = {o: engine.origin_closure(reg.road, close, o, lib.HORIZON_S) for o in by[sn]}
        t0 = time.time()
        fld = MF.margin_field(inst, lib.HORIZON_S)
        tm = time.time() - t0
        for o in by[sn]:
            f = MF.issue_margin(fld, o)
            mu0 = pl.value(f, 0)
            L0 = one_shelter(g, arr, sn, [o])[0][0]
            # shift tolerance at 60 s resolution vs mu(0)
            ok_at = lambda mm: one_shelter(g, shift_array(arr, mm), sn, [o])[0][0] >= 0
            exact = None
            if mu0 >= 0:
                exact = ok_at(mu0) and (mu0 == lib.HORIZON_S or not ok_at(mu0 + 1))
            # mu(t) against L - t on the feasible window
            dense = pl.to_dense(f, 0, max(L0, 0)) if L0 >= 0 else []
            slack_eq = int(sum(1 for t, v in enumerate(dense) if v == min(lib.HORIZON_S, L0 - t)))
            out.append({"rid": rid, "issue_utc": T.isoformat(), "shelter": int(sn), "origin": int(o), "mu0_s": int(mu0), "L0_s": int(L0),
                        "shift_tolerance_equals_mu0": exact, "seconds_with_mu_eq_L_minus_t": slack_eq, "window_seconds": len(dense),
                        "margin_field_s": round(tm, 1)})
            print(out[-1], flush=True)
(HERE.parent / "out").mkdir(exist_ok=True)
(HERE.parent / "out/check_margin.json").write_text(json.dumps(out, indent=1))
n = len(out)
print("pairs", n, "shift == margin field at t=0:", sum(1 for x in out if x["shift_tolerance_equals_mu0"] in (True, None)),
      "mu(t) == L - t on every second of the window:", sum(1 for x in out if x["seconds_with_mu_eq_L_minus_t"] == x["window_seconds"]))
