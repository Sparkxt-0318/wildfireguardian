"""Bound WFGC 2 certificates for F-DYN no_reentry/2 packets (NR2_CERT_RULE.md), with per-row checkpoints.

Per packet (gates, NR2_CERT_RULE §2): identity recorded (writer, HAZARD/npz sha); routable_contact_model with the
default guards (refusal -> packet REFUSED, no rows); P1 (raw vs ContactModel 0, HAZARD vs ContactModel 0 except later
ends < 1 us). Per row (§3): build_instance -> generate.certify -> bind_bundle.to_v2 -> verify_bound.verify with the same
graph, packet and request FILES; the row counts only as FULLY_BOUND.

Checkpoint: one JSON line per finished packet gate and per finished row, appended to --out/ROWS.jsonl and flushed.
A restart skips recorded keys (after re-checking the recorded bundle sha256 on disk). Bundles go to --out/bundles.

Usage (from the routing-next worktree root, F-3.2 PYTHONPATH):
  python research/harness-2026-11/F-3.2/xcheck/nr2_certs.py --leo <v3.7 worktree> --requests <requests.py out dir> \
      --out DIR --packets <packet dir relative to --leo> ... [--departures 0 7200] [--gate-only <packet> ...]
"""
import argparse
import hashlib
import json
import sys
import time
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
F32 = HERE.parent
sys.path.insert(0, str(F32))
import bind_bundle  # noqa: E402
import bind_digests  # noqa: E402
import generate  # noqa: E402
import p1_check as P  # noqa: E402
import verify_bound  # noqa: E402
from p1_check import routable_contact_model  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def gate(leo, rel, entry):
    pk = leo / rel
    hz_bytes = (pk / "HAZARD.json").read_bytes()
    hz = json.loads(hz_bytes)
    rec = dict(kind="packet", packet=rel, region=entry["region"], start=entry["start"], horizon_h=entry["horizon_h"],
               variant=entry["variant"], transform=entry.get("transform"), writer=P.writer_identity(hz),
               hazard_sha256=hashlib.sha256(hz_bytes).hexdigest(), npz_sha256=sha(pk / "constructed_arrays.npz"))
    try:
        model = routable_contact_model(str(pk))
    except ValueError as exc:
        return dict(rec, status="REFUSED", reason=str(exc)), None
    Hs = F(int(entry["horizon_h"]) * 3600)
    A = {k: v for k, v in P.from_hazard(hz, Hs).items() if v}
    B = {k: v for k, v in P.from_raw(pk, Hs).items() if v}
    C = {k: v for k, v in ((k, P.merge(v, F(0), Hs)) for k, v in model.cell_intervals.items()) if v}
    d_hc = [k for k in set(A) | set(C) if A.get(k) != C.get(k)]
    end_lt_1us = sum(1 for k in d_hc if len(A.get(k, [])) == len(C.get(k, [])) and all(
        x0 == y0 and x1 >= y1 and x1 - y1 < F(1, 10**6) for (x0, x1), (y0, y1) in zip(A[k], C[k])))
    raw = sum(B.get(k) != C.get(k) for k in set(B) | set(C))
    rec.update(active_cells=len(C), p1_raw_vs_contact=raw, p1_hazard_vs_contact=len(d_hc),
               p1_hazard_later_end_lt_1us=end_lt_1us)
    ok = raw == 0 and len(d_hc) == end_lt_1us
    return dict(rec, status="GATES_PASS" if ok else "P1_FAIL"), (model if ok else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leo", type=Path, required=True)
    ap.add_argument("--requests", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--packets", nargs="+", required=True)
    ap.add_argument("--departures", type=int, nargs="+", default=[0, 7200])
    ap.add_argument("--gate-only", nargs="*", default=[], help="packets run through the gates only (no rows), NR2 rule §5")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True); (a.out / "bundles").mkdir(exist_ok=True)
    log = a.out / "ROWS.jsonl"
    done = {}
    if log.exists():
        for line in log.read_text().splitlines():
            r = json.loads(line)
            done[(r["kind"], r["packet"], r.get("origin"), r.get("departure"))] = r
    entries = {e["out"]: e for e in json.loads((a.leo / "research/harness-2026-11/F-DYN/MANIFEST_v3_7.json").read_text())["entries"]}
    with log.open("a") as fh:
        def put(r):
            fh.write(json.dumps(r) + "\n"); fh.flush()
        for rel in a.packets:
            entry = entries[rel]
            graph_path = a.leo / entry["cmd"][entry["cmd"].index("--graph") + 1]
            gk = ("packet", rel, None, None)
            g, model = (done[gk], None) if gk in done else gate(a.leo, rel, entry)
            if gk not in done:
                put(g)
            print(json.dumps({k: g.get(k) for k in ("packet", "status", "reason", "p1_raw_vs_contact", "p1_hazard_vs_contact")}), flush=True)
            if g["status"] != "GATES_PASS" or rel in a.gate_only:
                continue
            if model is None:
                model = routable_contact_model(str(a.leo / rel))
            graph = json.loads(graph_path.read_text())
            rdir = a.requests / entry["region"] / Path(rel).name
            for rf in sorted(rdir.glob("*.json")):
                origin, dep = rf.stem.rsplit("__d", 1); dep = int(dep)
                if dep not in a.departures:
                    continue
                key = ("row", rel, origin, dep)
                bpath = a.out / "bundles" / ("%s__%s__%s__d%d.v2.wfgc" % (entry["region"], Path(rel).name, origin, dep))
                if key in done and bpath.exists() and sha(bpath) == done[key]["bundle_sha256"]:
                    continue
                t0 = time.perf_counter()
                request = json.loads(rf.read_text())
                inst, _ = build_instance(graph, request, model)
                claim, T, text1, ih, _ = generate.certify(inst)
                text2, I = bind_bundle.to_v2(text1, bind_digests.digests(graph_path, a.leo / rel, rf))
                assert I == ih
                bpath.write_text(text2)
                t1 = time.perf_counter()
                v = verify_bound.verify(bpath, graph_path, a.leo / rel, rf)
                row = dict(kind="row", packet=rel, origin=origin, departure=dep, request_sha256=sha(rf), claim=claim, T=T,
                           I=I, bundle=bpath.name, bundle_sha256=sha(bpath), bundle_bytes=bpath.stat().st_size,
                           verdict=v["verdict"], step=v["step"], detail=v["detail"],
                           certify_s=round(t1 - t0, 2), verify_s=round(time.perf_counter() - t1, 2))
                put(row)
                print(json.dumps({k: row[k] for k in ("origin", "departure", "claim", "T", "verdict", "certify_s", "verify_s")}), flush=True)


if __name__ == "__main__":
    main()
