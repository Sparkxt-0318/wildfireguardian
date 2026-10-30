"""Fixed, pinned contact-only K panel. No source creation or full-policy scoring."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
from fractions import Fraction as F
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for name in ("sipp-routing", "scenario-members", "synthetic-truth"):
    sys.path.insert(0, str(ROOT / "experimental" / name / "src"))
from wfg_sipp.known_footprint import KnownFootprintSource, CHECKED, UNRESOLVED, _utc, check_contact_route, plan_contact_route

BASE = "700ce9a4afc01e9917d508d6f482d0646ac26a3d"
PROTOCOL = ROOT / "research/sipp-routing/KNOWN_FOOTPRINT_K_PROTOCOL.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def dump(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def pin(path, expected):
    if sha(path) != expected:
        raise ValueError("INPUT_OR_SOURCE_SHA256_CHANGED:" + str(path))


def phase_pins(protocol):
    if load(PROTOCOL) != protocol:
        raise ValueError("COMMITTED_PROTOCOL_CONTENT_CHANGED")
    if sys.version_info[:2] != (3, 12) or np.__version__ != "1.26.4":
        raise ValueError("PINNED_ROUTING_RUNTIME_REQUIRED")
    for path, expected in protocol["source_pins"].items():
        pin(ROOT / path, expected)
    for path, expected in protocol["evidence_pins"].items():
        pin(ROOT / path, expected)


def jobs(cases):
    out = []
    for index, case in enumerate(cases):
        for K in (4, 8, 16, 32):
            for repetition, methods in ((1, ("sweep", "sipp")), (2, ("sipp", "sweep"))):
                for method in methods:
                    out.append(dict(job_index=len(out), case_index=index, mission=case["mission"],
                                    region=case["region"], K=K, repetition=repetition, method=method))
    return out


def bindings(protocol):
    phase_pins(protocol)
    census = load(ROOT / protocol["full_N_census"])
    topology = load(ROOT / protocol["topology_census"])
    cases = [c for c in load(ROOT / protocol["original_cases"]) if c["panel"] == "Korean"]
    if len(cases) != 20 or len({c["mission"] for c in cases}) != 20:
        raise ValueError("EXACT_ORIGINAL_TWENTY_MISSION_PANEL_REQUIRED")
    out = []
    for case in cases:
        topo = next(r for r in topology["rows"] if r["mission"] == case["mission"])
        domain = next(d for d in census["domains"] if d["domain_id"] == topo["domain_id"])
        window = next(w for w in census["export_windows"] if (w["event"], w["cutoff"]) == (domain["event"], domain["cutoff"]))
        if not domain["all_saved_unknown_masks_byte_equal"] or domain["checked_members"] != 1024:
            raise ValueError("ORIGINAL_COMPLETE_SHARED_MASK_PROOF_REQUIRED")
        unsupported = not topo["topology"]["origin_known"] or not any(d["known_node"] for d in topo["topology"]["destinations"])
        out.append(dict(original_case=case, topology=topo, domain=domain, window=window, unsupported_endpoints=unsupported))
    if sum(b["unsupported_endpoints"] for b in out) != 14:
        raise ValueError("ORIGINAL_FOURTEEN_ENDPOINT_ADMISSIONS_CHANGED")
    return out


def original_source(binding, K):
    """Authenticate saved bytes, full-native first-K rows and original clocks."""
    case, domain, window, topo = (binding[k] for k in ("original_case", "domain", "window", "topology"))
    for key in ("graph", "request"):
        pin(case[key], case["input_sha256"][key])
    for name in ("NATIVE_METADATA.json", "REPORT.json", "HAZARD.json", "constructed_arrays.npz"):
        pin(Path(case["packet"]) / name, case["input_sha256"][name])
    if Path(case["graph"]).stat().st_size > 64 << 20:
        raise ValueError("ORIGINAL_GRAPH_INPUT_SIZE_GUARD")
    metadata = load(Path(case["packet"]) / "NATIVE_METADATA.json")
    request_bytes = Path(case["request"]).read_bytes()
    request = json.loads(request_bytes)
    path, record_path = Path(window["npz"]), Path(topo["source"]["record"])
    pin(path, window["npz_sha256"])
    pin(record_path, window["record_sha256"])
    record = load(record_path)
    if path.name != record["npz"] or record["npz_sha256"] != window["npz_sha256"]:
        raise ValueError("ORIGINAL_RECORD_NPZ_IDENTITY")
    with zipfile.ZipFile(path) as archive, archive.open("trajectory_first_burn_hour.npy") as stream:
        version = np.lib.format.read_magic(stream)
        reader = {(1, 0): np.lib.format.read_array_header_1_0, (2, 0): np.lib.format.read_array_header_2_0}.get(version)
        if reader is None:
            raise ValueError("SAVED_NPY_VERSION")
        shape, fortran, dtype = reader(stream)
        if fortran or tuple(shape) != tuple(window["shape"]) or dtype != np.dtype("int16") or shape[0] != 1024:
            raise ValueError("ORIGINAL_TRAJECTORY_HEADER")
        size = 32 * shape[1] * shape[2] * dtype.itemsize
        if size > 4 << 20:
            raise ValueError("FIRST32_SOURCE_BUFFER_GUARD")
        payload = stream.read(size)
        if len(payload) != size or hashlib.sha256(payload).hexdigest() != window["first32_prefix_sha256"]:
            raise ValueError("ORIGINAL_FIRST32_PREFIX_BYTES")
        first32 = np.frombuffer(payload, dtype=dtype).reshape(32, *shape[1:])
    spec = importlib.util.spec_from_file_location("_campaign_bridge", ROOT / "experimental/scenario-members/bridge_v2.py")
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    CT = bridge.v1.CT
    names = set(CT.MASKS + CT.FIELDS + CT.CLOCK_KEYS + ("affine_transform",))
    with np.load(path, allow_pickle=False) as arrays:
        raw = {name: arrays[name] for name in names}
    settings = metadata["settings"]
    if (settings["seed"] != 20261008 or settings["timing"] != "uniform" or settings["horizon_s"] != 3600
            or F(settings["burning_duration_s"]) != F(3970.4642815249267)
            or request["horizon"] != 3600 or _utc(metadata["time_origin"]) != _utc(domain["cutoff"])
            or record["trajectory_horizon_hours"] != 1 or record["trajectory_count"] != 1024):
        raise ValueError("ORIGINAL_FIXED_SOURCE_SETTINGS_OR_CLOCK")
    CT.verify_binding(raw, record, domain["cutoff"], domain["event"], topo["source"]["source_epsg"])
    CT.validate_raw(raw, settings["burning_duration_s"])
    if np.any((first32[:K] == 1) & raw["probability_valid"] & (raw["new_burn_probability"] == 0)):
        raise ValueError("FIRST_HOUR_BURN_CONTRADICTS_VALID_ZERO_PROBABILITY")
    raw["trajectory_first_burn_hour"] = first32[:K]
    source = KnownFootprintSource(raw, trajectory_indices=list(range(K)), cutoff_utc=domain["cutoff"],
        epsg=topo["source"]["source_epsg"], source_horizon_s=3600, burning_duration_s=settings["burning_duration_s"],
        seed=settings["seed"], timing=settings["timing"], window=domain["existing_integer_window"], terminal_inclusive=True,
        initial_remaining_s=metadata["construction"]["assumptions"]["initial_remaining_s"],
        source_identity=dict(npz=str(path), npz_sha256=window["npz_sha256"], record=str(record_path), record_sha256=window["record_sha256"],
                             graph_sha256=case["input_sha256"]["graph"], request_sha256=case["input_sha256"]["request"],
                             metadata_sha256=case["input_sha256"]["NATIVE_METADATA.json"],
                             first32_prefix_sha256=window["first32_prefix_sha256"], saved_original_indices=list(range(K))))
    if list(source.shape) != domain["grid_shape"] or list(map(float, source.affine)) != domain["affine"]:
        raise ValueError("EXACT_EXISTING_REGIONAL_GRID_BINDING")
    if _utc(request["as_of"]) != _utc(domain["cutoff"]) or _utc(metadata["construction"]["parent_forecast"]["cutoff_utc"]) != _utc(domain["cutoff"]):
        raise ValueError("EXACT_ORIGINAL_REQUEST_AND_FORECAST_CUTOFF")
    mask = source.unknown_native.any(axis=0)[::-1]
    if hashlib.sha256(mask.tobytes()).hexdigest() != topo["source"]["combined_south_up_mask_sha256"]:
        raise ValueError("ORIGINAL_EFFECTIVE_SOURCE_MASK")
    return source, request, request_bytes


def child(bundle_path, job, result_path):
    started = time.perf_counter()
    bundle = load(bundle_path)
    protocol, binding = bundle["protocol"], bundle["bindings"][job["case_index"]]
    phase_pins(protocol)
    source, request, original_bytes = original_source(binding, job["K"])
    common = dict(job, status=UNRESOLVED, arrival=None, destination=None, search_started=False,
                  solver_metrics=None, planner_wall_s=None, independent_recheck=None, planner_claim=None,
                  original_request=request, original_request_utf8=original_bytes.decode("utf-8"),
                  source=source.provenance(), physical_safety_claim=False, full_policy_status="UNKNOWN", peak=None, dose=None, risk=None,
                  source_phase_head=bundle["source_phase_head"], source_hashes=protocol["source_pins"])
    if binding["unsupported_endpoints"]:
        common.update(reason="ORIGINAL_UNKNOWN_ISSUE_OR_DESTINATION_FOOTPRINT", admission_wall_s=time.perf_counter() - started)
    else:
        graph = load(binding["original_case"]["graph"])
        admitted = time.perf_counter()
        result = plan_contact_route(graph, request, source, method=job["method"], wall_s=max(.001, 29 - (admitted - started)))
        common["planner_claim"] = result
        common.update(status=result["status"], arrival=result["arrival"], destination=result["destination"], reason=result["reason"],
                      admission_wall_s=admitted - started, search_started="search_status" in result)
        if common["search_started"]:
            common.update(solver_metrics=result["metrics"], planner_wall_s=result["wall_s"], search_status=result["search_status"])
        else:
            common["admission_wall_s"] = time.perf_counter() - started
        if result["original_request"] != request:
            raise ValueError("ORIGINAL_ISSUED_HISTORY_CHANGED")
        if result["status"] == CHECKED:
            checked_started = time.perf_counter()
            fresh_source, fresh_request, fresh_bytes = original_source(binding, job["K"])
            if fresh_bytes != original_bytes:
                raise ValueError("ORIGINAL_REQUEST_BYTES_CHANGED")
            checked = check_contact_route(graph, fresh_request, fresh_source, result["legs"], result["destination"])
            common.update(independent_recheck=checked, independent_recheck_wall_s=time.perf_counter() - checked_started)
            if not checked["ok"]:
                common.update(status=UNRESOLVED, reason="POSTHOC_ORIGINAL_SOURCE_RECHECK_REFUSED", arrival=None)
    phase_pins(protocol)
    common["reported_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 2 if sys.platform == "darwin" else 1024)
    common["child_internal_wall_s"] = time.perf_counter() - started
    dump(result_path, common)


def completion_stop(elapsed, sampled, reported, previous=None):
    if previous:
        return previous
    if elapsed >= 30:
        return "DEADLINE_AFTER_EXIT"
    if reported is None:
        return "MISSING_FINAL_PEAK_RSS"
    if not all(math.isfinite(v) and v >= 0 for v in (elapsed, sampled, reported)):
        return "INVALID_FINAL_RESOURCE_EVIDENCE"
    if max(sampled, reported) > 3072:
        return "RSS_LIMIT_AFTER_EXIT"
    return None


def controlled(command, result_path):
    started = time.monotonic()
    proc = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    maximum, stop = 0., None
    try:
        while proc.poll() is None:
            ps = subprocess.run(["ps", "-o", "rss=", "-p", str(proc.pid)], text=True, capture_output=True)
            if ps.stdout.strip():
                maximum = max(maximum, float(ps.stdout.strip()) / 1024)
            if time.monotonic() - started >= 30 or maximum > 3072:
                stop = "DEADLINE" if time.monotonic() - started >= 30 else "RSS_LIMIT"
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(.05)
        stdout, stderr = proc.communicate()
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
    elapsed = time.monotonic() - started
    result = load(result_path) if proc.returncode == 0 and Path(result_path).exists() else {}
    stop = completion_stop(elapsed, maximum, result.get("reported_peak_rss_mib"), stop)
    group = subprocess.run(["ps", "-o", "pid=", "-g", str(proc.pid)], text=True, capture_output=True).stdout.strip()
    if group:
        os.killpg(proc.pid, signal.SIGKILL)
        stop = stop or "OWNED_PROCESS_GROUP_REMAINED"
    control = dict(command=command, child_pid=proc.pid, exit_code=proc.returncode, stop=stop, elapsed_s=elapsed,
                   sampled_rss_mib=maximum, reported_peak_rss_mib=result.get("reported_peak_rss_mib"),
                   owned_group_absent=not group, stdout=stdout.decode(errors="replace"), stderr=stderr.decode(errors="replace"))
    return result, control


def preflight(out):
    protocol = load(PROTOCOL)
    cases = bindings(protocol)
    rows = []
    for binding in cases:
        try:
            source, request, _ = original_source(binding, 32)
            rows.append(dict(mission=binding["original_case"]["mission"], status="PASS_ORIGINAL_SOURCE_ADMISSION",
                             unsupported_endpoints=binding["unsupported_endpoints"], source=source.provenance(),
                             original_request_sha256=sha(binding["original_case"]["request"])))
        except Exception as exc:
            rows.append(dict(mission=binding["original_case"]["mission"], status="REFUSED_ORIGINAL_SOURCE", reason=type(exc).__name__ + ":" + str(exc)))
    result = dict(status="PASS_ORIGINAL_INPUT_PREFLIGHT" if all(r["status"] == "PASS_ORIGINAL_SOURCE_ADMISSION" for r in rows) else "REFUSED_ORIGINAL_INPUT_PREFLIGHT",
                  protocol_sha256=sha(PROTOCOL), rows=rows, no_graph_parse=True, no_planner=True, no_simulation=True)
    dump(out, result)
    print(json.dumps(dict(status=result["status"], missions=len(rows), refusals=[r for r in rows if r["status"].startswith("REFUSED")])) )


def run(out, preflight_path):
    protocol = load(PROTOCOL)
    phase_pins(protocol)
    prior = load(preflight_path)
    if prior["status"] != "PASS_ORIGINAL_INPUT_PREFLIGHT" or prior["protocol_sha256"] != sha(PROTOCOL):
        raise ValueError("PASSING_CURRENT_ORIGINAL_PREFLIGHT_REQUIRED")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise ValueError("COMMITTED_CLEAN_SOURCE_PHASE_REQUIRED")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    out.mkdir(parents=True, exist_ok=False)
    case_bindings = bindings(protocol)
    all_jobs = jobs([b["original_case"] for b in case_bindings])
    bundle = dict(protocol=protocol, protocol_sha256=sha(PROTOCOL), bindings=case_bindings, source_phase_head=head,
                  preflight_sha256=sha(preflight_path), host=platform.platform(), python=sys.version, numpy=np.__version__)
    dump(out / "BUNDLE.json", bundle)
    dump(out / "JOBS.json", all_jobs)
    rows = []
    for job in all_jobs:
        pin(PROTOCOL, bundle["protocol_sha256"])
        phase_pins(protocol)
        dest = out / ("job-%03d.json" % job["job_index"])
        command = [sys.executable, "-I", str(Path(__file__).resolve()), "--child", str((out / "BUNDLE.json").resolve()),
                   "--job", str(job["job_index"]), "--result", str(dest.resolve())]
        print(json.dumps(dict(status="WAITING_HEAVY", job=job["job_index"], mission=job["mission"], K=job["K"], method=job["method"])), flush=True)
        lease_path = Path("/tmp/wfg/HEAVY.lock")
        lease_path.parent.mkdir(parents=True, exist_ok=True)
        with lease_path.open("a") as lease:
            fcntl.flock(lease, fcntl.LOCK_EX)
            acquired = datetime.now(timezone.utc).isoformat()
            result, control = controlled(command, dest)
            released = datetime.now(timezone.utc).isoformat()
        row = dict(job, control=control, lease_acquired_utc=acquired, lease_released_utc=released,
                   complete_child_wall_s=control["elapsed_s"], source_phase_head=head)
        if control["stop"] is None and control["exit_code"] == 0:
            row.update(result)
        else:
            row.update(status=UNRESOLVED, reason="CONTROL_REFUSAL", arrival=None, search_started=False,
                       solver_metrics=None, planner_wall_s=None, independent_recheck=None)
        rows.append(row)
        with (out / "EXECUTIONS.jsonl").open("a") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        phase_pins(protocol)
        print(json.dumps({k:row.get(k) for k in ("job_index", "mission", "K", "method", "repetition", "status", "arrival", "search_started")}), flush=True)
        time.sleep(.05)
    dump(out / "RESULTS.json", dict(status="COMPLETE_FIXED_CONTACT_K_CAMPAIGN", jobs=len(rows), source_phase_head=head,
          protocol_sha256=sha(PROTOCOL), checked_routes=sum(r["status"] == CHECKED for r in rows),
          unresolved=sum(r["status"] != CHECKED for r in rows), search_started=sum(r["search_started"] for r in rows),
          independent_rechecks=sum(r.get("independent_recheck") is not None for r in rows),
          inputs_and_source_still_pinned=True, host=platform.platform(), python=sys.version, numpy=np.__version__,
          control_scope="30s complete child with sampled RSS and final peak/elapsed checks, per-job exclusive HEAVY, owned process-group cleanup. Polling is not an instantaneous OS memory cap.",
          scope="Cell-local represented contact only; unknown thermal policy, peak, dose and risk; no physical/global original-domain claim."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--preflight-receipt", type=Path)
    parser.add_argument("--child", type=Path)
    parser.add_argument("--job", type=int)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    if args.child:
        bundle = load(args.child)
        child(args.child, jobs([b["original_case"] for b in bundle["bindings"]])[args.job], args.result)
    elif args.preflight:
        preflight(args.preflight)
    elif args.run:
        run(args.run, args.preflight_receipt)
    else:
        parser.error("Choose --preflight, --run with --preflight-receipt, or controller child")
