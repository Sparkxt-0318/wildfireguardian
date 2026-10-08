#!/usr/bin/env python3
"""Original hourly forecast -> declared construction -> maintained routing.

Numeric NPZ inputs only. Research mode is explicit, and all routing results
remain conditional on the supplied construction and finite scenario set.
"""
import time
STARTED = time.perf_counter()
import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import resource
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DELIVERY = ROOT.parent
sys.path.insert(0, str(ROOT / "routing-package"))
import numpy as np
from forecast_bridge import convert, IntegrationError
from routing.core import solve
from routing.independent import check_route
from routing.prepared import prepare_graph
from routing.session import RoutingSession
IMPORTS_DONE = time.perf_counter()


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise IntegrationError("TIME_METADATA", "Timezone-aware timestamps required")
    return dt.astimezone(timezone.utc)


def jsonbytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def build_hazard(graph, arrays, metadata, *, mode="strict", config=None,
                 origin=None, version=1, parent_sha256=None,
                 availability_delay_s=0):
    """Construct a new, distinctly identified future and preserve north-up data.

    Scenario identity is construction/version specific. A new future does not
    claim to be the old physical realization; update history is recombined
    conservatively by accept_constructed_update instead of resampling old IDs.
    """
    from hazard_constructor import construct_hazard
    if parent_sha256 is None:
        parent_sha256 = metadata.get("native_snapshot_sha256")
    if parent_sha256 is None:
        # Library callers without a file still receive an actual numeric-content
        # digest. The CLI records the original NPZ byte hash instead.
        content = hashlib.sha256(jsonbytes(metadata))
        for name in sorted(arrays):
            array = np.asarray(arrays[name])
            content.update(name.encode()); content.update(str(array.dtype).encode())
            content.update(jsonbytes(list(array.shape))); content.update(array.tobytes())
        parent_sha256 = content.hexdigest()
    constructor_begin = time.perf_counter()
    constructed = construct_hazard(arrays, metadata, mode=mode, config=config)
    constructor_done = time.perf_counter()
    fields = constructed["arrays"]
    details = constructed["metadata"]
    cutoff = utc(metadata["cutoff_utc"])
    origin_dt = utc(origin) if origin is not None else cutoff
    offset = (cutoff - origin_dt).total_seconds()
    if not math.isfinite(availability_delay_s) or availability_delay_s < 0:
        raise IntegrationError("CAUSAL_TIME", "Availability delay must be nonnegative")
    avail = cutoff + timedelta(seconds=availability_delay_s)
    identity_input = {"mode": mode, "version": version,
                      "parent_sha256": parent_sha256,
                      "cutoff": cutoff.isoformat(), "construction": details}
    construction_id = hashlib.sha256(jsonbytes(identity_input)).hexdigest()
    flux = np.asarray(fields["flux_w_m2"])
    support = np.asarray(fields["support"])
    ids = ["construction:" + construction_id[:20] + ":" + str(i)
           for i in range(flux.shape[0])]
    original_support = {
        "known_probability_cells": metadata.get("known_probability_cells"),
        "unknown_probability_cells": metadata.get("unknown_probability_cells"),
        "finite_expected_flux_cells": metadata.get("finite_expected_flux_cells"),
        "initial_active_burning_probability_supplied": metadata.get("initial_active_burning_probability_supplied"),
        "complete_expected_flux_available": metadata.get("complete_expected_flux_available"),
    }
    constructed_support = {"supported": int(support.sum()),
                           "total": int(support.size),
                           "fraction": float(support.mean()),
                           "constructor_status": constructed["status"]}
    physical = details.get("physical_scope", "Scenario radiant heat using illustrative combustion and finite-domain cell-center receiver geometry; excludes smoke, convective heat, embers and omitted-domain emissions")
    md = {
        "schema": "wfg.forecast.native-intervals/2", "mode": mode,
        "assumption_id": details.get("assumption_id") or "strict-original-support-v1",
        "parent_forecast_sha256": parent_sha256,
        "original_support": original_support, "constructed_support": constructed_support,
        "construction_id": construction_id, "construction": details,
        "graph_revision": graph["revision"], "crs": "EPSG:" + str(metadata["epsg"]),
        "shape": metadata["shape"], "affine_transform": metadata["affine_transform"],
        "flux_units": "W/m2", "flux_semantics": "interval_upper_bound_incident_radiant_flux",
        "flame_semantics": "contact_anywhere_during_interval",
        # Strict includes current-state uncertainty in the joint false support.
        "present_fire_included": True,
        "present_fire_support": "included in unknown joint support" if mode == "strict" else "explicit declared assumed state",
        "physical_scope": physical, "evidence_class": "MENTOR_FORECAST" if mode == "strict" else "RESEARCH_CONSTRUCTION",
        "source": "Original hourly mentor forecast numeric export with separately identified constructor",
        "time_origin": origin_dt.isoformat(), "issued_at": cutoff.isoformat(),
        "available_at": avail.isoformat(),
        "availability_provenance": "historical replay availability assignment; retrospective current state is not a live observed input",
        "source_generated_at_utc": metadata.get("generated_at_utc"),
        "construction_generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "breakpoints_s": (np.asarray(fields["time_edges_s"]) + offset).tolist(),
        "dt_s": metadata.get("routing_dt_s", 1), "version": version,
        "routing_lattice_assignment": "Explicit 1-second lattice matching the frozen Uljin graph travel_ticks; not forecast resolution",
        "unsupported_channels": ["smoke", "convective_heat", "embers", "secondary_ignition", "omitted_domain_sources"],
        "scenario_history_contract": "new future identities; conservative product with accepted past exposure ledger",
    }
    members = [{"id": mid, **{k: np.asarray(fields[k])[i] for k in
                            ("flux_w_m2", "flame_contact", "support")}}
               for i, mid in enumerate(ids)]
    hazard = convert(graph, md, members)
    constructed["integration_runtime_s"] = {"hazard_construction": constructor_done - constructor_begin,
                                            "native_adapter_and_metadata": time.perf_counter() - constructor_done}
    return hazard, constructed, md


def request_for_hazard(template, hazard, *, shift=True):
    """Copy a frozen query; adapt identities/time without altering budgets."""
    req = deepcopy(template.get("request", template))
    old_dose = list(req["budgets"]["dose"].values())
    if not old_dose or any(x != old_dose[0] for x in old_dose):
        raise IntegrationError("BUDGET_MAPPING", "Frozen query must use a common dose budget for constructed members")
    if any(float(x) != 0 for x in req.get("incurred", {}).values()):
        raise IntegrationError("HISTORY_MAPPING", "Existing incurred dose requires explicit session transfer")
    ids = [m["id"] for m in hazard["members"]]
    req["incurred"] = {mid: 0 for mid in ids}
    req["budgets"]["dose"] = {mid: old_dose[0] for mid in ids}
    req["hazard_version"] = hazard["version"]
    req["as_of"] = hazard["available_at"]
    if shift:
        offset = hazard["valid_from"]
        req["departure"] += offset
        req["horizon"] += offset
        for dest in req["destinations"]:
            dest["open_intervals"] = [[a + offset, b + offset] for a, b in dest["open_intervals"]]
    # Coverage is never extended; an overlong frozen query is refused by the
    # unchanged maintained validator rather than silently shortening its dwell.
    return req


def accept_constructed_update(session, hazard, as_of):
    """Join every new future with every accepted past history using max dose.

    This is a conservative Cartesian recombination within the accepted finite
    old ensemble. It is not a joint flame trajectory or real-fire guarantee.
    Changed assumptions apply prospectively. Unverified elapsed gaps cannot be
    crossed by replacing a forecast, and unknown history cannot become zero.
    """
    def refused(reason, **details):
        # Mirror the maintained session's rejected-update invalidation: keep
        # accepted hazard/progress, invalidate pending completions, and mark any
        # retained guidance as belonging to the older accepted version.
        session.generation += 1
        event = {"status": "UNSUPPORTED", "reason": reason,
                 "request_generation": session.generation,
                 "hazard_version": session.hazard.get("version") if session.hazard else None,
                 "rejected_version": hazard.get("version"), **details}
        session.last_update = deepcopy(event)
        return deepcopy(event)

    progress = session.progress
    if progress is not None:
        if progress["departure"] < hazard["valid_from"]:
            return refused("HISTORY_GAP_REQUIRES_VERIFIED_PROGRESS",
                           recorded_departure=progress["departure"], new_valid_from=hazard["valid_from"],
                           incurred_preserved=deepcopy(progress["incurred"]))
        values = list(progress["incurred"].values())
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 for x in values):
            return refused("HISTORY_SUPPORT_UNKNOWN")
        bound = max(values, default=0)
        mapping = {m["id"]: bound for m in hazard["members"]}
    else:
        mapping = None
    event = session.accept_update(hazard, as_of, conservative_mapping=mapping)
    event["history_transfer"] = {
        "law": "all new futures crossed with all accepted old supplied histories",
        "mapping": mapping, "past_assumptions_retained": True,
        "future_assumptions_prospective": True, "physical_history_correspondence_claim": False,
    }
    return event


def proof_level(result):
    if result.get("status") == "CONDITIONAL_OPTIMUM":
        return "exact finite supplied-scenario lattice optimum after independent check"
    if result.get("status") == "CHECKED_ROUTE":
        return "checked finite supplied-scenario witness; no global optimum claim"
    if result.get("status") == "PROVEN_INFEASIBLE":
        return "finite supplied-scenario contract infeasibility only"
    return "unresolved or refused; TIMEOUT remains unresolved"


def checked_dose_upper(row):
    """Encode an independent check's rational dose without rounding downward."""
    value = float(row["dose"])
    exact = Fraction(row.get("dose_exact", value))
    if Fraction(value) < exact:
        value = math.nextafter(value, math.inf)
    if not math.isfinite(value):
        raise IntegrationError("HISTORY_SUPPORT_UNKNOWN", "Cannot encode finite conservative incurred bound")
    return value


def run_pipeline(graph_path, snapshot_path, metadata_path, request_path, *,
                 mode="strict", config=None, origin=None, version=1, repeats=1,
                 output_dir=None, save_hazard=False):
    from hazard_constructor import load_snapshot
    begin = time.perf_counter()
    graph = read(graph_path)
    graph = graph.get("graph", graph)
    template = read(request_path)
    arrays, metadata = load_snapshot(snapshot_path, metadata_path)
    loaded = time.perf_counter()
    parent_sha = digest(snapshot_path)
    hazard, constructed, native_md = build_hazard(
        graph, arrays, metadata, mode=mode, config=config, origin=origin,
        version=version, parent_sha256=parent_sha)
    made = time.perf_counter()
    prepared = prepare_graph(graph)
    prepped = time.perf_counter()
    request = request_for_hazard(template, hazard)
    rows = []
    for iteration in range(repeats):
        start = time.perf_counter()
        result = solve(prepared, hazard, request)
        searched = time.perf_counter()
        checked = None
        if result.get("destination") is not None and result.get("legs") is not None:
            checked = check_route(graph, hazard, request, result["legs"], result["destination"])
            if result.get("status") in ("CONDITIONAL_OPTIMUM", "CHECKED_ROUTE") and not checked["ok"]:
                result = {**result, "status": "INTEGRATION_CHECK_FAILED"}
        end = time.perf_counter()
        rows.append({"iteration": iteration, "temperature": "cold query" if iteration == 0 else "warm query reused payload/preparation",
                     "request": request, "result": result, "independent_checker": checked,
                     "proof_level": proof_level(result), "physical_safety_claim": False,
                     "runtime_s": {"search_call_including_router_check": searched - start,
                                   "additional_independent_check": end - searched,
                                   "query_total": end - start}})
    done = time.perf_counter()
    report = {"schema": "wfg.hourly.integration-report/1", "mode": mode,
              "assumption_id": native_md["assumption_id"], "native_metadata": native_md,
              "forecast": {"npz_sha256": parent_sha, "metadata_sha256": digest(metadata_path),
                           "checkpoint_sha256": metadata.get("checkpoint_sha256"),
                           "cutoff_utc": metadata["cutoff_utc"], "evidence": metadata.get("evidence")},
              "graph_revision": graph["revision"], "rows": rows,
              "runtime_s": {"startup_imports": IMPORTS_DONE - STARTED,
                            "cli_or_caller_pre_pipeline_elapsed": begin - IMPORTS_DONE,
                            "load_graph_query_original_forecast": loaded - begin,
                            "forecast_inference": {"status": "PRECOMPUTED_NATIVE_EXPORT", "reported_prior_s": metadata.get("seconds")},
                            "construction_and_adapter": made - loaded,
                            **constructed["integration_runtime_s"],
                            "graph_preparation": prepped - made,
                            "measured_in_process_total": done - STARTED,
                            "cold_total_including_load_construction_preparation": prepped - STARTED + rows[0]["runtime_s"]["query_total"],
                            "warm_query_total": [r["runtime_s"]["query_total"] for r in rows[1:]]},
              "memory": {"process_peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024),
                         "constructed_array_bytes": sum(np.asarray(v).nbytes for v in constructed["arrays"].values()),
                         "serialized_hazard_bytes": len(jsonbytes(hazard))},
              "physical_safety_claim": False,
              "limits": ["Uljin development integration only", "finite sampled scenarios do not establish real-fire coverage", "historical retrospectively assembled state is not live cutoff evidence", "interval enclosures may refuse routes feasible under exact events", "routing budgets are unchanged supplied software contract numbers"]}
    if output_dir:
        output = Path(output_dir)
        save(output / "REPORT.json", report)
        save(output / "NATIVE_METADATA.json", native_md)
        if save_hazard:
            save(output / "HAZARD.json", hazard)
        np.savez_compressed(output / "constructed_arrays.npz", **constructed["arrays"])
    return report


def replay_pipeline(graph_path, snapshot_path, metadata_path, request_path, *,
                    config=None, next_snapshot=None, next_metadata=None, output_dir=None):
    """Exercise real constructed fields plus lifecycle refusal, no dose reset.

    A stationary ten-second modeled prefix is independently checked as a
    destination dwell. If the supplied fields refuse it, progress is not
    invented and history demonstration remains explicitly unsupported.
    """
    from hazard_constructor import load_snapshot
    replay_started = time.perf_counter()
    graph = read(graph_path); graph = graph.get("graph", graph)
    arrays, metadata = load_snapshot(snapshot_path, metadata_path)
    origin = metadata["cutoff_utc"]
    h1, c1, md1 = build_hazard(graph, arrays, metadata, mode="research", config=config,
                              origin=origin, parent_sha256=digest(snapshot_path))
    req = request_for_hazard(read(request_path), h1)
    session = RoutingSession(graph, prepare=True, graph_ownership="snapshot")
    events = [{"kind": "initial_update", "event": accept_constructed_update(session, h1, h1["available_at"])}]
    plan_started = time.perf_counter()
    first = session.plan(req)
    plan_finished = time.perf_counter()
    events.append({"kind": "initial_plan", "result": first, "commit": session.commit(first),
                   "native_metadata": md1, "proof_level": proof_level(first),
                   "runtime_s": {"search_and_session_admission": plan_finished - plan_started}})
    prefix_req = deepcopy(req)
    prefix_req["destinations"] = [{"node": req["position"]["node"], "dwell": 10,
                                   "open_intervals": [[h1["valid_from"], h1["valid_until"]]]}]
    prefix = check_route(graph, h1, prefix_req, [], req["position"]["node"])
    events.append({"kind": "modeled_stationary_prefix_10s", "checker": prefix,
                   "provenance": "synthetic replay execution under supplied construction; not observed movement"})
    if prefix["ok"]:
        incurred = {mid: checked_dose_upper(row) for mid, row in prefix["per_member"].items()}
        event = session.set_progress(req["position"], None, req["departure"] + 10, incurred, [])
        events.append({"kind": "progress", "event": event, "incurred": incurred})
    h2, c2, md2 = build_hazard(graph, arrays, metadata, mode="research", config=config,
                              origin=origin, version=2, parent_sha256=digest(snapshot_path))
    events.append({"kind": "new_future_ids", "native_metadata": md2,
                   "ids_disjoint": not (set(m["id"] for m in h1["members"]) & set(m["id"] for m in h2["members"])),
                   "event": accept_constructed_update(session, h2, h2["available_at"])})
    events.append({"kind": "stale_result", "committed": session.commit(first)})
    events.append({"kind": "stale_update", "event": accept_constructed_update(session, h1, h1["available_at"])})
    from hazard_constructor import ConstructionConfig
    alternative = replace(config or ConstructionConfig(), variant="timing_early", timing="early")
    h_alt, _, md_alt = build_hazard(graph, arrays, metadata, mode="research", config=alternative,
                                   origin=origin, version=3, parent_sha256=digest(snapshot_path))
    events.append({"kind": "changed_future_assumptions", "old_assumption_id": md2["assumption_id"],
                   "new_assumption_id": md_alt["assumption_id"],
                   "native_metadata": md_alt,
                   "event": accept_constructed_update(session, h_alt, h_alt["available_at"])})
    if next_snapshot and next_metadata:
        arrays3, metadata3 = load_snapshot(next_snapshot, next_metadata)
        h3, _, md3 = build_hazard(graph, arrays3, metadata3, mode="research", config=config,
                                  origin=origin, version=4, parent_sha256=digest(next_snapshot))
        events.append({"kind": "later_historical_cutoff", "native_metadata": md3,
                       "event": accept_constructed_update(session, h3, h3["available_at"])})
    replacement = deepcopy(graph)
    replacement["revision"] = graph["revision"] + ":replay-reset-control"
    events.append({"kind": "graph_replacement_without_reset", "event": session.replace_graph(replacement)})
    events.append({"kind": "graph_replacement_with_reset", "event": session.replace_graph(replacement, reset=True),
                   "progress_cleared": session.progress is None, "hazard_cleared": session.hazard is None})
    report = {"schema": "wfg.hourly.replay-report/1", "events": events,
              "initial_native_metadata": md1,
              "forecast": {"npz_sha256": digest(snapshot_path), "metadata_sha256": digest(metadata_path),
                           "checkpoint_sha256": metadata.get("checkpoint_sha256"),
                           "cutoff_utc": metadata["cutoff_utc"], "evidence": metadata.get("evidence")},
              "graph_revision": graph["revision"],
              "runtime_s": {"replay_pipeline_total": time.perf_counter() - replay_started},
              "memory": {"process_peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)},
              "history_claim": "conservative recombination within accepted supplied past histories, future assumptions prospective",
              "physical_history_validation": "UNAVAILABLE", "physical_safety_claim": False}
    if output_dir:
        save(Path(output_dir) / "REPLAY.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "native-run", "replay"):
        p = sub.add_parser(command)
        p.add_argument("--graph", default=str(DELIVERY / "sample/uljin_graph.json"))
        p.add_argument("--snapshot", default=str(DELIVERY / "sample/korean_native/20220304T030000Z.npz"))
        p.add_argument("--metadata", default=str(DELIVERY / "sample/korean_native/20220304T030000Z.json"))
        p.add_argument("--request", default=str(DELIVERY / "sample/uljin_GRID_CONTROL.json"))
        p.add_argument("--config", help="JSON object matching ConstructionConfig; explicit research assumptions")
        p.add_argument("--output-dir")
        if command in ("run", "native-run"):
            p.add_argument("--mode", choices=("strict", "research"), default="strict")
            p.add_argument("--repeats", type=int, default=1)
            p.add_argument("--origin")
            p.add_argument("--save-hazard", action="store_true")
            if command == "native-run":
                p.add_argument("--input", default=str(DELIVERY / "sample/input_snapshots/20220304T030000Z.npz"))
                p.add_argument("--checkpoint", default=str(DELIVERY / "sample/checkpoint.pt"))
        else:
            p.add_argument("--next-snapshot")
            p.add_argument("--next-metadata")
    sub.add_parser("tests")
    args = parser.parse_args()
    if args.command == "tests":
        # The inherited release seal is intentionally retained. New compatibility
        # inputs are verified by the new delivery manifest, not a forged old seal.
        commands = [[sys.executable, "-B", "-m", "unittest", "discover", "-s", str(ROOT / "routing-package/tests")],
                    [sys.executable, "-B", str(ROOT / "test_forecast_bridge.py")],
                    [sys.executable, "-B", str(ROOT / "test_hazard_constructor.py")],
                    [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(DELIVERY / "tests")],
                    [sys.executable, "-B", str(DELIVERY / "tests/independent_checks.py")]]
        for command in commands:
            subprocess.run(command, cwd=ROOT / "routing-package", check=True)
        return 0
    try:
        from hazard_constructor import ConstructionConfig
        cfg = ConstructionConfig(**read(args.config)) if args.config else None
        native_timing = None
        if args.command == "native-run":
            from native_forecast import predict_numeric_input
            output = Path(args.output_dir) if args.output_dir else DELIVERY / "results/end_to_end_native"
            target = output / "native_prediction.npz"
            before = time.perf_counter()
            native_row = predict_numeric_input(args.input, args.checkpoint, target)
            native_timing = {"status": "ORIGINAL_MODEL_RERUN", "original_model_total": time.perf_counter() - before,
                             "model_loading": native_row["model_loading_seconds"],
                             "input_loading": native_row["input_loading_seconds"],
                             "forecast_inference": native_row["inference_seconds"],
                             "original_expected_heat_export": native_row["expected_heat_seconds"]}
            args.snapshot = str(target); args.metadata = str(target.with_suffix(".json"))
            args.output_dir = str(output)
        if args.command in ("run", "native-run"):
            if args.repeats < 1:
                raise ValueError("repeats must be positive")
            report = run_pipeline(args.graph, args.snapshot, args.metadata, args.request,
                                  mode=args.mode, config=cfg, origin=args.origin,
                                  repeats=args.repeats, output_dir=args.output_dir,
                                  save_hazard=args.save_hazard)
            if native_timing:
                report["runtime_s"]["forecast_inference"] = native_timing
                report["runtime_s"]["native_forecast_then_routing_total"] = time.perf_counter() - STARTED
                save(Path(args.output_dir) / "REPORT.json", report)
        else:
            report = replay_pipeline(args.graph, args.snapshot, args.metadata, args.request,
                                     config=cfg, next_snapshot=args.next_snapshot,
                                     next_metadata=args.next_metadata, output_dir=args.output_dir)
        print(json.dumps(report, indent=2, allow_nan=False))
        # Unsupported/refused research cases are usable reports, never launch failures.
        return 0
    except (ValueError, TypeError, KeyError, OSError, IntegrationError) as exc:
        print(json.dumps({"status": "INTEGRATION_INPUT_REFUSED", "code": getattr(exc, "code", type(exc).__name__),
                          "reason": str(exc), "physical_safety_claim": False}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
