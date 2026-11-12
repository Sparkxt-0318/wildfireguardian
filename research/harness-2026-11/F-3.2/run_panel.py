"""Emit certificates for the 20 Korean native-panel missions and check them with the available checkers.

Usage: python run_panel.py --out DIR [--c-checker PATH]
Bundles (.wfgc, tens of MB) go to DIR, outside git. A summary JSON is printed and written to DIR/SUMMARY.json.
"""
from __future__ import annotations

import argparse
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

from wfg_scenario_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402

RECORDED = HERE.parents[2] / "research/sipp-routing/native-panel-20261030/EXECUTIONS.jsonl"


def recorded_outcomes():
    out = {}
    for line in RECORDED.read_text().splitlines():
        r = json.loads(line)
        if r["method"] == "sipp" and r["panel"] == "Korean":
            out.setdefault(r["mission"], set()).add((r["status"], r["arrival"], r.get("raw_status")))
    return out


def at_issue(graph, request, model, pg):
    """The frontend's two at-issue refusal conditions, evaluated directly (not a search result)."""
    from fractions import Fraction as F
    dep = F(request["departure"])
    cell = pg.node_cells[pg.nidx[request["position"]["node"]]]
    burning = [(b, e) for b, e in model.cell_intervals.get(cell, ()) if dep < e and dep >= b]
    over = {m: (request["incurred"][m], request["budgets"]["dose"][m]) for m in request["incurred"]
            if F(request["incurred"][m]) > F(request["budgets"]["dose"][m])}
    return burning, over


def run_checker(cmd, path):
    t0 = time.perf_counter()
    p = subprocess.run(cmd + [str(path)], capture_output=True, text=True)
    return {"exit": p.returncode, "out": p.stdout.strip(), "wall_s": round(time.perf_counter() - t0, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--c-checker")
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rec = recorded_outcomes()
    rows = []
    for c in cases.korean_cases():
        if a.only and c["mission"] not in a.only:
            continue
        graph = json.loads(Path(c["graph"]).read_text())
        request = json.loads(Path(c["request"]).read_text())
        model = ContactModel.from_packet(c["packet"])
        row = dict(mission=c["mission"], region=c["region"], supported=getattr(model, "supported", True) is True)
        t0 = time.perf_counter()
        inst, pg = build_instance(graph, request, model)
        burning, over = at_issue(graph, request, model, pg)
        row["at_issue"] = {"origin_burning": [[str(b), str(e)] for b, e in burning], "dose_over_budget": over}
        claim, T, text, ih, stats = generate.certify(inst)
        row.update(claim=claim, T=T, instance_sha256=ih, generate_wall_s=round(time.perf_counter() - t0, 3), **stats)
        row["recorded_sipp"] = sorted(map(list, rec.get(c["mission"], set())), key=str)
        path = out / (c["region"] + "__" + c["mission"] + ".wfgc")
        path.write_text(text)
        pk = Path(c["packet"])
        hz = json.loads((pk / "HAZARD.json").read_text())
        build = json.loads((pk / "BUILD_SUMMARY.json").read_text())
        prov = {"schema": "wfg.cert.provenance/1", "bundle": path.name, "instance_sha256": ih,
                "scope": "integer-second contact relaxation of the given hazard; see CERTIFICATE_SPEC.md section 5",
                "inputs_sha256": {"graph": cases.sha(c["graph"]), "request": cases.sha(c["request"]),
                                  **{n: cases.sha(pk / n) for n in ("HAZARD.json", "constructed_arrays.npz", "REPORT.json",
                                                                    "NATIVE_METADATA.json", "BUILD_SUMMARY.json")}},
                "hazard_extent": {"grid": hz["grid"], "dt": hz["dt"], "valid_from": hz["valid_from"],
                                  "valid_until": hz["valid_until"], "members": len(hz["members"])},
                "hazard_premises": {"model_supported": row["supported"],
                                    "raw_input_summary": build.get("raw_input_summary"),
                                    "max_flux_kW_m2": build.get("max_flux_kW_m2")}}
        Path(str(path) + ".json").write_text(json.dumps(prov, indent=1) + "\n")
        row["provenance"] = prov
        row["bundle_bytes"] = len(text)
        row["bundle_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        row["check_py"] = run_checker([sys.executable, str(HERE / "check_py.py")], path)
        if a.c_checker:
            row["check_c"] = run_checker([a.c_checker], path)
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("mission", "claim", "T", "states", "r_intervals", "bundle_bytes")}
                         | {"py": row["check_py"]["out"], "c": row.get("check_c", {}).get("out")}), flush=True)
    (out / "SUMMARY.json").write_text(json.dumps(rows, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
