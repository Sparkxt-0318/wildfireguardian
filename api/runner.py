"""One route check, executed inside a process-pool worker (never in a server thread: the kit controller uses
preexec_fn and process groups).

policy ``full``  -> ``wfg_latest.api.route_and_check`` (arm RDA_CAND, kit v3), exactly the evaluated path.
other policies   -> the frozen final-input ablation worker (A0-A3) launched by the same kit controller from an
                    identity-checked copy of the ablation study kit (FREEZE.json hashes), with planning inputs from the
                    study's own ``arm_transform.arm_inputs``.
In both cases the authoritative status is ``journey_decision_v2_1.decision_from_worker_record`` and the request time is
the controller receipt's ``external_launch_to_completion_wall_s``.
"""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

from . import config as C
from . import verdict as V
from .requests_build import build_request

_MODS: dict = {}


def _sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _load(name: str, path: Path):
    key = (name, str(path))
    if key not in _MODS:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODS[key] = mod
    return _MODS[key]


def _kit_modules():
    for d in (C.KIT_ROOT / "runner", C.KIT_ROOT / "decision"):
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))
    import journey_decision_v2_1 as JD   # noqa: E402  (same module object route_and_check imports)
    import wfg_controller as CTL         # noqa: E402
    pub = _load("wfg_api_publication_v1_1", C.KIT_ROOT / "phaseB" / "publication_v1_1.py")
    return JD, CTL, pub


def _write_json(path: Path, obj, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        if compact:
            json.dump(obj, f, allow_nan=False, separators=(",", ":"))
        else:
            json.dump(obj, f, allow_nan=False, indent=1)
        f.write("\n")


def _read(path: Path):
    return json.loads(Path(path).read_text()) if Path(path).exists() else {}


# --------------------------------------------------------------------------------------------- ablation study kit
def ablation_kit(runtime_dir: Path) -> Path:
    """Identity-checked copy of the frozen ablation study kit: integration/kit plus the study's phaseB worker files.
    Every file listed in the study FREEZE.json (sources only, not inputs/queues/records) must match its pinned hash."""
    dest = Path(runtime_dir) / "ablation_kit"
    marker = dest / ".FREEZE_VERIFIED.json"
    lock_path = Path(runtime_dir) / ".ablation_kit.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        freeze = json.loads((C.ABLATION_ROOT / "FREEZE.json").read_text())["files"]
        code = {p[len("study/"):]: h for p, h in freeze.items()
                if p.startswith("study/") and not p.startswith(("study/inputs/", "study/queues/", "study/raw/"))}
        if marker.exists():
            bad = [r for r, h in code.items() if not (dest / r).is_file() or _sha(dest / r) != h]
            if not bad:
                return dest
            shutil.rmtree(dest)
        tmp = Path(runtime_dir) / (".ablation_kit.tmp.%d" % os.getpid())
        if tmp.exists():
            shutil.rmtree(tmp)
        for rel in code:
            src = C.KIT_ROOT / rel
            if not src.is_file():
                src = C.ABLATION_ROOT / "experiment_source" / rel
            if not src.is_file():
                raise RuntimeError("ABLATION_SOURCE_MISSING:" + rel)
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, tmp / rel)
        bad = [r for r, h in code.items() if _sha(tmp / r) != h]
        if bad:
            shutil.rmtree(tmp)
            raise RuntimeError("ABLATION_SOURCE_IDENTITY_MISMATCH:" + ",".join(sorted(bad)))
        (tmp / "queues").mkdir(exist_ok=True)
        shutil.copy2(C.KIT_ROOT / "queues" / "LATEST_PREFLIGHT_REAL.json", tmp / "queues" / "LATEST_PREFLIGHT_REAL.json")
        _write_json(tmp / ".FREEZE_VERIFIED.json", {"freeze_sha256": _sha(C.ABLATION_ROOT / "FREEZE.json"), "files": len(code)})
        os.replace(tmp, dest)
        return dest


def run_ablation_attempt(*, policy: str, packet: Path, graph: Path, request_path: Path, out_dir: Path, inputs_dir: Path,
                         python: str, label: str, runtime_dir: Path):
    JD, CTL, _ = _kit_modules()
    kit = ablation_kit(runtime_dir)
    arm = C.POLICY_ARMS[policy]
    AT = _load("wfg_api_arm_transform", kit / "phaseB" / "arm_transform.py")
    hazard = json.loads((packet / "HAZARD.json").read_text())
    full_request = json.loads(request_path.read_text())
    ph, pr, receipt = AT.arm_inputs(arm, hazard, full_request)
    bad = AT.verify_transform(arm, hazard, full_request, ph, pr)
    if bad:
        raise RuntimeError("ARM_TRANSFORM_VERIFY:" + ";".join(bad))
    suff = AT.sentinel_sufficiency(hazard, full_request)
    if not suff["ok"]:
        raise RuntimeError("ARM_SENTINEL_NOT_SUFFICIENT")
    hz_path, rq_path = inputs_dir / "policy" / "HAZARD.json", inputs_dir / "policy" / "REQUEST.json"
    _write_json(hz_path, ph, compact=True)
    _write_json(rq_path, pr)
    q = json.loads((kit / "queues" / "LATEST_PREFLIGHT_REAL.json").read_text())["jobs"][0]
    phaseb = dict(q["phaseB_sha256"])
    phaseb["rda_worker_v1_1.py"] = _sha(kit / "phaseB" / "ablation_worker.py")   # the study pins its worker under this key
    job = {"label": label, "case_id": label, "cohort": "api", "arm": "RDA_CAND", "arm_key": arm, "rep": 1,
           "source_root": "routing_candidate", "source_directory": str(packet), "graph_path": str(graph),
           "hazard_path": str(hz_path), "request_path": str(rq_path), "complete_budget_s": C.BUDGET_S,
           "original_limits": full_request["limits"], "worker": "phaseB/ablation_worker.py", "env": {},
           "input_sha256": {"graph_path": _sha(graph), "hazard_path": _sha(hz_path), "request_path": _sha(rq_path)},
           "source_sha256": {n: _sha(packet / n) for n in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz")},
           "core_sha256": q["core_sha256"], "checker_module": q["checker_module"], "checker_sha256": q["checker_sha256"],
           "root": None, "decision_dir": None, "output_path": str(out_dir), "campaign": "API", "queue": "API",
           "preparation_mode": q["preparation_mode"], "preparation_mode_sha256": q["preparation_mode_sha256"],
           "preparation_source_sha256": q["preparation_source_sha256"], "memory_guard_mib": C.MEMORY_GUARD_MIB,
           "phaseB_sha256": phaseb, "policy": arm, "full_request_path": str(request_path),
           "full_request_sha256": _sha(request_path), "policy_transform": receipt}
    rc = CTL.run_attempt(kit, job, python, {"api": True})
    return rc, kit, hz_path, rq_path, {"arm": arm, "transform": receipt, "sentinel_sufficiency": suff}


# ------------------------------------------------------------------------------------------------- independent
def run_independent(kit: Path, graph: Path, packet: Path, request: Path, out_dir: Path, python: str) -> dict:
    ip = out_dir.parent / (out_dir.name + "_INDEPENDENT.json")
    cmd = [python, "-I", "-B", str(kit / "runner/ffi_independent_checker.py"), "--graph", str(graph), "--packet-dir", str(packet),
           "--request", str(request), "--result", str(out_dir / "RESULT.json"), "--out", str(ip)]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "cap_s": 120, "elapsed_s": time.perf_counter() - t0}
    if p.returncode != 0 or not ip.exists():
        return {"status": "FAILED", "tail": (p.stdout + p.stderr)[-400:], "elapsed_s": time.perf_counter() - t0}
    out = json.loads(ip.read_text())
    out["status"] = "OK"
    out["elapsed_s"] = time.perf_counter() - t0
    return out


# ------------------------------------------------------------------------------------------------ route output
def route_feature(journey: dict, request: dict, graph_edges: dict, node_lonlat) -> dict:
    """GeoJSON LineString through the visited road nodes with one time per vertex (a wait adds a second vertex at the
    same node with its end time). Edges carry no intermediate geometry in the study graphs."""
    node = request["position"]["node"]
    t = int(request["departure"])
    coords, times, nodes, edge_ids, waits = [], [], [], [], []

    def emit(n, tt):
        lon, lat = node_lonlat(n)
        coords.append([lon, lat]); times.append(tt); nodes.append(n)

    emit(node, t)
    wait = None
    for leg in journey.get("legs") or []:
        if leg["kind"] == "WAIT":
            if leg["node"] != node:
                raise ValueError("WAIT leg at %s while at %s" % (leg["node"], node))
            if wait is None:
                wait = {"node_id": node, "from_s": int(leg["start"]), "to_s": int(leg["end"])}
            else:
                wait["to_s"] = int(leg["end"])
            continue
        if wait is not None:
            waits.append(wait); emit(node, wait["to_s"]); wait = None
        u, v, _ = graph_edges[leg["edge"]]
        if u != node or leg.get("from_fraction", 0) != 0 or leg.get("to_fraction", 1) != 1:
            raise ValueError("non-contiguous or partial leg %s" % leg)
        edge_ids.append(leg["edge"])
        node = v
        emit(node, int(leg["end"]))
    if wait is not None:
        waits.append(wait); emit(node, wait["to_s"])
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {"times_s": times, "node_ids": nodes, "segment_count": len(edge_ids), "edge_ids": edge_ids,
                           "waits": waits, "legs_total": len(journey.get("legs") or [])}}


def _lower_bound_L(result: dict):
    """L = arrival of the completed contact-only lattice relaxation (the earliest flame-avoiding candidate), exactly as
    the worker kept it in RESULT.lower_bounds; a bound the worker dropped (EA cross-check disagreement) is never used."""
    for lb in result.get("lower_bounds") or []:
        if isinstance(lb, dict) and lb.get("kind") == "contact_only_lattice_relaxation" and lb.get("arrival") is not None:
            return lb["arrival"]
    return None


def _lower_bounds(result: dict) -> list:
    return [{"kind": lb.get("kind"), "arrival_s": lb.get("arrival")} for lb in result.get("lower_bounds") or [] if isinstance(lb, dict)]


def full_policy_assessment(kit: Path, graph: dict, packet: Path, full_request: dict, legs: list, destination: str) -> dict:
    """Assess a route found under a reduced policy against the UNCHANGED full hazard model with the kit's independent
    checker functions (grammar, centre model, exact whole-road contact), as the ablation grader (grade_route.py) did.
    Offline: not charged to compute_s. The project whole-road radiation check is not repeated here."""
    I = _load("wfg_api_ffi_independent_checker", kit / "runner" / "ffi_independent_checker.py")
    G = I.Graph(graph)
    pk = I.Packet(packet, G)
    gram = I.grammar(G, full_request, legs, destination, pk.horizon)
    cm = I.centre_model(pk, full_request, gram)
    contact = I.whole_road_contact(pk, gram)
    viol = []
    for mid, v in cm["per_member"].items():
        for flag, name in (("flame_contact", "FLAME"), ("peak_violation", "PEAK"), ("dose_violation", "DOSE")):
            if v.get(flag):
                viol.append({"scenario_id": mid, "constraint": name})
    if contact.get("status") != "CLEAR":
        viol.append({"scenario_id": None, "constraint": "WHOLE_ROAD_CONTACT"})
    per = {mid: {"peak_kw_m2": float(v["peak_kw_m2"]), "dose_kj_m2": float(v["dose_total_kj_m2"]),
                 "contact": bool(v.get("flame_contact")) or mid in (contact.get("witnesses") or {})}
           for mid, v in cm["per_member"].items()}
    return {"passes_full_centre_and_contact": bool(gram.get("ok") and cm.get("feasible") and contact.get("status") == "CLEAR"),
            "whole_road_contact": contact.get("status"), "violations": viol, "per_scenario": per,
            "scope": "independent grammar, centre-model exposure and exact whole-road contact against the unchanged full hazard; "
                     "the project whole-road radiation check was not repeated"}


def _graph_lookup(graph_path: Path):
    g = json.loads(Path(graph_path).read_text())
    edges = {e["id"]: (e["u"], e["v"], e["travel_ticks"]) for e in g["edges"]}
    xy = {n["id"]: (n["x"], n["y"]) for n in g["nodes"]}
    from pyproj import Transformer
    tf = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

    def node_lonlat(n):
        lon, lat = tf.transform(*xy[n])
        return float(lon), float(lat)
    return g, edges, node_lonlat


# ------------------------------------------------------------------------------------------------------- main
def build_zone_packet(spec: dict) -> dict:
    """Pool task for dispatch plans: build one spread_zones packet shared by every attempt of the plan."""
    from .adapters import spread_zones as SZ
    t0 = time.perf_counter()
    try:
        packet, meta = SZ.build_packet(spec["zone_plan"], graph_path=Path(spec["graph_path"]), out_dir=Path(spec["out_dir"]),
                                       python=spec["python"])
        return {"status": "done", "packet_dir": str(packet), "adapter_meta": meta, "adapter_s": time.perf_counter() - t0}
    except Exception as exc:
        return {"status": "failed", "error": {"code": "ZONE_PACKET_BUILD_FAILED", "message": "%s: %s" % (type(exc).__name__, exc)}}


def execute(spec: dict) -> dict:
    """Run one route check described by ``spec`` (built by the server). Never raises: internal errors come back as
    {"status": "failed", "result": {verdict: unresolved, reason_code: INTERNAL_ERROR}, ...}."""
    t_start = time.perf_counter()
    job_dir = Path(spec["job_dir"])
    notes, timings = [], {}
    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        inputs = job_dir / "inputs"
        graph_path = Path(spec["graph_path"])
        assumptions, adapter_meta = None, None
        if spec["fire_input"]["type"] == "spread_zones" and spec.get("prebuilt_packet"):
            packet, adapter_meta = Path(spec["prebuilt_packet"]), spec["adapter_meta"]
            assumptions = adapter_meta["assumptions"]
        elif spec["fire_input"]["type"] == "spread_zones":
            from .adapters import spread_zones as SZ
            t0 = time.perf_counter()
            packet, adapter_meta = SZ.build_packet(spec["zone_plan"], graph_path=graph_path, out_dir=inputs / "packet",
                                                   python=spec["python"])
            timings["adapter_s"] = time.perf_counter() - t0
            assumptions = adapter_meta["assumptions"]
        else:
            packet = Path(spec["packet_dir"])
        hazard = json.loads((packet / "HAZARD.json").read_text())
        sids = [m["id"] for m in hazard["members"]]
        rp = spec["request_params"]
        request = build_request(start_node=rp["start_node"], dest_node=rp["dest_node"], depart_offset_s=rp["depart_offset_s"],
                                dwell_s=rp["dwell_s"], window=rp["window"], limits=rp["limits"], scenario_ids=sids,
                                horizon_s=hazard["valid_until"], valid_from=hazard["valid_from"],
                                hazard_version=hazard["version"], as_of_iso=hazard["time_origin"], dt=int(hazard["dt"]))
        request_path = inputs / "REQUEST.json"
        _write_json(request_path, request)
        out_dir = job_dir / "attempt"
        python = spec["python"]
        policy = spec["policy"]
        label = "API__" + spec["job_id"]
        JD, CTL, PUB = _kit_modules()
        policy_meta = None
        if policy == "full":
            from wfg_latest import api as WA
            summary = WA.route_and_check(kit_root=C.KIT_ROOT, packet_dir=packet, graph=graph_path, request=request_path,
                                         out_dir=out_dir, arm="RDA_CAND", python=python, budget_s=C.BUDGET_S,
                                         memory_guard_mib=C.MEMORY_GUARD_MIB, check=False, label=label)
            kit_used, hz_used, rq_used = C.KIT_ROOT, packet / "HAZARD.json", request_path
        else:
            rc_, kit_used, hz_used, rq_used, policy_meta = run_ablation_attempt(
                policy=policy, packet=packet, graph=graph_path, request_path=request_path, out_dir=out_dir, inputs_dir=inputs,
                python=python, label=label, runtime_dir=Path(spec["runtime_dir"]))
            summary = None
        receipt = _read(out_dir / "COMPLETE_PROCESS_RECEIPT.json")
        result = _read(out_dir / "RESULT.json")
        job = _read(out_dir / "JOB.json")
        graph, edges, node_lonlat = _graph_lookup(graph_path)
        decision = JD.decision_from_worker_record(result, receipt, job, graph=graph, request=json.loads(Path(rq_used).read_text()),
                                                  hazard=json.loads(Path(hz_used).read_text()),
                                                  optimality_certificate=result.get("optimality_certificate"),
                                                  refusal_certificate=result.get("refusal_certificate"))
        if summary is not None and summary.get("authoritative_status") != decision.get("authoritative_status"):
            raise RuntimeError("DECISION_RECOMPUTATION_DIFFERS %s vs %s" % (summary.get("authoritative_status"), decision.get("authoritative_status")))
        independent = None
        if spec.get("run_independent_check") and result and policy != "full":
            notes.append("The offline independent checker is defined for the full policy only; it was not run for %s." % policy)
        elif spec.get("run_independent_check") and result:
            t0 = time.perf_counter()
            independent = run_independent(kit_used, graph_path, packet, rq_used, out_dir, python)
            timings["independent_s"] = time.perf_counter() - t0
        verdict, reason, raw_reason = V.classify(decision, receipt, result, independent, C.MEMORY_GUARD_MIB)
        journey = decision.get("journey") or {}
        out = {"verdict": verdict, "reason_code": reason, "raw_status": decision.get("authoritative_status"),
               "raw_reason": raw_reason, "departure_s": request["departure"], "arrival_s": None,
               "lower_bound_L_s": _lower_bound_L(result), "lower_bounds": _lower_bounds(result),
               "dwell_end_s": None, "route": None, "exposure": [],
               "compute_s": receipt.get("external_launch_to_completion_wall_s"), "within_budget": False,
               "policy": policy, "limits": dict(rp["limits"]), "independent_check": None, "assumptions": assumptions,
               "notes": notes}
        cs = out["compute_s"]
        out["within_budget"] = bool(cs is not None and cs <= C.BUDGET_S and receipt.get("on_time_complete_publication"))
        flame_enforced = policy != "travel_only"
        if verdict == V.CHECKED and flame_enforced:
            wr = result.get("whole_road_check") or {}
            contact = (wr.get("contact") or {}).get("status")
            if contact != "CLEAR":
                verdict, reason, raw_reason = V.UNRESOLVED, "CHECK_FAILED", "CONTACT_NOT_CLEAR"
                out.update(verdict=verdict, reason_code=reason, raw_reason=raw_reason)
        if verdict == V.CHECKED:
            dwell = request["destinations"][0]["dwell"]
            out["arrival_s"] = journey["arrival"]
            out["dwell_end_s"] = journey["arrival"] + dwell
            out["route"] = route_feature(journey, request, edges, node_lonlat)
            if len(out["route"]["geometry"]["coordinates"]) < 2:
                raise RuntimeError("DEGENERATE_ROUTE")
            if policy == "full":
                published, _role = PUB.route_of(result.get("result") or {})
                bounds = (((published or {}).get("whole_road_bounds") or {}).get("per_member")) or {}
                for sid in sids:
                    pm = (journey.get("per_member") or {}).get(sid) or {}
                    b = bounds.get(sid) or {}
                    out["exposure"].append({"scenario_id": sid, "peak_kw_m2": pm.get("peak"), "dose_kj_m2": pm.get("dose"),
                                            "contact": False, "basis": "centre_model",
                                            "peak_upper_kw_m2": b.get("peak_upper_kw_m2"), "dose_upper_kj_m2": b.get("dose_upper_kj_m2")})
            else:
                t0 = time.perf_counter()
                fpa = full_policy_assessment(kit_used, graph, packet, request, journey["legs"], journey["destination"])
                timings["full_policy_assessment_s"] = time.perf_counter() - t0
                out["full_policy_assessment"] = fpa
                for sid in sids:
                    e = fpa["per_scenario"][sid]
                    out["exposure"].append({"scenario_id": sid, "peak_kw_m2": e["peak_kw_m2"], "dose_kj_m2": e["dose_kj_m2"],
                                            "contact": e["contact"], "basis": "full_model_centre_check"})
                notes.append("Route checked under policy %s only (%s); exposure is reported against the unchanged full hazard. "
                             "It is not a full-policy checked route." % (policy, "flame contact not enforced" if not flame_enforced else
                                                                         "thermal limits partly disabled"))
                if not fpa["passes_full_centre_and_contact"]:
                    notes.append("This route FAILS the full policy: %s." % ", ".join(sorted({v["constraint"] for v in fpa["violations"]})))
        if verdict == V.NO_ROUTE:
            notes.append("Scoped refusal: no route exists within this model, lattice, scenarios and policy; "
                         "it is not proof that every real-world escape is impossible.")
        if verdict == V.UNRESOLVED:
            notes.append("Unresolved is never safe: no checked route and no scoped refusal were established.")
        if independent is not None:
            out["independent_check"] = {"status": independent.get("status"),
                                        "classification": (independent.get("classification") or {}).get("overall"),
                                        "verdict": (independent.get("optimality_or_refusal") or {}).get("verdict"),
                                        "contradictions": independent.get("contradictions"),
                                        "elapsed_s": independent.get("elapsed_s")}
            if independent.get("status") != "OK" and verdict != V.UNRESOLVED:
                notes.append("Offline independent corroboration did not complete (%s); the runtime authoritative decision stands."
                             % independent.get("status"))
        hashes = {"graph": _sha(graph_path), "hazard": _sha(packet / "HAZARD.json"), "request": _sha(request_path)}
        for n in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz"):
            hashes["packet/" + n] = _sha(packet / n)
        if policy != "full":
            hashes["policy_hazard"] = _sha(hz_used)
            hashes["policy_request"] = _sha(rq_used)
        if adapter_meta:
            hashes.update({"zones/" + k: v for k, v in adapter_meta.get("input_hashes", {}).items()})
        timings["worker_total_s"] = time.perf_counter() - t_start
        return {"status": "done", "result": out, "error": None, "timings": timings, "request_object": request,
                "decision_status": decision.get("authoritative_status"), "scenario_ids": sids, "input_hashes": hashes,
                "graph_id": graph.get("revision"), "policy_meta": policy_meta, "adapter_meta": adapter_meta,
                "receipt": {k: receipt.get(k) for k in ("on_time_complete_publication", "exit_code", "cleanup_state",
                                                         "deadline_termination_requested", "memory_guard_triggered",
                                                         "external_launch_to_completion_wall_s", "raw_primary_status")}}
    except Exception as exc:
        err = {"code": getattr(exc, "code", None) or "INTERNAL_ERROR", "message": "%s: %s" % (type(exc).__name__, exc)}
        try:
            (job_dir / "WORKER_ERROR.txt").write_text(traceback.format_exc())
        except Exception:
            pass
        status_code = 422 if getattr(exc, "status", None) == 422 else None
        return {"status": "failed", "error": err, "http_status": status_code, "details": getattr(exc, "details", None),
                "result": {"verdict": V.UNRESOLVED, "reason_code": "INTERNAL_ERROR", "raw_status": None, "raw_reason": err["message"],
                           "departure_s": None, "arrival_s": None, "lower_bound_L_s": None, "dwell_end_s": None, "route": None,
                           "exposure": [], "compute_s": None, "within_budget": False, "policy": spec.get("policy"),
                           "limits": (spec.get("request_params") or {}).get("limits") or
                           {"peak_kw_m2": C.DEFAULT_PEAK_KW_M2, "dose_kj_m2": C.DEFAULT_DOSE_KJ_M2, "incurred_dose_kj_m2": 0},
                           "independent_check": None, "assumptions": None,
                           "notes": ["API internal error; treat as unresolved (never safe)."]},
                "timings": {"worker_total_s": time.perf_counter() - t_start}}
