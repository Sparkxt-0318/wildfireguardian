"""Offline replay of high-precision decisions from a verify dump (python -m wfglink verify replay).

A dump run (`process CLIP --high-precision accept_all --verify-dump`) holds every analysed
frame's detections (detections.parquet), the per-hit features of every detection
(high_precision/hp_hits.parquet), the patches of every hit a confirmed track's buffer took
(hp_patches.npz) and the camera-motion status of every analysed frame (hp_frames.parquet).
`replay` rebuilds what any scorer would have decided online, without decoding the video and
without recomputing a single hit feature:

1. The tracker runs again on the recorded detections, frame by frame, with the run's frame
   indices, times, fps and exposure hint (the tracker is deterministic, so its tracks are the
   run's; `replay` checks that their records equal track_points.parquet and refuses when
   they do not).
2. A ReplayObserver, the HighPrecisionObserver itself with two steps replaced, follows the
   pipeline's order on every analysed frame: on_retire for the tracks the tracker finished,
   then on_frame. Of on_frame only the camera-motion status (from hp_frames) and the per-hit
   features (a HitBatch from hp_hits and hp_patches) come from the dump; the hit buffers,
   window features (features.window_features on the dumped hit features), checkpoints,
   Ledger, deadline, static rule, fragment flags and the counting (its own GateCounter fed
   by the same live and catch-up rules) are the observer's code. So the decisions and the
   crossing events of the method that ran online are reproduced exactly, and those of any
   other scorer are what it would have decided on that run.
3. `replay_many` runs several scorers in lock step over one tracker pass (calibration).

Replayed counting differs from the online counter only where the dump differs from the
online state: (a) a dump cut at its row limit (hp_summary dump.dump_truncated) loses the
features of later hits, so replay refuses it unless allow_truncated; (b) on a frame whose
detector state was not new (the observer then keeps the previous frame's motion status for
on_retire) the replay uses the dumped status of that frame; in file mode every analysed frame
has a new state, so this does not occur; (c) the booth's event pruning (live mode only) is
not replayed. The tests run a synthetic clip online with a rules threshold set and with
accept_all and a dump, and require the replayed rules decisions (state, reason, t_decision,
t_accept) and crossing events to equal the online ones.

`predictions` turns a replay into the inputs of evaluate.track_level exactly as
evaluate.load_predictions reads a high-precision run: the tracks ever accepted, the measured
points of each (a revoked track's up to its revocation), the replayed crossings and the
camera-motion frames.

File-mode runs only (one epoch; the booth's cuts are not replayed). The config given must be
the run's: its legacy part is checked against summary config_sha256 (the tracker repeats the
run only then), and the verify settings that shaped the dumped features (FEATURE_KEYS:
ring_frames, max_dets_per_frame, motion, hotspot, patch) must be the overlay's of the run;
window_hits, min_hits, deadline_s and the scorer are what a replay may vary.
feature_settings_sha256(cfg) hashes that subset; when the run's hp_summary records it
(scorer.feature_settings_sha256) a differing config is refused like a differing legacy
config, otherwise a note says it could not be checked (runs written before process.py
records it). dataset.json and calibration_points.json record the hash of the config used.

A buffer hit whose patch was not dumped gets an all-zero patch in the replay; the observer
counts them (missing_patches) and lists them (missing_hits: (frame, detection index)), and
the dataset and calibration refuse or leave out what they would touch.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

import numpy as np

from wfglink.verify.features import FEATURE_NAMES, HitBatch, HitRecord, empty_batch
from wfglink.verify.ledger import Ledger
from wfglink.verify.motion import MotionStatus
from wfglink.verify.observer import HighPrecisionObserver

DET_COLUMNS = ("x", "y", "area", "peak", "flux", "length", "width", "theta", "sat_frac", "color", "flags", "scale")
TRACK_CHECK = ("frame", "t", "x_meas", "y_meas", "x", "y", "coasted", "det_index")
COMPARE_FIELDS = ("state", "reason", "t_decision", "t_accept", "frame_decision", "revoked", "retro", "t_confirm",
                  "confirm_idx")
FEATURE_KEYS = ("ring_frames", "max_dets_per_frame", "motion", "hotspot", "patch")


def feature_settings(cfg: dict) -> dict[str, Any]:
    """The verify settings that shape the dumped per-hit features and patches."""
    v = cfg.get("verify") or {}
    return {k: v.get(k) for k in FEATURE_KEYS}


def feature_settings_sha256(cfg: dict) -> str:
    from wfglink.provenance import sha256_json

    return sha256_json(feature_settings(cfg))


class ReplayError(ValueError):
    """The run cannot be replayed (not a dump, cut, another config, or the tracker diverged)."""


# The dump --------------------------------------------------------------------------------

@dataclass
class DumpRun:
    """A dump run folder loaded for replay (arrays sorted by frame, then detection index)."""

    run_dir: Path
    summary: dict
    hp_summary: dict
    frames: np.ndarray              # analysed frame indices, in order
    times: np.ndarray               # their times
    motion: list[MotionStatus]      # per analysed frame
    over: np.ndarray                # per analysed frame: rows over the feature budget
    det: dict[str, np.ndarray]      # detection columns, rows in frame order
    det_start: np.ndarray           # per analysed frame: first row in det
    det_count: np.ndarray
    hit_values: np.ndarray          # (rows, len(FEATURE_NAMES)) float32, aligned with det
    hit_over: np.ndarray            # (rows,) bool
    patch_row: np.ndarray           # (rows,) index into patches, -1 without a dumped patch
    patches: np.ndarray             # (k, 2, P, P) float16
    points: Any                     # track_points DataFrame
    decisions: Any                  # online hp_decisions
    events: Any                     # online hp_events
    hp_frames: Any
    fps: float | None
    t_exp: float | None
    gate: dict | None
    size: tuple[int, int]           # analysed picture (w, h)
    metrics_scope: str
    truncated: bool
    notes: list[str] = field(default_factory=list)

    @property
    def method(self) -> str:
        return str(self.hp_summary.get("method"))

    def detections(self, i: int):
        from wfglink.detect.candidates import Detections

        a, n = int(self.det_start[i]), int(self.det_count[i])
        if n == 0:
            return Detections()
        cols = {k: self.det[k][a:a + n] for k in DET_COLUMNS}
        return Detections(**cols)

    def batch(self, i: int, patch_px: int) -> tuple[HitBatch, np.ndarray]:
        """The frame's HitBatch as the observer computed it, and which rows have a dumped patch."""
        a, n = int(self.det_start[i]), int(self.det_count[i])
        f, t = int(self.frames[i]), float(self.times[i])
        if n == 0:
            return empty_batch(f, t, patch_px), np.zeros(0, bool)
        rows = self.patch_row[a:a + n]
        has = rows >= 0
        P = patch_px
        pt = np.zeros((n, 2, P, P), np.float16)
        if has.any():
            pt[has] = self.patches[rows[has]]
        return HitBatch(f, t, self.hit_values[a:a + n], pt, self.hit_over[a:a + n], self.det["peak"][a:a + n]), has


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_dump(run_dir: str | Path, allow_truncated: bool = False) -> DumpRun:
    """A dump run (see the module notes), checked for every table replay needs."""
    import pandas as pd

    run = Path(run_dir)
    hp = run / "high_precision"
    need = [run / "summary.json", run / "frames.parquet", run / "detections.parquet", run / "track_points.parquet",
            hp / "hp_summary.json", hp / "hp_frames.parquet", hp / "hp_hits.parquet", hp / "hp_patches.npz",
            hp / "hp_decisions.parquet", hp / "hp_events.parquet"]
    missing = [str(p.relative_to(run)) for p in need if not p.is_file()]
    if missing:
        raise ReplayError(f"{run} is not a verify dump run (missing {', '.join(missing)}); make one with "
                          "`process CLIP --high-precision accept_all --verify-dump`")
    summary, hs = _read_json(run / "summary.json"), _read_json(hp / "hp_summary.json")
    dump_info = hs.get("dump") or {}
    truncated = bool(dump_info.get("dump_truncated"))
    if truncated and not allow_truncated:
        raise ReplayError("the dump was cut at its row limit (hp_summary dump.dump_truncated): later hits have no "
                          "features, so a replay would differ from the online run")
    if hs.get("observer_error"):
        raise ReplayError(f"the run's verifier failed online ({hs['observer_error']}): its dump is incomplete")
    fr = pd.read_parquet(run / "frames.parquet")
    if "duplicate" in fr:
        fr = fr[~fr["duplicate"].astype(bool)]
    frames = fr["frame"].to_numpy(np.int64)
    times = fr["t"].to_numpy(np.float64)
    hf = pd.read_parquet(hp / "hp_frames.parquet")
    if len(hf) != len(frames) or not np.array_equal(hf["frame"].to_numpy(np.int64), frames):
        raise ReplayError("hp_frames.parquet does not list the run's analysed frames (the verifier did not see every "
                          "frame)")
    if "epoch" in hf and int(hf["epoch"].max() if len(hf) else 0) > 0:
        raise ReplayError("the run has more than one epoch (cuts): replay covers file-mode runs only")
    motion = [MotionStatus(float(a), float(b), bool(c), bool(d), int(e)) for a, b, c, d, e in
              zip(hf["shift_px"], hf["residual"], hf["motion_unsupported"], hf["moving"], hf["tiles_changed"])]
    det = pd.read_parquet(run / "detections.parquet")
    dfr = det["frame"].to_numpy(np.int64)
    if len(dfr) and np.any(np.diff(dfr) < 0):
        raise ReplayError("detections.parquet is not in frame order")
    start = np.searchsorted(dfr, frames, side="left")
    count = np.searchsorted(dfr, frames, side="right") - start
    if int(count.sum()) != len(det):
        raise ReplayError("detections.parquet holds detections of frames that were not analysed")
    # A tracking-only run drops flux from its tables; the tracker only records it.
    cols = {k: det[k].to_numpy() if k in det else np.full(len(det), np.nan) for k in DET_COLUMNS}
    hits = pd.read_parquet(hp / "hp_hits.parquet")
    hits = hits.sort_values(["frame", "det_index"], kind="stable")
    if len(hits) != len(det) or not (np.array_equal(hits["frame"].to_numpy(np.int64), dfr)):
        raise ReplayError("hp_hits.parquet does not hold one row per detection (a truncated or foreign dump)")
    within = np.arange(len(det)) - np.repeat(start, count)
    if not np.array_equal(hits["det_index"].to_numpy(np.int64), within):
        raise ReplayError("hp_hits.parquet det_index does not follow the detections' order")
    values = hits[list(FEATURE_NAMES)].to_numpy(np.float64).astype(np.float32)
    over = hits["over_budget"].to_numpy(bool)
    with np.load(hp / "hp_patches.npz", allow_pickle=False) as z:
        pk, pf, pj, patches = z["key"], z["frame"].astype(np.int64), z["det_index"].astype(np.int64), z["patches"]
    patch_row = np.full(len(det), -1, np.int64)
    if len(pf):
        fi = np.searchsorted(frames, pf)
        ok = (fi < len(frames)) & (frames[np.minimum(fi, len(frames) - 1)] == pf)
        fi = np.minimum(fi, len(frames) - 1)
        ok &= (pj >= 0) & (pj < count[fi])
        rows = start[fi] + pj
        patch_row[rows[ok]] = np.flatnonzero(ok)
    inp = summary.get("input") or {}
    exp = summary.get("exposure") or {}
    t_exp = exp.get("t_exp_s")
    gate = (summary.get("totals") or {}).get("gate")
    w, h = int(inp.get("width") or 0), int(inp.get("height") or 0)
    return DumpRun(run_dir=run, summary=summary, hp_summary=hs, frames=frames, times=times, motion=motion,
                   over=hf["over_budget"].to_numpy(np.int64), det=cols, det_start=start, det_count=count,
                   hit_values=values, hit_over=over, patch_row=patch_row, patches=patches,
                   points=pd.read_parquet(run / "track_points.parquet"),
                   decisions=pd.read_parquet(hp / "hp_decisions.parquet"),
                   events=pd.read_parquet(hp / "hp_events.parquet"), hp_frames=hf,
                   fps=float(inp["fps"]) if inp.get("fps") else None,
                   t_exp=float(t_exp) if t_exp else None, gate=gate, size=(w, h),
                   metrics_scope=str(summary.get("metrics_scope") or "all"), truncated=truncated)


# The replayed observer ---------------------------------------------------------------------

class _Pipe:
    """What the observer reads of a Pipeline, for a replay."""

    def __init__(self, cfg: dict, tracker, gate_obj, record: bool = True):
        f = cfg.get("field", {})
        self.cfg = cfg
        self.tracker = tracker
        self._gate_obj = gate_obj
        self._last_t: float | None = None
        self.record = record
        self.downscale = False
        self.detector = None
        self.field_grid = tuple(int(v) for v in f.get("grid", [16, 9]))
        self.field_window = float(f.get("live_window_s", 3.0))
        self.field_min_n = int(f.get("min_tracks_show", 5))
        self.m_per_px = None
        self.distance_m = None


class _Frame:
    __slots__ = ("index",)

    def __init__(self, index: int):
        self.index = int(index)


class _Light:
    """The few fields of a high-precision state the observer's frame rows read."""

    __slots__ = ("detections", "trails", "precision_pending", "cpc_gross", "count_rate", "precision_status")

    def __init__(self, pending: int, status: str):
        self.detections, self.trails = (), ()
        self.precision_pending, self.precision_status = pending, status
        self.cpc_gross = self.count_rate = None


class _KeyedLedger(Ledger):
    """A Ledger that tells the scorer which track it scores (for the dataset's probe)."""

    def checkpoint(self, key, t, window, scorer, flags=(), frame=-1):
        if hasattr(scorer, "key"):
            scorer.key = key
            scorer.t, scorer.frame = float(t), int(frame)
        return super().checkpoint(key, t, window, scorer, flags, frame)


class ReplayObserver(HighPrecisionObserver):
    """HighPrecisionObserver whose camera motion and per-hit features come from a dump."""

    def __init__(self, cfg: dict, pipe: _Pipe, scorer, profile: str):
        base = copy.deepcopy(cfg)
        base["verify"]["method"] = "accept_all"       # the base builds a trivial scorer; ours replaces it
        base["verify"]["dump"] = False
        super().__init__(base, pipe)
        self.vcfg = replace(self.vcfg, dump=False)
        self.scorer = scorer
        self.method = str(getattr(scorer, "method", "replay"))
        self.profile = profile
        self._input: tuple | None = None
        self.missing_patches = 0
        self.missing_hits: set[tuple[int, int]] = set()
        self.last_hits: dict[int, list[HitRecord]] = {}
        self.window_cache: dict | None = None      # shared by the observers of one replay_many frame

    def reset(self) -> None:
        super().reset()
        self.ledger = _KeyedLedger(self.vcfg, keep_all=True)

    def feed(self, ms: MotionStatus, batch: HitBatch, has_patch: np.ndarray, over: int) -> None:
        self._input = (ms, batch, has_patch, over)

    def _motion_now(self, pipe, t, h, w):
        ms = self._input[0]
        self.motion.last = ms
        return ms, None, True

    def _features(self, pipe, image, t, fidx, det, ds, fresh, ms, prio, owner):
        _, batch, has, over = self._input
        self._batches.append((batch, not ms.unsupported))
        self._has_patch = has
        if over:
            self.stats["over_budget_frames"] += 1
        return batch, int(over)

    def _hit(self, batch, r, supported):
        hit = super()._hit(batch, r, supported)
        j = int(r[15])
        if hit.values is not None:
            has = getattr(batch, "_has_patch", None)
            if has is not None and not has[j]:
                self.missing_patches += 1
                self.missing_hits.add((int(batch.frame), j))
        return hit

    def _window(self, key, tr):
        buf = self._buffers.get(key)
        if buf:
            self.last_hits = {key: list(buf)}      # the hits of the window being built only (a probe reads them now)
        return super()._window(key, tr)

    def _make_window(self, key, hits, kin):
        """Every scorer of one replay sees the same tracker and dumped features, so a window of the
        same track, hits and kin is the same for all: it is built once per frame and shared, with
        its arrays read-only (a scorer that writes into one fails the replay)."""
        cache = self.window_cache
        if cache is None:
            return super()._make_window(key, hits, kin)
        ck = (key, kin, tuple((h.frame, h.det_index, h.supported, h.values is None, h.patch is None) for h in hits))
        win = cache.get(ck)
        if win is None:
            win = super()._make_window(key, hits, kin)
            for a in (win.vec, win.patches, win.hit_values):
                if a is not None:
                    a.setflags(write=False)
            cache[ck] = win
        return win

    def _hp_state(self, pipe, image, t, snaps, new_events, w, h, state, ms, over):
        return _Light(self.ledger.pending(), self._status(ms, over))


def _gate_for(dump: DumpRun, cfg: dict):
    from wfglink.measure.gate import Gate

    w, h = dump.size
    g = dump.gate
    if g is None:
        spec = {"p1": [0.62 * w, 0.08 * h], "p2": [0.62 * w, 0.92 * h], "name": "gate"}
        p1, p2, name = spec["p1"], spec["p2"], spec["name"]
    else:
        p1, p2, name = g["p1"], g["p2"], g.get("name", "gate")
    return Gate(tuple(p1), tuple(p2), float(cfg["gate"]["hysteresis_px"]), name)


def check_config(dump: DumpRun, cfg: dict) -> bool:
    """True when cfg's legacy part is the run's (summary config_sha256)."""
    from wfglink.outputs.process import _legacy_cfg
    from wfglink.provenance import sha256_json

    return sha256_json(_legacy_cfg(cfg)) == dump.summary.get("config_sha256")


def check_feature_settings(dump: DumpRun, cfg: dict) -> bool | None:
    """True or False when the run records its feature settings hash (hp_summary
    scorer.feature_settings_sha256, or a top-level one), None when it does not."""
    hs = dump.hp_summary
    rec = (hs.get("scorer") or {}).get("feature_settings_sha256") or hs.get("feature_settings_sha256")
    if not rec:
        return None
    return feature_settings_sha256(cfg) == rec


@dataclass
class ReplayResult:
    name: str
    method: str
    decisions: Any
    events: Any
    counts: dict
    identity: dict
    missing_patches: int
    observer: ReplayObserver
    missing_hits: set = field(default_factory=set)

    def accepted_ids(self) -> set[int]:
        d = self.decisions
        if not len(d):
            return set()
        ever = (d["state"].astype(str) == "method_accepted") | d["revoked"].astype(bool)
        return set(d.loc[ever, "track_id"].astype(int))


def replay_many(run, scorers: dict[str, Any], cfg: dict, profile: str = "file_native", *, check_tracks: bool = True,
                strict_config: bool = True, allow_truncated: bool = False,
                progress: Callable[[int, int], None] | None = None) -> dict[str, ReplayResult]:
    """Replay every scorer of `scorers` (name -> scorer) over one tracker pass of a dump run."""
    from wfglink.render.scene import LiveState
    from wfglink.track.tracker import Tracker

    dump = run if isinstance(run, DumpRun) else load_dump(run, allow_truncated)
    if "verify" not in cfg:
        raise ReplayError("the config has no verify section (use verify.config.hp_config)")
    if not check_config(dump, cfg):
        msg = "the config is not the run's (its legacy config_sha256 differs): the tracker would not repeat the run"
        if strict_config:
            raise ReplayError(msg)
        dump.notes.append(msg)
    fs = check_feature_settings(dump, cfg)
    if fs is False:
        msg = ("the config's feature settings (verify ring_frames, max_dets_per_frame, motion, hotspot, patch) are not "
               "the run's: the dumped features were made with others")
        if strict_config:
            raise ReplayError(msg)
        dump.notes.append(msg)
    elif fs is None:
        note = ("the run does not record its feature settings hash: that the config's verify ring_frames, "
                "max_dets_per_frame, motion, hotspot and patch are the run's was not checked")
        if note not in dump.notes:
            dump.notes.append(note)
    tracker = Tracker(cfg, fps=dump.fps, keep_history=True)
    if dump.t_exp:
        tracker.set_exposure_hint(dump.t_exp)
    pipe = _Pipe(cfg, tracker, _gate_for(dump, cfg))
    obs = {name: ReplayObserver(cfg, pipe, sc, profile) for name, sc in scorers.items()}
    for name, o in obs.items():
        o.set_metrics_scope(dump.metrics_scope)
        if getattr(scorers[name], "observer", False) is None:     # a probe that reads its observer's hit buffers
            scorers[name].observer = o
    cache: dict = {}
    for o in obs.values():
        o.window_cache = cache
    P = next(iter(obs.values())).vcfg.patch.target_px if obs else 17
    w, h = dump.size
    image = np.broadcast_to(np.zeros((), np.uint8), (max(h, 1), max(w, 1)))
    dummy = LiveState()
    n = len(dump.frames)
    for i in range(n):
        f, t = int(dump.frames[i]), float(dump.times[i])
        det = dump.detections(i)
        pipe._last_t = t
        cache.clear()
        snaps = tracker.update(det, t, f)
        fin = tracker.pop_finished()
        batch, has = dump.batch(i, P)
        batch._has_patch = has
        frame = _Frame(f)
        for o in obs.values():
            o.on_retire(fin)
            o.feed(dump.motion[i], batch, has, int(dump.over[i]))
            o.on_frame(pipe, frame, image, t, det, snaps, dummy)
        if progress is not None and (i % 50 == 0 or i == n - 1):
            progress(i + 1, n)
    fin = tracker.finish_all()
    for o in obs.values():
        o.on_retire(fin)
        o.finalize()
    if check_tracks:
        _check_tracks(dump, tracker)
    out = {}
    for name, o in obs.items():
        if o.failed is not None:
            raise ReplayError(f"replay {name}: the observer failed ({o.failed})")
        tabs = o.tables()
        out[name] = ReplayResult(name=name, method=o.method, decisions=tabs["hp_decisions"], events=tabs["hp_events"],
                                 counts=o.decision_counts(), identity=o.scorer.identity(),
                                 missing_patches=o.missing_patches, observer=o, missing_hits=set(o.missing_hits))
    return out


def replay(run_dir, vcfg_or_cfg, scorer, profile: str = "file_native", **kw) -> ReplayResult:
    """Replay one scorer (see the module notes); vcfg_or_cfg is the resolved config with its
    verify section (hp_config) whose legacy part is the run's."""
    return replay_many(run_dir, {"replay": scorer}, vcfg_or_cfg, profile, **kw)["replay"]


def _check_tracks(dump: DumpRun, tracker) -> None:
    from wfglink.track.tracker import tracks_to_frame

    again = tracks_to_frame(tracker.all_tracks(include_active=True))
    a = dump.points.sort_values(["track_id", "frame"], kind="stable").reset_index(drop=True)
    b = again.sort_values(["track_id", "frame"], kind="stable").reset_index(drop=True)
    cols = ["track_id", *TRACK_CHECK]
    if len(a) != len(b):
        raise ReplayError(f"the tracker run again gives {len(b)} track records, the run has {len(a)}: the replay "
                          "would not be the run's (another config or tracker version)")
    for c in cols:
        x, y = a[c].to_numpy(), b[c].to_numpy()
        same = np.array_equal(x, y, equal_nan=True) if x.dtype.kind == "f" and y.dtype.kind == "f" else \
            np.array_equal(x, y)
        if not same:
            raise ReplayError(f"the tracker run again differs from track_points.parquet in {c}: the replay would not "
                              "be the run's")


# Comparisons and evaluation inputs ---------------------------------------------------------

def compare_decisions(online, replayed, fields=COMPARE_FIELDS) -> dict[str, Any]:
    """Per-field mismatches between two decision tables (keyed by key)."""
    a = online.set_index("key").sort_index()
    b = replayed.set_index("key").sort_index()
    only_a, only_b = sorted(set(a.index) - set(b.index)), sorted(set(b.index) - set(a.index))
    common = a.index.intersection(b.index)
    mism = {}
    for f in fields:
        if f not in a or f not in b:
            continue
        x, y = a.loc[common, f].to_numpy(), b.loc[common, f].to_numpy()
        if x.dtype.kind == "f" or y.dtype.kind == "f":
            bad = ~((x == y) | (np.isnan(x.astype(float)) & np.isnan(y.astype(float))))
        else:
            bad = x != y
        if bad.any():
            mism[f] = [int(k) for k in common[bad][:20]]
    return {"identical": not (only_a or only_b or mism), "only_online": only_a[:20], "only_replay": only_b[:20],
            "n_online": int(len(a)), "n_replay": int(len(b)), "mismatched_fields": mism}


def compare_events(online, replayed) -> dict[str, Any]:
    """Whether two event tables hold the same crossings (key, t, direction, s, x, y)."""
    cols = ["key", "t", "direction", "s", "x", "y"]

    def rows(df):
        return sorted(tuple(r) for r in df[cols].itertuples(index=False, name=None)) if len(df) else []

    ra, rb = rows(online), rows(replayed)
    return {"identical": ra == rb, "n_online": len(ra), "n_replay": len(rb)}


def predictions(dump: DumpRun, res: ReplayResult) -> dict[str, Any]:
    """The inputs of evaluate.track_level for a replay, as evaluate.load_predictions reads a
    high-precision run (points, crossings, unsupported_frames, revoked_ids)."""
    import pandas as pd

    dec = res.decisions
    ever = (dec["state"].astype(str) == "method_accepted") | dec["revoked"].astype(bool) if len(dec) else []
    acc = dec[ever] if len(dec) else dec
    ids = set(acc["track_id"].astype(int)) if len(acc) else set()
    revoked = set(acc.loc[acc["revoked"].astype(bool), "track_id"].astype(int)) if len(acc) else set()
    pts = dump.points
    if len(pts) and ids:
        sel = pts["track_id"].isin(ids) & ~pts["coasted"].astype(bool)
        if revoked:
            t_rev = acc.loc[acc["revoked"].astype(bool)].set_index("track_id")["t_decision"].astype(float)
            cut = pts["track_id"].astype(int).map(t_rev).to_numpy(float)
            sel &= ~(pts["t"].to_numpy(float) >= cut - 1e-9)
        p = pts[sel]
        points = pd.DataFrame({"track_id": p["track_id"].astype(int), "frame": p["frame"].astype(int),
                               "t": p["t"].astype(float), "x": p["x_meas"].astype(float),
                               "y": p["y_meas"].astype(float), "length": p["length"].astype(float)})
    else:
        points = pd.DataFrame(columns=["track_id", "frame", "t", "x", "y", "length"])
    e = res.events
    crossings = pd.DataFrame({"track_id": e["track_id"].astype(np.int64), "t": e["t"].astype(float),
                              "x": e["x"].astype(float), "y": e["y"].astype(float)})
    hf = dump.hp_frames
    return {"points": points, "crossings": crossings, "revoked_ids": revoked,
            "unsupported_frames": set(hf.loc[hf["motion_unsupported"].astype(bool), "frame"].astype(int)),
            "accepted_tracks": len(ids)}


def confirmation_delays(res: ReplayResult) -> np.ndarray:
    """t_accept - t_confirm of the tracks ever accepted."""
    d = res.decisions
    if not len(d):
        return np.zeros(0)
    ever = (d["state"].astype(str) == "method_accepted") | d["revoked"].astype(bool)
    v = (d.loc[ever, "t_accept"] - d.loc[ever, "t_confirm"]).to_numpy(float)
    return v[np.isfinite(v)]


def write_replay(res: ReplayResult, dump: DumpRun, out_dir: str | Path) -> dict[str, Any]:
    """replay_decisions.parquet, replay_events.parquet and replay.json (with the comparison
    to the online decisions when the replayed method is the one that ran online)."""
    from wfglink.provenance import git_state, now_shanghai

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res.decisions.to_parquet(out / "replay_decisions.parquet", index=False)
    res.events.to_parquet(out / "replay_events.parquet", index=False)
    rec = {"schema_version": 1, "created": now_shanghai(), "run_dir": str(dump.run_dir), "method": res.method,
           "online_method": dump.method, "scorer": res.identity, "decisions": res.counts,
           "events": int(len(res.events)), "missing_patches": res.missing_patches,
           "confirm_to_accept_s": _stat(confirmation_delays(res)), "notes": list(dump.notes), **git_state(),
           "labels": {"accepted": "accepted by this method on replay, not proven to be an ember"}}
    if res.method == dump.method:
        rec["online_comparison"] = {"decisions": compare_decisions(dump.decisions, res.decisions),
                                    "events": compare_events(dump.events, res.events)}
    (out / "replay.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return rec


def _stat(v) -> dict[str, Any]:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    return {"median": float(np.median(v)) if v.size else None, "p95": float(np.percentile(v, 95)) if v.size else None,
            "n": int(v.size)}
