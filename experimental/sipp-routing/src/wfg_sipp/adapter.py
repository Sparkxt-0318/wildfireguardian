"""Copied frozen sweep and geometry, independent of a mutable kit import path."""
from . import geometry, frozen_sweep


def install():
    # The checker copy lives in another owned overlay, never in frozen source.
    import sys
    from pathlib import Path
    path = str(Path(__file__).resolve().parents[3] / "synthetic-truth/src")
    if path not in sys.path:
        sys.path.insert(0, path)
    from wfg_synthetic_truth import frozen_checker
    return {"core": geometry, "independent": frozen_checker, "zsweep": frozen_sweep}


def normalise(raw, planner_name, wall):
    route = raw.get("status") in ("CONDITIONAL_OPTIMUM", "CHECKED_ROUTE")
    no_route = raw.get("status") in ("PROVEN_INFEASIBLE", "DISCONNECTED", "AT_ISSUE_FAILURE")
    return {"status": "ROUTE" if route else "NO_ROUTE" if no_route else "UNRESOLVED",
            "raw_status": raw.get("status"), "reason": raw.get("reason"),
            "arrival": raw.get("arrival"), "legs": raw.get("legs") or [],
            "destination": raw.get("destination"), "metrics": raw.get("metrics", {}),
            "planner": planner_name, "complete": route or no_route, "wall_s": wall}


def sweep_plan(graph, request, model, *, wall_s=30):
    import time
    from . import geometry
    checker = install()["independent"]

    class Core:
        node_cell = staticmethod(geometry.node_cell)
        edge_occupancies = staticmethod(geometry.edge_occupancies)
        _globally_supported = staticmethod(lambda h, r: getattr(model, "supported", True) is True)

    def shape(g, h, r, legs, destination, zero_view):
        try:
            checker._shape(g, h, r, legs, destination)
            return {"ok": True, "per_member": {}}
        except (ValueError, TypeError, KeyError) as exc:
            return {"ok": False, "reason": str(exc)}

    hazard = {"dt": 1, "version": request.get("hazard_version", 1),
              "members": [{"id": mid} for mid in model.ids]}
    t0 = time.perf_counter()
    raw = frozen_sweep.contact_sweep(graph, hazard, request, model, wall_s=wall_s,
                                    core=Core, check_route_mode=shape, zero_view=None)
    return normalise(raw, "copied_frozen_sweep", time.perf_counter() - t0)
