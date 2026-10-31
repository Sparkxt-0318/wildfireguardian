"""Adapters that turn other hazard descriptions into hazard_contract v1 scenario sets."""
from .drawn import from_drawn_zones
from .perimeters import from_perimeters
from .synthetic import synthetic
from .wfg_packet import from_wfg_packet

__all__ = ["from_drawn_zones", "from_perimeters", "from_wfg_packet", "synthetic"]
