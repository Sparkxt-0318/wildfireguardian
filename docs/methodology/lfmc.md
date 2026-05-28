# Live Fuel Moisture Content (LFMC) — methodology

> Status (Session 3): **methodology scaffold implemented**. The feature
> engineering + XGBoost regression structure is in
> `src/wildfireguardian/lfmc_model/retrieval.py`, demonstrated on a
> CLEARLY-LABELLED synthetic training set. Real Sentinel-1/2 + MODIS
> ingestion and Korean field-LFMC labels are Round 2.

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

## Implemented scaffold (Session 3)

`wildfireguardian.lfmc_model.retrieval` implements the full end-to-end
structure:

- **Feature set** (`FEATURE_NAMES`): Sentinel-1 VV/VH backscatter + VH/VV
  ratio, MODIS/Sentinel-2 NDVI + NDMI, 30-day accumulated precipitation,
  terrain (elevation/slope/aspect), and KFS forest-type code. This matches
  the SAR-enhanced feature set of Rao et al. (2020) and Wang et al. (2019).
- **Model** (`LFMCRetrievalModel`): an XGBoost regressor with the
  hyper-parameters used in the published LFMC literature.
- **Synthetic demonstration** (`demo_train_synthetic`): trains the model
  on a clearly-labelled synthetic dataset whose feature→LFMC relationships
  mimic the published ones. On held-out synthetic data it achieves
  R² ≈ 0.79, RMSE ≈ 13.5 % LFMC. **This is a methodology demonstration,
  not a real Korean LFMC model** — every metadata record is tagged
  `synthetic=True` and `do_not_use_for_production=True`.

Reported synthetic-fit feature importances (illustrative ordering, NOT a
real Korean result): VH/VV ratio and 30-day precipitation dominate,
followed by NDMI — consistent with the published SAR-LFMC literature
where vegetation water content drives the radar backscatter signal.

## Round 2 plan (real data)

1. **Sentinel-1 GRD**: VV/VH backscatter, multi-temporal speckle filtered.
2. **Sentinel-2 L2A**: NDVI (B8, B4), NDMI (B8, B11), NBR (B8A, B12).
3. **MODIS**: MOD13 NDVI for temporal continuity.
4. **Reference labels**: Globe-LFMC 2.0 (Yebra et al. 2024) + KFS field
   LFMC reports (Korean stations only, to avoid biome-transfer error).
5. **Output**: 20-m LFMC raster updated every Sentinel-2 revisit (~ 5 days),
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
