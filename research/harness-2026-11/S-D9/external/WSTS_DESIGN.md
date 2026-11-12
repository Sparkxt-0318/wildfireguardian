# External yardstick: scoring S-D9 candidates in the WildfireSpreadTS setting

**Feasibility and adapter design, DEVELOPMENT-ONLY.** Nothing has been downloaded or scored. This note is for Iris to assess. Hosting, per-unit sizes and fetchability are pending from Daniel. No large download happens until the orchestrator has been told its size.

## 1. What WSTS is (Sofia, from the NeurIPS 2023 paper and the repo; page and table refs in her message)

- **Task.** Predict the next day's **binarised VIIRS active-fire map** (VNP14IMG, 375 m, 24 h) from 1 or 5 days of 23-channel inputs (Fig. 1, p.2).
  - The label is **all pixels detected as active that day**, so pixels that keep burning count as positives. It is *not* new burn.
  - About 0.1% of pixels are positive.
  - Non-burnable and never-burning cells are counted as negatives, with no mask.
- **Data.** 607 US fires, 13,607 fire-days, January 2018 to October 2021.
- **Splits.** All 12 permutations of 2 training / 1 validation / 1 test year, 2018–2021. Testing starts at the day-6 target of each fire (§5.2, p.7–8).
- **Metric.** Test-set **average precision**, pooled over all pixels of the test year (torchmetrics in the repo), reported as the mean ± SD over the 12 folds (Table 5, p.9).
- **Reference numbers (12-fold AP).**
  - Persistence: 0.193 ± 0.065. By test year: 2018 0.187, 2019 0.105, 2020 0.194, 2021 0.287.
  - Logistic regression: 0.279–0.288.
  - Res18 U-Net: 0.328–0.344.
  - UTAE: 0.321–0.372.
  - WSTS+ recipe: up to 0.478 ± 0.085.
- **No kernel or cellular probabilistic model** reports the official 12-fold AP. LIPS (Migliorini & Smyth) uses a different crop, split and metric.
- **Label noise.**
  - 35–49% of images per year have no detections (Table 1).
  - The external audit (Zenodo 23876108, CC BY 4.0) flags 1,732 fire-days whose **empty** maps are unreliable, and ships standard, flagged-only and detection-day evaluation rules. Its flags use post-gap information, so they are for retrospective evaluation only.

## 2. The mismatch with S-D9, stated before any number

| | S-D9 (A1) | WSTS |
|---|---|---|
| label | **new burn** within the interval, from mapped NIROPS perimeters (cumulative extent) | **all active** VIIRS pixels the next day (detections, not extent) |
| state at cutoff | mapped perimeter union | active-fire detections (noisy, 2–4 passes a day, cloud and smoke gaps) |
| horizon | 0 < Δ ≤ 48 h, survey-timed | a fixed 24 h day |
| grid | EPSG:5070, 375 m, fixed rectangle | 375 m resampled scenes, centre-cropped to a multiple of 32 |
| inputs our models need | temperature, E/N wind, slope, tree cover %, biome (rebuilt pipeline) | 23 channels: VIIRS reflectance, NDVI/EVI, GRIDMET weather and forecast, topography, MODIS land cover, drought |

A model that predicts new burn **cannot be scored on the official WSTS label without an adapter**: tomorrow's active pixels include fire that persists in already-burning cells. A number from such an adapter is not comparable to the S-D9 benchmark, and must not be presented as if it were.

## 3. Adapter design (two scores, both declared now)

**Inputs.** WSTS supplies the *labels and split* only. Covariates for our models come from **our rebuilt pipeline** (Daniel's builder) on each WSTS scene's footprint and dates, so every S-D9 model sees the inputs it was built for. The WSTS channels are not remapped.
- *Why.* GRIDMET winds would need conversion to E/N components. Tree cover % does not exist in WSTS, which has MODIS land-cover classes. Biome needs a lookup. Remapping would test the adapter, not the model.
- *Cost.* The Open-Meteo quota is about 1 call per node per 14 days per event. Daniel would price it.

**State at cutoff.** S = cumulative union of VIIRS active-fire detections up to and including day t, rasterised to our grid. This is the "burned so far" proxy, and the WSTS repo already stores the last-detection hour per pixel.

**Score A: official-label AP, for comparability.** The predicted probability that pixel j is active on day t + 1 is:
- for j ∉ S: our P(new burn within 24 h);
- for j ∈ S: a **declared persistence term**. The primary term is the indicator "j was detected active on day t", which is exactly WSTS persistence. The secondary is our `burnout` residence model, where available.

Score A is pooled AP over the test year's pixels, from the day-6 target, on full centre-cropped scenes, as WSTS does.
- **Reported as a decomposition on identical pixels (Iris).** (1) the persistence term alone; (2) persistence plus each model's new-burn probability; and (3) the increment, (2) − (1).
  - Most next-day active pixels are active today, so Score A will be carried by the persistence term. **If the increment is near zero, that is the finding**, and it is stated.
  - Score A is **placement only**. Score B answers the S-D9 question.
  - Score A is never set beside published WSTS numbers without this sentence: "our inputs are rebuilt covariates, and our score includes a declared persistence term". It is reported **with WSTS persistence computed on the identical pixels**, and with the repo commit stated. It measures "our new-burn forecast plus a stated persistence rule". It is not our model alone.

**Score B: native new-burn label, the S-D9 question.** The label is active on day t + 1 **and** not in S. Scores are computed over cells not in S:
- Brier, AP and BSS against persistence (= 0) and against climatology;
- reliability by bin;
- positives below 1/1024;
- CRC per fire (A1 §5.4);
- the Allaire binary rank histogram, for MC models.

Score B is directly comparable in kind to S-D9's cohort scores. It is not comparable to published WSTS numbers.
- **Cautions, stated with every Score B result (Iris).**
  - The label and S are built from **detections**. Cells that burned but were never detected count as negatives, and S, the "already burned" set, is **undercounted**. This applies Elena's missed-detection result.
  - The audit's flagged-only rule addresses only the part where a **whole day's empty map** is unreliable. It does not address cells that are missed within a day that has detections.
  - **Setting.** It is one 24 h step with weather held at the cutoff hour. That differs from the hourly models' design point, so results are reported as "the model in a 24 h, held-weather setting".

**Observation-aware variant (both scores).** Each score is repeated under the audit's flagged-only rule, which drops days whose empty maps are flagged unreliable. Both versions are reported.

## 4. Subset, leakage and exposure

- **Use the 2018 and 2019 test years only.**
  - *Leakage.* S-D9 models are trained on US fires from 2020–2022 (fit-23) and part a (NIROPS 2020–2024). The WSTS years 2018 and 2019 are disjoint from every S-D9 training year. 2020 and 2021 overlap them.
  - *Exposure.* The sealed parts b, c and d are NIROPS 2020–2024 incidents. A WSTS 2020 or 2021 scene could contain a sealed fire, and **loading it would expose a sealed fire.** 2018 and 2019 cannot.
- **Folds.** Our models are not trained on WSTS. So the 12-fold protocol reduces to the test years: each test year appears in 3 of the 12 folds, and the 12-fold mean over test years equals the mean of the per-year scores. With only 2018 and 2019, report **per-year** AP and the two-year mean beside WSTS persistence for those years (0.187 and 0.105). **Do not** quote a "12-fold" number.
- **Size.** The full dataset is about 48 GB. Two years is roughly half, so still too large for one container. The design is **streamed per fire**: fetch one fire's files, score it, keep only per-pixel predictions and labels for the scored pixels (or only running AP sufficient statistics), then delete. This depends on Daniel confirming per-fire or per-year fetchability (range requests or split archives). If only a single 48 GB archive exists, the plan falls back to a sample of fires, declared by a hash rule before fetching, and the result is labelled "subset, not the WSTS test set".
- **Status.** Development-only external yardstick. It never feeds an A1 §6 decision. Any claim from it names the score (A or B), the years, the commit and the observation rule.

## 5. Open items

1. Daniel: hosting, per-unit sizes, range-request or per-year access, file format and CRS, and fire metadata to confirm there is no 2018/2019 overlap with any S-D9 cohort. Metadata only.
2. Iris: does Score A's persistence term for j ∈ S make the comparison meaningful, or should only Score B be reported?
3. The audit's split and rule files (Zenodo 23876108, small) are fetched with the dataset.
4. Rebuilding covariates for the 2018–2019 fires is the main cost. That is roughly 300 fires if the 607 are spread evenly over 4 years; the real count comes from the metadata. Daniel would price it after item 1.
