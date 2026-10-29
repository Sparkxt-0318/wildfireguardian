"""Strict native-array boundary; no probability-to-flame/heat conversion.

Routing code is vendored unchanged beside this module. NumPy is an optional
bridge dependency, never a new dependency of the routing library itself.
"""
from copy import deepcopy
from datetime import datetime
import math
import re

import numpy as np


class IntegrationError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def fail(code, message):
    raise IntegrationError(code, message)


def _utc(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timezone missing")
        return result
    except (ValueError, TypeError, AttributeError):
        fail("TIME_METADATA", "UTC-aware timestamps are required")


def convert(graph, metadata, members):
    """Convert explicitly supplied physical interval fields to edgegrid/1.

    Each member supplies [interval, row, column] arrays flux_w_m2, flame_contact,
    support. Only a vertical row reversal and W->kW conversion are performed.
    NaN flux is allowed only where support is false; serialized zero there is
    a masked placeholder, never a zero-hazard assertion. Unknown flame/support
    cannot be inferred from a first-ignition or occupancy probability.
    """
    from routing.validation import validate_graph, validate_hazard

    validate_graph(graph)
    md = deepcopy(metadata)
    if md.get("schema") not in ("wfg.forecast.native-intervals/1", "wfg.forecast.native-intervals/2"):
        fail("NATIVE_SCHEMA", "Expected wfg.forecast.native-intervals/1 or /2")
    if md.get("schema") == "wfg.forecast.native-intervals/2":
        if md.get("mode") not in ("strict", "research"):
            fail("CONSTRUCTION_MODE", "Version 2 requires strict or research mode")
        for key in ("assumption_id", "parent_forecast_sha256"):
            if not isinstance(md.get(key), str) or not md[key].strip():
                fail("CONSTRUCTION_PROVENANCE", key + " is mandatory")
        if re.fullmatch(r"[0-9a-f]{64}", md["parent_forecast_sha256"]) is None:
            fail("CONSTRUCTION_PROVENANCE", "Parent forecast SHA256 must contain 64 lowercase hex characters")
        if not isinstance(md.get("original_support"), dict) or not isinstance(md.get("constructed_support"), dict):
            fail("CONSTRUCTION_PROVENANCE", "Separate original and constructed support records are mandatory")
        if md["mode"] == "research" and md.get("evidence_class") != "RESEARCH_CONSTRUCTION":
            fail("EVIDENCE_CLASS", "Research construction must retain its explicit evidence class")
        if md["mode"] == "strict" and md.get("evidence_class") == "RESEARCH_CONSTRUCTION":
            fail("EVIDENCE_CLASS", "Strict data cannot claim research construction")
    if md.get("graph_revision") != graph["revision"]:
        fail("GRAPH_REVISION", "Forecast must target the supplied graph revision")
    if md.get("crs") != graph["crs"]:
        fail("CRS_ALIGNMENT", "Forecast and graph must use the same projected CRS")
    if md.get("flux_units") != "W/m2":
        fail("UNITS", "Native incident flux must be explicitly W/m2")
    if md.get("flux_semantics") not in (
        "piecewise_constant_incident_radiant_flux",
        "interval_upper_bound_incident_radiant_flux",
    ):
        fail("TEMPORAL_FLUX_SEMANTICS", "An hourly mean is not an instantaneous field or interval maximum")
    if md.get("flame_semantics") not in (
        "piecewise_constant_flame_contact", "contact_anywhere_during_interval",
    ):
        fail("FLAME_SEMANTICS", "Explicit Boolean flame-contact interpretation required")
    if md.get("present_fire_included") is not True:
        fail("PRESENT_FIRE_MISSING", "The forecast must include existing active fire")
    if not isinstance(md.get("physical_scope"), str) or not md["physical_scope"].strip():
        fail("PHYSICAL_SCOPE", "Declare receiver/transport assumptions and excluded hazards")
    if md.get("evidence_class") not in ("MENTOR_FORECAST", "LABELLED_FIXTURE", "RESEARCH_CONSTRUCTION"):
        fail("EVIDENCE_CLASS", "Declare mentor forecast, labelled fixture, or research construction")
    if md.get("evidence_class") == "RESEARCH_CONSTRUCTION" and md.get("schema") != "wfg.forecast.native-intervals/2":
        fail("CONSTRUCTION_PROVENANCE", "Research construction requires version 2 provenance")
    grid = graph["grid"]
    height, width, res = grid["height"], grid["width"], grid["resolution"]
    transform = md.get("affine_transform")
    if not isinstance(transform, (list, tuple)) or len(transform) != 6:
        fail("GRID_ALIGNMENT", "Supply six affine coefficients a,b,c,d,e,f")
    if any(isinstance(x, bool) or not isinstance(x, (int,float)) or not math.isfinite(x) for x in transform):
        fail("GRID_ALIGNMENT", "Affine coefficients must be finite numbers")
    a,b,c,d,e,f = transform
    flip = e < 0
    expected = (res, 0.0, grid["x0"], 0.0, -res if flip else res,
                grid["y0"] + height*res if flip else grid["y0"])
    if md.get("shape") != [height, width] or any(abs(x-y) > 1e-8 for x,y in zip(transform,expected)):
        fail("GRID_ALIGNMENT", "No resampling: graph and source grid must coincide exactly")
    origin, issue, available = (_utc(md.get(k)) for k in ("time_origin", "issued_at", "available_at"))
    if available < issue:
        fail("CAUSAL_TIME", "Availability cannot predate forecast issue")
    bp = md.get("breakpoints_s")
    if not isinstance(bp, list) or len(bp) < 2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in bp):
        fail("BREAKPOINTS", "Supply finite interval boundaries in seconds")
    if any(y <= x for x,y in zip(bp,bp[1:])):
        fail("BREAKPOINTS", "Boundaries must increase strictly")
    if not members:
        fail("MEMBERS", "At least one physical scenario is required")
    output, ids = [], set()
    shape = (len(bp)-1, height, width)
    for member in members:
        mid = member.get("id")
        if not isinstance(mid,str) or not mid or mid in ids:
            fail("MEMBER_ID", "Member identifiers must be unique stable strings")
        ids.add(mid)
        if "flame_contact" not in member:
            fail("FLAME_FIELD_MISSING", "Probabilities and cumulative burned area are not flame-contact fields")
        arrays = {}
        for key in ("flux_w_m2", "flame_contact", "support"):
            if key not in member:
                fail("FIELD_MISSING", key + " is absent")
            if np.ma.isMaskedArray(member[key]):
                fail("ARRAY_MASK", "Supply a separate explicit support array")
            arr = np.asarray(member[key])
            if arr.shape != shape:
                fail("ARRAY_SHAPE", key + " must have shape " + str(shape))
            if key != "flux_w_m2" and arr.dtype != np.bool_:
                fail("BOOLEAN_MASK", key + " must contain actual booleans")
            if key == "flux_w_m2" and arr.dtype.kind not in "iuf":
                fail("FLUX_VALUES", "Flux must be real numeric values")
            arrays[key] = arr.copy()
        flux, flame, support = (arrays[k] for k in ("flux_w_m2","flame_contact","support"))
        if np.any(np.isinf(flux)) or np.any(flux < 0) or np.any(support & ~np.isfinite(flux)):
            fail("FLUX_VALUES", "Supported flux must be finite nonnegative; infinity/negative values are invalid")
        # Values hidden behind support=false are never consulted by the router.
        flux = np.where(support, flux, 0.0) / 1000.0
        if flip:
            flux, flame, support = (arr[:,::-1,:] for arr in (flux,flame,support))
        output.append({"id":mid,"breakpoints":bp[:],"flux":flux.reshape(len(bp)-1,-1).tolist(),
                       "flame":flame.reshape(len(bp)-1,-1).tolist(),
                       "support":support.reshape(len(bp)-1,-1).tolist()})
    h = {"schema":"wfg.routing.edgegrid/1", "version":md.get("version"),
         "graph_revision":graph["revision"],"crs":graph["crs"],"grid":deepcopy(grid),
         "dt":md.get("dt_s"),"time_origin":md["time_origin"],"issued_at":md["issued_at"],
         "available_at":md["available_at"],"valid_from":bp[0],"valid_until":bp[-1],
         "units":{"time":"s","flux":"kW/m2","dose":"kJ/m2"},
         "channels":["flame_contact","incident_heat_flux"],
         "unsupported_channels":md.get("unsupported_channels",[]),"evidence_class":md["evidence_class"],
         "provenance":{"source":md.get("source"),"interpretation":md["physical_scope"],
                       "native_metadata":md,"row_reversal":flip,
                       "unsupported_flux_placeholder":"zero under support=false only"},"members":output}
    validate_hazard(graph,h)
    return h


def inspect_mentor_export(summary, arrays):
    """Report blockers in the delivered one-hour expectation export, without fills."""
    findings = []
    def add(code, detail):
        findings.append({"code":code,"detail":detail})
    if "flame_contact" not in arrays:
        add("FLAME_FIELD_MISSING", "No interval Boolean flame-contact field is exported")
    if summary.get("initial_active_burning_probability_supplied") is not True:
        add("PRESENT_FIRE_MISSING", "Currently active existing-fire contribution is excluded")
    flux = arrays.get("expected_heat_flux_w_m2")
    if flux is None:
        add("FLUX_FIELD_MISSING", "No full-domain radiant flux field")
    elif np.asarray(flux).ndim == 2:
        add("TEMPORAL_FLUX_SEMANTICS", "This is a one-hour mean, not route-time piecewise flux or an interval maximum")
    if summary.get("complete_expected_flux_available") is not True:
        add("THERMAL_SUPPORT_INCOMPLETE", "Unknown emitting sources leave the full expected thermal field unknown")
    for key in ("issued_at","available_at","stable_member_ids"):
        if key not in summary:
            add("IDENTITY_TIME_METADATA", "Missing " + key)
    return {"ready_for_existing_router":not findings,"blockers":findings,
            "flux_finite_cells":int(np.isfinite(flux).sum()) if flux is not None else 0,
            "flux_total_cells":int(np.asarray(flux).size) if flux is not None else 0}
