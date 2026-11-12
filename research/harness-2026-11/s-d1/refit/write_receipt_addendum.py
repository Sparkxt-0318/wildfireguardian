"""Write REFIT_RECEIPT_ADDENDUM.json beside a refit receipt (S-D9 A1 §4.1 rule 3; not part of the pinned
wrapper, so the wrapper's sha 264deaea... stays unchanged).

It binds itself to the wrapper's receipt by that receipt's sha256 and states how arrival-raster validity
is used. For the A1 §3.1 refits through forecast-v2 pipeline.py (non-mixed variants and the logistic):
  * labels come from pipeline.perimeter_samples (perimeter states over the full grid);
  * features are loaded with wildfire.data.load_data(..., include_fire_labels=False);
  * kriged_samples (the only arrival-raster label reader) runs only for mixed variants.
pipeline.Environment._verify_sources hashes EVERY file under regions/<event>/ for identity, including
arrival_time_hours.tif; those files are listed here as "hashed for identity only, values not read".

    python research/harness-2026-11/s-d1/refit/write_receipt_addendum.py --run RUN_DIR --command final \
        --input-manifest PINS.json --train-events TRAIN.txt [--variant d4_wind]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MIXED_VARIANTS = {"mixed_base"}  # forecast-v2 VARIANTS with mixed=True (pipeline.py)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--command", required=True)
    ap.add_argument("--input-manifest", type=Path, required=True)
    ap.add_argument("--train-events", type=Path, required=True)
    ap.add_argument("--variant", default=None)
    args = ap.parse_args()
    receipt = args.run / f"REFIT_RECEIPT_{args.command}.json"
    if not receipt.exists():
        raise SystemExit(f"missing wrapper receipt: {receipt}")
    if args.variant in MIXED_VARIANTS:
        raise SystemExit("mixed variants read kriged arrival labels; this addendum does not cover them")
    pins = json.loads(args.input_manifest.read_text())
    train = {line.strip() for line in args.train_events.read_text().splitlines() if line.strip()}
    hashed = sorted(p for p in pins if p.endswith("arrival_time_hours.tif") and p.split("/")[-2] in train)
    addendum = dict(
        schema="s-d1.refit-receipt-addendum/1",
        wrapper_receipt=str(receipt.name), wrapper_receipt_sha256=sha256(receipt),
        command=args.command, variant=args.variant,
        arrival_raster_validity_use=(
            "not used: training labels from pipeline.perimeter_samples (perimeter states, full grid); "
            "features via wildfire.data.load_data(include_fire_labels=False); kriged_samples not invoked "
            "(variant not mixed)"),
        arrival_rasters_hashed_for_identity_only=hashed,
        input_manifest_sha256=sha256(args.input_manifest),
        train_events_file_sha256=sha256(args.train_events),
    )
    out = args.run / "REFIT_RECEIPT_ADDENDUM.json"
    out.write_text(json.dumps(addendum, indent=1) + "\n")
    print(json.dumps(dict(written=str(out), arrival_rasters_listed=len(hashed))))


if __name__ == "__main__":
    main()
