"""Exact, dependency-free alternatives to baseline chord admission geometry.

This module is an isolated experiment. It never edits the baseline and never
caches hazard/request decisions. Factories are scoped to one validation job.
"""

from fractions import Fraction
import math


ZERO = Fraction(0)
ONE = Fraction(1)


def _default_fail(code, message):
    raise ValueError(code + ": " + message)


def _raw_grid_key(grid):
    return (grid["x0"], grid["y0"], grid["resolution"],
            grid["width"], grid["height"])


def _grid_fractions(grid):
    return (Fraction(grid["x0"]), Fraction(grid["y0"]),
            Fraction(grid["resolution"]), grid["width"], grid["height"])


def _point_fractions(node):
    return (Fraction(node["x"]), Fraction(node["y"]))


def _exact_segments(spec, u, v, fail):
    """Return (cell, exact_start, exact_end), restricting tested grid lines.

    All arithmetic remains rational. The strict open endpoint inequalities are
    retained, including grid-line and grid-vertex endpoint cases.
    """
    x0, y0, resolution, width, height = spec
    cuts = {ZERO, ONE}
    for a, b, base, extent in ((u[0], v[0], x0, width),
                               (u[1], v[1], y0, height)):
        if a == b:
            continue
        lo, hi = min(a, b), max(a, b)
        # lo < base + k*r < hi exactly; only interior grid lines count.
        first = max(1, math.floor((lo - base) / resolution) + 1)
        last = min(extent - 1, math.ceil((hi - base) / resolution) - 1)
        delta = b - a
        for k in range(first, last + 1):
            cuts.add((base + k * resolution - a) / delta)
    cuts = sorted(cuts)
    dx, dy = v[0] - u[0], v[1] - u[1]
    out = []
    for a, b in zip(cuts, cuts[1:]):
        midpoint = (a + b) / 2
        col = math.floor((u[0] + dx * midpoint - x0) / resolution)
        row = math.floor((u[1] + dy * midpoint - y0) / resolution)
        if not (0 <= col < width and 0 <= row < height):
            fail("SPATIAL_COVERAGE", "road coordinate outside grid")
        cell = row * width + col
        if out and out[-1][0] == cell:
            out[-1] = (cell, out[-1][1], b)
        else:
            out.append((cell, a, b))
    return tuple(out)


def _serialize(exact):
    # Float conversion occurs at the same final boundary as the baseline.
    return [{"cell": cell, "start": float(a), "end": float(b)}
            for cell, a, b in exact]


def make_range_clipped(fail=_default_fail):
    """No retained state. Cold exact range clipping plus local Fraction reuse."""
    def chord_segments(grid, u, v):
        return _serialize(_exact_segments(
            _grid_fractions(grid), _point_fractions(u), _point_fractions(v), fail))
    chord_segments.reset = lambda: None
    chord_segments.cache_sizes = lambda: {"grid_entries": 0,
                                         "point_entries": 0,
                                         "chord_entries": 0}
    return chord_segments


class CachedFractionChord:
    """Per-validation-job reuse of immutable numeric coordinate values."""

    def __init__(self, fail=_default_fail, symmetric=False):
        self.fail = fail
        self.symmetric = symmetric
        self.grids = {}
        self.points = {}
        self.chords = {}

    def __call__(self, grid, u, v):
        raw_grid = _raw_grid_key(grid)
        spec = self.grids.get(raw_grid)
        if spec is None:
            spec = _grid_fractions(grid)
            self.grids[raw_grid] = spec
        endpoints = []
        raw_endpoints = []
        for node in (u, v):
            raw = (node["x"], node["y"])
            raw_endpoints.append(raw)
            point = self.points.get(raw)
            if point is None:
                point = _point_fractions(node)
                self.points[raw] = point
            endpoints.append(point)
        first, second = endpoints
        if not self.symmetric:
            return _serialize(_exact_segments(spec, first, second, self.fail))

        # Reversed roads share exact chord geometry. Preserve direction and
        # transform exact rational endpoints before any binary64 rounding.
        reverse = first > second
        left, right = (second, first) if reverse else (first, second)
        # Finite int/float tuple equality is equality of represented numeric
        # values, and equal values convert to equal Fractions. Hash raw values
        # rather than repeatedly hashing potentially large rational objects.
        raw_left, raw_right = (raw_endpoints[1], raw_endpoints[0]) if reverse else raw_endpoints
        key = (raw_grid, raw_left, raw_right)
        exact = self.chords.get(key)
        if exact is None:
            exact = _exact_segments(spec, left, right, self.fail)
            self.chords[key] = exact
        if reverse:
            exact = tuple((cell, ONE - b, ONE - a)
                          for cell, a, b in reversed(exact))
        return _serialize(exact)

    def cache_sizes(self):
        return {"grid_entries": len(self.grids),
                "point_entries": len(self.points),
                "chord_entries": len(self.chords)}

    def reset(self):
        self.grids.clear()
        self.points.clear()
        self.chords.clear()


class CellShortcutChord(CachedFractionChord):
    """Exact convex-cell shortcut with full-value endpoint-cell keys.

    Unsupported low-level inputs use the clipped exact path. No endpoint cell
    declaration supplied by the caller is trusted.
    """

    def __init__(self, fail=_default_fail):
        super().__init__(fail)
        self.cells = {}
        self.shortcut_hits = 0
        self.fallback_calls = 0

    def __call__(self, grid, u, v):
        values = (grid["x0"], grid["y0"], grid["resolution"],
                  u["x"], u["y"], v["x"], v["y"])
        try:
            eligible = (all(type(value) in (int, float) and math.isfinite(value)
                            for value in values)
                        and type(grid["width"]) is int and grid["width"] > 0
                        and type(grid["height"]) is int and grid["height"] > 0
                        and grid["resolution"] > 0)
        except OverflowError:
            eligible = False
        if not eligible:
            self.fallback_calls += 1
            return super().__call__(grid, u, v)

        raw_grid = _raw_grid_key(grid)
        spec = self.grids.get(raw_grid)
        if spec is None:
            spec = _grid_fractions(grid)
            self.grids[raw_grid] = spec
        x0, y0, resolution, width, height = spec
        endpoint_cells = []
        absent = object()
        for node in (u, v):
            raw_point = (node["x"], node["y"])
            cell_key = (raw_grid, raw_point)
            cell = self.cells.get(cell_key, absent)
            if cell is absent:
                point = self.points.get(raw_point)
                if point is None:
                    point = _point_fractions(node)
                    self.points[raw_point] = point
                col = math.floor((point[0] - x0) / resolution)
                row = math.floor((point[1] - y0) / resolution)
                cell = row * width + col if 0 <= col < width and 0 <= row < height else None
                self.cells[cell_key] = cell
            endpoint_cells.append(cell)
        if endpoint_cells[0] is not None and endpoint_cells[0] == endpoint_cells[1]:
            self.shortcut_hits += 1
            return [{"cell": endpoint_cells[0], "start": 0.0, "end": 1.0}]
        self.fallback_calls += 1
        return super().__call__(grid, u, v)

    def cache_sizes(self):
        result = super().cache_sizes()
        result["cell_entries"] = len(self.cells)
        return result

    def reset(self):
        super().reset()
        self.cells.clear()
        self.shortcut_hits = 0
        self.fallback_calls = 0


def make_variants(validation_module):
    """Fresh per-job alternatives; pass validation.fail for identical errors.

    Parent harness may replace validation_module.chord_segments inside its own
    isolated process. Never install these in the preserved reference directory.
    """
    return {
        "clip": make_range_clipped(validation_module.fail),
        "clip_context": CachedFractionChord(validation_module.fail),
        "clip_context_chord": CachedFractionChord(validation_module.fail, True),
        "clip_cell_shortcut": CellShortcutChord(validation_module.fail),
    }
