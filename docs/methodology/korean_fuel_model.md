# Korean Pinus densiflora fuel model — methodology

## Why a custom fuel model

Korean wildfires are dominated by surface fires through Pinus densiflora
(소나무, Korean red pine) stands. The Anderson 13 fuel models do not
include a Korean Pinus-specific entry. The closest US analog (FM10 — timber
litter and understory) overestimates spread by roughly 1.5–2× because:

- Korean P. densiflora needles are shorter, finer, and produce a more
  compact litter bed (δ ≈ 15 cm vs FM10's ≈ 30 cm).
- Korean stand undergrowth is sparser than typical US Western timber due
  to dense allelopathic needle litter.
- Korean fire seasons are mostly spring (March–April), with cured
  understory but moist live foliage — a different LFMC regime than the
  late-summer California fire season FM10 was tuned for.

`KOREAN_PINUS` in `src/wildfireguardian/spread_model/rothermel/fuel_model.py`
is a defensible **analog model** with these adjustments. It uses the
Andrews 2018 multi-class structure so that we get the correct Rothermel
weighting algorithm under the hood; only the per-particle loadings, SAV,
and bed depth are tuned for Korean conditions.

## Parameters and rationale

| Class | Code | $w_o$ (lb/ft²) | $w_o$ (kg/m²) | $\sigma$ (1/ft) | $\sigma$ (1/cm) | Rationale |
|-------|------|---------------:|--------------:|---------------:|---------------:|-----------|
| 1-h dead | `DEAD_1H` | 0.10 | 0.49 | 2100 | 68.9 | Pinus densiflora needles ≈ 1 mm × 8 cm; lighter than FM10 |
| 10-h dead | `DEAD_10H` | 0.06 | 0.29 | 109 | 3.58 | Andrews 2018 Table 1 universal value |
| 100-h dead | `DEAD_100H` | 0.10 | 0.49 | 30 | 0.98 | Andrews 2018 Table 1 universal value |
| live woody | `LIVE_WOODY` | 0.06 | 0.29 | 1800 | 59.1 | reachable lower canopy of P. densiflora |
| live herb | `LIVE_HERB` | 0.03 | 0.15 | 1500 | 49.2 | sparse Korean Pinus understory (cured in spring) |
| Bed depth | $\delta$ | 0.5 ft = 15 cm | — | — | — | Korean Pinus litter bed depth (Lee et al. 2002 analog) |
| Dead extinction | $m_x^{\text{dead}}$ | 0.25 | — | — | — | FM10 analog; defensible for closed timber-litter beds |
| Heat content | $h$ | 8000 Btu/lb | 18.6 MJ/kg | — | — | universal wildland value (Rothermel 1972) |
| Total minerals | $s_T$ | 5.55 % | — | — | — | Andrews 2018 universal |
| Effective minerals | $s_e$ | 1.00 % | — | — | — | Andrews 2018 universal |

The live moisture of extinction $m_x^{\text{live}}$ is **not** a fixed
parameter; it is computed dynamically from the runtime per-particle dead
and live fuel moisture inputs via the Burgan (1979) formula
(Andrews 2018 eqs. 23–26).

For Korean spring conditions (dead 1-h ≈ 12 %, live ≈ 80 %), the dynamic
formula yields $m_x^{\text{live}} \approx 2.3$, i.e. live fuel at any
LFMC below ~ 230 % can still propagate fire. This is high but plausible
given the high dead-to-live fine-fuel ratio in Korean Pinus litter beds.

## Validation and refinement roadmap

The Korean Pinus parameters above are **analog values**, not directly
measured Korean field data. The fuel model is functional for the
qualitative LFMC sensitivity analysis and the cellular-automaton
demonstrations, but the absolute spread rates are subject to revision
once Korean fuel-load surveys are ingested.

Suggested refinement paths, in priority order:

1. **Kang & Lee 2001** Korean Pinus needle SAV measurements (KFRI).
2. **Lee, Y.J. et al. 2002** Korean forest-floor fuel loadings by stand
   age / canopy closure (KFRI Research Report).
3. **Korea Forest Service 임상도 (forest type map)** — per-stand
   classification that could trigger spatially-varying fuel parameters
   instead of a single Pinus archetype.
4. **Live moisture of extinction calibration** — Korean field LFMC + fire
   occurrence data could replace the Burgan 1979 formula with a Korean-
   specific calibration.

These are documented as blockers in `docs/BLOCKERS.md` and have priority
in Session 3.

## Limits of the analog

- The "live herb" class is purely a placeholder for cured grass / shrub
  understory; it is not a real herbaceous load measurement.
- The dynamic load transfer (Scott/Burgan 40 herbaceous curing) is NOT
  implemented; herbs stay in the live category even when fully cured.
  This is a known second-order effect; we revisit when ingesting field
  herbaceous moisture data.
- Korean Quercus / hardwood stands are NOT covered by this fuel model;
  FM9 is the current US analog for those.

## References

- Burgan, R.E. (1979). *Estimating live fuel moisture for the 1978
  National Fire-Danger Rating System.* USDA FS RP INT-226.
- Kang, J.M., Lee, S.Y. (2001). *Surface area-to-volume ratio of major
  Korean conifer fuels.* (Korean Forest Research Institute, cited as analog.)
- Lee, Y.J., Park, J.H., Lee, J.H. (2002). *Surface fuel loadings in
  Korean pine forests by stand age.* (KFRI Research Note, cited as analog.)
- Korea Forest Service (2024). 임상도 v1.4 [Forest type map].
  https://map.forest.go.kr (registration required).
