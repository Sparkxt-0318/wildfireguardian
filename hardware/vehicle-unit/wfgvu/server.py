"""asyncio WebSocket server of the roof unit: one socket, ``ws://0.0.0.0:8770/stream``, broadcast to all clients.

Flow: drivers (threads) call ``UnitServer.emit(msg)``. ``emit`` serialises once, hands the exact text to the
recorder (which records every message, every thermal frame included), applies the thermal wire decimation
(``thermal_wire_hz``, default 4 Hz) and schedules the broadcast on the event loop with ``call_soon_threadsafe``.
Nothing in this path waits on a client, so a slow or stuck laptop never blocks a driver.

Per client: a bounded queue (``client_queue_max``). When it is full the OLDEST message is dropped (fresh data is
worth more than old data) and counted; once a second the server sends that client an ``event`` ``kind="dropped"``
with the counts, and records it. A client first receives ``hello`` (sensors, version, config_digest,
thermal_wire_hz, and ``mount``: the camera/radar mount of this unit, see ``__main__.hello_mount``), then the live
broadcast.

The server also emits ``heartbeat`` messages for the pseudo-sensor ``"unit"`` every ``heartbeat_s`` (detail
lists the client count), and ``event`` messages for client connect/disconnect and recorder events.
Only the path ``/stream`` is served; other paths are closed with code 1008.

Shutdown (``stop``; SIGTERM/SIGINT or ``--duration`` in ``__main__``) is bounded by ``stop_timeout_s`` (default
1.8 s) even with clients connected, including a client that has stopped reading. Root cause of the old hang: a
client that does not read fills its TCP window, so ``ws.send`` (and websockets' own ``close()``) wait forever in
the transport's flow-control ``drain()``, which websockets' ``close_timeout`` does not cover, and
``transport.close()`` waits for that unsent buffer too. ``stop`` therefore: stops the drivers in parallel (each
joins its threads with ``driver_join_s``, run on daemon threads so a stuck device cannot hold the process); closes
the client queues so readers get the final heartbeats and then a close frame with code 1001 "unit stopping"; after
``client_grace_s`` cancels any per-client sender task still running and ABORTS its transport (no flush); closes the
listening socket with a bounded wait; then flushes and closes the recorder with its own budget
(``recorder_close_s``, default 5 s, or the time left if that is longer): the clients are gone by then, and a recorder
backlog on a slow card should reach the disk (systemd allows ``TimeoutStopSec=15``). A recorder that still cannot
finish writes ``closed_cleanly: false`` into session.json.

The ``unit`` heartbeat is ``status: "error"`` (detail "recorder dead" / "recording paused" / "record error") when a
recorder is attached and its writer thread is dead or failed, recording is paused, or a write error happened in the
last 10 s (``Recorder.health``).
"""
from __future__ import annotations

import asyncio
import collections
import logging
import threading
import time
from typing import Any, Callable, Deque, Dict, List, Optional

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State

from . import __version__, protocol

log = logging.getLogger("wfgvu.server")


class ClientQueue:
    """Bounded FIFO of wire texts for one client; ``put`` drops the oldest when full. Event-loop thread only."""

    def __init__(self, maxsize: int = 400, name: str = "client"):
        self.maxsize = max(1, int(maxsize))
        self.name = name
        self.q: Deque[str] = collections.deque()
        self.dropped = 0
        self.dropped_reported = 0
        self.sent = 0
        self.closed = False
        self._ready = asyncio.Event()

    def close(self) -> None:
        """Server shutdown: ``get`` returns None once the queued messages are drained, so the handler ends."""
        self.closed = True
        self._ready.set()

    def put(self, text: str) -> None:
        if self.closed:
            return
        if len(self.q) >= self.maxsize:
            self.q.popleft()
            self.dropped += 1
        self.q.append(text)
        self._ready.set()

    async def get(self) -> Optional[str]:
        while not self.q:
            if self.closed:
                return None
            self._ready.clear()
            await self._ready.wait()
        return self.q.popleft()

    def __len__(self) -> int:
        return len(self.q)


class UnitServer:
    """Owns the clients, the broadcast and the unit heartbeat; drivers are added with ``add_driver``."""

    def __init__(self, ctx: protocol.Context, cfg: Optional[dict] = None, recorder=None, *, host: str = "0.0.0.0",
                 port: int = 8770, path: str = "/stream", thermal_wire_hz: Optional[float] = 4.0,
                 client_queue_max: int = 400, heartbeat_s: float = 0.5, session=None, speed: float = 1.0,
                 loop_replay: bool = False, stop_timeout_s: float = 1.8, driver_join_s: float = 0.4,
                 client_grace_s: float = 0.25, mount: Optional[dict] = None, recorder_close_s: float = 5.0):
        self.ctx = ctx
        self.cfg = cfg or {}
        self.recorder = recorder
        self.host, self.port, self.path = host, int(port), path
        self.thermal_wire_hz = thermal_wire_hz
        self.client_queue_max = client_queue_max
        self.heartbeat_s = heartbeat_s
        self.session = session
        self.speed, self.loop_replay = speed, loop_replay
        self.drivers: List[Any] = []
        self.clients: Dict[int, ClientQueue] = {}
        self._conns: Dict[int, tuple] = {}                   # id(client) -> (ws, ClientQueue, sender task)
        self.stop_timeout_s = float(stop_timeout_s)
        self.driver_join_s = float(driver_join_s)
        self.client_grace_s = float(client_grace_s)
        self.recorder_close_s = float(recorder_close_s)
        self.last_stop_s: Optional[float] = None
        self.mount = mount                                   # sent in hello (camera pitch etc.); None = not sent
        self.digest = protocol.config_digest(self.cfg)
        self.emitted = 0
        self.emit_errors = 0
        self.thermal_decimated = 0
        self._thermal_next: Optional[float] = None
        self._tlock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws = None
        self._tasks: List[asyncio.Task] = []
        self._hb_seq = 0

    # ------------------------------------------------------------------ emit path (any thread)
    def add_driver(self, driver) -> None:
        self.drivers.append(driver)

    def emit(self, msg: dict) -> None:
        """Record and broadcast one protocol message. Safe from any thread; never blocks on clients."""
        try:
            text = protocol.dumps(msg)
        except protocol.ProtocolError:
            self.emit_errors += 1
            return
        self.emitted += 1
        if self.recorder is not None:
            self.recorder.write(msg, text)
        if msg.get("type") == "reading" and msg.get("sensor") == "thermal" and self.thermal_wire_hz:
            # Schedule-based decimation: a frame goes out when it is at most 20 % of a period early for the next
            # slot, and the slot advances by exactly one period, so the long-run wire rate is thermal_wire_hz even
            # with timestamp jitter. (A plain "dt >= period" rule dropped about 30 % of jittered 4 Hz frames.)
            t = float(msg["t_mono"])
            period = 1.0 / float(self.thermal_wire_hz)
            with self._tlock:
                nxt = self._thermal_next
                if nxt is not None and t < nxt - 0.2 * period:
                    self.thermal_decimated += 1
                    return
                base = nxt if (nxt is not None and t - nxt < period) else t
                self._thermal_next = base + period
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._broadcast, text)
        except RuntimeError:                                 # loop closing
            pass

    def event(self, kind: str, detail: str) -> None:
        self.emit(self.ctx.make("event", kind=kind, detail=detail))

    def _broadcast(self, text: str) -> None:
        for c in list(self.clients.values()):
            c.put(text)

    def hello(self) -> dict:
        extra = {} if self.mount is None else {"mount": self.mount}
        return self.ctx.make("hello", sensors=[d.name for d in self.drivers], version=__version__,
                             config_digest=self.digest, thermal_wire_hz=self.thermal_wire_hz, **extra)

    # ------------------------------------------------------------------ websocket side
    async def _handler(self, ws: ServerConnection) -> None:
        req_path = ws.request.path if ws.request is not None else ""
        if req_path.split("?", 1)[0] != self.path:
            await ws.close(code=1008, reason="use %s" % self.path)
            return
        peer = "%s:%s" % (ws.remote_address[:2] if ws.remote_address else ("?", "?"))
        client = ClientQueue(self.client_queue_max, name=peer)
        try:
            await ws.send(protocol.dumps(self.hello()))
        except ConnectionClosed:
            return
        sender = asyncio.ensure_future(self._sender(ws, client))
        closed = asyncio.ensure_future(ws.wait_closed())
        self.clients[id(client)] = client
        self._conns[id(client)] = (ws, client, sender)
        self.event("client_connected", "%s (clients=%d)" % (peer, len(self.clients)))
        stopping = False
        try:
            await asyncio.wait({sender, closed}, return_when=asyncio.FIRST_COMPLETED)
            stopping = sender.done() and not sender.cancelled() and sender.exception() is None
        finally:
            for t in (sender, closed):
                t.cancel()
            await asyncio.gather(sender, closed, return_exceptions=True)
            self.clients.pop(id(client), None)
            self._conns.pop(id(client), None)
            self.event("client_disconnected", "%s sent=%d dropped=%d" % (peer, client.sent, client.dropped))
        if stopping:
            # Queue closed by stop(): tell the client why. For a client that does not read this waits in drain()
            # until stop() aborts the transport after client_grace_s.
            try:
                await ws.close(1001, "unit stopping")
            except Exception:                                # noqa: BLE001 - closing anyway
                pass

    async def _sender(self, ws: ServerConnection, client: ClientQueue) -> None:
        """Per-client sender task: queue -> socket. Returns when the queue is closed (server stopping)."""
        while True:
            text = await client.get()
            if text is None:
                return
            await ws.send(text)
            client.sent += 1

    async def _unit_heartbeat(self) -> None:
        while True:
            seq = self._hb_seq
            self._hb_seq += 1
            status, rec = "ok", ""
            if self.recorder is not None:
                rec = " rec_dropped=%d" % self.recorder.dropped
                health = getattr(self.recorder, "health", None)
                ok, why = health() if callable(health) else (True, "")
                if not ok:
                    status, rec = "error", "%s; %s" % (rec, why)
            self.emit(self.ctx.make("heartbeat", sensor="unit", status=status,
                                    detail="clients=%d%s" % (len(self.clients), rec), last_reading_seq=None,
                                    rate_hz=None, seq=seq))
            await asyncio.sleep(self.heartbeat_s)

    async def _drop_reporter(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            for c in list(self.clients.values()):
                new = c.dropped - c.dropped_reported
                if new > 0:
                    c.dropped_reported = c.dropped
                    msg = self.ctx.make("event", kind="dropped",
                                        detail="client %s: %d messages dropped (total %d), queue max %d"
                                               % (c.name, new, c.dropped, c.maxsize))
                    text = protocol.dumps(msg)
                    if self.recorder is not None:
                        self.recorder.write(msg, text)
                    c.put(text)

    async def start(self) -> None:
        """Bind the socket, start the sim clock (if any), the drivers and the background tasks."""
        self._loop = asyncio.get_running_loop()
        self._ws = await serve(self._handler, self.host, self.port, ping_interval=5, ping_timeout=10,
                               max_size=2 ** 20, compression=None)
        sock = next(iter(self._ws.sockets))
        self.port = sock.getsockname()[1]
        if self.session is not None:
            self.session.start(self.speed, self.loop_replay)
        for d in self.drivers:
            d.start()
        self._tasks = [asyncio.ensure_future(self._unit_heartbeat()), asyncio.ensure_future(self._drop_reporter())]
        log.info("serving ws://%s:%d%s session=%s sim=%s", self.host, self.port, self.path, self.ctx.session_id,
                 self.ctx.sim)

    async def stop(self) -> None:
        """Bounded shutdown (``stop_timeout_s``, default 1.8 s), with or without connected clients.

        1. drivers stop in parallel (final ``no_device`` heartbeats), each joining its threads with ``driver_join_s``;
        2. unit heartbeat and drop reporter tasks cancelled;
        3. client queues closed: a reading client gets what is queued, then close code 1001 "unit stopping";
           after ``client_grace_s`` any sender task still running is cancelled and its transport aborted;
        4. listening socket closed (bounded wait; leftover connections aborted);
        5. recorder flushed and closed with max(time left, ``recorder_close_s``) (a recorder that cannot finish in
           time is left to its daemon writer thread and session.json says ``closed_cleanly: false``; files stay
           readable up to the last flush, see ``replay.iter_lines``).
        """
        loop = asyncio.get_running_loop()
        t_start = time.monotonic()
        deadline = t_start + self.stop_timeout_s

        def left(floor: float = 0.05) -> float:
            return max(floor, deadline - time.monotonic())

        # 1. drivers
        if self.drivers:
            futs = [_in_daemon_thread(loop, _stop_driver, d, self.driver_join_s) for d in self.drivers]
            done, pending = await asyncio.wait(futs, timeout=min(left(), 2 * self.driver_join_s + 0.3))
            if pending:
                log.warning("stop: %d driver(s) did not stop in time; left to daemon threads", len(pending))
        await asyncio.sleep(0.05)                            # let the final heartbeats reach the queues
        # 2. background tasks
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        # 3. clients: close the queues so handlers drain, send 1001 and return
        for c in list(self.clients.values()):
            c.close()
        conns = list(self._conns.values())
        if conns:
            handlers_done = [asyncio.ensure_future(_closed_or_gone(ws)) for ws, _, _ in conns]
            await asyncio.wait(handlers_done, timeout=min(self.client_grace_s, left()))
            for f in handlers_done:
                f.cancel()
        for ws, _client, sender in conns:                    # still open after the grace: stuck client
            if not sender.done():
                sender.cancel()
            if ws.state is not State.CLOSED:
                _abort(ws)
        # 4. listening socket
        if self._ws is not None:
            srv, self._ws = self._ws, None
            srv.close()
            try:
                await asyncio.wait_for(srv.wait_closed(), timeout=min(0.5, left()))
            except asyncio.TimeoutError:
                for ws in list(getattr(srv, "handlers", {}) or {}):
                    _abort(ws)
                try:
                    await asyncio.wait_for(srv.wait_closed(), timeout=min(0.3, left()))
                except asyncio.TimeoutError:
                    log.warning("stop: websocket server did not close in time")
        # 5. recorder flush/close
        if self.recorder is not None:
            budget = max(left(0.3), self.recorder_close_s)
            fut = _in_daemon_thread(loop, self.recorder.close, budget)
            done, _ = await asyncio.wait([fut], timeout=budget + 0.1)
            if not done:
                log.warning("stop: recorder did not close within %.1f s", budget)
        self._loop = None
        self.last_stop_s = time.monotonic() - t_start
        log.info("stopped in %.2f s", self.last_stop_s)

    def all_sim_ended(self) -> bool:
        return bool(self.drivers) and all(d.status()[0] == "sim_ended" for d in self.drivers)

    async def run(self, duration_s: Optional[float] = None, stop_event: Optional[asyncio.Event] = None,
                  exit_on_sim_end: bool = False) -> None:
        """Start, serve until ``duration_s`` elapses, ``stop_event`` is set or (optionally) the replay ends."""
        await self.start()
        t_end = None if duration_s is None else time.monotonic() + duration_s
        try:
            while True:
                if t_end is not None and time.monotonic() >= t_end:
                    break
                if stop_event is not None and stop_event.is_set():
                    break
                if exit_on_sim_end and self.all_sim_ended():
                    await asyncio.sleep(1.0)
                    break
                await asyncio.sleep(0.1)
        finally:
            await self.stop()


# ---------------------------------------------------------------------- shutdown helpers
def _stop_driver(driver, join_s: float) -> None:
    try:
        driver.stop(join_s)
    except TypeError:                                        # a driver-like object whose stop() takes no timeout
        driver.stop()


def _in_daemon_thread(loop: asyncio.AbstractEventLoop, fn: Callable, *args) -> "asyncio.Future":
    """Run ``fn(*args)`` on a new daemon thread; the returned future resolves on ``loop``. Unlike
    ``asyncio.to_thread`` (default executor, joined by ``asyncio.run`` at exit), a call that never returns cannot
    keep the process alive."""
    fut = loop.create_future()

    def _set(result=None, exc=None) -> None:
        if fut.done():
            return
        if exc is not None:
            fut.set_exception(exc)
        else:
            fut.set_result(result)

    def _run() -> None:
        try:
            r = fn(*args)
        except BaseException as exc:                         # noqa: BLE001 - handed to the awaiting side
            err = exc
            try:
                loop.call_soon_threadsafe(_set, None, err)
            except RuntimeError:
                pass
            return
        try:
            loop.call_soon_threadsafe(_set, r)
        except RuntimeError:                                 # loop already closed
            pass

    threading.Thread(target=_run, name="stop-%s" % getattr(fn, "__name__", "call"), daemon=True).start()
    return fut


async def _closed_or_gone(ws) -> None:
    await ws.wait_closed()


def _abort(ws) -> None:
    """Drop the TCP connection now, discarding unsent data (``transport.close()`` would wait for a stuck peer)."""
    try:
        tr = ws.transport
        if tr is not None:
            tr.abort()                                       # also when already closing on a full buffer
    except Exception:                                        # noqa: BLE001
        pass
