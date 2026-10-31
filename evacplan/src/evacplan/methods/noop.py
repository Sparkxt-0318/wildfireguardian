"""``noop``: the empty plan. It only tests the harness plumbing (instances, oracle, CSV,
leaderboard): it delivers nobody, claims no bound, and every resident is reported as not planned."""
from __future__ import annotations

from ..schema import Solution
from .base import Method, MethodResult


class NoopMethod(Method):
    name = "noop"

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        return MethodResult(Solution(instance=instance.name, method=self.name, itineraries=[],
                                     provenance={"seed": int(seed), "note": "empty plan (harness plumbing)"}))
