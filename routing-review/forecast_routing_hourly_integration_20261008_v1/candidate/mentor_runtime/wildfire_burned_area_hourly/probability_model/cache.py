"""Prepared partitions and training-only weighted feature normalization."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np

from .input_schema import validate_one_hot_array

SPLIT_NAMES = ("train", "validation", "test")


def cache_kernel_size(metadata: dict[str, Any]) -> int:
    """Read the explicit odd spatial kernel side length from cache metadata."""
    size = metadata.get("kernel_size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 3 or size % 2 != 1:
        raise ValueError("Cache kernel_size must be an odd integer >= 3")
    return size



@dataclass(frozen=True)
class CachedSplit:
    environment: np.ndarray
    burned: np.ndarray
    target: np.ndarray
    weight: np.ndarray
    event_index: np.ndarray
    time_utc: np.ndarray
    row: np.ndarray
    col: np.ndarray

    def __len__(self) -> int:
        return len(self.target)

    @property
    def neighbor_count(self) -> np.ndarray:
        # The central cell is required to be unburned by load_split().
        return self.burned.sum(axis=(1, 2, 3), dtype=np.float32)



def load_split(directory: Path, name: str, metadata: dict[str, Any]) -> CachedSplit:
    """Load one cache partition and reject an inconsistent training contract."""
    with np.load(directory / f"{name}.npz", allow_pickle=False) as archive:
        names = tuple(CachedSplit.__dataclass_fields__)
        missing = set(names) - set(archive.files)
        if missing:
            raise ValueError(f"{name}.npz is missing {sorted(missing)}")
        data = CachedSplit(**{key: archive[key] for key in names})
    n, channels = len(data), len(metadata["channels"])
    kernel_size = cache_kernel_size(metadata)
    center = kernel_size // 2
    if n == 0:
        raise ValueError(f"The {name} cache is empty")
    if data.environment.shape != (n, channels, kernel_size, kernel_size):
        raise ValueError(f"Invalid environmental patch shape in {name}")
    if data.burned.shape != (n, 1, kernel_size, kernel_size):
        raise ValueError(f"Invalid burned patch shape in {name}")
    for key in ("target", "weight", "event_index", "time_utc", "row", "col"):
        if getattr(data, key).shape != (n,):
            raise ValueError(f"Invalid {key} shape in {name}")
    if data.environment.dtype != np.float32 or data.burned.dtype != np.float32:
        raise TypeError("Environmental and burned patches must be float32")
    if data.weight.dtype != np.float64:
        raise TypeError("Inverse inclusion-probability weights must be float64")
    if not np.isfinite(data.environment).all():
        raise ValueError(f"Nonfinite environmental features in {name}")
    validate_one_hot_array(data.environment, metadata)
    if not np.isin(data.burned, (0, 1)).all():
        raise ValueError(f"Nonbinary burned patch values in {name}")
    if not (data.burned[:, 0, center, center] == 0).all():
        raise ValueError(f"The {name} cache contains already-burned targets")
    if metadata.get("eligibility") == "at_least_one_burned_neighbor" and not (data.neighbor_count > 0).all():
        raise ValueError(f"The {name} cache contains a no-contact target despite its contact-only contract")
    if not np.isin(data.target, (0, 1)).all():
        raise ValueError(f"Targets in {name} must be exactly zero or one")
    if not np.isfinite(data.weight).all() or not (data.weight >= 1).all():
        raise ValueError(f"Invalid inverse sampling weights in {name}")
    for key in ("event_index", "time_utc", "row", "col"):
        if not np.issubdtype(getattr(data, key).dtype, np.integer):
            raise TypeError(f"{key} must have an integer dtype")
    if (data.event_index < 0).any() or (data.event_index >= len(metadata["event_ids"])).any():
        raise ValueError(f"Out-of-range event indices in {name}")
    for index in np.unique(data.event_index):
        event_id = metadata["event_ids"][int(index)]
        if metadata["splits"][event_id] != name:
            raise ValueError(f"Event {event_id} is in the wrong cache split")
    return data



def fit_normalization(data: CachedSplit, chunk_size: int = 8192) -> tuple[np.ndarray, np.ndarray]:
    """Weighted feature moments using training targets and every patch cell.

    Each target's inverse sampling weight applies equally to its feature
    positions. A second centered pass avoids cancellation for large raw values.
    Constant channels use a scale of one.
    """
    channels = data.environment.shape[1]
    # Wider environmental patches should not require an unbounded float64
    # temporary. Existing 3x3 runs retain their 8192-row summation order.
    bytes_per_row = channels * math.prod(data.environment.shape[2:]) * np.dtype(np.float64).itemsize
    chunk_size = min(chunk_size, max(1, (64 * 1024 * 1024) // bytes_per_row))
    total_weight = float(data.weight.sum(dtype=np.float64))
    mean = np.zeros(channels, dtype=np.float64)
    for start in range(0, len(data), chunk_size):
        end = min(start + chunk_size, len(data))
        values = data.environment[start:end].astype(np.float64)
        pixel_mean = values.mean(axis=(2, 3))
        mean += (pixel_mean * data.weight[start:end, None]).sum(axis=0)
    mean /= total_weight
    variance = np.zeros(channels, dtype=np.float64)
    for start in range(0, len(data), chunk_size):
        end = min(start + chunk_size, len(data))
        centered = data.environment[start:end].astype(np.float64) - mean[None, :, None, None]
        pixel_variance = np.square(centered).mean(axis=(2, 3))
        variance += (pixel_variance * data.weight[start:end, None]).sum(axis=0)
    std = np.sqrt(variance / total_weight)
    std = np.where(std < 1e-6, 1.0, std)
    if not np.isfinite(mean).all() or not np.isfinite(std).all():
        raise RuntimeError("Training normalization produced nonfinite moments")
    return mean.astype(np.float32), std.astype(np.float32)

