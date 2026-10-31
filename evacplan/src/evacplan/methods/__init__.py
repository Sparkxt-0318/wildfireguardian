"""Planning methods for the harness (``evacplan run --method NAME``).

Registered: ``noop`` (empty plan, plumbing only). Baselines B0-B3 and the Phase-1 experiments
register here as they are written.
"""
from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from .base import Method, MethodResult

_REGISTRY: dict[str, str | Callable[..., Method]] = {
    "noop": "evacplan.methods.noop:NoopMethod",
}


def register(name: str, factory: str | Callable[..., Method], *, replace: bool = False) -> None:
    """Register a method by ``"module:Class"`` path or a factory callable."""
    if name in _REGISTRY and not replace:
        raise ValueError(f"method {name!r} is already registered")
    _REGISTRY[name] = factory


def available() -> list[str]:
    return sorted(_REGISTRY)


def get_method(name: str, **config) -> Method:
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown method {name!r}; available: {', '.join(available())}") from None
    if isinstance(factory, str):
        mod, _, attr = factory.partition(":")
        factory = getattr(import_module(mod), attr)
    method = factory(**config)
    if not isinstance(method, Method):
        raise TypeError(f"{name!r} does not build an evacplan.methods.Method")
    return method


__all__ = ["Method", "MethodResult", "available", "get_method", "register"]
