"""G2b (kit v2 PLAN.md, Thomas's review): necessary-condition cross-check of v2 decisions against the F-3.2 certified
contact relaxation, which is a lower bound on the full policy (CERTIFICATE_SPEC.md §4a, §5).

Per v2 run folder (JOB.json, RESULT.json, COMPLETE_PROCESS_RECEIPT.json; JOB paths absolute, or relative to --kit-root):
  decision      the decision the worker PUBLISHED (RESULT.decision); else DECISION.json; else the kit's
                decision/<--decision-module, default journey_decision>.decision_from_worker_record. The route is
                RESULT.result if it has a destination, else RESULT.result.checked_incumbent (Z-published routes);
  packet gate   X1 rules 0-2 on the packet (arrays routable, HAZARD cells = ContactModel cells, starts equal, ends within
                1 us); a packet that fails is NOT_APPLICABLE (the relaxation would not describe the stated hazard);
  relaxation    build_instance + generate.certify, accepted by BOTH checkers with the same claim/T.
Rules (the implications hold for journeys departing on integer seconds only, the model boundary of §4a; a route with a
non-integer departure is reported NOT_APPLICABLE_NONINTEGER, never a violation):
  (a) a success status with arrival A requires A >= T_relax;
  (b) relaxation NO_ROUTE => no success status (no published route);
  (c) FULL_MODEL_REFUSAL_PROVEN while the relaxation has a ROUTE is LISTED (not a contradiction: the relaxation is weaker).
These are necessary conditions, not a proof of optimality. Exit status 1 on any violation or checker failure.
Usage: python g2b.py --kit-root R --runs DIR [DIR...] --c-checker PATH --out FILE [--decision-module journey_decision]
C checker: make -C research/harness-2026-11/F-3.2/checker_c  (builds research/harness-2026-11/F-3.2/checker_c/wfgc_check)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))

SUCCESS = ("CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN", "CHECKED_JOURNEY_CENTRE_OPTIMUM", "CHECKED_JOURNEY_FEASIBLE")
REFUSAL = "FULL_MODEL_REFUSAL_PROVEN"


def judge(status, arrival, integral, relax_claim, relax_T):
    """Pure rule function. Returns (verdict, note). verdict in PASS, VIOLATION, LISTED, NOT_APPLICABLE_NONINTEGER,
    NOT_APPLICABLE_STATUS."""
    if status in SUCCESS:
        if not integral:
            return "NOT_APPLICABLE_NONINTEGER", "route departs on a non-integer second (model boundary, spec 4a)"
        if relax_claim == "NO_ROUTE":
            return "VIOLATION", "(b) relaxation proves NO_ROUTE but v2 published a route"
        if F(arrival) < F(relax_T):
            return "VIOLATION", "(a) arrival %s < relaxation optimum %s" % (arrival, relax_T)
        return "PASS", "attains the relaxation optimum" if F(arrival) == F(relax_T) else "(a) arrival >= relaxation optimum"
    if status == REFUSAL:
        if relax_claim == "ROUTE":
            return "LISTED", "(c) full-model refusal while the relaxation has a route at %s" % relax_T
        return "PASS", "refusal consistent with relaxation NO_ROUTE"
    return "NOT_APPLICABLE_STATUS", "status %s makes no route or refusal claim" % status


def _integral(x):
    return F(x).denominator == 1


def route_is_integral(request, route):
    starts = [request.get("departure", 0)] + [l.get("start") for l in (route or {}).get("legs", []) if isinstance(l, dict)]
    return all(s is not None and _integral(s) for s in starts)


def packet_gate(pk, H):
    import numpy as np
    import p1_check as P
    from x1_packets import classify
    from wfg_scenario_members.contact import ContactModel
    from p1_check import routable_contact_model  # noqa: E402
    hz = json.loads((pk / "HAZARD.json").read_text())
    try:
        with np.load(pk / "constructed_arrays.npz", allow_pickle=False) as arr:
            P.require_routable_arrays(arr, pk)
        haz = {k: v for k, v in P.from_hazard(hz, F(H)).items() if v}
        con = {k: v for k, v in ((k, P.merge(v, F(0), F(H))) for k, v in routable_contact_model(pk).cell_intervals.items()) if v}
    except Exception as e:
        return False, "refused: %s" % str(e)[:160], P.writer_identity(hz)
    c = classify(haz, con)
    ok = c["only_hazard"] == c["only_contact"] == c["other"] == 0
    return ok, {k: v for k, v in c.items() if k != "examples"}, P.writer_identity(hz)


def relaxation(graph, request, pk, c_checker):
    import generate as G
    from wfg_scenario_members.contact import ContactModel
    from p1_check import routable_contact_model  # noqa: E402
    from wfg_sipp.frontend import build_instance
    inst, _ = build_instance(graph, request, routable_contact_model(pk))
    claim, T, text, ih, _ = G.certify(inst)
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "r.wfgc"; p.write_text(text)
        py = subprocess.run([sys.executable, str(HERE.parent / "check_py.py"), str(p)], capture_output=True, text=True).stdout.strip()
        cc = subprocess.run([c_checker, str(p)], capture_output=True, text=True).stdout.strip()
    want = "ACCEPT %s %s" % (claim, T)
    return claim, T, ih, (py == cc == want), py, cc


def route_of(sr):
    """The kit's rule (journey_decision.route_of): the primary route if it has a destination, else a checked incumbent
    (Z-published routes live in RESULT.result.checked_incumbent)."""
    if not isinstance(sr, dict):
        return None
    if sr.get("destination") is not None:
        return sr
    inc = sr.get("checked_incumbent")
    return inc if isinstance(inc, dict) and inc.get("destination") is not None else None


def decision_of(run, kit_root, module="journey_decision"):
    """The decision the worker PUBLISHED: RESULT.decision (what v2 claimed) when present; else DECISION.json; else the
    kit's decision/<module>.decision_from_worker_record on the raw records. Returns (status, journey, source)."""
    J = lambda p: json.loads(Path(p).read_text())
    res = J(run / "RESULT.json") if (run / "RESULT.json").exists() else {}
    route = route_of(res.get("result")) or {}
    if isinstance(res.get("decision"), dict) and res["decision"].get("authoritative_status"):
        d = res["decision"]
        j = dict(d.get("journey") or {})
        j.setdefault("arrival", route.get("arrival")); j["legs"] = route.get("legs", [])
        return d["authoritative_status"], j, "RESULT.decision"
    if (run / "DECISION.json").exists():
        d = J(run / "DECISION.json")
        return d["authoritative_status"], d.get("journey") or {}, "DECISION.json"
    sys.path.insert(0, str(kit_root / "decision"))
    JD = __import__(module)
    job, rc = J(run / "JOB.json"), J(run / "COMPLETE_PROCESS_RECEIPT.json")
    dec = JD.decision_from_worker_record(res, rc, job, graph=J(resolve(kit_root, job["graph_path"])),
                                         request=J(resolve(kit_root, job["request_path"])), hazard=J(resolve(kit_root, job["hazard_path"])),
                                         optimality_certificate=res.get("optimality_certificate"), refusal_certificate=res.get("refusal_certificate"))
    return dec["authoritative_status"], dict(dec.get("journey") or {}, legs=route.get("legs", [])), "decision/%s.py" % module


def resolve(root, p):
    """JOB paths may be absolute (v2 workers) or relative to the kit root (frozen runner)."""
    p = Path(p)
    return p if p.is_absolute() else Path(root) / p


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit-root", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--c-checker", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--decision-module", default="journey_decision", help="decision/<module>.py, used only when RESULT has no decision")
    a = ap.parse_args(argv)
    R = Path(a.kit_root)
    rows = []
    for run in map(Path, a.runs):
        job = json.loads((run / "JOB.json").read_text())
        graph = json.loads(resolve(R, job["graph_path"]).read_text()); request = json.loads(resolve(R, job["request_path"]).read_text())
        pk = resolve(R, job["source_directory"])
        status, journey, source = decision_of(run, R, a.decision_module)
        res = json.loads((run / "RESULT.json").read_text()) if (run / "RESULT.json").exists() else {}
        row = dict(run=run.name, status=status, decision_source=source, kit_identity=res.get("kit_identity"),
                   arrival=str(journey.get("arrival")) if journey.get("arrival") is not None else None)
        ok, gate, writer = packet_gate(pk, int(F(request["horizon"])))
        row.update(writer=writer, packet_gate=gate)
        if not ok:
            row.update(verdict="NOT_APPLICABLE_PACKET_INCONSISTENT"); rows.append(row); continue
        claim, T, ih, accepted, py, cc = relaxation(graph, request, pk, a.c_checker)
        row.update(relax_claim=claim, relax_T=T, relax_instance_sha256=ih, relax_checkers_accept=accepted)
        if not accepted:
            row.update(verdict="CHECKER_FAILURE", note="py=%r c=%r" % (py, cc)); rows.append(row); continue
        integral = route_is_integral(request, journey) if status in SUCCESS else True
        row["verdict"], row["note"] = judge(status, journey.get("arrival"), integral, claim, T)
        rows.append(row)
        print(json.dumps(row, default=str), flush=True)
    Path(a.out).write_text(json.dumps(rows, indent=1, default=str) + "\n")
    bad = [r for r in rows if r["verdict"] in ("VIOLATION", "CHECKER_FAILURE")]
    print(json.dumps({"runs": len(rows), "violations": len(bad),
                      "by_verdict": {v: sum(r["verdict"] == v for r in rows) for v in sorted({r["verdict"] for r in rows})}}))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
