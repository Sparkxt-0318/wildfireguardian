"""SUPPORT_READ_RULE.md T1/T2: a digest of everything PacketModel derives from a packet, importing PacketModel from
a given F-3.1 tree (so the same script measures 969a2ca2 and the new code).
    python3 deadline_field/pm_digest.py --f31 TREE --graph G --packet P --instance-json I --region R --start S
        --horizon-s HS [--fields] --out OUT"""
import argparse, hashlib, json, sys
from pathlib import Path


def h(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def digest(PacketModel, issue_set, backward, graph, packet, inst, fields):
    pm = PacketModel(graph, packet)
    H = pm.H
    out = {"H": H,
           "phases": h([{str(c): [str(x) for x in v] for c, v in sorted(ph.items())} for ph in pm.pk.phases]),
           "B_router": h([[list(map(str, p)) for p in b] for b in pm.B["router"]]),
           "B_closed": h([[list(map(str, p)) for p in b] for b in pm.B["closed"]]),
           "present_cells": h(sorted(pm.pk.present_cells)), "burning_cells": h(sorted(pm.pk.burning_cells))}
    specs, skipped = {}, 0
    for o in inst["origins"]:
        if o["entry_node"] not in pm.nidx:
            skipped += 1
            continue
        for d in o["destinations"]:
            if d["node"] in pm.nidx:
                specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    origins = sorted({o["entry_node"] for o in inst["origins"] if o["entry_node"] in pm.nidx})
    out["origins_not_in_graph"] = skipped
    inst_parts, issue = {}, {}
    for var in ("cert", "router"):
        for (dn, dw), os_ in sorted(specs.items()):
            I = pm.instance(var, [{"node": dn, "dwell": dw, "window": [0, H]}], origins)
            inst_parts["%s|%s|%s" % (var, dn, dw)] = h({"W": [[list(map(str, p)) for p in w] for w in I.W],
                                                         "A": [[list(map(str, p)) for p in a] for a in I.A],
                                                         "IB": {str(k): [list(map(str, p)) for p in v] for k, v in sorted(I.IB.items())},
                                                         "waitable": I.waitable})
            if fields:
                fld = backward(I)
                for o in sorted(os_):
                    issue["%s|%s|%s|%s" % (var, dn, dw, o)] = [list(map(str, p)) for p in issue_set(fld, pm.nidx[o])]
                del fld
    out["instances"] = h(inst_parts)
    out["n_instances"] = len(inst_parts)
    if fields:
        out["issue_sets"] = h(issue)
        out["n_issue_sets"] = len(issue)
    return out, pm


def main():
    ap = argparse.ArgumentParser()
    for k in ("f31", "graph", "packet", "instance-json", "region", "start", "horizon-s", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--fields", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, a.f31)
    from deadline_field.real import PacketModel
    from deadline_field.core import backward, issue_set
    doc = json.loads(Path(a.instance_json).read_text())
    inst = next(i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == int(a.horizon_s)
                and i["start_tag"] == a.start)
    d, _ = digest(PacketModel, issue_set, backward, a.graph, a.packet, inst, a.fields)
    d["packet_npz_sha256"] = hashlib.sha256((Path(a.packet) / "constructed_arrays.npz").read_bytes()).hexdigest()
    Path(a.out).write_text(json.dumps(d, indent=1))
    print(json.dumps(d))


if __name__ == "__main__":
    main()
