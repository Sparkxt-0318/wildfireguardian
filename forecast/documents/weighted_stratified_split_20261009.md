# Weighted stratified split — completed verification

The new prepared cache gives training coverage of every categorical input value observed in the development and fixed test data. Training and validation use disjoint cell-hour rows. Test retains the original whole-fire and later-season partition.

## Prepared artifact and scope

The completed cache is `wildfire_burned_area_hourly/probability_model/training_runs/20261009_weighted_stratified_split/prepared_all/`. Its four input files are `metadata.json`, `train.npz`, `validation.npz`, and `test.npz`; `resplit.json` records generation and lineage checks. The original parent remains `training_runs/20261007_1h_kernel_sweep/9x9/prepared_all/`.

The same training, validation, and test NPZ archives are present byte-for-byte in both this workspace and its sibling `wildfire` repository. Metadata retains each workspace's source paths. Existing fitted models and completed experiment results retain their original partition bindings. No full model fit was started for this change.

## Objects and allocation rule

A prepared row is identified by `(event_index, time_utc, row, col)`: one fire, one UTC hour, and one target grid cell. Its input is the complete 9×9 environmental and cumulative-burned context. The binary target `y_i` equals one when the currently unburned target cell becomes burned at the exact next hour. These targets come from retrospective reconstruction and do not represent observed active flames.

Each row has its original inverse inclusion weight `w_i`, a finite value at least one. For any cohort `A`, the reported weighted positive frequency is

\[
\widehat p_A = \frac{\sum_{i\in A} w_i y_i}{\sum_{i\in A} w_i}.
\]

The denominator is represented population weight. It is distinct from the number of sampled rows. A contact cohort requires at least one already-burned, off-center cell in its stated centered input support.

Only original training and validation rows enter allocation. The algorithm uses seed 7 and strata defined by binary next-hour outcome, the smallest current-contact support, and categorical-presence signatures in the 3×3, 5×5, 7×7, and 9×9 environmental crops. Thus it balances positive and negative weight separately while preserving the supported input distinctions.

Within each stratum, seeded random row ordering and bounded one-row moves or one-for-one swaps approximate a 20% validation population-weight target. This is a finite heuristic; it does not guarantee an exact weighted optimum or equal row-selection probabilities. Every stratum with at least two rows retains rows on both sides. All 13 singleton strata remain in training. There are 163 strata. Original features, labels, identities, and inclusion weights are retained.

## Realized partitions and categorical coverage

| Partition | Sampled cell-hour rows | Contributing fires |
|---|---:|---:|
| Training | 199,185 | 25 |
| Validation | 49,900 | 25 |
| Test | 61,965 | 8 |

The pooled development population contains 249,085 sampled rows. Validation receives 20.005804% of its represented population weight, and training receives the remaining 79.994196%. Training and validation share the 25 contributing fires but share no cell-hour identity. All ten original test event declarations remain exclusively test; two of those events contribute no prepared rows.

The categorical environmental input in this cache is the biome class, encoded with fourteen fixed one-hot vocabulary channels. Five values actually occur:

| Code | Meaning |
|---:|---|
| 4 | Temperate Broadleaf & Mixed Forests |
| 5 | Temperate Conifer Forests |
| 8 | Temperate Grasslands, Savannas & Shrublands |
| 12 | Mediterranean Forests, Woodlands & Scrub |
| 13 | Deserts & Xeric Shrublands |

Original training lacked class 8, which occurred in original validation context patches. New training contains all five observed values across full patches and within contact-eligible 3×3, 5×5, 7×7, and 9×9 inputs. This was independently recomputed from the actual output environmental arrays. Every value seen in validation or test is covered by training for each support. The native 3×3 validation cohort does not contain class 8; retaining its rare signatures in training satisfies the requested training coverage.

Coverage means coverage of individual observed categorical values. It does not imply that every possible category combination, continuous-input range, or fire condition occurs in training. Unobserved vocabulary classes remain defined but are not claimed to have training examples. A future cache with a test-only category fails coverage checks rather than silently transferring test rows into training.

## Weighted positive frequencies

| Cohort | Training | Validation | Fixed test |
|---|---:|---:|---:|
| All prepared cell-hours | 0.186826% | 0.186689% | 0.340179% |
| Common / native 3×3 contact | 2.689862% | 2.689217% | 8.666407% |
| Native 5×5 contact | 1.678959% | 1.678025% | 5.657207% |
| Native 7×7 contact | 1.274019% | 1.273134% | 4.330056% |
| Native 9×9 contact | 1.053227% | 1.052498% | 3.518606% |

On the common 3×3 cohort, the old split's training and validation frequencies were 2.805919% and 1.914941%. The new values are approximately equal. This removes the earlier prevalence mismatch from that training/validation comparison. It does not guarantee a particular ordering of model losses; environmental difficulty and within-fire spatial or temporal dependence remain relevant.

## Test separation and integrity

The fixed test seasons remain Korea 2025 and United States 2024. Development data comes from the original earlier training and validation seasons. No test fire contributes a training or validation row. Test labels do not enter allocation, and test environmental inputs are used only for categorical-coverage acceptance checks after allocation. Test outcome frequencies above are descriptive audits computed after allocation; they do not select the split.

The original and new `test.npz` SHA-256 is exactly:

```text
e36391d77a6e5909ad4dfae8de4d14c50d6da28a4caf18409f1f0b19cbef8e0e
```

Whole-fire and later-season separation protects the existing test boundary. It does not assert that fire regions, environmental contexts, or all input distributions are geographically disjoint. Validation measures held-out cell-hours within represented fires; neighboring cells, nearby hours, and overlapping contexts may cross training and validation.

## Implementation and verification

Fresh preparation now defaults to `weighted-cell-hour`, with a separate split seed and negative-sampling seed. `--split-policy season` retains the historical extraction design. `resplit` derives this cache from an existing prepared cache without repeating raster processing. The four direct kernel-search families use the new cache and fresh experiment directories; original-cache portable recovery continues to enforce its historical checksums. Reports and independent verifiers distinguish row separation from fire separation, and reject inconsistent original test declarations.

The final regression command passed **827 tests with 8 skipped** in 64.63 seconds. Its 272 warnings are plotting dependency deprecations. Tests include weighted allocation, categorical coverage, malformed partition declarations, duplicate rows, original-test isolation, adapters, search/report contracts, a small training fixture, and cleanup on simulated Windows file locks.

An independent audit checked source and output archive checksums; exact pooled identities, labels, weights, and burned patches; per-support frequencies; actual categorical coverage; and byte-identical code, tests, and NPZ mirrors. Generation verified every row's environmental arrays in bounded chunks and all 486 source-file manifest hashes. A final real-cache multiscale setup verified those 486 sources again and created a valid cell-hour protocol without invoking training.

The machine-readable companion `weighted_stratified_split_20261009.json` records exact frequencies, independent coverage, archive hashes, final reviewed source hashes, and verification results. Its source hashes describe the reviewed implementation; generation timestamps remain those in the original `resplit.json` audit.
