"""Graph preparation shared by both integrated routing workers (reference RDA_BASE and candidate RDA_CAND).

Integration routing_preparation_integration_20261014_v1. Both workers call prepare_graph() at the exact point where
the frozen workers constructed PreparedGraph(graph), inside each request's complete deadline. Nothing request-,
hazard-, member-, clock-, limit- or exposure-dependent is prepared, cached or reused here.

COLD_FAST (default; the only mode of the primary comparison): the ORIGINAL constructor
routing.prepared.PreparedGraph(graph) runs full graph admission. Its validate_graph uses the independently reviewed
exact same-cell shortcut with clipped-boundary fallback (routing/admission_geometry.py, clip_cell_shortcut).

AUTHENTICATED_ARTIFACT (opt-in only, WFG_OWNER_PREPARED_CACHE=<owner-private directory>): the reviewed
routing.prepared_reuse.ArtifactPreparedStore. An artifact is used only if its HMAC-authenticated header and its full
canonical graph bytes match, under the source identity of every routing-package module (admission_geometry.py,
validation.py, prepared.py, core.py, ...) and prepared_reuse.py. A source or graph change selects a different
artifact (miss, full cold admission); a corrupted or unauthenticated artifact raises CacheAuthorityError, which
fails the request (never a silent rebuild or fallback).

Never consulted: the FUP1 prepared_restore certificate (job fields prepared_certificate*), whose binding covers only
validation.py and prepared.py and therefore not admission_geometry.py.

A queue may pin preparation_mode (declared mode), preparation_mode_sha256 (this file) and preparation_source_sha256
(prepared_reuse.source_identity()); any mismatch fails the request before preparation starts.
"""
import hashlib
import os
import pathlib
import platform
import sys
import time

SCHEMA = 'wfg.integrated-preparation-receipt/1'
ENV = 'WFG_OWNER_PREPARED_CACHE'
GEOMETRY_METHOD = 'clip_cell_shortcut'


def _sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def prepare_graph(graph, job, state):
    """Return the PreparedGraph; record the preparation receipt progressively in state['preparation']."""
    t0 = time.perf_counter()
    root = os.environ.get(ENV)
    mode = 'COLD_FAST' if root is None else 'AUTHENTICATED_ARTIFACT'
    rec = {'schema': SCHEMA, 'status': 'STARTED', 'mode': mode, 'declared_mode': job.get('preparation_mode'),
           'geometry_method': GEOMETRY_METHOD, 'fup1_certificate_consulted': False,
           'interpreter': {'version': sys.version, 'executable': sys.executable,
                           'implementation': sys.implementation.name, 'platform': sys.platform,
                           'machine': platform.machine()}}
    state['preparation'] = rec
    module_sha256 = _sha(__file__)
    rec['preparation_mode_sha256'] = module_sha256
    if job.get('preparation_mode_sha256') not in (None, module_sha256):
        raise ValueError('PREPARATION_MODE_MODULE_HASH_MISMATCH')
    if rec['declared_mode'] is not None and rec['declared_mode'] != mode:
        raise ValueError('PREPARATION_MODE_NOT_AS_DECLARED:' + mode)
    from routing import prepared_reuse
    from routing.prepared import PreparedGraph
    source = prepared_reuse.source_identity()
    rec['preparation_source_sha256'] = source
    if job.get('preparation_source_sha256') not in (None, source):
        raise ValueError('PREPARATION_SOURCE_IDENTITY_MISMATCH')
    rec['identity_checks_s'] = time.perf_counter() - t0
    t = time.perf_counter()
    if root is None:
        pg = PreparedGraph(graph)
        rec.update(cache_hit=False, admission_reused=False)
    else:
        pg, receipt = prepared_reuse.ArtifactPreparedStore(root, expected_source_sha256=source).get(graph)
        rec.update(cache_hit=receipt.cache_hit, admission_reused=receipt.admission_reused,
                   store_schema=receipt.schema, store_source_sha256=receipt.source_sha256,
                   store_lookup_s=receipt.lookup_s, payload_bytes=receipt.payload_bytes)
    rec.update(status='PREPARED', prepare_s=time.perf_counter() - t, graph_fingerprint=pg.fingerprint,
               graph_revision=graph.get('revision') if isinstance(graph, dict) else None,
               total_s=time.perf_counter() - t0)
    return pg
