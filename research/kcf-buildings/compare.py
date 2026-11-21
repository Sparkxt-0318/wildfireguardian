"""Assumed vs real demand, same code, same place-hours (PROTOCOL §5). Reads the committed assumed-arm rows
(research/kcf-queue/results/place_hours.csv.gz) and the real-arm rows (research/kcf-queue/results_real/work/*__<stage>.json.gz).
Writes research/kcf-buildings/compare.json and prints the tables used in RESULTS.md.
Usage: python3 compare.py [mid|lh]"""
import csv, glob, gzip, json, statistics as st, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
Q = HERE.parent / "kcf-queue"
stage = sys.argv[1] if len(sys.argv) > 1 else "mid"
params = ["MID"] if stage == "mid" else ["LOW", "HIGH"]
def num(x):
    return None if x in ("", None) else int(float(x))
A, B = {}, {}
for r in csv.DictReader(gzip.open(Q / "results/place_hours.csv.gz", "rt", encoding="utf-8")):
    if r["param"] in params:
        A[(r["param"], r["region"], int(r["issue_utc"]), r["place_id"])] = r
for fn in sorted(glob.glob(str(Q / f"results_real/work/*__{stage}.json.gz"))):
    for r in json.load(gzip.open(fn, "rt"))["rows"]:
        B[(r["param"], r["region"], int(r["issue_utc"]), r["place_id"])] = r
keys = sorted(set(A) & set(B))
print(stage, "assumed rows", len(A), "real rows", len(B), "common", len(keys))
def mins(x): return None if x is None else x / 60.0
def q(v, p): return None if not v else sorted(v)[min(len(v) - 1, int(p * len(v)))]
def summ(v): return None if not v else {"n": len(v), "median": round(st.median(v), 2), "q1": round(q(v, .25), 2), "q3": round(q(v, .75), 2), "max": round(max(v), 2), "min": round(min(v), 2)}
out = {"stage": stage, "n_common": len(keys), "by_param": {}}
for pn in params:
    ks = [k for k in keys if k[0] == pn]
    res = {"n": len(ks)}
    for scen in ("contested", "isolated"):
        sa = {k: num(A[k][scen + "_s"]) for k in ks}; sb = {k: num(B[k].get(scen + "_s")) for k in ks}
        ca = sum(1 for k in ks if sa[k] is not None); cb = sum(1 for k in ks if sb[k] is not None)
        both = [k for k in ks if sa[k] is not None and sb[k] is not None]
        d = [(sb[k] - sa[k]) / 60 for k in both]
        r = {"clear_assumed": ca, "cannot_assumed": len(ks) - ca, "clear_real": cb, "cannot_real": len(ks) - cb,
             "became_cannot": sum(1 for k in ks if sa[k] is not None and sb[k] is None), "became_clear": sum(1 for k in ks if sa[k] is None and sb[k] is not None),
             "n_both_clear": len(both), "changed_ge_1min": sum(1 for x in d if abs(x) >= 1.0), "changed_ge_10min": sum(1 for x in d if abs(x) >= 10.0),
             "earlier_ge_1min": sum(1 for x in d if x <= -1.0), "later_ge_1min": sum(1 for x in d if x >= 1.0), "delta_min": summ(d)}
        r["any_leaveby_change"] = r["changed_ge_1min"] + r["became_cannot"] + r["became_clear"]
        # queue-induced delay S_free - s*  (minutes): the part of the shift that the spread does not explain
        def delay(S, s_):
            return [(int(float(S[k]["S_free"])) - s_[k]) / 60 for k in ks if s_[k] is not None and S[k].get("S_free") not in ("", None)]
        r["queue_delay_assumed_min"] = summ(delay(A, sa)); r["queue_delay_real_min"] = summ(delay(B, sb))
        r["s_assumed_min"] = summ([mins(v) for v in sa.values() if v is not None]); r["s_real_min"] = summ([mins(v) for v in sb.values() if v is not None])
        res[scen] = r
        if scen == "contested":
            # per place
            pl = {}
            for k in ks:
                pl.setdefault(k[3], []).append(k)
            rows = []
            for pid, kk in pl.items():
                na, nb = int(A[kk[0]]["N"]), int(B[kk[0]]["N"])
                dd = [(sb[k] - sa[k]) / 60 for k in kk if sa[k] is not None and sb[k] is not None]
                rows.append({"place_id": pid, "name": A[kk[0]]["name"], "sigungu": A[kk[0]]["sigungu"], "eupmyeon": A[kk[0]]["eupmyeon"], "hours": len(kk),
                             "N_assumed": na, "N_real": nb, "N_ratio": round(nb / na, 3),
                             "cannot_assumed": sum(1 for k in kk if sa[k] is None), "cannot_real": sum(1 for k in kk if sb[k] is None),
                             "median_shift_min": round(st.median(dd), 2) if dd else None, "max_abs_shift_min": round(max(abs(x) for x in dd), 2) if dd else None,
                             "clearance_card_assumed_min": round(na / 800 * 60, 1), "clearance_card_real_min": round(nb / 800 * 60, 1)})
            res["places"] = rows
            res["card_clearance_min"] = {"assumed": summ([r_["clearance_card_assumed_min"] for r_ in rows]), "real": summ([r_["clearance_card_real_min"] for r_ in rows])}
            res["N"] = {"assumed": summ([r_["N_assumed"] for r_ in rows]), "real": summ([r_["N_real"] for r_ in rows]), "places": len(rows)}
    # checker verdicts of the real arm
    bad = [k for k in ks if B[k].get("contested_cert_valid") is False or B[k].get("isolated_cert_valid") is False]
    res["real_cert_invalid"] = len(bad)
    res["real_cert_checked"] = sum(1 for k in ks for f in ("isolated_cert_valid", "contested_cert_valid") if B[k].get(f) is not None)
    out["by_param"][pn] = res
json.dump(out, open(HERE / f"compare_{stage}.json", "w"), ensure_ascii=False, indent=1)
for pn, res in out["by_param"].items():
    c = res["contested"]
    print(pn, "n", res["n"], "| CONTESTED: cannot clear", c["cannot_assumed"], "->", c["cannot_real"], "| became cannot / clear", c["became_cannot"], c["became_clear"],
          "| both clear", c["n_both_clear"], "changed >=1 min", c["changed_ge_1min"], ">=10 min", c["changed_ge_10min"], "| delta", c["delta_min"])
    print("  card clearance min", res["card_clearance_min"], "N", res["N"])
    print("  queue delay assumed", c["queue_delay_assumed_min"], "real", c["queue_delay_real_min"], "| real cert invalid", res["real_cert_invalid"], "of", res["real_cert_checked"])
    pl = sorted(res["places"], key=lambda r: -(r["max_abs_shift_min"] or 0))[:10]
    print("  top 10 by max |shift|:", [(r["name"], r["eupmyeon"], r["N_assumed"], r["N_real"], r["max_abs_shift_min"]) for r in pl])
