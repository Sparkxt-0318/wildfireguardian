"""Reference digests for certificate binding (BINDING_RULE.md rev 2.1, R1 and R6).

The consumer runs this on ITS OWN graph, packet and request and passes the result to either checker as
`--expect G=..,A=..,W=..,Q=..`. The C checker never parses JSON or npz; it only compares 8-word digests.

- G  sha256 of the graph file bytes.
- A  routed-hazard digest: canonical bytes of what the routing path and its guards read
     (npz keys ignition_time_s, current_active, support, per_cell_law_HAZARD_only, absence bound explicitly;
     REPORT.json burning_duration_s, initial_remaining_s, member ids). Not raw file bytes: npz zip entries carry
     timestamps and REPORT/HAZARD embed absolute host paths.
- W  packet_writer_sha256 from HAZARD.json provenance.identity, or 64 zeros if the packet declares none.
- Q  canonical bytes of the request projection wfg.request-projection/1 (the fields build_instance and the at-issue
     check read).

Canonical bytes (R6): RFC 8785 (JCS). Every number is first turned into an exact reduced rational string ("p/q", or
"p" when q = 1) via fractions.Fraction, so the JSON value holds only strings, booleans, null, arrays and objects with
ASCII keys. For such values JCS output equals json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)
of the NFC-normalised value; `canonical()` asserts the restrictions instead of assuming them.

Usage: python3 bind_digests.py --graph G.json --packet PACKET_DIR --request REQ.json [--json]
"""
import argparse
import hashlib
import json
import math
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path

import numpy as np

A_NPZ_KEYS = ("ignition_time_s", "current_active", "support", "per_cell_law_HAZARD_only")
Q_VERSION = "wfg.request-projection/1"
A_VERSION = "wfg.routed-hazard/1"
ABSENT = {"_absent": True}
FIELDS = ("G", "A", "W", "Q")


def rat(x):
    """Exact reduced rational string of an int, float or numeric string. Non-finite values are refused."""
    if isinstance(x, bool):
        raise ValueError("boolean where a number is expected")
    if isinstance(x, float) and not math.isfinite(x):
        raise ValueError("non-finite number %r" % x)
    f = Fraction(x)
    return str(f.numerator) if f.denominator == 1 else "%d/%d" % (f.numerator, f.denominator)


def _check(v, path="$"):
    if v is None or isinstance(v, bool):
        return
    if isinstance(v, str):
        if unicodedata.normalize("NFC", v) != v:
            raise ValueError("%s: string not NFC" % path)
        return
    if isinstance(v, list):
        for i, x in enumerate(v):
            _check(x, "%s[%d]" % (path, i))
        return
    if isinstance(v, dict):
        for k, x in v.items():
            if not isinstance(k, str) or not k.isascii():
                raise ValueError("%s: non-ASCII or non-string key %r" % (path, k))
            _check(x, "%s.%s" % (path, k))
        return
    raise ValueError("%s: %s not allowed in a canonical value (numbers must be rat() strings)" % (path, type(v).__name__))


def canonical(v):
    _check(v)
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _get(d, *keys):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return ABSENT
        d = d[k]
    return d


def _num_or_absent(v):
    return v if v is ABSENT else (None if v is None else rat(v))


def q_projection(request):
    """wfg.request-projection/1: exactly the request fields frontend.build_instance and the at-issue check read."""
    dests = request.get("destinations", ABSENT)
    if dests is not ABSENT:
        dests = [{"node": _get(d, "node"), "dwell": _num_or_absent(_get(d, "dwell")),
                  "open_intervals": (ABSENT if _get(d, "open_intervals") is ABSENT else
                                     [[rat(a), rat(b)] for a, b in d["open_intervals"]])} for d in dests]
    budgets = _get(request, "budgets", "dose")
    incurred = request.get("incurred", ABSENT)
    return {"version": Q_VERSION,
            "position_node": _get(request, "position", "node"),
            "incoming_edge": _get(request, "incoming_edge"),
            "departure": _num_or_absent(_get(request, "departure")),
            "horizon": _num_or_absent(_get(request, "horizon")),
            "destinations": dests,
            "budgets_dose": budgets if budgets is ABSENT else {k: rat(v) for k, v in budgets.items()},
            "incurred": incurred if incurred is ABSENT else {k: rat(v) for k, v in incurred.items()}}


def _array_entry(name, a):
    if a is None:
        return {"name": name, "present": False}
    x = np.ascontiguousarray(a)   # raw IEEE bytes, non-finite values included: bound as they are, guarded elsewhere
    return {"name": name, "present": True, "dtype": x.dtype.str, "shape": [rat(int(n)) for n in x.shape],
            "data_hex": x.tobytes().hex()}


def a_projection(packet_dir):
    """wfg.routed-hazard/1. ignition_time_s keeps +inf ('never ignites') and NaN/-inf as raw IEEE bytes: they are
    bound, and require_routable_arrays refuses NaN/-inf separately."""
    d = Path(packet_dir)
    with np.load(d / "constructed_arrays.npz", allow_pickle=False) as z:
        arrays = [_array_entry(k, z[k] if k in z.files else None) for k in A_NPZ_KEYS]
    report = json.loads((d / "REPORT.json").read_text())
    ass = _get(report, "native_metadata", "construction", "assumptions")
    rows = _get(report, "rows")
    ids = ABSENT
    if rows is not ABSENT and rows:
        inc = _get(rows[0], "request", "incurred")
        ids = ABSENT if inc is ABSENT else list(inc)
    return {"version": A_VERSION, "arrays": arrays,
            "burning_duration_s": _num_or_absent(_get(ass, "burning_duration_s")),
            "initial_remaining_s": _num_or_absent(_get(ass, "initial_remaining_s")),
            "member_ids": ids}


def writer_sha(packet_dir):
    hz = json.loads((Path(packet_dir) / "HAZARD.json").read_text())
    w = ((hz.get("provenance") or {}).get("identity") or {}).get("packet_writer_sha256")
    if w is None:
        return "0" * 64
    if not (isinstance(w, str) and len(w) == 64 and all(c in "0123456789abcdef" for c in w)):
        raise ValueError("packet_writer_sha256 is not 64 lowercase hex: %r" % (w,))
    return w


def digests(graph_path, packet_dir, request):
    if not isinstance(request, dict):
        request = json.loads(Path(request).read_text())
    return {"G": hashlib.sha256(Path(graph_path).read_bytes()).hexdigest(),
            "A": hashlib.sha256(canonical(a_projection(packet_dir))).hexdigest(),
            "W": writer_sha(packet_dir),
            "Q": hashlib.sha256(canonical(q_projection(request))).hexdigest()}


def words(hexdigest):
    """The 8 big-endian 32-bit words of a SHA-256 hex digest, as written in a BIND record."""
    return [int(hexdigest[8 * i:8 * i + 8], 16) for i in range(8)]


def expect_arg(dg):
    return ",".join("%s=%s" % (k, dg[k]) for k in FIELDS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--graph", required=True)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--request", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    dg = digests(a.graph, a.packet, a.request)
    print(json.dumps(dg, indent=1) if a.json else expect_arg(dg))


if __name__ == "__main__":
    sys.exit(main())
