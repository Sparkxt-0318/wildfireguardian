"""Reconstructed exploratory cohort: DEPARTURE SWEEP of the 20 frozen Korean requests.

NOT the November 106-request rekeyed cohort (unavailable: owner-local only) and NOT its two unproved claims.
Each frozen request is re-issued unchanged except `departure` in OFFSETS (seconds; graph, packet, destinations,
horizon unchanged). Per request:
  * at-issue refusal check (origin cell burning at departure);
  * SIPP + certificate (forward CERT) -> both checkers;
  * independent verdict from the copied frozen sweep (wfg_sipp.adapter.sweep_plan, separate code path) with a wall cap,
    standing in for the November note's "independent model check".
Usage: python cohort.py --out DIR --c-checker PATH [--offsets 0 300 ...] [--sweep-wall 120]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cases  # noqa: E402
import generate  # noqa: E402
from run_panel import at_issue  # noqa: E402

from wfg_scenario_members.contact import ContactModel  # noqa: E402

from p1_check import routable_contact_model  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402
from wfg_sipp.adapter import sweep_plan  # noqa: E402
import derive_instance as DI  # noqa: E402


def check(cmd, path):
    t0 = time.perf_counter()
    p = subprocess.run(cmd + [str(path)], capture_output=True, text=True)
    return p.stdout.strip(), round(time.perf_counter() - t0, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--c-checker", required=True)
    ap.add_argument("--offsets", type=int, nargs="*", default=[0, 300, 600, 900, 1200, 1500, 1800])
    ap.add_argument("--sweep-wall", type=float, default=120.0)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows, seen = [], set()
    for c in cases.korean_cases():
        graph = json.loads(Path(c["graph"]).read_text())
        base = json.loads(Path(c["request"]).read_text())
        model = routable_contact_model(c["packet"])
        for dep in a.offsets:
            if dep > base["horizon"]:
                continue
            req = copy.deepcopy(base); req["departure"] = dep
            key = hashlib.sha256((c["packet"] + json.dumps(req, sort_keys=True)).encode()).hexdigest()
            if key in seen:          # identical (packet, request): count once
                continue
            seen.add(key)
            row = dict(mission=c["mission"], region=c["region"], departure=dep, frozen_departure=base["departure"],
                       request_key=key[:16])
            inst, pg = build_instance(graph, req, model)
            burning, over = at_issue(graph, req, model, pg)
            row["at_issue_refusal"] = bool(burning or over)
            t0 = time.perf_counter()
            # O2 binding (Mira N1): certificate acceptance alone does not bind the embedded instance to the request
            row["o2_diffs"] = len(DI.compare(inst, DI.derive(graph, req, model.cell_intervals)))
            claim, T, text, ih, st = generate.certify(inst)
            row.update(claim=claim, T=T, instance_sha256=ih, certify_s=round(time.perf_counter() - t0, 2),
                       states=st["states"], r_intervals=st["r_intervals"], bundle_bytes=len(text))
            p = out / ("%s__%s__d%d.wfgc" % (c["region"], c["mission"], dep)); p.write_text(text)
            row["py"], row["py_s"] = check([sys.executable, str(HERE / "check_py.py")], p)
            row["c"], row["c_s"] = check([a.c_checker], p)
            t0 = time.perf_counter()
            try:
                sw = sweep_plan(graph, req, model, wall_s=a.sweep_wall)
                row["sweep"] = sw["status"]; row["sweep_raw"] = sw.get("raw_status"); row["sweep_arrival"] = sw.get("arrival")
            except Exception as exc:  # recorded, never silently dropped
                row["sweep"] = "ERROR"; row["sweep_raw"] = repr(exc)[:200]; row["sweep_arrival"] = None
            row["sweep_s"] = round(time.perf_counter() - t0, 2)
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("mission", "departure", "at_issue_refusal", "claim", "T", "py", "c",
                                                  "sweep", "sweep_arrival", "sweep_s")}), flush=True)
    (out / "COHORT.json").write_text(json.dumps(rows, indent=1) + "\n")


if __name__ == "__main__":
    main()
