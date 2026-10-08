"""Exact-event temporal reference for unchanged saved constructed source histories.

This diagnostic does not draw scenarios or change physics. It uses the original
finite-cell radiation operator at specified receivers, analytical source-time
overlap for dose, and grouped source jumps for peak. Geometry remains floating
point and physically unvalidated. It is not a replacement routing certificate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

_HERE = Path(__file__).resolve().parent
if (_HERE / "mentor_runtime").exists():
    sys.path.insert(0, str(_HERE / "mentor_runtime"))


class EventReference:
    schema = "wfg.diagnostic.exact-events/1"

    def __init__(self, ignition_time_s, current_active, config, affine_transform, scenario_ids=None):
        from expected_heat_flux.model import AffineGrid, CombustionParameters, ExpectedHeatFluxModel
        self.events = np.asarray(ignition_time_s, dtype=float).copy()
        self.current = np.asarray(current_active).copy()
        self.config = dict(config)
        if self.events.ndim != 3 or min(self.events.shape) < 1 or self.current.shape != self.events.shape[1:] or self.current.dtype != np.bool_:
            raise ValueError("events must be [scenario,row,column] and current state a Boolean grid")
        if np.any(np.isnan(self.events)) or np.any(self.events < 0):
            raise ValueError("event times must be nonnegative or positive infinity")
        if np.any(np.isfinite(self.events[:, self.current])):
            raise ValueError("saved current and first-new-event sources must be disjoint")
        self.horizon = float(self.config.get("horizon_s", 3600.0))
        self.duration = float(self.config["burning_duration_s"])
        self.remaining = float(self.config["initial_remaining_s"])
        if not np.isfinite(self.horizon) or self.horizon <= 0 or not np.isfinite(self.duration) or self.duration <= 0 or not 0 <= self.remaining <= self.duration:
            raise ValueError("horizon/duration/same-phase remaining invalid")
        if np.any(np.isfinite(self.events) & (self.events >= self.horizon)):
            raise ValueError("finite saved ignition must be inside the native horizon")
        self.shape = self.current.shape
        self.scenario_count = self.events.shape[0]
        self.ids = list(scenario_ids) if scenario_ids is not None else ["event-reference:" + str(i) for i in range(self.scenario_count)]
        if len(self.ids) != self.scenario_count or len(set(self.ids)) != len(self.ids):
            raise ValueError("unique scenario IDs required")
        self.grid = AffineGrid(tuple(float(x) for x in affine_transform))
        self.combustion = CombustionParameters(
            fuel_load_kg_m2=self.config["fuel_load_kg_m2"],
            heat_of_combustion_j_kg=self.config["heat_of_combustion_j_kg"],
            burning_duration_s=self.duration, consumed_fraction=self.config["consumed_fraction"])
        self.model = ExpectedHeatFluxModel(
            grid=self.grid, heat_release_rate_density_w_m2=self.combustion.heat_release_rate_density_w_m2,
            radiative_fraction=self.config["radiative_fraction"], emission_height_m=self.config["emission_height_m"],
            receiver_height_m=self.config["receiver_height_m"], atmospheric_transmissivity=self.config["atmospheric_transmissivity"])
        self.centers = self.grid.centers(self.shape)
        self.event_flat = self.events.reshape(self.scenario_count, -1)
        self.current_flat = self.current.ravel()
        self._weight_cache = {}
        self.provenance = {}

    @classmethod
    def from_case(cls, case_dir):
        case_dir = Path(case_dir)
        report = json.loads((case_dir / "REPORT.json").read_text())
        construction = report["native_metadata"]["construction"]
        config = construction["assumptions"]
        if config is None or report["mode"] != "research":
            raise ValueError("exact events require saved research source histories")
        path = case_dir / "constructed_arrays.npz"
        with np.load(path, allow_pickle=False) as arrays:
            events = arrays["ignition_time_s"]
            current = arrays["current_active"]
        ids = list(report["rows"][0]["request"]["incurred"])
        result = cls(events, current, config, report["native_metadata"]["affine_transform"], ids)
        result.provenance = {"case_directory":str(case_dir), "source_history_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                             "assumption_id": report["assumption_id"], "source_histories_changed":False,
                             "reference_schema":cls.schema, "numerical_geometry":"original float64 finite-cell transfer; analytical temporal overlap and grouped events"}
        return result

    def _time_interval(self, start, end):
        start, end = float(start), float(end)
        if not np.isfinite(start) or not np.isfinite(end) or start < 0 or end < start or end > self.horizon:
            raise ValueError("reference coverage cannot extend beyond native horizon")
        return start, end

    def _cell(self, row, col):
        if type(row) is not int or type(col) is not int or not 0 <= row < self.shape[0] or not 0 <= col < self.shape[1]:
            raise ValueError("native cell indices out of bounds")
        return row * self.shape[1] + col

    def weights_at_point(self, x, y):
        key = (float(x), float(y))
        if not np.all(np.isfinite(key)):
            raise ValueError("receiver coordinates must be finite")
        if key not in self._weight_cache:
            displacement = self.centers.reshape(-1,2) - key
            transfer = self.model._cell_transfer(displacement[:,0], displacement[:,1])
            density = np.broadcast_to(self.model.heat_release_rate_density_w_m2 * self.model.radiative_fraction, self.shape).ravel()
            self._weight_cache[key] = transfer * density * self.model.atmospheric_transmissivity
        return self._weight_cache[key]

    def weights_at_cell(self, row, col):
        self._cell(row,col)
        return self.weights_at_point(*self.centers[row,col])

    def active_sources(self, t):
        t, _ = self._time_interval(t,t)
        active = (self.event_flat <= t) & (self.event_flat+self.duration > t)
        if t < self.remaining:
            active |= self.current_flat[None,:]
        return active

    def cell_query(self, row, col, t):
        cell = self._cell(row,col)
        active = self.active_sources(t)
        flux = active @ self.weights_at_cell(row,col)
        return [{"id":self.ids[s], "flame_contact":bool(active[s,cell]), "flux_w_m2":float(flux[s]),
                 "peak_kw_m2":float(flux[s]/1000.0)} for s in range(self.scenario_count)]

    def point_query(self, x, y, t):
        active = self.active_sources(t)
        flux = active @ self.weights_at_point(x,y)
        return [{"id":self.ids[s], "flux_w_m2":float(flux[s]), "peak_kw_m2":float(flux[s]/1000.0)} for s in range(self.scenario_count)]

    def _integrate_weights(self, weights, start, end, contact_cell=None):
        start,end = self._time_interval(start,end)
        current_duration = max(0.0, min(end,self.remaining)-start)
        current_flux = float(weights[self.current_flat].sum())
        rows = []
        for s in range(self.scenario_count):
            events = self.event_flat[s]
            overlaps = np.maximum(0.0, np.minimum(end,events+self.duration)-np.maximum(start,events))
            dose_j = float(overlaps @ weights) + current_duration*current_flux
            active_start = (events <= start) & (events+self.duration > start)
            if start < self.remaining:
                active_start |= self.current_flat
            initial = float(weights[active_start].sum())
            # Group coincident ignition/extinction jumps before checking peaks.
            # Closed occupancy endpoints are checked at the right-continuous state,
            # matching the maintained router's endpoint admission convention.
            starts = np.isfinite(events) & (events > start) & (events <= end)
            ends = np.isfinite(events) & (events+self.duration > start) & (events+self.duration <= end)
            times = np.concatenate((events[starts], (events+self.duration)[ends]))
            deltas = np.concatenate((weights[starts], -weights[ends]))
            if start < self.remaining <= end and self.current_flat.any():
                times = np.append(times,self.remaining)
                deltas = np.append(deltas,-current_flux)
            if len(times):
                order = np.argsort(times,kind="stable")
                times,deltas = times[order],deltas[order]
                _,first = np.unique(times,return_index=True)
                jumps = np.add.reduceat(deltas,first)
                peak = max(initial,float(np.max(initial+np.cumsum(jumps))),0.0)
                boundaries = np.unique(times).tolist()
            else:
                peak,boundaries = initial,[]
            contact = False
            contact_duration = 0.0
            if contact_cell is not None:
                event = events[contact_cell]
                contact_duration = float(overlaps[contact_cell])
                contact = bool(np.isfinite(event) and event <= end and event+self.duration > start)
                if self.current_flat[contact_cell]:
                    contact_duration += current_duration
                    contact |= bool(start < self.remaining and end >= 0)
            rows.append({"id":self.ids[s], "dose_kj_m2":dose_j/1000.0, "dose_j_m2":dose_j,
                         "peak_kw_m2":peak/1000.0, "peak_w_m2":peak,
                         "flame_contact_any":contact,"contact_duration_s":contact_duration,
                         "event_boundaries_evaluated":len(boundaries), "endpoint_semantics":"closed occupancy/right-continuous hazard; source activity half-open"})
        return rows

    def integrate_cell(self, row, col, start, end):
        cell = self._cell(row,col)
        return self._integrate_weights(self.weights_at_cell(row,col),start,end,cell)

    def integrate_point(self, x, y, start, end):
        return self._integrate_weights(self.weights_at_point(x,y),start,end)

    def native_cell_from_router(self, cell, grid):
        if grid["height"] != self.shape[0] or grid["width"] != self.shape[1]:
            raise ValueError("router/native shape differs")
        if type(cell) is not int or not 0 <= cell < self.current.size:
            raise ValueError("router cell out of bounds")
        bottom_row,col = divmod(cell,self.shape[1])
        return self.shape[0]-1-bottom_row,col

    def integrate_occupancy(self, occupancies, grid):
        per = {mid:{"dose":0.0,"peak":0.0,"flame_contact":False,"contact_duration_s":0.0} for mid in self.ids}
        codes = set()
        for occ in occupancies:
            row,col = self.native_cell_from_router(occ["cell"],grid)
            try:
                values = self.integrate_cell(row,col,occ["start"],occ["end"])
            except ValueError:
                codes.add("UNSUPPORTED")
                continue
            for value in values:
                out = per[value["id"]]
                out["dose"] += value["dose_kj_m2"]
                out["peak"] = max(out["peak"],value["peak_kw_m2"])
                out["flame_contact"] |= value["flame_contact_any"]
                out["contact_duration_s"] += value["contact_duration_s"]
                if value["flame_contact_any"]:
                    codes.add("FLAME_CONTACT")
        return {"ok":not codes,"codes":sorted(codes),"per_member":per,"reference_schema":self.schema,
                "scope":"same saved realizations, exact event-time treatment at cell centers; no global search or physical validation"}
