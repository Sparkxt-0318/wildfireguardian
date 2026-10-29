"""Export v3 (Contract A) for the 15 frozen Korean windows, replay mode, N = K = 1024 trajectories, seed 0.

Run in the forecast environment (PyTorch CPU). Writes the v3 NPZ files to --out (outside git, they carry the v2 arrays)
and copies the small v3 records into research/scenario-members/data/exports_v3/ with an index of hashes.

  python research/scenario-members/make_exports_v3.py --out /path/to/artifacts/exports_v3
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
from wfg_members import kit  # noqa: E402  (only the panel table and input paths; no frozen import here)

WINDOWS = sorted({(event, tag) for _, tag, event, _ in kit.PANEL})


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()
    root = kit.input_root()
    kit.verify_inputs(root)
    out = Path(a.out)
    rec_dir = HERE / "data" / "exports_v3"
    rec_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for event, tag in WINDOWS:
        dest = out / event
        rec = dest / ("FORECAST_RECORD_%s.json" % tag)
        if not rec.exists():
            cmd = [a.python, "-I", str(REPO / "experimental" / "scenario-members" / "export_v3.py"), "replay",
                   "--v2-dir", str(root / "latest_inputs_try02" / "exports" / event), "--event", event,
                   "--cutoff", kit.cutoff_iso(tag), "--out", str(dest), "--n", str(a.n), "--export-count", str(a.n),
                   "--seed", str(a.seed)]
            print(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip())
        r = json.loads(rec.read_text())
        shutil.copyfile(rec, rec_dir / ("%s_%s.json" % (event, tag)))
        index.append({"event": event, "cutoff": tag, "v3_npz_sha256": r["npz_sha256"], "v2_npz_sha256": r["v2_npz_sha256"],
                      "trajectory_count": r["trajectory_count"], "ignitions_per_trajectory_mean": r["trajectory_statistics"]["ignitions_per_trajectory_mean"],
                      "record_sha256": sha(rec)})
    (rec_dir / "INDEX.json").write_text(json.dumps({"mode": "replay", "n": a.n, "seed": a.seed, "inputs": kit.verify_inputs(root),
                                                    "windows": index}, indent=1) + "\n")


if __name__ == "__main__":
    main()
