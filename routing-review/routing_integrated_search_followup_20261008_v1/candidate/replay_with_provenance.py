#!/usr/bin/env python3
"""Documented historical replay with complete source and assumption context."""
import time
STARTED = time.perf_counter()
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import resource
import sys

from hourly import DELIVERY, digest, read, replay_pipeline, save, proof_level
from hazard_constructor import ConstructionConfig, load_snapshot, construct_hazard
IMPORTS_DONE = time.perf_counter()


def enrich_replay(report, graph_path, snapshot_path, metadata_path, config):
    """Add source context without changing execution/history/numerical outcomes."""
    started = time.perf_counter()
    arrays, metadata = load_snapshot(snapshot_path, metadata_path)
    construction = construct_hazard(arrays, metadata, mode="research", config=config)
    graph = read(graph_path); graph = graph.get("graph", graph)
    initial = next(e for e in report["events"] if e["kind"] == "initial_plan")
    request = initial["result"]["request"]
    report["initial_forecast_context"] = {
        "npz_sha256": digest(snapshot_path), "metadata_sha256": digest(metadata_path),
        "checkpoint_sha256": metadata.get("checkpoint_sha256"),
        "original_metadata": metadata, "mode": "research",
        "assumption_id": config.assumption_id, "assumptions": asdict(config),
        "construction_metadata": construction["metadata"],
        "original_support": {"known_probability_cells": metadata.get("known_probability_cells"),
                             "unknown_probability_cells": metadata.get("unknown_probability_cells"),
                             "finite_expected_flux_cells": metadata.get("finite_expected_flux_cells"),
                             "initial_active_burning_probability_supplied": metadata.get("initial_active_burning_probability_supplied")},
        "constructed_support": {"supported": int(construction["arrays"]["support"].sum()),
                                "total": int(construction["arrays"]["support"].size)},
        "scenario_ids": list(request["incurred"]), "scenario_count": len(request["incurred"]),
        "graph_revision": graph["revision"], "time_origin": metadata["cutoff_utc"],
        "assigned_historical_issue_time": metadata["cutoff_utc"],
        "assigned_historical_availability": request["as_of"],
        "actual_source_generation": metadata.get("generated_at_utc"),
        "availability_provenance": "hypothetical historical replay clock; original current state retrospectively assembled",
        "physical_safety_claim": False,
    }
    initial["proof_level"] = proof_level(initial["result"])
    initial["runtime_s"] = {"router_search_including_internal_check": initial["result"].get("metrics", {}).get("wall_s")}
    report.setdefault("runtime_s", {})["additional_context_construction"] = time.perf_counter() - started
    report["memory"] = {"process_peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default=str(DELIVERY / "sample/uljin_graph.json"))
    parser.add_argument("--snapshot", default=str(DELIVERY / "sample/korean_native/20220304T030000Z.npz"))
    parser.add_argument("--metadata", default=str(DELIVERY / "sample/korean_native/20220304T030000Z.json"))
    parser.add_argument("--request", default=str(DELIVERY / "sample/query_simple.json"))
    parser.add_argument("--next-snapshot", default=str(DELIVERY / "sample/korean_native/20220304T060000Z.npz"))
    parser.add_argument("--next-metadata", default=str(DELIVERY / "sample/korean_native/20220304T060000Z.json"))
    parser.add_argument("--config")
    parser.add_argument("--output-dir", default=str(DELIVERY / "results/documented_replay"))
    args = parser.parse_args()
    config = ConstructionConfig(**read(args.config)) if args.config else ConstructionConfig()
    before = time.perf_counter()
    report = replay_pipeline(args.graph, args.snapshot, args.metadata, args.request,
                             config=config, next_snapshot=args.next_snapshot, next_metadata=args.next_metadata)
    ended = time.perf_counter()
    report = enrich_replay(report, args.graph, args.snapshot, args.metadata, config)
    report["runtime_s"].update(startup_imports=IMPORTS_DONE - STARTED,
                                replay_pipeline=ended - before,
                                total_in_process=time.perf_counter() - STARTED)
    save(Path(args.output_dir) / "REPLAY.json", report)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
