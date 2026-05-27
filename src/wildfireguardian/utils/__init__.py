"""Shared utilities: logging, unit conversions, constants.

This module currently exposes only :data:`units` — a tiny table of
conversion factors used by the spread model. It is imported eagerly because
it has no heavy dependencies.
"""

from __future__ import annotations

from . import units

__all__ = ["units"]
