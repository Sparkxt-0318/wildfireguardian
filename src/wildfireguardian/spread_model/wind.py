"""Wind Adjustment Factor (WAF) and midflame-wind conversion.

Rothermel's surface fire spread model requires the **midflame** wind
speed — the wind averaged over the flame zone, typically a fraction of
the open 10-m or 20-ft wind. Feeding a raw station / 10-m wind directly
into the wind coefficient :math:`\\phi_w` overestimates spread, badly,
under a forest canopy (this was the Session 1-4 bug that inflated the
"wind-alone" factor to ~12.8).

This module implements the midflame Wind Adjustment Factor of

    Andrews, P.L. (2012). *Modeling wind adjustment factor and midflame
    wind speed for Rothermel's surface fire spread model.* USDA Forest
    Service, RMRS-GTR-266. 39 p.

which itself builds on Albini & Baughman (1979) and Baughman & Albini
(1980). Two regimes:

- **Unsheltered** (no overstory): the WAF depends only on the fuel-bed
  depth — a deeper fuel bed reaches higher into the wind profile.
- **Sheltered** (surface fuel under a tree canopy, e.g. closed Korean
  *Pinus densiflora*): the WAF additionally depends on the canopy
  height and the crown-fill fraction, and is much smaller (~0.1-0.3),
  because the canopy decouples the surface fuel from the free wind.

Unit note
---------
The Andrews 2012 / Albini-Baughman formulae are written with the **20-ft**
wind as the reference height and lengths in **feet**. We accept SI inputs
(metres) and convert internally. We then apply the resulting WAF directly
to the **10-m** wind per the project convention
(:func:`midflame_wind`). The 10-m vs 20-ft reference-height difference is
a ~5-10 % effect folded into the WAF here and flagged as provisional in
``docs/methodology/korean_fuel_model.md``.
"""

from __future__ import annotations

import math

from ..utils import units as U

#: Floor on the sheltered WAF. Andrews 2012 notes the sheltered model loses
#: validity for vanishingly small WAF; operationally a closed-canopy WAF
#: bottoms out around 0.1-0.15. We clamp to avoid pathological near-zero
#: midflame winds while keeping the value physically small.
WAF_FLOOR: float = 0.10


def _unsheltered_waf_from_depth_ft(depth_ft: float) -> float:
    r"""Unsheltered midflame WAF from fuel-bed depth (Baughman & Albini 1980).

    .. math::
        \mathrm{WAF} = \frac{1.83}{\ln\!\big((20 + 0.36\,\delta)/(0.13\,\delta)\big)}

    where :math:`\delta` is the fuel-bed depth in feet and 20 is the 20-ft
    reference height. Andrews 2012 eq. (8).
    """
    if depth_ft <= 0.0:
        raise ValueError("fuel-bed depth must be > 0 for the WAF")
    return 1.83 / math.log((20.0 + 0.36 * depth_ft) / (0.13 * depth_ft))


def _sheltered_waf(canopy_height_ft: float, crown_fill_fraction: float) -> float:
    r"""Sheltered midflame WAF under an overstory canopy (Albini & Baughman 1979).

    .. math::
        \mathrm{WAF} = \frac{0.555}
            {\sqrt{f\,H}\;\ln\!\big((20 + 0.36\,H)/(0.13\,H)\big)}

    where :math:`H` is the canopy top height (ft) and :math:`f` is the
    crown-fill fraction. Andrews 2012 eq. (9).

    We use the canopy-cover fraction as ``f`` — the common open-source
    simplification (e.g. pyrothermel, firelib). Andrews' precise crown-fill
    definition would refine this; the difference is documented and flagged
    provisional, but does not change the key qualitative result (sheltered
    WAF ≪ 1).
    """
    if canopy_height_ft <= 0.0:
        raise ValueError("canopy height must be > 0 for the sheltered WAF")
    if not (0.0 < crown_fill_fraction <= 1.0):
        raise ValueError("crown_fill_fraction must be in (0, 1]")
    denom = (
        math.sqrt(crown_fill_fraction * canopy_height_ft)
        * math.log((20.0 + 0.36 * canopy_height_ft) / (0.13 * canopy_height_ft))
    )
    return 0.555 / denom


def wind_adjustment_factor(
    fuel_depth_m: float,
    canopy_cover_frac: float = 0.0,
    canopy_height_m: float | None = None,
    crown_ratio: float | None = None,
) -> float:
    """Midflame Wind Adjustment Factor (Andrews 2012, RMRS-GTR-266).

    Returns the multiplier that converts the open wind to the midflame
    wind. Always in ``(0, 1]``.

    Parameters
    ----------
    fuel_depth_m : float
        Surface fuel-bed depth, metres. Drives the unsheltered WAF.
    canopy_cover_frac : float, default 0.0
        Overstory canopy cover, fraction ``[0, 1]``. If 0, the stand is
        treated as unsheltered. If > 0, the sheltered WAF is used (and
        capped at the unsheltered value — a canopy can only reduce wind).
    canopy_height_m : float | None
        Canopy top height, metres. Required when ``canopy_cover_frac > 0``.
    crown_ratio : float | None
        Live-crown ratio (crown length / tree height), ``[0, 1]``. If
        given, it scales the crown-fill fraction
        ``f = canopy_cover_frac × crown_ratio`` (Andrews 2012); otherwise
        ``f = canopy_cover_frac``.

    Returns
    -------
    float
        The wind adjustment factor, ``0 < WAF ≤ 1``.
    """
    depth_ft = fuel_depth_m * U.FT_PER_M
    unsheltered = _unsheltered_waf_from_depth_ft(depth_ft)
    unsheltered = min(unsheltered, 1.0)

    if canopy_cover_frac <= 0.0:
        return unsheltered

    if canopy_height_m is None or canopy_height_m <= 0.0:
        raise ValueError(
            "canopy_height_m is required (and must be > 0) when "
            "canopy_cover_frac > 0"
        )
    f = canopy_cover_frac
    if crown_ratio is not None:
        if not (0.0 < crown_ratio <= 1.0):
            raise ValueError("crown_ratio must be in (0, 1]")
        f = canopy_cover_frac * crown_ratio
    f = max(f, 1e-3)

    sheltered = _sheltered_waf(canopy_height_m * U.FT_PER_M, f)
    # A canopy can only reduce the wind reaching the surface fuel.
    sheltered = min(sheltered, unsheltered)
    # Clamp to the physical floor.
    return max(WAF_FLOOR, min(sheltered, 1.0))


def midflame_wind(u_10m_ms: float, waf: float) -> float:
    """Convert a 10-m open wind to the midflame wind: ``u_midflame = waf · u_10m``.

    Parameters
    ----------
    u_10m_ms : float
        Open wind speed at 10 m, m/s (e.g. a KMA AWS observation).
    waf : float
        Wind adjustment factor from :func:`wind_adjustment_factor`,
        ``0 < waf ≤ 1``.

    Returns
    -------
    float
        Midflame wind speed, m/s — the quantity Rothermel's :math:`\\phi_w`
        expects.
    """
    if u_10m_ms < 0.0:
        raise ValueError("wind speed must be >= 0")
    if not (0.0 < waf <= 1.0):
        raise ValueError(f"WAF must be in (0, 1]; got {waf}")
    return waf * u_10m_ms


# ---------------------------------------------------------------------------
# Korean Pinus densiflora stand WAF (Gyeongbuk closed-canopy case)
# ---------------------------------------------------------------------------
#
# Stand structure from Lee, S.J. et al. (2018) "Crown fuel characteristics
# and allometric equations of Pinus densiflora in Gyeongbuk Province":
# crown base height 3.6-5.2 m. We take a representative canopy top height of
# ~12 m and a closed-stand canopy cover of ~0.5. A surface fire's midflame
# height (~0.5-1.5 m) sits well below the 3.6-5.2 m crown base, so the
# sheltered regime applies — the surface fuel is strongly decoupled from
# the free wind.

KOREAN_PINE_CANOPY_HEIGHT_M: float = 12.0
KOREAN_PINE_CANOPY_COVER: float = 0.50
KOREAN_PINE_SURFACE_BED_DEPTH_M: float = 0.08   # see korean_fuel_model.md (provisional)


def korean_pine_waf() -> float:
    """Representative midflame WAF for a closed Gyeongbuk Korean pine stand.

    Computed from the documented stand structure (sheltered regime). This
    is the value the validation should use instead of the Session 3-4
    ad-hoc ``canopy_reduction_factor = 0.30``.
    """
    return wind_adjustment_factor(
        fuel_depth_m=KOREAN_PINE_SURFACE_BED_DEPTH_M,
        canopy_cover_frac=KOREAN_PINE_CANOPY_COVER,
        canopy_height_m=KOREAN_PINE_CANOPY_HEIGHT_M,
    )


__all__ = [
    "WAF_FLOOR",
    "wind_adjustment_factor",
    "midflame_wind",
    "korean_pine_waf",
    "KOREAN_PINE_CANOPY_HEIGHT_M",
    "KOREAN_PINE_CANOPY_COVER",
    "KOREAN_PINE_SURFACE_BED_DEPTH_M",
]
