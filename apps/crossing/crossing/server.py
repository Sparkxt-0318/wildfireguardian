"""FastAPI server of the crossing app on 127.0.0.1:8781 (DESIGN.md section 9).

Routes:
    GET  /                    the web app (static files in apps/crossing/web/, written by the UI engineer)
    WS   /ws                  pushes the State JSON (schema: apps/crossing/README.md, STATE_SCHEMA) right after each
                              pipeline tick (tick_hz, 5 Hz; at least every 1/ws_hz s)
    GET  /api/state           the latest State (verdict re-checked for expiry at request time)
    GET  /api/health          server alive + link and sensor health
    GET  /api/vehicles        vehicle profiles (PLACEHOLDER limits) and the selected one
    GET  /api/fuels           fuel catalogue (FBFM40 + C064_GRASS + DEFAULT + custom) and the selected one
    POST /api/vehicle         {"name": "fire_engine"} or {"name": "custom", "custom": {<vehicles.yaml fields>}}
    POST /api/fuel            {"code": "GR1"} or {"custom": {"code", "residence_s", "consumed_load_kg_m2",
                              "heat_kj_kg", "residence_rel_sigma"?}}
    POST /api/baseline        {"action": "capture" | "clear", "force": false}
    POST /api/mark_crossing   {"measured_m": null | metres, "lookback_s": 60}
    GET  /api/replay          replay mode only: {"mode": "replay", "paused", "speed", "t", "t_end", "t_fed", "ended",
                              "loop", "pass", "source", "sim"}; 404 {"mode": "live" | "idle"} otherwise
    POST /api/replay          replay mode only: {"action": "play" | "pause"} or {"action": "speed", "speed": x}
                              (0.1 <= x <= 20); returns the status above

Replay pause fails closed: pausing stops feeding recorded messages AND marks the link down ("replay paused"), so the
next tick (done at once by the handler) decides CLOSED / LINK_DOWN exactly as for a lost roof unit. A paused replay
never shows a verdict from data that is no longer arriving. Resuming restores the recorded link state; sensors
then need fresh readings again before anything but CLOSED can be decided.

Everything runs on one asyncio event loop: the link client (or the replay task) feeds the pipeline, a ticker calls
``Pipeline.tick`` at tick_hz, API handlers call pipeline methods directly. Nothing is exposed beyond the loopback
interface by default. The server never makes a decision itself; it only shows the pipeline's verdict, which
expires to CLOSED 5 s after issue even if the ticker stalls (``Pipeline.snapshot``).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, _repo
from . import decision as dc
from . import fuels as fu
from .pipeline import Pipeline, apply_item, is_research_log, iter_source, state_json
from .vehicles import PLACEHOLDER_NOTE, from_mapping, load_vehicles

log = logging.getLogger("crossing.server")

WEB_DIR = _repo.APP / "web"
PLACEHOLDER_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Crossing</title>
<meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="font-family:sans-serif">
<h1>WildfireGuardian crossing app</h1><p><b>Advisory only: verdicts are for trained crews.</b> Every limit is a
PLACEHOLDER for the fire service to set. Not verified on hardware. The web UI is not installed
(apps/crossing/web/index.html is missing). The State is at <a href="/api/state">/api/state</a> and on the
WebSocket <code>/ws</code>.</p></body></html>"""


REPLAY_SPEED_MIN = 0.1
REPLAY_SPEED_MAX = 20.0


class ReplayPlayer:
    """Real-time replay of a recorded session into the pipeline, with play / pause / speed control.

    Same timing as ``pipeline.play`` (receipt time = this laptop's clock at feed time, recorded spacing divided by
    ``speed``), plus a replay clock ``t`` (seconds of recorded time since the start of the session) that can be
    paused and re-anchored when the speed changes. Control methods must be called on the event loop.

    Fail closed: ``pause()`` stops feeding and marks the pipeline link down with reason "replay paused", so the
    pipeline (which decides from fresh data only, laptop clock) gives CLOSED at its next tick, and in any case the
    last verdict expires 5 s after issue. A paused replay is "no fresh data", never a frozen verdict.
    ``play()`` restores the link state last recorded in the session (a research-log replay can contain link-down
    markers) and continues from the paused point; after the session has ended (no ``loop``) it starts over.
    """

    def __init__(self, pipeline: Pipeline, path: Any, speed: float = 1.0, loop: bool = False,
                 clock: Callable[[], float] = time.monotonic):
        if not (isinstance(speed, (int, float)) and math.isfinite(speed) and speed > 0):
            raise ValueError("speed must be > 0")
        self.pipeline = pipeline
        self.path = path
        self.speed = float(speed)
        self.loop = bool(loop)
        self.clock = clock
        self.paused = False
        self.ended = False
        self.pass_no = 0
        self.t_fed: Optional[float] = None          # recorded time of the last item fed
        self.t_end: Optional[float] = None          # recorded session length when known
        self._anchor_t = 0.0                        # replay time at _anchor_mono
        self._anchor_mono = clock()
        self._paused_t = 0.0
        self._link_up = True                        # link state as recorded in the session
        self._link_reason = ""
        self._changed: Optional[asyncio.Event] = None

    # -------------------------------------------------------------------------------- clock
    def t(self, now: Optional[float] = None) -> float:
        """Replay clock (recorded seconds since session start); frozen while paused."""
        if self.paused:
            return self._paused_t
        now = self.clock() if now is None else now
        t = self._anchor_t + max(0.0, now - self._anchor_mono) * self.speed
        return min(t, self.t_end) if self.t_end is not None else t

    def _due(self, t_rel: float) -> float:
        return self._anchor_mono + (t_rel - self._anchor_t) / self.speed

    def _reanchor(self, t: float, now: float) -> None:
        self._anchor_t = t
        self._anchor_mono = now

    def _notify(self) -> None:
        if self._changed is not None:
            self._changed.set()

    # -------------------------------------------------------------------------------- control
    def status(self) -> dict:
        now = self.clock()
        return {"mode": "replay", "paused": self.paused, "speed": self.speed, "t": round(self.t(now), 3),
                "t_end": round(self.t_end, 3) if self.t_end is not None else None,
                "t_fed": round(self.t_fed, 3) if self.t_fed is not None else None, "ended": self.ended,
                "loop": self.loop, "pass": self.pass_no, "source": str(self.path), "sim": bool(self.pipeline.sim),
                "fail_closed": "paused = no fresh data: link marked down, verdict CLOSED"}

    def pause(self) -> None:
        if self.paused:
            return
        now = self.clock()
        self._paused_t = self.t(now)
        self.paused = True
        self.pipeline.set_connected(False, now, "replay paused")
        self._notify()

    def play(self) -> None:
        if not self.paused:
            return
        now = self.clock()
        self.paused = False
        if self.ended:                              # the run loop starts a new pass (and its own link-up item)
            self.ended = False
            self.t_fed = None
            self._reanchor(0.0, now)
            return self._notify()
        self._reanchor(self._paused_t, now)
        if self._link_up:
            self.pipeline.set_connected(True, now, "replay resumed")
        else:
            self.pipeline.set_connected(False, now, self._link_reason or "link down (recorded)")
        self._notify()

    def set_speed(self, speed: Any) -> None:
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) \
                or not REPLAY_SPEED_MIN <= speed <= REPLAY_SPEED_MAX:
            raise ValueError("speed must be a number in [%g, %g]" % (REPLAY_SPEED_MIN, REPLAY_SPEED_MAX))
        now = self.clock()
        if not self.paused:
            self._reanchor(self.t(now), now)
        self.speed = float(speed)
        self._notify()

    # -------------------------------------------------------------------------------- run
    async def _wait(self, stop: asyncio.Event, timeout: Optional[float]) -> None:
        waiters = [asyncio.ensure_future(stop.wait()), asyncio.ensure_future(self._changed.wait())]
        try:
            await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for w in waiters:
                w.cancel()

    def _known_length(self) -> Optional[float]:
        if is_research_log(self.path):
            return None                             # known after the first pass
        from wfgvu import replay
        try:
            return float(replay.load(self.path).duration)
        except Exception:  # noqa: BLE001 - the length is only shown, never used to decide
            return None

    async def run(self, stop: asyncio.Event) -> None:
        self._changed = asyncio.Event()
        if self.t_end is None:
            self.t_end = await asyncio.to_thread(self._known_length)
        while not stop.is_set():
            self.pass_no += 1
            self.ended = False
            self.t_fed = None
            self._reanchor(0.0, self.clock())
            if self.paused:
                self._paused_t = 0.0
            n = 0
            for t_rel, kind, payload in iter_source(self.path):
                if n % 200 == 0:
                    await asyncio.sleep(0)          # let the ticker and the API run when behind schedule
                while True:                         # no await between the last pause check and the feed
                    if stop.is_set():
                        return
                    self._changed.clear()
                    if self.paused:
                        await self._wait(stop, None)
                        continue
                    delay = self._due(t_rel) - self.clock()
                    if delay <= 0:
                        break
                    await self._wait(stop, delay)
                now = self.clock()
                if kind == "link":
                    self._link_up, self._link_reason = bool(payload[0]), str(payload[1] or "")
                apply_item(self.pipeline, kind, payload, now)
                self.t_fed = t_rel
                n += 1
            if self.t_fed is not None and (self.t_end is None or self.t_fed > self.t_end):
                self.t_end = self.t_fed
            if self.loop:
                await asyncio.sleep(0.5)
                continue
            self.ended = True
            self._paused_t = self.t_end or (self.t_fed or 0.0)
            self.paused = True
            self.pipeline.set_connected(False, self.clock(), "replay ended")
            while self.paused and not stop.is_set():  # play() starts the session over
                self._changed.clear()
                await self._wait(stop, None)


class Runtime:
    """Owns the pipeline and its background tasks (link or replay, ticker, optional sim-link client)."""

    def __init__(self, pipeline: Pipeline, *, pi_url: Optional[str] = None, replay_dir: Optional[str] = None,
                 speed: float = 1.0, loop: bool = False, simlink_client: Any = None,
                 clock: Callable[[], float] = time.monotonic):
        self.pipeline = pipeline
        self.cfg = pipeline.cfg
        self.pi_url = pi_url
        self.replay_dir = replay_dir
        self.speed = speed
        self.loop = loop
        self.simlink_client = simlink_client
        self.clock = clock
        self.link_client = None
        self.stop_event: Optional[asyncio.Event] = None
        self.tasks: List[asyncio.Task] = []
        self.started = False
        self._json_cache = (None, "")
        self.vehicles = load_vehicles()
        self.custom_vehicle = None
        self._ticked: Optional[asyncio.Event] = None     # set after every tick; /ws pushes right after it
        self.replay: Optional[ReplayPlayer] = (ReplayPlayer(pipeline, replay_dir, speed, loop, clock=clock)
                                               if replay_dir else None)

    @property
    def mode(self) -> str:
        return "replay" if self.replay_dir else ("live" if self.pi_url else "idle")

    async def start(self) -> None:
        if self.started:
            return
        self.started = True
        self.stop_event = asyncio.Event()
        self.tasks.append(asyncio.ensure_future(self._ticker()))
        if self.pi_url:
            from .link import LinkClient
            self.link_client = LinkClient(self.pi_url, self.pipeline, self.cfg.link, clock=self.clock)
            self.tasks.append(asyncio.ensure_future(self.link_client.run(self.stop_event)))
        elif self.replay is not None:
            self.tasks.append(asyncio.ensure_future(self.replay.run(self.stop_event)))
        if self.simlink_client is not None:
            self.tasks.append(asyncio.ensure_future(self.simlink_client.run(self.stop_event)))

    async def stop(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()
        for t in self.tasks:
            t.cancel()
        for t in self.tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        self.tasks = []
        self.started = False
        if self.pipeline.rlog is not None:
            self.pipeline.rlog.close()

    async def _ticker(self) -> None:
        period = 1.0 / self.cfg.tick_hz
        nxt = self.clock()
        while not self.stop_event.is_set():
            self.pipeline.tick(self.clock())
            ev, self._ticked = self._ticked, asyncio.Event()
            if ev is not None:
                ev.set()
            nxt += period
            delay = nxt - self.clock()
            if delay < 0:
                nxt = self.clock()
                delay = 0.0
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    def tick_now(self) -> None:
        """Re-decide at once (after a replay pause, so the State does not keep a go verdict until the next tick)."""
        self.pipeline.tick(self.clock())
        ev, self._ticked = self._ticked, asyncio.Event()
        if ev is not None:
            ev.set()

    async def wait_tick(self, timeout: float) -> None:
        """Return right after the next pipeline tick, or after ``timeout`` s (no ticker running)."""
        if self._ticked is None:
            self._ticked = asyncio.Event()
        try:
            await asyncio.wait_for(self._ticked.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    def snapshot(self) -> dict:
        return self.pipeline.snapshot(self.clock())

    def snapshot_json(self) -> str:
        now = self.clock()
        key = (self.pipeline.state_version, round(now, 1))
        if self._json_cache[0] != key:
            self._json_cache = (key, state_json(self.pipeline.snapshot(now)))
        return self._json_cache[1]

    def vehicle_list(self) -> dict:
        vs = dict(self.vehicles)
        if self.custom_vehicle is not None:
            vs["custom"] = self.custom_vehicle
        return {"selected": self.pipeline.vehicle.name, "placeholder_note": PLACEHOLDER_NOTE,
                "vehicles": {k: v.to_dict() for k, v in vs.items()}}


def create_app(runtime: Runtime, start_tasks: bool = True, web_dir: Optional[Path] = None) -> FastAPI:
    web = Path(web_dir) if web_dir is not None else WEB_DIR

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_tasks:
            await runtime.start()
        try:
            yield
        finally:
            if start_tasks:
                await runtime.stop()

    app = FastAPI(title="WildfireGuardian crossing app", version=__version__, lifespan=lifespan)
    app.state.runtime = runtime
    pipe = runtime.pipeline

    @app.get("/api/health")
    def health() -> dict:
        now = runtime.clock()
        v = dc.effective(pipe.verdict, now)
        return {"ok": True, "app_version": __version__, "mode": runtime.mode,
                "source": runtime.pi_url or runtime.replay_dir or "", "sim": pipe.sim,
                "verdict_state": v.state, "advisory": True, "link": pipe.link.info(),
                "link_client": runtime.link_client.info() if runtime.link_client is not None else None,
                "health": pipe.link.health(now).to_dict(), "pipeline_errors": pipe.errors,
                "simlink": runtime.simlink_client.status() if runtime.simlink_client is not None
                else {"enabled": False}}

    @app.get("/api/state")
    def state() -> Response:
        return Response(content=runtime.snapshot_json(), media_type="application/json")

    @app.get("/api/vehicles")
    def vehicles() -> dict:
        return runtime.vehicle_list()

    @app.get("/api/fuels")
    def fuels() -> dict:
        return {"selected": pipe.fuel.code,
                "fuels": [dict(f.to_dict(), code=code) for code, f in sorted(fu.all_fuels().items())]}

    @app.post("/api/vehicle")
    def set_vehicle(body: dict = Body(default={})) -> dict:
        name = body.get("name")
        try:
            if name == "custom" and isinstance(body.get("custom"), dict):
                spec = dict(runtime.vehicles.get("custom").to_dict() if "custom" in runtime.vehicles else {})
                spec.update(body["custom"])
                spec["placeholder"] = True
                spec.pop("name", None)
                spec.pop("placeholder_note", None)
                v = from_mapping("custom", spec)
                runtime.custom_vehicle = v
            elif isinstance(name, str) and name in runtime.vehicles:
                v = runtime.vehicles[name]
            elif name == "custom" and runtime.custom_vehicle is not None:
                v = runtime.custom_vehicle
            else:
                raise HTTPException(400, "unknown vehicle %r" % (name,))
            pipe.set_vehicle(v, runtime.clock())
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "vehicle": v.to_dict()}

    @app.post("/api/fuel")
    def set_fuel(body: dict = Body(default={})) -> dict:
        try:
            if isinstance(body.get("custom"), dict):
                c = dict(body["custom"])
                code = str(c.pop("code", "")).strip()
                allowed = {"residence_s", "consumed_load_kg_m2", "heat_kj_kg", "residence_rel_sigma", "name"}
                if set(c) - allowed:
                    raise ValueError("unknown custom fuel fields: %s" % ", ".join(sorted(set(c) - allowed)))
                f = fu.custom_fuel(code, **c)           # registers (or replaces) a custom code
            else:
                f = fu.get_fuel(body.get("code"))
            pipe.set_fuel(f, runtime.clock())
        except (KeyError, ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc))
        return {"ok": True, "fuel": f.to_dict(), "calibration": pipe.calib.to_dict()}

    @app.post("/api/baseline")
    def baseline(body: dict = Body(default={})) -> dict:
        action = body.get("action", "capture")
        now = runtime.clock()
        if action == "capture":
            return pipe.capture_baseline(now, force=bool(body.get("force", False)))
        if action == "clear":
            pipe.clear_baseline(now, "cleared by operator")
            return {"ok": True, "reason": "cleared"}
        raise HTTPException(400, "action must be capture or clear")

    @app.post("/api/mark_crossing")
    def mark_crossing(body: dict = Body(default={})) -> dict:
        m = body.get("measured_m")
        lookback = body.get("lookback_s", 60.0)
        if m is not None and (isinstance(m, bool) or not isinstance(m, (int, float))):
            raise HTTPException(400, "measured_m must be a number or null")
        if isinstance(lookback, bool) or not isinstance(lookback, (int, float)) or not 5 <= lookback <= 600:
            raise HTTPException(400, "lookback_s must be a number in [5, 600]")
        return pipe.mark_crossing(runtime.clock(), measured_m=m, lookback_s=float(lookback))

    def _no_replay() -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "no replay: the app runs in %s mode" % runtime.mode,
                                                      "mode": runtime.mode})

    # async handlers: they run on the event loop with the replay task and the ticker (asyncio.Event is not
    # thread-safe, so these must not run in the threadpool)
    @app.get("/api/replay")
    async def replay_status() -> Any:
        if runtime.replay is None:
            return _no_replay()
        return runtime.replay.status()

    @app.post("/api/replay")
    async def replay_control(body: Any = Body(default={})) -> Any:
        rp = runtime.replay
        if rp is None:
            return _no_replay()
        if not isinstance(body, dict):
            raise HTTPException(400, "body must be a JSON object")
        action = body.get("action")
        if action == "pause":
            rp.pause()
            runtime.tick_now()                  # CLOSED (LINK_DOWN: replay paused) at once, not at the next tick
        elif action == "play":
            rp.play()
        elif action == "speed":
            try:
                rp.set_speed(body.get("speed"))
            except ValueError as exc:
                raise HTTPException(400, str(exc))
        else:
            raise HTTPException(400, "action must be play, pause or speed")
        return rp.status()

    @app.websocket("/ws")
    async def ws_state(ws: WebSocket) -> None:
        await ws.accept()
        period = 1.0 / max(runtime.cfg.server.ws_hz, 0.5)
        try:
            while True:
                await ws.send_text(runtime.snapshot_json())
                # push right after each pipeline tick (no extra up-to-one-period delay before a new verdict reaches
                # the UI); at most every `period` when the ticker is not running
                await runtime.wait_tick(period)
        except (WebSocketDisconnect, RuntimeError):
            return

    if (web / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(web), html=True), name="web")
    else:
        @app.get("/")
        def index() -> HTMLResponse:
            return HTMLResponse(PLACEHOLDER_HTML)

    return app
