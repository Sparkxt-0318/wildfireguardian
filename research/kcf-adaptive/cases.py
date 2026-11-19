"""Arm 1 inputs and scores (PROTOCOL.md section 2).

Reads the committed held-out case files of the frozen forecast study. Nothing here fits anything.
The one function that decides what adaptation may see is `history_for` (PROTOCOL 2.2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
HELDOUT = REPO / "forecast/runs/20261030_perimeter_trained/execution_v3/heldout"
KOREAN = REPO / "forecast/runs/20261030_perimeter_trained/execution_v3/korean2025"
C651 = REPO / "forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"
C651_SHA256 = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"
MAX_HISTORY = 8
BINS = (0.0, 0.001, 0.01, 0.1, 0.5, 1.0)
THRESHOLDS = (0.01, 0.05, 0.1, 0.5)
BOOT_DRAWS, BOOT_SEED = 10000, 20261030


@dataclass
class Window:
    event: str
    case_id: str
    cutoff: pd.Timestamp          # the issue time
    endpoint: pd.Timestamp
    hours: float
    shape: tuple
    weather_hour: pd.Timestamp
    row: np.ndarray
    col: np.ndarray
    y: np.ndarray                 # labels on the scored cells; the future of this window
    committed: dict = field(default_factory=dict, repr=False)   # committed predictions (context only)
    status: str = "SCORED"
    excluded: int = 0

    @property
    def initial(self) -> np.ndarray:
        """Burned at cut-off: every rectangle cell that is not a scored cell (PROTOCOL 2.1)."""
        if self.excluded:
            raise ValueError(f"{self.case_id}: excluded cells; the burned state cannot be read from the scored cells")
        b = np.ones(self.shape, bool)
        b[self.row, self.col] = False
        return b

    def grid(self, values) -> np.ndarray:
        g = np.zeros(self.shape, float)
        g[self.row, self.col] = values
        return g


def load_windows(root: Path = HELDOUT, keep=("p_c651_mc", "p_c651_meanfield")) -> dict[str, list[Window]]:
    """All committed windows by fire, in issue-time order."""
    fires: dict[str, list[Window]] = {}
    for f in sorted((root / "cases").glob("*.json")):
        c = json.loads(f.read_text())
        if c["status"] != "SCORED":
            continue
        with np.load(f.with_suffix(".npz"), allow_pickle=False) as z:
            w = Window(c["case"]["event"], c["case_id"], pd.Timestamp(c["case"]["cutoff"]),
                       pd.Timestamp(c["case"]["endpoint"]), float(c["case"]["hours"]), tuple(c["rectangle"]),
                       pd.Timestamp(c["weather_hour"]), z["row"].copy(), z["col"].copy(), z["y"].astype(np.int8),
                       {k: z[k].astype(float) for k in keep}, excluded=int(c.get("excluded_cells", 0)))
        if w.weather_hour > w.cutoff:
            raise ValueError(f"{w.case_id}: weather hour after the cut-off")
        fires.setdefault(w.event, []).append(w)
    for ws in fires.values():
        ws.sort(key=lambda w: w.cutoff)
    return fires


def history_for(windows: list[Window], target: Window, max_history: int = MAX_HISTORY,
                _leak_target: bool = False) -> list[Window]:
    """The only windows adaptation may see for `target`: same fire, ended at or before its issue time.

    `_leak_target` exists only for the positive control of the leakage test (PROTOCOL 2.7, L3).
    """
    hist = [w for w in windows if w.event == target.event and w.endpoint <= target.cutoff and w is not target]
    hist.sort(key=lambda w: w.cutoff)
    hist = hist[-max_history:]
    if _leak_target:
        hist = hist + [target]
    else:
        check_history(hist, target)
    return hist


def check_history(hist: list[Window], target: Window) -> None:
    for w in hist:
        if w is target or w.event != target.event or w.endpoint > target.cutoff or w.weather_hour > target.cutoff:
            raise ValueError(f"leak: window {w.case_id} (ends {w.endpoint}) is not in the past of {target.cutoff}")


# ------------------------------------------------------------------ scores
def brier_sums(y, p):
    return float(np.sum((p - y) ** 2)), int(len(y))


def paired_bootstrap(se_a: dict, se_b: dict, n: dict, draws=BOOT_DRAWS, seed=BOOT_SEED):
    """Whole-fire bootstrap of the pooled Brier difference a - b (the S-D9 convention)."""
    fires = sorted(n)
    a = np.array([se_a[f] for f in fires])
    b = np.array([se_b[f] for f in fires])
    m = np.array([n[f] for f in fires], float)
    rng = np.random.default_rng(seed)
    s = rng.integers(0, len(fires), size=(draws, len(fires)))
    boot = (a[s].sum(1) - b[s].sum(1)) / m[s].sum(1)
    return dict(point=float((a.sum() - b.sum()) / m.sum()), ci95=np.quantile(boot, [.025, .975]).tolist(),
                fires_favouring_a=int((a / m < b / m).sum()), n_fires=len(fires),
                per_fire={f: float((a[i] - b[i]) / m[i]) for i, f in enumerate(fires)})


def calibration(y, p):
    rows, ece = [], 0.0
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        k = int(m.sum())
        row = dict(bin=[lo, hi], count=k, positives=int(y[m].sum()),
                   mean_p=float(p[m].mean()) if k else None, observed=float(y[m].mean()) if k else None)
        if k:
            row["gap"] = abs(row["mean_p"] - row["observed"])
            ece += k / len(y) * row["gap"]
        rows.append(row)
    return dict(bins=rows, ece=float(ece), lowest_bin_gap=rows[0].get("gap"),
                sum_p_over_burned=float(p.sum() / y.sum()) if y.sum() else None)


def flagging(y, p):
    pos = y == 1
    n_pos = int(pos.sum())
    out = dict(expected_area_per_burned_cell=float(p.sum() / n_pos), expected_miss_rate=float((1 - p[pos]).mean()),
               thresholds={}, at_fixed_miss={})
    for t in THRESHOLDS:
        f = p >= t
        out["thresholds"][str(t)] = dict(flagged_per_burned=float(f.sum() / n_pos), miss_rate=float((~f[pos]).mean()))
    pp = np.sort(p[pos])
    for miss in (0.10, 0.20):
        # largest threshold that still flags at least (1 - miss) of the burned cells
        k = int(np.floor(miss * n_pos))
        thr = pp[k]
        f = p >= thr
        out["at_fixed_miss"][str(miss)] = dict(threshold=float(thr), flagged_per_burned=float(f.sum() / n_pos),
                                               miss_rate=float((~f[pos]).mean()),
                                               note="threshold read from the same data; descriptive only")
    return out


def summarise(fire, y, preds: dict):
    """fire, y: arrays over all entries; preds: name -> probability array."""
    fires = sorted(set(fire))
    idx = {f: fire == f for f in fires}
    n = {f: int(idx[f].sum()) for f in fires}
    out = dict(entries=int(len(y)), positives=int(y.sum()), n_fires=len(fires), models={})
    se = {}
    for name, p in preds.items():
        se[name] = {f: float(np.sum((p[idx[f]] - y[idx[f]]) ** 2)) for f in fires}
        out["models"][name] = dict(brier=float(np.mean((p - y) ** 2)),
                                   per_fire_brier={f: se[name][f] / n[f] for f in fires},
                                   calibration=calibration(y, p), flagging=flagging(y, p))
    out["_se"], out["_n"] = se, n
    return out
