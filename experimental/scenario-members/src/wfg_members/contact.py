"""Exact per-member flame-activity intervals on graph cells (the contact model shared by every planner here).

A member is active in a cell on half-open intervals [b, b + T) for a first-new ignition at exact second b, and every
member shares the present-fire enclosure [0, R) on the present-fire cells (R > 0). Times are exact rationals of the
represented binary64 values, exactly as `integration/kit/phaseB/road_bounds.RoadBoundModel.cell_intervals` builds them
(tested for equality on the frozen packets). Graph cells are south-up: native north-up row r maps to graph row H-1-r.

`ContactModel` duck-types the `model` argument of the frozen `zsweep.contact_sweep` (attribute `cell_intervals`).
"""
from __future__ import annotations

import json
import math
from fractions import Fraction as F
from pathlib import Path

import numpy as np


def rational(value) -> F:
    """Same rule as road_exposure.rational: exact rational of an int or of the binary64 value."""
    if isinstance(value, F):
        return value
    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        return F(int(value))
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("finite numeric value required")
    return F(value)


class ContactModel:
    def __init__(self, *, shape, T, R, current_native, events_native, ids, weights=None, label=None):
        H, W = shape
        self.shape = (int(H), int(W))
        self.T, self.R = rational(T), rational(R)
        if self.T <= 0 or not (0 <= self.R <= self.T):
            raise ValueError("invalid duration or remaining time")
        self.ids = list(ids)
        if len(self.ids) != len(events_native) or len(set(self.ids)) != len(self.ids):
            raise ValueError("one unique id per member required")
        self.current = sorted(self._g(int(i)) for i in current_native)
        self.events = []       # per member: {graph cell: Fraction birth}
        for row in events_native:
            ev = {self._g(int(i)): rational(b) for i, b in row.items()}
            if set(ev) & set(self.current):
                raise ValueError("present-fire cell also has a first-new ignition")
            self.events.append(ev)
        n = len(self.ids)
        self.weights = [F(1, n)] * n if weights is None else [F(w) if not isinstance(w, float) else F(w) for w in weights]
        self.label = label
        self._union = None

    def _g(self, native_index):
        H, W = self.shape
        r, c = divmod(native_index, W)
        return (H - 1 - r) * W + c

    def native_index(self, graph_cell):
        H, W = self.shape
        gr, c = divmod(int(graph_cell), W)
        return (H - 1 - gr) * W + c

    # ------------------------------------------------------------------ constructors
    @classmethod
    def from_arrays(cls, ignition_time_s, current_active, T, R, ids=None, weights=None, label=None):
        ign = np.asarray(ignition_time_s, dtype=float)
        cur = np.asarray(current_active, dtype=bool)
        if ign.ndim != 3 or cur.shape != ign.shape[1:]:
            raise ValueError("ignition [S,H,W] and current [H,W] required")
        S, H, W = ign.shape
        events = []
        for s in range(S):
            flat = ign[s].ravel()
            idx = np.flatnonzero(np.isfinite(flat))
            events.append({int(i): rational(flat[i]) for i in idx})
        current = np.flatnonzero(cur.ravel()).tolist() if rational(R) > 0 else []
        ids = ids if ids is not None else ["m%d" % s for s in range(S)]
        return cls(shape=(H, W), T=T, R=R, current_native=current, events_native=events, ids=ids, weights=weights, label=label)

    @classmethod
    def from_packet(cls, packet_dir, weights=None, label=None):
        packet_dir = Path(packet_dir)
        report = json.loads((packet_dir / "REPORT.json").read_text())
        assumptions = report["native_metadata"]["construction"]["assumptions"]
        ids = list(report["rows"][0]["request"]["incurred"])
        with np.load(packet_dir / "constructed_arrays.npz", allow_pickle=False) as a:
            ign, cur = a["ignition_time_s"], a["current_active"]
        return cls.from_arrays(ign, cur, assumptions["burning_duration_s"], assumptions["initial_remaining_s"], ids=ids,
                               weights=weights, label=label or str(packet_dir))

    # ------------------------------------------------------------------ views
    def subset(self, indices, label=None):
        indices = list(indices)
        out = ContactModel.__new__(ContactModel)
        out.shape, out.T, out.R = self.shape, self.T, self.R
        out.ids = [self.ids[i] for i in indices]
        out.current = list(self.current)
        out.events = [self.events[i] for i in indices]
        out.weights = [self.weights[i] for i in indices]
        out.label = label or ("%s[%s]" % (self.label, ",".join(map(str, indices))))
        out._union = None
        return out

    def shared_only(self, label=None):
        """Present fire only (the part every member shares); one pseudo-member with no first-new ignitions."""
        out = ContactModel.__new__(ContactModel)
        out.shape, out.T, out.R = self.shape, self.T, self.R
        out.ids, out.current, out.events, out.weights = ["shared"], list(self.current), [{}], [F(1)]
        out.label = label or ("%s[shared]" % self.label)
        out._union = None
        return out

    def member_cell_intervals(self, s, include_current=True):
        out = {}
        for c, b in self.events[s].items():
            out.setdefault(c, []).append((b, b + self.T))
        if include_current and self.R > 0:
            for c in self.current:
                out.setdefault(c, []).append((F(0), self.R))
        return {k: sorted(set(v)) for k, v in out.items()}

    @property
    def cell_intervals(self):
        """Union over members: graph cell -> sorted exact half-open activity intervals (RoadBoundModel layout)."""
        if self._union is None:
            out = {}
            for ev in self.events:
                for c, b in ev.items():
                    out.setdefault(c, []).append((b, b + self.T))
            if self.R > 0:
                for c in self.current:
                    out.setdefault(c, []).append((F(0), self.R))
            self._union = {k: sorted(set(v)) for k, v in out.items()}
        return self._union

    def new_ignition_counts(self):
        return [len(ev) for ev in self.events]
