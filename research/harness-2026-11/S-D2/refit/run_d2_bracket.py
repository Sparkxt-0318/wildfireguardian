"""d2_bracket_rebuilt wrapper (A1 §3.1 item 21). It is separate from run_d2.py, whose sha is pinned for d2_nll.

Same shared recipe and guards as ``run_d2.py`` and Marcus's ``run_pipeline_rebuilt.py``:
* pinned pipeline.py and RUN_PROTOCOL.json, checked before anything runs;
* rebuilt-input pins through ``Environment(input_sha256=...)``;
* the A1 training list in place of ``SPLIT["fit"]["us_perimeter_and_kriged"]``;
* a receipt.
The deviation: ``pipeline.fit_mean_field`` is replaced in memory by ``d2_bracket.fit_bracket``, an EM over latent
arrival times within survey brackets that changes both the loss and the fitting procedure. The architecture,
hyperparameters, data, seed and scoring path (mean-field forecast) are unchanged. pipeline.py and survival.py are
not edited. ``--sweeps`` and ``--step`` (E-step settings) are recorded in the receipt and must be frozen with this
file's sha before any run.

    python run_d2_bracket.py --input-manifest PINS.json --train-events TRAIN.txt --sweeps 2 --step 0.25 -- final ...
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PIPELINE = REPO / "research/forecast-v2/scripts/pipeline.py"
PROTOCOL = REPO / "research/forecast-v2/RUN_PROTOCOL.json"
SURVIVAL = REPO / "forecast/wildfire/survival.py"
PINNED = {
    PIPELINE: "88d376d219993e72832f21c86df5f90140dc894f876b3bb9cd37688520c92d67",
    PROTOCOL: "c2dce7f7724b1bda6d71391b690904067e6ad46c808276c34f72fd4a1b1e8243",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-manifest", type=Path, required=True)
    ap.add_argument("--train-events", type=Path, required=True)
    ap.add_argument("--sweeps", type=int, default=2)
    ap.add_argument("--step", type=float, default=0.25)
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
    pipeline = load("pipeline", PIPELINE)
    bracket = load("d2_bracket", HERE / "d2_bracket.py")
    original_env = pipeline.Environment

    class RebuiltEnvironment(original_env):
        def __init__(self, data_root, cache, input_sha256=None):
            if input_sha256 is not None:
                raise RuntimeError("Unexpected explicit pins from pipeline code")
            super().__init__(data_root, cache, input_sha256=pins)

    pipeline.Environment = RebuiltEnvironment
    pipeline.SPLIT["fit"]["us_perimeter_and_kriged"] = list(train)
    pipeline.fit_mean_field = functools.partial(bracket.fit_bracket, sweeps=args.sweeps, step=args.step)
    receipt = dict(
        candidate="d2_bracket_rebuilt", wrapper_sha256=sha256(Path(__file__)),
        d2_bracket_sha256=sha256(HERE / "d2_bracket.py"), pipeline_sha256=PINNED[PIPELINE],
        run_protocol_sha256=PINNED[PROTOCOL], survival_sha256=sha256(SURVIVAL),
        procedure="EM over latent arrival times within survey brackets; E-step Gibbs with kernels detached; "
                  "M-step complete-data log-likelihood (additive eps 1e-7); same optimiser, schedule, weights, "
                  "prevalence scaling, D4 augmentation",
        e_step=dict(sweeps=args.sweeps, step_hours=args.step),
        arrival_raster_validity="not used (label validity from perimeter states, A1 §4.1 rule 3)",
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
    out = run / f"REFIT_RECEIPT_{rest[0]}_d2_bracket.json"
    out.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(dict(receipt_written=str(out), wall_seconds=receipt["wall_seconds"])))


if __name__ == "__main__":
    main()
