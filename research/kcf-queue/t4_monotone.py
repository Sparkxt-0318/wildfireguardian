"""T4 (PROTOCOL 5): is feasibility a prefix in s? Random 5 % of MID place-hours (seed fixed), ISOLATED, scan every 60 s over [0, L0]."""
import gzip, json, random, glob, collections
from datetime import datetime, timezone
from kq import real, solver, run_real

rnd = random.Random(20261119)
rows = []
for fn in sorted(glob.glob("results/work/*__mid.json.gz")):
    rows += json.load(gzip.open(fn, "rt"))["rows"]
k = max(1, round(0.05 * len(rows)))
pick = rnd.sample(rows, k)
bykey = collections.defaultdict(list)
for r in pick: bykey[(r["region"], r["issue_utc"])].append(r)
out = {"sampled": k, "place_hours_scanned": 0, "non_prefix": [], "scan_points": 0}
for (rid, hu), rs in sorted(bykey.items()):
    R = run_real.reg(rid); T = datetime(2025, 3, 25, hu, tzinfo=timezone.utc)
    close, dist = R.closure(T); p = run_real.MID
    net = R.net(close, real.cap_table(p["cap_other"]), p["rho"])
    for o, node, sh in R.village_ctx_args(close):
        r = next((x for x in rs if x["place_id"] == o["id"]), None)
        if r is None: continue
        ctx = solver.Ctx(net, node, sh)
        N, W = r["N"], r["W"]; seq = []
        for s in range(0, ctx.l0 + 1, 60):
            seq.append(solver.try_start(net, ctx, N, s, W, {}) is not None)
            out["scan_points"] += 1
        out["place_hours_scanned"] += 1
        # prefix = True...True False...False
        if any((not a) and b for a, b in zip(seq, seq[1:])):
            out["non_prefix"].append({"region": rid, "hour": hu, "place": o["id"], "pattern_first_change": [i for i in range(len(seq) - 1) if (not seq[i]) and seq[i + 1]][:3]})
        print(rid, hu, o["id"], len(seq), flush=True)
json.dump(out, open("results/t4_monotonicity.json", "w"), indent=1)
print({k: (v if not isinstance(v, list) else len(v)) for k, v in out.items()})
