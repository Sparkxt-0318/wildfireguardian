"""FastAPI application: http://127.0.0.1:8765/v1 (local only, no auth, no runtime network).

Every response carries provenance. Verdicts come only from the kit's authoritative decision via api.verdict.
"""
from __future__ import annotations

import json
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
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


def create_app(settings: C.Settings | None = None) -> FastAPI:
    st = State()

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
    @app.exception_handler(APIError)
    async def _api_error(request, exc: APIError):
        return JSONResponse(exc.body(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request, exc: RequestValidationError):
        return JSONResponse({"error": {"code": "VALIDATION_ERROR", "message": "invalid request parameters",
                                       "details": json.loads(json.dumps(exc.errors(), default=str))}}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_%d" % exc.status_code)
        return JSONResponse({"error": {"code": code, "message": str(exc.detail)}}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _internal(request, exc: Exception):
        return JSONResponse({"error": {"code": "INTERNAL_ERROR", "message": "%s: %s" % (type(exc).__name__, exc)}}, status_code=500)

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
        try:
            body = json.loads(raw or b"null")
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
        window = (md.get("regional") or {}).get("window_rows_cols_north_up")
        zone_plan = SZ.plan(region=region, sset=sset, fire_input=fire, to_5179=to_5179, horizon_s=sset.horizon_s,
                            active_duration_s=T, present_fire=present, window=window)
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

    def _new_route_job(body: dict, region, sset, zone_plan, snap: dict, parent=None, request_params=None, prebuilt=None,
                       callback=None) -> dict:
        job_id = st.jobs.new_id("rc")
        fire = body["fire_input"]
        policy = body.get("policy", "full")
        limits = request_params["limits"]
        job = {"job_id": job_id, "kind": "route_check", "status": "queued", "created_at": utc_now(), "started_at": None,
               "finished_at": None, "request": body, "snap": snap, "result": None, "error": None}
        if parent:
            job["parent_job_id"] = parent
        st.jobs.put(job)
        if callback is not None:
            callbacks[job_id] = callback
        spec = {"job_id": job_id, "job_dir": str(st.jobs.job_dir(job_id)), "graph_path": str(region.graph_path),
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
                if out.get("timings"):
                    res["provenance"]["timings_s"] = out["timings"]
                if out.get("receipt"):
                    res["provenance"]["receipt"] = out["receipt"]
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
    @app.get("/v1/health")
    async def health():
        reg = st.registry
        issues = list(reg.issues)
        return {"status": "ok" if reg.regions and not issues else "degraded", "api_version": API_VERSION,
                "package": st.identity.package, "package_version": st.identity.package_version, "kit": st.identity.kit,
                "checkpoint": st.identity.checkpoint, "git_commit": st.identity.git_commit, "regions": sorted(reg.regions),
                "workers": st.settings.workers, "data_root": str(st.settings.data_root), "issues": issues,
                "jobs": st.jobs.counts(), "queued_tasks": st.jobs.queued(), "budget_s": C.BUDGET_S,
                "kit_candidate_id": st.identity.kit_candidate_id, "git_dirty": st.identity.git_dirty}

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
    @app.post("/v1/route-checks", status_code=202)
    async def create_route_check(request: Request):
        body = _body(await request.body(), "RouteCheckRequest")
        _require_data()
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
                            headers={"Content-Disposition": 'attachment; filename="%s.kml"' % fname})
        return PlainTextResponse(X.to_csv(j), media_type="text/csv",
                                 headers={"Content-Disposition": 'attachment; filename="%s.csv"' % fname})

    # ---------------------------------------------------------------------------------------------- dispatch
    @app.post("/v1/dispatch-plans", status_code=202)
    async def create_dispatch(request: Request):
        body = _body(await request.body(), "DispatchPlanRequest")
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
        dwell_default = body.get("dwell_s", C.DEFAULT_DWELL_S)
        limits_body = {"limits": body.get("limits") or {}}
        attempts_spec = []
        for o, osnap in origins:
            for d, dsnap in dests:
                for off in body["depart_offsets_s"]:
                    pseudo = {"depart_offset_s": off, "dwell_s": d.get("dwell_s", dwell_default), "destination_window": d.get("window"),
                              **limits_body}
                    rp = _request_params(pseudo, region, sset, {"start": osnap, "destination": dsnap})
                    attempts_spec.append((o, osnap, d, dsnap, off, rp))
        job_id = st.jobs.new_id("dp")
        total = len(attempts_spec)
        job = {"job_id": job_id, "kind": "dispatch_plan", "status": "queued", "created_at": utc_now(), "started_at": None,
               "finished_at": None, "request": body, "progress": {"done": 0, "total": total}, "result": None, "error": None}
        st.jobs.put(job)
        t_start = time.perf_counter()
        lock = threading.Lock()
        records: dict = {}
        dest_order = {d["id"]: i for i, (d, _) in enumerate(dests)}
        origin_order = {o["id"]: i for i, o in enumerate(body["origins"])}

        def finish(error=None):
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
                                    evaluated_configuration=(zone_plan is None and policy == "full" and not body.get("limits")),
                                    approximation=APPROXIMATION_NOTE if zone_plan is not None else None, clock=CLOCK_DEFINITION,
                                    budget_s=C.BUDGET_S, workers=st.settings.workers)
            if zone_plan is not None and shared.get("meta"):
                prov["scenario_ids"] = shared["meta"]["scenario_ids"]
                prov["scenario_set_id"] = shared["meta"]["scenario_ids"][0].rsplit(":", 1)[0]
                prov["input_hashes"].update({"zones/" + k: v for k, v in (shared["meta"].get("input_hashes") or {}).items()})
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
            if total == 0:
                finish()
                return
            for o, osnap, d, dsnap, off, rp in attempts_spec:
                rbody = {"region": body["region"], "input_time": body["input_time"], "start": o["location"],
                         "destination": d["location"], "depart_offset_s": off, "dwell_s": rp["dwell_s"],
                         "destination_window": d.get("window"), "policy": policy, "fire_input": body["fire_input"],
                         "limits": {k: rp["limits"][k] for k in ("peak_kw_m2", "dose_kj_m2")}, "run_independent_check": False}
                if rbody["destination_window"] is None:
                    rbody.pop("destination_window")
                key = (o["id"], d["id"], off)
                _new_route_job(rbody, region, sset, zone_plan, {"start": osnap, "destination": dsnap}, parent=job_id,
                               request_params=rp, prebuilt=prebuilt, callback=lambda rc_id, key=key: attempt_done(rc_id, key))

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
            st.jobs.schedule("zone_packet", {"zone_plan": zone_plan, "graph_path": str(region.graph_path), "out_dir": str(pdir),
                                             "python": st.settings.python}, lambda: None, zp_done, priority=1)
        return JSONResponse({"job_id": job_id, "status": st.jobs.get(job_id)["status"], "kind": "dispatch_plan",
                             "links": {"self": "/v1/dispatch-plans/%s" % job_id}}, status_code=202)

    @app.get("/v1/dispatch-plans/{job_id}")
    async def get_dispatch(job_id: str):
        j = st.jobs.get(job_id)
        if j is None or j.get("kind") != "dispatch_plan":
            raise not_found("JOB_NOT_FOUND", "dispatch plan %r not found" % job_id)
        return j

    return app


app = create_app()
