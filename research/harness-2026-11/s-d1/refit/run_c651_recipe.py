"""Run the c651 recipe (forecast/wildfire/prepare.py then train.py) with or without the A1 §3.2
full-rectangle validity change, leaving prepare.py, train.py and data.py byte-unchanged (sha-checked).

The arm's one change: inside the event rectangle, a cell with NO arrival value is a KNOWN cell that never
burns in the window. It is injected in memory at the two places that read the arrival raster:
  * prepare.py:862 (``rasterio.open(root / event["arrival_path"])`` in prepare_event), and
  * data.py ``WildfireSequenceDataset._read`` for ``arrival_time_hours.tif`` (label values and validity).
Both see missing arrival values replaced by NEVER = 1e9 hours, marked valid. Consequences, with no other
line touched:
  * prepare.py's k x k eligibility (``minimum_filter(finite, cval=0)``) then requires only that the window
    lie inside the rectangle (edge windows are still excluded by cval=0);
  * those cells are at risk for the whole window, never positive, and enter the negative strata;
  * data.py's labels for them are 0 (never burned) with label validity True.
Cells WITH an arrival value are untouched. ``--fullvalid off`` is the comparator: identical wrapper with
the injection disabled.

    python research/harness-2026-11/s-d1/refit/run_c651_recipe.py --fullvalid on|off -- prepare \
        --output-dir ... --data-root ... --kernel-size 9 --contact-negatives-per-event 5000 \
        --no-contact-negatives-per-event 2000 --seed 7 [--split-policy ... --split-seed 7 ...]

    python research/harness-2026-11/s-d1/refit/run_c651_recipe.py --fullvalid on|off -- candidate \
        --cache PREPARED --output OUT --epochs 512 --finalist-epochs 4096 --learning-rates 0.01 0.05 0.1 \
        --schedules constant warmup_cosine --seed 7 --device cpu --threads N

Training stage (A1 §3.2 decision (b)). c651 came from the categorical-balanced benchmark run by
wildfire.search.MultiscaleSearch (276 candidates incl. neural_mixed; learning rates 0.01/0.05/0.1). It was
NOT a finalist (runs/20261010_categorical_balanced_benchmark/finalist_selection.json): its checkpoint is the
validation-best epoch (5) of its 512-epoch candidate fit. The ``candidate`` stage therefore runs exactly the
candidate loop of MultiscaleSearch.train_search for the single candidate mixed_3_5_7_9_02_lr0.1_warmup_cosine
(same setup, native k=9 cohort, categorical balance, normalisation, global-rate initialisation, tensors and
fit_candidate with --epochs), using MultiscaleSearch's own functions. fit_candidate reseeds per candidate,
so restricting the plan does not change the candidate's training. The finalist extension is not run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "forecast"))
PINNED = {  # sha256 at the time of writing; any change refuses to run
    REPO / "forecast/wildfire/prepare.py": "e2c704333974ca3cb05e020075895ae50a7c38bcb7244640e5eaec9d95c62dd0",
    REPO / "forecast/wildfire/train.py": "9c8a62150589b7d7785205e160f32e6a0d209dd4c01de27736c38d4244244b0e",
    REPO / "forecast/wildfire/data.py": "8fb447ab28475e1909290e3b5af7717daace02db92655ff6f049861118d63230",
    REPO / "forecast/wildfire/search.py": "136442fa7116938c1a895ba4d4be28f1a81547659b8d3efb3f0a194f3b0537b4",
}
CANDIDATE_ID = "mixed_3_5_7_9_02_lr0.1_warmup_cosine"
NEVER = 1.0e9
ARRIVAL_NAME = "arrival_time_hours.tif"


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class _ArrivalSource:
    """Delegating rasterio dataset whose masked/non-finite arrival values read as NEVER and valid."""

    def __init__(self, source):
        self._source = source

    def read(self, *args, **kwargs):
        a = self._source.read(*args, **kwargs)
        if isinstance(a, np.ma.MaskedArray):
            data = np.where(np.ma.getmaskarray(a) | ~np.isfinite(a.data), NEVER, a.data).astype(a.dtype)
            return np.ma.MaskedArray(data, mask=np.zeros(data.shape, dtype=bool))
        return np.where(np.isfinite(a), a, NEVER).astype(a.dtype)

    def __getattr__(self, name):
        return getattr(self._source, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._source.close()
        return False


class _RasterioProxy:
    def __init__(self, module):
        self._module = module

    def open(self, path, *args, **kwargs):
        source = self._module.open(path, *args, **kwargs)
        return _ArrivalSource(source) if Path(path).name == ARRIVAL_NAME else source

    def __getattr__(self, name):
        return getattr(self._module, name)


def install_fullvalid():
    import wildfire.data as data
    import wildfire.prepare as prepare
    prepare.rasterio = _RasterioProxy(prepare.rasterio)
    original = data.WildfireSequenceDataset._read

    def _read(self, path, e, bands, window, out_dtype="float32"):
        values, valid = original(self, path, e, bands, window, out_dtype)
        if Path(path).name == ARRIVAL_NAME:
            values = np.where(valid, values, NEVER).astype(values.dtype)
            valid = np.ones_like(valid)
        return values, valid

    data.WildfireSequenceDataset._read = _read


def run_candidate(argv):
    """Candidate stage of MultiscaleSearch.train_search (search.py) for CANDIDATE_ID only."""
    import numpy as np
    import torch
    from wildfire import search as S
    MS = S.MultiscaleSearch
    sys.argv = ["wildfire.search"] + ["train"] + argv
    args = MS.parser().parse_args()
    if args.device == "auto":
        raise SystemExit("pass an explicit --device")
    protocol = MS.setup_from_args(args)
    chosen = [c for c in protocol["candidates"] if c["id"] == CANDIDATE_ID]
    if len(chosen) != 1:
        raise SystemExit(f"{CANDIDATE_ID} is not in the generated plan; check --learning-rates/--schedules")
    candidate = chosen[0]
    metadata = json.loads((args.cache / "metadata.json").read_text())
    train_base, validation_base = (MS.load_split(args.cache, name, metadata) for name in ("train", "validation"))
    S.validate_partition_disjointness({"train": train_base, "validation": validation_base}, metadata)
    device = S.choose_device(args.device)
    torch.set_num_threads(args.threads)
    k = candidate["kernel_size"]
    if candidate["family"] not in MS.SPATIAL_FAMILIES:
        raise SystemExit("unexpected non-spatial family")
    ti, vi = S.native_indices(train_base, k), S.native_indices(validation_base, k)
    train_data, val_data = S.crop_split(train_base, k, ti), S.crop_split(validation_base, k, vi)
    effective, balance_audit = MS.fit_native_balance(train_data, metadata, protocol, args.output)
    mean, std = S.fit_normalization(train_data, metadata=metadata)
    global_baseline = S.fit_global_rate(train_data)
    tci = np.flatnonzero(np.isin(ti, S.common_indices(train_base)))
    ci = np.flatnonzero(np.isin(vi, S.common_indices(validation_base)))
    tensors = MS.tensor_data(train_data, mean, std, "legacy", device, tci, optimization_weight=effective,
                             categorical_balance=balance_audit)
    vt = MS.tensor_data(val_data, mean, std, "legacy", device, ci)
    summary = MS.fit_candidate(candidate, train_data, val_data, tensors, vt, mean, std, global_baseline,
                               metadata, protocol, args.output, device, args.epochs)
    S.write_json(args.output / "candidate_selection.json", [summary])
    return args.output


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fullvalid", choices=("on", "off"), required=True)
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    rest = args.rest[1:] if args.rest and args.rest[0] == "--" else args.rest
    if not rest or rest[0] not in ("prepare", "candidate"):
        raise SystemExit("first forwarded argument must be 'prepare' or 'candidate'")
    for path, expected in PINNED.items():
        if sha256(path) != expected:
            raise SystemExit(f"Pinned source changed: {path.relative_to(REPO)}")
    if args.fullvalid == "on":
        install_fullvalid()
    receipt = dict(wrapper_sha256=sha256(Path(__file__)), pinned={str(p.relative_to(REPO)): h for p, h in PINNED.items()},
                   wildfire_package_sha256={str(p.relative_to(REPO)): sha256(p)
                                            for p in sorted((REPO / "forecast/wildfire").glob("*.py"))},
                   candidate_id=CANDIDATE_ID,
                   fullvalid=args.fullvalid, never_hours=NEVER, argv=rest,
                   host=dict(python=platform.python_version(), platform=platform.platform()))
    try:
        import torch
        receipt["host"]["torch"] = torch.__version__
    except ImportError:
        pass
    started = time.perf_counter()
    if rest[0] == "prepare":
        sys.argv = ["wildfire.prepare"] + rest[1:]
        from wildfire.prepare import prepare_main
        prepare_main()
        out = Path(rest[rest.index("--output-dir") + 1])
    else:
        out = run_candidate(rest[1:])
    receipt["wall_seconds"] = time.perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    (out / f"C651_RECIPE_RECEIPT_{rest[0]}_{args.fullvalid}.json").write_text(json.dumps(receipt, indent=1) + "\n")


if __name__ == "__main__":
    main()
