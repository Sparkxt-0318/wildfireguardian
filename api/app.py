"""FastAPI application: http://127.0.0.1:8765/v1 (local only, no auth, no runtime network).

Every response carries provenance. Verdicts come only from the kit's authoritative decision via api.verdict.
"""
from __future__ import annotations

import asyncio
import json
import math
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import API_VERSION
from . import config as C
from . import contract as K
from . import dispatch as D
from . import exports as X
from . import live as LV
from .errors import APIError, conflict, not_found, unavailable, unprocessable
from .jobs import JobManager
from .provenance import APPROXIMATION_NOTE, CLOCK_DEFINITION, Identity, utc_now
from .regions import Registry, normalize_input_time, tag_to_iso
from .requests_build import build_request, effective_limits, is_default_limits

STATIC = Path(__file__).resolve().parent / "static"


class State:
    settings: C.Settings
    identity: Identity
    registry: Registry
    jobs: JobManager
    live: "LV.LiveState | None" = None      # step 9 live road state; None unless WFG_API_LIVE_CLOSURES=1


def create_app(settings: C.Settings | None = None) -> FastAPI:
    st = State()
    # Decided once, when the routes are registered: with the flag off the live socket does not exist and no code path
    # below changes a request, a job record or a response.
    live_on = settings.live_closures if settings is not None else C.live_closures_enabled()
    st.live = LV.LiveState() if live_on else None

    @asynccontextmanager
    async def lifespan(app):
        st.settings = settings or C.load_settings()
        st.identity = Identity()
        st.registry = Registry(st.settings).load()
        st.jobs = JobManager(st.settings.runtime_dir, st.settings.workers)
        app.state.wfg = st
        yield
        st.jobs.shutdown()

    app = FastAPI(title="WildfireGuardian Route-Check API", version=API_VERSION, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    # ---------------------------------------------------------------------------------------------- errors
    def _error_provenance() -> dict | None:
        ident = getattr(st, "identity", None)
        return ident.base() if ident is not None else None

    @app.exception_handler(APIError)
    async def _api_error(request, exc: APIError):
        return JSONResponse(dict(exc.body(), provenance=_error_provenance()), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request, exc: RequestValidationError):
        return JSONResponse({"error": {"code": "VALIDATION_ERROR", "message": "invalid request parameters",
                                       "details": json.loads(json.dumps(exc.errors(), default=str))},
                             "provenance": _error_provenance()}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_%d" % exc.status_code)
        return JSONResponse({"error": {"code": code, "message": str(exc.detail)}, "provenance": _error_provenance()},
                            status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _internal(request, exc: Exception):
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "%s: %s" % (type(exc).__name__, exc)},
                             "provenance": _error_provenance()}, status_code=500)

    # ---------------------------------------------------------------------------------------------- docs
    def _openapi() -> dict:
        return K.spec()

    @app.get("/openapi.json", include_in_schema=False)
    @app.get("/v1/openapi.json", include_in_schema=False)
    async def openapi_json():
        return JSONResponse(_openapi())

    @app.get("/docs", include_in_schema=False)
    @app.get("/v1/docs", include_in_schema=False)
    async def docs():
        html = get_swagger_ui_html(openapi_url="/openapi.json", title="WildfireGuardian 경로 점검 API 문서",
                                   swagger_js_url="/static/swagger-ui/swagger-ui-bundle.js",
                                   swagger_css_url="/static/swagger-ui/swagger-ui.css",
                                   swagger_favicon_url="/static/swagger-ui/favicon-32x32.png",
                                   swagger_ui_parameters={"docExpansion": "list", "defaultModelsExpandDepth": 0})
        return HTMLResponse(html.body.decode().replace('<html>', '<html lang="ko">', 1))

    @app.get("/", include_in_schema=False)
    async def root():
        return JSONResponse({"service": "WildfireGuardian Route-Check API", "base": "/v1", "docs": "/docs", "openapi": "/openapi.json"})

    # ---------------------------------------------------------------------------------------------- helpers
    def _body(raw: bytes, component: str) -> dict:
        def _no_constant(tok):
            raise ValueError("non-finite number %s is not valid JSON" % tok)

        def _finite_float(tok):               # 1e999 parses to inf; reject it like NaN and Infinity
            v = float(tok)
            if not math.isfinite(v):
                raise ValueError("number %s is outside the finite range" % tok[:40])
            return v

        def _finite_int(tok):                 # an integer too large for a float would overflow later
            v = int(tok)
            if abs(v) > sys.float_info.max:
                raise ValueError("integer %s... is outside the finite range" % tok[:20])
            return v
        try:
            body = json.loads(raw or b"null", parse_constant=_no_constant, parse_float=_finite_float, parse_int=_finite_int)
        except ValueError as exc:
            raise unprocessable("VALIDATION_ERROR", "request body is not valid JSON: %s" % exc)
        errs = K.errors(component, body)
        if errs:
            raise unprocessable("VALIDATION_ERROR", "request body does not match %s" % component, errs[:20])
        return body

    def _require_data():
        if not st.registry.regions:
            raise unavailable("DATA_UNAVAILABLE", "recorded routing inputs are not loaded; run: python tools/fetch_routing_inputs.py",
                              {"issues": st.registry.issues})

    def _resolve_fire(region, tag: str, fire: dict):
        """Return (scenario_set, zone_plan or None)."""
        sset = st.registry.scenario_set(region, tag)
        if fire["type"] == "recorded":
            want = st.registry.scenario_set_by_id(region, fire["scenario_set_id"])
            if want.tag != tag:
                raise unprocessable("SCENARIO_SET_TIME_MISMATCH", "scenario set %s belongs to input_time %s, not %s"
                                    % (want.scenario_set_id, tag_to_iso(want.tag), tag_to_iso(tag)))
            return sset, None
        bsid = fire.get("burning_scenario_set_id")
        if bsid is not None and bsid != sset.scenario_set_id:
            raise unprocessable("SCENARIO_SET_TIME_MISMATCH", "burning_scenario_set_id must be the recorded scenario set at input_time (%s)"
                                % sset.scenario_set_id)
        import numpy as np
        from .adapters import spread_zones as SZ
        from .regions import to_5179
        md = json.loads((sset.packet_dir / "NATIVE_METADATA.json").read_text())
        with np.load(sset.packet_dir / "constructed_arrays.npz", allow_pickle=False) as z:
            present = z["current_active"].copy()
        T = float(md["construction"]["assumptions"]["burning_duration_s"])
        reg_md = md.get("regional") or {}
        window = reg_md.get("window_rows_cols_north_up")
        event_grid = None
        if window is not None and reg_md.get("full_event_shape") and reg_md.get("full_event_affine_transform"):
            hf, wf = reg_md["full_event_shape"]
            a, _, c, _, e, f = reg_md["full_event_affine_transform"]
            event_grid = {"x0": c, "y0": f + hf * e, "resolution": a, "width": wf, "height": hf}
        zone_plan = SZ.plan(region=region, sset=sset, fire_input=fire, to_5179=to_5179, horizon_s=sset.horizon_s,
                            active_duration_s=T, present_fire=present, window=window, event_grid=event_grid)
        return sset, zone_plan

    def _prov(out: dict | None, region, sset, fire_type: str, policy: str, limits: dict) -> dict:
        out = out or {}
        sids = out.get("scenario_ids") or (list(sset.scenario_ids) if fire_type == "recorded" else [])
        recorded_match = None
        if fire_type == "recorded" and out.get("request_object") is not None:
            for key, path in region.missions.items():
                if key.startswith(sset.tag) and json.loads(Path(path).read_text()) == out["request_object"]:
                    recorded_match = key
        evaluated = fire_type == "recorded" and policy == "full" and (is_default_limits(limits) or recorded_match is not None)
        return st.identity.base(region=region.id, input_time=tag_to_iso(sset.tag), graph_id=out.get("graph_id") or region.graph.revision,
                                input_hashes=out.get("input_hashes") or {},
                                scenario_set_id=sids[0].rsplit(":", 1)[0] if sids else None, scenario_ids=sids,
                                fire_input_type=fire_type, policy=policy, evaluated_configuration=evaluated,
                                approximation=APPROXIMATION_NOTE if fire_type == "spread_zones" else None,
                                clock=CLOCK_DEFINITION, recorded_mission_match=recorded_match,
                                budget_s=C.BUDGET_S, workers=st.settings.workers)

    def _job_prov(region, sset, fire_type: str, policy: str, limits: dict | None) -> dict:
        """Provenance known when a job is accepted (inputs it will use); the finished result carries the full record."""
        recorded = fire_type == "recorded"
        hashes = {"graph": region.graph.sha256}
        if recorded:
            hashes["hazard"] = sset.hazard_sha256
        return st.identity.base(region=region.id, input_time=tag_to_iso(sset.tag), graph_id=region.graph.revision,
                                input_hashes=hashes, scenario_set_id=sset.scenario_set_id if recorded else None,
                                scenario_ids=list(sset.scenario_ids) if recorded else [], fire_input_type=fire_type, policy=policy,
                                evaluated_configuration=(recorded and policy == "full" and limits is not None and is_default_limits(limits)) or None,
                                approximation=APPROXIMATION_NOTE if fire_type == "spread_zones" else None, clock=CLOCK_DEFINITION,
                                budget_s=C.BUDGET_S, workers=st.settings.workers)

    def _graph_input_v(region, job_dir: Path) -> tuple:
        """The road graph a job runs on: (graph_path, live_meta, state_version). Without live closures (flag off, or none
        in this region) it is the recorded graph.json and live_meta is None. With closures it is a derived graph.json
        written into the job's inputs/ directory without the closed edges and without forbidden_turns pairs that name them
        (same revision); live_meta records the closed edge ids, the region's live state version and both hashes for the
        job provenance. The closed set and the version are read together (one snapshot)."""
        if st.live is None:
            return str(region.graph_path), None, None
        closed, version = st.live.snapshot(region.id)
        closed = tuple(sorted(e for e in closed if e in region.graph.edges))
        if not closed:
            return str(region.graph_path), None, version
        path = Path(job_dir) / "inputs" / "graph.json"
        sha, dropped = st.live.graphs.write(region.graph_path, region.graph.sha256, closed, path)
        meta = {"closed_edge_ids": list(closed), "state_version": version, "base_graph_sha256": region.graph.sha256,
                "derived_graph_sha256": sha, "derived_graph_path": str(path), "forbidden_turns_dropped": dropped,
                "source": "WS /v1/live/closures (crossing-unit CLOSED reports; advisory, unverified in the field)"}
        return str(path), meta, version

    def _graph_input(region, job_dir: Path) -> tuple:
        return _graph_input_v(region, job_dir)[:2]

    def _with_live(prov: dict, meta) -> dict:
        """Add the live-closure record to a provenance dict (no-op without one). A derived graph replaces the graph hash
        and makes the run NOT the evaluated configuration (the study evaluated the unmodified recorded graph)."""
        if meta:
            prov["live_closures"] = dict(meta)
            if meta.get("derived_graph_sha256"):
                prov.setdefault("input_hashes", {})["graph"] = meta["derived_graph_sha256"]
                prov["evaluated_configuration"] = False
        return prov

    def _new_route_job(body: dict, region, sset, zone_plan, snap: dict, parent=None, request_params=None, prebuilt=None,
                       callback=None, graph_input=None) -> dict:
        job_id = st.jobs.new_id("rc")
        fire = body["fire_input"]
        policy = body.get("policy", "full")
        limits = request_params["limits"]
        graph_path, live_meta = graph_input or _graph_input(region, st.jobs.job_dir(job_id))
        job = {"job_id": job_id, "kind": "route_check", "status": "queued", "created_at": utc_now(), "started_at": None,
               "finished_at": None, "request": body, "snap": snap, "result": None, "error": None,
               "provenance": _with_live(_job_prov(region, sset, fire["type"], policy, limits), live_meta)}
        if parent:
            job["parent_job_id"] = parent
        st.jobs.put(job)
        if callback is not None:
            callbacks[job_id] = callback
        spec = {"job_id": job_id, "job_dir": str(st.jobs.job_dir(job_id)), "graph_path": graph_path,
                "packet_dir": str(sset.packet_dir), "fire_input": {"type": fire["type"]}, "zone_plan": zone_plan,
                "request_params": request_params, "policy": policy, "python": st.settings.python,
                "run_independent_check": bool(body.get("run_independent_check", False)),
                "runtime_dir": str(st.settings.runtime_dir)}
        if prebuilt:
            spec["prebuilt_packet"], spec["adapter_meta"] = prebuilt
            spec["zone_plan"] = None

        def on_start():
            st.jobs.update(job_id, status="running", started_at=utc_now())

        def on_done(out, exc, job_id=job_id):
            if exc is not None or out is None:
                out = {"status": "failed", "error": {"code": "WORKER_ERROR", "message": repr(exc)},
                       "result": {"verdict": "unresolved", "reason_code": "INTERNAL_ERROR", "raw_status": None,
                                  "raw_reason": repr(exc), "departure_s": None, "arrival_s": None, "lower_bound_L_s": None,
                                  "dwell_end_s": None, "route": None, "exposure": [], "compute_s": None, "within_budget": False,
                                  "policy": policy, "limits": limits, "independent_check": None, "assumptions": None,
                                  "notes": ["API worker failure; treat as unresolved (never safe)."]}}
            res = out.get("result")
            if res is not None:
                res["provenance"] = _prov(out, region, sset, fire["type"], policy, limits)
                if live_meta:
                    res["provenance"]["live_closures"] = dict(live_meta)
                    if live_meta.get("derived_graph_sha256"):
                        res["provenance"]["evaluated_configuration"] = False
                if out.get("timings"):
                    res["provenance"]["timings_s"] = out["timings"]
                if out.get("receipt"):
                    res["provenance"]["receipt"] = out["receipt"]
            if out.get("tainted"):
                st.jobs.pause("kit attempt %s: process cleanup was not confirmed CLEAN; new launches are paused as the frozen "
                              "controller requires. Check for leftover processes, then restart the API." % job_id)
            st.jobs.update(job_id, status="done" if out.get("status") == "done" else "failed", finished_at=utc_now(),
                           result=res, error=out.get("error"))
            cb = callbacks.pop(job_id, None)
            if cb:
                cb(job_id)
        st.jobs.schedule("route_check", spec, on_start, on_done, priority=1 if parent else 0)
        return job

    callbacks: dict = {}

    def _request_params(body, region, sset, snap):
        limits = effective_limits(body)
        rp = {"start_node": snap["start"]["node_id"], "dest_node": snap["destination"]["node_id"],
              "depart_offset_s": body.get("depart_offset_s", 0), "dwell_s": body.get("dwell_s", C.DEFAULT_DWELL_S),
              "window": body.get("destination_window"), "limits": limits}
        # validate now (synchronous 422) with the recorded set's clock; the worker rebuilds it on the actual packet
        build_request(start_node=rp["start_node"], dest_node=rp["dest_node"], depart_offset_s=rp["depart_offset_s"],
                      dwell_s=rp["dwell_s"], window=rp["window"], limits=limits, scenario_ids=list(sset.scenario_ids),
                      horizon_s=sset.horizon_s, valid_from=sset.valid_from, hazard_version=sset.hazard_version,
                      as_of_iso=sset.time_origin, dt=sset.dt)
        return rp

    # ---------------------------------------------------------------------------------------------- system
    def _notices() -> list:
        out = []
        if st.jobs.interrupted:
            out.append("%d job(s) left queued or running by the previous server process were marked failed "
                       "(SERVER_RESTARTED); a kit attempt that was running then may still be finishing on its own."
                       % st.jobs.interrupted)
        if st.settings.host not in ("127.0.0.1", "localhost", "::1"):
            out.append("bound to %s: the API has no authentication and is meant for local use only" % st.settings.host)
        return out

    def _tool_issues() -> list:
        import os
        out = []
        for tool in ("/usr/bin/time", "/bin/ps"):
            if not os.access(tool, os.X_OK):
                out.append("%s is missing; the kit controller needs it (Debian/Ubuntu: apt-get install time procps)" % tool)
        return out

    @app.get("/v1/health")
    async def health():
        reg = st.registry
        issues = list(reg.issues) + _tool_issues() + ([st.jobs.paused] if st.jobs.paused else [])
        return {"status": "ok" if reg.regions and not issues else "degraded", "api_version": API_VERSION,
                "package": st.identity.package, "package_version": st.identity.package_version, "kit": st.identity.kit,
                "checkpoint": st.identity.checkpoint, "git_commit": st.identity.git_commit, "regions": sorted(reg.regions),
                "workers": st.settings.workers, "data_root": str(st.settings.data_root), "issues": issues,
                "jobs": st.jobs.counts(), "queued_tasks": st.jobs.queued(), "budget_s": C.BUDGET_S,
                "pool_restarts": st.jobs.pool_restarts, "notices": _notices(),
                "kit_candidate_id": st.identity.kit_candidate_id, "git_dirty": st.identity.git_dirty,
                "provenance": st.identity.base(input_hashes={"%s/graph" % r.id: r.graph.sha256 for r in reg.regions.values()})}

    @app.get("/v1/regions")
    async def regions():
        _require_data()
        hashes = {"%s/graph" % r.id: r.graph.sha256 for r in st.registry.regions.values()}
        for r in st.registry.regions.values():
            for s in r.scenario_sets.values():
                hashes["%s/%s/HAZARD.json" % (r.id, s.tag)] = s.hazard_sha256
        return {"regions": [st.registry.region(rid).public() for rid in sorted(st.registry.regions)],
                "provenance": st.identity.base(input_hashes=hashes,
                                               scenario_ids=[i for r in st.registry.regions.values() for s in r.scenario_sets.values() for i in s.scenario_ids])}

    @app.get("/v1/regions/{region}/forecast")
    async def forecast(region: str, input_time: str, only_nonzero: bool = False):
        _require_data()
        from .forecast import forecast_collection
        r = st.registry.region(region, status=404)
        tag = normalize_input_time(input_time)
        sset = st.registry.scenario_set(r, tag, status=404)
        body = forecast_collection(r, sset, st.identity, only_nonzero=only_nonzero)
        return Response(json.dumps(body, allow_nan=False), media_type="application/geo+json")

    # ---------------------------------------------------------------------------------------------- route checks
    def _require_capacity(extra: int = 1):
        from .jobs import MAX_QUEUED_TASKS
        if st.jobs.queued() + extra > MAX_QUEUED_TASKS:
            raise unavailable("BUSY", "too many queued checks (%d); retry later" % st.jobs.queued())
        if st.jobs.paused:
            raise unavailable("LAUNCHES_PAUSED", st.jobs.paused)

    @app.post("/v1/route-checks", status_code=202)
    async def create_route_check(request: Request):
        body = _body(await request.body(), "RouteCheckRequest")
        _require_data()
        _require_capacity()
        region = st.registry.region(body["region"])
        tag = normalize_input_time(body["input_time"])
        sset, zone_plan = _resolve_fire(region, tag, body["fire_input"])
        snap = {"start": region.graph.snap(body["start"], "start"), "destination": region.graph.snap(body["destination"], "destination")}
        rp = _request_params(body, region, sset, snap)
        norm = dict(body)
        norm.setdefault("depart_offset_s", 0); norm.setdefault("dwell_s", C.DEFAULT_DWELL_S); norm.setdefault("policy", "full")
        norm.setdefault("run_independent_check", False); norm["limits"] = {k: rp["limits"][k] for k in ("peak_kw_m2", "dose_kj_m2")}
        norm.setdefault("incurred_dose_kj_m2", rp["limits"]["incurred_dose_kj_m2"])
        job = _new_route_job(norm, region, sset, zone_plan, snap, request_params=rp)
        return JSONResponse({"job_id": job["job_id"], "status": "queued", "kind": "route_check", "snap": snap,
                             "provenance": job["provenance"],
                             "links": {"self": "/v1/route-checks/%s" % job["job_id"],
                                       "export_geojson": "/v1/route-checks/%s/export?format=geojson" % job["job_id"]}},
                            status_code=202)

    @app.get("/v1/route-checks/{job_id}")
    async def get_route_check(job_id: str):
        j = st.jobs.get(job_id)
        if j is None or j.get("kind") != "route_check":
            raise not_found("JOB_NOT_FOUND", "route check %r not found" % job_id)
        return j

    @app.get("/v1/route-checks/{job_id}/export")
    async def export_route_check(job_id: str, format: str):
        j = st.jobs.get(job_id)
        if j is None or j.get("kind") != "route_check":
            raise not_found("JOB_NOT_FOUND", "route check %r not found" % job_id)
        if format not in ("geojson", "kml", "csv"):
            raise unprocessable("VALIDATION_ERROR", "format must be geojson, kml or csv", {"format": format})
        if j["status"] not in ("done", "failed"):
            raise conflict("JOB_NOT_DONE", "route check is %s" % j["status"])
        res = j.get("result") or {}
        if res.get("verdict") != "checked_route" or not res.get("route"):
            raise conflict("NO_CHECKED_ROUTE", "only checked routes are exported; this result is %s" % res.get("verdict"),
                           {"verdict": res.get("verdict"), "reason_code": res.get("reason_code")})
        fname = "wfg_route_%s" % job_id
        if format == "geojson":
            return Response(json.dumps(X.to_geojson(j), allow_nan=False), media_type="application/geo+json",
                            headers={"Content-Disposition": 'attachment; filename="%s.geojson"' % fname})
        if format == "kml":
            return Response(X.to_kml(j), media_type="application/vnd.google-earth.kml+xml",
                            headers={"Content-Disposition": 'attachment; filename="%s.kml"' % fname,
                                     "X-WFG-Provenance": X.provenance_header(j)})
        return PlainTextResponse(X.to_csv(j), media_type="text/csv",
                                 headers={"Content-Disposition": 'attachment; filename="%s.csv"' % fname,
                                          "X-WFG-Provenance": X.provenance_header(j)})

    # ---------------------------------------------------------------------------------------------- dispatch
    @app.post("/v1/dispatch-plans", status_code=202)
    async def create_dispatch(request: Request):
        body = _body(await request.body(), "DispatchPlanRequest")
        job = _submit_dispatch(body)
        if st.live is not None:          # the live recompute reruns the most recent plan of the region
            st.live.remember_plan(body["region"], body)
        return JSONResponse({"job_id": job["job_id"], "status": st.jobs.get(job["job_id"])["status"], "kind": "dispatch_plan",
                             "provenance": job["provenance"],
                             "links": {"self": "/v1/dispatch-plans/%s" % job["job_id"]}}, status_code=202)

    def _submit_dispatch(body: dict, live_trigger: dict | None = None, on_finish=None) -> dict:
        """Validate and launch one dispatch plan (``body`` already matches DispatchPlanRequest); return the job record.
        ``on_finish(job_id, status, error)`` (live recompute only) is called once when the job record is final; it may run
        before this function returns (synchronous schedulers) and in a worker-callback thread."""
        _require_data()
        if len(body["origins"]) > C.MAX_DISPATCH_ORIGINS:
            raise unprocessable("TOO_MANY_ORIGINS", "at most %d origins" % C.MAX_DISPATCH_ORIGINS)
        region = st.registry.region(body["region"])
        tag = normalize_input_time(body["input_time"])
        sset, zone_plan = _resolve_fire(region, tag, body["fire_input"])
        dests = []
        for d in body["destinations"]:
            dests.append((d, region.graph.snap(d["location"], "destination %s" % d["id"])))
        ids = [o["id"] for o in body["origins"]]
        if len(set(ids)) != len(ids) or len({d["id"] for d in body["destinations"]}) != len(body["destinations"]):
            raise unprocessable("DUPLICATE_ID", "origin ids and destination ids must be unique")
        origins, rejected = [], []
        for o in body["origins"]:
            try:
                origins.append((o, region.graph.snap(o["location"], "origin %s" % o["id"])))
            except APIError as e:
                rejected.append({"origin_id": o["id"], "error": {"code": e.code, "message": e.message}})
        policy = body.get("policy", "full")
        if policy != "full":
            raise unprocessable("POLICY_NOT_ALLOWED", "dispatch plans use the full policy only; reduced policies may return routes "
                                "that fail the full hazard model", {"policy": policy})
        from .requests_build import lattice_int
        offs = [lattice_int(o, "depart_offsets_s") for o in body["depart_offsets_s"]]
        if len(set(offs)) != len(offs):
            raise unprocessable("DUPLICATE_OFFSET", "depart_offsets_s must not repeat a value", {"depart_offsets_s": body["depart_offsets_s"]})
        dwell_default = body.get("dwell_s", C.DEFAULT_DWELL_S)
        limits_body = {"limits": body.get("limits") or {}}
        attempts_spec, pre_rejected = [], {}
        for o, osnap in origins:
            for d, dsnap in dests:
                for off in offs:
                    pseudo = {"depart_offset_s": off, "dwell_s": d.get("dwell_s", dwell_default), "destination_window": d.get("window"),
                              **limits_body}
                    try:
                        rp = _request_params(pseudo, region, sset, {"start": osnap, "destination": dsnap})
                    except APIError as e:   # this combination cannot be posed (e.g. window unsatisfiable): never a route
                        pre_rejected[(o["id"], d["id"], off)] = {
                            "destination_id": d["id"], "depart_offset_s": off, "verdict": "unresolved", "reason_code": "INPUT_REJECTED",
                            "raw_reason": e.code, "arrival_s": None, "lower_bound_L_s": None, "compute_s": None, "route_check_job_id": None}
                        continue
                    attempts_spec.append((o, osnap, d, dsnap, off, rp))
        _require_capacity(len(attempts_spec))
        if len(attempts_spec) + len(pre_rejected) > C.MAX_DISPATCH_ATTEMPTS:
            raise unprocessable("TOO_MANY_ATTEMPTS", "origins x destinations x offsets is %d; the limit is %d per plan"
                                % (len(attempts_spec) + len(pre_rejected), C.MAX_DISPATCH_ATTEMPTS))
        job_id = st.jobs.new_id("dp")
        total = len(attempts_spec) + len(pre_rejected)
        dp_limits = effective_limits({"limits": body.get("limits") or {}})
        gp, live_meta, state_version = _graph_input_v(region, st.jobs.job_dir(job_id))
        dp_graph = (gp, live_meta)                                     # one closure snapshot for the whole plan
        if live_meta is not None and live_trigger is not None:
            live_meta = dict(live_meta, recompute=live_trigger)
        elif live_meta is None and live_trigger is not None:
            live_meta = {"closed_edge_ids": [], "state_version": state_version, "recompute": live_trigger}
        job = {"provenance": _with_live(_job_prov(region, sset, body["fire_input"]["type"], policy, dp_limits), live_meta),
               "job_id": job_id, "kind": "dispatch_plan", "status": "queued", "created_at": utc_now(), "started_at": None,
               "finished_at": None, "request": body, "progress": {"done": len(pre_rejected), "total": total}, "result": None, "error": None}
        st.jobs.put(job)
        t_start = time.perf_counter()
        lock = threading.Lock()
        records: dict = dict(pre_rejected)
        dest_order = {d["id"]: i for i, (d, _) in enumerate(dests)}
        origin_order = {o["id"]: i for i, o in enumerate(body["origins"])}

        def finish(error=None):
            if on_finish is None:            # every non-live plan: exactly as before
                _finish(error)
                return
            try:
                _finish(error)
            except Exception as exc:        # never leave a live recompute marked running
                st.jobs.update(job_id, status="failed", finished_at=utc_now(),
                               error={"code": "INTERNAL_ERROR", "message": "%s: %s" % (type(exc).__name__, exc)})
            if on_finish is not None:
                j = st.jobs.get(job_id) or {}
                try:
                    on_finish(job_id, j.get("status") or "failed", j.get("error"))
                except Exception:
                    pass

        def _finish(error=None):
            if error is not None:
                st.jobs.update(job_id, status="failed", finished_at=utc_now(), error=error)
                return
            plans = []
            all_attempts = []
            for o, osnap in origins:
                atts = [records[k] for k in records if k[0] == o["id"]]
                all_attempts += atts
                plans.append(D.origin_plan(o["id"], osnap, atts, dest_order))
            plans = D.sort_by_urgency(plans, origin_order)
            prov = st.identity.base(region=region.id, input_time=tag_to_iso(tag), graph_id=region.graph.revision,
                                    input_hashes={"graph": region.graph.sha256, "hazard": sset.hazard_sha256} if zone_plan is None else {"graph": region.graph.sha256},
                                    scenario_set_id=sset.scenario_set_id if zone_plan is None else None,
                                    scenario_ids=list(sset.scenario_ids) if zone_plan is None else [],
                                    fire_input_type=body["fire_input"]["type"], policy=policy,
                                    evaluated_configuration=(zone_plan is None and policy == "full" and is_default_limits(dp_limits)),
                                    approximation=APPROXIMATION_NOTE if zone_plan is not None else None, clock=CLOCK_DEFINITION,
                                    budget_s=C.BUDGET_S, workers=st.settings.workers)
            if zone_plan is not None and shared.get("meta"):
                prov["scenario_ids"] = shared["meta"]["scenario_ids"]
                prov["scenario_set_id"] = shared["meta"]["scenario_ids"][0].rsplit(":", 1)[0]
                prov["input_hashes"].update({"zones/" + k: v for k, v in (shared["meta"].get("input_hashes") or {}).items()})
            _with_live(prov, live_meta)
            result = {"plans": plans, "summary": D.summary(plans, all_attempts, time.perf_counter() - t_start),
                      "rejected_origins": rejected, "assumptions": zone_plan["assumptions"] if zone_plan else None, "provenance": prov}
            st.jobs.update(job_id, status="done", finished_at=utc_now(), result=result)

        def attempt_done(rc_id, key):
            j = st.jobs.get(rc_id)
            res = j.get("result") or {}
            o, d, off = key
            rec = {"destination_id": d, "depart_offset_s": off, "verdict": res.get("verdict", "unresolved"),
                   "reason_code": res.get("reason_code") if res else "INTERNAL_ERROR", "arrival_s": res.get("arrival_s"),
                   "lower_bound_L_s": res.get("lower_bound_L_s"), "compute_s": res.get("compute_s"), "route_check_job_id": rc_id}
            with lock:
                records[key] = rec
                n = len(records)
            st.jobs.update(job_id, progress={"done": n, "total": total})
            if n == total:
                finish()

        shared: dict = {}

        def launch(prebuilt=None):
            if not attempts_spec:
                finish()
                return
            for o, osnap, d, dsnap, off, rp in attempts_spec:
                fire_ref = body["fire_input"] if body["fire_input"]["type"] == "recorded" else \
                    {"type": "spread_zones", "see_dispatch_plan": job_id, "plan_sha256": zone_plan["plan_sha256"]}
                rbody = {"region": body["region"], "input_time": body["input_time"], "start": o["location"],
                         "destination": d["location"], "depart_offset_s": off, "dwell_s": rp["dwell_s"],
                         "destination_window": d.get("window"), "policy": policy, "fire_input": fire_ref,
                         "limits": {k: rp["limits"][k] for k in ("peak_kw_m2", "dose_kj_m2")}, "run_independent_check": False}
                if rbody["destination_window"] is None:
                    rbody.pop("destination_window")
                key = (o["id"], d["id"], off)
                _new_route_job(rbody, region, sset, zone_plan, {"start": osnap, "destination": dsnap}, parent=job_id,
                               request_params=rp, prebuilt=prebuilt, callback=lambda rc_id, key=key: attempt_done(rc_id, key),
                               graph_input=dp_graph)

        st.jobs.update(job_id, status="running", started_at=utc_now())
        if zone_plan is None:
            launch()
        else:
            pdir = st.jobs.job_dir(job_id) / "zone_packet"

            def zp_done(out, exc):
                if exc is not None or not out or out.get("status") != "done":
                    finish(error=(out or {}).get("error") or {"code": "ZONE_PACKET_BUILD_FAILED", "message": repr(exc)})
                    return
                shared["meta"] = out["adapter_meta"]
                launch(prebuilt=(out["packet_dir"], out["adapter_meta"]))
            st.jobs.schedule("zone_packet", {"zone_plan": zone_plan, "graph_path": dp_graph[0], "out_dir": str(pdir),
                                             "python": st.settings.python}, lambda: None, zp_done, priority=1)
        if st.live is not None:
            st.live.note_plan_origins(region.id, job_id, [o["id"] for o in body["origins"]])
        return job

    @app.get("/v1/dispatch-plans/{job_id}")
    async def get_dispatch(job_id: str):
        j = st.jobs.get(job_id)
        if j is None or j.get("kind") != "dispatch_plan":
            raise not_found("JOB_NOT_FOUND", "dispatch plan %r not found" % job_id)
        return j

    if st.live is not None:
        _register_live(app, st, _submit_dispatch)
    return app


# ------------------------------------------------------------------------------------------------ step 9 live input
LIVE_POLL_S = 0.5            # how often each live socket checks pending/running recomputes (non-blocking asyncio sleep)
LIVE_SUBPROTOCOL = "wfg-live.v1"
LIVE_TOKEN_PREFIX = "wfg-token."
_LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1")


def _host_name(host: str) -> str:
    host = (host or "").strip().lower()
    if host.startswith("["):
        return host[:host.index("]") + 1] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def live_handshake_refusal(headers, subprotocols, settings) -> str | None:
    """Why a WS /v1/live/closures handshake is refused, or None. Checked before accept():
    a browser Origin must be listed exactly in WFG_API_LIVE_ORIGINS ("null" never; the Python client sends none);
    the Host must be loopback, the bind host or listed in WFG_API_LIVE_HOSTS (DNS rebinding);
    with WFG_API_LIVE_TOKEN set, the client must offer "wfg-token.<token>" as a subprotocol (constant-time compare)."""
    origin = headers.get("origin")
    if origin is not None and (origin.strip() == "null" or origin.strip() not in tuple(settings.live_origins or ())):
        return "origin not allowed"
    allowed = {h.lower() for h in _LOCAL_HOSTS} | {h.lower() for h in (settings.live_hosts or ())}
    if settings.host and settings.host not in ("0.0.0.0", "::"):
        allowed.add(_host_name(settings.host) if ":" not in settings.host else "[%s]" % settings.host.strip("[]"))
    if _host_name(headers.get("host") or "") not in allowed:
        return "host not allowed"
    if settings.live_token:
        offered = [p[len(LIVE_TOKEN_PREFIX):] for p in (subprotocols or ()) if isinstance(p, str) and p.startswith(LIVE_TOKEN_PREFIX)]
        if not any(LV.token_matches(p, settings.live_token) for p in offered):
            return "token missing or wrong"
    return None


def _register_live(app: FastAPI, st: State, submit_dispatch):
    """Register WS /v1/live/closures and GET /v1/live/state (only called when WFG_API_LIVE_CLOSURES=1). See api/live.py
    for the message format and the closure rules. Every frame gets exactly one ack: {"ok": true, ...} or
    {"ok": false, "code", "error", "verdict_id"?}. Recomputes are coalesced per region (at most one live dispatch-plan
    rerun in flight; changes arriving meanwhile stay pending and rerun once with the latest state); every connected
    socket gets {"type": "leave_by_update"} frames (submitted, then done/failed/superseded/unknown_state)."""
    hub_lock = threading.Lock()
    sockets: list = []            # (event loop, outbox queue) per connected socket

    def _broadcast(item):
        with hub_lock:
            targets = list(sockets)
        for loop, q in targets:
            try:
                loop.call_soon_threadsafe(q.put_nowait, item)
            except RuntimeError:      # that socket's loop is gone
                pass

    def _origin_edges(region_id: str, origin_id: str):
        """Edge ids used by the checked routes of this origin's latest plan, or None when that is not known
        (plan not finished, origin rejected, a route-check record missing or without edge ids)."""
        dp = st.live.plan_of_origin(region_id, origin_id)
        j = st.jobs.get(dp) if dp else None
        if not j or j.get("status") != "done" or not j.get("result"):
            return None
        plan = next((p for p in j["result"].get("plans") or [] if p.get("origin_id") == origin_id), None)
        if plan is None:
            return None
        used = set()
        for a in plan.get("attempts") or []:
            if a.get("verdict") != "checked_route":
                continue
            rc = st.jobs.get(a.get("route_check_job_id") or "")
            ids = ((((rc or {}).get("result") or {}).get("route") or {}).get("properties") or {}).get("edge_ids")
            if ids is None:
                return None
            used.update(ids)
        return used

    def _select(region_id: str, body: dict, view: dict) -> tuple:
        """(origins to rerun, basis). A pending REOPENED (or an unknown usage) reruns every origin: a reopened road can
        give any origin a new, later leave-by. CLOSED only: the origins whose last checked routes used a changed edge."""
        if view["all_origins"]:
            return list(body["origins"]), "all_origins (a reopened road can help any origin)"
        changed_set, keep, unknown = set(view["edges"]), [], []
        for o in body["origins"]:
            used = _origin_edges(region_id, o["id"])
            if used is None:
                unknown.append(o["id"]); keep.append(o)
            elif used & changed_set:
                keep.append(o)
        return keep, "origins_whose_routes_used_the_edge" + (" (usage unknown for %d, included)" % len(unknown) if unknown else "")

    def _status(rid: str, **kw):
        with st.live.lock:
            st.live.recompute_status[rid] = dict(kw, at=utc_now(), pending=st.live.pending_view(rid) is not None)

    def _settled(rid: str, reserve: dict, job_id: str, status: str, error):
        """A live recompute's job record is final (any thread). Clears the pending changes it covered only when done."""
        with st.live.lock:
            if st.live.running.get(rid) is reserve:
                st.live.running.pop(rid)
            if status == "done":
                st.live.clear_pending(rid, reserve["seq"])
            reserve["finished"] = True
            announce = reserve.get("job_id") is not None          # else _kick announces after "submitted"
            _status(rid, status=status, job_id=job_id, error=error, state_version=reserve.get("version"),
                    attempt_mono=time.monotonic())
        if announce:
            _broadcast(("job", job_id))

    def _kick(rid: str, force: bool) -> dict | None:
        """Submit one recompute covering every pending change of the region, unless one is already in flight
        (coalesced: it reruns once that one finishes). ``force`` (a new event) ignores the retry interval after a failure.
        Never raises: a failure keeps the changes pending and is reported (fail closed: the times are flagged stale)."""
        now = time.monotonic()
        with st.live.lock:
            view = st.live.pending_view(rid)
            if view is None:
                return None
            run = st.live.running.get(rid)
            if run is not None:
                return {"status": "coalesced", "job_id": run.get("job_id"), "pending": True,
                        "note": "a recompute is in flight; the pending change reruns once it finishes"}
            last = st.live.recompute_status.get(rid) or {}
            if not force and last.get("status") == "failed" and now - float(last.get("attempt_mono") or 0.0) < LV.RETRY_S:
                return {"status": "failed", "pending": True, "error": last.get("error")}
            reserve = {"seq": view["seq"], "job_id": None, "version": None}
            st.live.running[rid] = reserve
        keep = []
        try:
            body = st.live.plan_body(rid)
            if body is None:
                outcome = {"status": "no_previous_plan", "pending": False}
            else:
                keep, basis = _select(rid, body, view)
                outcome = None if keep else {"status": "not_needed", "pending": False,
                                             "reason": "no origin's last checked route used the closed edge"}
            if outcome is not None:
                with st.live.lock:
                    if st.live.running.get(rid) is reserve:
                        st.live.running.pop(rid)
                    st.live.clear_pending(rid, view["seq"])
                    _status(rid, status=outcome["status"], job_id=None, error=None)
                return outcome
            trigger = dict(view["trigger"], edge_ids=view["edges"], basis=basis, coalesced_events=view["count"])
            job = submit_dispatch(dict(body, origins=keep), live_trigger=trigger,
                                  on_finish=lambda jid, status, error: _settled(rid, reserve, jid, status, error))
        except Exception as e:      # BUSY, LAUNCHES_PAUSED or anything else: the road state already changed; stay pending
            err = {"code": getattr(e, "code", "INTERNAL_ERROR"),
                   "message": getattr(e, "message", None) or "%s: %s" % (type(e).__name__, e)}
            with st.live.lock:
                if st.live.running.get(rid) is reserve:
                    st.live.running.pop(rid)
                _status(rid, status="failed", job_id=None, error=err, attempt_mono=now)
            return {"status": "failed", "pending": True, "error": err}
        version = ((job.get("provenance") or {}).get("live_closures") or {}).get("state_version")
        origins = [o["id"] for o in keep]
        if isinstance(version, int):
            st.live.note_origin_version(rid, origins, version)
        with st.live.lock:
            reserve["job_id"], reserve["version"] = job["job_id"], version
            finished = reserve.get("finished", False)
            if not finished:
                _status(rid, status="submitted", job_id=job["job_id"], error=None, state_version=version)
        out = {"status": "submitted", "job_id": job["job_id"], "origins": origins, "basis": basis, "state_version": version,
               "pending": True}
        _broadcast(("frame", {"type": "leave_by_update", "region": rid, "job_id": job["job_id"], "status": "submitted",
                              "origins": origins, "state_version": version}))
        if finished:
            _broadcast(("job", job["job_id"]))
        return out

    def _supervise():
        """Per poll: settle running recomputes whose job record is final but whose hook never ran (e.g. SERVER_RESTARTED),
        then retry regions with pending changes (at most every RETRY_S after a failure)."""
        with st.live.lock:
            running = list(st.live.running.items())
        for rid, reserve in running:
            jid = reserve.get("job_id")
            j = st.jobs.get(jid) if jid else None
            if jid and (j is None or j.get("status") in ("done", "failed")):
                _settled(rid, reserve, jid, (j or {}).get("status") or "failed",
                         (j or {}).get("error") or {"code": "JOB_NOT_FOUND", "message": "job record missing"})
        for rid in st.live.pending_regions():
            _kick(rid, force=False)

    def _apply(ev: dict) -> dict:
        """Apply one validated event; return the ack. Raises APIError (bad region/point) only BEFORE any state change.
        After a change the ack is always ok:true; a failed recompute is reported in it as status failed, pending true."""
        if not st.registry.regions:
            raise unavailable("DATA_UNAVAILABLE", "recorded routing inputs are not loaded")
        from .regions import to_5179
        region = st.registry.region(ev["region"])
        g = region.graph
        m = g.nearest_edge(ev["lon"], ev["lat"], max_m=C.SNAP_MAX_M, margin_m=LV.MATCH_MARGIN_M)
        claim = (ev["unit_id"], ev["session_id"])
        rid = region.id
        x, y = (float(v) for v in to_5179(ev["lon"], ev["lat"]))
        ack = {"ok": True, "event": ev["event"], "region": rid, "verdict_id": ev["verdict_id"], "edge_ids": [],
               "distance_m": m["distance_m"], "matched_edge_id": m["edge_id"], "matched_edge_ids": list(m["close_edge_ids"]),
               "match_margin_m": LV.MATCH_MARGIN_M, "placeholder_limits": True}

        def refuse(code: str, msg: str) -> dict:
            return {"ok": False, "code": code, "event": ev["event"], "verdict_id": ev["verdict_id"], "error": msg,
                    "edge_ids": [], "distance_m": m["distance_m"]}

        if ev["event"] == "CLOSED":
            edges = list(m["close_edge_ids"])
            ahead, pts = [], []
            for p in ev.get("ahead") or []:
                try:
                    ma = g.nearest_edge(p["lon"], p["lat"], max_m=C.SNAP_MAX_M, margin_m=LV.MATCH_MARGIN_M)
                except APIError as e:          # the vehicle point still closes its road
                    ahead.append({"ok": False, "code": e.code})
                    continue
                ax, ay = (float(v) for v in to_5179(p["lon"], p["lat"]))
                pts.append([ax, ay])
                ahead.append({"ok": True, "edge_ids": list(ma["close_edge_ids"]), "distance_m": ma["distance_m"]})
                edges += [e for e in ma["close_edge_ids"] if e not in edges]
            rec = {"unit_id": ev["unit_id"], "session_id": ev["session_id"], "verdict_id": ev["verdict_id"],
                   "utc": ev["utc"], "lat": ev["lat"], "lon": ev["lon"], "x": x, "y": y, "ahead_xy": pts,
                   "distance_m": m["distance_m"], "received_at": utc_now()}
            res = st.live.close(rid, claim, ev["verdict_id"], edges, rec)
            ack.update(edge_ids=list(res["edge_ids"]), claim_token=res["token"], duplicate=res["duplicate"],
                       superseded_verdict_ids=res["superseded"], state_version=res["version"])
            if ahead:
                ack["ahead"] = ahead
            changed, all_origins = res["newly"], False
        else:
            own = st.live.records_of(rid, claim)
            if not own:
                held = st.live.holder_count(rid, set(m["close_edge_ids"]))
                if held:
                    out = refuse("CLOSED_BY_OTHER_UNIT", "the road here stays closed: it was closed by another unit/session; "
                                 "only the unit that closed a road reopens it")
                    out["holder_count"] = {e: n for e, n in sorted(held.items())}
                    return out
                return refuse("NOT_CLOSED", "this unit/session holds no closure in %s (matched %s)" % (rid, m["edge_id"]))
            rec = st.live.find_by_token(rid, claim, ev.get("claim_token"))
            if rec is None:
                return refuse("REOPEN_UNAUTHORIZED", "REOPENED must carry the claim_token returned in the ack of the CLOSED "
                              "it reopens; the road stays closed")
            if ev.get("closes_verdict_id") is not None and ev["closes_verdict_id"] != rec["verdict_id"]:
                return refuse("NOT_CLOSED", "closes_verdict_id does not name the closure of this claim_token; the road "
                              "stays closed")
            refs = [(rec["x"], rec["y"])] + [tuple(p) for p in rec.get("ahead_xy") or []]
            d = min(((x - rx) ** 2 + (y - ry) ** 2) ** 0.5 for rx, ry in refs)
            if d > LV.REOPEN_RADIUS_M:
                return refuse("REOPEN_TOO_FAR", "REOPENED is %.0f m from the CLOSED point of %s (limit %.0f m, PLACEHOLDER); "
                              "the road stays closed" % (d, rec["verdict_id"], LV.REOPEN_RADIUS_M))
            rec_edges, here = set(rec["edge_ids"]), set(m["close_edge_ids"])

            def nodes(es):
                return {n for e in es if e in g.edges for n in g.edges[e][:2]}
            if not (rec_edges & here or nodes(rec_edges) & nodes(here)):
                return refuse("REOPEN_NOT_ON_CLOSED_ROAD", "the REOPENED point matches no edge or junction of the closure "
                              "%s; the road stays closed" % rec["verdict_id"])
            reopened, still = st.live.withdraw(rid, claim, rec["verdict_id"])
            ack.update(edge_ids=reopened, reopened_verdict_id=rec["verdict_id"], state_version=st.live.state_version(rid))
            if still:
                ack["still_closed_by_other_units"] = still
            changed, all_origins = reopened, True
        ack["closed_edge_ids"] = list(st.live.closed_edges(rid))
        try:
            if changed:
                st.live.add_pending(rid, changed, all_origins,
                                    {"event": ev["event"], "verdict_id": ev["verdict_id"], "utc": ev["utc"]})
            r = _kick(rid, force=True)
            if r is None:
                r = {"status": "not_needed", "reason": "road state did not change", "pending": False}
        except Exception as e:      # the state change above stands; say so, never "not applied"
            r = {"status": "failed", "pending": True, "error": {"code": "INTERNAL_ERROR", "message": "%s: %s" % (type(e).__name__, e)}}
        ack["recompute"] = r
        return ack

    def _leave_by(job: dict) -> dict:
        """One leave_by_update frame. ``closed_edge_ids``/``state_version`` are the road state the job ran on (its own
        snapshot); ``current_*`` and ``stale`` are read at send time. An origin a newer live recompute also covers is
        marked superseded (leave_by_s null); unknown road state gives status unknown_state and null times (fail closed)."""
        res = job.get("result") or {}
        meta = (job.get("provenance") or {}).get("live_closures") or {}
        rid = (job.get("request") or {}).get("region")
        version, snap = meta.get("state_version"), meta.get("closed_edge_ids")
        known = isinstance(version, int) and not isinstance(version, bool) and isinstance(snap, list) and isinstance(rid, str)
        out = {"type": "leave_by_update", "region": rid, "job_id": job.get("job_id"), "status": job.get("status"),
               "error": job.get("error"), "summary": res.get("summary"),
               "state_version": version if known else None, "closed_edge_ids": list(snap) if known else None,
               "note": "leave_by_s = latest_contiguous_checked_depart_offset_s (conservative); advisory only"}
        if known:
            cur, cur_v = st.live.snapshot(rid)
            out.update(current_closed_edge_ids=list(cur), current_state_version=cur_v, stale=tuple(sorted(snap)) != cur)
        else:
            out.update(current_closed_edge_ids=None, current_state_version=None, stale=None)
            if out["status"] == "done":
                out["status"] = "unknown_state"
        entries = []
        for p in res.get("plans") or []:
            e = {"origin_id": p["origin_id"], "best_verdict": p["best_verdict"],
                 "leave_by_s": p.get("latest_contiguous_checked_depart_offset_s"),
                 "latest_checked_depart_offset_s": p.get("latest_checked_depart_offset_s"),
                 "best_destination_id": (p.get("best") or {}).get("destination_id")}
            newer = st.live.origin_latest_version(rid, p["origin_id"]) if known else None
            if not known or (newer is not None and newer > version):
                e["leave_by_s"] = e["latest_checked_depart_offset_s"] = None
                if known:
                    e["superseded_by_version"] = newer
            entries.append(e)
        out["leave_by"] = entries
        if known and out["status"] == "done" and entries and all("superseded_by_version" in e for e in entries):
            out["status"] = "superseded"
        return out

    st.live_leave_by = _leave_by          # for tests and diagnostics
    st.live_kick = _kick

    @app.get("/v1/live/state")
    async def live_state(region: str):
        """Closed edges, state version and the recompute status of one region. No unit/session ids, no tokens."""
        r = st.registry.region(region)
        rid = r.id
        cur, v = st.live.snapshot(rid)
        with st.live.lock:
            rs = dict(st.live.recompute_status.get(rid) or {})
            pv = st.live.pending_view(rid)
            run = st.live.running.get(rid)
        rs.pop("attempt_mono", None)
        return {"region": rid, "closed_edge_ids": list(cur), "state_version": v,
                "holder_count": st.live.holder_count(rid, set(cur)),
                "recompute": {"last": rs or None, "running_job_id": (run or {}).get("job_id"),
                              "pending": pv is not None, "pending_edge_ids": pv["edges"] if pv else [],
                              "note": ("leave-by times from earlier plans may assume this road state is still open: "
                                       "a recompute is pending or failed") if pv else None},
                "placeholder_limits": {"match_margin_m": LV.MATCH_MARGIN_M, "reopen_radius_m": LV.REOPEN_RADIUS_M},
                "advisory": "advisory for trained crews; unverified in the field"}

    @app.websocket("/v1/live/closures")
    async def live_closures(ws: WebSocket):
        offered = list(ws.scope.get("subprotocols") or [])
        why = live_handshake_refusal(ws.headers, offered, st.settings)
        if why is not None:
            await ws.close(code=1008, reason=why)
            return
        await ws.accept(subprotocol=LIVE_SUBPROTOCOL if LIVE_SUBPROTOCOL in offered else None)
        loop = asyncio.get_running_loop()
        outbox: asyncio.Queue = asyncio.Queue()
        me = (loop, outbox)
        with hub_lock:
            sockets.append(me)
        bucket = [float(LV.RATE_BURST), time.monotonic()]

        async def sender():
            while True:
                kind, obj = await outbox.get()
                if kind == "job":
                    j = st.jobs.get(obj) or {"job_id": obj, "status": "failed",
                                             "error": {"code": "JOB_NOT_FOUND", "message": "job record missing"}}
                    obj = _leave_by(j)
                await ws.send_text(json.dumps(obj, default=str, allow_nan=False))

        async def ticker():
            while True:
                await asyncio.sleep(LIVE_POLL_S)
                try:
                    _supervise()
                except Exception:
                    pass

        tasks = [asyncio.create_task(sender()), asyncio.create_task(ticker())]
        try:
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                if tasks[0].done():
                    break
                now = time.monotonic()
                bucket[0] = min(float(LV.RATE_BURST), bucket[0] + (now - bucket[1]) * float(LV.RATE_PER_S))
                bucket[1] = now
                text = msg.get("text")
                if bucket[0] < 1.0:
                    outbox.put_nowait(("frame", dict({"ok": False, "code": "RATE_LIMITED", "error": "more than %g events/s "
                                                      "on this connection; not applied, resend later" % LV.RATE_PER_S},
                                                     **LV.ids_of(text))))
                    continue
                bucket[0] -= 1.0
                if text is None:
                    outbox.put_nowait(("frame", {"ok": False, "code": "VALIDATION_ERROR", "error": "send one JSON object per text frame"}))
                    continue
                try:
                    ev = LV.parse_event(text)
                except LV.LiveEventError as e:
                    outbox.put_nowait(("frame", dict({"ok": False, "code": e.code, "error": e.message}, **LV.ids_of(text))))
                    continue
                try:
                    ack = _apply(ev)
                except APIError as e:          # raised before any state change
                    ack = {"ok": False, "code": e.code, "error": e.message, "details": e.details, "event": ev["event"],
                           "verdict_id": ev["verdict_id"]}
                except Exception as e:         # raised before any state change (see _apply)
                    ack = {"ok": False, "code": "INTERNAL_ERROR", "error": "%s: %s" % (type(e).__name__, e),
                           "event": ev["event"], "verdict_id": ev["verdict_id"]}
                outbox.put_nowait(("frame", ack))
        except Exception:
            pass
        finally:
            with hub_lock:
                if me in sockets:
                    sockets.remove(me)
            # let queued frames go out before the sender stops (the client may already be gone)
            try:
                await asyncio.wait_for(_drain(outbox), timeout=0.5)
            except Exception:
                pass
            for t in tasks:
                t.cancel()


async def _drain(q: asyncio.Queue):
    while not q.empty():
        await asyncio.sleep(0.01)


app = create_app()
