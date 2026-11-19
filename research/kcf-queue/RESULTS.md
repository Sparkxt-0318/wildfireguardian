# kcf-queue: results (congested leave-by, 174 places, 25 March 2025, MEASURED 8 h)

**Every number here is model output on reconstructed inputs and assumed parameters. It is not what happened to people, not an
order, and not advice to any official.** Protocol: [PROTOCOL.md](PROTOCOL.md), frozen at `8f1355b` before any result;
one amendment (§9, made before any real-data outcome). Literature gate: [LITERATURE.md](LITERATURE.md). Inputs: no real
traffic counts, no driver-behaviour data, every demand and capacity parameter assumed (low/middle/high in PROTOCOL §4).
`DATA_GO_KR_KEY` and `KMA_API_KEY` were **not present in this container**, so no KOSIS/data.go.kr data was fetched;
households are the cited county/읍·면 totals split equally (ASSUMED).

## 0 What was and was not proved

* **The answer is a guaranteed-safe lower bound, not the exact optimum.** Every start time the solver accepts has an explicit
  schedule that obeys the road rules (the certificate). The true latest start under the same rules can be later.
  **T1** (6,000 random small networks, 66,000 start times, exhaustive vehicle-by-vehicle search): **0 cases where the solver
  accepts and brute force does not (soundness holds)**, but **66 cases (0.10 %) in 64 networks (1.07 %) where brute force finds
  a schedule the solver misses**. So exactness is *not* claimed. The size of the gap on real graphs is unknown.
* An **upper bound** is the free-flow single-vehicle leave-by `L0` of the existing field. Each answer therefore sits in
  `[s*, L0 − spread]` (the second term is `S_free`, free flow with the same spread).
* **With unlimited capacity the solver equals the existing deadline field exactly** (T2: 6,000 random instances, 90,000 start
  seconds, 0 differences; and on the real graphs, T0 below).

| test | result | file |
|---|---|---|
| **T0** free-flow field reproduced from my closure fields and recursion vs the committed `per_place.csv` (MEASURED, 8 h) | **2,262 of 2,262 rows equal** (1,077 inside, 785 not cut within 8 h, 349 cut, 51 no safe departure: state equal in every row, leave-by equal to the minute in every row that has one). 0 mismatches. | `results/t0_free_flow_reproduction.json` |
| **T1** brute force, 6,000 random networks | soundness **0 violations**; exact agreement in 65,934 of 66,000 cases; **66 gaps** (above). Solver is a lower bound | `results/t1_bruteforce.json` |
| **T2** unlimited capacity vs `core.backward` | **0 / 6,000** networks differ (90,000 seconds compared), L0 equal in all | `results/t2_unlimited_capacity.json` |
| **T3** mutation tests on the independent checker | **2,080 / 2,080 mutants rejected**, each with a failure code in the expected set (0 wrong codes); 38 / 38 unaltered certificates valid. 17 mutant families (≈ 122 each) | `results/t3_mutation.json`, `mutate.py` |
| **T3b** checker on every certificate generated in the runs | all valid: MID 1,064 isolated + 1,064 contested; LOW 1,085 + 168 (sample); HIGH 1,025 + 165 (sample). **0 invalid** | `numbers.json` |
| **T4** is feasibility a prefix in the start time? | random 5 % of MID place-hours: **56 place-hours, 21,161 start times scanned every 60 s, 0 non-prefix** | `results/t4_monotonicity.json` |
| **T5** contested start ≤ isolated start | **0 violations** in 3,174 pairs (LOW, MID, HIGH) | `numbers.json` |

The checker (`checker.py`, 255 lines, standard library) was written by a separate agent that read only
`CERTIFICATE_SPEC.md` and no solver code; it shares no code with the solver. A certificate holds the full timed route
of every vehicle (the subject village and its neighbours), the closure data with its SHA-256, and the binding element.
It proves the listed schedule is feasible. **It does not prove that a later start fails.** Not detectable by design: a certificate
whose raw data and data hash were both replaced consistently.

## 1 Units

Villages: 168 villages and 1 hamlet of the 174 places (the 5 care facilities have no vehicle demand in the card model and
are not evaluated). 13 issue hours, 12:00–24:00 KST. Of 2,262 place-hours, the **village** place-hours by free-flow state:

| free-flow state (committed `per_place.csv`) | village place-hours |
|---|---|
| already inside the known fire area (no departure) | 1,028 |
| no safe departure at the issue hour | 50 |
| last departure set by a road cut inside 8 h (**CUT**) | 342 |
| not cut within 8 h (set by the 8 h horizon; the deadline is the horizon, not fire) | 777 |

The solver runs on the last two: **1,119 village place-hours at 137 places**. The 777 horizon-limited rows are reported
but are not fire-limited.

## 2 Headline (MIDDLE parameters, CONTESTED scenario, n = 1,119 place-hours)

* **1,064 place-hours clear; 55 cannot clear at all** (23 places; 4 of them in no hour). All 55 are CUT rows. In every one
  the free-flow window is shorter than the 30-minute mobilisation spread, so the last vehicle departs after the road is cut.
  No place-hour fails because of its own queue at middle parameters (HIGH: 3).
* **The leave-by moves earlier against the free-flow answer by a median 30.0 min (p90 35.3, max 41.4; n = 1,064).** This is
  **almost all the mobilisation spread, not congestion**: the card's free-flow leave-by `L0` is when the *first* vehicle must
  leave; the whole village must start `W` earlier. Against free flow *with the same spread* (`S_free`) the queue adds:

| MIDDLE | all 1,064 clearing | of which CUT rows (287) |
|---|---|---|
| queue delay (`S_free − s_isolated`) ≥ 1 min | 274 place-hours at 29 places | 41 |
| ≥ 5 min | 115 at 12 places | 20 |
| ≥ 15 min | **0** | 0 |
| median / max | 0.12 min / **11.4 min** | 0.10 / 11.3 |

  (Starts are on a 10 s grid, so "> 0 s" counts mostly rounding and is not reported as a finding.)
* **Sharing roads with neighbours changed no middle-parameter answer** (0 of 1,064; HIGH: 2 place-hours, up to 34.5 min).
  Reason, stated plainly: neighbours are released at the issue hour and the village itself starts later; in only **11** of the
  287 CUT clearing place-hours does the village's start fall inside its neighbours' release window at all. The scenario is
  also one hop only and is a definition (PROTOCOL §3.7), so this is **a weak test of road sharing, not evidence that sharing
  does not matter**.
* **Which roads bind** (CUT rows, middle, minimum-slack element at the leave-by): 202 of 287 end on a road cell closing, 85 at the
  shelter closing. No road binds for more than **3 places**; 7 roads bind for ≥ 2 places. Top: **일직점곡로 (secondary,
  OSM way 30043762, 의성): 3 places, 7 place-hours**; 32531447 (residential, 의성): 3 places; 신흥길 (way 32721332, 의성): 2 places;
  경동로 (primary, 영덕), 주왕산로 (secondary, 영덕), 풍일로 (secondary, 의성): 2 places each. Full list in
  `results/extra.json`. **The binding element is the road whose closure ends the window, not a road where a queue forms:** queue
  delay is small at middle parameters.

## 3 LOW / MIDDLE / HIGH

| | LOW (favourable) | MIDDLE | HIGH (adverse) |
|---|---|---|---|
| households × / vehicles per household / spread / smoke factor / "other" road veh/h | 0.7 / 0.9 / 15 min / 1.00 / 1,000 | 1.0 / 1.198 / 30 min / 0.85 / 800 | 1.4 / 1.5 / 60 min / 0.70 / 600 |
| vehicles per village (typical) | 101 | 192 | 336 |
| clear / cannot clear (of 1,119) | 1,085 / 34 | 1,064 / 55 | 1,025 / 94 (3 by own queue) |
| median shift vs `L0` (min) | 15.0 | 30.0 | 60.0 |
| queue delay ≥ 5 min (place-hours) | 0 | 115 | 231 |
| queue delay ≥ 15 min | 0 | 0 | 200 (22 places) |
| max queue delay (min) | 0.15 | 11.4 | 53.6 |
| neighbour sharing changed the answer | 0 | 0 | 2 (max 34.5 min) |
| CUT rows: clear / cannot | 308 / 34 | 287 / 55 | 248 / 94 |

Paired over the 248 CUT place-hours that clear under all three: LOW start − MIDDLE start median 15.0 min (max 26.2);
MIDDLE − HIGH median 30.0 (max 72.3); LOW − HIGH median 45.0 (max 98.5). The median is the spread; the tail is queue.

**One at a time** (CONTESTED, others at middle; "high" = adverse end). The two cards' hours:

| one parameter changed from middle | uiseong_andong_12:00KST | yeongdeok_18:00KST |
|---|---|---|
| middle (reference) | 43 clear / 4 cannot; median shift 30.0 min; max shift 30.1; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 30.0 min; max shift 41.4; max queue delay 11.4 min |
| households × 0.7 | 43 clear / 4 cannot; median shift 29.9 min; max shift 30.0; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 29.9 min; max shift 30.1; max queue delay 0.1 min |
| households × 1.4 | 43 clear / 4 cannot; median shift 30.0 min; max shift 30.1; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 30.0 min; max shift 57.5; max queue delay 27.6 min |
| 0.9 vehicles/household | 43 clear / 4 cannot; median shift 29.9 min; max shift 30.0; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 29.9 min; max shift 31.2; max queue delay 1.2 min |
| 1.5 vehicles/household | 43 clear / 4 cannot; median shift 30.0 min; max shift 30.1; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 30.0 min; max shift 51.5; max queue delay 21.6 min |
| spread 15 min | 44 clear / 3 cannot; median shift 16.9 min; max shift 17.4; max queue delay 2.5 min | 90 clear / 0 cannot; median shift 15.3 min; max shift 41.2; max queue delay 26.2 min |
| spread 60 min | 41 clear / 6 cannot; median shift 59.9 min; max shift 60.0; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 59.9 min; max shift 60.1; max queue delay 0.1 min |
| smoke factor 1.00 | 43 clear / 4 cannot; median shift 30.0 min; max shift 30.1; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 30.0 min; max shift 34.9; max queue delay 4.9 min |
| smoke factor 0.70 | 43 clear / 4 cannot; median shift 30.0 min; max shift 30.1; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 30.0 min; max shift 50.4; max queue delay 20.4 min |
| other roads 1,000 veh/h | 43 clear / 4 cannot; median shift 30.0 min; max shift 30.1; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 30.0 min; max shift 32.5; max queue delay 2.6 min |
| other roads 600 veh/h | 43 clear / 4 cannot; median shift 30.0 min; max shift 30.1; max queue delay 0.1 min | 88 clear / 2 cannot; median shift 30.0 min; max shift 56.5; max queue delay 26.6 min |

Shift = leave-by earlier than the card's free-flow figure `L0`; the median equals the spread. Queue delay = free flow with the same spread minus the solved start. Parameter names in `results/oat.json` follow the stress end (`high` = adverse), not the numeric value.

**Reading.** At 의성·안동 12:00 no single parameter produces more than 0.1 min of queue delay except the 15-minute spread (2.5 min): most of its 47 villages are horizon-limited or have short windows, so the spread decides who can clear (cannot-clear 3 / 4 / 6 for spread 15 / 30 / 60 min). At 영덕 18:00 the queue matters once demand, capacity or smoke is set to the adverse end (max delay 20–28 min for 1.4× households, 1.5 vehicles/household, smoke 0.70, or 600 veh/h roads; 26 min for the 15-minute spread, whose peak rate is higher), and no one-at-a-time change makes more than 2 of 90 villages unable to clear. These two cases are two hours of one fire: they say nothing about other days.

## 4 What the cards now show

`product/wfg-roadlayer` village cards for the two worked cases (의성·안동 12:00 KST, 영덕 18:00 KST; 137 of 174 places have a
value, the rest are already inside the fire area, have no free-flow window, or are care facilities) carry a new line
"Leave by (queue model KQ-1)": the MIDDLE contested start with the LOW and HIGH starts in brackets and the vehicle count.
The old line (`vehicles ÷ narrowest road 800 veh/h = N min`) is unchanged and still shown. The audit CSV gains five columns.
Data: `product/wfg-roadlayer/data/queue_leaveby.csv` (from `export_cards.py`). The card vehicle count (rounded up in the old
line, rounded to nearest here) can differ by 1. Cards of other hours carry no queue line. Roadlayer tests: full suite 68 passed, 4 skipped before the last layout change; `test_cards` and `test_golden` rerun after it: 23 passed.

## 5 Limits and deviations, stated plainly

* **Lower bound only** (T1 gap 0.10 % of small cases; size on real graphs unknown). Route choice is greedy, not optimal.
* **Not independent of the fire reconstruction:** fire arm MEASURED 8 h only; one day; two regions. Other arms and the 5 h
  horizon not run.
* **No real traffic counts, no driver behaviour, parameters assumed.** Demand rests on cited province-level vehicle ratios and an equal
  split of 읍·면 or 시·군 household totals; no per-리 count; keys for official statistics were not available here.
* Capacity per edge only: no junction, merge or turn capacity; point queues of zero length; unlimited shelter space; the 2026 OSM road
  class on the 2025 graph.
* Neighbour scenario: one hop, neighbours released at the issue hour, with right of way. It under-counts traffic and cannot represent a village
  that leaves late into the traffic of others.
* The uniform mobilisation ramp is a stand-in. The 30-minute shift against the card's `L0` is mostly this assumption.
* **777 of 1,119 place-hours are horizon-limited** (deadline = the 8 h forecast end), not fire-limited; their binding element is the shelter/horizon.
* Certificates for **every** answer exist only transiently: every MID answer and all LOW/HIGH isolated answers were checked during the run, LOW/HIGH
  contested answers for 1 village in 5 (crc32 of the id). Certificate files are committed for a sample only (`certs_sample/`); the 152 MB
  of card-case certificates are not committed; verdicts and `numbers.json` are.
* The first mutation run was too slow for the checker on large contested certificates and was stopped by its time limit; the reported run uses
  30 isolated and the 8 smallest contested certificates (2,080 mutants).
* Process: a worker restart interrupted a timing run; every reported run completed.

## 6 Reproduce

```bash
cd research/kcf-queue && python3 -m kq.run_t1_t2 T1 6000 results/t1_bruteforce.json && python3 -m kq.run_t1_t2 T2 6000 results/t2_unlimited_capacity.json
```

```bash
cd research/kcf-queue && python3 t0_free_flow.py && for s in mid lh oat; do KQ_CERT_DIR=/tmp/kq_certs python3 -m kq.run_all $s 4; done && python3 aggregate.py && python3 analysis2.py && python3 oat_table.py
```

```bash
cd research/kcf-queue && python3 mutate.py /tmp/kq_certs results/t3_mutation.json 130 && python3 -m unittest test_checker.py
```
