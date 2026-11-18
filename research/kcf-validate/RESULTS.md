# kcf-validate: what could be checked against records the model never used

**Model output on reconstructed inputs or synthetic truth. Not what happened to people. No claim about what any official should have done.**

Rules frozen first: [PROTOCOL.md](PROTOCOL.md) (commit `1a6a5a7`; amendments 1-2 dated and made before the outcomes they touch). Numbers: [numbers.json](numbers.json).
Skipped sources: [SKIPPED.md](SKIPPED.md). Prospective log: [PROSPECTIVE_LOG.md](PROSPECTIVE_LOG.md).

## Headline, in four sentences

1. Three of the six sources could not be obtained (KEC traffic, 재난문자, NIST Camp Fire): their hosts are refused by this container's network policy, so **no REPORTED row of `research/kcf-roadcut/validation_table.csv` was replaced by an official record (0 of its 29 rows: 13 road, 3 village-arrival, 13 order).**
2. The one independent satellite record I could get is Sentinel-2 on **24 March**, day 3, not the 25 March window of the replay. On the frozen map the reconstruction's reached area agrees with it (POD 0.88-0.91) while over-reaching (FAR 0.43-0.44), **but the burned-area map itself changes more than 13-fold with the dNBR convention (26-352 km²) and the verdict with it**, and the interval tested contains no detected fire growth, so this scene does not test the 5 h / 8 h margin.
3. In a twin experiment (my own simulator as truth, 12 fires × 2 issue times, 영덕), the unchanged pipeline fed only synthetic detections **missed 12 of 221 true road cut-offs (5.4 %; 12 of 118 = 10.2 % where the cut had to be forecast)** and raised **146 false cut-offs** among 1,939 places the truth never cut within 8 h (7.5 %).
4. Perfect detections change that very little (11 misses instead of 12), so in this twin the loss comes from the reach margin, not from what the satellites see. That holds for this simulator only.

## Validation table (one table)

n counts are cells, place-pairs or records as stated. "Miss" = the record shows it, the model does not. Status NOT OBTAINED means no number exists, not a pass.

| # | Source / comparison | n | Result, as measured | Misses and limits |
|---|---|---|---|---|
| 1 | KEC 15-min section traffic, 22-27 Mar 2025 | - | **NOT OBTAINED** | `data.ex.co.kr` refused (CONNECT 403). No closure time or outbound surge derived. |
| 2 | Official 재난문자 send times, 22-27 Mar 2025 | - | **NOT OBTAINED** | `safekorea.go.kr`, `data.go.kr`, `apis.data.go.kr`, `mois.go.kr` refused. Text times in kcf-replay stay REPORTED. |
| 3a | Sentinel-2 (24 Mar 02:17 UTC) burned map vs **Choi TOA** reached at that time (model input) | 12,303 assessable cells (567 burned) | hits 513, misses 54, false alarms 408, correct negatives 11,328; **POD 0.905, FAR 0.443, CSI 0.526** | 54 burned cells not reached. Primary map: raw DN, dNBR ≥ 0.10 (frozen). 6,420 of 18,723 cells not assessable (east half cloud/outside tile). Whether Choi used Sentinel-2 is unknown to me. |
| 3b | same vs **replay known area** (FIRMS+AHI discs before t_S) | 12,303 | hits 501, misses 66, FA 378, CN 11,358; **POD 0.884, FAR 0.430, CSI 0.530** | 66 burned cells outside every detection disc. |
| 3c | same vs **MEASURED 8 h zone** issued 23 Mar 18:00 UTC (class quiet, R8 3.5 km) | 12,303 | hits 541, misses 26, FA 2,288; **POD 0.954, FAR 0.809, CSI 0.189**. Newly burned cells inside zone: **40 of 66 (0.61)**; 26 beyond R8 | None of the 66 was seen by FIRMS/AHI between issue and t_S (exploratory, below): mapping noise or earlier undetected burn, not demonstrated spread beyond R8. Zone ends 17.5 min before t_S. |
| 3d | same vs **MEASURED 5 h zone** (issued 21:00 UTC, R5 2.6 km) | 12,303 | hits 540, misses 27, FA 1,867; POD 0.952, FAR 0.776, CSI 0.222. Newly burned inside zone 39 of 66 (0.59) | as 3c |
| 3e | Map sensitivity, same comparisons | 4 maps | Burned area 79.7 (raw 0.10), 26.2 (raw 0.27), **352.3** (offset 0.10), 25.6 km² (offset 0.27). Choi POD 0.905 / 0.995 / **0.150** / 0.632; 8 h zone POD 0.954 / 1.000 / 0.337 / 0.791 | The offset-corrected 0.10 map (amendment 1, sensitivity) calls 2,505 cells burned; Choi and the discs reach ~900 cells. Which map is right is not decided here. |
| 4 | NIST TN 2135 / TN 2252 Camp Fire; road layer on Paradise | - | **NOT OBTAINED** | `nvlpubs.nist.gov`, `www.nist.gov`, `tsapps.nist.gov`, `data.nist.gov` refused. No Paradise run (no Paradise road graph in the repository either). |
| 5a | **Twin, cells** (not burning at T, true arrival ≤ T + 8 h): system closure later than true arrival or absent | 20,480 cell-instances, 24 pairs | **1,129 late (5.5 %)**; ≥ 15 min late 1,039; ≥ 60 min late 858 (4.2 %); absent 686 (3.3 %). Seed-bootstrap 95 %: 2.4-9.0 % | Pairs are not independent. 56,589 cell-instances the system closes within 8 h that the truth does not reach (false reach) against 20,480 true. |
| 5b | **Twin, places**: missed last-road cut-off (truth CUT; system NOT CUT or later) | 221 true-CUT place-pairs (of 2,160) | **12 missed (5.4 %)**, of which 7 system-absent; ≥ 15 min: 12; ≥ 60 min: 8. Seed-bootstrap 95 %: 2.0-13.9 % | Truth "cut inside horizon" 12 of 118 (**10.2 %**); truth "already cut at issue" 0 of 103. Misses by seed: s0 2/14, s1 1/11, s6 1/20, s7 2/3, s8 1/67, s9 3/8, s11 2/12; none in s2, s3, s5, s10 (s4 had no cut). |
| 5c | Twin, places: **false cut-off** (system CUT, truth NOT CUT) | 1,939 truth-NOT-CUT place-pairs | **146 (7.5 %)** | 106 at issue + 24 h, 40 at + 36 h. The zone is wider than the simulated spread most of the time. |
| 5d | Twin, cut-off **time error** (system − true), places CUT in both | 214: 111 forecast + 103 already cut at issue | **Forecast part (n = 111): median −176 min (system cuts earlier), p10 −321, p90 −26, range −439 to +166; 106 early (85 by ≥ 60 min), 5 late.** Already-cut part (n = 103): exactly 0 in all 103 | Pooled median and p90 are 0.0 only because of the 103 trivial places; do not quote them. Village fire-arrival error, forecast part (n = 106): median −188 min, p10 −334, p90 −27. |
| 5e | Twin **control** (perfect detections, same pipeline) | 20,480 cells; 221 places | 946 late cells (4.6 %, bootstrap 2.3-7.0 %); **11 missed** cut-offs (5.0 %); 145 false cut-offs | Detection loss is small next to the margin rule's. |
| 6 | Prospective log | - | **Started, no entry**: no active Korean fire identified | Two web searches only; FIRMS and KFS unreachable, absence unverified. Entry maker dry-run on 2025 data works. |

## What each source did and did not show

**Sources 1, 2, 4 (not obtained).** Each host answers a plain HTTPS request from this container with 403 on CONNECT (ten hosts checked, same result), and the separate fetch tool failed on DNS. I did not look for a mirror, an aggregator copy, a key or a login, and I did not change the network policy. Whether these sites would have had the data, or would have needed an account, is unknown. If the hosts are allow-listed, sources 1, 2 and 4 can be re-run: the freeze for them is in the protocol's §1 and nothing was compared. The 13 road rows and 13 order rows in kcf-roadcut remain REPORTED, with their errors as published there; none was upgraded.

**Source 3 (Sentinel-2).** Only one scene pair lies inside the fire and is usable: 24 March 02:17 UTC (11:17 KST), tiles 52SDF (full) and 52SEF (56 % cloud). 27 March is 99.99 % cloud, 22 March is partial and pre-fire. GK-2A is not reachable; Landsat was not used (its AWS bucket is requester-pays, which I know but did not test, and no payer account was given). Reading the table:
* The reconstruction (Choi) and the discs agree with the satellite map about as well as each other (3a, 3b). Among assessable cells the model reaches 921 (Choi) or 879 (discs) against 567 burned: it **over-reaches by about 400 cells** and **misses 54-66 burned cells**. That is at the frozen threshold. At the other three map definitions the numbers are 3e: POD between 0.15 and 0.995. **I cannot say the reconstruction is validated by this scene.**
* The MEASURED zones (3c, 3d) were applied at issue times the replay did not use (it issued on 25 March only), as an extension of its rule. Coverage of newly burned cells is 0.61 and 0.59, against the 0.90 coverage that alpha 0.10 targets in kcf-margin. The exploratory check (below) says why this is not a finding about spread: none of the 66 cells was seen by FIRMS/AHI between the issue time and t_S, and 27 of them are inside Choi's reached area at t_S.
* Exploratory, not frozen (`out/s3_exploratory.json`, written after the first output): 0 detection discs from FIRMS/AHI touch a "newly burned" cell between 23 Mar 18:00 UTC and t_S; the 26 cells beyond R8 are in the west of the lattice (columns 6-65) and are known neither to the discs nor to Choi at t_S. The 23-24 March night is quiet in the detections, so this scene has little power to test the 5 h / 8 h margin. The test of the margin on a day with growth needs a scene on 25-26 March, and none exists in the open bucket (27 March is cloud).

**Source 5 (twin).** Frozen design: protocol §3. The truth simulator (`twin/twin_lib.py`) is minimum-travel-time spread with a wind-driven ellipse, diurnal speed, a correlated speed field, one wind shift and random spotting. It is **not FARSITE** and is not fitted to the 2025 fire. Head-fire speed v0 (at the diurnal peak, before the spatial speed multiplier; 35 % of it at night) was 1.0-4.3 km/h across the 12 fires. The system's known area comes only from synthetic detections (passes at the real FIRMS time-of-day clusters, 20 % of passes lost to cloud, per-cell detection probability 0.70 VIIRS / 0.35 MODIS, AHI-like 5 × 5-cell blocks). The system is the repository's own MEASURED arm, with the twin's re-implementation of the raster builder asserted equal to the committed example raster on the real data before use, then `product/wfg-roadlayer` for every place. The truth reference is the same road rule fed the true arrival, so the table measures the **cost of not knowing the fire**, not the validity of the road rule against real roads.
* The class assigned from detections was "quiet" in 11 of 12 pairs at + 36 h and "slow" or "running" in 8 of 12 at + 24 h: R8 was 3.5 km in most of the later hours (0.44 km/h averaged over 8 h), while the simulated head speeds are 0.4-4.3 km/h. This is consistent with the misses coming from a zone that is too narrow for the faster fires and the false cut-offs from one that is too wide for the slower ones; I did not test that explanation.
* The system's cut-off time is mostly **earlier** than the true one (5d): the late cases are the 12 misses (7 of them no cut at all). The 12 misses are concentrated in 7 of 12 fires; the pooled percentage hides that. The seed-level bootstrap (12 seeds, one simulator, one region) gives wide intervals; read them as description, not as a population claim.
* Assumed detection values (probabilities, cloud rate, 2 h flaming duration, AHI on the whole lattice, latency 0) are my choices and are optimistic on coverage and latency. A different simulator or different detection assumptions would give different rates.

**Source 6.** `PROSPECTIVE_LOG.md` holds the procedure (commit and push before the outcome time, hash recorded, scoring rule frozen, no later edits) and the entry maker `prospective/make_entry.py`. A dry run on the 2025 FIRMS files (labelled DRY RUN) works and is not an entry. The log has **no entry**: no active Korean fire turned up in two web searches, but FIRMS and KFS cannot be read from here, so this is not a statement that no fire is burning.

## Reproduce

```bash
python3 tools/fetch_routing_inputs.py            # routing inputs (SHA-verified)
python3 research/kcf-validate/twin/run_twin.py check
python3 research/kcf-validate/twin/run_twin.py make WORK && python3 research/kcf-validate/twin/run_twin.py run WORK
python3 research/kcf-validate/twin/run_twin.py score WORK research/kcf-validate/out && python3 research/kcf-validate/twin/summarize_twin.py research/kcf-validate/out
python3 -I research/kcf-validate/satellite_extent.py S2_DIR OUT     # scenes: sha256 in out/s3_scene_sha256.txt
python3 research/kcf-validate/build_numbers.py
```

The roadlayer runs take about 50 s each (4 cores), 72 in all; Sentinel-2 files are 12 COGs from the open bucket `sentinel-cogs`.
