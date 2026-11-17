"""Test D analysis: time from a fault (operator event mark) to a CLOSED verdict attributable to that fault.

Inputs, either:
- a run directory written by d_failsafe_run.py: states.jsonl.gz (one line per State pushed by the crossing app on
  ws://127.0.0.1:8781/ws, with this laptop's receipt time t_rx) and marks.jsonl (fault_inject / fault_restore marks
  on the same clock); or
- a research-log session directory of the crossing app (DESIGN.md section 11: verdicts.csv + health.csv) together
  with a marks file (the marks.jsonl of a d_failsafe_run session, or a CSV t,fault). Both must use this laptop's
  time.monotonic() (system-wide on macOS, so separate processes share it). Columns follow
  apps/crossing/research_log/README.md (verdicts.csv: rx_mono, state, reasons ";"-joined; health.csv: rx_mono,
  link_up, <sensor>_fresh) and are matched loosely (a long format t, sensor, fresh is accepted too).

Per fault:
- pre: the last State (with a verdict) before the fault time, at most PRE_MAX_AGE_S = 1.0 s old. Without one the
  row is NOT_ATTRIBUTABLE (fail closed: nothing to compare with).
- Attribution is by CHANGE, never by presence, and by exact reason codes, never by substrings. A State is
  attributable to the fault when its verdict is CLOSED and, compared with pre, one of these appeared: (sensor
  faults) the sensor's health `fresh` went False, or one of the codes crossing/decision.py emits for that sensor
  (SENSOR_NOT_FRESH:<s>, SENSOR_FAULT:<s>, INPUT_TOO_OLD:<s>, INPUT_TIME_MISSING:<s>, INPUT_TIME_IN_FUTURE:<s>,
  VALUE_INVALID:input_time.<s>); (link faults) health link went False, or the code LINK_DOWN. Reasons that are
  normal on a bench (RADAR_UNKNOWN, GNSS_NO_FIX, FLAME_*, NO_FLAME, ...) never count. A sensor fault is not
  attributed while the link is down (a link loss marks every sensor not fresh).
- If pre already shows the cause (sensor not fresh, link down, or a matching code), the row is NOT_ATTRIBUTABLE: the
  fault cannot be timed (the mark was late, or the sensor was already down). Never PASS.
- time_to_closed = t_closed - t_fault. pre_verdict = verdict of pre. If it was already CLOSED (normal on a bench
  with no flame), the time is to the fault-attributed CLOSED, i.e. to the moment the app knew. Stated per row.
- PASS if time_to_closed <= 2.0 s (the user's criterion). FAIL if longer or if no attributable CLOSED arrives
  within the timeout. Also reported: time until the faulted sensor shows not fresh (same change rule), and
  recovery time after the restore mark (sensor fresh again), which has no pass criterion here.
- Any CROSS FAST / SPRAY / REOPENED verdict after the fault-attributed CLOSED and before the restore mark is a hard
  failure (go verdicts before detection are the detection latency, which the time criterion covers).
- thermal_freeze: the fault time is taken from the DATA, never from the operator's NOW (the Pi's sim session
  starts the freeze at its own session time T, which the operator cannot see). Source, in order: an `event_t` on
  the mark; else the thermal frames the laptop received (the d_failsafe_run `--pi` copy in <run>/pi, or the
  research log's wire.jsonl.gz): the receipt time of the last frame whose raw pixels differ from the frame after
  it, where that frame starts a run of identical frames (the freeze onset nearest the mark). That frame is the one
  the app's own freeze timer starts from, so the time is an upper bound on the latency (true onset is up to one
  wire period, 0.25 s at 4 Hz, later). With neither source the row is NOT_MEASURED ("fault time unknown, not a
  measurement") and is not scored.

Timing error: for the unplug / open / Wi-Fi / power faults the mark is the "NOW" of a printed countdown; the
operator's own reaction adds a few tenths of a second either way (not measured). States arrive at 5 Hz, so the
resolution is 0.2 s.
Expected by design (DESIGN.md section 5 as built 2026-11-17, not measured): a Wi-Fi drop or a power pull is noticed
when no message at all has arrived for silence_s = 1.5 s (the Pi sends heartbeats every 0.5 s), i.e. about
1.4-1.7 s after the fault with the 5 Hz tick; frozen thermal data (identical raw pixels; how the Pi's sim mode with
`--freeze thermal@T` freezes) after freeze_s = 1.0 s of unchanged values, i.e. 0.8-1.2 s after the fault (the
synthetic replay test in tests/test_pipeline.py measured 0.80-1.15 s, worst case <= 1.5 s required). Earlier
builds used stale_s = 2.0 s / freeze_s = 2.0 s for these and could not meet the 2 s criterion. Thermocouple, IMU
and GNSS value freezes (seq still advancing) keep longer windows (5 / 2 / 5 s, values can legitimately repeat) and
are not among the faults here; a Pi-side freeze (repeated seq or t_mono) is caught at the next message.
Not among the faults (stated in protocols/D_failsafe.md, known limits): a Pi health fault (under-voltage,
throttling) although `pi` is a required input since decision D1.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common  # noqa: E402
from field_tests.recordkit import read_marks  # noqa: E402

PASS_S = 2.0
PRE_MAX_AGE_S = 1.0          # the State compared against must be this recent before the fault time
SENSORS = ("thermal", "radar", "tc_plate", "tc_housing", "tc_air", "imu", "gnss", "pi")
LINK = "link"
GO_STATES = ("CROSS FAST", "CROSS_FAST", "SPRAY THEN RE-CHECK", "SPRAY_THEN_RECHECK", "SPRAY", "REOPENED")


@dataclass(frozen=True)
class Fault:
    id: str
    sensors: tuple               # sensors whose loss this fault causes; ("link",) for link-level faults
    inject: str                  # instruction at "NOW"
    restore: str
    prepare: str = ""
    expected: str = ""           # mechanism and the expected detection time (design, not measured)


FAULTS: Dict[str, Fault] = {f.id: f for f in (
    Fault("thermal_unplug", ("thermal",), "UNPLUG the TC001 USB cable", "Plug the TC001 back in",
          "Hand on the TC001 USB plug", "driver read error -> no_device heartbeat at once; expect < 1 s"),
    Fault("radar_unplug", ("radar",), "UNPLUG the radar EVM USB cable", "Plug the radar back in (config resend)",
          "Hand on the radar USB plug", "driver read error -> no_device heartbeat; expect < 1 s"),
    Fault("gnss_unplug", ("gnss",), "UNPLUG the GNSS USB cable", "Plug the GNSS back in",
          "Hand on the GNSS USB plug", "driver read error -> no_device; expect < 1 s (gnss stale_s 2.0 if not)"),
    Fault("imu_disconnect", ("imu",), "PULL the BNO055 SDA lead", "Reconnect the BNO055 SDA lead",
          "Hand on the BNO055 SDA lead (Pi powered; 3.3 V logic only)", "I2C error on next read; expect < 1 s"),
    Fault("tc_plate_open", ("tc_plate",), "UNPLUG the plate thermocouple connector", "Reconnect it",
          "Hand on the plate thermocouple mini-connector", "MAX31855 'open' fault on next 10 Hz read; expect < 0.5 s"),
    Fault("tc_air_open", ("tc_air",), "UNPLUG the air thermocouple connector", "Reconnect it",
          "Hand on the air thermocouple mini-connector", "MAX31855 'open' fault; expect < 0.5 s"),
    Fault("tc_housing_open", ("tc_housing",), "UNPLUG the housing thermocouple connector", "Reconnect it",
          "Hand on the housing thermocouple mini-connector", "MAX31855 'open' fault; expect < 0.5 s"),
    Fault("wifi_drop", (LINK,), "TURN OFF the laptop Wi-Fi", "Turn the laptop Wi-Fi back on and rejoin the hotspot",
          "Pointer on the Wi-Fi menu", "no messages; link silence_s = 1.5 s -> expect 1.4-1.7 s"),
    Fault("pi_power", (LINK,), "PULL the unit's 12 V plug", "Reconnect 12 V (Pi boots, about 30-60 s)",
          "Hand on the 12 V plug", "link silent; silence_s = 1.5 s -> expect 1.4-1.7 s"),
    Fault("thermal_freeze", ("thermal",), "(sim mode on the Pi) thermal freeze begins near NOW",
          "Stop the sim session", "Pi running `python -m wfgvu --sim <session made with --freeze thermal@T>` and "
          "this script started WITH --pi (the fault time is taken from the received thermal frames, not from NOW; "
          "NOW can be off from T by seconds). Without the --pi copy (or a research log) the row is NOT_MEASURED",
          "identical thermal pixels for freeze_s = 1.0 s -> expect 0.8-1.3 s (worst case <= 1.5 s)"),
)}


# ---------------------------------------------------------------------------------------------- state parsing
def _first(d: dict, keys: Sequence[str]):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return None


def _truthy(v) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "ok", "fresh", "connected", "up"):
        return True
    if s in ("false", "0", "no", "stale", "down", "disconnected", "lost"):
        return False
    return None


def summarize_state(state: dict) -> dict:
    """Reduce a crossing-app State (DESIGN.md section 9) to {verdict, reasons, link, fresh{sensor}, sim}.
    The app (crossing/pipeline.py) sends verdict = {"state", "reasons", ...} and health = {"link_up", "link_reason",
    "sensors": {sensor: {"fresh", "reason", ...}}}; other shapes are accepted too (verdict as str, health as
    {sensor: {fresh}}, link as health.link / state.link / state.link_connected, bool or {"connected": bool})."""
    v = state.get("verdict")
    if isinstance(v, dict):
        verdict = _first(v, ("state", "verdict", "status"))
        reasons = v.get("reasons") or []
    else:
        verdict, reasons = v, state.get("reasons") or []
    health = state.get("health") or {}
    sensors = health.get("sensors") if isinstance(health.get("sensors"), dict) else health
    fresh = {}
    for s in SENSORS:
        h = sensors.get(s) if isinstance(sensors, dict) else None
        if isinstance(h, dict):
            fresh[s] = _truthy(h.get("fresh"))
        elif h is not None:
            fresh[s] = _truthy(h)
    link = _first(health, ("link_up", "link", "link_connected", "connected")) if isinstance(health, dict) else None
    if link is None:
        link = _first(state, ("link_up", "link", "link_connected"))
    if isinstance(link, dict):
        link = _first(link, ("connected", "up", "ok"))
    return {"verdict": None if verdict is None else str(verdict).upper().replace("_", " "),
            "reasons": [str(r) for r in (reasons if isinstance(reasons, list) else [reasons])],
            "link": _truthy(link), "fresh": fresh, "sim": bool(state.get("sim", False))}


def fault_codes(sensors: Sequence[str]) -> frozenset:
    """Exact verdict reason codes (crossing/decision.py `_sensor_checks` and `_decide`) that name this fault."""
    if LINK in sensors:
        return frozenset({"LINK_DOWN"})
    out = set()
    for s in sensors:
        out |= {"SENSOR_NOT_FRESH:%s" % s, "SENSOR_FAULT:%s" % s, "INPUT_TOO_OLD:%s" % s,
                "INPUT_TIME_MISSING:%s" % s, "INPUT_TIME_IN_FUTURE:%s" % s, "VALUE_INVALID:input_time.%s" % s}
    return frozenset(out)


def reason_codes(st: Optional[dict]) -> set:
    """Verdict reasons as a set of exact codes (each entry also split on ';', as the research log joins them)."""
    out = set()
    for r in (st or {}).get("reasons") or []:
        for part in str(r).split(";"):
            part = part.strip()
            if part:
                out.add(part)
    return out


def _causes(st: Optional[dict], sensors: Sequence[str]) -> set:
    """The fault's causes visible in one State: ('fresh', s), ('link',) or ('code', c). Presence only."""
    if not st:
        return set()
    out = set()
    codes = reason_codes(st) & fault_codes(sensors)
    if LINK in sensors:
        if st.get("link") is False:
            out.add(("link",))
    else:
        if st.get("link") is False:          # a link loss marks every sensor not fresh: not this sensor's fault
            return set()
        fr = st.get("fresh") or {}
        out |= {("fresh", s) for s in sensors if fr.get(s) is False}
    out |= {("code", c) for c in codes}
    return out


def cause_before(pre: Optional[dict], sensors: Sequence[str]) -> bool:
    """True when the State before the fault already shows its cause (then the fault cannot be timed)."""
    return bool(_causes(pre, sensors))


def attributable(st: dict, sensors: Sequence[str], pre: Optional[dict] = None) -> bool:
    """CLOSED and a cause of the fault APPEARED since `pre` (the last State before the fault; see the module
    docstring). Exact codes only. pre=None means nothing to compare with: False (fail closed, NOT_ATTRIBUTABLE)."""
    if pre is None or st.get("verdict") != "CLOSED":
        return False
    return bool(_causes(st, sensors) - _causes(pre, sensors))


def sensor_down(st: dict, sensors: Sequence[str], pre: Optional[dict] = None) -> bool:
    """The fault's sensor (or the link) shows not fresh / down now and did not in `pre`. pre=None: False."""
    if pre is None:
        return False
    now = {c for c in _causes(st, sensors) if c[0] != "code"}
    return bool(now - _causes(pre, sensors))


def sensor_up(st: dict, sensors: Sequence[str]) -> bool:
    fr = st.get("fresh") or {}
    if LINK in sensors:
        return st.get("link") is not False and bool(fr) and any(v is True for v in fr.values())
    return st.get("link") is not False and all(fr.get(s) is True for s in sensors)


# ---------------------------------------------------------------------------------------------- loading
def load_states(run_dir) -> List[dict]:
    p = Path(run_dir) / "states.jsonl.gz"
    out = []
    if not p.exists():
        return out
    try:
        with gzip.open(p, "rt") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (EOFError, OSError):
        pass
    out.sort(key=lambda s: s["t_rx"])
    return out


def _col(row: dict, names) -> Optional[str]:
    low = {k.lower(): k for k in row}
    for n in names:
        if n in low:
            return low[n]
    return None


def load_research_log(log_dir) -> List[dict]:
    """Timeline from research-log verdicts.csv + health.csv (columns matched loosely, see module docstring)."""
    d = Path(log_dir)
    vpath, hpath = d / "verdicts.csv", d / "health.csv"
    if not vpath.exists():
        raise FileNotFoundError("research log has no verdicts.csv: %s" % d)
    tnames = ("rx_mono", "t_mono", "laptop_mono", "t", "mono", "t_s", "time_mono")
    events: List[dict] = []
    with open(vpath, newline="") as fh:
        for row in csv.DictReader(fh):
            tc, vc = _col(row, tnames), _col(row, ("state", "verdict", "effective_state", "verdict_state"))
            if tc is None or vc is None:
                raise ValueError("verdicts.csv needs a time column %s and a state column" % (tnames,))
            rc = _col(row, ("reasons", "reason"))
            reasons = row.get(rc, "") if rc else ""
            try:
                reasons = json.loads(reasons) if reasons.startswith("[") else [r for r in reasons.split(";") if r]
            except json.JSONDecodeError:
                reasons = [reasons]
            events.append({"t_rx": float(row[tc]), "kind": "verdict", "verdict": row[vc], "reasons": reasons})
    if hpath.exists():
        with open(hpath, newline="") as fh:
            for row in csv.DictReader(fh):
                tc = _col(row, tnames)
                if tc is None:
                    continue
                sc, fc = _col(row, ("sensor",)), _col(row, ("fresh",))
                lc = _col(row, ("link_up", "link", "link_connected"))
                ev = {"t_rx": float(row[tc]), "kind": "health", "fresh": {}, "link": None}
                if sc and fc:
                    ev["fresh"][row[sc]] = _truthy(row[fc])
                for s in SENSORS:
                    c = _col(row, (s + "_fresh", s))
                    if c and not sc:
                        ev["fresh"][s] = _truthy(row[c])
                if lc:
                    ev["link"] = _truthy(row[lc])
                events.append(ev)
    events.sort(key=lambda e: e["t_rx"])
    states, cur = [], {"verdict": None, "reasons": [], "link": None, "fresh": {}, "sim": False}
    for e in events:
        cur = dict(cur, fresh=dict(cur["fresh"]))
        if e["kind"] == "verdict":
            cur["verdict"], cur["reasons"] = str(e["verdict"]).upper().replace("_", " "), e["reasons"]
        else:
            cur["fresh"].update({k: v for k, v in e["fresh"].items() if v is not None})
            if e["link"] is not None:
                cur["link"] = e["link"]
        states.append(dict(cur, t_rx=e["t_rx"]))
    return states


def load_marks_any(path) -> List[dict]:
    p = Path(path)
    if p.is_dir():
        return read_marks(p)
    if p.suffix == ".csv":
        out = []
        with open(p, newline="") as fh:
            for row in csv.DictReader(fh):
                out.append({"t_rx": float(row["t"]), "kind": row.get("kind", "fault_inject"), "fault": row["fault"]})
        return out
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


# ---------------------------------------------------------------------------------------------- thermal frames
def load_thermal_frames(src) -> List[tuple]:
    """(t_rx, pix) of every thermal reading the laptop received, sorted by t_rx. Reads a research-log
    wire.jsonl.gz ({"rx", "msg"}) or a recordkit copy (rx.jsonl.gz receipt times joined to thermal.jsonl.gz by
    (seq, t_mono)). Missing or unreadable files give []."""
    d = Path(src) if src is not None else None
    if d is None or not d.is_dir():
        return []
    out: List[tuple] = []
    wire = d / "wire.jsonl.gz"
    try:
        if wire.exists():
            with gzip.open(wire, "rt") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    m = r.get("msg") if isinstance(r, dict) else None
                    if isinstance(m, dict) and m.get("type") == "reading" and m.get("sensor") == "thermal" \
                            and isinstance(m.get("data"), dict) and m["data"].get("pix") is not None:
                        out.append((float(r["rx"]), m["data"]["pix"]))
        elif (d / "rx.jsonl.gz").exists() and (d / "thermal.jsonl.gz").exists():
            rx = {}
            with gzip.open(d / "rx.jsonl.gz", "rt") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("type") == "reading" and r.get("sensor") == "thermal":
                        rx[(r.get("seq"), r.get("t_mono"))] = float(r["t_rx"])
            with gzip.open(d / "thermal.jsonl.gz", "rt") as fh:
                for line in fh:
                    try:
                        m = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if m.get("type") != "reading" or not isinstance(m.get("data"), dict):
                        continue
                    t = rx.get((m.get("seq"), m.get("t_mono")))
                    if t is not None and m["data"].get("pix") is not None:
                        out.append((t, m["data"]["pix"]))
    except (EOFError, OSError):
        pass                                   # truncated tail: keep what was read
    out.sort(key=lambda x: x[0])
    return out


def freeze_onsets(frames: Sequence[tuple]) -> List[float]:
    """Receipt times of the last frame before each run of identical frames (the frame that is repeated), where at
    least one earlier frame differed (so the stream was demonstrably changing before)."""
    out = []
    for i in range(2, len(frames)):
        if frames[i][1] == frames[i - 1][1] and frames[i - 1][1] != frames[i - 2][1]:
            out.append(float(frames[i - 1][0]))
    return out


# ---------------------------------------------------------------------------------------------- analysis
def evaluate(states: List[dict], marks: List[dict], timeout_s: float = 10.0, recover_timeout_s: float = 120.0,
             thermal_frames: Optional[Sequence[tuple]] = None) -> List[dict]:
    states = [s for s in states if s.get("verdict") is not None or s.get("app_link") is None]
    t = np.array([s["t_rx"] for s in states], dtype=float)
    vt = [s for s in states if s.get("verdict") is not None]          # States that carry a verdict
    tv = np.array([s["t_rx"] for s in vt], dtype=float)
    injects = [m for m in marks if m.get("kind") == "fault_inject"]
    onsets = freeze_onsets(thermal_frames or [])
    rows = []
    for i, m in enumerate(injects):
        f = FAULTS.get(m.get("fault"))
        sensors = tuple(m.get("sensors") or (f.sensors if f else ()))
        t_now = float(m["t_rx"])
        restore = next((x for x in marks if x.get("kind") == "fault_restore" and x.get("fault") == m.get("fault")
                        and x["t_rx"] > t_now), None)
        t_rest = float(restore["t_rx"]) if restore else None
        nxt = injects[i + 1]["t_rx"] if i + 1 < len(injects) else math.inf
        prev_end = max([float(x["t_rx"]) for x in marks if x.get("kind") == "fault_restore"
                        and float(x["t_rx"]) < t_now] + [-math.inf])
        row = {"fault": m.get("fault"), "sensors": "+".join(sensors), "t_mark": t_now,
               "expected": f.expected if f else "", "note": m.get("note", ""), "fault_time_source": "operator NOW"}
        tm = t_now
        if m.get("event_t") is not None:
            tm, row["fault_time_source"] = float(m["event_t"]), "event_t on the mark"
        elif m.get("fault") == "thermal_freeze":
            cand = [o for o in onsets if prev_end < o < (t_rest if t_rest else nxt)]
            if cand:
                tm = min(cand, key=lambda o: abs(o - t_now))
                row["fault_time_source"] = "thermal frames (last frame before identical repeats)"
            else:
                tm = None
        row["t_fault"] = tm
        row["mark_minus_fault_s"] = None if tm is None else t_now - tm
        if tm is None:
            row.update(pre_verdict=None, pre_state_age_s=None, time_to_closed_s=None, time_to_not_fresh_s=None,
                       go_verdicts_during_fault=0, result="NOT_MEASURED",
                       why="fault time unknown, not a measurement (no event_t and no received thermal frames with "
                           "a freeze onset; run d_failsafe_run with --pi)", fault_time_source="none")
            rows.append(row)
            continue
        kv = int(np.searchsorted(tv, tm, side="left"))
        pre = vt[kv - 1] if kv > 0 else None
        if pre is not None and tm - pre["t_rx"] > PRE_MAX_AGE_S:
            pre_note = "last State before the fault is %.1f s old (> %.1f s)" % (tm - pre["t_rx"], PRE_MAX_AGE_S)
            row["pre_verdict"], row["pre_state_age_s"] = pre["verdict"], tm - pre["t_rx"]
            pre = None
        else:
            pre_note = "no State before the fault"
            row["pre_verdict"] = pre["verdict"] if pre else None
            row["pre_state_age_s"] = tm - pre["t_rx"] if pre else None
        k0 = int(np.searchsorted(t, tm, side="left"))
        window_end = min(tm + timeout_s, t_rest if t_rest else math.inf, nxt)
        t_closed = t_down = None
        go = []
        for s in states[k0:]:
            if s["t_rx"] > (t_rest if t_rest else nxt):
                break
            if t_closed is not None and s.get("verdict") in GO_STATES:
                go.append(s["verdict"])          # a go verdict after the app had noticed the fault
            if s["t_rx"] > window_end:
                continue
            if t_down is None and sensor_down(s, sensors, pre):
                t_down = s["t_rx"]
            if t_closed is None and attributable(s, sensors, pre):
                t_closed = s["t_rx"]
        row["time_to_closed_s"] = None if t_closed is None else t_closed - tm
        row["time_to_not_fresh_s"] = None if t_down is None else t_down - tm
        row["go_verdicts_during_fault"] = len(go)
        if pre is None:
            row["result"] = "NOT_ATTRIBUTABLE"
            row["why"] = "%s: nothing to compare with, the fault cannot be timed" % pre_note
            row["time_to_closed_s"] = row["time_to_not_fresh_s"] = None
        elif cause_before(pre, sensors):
            row["result"] = "NOT_ATTRIBUTABLE"
            row["why"] = "the cause was already visible before the fault time (%s): mark late or sensor already " \
                "down; the fault cannot be timed" % ", ".join(sorted(":".join(c) for c in _causes(pre, sensors)))
            row["time_to_closed_s"] = row["time_to_not_fresh_s"] = None
        elif t_closed is None:
            row["result"] = "FAIL"
            row["why"] = "no CLOSED attributable to the fault within %.0f s" % (window_end - tm)
        elif go:
            row["result"] = "FAIL"
            row["why"] = "%d go verdict(s) (%s) after the fault-attributed CLOSED, before restore" % (len(go), go[0])
        elif row["time_to_closed_s"] <= PASS_S:
            row["result"] = "PASS"
            row["why"] = ""
        else:
            row["result"] = "FAIL"
            row["why"] = "%.2f s > %.1f s" % (row["time_to_closed_s"], PASS_S)
        if pre is not None and pre["verdict"] == "CLOSED":
            row["why"] = (row["why"] + "; " if row["why"] else "") + "verdict was already CLOSED before the fault: " \
                "time is to the fault-attributed CLOSED"
        if row["fault_time_source"].startswith("thermal frames"):
            row["why"] = (row["why"] + "; " if row["why"] else "") + "fault time from received thermal frames " \
                "(upper bound on the latency, <= one wire period)"
        if t_rest is not None:
            kr = int(np.searchsorted(t, t_rest))
            up = next((s["t_rx"] for s in states[kr:] if s["t_rx"] <= t_rest + recover_timeout_s
                       and sensor_up(s, sensors)), None)
            row["recovery_s"] = None if up is None else up - t_rest
        rows.append(row)
    return rows


def analyse(out, run_dir=None, research_log=None, marks=None, timeout_s: float = 10.0) -> dict:
    out = common.out_dir(out)
    if run_dir is not None:
        states = load_states(run_dir)
        mk = read_marks(run_dir) if marks is None else load_marks_any(marks)
        trial = json.loads((Path(run_dir) / "trial.json").read_text()) if (Path(run_dir) / "trial.json").exists() \
            else {}
        source = "live app states (%s)" % Path(run_dir).name
        frames = load_thermal_frames(Path(run_dir) / "pi")
    elif research_log is not None:
        if marks is None:
            raise SystemExit("--marks is required with --research-log")
        states = load_research_log(research_log)
        mk = load_marks_any(marks)
        trial = {}
        source = "research log (%s)" % Path(research_log).name
        frames = load_thermal_frames(research_log)
    else:
        raise SystemExit("give --run DIR or --research-log DIR --marks FILE")
    sim = common.is_simulated(trial.get("simulated"), any(s.get("sim") for s in states))
    rows = evaluate(states, mk, timeout_s, thermal_frames=frames)
    cols = ["fault", "sensors", "pre_verdict", "time_to_closed_s", "time_to_not_fresh_s", "result", "why",
            "recovery_s", "go_verdicts_during_fault", "expected", "t_mark", "t_fault", "fault_time_source",
            "mark_minus_fault_s", "note"]
    common.write_csv(out / "D_faults.csv", rows, cols, sim)
    _plot(out / "D_time_to_closed.png", rows, sim)
    n_pass = sum(1 for r in rows if r["result"] == "PASS")
    n_na = sum(1 for r in rows if r["result"] == "NOT_ATTRIBUTABLE")
    n_nm = sum(1 for r in rows if r["result"] == "NOT_MEASURED")
    body = ["Source: %s. Criterion: CLOSED attributable to the fault (a matching reason code or health flag that "
            "APPEARED after the fault time) within %.1f s of the fault time. %d of %d faults passed; %d not "
            "attributable, %d not measured (neither is a pass)." % (source, PASS_S, n_pass, len(rows), n_na, n_nm),
            "",
            common.md_table(rows, ["fault", "pre_verdict", "time_to_closed_s", "time_to_not_fresh_s", "result",
                                   "why", "recovery_s"],
                            ["fault", "verdict before", "to CLOSED (s)", "to not fresh (s)", "result", "why",
                             "recovery (s)"], nd=2), "",
            "Marks are the NOW of a countdown; operator timing error (a few tenths of a second) is not measured. "
            "thermal_freeze is timed from the received thermal frames, never from NOW (NOW can be off from the "
            "sim session's freeze by seconds); without them that row is NOT_MEASURED. "
            "States arrive at 5 Hz (0.2 s resolution).",
            "Expected by design (not measured): link loss and power loss after silence_s = 1.5 s (1.4-1.7 s), frozen "
            "thermal data after freeze_s = 1.0 s of identical pixels (0.8-1.3 s); every row is reported as measured.",
            "Files: D_faults.csv, D_time_to_closed.png."]
    md = common.md_snippet("Test D - fail-safe: fault to CLOSED", sim, body)
    (out / "D_results.md").write_text(md)
    return {"simulated": sim, "faults": rows, "markdown": md}


def _plot(path, rows, sim):
    plt = common.pyplot()
    fig, ax = plt.subplots(figsize=(7.5, 0.45 * max(len(rows), 3) + 1.6))
    y = np.arange(len(rows))
    vals = [r["time_to_closed_s"] if r["time_to_closed_s"] is not None else np.nan for r in rows]
    cols = ["tab:green" if r["result"] == "PASS" else "tab:gray" if r["result"] in ("NOT_MEASURED", "NOT_ATTRIBUTABLE")
            else "tab:red" for r in rows]
    ax.barh(y, np.nan_to_num(vals, nan=0.0), color=cols)
    for yi, v, r in zip(y, vals, rows):
        lab = "%.2f s" % v if np.isfinite(v) else ("no CLOSED" if r["result"] == "FAIL" else "not timed")
        ax.text((0 if not np.isfinite(v) else v) + 0.05, yi, lab + "  " + r["result"], va="center", fontsize=8)
    ax.axvline(PASS_S, color="k", ls="--", lw=1, label="2.0 s criterion")
    ax.set_yticks(y); ax.set_yticklabels([r["fault"] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("time from fault to fault-attributed CLOSED (s)")
    ax.set_xlim(0, max([PASS_S * 1.6] + [v * 1.3 for v in vals if np.isfinite(v)]))
    ax.legend(fontsize=7, loc="lower right"); ax.grid(axis="x", alpha=0.3)
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    common.finish_figure(fig, path, "Test D: fail-safe, fault to CLOSED", sim)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test D analysis")
    p.add_argument("--run", help="run directory from d_failsafe_run.py")
    p.add_argument("--research-log", help="crossing research-log session directory")
    p.add_argument("--marks", help="marks.jsonl / marks CSV (t,fault) on the laptop monotonic clock")
    p.add_argument("--timeout-s", type=float, default=10.0)
    p.add_argument("--out", default=str(common.RECORDS / "D" / "analysis"))
    a = p.parse_args(argv)
    res = analyse(a.out, a.run, a.research_log, a.marks, a.timeout_s)
    print(res["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
