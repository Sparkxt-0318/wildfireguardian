#!/usr/bin/env python3
"""A minimal Chrome DevTools Protocol client, standard library only (WFG-009).

Why this file exists rather than a dependency
---------------------------------------------
`web/finals.html` is the screen five judges watch, and readiness line R1 asks that
「all four acts advance」.  Advancing an act means pressing a button, which
`--dump-dom` cannot do: it presses nothing, so the two acts that build on a click
were exactly the ones no measurement covered (critic #36, 2026-09-07T1717Z).

Driving a real browser normally means Playwright.  This sandbox cannot install it:
`pip` times out on `files.pythonhosted.org` and no WebSocket package
(`websockets`, `websocket-client`) is present either.  CHARTER §4 forbids a test
that reaches the network, so "install it in CI" is not an escape hatch — the gate
has to run on a clean clone with no wheel downloads.

So this is the smallest thing that works: the DevTools protocol is JSON over one
WebSocket, and RFC 6455 client framing is about eighty lines.  It speaks only the
handshake, text frames and close, because that is all the driver needs.

What it does NOT do
-------------------
No permessage-deflate, no continuation of *client* messages (every command this
driver sends fits one frame), no ping/pong initiation.  It is a test harness for
one local browser over loopback, not a general WebSocket client, and it should
not grow into one.  The loopback socket is not "the network" in CHARTER §4b's
sense — nothing outside the machine is contacted — but the driver still refuses
to run when Chromium is absent rather than downloading one.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import urllib.parse
import urllib.request

#: RFC 6455 §1.3.  Fixed by the standard, not a choice.
_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class CDPError(RuntimeError):
    """A DevTools command came back with an `error` member, or the socket died."""


class _WebSocket:
    """Client side of one RFC 6455 connection, text frames only."""

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        parts = urllib.parse.urlparse(url)
        host, port = parts.hostname or "127.0.0.1", parts.port or 80
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._buf = b""
        key = base64.b64encode(os.urandom(16)).decode()
        path = parts.path + (("?" + parts.query) if parts.query else "")
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._sock.sendall(req.encode())
        head = self._read_until(b"\r\n\r\n")
        if b"101" not in head.split(b"\r\n", 1)[0]:
            raise CDPError(f"WebSocket upgrade refused: {head[:200]!r}")
        expect = base64.b64encode(hashlib.sha1((key + _GUID).encode()).digest()).decode()
        if expect.lower().encode() not in head.lower():
            raise CDPError("WebSocket accept key did not match; not a real endpoint")

    def _read_until(self, marker: bytes) -> bytes:
        while marker not in self._buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise CDPError("socket closed during handshake")
            self._buf += chunk
        head, self._buf = self._buf.split(marker, 1)
        return head + marker

    def _recv_exactly(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self._sock.recv(1 << 20)
            if not chunk:
                raise CDPError("socket closed mid-frame")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def send(self, text: str) -> None:
        payload = text.encode()
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        n = len(payload)
        if n < 126:
            header = struct.pack("!BB", 0x81, 0x80 | n)
        elif n < (1 << 16):
            header = struct.pack("!BBH", 0x81, 0x80 | 126, n)
        else:
            header = struct.pack("!BBQ", 0x81, 0x80 | 127, n)
        self._sock.sendall(header + mask + masked)

    def recv(self) -> str:
        """One complete text message, reassembling server continuation frames."""
        chunks: list[bytes] = []
        while True:
            b0, b1 = self._recv_exactly(2)
            fin, opcode = b0 & 0x80, b0 & 0x0F
            length = b1 & 0x7F
            if length == 126:
                (length,) = struct.unpack("!H", self._recv_exactly(2))
            elif length == 127:
                (length,) = struct.unpack("!Q", self._recv_exactly(8))
            if b1 & 0x80:  # a server frame must not be masked
                raise CDPError("server sent a masked frame")
            data = self._recv_exactly(length)
            if opcode == 0x8:
                raise CDPError("server closed the connection")
            if opcode == 0x9:  # ping -> pong, so a slow act does not drop us
                self._sock.sendall(struct.pack("!BB", 0x8A, 0x80) + os.urandom(4))
                continue
            if opcode == 0xA:
                continue
            chunks.append(data)
            if fin:
                return b"".join(chunks).decode("utf-8", "replace")

    def close(self) -> None:
        try:
            self._sock.sendall(struct.pack("!BB", 0x88, 0x80) + os.urandom(4))
        except OSError:
            pass
        finally:
            self._sock.close()


class CDP:
    """One page target.  `call` is request/response; `events` is what arrived."""

    def __init__(self, ws_url: str, timeout: float = 30.0) -> None:
        self._ws = _WebSocket(ws_url, timeout=timeout)
        self._id = 0
        self.events: list[dict] = []

    def call(self, method: str, **params) -> dict:
        self._id += 1
        mid = self._id
        self._ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CDPError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)

    def drain(self) -> None:
        """Collect events already queued without blocking on a new one."""
        self._ws._sock.settimeout(0.35)
        try:
            while True:
                msg = json.loads(self._ws.recv())
                if "method" in msg:
                    self.events.append(msg)
        except (socket.timeout, TimeoutError, OSError, CDPError):
            pass
        finally:
            self._ws._sock.settimeout(30.0)

    def evaluate(self, expression: str):
        """Evaluate JS and return the value, JSON-decoded when it is a string."""
        res = self.call(
            "Runtime.evaluate", expression=expression,
            returnByValue=True, awaitPromise=True,
        )
        if res.get("exceptionDetails"):
            d = res["exceptionDetails"]
            desc = d.get("exception", {}).get("description") or d.get("text")
            raise CDPError(f"JS threw: {desc}")
        return res.get("result", {}).get("value")

    def close(self) -> None:
        self._ws.close()


def page_target(port: int, timeout: float = 30.0) -> str:
    """The WebSocket URL of the one page target, waiting for the browser to listen."""
    import time

    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/list", timeout=2
            ) as fh:
                targets = json.loads(fh.read().decode())
            for t in targets:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return t["webSocketDebuggerUrl"]
        except Exception as exc:  # noqa: BLE001 - the browser is still starting
            last = exc
        time.sleep(0.2)
    raise CDPError(f"no page target on port {port} within {timeout}s (last: {last})")
