"""Bind fresh native cases to the sealed job expectations and source commit."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument("--jobs", action="append", required=True)
    p.add_argument("--run", default=str(Path(__file__).parent / "native-panel-20261030"))
    a = p.parse_args(); run = Path(a.run)
    jobs = {sha(f): (f, json.loads(f.read_text())) for folder in a.jobs for f in Path(folder).glob("*.json")}
    rows = []
    for case in json.loads((run / "CASES.json").read_text()):
        source, job = jobs[case["job_sha256"]]
        expectations = job.get("input_sha256", {})
        source_expectations = job.get("source_sha256", {})
        fields = {}
        for key, jobkey in (("graph", "graph_path"), ("request", "request_path"), ("HAZARD.json", "hazard_path")):
            path = Path(case[key]) if key in ("graph", "request") else Path(case["packet"]) / key
            actual = sha(path); expected = expectations.get(jobkey)
            fields[key] = {"actual": actual, "expected": expected,
                           "matches_job": actual == expected if expected is not None else None,
                           "matches_case": actual == case["input_sha256"][key]}
        for name in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz"):
            actual = sha(Path(case["packet"]) / name); expected = source_expectations.get(name)
            fields[name] = {"actual": actual, "expected": expected,
                            "matches_job": actual == expected if expected is not None else None,
                            "matches_case": actual == case["input_sha256"][name]}
        rows.append({"mission": case["mission"], "job_sha256": case["job_sha256"], "fields": fields})
    flat = [f for r in rows for f in r["fields"].values()]
    original = json.loads((run / "RESULTS.json").read_text())["source_sha256"]
    snapshot = sha(run / "ORIGINAL_CONTROLLER.py")
    result = {"missions": len(rows), "pinned_fields": len(flat),
              "job_matches": sum(x["matches_job"] is True for x in flat),
              "job_expectations_unavailable": sum(x["matches_job"] is None for x in flat),
              "mismatches": sum(x["matches_job"] is False or not x["matches_case"] for x in flat),
              "controller_snapshot_matches_execution": original == snapshot,
              "producer_code_commit": "e8a492aef", "actual_reads": ["graph", "request", "REPORT.json", "constructed_arrays.npz"],
              "external_native_source_files_read": [],
              "guard_review": "Original rows all <30 s and <3072 MiB. Final-after-exit admission added after the run; original producer snapshot retained, no pooling with a new campaign.",
              "rows": rows}
    (run / "CUSTODY.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))
    if result["mismatches"] or not result["controller_snapshot_matches_execution"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
