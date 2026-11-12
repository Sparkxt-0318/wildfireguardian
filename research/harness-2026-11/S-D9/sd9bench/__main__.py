"""CLI: python -m sd9bench --out RESULTS.json [--predictors a,b] [--draws N] FILE.npz ...

Run with research/harness-2026-11/S-D9 on PYTHONPATH. The output directory must
not already contain the target file (no overwrite).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from . import load, score


def _clean(o):
    if isinstance(o, float):
        return None if math.isnan(o) else ("Infinity" if math.isinf(o) else o)
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item"):
        return _clean(o.item())
    return o


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="sd9bench")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--predictors", default=None, help="comma-separated subset; references must be included")
    ap.add_argument("--draws", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261030)
    ap.add_argument("--mc", action="append", default=[], metavar="NAME=N",
                    help="declare N Monte Carlo trajectories behind predictor NAME (repeatable)")
    args = ap.parse_args(argv)
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    names = args.predictors.split(",") if args.predictors else None
    mc = {k: int(v) for k, v in (x.split("=", 1) for x in args.mc)}
    result = score(load(args.files, names), draws=args.draws, seed=args.seed, mc_trajectories=mc)
    args.out.write_text(json.dumps(_clean(result), indent=1, sort_keys=True, allow_nan=False) + "\n")
    print(f"wrote {args.out}: {result['entries']} entries, {result['positives']} positives, "
          f"{len(result['fires'])} fires")


if __name__ == "__main__":
    main()
