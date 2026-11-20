"""Fuel table for the crossing app: residence time, consumed load and heat content per fuel.

Provenance
----------
The FBFM40 (Scott and Burgan 2005, table 7, printed p.18) parameter values below are COPIED from
``forecast/wildfire/heat.py::_FBFM40_PARAMETERS`` (as the design contract asks: copy the values, do not import
``forecast``, which pulls a large package). Columns: name, dry load in short tons/acre for
[dead 1-h, dead 10-h, dead 100-h, live herb, live woody], SAV in ft^-1 for [dead 1-h, live herb, live woody].
For all models dead 10-h SAV = 109 ft^-1 and dead 100-h SAV = 30 ft^-1. 9999 is the source table's placeholder
SAV in classes with zero load (it carries no surface area, so it has no effect).

Physics and stated assumptions (units in brackets)
--------------------------------------------------
* Residence time (Anderson 1969, as forecast/wildfire/heat.py computes it):
  characteristic SAV sigma = sum(load * sav^2) / sum(load * sav)  [ft^-1] (surface-area weighted, Andrews 2018
  3.2.3-3.2.5), t_r [min] = 384 / sigma [ft^-1], so t_r [s] = 384 * 60 / sigma_ft. This is the point-scale
  passing flaming-front residence time; it excludes trailing burning and smouldering. Reproduced values:
  GR1 11.2 s, SH6 20.1 s, TU4 10.4 s (tested against forecast/wildfire/heat.py when importable).
* residence_rel_sigma = 0.30 (relative 1-sigma of t_r) for every catalogue fuel. This is a PLACEHOLDER for the
  scatter of Anderson's relation for a real, heterogeneous fuel bed; it is not a fitted value.
* Consumed load by default = dead 1-h + 50 % of live herbaceous load [kg/m2] (tons/acre * 0.224170231).
  This is a stated flaming-front scenario (fine fuel burns in the front, half the herb is assumed cured);
  10-h / 100-h / live woody fuel is assumed NOT consumed in the passing front. It is not a consumption model.
* Heat content (Scott and Burgan nominal, as forecast/wildfire/heat_parameters.py): 8000 Btu/lb = 18608 kJ/kg
  for every model except GR6 (code 106), 9000 Btu/lb = 20934 kJ/kg; no moisture correction.
* C064_GRASS: the FDS case used by research/kcf-heat (SAV 9770 1/m -> t_r = 75590.55/9770 = 7.74 s,
  0.28 kg/m2, 17425 kJ/kg).
* DEFAULT: the wfg_latest POLICY packet (integration/src/wfg_latest/contract.py): t_r 11.52 s,
  10 kg/m2 x 0.1 consumed = 1.0 kg/m2, 18608 kJ/kg.

All of these are reference scenarios. None is a measurement of the fuel in front of the vehicle.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Dict, Mapping, Optional

TONS_PER_ACRE_TO_KG_M2 = 907.18474 / 4046.8564224          # 0.224170231 (short ton, international acre)
BTU_PER_LB_TO_KJ_PER_KG = 2.326                              # NIST SP811 Btu_IT/lb -> kJ/kg
SAV_RESIDENCE_COEFFICIENT_S_PER_M = 384.0 * 60.0 / 0.3048    # t_r[s] = this / sigma[1/m]
DEAD_10H_SAV_FT = 109.0
DEAD_100H_SAV_FT = 30.0
DEFAULT_RESIDENCE_REL_SIGMA = 0.30                           # PLACEHOLDER (see module docstring)
DEFAULT_LIVE_HERB_FRACTION = 0.5                             # consumed share of live herb (stated scenario)

# Copied from forecast/wildfire/heat.py::_FBFM40_PARAMETERS (Scott and Burgan 2005 table 7, p.18).
FBFM40_PARAMETERS = MappingProxyType({
    101: ("GR1", (0.10, 0.00, 0.00, 0.30, 0.00), (2200, 2000, 9999)),
    102: ("GR2", (0.10, 0.00, 0.00, 1.00, 0.00), (2000, 1800, 9999)),
    103: ("GR3", (0.10, 0.40, 0.00, 1.50, 0.00), (1500, 1300, 9999)),
    104: ("GR4", (0.25, 0.00, 0.00, 1.90, 0.00), (2000, 1800, 9999)),
    105: ("GR5", (0.40, 0.00, 0.00, 2.50, 0.00), (1800, 1600, 9999)),
    106: ("GR6", (0.10, 0.00, 0.00, 3.40, 0.00), (2200, 2000, 9999)),
    107: ("GR7", (1.00, 0.00, 0.00, 5.40, 0.00), (2000, 1800, 9999)),
    108: ("GR8", (0.50, 1.00, 0.00, 7.30, 0.00), (1500, 1300, 9999)),
    109: ("GR9", (1.00, 1.00, 0.00, 9.00, 0.00), (1800, 1600, 9999)),
    121: ("GS1", (0.20, 0.00, 0.00, 0.50, 0.65), (2000, 1800, 1800)),
    122: ("GS2", (0.50, 0.50, 0.00, 0.60, 1.00), (2000, 1800, 1800)),
    123: ("GS3", (0.30, 0.25, 0.00, 1.45, 1.25), (1800, 1600, 1600)),
    124: ("GS4", (1.90, 0.30, 0.10, 3.40, 7.10), (1800, 1600, 1600)),
    141: ("SH1", (0.25, 0.25, 0.00, 0.15, 1.30), (2000, 1800, 1600)),
    142: ("SH2", (1.35, 2.40, 0.75, 0.00, 3.85), (2000, 9999, 1600)),
    143: ("SH3", (0.45, 3.00, 0.00, 0.00, 6.20), (1600, 9999, 1400)),
    144: ("SH4", (0.85, 1.15, 0.20, 0.00, 2.55), (2000, 1800, 1600)),
    145: ("SH5", (3.60, 2.10, 0.00, 0.00, 2.90), (750, 9999, 1600)),
    146: ("SH6", (2.90, 1.45, 0.00, 0.00, 1.40), (750, 9999, 1600)),
    147: ("SH7", (3.50, 5.30, 2.20, 0.00, 3.40), (750, 9999, 1600)),
    148: ("SH8", (2.05, 3.40, 0.85, 0.00, 4.35), (750, 9999, 1600)),
    149: ("SH9", (4.50, 2.45, 0.00, 1.55, 7.00), (750, 1800, 1500)),
    161: ("TU1", (0.20, 0.90, 1.50, 0.20, 0.90), (2000, 1800, 1600)),
    162: ("TU2", (0.95, 1.80, 1.25, 0.00, 0.20), (2000, 9999, 1600)),
    163: ("TU3", (1.10, 0.15, 0.25, 0.65, 1.10), (1800, 1600, 1400)),
    164: ("TU4", (4.50, 0.00, 0.00, 0.00, 2.00), (2300, 9999, 2000)),
    165: ("TU5", (4.00, 4.00, 3.00, 0.00, 3.00), (1500, 9999, 750)),
    181: ("TL1", (1.00, 2.20, 3.60, 0.00, 0.00), (2000, 9999, 9999)),
    182: ("TL2", (1.40, 2.30, 2.20, 0.00, 0.00), (2000, 9999, 9999)),
    183: ("TL3", (0.50, 2.20, 2.80, 0.00, 0.00), (2000, 9999, 9999)),
    184: ("TL4", (0.50, 1.50, 4.20, 0.00, 0.00), (2000, 9999, 9999)),
    185: ("TL5", (1.15, 2.50, 4.40, 0.00, 0.00), (2000, 9999, 1600)),
    186: ("TL6", (2.40, 1.20, 1.20, 0.00, 0.00), (2000, 9999, 9999)),
    187: ("TL7", (0.30, 1.40, 8.10, 0.00, 0.00), (2000, 9999, 9999)),
    188: ("TL8", (5.80, 1.40, 1.10, 0.00, 0.00), (1800, 9999, 9999)),
    189: ("TL9", (6.65, 3.30, 4.15, 0.00, 0.00), (1800, 9999, 1600)),
    201: ("SB1", (1.50, 3.00, 11.00, 0.00, 0.00), (2000, 9999, 9999)),
    202: ("SB2", (4.50, 4.25, 4.00, 0.00, 0.00), (2000, 9999, 9999)),
    203: ("SB3", (5.50, 2.75, 3.00, 0.00, 0.00), (2000, 9999, 9999)),
    204: ("SB4", (5.25, 3.50, 5.25, 0.00, 0.00), (2000, 9999, 9999)),
})


@dataclass(frozen=True)
class Fuel:
    """One fuel scenario.

    code: short identifier ("GR1", "C064_GRASS", "DEFAULT", or a custom code).
    residence_s: flaming residence time t_r [s]; depth of the flaming zone D = R * t_r.
    residence_rel_sigma: relative 1-sigma of t_r (dimensionless; placeholder unless calibrated).
    consumed_load_kg_m2: dry mass consumed in the flaming front w [kg/m2].
    heat_kj_kg: heat content H [kJ/kg]; Byram intensity I = H * w * R [kW/m].
    """
    code: str
    name: str
    residence_s: float
    residence_rel_sigma: float
    consumed_load_kg_m2: float
    heat_kj_kg: float
    fbfm40: Optional[int] = None
    source: str = ""

    def __post_init__(self) -> None:
        for field_name in ("residence_s", "consumed_load_kg_m2", "heat_kj_kg"):
            v = getattr(self, field_name)
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
                raise ValueError("%s must be finite and > 0, got %r" % (field_name, v))
        s = self.residence_rel_sigma
        if not (isinstance(s, (int, float)) and math.isfinite(s) and s >= 0):
            raise ValueError("residence_rel_sigma must be finite and >= 0, got %r" % (s,))

    @property
    def energy_kj_m2(self) -> float:
        """Heat released per ground area in the flaming front, H * w [kJ/m2]."""
        return self.heat_kj_kg * self.consumed_load_kg_m2

    def to_dict(self) -> dict:
        d = asdict(self)
        d["energy_kj_m2"] = self.energy_kj_m2
        return d


def characteristic_sav_ft(loads, three_sav) -> float:
    """Surface-area-weighted characteristic SAV [ft^-1], as forecast/wildfire/heat.py computes it."""
    particle = (float(three_sav[0]), DEAD_10H_SAV_FT, DEAD_100H_SAV_FT, float(three_sav[1]), float(three_sav[2]))
    surface = [float(w) * s for w, s in zip(loads, particle)]
    total = sum(surface)
    if total <= 0:
        raise ValueError("fuel model has no surface area")
    return sum(a * s for a, s in zip(surface, particle)) / total


def residence_from_sav_ft(sigma_ft: float) -> float:
    """Anderson (1969): t_r [s] = 384 * 60 / sigma [ft^-1]."""
    return 384.0 * 60.0 / sigma_ft


def residence_from_sav_m(sigma_m: float) -> float:
    """Anderson (1969) with sigma in 1/m: t_r [s] = (384 * 60 / 0.3048) / sigma [1/m]."""
    return SAV_RESIDENCE_COEFFICIENT_S_PER_M / sigma_m


def heat_content_kj_kg(code: int) -> float:
    """Nominal Scott and Burgan heat content: 9000 Btu/lb for GR6 (106), else 8000 Btu/lb [kJ/kg]."""
    return (9000.0 if int(code) == 106 else 8000.0) * BTU_PER_LB_TO_KJ_PER_KG


def consumed_load_kg_m2(loads, live_herb_fraction: float = DEFAULT_LIVE_HERB_FRACTION) -> float:
    """Default consumed load: dead 1-h + live_herb_fraction * live herb [kg/m2] (stated scenario)."""
    return (float(loads[0]) + live_herb_fraction * float(loads[3])) * TONS_PER_ACRE_TO_KG_M2


def fbfm40_fuel(code: int, live_herb_fraction: float = DEFAULT_LIVE_HERB_FRACTION,
                residence_rel_sigma: float = DEFAULT_RESIDENCE_REL_SIGMA) -> Fuel:
    """Build the Fuel for an FBFM40 numeric code from the copied table."""
    name, loads, three_sav = FBFM40_PARAMETERS[int(code)]
    sigma = characteristic_sav_ft(loads, three_sav)
    return Fuel(code=name, name="FBFM40 %s (%d)" % (name, int(code)),
                residence_s=residence_from_sav_ft(sigma), residence_rel_sigma=residence_rel_sigma,
                consumed_load_kg_m2=consumed_load_kg_m2(loads, live_herb_fraction),
                heat_kj_kg=heat_content_kj_kg(code), fbfm40=int(code),
                source="Scott and Burgan 2005 table 7 via forecast/wildfire/heat.py; consumed = 1h + "
                       "%.0f%% live herb" % (100 * live_herb_fraction))


C064_GRASS = Fuel(code="C064_GRASS", name="FDS case C064 grass (research/kcf-heat)",
                  residence_s=residence_from_sav_m(9770.0), residence_rel_sigma=DEFAULT_RESIDENCE_REL_SIGMA,
                  consumed_load_kg_m2=0.28, heat_kj_kg=17425.0, fbfm40=None,
                  source="research/kcf-heat FDS case C064: SAV 9770 1/m, 0.28 kg/m2, 17425 kJ/kg")

DEFAULT = Fuel(code="DEFAULT", name="wfg_latest POLICY packet default",
               residence_s=11.52, residence_rel_sigma=DEFAULT_RESIDENCE_REL_SIGMA,
               consumed_load_kg_m2=1.0, heat_kj_kg=18608.0, fbfm40=None,
               source="integration/src/wfg_latest/contract.py POLICY: t_r 11.52 s, 10 kg/m2 x 0.1, 18608 kJ/kg")


def _build() -> Dict[str, Fuel]:
    out: Dict[str, Fuel] = {}
    for code in FBFM40_PARAMETERS:
        f = fbfm40_fuel(code)
        out[f.code] = f
    out[C064_GRASS.code] = C064_GRASS
    out[DEFAULT.code] = DEFAULT
    return out


FUELS: Mapping[str, Fuel] = MappingProxyType(_build())
_CUSTOM: Dict[str, Fuel] = {}


def custom_fuel(code: str, residence_s: float, consumed_load_kg_m2: float, heat_kj_kg: float = 18608.0,
                residence_rel_sigma: float = DEFAULT_RESIDENCE_REL_SIGMA, name: str = "",
                register: bool = True) -> Fuel:
    """Create (and by default register) a user-defined fuel scenario. Codes may not shadow catalogue fuels."""
    if not code or code in FUELS:
        raise ValueError("custom fuel code must be non-empty and not a catalogue code: %r" % (code,))
    f = Fuel(code=code, name=name or ("custom " + code), residence_s=float(residence_s),
             residence_rel_sigma=float(residence_rel_sigma), consumed_load_kg_m2=float(consumed_load_kg_m2),
             heat_kj_kg=float(heat_kj_kg), source="custom (user supplied)")
    if register:
        _CUSTOM[code] = f
    return f


def get_fuel(code) -> Fuel:
    """Look a fuel up by short code ("GR2", "C064_GRASS", "DEFAULT", custom) or FBFM40 number (102)."""
    if isinstance(code, Fuel):
        return code
    if isinstance(code, int) and not isinstance(code, bool):
        if code in FBFM40_PARAMETERS:
            return FUELS[FBFM40_PARAMETERS[code][0]]
        raise KeyError("unknown FBFM40 code %r" % (code,))
    key = str(code).strip()
    if key.isdigit():
        return get_fuel(int(key))
    if key in FUELS:
        return FUELS[key]
    if key in _CUSTOM:
        return _CUSTOM[key]
    raise KeyError("unknown fuel %r" % (code,))


def all_fuels() -> Dict[str, Fuel]:
    out = dict(FUELS)
    out.update(_CUSTOM)
    return out
