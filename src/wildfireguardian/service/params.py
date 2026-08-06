"""The parameter set one routing request is made of.

Round-3 PHASE 19 STEP 1.

WHY A FROZEN DATACLASS RATHER THAN ``args``
-------------------------------------------
Every entry point in ``scripts/`` reaches its knobs through an
:class:`argparse.Namespace`. That is fine for a process that runs once and
exits, and wrong for a service: a Namespace is mutable, unhashable, carries
script-only fields (``--reset-state``, ``--no-pdf``) beside computational ones,
and cannot be used as a cache key. This is the computational subset, frozen, so
that

* two requests with equal parameters are provably equal (``==`` and ``hash``),
* a request cannot mutate the parameters of a request already running,
* the resource cache can key on the parameters that actually change what is
  loaded.

⚠ EVERY DEFAULT IS THE SAME LOOKUP THE SCRIPTS ALREADY DO, with the same
fallback literal. This file introduces no new value. If a default here ever
disagrees with the script it replaced, the routing answer moves, and that is the
one thing this PHASE may not do — ``tests/test_service_layer.py`` pins each one
against the argparse default it came from.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path

from ..config import get as _cfg

REPO = Path(__file__).resolve().parents[3]

#: Region -> the pre-computed hazard field it is routed on. Yeongdeok's is the
#: CANONICAL field; ``routing_demo.npz`` is the output of a reverted run and is
#: refused outright (HANDOFF_ROUND3.md §2-A, rule 20).
FORBIDDEN_NPZ_NAMES: frozenset[str] = frozenset({"routing_demo.npz"})


class ParameterError(ValueError):
    """A request's parameters are not usable. Raised, never printed."""


def npz_for_region(region: str, *, repo: Path = REPO) -> Path:
    """The hazard field this region routes on.

    Identical rule to ``run_manual_trigger.main``: Yeongdeok reads
    ``live.hazard_npz``; every other region reads its own per-region field.
    """
    if region == "yeongdeok_2025":
        rel = _cfg("live.hazard_npz", "data/processed/routing_demo_canonical.npz")
    else:
        rel = f"data/processed/hazard_{region}.npz"
    return repo / str(rel)


def walk_bbox(region: str) -> tuple[float, float, float, float]:
    """The registered walk bbox (W, S, E, N) for ``region``."""
    table = _cfg("bbox.multi_region_walk_bbox", {}) or {}
    if region not in table:
        raise ParameterError(
            f"{region!r} has no registered walk bbox. The walk network, the "
            "refuges and the hazard field are prepared for the registered "
            "regions only; routing outside one would manufacture evidence that "
            "does not exist.")
    w, s, e, n = tuple(table[region])
    return float(w), float(s), float(e), float(n)


def known_regions() -> tuple[str, ...]:
    """Every region with a registered walk bbox, in config order."""
    return tuple((_cfg("bbox.multi_region_walk_bbox", {}) or {}).keys())


@dataclass(frozen=True)
class RoutingParams:
    """The computational parameters of one 459-series scan.

    Frozen and hashable so it can key a cache and cross a thread boundary.
    Field-for-field the argparse defaults of ``run_manual_trigger.py`` and
    ``run_live_detection.py``.
    """

    # -- the scan -----------------------------------------------------------
    p_cut: float = 0.5
    time_budget_min: float = 600.0
    time_step_min: float = 10.0
    stride: int = 18
    #: 0 = every candidate origin. Non-zero is a SMOKE TEST truncation and is
    #: carried into the result so a truncated run can never be quoted.
    limit_origins: int = 0

    # -- the network build (part of the resource cache key) -----------------
    sampling_m: float = 60.0
    max_abs_slope: float = 0.60

    # -- delivery -----------------------------------------------------------
    eps_m: float = 500.0
    collect_routes: int = 12

    # -- labelling ----------------------------------------------------------
    applicability_radius_km: float = 15.0

    @classmethod
    def from_config(cls, **overrides) -> "RoutingParams":
        """Build from ``config/default.yaml``, then apply ``overrides``.

        The literals below are the historical fallbacks, unchanged, so an
        absent or unreadable config degrades to the committed behaviour rather
        than to something new — the same stance :mod:`wildfireguardian.config`
        takes.
        """
        base = cls(
            p_cut=float(_cfg("pedestrian.walk_cutoff_p", 0.5)),
            time_budget_min=float(_cfg("pedestrian.walk_budget_min", 600.0)),
            time_step_min=float(_cfg("time.routing_time_step_min", 10.0)),
            stride=int(_cfg("origin_scan.real_osm_stride", 18)),
            sampling_m=float(_cfg("pedestrian.slope_sampling_m", 60.0)),
            max_abs_slope=float(_cfg("pedestrian.max_abs_slope", 0.60)),
            applicability_radius_km=float(
                _cfg("live.trigger.field_applicability_radius_km", 15.0)),
        )
        return replace(base, **overrides) if overrides else base

    @classmethod
    def from_args(cls, args) -> "RoutingParams":
        """Lift the computational subset out of an argparse Namespace.

        This is the seam that keeps the scripts thin: the CLI keeps owning
        flags, and everything that changes a NUMBER lives here.
        """
        base = cls.from_config()
        got = {}
        for field_name, arg_name in (
                ("p_cut", "p_cut"),
                ("time_budget_min", "time_budget_min"),
                ("time_step_min", "time_step_min"),
                ("stride", "stride"),
                ("limit_origins", "limit_origins"),
                ("sampling_m", "sampling_m"),
                ("max_abs_slope", "max_abs_slope"),
                ("eps_m", "eps_m"),
                ("collect_routes", "collect_routes"),
                ("applicability_radius_km", "applicability_radius_km")):
            v = getattr(args, arg_name, None)
            if v is not None:
                got[field_name] = v
        return replace(base, **got)

    # -- the cache key ------------------------------------------------------
    @property
    def resource_key(self) -> tuple[float, float]:
        """The subset that changes what is LOADED, not what is computed on it.

        The walk network is built once per (sampling_m, max_abs_slope); p_cut,
        the budget and the stride change only the scan that runs over it. Two
        requests that differ only in stride therefore share one loaded network,
        which is the whole point of the cache.
        """
        return (float(self.sampling_m), float(self.max_abs_slope))

    def as_dict(self) -> dict:
        d = asdict(self)
        d["routing_objective"] = "length_m (distance-ranked)"
        d["source"] = "config/default.yaml — identical to the 459-series runs"
        return d

    def as_run_parameters(self) -> dict:
        """The ``parameters`` block the RUN.json schema already carries.

        Key names are the committed ones (``origin_scan_stride``, not
        ``stride``) so a RUN.json written through the service is readable by
        every consumer that reads one written by a script — including
        ``tests/test_manual_trigger.py``.
        """
        return {
            "p_cut": self.p_cut,
            "time_budget_min": self.time_budget_min,
            "time_step_min": self.time_step_min,
            "origin_scan_stride": self.stride,
            "eps_m": self.eps_m,
            "routing_objective": "length_m (distance-ranked)",
            "source": "config/default.yaml — identical to the 459-series runs",
        }


def check_npz(path: Path) -> Path:
    """Refuse a missing field, and refuse the reverted run's field by name."""
    p = Path(path)
    if p.name in FORBIDDEN_NPZ_NAMES:
        raise ParameterError(
            f"{p.name} is the output of a REVERTED run and must not be consumed "
            "in new work (HANDOFF_ROUND3.md §2-A). Use "
            "routing_demo_canonical.npz.")
    if not p.exists():
        raise ParameterError(f"hazard field missing: {p}")
    return p


def check_in_region(region: str, lat: float, lon: float) -> dict:
    """Is this coordinate inside the region's registered walk bbox?

    Returns the verdict as data. The CLI turns a False into exit 3 and a
    Korean explanation; a future HTTP layer would turn it into a 422. Neither
    decision belongs here.
    """
    w, s, e, n = walk_bbox(region)
    inside = (w <= lon <= e) and (s <= lat <= n)
    return {
        "region": region,
        "bbox_wsen": [w, s, e, n],
        "lat": float(lat),
        "lon": float(lon),
        "inside_registered_region": bool(inside),
        "reason_ko": (
            "등록 지역 안입니다."
            if inside else
            "좌표가 등록 지역 bbox 밖입니다. 이 지역의 보행망·대피소·위험면은 "
            "이 범위에 대해서만 준비되어 있으므로, 범위 밖 좌표로 산출하면 없는 "
            "근거를 만들어내는 것이 됩니다."),
    }


__all__ = [
    "FORBIDDEN_NPZ_NAMES", "ParameterError", "RoutingParams", "check_in_region",
    "check_npz", "known_regions", "npz_for_region", "walk_bbox",
]
