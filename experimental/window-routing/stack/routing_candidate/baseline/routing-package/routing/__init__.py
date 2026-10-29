"""Fixture-ready WildfireGuardian road thermal routing adapter."""

from .core import solve
from .validation import (
    ValidationError,
    validate_graph,
    validate_hazard,
    validate_request,
)
from .prepared import PreparedGraph, prepare_graph
