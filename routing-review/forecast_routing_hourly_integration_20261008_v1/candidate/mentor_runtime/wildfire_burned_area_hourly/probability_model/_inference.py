"""Saved preprocessing and contact masks shared by the two fitted models."""

import torch
from torch import nn
from torch.nn import functional as F

from .input_schema import one_hot_groups


class NormalizedBurnModel(nn.Module):
    """Common checkpoint state; subclasses retain their distinct output links."""

    def __init__(self, model, mean, std, contract, best_epoch):
        super().__init__()
        self.model = model
        self.register_buffer("mean", mean.reshape(-1, 1, 1))
        self.register_buffer("std", std.reshape(-1, 1, 1))
        self.channel_names = tuple(contract["channels"])
        self.contract = contract
        self.source_channels = tuple(contract.get("source_channels", self.channel_names))
        self.categorical_classes = contract.get("categorical_classes", {})
        self.one_hot_groups = one_hot_groups(contract)
        self.best_epoch = best_epoch
        stencil = torch.ones(1, 1, model.kernel_size, model.kernel_size)
        stencil[:, :, model.kernel_size // 2, model.kernel_size // 2] = 0
        self.register_buffer("neighbor_stencil", stencil)

    def _validate_one_hot(self, environmental_data, feature_valid):
        for source, indices in self.one_hot_groups.items():
            values = environmental_data[..., list(indices), :, :]
            known = torch.isfinite(values).all(dim=-3)
            if feature_valid is not None:
                known = known & feature_valid[..., list(indices), :, :].all(dim=-3)
            binary = ((values == 0) | (values == 1)).all(dim=-3)
            if not bool((~known | (binary & (values.sum(dim=-3) == 1))).all()):
                raise ValueError(f"Invalid known one-hot input group: {source}")

    def _contact(self, burned_area, burned_area_valid):
        known = torch.isfinite(burned_area)
        if burned_area_valid is not None:
            known = known & burned_area_valid
        sources = torch.where(known, burned_area, 0).to(dtype=self.mean.dtype)
        h, w = sources.shape[-2:]
        contact = F.conv2d(
            sources.reshape(-1, 1, h, w), self.neighbor_stencil,
            padding=self.model.kernel_size // 2,
        ).reshape_as(burned_area) > 0
        return contact, known


def checkpoint_normalization(saved, channels, *, shape_error, require_floating=False):
    """Validate saved scales without fitting or inspecting any data labels."""
    mean, std = saved["normalization_mean"], saved["normalization_std"]
    if mean.shape != (len(channels),) or std.shape != mean.shape:
        raise ValueError(shape_error)
    if ((require_floating and (not mean.is_floating_point() or not std.is_floating_point()))
            or not torch.isfinite(mean).all() or not torch.isfinite(std).all()
            or not (std > 0).all()):
        raise ValueError("Checkpoint normalization must be finite with positive scales")
    return mean, std
