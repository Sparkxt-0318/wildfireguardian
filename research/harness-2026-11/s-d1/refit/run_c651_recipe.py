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

TRAINING STAGE NOT INCLUDED: c651 was trained by the categorical-balanced scheduled/mixed kernel search
(protocol training_source_sha256 lists the archived kernel_search*.py / mixed_kernels.py), whose current
refactored entry point (wildfire.search MixedSearch, stage run/train/finalize) has no single-candidate
mode. How the arm trains exactly candidate mixed_3_5_7_9_02_lr0.1_warmup_cosine is an open A1 decision.
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
}
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fullvalid", choices=("on", "off"), required=True)
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    rest = args.rest[1:] if args.rest and args.rest[0] == "--" else args.rest
    if not rest or rest[0] != "prepare":
        raise SystemExit("first forwarded argument must be 'prepare' (training stage not yet defined)")
    for path, expected in PINNED.items():
        if sha256(path) != expected:
            raise SystemExit(f"Pinned source changed: {path.relative_to(REPO)}")
    if args.fullvalid == "on":
        install_fullvalid()
    receipt = dict(wrapper_sha256=sha256(Path(__file__)), pinned={str(p.relative_to(REPO)): h for p, h in PINNED.items()},
                   fullvalid=args.fullvalid, never_hours=NEVER, argv=rest,
                   host=dict(python=platform.python_version(), platform=platform.platform()))
    try:
        import torch
        receipt["host"]["torch"] = torch.__version__
    except ImportError:
        pass
    sys.argv = [f"wildfire.{rest[0]}"] + rest[1:]
    started = time.perf_counter()
    from wildfire.prepare import prepare_main
    prepare_main()
    out = Path(rest[rest.index("--output-dir") + 1])
    receipt["wall_seconds"] = time.perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    (out / f"C651_RECIPE_RECEIPT_{rest[0]}_{args.fullvalid}.json").write_text(json.dumps(receipt, indent=1) + "\n")


if __name__ == "__main__":
    main()
