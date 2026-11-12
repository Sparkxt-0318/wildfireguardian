"""D2 refit wrapper (A1 §3.1 item 21): the frozen forecast-v2 recipe with a loss-only deviation.

It follows Marcus's ``research/harness-2026-11/s-d1/refit/run_pipeline_rebuilt.py`` (6dcf3f9) exactly for the
shared recipe:
* pinned ``pipeline.py`` and ``RUN_PROTOCOL.json`` sha256, checked before anything runs;
* rebuilt-input pins injected through ``Environment(input_sha256=...)``;
* the A1 training list injected in place of ``SPLIT["fit"]["us_perimeter_and_kriged"]``;
* a receipt in ``<--run>/REFIT_RECEIPT_<command>_<variant>.json``.
``pipeline.py`` and ``survival.py`` are not edited.

D2 deviation, by variant:

* ``--d2 nll`` (``d2_nll_rebuilt``): inside ``survival.fit_mean_field`` only, the endpoint loss
  ``survival.endpoint_brier`` (sum w (p - y)^2, sum w) is replaced by a smooth Bernoulli NLL with the same
  return contract: ``(sum w * -[y log(p + eps) + (1 - y) log(1 - p + eps)], sum w)`` with eps = 1e-7. The
  weights, the prevalence scaling, the optimiser and the schedule are unchanged. The original function is
  restored after fitting, so validation and scoring paths still use Brier. eps is added, not used as a clamp, so
  the gradient stays nonzero for p < eps (``survival.clipped_nll`` clamps and would zero it exactly in the
  near-zero tail that P-D2 is about).
* ``--d2 bracket`` (``d2_bracket_rebuilt``): not implemented yet. Its E-step cost must be timed first (Iris).

    python run_d2.py --d2 nll --input-manifest PINS.json --train-events TRAIN.txt -- final --data-root ... \\
        --perimeters ... --work ... --run ... --variant d4_wind --seed 0 --epochs 3 --hidden 16 --lr 0.003 \\
        --samples-per-step 1 --threads 2 --n-samples 1024 --balance --max-fit-intervals-per-fire 0 \\
        --intervals-per-epoch 0
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
SURVIVAL = REPO / "forecast/wildfire/survival.py"
PINNED = {  # S-D9 A1 §3.1
    PIPELINE: "88d376d219993e72832f21c86df5f90140dc894f876b3bb9cd37688520c92d67",
    PROTOCOL: "c2dce7f7724b1bda6d71391b690904067e6ad46c808276c34f72fd4a1b1e8243",
}
NLL_EPS = 1e-7


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def endpoint_nll(probability, label, weight, mask):
    """Smooth Bernoulli NLL with ``survival.endpoint_brier``'s contract: (sum w * nll, sum w) over masked cells."""
    import torch
    use = mask & torch.isfinite(probability)
    if bool((use & (~torch.isfinite(label) | ((label != 0) & (label != 1)))).any()):
        raise ValueError("Scored endpoint labels must be binary and finite")
    if bool((use & (~torch.isfinite(weight) | (weight < 0))).any()):
        raise ValueError("Scored weights must be finite and nonnegative")
    p = torch.where(use, probability, torch.full_like(probability, 0.5))
    y = torch.where(use, label, torch.zeros_like(label))
    w = torch.where(use, weight, torch.zeros_like(weight))
    nll = -(y * torch.log(p + NLL_EPS) + (1 - y) * torch.log1p(-p + NLL_EPS))
    return (w * nll).sum(), w.sum()


def install_nll(pipeline):
    """Swap endpoint_brier -> endpoint_nll inside fit_mean_field calls only."""
    from wildfire import survival
    original_fit = pipeline.fit_mean_field
    original_loss = survival.endpoint_brier

    def fit_mean_field_nll(*a, **kw):
        survival.endpoint_brier = endpoint_nll
        try:
            return original_fit(*a, **kw)
        finally:
            survival.endpoint_brier = original_loss

    pipeline.fit_mean_field = fit_mean_field_nll


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--d2", choices=["nll", "bracket"], required=True)
    ap.add_argument("--input-manifest", type=Path, required=True)
    ap.add_argument("--train-events", type=Path, required=True)
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    if args.d2 == "bracket":
        raise SystemExit("d2_bracket_rebuilt is not implemented yet (E-step cost to be timed first)")
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
    install_nll(pipeline)

    receipt = dict(
        candidate=f"d2_{args.d2}_rebuilt", wrapper_sha256=sha256(Path(__file__)),
        pipeline_sha256=PINNED[PIPELINE], run_protocol_sha256=PINNED[PROTOCOL], survival_sha256=sha256(SURVIVAL),
        loss="smooth Bernoulli NLL on mean-field p(t2), eps=1e-7 (additive, not a clamp); same weights and "
             "prevalence scaling; Brier restored outside fit_mean_field",
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
    out = run / f"REFIT_RECEIPT_{rest[0]}_d2_{args.d2}.json"
    out.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(dict(receipt_written=str(out), wall_seconds=receipt["wall_seconds"])))


if __name__ == "__main__":
    main()
