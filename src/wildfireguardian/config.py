"""Canonical parameter registry loader (Round-3 PHASE 1-A).

One YAML file (``config/default.yaml``) holds every tunable that used to be a
literal scattered across ``scripts/`` and ``src/``. This module loads it, hashes
it, and exposes dotted-path lookup.

Why a hash
----------
A reported number is only meaningful together with the parameter set that
produced it. :func:`config_hash` reduces that parameter set to one 64-hex
string, which ``docs/NUMBERS.json`` stores next to every value. If the config
changes, the hash changes, and every number still carrying the old hash is
thereby marked stale rather than silently wrong.

Two hashes are exposed because they answer different questions:

``config_hash()``
    sha256 of the *canonical JSON serialisation* of the parsed content
    (sorted keys, no whitespace). Insensitive to comments, key order and
    formatting — it changes only when a **value** changes. This is the one
    recorded in NUMBERS.json.

``config_file_sha256()``
    sha256 of the raw file bytes. Changes on any edit at all, including
    comments. Useful for "is this literally the same file" questions.

Fallback stance
---------------
Lookup is fail-loud by default: a missing key raises. Call sites that must
survive a missing config (library defaults in :mod:`wildfireguardian.routing`)
pass an explicit ``default=``, which is always the historical literal, so a
missing or unreadable config can never silently change a result.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

__all__ = [
    "REPO_ROOT",
    "DEFAULT_CONFIG_PATH",
    "ConfigError",
    "load_config",
    "get",
    "config_hash",
    "config_file_sha256",
    "canonical_json",
    "reset_cache",
]

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH: Path = REPO_ROOT / "config" / "default.yaml"

#: Sentinel distinguishing "no default supplied" from "default is None".
_MISSING = object()

_lock = threading.Lock()
_cache: dict[Path, dict[str, Any]] = {}


class ConfigError(RuntimeError):
    """Raised when the config cannot be loaded or a required key is absent."""


def _resolve(path: str | os.PathLike[str] | None) -> Path:
    """Config path precedence: explicit arg > ``$WFG_CONFIG`` > repo default."""
    if path is not None:
        return Path(path).resolve()
    env = os.environ.get("WFG_CONFIG")
    if env:
        return Path(env).resolve()
    return DEFAULT_CONFIG_PATH


def load_config(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Parse and cache the config. Returns the raw nested mapping."""
    p = _resolve(path)
    with _lock:
        if p in _cache:
            return _cache[p]
    try:
        import yaml
    except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent
        raise ConfigError(
            "PyYAML is required to read config/default.yaml "
            "(pip install pyyaml; it is listed in requirements.txt)."
        ) from exc
    if not p.exists():
        raise ConfigError(f"config not found: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ConfigError(f"could not parse {p}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a mapping, got {type(data).__name__}: {p}")
    with _lock:
        _cache[p] = data
    return data


def reset_cache() -> None:
    """Drop the parse cache (tests that write temporary configs)."""
    with _lock:
        _cache.clear()


def get(
    dotted_key: str,
    default: Any = _MISSING,
    *,
    path: str | os.PathLike[str] | None = None,
) -> Any:
    """Look up ``"a.b.c"`` in the config.

    Raises :class:`ConfigError` if the key is absent and no ``default`` was
    supplied. If the config itself cannot be loaded, an explicit ``default`` is
    returned rather than propagating — this is what keeps library defaults
    working in an environment with no PyYAML.
    """
    try:
        node: Any = load_config(path)
    except ConfigError:
        if default is _MISSING:
            raise
        return default

    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            if default is _MISSING:
                raise ConfigError(f"missing config key: {dotted_key!r}")
            return default
        node = node[part]
    return node


def canonical_json(path: str | os.PathLike[str] | None = None) -> str:
    """Value-only canonical serialisation used as the hash pre-image."""
    return json.dumps(
        load_config(path), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def config_hash(path: str | os.PathLike[str] | None = None) -> str:
    """sha256 over parsed values (comment- and formatting-insensitive)."""
    return hashlib.sha256(canonical_json(path).encode("utf-8")).hexdigest()


def config_file_sha256(path: str | os.PathLike[str] | None = None) -> str:
    """sha256 over the raw config file bytes (sensitive to any edit)."""
    return hashlib.sha256(_resolve(path).read_bytes()).hexdigest()


def _main() -> int:
    p = _resolve(None)
    print(f"config file       : {p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p}")
    print(f"config_hash       : {config_hash()}")
    print(f"config_file_sha256: {config_file_sha256()}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
