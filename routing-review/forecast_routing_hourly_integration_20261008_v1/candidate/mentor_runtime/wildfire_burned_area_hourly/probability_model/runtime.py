"""Small shared runtime helpers for training and evaluation commands."""

import json
from pathlib import Path
from typing import Any

import torch


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")



def choose_device(requested: str) -> torch.device:
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was explicitly requested but is unavailable")
    if device.type == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS was explicitly requested but is unavailable")
    if device.type not in ("cpu", "cuda", "mps"):
        raise ValueError("The training device must be cpu, cuda, or mps")
    return device

