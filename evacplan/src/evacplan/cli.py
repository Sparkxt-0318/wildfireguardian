"""``evacplan`` command line.

    evacplan run --method noop --set dev --budget-s 60 [--repeats 5 | --seeds 0 1 2] [--instances ID ...]
                 [--interleave-with b2_vrptw]   (ABAB with B2 in one lock hold, a speed probe before every pair)
    evacplan leaderboard
    evacplan instances [--set dev] [--materialize]
    evacplan generate --size S --tightness 0.5 --graph grid --seed 7 --out DIR
    evacplan build-caldor --cms FILE --geocodes FILE --perimeters FILE --graph FILE --out DIR

``run`` checks every plan with the oracle, upserts ``results/<method>.csv`` and regenerates
``LEADERBOARD.md`` and its margin figures (``figures/`` next to it); it holds the shared bench lock
while timing (``--lock auto`` skips acquiring when a parent ``program/benchlock.py`` already holds it).
``--repeats N`` runs seeds 0 .. N-1: the comparison rule (``program/DECISIONS.md``, 2026-11-01) is
``--repeats 5`` on a quiet machine. ``--set test`` is refused unless ``--allow-test`` is given
(milestones only, after Siyeong approves).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import harness
from .instances import CACHE_DIR, SPLIT_PATH, load_split, materialize


def _seeds(values: list[str]) -> list[int]:
    out: list[int] = []
    for v in values:
        out.extend(int(x) for x in str(v).split(",") if x.strip())
    return out


def _repeats(text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {text!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError("give at least 1 repeat")
    return n


def _paths(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--split", type=Path, default=SPLIT_PATH, help=argparse.SUPPRESS)
    ap.add_argument("--cache-dir", type=Path, default=CACHE_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--results-dir", type=Path, default=harness.RESULTS_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--leaderboard", type=Path, default=harness.LEADERBOARD_PATH, help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="evacplan", description="Track C evacuation planner: harness and instances")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a method on a split set at a fixed wall-clock budget")
    r.add_argument("--method", required=True)
    r.add_argument("--set", dest="set_name", required=True, choices=("dev", "test"))
    r.add_argument("--budget-s", type=float, required=True, help="wall-clock budget per instance and seed (s)")
    seeds = r.add_mutually_exclusive_group()
    seeds.add_argument("--seeds", nargs="+", default=None, help="method seeds (space or comma separated; default 0)")
    seeds.add_argument("--repeats", type=_repeats, default=None,
                       help="seeds 0 .. N-1 (the comparison rule: --repeats 5 on a quiet machine)")
    r.add_argument("--instances", nargs="+", default=None, help="only these instance ids of the set")
    r.add_argument("--config", default=None, help="method configuration as a JSON object")
    r.add_argument("--lock", choices=("auto", "yes", "no"), default="auto", help="shared bench lock (default auto)")
    r.add_argument("--allow-test", action="store_true", help="run the test set (milestones only, with approval)")
    r.add_argument("--no-save-plans", action="store_true", help="do not keep plans and oracle results")
    r.add_argument("--interleave-with", default=None, metavar="METHOD",
                   help="run METHOD (in practice b2_vrptw) in the same lock hold, alternating with --method (ABAB) per "
                        "instance and seed, with a speed probe before every pair")
    r.add_argument("--partner-seed-offset", type=int, default=None,
                   help="the partner's seed = seed + this (default: after its existing rows of this set, budget, host)")
    _paths(r)

    lb = sub.add_parser("leaderboard", help="regenerate LEADERBOARD.md and its margin figures from results/*.csv")
    _paths(lb)

    ins = sub.add_parser("instances", help="list the frozen split (and optionally regenerate it into the cache)")
    ins.add_argument("--set", dest="set_name", default="dev", choices=("dev", "test"))
    ins.add_argument("--materialize", action="store_true", help="regenerate into the cache and verify fingerprints")
    ins.add_argument("--allow-test", action="store_true")
    _paths(ins)

    gen = sub.add_parser("generate", help="write one SYNTHETIC instance (not part of the split)")
    gen.add_argument("--size", required=True, choices=("S", "M", "L"))
    gen.add_argument("--tightness", type=float, required=True)
    gen.add_argument("--graph", default="grid", choices=("grid", "geo"))
    gen.add_argument("--seed", type=int, required=True)
    gen.add_argument("--out", type=Path, required=True)

    cal = sub.add_parser("build-caldor", help="build real US region 1 (Caldor Fire 2021, South Lake Tahoe)")
    from .regions.caldor import add_arguments
    add_arguments(cal)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "run":
        cfg = json.loads(args.config) if args.config else None
        if cfg is not None and not isinstance(cfg, dict):
            print("--config must be a JSON object", file=sys.stderr)
            return 2
        seeds = list(range(args.repeats)) if args.repeats is not None else _seeds(args.seeds or ["0"])
        try:
            harness.run(args.method, args.set_name, args.budget_s, seeds=seeds, instances=args.instances,
                        method_config=cfg, allow_test=args.allow_test, lock=args.lock, split_path=args.split,
                        cache_dir=args.cache_dir, results_dir=args.results_dir, leaderboard_path=args.leaderboard,
                        save_plans=not args.no_save_plans, interleave_with=args.interleave_with,
                        partner_seed_offset=args.partner_seed_offset)
        except harness.TestSetRefused as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 3
        return 0
    if args.cmd == "leaderboard":
        harness.write_leaderboard(args.results_dir, load_split(args.split), args.leaderboard)
        print(args.leaderboard)
        return 0
    if args.cmd == "instances":
        if args.set_name == "test" and args.materialize and not args.allow_test:
            print("refused: the test set is touched only at milestones, after Siyeong approves (--allow-test)",
                  file=sys.stderr)
            return 3
        split = load_split(args.split)
        for e in split.entries(args.set_name):
            path = materialize(e, args.cache_dir) if args.materialize else None
            st = e.stats
            print(f"{e.id}\t{e.label or 'real'}\tfacilities {st.get('facilities')}\tvehicles {st.get('vehicles')}\t"
                  f"residents {st.get('residents')}\tlead {st.get('lead_realized_s')} s" + (f"\t{path}" if path else ""))
        return 0
    if args.cmd == "generate":
        from .generators import SyntheticConfig, generate
        g = generate(SyntheticConfig(size=args.size, tightness=args.tightness, graph=args.graph, seed=args.seed))
        g.write(args.out)
        print(f"{g.instance_id} -> {args.out} (SYNTHETIC; fingerprint {g.fingerprint()})")
        return 0
    if args.cmd == "build-caldor":
        from .regions.caldor import cli_main
        return cli_main(args)
    raise AssertionError(args.cmd)  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
