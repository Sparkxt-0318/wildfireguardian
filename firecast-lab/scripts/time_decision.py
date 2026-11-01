"""TIMING ONLY: the decision metric's cost per window, on a real road graph with a SYNTHETIC hazard.

This reruns the number behind "about 4.6 min per window" in README.md and METRICS.md section 7.6. It runs one window
of ``firecast_lab.decision.decide_window`` exactly as ``firecast-lab decision`` does: K members under both
couplings, the K-curve member orders, ``RequestConfig`` requests, and reconstruction truth with and without the
partly burned ring. The road graph is real (default: the Uljin KFS_02 dev graph). The fire is SYNTHETIC: the
elliptical test fire of ``tests/synthetic.py`` on that fire's event grid (events.json metadata only: shape,
transform, CRS). The model is a calibrated dilation fitted on SYNTHETIC windows. No number printed here says anything
about a real fire. Test fires are refused. Run it through the bench lock::

    python program/benchlock.py --label fl-decision-timing -- \\
        .venv/bin/python firecast-lab/scripts/time_decision.py --graphs "$FIRECAST_GRAPHS"

It prints one JSON line: seconds for the requests and for the whole window, the median trip, and the extrapolation
to the Korean dev windows that have road graphs. That window count is approximate (SPLITS.json
``approx_windows_24h``, from events.json times, not the exact window rule), and every window is charged the
cost of this graph's window. Commit, host, Python and the config come with it.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "tests"))          # the SYNTHETIC fire and window generators of the test suite
sys.dont_write_bytecode = True

import synthetic as syn  # noqa: E402

from firecast_lab import baselines as bl  # noqa: E402
from firecast_lab import data as fd  # noqa: E402
from firecast_lab import decision as dm  # noqa: E402
from firecast_lab import splits as sp  # noqa: E402

FIRE_SEED, HOURS_PER_CELL = 7, 2.0               # the SYNTHETIC fire of the original timing (2026-10-31)


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--graphs", default=None, help=f"road-graph folder (default: ${dm.GRAPHS_ENV})")
    parser.add_argument("--fire", default="KFS_02", help="a dev fire with a road graph (its grid and graph only)")
    parser.add_argument("--window", type=int, default=1, help="which window of the SYNTHETIC fire to time")
    parser.add_argument("--members", type=int, default=64)
    parser.add_argument("--requests", type=int, default=dm.RequestConfig.n_requests)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=None, help="also write the JSON line to this file")
    args = parser.parse_args(argv)

    splits = sp.load_splits()
    record = fd.check_access(args.fire, splits=splits)            # refuses test fires and the fresh holdout
    path = dm.graph_path(dm.graphs_root(args.graphs), args.fire)
    if path is None:
        raise dm.RoadGraphsNotFound(f"{args.fire} has no road graph under {dm.graphs_root(args.graphs)}")
    catalog = {e["id"]: e for e in sp.load_catalog()[0]}[args.fire]
    shape = (catalog["height"], catalog["width"])
    arrival, *_ = syn.fire(shape, seed=FIRE_SEED, hours_per_cell=HOURS_PER_CELL)       # SYNTHETIC
    event = dict(syn.event(f"SYNTHETIC_ON_{args.fire}_GRID", shape), transform=list(catalog["transform"]),
                 epsg=catalog["epsg"])
    window = list(fd.windows_from_arrays(event, arrival, 24, record=dict(record, id=event["id"])))[args.window]
    train = syn.windows("SYNTHETIC_0", *syn.fire(seed=0)) + syn.windows("SYNTHETIC_1", *syn.fire(seed=1))
    model = bl.CalibratedDilation().fit(train)
    graph = dm.load_road_graph(path)
    config = dm.RequestConfig(n_requests=args.requests)

    start = time.perf_counter()
    requests = dm.requests_for(window, graph, seed=args.seed, config=config)
    requests_s = time.perf_counter() - start
    start = time.perf_counter()
    rows, note = dm.decide_window(window, graph, model, K=args.members, seed=args.seed,
                                  truth=dm.truth_from_reconstruction(window), truth_kind="SYNTHETIC reconstruction",
                                  truth_centre_in=dm.truth_from_reconstruction(window, partly_burned=False),
                                  config=config, repeats=args.repeats)
    window_s = time.perf_counter() - start
    dev_windows = sum(f["approx_windows_24h"] for f in splits["fires"]
                      if f["id"] in dm.GRAPH_FOLDERS and f["split"] == "dev")
    out = dict(synthetic=True, note="SYNTHETIC hazard on a real road graph: timing only, not a result",
               fire_grid=args.fire, graph=str(path), graph_nodes=len(graph.nodes), graph_edges=len(graph.edges),
               window_cutoff=window.cutoff_utc, requests_built=note["requests_built"],
               median_edges_per_request=float(np.median([len(r.edges) for r in requests.requests])),
               requests_s=round(requests_s, 1), window_s=round(window_s, 1), window_min=round(window_s / 60.0, 2),
               korean_dev_windows_with_graphs_approx=dev_windows,
               minutes_per_model_approx=round(window_s * dev_windows / 60.0),
               **fd.run_record(dict(command="time_decision", members=args.members, requests=args.requests,
                                    repeats=args.repeats, couplings=["shared", "copula"], window=args.window,
                                    fire_seed=FIRE_SEED, hours_per_cell=HOURS_PER_CELL), args.seed))
    text = json.dumps(out)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    return out


if __name__ == "__main__":
    try:
        main()
    except (dm.RoadGraphsNotFound, PermissionError, ValueError) as error:
        sys.exit(f"error: {error}")
