# FIRES: every fire in the finals paper and in the repo's frozen registries (kcf-abstain)

Frozen 2026-11-18 with `PROTOCOL.md`, before any outcome of this study was computed. 63 distinct fires.
Every one is a calibration fire, a test fire, or NOT TESTED with the reason. Where a test fire turns out to have no
scorable issue hour under the frozen rules (for example a fire shorter than 5 h), `RESULTS.md` reports it as
NOT TESTED with that reason; the list itself does not change.

## Sources read

| source | what it names |
|---|---|
| Finals paper (SMOKE, attached PDF, 21 pp.) | A catalog of "15 South Korean and 29 U.S. fires" (section 2, Appendix B.1). Wapiti is the only fire named in the text (25 NIROPS survey intervals, the held-out evaluation). The Korean 2025 and US 2024 seasons are held out; "25 contributing development fires" and test fires are counted but not named. |
| Finals poster | **Not attached and not in the repo.** A search of the repo for poster, finals, ISEF and the paper title found only map thumbnails (`planner/research-map/site/regions/*/poster.webp`). The poster's fire list could not be checked; any fire that appears only on the poster is missing below. |
| `forecast/data/environment/events.json` | The paper's catalog: 44 events with ids, names and dates (15 KR, 29 US). |
| `forecast/runs/20261010_categorical_balanced_benchmark/protocol.json` | The paper's split: 27 train, 7 validation, 10 test events. `forecast/documents/weighted_stratified_split_20261009.md`: 25 fires contributed rows to training and validation and 8 to test; which 9 development and 2 test events contributed none is recorded only in the owner-local cache `metadata.json`, not in git. |
| `research/forecast-v2/SPLIT.json` (frozen registry) | Fit: 23 US, 11 KR. Held out: **US2024** (6 fires; 273 NIROPS survey intervals), **Korea2025** (4 fires; 33 twelve-hour windows, 26 scored). |
| `research/kcf-evidence/sources/corridor-router-v8/*.csv` (frozen routing registry, 273 receipts) | Incidents **Gyeongbuk_2025** (78 cases; regions uiseong_andong_2025, yeongdeok_2025), **uljin_2022** (154), **hongseong_2023** (21), **miryang_2022** (17), **Caldor2021** (3). |
| `research/sipp-routing`, `research/next-combined/caldor-rim-alignment-*` | **Caldor/Rim panel**: Caldor 2021, Rim 2013. |
| `research/kcf-margin` (GOFER v0.2) | The **28 GOFER fires**. |
| `research/harness-2026-11/S-D9/ledger/EXPOSURE_LEDGER.csv` | Cross-check of all of the above (49 rows). |

## Reconciliation: paper versus registries

- **Same fires, different names.** Gyeongbuk_2025 (routing) = KFS_01 "Uiseong" (paper catalog), the fire that spread
  from Uiseong through Andong, Cheongsong and Yeongyang to Yeongdeok; the routing kit splits it into two regions.
  uljin_2022 = KFS_02 (4 March 2022), not KFS_14 (a separate Uljin fire, 28 May 2022). hongseong_2023 = KFS_05.
  miryang_2022 = KFS_11. GOFER "North Complex" = catalog PNFNorthComplex. "Wapiti_Wapiti" = Wapiti.
- **The paper's development fires are the forecast-v2 fit set.** The paper's 34 train + validation events are
  exactly SPLIT.json's 23 US + 11 KR fit fires, and its 10 test events are exactly US2024 + Korea2025.
- **In the paper catalog, in none of the routing, Caldor/Rim or GOFER registries:** 30 fires: 13 US development fires
  not in GOFER, the 6 US2024 fires, and the 11 Korean fires other than KFS_01, KFS_02, KFS_05 and KFS_11. Nine of them
  (US2024 and KFS_04, KFS_06, KFS_13) are in the forecast-v2 held-out registries; the other 21 are in its fit registry.
  Check: 44 catalog fires = 10 also in GOFER + 4 also in the routing registry + these 30.
- **In a registry, not in the paper:** 18 GOFER fires that are not catalog fires (including Caldor), and Rim 2013.
- **Ten fires are in both the paper catalog and GOFER:** Dixie, River Complex, Antelope, August Complex, North Complex,
  Monument, Creek, SQF Complex, McCash, Red Salmon Complex.
- **Counts that do not match by name.** The paper counts 25 contributing development fires, not 34, and 8 contributing
  test fires, not 10; the non-contributing ones are not identified in git. "273" names two different sets in this
  repo: the US2024 NIROPS intervals and the corridor-router-v8 routing receipts (154 + 78 + 21 + 17 + 3). "33 cases"
  are Korea2025 twelve-hour windows, of which 26 were scored (the 7 unscored are all KFS_01).
- **Cases are not the unit here.** NIROPS survey intervals (US2024's 273, Wapiti's 25), Korea2025's 33 windows and the
  273 routing receipts are not tested as cases: survey gaps are irregular and windows are 12 h, not 5 h and 8 h. Each
  of their fires is tested hour by hour instead, where an hourly arrival product exists.

## The frozen list

Product: GOFER = hourly GOFER perimeters; Choi = Choi et al. 2026 kriged arrival raster (Zenodo 21788344);
DET = FIRMS VIIRS + Himawari AHI detection union (kcf-margin, 25 March 2025 only). Forecast: GFS 0.25 deg or HRRR,
by the order in `PROTOCOL.md` section 3. Where named: P = paper catalog, R = routing registry, CR = Caldor/Rim panel,
G = GOFER, US24 / KR25 = forecast-v2 held-out registries.

### Calibration fires (28, GOFER; the only fires that set anything)

| # | fire | year | named in | forecast | status |
|---|---|---|---|---|---|
| 1 | Kincade | 2019 | G | HRRR | CALIBRATION, tested leave-one-fire-out |
| 2 | Walker | 2019 | G | HRRR | CALIBRATION, LOFO |
| 3 | August Complex | 2020 | G, P (dev) | HRRR | CALIBRATION, LOFO; Choi raster used only in S3 |
| 4 | Bobcat | 2020 | G | HRRR | CALIBRATION, LOFO |
| 5 | CZU Lightning Complex | 2020 | G | HRRR | CALIBRATION, LOFO |
| 6 | Creek | 2020 | G, P (dev) | HRRR | CALIBRATION, LOFO; Choi raster only in S3 |
| 7 | Dolan | 2020 | G | HRRR | CALIBRATION, LOFO |
| 8 | Glass | 2020 | G | HRRR | CALIBRATION, LOFO |
| 9 | July Complex | 2020 | G | HRRR | CALIBRATION, LOFO |
| 10 | LNU Lightning Complex | 2020 | G | HRRR | CALIBRATION, LOFO |
| 11 | North Complex | 2020 | G, P (dev, PNFNorthComplex) | HRRR | CALIBRATION, LOFO; Choi raster only in S3 |
| 12 | Red Salmon Complex | 2020 | G, P (dev) | HRRR | CALIBRATION, LOFO; Choi raster only in S3 |
| 13 | SCU Lightning Complex | 2020 | G | HRRR | CALIBRATION, LOFO |
| 14 | SQF Complex | 2020 | G, P (dev) | HRRR | CALIBRATION, LOFO; Choi raster only in S3 |
| 15 | Slater and Devil | 2020 | G | HRRR | CALIBRATION, LOFO |
| 16 | W-5 Cold Springs | 2020 | G | HRRR | CALIBRATION, LOFO |
| 17 | Zogg | 2020 | G | HRRR | CALIBRATION, LOFO |
| 18 | Antelope | 2021 | G, P (dev) | GFS | CALIBRATION, LOFO; Choi raster only in S3 |
| 19 | Beckwourth Complex | 2021 | G | GFS | CALIBRATION, LOFO |
| 20 | Caldor | 2021 | G, R (Caldor2021), CR | GFS | CALIBRATION, LOFO |
| 21 | Dixie | 2021 | G, P (dev) | GFS | CALIBRATION, LOFO; Choi raster only in S3 |
| 22 | KNP Complex | 2021 | G | GFS | CALIBRATION, LOFO |
| 23 | McCash | 2021 | G, P (dev) | GFS | CALIBRATION, LOFO; Choi raster only in S3 |
| 24 | McFarland | 2021 | G | GFS | CALIBRATION, LOFO |
| 25 | Monument | 2021 | G, P (dev) | GFS | CALIBRATION, LOFO; Choi raster only in S3 |
| 26 | River Complex | 2021 | G, P (dev) | GFS | CALIBRATION, LOFO; Choi raster only in S3 |
| 27 | Tamarack | 2021 | G | GFS | CALIBRATION, LOFO |
| 28 | Windy | 2021 | G | GFS | CALIBRATION, LOFO |

### Korean test fires (15; counts only, never a rate)

| # | catalog id | fire | date (UTC start) | named in | product | forecast | status |
|---|---|---|---|---|---|---|---|
| 29 | KFS_01 | Uiseong (Uiseong-Andong-Yeongdeok) | 2025-03-22 | P (test), KR25, R (Gyeongbuk_2025) | DET on 25 March 00-23 KST (primary that day); Choi for 22-26 March | GFS | TEST |
| 30 | KFS_02 | Uljin | 2022-03-04 | P (dev), R (uljin_2022) | Choi | GFS | TEST |
| 31 | KFS_03 | Gangneung | 2022-03-04 | P (dev) | Choi | GFS | TEST |
| 32 | KFS_04 | Sancheong | 2025-03-21 | P (test), KR25 | Choi | GFS | TEST |
| 33 | KFS_05 | Hongseong | 2023-04-02 | P (dev), R (hongseong_2023) | Choi | GFS | TEST |
| 34 | KFS_06 | Ulju | 2025-03-22 | P (test), KR25 | Choi | GFS | TEST |
| 35 | KFS_07 | Geumsan | 2023-04-02 | P (dev) | Choi | GFS | TEST |
| 36 | KFS_09 | Yanggu | 2022-04-10 | P (dev) | Choi | GFS | TEST |
| 37 | KFS_11 | Miryang | 2022-05-31 | P (dev), R (miryang_2022) | Choi | GFS | TEST |
| 38 | KFS_12 | Yeongdeok | 2022-02-14 | P (dev) | Choi | GFS | TEST |
| 39 | KFS_13 | Buk-gu | 2025-04-28 | P (test), KR25 | Choi | GFS | TEST |
| 40 | KFS_14 | Uljin (May) | 2022-05-28 | P (dev) | Choi | GFS | TEST |
| 41 | KFS_15 | Gunwi | 2022-04-10 | P (dev) | Choi | GFS | TEST |
| 42 | KFS_16 | Suncheon | 2023-04-03 | P (dev) | Choi | GFS | TEST (catalog window 1 h: likely no eligible hour) |
| 43 | KFS_17 | Hapcheon | 2023-03-08 | P (dev) | Choi | GFS | TEST |

### US test fires (19 on Choi rasters; rates allowed for the group of 19, counts only for US2024)

| # | catalog id | year | named in | forecast | status |
|---|---|---|---|---|---|
| 44 | ID-BOF-000683_Wapiti_Wapiti | 2024 | P (test; the paper's evaluation fire), US24 | GFS | TEST |
| 45 | ID-BOF-000904_Goat | 2024 | P (test), US24 | GFS | TEST |
| 46 | ID-BOF-001080_Lava | 2024 | P (test), US24 | GFS | TEST |
| 47 | ID-SCF-240202_RedRock | 2024 | P (test), US24 | GFS | TEST |
| 48 | WA-SES-000173_Pioneer | 2024 | P (test), US24 | GFS | TEST |
| 49 | WY-BTF-002416_FishCreek | 2024 | P (test), US24 | GFS | TEST |
| 50 | CO-ARF-000636_CameronPeak | 2020 | P (dev) | HRRR | TEST |
| 51 | UT-ASF-100340_EastFork | 2020 | P (dev) | HRRR | TEST |
| 52 | MT-BDF-006269_AlderCreek | 2021 | P (dev) | GFS | TEST |
| 53 | MT-BDF-006272_TrailCreek | 2021 | P (dev) | GFS | TEST |
| 54 | MT-LNF-000893_WestLolo | 2021 | P (dev) | GFS | TEST |
| 55 | OR-UMF-000659_GreenRidge | 2021 | P (dev) | GFS | TEST |
| 56 | OR-UMP-000373_RoughPatchCpx | 2021 | P (dev) | GFS | TEST |
| 57 | OR-UPF-000265_Jack | 2021 | P (dev) | GFS | TEST |
| 58 | OR-UPF-000450_DevilsKnob | 2021 | P (dev) | GFS | TEST |
| 59 | WA-OWF-000453_SchneiderSprings | 2021 | P (dev) | GFS | TEST |
| 60 | ID-SCF-022105_Moose | 2022 | P (dev) | GFS | TEST |
| 61 | NM-SNF-000027_HermitsPeak | 2022 | P (dev) | GFS | TEST |
| 62 | OR-WIF-220180_CedarCreek | 2022 | P (dev) | GFS | TEST |

### Not tested

| # | fire | named in | reason |
|---|---|---|---|
| 63 | Rim 2013 | CR | **NOT TESTED.** No hourly arrival product: the repo's sources are 33 irregular airborne-IR perimeters (Hatchett 2025) and FEDS 12-hourly perimeters, neither of which gives a 5 h or 8 h reach at hourly issue times. No issued forecast is reachable for 2013 either (GFS archive here from 2021, HRRR from 2014-07-30). |

## Outside the requested scope (listed so nothing is silently dropped; not tested)

Fires used elsewhere in the repo but not in the paper or the registries named in the brief: the 488 NIROPS part-A
allowlist incidents of kcf-margin's 12-48 h check (`research/harness-2026-11/S-D9/cohort/PART_A_ALLOWLIST_FINAL.csv`);
the S-D9 cohort (704 incidents, parts b-d sealed and not read); the S-D9 pilot fires Blue2, ThreeNine and Line;
HUNT 2019 and LEVELOCK 2019 (`d4_experimental`, artifacts held outside git).
