"""Statistics on recorded unit sessions shared by tests E (vehicle) and F (housing).

Clocks: Pi-side quantities (heartbeat gaps, reading gaps, completeness) use the Pi `t_mono` of each message;
link quantities use the laptop receipt time `t_rx` from recordkit's rx.jsonl.gz. A Pi reboot restarts t_mono, so a
session_id change or a backwards t_mono step is reported as a reboot and the statistics are split there.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

STALE_S = {"thermal": 1.0, "radar": 1.0, "tc_plate": 1.0, "tc_housing": 1.0, "tc_air": 1.0, "imu": 0.5,
           "gnss": 2.0, "pi": 3.0}                           # DESIGN.md section 3 per-sensor stale_s (Pi side)
NOMINAL_HZ = {"thermal": 25.0, "radar": 10.0, "tc_plate": 10.0, "tc_housing": 10.0, "tc_air": 10.0, "imu": 20.0,
              "gnss": None, "pi": 1.0}                       # gnss: the measured median rate is used
THROTTLE_BITS = {0: "under-voltage now", 1: "ARM frequency capped now", 2: "throttled now",
                 3: "soft temperature limit now", 16: "under-voltage occurred", 17: "frequency capping occurred",
                 18: "throttling occurred", 19: "soft temperature limit occurred"}
EARTH_R = 6371008.8


# ---------------------------------------------------------------------------------------------- link
def link_dropouts(rx: List[dict], gap_s: float = 1.0) -> Dict[str, object]:
    """Dropouts = gaps between consecutive received messages (laptop t_rx) longer than gap_s. A healthy link
    carries several heartbeats every 0.5 s, so gaps above 1 s mean nothing arrived. Disconnect lines are counted
    separately. Returns count, durations (s), longest, total, and the start offsets from the first message."""
    msgs = sorted(float(x["t_rx"]) for x in rx if "type" in x and x.get("type") != "bad")
    disc = [x for x in rx if x.get("link") == "disconnect"]
    if len(msgs) < 2:
        return {"n_messages": len(msgs), "count": 0, "durations_s": [], "starts_s": [], "longest_s": float("nan"),
                "total_s": 0.0, "span_s": 0.0, "disconnects": len(disc), "max_gap_s": float("nan")}
    t = np.asarray(msgs)
    g = np.diff(t)
    idx = np.flatnonzero(g > gap_s)
    return {"n_messages": int(t.size), "count": int(idx.size), "durations_s": [float(g[i]) for i in idx],
            "starts_s": [float(t[i] - t[0]) for i in idx], "longest_s": float(g[idx].max()) if idx.size else 0.0,
            "total_s": float(g[idx].sum()), "span_s": float(t[-1] - t[0]), "disconnects": len(disc),
            "max_gap_s": float(g.max())}


# ---------------------------------------------------------------------------------------------- Pi side
def segments_by_boot(msgs: List[dict]) -> List[List[dict]]:
    """Split a time-ordered message list where the session_id changes or t_mono steps backwards (reboot)."""
    out: List[List[dict]] = []
    cur: List[dict] = []
    for m in msgs:
        if cur and (m["session_id"] != cur[-1]["session_id"] or m["t_mono"] < cur[-1]["t_mono"] - 1.0):
            out.append(cur)
            cur = []
        cur.append(m)
    if cur:
        out.append(cur)
    return out


def gaps(times: Sequence[float], limit_s: float) -> List[Dict[str, float]]:
    t = np.sort(np.asarray(times, dtype=float))
    if t.size < 2:
        return []
    d = np.diff(t)
    return [{"start": float(t[i]), "end": float(t[i + 1]), "gap_s": float(d[i])} for i in np.flatnonzero(d > limit_s)]


def heartbeat_gaps(hbs: List[dict], limit_s: float = 2.0, span: Optional[tuple] = None) -> List[Dict[str, float]]:
    """Gaps between heartbeats (Pi t_mono) above limit_s; with `span` also a missing start/end of the record."""
    t = [float(m["t_mono"]) for m in hbs]
    out = gaps(t, limit_s)
    if span is not None and t:
        if t[0] - span[0] > limit_s:
            out.insert(0, {"start": span[0], "end": t[0], "gap_s": t[0] - span[0]})
        if span[1] - t[-1] > limit_s:
            out.append({"start": t[-1], "end": span[1], "gap_s": span[1] - t[-1]})
    elif span is not None and not t:
        out.append({"start": span[0], "end": span[1], "gap_s": span[1] - span[0]})
    return out


def silent_stops(readings: List[dict], hbs: List[dict], stale_s: float, hb_alive_s: float = 1.0
                 ) -> List[Dict[str, float]]:
    """Reading gaps longer than stale_s during which the heartbeat stream stayed alive (no heartbeat gap longer
    than hb_alive_s across the reading gap) and every heartbeat said "ok": the sensor stopped but its heartbeat did
    not admit it (a HOUSING.md test F fail condition). A gap where the heartbeats are missing too is a link or unit
    gap, reported by heartbeat_gaps / link_dropouts instead."""
    out = []
    ht = np.array([float(h["t_mono"]) for h in hbs])
    hs = [h["status"] for h in hbs]
    for g in gaps([m["t_mono"] for m in readings], stale_s):
        a, b = g["start"] + stale_s, g["end"]
        sel = np.flatnonzero((ht > a) & (ht < b))
        inside = np.concatenate([[g["start"]], ht[(ht >= g["start"]) & (ht <= g["end"])], [g["end"]]])
        alive = float(np.max(np.diff(inside))) <= hb_alive_s
        if sel.size and alive and all(hs[i] == "ok" for i in sel):
            out.append(g)
    return out


def completeness(sensor: str, readings: List[dict], hbs: List[dict], span: tuple,
                 nominal_hz: Optional[float] = None) -> Dict[str, object]:
    """Per-sensor data completeness over `span` (Pi t_mono start, end)."""
    dur = max(span[1] - span[0], 1e-9)
    t = np.array([float(m["t_mono"]) for m in readings])
    row: Dict[str, object] = {"sensor": sensor, "n_readings": int(t.size), "span_s": dur}
    if t.size >= 2:
        dt = np.diff(np.sort(t))
        med = float(np.median(dt))
        row["median_rate_hz"] = 1.0 / med if med > 0 else float("nan")
    else:
        row["median_rate_hz"] = float("nan")
    nom = nominal_hz if nominal_hz else NOMINAL_HZ.get(sensor) or row["median_rate_hz"]
    row["nominal_hz"] = nom
    row["completeness_pct"] = 100.0 * t.size / (dur * nom) if nom and math.isfinite(nom) else float("nan")
    seqs = np.array(sorted(int(m["seq"]) for m in readings))
    row["seq_missing"] = int(np.sum(np.clip(np.diff(seqs) - 1, 0, None))) if seqs.size > 1 else 0
    st = STALE_S.get(sensor, 2.0)
    gl = gaps(np.concatenate([[span[0]], t, [span[1]]]) if t.size else [span[0], span[1]], st)
    row["gaps_over_stale"] = len(gl)
    row["stale_s"] = st
    row["time_stale_s"] = float(sum(g["gap_s"] - st for g in gl))
    row["fresh_time_pct"] = 100.0 * (1.0 - row["time_stale_s"] / dur)
    row["longest_gap_s"] = float(max([g["gap_s"] for g in gl], default=0.0))
    status = [h["status"] for h in hbs]
    row["heartbeats"] = len(status)
    row["hb_not_ok_pct"] = 100.0 * sum(1 for s in status if s != "ok") / len(status) if status else float("nan")
    bad = [m for m in readings if m["data"].get("fault")]
    row["fault_readings"] = len(bad)
    return row


# ---------------------------------------------------------------------------------------------- power / temps
def throttle_bits(hex_str: Optional[str]) -> List[int]:
    if not hex_str:
        return []
    try:
        v = int(str(hex_str), 16)
    except ValueError:
        return []
    return [b for b in THROTTLE_BITS if v & (1 << b)]


def power_summary(pi_readings: List[dict]) -> Dict[str, object]:
    t = np.array([float(m["t_mono"]) for m in pi_readings])
    uv = [m["data"].get("under_voltage_now") for m in pi_readings]
    events, in_ev, start, total = [], False, None, 0.0
    for i, v in enumerate(uv):
        if v and not in_ev:
            in_ev, start = True, t[i]
        elif not v and in_ev:
            in_ev = False
            events.append({"start": float(start), "end": float(t[i]), "duration_s": float(t[i] - start)})
    if in_ev:
        events.append({"start": float(start), "end": float(t[-1]), "duration_s": float(t[-1] - start),
                       "open": True})
    bits_now: Dict[int, int] = {}
    last_bits: List[int] = []
    for m in pi_readings:
        bs = throttle_bits(m["data"].get("throttled_hex"))
        if bs or m["data"].get("throttled_hex"):
            last_bits = bs
        for b in bs:
            if b < 16:
                bits_now[b] = bits_now.get(b, 0) + 1
    v = [m["data"].get("input_v") for m in pi_readings if m["data"].get("input_v") is not None]
    return {"n_readings": len(pi_readings), "under_voltage_events": events, "n_under_voltage_events": len(events),
            "under_voltage_s": float(sum(e["duration_s"] for e in events)),
            "readings_with_bit": {THROTTLE_BITS[b]: n for b, n in sorted(bits_now.items())},
            "occurred_since_boot": [THROTTLE_BITS[b] for b in last_bits if b >= 16],
            "unknown_throttle_readings": sum(1 for m in pi_readings if m["data"].get("throttled_hex") is None),
            "input_v_min": min(v) if v else None, "input_v_max": max(v) if v else None}


def local_xy(lat, lon, lat0: float, lon0: float):
    """Equirectangular local metres around (lat0, lon0): adequate for a 30-minute drive (km scale)."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    x = np.radians(lon - lon0) * math.cos(math.radians(lat0)) * EARTH_R
    y = np.radians(lat - lat0) * EARTH_R
    return x, y
