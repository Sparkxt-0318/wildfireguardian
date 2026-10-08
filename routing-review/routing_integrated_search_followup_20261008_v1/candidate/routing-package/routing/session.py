"""Forecast admission and continuation state with stale-result protection."""

from copy import deepcopy
import math
from fractions import Fraction


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


class RoutingSession:
    def __init__(self, graph, *, prepare=False, graph_ownership="snapshot"):
        from .validation import validate_graph
        from .prepared import prepare_graph

        if graph_ownership not in {"snapshot", "checked"}:
            raise ValueError("graph_ownership must be snapshot or checked")
        if graph_ownership == "checked" and not prepare:
            raise ValueError("checked ownership requires preparation")
        self._graph_ownership = graph_ownership
        self._prepared = prepare_graph(graph) if prepare else None
        self._external_graph = graph if graph_ownership == "checked" else None
        self._raw_graph = None if prepare else validate_graph(graph)
        self.hazard = None
        self.generation = 0
        self.progress = None
        self.retained = None
        self.last_update = None
        self._last_request = None
        self._pending_request = None
        self._as_of = None

    @property
    def graph(self):
        """Prepared sessions export fresh copies; raw sessions retain the raw API."""
        return self._operation_graph()

    @property
    def prepared_graph(self):
        """Immutable handle for serialized-owner planning; no shared mutable trust."""
        return self._prepared

    def _operation_graph(self):
        from .validation import ValidationError

        if self._prepared is None:
            return self._raw_graph
        if self._external_graph is not None and not self._prepared.matches(
            self._external_graph
        ):
            self.generation += 1
            self._pending_request = self.retained = self._last_request = None
            raise ValidationError(
                "PREPARED_GRAPH_MISMATCH", "explicit graph replacement required"
            )
        return self._prepared.snapshot()

    def _validated_request(self, graph, hazard, request):
        from .validation import validate_hazard, validate_request

        if self._prepared is None:
            return validate_request(graph, hazard, request)
        admitted = validate_hazard(
            graph, hazard, request.get("as_of"), _graph_validated=True
        )
        return validate_request(graph, admitted, request, _validated_inputs=True)

    def replace_graph(self, graph, *, reset=False):
        """Admit replacement atomically; active mission state requires explicit reset."""
        from .validation import validate_graph, ValidationError
        from .prepared import prepare_graph

        if type(reset) is not bool:
            return self._event("INVALID_INPUT", "GRAPH_REPLACEMENT_RESET_FLAG")
        active = any(
            v is not None
            for v in (self.hazard, self.progress, self.retained, self._pending_request)
        )
        if active and not reset:
            return self._event("INVALID_INPUT", "GRAPH_REPLACEMENT_REQUIRES_RESET")
        try:
            replacement = (
                prepare_graph(graph)
                if self._prepared is not None
                else validate_graph(graph)
            )
        except (ValidationError, TypeError, ValueError, KeyError) as exc:
            return self._event("INVALID_INPUT", getattr(exc, "code", str(exc)))
        if reset:
            self.reset()
        else:
            self.generation += 1
        if self._prepared is not None:
            self._prepared = replacement
            self._external_graph = graph if self._graph_ownership == "checked" else None
        else:
            self._raw_graph = replacement
        return self._event(
            "GRAPH_REPLACED",
            "DEPENDENT_STATE_CLEARED" if reset else "EMPTY_SESSION_GRAPH_REPLACED",
        )

    def check_return(self, request, endpoint, dwell=0, *, history=None):
        """Check recorded return against current progress and freshly admitted inputs."""
        from .fallback import checked_return
        from .validation import ValidationError

        try:
            graph = self._operation_graph()
        except ValidationError as exc:
            return self._event("INVALID_INPUT", exc.code)
        if self.hazard is None:
            return self._event("UNSUPPORTED", "NO_ACCEPTED_HAZARD")
        if not isinstance(request, dict):
            return self._event("INVALID_INPUT", "REQUEST_SHAPE")
        req = self._request(request)
        records = (
            history
            if history is not None
            else self.progress["history"] if self.progress else []
        )
        return checked_return(
            self._prepared if self._prepared is not None else graph,
            self.hazard,
            req,
            records,
            endpoint,
            dwell,
        )

    def _event(self, status, reason, **details):
        return {
            "status": status,
            "reason": reason,
            "request_generation": self.generation,
            "hazard_version": self.hazard.get("version") if self.hazard else None,
            **details,
        }

    def accept_update(self, hazard, as_of, conservative_mapping=None):
        """Optional mapping is an explicit upper bound for each new member's past dose.

        On changed identity sets every value must bound the maximum dose incurred
        under any old member. This conservative boundary admits no inferred zero
        for a newly introduced forecast member.
        """
        from .validation import ValidationError

        try:
            graph = self._operation_graph()
        except ValidationError as exc:
            return self._event("INVALID_INPUT", exc.code)
        from .validation import validate_hazard, ValidationError

        try:
            candidate = validate_hazard(
                graph, hazard, as_of, _graph_validated=self._prepared is not None
            )
        except (ValidationError, TypeError, ValueError, KeyError) as exc:
            self.generation += 1
            self.last_update = self._event(
                "REJECTED_UPDATE",
                getattr(exc, "code", str(exc)),
                rejected_version=(
                    hazard.get("version") if isinstance(hazard, dict) else None
                ),
            )
            return deepcopy(self.last_update)
        if self.hazard and candidate["version"] <= self.hazard["version"]:
            self.generation += 1
            self.last_update = self._event(
                "STALE_UPDATE",
                "VERSION_NOT_NEWER",
                rejected_version=candidate["version"],
            )
            return deepcopy(self.last_update)
        if self.hazard:
            from .validation import timestamp

            if timestamp(candidate["issued_at"], "issued_at") < timestamp(
                self.hazard["issued_at"], "issued_at"
            ) or timestamp(candidate["available_at"], "available_at") < timestamp(
                self.hazard["available_at"], "available_at"
            ):
                self.generation += 1
                self.last_update = self._event(
                    "STALE_UPDATE",
                    "OUT_OF_ORDER_ISSUE_OR_AVAILABILITY",
                    rejected_version=candidate["version"],
                )
                return deepcopy(self.last_update)
        if self.hazard and candidate["time_origin"] != self.hazard["time_origin"]:
            self.generation += 1
            self.last_update = self._event(
                "REJECTED_UPDATE",
                "TIME_ORIGIN_CHANGE_REQUIRES_RESET",
                rejected_version=candidate["version"],
            )
            return deepcopy(self.last_update)
        old_ids = {m["id"] for m in self.hazard["members"]} if self.hazard else set()
        new_ids = {m["id"] for m in candidate["members"]}
        mapped = None
        if self.progress is not None and set(self.progress["incurred"]) != new_ids:
            prior = self.progress["incurred"]
            bound = max(prior.values(), default=0)
            if (
                not isinstance(conservative_mapping, dict)
                or set(conservative_mapping) != new_ids
                or any(
                    isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not _finite_number(v)
                    or v < bound
                    for v in conservative_mapping.values()
                )
            ):
                self.generation += 1
                self.last_update = self._event(
                    "UNSUPPORTED",
                    "CHANGED_MEMBER_HISTORY_REQUIRES_CONSERVATIVE_MAPPING",
                    rejected_version=candidate["version"],
                    old_members=sorted(old_ids),
                    new_members=sorted(new_ids),
                )
                return deepcopy(self.last_update)
            mapped = deepcopy(conservative_mapping)
        self.hazard = candidate
        self._as_of = as_of
        if mapped is not None:
            self.progress["incurred"] = mapped
        self.generation += 1
        self.last_update = self._event(
            "ACCEPTED_UPDATE",
            "VALIDATED_FORECAST_ADMITTED",
            mapping_applied=mapped is not None,
        )
        return deepcopy(self.last_update)

    def set_progress(self, position, incoming_edge, departure, incurred, history):
        """Record actual continuation state. Invalid input never replaces valid state."""
        from .validation import ValidationError

        try:
            graph = self._operation_graph()
        except ValidationError as exc:
            return self._event("INVALID_INPUT", exc.code)
        if self.hazard is None:
            return self._event("UNSUPPORTED", "NO_ACCEPTED_HAZARD")
        ids = {m["id"] for m in self.hazard["members"]}
        try:
            if not isinstance(incurred, dict) or set(incurred) != ids:
                raise ValueError("MEMBER_HISTORY_IDENTITY_MISMATCH")
            if any(
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not _finite_number(v)
                or v < 0
                for v in incurred.values()
            ):
                raise ValueError("INVALID_INCURRED_DOSE")
            if not isinstance(history, list) or not isinstance(position, dict):
                raise ValueError("INVALID_PROGRESS")
            # Request validation also checks lattice, location and turn context.
            from .validation import validate_request

            node = graph["nodes"][0]["id"]
            probe = {
                "position": position,
                "incoming_edge": incoming_edge,
                "departure": departure,
                "horizon": self.hazard["valid_until"],
                "destinations": [
                    {
                        "node": node,
                        "dwell": 0,
                        "open_intervals": [
                            [self.hazard["valid_from"], self.hazard["valid_until"]]
                        ],
                    }
                ],
                "incurred": incurred,
                "hazard_version": self.hazard["version"],
                "as_of": self._as_of,
                "objective": "earliest_arrival",
                "exposure_scope": "route_only",
                "budgets": {"peak": 1e300, "dose": {i: 1e300 for i in ids}},
                "solver": "baseline",
                "limits": {
                    "wall_s": 1,
                    "max_labels": 100,
                    "max_expansions": 100,
                    "frontier_width": 100,
                },
            }
            validated = self._validated_request(graph, self.hazard, probe)
            position, incoming_edge = validated["position"], validated["incoming_edge"]
            edge_map = {e["id"]: e for e in graph["edges"]}
            previous = None
            for index, entry in enumerate(history):
                edge = edge_map[entry["edge"]]
                a, b = entry["from_fraction"], entry["to_fraction"]
                if (
                    isinstance(a, bool)
                    or isinstance(b, bool)
                    or a != 0
                    or not isinstance(b, (int, float))
                    or not _finite_number(b)
                    or not 0 < b <= 1
                    or (b < 1 and index != len(history) - 1)
                ):
                    raise ValueError("INVALID_HISTORY_FRACTION")
                if previous is not None and previous["v"] != edge["u"]:
                    raise ValueError("DISCONTINUOUS_HISTORY")
                if (
                    previous is not None
                    and [previous["id"], edge["id"]] in graph["forbidden_turns"]
                ):
                    raise ValueError("FORBIDDEN_HISTORY_TURN")
                previous = edge
            if "edge" in position:
                if (
                    not history
                    or history[-1]["edge"] != position["edge"]
                    or history[-1]["to_fraction"] != position["fraction"]
                ):
                    raise ValueError("CURRENT_PARTIAL_HISTORY_MISMATCH")
            elif history and (
                history[-1]["to_fraction"] != 1
                or previous["v"] != position["node"]
                or incoming_edge != previous["id"]
            ):
                raise ValueError("CURRENT_NODE_HISTORY_MISMATCH")
            if self.progress and departure < self.progress["departure"]:
                raise ValueError("PROGRESS_TIME_REGRESSION")
            if self.progress and any(
                incurred[i] < self.progress["incurred"][i] for i in ids
            ):
                raise ValueError("INCURRED_DOSE_REGRESSION")
            if self.progress:
                old_history = self.progress["history"]
                if len(history) < len(old_history):
                    raise ValueError("HISTORY_TRUNCATION")
                for old, new in zip(old_history, history):
                    if (
                        old["edge"] != new["edge"]
                        or old["from_fraction"] != new["from_fraction"]
                        or new["to_fraction"] < old["to_fraction"]
                        or (old["to_fraction"] == 1 and new["to_fraction"] != 1)
                    ):
                        raise ValueError("HISTORY_REWRITE")
                old_pos = self.progress["position"]
                additions = history[len(old_history) :]
                if additions:
                    old_node = old_pos.get("node")
                    if old_node is None:
                        if history[len(old_history) - 1]["to_fraction"] != 1:
                            raise ValueError("PARTIAL_HISTORY_NOT_COMPLETED")
                        old_node = edge_map[old_pos["edge"]]["v"]
                    if edge_map[additions[0]["edge"]]["u"] != old_node:
                        raise ValueError("PROGRESS_TELEPORT")
                    incoming = self.progress["incoming_edge"]
                    if (
                        incoming is not None
                        and [incoming, additions[0]["edge"]] in graph["forbidden_turns"]
                    ):
                        raise ValueError("FORBIDDEN_PROGRESS_TURN")
                elif "node" in old_pos and position != old_pos:
                    raise ValueError("PROGRESS_TELEPORT")
                elif (
                    "node" in old_pos
                    and incoming_edge != self.progress["incoming_edge"]
                ):
                    raise ValueError("INCOMING_CONTEXT_REWRITE")
                elif "edge" in old_pos and not old_history:
                    raise ValueError("MISSING_PARTIAL_HISTORY")
                distance_ticks = 0
                if "edge" in old_pos:
                    delta = (
                        history[len(old_history) - 1]["to_fraction"]
                        - old_pos["fraction"]
                    )
                    distance_ticks += math.ceil(
                        (
                            Fraction(history[len(old_history) - 1]["to_fraction"])
                            - Fraction(old_pos["fraction"])
                        )
                        * edge_map[old_pos["edge"]]["travel_ticks"]
                    )
                for entry in additions:
                    distance_ticks += math.ceil(
                        Fraction(entry["to_fraction"])
                        * edge_map[entry["edge"]]["travel_ticks"]
                    )
                if (
                    departure - self.progress["departure"]
                    < distance_ticks * self.hazard["dt"]
                ):
                    raise ValueError("PROGRESS_FASTER_THAN_DECLARED_TRAVEL")
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            return self._event("INVALID_INPUT", getattr(exc, "code", str(exc)))
        self.progress = deepcopy(
            {
                "position": position,
                "incoming_edge": incoming_edge,
                "departure": departure,
                "incurred": incurred,
                "history": history,
            }
        )
        self.generation += 1
        return self._event("PROGRESS_ACCEPTED", "ACTUAL_STATE_RECORDED")

    def _request(self, request):
        req = deepcopy(request)
        progress = self.progress
        if progress is not None:
            for field in ("position", "incoming_edge", "departure", "incurred"):
                req[field] = deepcopy(progress[field])
        req["hazard_version"] = self.hazard["version"]
        if self._as_of is not None:
            req["as_of"] = self._as_of
        return req

    def plan(self, request):
        from .validation import ValidationError

        try:
            graph = self._operation_graph()
        except ValidationError as exc:
            return self._event("INVALID_INPUT", exc.code)
        if not isinstance(request, dict):
            return self._event("INVALID_INPUT", "REQUEST_SHAPE")
        if self.hazard is None:
            return self._event("UNSUPPORTED", "NO_ACCEPTED_HAZARD")
        from .core import solve

        req = self._request(request)
        from .validation import validate_request, ValidationError

        try:
            req = self._validated_request(graph, self.hazard, req)
        except (ValidationError, TypeError, ValueError, KeyError) as exc:
            return self._event("INVALID_INPUT", getattr(exc, "code", str(exc)))
        # Each solve belongs to a distinct request generation, even if the
        # forecast is unchanged. Two asynchronous completions cannot overwrite
        # the latest requested plan with an earlier request's result.
        self.generation += 1
        generation = self.generation
        self._pending_request = deepcopy(req)
        result = solve(
            self._prepared if self._prepared is not None else deepcopy(graph),
            deepcopy(self.hazard),
            req,
        )
        if (
            self.progress is None
            and result.get("status") != "INVALID_INPUT"
            and generation == self.generation
        ):
            self.progress = {
                k: deepcopy(req[k])
                for k in ("position", "incoming_edge", "departure", "incurred")
            }
            self.progress["history"] = deepcopy(req.get("history", []))
        result["request_generation"] = generation
        result["request"] = deepcopy(req)
        result["update_status"] = deepcopy(self.last_update)
        result["guidance_version_label"] = (
            "OLDER_ACCEPTED_VERSION"
            if self.last_update and self.last_update["status"] != "ACCEPTED_UPDATE"
            else "CURRENT_ACCEPTED_VERSION"
        )
        return result

    def commit(self, result):
        """False for stale, rejected, or independently inadmissible completions."""
        from .validation import ValidationError

        try:
            graph = self._operation_graph()
        except ValidationError as exc:
            return False
        if (
            not isinstance(result, dict)
            or self.hazard is None
            or result.get("hazard_version") != self.hazard["version"]
            or result.get("request_generation") != self.generation
            or result.get("status") not in {"CHECKED_ROUTE", "CONDITIONAL_OPTIMUM"}
        ):
            return False
        from .independent import check_route

        req = result.get("request")
        if not isinstance(req, dict):
            return False
        if req != self._pending_request:
            return False
        if self.progress is not None and any(
            req.get(k) != self.progress[k]
            for k in ("position", "incoming_edge", "departure", "incurred")
        ):
            return False
        try:
            if self._prepared is not None:
                self._validated_request(graph, self.hazard, req)
            checked = check_route(
                graph,
                self.hazard,
                req,
                result.get("legs", []),
                result.get("destination"),
            )
        except (ValueError, TypeError, KeyError):
            return False
        if not checked.get("ok"):
            return False
        if (
            result.get("request_generation") != self.generation
            or result.get("hazard_version") != self.hazard["version"]
        ):
            return False
        self.retained = deepcopy(result)
        self.retained["per_member"] = checked["per_member"]
        self._last_request = deepcopy(req)
        return True

    def retained_plan(self, as_of=None):
        """Display only after another independent check against current actual state."""
        from .validation import ValidationError

        try:
            graph = self._operation_graph()
        except ValidationError as exc:
            return self._event("INVALID_INPUT", exc.code)
        if self.retained is None or self.hazard is None:
            return self._event("UNSUPPORTED", "NO_RETAINED_PLAN")
        generation = self.generation
        hazard = deepcopy(self.hazard)
        retained = deepcopy(self.retained)
        from .independent import check_route

        req = self._request(self._last_request)
        if as_of is not None:
            req["as_of"] = as_of
        try:
            from .validation import validate_request

            req = self._validated_request(graph, hazard, req)
            checked = check_route(
                graph, hazard, req, retained["legs"], retained["destination"]
            )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            return self._event(
                "UNSUPPORTED",
                "RETAINED_PLAN_RECHECK_REFUSED",
                codes=[getattr(exc, "code", str(exc))],
                update_status=deepcopy(self.last_update),
            )
        if not checked.get("ok"):
            return self._event(
                "UNSUPPORTED",
                "RETAINED_PLAN_RECHECK_REFUSED",
                codes=checked.get("codes", []),
                update_status=deepcopy(self.last_update),
            )
        if (
            generation != self.generation
            or self.hazard is None
            or hazard["version"] != self.hazard["version"]
        ):
            return self._event("UNSUPPORTED", "RETAINED_PLAN_RECHECK_STALE")
        result = retained
        result.update(
            {
                "status": "CHECKED_ROUTE",
                "reason": "RETAINED_PLAN_INDEPENDENTLY_RECHECKED",
                "hazard_version": self.hazard["version"],
                "request_generation": self.generation,
                "request": req,
                "per_member": checked["per_member"],
                "update_status": deepcopy(self.last_update),
                "guidance_version_label": (
                    "OLDER_ACCEPTED_VERSION"
                    if self.last_update
                    and self.last_update["status"] != "ACCEPTED_UPDATE"
                    else "CURRENT_ACCEPTED_VERSION"
                ),
            }
        )
        return result

    def reset(self):
        self.hazard = self.progress = self.retained = self._last_request = (
            self.last_update
        ) = None
        self._pending_request = self._as_of = None
        self.generation += 1
        return self._event("RESET", "SESSION_STATE_CLEARED")
