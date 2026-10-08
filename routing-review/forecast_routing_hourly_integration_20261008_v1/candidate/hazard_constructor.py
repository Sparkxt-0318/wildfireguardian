"""Explicit research construction from unchanged hourly forecast marginals.

This module preserves native north-up rows. Its interval fields enclose a
declared finite collection of fire realizations; they do not establish real
fire coverage. See ASSUMPTIONS.md for the positivity proof and model scope.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping

import numpy as np

_VENDOR = Path(__file__).resolve().parent / "mentor_runtime"
if _VENDOR.exists():
    sys.path.insert(0, str(_VENDOR))


@dataclass(frozen=True)
class ConstructionConfig:
    version: str = "wfg.hazard.construction/1"
    variant: str = "baseline"
    scenario_count: int = 4
    seed: int = 20261008
    horizon_s: float = 3600.0
    interval_s: float = 300.0
    dependence: str = "independent"
    timing: str = "uniform"
    unknown_probability: float = 0.5
    current_state: str = "known_burned_active"
    unknown_current_state: str = "cold"
    initial_remaining_s: float = 300.0
    fuel_load_kg_m2: float = 10.0
    heat_of_combustion_j_kg: float = 18000000.0
    burning_duration_s: float = 300.0
    consumed_fraction: float = 0.1
    radiative_fraction: float = 0.3
    emission_height_m: float = 5.0
    receiver_height_m: float = 0.0
    atmospheric_transmissivity: float = 1.0

    def __post_init__(self):
        if type(self.scenario_count) is not int or self.scenario_count < 1:
            raise ValueError("scenario_count must be a positive integer")
        if type(self.seed) is not int or not 0 <= self.seed < 2**64:
            raise ValueError("seed must be a uint64 integer")
        for name in ("horizon_s", "interval_s", "heat_of_combustion_j_kg", "burning_duration_s"):
            if isinstance(getattr(self, name), (bool, np.bool_)) or not np.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(name + " must be finite positive")
        for name in ("initial_remaining_s", "fuel_load_kg_m2", "emission_height_m", "receiver_height_m"):
            if isinstance(getattr(self, name), (bool, np.bool_)) or not np.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(name + " must be finite nonnegative")
        for name in ("unknown_probability", "consumed_fraction", "radiative_fraction", "atmospheric_transmissivity"):
            if isinstance(getattr(self, name), (bool, np.bool_)) or not np.isfinite(getattr(self, name)) or not 0 <= getattr(self, name) <= 1:
                raise ValueError(name + " must be in [0,1]")
        if self.emission_height_m <= self.receiver_height_m:
            raise ValueError("emission must be above receiver")
        if self.dependence not in ("independent", "comonotone"):
            raise ValueError("unknown dependence law")
        if self.timing not in ("uniform", "early", "late"):
            raise ValueError("unknown ignition timing law")
        if self.current_state not in ("known_burned_active", "cold"):
            raise ValueError("unknown initial-state assumption")
        if self.unknown_current_state not in ("cold", "active"):
            raise ValueError("unknown-current state must be cold or active")
        if self.initial_remaining_s > self.burning_duration_s:
            raise ValueError("initial remaining duration cannot exceed the same combustion phase duration")
        if self.version != "wfg.hazard.construction/1":
            raise ValueError("unsupported construction version")

    @property
    def assumption_id(self):
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return self.version + ":" + hashlib.sha256(raw).hexdigest()[:20]


def sensitivity_panel():
    """Coordinator-frozen one-at-a-time panel; no route-driven parameter tuning."""
    baseline = ConstructionConfig()
    changes = {
        "baseline": {}, "missing_zero": {"unknown_probability": 0.0},
        "missing_one": {"unknown_probability": 1.0},
        "comonotone": {"dependence": "comonotone"},
        "timing_early": {"timing": "early"}, "timing_late": {"timing": "late"},
        "current_cold": {"current_state": "cold", "initial_remaining_s": 0.0},
        "current_short": {"initial_remaining_s": 150.0},
        "current_unknown_active": {"unknown_current_state": "active"},
        "fuel_half": {"fuel_load_kg_m2": 5.0}, "fuel_double": {"fuel_load_kg_m2": 20.0},
        "duration_short": {"burning_duration_s": 180.0, "initial_remaining_s": 180.0},
        "duration_long": {"burning_duration_s": 600.0},
    }
    return {name: replace(baseline, variant=name, **values) for name, values in changes.items()}


def load_snapshot(npz_path, metadata_path=None):
    """Load numeric arrays only. Object arrays and implicit masks are rejected."""
    path = Path(npz_path)
    with np.load(path, allow_pickle=False) as packet:
        arrays = {key: packet[key].copy() for key in packet.files}
    metadata_path = Path(metadata_path) if metadata_path else path.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text())
    metadata = dict(metadata, native_snapshot_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return arrays, metadata


def validate_snapshot(arrays, metadata):
    required = ("new_burn_probability", "probability_valid", "source_burned_area", "source_burned_area_valid", "affine_transform")
    if any(key not in arrays for key in required):
        raise ValueError("snapshot lacks required native arrays")
    for key in required:
        if np.ma.isMaskedArray(arrays[key]):
            raise ValueError("masked arrays require explicit support")
        if np.asarray(arrays[key]).dtype.kind not in "biuf":
            raise ValueError("numeric or Boolean arrays required")
    q = np.asarray(arrays["new_burn_probability"])
    valid = np.asarray(arrays["probability_valid"])
    burned = np.asarray(arrays["source_burned_area"])
    bvalid = np.asarray(arrays["source_burned_area_valid"])
    if q.ndim != 2 or min(q.shape) < 1 or valid.shape != q.shape or burned.shape != q.shape or bvalid.shape != q.shape:
        raise ValueError("snapshot arrays must share nonempty [row,column] shape")
    if valid.dtype != np.bool_ or bvalid.dtype != np.bool_:
        raise ValueError("native validity masks must be Boolean")
    if np.any(valid & (~np.isfinite(q) | (q < 0) | (q > 1))):
        raise ValueError("supported probabilities must be finite and in [0,1]")
    if np.any(np.isinf(q)):
        raise ValueError("probability infinity is invalid")
    if np.any(bvalid & (~np.isfinite(burned) | ((burned != 0) & (burned != 1)))):
        raise ValueError("known burned values must be binary")
    transform = np.asarray(arrays["affine_transform"], dtype=float)
    if transform.shape != (6,) or not np.all(np.isfinite(transform)):
        raise ValueError("affine must have six finite coefficients")
    if metadata.get("shape", list(q.shape)) != list(q.shape):
        raise ValueError("metadata grid shape differs from arrays")
    if metadata.get("affine_transform") is not None and not np.array_equal(transform, metadata["affine_transform"]):
        raise ValueError("metadata affine differs from arrays")
    if metadata.get("metadata", {}).get("forecast_interval_s", 3600.0) != 3600.0:
        raise ValueError("this original prediction endpoint is one hour")
    return q.astype(float, copy=True), valid, burned, bvalid, transform


def radiation_model(transform, config):
    """Use the byte-preserved original finite-cell solid-angle radiation model."""
    from expected_heat_flux.model import AffineGrid, CombustionParameters, ExpectedHeatFluxModel
    combustion = CombustionParameters(
        fuel_load_kg_m2=config.fuel_load_kg_m2,
        heat_of_combustion_j_kg=config.heat_of_combustion_j_kg,
        burning_duration_s=config.burning_duration_s,
        consumed_fraction=config.consumed_fraction,
    )
    return ExpectedHeatFluxModel(
        grid=AffineGrid(tuple(transform)),
        heat_release_rate_density_w_m2=combustion.heat_release_rate_density_w_m2,
        radiative_fraction=config.radiative_fraction,
        emission_height_m=config.emission_height_m,
        receiver_height_m=config.receiver_height_m,
        atmospheric_transmissivity=config.atmospheric_transmissivity,
    )


def draw_ignitions(q, config):
    """Bernoulli marginals plus a declared independent conditional timing law."""
    q = np.asarray(q, dtype=float)
    if q.ndim != 2 or not np.all(np.isfinite(q)) or np.any((q < 0) | (q > 1)):
        raise ValueError("complete finite [0,1] probability matrix required")
    rng = np.random.default_rng(config.seed)
    shape = (config.scenario_count,) + q.shape
    u = rng.random(shape if config.dependence == "independent" else (config.scenario_count, 1, 1))
    occurrence = u < q
    # Draw timing even for early/late variants to preserve the occurrence draws.
    times = rng.random(shape) * config.horizon_s
    if config.timing == "early":
        times.fill(0.0)
    elif config.timing == "late":
        times.fill(np.nextafter(config.horizon_s, 0.0))
    return np.where(occurrence, times, np.inf)


def interval_enclosures(ignition_time_s, current_active, current_remaining_s, time_edges_s, burning_duration_s, model):
    """Any-contact and positive-source radiant upper enclosure on half-open bins.

    A source burning at any interior time is in the union mask. The original
    model has fixed nonnegative transfer coefficients, hence its union-source
    flux bounds all instantaneous realized flux, including interior maxima.
    Endpoint samples are not used. Native receiver positions are cell centers.
    """
    events = np.asarray(ignition_time_s, dtype=float)
    current = np.asarray(current_active)
    edges = np.asarray(time_edges_s, dtype=float)
    if events.ndim != 3 or current.shape != events.shape[1:] or current.dtype != np.bool_:
        raise ValueError("event/current shapes or Boolean mask invalid")
    if np.any(np.isnan(events)) or np.any(events < 0):
        raise ValueError("events must be nonnegative or positive infinity")
    if edges.ndim != 1 or len(edges) < 2 or not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0):
        raise ValueError("interval edges must increase strictly")
    if not np.isfinite(current_remaining_s) or current_remaining_s < 0 or not np.isfinite(burning_duration_s) or burning_duration_s <= 0:
        raise ValueError("durations invalid")
    shape = (events.shape[0], len(edges) - 1) + events.shape[1:]
    flame = np.zeros(shape, dtype=bool)
    flux = np.zeros(shape, dtype=float)
    for s in range(events.shape[0]):
        for k, (left, right) in enumerate(zip(edges[:-1], edges[1:])):
            mask = (events[s] < right) & ((events[s] + burning_duration_s) > left)
            if left < current_remaining_s and right > 0:
                mask |= current
            flame[s, k] = mask
            flux[s, k] = model.predict(mask.astype(float)).incident_heat_flux_w_m2
            # Numerical margin for the delivered float64 FFT implementation.
            # Positivity proof is exact-arithmetic; independent direct/quadrature
            # checks establish bounded numerical agreement, not formal FP proof.
            if mask.any():
                flux[s, k] = np.nextafter(flux[s, k] + 1e-8 * max(1.0, float(flux[s, k].max())), np.inf)
    return flame, flux


def mean_uniform_occupancy(q, horizon_s, duration_s):
    """Exact hour-mean occupancy for Bernoulli event/uniform conditional time."""
    q = np.asarray(q, dtype=float)
    d = min(float(duration_s), float(horizon_s))
    return q * (d - d*d/(2.0*horizon_s)) / horizon_s


def construct_hazard(arrays: Mapping, metadata: Mapping, *, mode="strict", config=None):
    config = ConstructionConfig() if config is None else config
    if not isinstance(config, ConstructionConfig):
        raise TypeError("config must be ConstructionConfig")
    if mode not in ("strict", "research"):
        raise ValueError("mode must be strict or research")
    q, valid, burned, bvalid, transform = validate_snapshot(arrays, metadata)
    if config.horizon_s != 3600.0:
        raise ValueError("cannot extend or repeat native one-hour horizon")
    edges = np.arange(0, config.horizon_s, config.interval_s)
    edges = np.append(edges, config.horizon_s)
    shape = (config.scenario_count, len(edges)-1) + q.shape
    parent_id = metadata.get("native_snapshot_sha256", metadata.get("cutoff_utc", "anonymous-snapshot"))
    identity = hashlib.sha256((str(parent_id) + ":" + config.assumption_id).encode()).hexdigest()[:20]
    common = {
        "mode": mode, "assumption_id": config.assumption_id if mode == "research" else None,
        "construction_version": config.version, "assumptions": asdict(config) if mode == "research" else None,
        "scenario_ids": ["constructed:" + identity + ":" + str(s) for s in range(config.scenario_count)],
        "scenario_identity_scope": "fresh cutoff-conditioned realization; requires conservative transfer or rejection across forecast updates",
        "parent_forecast": dict(metadata), "shape": list(q.shape), "affine_transform": transform.tolist(),
        "original_probability_valid_cells": int(valid.sum()), "original_probability_cells": int(q.size),
        "known_burned_cells": int(((burned == 1) & bvalid).sum()),
        "unknown_burned_state_cells": int((~bvalid).sum()),
        "flame_semantics": "contact_anywhere_during_interval",
        "flux_semantics": "interval_upper_bound_incident_radiant_flux",
        "flux_units": "W/m2", "time_units": "s", "horizon_s": config.horizon_s,
        "source_domain": "finite native raster only; exterior emission excluded by assumption",
        "receiver_scope": "upward-facing receiver at native cell centers, fixed common height; per-cell routing surrogate",
        "numerical_enclosure": "positive source-union enclosure; float64 FFT plus relative absolute margin; independently checked, not formally rounded geometry",
    }
    if mode == "strict":
        common["scenario_ids"] = ["unsupported-placeholder:" + identity + ":" + str(s) for s in range(config.scenario_count)]
        common.update(evidence_class="MENTOR_FORECAST", present_fire_included=False,
                      unsupported_reasons=["JOINT_FLAME_SCENARIOS_ABSENT", "CURRENT_ACTIVE_STATE_ABSENT", "UNKNOWN_EMITTING_SOURCES", "NATIVE_FLUX_IS_HOURLY_MEAN"],
                      constructed_support_cells=0)
        return {"status": "UNSUPPORTED", "arrays": {
            "flame_contact": np.zeros(shape, dtype=bool), "flux_w_m2": np.full(shape, np.nan),
            "support": np.zeros(shape, dtype=bool), "time_edges_s": edges,
            "scenario_weights": np.full(config.scenario_count, 1.0/config.scenario_count)}, "metadata": common}
    constructed_q = np.where(valid, q, config.unknown_probability)
    # First-new-event probabilities are zero at known previously burned cells.
    # This does not decide whether those cells are currently actively burning.
    constructed_q[(burned == 1) & bvalid] = 0.0
    current = (burned == 1) & bvalid if config.current_state == "known_burned_active" else np.zeros(q.shape, bool)
    if config.unknown_current_state == "active":
        # Adversarial alternative: hypothetical pre-cutoff event/current activity
        # on every unknown-state cell. Preserve raw q, make constructed first-new
        # events disjoint with those assumed-current sources.
        current = current | ~bvalid
        constructed_q[~bvalid] = 0.0
    events = draw_ignitions(constructed_q, config)
    model = radiation_model(transform, config)
    flame, flux = interval_enclosures(events, current, config.initial_remaining_s, edges, config.burning_duration_s, model)
    support = np.ones(shape, dtype=bool)
    mean_occ = mean_uniform_occupancy(constructed_q, config.horizon_s, config.burning_duration_s)
    mean_occ += current * min(config.initial_remaining_s, config.horizon_s)/config.horizon_s
    common.update(evidence_class="RESEARCH_CONSTRUCTION", present_fire_included=True,
                  constructed_support_cells=int(support.sum()), unknown_source_assignment_cells=int((~valid).sum()),
                  current_unknown_state_assumption=("unknown current states cold; unknown future sources receive declared q assignment"
                      if config.unknown_current_state == "cold" else
                      "unknown current states active for declared remaining duration; their constructed first-new q=0 for disjointness"),
                  target_mapping="retrospective reconstructed first arrival endpoint mapped to hypothetical flame ignition event; unvalidated",
                  occurrence_law="cell Bernoulli with clipped original evaluation-score marginals where known; assigned q elsewhere",
                  dependence_law=config.dependence,
                  dependence_scope="occurrence comonotone only; conditional uniform ignition times independent per cell" if config.dependence == "comonotone" else "independent cell occurrences and conditional ignition times",
                  timing_law=config.timing,
                  finite_ensemble_guarantee="none; routes checked against these finite declared realizations only",
                  parameter_evidence="illustrative study anchors and sensitivity values; no same-fire calibration")
    return {"status": "CONSTRUCTED", "arrays": {
        "flame_contact": flame, "flux_w_m2": flux, "support": support, "time_edges_s": edges,
        "scenario_weights": np.full(config.scenario_count, 1.0/config.scenario_count),
        "ignition_time_s": events, "current_active": current, "constructed_probability": constructed_q,
        "uniform_mean_active_occupancy": mean_occ,
        "uniform_mean_flux_w_m2": model.predict(mean_occ).incident_heat_flux_w_m2,
    }, "metadata": common}


def save_construction(result, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if any(np.asarray(arr).dtype.kind not in "biuf" or np.ma.isMaskedArray(arr) for arr in result["arrays"].values()):
        raise ValueError("construction exports require unmasked numeric arrays; no pickle data")
    np.savez_compressed(output_path, **result["arrays"])
    md = dict(result["metadata"], status=result["status"], payload_sha256=hashlib.sha256(output_path.read_bytes()).hexdigest())
    output_path.with_suffix(".json").write_text(json.dumps(md, indent=2, allow_nan=False))
    return md
