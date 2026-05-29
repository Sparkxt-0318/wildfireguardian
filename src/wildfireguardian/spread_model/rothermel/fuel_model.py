"""Fuel-model data structures and registries.

Two representations live here side-by-side:

- :class:`FuelModel` — *single-class* representation kept for backwards
  compatibility with Session 1. One characteristic loading + SAV.
  Single-class is known to overestimate spread for live-fuel-dominated
  models (FM4, FM10) by 2–3× vs published BehavePlus values.
- :class:`MultiClassFuelModel` — Andrews 2018 multi-class representation
  with one :class:`FuelClass` per particle (1-h, 10-h, 100-h dead;
  herbaceous live; woody live). This is the scientific upgrade.

The :data:`ANDERSON_13` registry exposes all 13 Anderson (1982) fuel
models in their canonical multi-class form, with loadings and SAVs taken
from Andrews 2018 Table 1.

Both representations consume the same Rothermel sub-equations
(:mod:`wildfireguardian.spread_model.rothermel.equations`); the routing
between them lives in :mod:`wildfireguardian.spread_model.rothermel.spread`.

References
----------
- Anderson, H.E. (1982). *Aids to determining fuel models for estimating
  fire behavior.* USDA FS GTR INT-122. 22 pp.
- Andrews, P.L. (2018). *The Rothermel surface fire spread model and
  associated developments.* USDA FS GTR RMRS-GTR-371. 121 pp. (Table 1,
  p. 12, lists the multi-class parameters for Anderson 13.)
- Scott, J.H., Burgan, R.E. (2005). *Standard fire behavior fuel models.*
  USDA FS GTR RMRS-GTR-153. (For the dynamic load-transfer scheme used in
  Scott/Burgan 40, beyond the scope of this session.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final

from .equations import (
    PARTICLE_DENSITY_LB_FT3,
    bulk_density,
    optimum_packing_ratio,
    packing_ratio,
)


# ---------------------------------------------------------------------------
# Fuel-class enums
# ---------------------------------------------------------------------------


class FuelCategory(str, Enum):
    """Whether a particle is dead-and-cured or live-and-photosynthesising."""

    DEAD = "dead"
    LIVE = "live"


class FuelClassKind(str, Enum):
    """Per Andrews 2018 Table 1, the five canonical particle classes.

    The 1-h / 10-h / 100-h classes correspond to time-lag drying classes
    (Fosberg 1971): 1-h particles equilibrate to ambient humidity within
    one hour, etc. Operationally these correspond to fine litter, twigs,
    and downed wood up to ~3 inches.
    """

    DEAD_1H = "1h_dead"
    DEAD_10H = "10h_dead"
    DEAD_100H = "100h_dead"
    LIVE_HERB = "live_herb"
    LIVE_WOODY = "live_woody"


def _category_of(kind: FuelClassKind) -> FuelCategory:
    return (
        FuelCategory.LIVE
        if kind in (FuelClassKind.LIVE_HERB, FuelClassKind.LIVE_WOODY)
        else FuelCategory.DEAD
    )


# ---------------------------------------------------------------------------
# Single particle (Andrews 2018 multi-class building block)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FuelClass:
    """One particle class within a multi-class fuel model.

    All units are Rothermel imperial; SI conversions live in the public
    spread_rate wrapper.

    Attributes
    ----------
    kind : FuelClassKind
        Which canonical particle class this is.
    w_o : float
        Oven-dry loading of THIS particle class, lb/ft².
    sigma : float
        Surface-area-to-volume ratio, 1/ft.
    h : float
        Heat content, Btu/lb. Defaults to 8000 (typical wildland fuel).
    s_T : float
        Total mineral content, fraction. Andrews 2018 default 0.0555.
    s_e : float
        Effective (silica-free) mineral content, fraction. Default 0.0100.
    """

    kind: FuelClassKind
    w_o: float           # lb/ft²
    sigma: float         # 1/ft
    h: float = 8000.0    # Btu/lb
    s_T: float = 0.0555  # fraction
    s_e: float = 0.0100  # fraction

    @property
    def category(self) -> FuelCategory:
        """Dead or live."""
        return _category_of(self.kind)

    @property
    def surface_area_per_ground_area(self) -> float:
        """A_ij = σ_ij · w_o_ij / ρ_p  (ft² of particle surface / ft² ground)."""
        return self.sigma * self.w_o / PARTICLE_DENSITY_LB_FT3


# ---------------------------------------------------------------------------
# Multi-class fuel model (Andrews 2018 Table 1 representation)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiClassFuelModel:
    """A fuel model with separate 1-h, 10-h, 100-h dead, and live classes.

    This is the scientifically correct representation used by BehavePlus
    and FARSITE. The single-class :class:`FuelModel` lives alongside this
    for backwards compatibility; new code should prefer this class.

    Attributes
    ----------
    code : str
        Short identifier, e.g. ``"FM10"`` or ``"KP_PINE"``.
    name : str
        Human-readable name (English).
    name_kr : str
        Korean translation if applicable, else empty.
    particles : tuple of FuelClass
        Per-particle parameters. Order is not significant; both this list
        and the per-class moisture inputs are looked up by ``kind``.
    delta : float
        Fuel bed depth, ft.
    m_x_dead : float
        Moisture of extinction for the DEAD fuels, fraction. The live
        moisture of extinction is computed dynamically per Burgan (1979).
    description : str
        Free-text ecological description.
    dynamic_load_transfer : bool
        If True, this is a Scott/Burgan dynamic fuel model in which
        herbaceous load is moved from "live" to "dead" as the herb cures.
        Not used in Anderson 13 (always False); reserved for future use.
    """

    code: str
    name: str
    particles: tuple[FuelClass, ...]
    delta: float                        # ft
    m_x_dead: float = 0.25              # fraction
    name_kr: str = ""
    description: str = ""
    dynamic_load_transfer: bool = False
    #: Representative live-fuel moisture (fraction) for this stand, where a
    #: measured value exists (e.g. Korean Pinus foliar moisture 1.19).
    #: ``None`` means "no canonical default — caller must supply LFMC".
    live_moisture_default: float | None = None
    #: Canopy structure for crown-fire physics (Session 6). ``None`` ⇒ the
    #: cell cannot crown (surface-only). Set for forested fuels only.
    canopy_base_height_m: float | None = None
    canopy_bulk_density_kg_m3: float | None = None

    # Convenience -----

    def get(self, kind: FuelClassKind) -> FuelClass | None:
        """Return the FuelClass for ``kind`` if present, else None."""
        for p in self.particles:
            if p.kind is kind:
                return p
        return None

    @property
    def dead_classes(self) -> tuple[FuelClass, ...]:
        return tuple(p for p in self.particles if p.category is FuelCategory.DEAD)

    @property
    def live_classes(self) -> tuple[FuelClass, ...]:
        return tuple(p for p in self.particles if p.category is FuelCategory.LIVE)

    @property
    def total_loading_lb_ft2(self) -> float:
        """Σ_ij w_o_ij (lb/ft²)."""
        return sum(p.w_o for p in self.particles)

    @property
    def fine_fuel_load_kg_m2(self) -> float:
        """Available fine-fuel load for Byram intensity (kg/m²).

        The 1-h dead + all live particles — the fuel consumed in the flaming
        front. Used by the crown-fire transition check.
        """
        from ...utils import units as _U
        fine = sum(
            p.w_o for p in self.particles
            if p.kind is FuelClassKind.DEAD_1H or p.category is FuelCategory.LIVE
        )
        return fine * _U.KGM2_PER_LBFT2

    @property
    def can_crown(self) -> bool:
        return (self.canopy_base_height_m is not None
                and self.canopy_bulk_density_kg_m3 is not None)

    @property
    def bulk_density_lb_ft3(self) -> float:
        return bulk_density(self.total_loading_lb_ft2, self.delta)

    @property
    def packing_ratio(self) -> float:
        return packing_ratio(self.bulk_density_lb_ft3)

    @property
    def has_live(self) -> bool:
        return any(p.category is FuelCategory.LIVE for p in self.particles)


# ---------------------------------------------------------------------------
# Legacy single-class fuel model (Session 1 API; kept for back-compat)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FuelModel:
    """Single-class fuel-model record (Session 1 representation).

    Treats all particles in the Anderson 13 multi-class definition as a
    single characteristic class. Convenient for sensitivity studies and
    educational use, but known to over-estimate spread rate for fuels
    where live fuels dominate (FM4) or non-fine dead fuels carry mass
    (FM10, FM13).

    For scientifically defensible spread predictions, use
    :class:`MultiClassFuelModel` and :data:`ANDERSON_13` instead.

    Attributes
    ----------
    code : str
        Short identifier, e.g. ``"FM4"``.
    name : str
        Human-readable name.
    w_o : float
        Characteristic oven-dry loading, lb/ft².
    delta : float
        Fuel bed depth, ft.
    sigma : float
        Characteristic SAV, 1/ft (typically the 1-h dead value).
    h : float
        Heat content, Btu/lb.
    m_x : float
        Moisture of extinction, fraction.
    s_T, s_e : float
        Mineral content fractions.
    description : str
        Free-text ecological description.
    """

    code: str
    name: str
    w_o: float           # lb/ft²
    delta: float         # ft
    sigma: float         # 1/ft
    h: float = 8000.0    # Btu/lb
    m_x: float = 0.25    # fraction
    s_T: float = 0.0555  # fraction
    s_e: float = 0.0100  # fraction
    description: str = ""

    @property
    def bulk_density_lb_ft3(self) -> float:
        return bulk_density(self.w_o, self.delta)

    @property
    def packing_ratio(self) -> float:
        return self.bulk_density_lb_ft3 / PARTICLE_DENSITY_LB_FT3

    @property
    def optimum_packing_ratio(self) -> float:
        return optimum_packing_ratio(self.sigma)


# ---------------------------------------------------------------------------
# Anderson 13 multi-class registry (Andrews 2018 Table 1)
# ---------------------------------------------------------------------------
#
# Per-class loadings (w_o, lb/ft²) and SAVs (σ, 1/ft) are reproduced from
# Andrews 2018 GTR-RMRS-371 Table 1 (p. 12), which itself reproduces
# Anderson 1982 Table 2 with the SAV refinements of Albini 1976. Bed depth
# δ comes from the same table. m_x_dead is the dead moisture of extinction
# (Anderson 1982 §IV). Heat content and mineral content default to the
# Rothermel-default 8000 Btu/lb and 5.55 % / 1.00 %.
#
# Anderson 13 fuel models DO NOT include herbaceous live carryover dynamics
# (those are Scott/Burgan 40 dynamic). We faithfully reproduce the static
# loadings here.


def _make_anderson13() -> dict[str, MultiClassFuelModel]:
    """Build the Anderson 13 multi-class registry."""

    def fm(  # tiny convenience to keep the registry compact
        code: str, name: str,
        w_1h: float, w_10h: float, w_100h: float,
        w_live_herb: float, w_live_woody: float,
        sav_1h: float, sav_live_herb: float, sav_live_woody: float,
        delta: float, m_x_dead: float, description: str,
    ) -> MultiClassFuelModel:
        particles: list[FuelClass] = []
        # Dead 1-h: always present.
        if w_1h > 0.0:
            particles.append(FuelClass(FuelClassKind.DEAD_1H, w_1h, sav_1h))
        # 10-h dead: Andrews 2018 Table 1 fixes σ_10h = 109 1/ft.
        if w_10h > 0.0:
            particles.append(FuelClass(FuelClassKind.DEAD_10H, w_10h, 109.0))
        # 100-h dead: σ_100h = 30 1/ft.
        if w_100h > 0.0:
            particles.append(FuelClass(FuelClassKind.DEAD_100H, w_100h, 30.0))
        # Live herbaceous.
        if w_live_herb > 0.0:
            particles.append(FuelClass(FuelClassKind.LIVE_HERB, w_live_herb, sav_live_herb))
        # Live woody.
        if w_live_woody > 0.0:
            particles.append(FuelClass(FuelClassKind.LIVE_WOODY, w_live_woody, sav_live_woody))
        return MultiClassFuelModel(
            code=code, name=name,
            particles=tuple(particles),
            delta=delta, m_x_dead=m_x_dead,
            description=description,
        )

    return {
        # FM1 — short grass. 1-h dead grass only.
        "FM1": fm(
            "FM1", "Short grass (1 ft)",
            w_1h=0.034, w_10h=0.0, w_100h=0.0,
            w_live_herb=0.0, w_live_woody=0.0,
            sav_1h=3500.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=1.0, m_x_dead=0.12,
            description="Cured annual / native perennial grasslands.",
        ),
        # FM2 — timber understory grass.
        "FM2": fm(
            "FM2", "Timber (grass and understory)",
            w_1h=0.092, w_10h=0.046, w_100h=0.023,
            w_live_herb=0.023, w_live_woody=0.0,
            sav_1h=3000.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=1.0, m_x_dead=0.15,
            description="Open pine/oak with grass understory.",
        ),
        # FM3 — tall grass.
        "FM3": fm(
            "FM3", "Tall grass (2.5 ft)",
            w_1h=0.138, w_10h=0.0, w_100h=0.0,
            w_live_herb=0.0, w_live_woody=0.0,
            sav_1h=1500.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=2.5, m_x_dead=0.25,
            description="Cured prairie or steppe.",
        ),
        # FM4 — chaparral (live-dominated).
        "FM4": fm(
            "FM4", "Chaparral (6 ft)",
            w_1h=0.230, w_10h=0.184, w_100h=0.092,
            w_live_herb=0.0, w_live_woody=0.230,
            sav_1h=2000.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=6.0, m_x_dead=0.20,
            description="Mature chaparral — high-intensity live-woody surface fuel.",
        ),
        # FM5 — short brush.
        "FM5": fm(
            "FM5", "Brush (2 ft)",
            w_1h=0.046, w_10h=0.023, w_100h=0.0,
            w_live_herb=0.0, w_live_woody=0.092,
            sav_1h=2000.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=2.0, m_x_dead=0.20,
            description="Young brush / short chaparral.",
        ),
        # FM6 — dormant brush / hardwood slash.
        "FM6": fm(
            "FM6", "Dormant brush / hardwood slash",
            w_1h=0.069, w_10h=0.115, w_100h=0.092,
            w_live_herb=0.0, w_live_woody=0.0,
            sav_1h=1750.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=2.5, m_x_dead=0.25,
            description="Dormant brush; intermediate between FM5 and FM4.",
        ),
        # FM7 — southern rough.
        "FM7": fm(
            "FM7", "Southern rough",
            w_1h=0.052, w_10h=0.086, w_100h=0.069,
            w_live_herb=0.0, w_live_woody=0.017,
            sav_1h=1750.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=2.5, m_x_dead=0.40,
            description="Palmetto-gallberry; flammable even at high RH.",
        ),
        # FM8 — closed timber litter.
        "FM8": fm(
            "FM8", "Closed timber litter (0.2 ft)",
            w_1h=0.069, w_10h=0.046, w_100h=0.115,
            w_live_herb=0.0, w_live_woody=0.0,
            sav_1h=2000.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=0.2, m_x_dead=0.30,
            description="Closed-canopy timber, compact litter; slow but persistent.",
        ),
        # FM9 — hardwood litter.
        "FM9": fm(
            "FM9", "Hardwood litter (0.2 ft)",
            w_1h=0.134, w_10h=0.019, w_100h=0.007,
            w_live_herb=0.0, w_live_woody=0.0,
            sav_1h=2500.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=0.2, m_x_dead=0.25,
            description="Hardwood (oak / hickory) litter.",
        ),
        # FM10 — timber understory (relevant to Korean Pinus stands).
        "FM10": fm(
            "FM10", "Timber (litter + understory) (1 ft)",
            w_1h=0.138, w_10h=0.092, w_100h=0.230,
            w_live_herb=0.0, w_live_woody=0.092,
            sav_1h=2000.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=1.0, m_x_dead=0.25,
            description=(
                "Mature timber with heavy down material and understory. "
                "Most commonly cited US-analogue for Korean Pinus densiflora "
                "surface fuel; see KoreanPinusFuelModel for the project's "
                "Korean-tuned version."
            ),
        ),
        # FM11 — light slash.
        "FM11": fm(
            "FM11", "Light logging slash (1 ft)",
            w_1h=0.069, w_10h=0.207, w_100h=0.253,
            w_live_herb=0.0, w_live_woody=0.0,
            sav_1h=1500.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=1.0, m_x_dead=0.15,
            description="Light slash.",
        ),
        # FM12 — medium slash.
        "FM12": fm(
            "FM12", "Medium logging slash (2.3 ft)",
            w_1h=0.184, w_10h=0.644, w_100h=0.759,
            w_live_herb=0.0, w_live_woody=0.0,
            sav_1h=1500.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=2.3, m_x_dead=0.20,
            description="Medium slash.",
        ),
        # FM13 — heavy slash.
        "FM13": fm(
            "FM13", "Heavy logging slash (3 ft)",
            w_1h=0.322, w_10h=1.058, w_100h=1.288,
            w_live_herb=0.0, w_live_woody=0.0,
            sav_1h=1500.0, sav_live_herb=1500.0, sav_live_woody=1500.0,
            delta=3.0, m_x_dead=0.25,
            description="Heavy slash.",
        ),
    }


#: Anderson (1982) 13 standard fuel models in multi-class form per
#: Andrews 2018 Table 1.
ANDERSON_13: Final[dict[str, MultiClassFuelModel]] = _make_anderson13()


# ---------------------------------------------------------------------------
# Korean Pinus densiflora fuel model  (Session 5: literature-anchored)
# ---------------------------------------------------------------------------
#
# Live-fuel moisture and the stand context are anchored to MEASURED Korean
# values; the Rothermel SURFACE fuel bed (needle-litter load, depth, SAV,
# dead m_x) is a PROVISIONAL best-estimate, because the available Korean
# papers characterise CROWN fuel, not the ground litter bed the Rothermel
# surface model needs. Every provisional number is flagged here and in
# docs/methodology/korean_fuel_model.md + docs/BLOCKERS.md.
#
# MEASURED (cited):
#   - Foliar (live) moisture 119 %, average crown moisture 105.3 %.
#     "Allometric Equations of Crown Fuel Biomass for Pinus densiflora."
#     → live_moisture_default = 1.19.
#   - Crown structure (crown base height 3.6-5.2 m; crown bulk density
#     0.29-0.47 kg/m³; needles+twigs <1 cm = 50.3 % of crown fuel).
#     Lee, S.J. et al. (2018), J. Korean Soc. Forest Sci. 107(4):412-421.
#     → used for the canopy WAF (spread_model/wind.py), not the surface bed.
#   - Stand-level loading magnitude justified by the NIFoS P. densiflora
#     wildfire fuel-load model from 1,434 NFI plots, Forests 2022, 13(9):1372.
#
# PROVISIONAL surface-bed estimates (NOT measured — flagged):
#   - needle-litter (1-h dead) load 0.7 kg/m²  (range 0.5-0.9)
#   - fuel-bed depth 0.08 m                     (range 0.05-0.10)
#   - needle SAV 6000 1/m ≈ 1829 1/ft           (range 5500-6500 1/m)
#   - dead moisture of extinction 0.30          (range 0.25-0.30)
# These await Korean surface-litter field literature (see BLOCKERS).

# --- provisional surface-bed values in SI, converted to imperial below ---
_KP_LITTER_LOAD_KGM2: Final[float] = 0.7        # PROVISIONAL
_KP_FINE_TWIG_LOAD_KGM2: Final[float] = 0.2     # PROVISIONAL (downed twigs <1 cm)
_KP_UNDERSTORY_LOAD_KGM2: Final[float] = 0.15   # PROVISIONAL (sparse low live understory)
_KP_BED_DEPTH_M: Final[float] = 0.08            # PROVISIONAL
_KP_NEEDLE_SAV_PER_M: Final[float] = 6000.0     # PROVISIONAL
_KP_UNDERSTORY_SAV_PER_M: Final[float] = 5000.0 # PROVISIONAL
_KP_M_X_DEAD: Final[float] = 0.30               # PROVISIONAL (lit. range 0.25-0.30)
_KP_FOLIAR_MOISTURE: Final[float] = 1.19        # MEASURED (foliar live moisture 119 %)


def _kgm2_to_lbft2(x: float) -> float:
    """kg/m² → lb/ft² using the project unit table."""
    from ...utils import units as _U
    return x * _U.LBFT2_PER_KGM2


def _per_m_to_per_ft(sigma_per_m: float) -> float:
    """SAV 1/m → 1/ft (σ[1/ft] = σ[1/m] × 0.3048)."""
    from ...utils import units as _U
    return sigma_per_m * _U.M_PER_FT


def _m_to_ft(x: float) -> float:
    from ...utils import units as _U
    return x * _U.FT_PER_M


def _make_korean_pinus_fuel() -> MultiClassFuelModel:
    """Construct the Korean Pinus densiflora multi-class fuel model.

    Live moisture is the MEASURED Korean foliar value (119 %); the surface
    fuel bed is a PROVISIONAL estimate (see the module comment above and
    docs/methodology/korean_fuel_model.md). The structure follows
    Andrews 2018 multi-class so the same spread.py code path serves
    Anderson 13 and Korean Pinus alike.
    """
    return MultiClassFuelModel(
        code="KP_PINE",
        name="Korean Pinus densiflora (Gyeongbuk; surface bed provisional)",
        name_kr="한국 소나무 (경북; 지표연료 잠정)",
        delta=_m_to_ft(_KP_BED_DEPTH_M),
        m_x_dead=_KP_M_X_DEAD,
        live_moisture_default=_KP_FOLIAR_MOISTURE,
        # Canopy structure (MEASURED, Lee et al. 2018) for crown-fire physics.
        canopy_base_height_m=4.0,            # Gyeongbuk default (range 3.6–5.2)
        canopy_bulk_density_kg_m3=0.47,      # dense Gyeongbuk stand
        particles=(
            # 1-h dead needle litter — PROVISIONAL load/SAV.
            FuelClass(
                FuelClassKind.DEAD_1H,
                w_o=_kgm2_to_lbft2(_KP_LITTER_LOAD_KGM2),
                sigma=_per_m_to_per_ft(_KP_NEEDLE_SAV_PER_M),
            ),
            # 10-h dead downed twigs <1 cm — PROVISIONAL load; SAV Andrews universal.
            FuelClass(
                FuelClassKind.DEAD_10H,
                w_o=_kgm2_to_lbft2(_KP_FINE_TWIG_LOAD_KGM2),
                sigma=109.0,
            ),
            # Live low understory — PROVISIONAL load; moisture = measured foliar 119 %.
            FuelClass(
                FuelClassKind.LIVE_WOODY,
                w_o=_kgm2_to_lbft2(_KP_UNDERSTORY_LOAD_KGM2),
                sigma=_per_m_to_per_ft(_KP_UNDERSTORY_SAV_PER_M),
            ),
        ),
        description=(
            "Korean Pinus densiflora (Gyeongbuk) surface fuel. LIVE moisture "
            "and stand/canopy structure are MEASURED (Lee et al. 2018; foliar "
            "moisture 119 %); the Rothermel SURFACE bed (litter load 0.7 kg/m², "
            "depth 0.08 m, needle SAV 6000 1/m, dead m_x 0.30) is PROVISIONAL "
            "pending Korean surface-litter literature. Live moisture of "
            "extinction is computed dynamically per Burgan 1979. See "
            "docs/methodology/korean_fuel_model.md and docs/BLOCKERS.md."
        ),
    )


#: Korean Pinus densiflora fuel model (multi-class; live measured, surface provisional).
KOREAN_PINUS: Final[MultiClassFuelModel] = _make_korean_pinus_fuel()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class FuelModelRegistry:
    """Lookup table for fuel models by code, supporting multi-class and
    legacy single-class entries side by side.

    Anderson 13 entries are available under both their multi-class form
    (e.g. ``registry.multi("FM10")``) and their legacy single-class form
    (e.g. ``registry.single("FM10")``).
    """

    def __init__(self) -> None:
        self._multi: dict[str, MultiClassFuelModel] = dict(ANDERSON_13)
        self._multi[KOREAN_PINUS.code] = KOREAN_PINUS
        self._single: dict[str, FuelModel] = _build_legacy_single_class()

    # ----- multi-class -----

    def multi(self, code: str) -> MultiClassFuelModel:
        try:
            return self._multi[code]
        except KeyError as exc:
            raise KeyError(
                f"Unknown multi-class fuel model {code!r}; "
                f"available: {sorted(self._multi)}"
            ) from exc

    def has_multi(self, code: str) -> bool:
        return code in self._multi

    @property
    def multi_codes(self) -> tuple[str, ...]:
        return tuple(self._multi.keys())

    # ----- legacy single-class -----

    def single(self, code: str) -> FuelModel:
        try:
            return self._single[code]
        except KeyError as exc:
            raise KeyError(
                f"Unknown single-class fuel model {code!r}; "
                f"available: {sorted(self._single)}"
            ) from exc

    def has_single(self, code: str) -> bool:
        return code in self._single

    @property
    def single_codes(self) -> tuple[str, ...]:
        return tuple(self._single.keys())


def _build_legacy_single_class() -> dict[str, FuelModel]:
    """Re-build the Session 1 single-class FUEL_MODELS registry.

    Loadings sum the dead + (where live-dominated) live particles, with
    σ set to the 1-h dead value — the standard educational simplification
    that collapses Anderson 13 into a one-class kernel. Kept verbatim for
    backwards compatibility with Session 1 tests and the
    ``demo_sensitivity`` plot legend.
    """
    return {
        "FM1": FuelModel(
            code="FM1", name="Short grass (1 ft)",
            w_o=0.034, delta=1.0, sigma=3500.0, m_x=0.12,
            description="Cured annual / native perennial grasslands.",
        ),
        "FM2": FuelModel(
            code="FM2", name="Timber (grass and understory)",
            w_o=0.092 + 0.046 + 0.023, delta=1.0, sigma=3000.0, m_x=0.15,
            description="Open pine/oak with grass understory.",
        ),
        "FM3": FuelModel(
            code="FM3", name="Tall grass (2.5 ft)",
            w_o=0.138, delta=2.5, sigma=1500.0, m_x=0.25,
            description="Cured prairie or steppe.",
        ),
        "FM4": FuelModel(
            code="FM4", name="Chaparral (6 ft)",
            w_o=0.230 + 0.184 + 0.092 + 0.230, delta=6.0, sigma=2000.0, m_x=0.20,
            description="Mature chaparral.",
        ),
        "FM5": FuelModel(
            code="FM5", name="Brush (2 ft)",
            w_o=0.046 + 0.023 + 0.092, delta=2.0, sigma=2000.0, m_x=0.20,
            description="Young brush.",
        ),
        "FM6": FuelModel(
            code="FM6", name="Dormant brush / hardwood slash",
            w_o=0.069 + 0.115 + 0.092, delta=2.5, sigma=1750.0, m_x=0.25,
            description="Dormant brush.",
        ),
        "FM7": FuelModel(
            code="FM7", name="Southern rough",
            w_o=0.052 + 0.086 + 0.069 + 0.017, delta=2.5, sigma=1750.0, m_x=0.40,
            description="Palmetto-gallberry.",
        ),
        "FM8": FuelModel(
            code="FM8", name="Closed timber litter (0.2 ft)",
            w_o=0.069 + 0.046 + 0.115, delta=0.2, sigma=2000.0, m_x=0.30,
            description="Closed-canopy timber.",
        ),
        "FM9": FuelModel(
            code="FM9", name="Hardwood litter (0.2 ft)",
            w_o=0.134 + 0.019 + 0.007, delta=0.2, sigma=2500.0, m_x=0.25,
            description="Hardwood litter.",
        ),
        "FM10": FuelModel(
            code="FM10", name="Timber (litter and understory) (1 ft)",
            w_o=0.138 + 0.092 + 0.230 + 0.092, delta=1.0, sigma=2000.0, m_x=0.25,
            description="Timber understory; Korean Pinus surrogate.",
        ),
        "FM11": FuelModel(
            code="FM11", name="Light logging slash (1 ft)",
            w_o=0.069 + 0.207 + 0.253, delta=1.0, sigma=1500.0, m_x=0.15,
            description="Light slash.",
        ),
        "FM12": FuelModel(
            code="FM12", name="Medium logging slash (2.3 ft)",
            w_o=0.184 + 0.644 + 0.759, delta=2.3, sigma=1500.0, m_x=0.20,
            description="Medium slash.",
        ),
        "FM13": FuelModel(
            code="FM13", name="Heavy logging slash (3 ft)",
            w_o=0.322 + 1.058 + 1.288, delta=3.0, sigma=1500.0, m_x=0.25,
            description="Heavy slash.",
        ),
    }


#: Module-level shared registry instance.
REGISTRY: Final[FuelModelRegistry] = FuelModelRegistry()

#: Legacy alias for Session 1 code that imports ``FUEL_MODELS``.
FUEL_MODELS: Final[dict[str, FuelModel]] = REGISTRY._single  # noqa: SLF001


__all__ = [
    "FuelCategory",
    "FuelClassKind",
    "FuelClass",
    "MultiClassFuelModel",
    "FuelModel",
    "FuelModelRegistry",
    "ANDERSON_13",
    "KOREAN_PINUS",
    "REGISTRY",
    "FUEL_MODELS",
]
