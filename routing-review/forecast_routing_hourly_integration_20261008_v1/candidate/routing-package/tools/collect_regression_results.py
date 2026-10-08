#!/usr/bin/env python3
"""Capture declared fixture results; compare releases without a timing claim.

The --package root chooses one package in a fresh process. Nothing is imported
from the historical archived benchmark drivers or their global workspace paths.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


def normalize(value):
    if isinstance(value, dict):
        return {
            key: normalize(child)
            for key, child in value.items()
            if key not in {"wall_s", "peak_rss_mb", "end_to_end_s"}
            or key == "wall_s"
            and "max_labels" in value
        }
    if isinstance(value, list):
        return [normalize(child) for child in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.package.resolve()))
    from routing.core import solve
    from routing.independent import check_route
    from routing.prepared import prepare_graph
    from routing.replay import replay

    cases = json.loads((args.package / "fixtures/evaluation_cases.json").read_text())[
        "cases"
    ]
    rows = []
    for case in cases:
        for solver in ["baseline", "astar", "dijkstra"]:
            for prepared in [False, True]:
                request = deepcopy(case["request"])
                request["solver"] = solver
                graph = prepare_graph(case["graph"]) if prepared else case["graph"]
                result = solve(graph, case["hazard"], request)
                checked = None
                if result["status"] in {"CONDITIONAL_OPTIMUM", "CHECKED_ROUTE"}:
                    checked = check_route(
                        case["graph"],
                        case["hazard"],
                        request,
                        result["legs"],
                        result["destination"],
                    )
                    if not checked["ok"]:
                        raise RuntimeError("independent witness refused: " + case["id"])
                rows.append(
                    {
                        "case": case["id"],
                        "solver": solver,
                        "prepared": prepared,
                        "result": result,
                        "independent_check": checked,
                    }
                )
    replay_path = args.package / "fixtures/continuity_replay.json"
    if not replay_path.exists():
        replay_path = args.package / "evidence/CONTINUITY_REPLAY_FIXTURE.json"
    fixture = json.loads(replay_path.read_text())
    replay_results = {"raw": replay(fixture), "prepared": replay(fixture, prepare=True)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"rows": rows, "replay": replay_results},
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "rows": len(rows),
                "fixture_cases": len(cases),
                "output": str(args.output),
                "timing_claim": False,
            }
        )
    )


if __name__ == "__main__":
    main()
