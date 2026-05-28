# Validation strategy

## What we validate

WildfireGuardian's headline scientific claim is that **multi-class
Rothermel + CRS-aware Huygens-elliptical CA + Korean Pinus fuel
parameters** can produce a defensible retrospective forecast of the
2025 Yeongdeok wildfire (and earlier East-Coast Pine-Belt events) before
the actual official 재난문자 was issued.

To support that claim, we exercise the system against three retrospective
cases and report standard quantitative skill scores.

## Three-site validation backbone

| Case | Date | Area (ha) | Why this case |
|------|------|----------:|---------------|
| **Yeongdeok 2025** | 2025-03-22 to 03-28 | ~3,800 | The motivating event. Recent KFS report. Mid-scale, urban-rural interface, multiple casualties in rural elderly. |
| **Uljin / Samcheok 2022** | 2022-03-04 to 03-13 | ~16,000 | Largest South Korean wildfire on record. Tests model behaviour at scale + cross-administrative-boundary spread. |
| **Goseong 2019** | 2019-04-04 to 04-06 | ~2,800 | Wind-driven night fire. Tests wind-dominance, short-duration event, casualty tail. |

All three sit in the **East Coast Pine Belt** (강원 동해안 + 경북 동해안)
and are dominated by Pinus densiflora 소나무 stands. Together they
provide:

- **Scale variation**: 2.8k ha → 3.8k ha → 16k ha.
- **Duration variation**: 2 days → 6 days → 10 days.
- **Interface variation**: pure rural (Goseong) → mixed rural/peri-urban
  (Yeongdeok) → mountainous remote (Uljin/Samcheok).

This is enough heterogeneity to make a scientifically defensible claim
that the system isn't tuned to a single case.

## Metrics

The metric set lives in `src/wildfireguardian/validation/metrics.py`.

### Spatial agreement

- **IoU (Jaccard index)**: |A ∩ B| / |A ∪ B|. Standard remote-sensing
  metric; 0 = disjoint, 1 = identical.
- **Sørensen-Dice**: 2|A ∩ B| / (|A| + |B|). Weights intersection more
  heavily; preferred in fire-spread validation literature (Filippi et al.
  2014).
- **Symmetric-difference area (km²)**: misclassified region. Useful for
  reporting "we got this many km² wrong".

### Probabilistic skill

- **Brier score**: mean squared error of probability vs. binary truth.
  0 = perfect, 0.25 = no skill, 1 = perfectly wrong. Operationalises the
  Monte Carlo ensemble output. (Brier 1950.)
- **Brier skill score**: 1 − BS / BS_climatology. > 0 means we beat a
  constant-prevalence forecast.

### Operational signal

- **Lead-time gain**: how much earlier the predicted ignition / first
  perimeter crossing of a threshold area would have triggered a warning
  vs. the historical 재난문자 issuance time. This is the headline
  operational metric for the rural-elderly use case.

### Temporal accuracy

- **Perimeter-area RMSE at horizons**: 1 h / 3 h / 6 h / 24 h. Maps
  directly to "we forecast X ha at 3 hours; actually was Y ha".

## Honest limitations (Session 2)

The Session 2 validation pipeline runs end-to-end on **synthetic** DEM
and **synthetic** fuel rasters. The Yeongdeok case manifest uses
**approximate** values reconstructed from public news coverage:

- The ignition point is from news; not the KFS official point.
- The official-warning timeline is reconstructed from media coverage of
  재난문자 issuance times.
- The total burn area is the KFS preliminary number; final may differ.
- The observed perimeter shapefile is **not yet ingested** — see
  `docs/BLOCKERS.md`.

Because of these stubs, the **numerical metric values from Session 2
are not yet meaningful** — the validation pipeline proves only that
the code runs end-to-end. Session 3 ingestion of real KFS / NGII / KMA
data is required before headline metric claims become defensible.

## Round 2+ research extension

The deployment-target region is the East Coast Pine Belt. Once Session
3 has the three validation cases running on real data, an obvious
research extension is to add cases from:

- **Central Mountain Belt** (충북 + 인내 강원): mixed hardwood-conifer
  forests, different fuel regime.
- **Southwestern Coast** (전남 + 경남 서부): humid spring climate,
  broadleaf-mixed stands, lower fire frequency.

These are catalogued as Tier-2 `RegionConfig` presets but are NOT
exercised in Session 2 or Session 3. They are reserved for a future
"can the model generalise outside its tuning regime" study.

## What forestry reviewers will look for

This validation strategy is built for review by Korean forestry and
environmental science researchers. The points we expect them to probe:

1. **"Why not BehavePlus / FlamMap directly?"** — Because BehavePlus is
   point-based; FlamMap is a complete national fuel raster pipeline that
   we cannot rebuild in the available time. The methodological core (the
   Rothermel multi-class + Burgan dynamics) is shared with both
   BehavePlus and FlamMap; we validate against published BehavePlus
   reference values in `tests/test_rothermel_multiclass.py`.
2. **"Why a custom Korean Pinus fuel model?"** — Because Anderson 13
   doesn't include a Korean-specific entry. The parameters are analog
   values flagged as such in `docs/methodology/korean_fuel_model.md`
   with a roadmap to Korean field-fuel-load data.
3. **"Why the geometric vulnerability mean?"** — A near-zero sub-score
   should zero out the composite; we should not call a fire-free county
   a deployment target. See `docs/methodology/vulnerable_counties.md`.
4. **"How honest is the lead-time gain?"** — The official-warning
   timeline is reconstructed from public sources, not from MOIS/KFS
   internal records. We acknowledge this in the manifest's
   `data_provenance` field.

## References

- Brier, G.W. (1950). *Verification of forecasts expressed in terms of
  probability.* Mon. Weather Rev. 78: 1–3.
- Filippi, J.B. et al. (2014). *Evaluation of forest fire spread
  simulations using two coupled fire/atmosphere models.* Comput. Geosci.
  71: 87–98.
- Sørensen, T. (1948). *A method of establishing groups of equal
  amplitude in plant sociology...* Biol. Skr. 5: 1–34.
