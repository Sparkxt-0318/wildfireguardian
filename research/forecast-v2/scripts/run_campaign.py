"""Execute the frozen current-host campaign with one exclusive lease per job.

Development/final fitting is a separate invocation from heldout scoring. The
driver never launches heldout scoring until exact selected checkpoint hashes
have been frozen. Existing completed receipts are preserved and checked.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
TASK = REPO.parent.parent
DATA = TASK / "work/data/forecast-v2"
RUN = REPO / "forecast/runs/20261030_perimeter_trained/execution_v3"
EVIDENCE = HERE.parents[1]
VARIANTS = ["base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def job(name, command, expected):
    receipts = EVIDENCE / "executions"
    receipt = receipts / f"{name}.json"
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if old["exit_code"] != 0 or not expected.exists() or old["output_sha256"] != sha(expected):
            raise RuntimeError(f"Existing receipt is failed or output changed: {name}")
        print(f"authenticated completed job {name}", flush=True)
        return
    receipts.mkdir(exist_ok=True)
    log = receipts / f"{name}.log"
    if log.exists() or expected.exists():
        raise FileExistsError(f"Unreceipted output already exists for {name}")
    print(f"waiting for shared numerical lease: {name}", flush=True)
    started_utc = datetime.now(timezone.utc).isoformat()
    lease = TASK / "work/forecast-heavy-lease.json"
    with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (TASK / "work/forecast-pause-before-next-job").exists():
            raise RuntimeError("Coordinator requested resource handoff before the next job")
        source_paths = sorted(p for p in (REPO / "forecast/wildfire").rglob("*")
                              if p.is_file() and p.suffix in (".py", ".json"))
        source_paths += [HERE, HERE.with_name("pipeline.py"), HERE.with_name("audit_fit_coverage.py"),
                         EVIDENCE / "RUN_PROTOCOL.json"]
        source = {str(p.relative_to(REPO)): sha(p) for p in source_paths}
        # A queued job authenticates the exact bytes it will execute after the
        # lease arrives. Preserve content-addressed snapshots for independent replay.
        for path in source_paths:
            snapshot = EVIDENCE / "source_snapshots" / source[str(path.relative_to(REPO))] / path.name
            if not snapshot.exists():
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                snapshot.write_bytes(path.read_bytes())
        record = dict(job=name, pid=os.getpid(), acquired_utc=datetime.now(timezone.utc).isoformat(),
                      status="running", command=command, source_sha256=source)
        write(lease, record)
        print(f"running {name}", flush=True)
        started = time.perf_counter()
        environment = dict(os.environ, PYTHONPATH=str(REPO / "forecast"), OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
                           PYTHONUNBUFFERED="1")
        with log.open("w") as output:
            completed = subprocess.run(command, cwd=REPO, env=environment, stdout=output, stderr=subprocess.STDOUT)
        seconds = time.perf_counter() - started
        record.update(status="complete" if completed.returncode == 0 else "failed", exit_code=completed.returncode,
                      elapsed_seconds=seconds, finished_utc=datetime.now(timezone.utc).isoformat())
        write(lease, record)
        fcntl.flock(lock, fcntl.LOCK_UN)
    result = dict(job=name, command=command, exit_code=completed.returncode,
                  elapsed_seconds=seconds, started_utc=started_utc, finished_utc=record["finished_utc"],
                  source_sha256=source, output=str(expected),
                  output_sha256=sha(expected) if expected.exists() else None,
                  log_sha256=sha(log), host=dict(platform=platform.platform(), python=platform.python_version(),
                                               cpu_count=os.cpu_count()),
                  data_manifest_sha256=sha(DATA / "EXTRACTION_MANIFEST.json"))
    write(receipt, result)
    print(json.dumps(dict(job=name, exit_code=completed.returncode, seconds=seconds)), flush=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Campaign stopped at failed job {name}; preserve outputs before repair")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["fits", "freeze", "baselines", "compare", "heldout"])
    parser.add_argument("--attempt", type=int, default=3)
    args = parser.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    pipeline = HERE.with_name("pipeline.py")
    shared = ["--data-root", str(DATA / "environment"), "--perimeters", str(DATA / "perimeters"),
              "--work", str(DATA / "campaign-work"), "--run", str(RUN),
              "--data-manifest-sha256", sha(DATA / "EXTRACTION_MANIFEST.json"),
              "--epochs", "3", "--seed", "0", "--hidden", "16", "--lr", ".003",
              "--samples-per-step", "1", "--max-fit-intervals-per-fire", "3",
              "--threads", "2", "--n-samples", "1024", "--balance"]
    if args.stage == "fits":
        for fold in ("2020", "2021", "2022"):
            for variant in VARIANTS:
                suffix = "_utc_fixed" if variant == "mixed_base" else ""
                name = f"a{args.attempt:02d}_fold_{fold}_{variant}{suffix}"
                command = [sys.executable, str(pipeline), "fold", *shared, "--fold", fold,
                           "--variant", variant, "--artifact-suffix", suffix]
                job(name, command, RUN / "folds" / f"{variant}_fold{fold}_seed0{suffix}/result.json")
        for variant in VARIANTS:
            command = [sys.executable, str(pipeline), "final", *shared, "--variant", variant,
                       "--max-fit-intervals-per-fire", "0", "--intervals-per-epoch", "0"]
            job(f"a{args.attempt:02d}_final_{variant}", command, RUN / "final" / f"{variant}_seed0/result.json")
        print("FITS_COMPLETE_AWAITING_POSTFIT_AUDIT: run final cache and full-membership audits before freeze", flush=True)
        return
    if args.stage == "freeze":
        import audit_fit_coverage as coverage
        by_variant = {}
        for variant in VARIANTS:
            values = []
            for fold in ("2020", "2021", "2022"):
                suffix = "_utc_fixed" if variant == "mixed_base" else ""
                data = json.loads((RUN / "folds" / f"{variant}_fold{fold}_seed0{suffix}/result.json").read_text())
                values.extend(s["brier"] for s in data["validation_per_fire"].values())
            by_variant[variant] = sum(values) / len(values)
        selected = min(VARIANTS, key=lambda v: (by_variant[v], VARIANTS.index(v)))
        identities = {}
        for variant in VARIANTS:
            path = RUN / "final" / f"{variant}_seed0/checkpoint.pt"
            identities[variant] = dict(path=str(path.relative_to(REPO)), sha256=sha(path))
        if list((RUN / "heldout/cases").glob("*.npz")) or list((RUN / "korean2025/cases").glob("*.npz")):
            raise ValueError("Cannot freeze primary identities after held-out prediction artifacts already exist")
        baseline_receipt = EVIDENCE / "executions/a03_baselines.json"
        baseline_execution = json.loads(baseline_receipt.read_text())
        dilation = RUN / "baselines/dilation_choice.json"
        if baseline_execution["exit_code"] != 0 or baseline_execution["output_sha256"] != sha(dilation):
            raise ValueError("Authenticated fit-only baseline selection is required before freeze")
        baselines = {name: dict(path=str(path.relative_to(REPO)), sha256=sha(path)) for name, path in
                     {"logistic": RUN / "baselines/logistic.pkl", "logistic_parameters": RUN / "baselines/logistic.json",
                      "dilation_choice": dilation}.items()}
        cache_audit_path = EVIDENCE / "CACHE_AUDIT_FINAL.json"
        cache_audit = json.loads(cache_audit_path.read_text())
        if cache_audit["status"] != "PASS_NO_CONSUMED_VALUES_CHANGED" or not cache_audit["producer_unchanged_during_audit"]:
            raise ValueError("Consumed-input cache audit must pass before the model freeze")
        coverage_identity, _ = coverage.verify_coverage(REPO, RUN,
                dict(path=str((EVIDENCE / "FIT_COVERAGE.json").relative_to(REPO)), sha256=sha(EVIDENCE / "FIT_COVERAGE.json")))
        selection = dict(selected_variant=selected, criterion="lowest equal-fire development Brier across three year folds",
                         development_brier=by_variant, checkpoints=identities,
                         baselines=baselines, baseline_execution_sha256=sha(baseline_receipt),
                         fit_coverage=coverage_identity,
                         cache_audit=dict(path=str(cache_audit_path.relative_to(REPO)), sha256=sha(cache_audit_path)),
                         cache_audit_sha256=sha(cache_audit_path),
                         input_manifests_sha256={name: sha(DATA / name) for name in
                            ["EXTRACTION_MANIFEST.json", "BASELINE_TERRAIN_MANIFEST.json", "perimeters/PERIMETER_MANIFEST.json"]},
                         frozen_before_heldout_scoring=True, frozen_utc=datetime.now(timezone.utc).isoformat(),
                         protocol_sha256=sha(EVIDENCE / "RUN_PROTOCOL.json"))
        destination = EVIDENCE / "MODEL_SELECTION.json"
        if destination.exists():
            raise FileExistsError(destination)
        write(destination, selection)
        print(json.dumps(selection, indent=2), flush=True)
    else:
        if args.stage == "heldout" and not (EVIDENCE / "MODEL_SELECTION.json").is_file():
            raise RuntimeError("Exact selected checkpoint identities must be frozen first")
        if args.stage == "compare":
            import pandas as pd
            rows, case_receipts, source_phases = [], [], []
            for index in range(12):
                name = f"a{args.attempt:02d}_compare_case{index:02d}"
                expected_case = RUN / "meanfield_vs_mc" / f"case_{index:02d}" / "meanfield_vs_mc.json"
                job(name, [sys.executable, str(pipeline), "compare", *shared, "--compare-case-index", str(index)], expected_case)
                result = json.loads(expected_case.read_text())
                rows.extend(result["rows"])
                receipt_path = EVIDENCE / "executions" / f"{name}.json"
                receipt = json.loads(receipt_path.read_text())
                source_phases.append(receipt["source_sha256"])
                case_receipts.append(dict(path=str(receipt_path.relative_to(REPO)), sha256=sha(receipt_path)))
            if any(source != source_phases[0] for source in source_phases):
                raise ValueError("Preserve per-case output when comparison producer sources differ")
            if len(rows) != 66:
                raise ValueError("All sixty fixed-horizon and six next-survey comparison rows are required")
            out = RUN / "meanfield_vs_mc"
            pd.DataFrame(rows).to_csv(out / "meanfield_vs_mc.csv", index=False)
            destination = out / "meanfield_vs_mc.json"
            write(destination, dict(rows=rows, checkpoint_sha256=result["checkpoint_sha256"], case_receipts=case_receipts,
                                    host=result["host"], timing="Each fixed-horizon group shares one joint24h MC and MF call"))
            write(EVIDENCE / "executions" / f"a{args.attempt:02d}_compare.json",
                  dict(job=f"a{args.attempt:02d}_compare", exit_code=0, output=str(destination), output_sha256=sha(destination),
                       case_receipts=case_receipts, source_sha256=source_phases[0]))
            print("All12 frozen cutoff jobs and66 horizon rows aggregated", flush=True)
            return
        expected = {"baselines": RUN / "baselines/dilation_choice.json",
                    "compare": RUN / "meanfield_vs_mc/meanfield_vs_mc.json",
                    "heldout": RUN / "report_inputs.json"}[args.stage]
        command = [sys.executable, str(pipeline), args.stage, *shared]
        if args.stage == "baselines":
            command += ["--max-fit-intervals-per-fire", "0"]
        job(f"a{args.attempt:02d}_{args.stage}", command, expected)


if __name__ == "__main__":
    main()
