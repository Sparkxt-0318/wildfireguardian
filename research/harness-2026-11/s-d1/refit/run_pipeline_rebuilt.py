"""Run the FROZEN forecast-v2 pipeline.py on rebuilt covariates and the A1 §3.1 training pool.

pipeline.py is not edited (its sha256 is pinned in S-D9 A1 §3.1 and checked here). Exactly two
things are injected in memory, both required deviations raised with S-D9 before any refit:

  --input-manifest PATH  JSON {relative_path: sha256} for every rebuilt input file (paths relative to
                         the parent of --data-root, as pipeline.Environment expects). It is passed to
                         pipeline.Environment(..., input_sha256=pins) instead of the archive manifest.
                         Every file read is still hash-verified by pipeline.Environment._verify_path.
  --train-events PATH    newline-separated event ids (fit-23 + part-a eligible). It replaces
                         SPLIT["fit"]["us_perimeter_and_kriged"], which command_final/fold/baselines
                         read as the training list. SPLIT.json on disk is not modified.

All other arguments go to pipeline.main() unchanged. A receipt (wrapper + pipeline + protocol shas,
manifest and train-list shas, argv, host, wall time) is written to <--run>/REFIT_RECEIPT_<command>.json.

    python research/harness-2026-11/s-d1/refit/run_pipeline_rebuilt.py \
        --input-manifest PINS.json --train-events TRAIN.txt -- final --data-root ... --perimeters ... \
        --work ... --run ... --variant d4_wind --seed 0 --epochs 3 --hidden 16 --lr 0.003 \
        --samples-per-step 1 --threads 2 --n-samples 1024 --balance \
        --max-fit-intervals-per-fire 0 --intervals-per-epoch 0
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PIPELINE = REPO / "research/forecast-v2/scripts/pipeline.py"
PROTOCOL = REPO / "research/forecast-v2/RUN_PROTOCOL.json"
PINNED = {  # S-D9 A1 §3.1
    PIPELINE: "88d376d219993e72832f21c86df5f90140dc894f876b3bb9cd37688520c92d67",
    PROTOCOL: "c2dce7f7724b1bda6d71391b690904067e6ad46c808276c34f72fd4a1b1e8243",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-manifest", type=Path, required=True)
    ap.add_argument("--train-events", type=Path, required=True)
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    rest = args.rest[1:] if args.rest and args.rest[0] == "--" else args.rest
    for path, expected in PINNED.items():
        if sha256(path) != expected:
            raise SystemExit(f"Pinned source changed: {path.relative_to(REPO)}")
    pins = json.loads(args.input_manifest.read_text())
    if not isinstance(pins, dict) or not pins or not all(isinstance(v, str) and len(v) == 64 for v in pins.values()):
        raise SystemExit("--input-manifest must be a non-empty {relative_path: sha256} object")
    train = [line.strip() for line in args.train_events.read_text().splitlines() if line.strip()]
    if len(set(train)) != len(train):
        raise SystemExit("--train-events contains duplicates")

    spec = importlib.util.spec_from_file_location("pipeline", PIPELINE)
    pipeline = importlib.util.module_from_spec(spec)
    sys.modules["pipeline"] = pipeline
    spec.loader.exec_module(pipeline)

    original_env = pipeline.Environment

    class RebuiltEnvironment(original_env):
        def __init__(self, data_root, cache, input_sha256=None):
            if input_sha256 is not None:
                raise RuntimeError("Unexpected explicit pins from pipeline code")
            super().__init__(data_root, cache, input_sha256=pins)

    pipeline.Environment = RebuiltEnvironment
    pipeline.SPLIT["fit"]["us_perimeter_and_kriged"] = list(train)

    receipt = dict(
        wrapper_sha256=sha256(Path(__file__)), pipeline_sha256=PINNED[PIPELINE], run_protocol_sha256=PINNED[PROTOCOL],
        input_manifest=str(args.input_manifest), input_manifest_sha256=sha256(args.input_manifest),
        input_files=len(pins), train_events_file_sha256=sha256(args.train_events), train_events=len(train),
        argv=rest, host=dict(python=platform.python_version(), platform=platform.platform()),
    )
    try:
        import torch
        receipt["host"]["torch"] = torch.__version__
    except ImportError:
        pass
    sys.argv = [str(PIPELINE)] + rest
    started = time.perf_counter()
    pipeline.main()
    receipt["wall_seconds"] = time.perf_counter() - started
    run = Path(rest[rest.index("--run") + 1])
    run.mkdir(parents=True, exist_ok=True)
    (run / f"REFIT_RECEIPT_{rest[0]}.json").write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(dict(receipt_written=str(run / f"REFIT_RECEIPT_{rest[0]}.json"),
                          wall_seconds=receipt["wall_seconds"])))


if __name__ == "__main__":
    main()
