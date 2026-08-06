"""Process-global state, frozen at start-up and checked around every job.

Round-3 PHASE 19 STEP 1, decisions ③ and ④.

THE PROBLEM A SERVICE HAS AND A SCRIPT DOES NOT
-----------------------------------------------
A script owns its process. It can set a global, run, and exit, and nothing else
was ever going to observe that global. A service runs many requests in one
process, so a global that one request changes is a global every *other* request
silently inherits — including one already half-way through a routing scan.

Two globals in this tree can do that:

``osmnx.settings``
    A module-level namespace (35 public attributes) read by ``load_graphml``
    and ``project_graph``. Nothing in this repository writes to it today, and
    that is exactly why it is worth freezing now: the failure it would cause —
    a graph loaded under different tag settings than the one beside it — is
    silent, and would show up as a routing count that moved for no reason.

``numpy.random``'s global generator
    Seven files under ``scripts/spread_v2/`` seed it — ``00_audit.py``,
    ``01_build_features.py``, ``02_lofo_cv.py``, ``03_comparison.py``,
    ``04_importance.py``, ``05_weather_decomposition.py``, ``06_figures.py``.

    ⚠ Stated precisely, because the imprecise version is alarming and wrong:
    each call is INSIDE a function, not at import time, and each of those files
    is named ``NN_thing.py``, which is not an importable identifier. So none of
    them can be pulled onto the request path by accident, and **no observed
    pollution has ever occurred** — a measured request leaves this digest
    unchanged.

    The risk is structural rather than present, and it is the shape that
    matters: a script owns its process, so seeding the global stream there is
    harmless and invisible. A service does not. The guard exists so that the
    day some future edit reaches for ``np.random.seed`` on the request path,
    the failure is a named exception rather than one request quietly changing
    the next one's answer.

WHAT THIS MODULE DOES, AND DOES NOT
-----------------------------------
It does **not** set anything. Freezing means recording what the values are at
process start and refusing to let a request end with different ones. A guard
that silently restored them would hide the bug; this one names it.
"""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from dataclasses import dataclass

import numpy as np

#: osmnx settings attributes that are not configuration — module machinery that
#: happens to be public on the namespace. Excluded from the digest so an import
#: side effect cannot look like a settings change.
_NON_SETTINGS: frozenset[str] = frozenset({
    "Any", "TYPE_CHECKING", "annotations", "lg", "logging", "os", "Path",
    "datetime", "warnings",
})

_lock = threading.Lock()
_frozen: "GlobalsSnapshot | None" = None


class GlobalStateViolation(RuntimeError):
    """A request changed a process global. The request is at fault, not the guard."""


@dataclass(frozen=True)
class GlobalsSnapshot:
    """What the process globals were when the service started."""

    osmnx_digest: str
    osmnx_n_attrs: int
    numpy_global_digest: str

    def as_dict(self) -> dict:
        return {
            "osmnx_settings_sha256": self.osmnx_digest,
            "osmnx_settings_n_attributes": self.osmnx_n_attrs,
            "numpy_global_rng_sha256": self.numpy_global_digest,
            "note": "recorded once at process start; every job asserts these "
                    "are unchanged on the way out",
        }


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------


def osmnx_settings_items() -> list[tuple[str, str]]:
    """``(name, repr)`` for every osmnx setting, sorted. Empty if osmnx is absent."""
    try:
        import osmnx as ox  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - osmnx is optional for non-routing users
        return []
    s = ox.settings
    out: list[tuple[str, str]] = []
    for name in sorted(dir(s)):
        if name.startswith("_") or name in _NON_SETTINGS:
            continue
        try:
            value = getattr(s, name)
        except Exception:  # noqa: BLE001
            continue
        if callable(value) or isinstance(value, type):
            continue
        out.append((name, repr(value)))
    return out


def osmnx_settings_digest() -> str:
    items = osmnx_settings_items()
    blob = "\n".join(f"{k}={v}" for k, v in items)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def numpy_global_digest() -> str:
    """Digest of numpy's LEGACY global RNG state.

    Any use of ``np.random.rand``/``choice``/``seed`` moves this. Service code
    is required to use an explicit :class:`numpy.random.Generator` instead, so
    this digest must be identical before and after every job.
    """
    state = np.random.get_state()
    blob = repr((state[0], state[1].tobytes(), state[2], state[3], state[4]))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Freeze / assert
# ---------------------------------------------------------------------------


def freeze_globals(*, force: bool = False) -> GlobalsSnapshot:
    """Record the process globals. Idempotent; call at service start-up.

    Returns the snapshot taken the FIRST time it was called unless ``force``,
    so a second call cannot quietly re-baseline a drift that already happened.
    """
    global _frozen
    with _lock:
        if _frozen is not None and not force:
            return _frozen
        _frozen = GlobalsSnapshot(
            osmnx_digest=osmnx_settings_digest(),
            osmnx_n_attrs=len(osmnx_settings_items()),
            numpy_global_digest=numpy_global_digest())
        return _frozen


def frozen_snapshot() -> GlobalsSnapshot:
    """The recorded snapshot, taking one now if the service never froze."""
    return _frozen if _frozen is not None else freeze_globals()


def assert_globals_unchanged(*, where: str = "job") -> None:
    """Raise if a process global moved since :func:`freeze_globals`."""
    snap = frozen_snapshot()
    now_osm = osmnx_settings_digest()
    if now_osm != snap.osmnx_digest:
        raise GlobalStateViolation(
            f"{where}: osmnx.settings changed during a request. osmnx settings "
            "are process-wide, so a request that edits them changes how every "
            "OTHER request loads its graph — silently, and after the fact. Set "
            "them once before the service starts serving, or not at all.")
    now_np = numpy_global_digest()
    if now_np != snap.numpy_global_digest:
        raise GlobalStateViolation(
            f"{where}: numpy's global random state changed during a request. "
            "Service code must draw from an explicit numpy.random.Generator "
            "(np.random.default_rng(seed)) so that two requests with the same "
            "input give the same answer regardless of what else the process "
            "has done.")


@contextmanager
def stable_globals(*, where: str = "job"):
    """Run a block and assert it left the process globals exactly as it found them.

    The assertion runs on the way out of a SUCCESSFUL block only. An exception
    inside is the caller's failure to report and must not be masked by a
    second, less informative one.
    """
    freeze_globals()
    yield
    assert_globals_unchanged(where=where)


__all__ = [
    "GlobalStateViolation", "GlobalsSnapshot", "assert_globals_unchanged",
    "freeze_globals", "frozen_snapshot", "numpy_global_digest",
    "osmnx_settings_digest", "osmnx_settings_items", "stable_globals",
]
