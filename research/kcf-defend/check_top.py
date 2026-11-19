"""PROTOCOL amendment 2: rank-1 candidate per hour (MEASURED, 8 h, delay 60) re-evaluated with deadline_field.core for
every gaining place; gains must match to the second. Usage: python3 check_top.py RUNS_DIR -> check_top.json"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import aggregate as AG, defend as DF, fastfield as FF
from gate2 import core_sets


def main(runs):
    J = AG.load(runs)
    DF.init(FF.REGIONS)
    out = []
    for h in AG.HOURS:
        C = AG.merged(J, "MEASURED", "8h", h)
        rk = AG.ranking(C, 60)
        if not rk:
            out.append({"hour_kst": h + 9, "rank1": None}); continue
        cid = rk[0][0]
        want = C[cid]["gains"][60]
        got = {}
        T = datetime(2025, 3, 25, h, tzinfo=timezone.utc); H = FF.HORIZONS["8h"]
        for region in C[cid]["regions"]:
            R = DF.REG[region]
            d, f, info, cs, b = DF.base_state(R, "MEASURED", T, H)
            ch = next(c for k, i, m, D, c in DF.candidate_changes(R, T, d, f, b, H) if i == cid and D == 60)
            b2 = b.copy()
            for c, v in ch.items():
                b2[c] = v
            pl = [R.places.index(p) for p in want if p in R.places]
            s0 = core_sets(R, b, H, pl); s1 = core_sets(R, b2, H, pl)
            m = lambda s: sum(x[1] - x[0] + 1 for x in s)
            for p in pl:
                got[R.places[p]] = m(s1[p]) - m(s0[p])
        out.append({"hour_kst": h + 9, "rank1": cid, "places": len(want), "equal": got == want,
                    "diff": {p: [want.get(p), got.get(p)] for p in set(want) | set(got) if want.get(p) != got.get(p)}})
        print(out[-1], flush=True)
    Path("check_top.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
