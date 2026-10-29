"""Model-mode export v3 at a multi-hour horizon (default 6 h) for the 15 Korean cutoffs, on the REAL forecast data tree.
Needed by the extended-horizon exploratory panel (research/synthetic-truth/run_extended_panel.py --mode real). Not run on
this host yet: the environmental rasters (--data-root) were not available. Each window is written to OUT/<event>/<tag>/
(the frozen v2 exporter output sits in its v2_staging/ subfolder; the record says whether it equals the frozen v2 export).

  python research/scenario-members/make_exports_v3_model.py --data-root DATA --out EXPORTS6 [--hours 6 --n 1024]
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
from wfg_members import kit  # noqa: E402

CHECKPOINT = REPO / "forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hours", type=int, default=6)
    ap.add_argument("--n", type=int, default=1024)
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()
    for event, tag in sorted({(e, t) for _, t, e, _ in kit.PANEL}):
        dest = Path(a.out) / event / tag
        if (dest / ("FORECAST_RECORD_%s.json" % tag)).exists():
            continue
        cmd = [a.python, "-I", str(REPO / "experimental/scenario-members/export_v3.py"), "model", "--source-root", str(REPO / "forecast"),
               "--data-root", a.data_root, "--checkpoint", str(CHECKPOINT), "--event", event, "--cutoff", kit.cutoff_iso(tag),
               "--out", str(dest), "--n", str(a.n), "--export-count", str(a.n), "--hours", str(a.hours)]
        print(" ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
