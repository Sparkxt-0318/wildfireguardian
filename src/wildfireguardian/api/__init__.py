"""HTTP transport over the PHASE-19 service layer.

Round-3 PHASE 22. Four endpoints, a JSON offline gate, and static file serving
for the vendored fonts. Nothing here decides a number: every parameter that
moves a result comes from ``config/default.yaml`` through
``service.RoutingParams.from_config`` and is not settable over HTTP.

⚠ The service package still imports no web framework, and a test still asserts
that. The dependency runs one way — api -> service — so the service layer stays
testable, and callable, without a server.
"""

from __future__ import annotations

from .app import IgnitionBody, PRELOAD_REGIONS, create_app
from .guard import ExternalReferenceError, assert_offline, find_external_refs

__all__ = ["ExternalReferenceError", "IgnitionBody", "PRELOAD_REGIONS",
           "assert_offline", "create_app", "find_external_refs"]
