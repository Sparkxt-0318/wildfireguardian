"""Expected incident radiant heat from active-burning probability rasters."""

from .model import (
    AffineGrid,
    CombustionParameters,
    ExpectedHeatFluxModel,
    HeatFluxResult,
    integrate_heat_flux,
)
from .ecology import EcologicalFuelMaps, FCCS_TONS_PER_ACRE_TO_KG_M2
from .temporal import BurningOccupancy, ignition_to_active_probability, initial_active_occupancy
from .pipeline import IntegratedHeatPrediction, WildfireHeatModel

__all__ = [
    "AffineGrid",
    "CombustionParameters",
    "ExpectedHeatFluxModel",
    "HeatFluxResult",
    "integrate_heat_flux",
    "EcologicalFuelMaps",
    "FCCS_TONS_PER_ACRE_TO_KG_M2",
    "BurningOccupancy",
    "ignition_to_active_probability",
    "initial_active_occupancy",
    "IntegratedHeatPrediction",
    "WildfireHeatModel",
]

__version__ = "0.2.0"
