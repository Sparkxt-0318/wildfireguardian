"""Importable API: latest forecast -> hazard packet -> routing -> whole-road check -> returned result.

Every heavy step runs in a fresh child interpreter (python -I -B) so the latest forecast package, the inherited radiation
operator and the routing engine never share one process. Paths may be str or pathlib.Path. Example (see example.py):

    from wfg_latest import api
    rec = api.export_forecast(source_root=SRC, data_root=DATA, checkpoint=CK, event="KFS_05",
                              cutoff="2023-04-02T07:00:00Z", out_dir=OUT / "export", python=FORECAST_PY)
    pkt = api.build_packet(graph=GRAPH, export_dir=OUT / "export", event="KFS_05", cutoff="2023-04-02T07:00:00Z",
                           region="hongseong_2023", out_dir=OUT / "packet", python=FORECAST_PY)
    req = api.rekey_request(REQUEST, OUT / "packet", "2023-04-02T07:00:00Z", out_path=OUT / "request.json")
    res = api.route_and_check(kit_root=KIT, packet_dir=OUT / "packet", graph=GRAPH, request=OUT / "request.json",
                              out_dir=OUT / "route_RDA_CAND", arm="RDA_CAND", python=FORECAST_PY)
"""
from __future__ import annotations

import hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM_WORKER = {"RDA_CAND": "phaseB/rda_worker_v1_1.py", "RDA_BASE": "phaseB/baseline_worker.py"}


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _run(cmd, log):
    with open(log, "w") as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError("%s failed (exit %s); see %s" % (Path(cmd[3]).name, p.returncode, log))


def _tag(cutoff):
    sys.path.insert(0, str(HERE))
    import contract as CT
    return CT.normalize_cutoff(str(cutoff))[0], CT.tag(str(cutoff))


def export_forecast(*, source_root, data_root, checkpoint, event, cutoff, out_dir, python=None):
    """Run the latest forecast for one event and one whole-hour UTC cutoff; returns the export record (dict)."""
    iso, tag = _tag(cutoff); out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    _run([python or sys.executable, "-I", "-B", str(HERE / "export.py"), "--source-root", str(source_root), "--data-root", str(data_root),
          "--checkpoint", str(checkpoint), "--event", event, "--cutoff", iso, "--out", str(out)], out / ("export_%s.log" % tag))
    return json.loads((out / ("FORECAST_RECORD_%s.json" % tag)).read_text())


def build_packet(*, graph, export_dir, event, cutoff, region, out_dir, window=None, python=None):
    """Construct one regional hazard packet from a clock-bound export; returns BUILD_SUMMARY (dict)."""
    iso, tag = _tag(cutoff); out = Path(out_dir)
    cmd = [python or sys.executable, "-I", "-B", str(HERE / "build_packet.py"), "--graph", str(graph), "--export-dir", str(export_dir),
           "--event", event, "--cutoff", iso, "--region", region, "--out", str(out)]
    if window is not None:
        cmd += ["--window-json", json.dumps(window)]
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(cmd, out.parent / ("build_packet_%s_%s.log" % (region, tag)))
    return json.loads((out / "BUILD_SUMMARY.json").read_text())


def rekey_request(request, packet_dir, cutoff, *, out_path=None):
    """Re-key a frozen request (path or dict) onto the packet's member identifiers; returns the new request dict."""
    spec = importlib.util.spec_from_file_location("wfg_latest_rekey", HERE / "requests.py")
    RQ = importlib.util.module_from_spec(spec); spec.loader.exec_module(RQ)
    iso, _ = _tag(cutoff)
    req = request if isinstance(request, dict) else json.loads(Path(request).read_text())
    hz = json.loads((Path(packet_dir) / "HAZARD.json").read_text())
    new, mapping = RQ.rekey(req, hz, iso)
    if out_path is not None:
        Path(out_path).write_text(json.dumps(new, indent=1) + "\n")
    return new


def route_and_check(*, kit_root, packet_dir, graph, request, out_dir, arm="RDA_CAND", python=None, budget_s=30.0,
                    memory_guard_mib=3072, check=True, label=None):
    """One controlled routing attempt with the kit's lifecycle controller, then the authoritative decision and (optionally)
    the offline independent checker (120 s cap). Returns a dict with the receipt summary, decision and independent verdict."""
    kit = Path(kit_root).resolve(); out = Path(out_dir).resolve(); packet = Path(packet_dir).resolve()
    graph = Path(graph).resolve(); request = Path(request).resolve(); py = python or sys.executable
    sys.path.insert(0, str(kit / "runner")); sys.path.insert(0, str(kit / "decision"))
    import wfg_controller as CTL
    import journey_decision_v2_1 as JD
    q = json.loads((kit / "queues/LATEST_PREFLIGHT_REAL.json").read_text())["jobs"][0]   # reviewed identity constants
    req = json.loads(request.read_text())
    label = label or "API__%s__%s" % (packet.name, arm)
    job = {"label": label, "case_id": label, "cohort": "api", "arm": arm, "arm_key": arm, "rep": 1, "source_root": q["source_root"],
           "source_directory": str(packet), "graph_path": str(graph), "hazard_path": str(packet / "HAZARD.json"), "request_path": str(request),
           "complete_budget_s": float(budget_s), "original_limits": req["limits"], "worker": ARM_WORKER[arm], "env": {},
           "input_sha256": {"graph_path": _sha(graph), "hazard_path": _sha(packet / "HAZARD.json"), "request_path": _sha(request)},
           "source_sha256": {n: _sha(packet / n) for n in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz")},
           "core_sha256": q["core_sha256"], "checker_module": q["checker_module"], "checker_sha256": q["checker_sha256"],
           "root": None, "decision_dir": None, "output_path": str(out), "campaign": "API", "queue": "API",
           "preparation_mode": q["preparation_mode"], "preparation_mode_sha256": q["preparation_mode_sha256"],
           "preparation_source_sha256": q["preparation_source_sha256"], "memory_guard_mib": memory_guard_mib}
    if arm == "RDA_CAND":
        job["phaseB_sha256"] = q["phaseB_sha256"]
    else:
        job["baseline_sha256"] = {"baseline_worker.py": _sha(kit / "phaseB/baseline_worker.py")}
    rc = CTL.run_attempt(kit, job, py, {"api": True})
    res = json.loads((out / "RESULT.json").read_text()) if (out / "RESULT.json").exists() else {}
    jobj = json.loads((out / "JOB.json").read_text())
    dec = JD.decision_from_worker_record(res, rc, jobj, graph=json.loads(graph.read_text()), request=req,
                                         hazard=json.loads((packet / "HAZARD.json").read_text()),
                                         optimality_certificate=res.get("optimality_certificate"), refusal_certificate=res.get("refusal_certificate"))
    ind = None
    if check and res:
        ip = out.parent / (out.name + "_INDEPENDENT.json")
        p = subprocess.run([py, "-I", "-B", str(kit / "runner/ffi_independent_checker.py"), "--graph", str(graph), "--packet-dir", str(packet),
                            "--request", str(request), "--result", str(out / "RESULT.json"), "--out", str(ip)], capture_output=True, text=True, timeout=120)
        ind = json.loads(ip.read_text()) if p.returncode == 0 and ip.exists() else {"status": "FAILED", "tail": (p.stdout + p.stderr)[-400:]}
    j = dec.get("journey") or {}
    return {"label": label, "arm": arm, "on_time": rc.get("on_time_complete_publication"), "wall_s": rc.get("external_launch_to_completion_wall_s"),
            "cleanup_state": rc.get("cleanup_state"), "primary_status": res.get("primary_status"),
            "runtime_whole_road": (res.get("whole_road_check") or {}).get("status"), "authoritative_status": dec.get("authoritative_status"),
            "successful_journey": dec.get("is_successful_journey"), "unresolved_reason": dec.get("unresolved_reason"), "arrival_s": j.get("arrival"),
            "independent": None if ind is None else {"classification": ind.get("classification"),
                                                     "verdict": (ind.get("optimality_or_refusal") or {}).get("verdict"),
                                                     "contradictions": ind.get("contradictions"), "status": ind.get("status")},
            "out_dir": str(out)}
