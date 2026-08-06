"""The transport. Four endpoints over the PHASE-19 job model, and nothing else.

Round-3 PHASE 22 STEP 0.

WHAT THIS LAYER IS ALLOWED TO DO
--------------------------------
Parse a request, call a service function, serialise what comes back, choose a
status code. That is the whole list. No routing decision, no parameter default,
no Korean wording that a sheet or a screen also carries — every one of those
already has exactly one home in :mod:`wildfireguardian.service`, and a second
copy here is a second thing to keep in step.

The shape is not an accident: PHASE 19 built ``submit -> status -> result ->
cancel`` deliberately so that a transport would be thin when it arrived, and
this file is the evidence that it was worth doing. It is mostly argument
marshalling.

WHY THE SCAN CANNOT BE SYNCHRONOUS
----------------------------------
A scan takes about eleven seconds warm (PHASE 20; before that, twenty-seven).
Holding a connection open for that long puts the answer at the mercy of every
read timeout between the browser and the process, and gives the operator a
frozen page in the meantime. So ``POST /api/jobs`` returns a job id in
milliseconds and the screen polls ``GET /api/jobs/{id}`` for the six-stage
progress the service already produces.

⚠ ONE WORKER, ON PURPOSE
``build_runner(max_workers=1)``. Threads do not make two scans faster — the
routing is pure-Python Dijkstra and the GIL serialises it, measured at roughly
double the single-job time each. A second worker only makes the second request
*start* sooner, at the cost of both finishing later. For a demonstration where
one person clicks one coordinate, one worker is the honest configuration; the
queue is what absorbs a double-click.

⚠ EVERY RESPONSE IS SCANNED FOR EXTERNAL URLS
:mod:`.guard`. The screen this serves must work with the network unplugged, and
a payload is the one place a fetchable URL can appear without any static check
noticing.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..service import (
    IgnitionRequest, JobRunner, QueueFull, RoutingParams, ServiceError,
    build_runner, known_regions, region_catalogue, region_gate,
)
from ..service import jobs as _jobs
from .guard import ExternalReferenceError, assert_offline

REPO = Path(__file__).resolve().parents[3]
WEB_ROOT = REPO / "web"

#: Regions warmed at start-up. All of them: PHASE 19 measured the three
#: resident together at 462-489 MiB peak RSS, and a judge who asks for a region
#: that was not preloaded should not be the one who pays the load.
PRELOAD_REGIONS: tuple[str, ...] = tuple(known_regions())


class IgnitionBody(BaseModel):
    """One reported ignition point.

    Only the fields a caller may legitimately choose. Everything that decides a
    NUMBER — p_cut, the budget, the stride, the slope sampling — is taken from
    ``config/default.yaml`` through ``RoutingParams.from_config`` and is
    deliberately NOT settable over HTTP: a dispatch list produced with a stride
    somebody typed into a URL is not comparable with anything this project has
    published.
    """

    region: str = Field(..., description="registered region id")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    reported_by: str = Field("수동 입력", max_length=120)
    make_pdf: bool = Field(
        False, description="A4 PDF conversion. Runs AFTER the dispatch list "
                           "exists and costs ~2.7 s per sheet, so it is off by "
                           "default and excluded from every quoted timing.")


def _payload(obj: Any, *, where: str, status: int = 200) -> JSONResponse:
    """Serialise, then prove the result fetches nothing."""
    assert_offline(obj, where=where)
    return JSONResponse(obj, status_code=status)


def create_app(*, runner: JobRunner | None = None,
               preload: tuple[str, ...] | None = None) -> FastAPI:
    """Build the app. ``runner`` is injectable so tests need no real preload."""
    state: dict[str, Any] = {"runner": runner, "started": None,
                             "preloaded": [], "owns_runner": runner is None}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        t0 = time.monotonic()
        if state["runner"] is None:
            regions = list(PRELOAD_REGIONS if preload is None else preload)
            # The whole point of the cache: pay the load once, at start-up,
            # where nobody is waiting, instead of on the first operator's
            # request. PHASE 19 measured ~1.4-2.7 s per region.
            state["runner"] = build_runner(regions=regions,
                                           capacity=max(1, len(regions)),
                                           max_workers=1)
            state["preloaded"] = regions
        state["started"] = time.monotonic() - t0
        try:
            yield
        finally:
            if state["owns_runner"] and state["runner"] is not None:
                state["runner"].shutdown(wait=False)

    app = FastAPI(title="WildfireGuardian API", version="22.0",
                  docs_url=None, redoc_url=None,   # no CDN-backed doc pages
                  lifespan=lifespan)

    def R() -> JobRunner:
        r = state["runner"]
        if r is None:                                    # pragma: no cover
            raise HTTPException(503, "service not started")
        return r

    # -- read-only ---------------------------------------------------------
    @app.get("/api/health")
    def health() -> JSONResponse:
        r = R()
        return _payload({
            "ok": True,
            "startup_seconds": round(state["started"] or 0.0, 3),
            "preloaded_regions": state["preloaded"],
            "runner": r.stats(),
        }, where="GET /api/health")

    @app.get("/api/regions")
    def regions() -> JSONResponse:
        return _payload({"regions": region_catalogue()}, where="GET /api/regions")

    @app.get("/api/regions/{region}/locate")
    def locate(region: str, x: float, y: float) -> JSONResponse:
        """EPSG:5179 metres in, WGS84 degrees and the gate verdict out.

        ⚠ THE GEODESY LIVES HERE, NOT IN THE PAGE. The console knows how to turn
        a click into its own viewBox coordinates and then into projected metres,
        because that is arithmetic on numbers it was handed at build time. Going
        from metres to degrees is a projection, and doing it in JavaScript would
        mean vendoring a projection library and trusting it to agree with the
        pyproj transformer every committed coordinate was produced by. One
        transformer, server-side, is the only way those cannot diverge.

        Returns the gate verdict in the same payload, so a click costs one round
        trip rather than two.
        """
        try:
            from pyproj import Transformer
            to4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326",
                                          always_xy=True)
            lon, lat = to4326.transform(float(x), float(y))
            verdict = region_gate(region, lat, lon)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(404, f"unknown region: {region}") from exc
        return _payload({
            "x_5179": float(x), "y_5179": float(y),
            "lon": lon, "lat": lat,
            **verdict,
            "hazard_field_note_ko": (
                f"위험면은 {region}의 사전 계산 결과이며 클릭 좌표로 "
                "재생성되지 않습니다."),
        }, where="GET /api/regions/{region}/locate")

    @app.get("/api/regions/{region}/gate")
    def gate(region: str, lat: float, lon: float) -> JSONResponse:
        try:
            verdict = region_gate(region, lat, lon)
        except Exception as exc:                          # unregistered region
            raise HTTPException(404, str(exc)) from exc
        # A refusal is a 200 carrying a verdict, not a 4xx: the caller asked a
        # question and got an answer. 4xx is for a request that was malformed.
        return _payload(verdict, where="GET /api/regions/{region}/gate")

    # -- the job model -----------------------------------------------------
    @app.post("/api/jobs")
    def submit(body: IgnitionBody) -> JSONResponse:
        verdict = None
        try:
            verdict = region_gate(body.region, body.lat, body.lon)
        except Exception as exc:
            raise HTTPException(404, f"unknown region: {body.region}") from exc
        if not verdict["inside_registered_region"]:
            # 422, and the Korean sentence the service already owns. The screen
            # shows it verbatim; this layer does not compose operator wording.
            raise HTTPException(422, verdict["reason_ko"])

        req = IgnitionRequest(
            region=body.region, lat=body.lat, lon=body.lon,
            reported_by=body.reported_by,
            params=RoutingParams.from_config(),
            make_pdf=body.make_pdf)
        try:
            job_id = R().submit_ignition(req)
        except QueueFull as exc:
            raise HTTPException(429, str(exc)) from exc
        return _payload({"job_id": job_id, **R().status(job_id)},
                        where="POST /api/jobs", status=202)

    @app.get("/api/jobs/{job_id}")
    def status(job_id: str) -> JSONResponse:
        try:
            return _payload(R().status(job_id), where="GET /api/jobs/{id}")
        except KeyError as exc:
            raise HTTPException(404, f"unknown job_id: {job_id}") from exc

    @app.get("/api/jobs/{job_id}/result")
    def result(job_id: str) -> JSONResponse:
        try:
            st = R().status(job_id)
        except KeyError as exc:
            raise HTTPException(404, f"unknown job_id: {job_id}") from exc
        if st["state"] != _jobs.SUCCEEDED:
            # 409, not 404: the job exists and the caller asked too early, or
            # it failed. Saying which is the difference between "poll again"
            # and "stop polling".
            raise HTTPException(409, {"state": st["state"],
                                      "state_ko": st["state_ko"],
                                      "error": st.get("error")})
        try:
            return _payload(R().result(job_id), where="GET /api/jobs/{id}/result")
        except ServiceError as exc:                       # pragma: no cover
            raise HTTPException(409, str(exc)) from exc

    @app.delete("/api/jobs/{job_id}")
    def cancel(job_id: str) -> JSONResponse:
        try:
            accepted = R().cancel(job_id)
        except KeyError as exc:
            raise HTTPException(404, f"unknown job_id: {job_id}") from exc
        return _payload({"job_id": job_id, "cancel_accepted": accepted,
                         **R().status(job_id)}, where="DELETE /api/jobs/{id}")

    # -- failures -----------------------------------------------------------
    @app.exception_handler(ExternalReferenceError)
    async def _external_ref(_request: Request, exc: ExternalReferenceError):
        # 500, loudly. A payload carrying a fetchable URL is this project's
        # bug, not the caller's, and a screen that silently rendered it would
        # be the failure the offline design exists to prevent.
        return JSONResponse({"error": "external_reference_in_response",
                             "detail": str(exc), "urls": exc.urls}, status_code=500)

    # -- static ------------------------------------------------------------
    # Mounted LAST so it cannot shadow /api. Serves the vendored fonts, which is
    # the whole reason the screen needs no network.
    if WEB_ROOT.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="web")
    return app


__all__ = ["IgnitionBody", "PRELOAD_REGIONS", "create_app"]
