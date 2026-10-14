"""Death detection, spot fire flags and live reconstruction for the booth demo.

Rules (kept simple so visitors can follow them):
- A node is dead after `timeout_beats` missed heartbeats. Death time = arrival
  time of its last heartbeat. A node that starts beating again is revived.
- Spot fire: a newly dead node whose nearest earlier-dead node is at least
  `min_jump_m` away, with at least one LIVE node inside the corridor between
  them. Jump distance = distance to that nearest earlier-dead node.
- Burned area: for each map point, the inverse-distance-weighted share of dead
  nodes among the k nearest heard nodes; burned where the share is at least 0.5.
- Arrival-time map: inverse-distance weighting of death times, shown only
  inside the burned area.
"""
from __future__ import annotations

import numpy as np


class DemoState:
    def __init__(self, village, interval_s=1.0, timeout_beats=3, min_jump_m=250.0, corridor_m=120.0,
                 grid_m=5.0, k=4, max_support_m=300.0):
        self.v = village
        self.ids = [n["id"] for n in village["nodes"]]
        self.xy = np.array([[n["x"], n["y"]] for n in village["nodes"]], float)
        self.index = {i: k for k, i in enumerate(self.ids)}
        n = len(self.ids)
        self.last = np.full(n, np.nan)
        self.dead = np.zeros(n, bool)
        self.t_death = np.full(n, np.nan)
        self.temp = np.full(n, np.nan)
        self.timeout = timeout_beats * interval_s
        self.min_jump = min_jump_m
        self.corridor = corridor_m
        self.k = k
        self.max_support_m = max_support_m
        self.spots = []
        self.events = []
        gx = np.arange(grid_m / 2, village["width_m"], grid_m)
        gy = np.arange(grid_m / 2, village["height_m"], grid_m)
        self.GX, self.GY = np.meshgrid(gx, gy)
        self.q = np.c_[self.GX.ravel(), self.GY.ravel()]
        self.d_q = np.hypot(self.q[:, None, 0] - self.xy[None, :, 0], self.q[:, None, 1] - self.xy[None, :, 1])
        # Support: how far each map point is from the nearest node (nothing is known far from nodes).
        self.d_near = self.d_q.min(1).reshape(self.GX.shape)

    def ingest(self, msgs):
        for m in msgs:
            k = self.index.get(m["id"])
            if k is None:
                continue
            if self.dead[k] and m["t"] > self.t_death[k] + self.timeout:
                self.dead[k] = False
                self.t_death[k] = np.nan
                self.spots = [s for s in self.spots if s["id"] != self.ids[k]]
                self.events.append((m["t"], f"node {self.ids[k]} revived"))
            self.last[k] = m["t"] if np.isnan(self.last[k]) else max(self.last[k], m["t"])
            self.temp[k] = m.get("temp_c", np.nan)

    def update(self, now):
        heard = ~np.isnan(self.last)
        newly = np.where(heard & ~self.dead & (now - self.last > self.timeout))[0]
        for k in sorted(newly, key=lambda j: self.last[j]):
            self.dead[k] = True
            self.t_death[k] = self.last[k]
            self._check_spot(k)
            self.events.append((now, f"node {self.ids[k]} burned"))

    def _check_spot(self, k):
        earlier = np.where(self.dead & (self.t_death < self.t_death[k]))[0]
        if not len(earlier):
            return
        d = np.hypot(*(self.xy[earlier] - self.xy[k]).T)
        j = earlier[int(np.argmin(d))]
        jump = float(d.min())
        if jump < self.min_jump:
            return
        a, b = self.xy[j], self.xy[k]
        u = (b - a) / jump
        rel = self.xy - a
        s = rel @ u
        perp = np.abs(rel @ np.array([-u[1], u[0]]))
        alive = ~self.dead & ~np.isnan(self.last)
        between = alive & (s > 0.1 * jump) & (s < 0.9 * jump) & (perp < self.corridor / 2)
        if between.any():
            self.spots.append({"id": self.ids[k], "x": float(b[0]), "y": float(b[1]), "jump_m": jump,
                               "from": self.ids[j], "t": float(self.t_death[k])})

    def fields(self):
        """Burned share (0 to 1) and arrival-time grid (nan outside the burned area)."""
        heard = ~np.isnan(self.last)
        if not self.dead.any():
            return np.zeros(self.GX.shape), np.full(self.GX.shape, np.nan)
        idx = np.where(heard)[0]
        D = self.d_q[:, idx]
        kk = min(self.k, len(idx))
        part = np.argpartition(D, kk - 1, axis=1)[:, :kk]
        dsel = np.take_along_axis(D, part, 1)
        w = 1.0 / np.maximum(dsel, 5.0) ** 2
        share = (w * self.dead[idx][part]).sum(1) / w.sum(1)
        di = np.where(self.dead)[0]
        Dd = self.d_q[:, di]
        kd = min(8, len(di))
        pd = np.argpartition(Dd, kd - 1, axis=1)[:, :kd]
        wd = 1.0 / np.maximum(np.take_along_axis(Dd, pd, 1), 5.0) ** 2
        arr = (wd * self.t_death[di][pd]).sum(1) / wd.sum(1)
        burned = share >= 0.5
        return share.reshape(self.GX.shape), np.where(burned, arr, np.nan).reshape(self.GX.shape)
