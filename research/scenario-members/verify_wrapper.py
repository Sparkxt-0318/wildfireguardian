"""One bounded real-cutoff equivalence check for the opt-in v3 wrapper."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument("--reference", required=True)
    p.add_argument("--data-root", required=True); p.add_argument("--out", required=True)
    a = p.parse_args(); reference = Path(a.reference)
    rec = json.loads(next(reference.glob("FORECAST_RECORD_*.json")).read_text())
    command = [sys.executable, "-I", str(ROOT / "experimental/scenario-members/export_v3.py"),
               "--source-root", str(ROOT / "forecast"), "--data-root", a.data_root,
               "--checkpoint", str(ROOT / "forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"),
               "--event", rec["event"], "--cutoff", rec["cutoff_utc"], "--out", a.out,
               "--trajectory-count", "1024", "--trajectory-samples", "1024", "--trajectory-seed", "0", "--trajectory-batch-size", "32"]
    with open("/tmp/wfg/HEAVY.lock", "a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    new_record = json.loads(next(Path(a.out).glob("FORECAST_RECORD_*.json")).read_text())
    old_npz, new_npz = reference / rec["npz"], Path(a.out) / new_record["npz"]
    with np.load(old_npz) as old, np.load(new_npz) as new:
        assert set(old.files) == set(new.files)
        same = {k: bool(np.array_equal(old[k], new[k], equal_nan=True) if old[k].dtype.kind == "f" else np.array_equal(old[k], new[k])) for k in old.files}
    receipt = dict(event=rec["event"], cutoff=rec["cutoff_utc"], command=command,
                   exit_code=result.returncode, all_arrays_identical=all(same.values()),
                   arrays_identical=same, npz_bytes_identical=sha(old_npz) == sha(new_npz),
                   old_npz_sha256=sha(old_npz), new_npz_sha256=sha(new_npz),
                   old_exporter_sha256=rec["exporter_sha256"], wrapper_sha256=new_record["exporter_sha256"],
                   script_sha256=sha(__file__), source_identity="Separate exporter hashes; original outputs retain their archived producer identity")
    (Path(__file__).parent / "WRAPPER_EQUIVALENCE.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: receipt[k] for k in ("event", "cutoff", "all_arrays_identical", "npz_bytes_identical")}))
    if not all(same.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
