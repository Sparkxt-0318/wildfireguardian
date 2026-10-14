"""Explicit source contracts for nominal heat content and supplied phase mass.

The heat-content lookup is a reference fuel-model scenario. No function in this
module estimates moisture-adjusted effective heat or runs a fuel-consumption
model. Source and scope metadata are retained by CombustionParameters.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .heat import _FBFM40_PARAMETERS, _immutable_array, _real_array


BTU_IT_PER_LB_TO_J_PER_KG = 2326.0

_SCOTT_BURGAN_URL = "https://research.fs.usda.gov/download/treesearch/9521.pdf"
_NWCG_URL = "https://www-nwcg.fs2c.usda.gov/publications/pms437/fuels/surface-fuel-model-descriptions"
_NIST_URL = "https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication811e2008.pdf"
_SCOTT_2012_URL = "https://pyrologix.com/wp-content/uploads/2014/04/Scott_20121.pdf"
_CONSUME_URL = "https://depts.washington.edu/fft/webtool/help/docs/consume30_users_guide.pdf"


def heat_content_from_fbfm40(codes: ArrayLike) -> NDArray[np.float64]:
    """Return nominal FBFM40 heat content in J/kg of dry fuel.

    The Scott--Burgan fuel models prescribe 8000 Btu/lb except GR6 (code 106),
    which prescribes 9000 Btu/lb for both live and dead categories. Interpreting
    those catalog units as International Table Btu, NIST SP811 converts one
    Btu_IT/lb to 2326 J/kg. This produces 18,608,000 and 20,934,000 J/kg.
    No moisture, mineral, or incomplete-combustion correction is applied.

    Require genuine numeric integer-valued supported codes in a scalar or a
    nonempty [H,W] map. Missing, masked, nonburnable, and custom codes fail.
    Callers needing another heat yield must supply that scenario explicitly to
    CombustionParameters. The returned copied array is immutable.
    """
    code_array = _real_array(codes, "codes")
    if np.any(code_array != np.floor(code_array)):
        raise ValueError("codes must contain integer-valued fuel-model identifiers")
    supported = np.isin(code_array, tuple(_FBFM40_PARAMETERS))
    if not np.all(supported):
        invalid = np.unique(code_array[~supported]).tolist()
        raise ValueError(
            "FBFM40 heat content is unavailable for nonburnable or unsupported codes "
            f"{invalid}; supply an explicit heat_of_combustion_j_kg scenario instead"
        )
    btu_per_lb = np.where(code_array == 106, 9000.0, 8000.0)
    return _immutable_array(btu_per_lb * BTU_IT_PER_LB_TO_J_PER_KG)


def _with_input_provenance(metadata: dict[str, Any], provenance: Mapping[str, Any] | None) -> dict[str, Any]:
    if provenance is not None:
        if not isinstance(provenance, Mapping):
            raise ValueError("provenance must be a mapping")
        metadata["input_provenance"] = provenance
    return metadata


def fbfm40_heat_content_provenance(
    codes: ArrayLike, provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe the nominal lookup without claiming measured heat yield."""
    # Validate here too so metadata cannot certify unsupported assignments.
    heat_content_from_fbfm40(codes)
    code_array = _real_array(codes, "codes")
    metadata: dict[str, Any] = {
        "method": "scott_burgan_2005_nominal_fbfm40_heat_content",
        "energy_basis": "nominal reference heat per kg dry fuel; not event-specific measured effective heat yield",
        "heat_content_equation": "H_j_kg = (9000 if code == 106 else 8000) * 2326",
        "original_heat_content_units": "Btu_IT/lb",
        "heat_content_units": "J/kg of dry fuel",
        "btu_convention": "International Table Btu (explicit unit interpretation)",
        "conversion_j_kg_per_btu_it_lb": BTU_IT_PER_LB_TO_J_PER_KG,
        "catalog_codes_used": {
            str(int(code)): _FBFM40_PARAMETERS[int(code)][0]
            for code in np.unique(code_array)
        },
        "sources": [
            {"author_year": "Scott and Burgan 2005", "url": _SCOTT_BURGAN_URL,
             "location": "fuel-model parameter discussion and table 7"},
            {"author_year": "NWCG PMS 437", "url": _NWCG_URL,
             "location": "surface fuel model tables, Dead Heat and Live Heat columns; GR6 row"},
            {"author_year": "Thompson and Taylor 2008, NIST SP811", "url": _NIST_URL,
             "location": "Appendix B conversion table, printed p.46, Btu_IT per pound"},
        ],
        "limitations": [
            "nominal reference fuel-model values do not establish measured effective heat of this fire",
            "no moisture, mineral, or incomplete-combustion adjustment",
            "does not estimate flaming-phase consumed fraction or initial dry fuel loading",
            "all supplied consumption and duration inputs must describe the same modeled flaming phase",
        ],
    }
    return _with_input_provenance(metadata, provenance)


def phase_consumption_provenance(
    method: str, provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record the phase-mass adapter's energy balance and external-input scope."""
    metadata: dict[str, Any] = {
        "method": method,
        "phase_scope": "explicitly supplied modeled flaming phase",
        "energy_basis": "supplied heat per kg of dry fuel consumed in the modeled flaming phase",
        "energy_equation": "phase_energy_j_m2 = consumed_fuel_load_kg_m2 * heat_of_combustion_j_kg",
        "rate_equation": "heat_release_rate_density_w_m2 = phase_energy_j_m2 / burning_duration_s",
        "consumption_origin": "explicit supplied phase-consumed dry mass; measurement or external model output",
        "mass_units": "kg dry fuel per m2 of entire ground-cell area",
        "sources": [
            {"author_year": "Scott 2012", "url": _SCOTT_2012_URL,
             "location": "printed pp.17-18, heat per unit area and flaming-front consumed mass"},
            {"author_year": "Prichard, Ottmar and Anderson, CONSUME 3.0 User's Guide (undated accessed copy)",
             "url": _CONSUME_URL,
             "location": "printed pp.111,114, phase reports; Appendix C, pp.139-195"},
        ],
        "limitations": [
            "does not run CONSUME or infer consumed mass from total FCCS loading",
            "does not estimate consumption from relative humidity or fuel moisture alone",
            "external output must select the same modeled flaming phase and ground-area basis",
            "uniform heat-release rate during the supplied duration is an additional temporal scenario",
            "post-front flaming, smouldering and residual consumption are not automatically added",
        ],
    }
    return _with_input_provenance(metadata, provenance)
