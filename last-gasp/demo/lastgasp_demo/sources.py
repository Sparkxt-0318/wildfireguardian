"""Heartbeat sources. Each source returns new messages (dicts) with a host arrival time 't' in seconds.

- SimulatorSource: a synthetic fire crosses the village map; every node sends a
  heartbeat each interval until the fire reaches it. Optional spot fire.
- SerialSource: JSON lines from a receiver ESP32 over USB serial (needs pyserial).
- BleSource: scans BLE advertisements directly from the laptop (needs bleak).
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque

import numpy as np

from .protocol import decode_adv, decode_json


class SimulatorSource:
    """Elliptical fire from an ignition point plus an optional spot fire. SIMULATED, not real data."""

    def __init__(self, village, interval_s=1.0, head_speed=10.0, wind_to_deg=0.0, lb=2.5,
                 ignition=None, spot=True, loss=0.05, seed=1, start_delay_s=5.0):
        self.nodes = village["nodes"]
        self.interval = interval_s
        self.loss = loss
        self.rng = np.random.default_rng(seed)
        W, H = village["width_m"], village["height_m"]
        ig = ignition or (0.0, H * 0.45)
        e = math.sqrt(1 - 1 / lb ** 2)
        wt = math.radians(wind_to_deg)

        def tt(x0, y0, x, y):
            d = math.hypot(x - x0, y - y0)
            th = math.atan2(y - y0, x - x0) - wt
            return d * (1 - e * math.cos(th)) / (head_speed * (1 - e))

        self.spot_point = None
        death = {}
        for n in self.nodes:
            death[n["id"]] = start_delay_s + tt(ig[0], ig[1], n["x"], n["y"])
        if spot:
            # A firebrand lands next to the node nearest (0.75 W, 0.38 H), well ahead of the front,
            # at the moment the main front is about 40% of the way to it.
            xy = np.array([[n["x"], n["y"]] for n in self.nodes], float)
            k = int(np.argmin(np.hypot(*(xy - [0.75 * W, 0.38 * H]).T)))
            sx, sy = xy[k] + [-15.0, 10.0]
            t_spot = start_delay_s + tt(ig[0], ig[1], sx, sy) * 0.40
            self.spot_point = (sx, sy, t_spot)
            for n in self.nodes:
                death[n["id"]] = min(death[n["id"]], t_spot + tt(sx, sy, n["x"], n["y"]))
        jitter = self.rng.uniform(0, 1.5, len(self.nodes))
        self.death = {n["id"]: death[n["id"]] + j for n, j in zip(self.nodes, jitter)}
        self.phase = {n["id"]: self.rng.uniform(0, interval_s) for n in self.nodes}
        self.seq = {n["id"]: 0 for n in self.nodes}
        self.t_sent = {n["id"]: -1.0 for n in self.nodes}

    def poll(self, now):
        out = []
        for n in self.nodes:
            i = n["id"]
            k_last = math.floor((min(now, self.death[i]) - self.phase[i]) / self.interval)
            k_prev = math.floor((self.t_sent[i] - self.phase[i]) / self.interval) if self.t_sent[i] >= 0 else -1
            for k in range(max(k_prev + 1, 0), k_last + 1):
                t = self.phase[i] + k * self.interval
                if t > now or t > self.death[i]:
                    break
                self.seq[i] += 1
                if self.rng.random() < self.loss:
                    continue
                temp = 25 + max(0.0, 40 - 4 * (self.death[i] - t))
                out.append({"v": 1, "id": i, "seq": self.seq[i], "bat_mv": 3000, "temp_c": int(temp),
                            "flags": 4 if temp > 50 else 0, "rssi": -60, "rx": "sim", "t": t})
            self.t_sent[i] = min(now, self.death[i])
        out.sort(key=lambda m: m["t"])
        return out


class SerialSource:
    """JSON-lines heartbeats from a receiver ESP32 on a serial port (pip install pyserial)."""

    def __init__(self, port, baud=115200):
        import serial  # noqa: PLC0415
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.t0 = time.monotonic()
        self.buf = deque()
        self._stop = False
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while not self._stop:
            line = self.ser.readline().decode("utf-8", "replace")
            m = decode_json(line) if line else None
            if m:
                m["t"] = time.monotonic() - self.t0
                self.buf.append(m)

    def poll(self, now):
        out = []
        while self.buf:
            out.append(self.buf.popleft())
        return out


class BleSource:
    """Scan BLE advertisements directly (pip install bleak). Runs the asyncio scanner in a thread."""

    def __init__(self):
        import asyncio  # noqa: PLC0415

        from bleak import BleakScanner  # noqa: PLC0415
        self.t0 = time.monotonic()
        self.buf = deque()

        def cb(device, adv):
            for cid, data in adv.manufacturer_data.items():
                m = decode_adv(cid.to_bytes(2, "little") + bytes(data))
                if m:
                    m.update({"rssi": adv.rssi, "rx": "ble", "t": time.monotonic() - self.t0})
                    self.buf.append(m)

        async def run():
            async with BleakScanner(cb):
                while True:
                    await asyncio.sleep(1.0)

        threading.Thread(target=lambda: asyncio.run(run()), daemon=True).start()

    def poll(self, now):
        out = []
        while self.buf:
            out.append(self.buf.popleft())
        return out
