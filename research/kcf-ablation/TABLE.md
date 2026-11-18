# TABLE: what each component adds, fire by fire

Frozen layout: [LAYOUT.md](LAYOUT.md). Values: [cells.json](cells.json) (every cell carries file, command and reason). Reading: [READING.md](READING.md).
Main at `a697d14`. **[R]** = RECORDED (committed file, cited in cells.json), **[N]** = NEW RUN (command in cells.json), **– (code)** = NOT RUN, reason code in §Reasons.
Budget triples are the three dose budgets **92 / 105 / 290 TDU**, side by side; none is chosen as the submission. A single number means the same value at all three budgets. n/a = no place changed (or no value exists). Metrics per line: decided · routes found · places whose leave-by changes (changed of places with a leave-by in row 1) · median change s · largest change s · run time s.
Versions V1–V5 are different inputs and are never added; the lines inside a cell are separate versions (LAYOUT §1).

| row | **F1** Gyeongbuk 2025 (KFS_01) | **F2** Uljin 2022 (KFS_02) | **F3** Hongseong 2023 (KFS_05) | **F4** Miryang 2022 (KFS_11) | **F5** Caldor 2021 |
|---|---|---|---|---|---|
| **1. full system as submitted** | **V1** 8/8 [R] · 7 [R] · base [N] · base [N] · base [N] · 8.603 [R]<br>**V2** 9722/9722 [N] · 7952 / 7955 / 7958 [N] · base [R] · base [R] · base [R] · 3016.0 [N]<br>**V3** NOT RUN (NR-V3JOBS)<br>**V5** 78/78 [R] · 30 [R] · base [R] · base [R] · base [R] · 1.859 [R] | **V1** 4/4 [R] · 4 [R] · base [N] · base [N] · base [N] · 5.599 [R]<br>**V5** 154/154 [R] · 131 [R] · base [R] · base [R] · base [R] · 1.18 [R] | **V1** 4/4 [R] · 2 [R] · base [N] · base [N] · base [N] · 3.875 [R]<br>**V5** 21/21 [R] · 9 [R] · base [R] · base [R] · base [R] · 0.392 [R] | **V1** 4/4 [R] · 2 [R] · base [N] · base [N] · base [N] · 3.416 [R]<br>**V5** 17/17 [R] · 17 [R] · base [R] · base [R] · base [R] · 0.328 [R] | **V5** 3/3 [R] · 2 [R] · base [R] · base [R] · base [R] · 1.379 [R] |
| **2. forecast → persistence** | **V1** 8/8 [N] · 7 [N] · 1/7 [N] · 527 [N] · 527 [N] · 31.24 [N]<br>**V2** 9722/9722 [N] · 8021 [N] · 21/507 [N] · 362 [N] · 1744 / 1717 / 1581 [N] · 1686.7 [N]<br>**V3** NOT RUN (NR-V3PERSIST)<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 4 [N] · 0/4 [N] · n/a [N] · n/a [N] · 3.78 [N]<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 2 [N] · 0/2 [N] · n/a [N] · n/a [N] · 0.26 [N]<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 2 [N] · 0/2 [N] · n/a [N] · n/a [N] · 0.58 [N]<br>**V5** NOT RUN (NR-V5) | **V5** NOT RUN (NR-V5) |
| **3. forecast → measured reach margin** | **V1** NOT RUN (NR-MARGIN)<br>**V2** NOT RUN (NR-MARGIN)<br>**V3** NOT RUN (NR-MARGIN)<br>**V5** NOT RUN (NR-V5) | **V1** NOT RUN (NR-MARGIN)<br>**V5** NOT RUN (NR-V5) | **V1** NOT RUN (NR-MARGIN)<br>**V5** NOT RUN (NR-V5) | **V1** NOT RUN (NR-MARGIN)<br>**V5** NOT RUN (NR-V5) | **V5** NOT RUN (NR-V5) |
| **4. heat closure off** | **V1** 8/8 [N] · 7 [N] · 0/7 [N] · n/a [N] · n/a [N] · 30.35 [N]<br>**V2** 9722/9722 [N] · 7955 / 7958 / 7967 [N] · 1/507 / 1/507 / 4/507 [N] · 268 / 276 / 41 [N] · 268 / 276 / 317 [N] · 1940.1 [N]<br>**V3** NOT RUN (NR-V3HEATOFF)<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 4 [N] · 0/4 [N] · n/a [N] · n/a [N] · 2.92 [N]<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 2 [N] · 0/2 [N] · n/a [N] · n/a [N] · 0.23 [N]<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 2 [N] · 0/2 [N] · n/a [N] · n/a [N] · 0.43 [N]<br>**V5** NOT RUN (NR-V5) | **V5** NOT RUN (NR-V5) |
| **5. thermal-dose budget off** | **V1** 8/8 [N] · 7 [N] · 0/7 [N] · n/a [N] · n/a [N] · 26.21 [N]<br>**V2** 9722/9722 [N] · 7958 [N] · 4/507 / 4/507 / 3/507 [R] · 222.5 / 191.5 / 21 [R] · 453 / 252 / 51 [R] · 494.8 [N]<br>**V3** – (NR-V3JOBS) · – (NR-V3JOBS) · 22/286 / 21/286 / 16/286 [R] · 301.0 / 268.0 / 117.5 [R] · 529 / 521 / 257 [R] · 7333.5 [R]<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 4 [N] · 0/4 [N] · n/a [N] · n/a [N] · 2.44 [N]<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 2 [N] · 0/2 [N] · n/a [N] · n/a [N] · 0.22 [N]<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [N] · 2 [N] · 0/2 [N] · n/a [N] · n/a [N] · 0.35 [N]<br>**V5** NOT RUN (NR-V5) | **V5** NOT RUN (NR-V5) |
| **6. corridor router → reference router** | **V1** 5/8 [R] · 5 [R] · – (NR-LB) · – (NR-LB) · – (NR-LB) · 8.589 [R]<br>**V2** NOT RUN (NR-REFV2)<br>**V3** NOT RUN (NR-V3JOBS)<br>**V5** NOT RUN (NR-V5) | **V1** 4/4 [R] · 4 [R] · – (NR-LB) · – (NR-LB) · – (NR-LB) · 5.748 [R]<br>**V5** NOT RUN (NR-V5) | **V1** 2/4 [R] · 2 [R] · – (NR-LB) · – (NR-LB) · – (NR-LB) · 11.367 [R]<br>**V5** NOT RUN (NR-V5) | **V1** 2/4 [R] · 2 [R] · – (NR-LB) · – (NR-LB) · – (NR-LB) · 9.552 [R]<br>**V5** NOT RUN (NR-V5) | **V5** NOT RUN (NR-V5) |
| **7. deadline field → recorded per-departure checks** | **V1** NOT RUN (NR-NOSWEEP)<br>**V2** 9239/9722 [R] · 7771 [R] · 154/507 [R] · 348.0 / 348.0 / 349.0 [R] · 1558 [R] · 147900 [R]<br>**V3** NOT RUN (NR-V3JOBS)<br>**V5** NOT RUN (NR-V5) | **V1** NOT RUN (NR-NOSWEEP)<br>**V5** NOT RUN (NR-V5) | **V1** NOT RUN (NR-NOSWEEP)<br>**V5** NOT RUN (NR-V5) | **V1** NOT RUN (NR-NOSWEEP)<br>**V5** NOT RUN (NR-V5) | **V5** NOT RUN (NR-V5) |

## Fires with no road inputs (all seven rows NOT RUN, every cell)

| col | fire | group | rows 1–7 |
|---|---|---|---|
| F6 | Wapiti 2024 | US held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| F7 | Goat | US held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| F8 | Lava | US held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| F9 | Red Rock | US held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| F10 | Pioneer | US held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| F11 | Fish Creek | US held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| F12 | Sancheong (KFS_04) | Korean held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| F13 | Ulju (KFS_06) | Korean held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| F14 | Bukgu (KFS_13) | Korean held-out forecast cohort | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| P-A | 28 GOFER fires | margin calibration population | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| P-B | 488 NIROPS incidents | margin check population | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |
| P-C | SMOKE catalog, 44 events | training / validation population | NOT RUN (NR-NOGRAPH) in all seven rows and all six metrics |

## Reasons

* **NR-NOGRAPH**: No road graph, places or missions exist for this fire in the repo or in the fetched inputs (it is a forecast-scoring, calibration or training fire); the routing metrics are undefined.
* **NR-MARGIN**: LAYOUT §7: the frozen margin rule exists for 5 h / 8 h horizons on known-perimeter inputs; the forecast arm exists at a 1-hour horizon on other issue times (V1, V2) or as retrospective scenarios (V3); V4 has no forecast arm. A run needs a rule mapping R to a 1-hour hazard that would be chosen after the full-system outputs are known.
* **NR-NOSWEEP**: No recorded per-departure sweep exists for the V1 missions (committed per-departure checks cover the six 2025 planner caches only), so there is nothing to substitute for the field.
* **NR-LB**: The router answers one departure per request; it produces no leave-by.
* **NR-V3JOBS**: The V3 summaries are per place and place-run; job-level decided / route counts are not committed.
* **NR-V3HEATOFF**: Heat closure off with the dose budget kept has no committed contrast, and the V3 inputs are not in the repo tree (rebuilt from three other branches by scripts/fdyn_rebuild_inputs.sh; the batch takes about 1 h 40 min with 3 workers per dwell mode) — not attempted.
* **NR-V3PERSIST**: V3 hazards are retrospective reconstructions (kriged, FIRMS, envelope), not forecasts; there is no forecast to replace.
* **NR-V5**: The v8 campaign has one arm and no ablation arms; only its own receipts exist.
* **NR-REFV2**: No reference-router sweep is committed for V2; the planner caches were produced by the proposed router only.
* **NR-CALDOR**: Caldor 2021 appears only in the v8 receipts; its graph is not in the fetched inputs, so no field or router can be run.
* **NR-V4**: kcf-replay has margin arms only (R-based); it contains no forecast arm and no full-system arm to compare with.
* **NR-V3RUN**: Not tabulated at this unit in a committed file.

## Footnotes

1. **Mixed versions across a row.** Row 1 mixes V1 (paper router outcomes, RECORDED, Apple host) with V2/V3/V5 lines; they are separate lines, never summed. Row 5 mixes V1 (NEW RUN), V2 (RECORDED leave-by) and V3 (RECORDED).
2. **Host.** NEW RUN times are from this container (Linux x86_64, 4 cores, Python 3.13.18, numpy 2.5.3); RECORDED times are from the host named in each file. They are not compared with each other (F-3.1 RESULTS §5 measures this host at 2.6–2.8× slower than the Mac).
3. **Leave-by definitions differ by version** (LAYOUT §4): V1 uncapped exact; V2 exact capped at the planner range; V3 range over timing variants, earliest edge. Nothing is pooled across them.
4. **Row 7 base.** The recorded checks carry no heat closure and no dose budget; V2 row 7 therefore differs from row 1 in three ways. See the line in cells.json.
5. **V1 base check.** The contact-only arm of run_v1.py returns P1's 15 routes and 5 refusals at the missions' own departures (cells.json → checks); the full arm differs from it in no mission.
6. **Row 6 leave-by.** Not produced by a one-departure router (NR-LB). Arrival-second agreement on jointly routed executions is in the cell notes.
7. **Dose budget in P1.** P1's own cumulative-exposure limit (old 0.703 kW/m² law; 200-execution ablation `research/routing/final-input-ablation/`) is a different component from the kcf-heat TDU budget in row 5 and is not used for that row.
8. **V2 NEW RUN times.** The three V2 arms (full, persistence, heat_off) ran at the same time on 4 cores, so each time is longer than a solo run. The full arm also computes the contact-only field used for the 7,970-job check, and its time includes it. V2 arms were run without the witness pass that kcf-heat's committed C.4 files include; their leave-by values for the full arm equal the committed ones at all 4,240 compared values.
9. **Persistence in the forecast-skill sense** (Brier) is in READING.md as context only; it is not one of the cell metrics.
