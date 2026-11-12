# WSTS 2019 labels-only persistence replication: result

**Verdict: MATCH.** The computed persistence AP is 0.10486 against the published 0.105, so |Δ| = 0.00014, inside the MATCH band (≤ 0.005).

The tolerance (`WSTS_DESIGN.md` §6) was committed at b28a518f, 2026-11-12T11:46:01Z. That is before the run's aggregate output was written (about 12:21Z), and the AP exists only in that aggregate.

## What was run
- **Data:** WSTS (Zenodo record 8006177), all 74 fires of 2019. Each fire's tif was streamed by HTTP range read, scored, and deleted immediately. No tif data is kept or committed.
- **Scope:** development-only; labels and metadata only, with no covariates or model.
- **Script:** `wsts_persistence.py` (90c34a7e):
  - target = band 22 (active fire) at day index 5 onwards;
  - persistence forecast = the previous day's active-fire mask;
  - centre crop to a multiple of 32.
- **Output:** `WSTS_2019_PERSISTENCE.json`, sha256 42afa89a…9735. It holds counts and per-fire tif digests only.

## Figures
| | value |
|---|---|
| fires (with targets) | 74 (74) |
| pixels scored | 76,216,320 |
| positives | 42,174 (base rate 0.000553) |
| persistence recall / precision | 0.3238 / 0.3227 |
| persistence AP | **0.10486** (published 0.105) |
| score-B new-burn cells / positives | 75,903,123 / 24,706 (base rate 0.000325) |

**Consistency check.** For a binary score, AP = r·p + (1 − r)·base. That gives 0.3238 × 0.3227 + 0.6762 × 0.000553 = 0.10486, which equals the reported AP.

## What this does and does not establish
- **It does establish** that the adapter reads the WSTS 2019 active-fire labels, and the published persistence protocol, the way the dataset authors did. It may be used for label-level work.
- **It does not establish** anything about covariates, models, or other years.
  - The full model check stays **deferred** under the conditions in `WSTS_DESIGN.md`: the part-c prerequisites frozen and rebuilt, no Open-Meteo quota or builder time taken from part c, it ranks below the part-a cross-validation, and the owner's separate approval with a price.
  - 2018 and any covariate rebuild are not approved.

## Not verified
- This has not yet been independently rerun. A rerun streams about 5.2 GB.
