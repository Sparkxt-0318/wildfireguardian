"""C.2 (multi-hour): the F-3.1 HEADLINE leave-by on one F-DYN no_reentry/2 packet, with and without the heat rule.

NOT RUN in this cut: the F-DYN packets are built by research/harness-2026-11/F-DYN/fdyn/build.py (branch
leo/f-c1-see-before-leave, MANIFEST_v3_7.json) from F-DYN/_data/, which is gitignored and exists only on the host that
built the F-3.1 HEADLINE run. Run this where those packets exist, with the same arguments as
deadline_field/headline.py (see batch/headline_nr2_batch.py):

    python scripts/c2_deadlines_multihour.py --graph G --nr-packet P --instance-json I --region R --start S \
        --horizon-s H --out OUT.json [--lead-scale 1.0]

Leave-by per origin = latest second of the union over its destinations of the feasible departure set, when that set
starts at 0 (deadline_field/headline.py's rule), for variants cert and cert_heat on the no_reentry/2 packet.
The heat constants are the frozen packet values; the F-DYN packets keep the bridge's energy constants but have per-cell
arrival times, so T* (independent of R) is exact for the law while the halo uses the packet spread rate (UNVERIFIED
for F-DYN, where local spread rates differ).
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat.closure import HeatPacketModel, HeatRule, iv  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    for k in ("--graph", "--nr-packet", "--instance-json", "--out"):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--horizon-s", type=int, required=True)
    ap.add_argument("--lead-scale", type=float, default=1.0)
    a = ap.parse_args()
    t0 = time.time()
    inst = json.loads(a.instance_json.read_text())[a.region][a.start]
    rule = HeatRule(lead_scale=a.lead_scale)
    pm = HeatPacketModel(a.graph, a.nr_packet, heat=rule)
    if pm.H != a.horizon_s:
        raise SystemExit("packet horizon %d != --horizon-s %d" % (pm.H, a.horizon_s))
    window = [0, pm.H]
    specs = {}
    for o in inst["origins"]:
        for d in o["destinations"]:
            specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    feas = {}
    for (dn, dw), origins in sorted(specs.items()):
        for var in ("cert", "cert_heat"):
            fld = backward(pm.instance(var, [{"node": dn, "dwell": dw, "window": window}], sorted(origins)))
            for o in origins:
                feas[(var, dn, dw, o)] = issue_set(fld, pm.nidx[o])
    rows = {}
    for o in inst["origins"]:
        e = o["entry_node"]; r = {"entry_node": e, "type": o.get("origin_type")}
        for var in ("cert", "cert_heat"):
            u = iv.normalize([p for d in o["destinations"] for p in feas[(var, d["node"], d["dwell_s"], e)]])
            r["leave_by_" + var] = u[-1][1] if u and u[0][0] == 0 else None
        rows[o["origin_id"]] = r
    moved = [r["leave_by_cert"] - r["leave_by_cert_heat"] for r in rows.values()
             if r["leave_by_cert"] is not None and r["leave_by_cert_heat"] is not None and r["leave_by_cert"] != r["leave_by_cert_heat"]]
    lost = sum(1 for r in rows.values() if r["leave_by_cert"] is not None and r["leave_by_cert_heat"] is None)
    out = {"schema": "kcf-heat.multihour/1", "region": a.region, "start": a.start, "H": pm.H, "heat_rule": rule.describe(),
           "packet": str(a.nr_packet), "origins": len(rows), "moved": len(moved), "lost_route": lost,
           "shift_s": sorted(moved), "wall_s": time.time() - t0, "origins_detail": rows}
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("region", "start", "H", "origins", "moved", "lost_route", "wall_s")}))


if __name__ == "__main__":
    main()
