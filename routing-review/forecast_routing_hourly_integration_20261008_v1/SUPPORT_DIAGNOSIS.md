# Sparse forecast support diagnosis

Date: 8 October 2026, Asia/Shanghai. The original model-bound raster loader and original safe predictor were rerun for the three KFS_02 cutoffs. Every original numeric snapshot array, including NaN locations, exactly matches the preserved previous packet. The portable numeric-input workflow also reproduces all arrays exactly at all three cutoffs. Machine-readable evidence: `results/native_reproduced/SUMMARY.json` and `results/hazard_source_verification.json`.

## Actual target and mask chain

`wildfire_burned_area_hourly/pytorch_loader/dataset.py:350-473` reads the published arrival raster and returns current labels `arrival<=elapsed` with `burned_area_valid=arrival_valid`. The training target in `probability_model/prepare_training.py:87-217` is `arrival<=elapsed[next_hour]` for a current unburned, valid full-context at-risk cell. The current raster and target are retrospective reconstruction estimates. The source README states final perimeters and full VIIRS/Himawari detection histories inform this kriging product; no independent Korean field arrival validation is established in the supplied input.

The checkpoint's eligibility is `at_least_one_burned_neighbor`, kernel 5×5. `NormalizedBurnModel._contact` excludes the central cell and computes local burned-neighbor contact. `TrainedDirectBurnModel.forward` intersects original validity with this contact or the known-already-burned override. Environmental context requires all trained channels to be finite/valid over the 5×5 neighborhood. Burned context also requires the full neighborhood known; unknown outside-raster boundary remains unknown. Known already-burned cells receive first-new-event q=0. This is a target-population rule, not proof that non-contact cells cannot ignite.

`native_forecast.py` reproduces these actual intermediate masks and verifies equality against the original prediction validity. The following categories are disjoint and exhaust the 3,596 native raster cells; precedence is current-label support, already-burned override, environmental context, burned context, then target eligibility.

| Category | 03:00Z | 06:00Z | 12:00Z |
|---|---:|---:|---:|
| Current label unavailable/outside retrospective reconstruction | 1,659 | 1,659 | 1,659 |
| Known already burned; q=0 override | 1 | 104 | 198 |
| Known unburned; environmental 5×5 context incomplete | 137 | 137 | 137 |
| Known unburned; burned 5×5 context incomplete | 342 | 342 | 342 |
| Known unburned; no burned neighbor eligibility | 1,433 | 1,209 | 1,082 |
| Known unburned; eligible full context | 24 | 145 | 178 |
| **Original probability supported** | **25** | **249** | **376** |
| **Original probability unknown** | **3,571** | **3,347** | **3,220** |

There are 1,937 valid retrospective arrival cells, 2,698 full environmental-context cells and 1,467 full burned-context cells at each cutoff. Weather temperature/wind channels and slope have no native missing cell in these samples. Tree-cover predictors are missing at 400 cells; each of the 14 biome one-hot indicators shares a 405-cell invalid group. Unknown biome context is retained as unknown, not assigned a class. Exact per-channel counts and diagnosis masks are saved in native JSON/NPZ.

## No zero-source repair is justified

No physically justified non-emitting mask was supplied. Cells outside the reconstructed final mask are absent labels, not measured unburned/no-fuel land. No-neighbor eligibility is a model domain restriction; missing vegetation/biome input is a predictor gap; neither establishes a non-emitter. Missing probability cannot be converted into zero. The existing model's finite-cell radiation operator has nonnegative contributions from the entire raster, so unresolved emitters affect remote receiver cells. All three original complete expected-flux rasters therefore remain entirely unknown; known-source heat is a partial contribution only.

The executed diagnosis found no demonstrated loader/assembly bug to repair: safe original loader masks reproduce the exact original validity, all present feature intervals end by cutoff, and output equivalence is exact. More coverage would require different input support/model eligibility or additional scientifically justified source exclusion, each a distinct method change. This candidate does not widen eligibility or silently fill absent predictors.

Research mode assigns missing future q=0.5, with frozen q=0/q=1 sensitivity cases; strict mode keeps absence unresolved. These assignments create assumption-conditional source support, not observed support. Current-active state is absent in the original export. Research current states are explicitly assumed; the already-burned mask alone does not identify active or cold fire.

## Source verification and graph coverage

Tier 2 graph project `mentor-forecast-integration-20261007`, generation `2026-10-07T15:42:51Z`, supplied exact snippets for loader, inference, training preparation and radiation source paths. Coverage checks reported no recorded issue with matching metadata for those Python paths; that is a best-effort signal, not proof of completeness. `environmental_data` and `probability_model/training_runs` are excluded graph subtrees. We directly read KFS_02 grid/config and actual source rasters through the original loader, and safe-loaded the checkpoint contract instead of relying on graph omission. Input provenance hashes cover arrival and environmental layers actually used.

The original KFS_02 grid is EPSG:5179, 62 rows×58 columns, north-up affine `[375,0,1149000,0,-375,1912125]`. It is paired only with the supplied Uljin graph. Portable numeric inputs preserve original tensor values/channel order/masks. The original checkpoint loaders use `torch.load(weights_only=True)`; no unsafe pickle fallback or credential data is bundled. NPZ reads use `allow_pickle=False`.
