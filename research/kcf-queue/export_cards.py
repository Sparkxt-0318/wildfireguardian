"""Writes product/wfg-roadlayer/data/queue_leaveby.csv for the two card cases from results/work (PROTOCOL 6); KQ_RESULTS_WORK=results_real/work for the real-demand arm of research/kcf-buildings."""
import csv, glob, gzip, json, os
from pathlib import Path
HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "product/wfg-roadlayer/data/queue_leaveby.csv"
CASES = {("uiseong_andong_2025", 3), ("yeongdeok_2025", 9)}
rows = {}
SRC = os.environ.get("KQ_RESULTS_WORK", "results/work")  # kcf-buildings: results_real/work for the real-demand arm
for fn in glob.glob(str(HERE / SRC / "*.json.gz")):
    if "oat" in fn: continue
    for r in json.load(gzip.open(fn, "rt"))["rows"]:
        if (r["region"], r["issue_utc"]) not in CASES: continue
        k = (r["region"], r["issue_utc"], r["place_id"])
        e = rows.setdefault(k, {"region": r["region"], "issue_utc": "2025-03-25T%02d:00:00Z" % r["issue_utc"], "place_id": r["place_id"], "L0_s": r["L0"]})
        e["N_" + r["param"].lower()] = r["N"]
        e["s_cont_" + r["param"].lower()] = "" if r["contested_s"] is None else r["contested_s"]
        e["s_iso_" + r["param"].lower()] = "" if r["isolated_s"] is None else r["isolated_s"]
        if r["param"] == "MID":
            b = r.get("contested_bind") or {}
            e.update(S_free_mid=r["S_free"] if r["S_free"] is not None else "", bind_kind_mid=b.get("kind", ""), bind_way_mid=b.get("way") or "",
                     cert_checked_mid=r.get("contested_cert_valid", ""))
cols = ["region", "issue_utc", "place_id", "L0_s", "N_low", "N_mid", "N_high", "S_free_mid", "s_iso_low", "s_iso_mid", "s_iso_high",
        "s_cont_low", "s_cont_mid", "s_cont_high", "bind_kind_mid", "bind_way_mid", "cert_checked_mid"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols, lineterminator="\n"); w.writeheader()
    for k in sorted(rows): w.writerow({c: rows[k].get(c, "") for c in cols})
print(len(rows), OUT)
