"""Exact model-conditional routing; no physical-safety guarantee."""
from ._engine.core import solve
from ._engine.independent import check_route
from ._engine.prepared import PreparedGraph, prepare_graph
from ._engine.validation import ValidationError, validate_graph, validate_hazard, validate_request
from ._engine.fixture import example
from .runtime import ReleaseRuntime, BackendError, BackendTimeout

__version__ = "0.1.0"
__all__ = ["solve", "check_route", "prepare_graph", "PreparedGraph", "ValidationError",
           "validate_graph", "validate_hazard", "validate_request", "example",
           "ReleaseRuntime", "BackendError", "BackendTimeout"]
