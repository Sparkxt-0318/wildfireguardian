"""Slim per-job cross-reference table of the 1-h reproduction (Nora row 25) for kit-v2 gate G6 (Priya).

Per route-check job of the six planner caches: recorded verdict / raw_status / reason_code / recheck_of / recorded
arrival / route_sha256 (from the cache), and this field's ROUTER and CERT verdicts (issue_blocked, feasible, earliest
arrival, sha256 of the witness legs as canonical JSON). Field rows come from deadline_field.reproduce outputs.
    python3 -m deadline_field.slim_jobs RAW_REPRODUCE_JSON... --out results/JOBS_1h_crossref.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def legs_sha(legs):
    return None if legs is None else hashlib.sha256(json.dumps(legs, separators=(",", ":")).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows = []
    for f in a.raw:
        d = json.loads(f.read_text())
        cache = json.loads((ROOT / d["cache_file"]).read_text())["route_checks"]
        for j in d["jobs"]:
            res = cache[j["job"]].get("result") or {}
            r = {"job": j["job"], "cache": d["cache_file"], "offset": j["offset"], "verdict": res.get("verdict"),
                 "raw_status": res.get("raw_status"), "reason_code": res.get("reason_code"),
                 "recheck_of": cache[j["job"]].get("recheck_of"), "recorded_arrival": res.get("arrival_s"),
                 "route_sha256": ((res.get("route") or {}).get("properties") or {}).get("route_sha256")}
            for v in ("router", "cert"):
                fv = j["field"][v]
                r[v] = {"issue_blocked": fv["issue_blocked"], "feasible": fv["feasible"], "arrival": fv["arrival"],
                        "legs_sha256": legs_sha(fv["legs"])}
            rows.append(r)
    a.out.write_text(json.dumps({"what": "1-h per-job cross-reference (field reproduction at 70f70d7, Nora row 25); "
                                         "router = kit's own contact rule, cert = router OR closed footprint",
                                 "n": len(rows), "rows": rows}, separators=(",", ":")))
    print(len(rows))


if __name__ == "__main__":
    main()
