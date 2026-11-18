"""Gate part 1 (PROTOCOL §2.1.1): fast base vs committed per_place.csv, all 27,144 rows. Writes gate1.json."""
import csv, json, sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import fastfield as FF, defend as DF

KST = timezone(timedelta(hours=9))

def job(a):
    region, arm, hz, hour = a
    R = DF.REG[region]; H = FF.HORIZONS[hz]; T = datetime(2025, 3, 25, hour, tzinfo=timezone.utc)
    d, f, info, cs, b = DF.base_state(R, arm, T, H)
    lo, fields = DF.solve_all(R, b, H)
    base = DF.place_values(R, b, lo, fields)
    nob = b.copy(); nob[:] = -1
    lo0, f0 = DF.solve_all(R, nob, H, shelters=sorted({v[1] for v in base.values() if v[1] is not None}))
    out = []
    for p, (v, s, per) in base.items():
        oid = R.places[p]
        inside = bool(d[R.node_cell[R.pl_node[p]]] == 0)
        if v < 0:
            st = "INSIDE_KNOWN_FIRE_AREA" if inside else "NO_SAFE_DEPARTURE"; sh = ""
        else:
            st = "LATEST_SAFE_DEPARTURE" if v < R.issue_value(f0[s], lo0, nob, p) else "NOT_CUT_WITHIN_H"
            sn = R.shelter_nodes[s]
            sh = next(x for x in R.R.cands[oid][1] if x["properties"]["entry"]["node"] == sn)["properties"]["id"]
        t = (T + timedelta(seconds=int(v))).astimezone(KST).strftime("%m-%d %H:%M") if v >= 0 else ""
        out.append((region, oid, arm, hz, T.astimezone(KST).strftime("%m-%d %H:%M"), st, t, sh))
    return out

def main():
    jobs = [(r, s, h, i) for r in FF.REGIONS for s in FF.ARMS for h in FF.HORIZONS for i in range(3, 16)]
    mine = {}
    with ProcessPoolExecutor(4, initializer=DF.init, initargs=(FF.REGIONS,)) as ex:
        for res in ex.map(job, jobs):
            for r in res:
                mine[r[:5]] = r[5:]
    rows = list(csv.DictReader(open(FF.ROOT / "research/kcf-replay/per_place.csv")))
    mm = Counter(); ex_ = []
    for r in rows:
        k = (r["region"], r["place_id"], r["standin"], r["horizon"], r["issue_kst"])
        st, t, sh = mine[k]
        c = {"ld_minute": t == r["last_departure_in_horizon_kst"], "shelter": sh == r["shelter_id"],
             "state": st == r["departure_state"],
             "empty_vs_nonempty": (t == "") == (r["last_departure_in_horizon_kst"] == "")}
        for kk, ok in c.items():
            if not ok:
                mm[kk] += 1
                if len(ex_) < 30:
                    ex_.append({"key": k, "check": kk, "mine": [st, t, sh], "committed": [r["departure_state"], r["last_departure_in_horizon_kst"], r["shelter_id"]]})
    states = Counter((r["departure_state"], mine[(r["region"], r["place_id"], r["standin"], r["horizon"], r["issue_kst"])][0]) for r in rows)
    res = {"rows": len(rows), "mismatches": dict(mm), "examples": ex_, "state_confusion_committed_vs_fast": {f"{a}|{b}": n for (a, b), n in states.items()}}
    Path("gate1.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps({k: res[k] for k in ("rows", "mismatches")}), res["examples"][:5])

if __name__ == "__main__":
    main()
