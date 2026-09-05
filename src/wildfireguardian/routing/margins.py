"""Round-trip margins, withdrawal trigger lines, and advisory output.

Session 8, Phase 1. Motivated by a 현장 실무자 자문 (N = 1, qualitative —
``docs/firefighter_consultation.md``; a statement of field practice, never a
data source): a categorical 「구조대가 갈 수 없습니다」 is the wrong shape for
field use, and withdrawal is a *spatial* judgment (wind direction/speed), not a
clock. Cova, Dennison, Kim & Moritz (2005, *Transactions in GIS*) formalise the
spatial form as wildfire evacuation **trigger points**: reverse-model fire
spread from the asset so that when fire crosses a geographic line, the action
must begin.

Three additions, all **on top of** the committed one-way machinery in
:mod:`.rescue` (which is unchanged — the 7-key classification, the four-way
split and the dispatch ranking stay exactly as committed):

1. **Round-trip margin** (:func:`round_trip_margin`). The committed urgency is
   one-way (``ingress_survival_time − responder_ETA``). The margin extends it
   to the full mission::

       M = S − (ETA_in + t_load + ETA_out)

   where ``S`` is the corridor's earliest cutoff-crossing slice, ``t_load`` is
   the on-scene pickup time (NEW, ASSUMED, swept), and the egress leg is
   evaluated **at the egress departure time** ``ETA_in + t_load`` — the same
   corridor at ingress time and at egress time is a different edge of the
   time-expanded graph. A corridor survivable at ingress but closed at egress
   must produce a negative margin (pinned by a test).

2. **Withdrawal trigger line** (:func:`withdrawal_trigger_line`). The spatial
   dual of the margin: the isochrone of the hazard field whose arrival time
   equals the mission's latest safe commitment time (the clock time at which
   ``M(t) → 0``).

3. **Advisory output** (:func:`advisory`). ``margin_minutes`` (signed),
   ``margin_band`` (derived from the committed vehicle-cutoff sweep range —
   real, or ``null``), ``recommendation`` ∈ {진입 권장, 진입 보류 권장,
   철수 권장} (advisory wording, never 불가), ``trigger_line``, and ``basis``
   (the fields the recommendation was computed from, so a human commander can
   audit it).

⚠ Hazard time resolution is overpass-scale (hours), so trigger lines are
**planning-scale, not tactical**: "Time resolution is overpass-scale (hours).
Rules out tactical (minute-scale) use, exactly as the parent routing report
states." (``docs/rescue_routing.md`` §5 — wording reused, not softened.)
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace

import networkx as nx
import numpy as np

from ..config import get as _cfg
from .evacuation import future_aware_route
from .future_front import RoadNetwork
from .hazard import HazardSequence
from .rescue import (
    RescueConfig,
    corridor_survival_time,
    sample_corridor_points,
)

#: Vehicle-cutoff values over which the margin band is derived. This is the
#: COMMITTED sweep range from docs/rescue_routing.md §4a (the 2-D sweep) — the
#: band is real spread over an already-reported axis, not an invented interval.
BAND_CUTOFFS: tuple[float, ...] = tuple(
    _cfg("responder.vehicle_cutoff_sweep", (0.5, 0.6, 0.7, 0.8, 0.9)))

#: The three advisory wordings. Advisory, auditable, never 불가.
RECOMMENDATIONS: tuple[str, str, str] = ("진입 권장", "진입 보류 권장", "철수 권장")


def _round_or_none(v: float | None, nd: int = 2) -> float | None:
    if v is None or (isinstance(v, float) and math.isinf(v)):
        return None
    return round(float(v), nd)


@dataclass
class RoundTripMargin:
    """Round-trip mission margin for one dispatchable home from one depot."""

    home_node: int
    depot_index: int | None
    egress_policy: str                      # "same_route" | "free"
    eta_in_min: float                       # dispatch delay + ingress travel
    t_load_min: float                       # ASSUMED on-scene pickup time
    eta_out_min: float                      # egress travel time (leg only)
    egress_departure_min: float             # eta_in + t_load (clock)
    ingress_survival_time_min: float        # S_in: earliest cut slice, ingress corridor
    egress_survival_time_min: float         # S_out: earliest cut slice, egress corridor
    margin_minutes: float                   # min over legs; == S − round-trip for same_route
    corridor_never_cut: bool                # both legs' corridors never reach cutoff
    note: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("eta_in_min", "t_load_min", "eta_out_min",
                  "egress_departure_min", "ingress_survival_time_min",
                  "egress_survival_time_min", "margin_minutes"):
            d[k] = _round_or_none(d[k])
        return d


def round_trip_margin(
    drive: RoadNetwork, depot_node: int, home_node: int, hazard: HazardSequence,
    cfg: RescueConfig, *, depot_index: int | None = 0,
) -> RoundTripMargin:
    """Compute the round-trip margin ``M = S − (ETA_in + t_load + ETA_out)``.

    The ingress leg is the committed shortest-time drive corridor (identical to
    :func:`~.rescue.ingress_corridor`). The egress leg depends on
    ``cfg.egress_policy``:

    - ``"same_route"`` (default; doctrine per the field consultation, N = 1):
      the ingress corridor reversed. Same points, so the corridor's earliest
      cutoff-crossing slice ``S`` is shared — but the *comparison time* is the
      egress leg's, so the margin is negative whenever the corridor closes
      after the responder gets in but before the round trip completes. This is
      the 의성 responder-isolation failure mode.
    - ``"free"``: the exposure-minimising time-expanded router picks a fresh
      egress route departing at ``ETA_in + t_load`` (so it meets the fire as it
      will be at egress time). If no safe egress route exists within the
      responder budget the margin is ``-inf`` (serialised ``None`` with an
      explanatory note — reported, never imputed).

    The margin is ``min(S_in − ETA_in, S_out − (ETA_in + t_load + ETA_out))``:
    reach the scene before the ingress corridor closes, AND complete the exit
    before the egress corridor closes. For ``same_route`` the second term is
    the binding one, so this reduces exactly to the brief's
    ``M(t) = ingress_survival_time − (t + ETA_in + t_load + ETA_out)`` at
    ``t = 0``.
    """
    if cfg.egress_policy not in ("same_route", "free"):
        raise ValueError(f"egress_policy must be 'same_route' or 'free', "
                         f"got {cfg.egress_policy!r}")
    try:
        travel_in, path = nx.single_source_dijkstra(
            drive.graph, depot_node, target=home_node, weight="time_min")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return RoundTripMargin(
            home_node=int(home_node), depot_index=depot_index,
            egress_policy=cfg.egress_policy, eta_in_min=math.inf,
            t_load_min=cfg.t_load_min, eta_out_min=math.inf,
            egress_departure_min=math.inf, ingress_survival_time_min=math.inf,
            egress_survival_time_min=math.inf, margin_minutes=-math.inf,
            corridor_never_cut=False, note="no drive path depot->home")

    eta_in = cfg.responder_dispatch_delay_min + travel_in
    xs, ys, _ = sample_corridor_points(drive, path, cfg.ingress_sample_spacing_m)
    s_in = corridor_survival_time(hazard, xs, ys, cfg.vehicle_cutoff)
    t_out = eta_in + cfg.t_load_min

    note = ""
    if cfg.egress_policy == "same_route":
        eta_out = travel_in                      # same corridor, reversed
        s_out = s_in                             # same sampled points
    else:
        egress_net = RoadNetwork(graph=drive.graph, shelters={depot_node})
        rt = future_aware_route(
            egress_net, home_node, hazard, departure_min=t_out,
            time_budget_min=cfg.responder_time_budget_min,
            p_cut=cfg.vehicle_cutoff, time_step_min=cfg.time_step_min)
        if rt.reached and not rt.enters_hazard:
            eta_out = rt.total_time_min
            exs, eys, _ = sample_corridor_points(drive, rt.route,
                                                 cfg.ingress_sample_spacing_m)
            s_out = corridor_survival_time(hazard, exs, eys, cfg.vehicle_cutoff)
        else:
            return RoundTripMargin(
                home_node=int(home_node), depot_index=depot_index,
                egress_policy=cfg.egress_policy, eta_in_min=eta_in,
                t_load_min=cfg.t_load_min, eta_out_min=math.inf,
                egress_departure_min=t_out, ingress_survival_time_min=s_in,
                egress_survival_time_min=-math.inf, margin_minutes=-math.inf,
                corridor_never_cut=False,
                note="no safe egress route at the egress departure time "
                     "(survival-aware router, detours allowed)")

    margin = min(s_in - eta_in, s_out - (t_out + eta_out))
    never_cut = math.isinf(s_in) and math.isinf(s_out)
    return RoundTripMargin(
        home_node=int(home_node), depot_index=depot_index,
        egress_policy=cfg.egress_policy, eta_in_min=eta_in,
        t_load_min=cfg.t_load_min, eta_out_min=eta_out,
        egress_departure_min=t_out, ingress_survival_time_min=s_in,
        egress_survival_time_min=s_out, margin_minutes=margin,
        corridor_never_cut=never_cut, note=note)


# ---------------------------------------------------------------------------
# Withdrawal trigger line — the spatial dual of the margin
# ---------------------------------------------------------------------------


@dataclass
class TriggerLine:
    """The hazard isochrone at the mission's latest safe commitment time.

    ⚠ Hazard time resolution is overpass-scale (hours), so trigger lines are
    **planning-scale, not tactical**: "Time resolution is overpass-scale
    (hours). Rules out tactical (minute-scale) use, exactly as the parent
    routing report states." (docs/rescue_routing.md §5.)
    """

    cells_xy: list[list[float]] = field(default_factory=list)   # EPSG:5179 cell centres
    cells_rc: list[list[int]] = field(default_factory=list)     # (row, col) on the hazard grid
    arrival_time_min: float | None = None    # the isochrone's slice time
    hazard_slice_index: int | None = None    # index into hazard.times_min
    latest_safe_commitment_min: float | None = None
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "cells_xy": [[round(x, 1), round(y, 1)] for x, y in self.cells_xy],
            "cells_rc": self.cells_rc,
            "arrival_time_min": _round_or_none(self.arrival_time_min),
            "hazard_slice_index": self.hazard_slice_index,
            "latest_safe_commitment_min": _round_or_none(self.latest_safe_commitment_min),
            "note": self.note,
        }


def _cell_arrival_times(hazard: HazardSequence, cutoff: float) -> np.ndarray:
    """Per-cell earliest ``times_min`` slice at which the cell reaches ``cutoff``.

    Back-propagation over the existing hazard time slices (no new model): the
    result is exactly one of the model's forecast times, or ``inf`` if the cell
    never crosses within the horizon.
    """
    arr = np.full((hazard.grid.nrows, hazard.grid.ncols), np.inf)
    for i, t in enumerate(hazard.times_min):
        newly = (hazard.surfaces[i] >= cutoff) & ~np.isfinite(arr)
        arr[newly] = float(t)
    return arr


def withdrawal_trigger_line(
    hazard: HazardSequence, cfg: RescueConfig, margin: RoundTripMargin,
) -> TriggerLine:
    """Isochrone of the hazard field at the mission's latest safe commitment time.

    The latest safe commitment time is the clock time ``t*`` at which the
    round-trip margin reaches zero: ``M(t) = S − (t + ETA_in + t_load +
    ETA_out) = 0`` gives ``t* = margin_minutes`` (with the decision clock at
    ``t = 0``). The emitted cell set is every hazard cell whose arrival time
    equals the **latest forecast slice ≤ t*** (snapping down is the
    conservative direction: the line is crossed no later than the true
    continuous-time trigger). When fire reaches these cells, commitment to
    this mission must have already begun.

    ⚠ Planning-scale only. Hazard time resolution is overpass-scale (hours):
    "Time resolution is overpass-scale (hours). Rules out tactical
    (minute-scale) use, exactly as the parent routing report states."
    """
    m = margin.margin_minutes
    if margin.corridor_never_cut or math.isinf(m) and m > 0:
        return TriggerLine(note="corridor never reaches the vehicle cutoff "
                                "within the forecast horizon — no trigger line")
    if math.isinf(m):  # -inf: no feasible round trip at all
        return TriggerLine(latest_safe_commitment_min=None,
                           note="no feasible round trip (margin -inf) — "
                                "commitment window already closed")
    times = hazard.times_min
    if m < float(times[0]):
        return TriggerLine(latest_safe_commitment_min=m,
                           note="latest safe commitment time precedes the "
                                "first forecast slice — commitment window "
                                "already closed at planning resolution")
    idx = int(np.searchsorted(times, m, side="right")) - 1
    slice_t = float(times[idx])
    arr = _cell_arrival_times(hazard, cfg.vehicle_cutoff)
    rows, cols = np.where(arr == slice_t)
    g = hazard.grid
    cells_xy = []
    cells_rc = []
    for r, c in zip(rows.tolist(), cols.tolist()):
        x, y = g.center_xy(r, c)
        cells_xy.append([float(x), float(y)])
        cells_rc.append([int(r), int(c)])
    return TriggerLine(
        cells_xy=cells_xy, cells_rc=cells_rc, arrival_time_min=slice_t,
        hazard_slice_index=idx, latest_safe_commitment_min=m,
        note=("planning-scale, not tactical: hazard time resolution is "
              "overpass-scale (hours)"))


# ---------------------------------------------------------------------------
# Advisory output — margins + band + recommendation + basis
# ---------------------------------------------------------------------------


def margin_band(
    drive: RoadNetwork, depot_node: int, home_node: int, hazard: HazardSequence,
    cfg: RescueConfig, *, cutoffs: tuple[float, ...] = BAND_CUTOFFS,
) -> dict | None:
    """Margin spread over the committed vehicle-cutoff sweep range, or ``None``.

    The band is derived from something real: re-evaluating the margin at each
    cutoff of the already-reported §4a sweep axis. If no cutoff yields a
    finite margin (e.g. the corridor never crosses any swept cutoff within the
    horizon) there is no defensible interval and ``None`` is returned — an
    interval is never invented.
    """
    vals = []
    for c in cutoffs:
        m = round_trip_margin(drive, depot_node, home_node, hazard,
                              replace(cfg, vehicle_cutoff=float(c)))
        if math.isfinite(m.margin_minutes):
            vals.append(m.margin_minutes)
    if not vals:
        return None
    return {"low_min": round(min(vals), 2), "high_min": round(max(vals), 2),
            "n_finite": len(vals),
            "derived_from": f"vehicle_cutoff sweep {list(cutoffs)} "
                            "(the committed §4a sweep axis)"}


def recommend(margin_minutes: float, cfg: RescueConfig) -> str:
    """Advisory wording from the signed margin. Never 불가.

    - margin > safety margin        → 진입 권장
    - 0 < margin ≤ safety margin    → 진입 보류 권장 (thin margin)
    - margin ≤ 0                    → 철수 권장
    """
    if margin_minutes > cfg.responder_safety_margin_min:
        return RECOMMENDATIONS[0]
    if margin_minutes > 0.0:
        return RECOMMENDATIONS[1]
    return RECOMMENDATIONS[2]


def advisory(
    drive: RoadNetwork, depot_node: int, home_node: int, hazard: HazardSequence,
    cfg: RescueConfig, *, depot_index: int | None = 0, with_band: bool = True,
    with_trigger: bool = True,
) -> dict:
    """The human-facing advisory record for one home (machine keys untouched).

    Replaces the categorical reachability verdict *in the human-facing output
    only* — the 7-key classification and the four-way split stay unchanged.
    """
    m = round_trip_margin(drive, depot_node, home_node, hazard, cfg,
                          depot_index=depot_index)
    band = (margin_band(drive, depot_node, home_node, hazard, cfg)
            if with_band else None)
    trigger = (withdrawal_trigger_line(hazard, cfg, m).as_dict()
               if with_trigger else None)
    rec = recommend(m.margin_minutes, cfg)
    return {
        "home_node": m.home_node,
        "margin_minutes": _round_or_none(m.margin_minutes),
        "margin_band": band,
        "recommendation": rec,
        "trigger_line": trigger,
        "basis": {
            "ingress_survival_time_min": _round_or_none(m.ingress_survival_time_min),
            "eta_in_min": _round_or_none(m.eta_in_min),
            "t_load_min": m.t_load_min,
            "t_load_source": "assumed",
            "eta_out_min": _round_or_none(m.eta_out_min),
            "egress_policy": m.egress_policy,
            "egress_departure_min": _round_or_none(m.egress_departure_min),
            "egress_survival_time_min": _round_or_none(m.egress_survival_time_min),
            "vehicle_cutoff": cfg.vehicle_cutoff,
            "safety_margin_min": cfg.responder_safety_margin_min,
            "formula": "M = min(S_in - ETA_in, S_out - (ETA_in + t_load + ETA_out))",
        },
        "note": m.note,
    }


__all__ = [
    "BAND_CUTOFFS",
    "RECOMMENDATIONS",
    "RoundTripMargin",
    "round_trip_margin",
    "TriggerLine",
    "withdrawal_trigger_line",
    "margin_band",
    "recommend",
    "advisory",
]
