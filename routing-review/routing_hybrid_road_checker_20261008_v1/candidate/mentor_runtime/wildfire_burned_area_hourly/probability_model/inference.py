"""Load a fitted kernel and its training-only preprocessing without fitting."""

from pathlib import Path

import torch

from ._inference import NormalizedBurnModel, checkpoint_normalization

from .model import BurnProbability, EnvironmentConditionedConvolution
from .input_schema import one_hot_groups


class TrainedBurnModel(NormalizedBurnModel):
    """Fitted probability model accepting raw, ordered environmental channels."""

    def forward(self, burned_area, environmental_data, *, channel_names,
                burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="unknown"):
        if tuple(channel_names) != self.channel_names:
            raise ValueError("Prediction channel names/order differ from the trained checkpoint")
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
        rate_valid = prediction.rate_valid & contact
        return BurnProbability(
            prediction.probability.masked_fill(~valid, torch.nan), valid,
            prediction.rate.masked_fill(~rate_valid, torch.nan), rate_valid,
        )


def load_trained_model(path: str | Path, device="cpu") -> TrainedBurnModel:
    """Load parameters, normalization and channel contract, using weights_only.

    Default inference is CPU. Call with device='mps'/'cuda', or move the result
    with .to(device), and move data and masks to the same device. This function
    does not refit preprocessing, inspect labels, or read the training cache.
    A contact-only checkpoint leaves currently unburned cells without a known
    burned neighbor unavailable (NaN/false mask), matching its training scope.
    """
    saved = torch.load(Path(path), map_location="cpu", weights_only=True)
    contract = saved["contract"]
    if (contract["format_version"] != 1
            or contract["architecture"] != "EnvironmentConditionedConvolution"
            or contract["dt_hours"] != 1.0 or contract["center_rate"] != 0.0):
        raise ValueError("Unsupported trained probability checkpoint contract")
    channels = contract["channels"]
    one_hot_groups(contract)
    if len(channels) != contract["in_channels"] or len(set(channels)) != len(channels):
        raise ValueError("Invalid checkpoint channel schema")
    mean, std = checkpoint_normalization(
        saved, channels, shape_error="Checkpoint normalization shape differs from its channel schema",
        require_floating=False,
    )
    model = EnvironmentConditionedConvolution(
        contract["in_channels"], contract["kernel_size"], contract["hidden_channels"],
    )
    model.load_state_dict(saved["model_state_dict"], strict=True)
    result = TrainedBurnModel(model, mean, std, contract, saved["best_epoch"])
    return result.to(device).eval()
