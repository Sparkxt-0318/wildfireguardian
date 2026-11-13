"""Summarise a merged NR2 run (NR2_CERT_RULE §4, erratum 1, note 2) into one results JSON.

Usage: python nr2_summary.py MERGED_ROWS.jsonl[.gz] --packets <list file> --gate-only-substr _h5_envelope_central --out RESULT.json
Per packet: gate record, rows, ROUTE/NO_ROUTE, verdict counts, PASS iff GATES_PASS and every row FULLY_BOUND and the
row count equals the request count recorded at certification. Gate-only packets: gate record only; any rows they have
(erratum 1) are listed as out of scope, data only.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

LABEL = ("F-DYN no_reentry/2 (person-facing default): relaxation certificates, bound and verified by verify_bound "
         "(both checkers, structure, O2); contact only, no radiation")
WAITING_S = ("The trip starts at the stated time. Once moving, a stop is allowed only at a road dead end (a graph "
             "dead-end node), which may be a short detour off the route; waiting is not allowed at any other node, "
             "including the start unless it is itself a dead end. Other departure times are separate results.")
BURNSET = ("envelope_burnset: sound relative to the final mapped burn set; burn set = kriged footprint ∪ FIRMS ∪ "
           "buffered AHI (16,176 cells; 10,955 kriged, 4,940 AHI-buffer-only, 281 FIRMS-only); single implementation, "
           "not independently checked")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rows")
    ap.add_argument("--packets", required=True)
    ap.add_argument("--gate-only-substr", default="_h5_envelope_central")
    ap.add_argument("--requests", type=Path, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw = Path(a.rows).read_bytes()
    text = gzip.decompress(raw).decode() if a.rows.endswith(".gz") else raw.decode()
    recs = [json.loads(l) for l in text.splitlines()]
    packets = Path(a.packets).read_text().split()
    gates = {r["packet"]: r for r in recs if r["kind"] == "packet"}
    rows = collections.defaultdict(list)
    for r in recs:
        if r["kind"] == "row":
            rows[r["packet"]].append(r)
    keys = [(r["packet"], r["origin"], r["departure"]) for r in recs if r["kind"] == "row"]
    assert len(keys) == len(set(keys)), "duplicate row keys"
    out = {"label": LABEL, "waiting_rule_form_S": WAITING_S, "departures_s": [0, 7200],
           "departures_note": "0 s and 7200 s are separate results, never a leave-by window",
           "rule": "NR2_CERT_RULE.md (+ erratum 1, note 2)", "rows_file_sha256": hashlib.sha256(raw).hexdigest(),
           "packets": [], "out_of_scope": [],
           "uncertified": "the other 360 certifiable packets of MANIFEST_v3_7 no_reentry/2 carry no F-3.2 certificate"}
    for rel in packets:
        g = gates.get(rel)
        name = rel.split("/")[-1]
        rs = rows.get(rel, [])
        gate_only = a.gate_only_substr in name
        base = {"packet": rel, "region": g and g["region"], "variant": g and g["variant"], "gate": g and {
            k: g.get(k) for k in ("status", "reason", "transform", "writer", "hazard_sha256", "npz_sha256", "active_cells",
                                  "p1_raw_vs_contact", "p1_hazard_vs_contact", "p1_hazard_later_end_lt_1us")}}
        if gate_only:
            out["packets"].append(dict(base, role="gate only (NR2 §5)", rows_reported=0))
            if rs:
                out["out_of_scope"].append({
                    "packet": rel, "rows": len(rs), "reason": "erratum 1: the v3.7 no_reentry/2 envelope is routable "
                    "by design (NOREENTRY_RULE.md §2/§5), so the gates passed and rows were certified before "
                    "--gate-only existed; data only, not results; label limited to the manifest's 'BRACKET-START, "
                    "NOT A LOWER BOUND'",
                    "claims": dict(collections.Counter(r["claim"] for r in rs)),
                    "verdicts": dict(collections.Counter(r["verdict"] for r in rs))})
            continue
        region = g["region"] if g else None
        n_req = len([f for f in (a.requests / region / name).glob("*.json")
                     if int(f.stem.rsplit("__d", 1)[1]) in (0, 7200)]) if region else None
        verdicts = collections.Counter(r["verdict"] for r in rs)
        claims = {str(d): dict(collections.Counter(r["claim"] for r in rs if r["departure"] == d)) for d in (0, 7200)}
        ok = bool(g) and g["status"] == "GATES_PASS" and verdicts == {"FULLY_BOUND": n_req} and len(rs) == n_req
        entry = dict(base, role="certified", requests=n_req, rows=len(rs), verdicts=dict(verdicts),
                     claims=dict(collections.Counter(r["claim"] for r in rs)), claims_by_departure=claims,
                     not_fully_bound=[{k: r[k] for k in ("origin", "departure", "verdict", "step", "detail")}
                                      for r in rs if r["verdict"] != "FULLY_BOUND"],
                     certify_s_total=round(sum(r["certify_s"] for r in rs), 1),
                     verify_s_total=round(sum(r["verify_s"] for r in rs), 1), result="PASS" if ok else "FAIL")
        if g and g["variant"] == "envelope_burnset":
            entry["variant_label"] = BURNSET
        out["packets"].append(entry)
    cert = [p for p in out["packets"] if p["role"] == "certified"]
    out["summary"] = {"certified_packets": len(cert), "pass": sum(p["result"] == "PASS" for p in cert),
                      "rows": sum(p["rows"] for p in cert),
                      "fully_bound": sum(p["verdicts"].get("FULLY_BOUND", 0) for p in cert),
                      "ROUTE": sum(p["claims"].get("ROUTE", 0) for p in cert),
                      "NO_ROUTE": sum(p["claims"].get("NO_ROUTE", 0) for p in cert),
                      "gate_only_packets": len(out["packets"]) - len(cert),
                      "out_of_scope_rows": sum(o["rows"] for o in out["out_of_scope"])}
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out["summary"]))


if __name__ == "__main__":
    main()
