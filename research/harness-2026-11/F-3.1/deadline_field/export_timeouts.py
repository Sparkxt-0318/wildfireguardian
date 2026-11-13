"""ROUTER-only NO_ROUTE certificates (Thomas's .wfgc format, F-3.2 FORMAT.md v1) for planner jobs the kit left
UNRESOLVED on its time budget (reason_code TIMEOUT). Iris: refusal claims come from the ROUTER-only instance under the
recorded field only (never CERT, never an unknown-support tier). Acceptance (Iris): every certificate accepted by
Thomas's checker plus his per-job inclusion check; any failure is listed, not dropped.

    python3 -m deadline_field.export_timeouts ../../../planner/cache/yeongdeok_2025/*.json --out-dir DIR [--check CHECK_PY]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_core  # noqa: E402
from deadline_field.export import wfgc_no_route  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caches", nargs="+", type=Path)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "routing")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--check", type=Path, help="Thomas's check_py.py (run on every certificate)")
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for cp in a.caches:
        doc = json.loads(cp.read_text())
        region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
        jobs = []
        for key, job in sorted(doc["route_checks"].items()):
            r = job.get("result") or {}
            if r.get("raw_status") == "UNRESOLVED" and r.get("reason_code") == "TIMEOUT":
                q = job["request"]
                jobs.append((key, q["start"]["node_id"], q["destination"]["node_id"], q["dwell_s"],
                             tuple(q["destination_window"]), int(q["depart_offset_s"])))
        if not jobs:
            continue
        pm = PacketModel(a.data_root / "graphs" / region / "graph.json",
                         a.data_root / "latest_inputs_try02" / "packets" / region / compact)
        specs = defaultdict(list)
        for j in jobs:
            specs[(j[2], j[3], j[4])].append(j)
        for (d, dw, w), js in sorted(specs.items(), key=str):
            fld = backward(pm.instance("router", [{"node": d, "dwell": dw, "window": list(w)}], sorted({j[1] for j in js})))
            for key, st, _, _, _, dep in js:
                o = pm.nidx[st]
                row = {"cache": str(cp.relative_to(ROOT)) if cp.is_absolute() else str(cp), "job": key, "start": st,
                       "dest": d, "dwell": dw, "window": list(w), "departure": dep}
                if iv.contains(issue_core(fld, o), dep):
                    row["status"] = "FEASIBLE_IN_ROUTER_FIELD (no certificate)"
                else:
                    txt, ish = wfgc_no_route(fld, o, dep)
                    f = a.out_dir / ("%s__%s__%s.wfgc" % (region, compact, key))
                    f.write_text(txt)
                    row.update(status="NO_ROUTE_CERT", file=f.name, instance_sha256=ish, bytes=len(txt))
                    if a.check:
                        r = subprocess.run([sys.executable, str(a.check), str(f)], capture_output=True, text=True)
                        row["checker_rc"] = r.returncode
                        row["checker_out"] = (r.stdout + r.stderr).strip()[-300:]
                index.append(row)
        print(cp.name, len(jobs), "timeout jobs", flush=True)
    (a.out_dir / "INDEX.json").write_text(json.dumps(index, indent=1))
    st = defaultdict(int)
    for r in index:
        st[r["status"] + ("" if "checker_rc" not in r else " checker_rc=%d" % r["checker_rc"])] += 1
    print(json.dumps(st, indent=1))


if __name__ == "__main__":
    main()
