"""Fail-closed integration seam while the mandatory physics gate is unresolved.

No copied full-journey adapter is represented as complete. The frozen evaluator
can be injected for law v1. The v2 integration campaign must remain unrun until
source-comparable physics evidence and the continuous-journey checker exist.
"""


def evaluate_decision(decision, *, radiation_law="v1", v1_evaluator=None, **kwargs):
    if radiation_law=="v2":
        raise NotImplementedError("law v2 physics gate unresolved; full-journey integration is not admitted")
    if radiation_law!="v1":raise ValueError("radiation_law must be v1 or v2")
    if v1_evaluator is None:raise ValueError("supply the unchanged complete v1 journey evaluator")
    return v1_evaluator(decision,**kwargs)
