"""Configuration: YAML files merged over configs/default.yaml, with a stable hash."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import yaml

from wfglink import PROJECT_ROOT
from wfglink.provenance import sha256_json

DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "default.yaml"


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge `override` into a copy of `base`."""
    out = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


LOCAL_CONFIG = PROJECT_ROOT / "configs" / "booth_local.yaml"


def load_config(*paths: str | Path, overrides: Mapping[str, Any] | None = None,
                local: bool = False) -> dict[str, Any]:
    """Load the default config, then configs/booth_local.yaml (only with local=True: the
    machine-specific switches written by the sittings), then each given YAML file, then
    explicit overrides."""
    with open(DEFAULT_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if local and LOCAL_CONFIG.exists():
        with open(LOCAL_CONFIG, encoding="utf-8") as f:
            cfg = deep_merge(cfg, yaml.safe_load(f) or {})
    for p in paths:
        with open(p, encoding="utf-8") as f:
            cfg = deep_merge(cfg, yaml.safe_load(f) or {})
    if overrides:
        cfg = deep_merge(cfg, overrides)
    return cfg


def config_hash(cfg: Mapping[str, Any]) -> str:
    return sha256_json(cfg)
