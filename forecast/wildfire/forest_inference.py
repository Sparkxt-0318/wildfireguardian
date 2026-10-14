"""Apply a saved patch forest to complete grids and recursive binary states.

The forest supplies a fitted one-hour probability, rather than a hazard model.
Its mean tree probability is used at each recursive transition. Tree membership
is never sampled as a Bayesian component. The fitted estimator runs on CPU.
"""
from __future__ import annotations

from copy import deepcopy
import re

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .models import (BurnProbability, PatchRandomForest, _check_grid, _duration,
                     _valid_mask)
from .schema import one_hot_groups


def _named_schema(channels):
    """Recover frozen indicator groups from the saved expanded channel names.

    No input values, reference outcomes, or new vocabulary are inspected.
    Names of the form ``source=integer`` are the package's saved one-hot naming
    convention. Ordinary channel names remain continuous.
    """
    sources, groups, classes, info = [], {}, {}, []
    for index, name in enumerate(channels):
        matched = re.fullmatch(r"(.+)=(-?\d+)", name)
        source = matched.group(1) if matched else name
        if source not in groups:
            sources.append(source)
            groups[source] = []
        groups[source].append(index)
        entry = dict(name=name, source_channel=source,
                     encoding="one_hot" if matched else "continuous")
        if matched:
            code = int(matched.group(2))
            classes.setdefault(source, []).append(code)
            entry["class_code"] = code
        info.append(entry)
    if not classes:
        return {}  # Legacy continuous contracts use the default raw encoding.
    return dict(source_channels=sources, channel_groups=groups,
                categorical_classes=classes, channel_info=info,
                categorical_encoding="one_hot")


class ForestGridPredictor(nn.Module):
    """A CPU grid adapter preserving a fitted forest's patch feature order.

    Raw inputs are transformed by saved normalization vectors when present.
    Checkpoints with neither vector use identity preprocessing, matching the
    standalone PatchRandomForest contract that its caller supplies fitted input
    values. One vector without the other is invalid. Missing interior inputs
    remain unavailable; known previous burns have exact new-burn probability
    zero. A complete unburned source neighborhood has structural probability
    zero, extending the contact-conditioned training endpoint to whole grids.

    ``rate`` is only the equivalent one-hour value ``-log(1-q)``. It can be
    infinite for exact q=1, and is not used for temporal extrapolation. Only
    dt_hours=1 is accepted; cumulative multi-hour inference uses recursion.
    """

    def __init__(self, forest: PatchRandomForest):
        super().__init__()
        self.forest = forest
        self.channel_names = forest.channel_names
        self.contract = dict(forest.contract)
        self.contract.update(_named_schema(self.channel_names))
        self.one_hot_groups = one_hot_groups(self.contract)
        self.categorical_classes = deepcopy(self.contract.get("categorical_classes", {}))
        self.source_channels = tuple(self.contract.get("source_channels", self.channel_names))
        metadata = forest.metadata
        supplied = [name in metadata for name in ("normalization_mean", "normalization_std")]
        if any(supplied) and not all(supplied):
            raise ValueError("Forest checkpoint must save both normalization_mean and normalization_std")
        if all(supplied):
            try:
                mean = np.asarray(metadata["normalization_mean"], dtype=np.float32)
                std = np.asarray(metadata["normalization_std"], dtype=np.float32)
            except (TypeError, ValueError) as error:
                raise ValueError("Forest checkpoint normalization must be real numeric vectors") from error
            policy = "saved_training_normalization"
        else:
            mean = np.zeros(len(self.channel_names), dtype=np.float32)
            std = np.ones(len(self.channel_names), dtype=np.float32)
            policy = "identity_preprocessed_inputs"
        if (mean.shape != (len(self.channel_names),) or std.shape != mean.shape
                or not np.isfinite(mean).all() or not np.isfinite(std).all()
                or not (std > 0).all()):
            raise ValueError("Forest checkpoint normalization must have channel-sized finite vectors and positive scales")
        self.preprocessing_policy = policy
        self.contract.update(
            preprocessing_policy=policy, inference_device="cpu",
            grid_eligibility="at_least_one_burned_neighbor_or_structural_zero",
            temporal_policy="recursive_one_hour_transitions_only",
            equivalent_rate="negative_log_one_minus_one_hour_probability",
        )
        # A frozen scalar gives the shared API a device/dtype reference. It is
        # not a learned coefficient and is not passed to sklearn.
        self.register_parameter("input_reference", nn.Parameter(torch.zeros(()), requires_grad=False))
        self.register_buffer("mean", torch.from_numpy(mean.copy()).reshape(-1, 1, 1))
        self.register_buffer("std", torch.from_numpy(std.copy()).reshape(-1, 1, 1))
        self.kernel_size = forest.kernel_size

    @property
    def prediction_metadata(self):
        return dict(model_family="random_forest", inference_device="cpu",
                    preprocessing_policy=self.preprocessing_policy,
                    probability_model="mean_tree_probability_at_each_hour",
                    tree_sampling=False,
                    structural_zero_policy="complete_unburned_source_neighborhood")

    def checkpoint_payload(self):
        """Export the original portable joblib format, without source files."""
        metadata = self.forest.metadata
        if self.preprocessing_policy == "saved_training_normalization":
            metadata.update(normalization_mean=self.mean[:, 0, 0].detach().cpu().tolist(),
                            normalization_std=self.std[:, 0, 0].detach().cpu().tolist())
        return dict(format_version=1, config=self.forest._config(),
                    contract=dict(self.forest.contract), estimator=self.forest.estimator,
                    metadata=metadata)

    def _validate_one_hot(self, environment, available):
        for source, indices in self.one_hot_groups.items():
            values = environment[..., list(indices), :, :]
            known = available[..., list(indices), :, :].all(dim=-3)
            binary = ((values == 0) | (values == 1)).all(dim=-3)
            if not bool((~known | (binary & (values.sum(dim=-3) == 1))).all()):
                raise ValueError(f"Invalid known one-hot input group: {source}")

    def forward(self, burned_area, environmental_data, *, channel_names,
                burned_area_valid=None, feature_valid=None, dt_hours=1.0,
                boundary="unknown"):
        if self.input_reference.device.type != "cpu":
            raise ValueError("PatchRandomForest inference requires device='cpu'")
        _check_grid(burned_area, "burned_area", 1)
        _check_grid(environmental_data, "environmental_data", len(self.channel_names))
        if tuple(channel_names) != self.channel_names:
            raise ValueError("Prediction channel names/order differ from the trained checkpoint")
        if (burned_area.shape[:-3] != environmental_data.shape[:-3]
                or burned_area.shape[-2:] != environmental_data.shape[-2:]):
            raise ValueError("burned_area and environmental_data must share leading and spatial dimensions")
        if (burned_area.device != self.input_reference.device
                or environmental_data.device != self.input_reference.device
                or environmental_data.dtype != self.input_reference.dtype):
            raise ValueError("Forest inputs must match the model CPU device and dtype")
        if not environmental_data.is_floating_point() or burned_area.is_complex():
            raise TypeError("Forest inputs must be real, with floating environmental data")
        duration = _duration(dt_hours, tuple(burned_area.shape[:-3]), environmental_data)
        if not bool((duration == 1).all()):
            raise ValueError("PatchRandomForest is fitted only for dt_hours=1.0; use method='recursive' for multi-hour probabilities")
        if boundary not in ("zero", "unknown"):
            raise ValueError("boundary must be 'unknown' or 'zero'")
        known = _valid_mask(burned_area_valid, burned_area, "burned_area_valid") & torch.isfinite(burned_area)
        if bool((known & (burned_area != 0) & (burned_area != 1)).any()):
            raise ValueError("Valid burned_area values must be exactly 0 or 1")
        available = (_valid_mask(feature_valid, environmental_data, "feature_valid")
                     & torch.isfinite(environmental_data))
        self._validate_one_hot(environmental_data, available)
        h, w = burned_area.shape[-2:]
        k, radius = self.kernel_size, self.kernel_size // 2
        source = torch.where(known, burned_area, 0).to(self.input_reference.dtype).reshape(-1, 1, h, w)
        environment = torch.where(available, (environmental_data - self.mean) / self.std, 0)
        if bool((available & ~torch.isfinite(environment)).any()):
            raise ValueError("Forest normalized environmental inputs must remain finite")

        def complete(mask):
            padded = F.pad(mask.to(environment.dtype).reshape(-1, 1, h, w),
                           (radius,) * 4, value=float(boundary == "zero"))
            return (F.avg_pool2d(padded, k, stride=1) == 1).reshape_as(burned_area)

        coverage = known & complete(known) & complete(available.all(dim=-3, keepdim=True))
        contact = (F.avg_pool2d(source, k, stride=1, padding=radius) > 0).reshape_as(burned_area)
        prior_burns = known & (burned_area == 1)
        query = coverage & ~prior_burns & contact
        probability = torch.zeros_like(burned_area, dtype=environment.dtype)
        if bool(query.any()):
            # Sliding views avoid materializing every environmental patch of a
            # full trajectory block. Query chunks bound sklearn's input matrix
            # even when a large rectangular grid has widespread source contact.
            padded_environment = np.pad(
                environment.reshape(-1, len(self.channel_names), h, w).detach().numpy(),
                ((0, 0), (0, 0), (radius, radius), (radius, radius)),
            )
            padded_source = np.pad(source.detach().numpy(),
                                   ((0, 0), (0, 0), (radius, radius), (radius, radius)))
            env_windows = np.lib.stride_tricks.sliding_window_view(padded_environment, (k, k), axis=(-2, -1))
            burn_windows = np.lib.stride_tricks.sliding_window_view(padded_source, (k, k), axis=(-2, -1))
            selected = torch.nonzero(query.reshape(-1), as_tuple=False).flatten()
            for start in range(0, len(selected), 8192):
                indices = selected[start:start + 8192]
                positions = indices.numpy()
                batch, spatial = np.divmod(positions, h * w)
                row, col = np.divmod(spatial, w)
                env_patches = env_windows[batch, :, row, col]
                burn_patches = burn_windows[batch, :, row, col]
                q = self.forest.predict_probability(env_patches, burn_patches,
                                                   channel_names=self.channel_names)
                if not np.isfinite(q).all() or ((q < 0) | (q > 1)).any():
                    raise RuntimeError("The fitted forest produced a nonfinite probability or a value outside [0,1]")
                probability.reshape(-1)[indices] = torch.from_numpy(q).to(environment.dtype)
        valid = coverage | prior_burns
        # This diagnostic does not assert a fitted continuous-time hazard. Its
        # availability also supplies deterministic coverage to the common rollout.
        rate = -torch.log1p(-probability)
        return BurnProbability(probability.masked_fill(~valid, torch.nan), valid,
                               rate.masked_fill(~coverage, torch.nan), coverage)
