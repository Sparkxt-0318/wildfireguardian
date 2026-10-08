"""Usable integration facade: escape solve and separately budgeted checked return."""

from copy import deepcopy
import time
from .core import solve
from .fallback import checked_return


def plan_with_return(
    graph,
    hazard,
    request,
    history=None,
    endpoint=None,
    *,
    return_budget_s=5.0,
    prepared=None
):
    start = time.perf_counter()
    escape = solve(graph, hazard, request, prepared=prepared)
    output = {
        "escape": escape,
        "return_alternative": None,
        "primary_problem_resolved": escape["status"]
        in [
            "CONDITIONAL_OPTIMUM",
            "PROVEN_INFEASIBLE",
            "DISCONNECTED",
            "AT_ISSUE_FAILURE",
        ],
        "return_policy": "recorded path only; separately declared wall budget; never turns timeout into infeasibility",
        "return_budget_s": return_budget_s,
    }
    if (
        escape["status"] in ["PROVEN_INFEASIBLE", "DISCONNECTED", "TIMEOUT"]
        and history is not None
        and endpoint is not None
    ):
        q = deepcopy(request)
        q["limits"]["wall_s"] = return_budget_s
        output["return_alternative"] = checked_return(
            graph, hazard, q, history, endpoint, prepared=prepared
        )
    output["end_to_end_s"] = time.perf_counter() - start
    return output
