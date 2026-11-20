"""Vehicle profiles (DESIGN.md section 8). Every limit is a PLACEHOLDER for a fire service to set.

Units: lengths in m, speed in m/s, dose in TDU = (kW/m2)^(4/3) s, intake air limit in degrees C.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml

VEHICLES_YAML = Path(__file__).with_name("vehicles.yaml")
PLACEHOLDER_NOTE = "PLACEHOLDER limits: to be set by the fire service"
REQUIRED = ("length_m", "width_m", "height_m", "sensor_height_m", "max_safe_speed_m_s", "dose_limit_tdu",
            "intake_air_limit_c", "has_water", "placeholder")
_RANGES = {"length_m": (1.0, 30.0), "width_m": (0.5, 5.0), "height_m": (0.5, 6.0), "sensor_height_m": (0.3, 7.0),
           "max_safe_speed_m_s": (0.1, 40.0), "dose_limit_tdu": (0.0, 1e6), "intake_air_limit_c": (-40.0, 500.0)}


@dataclass(frozen=True)
class Vehicle:
    name: str
    label: str
    length_m: float
    width_m: float
    height_m: float
    sensor_height_m: float
    max_safe_speed_m_s: float
    dose_limit_tdu: float
    intake_air_limit_c: float
    has_water: bool
    placeholder: bool = True

    def __post_init__(self) -> None:
        for k, (lo, hi) in _RANGES.items():
            v = getattr(self, k)
            if not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    and lo <= v <= hi):
                raise ValueError("vehicle %s: %s = %r outside [%g, %g]" % (self.name, k, v, lo, hi))
        if self.dose_limit_tdu <= 0:
            raise ValueError("vehicle %s: dose_limit_tdu must be > 0" % self.name)
        if not isinstance(self.has_water, bool) or not isinstance(self.placeholder, bool):
            raise ValueError("vehicle %s: has_water and placeholder must be booleans" % self.name)

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.placeholder:
            d["placeholder_note"] = PLACEHOLDER_NOTE
        return d


def from_mapping(name: str, m: dict) -> Vehicle:
    missing = [k for k in REQUIRED if k not in m]
    if missing:
        raise ValueError("vehicle %s missing %s" % (name, ", ".join(missing)))
    return Vehicle(name=name, label=str(m.get("label", name)),
                   **{k: (m[k] if k in ("has_water", "placeholder") else float(m[k])) for k in REQUIRED})


def load_vehicles(path: Optional[Path] = None) -> Dict[str, Vehicle]:
    with open(path or VEHICLES_YAML, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {name: from_mapping(name, m) for name, m in data.items()}


def get_vehicle(name: str, path: Optional[Path] = None) -> Vehicle:
    v = load_vehicles(path)
    if name not in v:
        raise KeyError("unknown vehicle %r (have %s)" % (name, ", ".join(sorted(v))))
    return v[name]
