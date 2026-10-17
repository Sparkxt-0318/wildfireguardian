"""HighPrecisionObserver: the verifier attached to one Pipeline (created only when the config has
a `verify` section).

Per analysed frame (on_frame, after the legacy state is built):
1. Camera motion from the native luma; this frame's per-hit features (the ring and the
   hotspot map hold earlier frames only); then the frame enters the ring and the hotspot map.
2. Each confirmed track measured this frame gets a HitRecord in its buffer (the last
   window_hits); a newly confirmed track becomes a candidate and its buffer is filled from its
   earlier hits (features of the last few frames are kept for that).
3. Every candidate measured this frame is checkpointed; then the deadline rule.
4. Tracks flagged static are rejected and excluded from the counter.
5. Counting, on the observer's own GateCounter (the pipeline's gate): every accepted, non-static,
   measured snapshot is fed. A new acceptance first feeds the track's records from its
   confirming hit to the previous frame, each at its own record time, so the counts do not
   depend on when the decision came (times and speeds never come from the latency); each
   event's track decision time, the time it was counted, the retro flag and the delay go into
   a side table (hp_events). While the camera moves (a gated scorer), nothing is fed, and at
   the onset every track's crossing state is forgotten, so no crossing is interpolated across
   the gap; a later catch-up skips those spans the same way.
6. The high-precision LiveState: the legacy state with the detections, trails, counts, speed,
   direction, field and sparkline replaced by those of the accepted tracks, computed by the
   pipeline's own code (Pipeline._update_running and Pipeline._build_state run on a view that
   holds only accepted tracks); plus precision_mode, precision_status and precision_pending.

The accept_all control accepts at confirmation and is never gated, so its counts equal the
legacy counter's exactly. A clip whose timebase is not real time (metrics_scope tracking_only)
gets no decisions (insufficient_evidence: timebase_not_real_time) and no counts.

The tables hold the tracks ever accepted (accepted now, or accepted and then revoked as
static): a revoked track was drawn and counted while it was accepted, and its crossings from
before its slow window stay counted, as in the legacy counter.

The verifier never stops the legacy analysis: an exception in a hook is recorded (`failed`),
the scorer becomes Unavailable("observer_error"), and from then on the hooks do nothing but
return the legacy state without detections, trails or counts (status unavailable).
"""
from __future__ import annotations

import math
import time
from collections import OrderedDict, deque
from dataclasses import replace
from typing import Any

import numpy as np

from wfglink.track.tracker import CONFIRMED
from wfglink.verify.config import VerifyConfig, profile_of
from wfglink.verify.features import (FEATURE_NAMES, WINDOW_NAMES, HitBatch, HitRecord, Kin, hit_features,
                                     window_features, window_patches)
from wfglink.verify.ledger import CANDIDATE, PUBLIC_FIELDS, STATES, Ledger, Window, is_ever_accepted, make_key
from wfglink.verify.motion import GlobalMotion, HotspotMap, MotionStatus
from wfglink.verify.ring import FrameRing, RingFrame
from wfglink.verify.scorers import Unavailable, build_scorer

LIVE_ROWS = 3000            # per-frame rows and event side entries kept in the booth
DUMP_MAX_ROWS = 2_000_000   # per-hit dump rows kept at most (file mode)


class _AcceptedView:
    """Pipeline-shaped view of the accepted tracks: Pipeline._update_running and
    Pipeline._build_state run on it unchanged, with the observer's counter."""

    def __init__(self, obs: "HighPrecisionObserver", pipe):
        self._obs, self._pipe = obs, pipe
        self.field_grid = pipe.field_grid
        self.field_window = pipe.field_window
        self.field_min_n = pipe.field_min_n
        self.m_per_px = pipe.m_per_px
        self.distance_m = pipe.distance_m
        self._spark: deque = deque()
        self._field: dict = {}
        self._speeds: deque = deque()
        self._t_ready: float | None = None
        self.counter = None
        self.tracker = self

    @property
    def detector(self):
        return self._pipe.detector

    @property
    def _gate_obj(self):
        return self._pipe._gate_obj

    def active_tracks(self, include_tentative: bool = False):
        obs = self._obs
        return [tr for tr in self._pipe.tracker.active_tracks() if obs.ledger.accepted(obs.key(tr.track_id))]


class HighPrecisionObserver:
    def __init__(self, cfg: dict, pipe):
        self.cfg = cfg
        self.pipe = pipe
        self.vcfg: VerifyConfig = VerifyConfig.from_cfg(cfg)
        self.method = self.vcfg.method
        self.record = bool(getattr(pipe, "record", False))
        self.profile = profile_of(self.record, bool(getattr(pipe, "downscale", False)))
        self.scorer = build_scorer(self.vcfg, self.profile)
        tr = cfg.get("track", {})
        self._history = max(int(tr.get("confirm_window", 4)), self.vcfg.window_hits) + 2
        self.metrics_scope = "all"
        self.failed: str | None = None      # the exception that stopped the verifier, if any
        self.reset()

    # Lifecycle ------------------------------------------------------------------------------
    def reset(self) -> None:
        v = self.vcfg
        self.epoch = 0
        self.ring = FrameRing(v.ring_frames)
        self.motion = GlobalMotion(v.motion)
        self.hot = HotspotMap(v.hotspot)
        self.ledger = Ledger(v, keep_all=self.record)
        self.counter = None
        self._gate_ref = None
        self._buffers: dict[int, deque] = {}
        self._batches: deque[tuple[HitBatch, bool]] = deque(maxlen=self._history)   # (features, motion-supported)
        self._fed: set[int] = set()
        self._withheld: deque = deque()        # [t0, t1] spans when crossings were not fed
        self._withholding = False
        self._static_seen: set[int] = set()
        self._event_info: OrderedDict = OrderedDict()   # CrossingEvent -> (t_decision, t_counted, retro, delay)
        self._view = _AcceptedView(self, self.pipe)
        self.legacy_state = None
        self._state_ref = None
        self._last_t: float | None = None
        self._frame_now = -1
        self._last_prune = -math.inf
        self._rows: list | deque = [] if self.record else deque(maxlen=LIVE_ROWS)
        self._ms: list | deque = [] if self.record else deque(maxlen=LIVE_ROWS)
        self.stats = {"frames": 0, "over_budget_frames": 0, "motion_unsupported_s": 0.0, "supported_s": 0.0,
                      "withheld_s": 0.0, "dump_rows": 0, "dump_patches": 0, "dump_windows": 0,
                      "dump_truncated": False}
        self._dump_hits: list[np.ndarray] = []
        self._dump_patches: list[tuple[int, int, int, np.ndarray]] = []
        self._dump_windows: list[np.ndarray] = []
        self._shown: list[tuple[int, int]] = []
        self.finalized = False

    def set_metrics_scope(self, scope: str) -> None:
        """metrics_scope of the clip (tracking_only: the timebase is not real time)."""
        self.metrics_scope = str(scope or "all")

    @property
    def tracking_only(self) -> bool:
        return self.metrics_scope == "tracking_only"

    @property
    def counting(self) -> bool:
        """Whether the high-precision counts exist at all (a usable method on a real-time clip)."""
        return bool(getattr(self.scorer, "available", True)) and not self.tracking_only

    def key(self, track_id: int) -> int:
        return make_key(self.epoch, track_id)

    def on_cut(self) -> None:
        """A cut in the picture (the booth playlist): a new epoch of track ids; frames, motion,
        hotspots and hit buffers restart; the decisions and the counts stay."""
        if self.failed is not None:
            return
        try:
            self._on_cut()
        except Exception as exc:     # the verifier never stops the legacy analysis
            self._fail(exc)

    def _on_cut(self) -> None:
        self.epoch += 1
        self.ledger.new_epoch()
        self.ring.clear()
        self.motion.reset()
        self.hot.reset()
        self._buffers.clear()
        self._batches.clear()
        self._state_ref = None
        self._withholding = False

    def finalize(self) -> None:
        """End of the stream: close every decision still open."""
        if self.finalized:
            return
        t = self._last_t if self._last_t is not None else 0.0
        try:
            self.ledger.finalize(t, self._frame_now)
        except Exception as exc:     # the verifier never stops the legacy analysis
            self._fail(exc)
        self._buffers.clear()
        self.finalized = True

    def _fail(self, exc: BaseException) -> None:
        """Record an exception in a hook and switch the verifier off for the rest of the stream."""
        self.failed = f"{type(exc).__name__}: {exc}"
        self.scorer = Unavailable("observer_error", self.method)
        self._view.counter = None

    def _failed_state(self, state):
        """The high-precision state once the verifier has failed: no detections, trails or counts."""
        fld = state.field_uvn
        return replace(state, detections=np.zeros((0, 2)), trails=[], trail_ages=[], count_rate=None, cpc_gross=None,
                       cpc_net=None, pnf=None, speed=None, direction_deg=None,
                       field_uvn=None if fld is None else np.zeros_like(fld), sparkline=np.full(60, np.nan),
                       precision_mode=self.method,
                       precision_status="not_real_time" if self.tracking_only else "unavailable", precision_pending=0)

    # Helpers --------------------------------------------------------------------------------
    def _now(self) -> tuple[float, int]:
        t = getattr(self.pipe, "_last_t", None)
        f = getattr(self.pipe.tracker, "_f_prev", None)
        return (float(t) if t is not None else (self._last_t or 0.0)), (int(f) if f is not None else self._frame_now)

    def _is_withheld(self, t: float) -> bool:
        return any(a - 1e-9 <= t <= b + 1e-9 for a, b in self._withheld)

    def _flags(self, motion: MotionStatus | None) -> set[str]:
        out = set()
        if self.tracking_only:
            out.add("timebase_not_real_time")
        if motion is not None and motion.unsupported:
            out.add("camera_motion")
        return out

    def _hit(self, batch: HitBatch | None, r: tuple, supported: bool) -> HitRecord:
        j = int(r[15])
        vals = patch = None
        peak = float(r[10])
        if batch is not None and 0 <= j < len(batch) and not batch.over_budget[j]:
            vals = batch.values[j].copy()
            patch = batch.patches[j].copy()
        return HitRecord(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[8]), float(r[9]), peak, vals, patch,
                         bool(supported), j)

    def _window(self, key: int, tr) -> Window | None:
        buf = self._buffers.get(key)
        if not buf:
            return None
        hits = list(buf)
        f0 = hits[0].frame
        elapsed = 0
        for r in reversed(tr.records):
            if r[0] < f0:
                break
            elapsed += 1
        vec = window_features(hits, Kin(float(tr.t_first), elapsed))
        if self.vcfg.dump:
            if self.stats["dump_windows"] < DUMP_MAX_ROWS:
                self._dump_windows.append(np.concatenate([[key, hits[-1].t, hits[-1].frame], vec]))
                self.stats["dump_windows"] += 1
            else:
                self.stats["dump_truncated"] = True
        hv = [h.values for h in hits if h.patch is not None and h.values is not None]   # rows of window_patches
        return Window(vec, window_patches(hits), sum(h.values is not None for h in hits),
                      any(h.values is None for h in hits), any(not h.supported for h in hits),
                      np.stack(hv) if hv else None)

    def _feed(self, key: int, t: float, x: float, y: float, t_now: float, retro: bool) -> int:
        """One position of an accepted track into the counter; a new event gets its track's decision
        time, the time it was counted (t_now), the retro flag and its delay (t_now - its own time)."""
        ev = self.counter.update_point(key, t, x, y)
        self._fed.add(key)
        if ev is None:
            return 0
        d = self.ledger.get(key)
        t_acc = d.t_accept if d is not None else math.nan
        self._event_info[ev] = (float(t_acc), float(t_now), bool(retro), float(t_now - ev.t))
        return 1

    def _catch_up(self, key: int, tr, t_now: float, retro: bool, stop_frame: int | None) -> int:
        """Feed the records from the confirming hit to before stop_frame (to the end with None),
        each at its own time, outside the spans when crossings were withheld."""
        if self.counter is None or not self.counting:
            return 0
        d = self.ledger.get(key)
        recs = tr.records
        n, reset = 0, False
        for i in range(max(d.confirm_idx, 0), len(recs)):
            r = recs[i]
            if stop_frame is not None and r[0] == stop_frame:
                break
            if r[14] or not math.isfinite(r[4]):
                continue
            if self.scorer.gated and self._is_withheld(r[1]):
                reset = True
                continue
            if reset:
                self.counter.forget(key)
                reset = False
            n += self._feed(key, r[1], r[4], r[5], t_now, retro)
        if reset:
            self.counter.forget(key)
        return n

    def _sync_counter(self) -> None:
        g = getattr(self.pipe, "_gate_obj", None)
        if g is not None and g is not self._gate_ref:
            from wfglink.measure.gate import GateCounter

            self._gate_ref = g
            self.counter = GateCounter(g, self.cfg)
            self._fed.clear()
            self._event_info.clear()
        self._view.counter = self.counter if self.counting else None

    # Hooks ----------------------------------------------------------------------------------
    def on_frame(self, pipe, frame, image: np.ndarray, t: float, det, snaps, state):
        """The high-precision LiveState of this analysed frame (see the module notes)."""
        self.legacy_state = state
        if self.failed is None:
            try:
                return self._on_frame(pipe, frame, image, t, det, snaps, state)
            except Exception as exc:     # the verifier never stops the legacy analysis
                self._fail(exc)
        return self._failed_state(state)

    def _on_frame(self, pipe, frame, image: np.ndarray, t: float, det, snaps, state):
        t0 = time.perf_counter()
        v = self.vcfg
        self.legacy_state = state
        fidx = int(frame.index)
        self._frame_now = fidx
        h, w = image.shape[:2]
        ms, ds, fresh = self._motion_now(pipe, t, h, w)
        dt = t - self._last_t if self._last_t is not None else 0.0
        self._last_t = t
        self.stats["frames"] += 1
        self.stats["motion_unsupported_s" if ms.unsupported else "supported_s"] += dt
        self._sync_counter()
        if self.counter is not None:
            self.counter.observe(t)
        withhold = bool(self.scorer.gated and ms.unsupported)
        if withhold:
            self.stats["withheld_s"] += dt
            if not self._withholding:
                for k in list(self._fed):
                    if self.counter is not None:
                        self.counter.forget(k)
                self._fed.clear()
                self._withheld.append([t, t])
            else:
                self._withheld[-1][1] = t
        self._withholding = withhold
        horizon = t - (v.deadline_s + 5.0)
        while self._withheld and self._withheld[0][1] < horizon:
            self._withheld.popleft()

        # 1. Features of this frame's detections (earlier frames only in the ring and map).
        tracker = pipe.tracker
        n = len(det)
        prio = np.full(n, 2, np.int64)
        owner = np.full(n, -1, np.int64)
        for tr in tracker.active_tracks(include_tentative=True):
            r = tr.records[-1] if tr.records else None
            if r is None or r[0] != fidx or r[14] or not 0 <= r[15] < n:
                continue
            j = int(r[15])
            owner[j] = self.key(tr.track_id)
            prio[j] = 0 if tr.status == CONFIRMED else (1 if len(tr.records) >= 2 else 2)
        batch, over = self._features(pipe, image, t, fidx, det, ds, fresh, ms, prio, owner)

        # 2. Hits of confirmed tracks; new candidates.
        measured: list[tuple[int, Any]] = []
        for tr in tracker.active_tracks():
            key = self.key(tr.track_id)
            r = tr.records[-1]
            is_hit = r[0] == fidx and not r[14]
            if key not in self.ledger:
                self.ledger.on_confirmed(key, tr, t)
                self._backfill(key, tr)
            elif is_hit and key in self.ledger.active:
                buf = self._buffers.setdefault(key, deque(maxlen=v.window_hits))
                hit = self._hit(batch, r, not ms.unsupported)
                buf.append(hit)
                self._dump_patch(key, hit)
            if is_hit:
                measured.append((key, tr))

        # 3. Checkpoints and the deadline.
        flags = self._flags(ms)
        accepted_now = []
        for key, tr in measured:
            d = self.ledger.active.get(key)
            if d is None or d.state != CANDIDATE:
                continue
            win = self._window(key, tr) or Window(np.full(len(WINDOW_NAMES), np.nan), None, 0)
            if self.ledger.checkpoint(key, t, win, self.scorer, flags, fidx):
                accepted_now.append((key, tr))
        self.ledger.deadline(t, fidx)

        # 4. Static lights.
        by_id = {tr.track_id: tr for tr in tracker.active_tracks()}
        for s in snaps:
            if not s.static:
                continue
            key = self.key(s.track_id)
            if key in self._static_seen:
                continue
            self._static_seen.add(key)
            since = getattr(by_id.get(s.track_id), "static_since", None)
            self.ledger.on_static(key, since, t, fidx)
            if self.counter is not None:
                self.counter.exclude(key, since=since)
            self._fed.discard(key)

        # 5. Counting.
        new_events = 0
        if self.counter is not None and self.counting:
            for key, tr in accepted_now:
                if not self.ledger.accepted(key):
                    continue
                new_events += self._catch_up(key, tr, t, False, stop_frame=fidx)
            if not withhold:
                for s in snaps:
                    if s.static or s.coasted:
                        continue
                    key = self.key(s.track_id)
                    if not self.ledger.accepted(key):
                        continue
                    new_events += self._feed(key, s.t, s.x, s.y, t, False)
            if not self.record and t - self._last_prune > 10.0:
                self.counter.prune_events(t - 120.0)
                while len(self._event_info) > LIVE_ROWS:
                    self._event_info.popitem(last=False)
                self._last_prune = t

        # 6. The high-precision state.
        hp = self._hp_state(pipe, image, t, snaps, new_events, w, h, state, ms, over)
        ms_used = (time.perf_counter() - t0) * 1000.0
        self._ms.append(ms_used)
        self._rows.append({"frame": fidx, "t": float(t), "epoch": self.epoch, "displayed": int(len(hp.detections)),
                           "accepted_tracks": int(len(hp.trails)), "pending": int(hp.precision_pending),
                           "motion_unsupported": bool(ms.unsupported), "moving": bool(ms.moving),
                           "withheld": withhold, "shift_px": float(ms.shift_px), "residual": float(ms.residual),
                           "tiles_changed": int(ms.tiles_changed), "over_budget": over, "cpc_gross": hp.cpc_gross, "count_rate": hp.count_rate,
                           "status": hp.precision_status, "observer_ms": round(ms_used, 3)})
        return hp

    def _motion_now(self, pipe, t: float, h: int, w: int) -> tuple[MotionStatus, Any, bool]:
        """Camera motion of this frame, the detector's native state and whether that state is new
        (a fresh state of the picture's size; otherwise motion keeps its hold and no features)."""
        ds = pipe.detector.state
        fresh = (ds is not self._state_ref and ds is not None and ds.luma is not None
                 and ds.background is not None and ds.sigma is not None and ds.luma.shape == (h, w))
        if fresh:
            ms = self.motion.update(ds.luma, t)
        else:
            ms = MotionStatus(0.0, 0.0, t < self.motion.unsupported_until)
        return ms, ds, fresh

    def _features(self, pipe, image: np.ndarray, t: float, fidx: int, det, ds, fresh: bool, ms: MotionStatus,
                  prio: np.ndarray, owner: np.ndarray) -> tuple[HitBatch, int]:
        """This frame's per-hit features (the ring and the hotspot map hold earlier frames only),
        then the frame enters the ring and the map; the dump rows. Returns the batch and the
        number of rows left without features by the budget. (verify/replay.py replaces this and
        _motion_now with the dumped values.)"""
        v = self.vcfg
        h, w = image.shape[:2]
        n = len(det)
        self.hot.ensure((h, w))
        levels = {f: d.state for f, d in getattr(pipe.detector, "levels", [])}
        mirror = getattr(getattr(pipe.detector, "native", None), "mirror", None)
        block = mirror.block if mirror is not None and mirror.enabled else None
        batch = hit_features(det, ds if fresh else None, self.ring, self.hot, ms, levels, patch_cfg=v.patch, t=t,
                             frame=fidx, priority=prio, cap=v.budget(self.profile), mirror_block=block)
        self._batches.append((batch, not ms.unsupported))
        over = int(batch.over_budget.sum()) if n and fresh else 0     # rows left without features by the budget
        if over:
            self.stats["over_budget_frames"] += 1
        if n:
            self.hot.add(det.x, det.y, t)
        if fresh:
            luma = ds.luma.copy() if image.ndim == 2 else ds.luma
            self.ring.push(RingFrame(fidx, float(t), luma, ds.background, ds.sigma))
            self._state_ref = ds
        if v.dump and n:
            if self.stats["dump_rows"] + n <= DUMP_MAX_ROWS:
                self._dump_hits.append(np.column_stack([np.full(n, fidx), np.full(n, t), np.arange(n), owner,
                                                        batch.over_budget, batch.values]))
                self.stats["dump_rows"] += n
            else:
                self.stats["dump_truncated"] = True
        return batch, over

    def _backfill(self, key: int, tr) -> None:
        """A new candidate's buffer from its earlier hits whose features are still held."""
        batches = {b.frame: (b, ok) for b, ok in self._batches}
        buf = self._buffers.setdefault(key, deque(maxlen=self.vcfg.window_hits))
        for r in tr.records:
            if r[14] or r[15] < 0:
                continue
            b = batches.get(int(r[0]))
            if b is None:
                continue
            hit = self._hit(b[0], r, b[1])
            buf.append(hit)
            self._dump_patch(key, hit)

    def _dump_patch(self, key: int, hit: HitRecord) -> None:
        if self.vcfg.dump and hit.patch is not None:
            if len(self._dump_patches) < DUMP_MAX_ROWS:
                self._dump_patches.append((key, hit.frame, hit.det_index, hit.patch))
                self.stats["dump_patches"] += 1
            else:
                self.stats["dump_truncated"] = True

    def _status(self, ms: MotionStatus, over: int) -> str:
        # The timebase comes first: on a clip that is not real time no method could decide.
        if self.tracking_only:
            return "not_real_time"
        if not getattr(self.scorer, "available", True):
            return "unavailable"
        if self.scorer.gated and ms.unsupported:
            return "camera_motion"
        if over:
            return "incomplete"
        return ""

    def _hp_state(self, pipe, image, t, snaps, new_events, w, h, state, ms, over):
        from wfglink.detect.candidates import Detections

        view = self._view
        acc = [s for s in snaps if self.ledger.accepted(self.key(s.track_id))]
        type(pipe)._update_running(view, t, acc, new_events, w, h)
        pts, idx = self._accepted_now(t)
        if self.record and idx:
            self._shown.extend((self._frame_now, j) for j in idx)
        det_acc = Detections(x=pts[:, 0].copy(), y=pts[:, 1].copy()) if len(pts) else Detections()
        built = type(pipe)._build_state(view, image, t, det_acc, acc, {})
        return replace(state, detections=built.detections, trails=built.trails, trail_ages=built.trail_ages,
                       count_rate=built.count_rate, cpc_gross=built.cpc_gross, cpc_net=built.cpc_net, pnf=built.pnf,
                       speed=built.speed, direction_deg=built.direction_deg, field_uvn=built.field_uvn,
                       sparkline=built.sparkline, precision_mode=self.method, precision_status=self._status(ms, over),
                       precision_pending=self.ledger.pending())

    def on_retire(self, tracks) -> None:
        """Finished tracks: the final checkpoint and decision, a retro catch-up of the counts of a
        track accepted at its end, then its counter state and hit buffer are dropped."""
        if self.failed is not None:
            return
        try:
            self._on_retire(tracks)
        except Exception as exc:     # the verifier never stops the legacy analysis
            self._fail(exc)

    def _on_retire(self, tracks) -> None:
        t, fidx = self._now()
        for tr in tracks:
            key = self.key(tr.track_id)
            if key in self.ledger.active:
                if tr.static and key not in self._static_seen:
                    self._static_seen.add(key)
                    self.ledger.on_static(key, getattr(tr, "static_since", None), t, fidx)
                    if self.counter is not None:
                        self.counter.exclude(key, since=getattr(tr, "static_since", None))
                end = None
                meas = [r for r in tr.records if not r[14]]
                if meas:
                    r = meas[-1]
                    end = (float(r[1]), float(r[2]), float(r[3]), float(r[6]), float(r[7]))
                win = self._window(key, tr)
                acc = self.ledger.on_finished(key, tr.t_end, win, self.scorer, self._flags(self.motion.last), t=t,
                                              frame=fidx, end=end)
                if acc and self.counter is not None:
                    self._catch_up(key, tr, t, True, stop_frame=None)
            if self.counter is not None:
                self.counter.forget(key)
            self._fed.discard(key)
            self._static_seen.discard(key)
            self._buffers.pop(key, None)

    def _accepted_now(self, t: float) -> tuple[np.ndarray, list[int]]:
        pts, idx = [], []
        for tr in self.pipe.tracker.active_tracks():
            if tr.static or not tr.records:
                continue
            r = tr.records[-1]
            if r[1] != t or r[14] or not math.isfinite(r[2]):
                continue
            if self.ledger.accepted(self.key(tr.track_id)):
                pts.append((r[2], r[3]))
                idx.append(int(r[15]))
        return (np.array(pts, dtype=float) if pts else np.zeros((0, 2))), idx

    def accepted_points(self, t: float) -> np.ndarray:
        """Where the accepted, moving tracks were measured in the frame at time t (n, 2): what the
        high-precision screen draws as glowing points."""
        return self._accepted_now(t)[0]

    def shown_detections(self) -> list[tuple[int, int]]:
        """File mode: (frame, detection index) of every point drawn as accepted, in frame order."""
        return list(self._shown)

    # Outputs --------------------------------------------------------------------------------
    def observer_ms(self) -> np.ndarray:
        return np.asarray(self._ms, np.float64)

    def tables(self) -> dict[str, Any]:
        """hp_decisions, hp_events, hp_tracks (the tracks ever accepted: accepted now, or accepted
        and then revoked), hp_frames, and with verify.dump hp_hits and hp_windows."""
        import pandas as pd

        dec = self.ledger.decisions()
        decisions = pd.DataFrame([{k: getattr(d, k) for k in PUBLIC_FIELDS} for d in dec], columns=list(PUBLIC_FIELDS))
        ev = self.counter.events if self.counter is not None else []
        info = [self._event_info.get(e, (math.nan, math.nan, False, math.nan)) for e in ev]
        events = pd.DataFrame({
            "gate": pd.Series([e.gate for e in ev], dtype=object),
            "key": np.array([e.track_id for e in ev], np.int64),
            "epoch": np.array([e.track_id // 10 ** 9 for e in ev], np.int64),
            "track_id": np.array([e.track_id % 10 ** 9 for e in ev], np.int64),
            "t": np.array([e.t for e in ev], np.float64),
            "direction": np.array([e.direction for e in ev], np.int8),
            "s": np.array([e.s for e in ev], np.float64),
            "x": np.array([e.x for e in ev], np.float64),
            "y": np.array([e.y for e in ev], np.float64),
            "t_decision": np.array([i[0] for i in info], np.float64),
            "t_counted": np.array([i[1] for i in info], np.float64),
            "retro": np.array([i[2] for i in info], bool),
            "delay_s": np.array([i[3] for i in info], np.float64)})
        cross: dict[int, list[int]] = {}
        for e in ev:
            cross.setdefault(int(e.track_id), []).append(int(e.direction))
        acc = [d for d in dec if is_ever_accepted(d)]
        tcols = ["key", "epoch", "track_id", "state", "revoked", "t_first", "t_confirm", "t_accept", "t_decision",
                 "retro", "n_hits", "score", "crossings_pos", "crossings_neg"]
        tracks = pd.DataFrame([{"key": d.key, "epoch": d.epoch, "track_id": d.track_id, "state": d.state,
                                "revoked": d.revoked, "t_first": d.t_first, "t_confirm": d.t_confirm,
                                "t_accept": d.t_accept, "t_decision": d.t_decision, "retro": d.retro,
                                "n_hits": d.n_hits, "score": d.score,
                                "crossings_pos": sum(1 for x in cross.get(d.key, []) if x > 0),
                                "crossings_neg": sum(1 for x in cross.get(d.key, []) if x < 0)} for d in acc],
                              columns=tcols)
        frames = pd.DataFrame(list(self._rows), columns=["frame", "t", "epoch", "displayed", "accepted_tracks", "pending",
                                                         "motion_unsupported", "moving", "withheld", "shift_px",
                                                         "residual", "tiles_changed", "over_budget", "cpc_gross",
                                                         "count_rate", "status", "observer_ms"])
        out = {"hp_decisions": decisions, "hp_events": events, "hp_tracks": tracks, "hp_frames": frames}
        if self.vcfg.dump:
            cols = ["frame", "t", "det_index", "key", "over_budget", *FEATURE_NAMES]
            arr = np.vstack(self._dump_hits) if self._dump_hits else np.zeros((0, len(cols)))
            hits = pd.DataFrame(arr, columns=cols)
            for c in ("frame", "det_index", "key"):
                hits[c] = hits[c].astype(np.int64)
            hits["over_budget"] = hits["over_budget"].astype(bool)
            wcols = ["key", "t", "frame", *WINDOW_NAMES]
            warr = np.vstack(self._dump_windows) if self._dump_windows else np.zeros((0, len(wcols)))
            windows = pd.DataFrame(warr, columns=wcols)
            for c in ("key", "frame"):
                windows[c] = windows[c].astype(np.int64)
            out["hp_hits"], out["hp_windows"] = hits, windows
        return out

    def dump_arrays(self) -> dict[str, np.ndarray] | None:
        """The dumped patches (verify.dump): key, frame, det_index and patches (k, 2, P, P) float16."""
        if not self.vcfg.dump:
            return None
        P = self.vcfg.patch.target_px
        d = self._dump_patches
        return {"key": np.array([x[0] for x in d], np.int64), "frame": np.array([x[1] for x in d], np.int64),
                "det_index": np.array([x[2] for x in d], np.int64),
                "patches": np.stack([x[3] for x in d]) if d else np.zeros((0, 2, P, P), np.float16)}

    def decision_counts(self) -> dict[str, Any]:
        """Decisions by state and by state:reason; ever_accepted counts the tracks accepted now
        or revoked (accepted, then static), revoked the latter."""
        by_state = {s: 0 for s in STATES}
        by_reason: dict[str, int] = {}
        ever = revoked = 0
        for d in self.ledger.decisions():
            by_state[d.state] = by_state.get(d.state, 0) + 1
            k = f"{d.state}:{d.reason}" if d.reason else d.state
            by_reason[k] = by_reason.get(k, 0) + 1
            ever += is_ever_accepted(d)
            revoked += bool(d.revoked)
        return {"by_state": by_state, "by_reason": dict(sorted(by_reason.items())), "ever_accepted": ever,
                "revoked": revoked, "archive_dropped": self.ledger.dropped}
