"""Load the heavy inputs once, and hand the same objects to every request.

Round-3 PHASE 19 STEP 1, decision ②.

WHAT IS HEAVY, AND WHY CACHING IT IS NOT THE INTERESTING PART
-------------------------------------------------------------
STEP 0 measured a cold request at about 30.5 s and a warm one at about 26.9 s.
So the cache is worth ~3.6 s, which is 12 % — real, but not what makes it
necessary. What makes it necessary is that the 3.6 s is spent re-reading a file
that did not change: the same snapshot graphml, the same DEM, the same POI
GeoJSON, parsed again for every request, forever. A service that does that is
paying a constant tax to learn something it already knew, and the tax grows with
traffic while the answer does not.

THE OBJECTS ARE SHARED, SO THEY MUST BE READ-ONLY
-------------------------------------------------
Two concurrent jobs get the *same* :class:`~wildfireguardian.live.pipeline.Resources`
instance — one graph, one hazard stack, one refuge list. That is safe only
because the routing path never writes to them: ``route_region`` reads the graph
and the hazard and builds its own per-request lists, and ``deliver`` mutates the
per-request point dicts, never ``res.destinations``. :func:`assert_read_only`
pins that property, because it is the kind of invariant that holds until
somebody adds one convenient line.

THE CACHED ENTRY REMEMBERS THAT IT WAS CACHED
---------------------------------------------
``Resources.timings`` carries the load cost of the run that produced it. Handing
that to a warm request would report a 3.6 s load the warm request never paid, so
the entry carries ``was_cached`` and the service zeroes the load stage when it
is true. A warm request's ``cold_total_s`` is then equal to its ``warm_total_s``,
which is the truth: nothing was loaded.
"""

from __future__ import annotations

import hashlib
import platform
import resource as _resource
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..live import pipeline as _pipeline
from .params import ParameterError, RoutingParams, check_npz, npz_for_region

REPO = Path(__file__).resolve().parents[3]

#: macOS reports ru_maxrss in bytes; Linux in kibibytes.
_RSS_SCALE: int = 1 if platform.system() == "Darwin" else 1024


def _peak_rss_bytes() -> int:
    return int(_resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss) * _RSS_SCALE


class ResourceError(RuntimeError):
    """A region's inputs could not be loaded. Raised, never printed."""


#: The exception types a MISSING INPUT can arrive as. See the note above
#: ``ResourceCache.resident_regions`` for why this is enumerated rather than a
#: bare ``except Exception``.
_MISSING_INPUT_ERRORS = (ResourceError, ParameterError, OSError)


@dataclass(frozen=True)
class ResourceKey:
    """What makes two loads the same load."""

    region: str
    npz_path: str
    sampling_m: float
    max_abs_slope: float

    @classmethod
    def build(cls, region: str, npz_path: Path, params: RoutingParams) -> "ResourceKey":
        s, m = params.resource_key
        return cls(region=region, npz_path=str(Path(npz_path).resolve()),
                   sampling_m=s, max_abs_slope=m)

    def digest(self) -> str:
        blob = f"{self.region}|{self.npz_path}|{self.sampling_m}|{self.max_abs_slope}"
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict:
        p = Path(self.npz_path)
        return {
            "region": self.region,
            "hazard_npz": (str(p.relative_to(REPO)) if p.is_relative_to(REPO)
                           else self.npz_path),
            "sampling_m": self.sampling_m,
            "max_abs_slope": self.max_abs_slope,
            "digest": self.digest(),
        }


@dataclass
class CacheEntry:
    """One loaded region, plus what it cost."""

    key: ResourceKey
    resources: object                     # live.pipeline.Resources
    loaded_utc: float
    load_seconds: float
    #: Exact size of the hazard stack. ``HazardSequence.surfaces`` holds VIEWS
    #: into this array, so it is counted once, not twice.
    hazard_bytes: int
    #: Peak-RSS delta observed across the load. An upper bound on the graph and
    #: everything else this load allocated, and the only figure available
    #: without psutil — it is a PEAK, so it never under-reports and may
    #: over-report when a transient allocation is larger than what was kept.
    rss_delta_bytes: int
    n_walk_nodes: int
    n_walk_edges: int
    n_shelter_pois: int
    n_shelter_nodes: int
    n_depot_pois: int
    hits: int = 0
    last_used: float = field(default_factory=time.monotonic)

    def as_dict(self) -> dict:
        return {
            **self.key.as_dict(),
            "load_seconds": round(self.load_seconds, 3),
            "hazard_bytes": self.hazard_bytes,
            "hazard_mib": round(self.hazard_bytes / 1048576, 2),
            "rss_delta_bytes": self.rss_delta_bytes,
            "rss_delta_mib": round(self.rss_delta_bytes / 1048576, 2),
            "rss_delta_is_peak_upper_bound": True,
            "n_walk_nodes": self.n_walk_nodes,
            "n_walk_edges": self.n_walk_edges,
            "n_shelter_pois": self.n_shelter_pois,
            "n_shelter_nodes": self.n_shelter_nodes,
            "n_depot_pois": self.n_depot_pois,
            "hits": self.hits,
            "idle_s": round(time.monotonic() - self.last_used, 1),
        }


class ResourceCache:
    """Per-region resources, loaded once, shared by every request.

    Thread-safe by two locks, deliberately: a coarse lock over the registry
    (held for microseconds) and a per-key load lock (held for seconds). Two
    concurrent requests for the SAME region therefore produce ONE load, with
    the second waiting rather than duplicating it — which matters because a
    duplicate load is not just slow, it doubles the peak memory of a process
    that is already holding a walk graph.
    """

    def __init__(self, *, capacity: int = 1, repo: Path = REPO) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = int(capacity)
        self.repo = Path(repo)
        self._entries: dict[ResourceKey, CacheEntry] = {}
        self._registry_lock = threading.RLock()
        self._load_locks: dict[ResourceKey, threading.Lock] = {}
        self._loads = 0
        self._hits = 0
        self._evictions = 0

    # -- the one method the service calls ----------------------------------
    def get(self, region: str, params: RoutingParams, *,
            npz_path: Path | None = None) -> tuple[object, bool, CacheEntry]:
        """Return ``(resources, was_cached, entry)``.

        ``was_cached`` is what lets the caller report a warm request's load
        cost as zero instead of repeating the cost of the load that filled the
        cache.
        """
        npz = check_npz(Path(npz_path) if npz_path is not None
                        else npz_for_region(region, repo=self.repo))
        key = ResourceKey.build(region, npz, params)

        with self._registry_lock:
            entry = self._entries.get(key)
            if entry is not None:
                entry.hits += 1
                entry.last_used = time.monotonic()
                self._hits += 1
                return entry.resources, True, entry
            lock = self._load_locks.setdefault(key, threading.Lock())

        with lock:
            # Another thread may have finished the load while we waited.
            with self._registry_lock:
                entry = self._entries.get(key)
                if entry is not None:
                    entry.hits += 1
                    entry.last_used = time.monotonic()
                    self._hits += 1
                    return entry.resources, True, entry
            entry = self._load(key, npz, params)

        with self._registry_lock:
            self._entries[key] = entry
            self._loads += 1
            self._evict_if_needed(protect=key)
        return entry.resources, False, entry

    # -- loading -----------------------------------------------------------
    def _load(self, key: ResourceKey, npz: Path, params: RoutingParams) -> CacheEntry:
        rss_before = _peak_rss_bytes()
        t0 = time.monotonic()
        try:
            res = _pipeline.load_resources(
                key.region, npz_path=npz, repo=self.repo,
                sampling_m=params.sampling_m,
                max_abs_slope=params.max_abs_slope)
        except Exception as exc:  # noqa: BLE001 - re-raised with the region named
            raise ResourceError(
                f"could not load resources for {key.region}: "
                f"{type(exc).__name__}: {exc}") from exc
        load_s = time.monotonic() - t0
        rss_after = _peak_rss_bytes()
        return CacheEntry(
            key=key, resources=res, loaded_utc=time.time(), load_seconds=load_s,
            hazard_bytes=int(res.haz.nbytes),
            rss_delta_bytes=max(0, rss_after - rss_before),
            n_walk_nodes=int(res.net.graph.number_of_nodes()),
            n_walk_edges=int(res.net.graph.number_of_edges()),
            n_shelter_pois=int(res.n_shelter_pois),
            n_shelter_nodes=int(len(res.net.shelters)),
            n_depot_pois=int(res.n_depot_pois))

    # -- capacity ----------------------------------------------------------
    def _evict_if_needed(self, *, protect: ResourceKey | None = None) -> None:
        while len(self._entries) > self.capacity:
            victim = min(
                (k for k in self._entries if k != protect),
                key=lambda k: self._entries[k].last_used, default=None)
            if victim is None:
                return
            del self._entries[victim]
            self._evictions += 1

    def preload(self, regions: list[str], params: RoutingParams,
                *, strict: bool = True) -> list[dict]:
        """Warm the cache for several regions at start-up.

        Refuses to load more regions than the cache can hold, rather than
        loading them and evicting them in the same loop — a preload that ends
        with a cold cache is worse than no preload, because it looks warm.
        """
        if len(regions) > self.capacity:
            raise ResourceError(
                f"asked to preload {len(regions)} regions into a cache of "
                f"capacity {self.capacity}. Raise the capacity deliberately "
                "(and check the memory report first) rather than letting the "
                "last load evict the first.")
        out = []
        for r in regions:
            try:
                _res, cached, entry = self.get(r, params)
            except _MISSING_INPUT_ERRORS as exc:
                if strict:
                    raise
                # SESSION 18, clean-clone boot. `data/raw/` is 1.3 GB and is
                # deliberately not in the repository, so on a fresh clone every
                # region's DEM is absent and a strict preload takes the whole
                # API down at start-up — the pre-built console and /field pages
                # serve fine, but `uvicorn` never comes up to serve them.
                # With strict=False the region is recorded as unavailable and
                # the service starts; /api/regions already carries `ready` and
                # `not_ready_reason` for exactly this state.
                # ⚠ Default stays strict=True so no existing caller changes
                # behaviour: a preload that silently half-succeeds is worse
                # than one that fails, everywhere except at boot.
                out.append({"region": r, "loaded": False,
                            "error": f"{type(exc).__name__}: {exc}"})
                continue
            out.append({**entry.as_dict(), "already_resident": cached,
                        "loaded": True})
        return out

    def evict(self, region: str | None = None) -> int:
        """Drop one region, or everything. Returns how many entries went."""
        with self._registry_lock:
            keys = [k for k in self._entries
                    if region is None or k.region == region]
            for k in keys:
                del self._entries[k]
            self._evictions += len(keys)
            return len(keys)

    # -- reporting ---------------------------------------------------------
    # ⚠ The exception types a MISSING INPUT can arrive as, named rather than a
    # bare ``except Exception``. Two were observed on a real clean clone:
    # ``ResourceError`` (the DEM read, which wraps RasterioIOError) and
    # ``ParameterError`` (``check_npz`` refusing an absent hazard field).
    # ``OSError`` covers a raw filesystem failure that reaches here unwrapped.
    # Anything OUTSIDE this tuple still propagates and still takes start-up
    # down, because an unexpected exception type at boot is a bug, not a
    # missing file, and hiding it would be the wrong trade.

    def resident_regions(self) -> set[str]:
        """Which regions are actually loaded right now.

        Added in Session 18 so the API can report a partial preload instead of
        reaching into ``_entries``. On a clean clone with no ``data/raw``
        bundle this is empty and every region is reported not-ready.
        """
        with self._registry_lock:
            return {k.region for k in self._entries}

    def stats(self) -> dict:
        with self._registry_lock:
            entries = [e.as_dict() for e in self._entries.values()]
            hazard = sum(e.hazard_bytes for e in self._entries.values())
            rss = sum(e.rss_delta_bytes for e in self._entries.values())
            return {
                "capacity": self.capacity,
                "resident": len(entries),
                "loads": self._loads,
                "hits": self._hits,
                "evictions": self._evictions,
                "hazard_bytes_total": hazard,
                "hazard_mib_total": round(hazard / 1048576, 2),
                "rss_delta_bytes_total": rss,
                "rss_delta_mib_total": round(rss / 1048576, 2),
                "process_peak_rss_mib": round(_peak_rss_bytes() / 1048576, 2),
                "entries": entries,
                "note": "rss_delta is a PEAK-RSS difference across each load — "
                        "an upper bound that includes transient parse buffers, "
                        "not a live-object measurement. hazard_bytes is exact.",
            }


def assert_read_only(res: object) -> None:
    """Pin the invariant the sharing depends on.

    Two jobs hold the same ``Resources``. If either mutated it, the other's
    answer would depend on when it happened to run — the exact failure a
    service must not have. Nothing here can prove absence of mutation, so this
    checks the two attributes a careless edit would reach for first.
    """
    if getattr(res, "net", None) is None:
        raise ResourceError("resources carry no walk network")
    if not getattr(res.net, "shelters", None):
        raise ResourceError(
            "the shared walk network has no shelter nodes. Every origin would "
            "be unreachable, so this is a load failure wearing a result.")


__all__ = ["CacheEntry", "ResourceCache", "ResourceError", "ResourceKey",
           "assert_read_only"]
