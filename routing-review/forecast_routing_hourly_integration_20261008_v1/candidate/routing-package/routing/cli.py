"""Fresh-process checks and JSON routing CLI. Standard library core only."""

import argparse
import json
from pathlib import Path
import time

from .checks import PACKAGE_ROOT, check


def read_fixture(path):
    """Read the explicit fixture, or the bundled example by default."""
    path = path if path is not None else PACKAGE_ROOT / "fixtures/example.json"
    return json.loads(Path(path).read_text())


def solve_fixture(fixture, *, prepare=False):
    """Dispatch to the unchanged service facade; never convert hazard quantities."""
    from .prepared import prepare_graph
    from .service import plan_with_return

    graph = prepare_graph(fixture["graph"]) if prepare else fixture["graph"]
    return plan_with_return(
        graph,
        fixture["hazard"],
        fixture["request"],
        fixture.get("history"),
        fixture.get("return_endpoint"),
        return_budget_s=fixture.get("return_budget_s", 5),
    )


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "solve", "replay"])
    parser.add_argument("--input", type=Path)
    parser.add_argument(
        "--prepare-graph",
        action="store_true",
        help="opt-in owned graph admission for this process; initialization is charged",
    )
    return parser


def main(argv=None):
    """Emit the existing JSON result format; expose argv for callers and tests."""
    args = build_parser().parse_args(argv)
    if args.command == "check":
        result = check()
    else:
        started = time.perf_counter()
        fixture = read_fixture(args.input)
        if args.command == "replay":
            from .replay import replay

            result = replay(fixture, prepare=args.prepare_graph)
        else:
            result = solve_fixture(fixture, prepare=args.prepare_graph)
            if args.prepare_graph:
                result["end_to_end_s"] = time.perf_counter() - started
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0
