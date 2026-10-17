# Route-Check API replay on a cloud Linux VM (2026-10-17)

**Host:** a cloud container with 4 vCPU (Intel Xeon @ 2.10 GHz, 1 thread per core), Linux 6.18 x86_64, Python 3.12.3,
numpy 1.26.4 and GNU time 1.9. **This is not the evaluated host.** The recorded campaign ran on native macOS on an
Apple M5 Pro. The 30 s request budget was **not** changed, so missions that the M5 Pro finishes in 9–23 s can exceed
30 s here and come back `unresolved/TIMEOUT`. That outcome is correct behaviour (unresolved is never reported as safe),
but it differs from the recorded verdict.

Every request went through `POST /v1/route-checks` with recorded inputs, `policy=full` and `run_independent_check=true`,
one request at a time with an otherwise idle machine. Each API body restates the recorded mission, and the API rebuilt
the recorded request object byte for byte (`provenance.recorded_mission_match`). Expected values come from
`research/routing/INDEPENDENT_ROWS.csv` (verdict, arrival) and the A4 rows of
`research/routing/final-input-ablation/data/ROWS.csv` (legs, route hash).

## Golden missions (`pytest tests/api -m golden`)

| region | mission | recorded | API verdict | reason | arrival (rec/API) | legs (rec/API) | compute_s | recorded wall_s | match |
|---|---|---|---|---|---|---|---:|---:|---|
| uiseong_andong_2025 | 20250324T090000Z_FL2 | checked_route | checked_route |  | 2143 / 2143 | 472 / 472 | 18.12 | 7.15/6.86 | yes |
| hongseong_2023 | 20230402T140000Z_FW2 | checked_route | checked_route |  | 1459 / 1459 | 217 / 217 | 25.97 | 12.61/12.37 | yes |
| uljin_2022 | 20220304T030000Z_FX1 | checked_route | unresolved | TIMEOUT | 3119 / None | 512 / None | 30.28 | 14.53/14.59 | NO |

identical: 2/3; median compute_s: 25.97406977799983; median recorded wall_s (M5 Pro, both reps): 12.492

In this run 울진 FX1 was `unresolved/TIMEOUT` at 30.28 s. The same mission met the budget in the panel run below
(29.94 s) and returned the recorded arrival of 3,119 s over 512 legs, with a 120 s dwell. On this VM it sits on the
budget edge. A diagnostic run of the same request outside the API, through `wfg_latest.api.route_and_check` with
`budget_s=120`, took 38.6 s and returned `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN` with arrival 3,119 s.

### Golden re-run on the final code (commit bb2acd0, after review fixes, fresh reboot)

| region | mission | recorded | API verdict | reason | arrival (rec/API) | legs (rec/API) | compute_s | recorded wall_s | match |
|---|---|---|---|---|---|---|---:|---:|---|
| uiseong_andong_2025 | 20250324T090000Z_FL2 | checked_route | checked_route |  | 2143 / 2143 | 472 / 472 | 20.23 | 7.15/6.86 | yes |
| hongseong_2023 | 20230402T140000Z_FW2 | checked_route | checked_route |  | 1459 / 1459 | 217 / 217 | 28.18 | 12.61/12.37 | yes |
| uljin_2022 | 20220304T030000Z_FX1 | checked_route | unresolved | TIMEOUT | 3119 / None | 512 / None | 30.12 | 14.53/14.59 | NO |

identical: 2/3; median compute_s: 28.179262609999995; median recorded wall_s (M5 Pro, both reps): 12.492

The outcome is the same: FL2 and FW2 are identical, and FX1 stays on the 30 s edge on this VM (30.12 s).

## Full final panel, 20 missions (`pytest tests/api -m panel`)

| region | mission | recorded | API verdict | reason | arrival (rec/API) | legs (rec/API) | compute_s | recorded wall_s | match |
|---|---|---|---|---|---|---|---:|---:|---|
| hongseong_2023 | 20230402T070000Z_FN1 | model_no_route | model_no_route |  | None / None | None / None | 0.59 | 0.31/0.27 | yes |
| hongseong_2023 | 20230402T070000Z_FX1 | model_no_route | model_no_route |  | None / None | None / None | 0.51 | 0.34/0.30 | yes |
| hongseong_2023 | 20230402T140000Z_FW2 | checked_route | checked_route |  | 1459 / 1459 | 217 / 217 | 25.87 | 12.61/12.37 | yes |
| hongseong_2023 | 20230402T230000Z_FD1 | checked_route | checked_route |  | 531 / 531 | 119 / 119 | 14.66 | 7.41/7.43 | yes |
| miryang_2022 | 20220531T100000Z_FN1 | checked_route | checked_route |  | 1142 / 1142 | 195 / 195 | 24.74 | 12.28/12.22 | yes |
| miryang_2022 | 20220601T020000Z_FW1 | checked_route | checked_route |  | 1270 / 1270 | 242 / 242 | 14.30 | 6.75/6.41 | yes |
| miryang_2022 | 20220601T080000Z_FD1 | model_no_route | model_no_route |  | None / None | None / None | 0.82 | 0.35/0.34 | yes |
| miryang_2022 | 20220601T080000Z_FX1 | model_no_route | model_no_route |  | None / None | None / None | 0.79 | 0.42/0.38 | yes |
| uiseong_andong_2025 | 20250323T010000Z_FD1 | checked_route | checked_route |  | 2460 / 2460 | 410 / 410 | 14.60 | 5.96/5.99 | yes |
| uiseong_andong_2025 | 20250323T010000Z_FX2 | checked_route | checked_route |  | 2540 / 2540 | 322 / 322 | 14.37 | 6.59/6.80 | yes |
| uiseong_andong_2025 | 20250324T090000Z_FL2 | checked_route | checked_route |  | 2143 / 2143 | 472 / 472 | 15.88 | 7.15/6.86 | yes |
| uiseong_andong_2025 | 20250325T170000Z_FW1 | checked_route | checked_route |  | 1064 / 1064 | 362 / 362 | 26.05 | 8.90/8.85 | yes |
| uljin_2022 | 20220304T030000Z_FD1 | checked_route | checked_route |  | 1589 / 1589 | 212 / 212 | 16.06 | 7.76/8.45 | yes |
| uljin_2022 | 20220304T030000Z_FX1 | checked_route | checked_route |  | 3119 / 3119 | 512 / 512 | 29.94 | 14.53/14.59 | yes |
| uljin_2022 | 20220304T060000Z_FL1 | checked_route | checked_route |  | 2067 / 2067 | 453 / 453 | 9.14 | 3.43/3.44 | yes |
| uljin_2022 | 20220304T120000Z_FW2 | checked_route | checked_route |  | 1655 / 1655 | 246 / 246 | 7.44 | 3.20/3.12 | yes |
| yeongdeok_2025 | 20250325T190000Z_FD1 | model_no_route | unresolved | TIMEOUT | None / None | None / None | 29.67 | 9.31/9.45 | NO |
| yeongdeok_2025 | 20250325T190000Z_FX2 | checked_route | unresolved | TIMEOUT | 2512 / None | 1129 / None | 32.68 | 22.48/22.44 | NO |
| yeongdeok_2025 | 20250325T230000Z_FL2 | checked_route | unresolved | TIMEOUT | 1922 / None | 657 / None | 29.41 | 12.73/12.65 | NO |
| yeongdeok_2025 | 20250326T080000Z_FW1 | checked_route | checked_route |  | 896 / 896 | 187 / 187 | 18.36 | 8.25/8.35 | yes |

identical: 17/20; median compute_s: 15.271435254999915; median recorded wall_s (M5 Pro, both reps): 7.281

All 17 identical missions also have identical route hashes, and the offline independent checker corroborates every one:
13 `INDEPENDENTLY_CERTIFIED_OPTIMAL` and 4 `INDEPENDENTLY_CERTIFIED_REFUSAL`. The three differences are all 영덕
timeouts. For each of them the independent checker agrees with the recorded outcome: `RELAXATION_INFEASIBLE` for FD1,
whose recorded result is a refusal, and `FEASIBLE_ROUTE_EXISTS` for FX2 and FL2, whose recorded results are routes. The
mismatch comes from host speed: the request did not finish inside the fixed budget. It is not a different answer.

Nothing was tuned in response. To reproduce on the evaluated host, run `make api-golden` and `make api-panel`.
