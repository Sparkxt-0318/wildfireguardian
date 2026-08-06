"""Stage-by-stage progress for a job that takes about half a minute.

Round-3 PHASE 19 STEP 1, decision ①.

WHY THIS IS NOT A COSMETIC CONCERN
----------------------------------
A 459-origin scan takes about 27 seconds on the reference machine. A browser
that waits 27 seconds with nothing on screen has, from the operator's side,
crashed — and an operator who believes the system has crashed during a wildfire
will do the thing this project exists to prevent, which is act on their own
guess. So the unit of progress has to be something a person can read while it
moves: not a spinner, and not a percentage that jumps 0 → 100.

WHAT THE STAGES ARE, AND WHY THEIR WEIGHTS LOOK LOPSIDED
--------------------------------------------------------
STEP 0 measured where the 27 seconds go. Routing is essentially all of it, and
every other stage is milliseconds:

    routing   ~26.9 s     one naive solve + one future-aware solve per origin
    cluster    ~0.02 s    DBSCAN over the actionable points
    render     ~0.04 s    three formats per village
    record     ~0.01 s    RUN.json

(The split of the routing line BETWEEN the two solvers is in
``docs/service_layer.md`` §5.1. It does not affect the weights here, which only
need routing's share of the whole, but an early draft of this docstring gave it
wrongly and the corrected profile is worth knowing before optimising anything.)

The weights below are those measurements, not a guess, so the overall bar is
honest even though it means one stage owns 99 % of it. What moves inside that
stage is the per-origin counter — ``경로 산출 137/458`` — which advances about
seventeen times a second and is the thing an operator actually watches.

A4 PDF conversion is a stage of its own and is EXCLUDED from the total, for the
same reason it is excluded everywhere else in this project: it runs after the
dispatch list already exists and scales with village count rather than with the
decision.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

#: Emit at most one callback per this many seconds, except for stage
#: transitions and the final item of a stage, which are always emitted.
DEFAULT_MIN_INTERVAL_S: float = 0.25


@dataclass(frozen=True)
class StageSpec:
    """One named stage of a job."""

    key: str
    label_ko: str
    #: Share of the job's wall clock, measured in STEP 0. Must sum to 1.0
    #: across the stages that are not excluded.
    weight: float
    unit_ko: str = ""
    #: Excluded stages report progress but contribute nothing to the overall
    #: percentage — the bar reaches 100 % when the DECISION is ready.
    excluded_from_total: bool = False


#: The stage plan of one ignition-to-dispatch-list job.
TRIGGER_STAGES: tuple[StageSpec, ...] = (
    StageSpec("load", "자원 적재 — 위험면·보행망·대피 POI", 0.118, "단계"),
    StageSpec("routing", "경로 산출 — 출발지별 대피소 탐색", 0.867, "출발지"),
    StageSpec("cluster", "마을 군집화", 0.003, "지점"),
    StageSpec("render", "전달물 생성 — A4·마을방송·SMS", 0.011, "마을"),
    StageSpec("record", "기록 작성 — RUN.json·viz.json", 0.001, "파일"),
    StageSpec("pdf", "A4 PDF 변환 (목록 확정 이후)", 0.0, "장",
              excluded_from_total=True),
)

_STATES = ("pending", "running", "done", "skipped", "failed")


@dataclass
class StageState:
    spec: StageSpec
    state: str = "pending"
    done: int = 0
    total: int | None = None
    note_ko: str = ""
    started_s: float | None = None
    finished_s: float | None = None
    skip_reason: str = ""

    @property
    def fraction(self) -> float:
        """How far through this stage we are, in [0, 1]."""
        if self.state in ("done", "skipped"):
            return 1.0
        if self.state == "pending" or not self.total:
            return 0.0
        return min(1.0, self.done / float(self.total))

    @property
    def elapsed_s(self) -> float:
        if self.started_s is None:
            return 0.0
        end = self.finished_s if self.finished_s is not None else time.monotonic()
        return end - self.started_s

    def as_dict(self) -> dict:
        d = {
            "key": self.spec.key,
            "label_ko": self.spec.label_ko,
            "state": self.state,
            "done": self.done,
            "total": self.total,
            "unit_ko": self.spec.unit_ko,
            "fraction": round(self.fraction, 4),
            "elapsed_s": round(self.elapsed_s, 3),
            "excluded_from_total": self.spec.excluded_from_total,
        }
        if self.note_ko:
            d["note_ko"] = self.note_ko
        if self.skip_reason:
            d["skip_reason"] = self.skip_reason
        return d

    def text_ko(self) -> str:
        """The one line a screen shows.

        ``경로 산출 — 출발지별 대피소 탐색 137/458 출발지 · 대피소 46곳 탐색``

        The trailing note is what the stage is DOING rather than how far along
        it is: the per-origin cost is one full-graph Dijkstra plus a pick over
        that many shelters, and an operator watching 25 seconds pass deserves
        to know that rather than 「계산 중」.
        """
        if self.state == "skipped":
            return f"{self.spec.label_ko} — 생략 ({self.skip_reason})"
        base = self.spec.label_ko
        if self.total:
            base = (f"{base} {self.done}/{self.total}"
                    f"{' ' + self.spec.unit_ko if self.spec.unit_ko else ''}")
        return f"{base} · {self.note_ko}" if self.note_ko else base


class Progress:
    """Thread-safe, callback-driven progress across a fixed stage plan.

    Every mutator is safe to call from the worker thread while
    :meth:`snapshot` is called from another — which is exactly the shape a
    status endpoint has.
    """

    def __init__(self, stages: tuple[StageSpec, ...] = TRIGGER_STAGES, *,
                 on_event: Callable[[dict], None] | None = None,
                 min_interval_s: float = DEFAULT_MIN_INTERVAL_S) -> None:
        self._lock = threading.RLock()
        self._stages: dict[str, StageState] = {
            s.key: StageState(spec=s) for s in stages}
        self._order: tuple[str, ...] = tuple(s.key for s in stages)
        self._on_event = on_event
        self._min_interval_s = float(min_interval_s)
        self._t0 = time.monotonic()
        self._last_emit = 0.0
        self._current: str | None = None
        self._finished = False

    # -- mutation ----------------------------------------------------------
    def begin(self, key: str, total: int | None = None, *,
              note_ko: str = "") -> None:
        with self._lock:
            st = self._stages[key]
            st.state = "running"
            st.total = int(total) if total else None
            st.done = 0
            st.note_ko = note_ko
            st.started_s = time.monotonic()
            self._current = key
        self._emit(force=True)

    def advance(self, key: str, n: int = 1, *, note_ko: str | None = None) -> None:
        with self._lock:
            st = self._stages[key]
            st.done += int(n)
            if note_ko is not None:
                st.note_ko = note_ko
            last = bool(st.total) and st.done >= st.total
        self._emit(force=last)

    def set_done(self, key: str, done: int, *, total: int | None = None) -> None:
        with self._lock:
            st = self._stages[key]
            if st.state == "pending":
                # A stage whose first callback already carries progress (the PDF
                # phase reports its first sheet, never a zero) must not sit at
                # "pending" while its counter climbs.
                st.state = "running"
                st.started_s = time.monotonic()
                self._current = key
            st.done = int(done)
            if total is not None:
                st.total = int(total)
        self._emit()

    def finish(self, key: str, *, note_ko: str = "") -> None:
        with self._lock:
            st = self._stages[key]
            st.state = "done"
            st.finished_s = time.monotonic()
            if st.total:
                st.done = st.total
            if note_ko:
                st.note_ko = note_ko
        self._emit(force=True)

    def skip(self, key: str, reason: str) -> None:
        with self._lock:
            st = self._stages[key]
            st.state = "skipped"
            st.skip_reason = reason
            st.started_s = st.started_s or time.monotonic()
            st.finished_s = time.monotonic()
        self._emit(force=True)

    def fail(self, key: str, error: str) -> None:
        with self._lock:
            st = self._stages[key]
            st.state = "failed"
            st.note_ko = error
            st.finished_s = time.monotonic()
        self._emit(force=True)

    def close(self) -> None:
        """Mark the whole plan finished, so ``overall`` reads exactly 1.0."""
        with self._lock:
            self._finished = True
        self._emit(force=True)

    # -- reading -----------------------------------------------------------
    @property
    def overall(self) -> float:
        """Weighted completion in [0, 1] over the non-excluded stages."""
        with self._lock:
            if self._finished:
                return 1.0
            total_w = sum(s.spec.weight for s in self._stages.values()
                          if not s.spec.excluded_from_total) or 1.0
            acc = sum(s.spec.weight * s.fraction for s in self._stages.values()
                      if not s.spec.excluded_from_total)
            return max(0.0, min(1.0, acc / total_w))

    def snapshot(self) -> dict:
        """A serialisable picture of where the job is right now."""
        with self._lock:
            cur = self._stages.get(self._current) if self._current else None
            elapsed = time.monotonic() - self._t0
            frac = self.overall
            eta = (elapsed / frac - elapsed) if frac > 0.02 and not self._finished else None
            return {
                "overall_fraction": round(frac, 4),
                "overall_pct": round(100.0 * frac, 1),
                "elapsed_s": round(elapsed, 3),
                "eta_s": (None if eta is None else round(max(0.0, eta), 1)),
                "current_stage": (cur.spec.key if cur else None),
                "current_text_ko": (cur.text_ko() if cur else ""),
                "stages": [self._stages[k].as_dict() for k in self._order],
                "note": "eta_s is elapsed/fraction extrapolation, not a model; "
                        "it is unreliable until the routing stage is under way.",
            }

    # -- internals ---------------------------------------------------------
    def _emit(self, *, force: bool = False) -> None:
        if self._on_event is None:
            return
        now = time.monotonic()
        with self._lock:
            if not force and (now - self._last_emit) < self._min_interval_s:
                return
            self._last_emit = now
        try:
            self._on_event(self.snapshot())
        except Exception:  # noqa: BLE001 - a listener must never kill a job
            pass


class NullProgress(Progress):
    """A Progress that records nothing. The default for batch callers.

    Passing this rather than ``None`` means the service functions have exactly
    one code path, so the path a script exercises is the path the service runs.
    """

    def __init__(self) -> None:
        super().__init__(TRIGGER_STAGES, on_event=None, min_interval_s=1e9)


__all__ = ["DEFAULT_MIN_INTERVAL_S", "NullProgress", "Progress", "StageSpec",
           "StageState", "TRIGGER_STAGES"]
