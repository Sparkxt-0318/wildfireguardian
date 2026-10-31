"""SYNTHETIC residents and fleet for real facilities (documented in ``docs/ASSUMPTIONS.md``).

* Residents per facility: the CMS average number of residents per day (a real count) when given,
  else ``occupancy x certified beds``; split into mobility classes by the SYNTHETIC generator's
  skilled-nursing mix with largest-remainder rounding (deterministic). Classes are the space a
  resident needs in the vehicle: seat, wheelchair slot, stretcher.
* Boarding and unloading times per resident: the SYNTHETIC generator's base values.
* Fleet: one facility-owned 8-seat van with 2 wheelchair slots at each facility (ready at once),
  plus a mutual-aid pool staged at the safe-side staging node: 40-seat buses (2 wheelchair slots)
  and ambulances (1 stretcher, 1 seat), sized from the resident totals, arriving after a delay.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..generators.synthetic import BOARDING_S, FACILITY_MIX, UNLOADING_S, VEHICLE_TYPES
from ..schema import ClassCounts, ClassDurations, Vehicle
from .cms import CmsFacility

MOBILITY_MIX = FACILITY_MIX["snf"]
OCCUPANCY = 0.75


def split_by_mix(n: int, mix=MOBILITY_MIX) -> tuple[int, int, int]:
    """Largest-remainder split of ``n`` residents by ``mix`` (ties: class order)."""
    raw = [n * p / sum(mix) for p in mix]
    base = [math.floor(r) for r in raw]
    rest = n - sum(base)
    for i in sorted(range(3), key=lambda i: (-(raw[i] - base[i]), i))[:rest]:
        base[i] += 1
    return base[0], base[1], base[2]


def residents_for(f: CmsFacility, *, occupancy: float = OCCUPANCY, mix=MOBILITY_MIX) -> tuple[ClassCounts, str]:
    if f.avg_residents is not None and f.avg_residents > 0:
        n, src = int(round(f.avg_residents)), "CMS average number of residents per day"
    elif f.certified_beds:
        n, src = int(round(occupancy * f.certified_beds)), f"occupancy {occupancy} x CMS certified beds"
    else:
        n, src = 0, "no census and no bed count in the CMS file"
    return ClassCounts.of(split_by_mix(n, mix)), src


def boarding_times() -> ClassDurations:
    return ClassDurations(ambulatory=BOARDING_S[0], wheelchair=BOARDING_S[1], bedbound=BOARDING_S[2])


def unloading_times() -> ClassDurations:
    return ClassDurations(ambulatory=UNLOADING_S[0], wheelchair=UNLOADING_S[1], bedbound=UNLOADING_S[2])


@dataclass(frozen=True)
class FleetRule:
    van_per_facility: int = 1
    ambulatory_per_bus: int = 80          # a bus is expected to make about two trips
    bedbound_per_ambulance: int = 4
    mutual_aid_delay_s: float = 1800.0
    shift_limit_s: float = 8 * 3600.0


def synthetic_fleet(facility_nodes: list[str], totals: tuple[int, int, int], staging_node: str,
                    rule: FleetRule = FleetRule()) -> list[Vehicle]:
    out: list[Vehicle] = []

    def add(kind: str, depot: str, start: float) -> None:
        seats, wc, st = VEHICLE_TYPES[kind]
        out.append(Vehicle(id=f"V{len(out) + 1:03d}", depot=depot, start_s=start, seats=seats, wheelchair_slots=wc,
                           stretcher_slots=st, shift_limit_s=rule.shift_limit_s, kind=f"{kind} (SYNTHETIC)"))

    for node in facility_nodes:
        for _ in range(rule.van_per_facility):
            add("van", node, 0.0)
    for _ in range(math.ceil(totals[0] / rule.ambulatory_per_bus)):
        add("bus", staging_node, rule.mutual_aid_delay_s)
    for _ in range(math.ceil(totals[2] / rule.bedbound_per_ambulance)):
        add("ambulance", staging_node, rule.mutual_aid_delay_s)
    return out
