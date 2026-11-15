"""Native forecast support on closed road-cell intersections.

This is a support constraint for research routing, not a model of unknown fire.
"""
from fractions import Fraction as F
from math import ceil, floor
from pathlib import Path

import numpy as np

from corridor_events import clip, union


def missing_intervals(packet, graph, horizon):
    """Return time intervals missing in at least one scenario member per cell."""
    grid = graph["grid"]
    h, w = grid["height"], grid["width"]
    with np.load(Path(packet) / "constructed_arrays.npz", allow_pickle=False) as a:
        raw = a["native_hourly_valid"]
        if raw.dtype != np.bool_ or raw.ndim != 4 or raw.shape[1:] != (4, h, w) or not raw.shape[0]:
            raise ValueError("INVALID_NATIVE_HOURLY_VALID")
        valid = np.all(raw, axis=1)
    missing = {}
    for hour, member_valid in enumerate(valid):
        start = hour * 3600
        # Match the original reader's last-hour clamping through the horizon.
        end = horizon + 1 if hour == len(valid) - 1 else min((hour + 1) * 3600, horizon + 1)
        if start > horizon:
            break
        rows, cols = np.nonzero(~member_valid)
        for row, col in zip(rows.tolist(), cols.tolist()):
            cell = (h - 1 - row) * w + col
            missing.setdefault(cell, []).append((start, end))
    return {cell: union(spans) for cell, spans in missing.items()}


def spatial_intersections(a, b, grid, missing):
    """Enumerate missing in-grid closed cells intersected by a road segment."""
    x0, y0, size = map(F, (grid["x0"], grid["y0"], grid["resolution"]))
    width, height = grid["width"], grid["height"]
    cols = sorted(floor((p[0] - x0) / size) for p in (a, b))
    rows = sorted(floor((p[1] - y0) / size) for p in (a, b))
    for row in range(max(0, rows[0] - 1), min(height - 1, rows[1] + 1) + 1):
        for col in range(max(0, cols[0] - 1), min(width - 1, cols[1] + 1) + 1):
            cell = row * width + col
            if cell not in missing:
                continue
            x, y = x0 + size * col, y0 + size * row
            cut = clip(a, b, (x, x + size, y, y + size))
            if cut is not None:
                yield cell, cut


def inside(a, grid):
    x0, y0, size = map(F, (grid["x0"], grid["y0"], grid["resolution"]))
    # A point exactly on the external boundary also touches an unsupported outside cell.
    return x0 < a[0] < x0 + size * grid["width"] and y0 < a[1] < y0 + size * grid["height"]


def constraints(graph, compiled, missing, request, deadline):
    """Compute exact unsupported-cell entry restrictions for each corridor."""
    from time import perf_counter

    grid = graph["grid"]
    horizon = int(request["horizon"])
    nodes = {n["id"]: n for n in graph["nodes"]}
    xy = {}
    def point(node):
        if node not in xy:
            xy[node] = (F(nodes[node]["x"]), F(nodes[node]["y"]))
        return xy[node]
    blocks = []
    for i, part in enumerate(compiled.parts):
        if i % 64 == 0 and perf_counter() >= deadline:
            raise TimeoutError("NATIVE_SUPPORT_CONSTRAINT_BUDGET")
        out = []
        offset = 0
        for idx in part:
            edge = compiled.index.edges[idx]
            a, b = point(edge["u"]), point(edge["v"])
            duration = int(edge["travel_ticks"])
            if not inside(a, grid) or not inside(b, grid):
                out.append((0, horizon + 1))
            else:
                for cell, (left, right) in spatial_intersections(a, b, grid, missing):
                    for start, end in missing[cell]:
                        lo = max(0, ceil(start - duration * right) - offset)
                        hi = min(horizon + 1, ceil(end - duration * left) - offset)
                        if lo < hi:
                            out.append((lo, hi))
            offset += duration
        blocks.append(union(out))
    point_blocks = {}
    important = compiled.index.waitable | {request["position"]["node"], request["destinations"][0]["node"]}
    for i, node in enumerate(important):
        if i % 64 == 0 and perf_counter() >= deadline:
            raise TimeoutError("NATIVE_SUPPORT_POINT_BUDGET")
        pt = point(node)
        if not inside(pt, grid):
            point_blocks[node] = [(0, horizon + 1)]
        else:
            periods = [span for cell, _ in spatial_intersections(pt, pt, grid, missing) for span in missing[cell]]
            if periods:
                point_blocks[node] = union(periods)
    return blocks, point_blocks


def route_supported(world, req, route):
    """Recheck the reconstructed complete journey independently of corridor masks."""
    from math import floor

    node = req["position"]["node"]
    actions = []
    for leg in route["legs"]:
        if leg["kind"] == "WAIT":
            target = node
        else:
            edge = world.edges[leg["edge"]]
            if edge["u"] != node:
                raise ValueError("ROUTE_DISCONTINUITY")
            target = edge["v"]
        actions.append((node, target, F(leg["start"]), F(leg["end"])))
        node = target
    arrival = F(route["arrival"])
    stay = req["destinations"][0]["dwell"]
    actions.append((node, node, arrival, arrival + F(stay)))
    for u, v, start, end in actions:
        for row, col, lo, hi, _ in world.cells(u, v):
            left, right = start + lo * (end - start), start + hi * (end - start)
            first = min(len(world.valid) - 1, floor(left / 3600))
            last = min(len(world.valid) - 1, floor(right / 3600))
            for hour in range(first, last + 1):
                if not (0 <= row < world.h and 0 <= col < world.w and world.valid[hour, row, col]):
                    return False
    return True
