# Live Fuel Moisture Content (LFMC) — methodology (skeleton)

> Status: **planning only.** No code exists yet; this is a placeholder.

## Why LFMC matters

Live fuel moisture content (LFMC, % of dry mass) controls the moisture
damping coefficient $\eta_M$ in the Rothermel reaction intensity term, and
therefore the rate of spread $R$. Below the "moisture of extinction"
$m_x$ no flaming spread is possible; well below $m_x$ the relationship is
steep and non-linear. For Korean conifer forests the empirical range of LFMC
between fire-prone (~ 40 %) and fire-resistant (~ 120 %) is much wider than
the 0–30 % range typical of fine dead fuels, so LFMC dominates seasonal
risk.

The March 2025 Yeongdeok event coincided with anomalously dry spring
conditions; KFS post-event reporting estimated regional LFMC near 35–45 %
for the affected pine stands. The `demo_sensitivity` figure in
`docs/figures/lfmc_sensitivity.png` plots this regime against the moisture
of extinction band.

## Planned approach

1. **Sentinel-2 inputs**: NBR (B8A, B12), NDWI (B8A, B11), NDVI (B8, B4),
   plus topographic predictors (slope, aspect, elevation, TWI).
2. **Reference labels**: in-situ LFMC measurements from the *Globe-LFMC 2.0*
   dataset (Yebra et al. 2024) plus any KFS field LFMC reports we can
   obtain.
3. **Model**: gradient-boosted regression (XGBoost), trained on Korean
   stations only to avoid biome transfer error; biome-transfer cross-check
   on Mediterranean Pinus data.
4. **Output**: 20-m LFMC raster updated every Sentinel-2 revisit (~ 5 days),
   gap-filled with a 16-day exponentially weighted moving mean.

## References

- Yebra, M., Quan, X., Riaño, D., Rozas Larraondo, P., van Dijk, A.I.J.M.,
  Cary, G.J. (2018). A fuel moisture content and flammability monitoring
  methodology for continental Australia based on optical remote sensing.
  *Remote Sensing of Environment*, 212, 260–272.
- Yebra, M. et al. (2024). *Globe-LFMC 2.0*, an enhanced global live fuel
  moisture content database. *Scientific Data*, 11, 31.
- Pellizzaro, G., Cesaraccio, C., Duce, P., Ventura, A., Zara, P. (2007).
  Relationships between seasonal patterns of live fuel moisture and
  meteorological drought indices for Mediterranean shrubland species.
  *International Journal of Wildland Fire* 16, 232–241.
