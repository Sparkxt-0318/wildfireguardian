"""HTTP and WebSocket server. Binds to 127.0.0.1 only. Run: python3 -m app.main [--port 8765] [--dev-device-double]"""
import argparse
import asyncio
import json
import sys
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config, exports, library, replay
from .device.link import LinkLost

ARGS = {"port": config.DEFAULT_PORT, "double": False, "quiet": False}


class Hub:
    """Fan-out of device events to every open page. emit() is safe to call from any thread."""

    def __init__(self):
        self.loop = None
        self.clients = set()
        self.lock = threading.Lock()

    def emit(self, ev):
        if not ARGS["quiet"] and ev.get("type") == "line" and not ev.get("same"):
            arrow = ev.get("dir", " ")
            note = (" " * 3 + ev["note_text"]) if ev.get("note_text") else ""
            print("%s %s %s%s" % (ev.get("time", ""), arrow, ev.get("raw") or ev.get("text", ""), note), flush=True)
        loop = self.loop
        if loop is None:
            return
        data = json.dumps(ev, ensure_ascii=False)
        with self.lock:
            targets = list(self.clients)
        for ws in targets:
            asyncio.run_coroutine_threadsafe(self._send(ws, data), loop)

    async def _send(self, ws, data):
        try:
            await ws.send_text(data)
        except Exception:   # a closed tab must never stop the others
            with self.lock:
                self.clients.discard(ws)


HUB = Hub()
DEV = {"mgr": None}


@asynccontextmanager
async def lifespan(_app):
    HUB.loop = asyncio.get_running_loop()
    from .device.manager import DeviceManager
    DEV["mgr"] = DeviceManager(HUB.emit, double=bool(ARGS["double"]), double_fw=ARGS.get("double_fw", "0.2.0"))
    DEV["mgr"].start()
    yield
    DEV["mgr"].shutdown()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def mgr():
    return DEV["mgr"]


# ----------------------------------------------------------------------------- library and replay
@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__, "double": ARGS["double"]}


@app.get("/api/library")
def get_library():
    return {"entries": library.entries(), "files": library.all_files()}


def _entry(key=None, file=None):
    if key is not None:
        e = library.by_key(int(key))
        if not e:
            raise HTTPException(404, "no library entry %s" % key)
        return e
    if file:
        try:
            library.safe_path(file)
        except ValueError:
            raise HTTPException(400, "bad path")
        return library.entry_for_file(file)
    raise HTTPException(400, "key or file required")


@app.get("/api/session")
def get_session(key: int = None, file: str = None):
    e = _entry(key, file)
    try:
        return JSONResponse(replay.build(e))
    except FileNotFoundError:
        raise HTTPException(404, "file not found: %s" % e["file"])


@app.get("/api/area_for")
def area_for(lat: float, lon: float, sim: int = 0):
    """Map data that covers a point (LIVE: the map is chosen from the first fix; the simulated logger gets the
    synthetic map)."""
    return {"area": replay.detect_area([lon, lat, lon, lat], sim=bool(sim))}


@app.post("/api/library/add")
def add_to_library(body: dict = Body(...)):
    try:
        return library.add(body["file"])
    except (KeyError, ValueError, OSError) as ex:
        raise HTTPException(400, str(ex))


@app.post("/api/export")
async def do_export(body: dict = Body(...)):
    e = _entry(body.get("key"), body.get("file"))
    payload = replay.build(e)
    if not payload["metrics"]:
        raise HTTPException(400, "no analysed movement in this session")
    query = ("key=%d" % e["key"]) if e.get("key") else ("file=" + e["file"])
    base = "http://%s:%d" % (config.HOST, ARGS["port"])
    try:
        return await run_in_threadpool(exports.export, base, query, payload, tuple(body.get("langs", ("ko", "en"))))
    except Exception as ex:   # report the reason to the page instead of a bare 500
        raise HTTPException(500, "export failed: %s" % ex)


# ----------------------------------------------------------------------------- device (section 3C)
@app.get("/api/device/state")
def device_state():
    return mgr().snapshot()


@app.get("/api/device/ports")
def device_ports():
    return {"ports": mgr().ports()}


def _call(fn, *a, **kw):
    """Errors of a device action become 409 with a short code the page turns into a sentence (device.js, _do)."""
    try:
        return fn(*a, **kw)
    except (RuntimeError, ValueError) as ex:
        raise HTTPException(409, str(ex))
    except TimeoutError as ex:
        raise HTTPException(409, "timeout: %s" % ex)
    except LinkLost as ex:
        raise HTTPException(409, "lost: %s" % ex)
    except OSError as ex:
        raise HTTPException(409, "port: %s" % ex)


@app.post("/api/device/connect")
async def device_connect(body: dict = Body(...)):
    return await run_in_threadpool(_call, mgr().connect, body["port"])


@app.post("/api/device/disconnect")
async def device_disconnect():
    return await run_in_threadpool(_call, mgr().disconnect)


@app.post("/api/device/view")
def device_view(body: dict = Body(...)):
    mgr().set_view(bool(body.get("visible")))
    return {"ok": True}


@app.post("/api/device/test/start")
async def test_start():
    return await run_in_threadpool(_call, mgr().test_start)


@app.post("/api/device/test/cancel")
def test_cancel():
    return _call(mgr().test_cancel)


@app.post("/api/device/test/screen")
def test_screen(body: dict = Body(...)):
    return _call(mgr().screen_answer, bool(body.get("seen")))


@app.get("/api/device/sessions")
async def device_sessions():
    return await run_in_threadpool(_call, mgr().device_sessions)


@app.post("/api/device/pull")
async def device_pull(body: dict = Body(...)):
    return await run_in_threadpool(_call, mgr().pull, body["name"], bool(body.get("force")))


@app.post("/api/device/conncheck/{action}")
async def conncheck(action: str, body: dict = Body(default={})):
    m = mgr()
    fn = {"start": m.conncheck_start, "answer": m.conncheck_answer, "cancel": m.conncheck_cancel}.get(action)
    if not fn:
        raise HTTPException(404, "unknown action")
    return await run_in_threadpool(_call, fn, **({"value": body.get("value")} if action == "answer" else {}))


@app.post("/api/device/calibrate")
async def calibrate(body: dict = Body(...)):
    return await run_in_threadpool(_call, mgr().calibrate, body.get("mv"), bool(body.get("reset")))


@app.get("/api/wifi/status")
async def wifi_status():
    return await run_in_threadpool(_call, mgr().wifi_status)


@app.get("/api/wifi/list")
async def wifi_list():
    return await run_in_threadpool(_call, mgr().wifi_list)


@app.post("/api/wifi/pull")
async def wifi_pull(body: dict = Body(...)):
    return await run_in_threadpool(_call, mgr().wifi_pull, body["name"])


@app.post("/api/device/double/{action}")
def double_action(action: str, body: dict = Body(default={})):
    return _call(mgr().double_action, action, body)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    with HUB.lock:
        HUB.clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "snapshot", "state": mgr().snapshot()}, ensure_ascii=False))
        while True:
            await ws.receive_text()   # the page sends nothing; this keeps the socket open
    except WebSocketDisconnect:
        pass
    finally:
        with HUB.lock:
            HUB.clients.discard(ws)


app.mount("/mapdata", StaticFiles(directory=str(config.MAPDATA)), name="mapdata")
app.mount("/", StaticFiles(directory=str(config.WEB), html=True), name="web")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Field route logger booth demo server (127.0.0.1 only)")
    ap.add_argument("--port", type=int, default=config.DEFAULT_PORT)
    ap.add_argument("--dev-device-double", action="store_true",
                    help="development only: a simulated logger (firmware 0.2.0 behaviour), watermarked as simulated")
    ap.add_argument("--dev-double-live", action="store_true",
                    help="development only: the simulated logger behaves like firmware 0.3.0 (LIVE lines)")
    ap.add_argument("--quiet", action="store_true", help="do not print the device stream to this terminal")
    a = ap.parse_args(argv)
    double = a.dev_device_double or a.dev_double_live
    ARGS.update({"port": a.port, "double": double, "double_fw": "0.3.0" if a.dev_double_live else "0.2.0",
                 "quiet": a.quiet})
    print("Field route logger demo %s on http://%s:%d/%s" % (__version__, config.HOST, a.port,
                                                              "  (SIMULATED DEVICE enabled)" if double else ""),
          flush=True)
    uvicorn.run(app, host=config.HOST, port=a.port, log_level="warning")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
