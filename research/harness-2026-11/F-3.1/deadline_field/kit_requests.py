"""ROUTER-only field verdict for kit route requests (e.g. Priya's F-DYN kit profile, F-3.4 results/fdyn/requests).

Per request: ROUTER-only field (kit router's flame rule; same graph, turns, admission, destination window, horizon;
peak and dose dropped = relaxation) at the request's departure.
  infeasible -> NO_ROUTE .wfgc certificate (checked with Thomas's check_py if given);
  issue-point blocked -> AT_ISSUE (origin point in flame at the departure second under the router rule);
  feasible   -> a field witness (greedy) checked by the UNCHANGED full checker (routing/independent.check_route) and the
                closed replay; PASS = a checked route exists for this request.
    python3 -m deadline_field.kit_requests --graph G --packet P --requests R1.json ... --out OUT.json [--certs DIR --check check_py.py]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_core, witness_greedy  # noqa: E402
from deadline_field.export import wfgc_no_route  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, required=True)
    ap.add_argument("--packet", type=Path, required=True)
    ap.add_argument("--requests", nargs="+", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--certs", type=Path)
    ap.add_argument("--check", type=Path)
    a = ap.parse_args()
    pm = PacketModel(a.graph, a.packet)
    hazard = json.loads((a.packet / "HAZARD.json").read_text())
    hsha = hashlib.sha256((a.packet / "HAZARD.json").read_bytes()).hexdigest()
    rows = []
    for rp in a.requests:
        q = json.loads(rp.read_text())
        o, dep = q["position"]["node"], int(q["departure"])
        d = q["destinations"][0]
        win = d["open_intervals"][0]
        fld = backward(pm.instance("router", [{"node": d["node"], "dwell": d["dwell"], "window": list(win)}], [o]))
        oi = pm.nidx[o]
        row = {"request": rp.name, "request_sha256": hashlib.sha256(rp.read_bytes()).hexdigest(), "hazard_sha256": hsha,
               "origin": o, "dest": d["node"], "departure": dep}
        if iv.contains(iv.normalize(fld.inst.IB.get(oi, [])), dep):
            row["field"] = "AT_ISSUE (origin point in flame at departure, router rule)"
        elif iv.contains(issue_core(fld, oi), dep):
            w = witness_greedy(fld, oi, dep)
            legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), s, e) for k, x, s, e in w[1]]
            chk = full_check(pm, hazard, origin=o, legs=legs, dest=d["node"], dwell=d["dwell"], window=win,
                             departure=dep, incurred=max(q["incurred"].values()), peak=q["budgets"]["peak"],
                             dose=min(q["budgets"]["dose"].values()))
            row.update(field="FEASIBLE", witness_arrival=w[0], full_policy_ok=chk["full_policy_ok"],
                       codes=chk["codes"], closed_replay_clear=chk["closed_and_router_replay_clear"],
                       max_dose=chk["max_dose"])
        else:
            row["field"] = "NO_ROUTE (router-only, relaxation)"
            if a.certs:
                a.certs.mkdir(parents=True, exist_ok=True)
                txt, ish = wfgc_no_route(fld, oi, dep)
                f = a.certs / (rp.stem + ".wfgc")
                f.write_text(txt)
                row.update(cert=f.name, cert_sha256=hashlib.sha256(txt.encode()).hexdigest(), instance_sha256=ish)
                if a.check:
                    r = subprocess.run([sys.executable, str(a.check), str(f)], capture_output=True, text=True)
                    row["checker"] = (r.stdout + r.stderr).strip()[-200:]
        rows.append(row)
        print(json.dumps({k: row[k] for k in row if k in ("request", "field", "full_policy_ok", "codes", "witness_arrival", "checker")}), flush=True)
    a.out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
