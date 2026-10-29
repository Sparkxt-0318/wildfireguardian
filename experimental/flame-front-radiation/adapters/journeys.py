"""Distinct returned journeys of the frozen 20-mission Korean panel (request-window replay, 29 October 2026).

Source: research/routing/request-window-20261029/RAW_EXECUTIONS.jsonl.gz (80 executions). A journey is identified by
its case and the SHA-256 of its canonical leg list; repetitions and arms returning the same legs collapse to one.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RAW = REPO / "research/routing/request-window-20261029/RAW_EXECUTIONS.jsonl.gz"


def canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_returned_journeys(raw_path=RAW):
    by_key = {}
    with gzip.open(raw_path, "rt") as f:
        for line in f:
            row = json.loads(line)
            job, res = row["job"], row["result"]
            inner = res.get("result") or {}
            legs = inner.get("legs") or []
            decision = res.get("decision") or {}
            if not legs or not decision.get("is_successful_journey"):
                continue
            key = (job["cohort"], job["case_id"], canonical_sha(legs))
            rec = by_key.get(key)
            if rec is None:
                rec = by_key[key] = {
                    "cohort": job["cohort"], "case_id": job["case_id"], "cutoff": job["cutoff"],
                    "legs_sha256": key[2], "legs": legs, "arrival": inner["arrival"],
                    "destination": inner["destination"], "executions": [],
                    "recorded_centre_per_member": {k: {"dose": v["dose"], "peak": v["peak"]}
                                                   for k, v in inner.get("per_member", {}).items()},
                    "recorded_whole_road_bounds": inner.get("whole_road_bounds", {}).get("per_member"),
                    "input_sha256": job["input_sha256"], "source_sha256": job["source_sha256"],
                }
            rec["executions"].append(job["execution_id"])
    return sorted(by_key.values(), key=lambda r: (r["cohort"], r["case_id"], r["legs_sha256"]))


if __name__ == "__main__":
    js = load_returned_journeys()
    print(len(js), "distinct journeys,", sum(len(j["executions"]) for j in js), "route executions")
    for j in js:
        print(j["cohort"], j["case_id"], j["arrival"], len(j["legs"]), len(j["executions"]))
