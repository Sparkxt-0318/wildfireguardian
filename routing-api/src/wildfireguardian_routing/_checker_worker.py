"""Executed in an isolated interpreter; not imported by the parent application."""
import json
from fractions import Fraction
from pathlib import Path
import sys
import time


def json_exact(value):
    if isinstance(value, Fraction):
        return str(value)
    raise TypeError(f"Unsupported checker output type: {type(value).__name__}")


def main():
    release, incoming, outgoing = map(Path, sys.argv[1:])
    sys.path.insert(0, str(release / "candidate"))
    sys.path.insert(0, str(release / "candidate/routing-package"))
    from hybrid_checker import HybridChecker
    payload = json.loads(incoming.read_text())
    # Charge checker construction against the requested shared primary deadline.
    deadline = time.perf_counter() + float(payload["wall_s"])
    checker = HybridChecker(payload["case_directory"], settings=payload["settings"])
    result = checker.check(payload["graph"], payload["request"], payload["legs"], payload["destination"],
                           wall_s=payload["wall_s"], deadline=deadline,
                           expected_graph_revision=payload["expected_graph_revision"],
                           expected_graph_sha256=payload["expected_graph_sha256"])
    outgoing.write_text(json.dumps(result, allow_nan=False, default=json_exact))


if __name__ == "__main__":
    main()
