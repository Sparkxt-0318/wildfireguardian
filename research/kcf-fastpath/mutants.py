"""Can the equality tests see a wrong fast solver? Each mutant breaks one rule of fastfield.py; test_fastfield.run
must report failures for every mutant and none for the unmutated code.

    python3 research/kcf-fastpath/mutants.py [N_PER_FAMILY] [OUT_JSON]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fastfield as ff  # noqa: E402
import test_fastfield as T  # noqa: E402

ORIG = {k: getattr(ff, k) for k in ("_upward_ok", "_downward_ok", "forward_lower_bound", "_for_origin",
                                    "dest_lower_bound")}


def assume_m1_m2(ivs, lo, hi):
    """Hypotheses M1/M2 assumed, never checked (closure taken as permanent from its first second in the window)."""
    ok, c = ORIG["_upward_ok"](ivs, lo, hi)
    if ok:
        return ok, c
    first = min((max(a, lo) for a, b in ivs if b >= lo and a <= hi), default=hi + 1)
    return True, first


def assume_m3(ivs, lo, hi):
    """Hypothesis M3 assumed: a late-opening shelter treated as open from the window start."""
    ok, a = ORIG["_downward_ok"](ivs, lo, hi)
    if ok:
        return ok, a
    return True, max(min(b, hi) for a_, b in ivs if b >= lo and a_ <= hi)


def bound_too_high(inst, origins):
    """Pruning bound one second too high (claims journeys arrive later than they can)."""
    e = ORIG["forward_lower_bound"](inst, origins)
    return [x + 1 if x < ff.INF and x > 0 else x for x in e]


def bound_ignores_short_edges(inst, origins):
    """Pruning bound from a search that skips the shortest edges (not a lower bound any more)."""
    D = inst.D
    saved = list(D)
    inst.D = [d + (1 if d == min(saved) else 0) for d in saved]
    try:
        return ORIG["forward_lower_bound"](inst, origins)
    finally:
        inst.D = saved


def dest_bound_plus_1(inst):
    """Destination-side window one second too narrow (h overestimated): a reopening just inside the usable window
    is missed."""
    return [x + 1 if 0 < x < ff.INF else x for x in ORIG["dest_lower_bound"](inst)]


def no_guard(fld, o, fallback):
    """Pruned field read for an origin outside its forward search."""
    return fld


MUTANTS = {
    "none": {},
    "assume_M1_M2": {"_upward_ok": assume_m1_m2},
    "assume_M3": {"_downward_ok": assume_m3},
    "prune_bound_plus_1": {"forward_lower_bound": bound_too_high},
    "prune_bound_not_lower": {"forward_lower_bound": bound_ignores_short_edges},
    "prune_no_origin_guard": {"_for_origin": no_guard},
    "window_dest_bound_plus_1": {"dest_lower_bound": dest_bound_plus_1},
}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    out = {}
    for name, patch in MUTANTS.items():
        for k, v in ORIG.items():
            setattr(ff, k, v)
        for k, v in patch.items():
            setattr(ff, k, v)
        res = T.run(n)
        out[name] = {"failures": res["failures"], "first": res["first_failures"][:3]}
        print(name, res["failures"], flush=True)
    for k, v in ORIG.items():
        setattr(ff, k, v)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
    bad = out["none"]["failures"] != 0 or any(out[m]["failures"] == 0 for m in MUTANTS if m != "none")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
