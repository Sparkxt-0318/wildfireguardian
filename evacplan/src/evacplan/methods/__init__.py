"""Planning methods for the harness (``evacplan run --method NAME``).

Registered: ``noop`` (empty plan, plumbing only), ``b0_independent`` (B0: each facility planned
alone with today's planner logic, vehicles shared first come first served), ``b1_greedy`` (B1:
earliest-deadline-first insertion with the latest-safe-departure sweep's deadlines), ``b2_vrptw`` (B2:
OR-Tools VRPTW with pickup and delivery, per-class capacities and static windows from the latest
departures), ``b3_mip`` (B3: MIPs on a time-expanded network with HiGHS, S instances only, with a
proven bound). Aliases ``B0`` ... ``B3`` (any case) name the baselines. The Phase-1 experiments
register here as they are written: ``e4_flow_bound`` (E4: a flow-over-time LP bound on the residents any
plan can deliver, every size; bound only, :attr:`Method.bound_only`).
"""
from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from .base import Method, MethodResult

_REGISTRY: dict[str, str | Callable[..., Method]] = {
    "noop": "evacplan.methods.noop:NoopMethod",
    "b0_independent": "evacplan.methods.b0_independent:B0Independent",
    "b1_greedy": "evacplan.methods.b1_greedy:B1Greedy",
    "b2_vrptw": "evacplan.methods.b2_vrptw:B2VRPTW",
    "b3_mip": "evacplan.methods.b3_mip:B3MIP",
    "e4_flow_bound": "evacplan.methods.flow_bound:E4FlowBound",
}
ALIASES = {"b0": "b0_independent", "b1": "b1_greedy", "b2": "b2_vrptw", "b3": "b3_mip"}


def register(name: str, factory: str | Callable[..., Method], *, replace: bool = False) -> None:
    """Register a method by ``"module:Class"`` path or a factory callable."""
    if name in _REGISTRY and not replace:
        raise ValueError(f"method {name!r} is already registered")
    _REGISTRY[name] = factory


def available() -> list[str]:
    return sorted(_REGISTRY)


def canonical(name: str) -> str:
    """The registered name of ``name`` (``B2`` -> ``b2_vrptw``); unknown names are returned unchanged."""
    if name in _REGISTRY:
        return name
    return ALIASES.get(name.lower(), name)


def get_method(name: str, **config) -> Method:
    name = canonical(name)
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown method {name!r}; available: {', '.join(available())} "
                       f"(aliases {', '.join(sorted(ALIASES))})") from None
    if isinstance(factory, str):
        mod, _, attr = factory.partition(":")
        factory = getattr(import_module(mod), attr)
    method = factory(**config)
    if not isinstance(method, Method):
        raise TypeError(f"{name!r} does not build an evacplan.methods.Method")
    return method


__all__ = ["ALIASES", "Method", "MethodResult", "available", "canonical", "get_method", "register"]
