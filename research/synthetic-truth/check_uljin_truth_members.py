"""Complete copied centre checks of the Uljin witness against its own members.

This is a regression, not a withheld-truth experiment or a new optimum proof.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experimental/synthetic-truth/src"))
from wfg_synthetic_truth.frozen_checker import check_route


def main():
    p = argparse.ArgumentParser(); p.add_argument("--run", default=str(ROOT / "research/sipp-routing/native-panel-20261030"))
    a = p.parse_args(); run = Path(a.run)
    cases = json.loads((run / "CASES.json").read_text())
    index, case = next((i, c) for i, c in enumerate(cases) if c["region"] == "uljin_2022" and c["mission"] == "20220304T030000Z_FX1")
    result_path = run / ("%02d_r1_sipp.json" % index)
    witness = json.loads(result_path.read_text())
    graph = json.loads(Path(case["graph"]).read_text()); request = json.loads(Path(case["request"]).read_text())
    hazard = json.loads((Path(case["packet"]) / "HAZARD.json").read_text())
    checks = []
    for member in hazard["members"]:
        checked = check_route(graph, dict(hazard, members=[member]), request, witness["legs"], witness["destination"])
        checks.append({"member": member["id"], **checked})
    out = {"scope": "full journey, frozen cell-centre model, own-members regression",
           "arrival_s": witness["arrival"], "member_checks": len(checks), "passed": sum(c["ok"] for c in checks),
           "false_safe_members": sum(not c["ok"] for c in checks),
           "clairvoyant_optimum_claim": False, "checks": checks,
           "input_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                             [Path(case["graph"]), Path(case["request"]), Path(case["packet"]) / "HAZARD.json", result_path]},
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (Path(__file__).parent / "ULJIN_TRUTH_MEMBERS_REGRESSION.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("arrival_s", "member_checks", "passed", "false_safe_members")}))
    if not all(c["ok"] for c in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
