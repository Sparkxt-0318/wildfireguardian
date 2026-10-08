"""Clearly labelled engineering fixtures. Never mentor outputs or road thermal truth."""

from .validation import chord_segments


def example():
    grid = {"x0": 0.0, "y0": 0.0, "resolution": 10.0, "width": 4, "height": 2}
    nodes = [
        {"id": "O", "x": 5.0, "y": 5.0, "waitable": False},
        {"id": "A", "x": 15.0, "y": 5.0, "waitable": True},
        {"id": "D", "x": 25.0, "y": 5.0, "waitable": False},
        {"id": "B", "x": 15.0, "y": 15.0, "waitable": False},
    ]
    by = {n["id"]: n for n in nodes}
    edges = []
    for eid, u, v, t, r in [
        ("OA", "O", "A", 2, "AO"),
        ("AO", "A", "O", 2, "OA"),
        ("AD", "A", "D", 2, "DA"),
        ("DA", "D", "A", 2, "AD"),
        ("OB", "O", "B", 3, "BO"),
        ("BO", "B", "O", 3, "OB"),
        ("BD", "B", "D", 3, "DB"),
        ("DB", "D", "B", 3, "BD"),
    ]:
        edges.append(
            {
                "id": eid,
                "u": u,
                "v": v,
                "travel_ticks": t,
                "reverse_edge": r,
                "segments": chord_segments(grid, by[u], by[v]),
            }
        )
    graph = {
        "revision": "labelled-fixture-road-v1",
        "crs": "EPSG:5179",
        "grid": grid,
        "nodes": nodes,
        "edges": edges,
        "forbidden_turns": [],
        "mid_edge_reversal": False,
    }
    N = grid["width"] * grid["height"]
    members = []
    for mid, flux in [("m0", 1.0), ("m1", 2.0)]:
        members.append(
            {
                "id": mid,
                "breakpoints": [0.0, 30.0],
                "flux": [[flux] * N],
                "flame": [[False] * N],
                "support": [[True] * N],
            }
        )
    hazard = {
        "schema": "wfg.routing.edgegrid/1",
        "version": 1,
        "graph_revision": graph["revision"],
        "crs": graph["crs"],
        "grid": grid.copy(),
        "dt": 1.0,
        "time_origin": "2026-10-04T00:00:00+08:00",
        "issued_at": "2026-10-04T00:00:00+08:00",
        "available_at": "2026-10-04T00:00:00+08:00",
        "valid_from": 0.0,
        "valid_until": 30.0,
        "units": {"time": "s", "flux": "kW/m2", "dose": "kJ/m2"},
        "evidence_class": "LABELLED_FIXTURE",
        "provenance": {
            "source": "local deterministic example",
            "interpretation": "generated incident heat-flux proxy, not forecast/physical truth",
        },
        "channels": ["flame_contact", "incident_heat_flux"],
        "unsupported_channels": ["embers", "secondary_ignition"],
        "members": members,
    }
    request = {
        "position": {"node": "O"},
        "incoming_edge": None,
        "departure": 0.0,
        "horizon": 20.0,
        "destinations": [{"node": "D", "dwell": 2.0, "open_intervals": [[0.0, 30.0]]}],
        "incurred": {"m0": 0.0, "m1": 0.0},
        "hazard_version": 1,
        "as_of": "2026-10-04T00:00:00+08:00",
        "objective": "earliest_arrival",
        "exposure_scope": "route_only",
        "budgets": {"peak": 10.0, "dose": {"m0": 25.0, "m1": 25.0}},
        "limits": {
            "wall_s": 5.0,
            "max_labels": 100000,
            "max_expansions": 100000,
            "frontier_width": 4096,
        },
        "solver": "baseline",
    }
    return {"graph": graph, "hazard": hazard, "request": request}
