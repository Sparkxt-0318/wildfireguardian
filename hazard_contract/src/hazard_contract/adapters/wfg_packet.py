"""Read this repo's hazard packets (``wfg.forecast.native-intervals/2``) as scenario sets.

Packet facts this adapter relies on (see ``integration/src/wfg_latest/bridge.py`` and
``packets.py``): arrays are north-up ``[K, H, W]``; times are seconds after ``time_origin``
(= issue time = forecast cutoff); ``ignition_time_s = +inf`` means "no first-new ignition
before the horizon" and is ALSO used for present fire, burned-out and unknown cells; the
packet's ``support`` array is all True by owner policy, and only the ``mask__*`` arrays keep
unknown cells apart.

Program rule 4 ("unknown is not unburned") is applied: cells whose native new-burn probability
is missing or whose burned state is unknown (``mask__policy_assigned_zero`` minus known-burned
cells) become ``supported = False`` with ``nan`` times. There is deliberately no option to
treat them as supported; changing that is an interface decision for Siyeong.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..meta import ContractError, HeatSource, ScenarioMeta
from ..scenario import ScenarioSet
from ._common import parse_time

PRESENT_FIRE_MODES = ("exact", "enclosure")


def from_wfg_packet(packet_dir, *, present_fire: str = "exact") -> ScenarioSet:
    """Convert one packet directory (``constructed_arrays.npz`` + ``NATIVE_METADATA.json``).

    present_fire
        ``exact``: each present-fire cell burns on ``[R_cell - T, R_cell)`` with its exact
        remaining time ``R_cell`` (the heat package's arrival-age rule). ``enclosure``: every
        present-fire cell burns until the packet's scalar ``R_max`` (what the router used).
        Unknown-age present fire burns on ``[-T, T)`` in both modes.
    """
    if present_fire not in PRESENT_FIRE_MODES:
        raise ValueError(f"present_fire must be one of {PRESENT_FIRE_MODES}")
    d = Path(packet_dir)
    md = json.loads((d / "NATIVE_METADATA.json").read_text())
    if md.get("schema") != "wfg.forecast.native-intervals/2":
        raise ContractError(f"unsupported packet schema {md.get('schema')!r}")
    A = md["construction"]["assumptions"]
    with np.load(d / "constructed_arrays.npz", allow_pickle=False) as z:
        arr = {k: z[k] for k in z.files}

    K = int(A["scenario_count"])
    T = float(A["burning_duration_s"])
    horizon = float(A["horizon_s"])
    r_max = float(A["initial_remaining_s"])
    H, W = (int(v) for v in md["shape"])
    ig = np.array(arr["ignition_time_s"], dtype=float)
    ex = np.stack([np.asarray(arr[f"member{k}__extinction_breakpoint_s"], dtype=float) for k in range(K)])
    if ig.shape != (K, H, W) or ex.shape != (K, H, W):
        raise ContractError(f"packet arrays {ig.shape}/{ex.shape} do not match K={K}, shape={(H, W)}")
    cur = np.asarray(arr["current_active"], dtype=bool)
    known_burned = np.asarray(arr["mask__known_burned"], dtype=bool)
    remaining = np.asarray(arr["mask__initial_remaining_s_native"], dtype=float)
    unknown = np.asarray(arr["mask__policy_assigned_zero"], dtype=bool) & ~known_burned
    if np.any(np.isfinite(ig[:, cur | known_burned | unknown])):
        raise ContractError("packet has finite ignitions on present-fire, burned or unknown cells")

    exact_age = cur & np.isfinite(remaining)
    unknown_age = cur & ~np.isfinite(remaining)
    burned_out = known_burned & ~cur
    ig[:, exact_age] = (remaining - T)[exact_age]
    ex[:, exact_age] = remaining[exact_age] if present_fire == "exact" else r_max
    ig[:, unknown_age] = -T
    ex[:, unknown_age] = T
    ig[:, burned_out] = -np.inf
    ex[:, burned_out] = 0.0
    sup = np.ones((K, H, W), dtype=bool)
    sup[:, unknown] = False
    ig[:, unknown] = np.nan
    ex[:, unknown] = np.nan

    heat = HeatSource(
        fuel_load_kg_m2=float(A["fuel_load_kg_m2"]),
        consumed_fraction=float(A["consumed_fraction"]),
        heat_content_kj_kg=float(A["heat_of_combustion_j_kg"]) / 1000.0,
        radiative_fraction=float(A["radiative_fraction"]),
        transmissivity=float(A["atmospheric_transmissivity"]),
        burn_duration_policy="scalar",
        burn_duration_s=T,
        emission_height_m=float(A["emission_height_m"]),
        receiver_height_m=float(A["receiver_height_m"]),
        note="from NATIVE_METADATA.construction.assumptions",
    )
    ident = md.get("identity", {})
    regional = md.get("regional", {})
    window = regional.get("window_rows_cols_north_up")
    meta = ScenarioMeta(
        crs_epsg=int(str(md["crs"]).split(":")[-1]),
        transform=tuple(float(v) for v in md["affine_transform"]),
        height=H, width=W, K=K,
        issue_time_utc=parse_time(md["time_origin"]),
        horizon_s=horizon,
        source="packet",
        synthetic=False,
        model_version=f"c651 {str(ident.get('checkpoint_sha256', 'unknown'))[:12]} via {md.get('bridge_version', '?')}",
        weather_source="c651 export inputs (not recorded in the packet)",
        heat_source=heat,
        provenance={
            "packet_dir": d.name,
            "region_id": regional.get("region_id"),
            "event_id": regional.get("event_id"),
            "construction_id": md.get("construction_id"),
            "graph_revision": md.get("graph_revision"),
            "seed": A.get("seed"),
            "parent_forecast": md["construction"].get("parent_forecast"),
        },
        extra={
            "member_ids": list(md["construction"].get("scenario_ids", [])),
            "support_policy": "rule4: mask__policy_assigned_zero & ~mask__known_burned -> unsupported",
            "present_fire": present_fire,
            "R_max_s": r_max,
            "window_rows_cols_north_up": window,
            "outside_window_sources": "omitted by the packet" if window else "none (whole event grid)",
            "n_unsupported_cells": int(unknown.sum()),
            "n_present_fire_cells": int(cur.sum()),
        },
    )
    return ScenarioSet(ig, ex, sup, meta)
