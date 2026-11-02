"""Frozen hazard packet (wfg.routing.edgegrid/1 + constructed_arrays.npz) read for contact replay.

Two representations of the same flame activity are loaded and required to agree cell by cell:

* ``phases`` -- exact half-open phases per member and router cell, exactly as the runtime whole-road contact check
  builds them (kit ``contact_first.ContactSources.from_arrays``): present-fire cells (``current_active``) burn on
  [0, R) in every member when R = ``initial_remaining_s`` > 0; a cell drawing a first-new ignition at ``b`` in a
  member burns on [b, b + T) with T = ``burning_duration_s``. Native north-up rows are mapped to router rows
  (row reversal) exactly as the independent checker does.
* ``bins`` -- the router's own input, ``HAZARD.json``: per member breakpoints bp[0..n] and ``flame[i][cell]`` on the
  sampling bins [bp[i], bp[i+1]) (the last bin also contains bp[n]).

``Packet.verify_consistency`` proves that, for every member and cell, the union of HAZARD flame bins equals the phase
interval with the router's rounded-up extinction (``bridge.round_up_sum``), clipped to [bp[0], bp[n]].
"""
from __future__ import annotations

import bisect
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import numpy as np

from .geometry import Grid, exact

PACKET_FILES = ("HAZARD.json", "REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def round_up_sum(a: float, b: float) -> float:
    """Smallest binary64 >= exact a + b (packet writer's extinction breakpoint, bridge.round_up_sum)."""
    s = float(a) + float(b)
    if F(s) < F(float(a)) + F(float(b)):
        s = float(np.nextafter(s, np.inf))
    return s


class PacketError(ValueError):
    pass


class Packet:
    """Phases and flame bins of one recorded scenario set (4 members)."""

    def __init__(self, packet_dir, grid: Grid, *, hazard: dict | None = None):
        d = Path(packet_dir)
        self.dir = d
        self.grid = grid
        self.sha256 = {name: sha256_file(d / name) for name in PACKET_FILES if (d / name).is_file()}
        report = json.loads((d / "REPORT.json").read_text())
        md = report["native_metadata"]
        a = md["construction"]["assumptions"]
        if a.get("version") != "wfg.hazard.construction/1":
            raise PacketError("unsupported source law %r" % a.get("version"))
        self.T = exact(a["burning_duration_s"])
        self.R = exact(a["initial_remaining_s"])
        self.horizon = exact(a["horizon_s"])
        self.T_float = float(a["burning_duration_s"])
        hz = hazard if hazard is not None else json.loads((d / "HAZARD.json").read_text())
        if hz.get("schema") != "wfg.routing.edgegrid/1":
            raise PacketError("HAZARD schema %r" % hz.get("schema"))
        g = hz["grid"]
        if (exact(g["x0"]), exact(g["y0"]), exact(g["resolution"]), int(g["width"]), int(g["height"])) != \
                (grid.x0, grid.y0, grid.res, grid.W, grid.H):
            raise PacketError("HAZARD grid differs from the graph grid")
        self.time_origin = hz["time_origin"]
        self.valid_from = exact(hz["valid_from"])
        self.valid_until = exact(hz["valid_until"])
        self.dt = int(hz["dt"])
        self.member_ids = [m["id"] for m in hz["members"]]
        incurred_ids = list(report["rows"][0]["request"]["incurred"])
        if incurred_ids != self.member_ids:
            raise PacketError("member order differs between HAZARD.json and REPORT.json")
        with np.load(d / "constructed_arrays.npz", allow_pickle=False) as z:
            ev = np.array(z["ignition_time_s"], dtype=float)
            cur = np.array(z["current_active"])
            sup = np.array(z["support"])
        S, Hn, Wn = ev.shape
        if (Hn, Wn) != (grid.H, grid.W) or S != len(self.member_ids):
            raise PacketError("npz shape differs from grid/members")
        if cur.dtype != np.bool_ or not sup.all() or np.isfinite(ev[:, cur]).any() or np.any(np.isnan(ev)) or np.any(ev < 0):
            raise PacketError("npz contract violated (current/support/events)")
        self.S = S
        # ---- exact phases (runtime contact semantics), router cell index ----------------------------------------
        self.phases = []          # per member: {cell: (birth, expiry_exact, expiry_router, kind)}
        cur_cells = [self.native_to_router(int(i)) for i in np.flatnonzero(cur.ravel())]
        for s in range(S):
            ph = {}
            if self.R > 0:
                for c in cur_cells:
                    ph[c] = (F(0), self.R, self.R, "CURRENT")
            evs = ev[s].ravel()
            for i in np.flatnonzero(np.isfinite(evs)):
                b = float(evs[i])
                if F(b) >= self.horizon:
                    raise PacketError("ignition at or after the horizon")
                ph[self.native_to_router(int(i))] = (F(b), F(b) + self.T, F(round_up_sum(b, self.T_float)), "FUTURE")
            self.phases.append(ph)
        self.present_cells = sorted(cur_cells)
        self.burning_cells = sorted({c for ph in self.phases for c in ph})
        # ---- router flame bins (HAZARD.json) -------------------------------------------------------------------
        self.breakpoints = []     # per member: list of Fractions
        self.flame_bins = []      # per member: {cell: sorted bin indices with flame}
        n_cells = grid.W * grid.H
        for m in hz["members"]:
            bp = [exact(x) for x in m["breakpoints"]]
            if any(b2 <= b1 for b1, b2 in zip(bp, bp[1:])):
                raise PacketError("breakpoints not increasing")
            fl = m["flame"]
            if len(fl) != len(bp) - 1 or any(len(row) != n_cells for row in fl):
                raise PacketError("flame array shape")
            bins = {}
            for i, row in enumerate(fl):
                for c in (j for j, v in enumerate(row) if v):
                    bins.setdefault(c, []).append(i)
            self.breakpoints.append(bp)
            self.flame_bins.append(bins)
        self.consistency = self.verify_consistency()

    # ------------------------------------------------------------------------------------------------ helpers
    def native_to_router(self, i: int) -> int:
        r, c = divmod(i, self.grid.W)
        return (self.grid.H - 1 - r) * self.grid.W + c

    def member_label(self, s: int) -> int:
        """Member number as the scenario id suffix (``...:0`` .. ``...:3``)."""
        return int(self.member_ids[s].rsplit(":", 1)[1])

    def verify_consistency(self) -> dict:
        """Every HAZARD flame bin set must equal the npz phase with router extinction, clipped to the bins."""
        checked = 0
        for s in range(self.S):
            bp = self.breakpoints[s]
            lo, hi = bp[0], bp[-1]
            cells = set(self.flame_bins[s]) | set(self.phases[s])
            for c in cells:
                ph = self.phases[s].get(c)
                want = []
                if ph is not None:
                    a, b = max(ph[0], lo), min(ph[2], hi)
                    if a < b:
                        want = [i for i in range(len(bp) - 1) if a <= bp[i] < b]
                        # the phase must be breakpoint-aligned inside [lo, hi]
                        if not want or bp[want[0]] != a or (b < hi and bp[want[-1] + 1] != b):
                            raise PacketError("phase of cell %d member %d not breakpoint-aligned" % (c, s))
                if self.flame_bins[s].get(c, []) != want:
                    raise PacketError("HAZARD flame bins differ from npz phases (cell %d member %d)" % (c, s))
                checked += 1
        return {"cells_checked": checked, "status": "HAZARD_FLAME_EQUALS_NPZ_PHASES"}

    # ------------------------------------------------------------------------------------------------ contact
    def contact_closed(self, s: int, cell: int, lo: F, hi: F):
        """Runtime closed-footprint rule on one closed occupancy [lo, hi] of the closed cell rectangle:
        contact iff w = max(lo, birth) satisfies w <= hi and w < expiry (exact expiry). Returns w or None."""
        ph = self.phases[s].get(cell)
        if ph is None:
            return None
        w = max(lo, ph[0])
        if w <= hi and w < ph[1]:
            return w
        return None

    def contact_router(self, s: int, cell: int, lo: F, hi: F) -> str | None:
        """Router ``evaluate_occupancy`` sampling rule on (cell, [lo, hi]) against HAZARD.json: samples lo, hi and
        every breakpoint strictly inside; bin index min(n-1, bisect_right(bp, p) - 1). Returns 'FLAME_CONTACT',
        'UNSUPPORTED' (occupancy outside [bp0, bpn]) or None."""
        bp = self.breakpoints[s]
        if lo < bp[0] or hi > bp[-1] or hi < lo:
            return "UNSUPPORTED"
        bins = self.flame_bins[s].get(cell)
        if not bins:
            return None
        pts = [lo, hi] + [p for p in bp[1:-1] if lo < p < hi]
        fb = set(bins)
        for p in pts:
            i = min(len(bp) - 2, bisect.bisect_right(bp, p) - 1)
            if i in fb:
                return "FLAME_CONTACT"
        return None
