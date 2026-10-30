"""Explicit seam for the copied journey checker and gated radiation law v2."""


def evaluate_decision(decision, *, radiation_law="v1", v1_evaluator=None, **kwargs):
    if radiation_law == "v2":
        raise NotImplementedError("law v2 not available: physics and enclosure gates unresolved")
    if radiation_law != "v1":
        raise ValueError("radiation_law must be v1 or v2")
    if v1_evaluator is None:
        raise ValueError("Complete law-v1 evaluator required")
    return v1_evaluator(decision, **kwargs)
