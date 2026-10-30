"""Opt-in, cell-local contact certificates on immutable source snapshots.

Unknown cells are support barriers, never assigned flame or no-flame values.
This object is deliberately not a thermal hazard packet or a default model.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
from types import MappingProxyType

import numpy as np

from . import adapter, geometry, frontend, sipp

SCOPE = "wfg.known-footprint.contact-only/1"
CHECKED = "CHECKED_CONTACT_ROUTE_WITHIN_KNOWN_FOOTPRINT"
UNRESOLVED = "UNRESOLVED_RESTRICTED_SUPPORT"
RAW_KEYS = (
    "trajectory_first_burn_hour", "source_burned_area", "source_burned_area_valid",
    "heat__initial_active_burning_probability", "heat__initial_burning_valid",
    "heat__initial_remaining_burning_duration_s", "affine_transform",
)


def _utc(value):
    # datetime silently truncates fractional precision beyond microseconds,
    # including fractional offset seconds. Refuse those clocks before parsing.
    if not isinstance(value, str) or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value) is None:
        raise ValueError("Source clock requires RFC3339 seconds with at most six fractional digits and Z or HH:MM offset")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("Explicit UTC-offset source clock required")
    return t.astimezone(timezone.utc)


def _snapshot(array):
    a = np.asarray(array)
    if a.dtype.hasobject:
        raise ValueError("Object arrays cannot be source data")
    # An immutable bytes owner prevents callers from switching WRITEABLE on.
    return np.frombuffer(a.tobytes(order="C"), dtype=a.dtype).reshape(a.shape)


def _digest(a):
    return hashlib.sha256(a.tobytes(order="C")).hexdigest()


class KnownFootprintSource:
    """Original selected full-grid arrays, with an exact optional integer view.

    `trajectory_indices` are the original saved identities of the supplied
    rows. Select them from the original export before calling this constructor.
    Uniform draws use the full native grid before cropping, so changing K or
    taking an existing regional window cannot reassign represented timing.
    The constructor validates source values; filesystem pinning remains the
    caller's input-admission responsibility, recorded in `source_identity`.
    """
    certificate_scope = SCOPE
    supported = False

    def __setattr__(self, key, value):
        if getattr(self, "_sealed", False):
            raise AttributeError("Known-footprint source binding is immutable")
        object.__setattr__(self, key, value)

    def __init__(self, forecast, *, trajectory_indices, cutoff_utc, epsg,
                 source_horizon_s, burning_duration_s, seed, timing="uniform",
                 window=None, initial_remaining_s=None, terminal_inclusive=True,
                 member_valid_until_s=None, source_identity=None):
        raw = {k: _snapshot(forecast[k]) for k in RAW_KEYS}
        first = raw["trajectory_first_burn_hour"]
        ids = tuple(trajectory_indices)
        if (first.dtype != np.int16 or first.ndim != 3 or not len(first)
                or len(ids) != len(first) or len(set(ids)) != len(ids)
                or any(isinstance(i, (bool, np.bool_)) or not isinstance(i, (int, np.integer)) or i < 0 for i in ids)):
            raise ValueError("Distinct original integer trajectory identities and int16 [K,H,W] required")
        H, W = first.shape[1:]
        if not H or not W or timing != "uniform":
            raise ValueError("Positive full source grid and reviewed uniform timing required")
        if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
            raise ValueError("Original nonnegative integer construction seed required")
        horizon, T = F(source_horizon_s), F(burning_duration_s)
        if horizon <= 0 or T <= 0 or horizon.denominator != 1:
            raise ValueError("Finite positive whole-second source horizon and positive duration required")
        if (first < -2).any() or (first > math.ceil(horizon / 3600)).any():
            raise ValueError("First-burn values outside saved source horizon")
        valid = raw["source_burned_area_valid"]
        iv = raw["heat__initial_burning_valid"]
        burned = raw["source_burned_area"]
        active = raw["heat__initial_active_burning_probability"]
        remaining = raw["heat__initial_remaining_burning_duration_s"]
        for name in RAW_KEYS[1:-1]:
            if raw[name].shape != (H, W):
                raise ValueError("Raw cutoff fields differ from full source grid")
        for name in ("source_burned_area", "heat__initial_active_burning_probability",
                     "heat__initial_remaining_burning_duration_s"):
            if raw[name].dtype.kind != "f":
                raise ValueError("RAW_FIELD_NOT_FLOAT:" + name)
        if valid.dtype != np.bool_ or iv.dtype != np.bool_:
            raise ValueError("Genuine Boolean source validity masks required")
        if not np.isin(burned[valid], [0, 1]).all() or not np.isin(active[iv], [0, 1]).all():
            raise ValueError("Known cutoff activity must be binary")
        if (not np.isfinite(remaining[iv]).all() or (remaining[iv] < 0).any()
                or (remaining[iv] > float(T)).any()):
            raise ValueError("Invalid represented initial remaining duration")
        # Preserve the canonical raw cutoff-state invariants before activity is
        # intersected with known burned cells. Contradictory fire cannot vanish.
        known_burned = valid & (burned == 1)
        active_known = iv & (active == 1)
        inactive_known = iv & (active == 0)
        if np.any(active_known & ~known_burned):
            raise ValueError("RAW_ACTIVE_OUTSIDE_KNOWN_BURNED")
        if np.any(active_known & (remaining <= 0)):
            raise ValueError("RAW_ACTIVE_REMAINING_INVALID")
        if np.any(inactive_known & (remaining != 0)):
            raise ValueError("RAW_INACTIVE_REMAINING_NOT_ZERO")
        if np.any(np.isfinite(remaining) & (remaining < 0)):
            raise ValueError("RAW_NEGATIVE_REMAINING")
        if (np.any(first[:, valid & (burned == 1)] != 0)
                or np.any(first[:, valid & (burned == 0)] == 0)):
            raise ValueError("Trajectory cutoff state contradicts original raw cutoff state")
        if raw["affine_transform"].shape != (6,) or raw["affine_transform"].dtype.kind != "f":
            raise ValueError("RAW_AFFINE: six floating affine values required")
        affine = tuple(map(F, raw["affine_transform"]))
        if (len(affine) != 6 or affine[0] <= 0 or affine[1] != 0
                or affine[3] != 0 or affine[4] != -affine[0]):
            raise ValueError("Exact north-up square source affine required")
        if isinstance(epsg, bool) or not isinstance(epsg, (int, np.integer)) or epsg <= 0:
            raise ValueError("Explicit source EPSG required")
        if window is None:
            bounds = (0, H - 1, 0, W - 1)
        else:
            bounds = tuple(window[k] for k in ("r0", "r1", "c0", "c1"))
            if any(isinstance(v, bool) or not isinstance(v, int) for v in bounds):
                raise ValueError("Existing inclusive integer window required")
        r0, r1, c0, c1 = bounds
        if not (0 <= r0 <= r1 < H and 0 <= c0 <= c1 < W):
            raise ValueError("Existing window outside source grid")
        sl = (slice(r0, r1 + 1), slice(c0, c1 + 1))
        current = known_burned & ((iv & (active == 1)) | ~iv)
        req_remaining = [F(float(v)) for v in remaining[sl][(known_burned & iv & (active == 1))[sl]]]
        if (known_burned & ~iv)[sl].any():
            req_remaining.append(T)
        minimum_R = max(req_remaining, default=F(0))
        R = minimum_R if initial_remaining_s is None else F(initial_remaining_s)
        if not minimum_R <= R <= T:
            raise ValueError("Declared max-remaining enclosure does not enclose original current fire")
        limits = tuple(F(t) for t in (member_valid_until_s if member_valid_until_s is not None else [horizon] * len(ids)))
        if len(limits) != len(ids) or any(not 0 < t <= horizon or t.denominator != 1 for t in limits):
            raise ValueError("Explicit positive whole-second member validity inside saved horizon required")
        if not isinstance(terminal_inclusive, bool):
            raise ValueError("Explicit terminal point convention required")
        self.raw = MappingProxyType(raw)
        self.trajectory_indices = tuple(map(int, ids))
        self.cutoff_utc = cutoff_utc
        _utc(cutoff_utc)
        self.epsg, self.seed, self.timing = int(epsg), int(seed), timing
        self.source_horizon_s, self.T, self.R = horizon, T, R
        self.member_valid_until_s, self.terminal_inclusive = limits, terminal_inclusive
        self.bounds, self.slice = bounds, sl
        self.shape = (r1 - r0 + 1, c1 - c0 + 1)
        self.affine = (affine[0], F(0), affine[2] + c0 * affine[0], F(0), affine[4], affine[5] + r0 * affine[4])
        self._source_identity_json = json.dumps(source_identity or {}, sort_keys=True, allow_nan=False)
        self.raw_sha256 = MappingProxyType({k: _digest(a) for k, a in raw.items()})
        self.current_native = _snapshot(current[sl])
        self.unknown_native = _snapshot((first[(slice(None),) + sl] == -2) | ~valid[sl])
        self._sealed = True

    @property
    def source_identity(self):
        return json.loads(self._source_identity_json)

    def __getitem__(self, key):
        raise TypeError("CONTACT_ONLY_SOURCE_IS_NOT_A_FULL_POLICY_HAZARD_PACKET")

    def assert_integrity(self):
        if any(_digest(a) != self.raw_sha256[k] for k, a in self.raw.items()):
            raise ValueError("Raw source snapshot changed")

    def represented_events(self):
        # Call the existing timing implementation with original row identities.
        path = Path(__file__).resolve().parents[3] / "scenario-members/bridge_v2.py"
        spec = importlib.util.spec_from_file_location("_known_footprint_bridge", path)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        full = bridge.ignition_seconds(self.raw["trajectory_first_burn_hour"], seed=self.seed,
                                       timing=self.timing, trajectory_indices=self.trajectory_indices)
        return full[(slice(None),) + self.slice].copy()

    def provenance(self):
        return dict(schema=SCOPE, source_identity=copy.deepcopy(self.source_identity),
                    raw_array_sha256=dict(self.raw_sha256), trajectory_indices=list(self.trajectory_indices),
                    cutoff_utc=self.cutoff_utc, source_horizon_s=str(self.source_horizon_s),
                    member_valid_until_s=list(map(str, self.member_valid_until_s)),
                    terminal_inclusive=self.terminal_inclusive, timing=self.timing, seed=self.seed,
                    burning_duration_s=str(self.T), initial_remaining_enclosure_s=str(self.R),
                    initial_age_policy="Known burned cells with unknown age use the full-T enclosure; current cells share max remaining.",
                    window_rows_cols_north_up=list(self.bounds),
                    right_censoring="-1 means no first ignition through the finite saved horizon only")


def _validate_binding(graph, request, source):
    if not isinstance(source, KnownFootprintSource):
        raise ValueError("Explicit known-footprint source required")
    source.assert_integrity()
    g = graph["grid"]
    h, w = source.shape
    expected = (F(g["resolution"]), F(0), F(g["x0"]), F(0), -F(g["resolution"]),
                F(g["y0"]) + h * F(g["resolution"]))
    if (g["height"] != h or g["width"] != w or source.affine != expected
            or graph["crs"] != "EPSG:%d" % source.epsg):
        raise ValueError("Original source/graph grid or CRS mismatch")
    if _utc(request["as_of"]) != _utc(source.cutoff_utc):
        raise ValueError("Original issue as-of differs from source cutoff")
    dep, hor = F(request["departure"]), F(request["horizon"])
    if dep < 0 or hor < dep or dep.denominator != 1 or hor.denominator != 1:
        raise ValueError("Original whole-second nonnegative mission clock required")
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    if len(nodes) != len(graph["nodes"]) or len(edges) != len(graph["edges"]):
        raise ValueError("Duplicate original graph identity")
    origin = request["position"].get("node")
    if origin not in nodes or set(request["position"]) != {"node"}:
        raise ValueError("Reviewed scope requires an exact node issue position")
    incoming = request["incoming_edge"]
    if incoming is not None and (incoming not in edges or edges[incoming]["v"] != origin):
        raise ValueError("Original incoming-edge context mismatch")
    for e in edges.values():
        if (e["u"] not in nodes or e["v"] not in nodes or isinstance(e["travel_ticks"], bool)
                or not isinstance(e["travel_ticks"], int) or e["travel_ticks"] <= 0):
            raise ValueError("Original directed lattice graph required")
    if not request["destinations"] or any(d["node"] not in nodes or F(d["dwell"]) < 0 for d in request["destinations"]):
        raise ValueError("Original destination and nonnegative dwell required")
    if not source.terminal_inclusive and any(F(d["dwell"]).denominator != 1 for d in request["destinations"]):
        raise ValueError("Exclusive source terminal requires whole-second dwell for the supported integer finish clock")
    if len({d["node"] for d in request["destinations"]}) != len(request["destinations"]):
        raise ValueError("One opening/dwell record per destination node required")
    return nodes, edges


def support_barriers(graph, source):
    """Exact node/edge support in original list order, without changing data.

    A known rectangle is a sufficient shortcut; mixed rectangles use every
    frozen Fraction chord midpoint, grid-cut point and endpoint occupancy.
    """
    checker = adapter.install()["independent"]
    nodes = {n["id"]: n for n in graph["nodes"]}
    H, W = source.shape
    cells = [checker._cell(graph, n) for n in graph["nodes"]]
    unknown = source.unknown_native.any(axis=0)[::-1].ravel()
    node_known = ~unknown[cells]
    by_id = dict(zip(nodes, cells))
    edge_known = []
    for edge in graph["edges"]:
        a, b = by_id[edge["u"]], by_id[edge["v"]]
        ar, ac = divmod(a, W); br, bc = divmod(b, W)
        if unknown[a] or unknown[b]:
            edge_known.append(False)
        elif not unknown.reshape(H, W)[min(ar, br):max(ar, br) + 1, min(ac, bc):max(ac, bc) + 1].any():
            edge_known.append(True)
        else:
            occupied = [o["cell"] for o in geometry.edge_occupancies(edge, 0, 1, graph=graph, node_lookup=nodes)]
            edge_known.append(not unknown[occupied].any())
    return _snapshot(node_known), _snapshot(np.asarray(edge_known, dtype=bool))


def check_contact_route(graph, request, source, legs, destination):
    """Check original raw data and independent geometry, never search barriers.

    Shape and occupancy use the separately copied independent checker. Flame
    tests regenerate the original uniform rule directly from full-grid raw
    values and identities, without the candidate's events or interval cache.
    """
    violations = []
    reports = []
    try:
        nodes, edges = _validate_binding(graph, request, source)
        ind = adapter.install()["independent"]
        _, _, arrival, _ = ind._shape(graph, {"dt": 1}, request, legs, destination)
        dest = next(d for d in request["destinations"] if d["node"] == destination)
        finish = F(arrival) + F(dest["dwell"])
        if finish > F(request["horizon"]) or not any(F(a) <= F(arrival) and finish <= F(b) for a, b in dest["open_intervals"]):
            raise ValueError("Exact destination dwell horizon or opening violation")
        spans = ind._position_spans(graph, request["position"], F(request["departure"]), nodes, edges)
        for leg in legs:
            spans.extend(ind._occupancy(graph, leg, nodes, edges))
        spans.append((ind._cell(graph, nodes[destination]), F(arrival), F(finish)))
        r0, _, c0, _ = source.bounds
        H, W = source.shape
        raw = source.raw
        valid, burned = raw["source_burned_area_valid"], raw["source_burned_area"]
        iv, active = raw["heat__initial_burning_valid"], raw["heat__initial_active_burning_probability"]
        for k, ident in enumerate(source.trajectory_indices):
            field = raw["trajectory_first_burn_hour"][k]
            draws = np.random.default_rng([source.seed, ident]).random(field.shape)
            codes = set()
            for cell, lo, hi in spans:
                lo, hi = F(lo), F(hi)
                limit = source.member_valid_until_s[k]
                if lo < 0 or hi > limit or (hi == limit and not source.terminal_inclusive):
                    codes.add("OUTSIDE_FINITE_SOURCE_CLOCK")
                    continue
                if not 0 <= cell < H * W:
                    codes.add("OUTSIDE_SOURCE_GRID")
                    continue
                gr, c = divmod(cell, W)
                r, c = r0 + H - 1 - gr, c0 + c
                hour = int(field[r, c])
                if hour == -2 or not valid[r, c]:
                    codes.add("UNKNOWN_OCCUPIED_CELL")
                    continue
                current = burned[r, c] == 1 and (not iv[r, c] or active[r, c] == 1)
                if current and lo < source.R and hi >= 0:
                    codes.add("REPRESENTED_FLAME_CONTACT")
                if hour > 0:
                    birth = F(float((hour - 1) * 3600.0 + draws[r, c] * 3600.0))
                    if lo < birth + source.T and hi >= birth:
                        codes.add("REPRESENTED_FLAME_CONTACT")
            reports.append(dict(trajectory_index=ident, contact_pass=not codes, violations=sorted(codes),
                                peak=None, dose=None, risk=None))
            violations.extend("trajectory:%d:%s" % (ident, code) for code in sorted(codes))
        return dict(ok=not violations, certificate_scope=SCOPE, violations=violations,
                    per_member=reports, arrival=arrival,
                    finish_including_dwell=int(finish) if finish.denominator == 1 else str(finish),
                    peak=None, dose=None, risk=None, full_policy_status="UNKNOWN", physical_safety_claim=False)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        return dict(ok=False, certificate_scope=SCOPE, violations=["INVALID_OR_UNSUPPORTED_WITNESS:" + str(exc)],
                    per_member=reports, peak=None, dose=None, risk=None, full_policy_status="UNKNOWN", physical_safety_claim=False)


class _SearchView:
    """Private union-only view, with no invented per-member exposure history."""
    supported = True
    ids = ()

    def __init__(self, source):
        from wfg_scenario_members.contact import ContactModel
        self.cell_intervals = ContactModel.from_arrays(source.represented_events(), source.current_native,
                                                       source.T, source.R).cell_intervals


def plan_contact_route(graph, request, source, *, method="sipp", wall_s=30.0, max_labels=None):
    """Explicit opt-in. Failed restricted searches say nothing about global refusal.

    Original issued history is returned verbatim. A private request omits
    thermal histories and budgets, rather than assigning them to new IDs.
    Only independent original-data checking can return the typed contact status.
    """
    import time
    started = time.perf_counter()
    if method not in ("sipp", "sweep"):
        raise ValueError("Choose sipp or sweep")
    if not math.isfinite(wall_s) or wall_s <= 0:
        raise ValueError("Positive finite wall limit required")
    out = dict(status=UNRESOLVED, certificate_scope=SCOPE, planner=method, arrival=None, legs=[], destination=None,
               contact_check=None, peak=None, dose=None, risk=None, full_policy_status="UNKNOWN",
               physical_safety_claim=False, original_request=copy.deepcopy(request), metrics={},
               history_handling=dict(contact_search="THERMAL_HISTORY_AND_BUDGETS_OMITTED",
                                     history_rebinding=False, thermal_history_checked=False,
                                     kinematic_issue_context="UNCHANGED"),
               original_domain_refusal="UNRESOLVED", original_domain_optimality="UNRESOLVED")
    try:
        nodes, _ = _validate_binding(graph, request, source)
        out["source"] = source.provenance()
        node_known, edge_known = support_barriers(graph, source)
        nidx = {n["id"]: i for i, n in enumerate(graph["nodes"])}
        out["support_barriers"] = dict(node_known_sha256=_digest(node_known), edge_known_sha256=_digest(edge_known),
                                       blocked_nodes=int((~node_known).sum()), blocked_edges=int((~edge_known).sum()))
        if not node_known[nidx[request["position"]["node"]]]:
            out["reason"] = "UNKNOWN_ISSUE_FOOTPRINT"
            return out
        eligible = [d for d in request["destinations"] if node_known[nidx[d["node"]]]]
        if not eligible:
            out["reason"] = "UNKNOWN_DESTINATION_FOOTPRINT"
            return out
        limit = min(source.member_valid_until_s)
        bound = min(F(request["horizon"]), limit)
        if bound.denominator != 1:
            raise ValueError("Unsupported fractional source/member horizon")
        horizon = int(bound)
        if not source.terminal_inclusive and bound == limit and bound.denominator == 1:
            horizon -= 1
        if horizon < request["departure"]:
            out["reason"] = "OUTSIDE_FINITE_SOURCE_CLOCK"
            return out
        # Removing thermal fields is an explicit contact relaxation. No history
        # value is copied to a selected trajectory or changed in the result.
        search_request = copy.deepcopy(request)
        search_request.update(horizon=horizon, incurred={}, budgets={"dose": {}}, destinations=copy.deepcopy(eligible))
        out["effective_search_horizon_s"] = horizon
        view = _SearchView(source)
        ocell = adapter.install()["independent"]._cell(graph, nodes[request["position"]["node"]])
        dep = F(request["departure"])
        if frontend._cell_contact(view.cell_intervals, ocell, dep, dep):
            out["reason"] = "REPRESENTED_CONTACT_AT_ISSUE"
            return out
        build_started = time.perf_counter()
        if method == "sipp":
            extra = {int(j): [(int(dep), horizon)] for j in np.flatnonzero(~edge_known)}
            inst, pg = frontend.build_instance(graph, search_request, view, extra_blocked=extra)
            for ni in np.flatnonzero(~node_known):
                inst.wait_block[int(ni)] = [(int(dep), horizon)]
                inst.accept[int(ni)] = []
            build_s = time.perf_counter() - build_started
            raw = sipp.solve(inst, deadline=started + wall_s, max_labels=max_labels)
            out["metrics"] = dict(raw["metrics"], build_s=build_s, search_s=raw["wall_s"],
                                  blocked_edges=len(inst.edge_block), blocked_wait_nodes=len(inst.wait_block))
            found = raw["status"] == "FOUND"
            legs = [dict(kind=kind, **({"edge": pg.edges[ident]["id"], "from_fraction": 0, "to_fraction": 1}
                                      if kind == "EDGE" else {"node": pg.node_list[ident]}), start=a, end=b)
                    for kind, ident, a, b in raw.get("legs", [])]
            destination = pg.node_list[raw["destination_node"]] if found else None
        else:
            from .restricted_sweep import contact_sweep
            checker = adapter.install()["independent"]

            class Core:
                node_cell = staticmethod(geometry.node_cell)
                edge_occupancies = staticmethod(geometry.edge_occupancies)
                _globally_supported = staticmethod(lambda h, r: True)

            def shape(g, h, r, legs, dest, zero_view):
                try:
                    checker._shape(g, h, r, legs, dest)
                    return {"ok": True, "per_member": {}}
                except (ValueError, TypeError, KeyError) as exc:
                    return {"ok": False, "reason": str(exc)}

            raw = contact_sweep(graph, {"dt": 1, "version": 1, "members": []}, search_request, view,
                                wall_s=max(0, started + wall_s - time.perf_counter()), core=Core,
                                check_route_mode=shape, zero_view=None, node_known=node_known, edge_known=edge_known)
            found = raw["status"] in ("CONDITIONAL_OPTIMUM", "CHECKED_ROUTE")
            out["metrics"] = raw["metrics"]
            legs, destination = raw.get("legs", []), raw.get("destination")
        out["search_status"] = raw["status"]
        if not found:
            out["reason"] = "RESTRICTED_SEARCH_" + raw["status"]
            return out
        checked = check_contact_route(graph, request, source, legs, destination)
        out["contact_check"] = checked
        if not checked["ok"]:
            out["reason"] = "INDEPENDENT_ORIGINAL_DATA_CHECK_REFUSED"
            return out
        if time.perf_counter() >= started + wall_s:
            out["reason"] = "WALL_LIMIT_AFTER_INDEPENDENT_CHECK"
            return out
        out.update(status=CHECKED, reason="INDEPENDENT_ORIGINAL_DATA_CONTACT_CHECK",
                   arrival=checked["arrival"], legs=legs, destination=destination,
                   restricted_problem_optimality="EARLIEST_CONTACT_ARRIVAL_WITHIN_SUPPORT_RESTRICTION")
        return out
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        out["reason"] = "UNSUPPORTED_INPUT:" + str(exc)
        return out
    finally:
        out["wall_s"] = time.perf_counter() - started
