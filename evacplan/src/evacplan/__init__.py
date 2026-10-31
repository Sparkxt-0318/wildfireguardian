"""evacplan — Track C: care-facility wildfire evacuation dispatch planner.

Milestone C0-oracle: the Problem v0 schema and JSON I/O (:mod:`evacplan.schema`), the hazard-free
validator (:mod:`evacplan.validate`) and THE feasibility oracle (:mod:`evacplan.oracle`), the only
code that declares ``checked`` / ``model_no_route`` / ``unresolved``. Hazards come in only through
``hazard_contract``.
"""
from .oracle import (
    ORACLE_VERSION, ItineraryResult, LegResult, Oracle, OracleInputError, PlanResult, RelaxedContactCheck,
    RelaxedItinerary, RelaxedLeg, State, TripResult, check_itinerary, check_plan, contact_records, state_rank,
)
from .schema import (
    CLASSES, Board, Budgets, ClassCounts, ClassDurations, Drive, Edge, Facility, HazardRef, Instance, InstanceIndex,
    Itinerary, Node, RoadGraph, Shelter, Solution, Unload, Vehicle, Wait, load_instance, load_scenario_set,
    load_solution, save_instance, save_solution, scenario_set_path,
)
from .validate import TIME_TOL_S, Issue, Segment, ValidationReport, validate_solution

__version__ = "0.1.0"

__all__ = [
    "CLASSES", "ORACLE_VERSION", "TIME_TOL_S", "Board", "Budgets", "ClassCounts", "ClassDurations", "Drive", "Edge",
    "Facility", "HazardRef", "Instance", "InstanceIndex", "Issue", "Itinerary", "ItineraryResult", "LegResult", "Node",
    "Oracle", "OracleInputError", "PlanResult", "RelaxedContactCheck", "RelaxedItinerary", "RelaxedLeg", "RoadGraph",
    "Segment", "Shelter", "Solution", "State", "TripResult", "Unload", "ValidationReport", "Vehicle", "Wait",
    "check_itinerary", "check_plan", "contact_records", "load_instance", "load_scenario_set", "load_solution",
    "save_instance", "save_solution", "scenario_set_path", "state_rank", "validate_solution",
]
