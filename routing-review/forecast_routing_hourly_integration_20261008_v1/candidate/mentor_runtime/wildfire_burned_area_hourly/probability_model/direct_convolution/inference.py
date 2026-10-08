"""Load a fitted direct-score checkpoint without fitting preprocessing."""

from pathlib import Path

import torch

from .._inference import NormalizedBurnModel, checkpoint_normalization

from ..input_schema import one_hot_groups
from ..model import _check_grid
from .model import DirectBurnPrediction, DirectEnvironmentConditionedConvolution


class TrainedDirectBurnModel(NormalizedBurnModel):
    """Apply saved normalization, schema checks, and contact-only eligibility."""

    def forward(self, burned_area, environmental_data, *, channel_names,
                burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="unknown"):
        """Return raw_score and evaluation probability on the trained domain."""
        if tuple(channel_names) != self.channel_names:
            raise ValueError("Prediction channel names/order differ from trained checkpoint")
        _check_grid(environmental_data, "environmental_data", len(self.channel_names))
        self._validate_one_hot(environmental_data, feature_valid)
        prediction = self.model(
            burned_area, (environmental_data - self.mean) / self.std,
            burned_area_valid=burned_area_valid, feature_valid=feature_valid,
            dt_hours=dt_hours, boundary=boundary,
        )
        if self.contract.get("eligibility") != "at_least_one_burned_neighbor":
            return prediction
        contact, known = self._contact(burned_area, burned_area_valid)
        valid = prediction.valid & (contact | (known & (burned_area == 1)))
        return DirectBurnPrediction(prediction.raw_score.masked_fill(~valid, torch.nan),
                                    prediction.probability.masked_fill(~valid, torch.nan), valid)


def load_trained_model(path: str | Path, device="cpu") -> TrainedDirectBurnModel:
    """Safely load the fixed one-hour identity-link model and saved raw schema.

    Hazard-link and other legacy checkpoints are rejected rather than
    silently reinterpreted as direct scores. The loaded model is in eval mode.
    """
    saved = torch.load(Path(path), map_location="cpu", weights_only=True)
    contract = saved["contract"]
    if (contract.get("format_version") != 1
            or contract.get("architecture") != "DirectEnvironmentConditionedConvolution"
            or contract.get("dt_hours") != 1.0
            or contract.get("center_coefficient") != 0.0
            or contract.get("output_link") != "identity"
            or contract.get("training_clipping") is not False
            or contract.get("evaluation_clipping") != [0.0, 1.0]
            or contract.get("kernel_constraint") not in ("signed", "nonnegative")):
        raise ValueError("Unsupported direct-convolution checkpoint contract")
    channels = contract["channels"]
    one_hot_groups(contract)
    if len(channels) != contract["in_channels"] or len(set(channels)) != len(channels):
        raise ValueError("Invalid checkpoint channel schema")
    mean, std = checkpoint_normalization(
        saved, channels, shape_error="Checkpoint normalization differs from channel schema",
        require_floating=True,
    )
    model = DirectEnvironmentConditionedConvolution(
        contract["in_channels"], contract["kernel_size"], contract["hidden_channels"],
        contract["kernel_constraint"],
    )
    model.load_state_dict(saved["model_state_dict"], strict=True)
    if any(not bool(torch.isfinite(parameter).all()) for parameter in model.parameters()):
        raise ValueError("Checkpoint model parameters must be finite")
    if not torch.equal(model.off_center, model.off_center.new_tensor(
        [0 if i == model.kernel_size ** 2 // 2 else 1 for i in range(model.kernel_size ** 2)]
    ).reshape_as(model.off_center)):
        raise ValueError("Checkpoint must fix its center coefficient to zero")
    result = TrainedDirectBurnModel(model, mean, std, contract, saved["best_epoch"])
    return result.to(device).eval()
