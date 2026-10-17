"""Accepted-track table of the sealed test, for scripts/precision_review.py sample --population test.

    python scripts/precision_test_accepted.py --point POINT_ID RUN [RUN ...] --control RUN [RUN ...] --out ACCEPTED.parquet

POINT_ID's runs are the selected method's online runs (process --high-precision); the control runs
are the accept_all runs of the same recordings (point_id accept_all). One row per track a run ever
accepted (method_accepted, or revoked), with the columns of verify calibrate's
calibration_accepted.parquet (verify.calibrate.accepted_rows_of): supported is false when the
acceptance frame is motion_unsupported in the run's hp_frames. The recording is the run's clip id (its input file's name).
It reads saved runs only and scores nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows_of_run(run: Path, point_id: str, family: str) -> list[dict]:
    import pandas as pd

    from wfglink.verify.calibrate import accepted_rows_of

    hp = run / "high_precision"
    dec = pd.read_parquet(hp / "hp_decisions.parquet")
    hf = pd.read_parquet(hp / "hp_frames.parquet")
    unsup = set(hf.loc[hf["motion_unsupported"].astype(bool), "frame"].astype(int))
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    clip = Path((summary.get("input") or {}).get("path") or run.name).stem     # data/raw/<clip id>.<ext>
    return accepted_rows_of(dec, unsup, {"point_id": point_id, "family": family, "seed": None, "param": None,
                                         "recording": str(clip), "run_dir": str(run)})


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    import pandas as pd

    from wfglink.verify.calibrate import ACCEPTED_COLUMNS

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--point", required=True, help="the selected point's id (selection.json)")
    ap.add_argument("runs", nargs="+", help="the selected method's runs")
    ap.add_argument("--family", required=True, help="the selected point's family")
    ap.add_argument("--control", nargs="+", required=True, help="accept_all runs of the same recordings")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rows = []
    for r in a.runs:
        rows += rows_of_run(Path(r), a.point, a.family)
    for r in a.control:
        rows += rows_of_run(Path(r), "accept_all", "accept_all")
    df = pd.DataFrame(rows, columns=ACCEPTED_COLUMNS)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out, index=False)
    print(df.groupby(["point_id", "recording"]).size().to_string())
    print(f"-> {a.out} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
