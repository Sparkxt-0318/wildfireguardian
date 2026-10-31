"""Small independent exact-rational sanity checks; not a proof or census."""
import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1] / "audit-1a"
SOURCE = ROOT / "experimental/flame-front-radiation/src"
sys.path.insert(0, str(SOURCE))
from wfg_flamefront.verified_view import _Arithmetic, _atan_unit, _atan2, _pi, lower_float


def atan_bracket(x, n=160):
    # Direct alternating series, independent of implementation half-angle code.
    total = sum(((-1) ** k * x ** (2*k+1) / (2*k+1) for k in range(n)), F(0))
    nxt = (-1) ** n * x ** (2*n+1) / (2*n+1)
    return min(total, total+nxt), max(total, total+nxt)


pi_a = atan_bracket(F(1, 5))
pi_b = atan_bracket(F(1, 239))
pi_ref = (16*pi_a[0]-4*pi_b[1], 16*pi_a[1]-4*pi_b[0])
counts = {"sqrt": 0, "atan": 0, "pi": 0, "atan2": 0, "lower_float": 0}
sqrt_inputs = [F(0), F(1), F(2), F(3), F(1, 7), F(2**53+1, 2**30+1), F(1, 10**200), F(10**200)]
for precision in (24, 48):
    a = _Arithmetic(precision)
    for exact in sqrt_inputs:
        actual = a(exact).sqrt()
        assert 0 <= F(actual.lo) ** 2 <= exact <= F(actual.hi) ** 2, (precision, exact, actual.lo, actual.hi)
        counts["sqrt"] += 1
    for x in (F(1, 5), F(1, 239), F(1, 2), F(1, 100)):
        ref = atan_bracket(x)
        actual = _atan_unit(a, a(x))
        assert F(actual.lo) <= ref[0] <= ref[1] <= F(actual.hi)
        counts["atan"] += 1
    actual = _pi(a)
    assert F(actual.lo) <= pi_ref[0] <= pi_ref[1] <= F(actual.hi)
    counts["pi"] += 1
    for y, x, ratio in ((1, 1, F(1, 4)), (1, -1, F(3, 4)), (1, 0, F(1, 2)), (0, -1, F(1))):
        actual = _atan2(a, a(y), a(x))
        assert F(actual.lo) <= ratio*pi_ref[0] <= ratio*pi_ref[1] <= F(actual.hi)
        counts["atan2"] += 1

for exact in (F(0), F(1, 3), F(1, 10), F(2**53+1), F(1, 2**1075), F(3, 2**1075), F(2**1023), F(2**1024-2**971)):
    actual = lower_float(exact)
    assert 0 <= F(actual) <= exact
    if math.isfinite(math.nextafter(actual, math.inf)):
        assert F(math.nextafter(actual, math.inf)) > exact
    counts["lower_float"] += 1

result = {"status": "PASS", "scope": "Fixed exact-rational software sanity checks only; no timing, universal proof, platform census, or physical validation.", "source_commit": "43324736fc5301a0444b01b918ef14a0372b1ec3", "source_sha256": hashlib.sha256((SOURCE / "wfg_flamefront/verified_view.py").read_bytes()).hexdigest(), "passed_counts": counts}
Path(__file__).with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result))
