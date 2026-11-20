"""Accuracy (PLAN.md 5): every job run under both methods, untimed.

    python3 compare.py CACHE_NAME A_JSONL B_JSON OUT_JSON

Per job: same verdict; departure second equal; arrival second equal (checked routes); identical legs; and route
validity of EACH method's route under the UNCHANGED checker (`deadline_field.verify.full_check`, which calls
`routing-package/routing/independent.py::check_route` and the closed-footprint replay). A's route legs are rebuilt
from its route feature with `tools/explain_deadlines/plans.py::reconstruct_legs` (hash-checked against route_sha256).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_ROOT, ROOT, load_cache  # noqa: E402

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "harness-2026-11" / "F-3.1"))
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402
from tools.explain_deadlines.plans import reconstruct_legs  # noqa: E402


def main():
    name, a_path, b_path, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    doc = load_cache(name)
    region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
    pm = PacketModel(DATA_ROOT / "graphs" / region / "graph.json", DATA_ROOT / "latest_inputs_try02" / "packets" / region / compact)
    hazard = json.loads((DATA_ROOT / "latest_inputs_try02" / "packets" / region / compact / "HAZARD.json").read_text())
    B = json.loads(b_path.read_text())["results"]
    rows = []
    seen = set()
    for line in a_path.read_text().splitlines():
        a = json.loads(line)
        jid = a["job"]
        if jid in seen:
            continue
        seen.add(jid)
        b = B[jid]
        q = doc["route_checks"][jid]["request"]
        recorded = doc["route_checks"][jid].get("result") or {}
        kw = dict(origin=q["start"]["node_id"], dest=q["destination"]["node_id"], dwell=q["dwell_s"],
                  window=tuple(q["destination_window"]), incurred=q.get("incurred_dose_kj_m2", 0) or 0,
                  peak=q["limits"]["peak_kw_m2"], dose=q["limits"]["dose_kj_m2"])
        a_legs, a_err, a_chk = None, None, None
        if a["verdict"] == "checked_route":
            try:
                rl = reconstruct_legs({"status": "done", "result": {"verdict": a["verdict"], "arrival_s": a["arrival_s"],
                                                                     "departure_s": a["departure_s"],
                                                                     "route": {"properties": a["route_properties"]}}})
                a_legs = [(l["kind"], l.get("edge") or l.get("node"), int(l["start"]), int(l["end"])) for l in rl["legs"]]
                a_chk = full_check(pm, hazard, legs=a_legs, departure=int(a["departure_s"]), **kw)
            except Exception as exc:     # reported, never hidden
                a_err = "%s: %s" % (type(exc).__name__, exc)
        b_chk = None
        if b["verdict"] == "checked_route":
            b_chk = full_check(pm, hazard, legs=[tuple(x) for x in b["legs"]], departure=int(b["departure_s"]), **kw)
        b_legs = [tuple(x) for x in b["legs"]] if b["legs"] else None
        rows.append({
            "job": jid, "offset": int(q["depart_offset_s"]),
            "recorded_verdict": recorded.get("verdict"), "recorded_raw_status": recorded.get("raw_status"),
            "recorded_arrival_s": recorded.get("arrival_s"),
            "a_verdict": a["verdict"], "a_raw_status": a["raw_status"], "a_reason_code": a["reason_code"],
            "a_status": a["status"], "a_error": a["error"],
            "b_verdict": b["verdict"], "b_issue_blocked": b["issue_blocked"],
            "same_verdict": a["verdict"] == b["verdict"],
            "a_departure_s": a["departure_s"], "b_departure_s": b["departure_s"],
            "same_departure_s": a["departure_s"] is not None and int(a["departure_s"]) == int(b["departure_s"]),
            "a_arrival_s": a["arrival_s"], "b_arrival_s": b["arrival_s"],
            "same_arrival_s": (a["arrival_s"] is not None and b["arrival_s"] is not None
                               and int(a["arrival_s"]) == int(b["arrival_s"])) if (a["verdict"] == b["verdict"] == "checked_route") else None,
            "same_legs": (a_legs == b_legs) if (a_legs is not None and b_legs is not None) else None,
            "a_route_rebuild_error": a_err,
            "a_full_check": a_chk, "b_full_check": b_chk,
            "a_route_valid": None if a_chk is None else bool(a_chk["full_policy_ok"]),
            "b_route_valid": None if b_chk is None else bool(b_chk["full_policy_ok"]),
        })
    out.write_text(json.dumps({"cache": name, "a_file": str(a_path), "b_file": str(b_path), "rows": rows}, default=str))
    n = len(rows)
    print(name, "jobs", n, "same_verdict", sum(r["same_verdict"] for r in rows))


if __name__ == "__main__":
    main()
