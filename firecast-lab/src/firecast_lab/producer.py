"""hazard_contract v1 scenario sets from member arrival fields: the Track A producer.

Member hours after the cutoff (``members`` conventions) become seconds after the issue time, which is the cutoff.
With ``T = heat.burn_duration_s`` (scalar policy):

| member hours                 | ignite_s  | extinguish_s | supported | meaning |
|------------------------------|-----------|--------------|-----------|---------|
| (0, horizon]                 | 3600 h    | ignite + T   | yes       | new burn in the horizon |
| +inf                         | +inf      | +inf         | yes       | does not burn within the horizon |
| <= 0 (finite)                | 3600 h    | ignite + T   | yes       | burned at the cutoff, ignited at its reconstructed arrival (burned out if ignite + T <= 0) |
| -inf                         | -T        | T            | yes       | burned at the cutoff, age unknown: the packet rule, burning through the first T seconds |
| NaN                          | NaN       | NaN          | no        | unknown |

Support policy (ground rule 4 and DATA_NOTES section 5):

- A cell is supported in a member iff the producing model had every cutoff input it needs there and the member's
  arrival is known. Unknown cells carry NaN and ``supported=False``: any query touching them is unresolved.
- Cells outside the reconstruction domain (no reconstructed arrival, i.e. outside the final burn scar) ARE
  supported and carry the model's forecast: their cutoff state "not burned" follows from the final perimeter, and
  support is decided by cutoff-time inputs only. Marking them unknown would make the final scar the support mask,
  which leaks where the fire stops and turns every route outside the eventual scar into "unresolved".
- Cells beyond the grid are outside the set; hazard_contract marks queries touching them unsupported. The grid
  edge is cut in hindsight (Korea: the final perimeter's bounding box; US: 2 km beyond it), so
  ``extra["edge_burning_members"]`` counts members with fire on the grid edge.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from hazard_contract import HeatSource, ScenarioMeta, ScenarioSet

from firecast_lab import __version__
from firecast_lab.data import Window, run_record

PACKET_HEAT = HeatSource(
    fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
    transmissivity=1.0, burn_duration_policy="scalar", burn_duration_s=3970.4642815249267, emission_height_m=5.0,
    receiver_height_m=0.0,
    note="repo hazard-packet parameters (experimental/scenario-members/export_v3.py: fuel load 10 kg/m2, consumed "
         "fraction 0.1, FBFM40 heat content 18.608 MJ/kg, radiative fraction 0.30, emission 5 m, receiver 0 m, "
         "transmissivity 1, cell front-crossing duration T)")
SUPPORT_POLICY = ("supported iff the model had its cutoff inputs and the member arrival is known; cells outside the "
                  "reconstruction domain are supported (cutoff state 'not burned', support from cutoff inputs "
                  "only); unknown -> NaN and supported=False; beyond the grid -> outside the set")
TIMING = ("hours after the cutoff; within the hour uniform timing (members.coherent_members, c651 offsets); "
          "present fire ignites at its reconstructed arrival")


def _jsonable(value):
    return json.loads(json.dumps(value, default=lambda v: v.item() if hasattr(v, "item") else str(v)))


def scenario_set(hours, supported=None, *, transform, crs_epsg: int, issue_time_utc, horizon_h: float,
                 model_version: str, weather_source: str, seed, config: dict, synthetic: bool,
                 heat: HeatSource = PACKET_HEAT, extra: dict | None = None) -> ScenarioSet:
    """A v1 scenario set (``source="model"``) from member hours ``[K, H, W]`` (table above). ``supported``: the
    model's own support, ``[H, W]`` or ``[K, H, W]``; members are unsupported wherever their hours are NaN."""
    hours = np.asarray(hours, dtype=np.float64)
    if hours.ndim != 3:
        raise ValueError("member hours must have shape [K, H, W]")
    known = ~np.isnan(hours)
    support = known if supported is None else known & np.broadcast_to(np.asarray(supported, dtype=bool), hours.shape)
    with np.errstate(invalid="ignore"):
        if (support & np.isfinite(hours) & (hours > horizon_h)).any():
            raise ValueError("finite member hours beyond the horizon: a member says nothing after the horizon")
    T = heat.burn_duration_s
    ignite = np.where(hours == -np.inf, -T, hours * 3600.0)
    extinguish = np.where(hours == -np.inf, T, ignite + T)            # inf stays inf
    ignite, extinguish = np.where(support, ignite, np.nan), np.where(support, extinguish, np.nan)
    if isinstance(issue_time_utc, str):
        issue_time_utc = datetime.fromisoformat(issue_time_utc.replace("Z", "+00:00"))
    meta = ScenarioMeta(
        crs_epsg=int(crs_epsg), transform=tuple(float(v) for v in transform), height=hours.shape[1],
        width=hours.shape[2], K=hours.shape[0], issue_time_utc=issue_time_utc.astimezone(timezone.utc),
        horizon_s=float(horizon_h) * 3600.0, source="model", synthetic=bool(synthetic), model_version=model_version,
        weather_source=weather_source, heat_source=heat, provenance=_jsonable(run_record(config, seed)),
        extra=_jsonable(dict(support_policy=SUPPORT_POLICY, timing=TIMING,
                             unsupported_cells=int((~support).any(axis=0).sum()), **(extra or {}))))
    s = ScenarioSet(ignite, extinguish, support, meta)
    s.meta = meta.model_copy(update=dict(extra=dict(meta.extra, edge_burning_members=int(s.edge_burning().sum()))))
    return s


def from_window(window: Window, hours, *, model, seed, config: dict, supported=None) -> ScenarioSet:
    """The scenario set of one window's members: issue time = cutoff, horizon = the window's lead, grid and CRS of
    the event, model version and weather source of the baseline that made the members."""
    return scenario_set(hours, supported, transform=window.transform, crs_epsg=window.epsg,
                        issue_time_utc=window.cutoff_utc, horizon_h=window.lead_h,
                        model_version=f"firecast-lab {__version__} {model.name}",
                        weather_source=model.weather_source, seed=seed, config=config, synthetic=window.synthetic,
                        extra=dict(fire=window.fire, cutoff_utc=window.cutoff_utc, fit=model.describe()))


def write(folder, scenarios: ScenarioSet, *, overwrite: bool = False) -> Path:
    """Write the set (float64 arrays) to ``folder``; read it back with ``hazard_contract.ScenarioSet.read``."""
    return scenarios.write(folder, overwrite=overwrite)
