"""One-at-a-time table (PROTOCOL 4): two card cases, CONTESTED, one parameter at low or high, others at middle."""
import glob, gzip, json, statistics as st, collections
rows = []
seen = set()
for fn in sorted(glob.glob("results/work/*__oat*.json.gz")) + sorted(glob.glob("results/work/*__mid.json.gz")):
    for r in json.load(gzip.open(fn, "rt"))["rows"]:
        k = (r["region"], r["issue_utc"], r["param"], r["place_id"])
        if (r["region"], r["issue_utc"]) in {("uiseong_andong_2025", 3), ("yeongdeok_2025", 9)} and k not in seen:
            seen.add(k); rows.append(r)
out = {}
for case, rid in (("uiseong_andong_12:00KST", "uiseong_andong_2025"), ("yeongdeok_18:00KST", "yeongdeok_2025")):
    tab = {}
    for pn in sorted({r["param"] for r in rows if r["region"] == rid}, key=lambda x: (x != "MID", x)):
        rs = [r for r in rows if r["region"] == rid and r["param"] == pn]
        ok = [r for r in rs if r["contested_s"] is not None]
        sh = [(r["L0"] - r["contested_s"]) / 60 for r in ok]
        qe = [(r["S_free"] - r["isolated_s"]) / 60 for r in ok if r["isolated_s"] is not None and r["S_free"] is not None]
        tab[pn] = {"villages": len(rs), "clear": len(ok), "cannot_clear": len(rs) - len(ok),
                   "median_shift_vs_L0_min": round(st.median(sh), 1) if sh else None, "max_shift_vs_L0_min": round(max(sh), 1) if sh else None,
                   "max_queue_effect_min": round(max(qe), 1) if qe else None}
    out[case] = tab
json.dump(out, open("results/oat.json", "w"), indent=1)
for c, t in out.items():
    print(c)
    for k, v in t.items(): print(" ", k, v)
