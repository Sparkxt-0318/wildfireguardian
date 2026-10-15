"""Latest-forecast export contract (wfg.latest-forecast-contract/1): clock binding, declared policy and strict raw-field
validation shared by the exporter, the hazard bridge and the packet builder. Standard library + NumPy only.

Repairs of the reviewed defects of the unadmitted 14 October adapter:
  * B06/LA01 clock authority: the requested cutoff must be a whole UTC hour and must equal the loaded sample time and the
    Prediction time (dt exactly 1 h); the cutoff, sample time, prediction time, event and policy are embedded INSIDE the
    hashed export NPZ and must equal the export record and the caller's request, so a renamed stale export is rejected.
  * B07/LA05 raw fields: every mask must already be a NumPy boolean array (never coerced), every field must have the same
    [H,W] shape, values marked valid must be finite and in range, present activity must be exactly 0 or 1 on valid cells,
    active cells need a finite remaining time in (0, T], valid inactive cells need remaining exactly 0, and present fire
    outside known-burned support is a contradiction. Violations raise ContractError; nothing is silently made cold.
The owner's zero assignment applies ONLY to missing new-burn probabilities (recorded separately by the bridge); it is
never used for activity, remaining time, timestamps, geometry or thermal quantities.
Version 1.1 (narrow repair of review findings MC01/MC02 on contract 6093f4d3): the export record's nested clock object must
equal the clock derived from the verified embedded epochs (any contradiction is rejected, and only the verified object is
returned for publication); the EPSG code is embedded in the hashed NPZ and must equal the record EPSG and the caller's
requested EPSG (an integer, never bool) before any construction."""
from __future__ import annotations

import datetime as _dt
import json
import math

import numpy as np

CONTRACT_VERSION = "wfg.latest-forecast-contract/1.1"
CHECKPOINT_SHA256 = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"

# Declared, complete policy of the latest export (compared field by field by the bridge and the packet builder).
POLICY = {
    "schema": "wfg.latest-forecast-export/2",
    "boundary": "unknown",
    "missing_burned_area": "unknown",
    "use_cell_burning_duration": True,
    "point_residence_s": 11.52,
    "spread_rate_m_s": 341.0 / 3600.0,
    "spread_direction_deg": 0.0,
    "fuel_load_kg_m2": 10.0,
    "consumed_fraction": 0.1,
    "heat_of_combustion_j_kg": 18608000.0,
    "radiative_fraction": 0.30,
    "emission_height_m": 5.0,
    "receiver_height_m": 0.0,
    "atmospheric_transmissivity": 1.0,
    "ignition_time_model": "uniform",
    "interval_s": 3600.0,
}

MASKS = ("probability_valid", "rate_valid", "source_burned_area_valid", "heat__initial_burning_valid")
FIELDS = ("new_burn_probability", "rate_per_h", "source_burned_area", "heat__initial_active_burning_probability",
          "heat__initial_remaining_burning_duration_s")
CLOCK_KEYS = ("contract__cutoff_epoch_s", "contract__sample_time_epoch_s", "contract__prediction_time_epoch_s",
              "contract__prediction_dt_hours", "contract__event_id", "contract__cell_duration_s", "contract__policy_json",
              "contract__version", "contract__epsg")


class ContractError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


# ----------------------------------------------------------------------------------------------------------- clock
def normalize_cutoff(text):
    """Return (canonical 'YYYY-MM-DDTHH:00:00Z', Unix seconds) for a timezone-aware whole-hour instant."""
    if not isinstance(text, str):
        raise ContractError("CLOCK_CUTOFF_TYPE", repr(text))
    try:
        t = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("CLOCK_CUTOFF_UNPARSEABLE", text) from exc
    if t.tzinfo is None:
        raise ContractError("CLOCK_CUTOFF_NAIVE", text)
    t = t.astimezone(_dt.timezone.utc)
    if t.minute or t.second or t.microsecond:
        raise ContractError("CLOCK_CUTOFF_NOT_WHOLE_HOUR", text)
    return t.strftime("%Y-%m-%dT%H:00:00Z"), int(t.timestamp())


def tag(text):
    iso, _ = normalize_cutoff(text)
    return iso.replace("-", "").replace(":", "")[:15] + "Z"


def _single_int(x, name):
    a = np.asarray(x)
    if a.size != 1 or a.dtype.kind not in "iu":
        raise ContractError("CLOCK_" + name.upper() + "_NOT_ONE_INTEGER", "%s %s" % (a.dtype, a.shape))
    return int(a.reshape(()).item())


def bind_clock(requested, sample_time_utc, sample_time_valid, prediction_time_utc, prediction_dt_hours):
    """Requested cutoff == loaded sample time == Prediction time; dt exactly 1 h. Returns the clock record."""
    iso, epoch = normalize_cutoff(requested)
    if sample_time_valid is not None:
        v = np.asarray(sample_time_valid)
        if v.dtype != np.bool_ or v.size != 1 or not bool(v.reshape(()).item()):
            raise ContractError("CLOCK_SAMPLE_TIME_NOT_VALID")
    s = _single_int(sample_time_utc, "sample_time")
    if prediction_time_utc is None:
        raise ContractError("CLOCK_PREDICTION_TIME_MISSING")
    p = _single_int(prediction_time_utc, "prediction_time")
    dt = np.asarray(prediction_dt_hours, dtype=float)
    if dt.size != 1 or not np.isfinite(dt).all() or float(dt.reshape(())) != 1.0:
        raise ContractError("CLOCK_PREDICTION_HORIZON_NOT_ONE_HOUR", repr(prediction_dt_hours))
    if s != epoch:
        raise ContractError("CLOCK_SAMPLE_TIME_MISMATCH", "requested %s (%d) sample %d" % (iso, epoch, s))
    if p != epoch:
        raise ContractError("CLOCK_PREDICTION_TIME_MISMATCH", "requested %s (%d) prediction %d" % (iso, epoch, p))
    return {"cutoff_utc": iso, "cutoff_epoch_s": epoch, "sample_time_epoch_s": s, "prediction_time_epoch_s": p,
            "prediction_dt_hours": 1.0, "offset_s": 0}


def _epsg(x, code):
    if isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer)) or int(x) <= 0:
        raise ContractError(code, repr(x))
    return int(x)


def derived_clock(epoch):
    """The only clock object a bound export may carry (requested == sample == Prediction, dt 1 h, offset 0)."""
    iso = _dt.datetime.fromtimestamp(int(epoch), _dt.timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
    return {"cutoff_utc": iso, "cutoff_epoch_s": int(epoch), "sample_time_epoch_s": int(epoch), "prediction_time_epoch_s": int(epoch),
            "prediction_dt_hours": 1.0, "offset_s": 0}


def embed_clock(arrays, clock, event_id, cell_duration_s, epsg, policy=POLICY):
    if clock != derived_clock(clock.get("cutoff_epoch_s", -1)):
        raise ContractError("CLOCK_RECORD_NOT_DERIVED", repr(clock))
    out = dict(arrays)
    out["contract__epsg"] = np.array(_epsg(epsg, "EPSG_INVALID"), dtype=np.int64)
    out["contract__cutoff_epoch_s"] = np.array(clock["cutoff_epoch_s"], dtype=np.int64)
    out["contract__sample_time_epoch_s"] = np.array(clock["sample_time_epoch_s"], dtype=np.int64)
    out["contract__prediction_time_epoch_s"] = np.array(clock["prediction_time_epoch_s"], dtype=np.int64)
    out["contract__prediction_dt_hours"] = np.array(clock["prediction_dt_hours"], dtype=np.float64)
    out["contract__event_id"] = np.array(str(event_id))
    out["contract__cell_duration_s"] = np.array(float(cell_duration_s), dtype=np.float64)
    out["contract__policy_json"] = np.array(json.dumps(policy, sort_keys=True))
    out["contract__version"] = np.array(CONTRACT_VERSION)
    return out


def verify_binding(arrays, record, requested_cutoff, event_id, requested_epsg, policy=POLICY):
    """Bind an export NPZ + record to the caller's request before any construction (rejects renamed stale pairs,
    contradictory nested record clocks and export/record/request CRS disagreement)."""
    iso, epoch = normalize_cutoff(requested_cutoff)
    req_epsg = _epsg(requested_epsg, "EPSG_REQUEST_INVALID")
    miss = [k for k in CLOCK_KEYS if k not in arrays]
    if miss:
        raise ContractError("EXPORT_NOT_CLOCK_BOUND", ",".join(miss))
    if str(arrays["contract__version"].reshape(()).item()) != CONTRACT_VERSION:
        raise ContractError("EXPORT_CONTRACT_VERSION")
    for k in ("contract__cutoff_epoch_s", "contract__sample_time_epoch_s", "contract__prediction_time_epoch_s"):
        if _single_int(arrays[k], k) != epoch:
            raise ContractError("CLOCK_EXPORT_MISMATCH", "%s=%s requested %s" % (k, arrays[k], iso))
    if float(np.asarray(arrays["contract__prediction_dt_hours"]).reshape(())) != 1.0:
        raise ContractError("CLOCK_PREDICTION_HORIZON_NOT_ONE_HOUR")
    if str(arrays["contract__event_id"].reshape(()).item()) != str(event_id):
        raise ContractError("EXPORT_EVENT_MISMATCH", "%s vs %s" % (arrays["contract__event_id"], event_id))
    rec_iso, rec_epoch = normalize_cutoff(record.get("cutoff_utc", ""))
    if rec_epoch != epoch or record.get("event") != event_id:
        raise ContractError("CLOCK_RECORD_MISMATCH", "record %s/%s requested %s/%s" % (rec_iso, record.get("event"), iso, event_id))
    verified_clock = derived_clock(epoch)
    rc = record.get("clock")
    if not isinstance(rc, dict) or set(rc) != set(verified_clock) or any(
            type(rc[k]) is bool or not isinstance(rc[k], type(verified_clock[k])) or rc[k] != verified_clock[k] for k in verified_clock):
        raise ContractError("CLOCK_RECORD_OBJECT_MISMATCH", "record.clock %r verified %r" % (rc, verified_clock))
    emb_epsg = _single_int(arrays["contract__epsg"], "epsg")
    rec_epsg = _epsg(record.get("epsg"), "EPSG_RECORD_INVALID")
    if not (emb_epsg == rec_epsg == req_epsg):
        raise ContractError("EPSG_BINDING", "embedded %d record %d requested %d" % (emb_epsg, rec_epsg, req_epsg))
    if record.get("checkpoint_sha256") != CHECKPOINT_SHA256:
        raise ContractError("CHECKPOINT_IDENTITY")
    embedded = json.loads(str(arrays["contract__policy_json"].reshape(()).item()))
    if embedded != policy or record.get("policy") != policy:
        raise ContractError("POLICY_MISMATCH", "embedded/record policy differs from the declared policy")
    T = float(np.asarray(arrays["contract__cell_duration_s"]).reshape(()))
    if not (math.isfinite(T) and T > 0) or float(record.get("cell_burning_duration_s", {}).get("value", float("nan"))) != T:
        raise ContractError("DURATION_BINDING", "embedded %r record %r" % (T, record.get("cell_burning_duration_s")))
    return {"cutoff_utc": iso, "cutoff_epoch_s": epoch, "event_id": event_id, "cell_duration_s": T, "clock": verified_clock,
            "epsg": req_epsg}


# ------------------------------------------------------------------------------------------------------ raw fields
def validate_raw(arrays, cell_duration_s, *, rel_tol=1e-12):
    """Strict raw-field validation. Returns counts; raises ContractError on the first class of violation found."""
    errs = []
    for k in MASKS + FIELDS + ("affine_transform",):
        if k not in arrays:
            raise ContractError("RAW_FIELD_MISSING", k)
    for k in MASKS:
        if not isinstance(arrays[k], np.ndarray) or arrays[k].dtype != np.bool_:
            raise ContractError("RAW_MASK_NOT_BOOLEAN", "%s dtype %s" % (k, getattr(arrays[k], "dtype", type(arrays[k]))))
    for k in FIELDS:
        if not isinstance(arrays[k], np.ndarray) or arrays[k].dtype.kind != "f":
            raise ContractError("RAW_FIELD_NOT_FLOAT", "%s dtype %s" % (k, getattr(arrays[k], "dtype", None)))
    shape = arrays["new_burn_probability"].shape
    if len(shape) != 2 or min(shape) < 1:
        raise ContractError("RAW_SHAPE", "probability shape %s" % (shape,))
    for k in MASKS + FIELDS:
        if arrays[k].shape != shape:
            raise ContractError("RAW_SHAPE_MISMATCH", "%s %s vs %s" % (k, arrays[k].shape, shape))
    aff = np.asarray(arrays["affine_transform"])
    if aff.dtype.kind != "f" or aff.shape != (6,) or not np.isfinite(aff).all() or aff[1] != 0 or aff[3] != 0 or not aff[0] > 0 or not aff[4] < 0:
        raise ContractError("RAW_AFFINE", repr(aff))
    T = float(cell_duration_s)
    if not (math.isfinite(T) and T > 0):
        raise ContractError("RAW_DURATION", repr(cell_duration_s))
    pv, q = arrays["probability_valid"], arrays["new_burn_probability"]
    if np.any(pv & ~(np.isfinite(q) & (q >= 0) & (q <= 1))):
        errs.append("RAW_VALID_PROBABILITY_OUT_OF_RANGE")
    rv, r = arrays["rate_valid"], arrays["rate_per_h"]
    if np.any(rv & ~(np.isfinite(r) & (r >= 0))):
        errs.append("RAW_VALID_RATE_INVALID")
    bv, b = arrays["source_burned_area_valid"], arrays["source_burned_area"]
    if np.any(bv & ~((b == 0) | (b == 1))):
        errs.append("RAW_VALID_BURNED_STATE_NOT_BINARY")
    iv = arrays["heat__initial_burning_valid"]
    ip = arrays["heat__initial_active_burning_probability"]; ir = arrays["heat__initial_remaining_burning_duration_s"]
    if np.any(iv & ~((ip == 0) | (ip == 1))):            # NaN fails both comparisons: valid-marked NaN is rejected
        errs.append("RAW_VALID_ACTIVITY_NOT_BINARY_OR_NAN")
    known_burned = bv & (b == 1)
    active = iv & (ip == 1)
    if np.any(active & ~known_burned):
        errs.append("RAW_ACTIVE_OUTSIDE_KNOWN_BURNED")
    if np.any(active & ~(np.isfinite(ir) & (ir > 0) & (ir <= T * (1 + rel_tol)))):
        errs.append("RAW_ACTIVE_REMAINING_INVALID")
    inactive = iv & (ip == 0)
    if np.any(inactive & ~(ir == 0)):
        errs.append("RAW_INACTIVE_REMAINING_NOT_ZERO")
    if np.any(np.isfinite(ir) & (ir < 0)):
        errs.append("RAW_NEGATIVE_REMAINING")
    if errs:
        raise ContractError(errs[0], "all violations: " + ",".join(errs))
    R = ir[active]
    return {"shape": list(shape), "cells": int(q.size), "probability_native_valid": int(pv.sum()),
            "probability_policy_zero": int((~pv).sum()), "burned_state_known": int(bv.sum()),
            "burned_state_unknown": int((~bv).sum()), "known_burned": int(known_burned.sum()),
            "present_fire_exact": int(active.sum()), "known_burned_unknown_age": int((known_burned & ~iv).sum()),
            "initial_state_invalid": int((~iv).sum()),
            "remaining_s": None if R.size == 0 else {"min": float(R.min()), "max": float(R.max()), "median": float(np.median(R))},
            "cell_duration_s": T}
