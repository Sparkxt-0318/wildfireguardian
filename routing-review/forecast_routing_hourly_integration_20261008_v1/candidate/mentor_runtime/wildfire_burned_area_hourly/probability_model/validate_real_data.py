"""Reproducible CPU integration checks, without fitting or downloading data."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import torch

from ..pytorch_loader import WildfireSequenceDataset, collate_fire_sequences
from .example import CHANNELS, scale_demo_features
from .model import EnvironmentConditionedConvolution


def _check_output(result, burned, observed):
    assert result.probability.shape == burned.shape
    assert result.valid.dtype == torch.bool
    assert torch.isfinite(result.probability[result.valid]).all()
    assert torch.isnan(result.probability[~result.valid]).all()
    assert torch.isfinite(result.rate[result.rate_valid]).all()
    assert torch.isnan(result.rate[~result.rate_valid]).all()
    assert (result.rate[result.rate_valid] >= 0).all()
    values = result.probability[result.valid]
    assert ((values >= 0) & (values <= 1)).all()
    existing = observed & (burned == 1)
    assert result.valid[existing].all()
    assert (result.probability[existing] == 0).all()
    assert not result.valid[~observed].any()
    return {
        "output_shape": list(result.probability.shape),
        "valid_probabilities": int(result.valid.sum()),
        "valid_unburned_targets": int((result.valid & (burned == 0)).sum()),
        "positive_new_burn_probabilities": int((result.probability[result.valid] > 0).sum()),
        "unknown_probabilities": int((~result.valid).sum()),
        "valid_rates": int(result.rate_valid.sum()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    torch.manual_seed(7)
    model = EnvironmentConditionedConvolution(len(CHANNELS)).eval()
    samples, checks = [], []
    for event in ("KFS_01", "CA-BTU-009205_Dixie"):
        dataset = WildfireSequenceDataset(
            events=[event], sequence_length=2, patch_size=None, channels=CHANNELS,
        )
        try:
            for index in (0, len(dataset) // 4):
                sample = dataset[index]
                with torch.no_grad():
                    result = model(
                        sample["burned_area"], scale_demo_features(sample["features"]),
                        burned_area_valid=sample["burned_area_valid"],
                        feature_valid=sample["feature_valid"],
                    )
                summary = _check_output(result, sample["burned_area"], sample["burned_area_valid"])
                summary.update(event_id=event, sample_index=index, input_shape=list(sample["features"].shape))
                assert summary["valid_unburned_targets"] > 0
                checks.append(summary)
                if index != 0:
                    samples.append(sample)
        finally:
            dataset.close()
    batch = collate_fire_sequences(samples)
    environment = scale_demo_features(batch["features"]).requires_grad_()
    result = model(
        batch["burned_area"], environment,
        burned_area_valid=batch["burned_area_valid"], feature_valid=batch["feature_valid"],
        dt_hours=torch.tensor([[1.0, 2.0], [0.5, 1.0]]),
    )
    batch_check = _check_output(result, batch["burned_area"], batch["burned_area_valid"])
    padding = (~batch["pixel_valid"]).unsqueeze(1).expand_as(result.valid)
    assert not result.valid[padding].any()
    result.probability[result.valid].sum().backward()
    assert torch.isfinite(environment.grad).all()
    assert all(torch.isfinite(parameter.grad).all() for parameter in model.parameters())
    assert any(bool(parameter.grad.abs().sum() > 0) for parameter in model.parameters())
    with torch.no_grad():
        zero = model(
            batch["burned_area"], environment.detach(), dt_hours=0,
            burned_area_valid=batch["burned_area_valid"], feature_valid=batch["feature_valid"],
        )
    assert torch.equal(zero.valid, batch["burned_area_valid"])
    assert (zero.probability[zero.valid] == 0).all()
    record = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": "Untrained technical integration checks; no fitting or forecast-skill evaluation",
        "torch_version": torch.__version__, "device": "cpu",
        "mps_available": torch.backends.mps.is_available(), "cuda_available": torch.cuda.is_available(),
        "channel_names": list(CHANNELS), "kernel_size": 3, "boundary": "unknown",
        "individual_sequences": checks,
        "mixed_rectangular_batch": batch_check,
        "spatial_padding_stays_unknown": True,
        "per_snapshot_horizons_checked": True,
        "finite_nonzero_parameter_gradients": True,
        "finite_environment_gradients": True,
        "zero_horizon_checked": True,
        "passed": True,
    }
    rendered = json.dumps(record, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
