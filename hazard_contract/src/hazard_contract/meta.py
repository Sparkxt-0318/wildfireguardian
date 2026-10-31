"""``meta.json`` schema of a hazard_contract v1 scenario set."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

CONTRACT_VERSION = "1.0"
SUPPORTED_MAJOR = 1
Source = Literal["model", "packet", "perimeter", "drawn", "synthetic"]


class ContractError(ValueError):
    """A scenario set or query violates hazard_contract."""


class HeatSource(BaseModel):
    """Declared thermal-source parameters of the reference flux model ``sheet_solid_angle_v1``.

    This is the law used by ``wfg_latest`` (``ExpectedHeatFluxModel``): every burning cell is a
    uniformly and isotropically emitting horizontal sheet at ``emission_height_m``, with radiant
    emission (kW/m^2)

        q_rad = radiative_fraction * transmissivity * fuel_load_kg_m2 * consumed_fraction
                * heat_content_kj_kg / duration_s

    where ``duration_s`` is ``burn_duration_s`` (``scalar`` policy) or the cell's own
    ``extinguish_s - ignite_s`` when finite and positive (``interval`` policy). A horizontal
    receiver at ``receiver_height_m`` gets ``q_rad * Omega / (4 pi)`` from each burning cell,
    where ``Omega`` is the cell's solid angle seen from the receiver; contributions add.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    fuel_load_kg_m2: float = Field(gt=0, description="c: fuel load per unit area (kg/m^2)")
    consumed_fraction: float = Field(default=1.0, gt=0, le=1, description="f: fraction of the load consumed while flaming")
    heat_content_kj_kg: float = Field(gt=0, description="H: fuel heat content (kJ/kg)")
    radiative_fraction: float = Field(gt=0, le=1, description="chi: radiated fraction of the heat release")
    transmissivity: float = Field(default=1.0, gt=0, le=1, description="atmospheric transmissivity; 1 = none (conservative)")
    burn_duration_policy: Literal["scalar", "interval"] = "scalar"
    burn_duration_s: float = Field(gt=0, description="T: whole-cell burning duration (s); scalar policy and fallback")
    emission_height_m: float = Field(default=5.0, description="height of the emitting sheet (m)")
    receiver_height_m: float = Field(default=0.0, description="height of the receiver (m)")
    flux_model: Literal["sheet_solid_angle_v1"] = "sheet_solid_angle_v1"
    note: str = ""

    @model_validator(mode="after")
    def _heights(self) -> "HeatSource":
        if not self.emission_height_m > self.receiver_height_m:
            raise ValueError("emission_height_m must exceed receiver_height_m")
        return self

    @property
    def height_gap_m(self) -> float:
        return self.emission_height_m - self.receiver_height_m

    def emission_kw_m2(self, duration_s):
        """Radiant emission q_rad (kW/m^2) of a cell burning for ``duration_s``."""
        return (self.radiative_fraction * self.transmissivity * self.fuel_load_kg_m2 * self.consumed_fraction
                * self.heat_content_kj_kg / duration_s)


class ScenarioMeta(BaseModel):
    """Everything a consumer needs to interpret ``members.npz``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = CONTRACT_VERSION
    crs_epsg: int
    transform: tuple[float, float, float, float, float, float] = Field(
        description="rasterio-order affine (a, b, c, d, e, f): x = a*col + c, y = e*row + f; north-up (b = d = 0)")
    height: int = Field(gt=0)
    width: int = Field(gt=0)
    K: int = Field(gt=0, description="number of scenario members")
    issue_time_utc: datetime = Field(description="time origin: all *_s arrays are seconds after this instant")
    horizon_s: float = Field(gt=0, description="the scenario says nothing about t > horizon_s")
    source: Source
    synthetic: bool = Field(description="True if any synthetic data went into this set")
    model_version: str
    weather_source: str
    heat_source: HeatSource
    provenance: dict[str, Any] = Field(default_factory=dict, description="commit, seed, config, host")
    extra: dict[str, Any] = Field(default_factory=dict, description="producer-specific, not interpreted by consumers")

    @field_validator("contract_version")
    @classmethod
    def _known_major(cls, v: str) -> str:
        try:
            major = int(str(v).split(".")[0])
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"bad contract_version {v!r}") from exc
        if major != SUPPORTED_MAJOR:
            raise ValueError(f"contract_version {v} is not readable by hazard_contract {CONTRACT_VERSION}")
        return v

    @field_validator("issue_time_utc")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("issue_time_utc must be timezone-aware (UTC)")
        return v.astimezone(timezone.utc)

    @field_serializer("issue_time_utc")
    def _ser_time(self, v: datetime) -> str:
        return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @model_validator(mode="after")
    def _consistent(self) -> "ScenarioMeta":
        a, b, _c, d, e, _f = self.transform
        if b != 0 or d != 0:
            raise ValueError("hazard_contract v1 supports north-up grids only (transform b == d == 0)")
        if a == 0 or e == 0:
            raise ValueError("degenerate transform (zero pixel size)")
        if self.source == "synthetic" and not self.synthetic:
            raise ValueError("source='synthetic' requires synthetic=True")
        return self
