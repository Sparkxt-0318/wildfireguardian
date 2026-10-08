"""Run an explicitly untrained demonstration on a real rectangular sequence."""

import argparse
import json

import torch

from ..pytorch_loader import WildfireSequenceDataset
from .model import EnvironmentConditionedConvolution


# Re-exported for callers of the original demonstration module.
from .input_schema import CHANNELS
# Fixed unit scales, only for this untrained numerical demonstration. These
# are not fitted standard deviations or scientifically calibrated parameters.
UNIT_SCALES = (50.0, 20.0, 20.0, 90.0, 100.0)


def scale_demo_features(features):
    shape = (1,) * (features.ndim - 3) + (len(CHANNELS), 1, 1)
    return features / features.new_tensor(UNIT_SCALES).reshape(shape)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", default="KFS_01")
    parser.add_argument("--sample-index", type=int)
    parser.add_argument("--sequence-length", type=int, default=2)
    parser.add_argument("--kernel-size", type=int, default=3)
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    dataset = WildfireSequenceDataset(
        events=[args.event], sequence_length=args.sequence_length,
        patch_size=None, channels=CHANNELS,
    )
    try:
        index = len(dataset) // 4 if args.sample_index is None else args.sample_index
        sample = dataset[index]
        device = torch.device(args.device)
        torch.manual_seed(7)
        model = EnvironmentConditionedConvolution(
            len(CHANNELS), kernel_size=args.kernel_size,
        ).to(device).eval()
        with torch.no_grad():
            result = model(
                sample["burned_area"].to(device),
                scale_demo_features(sample["features"]).to(device),
                burned_area_valid=sample["burned_area_valid"].to(device),
                feature_valid=sample["feature_valid"].to(device),
                dt_hours=args.hours,
            )
        values = result.probability[result.valid]
        print(json.dumps({
            "interpretation": "Untrained shape/mask demonstration; no forecast validation",
            "event_id": sample["event_id"],
            "sample_index": index,
            "location": dataset.sample_location(index),
            "channel_names": list(CHANNELS),
            "input_shape": list(sample["features"].shape),
            "probability_shape": list(result.probability.shape),
            "dt_hours": args.hours,
            "kernel_size": args.kernel_size,
            "valid_probabilities": int(result.valid.sum()),
            "unknown_probabilities": int((~result.valid).sum()),
            "valid_rates": int(result.rate_valid.sum()),
            "probability_min": float(values.min()) if values.numel() else None,
            "probability_max": float(values.max()) if values.numel() else None,
            "device": str(device),
        }, indent=2))
    finally:
        dataset.close()


if __name__ == "__main__":
    main()
