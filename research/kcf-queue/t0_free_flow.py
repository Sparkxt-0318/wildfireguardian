"""T0 (PROTOCOL 5): my closure fields + latest-label recursion vs the committed per_place.csv (MEASURED, 8h)."""
import csv, json, sys
from datetime import datetime, timedelta, timezone
from collections import Counter
from kq import real, solver

rows = [r for r in csv.DictReader(open(real.ROOT / "research/kcf-replay/per_place.csv")) if r["standin"] == "MEASURED" and r["horizon"] == "8h"]
by = {(r["region"], r["place_id"], r["issue_kst"]): r for r in rows}
rep = Counter(); mism = []
for rid in real.REGIONS:
    R = real.Reg(rid)
    tab = real.cap_table()
    for hu in real.HOURS_UTC:
        T = datetime(2025, 3, 25, hu, tzinfo=timezone.utc)
        kst = (T + timedelta(hours=9)).strftime("%m-%d %H:%M")
        close, d = R.closure(T)
        net = R.net(close, {k: v for k, v in tab.items()}, 1.0)
        net.ncap = None
        for o, node, sh in R.village_ctx_args(close):
            r = by.get((rid, o["id"], kst))
            if r is None:
                rep["no_row"] += 1; continue
            st = r["departure_state"]
            inside = d[R.road.node_cell[node]] <= 0
            ctx = solver.Ctx(net, node, sh)
            L = None if inside else ctx.L0(net)
            want = r["latest_safe_departure_kst"] or r["last_departure_in_horizon_kst"]
            if st == "INSIDE_KNOWN_FIRE_AREA":
                ok = inside
            elif st == "NO_SAFE_DEPARTURE":
                ok = (not inside) and L is None
            else:
                got = (T + timedelta(hours=9, seconds=L)).strftime("%m-%d %H:%M") if L is not None else None
                ok = got == want
            rep[(st, ok)] += 1
            if not ok:
                mism.append({"region": rid, "place": o["id"], "issue": kst, "state": st, "want": want, "L0": L, "inside": bool(inside)})
    print(rid, dict(rep), flush=True)
out = {"counts": {str(k): v for k, v in rep.items()}, "mismatches": mism}
json.dump(out, open("results/t0_free_flow_reproduction.json", "w"), indent=1)
print(len(mism), "mismatches")
