"""Explicit full-graph-bound exact static occupancy templates.

This cache contains no source, hazard, request, exposure or search-result state.
Templates own immutable fractions; each query receives fresh occupancy dicts.
"""
from fractions import Fraction
import sys
from .prepared import PreparedGraph


class SearchGeometryCache:
    __slots__ = ("_prepared", "_nodes", "_edges", "_templates", "_hits", "_misses", "_materializations")

    def __init__(self, raw_graph):
        self._prepared = PreparedGraph(raw_graph)
        graph = self._prepared.snapshot()
        self._nodes = {n["id"]: n for n in graph["nodes"]}
        self._edges = {e["id"]: e for e in graph["edges"]}
        self._templates = {}
        self._hits = self._misses = self._materializations = 0

    @property
    def fingerprint(self):
        return self._prepared.fingerprint

    def snapshot(self):
        return self._prepared.snapshot()

    def matches(self, graph):
        return self._prepared.matches(graph)

    def occupancies(self, edge_id, start, end, from_fraction=0, to_fraction=1):
        """Original cut order and point closures, exact affine time translation.

        Caller must bind the full graph with matches before a search. A miss is
        installed only after the entire original exact template is constructed.
        No mutation of returned dicts can contaminate owned templates.
        """
        from .core import edge_occupancies
        key = (edge_id, Fraction(from_fraction), Fraction(to_fraction))
        if key in self._templates:
            self._hits += 1
            template = self._templates[key]
        else:
            self._misses += 1
            raw = edge_occupancies(self._edges[edge_id], 0, 1, key[1], key[2],
                                   self._prepared.snapshot(), self._nodes)
            template = tuple((x["cell"], x["start"], x["end"]) for x in raw)
            self._templates[key] = template
        self._materializations += 1
        start, end = Fraction(start), Fraction(end)
        return [{"cell": cell, "start": start + (end-start)*lo,
                 "end": start + (end-start)*hi} for cell, lo, hi in template]

    def cache_info(self):
        return {"fingerprint": self.fingerprint, "entries": len(self._templates),
                "hits": self._hits, "misses": self._misses,
                "materializations": self._materializations, "evictions": 0,
                "encoded_graph_bytes": self._prepared.encoded_size_bytes,
                "shallow_template_bytes": sys.getsizeof(self._templates) +
                    sum(sys.getsizeof(k)+sys.getsizeof(v) for k,v in self._templates.items()),
                "memory_scope": "serialized graph plus shallow template containers; excludes nested Python/Fraction storage; process RSS reported separately"}
