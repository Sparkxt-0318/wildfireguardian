"""Conservative proven scope for the inherited floating schedule operations."""
from fractions import Fraction
import math

MAX_EXACT_TIME = 2**52


def _integer(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        return None
    try:
        if not math.isfinite(value):return None
        exact=Fraction(value)
        return exact.numerator if exact.denominator==1 else None
    except (OverflowError,ValueError,TypeError):return None


def check_clock_scope(hazard,request):
    """Normal input admission must still run before relying on this predicate.

    This guard is a numerical scope restriction, not an infeasibility claim.
    It never rounds a time, changes a threshold or prunes a search label.
    """
    receipt={"schema":"wfg.exact-transition-clock-scope/4",
             "supported":False,"max_nonnegative_mission_time":MAX_EXACT_TIME,
             "scope":"positive integral dt; nonnegative integral mission times <=2**52; normal exact lattice admission still required",
             "reason":"EXACT_CLOCK_SCOPE_UNSUPPORTED"}
    try:
        dt=_integer(hazard["dt"])
        if dt is None or dt<=0:
            receipt["detail"]="DT_NOT_POSITIVE_INTEGER";return receipt
        times=[("departure",request["departure"]),("horizon",request["horizon"])]
        for i,destination in enumerate(request["destinations"]):
            times.append((f"destination[{i}].dwell",destination["dwell"]))
            for j,(a,b) in enumerate(destination["open_intervals"]):
                times.extend([(f"destination[{i}].opening[{j}]",a),(f"destination[{i}].closing[{j}]",b)])
        for name,value in times:
            integer=_integer(value)
            if integer is None or not 0<=integer<=MAX_EXACT_TIME:
                receipt.update(detail="MISSION_TIME_OUTSIDE_PROVED_INTEGER_SCOPE",field=name)
                return receipt
        if request["horizon"]<request["departure"]:
            receipt["detail"]="HORIZON_BEFORE_DEPARTURE";return receipt
        receipt.update(supported=True,reason="PROVED_NONNEGATIVE_INTEGER_CLOCK")
        return receipt
    except (KeyError,TypeError,ValueError,IndexError,OverflowError):
        receipt["detail"]="CLOCK_SHAPE_NOT_ESTABLISHED"
        return receipt
