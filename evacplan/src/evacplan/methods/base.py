"""The interface every planning method implements for the harness.

A method gets an instance and its scenario set, a wall-clock budget (seconds) and a seed, and
returns a :class:`MethodResult`: a plan (:class:`~evacplan.schema.Solution`) and optionally a
proven upper bound on the residents that any plan can deliver (exact or relaxation methods).
Methods may use the RELAXED check and the oracle internally, but they declare no final state:
the harness checks every returned plan with :mod:`evacplan.oracle` and reports only that.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import hazard_contract as hc

from ..schema import Instance, Solution


@dataclass
class MethodResult:
    solution: Solution
    best_bound: float | None = None     # proven upper bound on residents delivered (checked); None = none
    info: dict[str, Any] = field(default_factory=dict)   # free-form, never used for scoring


class Method:
    """Base class. Subclasses set ``name`` and implement :meth:`solve`; constructor keyword
    arguments are the method's configuration (recorded in every result row)."""

    name = "method"

    def __init__(self, **config: Any):
        self._config = dict(config)

    def config(self) -> dict[str, Any]:
        return dict(self._config)

    def solve(self, instance: Instance, scenario_set: hc.ScenarioSet, *, budget_s: float, seed: int,
              deadline: float) -> MethodResult:
        """Return a plan before ``deadline`` (a ``time.monotonic()`` value = start + ``budget_s``)."""
        raise NotImplementedError

    @staticmethod
    def time_left(deadline: float) -> float:
        return deadline - time.monotonic()
