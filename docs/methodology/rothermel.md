# Rothermel surface fire spread model — methodology (skeleton)

## What this document will become

A self-contained description of how `wildfireguardian.spread_model.rothermel`
implements the Rothermel (1972) surface fire spread model, with:

1. The master equation and every sub-equation, in the notation of Andrews 2018.
2. Each numerical coefficient traced to its source paper.
3. Unit conversions between Rothermel's original imperial system and the SI
   units used throughout this project.
4. A worked example for FM1, FM4, FM8 reproducing Andrews 2018 reference
   values.

## Master equation

The (no-wind, no-slope, single fuel class) rate of spread is

$$ R = \frac{I_R \, \xi}{\rho_b \, \varepsilon \, Q_{ig}} $$

and with wind and slope:

$$ R = \frac{I_R \, \xi \, (1 + \phi_w + \phi_s)}{\rho_b \, \varepsilon \, Q_{ig}} $$

where

- $I_R$ — reaction intensity (Btu·ft⁻²·min⁻¹)
- $\xi$ — propagating flux ratio (–)
- $\phi_w, \phi_s$ — wind and slope coefficients (–)
- $\rho_b$ — ovendry bulk density (lb·ft⁻³)
- $\varepsilon$ — effective heating number (–)
- $Q_{ig}$ — heat of preignition (Btu·lb⁻¹)

## Sub-equations

Will be filled in here referencing each `rothermel.py` function. **(TBD)**

## Implementation notes

- All sub-equations are implemented in `src/wildfireguardian/spread_model/rothermel.py`.
- Internal computation is in **Rothermel's original imperial units** to
  exactly match Andrews 2018; the public function `compute_spread_rate`
  accepts SI inputs (m/s, degrees, fraction) and returns SI outputs (m/min).
- The conversion factor 1 ft·min⁻¹ = 0.3048 m·min⁻¹ is the only place SI
  enters the calculation chain.

## Limitations of single-class implementation

The standard Rothermel framework supports multiple fuel size classes (1-h,
10-h, 100-h dead, live herbaceous, live woody) combined by surface-area
weighting (Albini 1976 §IV; Andrews 2018 §3). Our `FuelModel` dataclass
currently treats each Anderson 13 fuel as a **single characteristic class**,
which is the customary simplification for educational implementations and
which preserves all the qualitative behaviour (LFMC sensitivity, wind
elongation, slope effect) we need for the demonstrations.

A multi-class weighting layer is on the roadmap but not required for the
research questions asked here.

## References

- Rothermel, R.C. (1972). *A mathematical model for predicting fire spread in
  wildland fuels.* USDA Forest Service Research Paper INT-115.
- Albini, F.A. (1976). *Estimating wildfire behavior and effects.* USDA Forest
  Service General Technical Report INT-30.
- Anderson, H.E. (1982). *Aids to determining fuel models for estimating fire
  behavior.* USDA Forest Service General Technical Report INT-122.
- Andrews, P.L. (2018). *The Rothermel surface fire spread model and
  associated developments: a comprehensive explanation.* USDA Forest Service
  General Technical Report RMRS-GTR-371.
