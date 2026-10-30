"""Run actual c651 Monte Carlo trajectory exports on the frozen Korean cutoffs."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(); p.add_argument("--cases", required=True)
    p.add_argument("--data-root", required=True); p.add_argument("--out", required=True)
    a = p.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    checkpoint = ROOT / "forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
    rows, seen = [], set()
    with open("/tmp/wfg/HEAVY.lock", "a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        for case in json.loads(Path(a.cases).read_text()):
            if case["panel"] != "Korean":
                continue
            md = json.loads((Path(case["packet"]) / "NATIVE_METADATA.json").read_text())
            parent = md["construction"]["parent_forecast"]
            event, cutoff = parent["event_id"], parent["cutoff_utc"]
            if (event, cutoff) in seen:
                continue
            seen.add((event, cutoff))
            dest = out / event / cutoff.replace(":", "").replace("-", "")
            if dest.exists():
                raise RuntimeError("EXPORT_OUTPUT_EXISTS:" + str(dest))
            cmd = [sys.executable, "-I", str(ROOT / "experimental/scenario-members/export_v3.py"),
                   "--source-root", str(ROOT / "forecast"), "--data-root", a.data_root,
                   "--checkpoint", str(checkpoint), "--event", event, "--cutoff", cutoff, "--out", str(dest),
                   "--export-version", "3", "--trajectory-count", "1024", "--trajectory-samples", "1024",
                   "--trajectory-seed", "0", "--trajectory-batch-size", "32"]
            start = time.perf_counter(); proc = subprocess.run(cmd, capture_output=True, text=True)
            row = dict(event=event, cutoff=cutoff, output=str(dest), exit_code=proc.returncode,
                       elapsed_s=time.perf_counter() - start, command=cmd, stderr=proc.stderr[-3000:])
            if proc.returncode == 0:
                record = json.loads(next(dest.glob("FORECAST_RECORD_*.json")).read_text())
                row["npz_sha256"] = record["npz_sha256"]
            rows.append(row)
            with (out / "EXECUTIONS.jsonl").open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(json.dumps({k: row[k] for k in ("event", "cutoff", "exit_code", "elapsed_s")}), flush=True)
    result = dict(attempts=len(rows), completed=sum(x["exit_code"] == 0 for x in rows),
                  host=platform.platform(), python=sys.version, seed=0, n_samples=1024,
                  checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), rows=rows)
    (out / "RESULTS.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
