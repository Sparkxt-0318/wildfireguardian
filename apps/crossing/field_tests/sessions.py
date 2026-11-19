"""Reading recorded runs: run directories written by recordkit (or simulate.py) and Pi record sessions
(hardware/vehicle-unit/records/<session_id>/, DESIGN.md section 4). Both use the same <sensor>.jsonl.gz files and are
read with wfgvu.replay, so a run directory can also be replayed into the crossing app.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import numpy as np

from . import common  # noqa: F401  (sys.path for wfgvu)
from .recordkit import read_marks, read_rx
from wfgvu import replay


@dataclass
class Run:
    dir: Path
    trial: dict
    info: dict
    marks: List[dict]
    session: Optional[replay.Session] = None
    _cache: Dict[str, list] = field(default_factory=dict, repr=False)

    @property
    def run_id(self) -> str:
        return str(self.trial.get("run_id") or self.dir.name)

    @property
    def simulated(self) -> bool:
        return bool(self.trial.get("simulated")) or bool(self.info.get("sim")) or bool(self.trial.get("sim"))

    def messages(self, sensor: str) -> list:
        if sensor not in self._cache:
            if self.session is None or sensor not in self.session.streams:
                self._cache[sensor] = []
            else:
                self._cache[sensor] = list(self.session.streams[sensor])
        return self._cache[sensor]

    def readings(self, sensor: str) -> list:
        return [m for m in self.messages(sensor) if m["type"] == "reading"]

    def heartbeats(self, sensor: str) -> list:
        if sensor == "unit":
            return unit_heartbeats(self.dir)
        return [m for m in self.messages(sensor) if m["type"] == "heartbeat"]

    def any_sim_message(self) -> bool:
        for s in ("tc_plate", "radar", "thermal", "gnss", "pi"):
            for m in self.messages(s)[:1]:
                if m.get("sim"):
                    return True
        return False

    def mark_t(self, kind: str, which: str = "first") -> Optional[float]:
        """Pi t_mono of a mark (first or last of that kind), None if absent or no clock mapping."""
        ms = [m for m in self.marks if m.get("kind") == kind and m.get("pi_t_mono") is not None]
        if not ms:
            return None
        return float((ms[0] if which == "first" else ms[-1])["pi_t_mono"])

    def rx(self) -> List[dict]:
        return read_rx(self.dir)


def load_run(run_dir) -> Run:
    d = Path(run_dir)
    trial = json.loads((d / "trial.json").read_text()) if (d / "trial.json").exists() else {}
    info = json.loads((d / "session.json").read_text()) if (d / "session.json").exists() else {}
    try:
        sess = replay.load(d)
    except FileNotFoundError:
        sess = None
    return Run(dir=d, trial=trial, info=info, marks=read_marks(d), session=sess)


def find_runs(root, test: str) -> List[Run]:
    """All run directories below `root` (any depth) whose trial.json has test == `test`, oldest first."""
    root = Path(root)
    runs = []
    for p in sorted(root.rglob("trial.json")):
        try:
            t = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if str(t.get("test", "")).upper() == test.upper():
            runs.append(load_run(p.parent))
    runs.sort(key=lambda r: (str(r.trial.get("created_utc", "")), r.dir.name))
    return runs


def unit_heartbeats(session_dir) -> list:
    """Server ("unit") heartbeats from unit.jsonl.gz (not a SensorStream in wfgvu.replay)."""
    from wfgvu import protocol
    out = []
    for path in replay.stream_files(Path(session_dir), "unit"):
        for line in replay.iter_lines(path):
            try:
                m = protocol.parse(line)
            except protocol.ProtocolError:
                continue
            if m["type"] == "heartbeat":
                out.append(m)
    out.sort(key=lambda m: m["t_mono"])
    return out


def scalar_series(msgs: list, key: str) -> Tuple[np.ndarray, np.ndarray]:
    """(t_mono, value) for readings whose data[key] is a finite number; None/missing -> NaN."""
    t = np.array([float(m["t_mono"]) for m in msgs], dtype=float)
    v = np.array([np.nan if m["data"].get(key) is None else float(m["data"][key]) for m in msgs], dtype=float)
    return t, v


def segment(msgs: list, t0: Optional[float], t1: Optional[float]) -> list:
    return [m for m in msgs if (t0 is None or m["t_mono"] >= t0) and (t1 is None or m["t_mono"] <= t1)]
