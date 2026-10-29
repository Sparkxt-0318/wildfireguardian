"""Constants, formulas and sources of radiation law ``wfg.radiation.law/2-flamefront``.

Every physical constant used anywhere in the package is defined here once, with its source, so that
``provenance()`` can return the complete list. Values marked ``verification`` = ``"prompt-supplied"`` were taken
from the track specification and were not re-read from the original paper in this work; values marked
``"standard"`` are textbook relations; values marked ``"repository"`` are copied from the frozen WildfireGuardian
export or bridge (``integration/src/wfg_latest/contract.py``) so that v2 runs on the same fuel energy as v1.
"""
from __future__ import annotations

import copy

LAW_VERSION = "wfg.radiation.law/2-flamefront"
PACKAGE_VERSION = "0.1.0"

# --- fuel and combustion (repository values, identical to the v1 export policy) --------------------------------
HEAT_CONTENT_KJ_KG = 18608.0          # FBFM40 nominal heat content, contract.POLICY heat_of_combustion_j_kg / 1000
FUEL_LOAD_KG_M2 = 10.0                # contract.POLICY fuel_load_kg_m2 (WildfireGuardian research value)
CONSUMED_FRACTION = 0.1               # contract.POLICY consumed_fraction (flaming-phase consumption)
FLAMING_CONSUMPTION_KG_M2 = FUEL_LOAD_KG_M2 * CONSUMED_FRACTION   # w = 1.0 kg/m2 consumed in the flaming front
POINT_RESIDENCE_S = 11.52             # contract.POLICY point_residence_s (Anderson 1969 residence, SAV 2000 ft^-1)
NOMINAL_SPREAD_RATE_M_S = 341.0 / 3600.0   # contract.POLICY spread_rate_m_s
COARSE_CELL_DURATION_S = 3970.4642815249267  # REPORT.json burning_duration_s of the frozen packets (375 m cells)
HORIZON_S = 3600.0                    # bridge BASE_SETTINGS horizon_s

# --- rate of spread clip ---------------------------------------------------------------------------------------
MAX_SPREAD_RATE_M_S = 3.0             # documented clip on 1/|grad tau|; about 10.8 km/h, above most surface fire spread

# --- Byram relations (standard) --------------------------------------------------------------------------------
BYRAM_FLAME_LENGTH_COEFF = 0.0775     # L = 0.0775 I^0.46, I in kW/m, L in m (Byram 1959)
BYRAM_FLAME_LENGTH_EXPONENT = 0.46

# --- flame tilt (Froude-number form) ---------------------------------------------------------------------------
GRAVITY_M_S2 = 9.80665
TILT_COEFFICIENT = 1.4                # tan(theta) = 1.4 U / sqrt(g L); see SOURCES["flame_tilt"]

# --- emissive power ---------------------------------------------------------------------------------------------
EMISSIVE_POWER_SURFACE_KW_M2 = 100.0  # grass and shrub default
EMISSIVE_POWER_CROWN_KW_M2 = 200.0    # crown fire default
STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8   # CODATA 2018
ATMOSPHERIC_TRANSMISSIVITY = 1.0      # same as v1 (contract.POLICY atmospheric_transmissivity)
RECEIVER_HEIGHT_M = 0.0               # same as v1 (contract.POLICY receiver_height_m)
CUTOFF_RADIUS_M = 500.0               # point-evaluation truncation radius (the enclosure is not truncated)

# --- dose and thresholds ----------------------------------------------------------------------------------------
TDU_EXPONENT = 4.0 / 3.0
TDU_THRESHOLDS = {                    # (kW/m2)^(4/3) s
    "pain": 92.0,
    "first_degree_burn": 105.0,
    "second_degree_burn": 290.0,
    "third_degree_burn": 1000.0,
    "lethality_1_percent": 1000.0,
    "lethality_50_percent": 2000.0,
}
EISENBERG_PROBIT = {"a_kw": -14.9, "b": 2.56, "a_w": -14.9 - 2.56 * (4.0 / 3.0) * 6.907755278982137}
# a_w: with q in W/m2, ln(t q^(4/3)) gains (4/3) ln(1000) = 9.2103, times b = 2.56 gives 23.58; a_w = -38.48.
AS3959_BANDS_KW_M2 = (("BAL-12.5", 12.5), ("BAL-19", 19.0), ("BAL-29", 29.0), ("BAL-40", 40.0),
                      ("BAL-FZ", float("inf")))   # band = first entry whose upper limit is >= q

SOURCES = {
    "byram_intensity": {"formula": "I = H w R (kW/m) with H kJ/kg, w kg/m2, R m/s",
                        "source": "Byram, G.M. 1959. Combustion of forest fuels. In: Davis, K.P. (ed.) Forest Fire: Control and Use. McGraw-Hill, New York, pp. 61-89.",
                        "verification": "standard"},
    "byram_flame_length": {"formula": "L = 0.0775 I^0.46 (L m, I kW/m)", "source": "Byram 1959 (as above)",
                           "verification": "standard"},
    "flame_tilt": {"formula": "tan(theta) = 1.4 U / sqrt(g L), flame height = L cos(theta), lean L sin(theta) downwind",
                   "source": "Froude-number tilt form used for wind-driven surface fires (Nelson, R.M. and Adkins, C.W. 1986, Flame characteristics of wind-driven surface fires, Can. J. For. Res. 16:1293-1300, doi:10.1139/x86-229)",
                   "verification": "form and coefficient not verified against the paper in this work; the routing packets carry no wind field, so the routing results never use it"},
    "emissive_power": {"values_kw_m2": {"surface": EMISSIVE_POWER_SURFACE_KW_M2, "crown": EMISSIVE_POWER_CROWN_KW_M2},
                       "context": "Butler et al. 2004 (Can. J. For. Res. 34:1577-1587): experimental crown fires, about 200 kW/m2 average and 290 kW/m2 peak; Frankman et al. 2013 (Int. J. Wildland Fire 22:157-167): in-flame radiative peaks 20-115 kW/m2 surface, 120-132 brush, 189-300 crown; blackbody at 1200 K = 117.6 kW/m2",
                       "verification": "prompt-supplied"},
    "view_factor": {"formula": "differential element to planar polygon: v = (1/(2 pi)) sum_i gamma_i u_i with u_i the unit normal of (R_i x R_i+1) and gamma_i the angle between R_i and R_i+1; F(n) = n.v; worst case |v|",
                    "source": "Lambert contour form of the configuration factor; Howell, J.R., Menguc, M.P., Siegel, R. Thermal Radiation Heat Transfer (contour integration, differential area to polygon); Howell catalogue of configuration factors, configuration B-3 (plane element to parallel rectangle, normal through a corner) used as a test",
                    "verification": "standard"},
    "infinite_wall": {"formula": "F = 0.5 h / sqrt(h^2 + d^2) (vertical receiver at the base, facing an infinitely wide wall of height h)",
                      "verification": "standard (limit of configuration B-3)"},
    "solid_angle_box": {"formula": "rectangle at distance d: sum of signed atan(XY / (d sqrt(d^2 + X^2 + Y^2))) corner terms; box = sum over visible faces",
                        "verification": "standard"},
    "tdu": {"formula": "TDU = integral of q^(4/3) dt, q kW/m2, t s; 1 TDU = 1 (kW/m2)^(4/3) s",
            "thresholds": TDU_THRESHOLDS,
            "source": "Eisenberg, N.A., Lynch, C.J., Breeding, R.J. 1975. Vulnerability model. US Coast Guard report CG-D-136-75; TNO Green Book (CPR 16E, 1992); UK HSE guidance on thermal dose",
            "verification": "prompt-supplied"},
    "probit": {"formula": "Pr = a + b ln(t q^(4/3)), lethality, q kW/m2: a = -14.9, b = 2.56; with q in W/m2 a = -38.48 (shift 23.58)",
               "source": "Eisenberg et al. 1975 (as above)", "verification": "prompt-supplied; the unit shift is computed here"},
    "as3959": {"bands_kw_m2": "BAL-12.5 up to 12.5, BAL-19 up to 19, BAL-29 up to 29, BAL-40 up to 40, flame zone above 40",
               "source": "Standards Australia AS 3959-2018 Construction of buildings in bushfire-prone areas",
               "verification": "prompt-supplied"},
    "vehicle_burnover": {"note": "2006 CSIRO passenger-vehicle burnover tests: 10-40 kW/m2 peak radiant intensity outside the vehicle; average time to toxic-air untenability inside about 10 minutes, driven by smoke and particles more than by heat",
                         "verification": "prompt-supplied"},
    "residence": {"value_s": POINT_RESIDENCE_S, "source": "frozen export policy contract.POLICY point_residence_s (Anderson 1969, SAV 2000 ft^-1)",
                  "verification": "repository"},
    "energy": {"heat_content_kj_kg": HEAT_CONTENT_KJ_KG, "fuel_load_kg_m2": FUEL_LOAD_KG_M2,
               "consumed_fraction": CONSUMED_FRACTION, "source": "frozen export policy contract.POLICY",
               "verification": "repository"},
}

ASSUMPTIONS = {
    "emitter": "flame sheet standing on the leading isochrone tau(x) = t (marching squares on the bilinear interpolation of the ignition-time field between cell centres), height = Byram flame length times cos(tilt), both faces emitting E",
    "contact_consistency": "a flame piece is kept only where its host cell (the grid cell that contains it) is active under the v1 member activity at that time; v2 flames are therefore a subset of the v1 flaming cells",
    "engulfment": "a receiver inside the flaming band (tau(x) <= t < tau(x) + residence, host cell active) receives E",
    "receiver_worst_case": "per segment the receiver normal maximises the unclipped Lambert integral (|v|); the enclosure uses the solid-angle bound min(1, Omega/pi), which bounds every real orientation including clipped near-field cases",
    "never_ignited_cells": "declared arrival horizon + coarse-cell duration (the front continues toward them at the bridge's nominal pace and does not reach their centre within the horizon)",
    "present_fire": "scalar maximum-remaining enclosure of the bridge: arrival R_max - T for every present-fire cell (unknown-age present cells: 0); per-cell option uses r - T",
    "burned_out_cells": "known burned cells that are not active at the cutoff: arrival -T",
    "unknown_cells": "excluded (no flame in any dual square touching them) and counted as unsupported_cells",
    "wind": "no wind field in the frozen packets: vertical flames",
    "not_modelled": ["convective heating", "smoke and toxic gases", "ember attack", "vehicle shielding", "flame emissivity below the declared E", "atmospheric attenuation (transmissivity 1)"],
}


def provenance():
    """Return a JSON-ready dict with the law version, every constant and every source."""
    constants = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, (int, float, str, tuple, dict))
                 and k not in ("SOURCES", "ASSUMPTIONS")}
    out = {
        "law_version": LAW_VERSION,
        "package_version": PACKAGE_VERSION,
        "constants": copy.deepcopy(constants),
        "sources": copy.deepcopy(SOURCES),
        "assumptions": copy.deepcopy(ASSUMPTIONS),
        "deterministic": True,
        "dependencies": ["numpy"],
        "physical_validation": False,
    }
    return _json_ready(out)


def _json_ready(o):
    if isinstance(o, dict):
        return {k: _json_ready(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_ready(v) for v in o]
    if isinstance(o, float) and o == float("inf"):
        return "inf"
    return o
