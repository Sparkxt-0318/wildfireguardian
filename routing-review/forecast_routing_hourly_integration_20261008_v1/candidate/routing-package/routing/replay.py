"""Deterministic JSON replay of an explicitly labelled routing fixture."""

import argparse
import json
from copy import deepcopy
from pathlib import Path
from .session import RoutingSession


def replay(fixture, *, prepare=False):
    """No forecast generation, probability conversion, or deployment inference."""
    session = RoutingSession(fixture["graph"], prepare=prepare)
    events = []
    admission = session.accept_update(fixture["hazard"], fixture["request"]["as_of"])
    events.append(admission)
    if admission["status"] != "ACCEPTED_UPDATE":
        return {"status": admission["status"], "events": events, "result": None}
    result = session.plan(fixture["request"])
    committed = session.commit(result)
    events.append(
        {
            "status": "PLAN_COMMITTED" if committed else "PLAN_NOT_COMMITTED",
            "request_generation": session.generation,
            "result": deepcopy(result),
        }
    )
    for action in fixture.get("events", []):
        kind = action["kind"]
        if kind == "UPDATE":
            result = None
            events.append(
                session.accept_update(
                    action["hazard"],
                    action["as_of"],
                    action.get("conservative_mapping"),
                )
            )
        elif kind == "PROGRESS":
            result = None
            events.append(
                session.set_progress(
                    action["position"],
                    action["incoming_edge"],
                    action["departure"],
                    action["incurred"],
                    action["history"],
                )
            )
        elif kind == "PLAN":
            result = session.plan(action["request"])
            events.append(
                {
                    "status": result["status"],
                    "request_generation": result.get("request_generation"),
                    "committed": session.commit(result),
                    "result": deepcopy(result),
                }
            )
        elif kind == "RETAINED":
            retained = session.retained_plan(action.get("as_of"))
            result = retained if retained.get("status") == "CHECKED_ROUTE" else None
            events.append(retained)
        elif kind == "RETURN":
            from .fallback import checked_return

            if session.hazard is None:
                events.append({"status": "UNSUPPORTED", "reason": "NO_ACCEPTED_HAZARD"})
            else:
                req = session._request(action.get("request", fixture["request"]))
                history = action.get(
                    "history", session.progress["history"] if session.progress else []
                )
                events.append(
                    session.check_return(
                        req, action["endpoint"], action.get("dwell", 0), history=history
                    )
                )
        elif kind == "GRAPH_REPLACE":
            result = None
            events.append(
                session.replace_graph(action["graph"], reset=action.get("reset", False))
            )
        elif kind == "RESET":
            result = None
            events.append(session.reset())
        else:
            raise ValueError("Unknown replay event: " + str(kind))
    output = {
        "status": result["status"] if result else events[-1]["status"],
        "events": events,
        "result": result,
        "evidence_class": fixture["hazard"]["evidence_class"],
        "interpretation": "Declared fixture routing check; no physical road tenability validation",
        "timing": "Wall duration and process RSS excluded from deterministic replay; resource completion still runtime dependent",
    }
    output = deepcopy(output)

    def omit_wall(value):
        if isinstance(value, dict):
            if isinstance(value.get("metrics"), dict):
                value["metrics"].pop("wall_s", None)
                value["metrics"].pop("peak_rss_mb", None)
            for child in value.values():
                omit_wall(child)
        elif isinstance(value, list):
            for child in value:
                omit_wall(child)

    omit_wall(output)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--prepare-graph",
        action="store_true",
        help="admit one owned graph for this replay process",
    )
    args = parser.parse_args(argv)
    result = replay(json.loads(args.fixture.read_text()), prepare=args.prepare_graph)
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
