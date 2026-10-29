# Trajectory members, scenario reduction and acceptance rules (track 1C-1)

**Headline (20 frozen Korean missions, frozen contact sweep plus the frozen centre checker per member).**

- **v1 versus v2 at the same K = 4.** v1 (the frozen independent members) gives **15 checked routes, 5 model-scoped no-route decisions and 0 unresolved**. This reproduces the frozen candidate outcomes exactly, with the same 15 arrival seconds (sum 26,369 s). v2 trajectory members give **15 / 5 / 0 with uniform and with ordered sub-hour timing**. Two routes change: Uiseong-Andong 2025-03-23 FX2 arrives at 2,646 s instead of 2,540 s, and Uljin 2022-03-04 12:00 FW2 at 1,674 s instead of 1,655 s.
- **Why so little changes.** Every frozen mission has a one-hour horizon. A trajectory is then one synchronous transition from the cutoff state, so v1 and v2 members have **the same law in distribution**. The forecast also adds few new ignitions: at most 0.048 per cell and 0 to 6.3 expected per window, and 7 of 15 windows have none. Coherence can only enter through sub-hour ordering, member count and reduction weights. Over this panel the ordered timing changed no decision.
- **Coverage over all N = 1,024 trajectories.** The routes returned with v1 members pass in **98.9% of the trajectories on average (minimum 90.6%, Uiseong-Andong FX2)**. Under rule `all` the mean rises to 99.3% (K = 4 and K = 8 first trajectories) and to 99.9% (k-medoids K = 16, first K = 32). The smallest K whose routes reach mean coverage within 1 percentage point of the K = 32 routes is **K = 8 for all three selection methods**.
- **More members and extremes refuse more.** With rule `all`, larger K and the appended corridor extremes turn up to 3 more missions into model-scoped refusals: Uljin FX1 and FW2, and Uiseong-Andong FX2 at K >= 16 for k-medoids. With `k_of_m` (k = ceil(0.9 m)) at K = 16 and 32, all 20 missions return to 15 routes and 5 refusals. That rule also accepts the 1,616 s Uiseong-Andong FL2 route that some members burn; synthetic-truth campaign C4 shows the reconstructed fire on that route (`research/synthetic-truth/README.md`).
- **Reduction cost.** Forward selection gives the lowest reduction cost for all three distances. For the edge-arrival distance, its cost at K = 4 is 0.68 of the first-K cost at K = 4, and 0.45 at K = 32.
- **Binding constraints relative to travel-only.** Contact changes the outcome in **8 of 20 missions** (v1). Relaxing the destination window to the whole horizon changes it in 6 missions (v1 and v2 K = 4, rule `all`). Dose and peak never bind on this panel; the source cap of 0.703 kW/m2 cannot reach the 10 kW/m2 peak limit. Unresolved: **0 in all 480 decisions**.

All of this is model-relative: members are draws of one forecast model under declared construction assumptions, not a calibrated joint forecast, and nothing here is field validation.

## What was run

| Item | Script | Output |
|---|---|---|
| Export v3 (Contract A), replay mode, all 15 cutoffs, N = K = 1,024, seed 0, batch 32 | `make_exports_v3.py` (forecast environment) | v3 NPZ outside git; records and hashes in `data/exports_v3/` (`INDEX.json`) |
| Members, reduction, decisions, coverage | `run_members.py` (routing environment) | `data/decisions.jsonl` (480 rows: 20 missions x 12 member sets x 2 rules), `data/reduction_costs.jsonl` (540 rows), `data/host.json` |
| Tables, figures | `analyze.py` | `RESULTS.json`, `OUTCOMES.csv`, `REDUCTION_COSTS.csv`, `DECISIONS.csv`, `figures/` |
| FIXTURE export v3, model mode | `fixture_data_root.py`, `export_v3.py model` | `data/fixture/FIXTURE_FORECAST_RECORD_*.json` (synthetic; no real fire) |

Member sets per window: `v1` (frozen packet, K = 4). `v2_first4_uniform` and `v2_first4_ordered`: trajectories 0..3, equal weights, no extremes, so that the comparison isolates the member law. `v2_<method>_K<k>` for K in {8, 16, 32} and the methods first_k, forward_selection and k_medoids (k-medoids++ seed 20261029), all on the edge-arrival distance with corridor extremes appended and redistributed weights. Timing seed 20261029. Corridors are the travel-only routes of the window's missions. Each set is decided under `all` and under `k_of_m` with k = ceil(0.9 m). When k = m (K = 4 and 8, including extremes), the `k_of_m` row repeats the `all` decision and is marked `K_OF_M_EQUALS_ALL`.

Decision procedure (`wfg_members.decide`): the frozen sweep solves the exact contact-only relaxation under the members the rule requires. The witness is checked per member by one frozen centre check plus the checker's own sampling rule per member (equal to separate frozen checks per member, tested), giving contact, peak, linear dose, TDU dose and a pass flag. The rule is then applied with exact rational weights. `k_of_m` is an exact subset enumeration over minimal qualifying subsets with two exact prunings: the shared present-fire lower bound, and members whose ignitions touch no road. Lazy constraints apply only if dose or peak fail; they never did here.

## Outcomes (20 missions per row)

| Member set | Rule | K (median) | Routes | No-route | Unresolved | Sum of arrivals (s) | Median decision time (s, this host) | Coverage of routes on N = 1,024 (mean / min) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| v1 | all | 4 | 15 | 5 | 0 | 26,369 | 1.42 | 0.989 / 0.906 |
| v2_first4_uniform | all | 4 | 15 | 5 | 0 | 26,494 | 1.47 | 0.993 / 0.943 |
| v2_first4_ordered | all | 4 | 15 | 5 | 0 | 26,494 | 1.91 | 0.993 / 0.943 |
| v2_first_k_K8 | all | 8 | 15 | 5 | 0 | 26,634 | 2.11 | 0.993 / 0.943 |
| v2_forward_selection_K8 | all | 8 | 13 | 7 | 0 | 21,701 | 1.44 | 0.995 / 0.943 |
| v2_k_medoids_K8 | all | 8 | 13 | 7 | 0 | 21,701 | 1.49 | 0.995 / 0.943 |
| v2_first_k_K16 | all | 16 | 14 | 6 | 0 | 24,960 | 2.48 | 0.995 / 0.943 |
| v2_first_k_K16 | k_of_m | 16 | 15 | 5 | 0 | 25,842 | 2.52 | 0.987 / 0.906 |
| v2_forward_selection_K16 | all | 16 | 13 | 7 | 0 | 21,701 | 1.57 | 0.995 / 0.943 |
| v2_forward_selection_K16 | k_of_m | 16 | 15 | 5 | 0 | 25,842 | 2.78 | 0.987 / 0.906 |
| v2_k_medoids_K16 | all | 16 | 12 | 8 | 0 | 19,055 | 1.60 | 0.999 / 0.987 |
| v2_k_medoids_K16 | k_of_m | 16 | 15 | 5 | 0 | 25,842 | 2.50 | 0.987 / 0.906 |
| v2_first_k_K32 | all | 32 | 13 | 7 | 0 | 22,314 | 3.03 | 0.999 / 0.987 |
| v2_first_k_K32 | k_of_m | 32 | 15 | 5 | 0 | 25,842 | 2.88 | 0.987 / 0.906 |
| v2_forward_selection_K32 | all | 32 | 13 | 7 | 0 | 21,701 | 1.73 | 0.995 / 0.943 |
| v2_forward_selection_K32 | k_of_m | 32 | 15 | 5 | 0 | 25,842 | 3.20 | 0.987 / 0.906 |
| v2_k_medoids_K32 | all | 31 | 12 | 8 | 0 | 19,492 | 2.12 | 0.998 / 0.974 |
| v2_k_medoids_K32 | k_of_m | 31 | 15 | 5 | 0 | 25,842 | 3.23 | 0.987 / 0.906 |

The rows with `k_of_m` at K = 4 and 8 equal the `all` rows (k = m) and are in `OUTCOMES.csv`. Sums of arrivals compare different route sets when the route counts differ. Per-mission verdicts, arrivals and coverage are in `RESULTS.json` (`per_mission`) and `DECISIONS.csv`. The maximum decision time was 28.3 s (Yeongdeok, k-medoids K = 31, frozen sweep on 111,924 edges). Decision times are host-specific Linux measurements on a shared host (load average 5.1 to 6.6) and are not comparable with the frozen native-Mac request times; they are not the kit's 30 s complete-request measure.

Missions whose decision changes with the member set (all other 16 missions are identical in every row):

| Mission | v1 | Change |
|---|---|---|
| Uiseong-Andong 2025-03-23 01:00 FX2 | route 2,540 s | 2,646 s with every v2 set; no-route under `all` with k-medoids K >= 16 and first K = 32 |
| Uiseong-Andong 2025-03-24 09:00 FL2 | route 2,143 s | 2,580 s with k-medoids K = 31 (`all`); 1,616 s under `k_of_m` at K >= 16 |
| Uljin 2022-03-04 03:00 FX1 | route 3,119 s | 3,259 s with first K >= 8; no-route with forward selection or k-medoids (corridor extremes) |
| Uljin 2022-03-04 12:00 FW2 | route 1,655 s | 1,674 s with v2 K <= 8 first; no-route with extremes or K >= 16 |

## Reduction cost versus K (mean over the 8 windows whose trajectories differ on the window)

| Distance | Method | K = 4 | K = 8 | K = 16 | K = 32 |
|---|---|---:|---:|---:|---:|
| edge_arrival (m s) | first_k | 2.374e6 | 1.879e6 | 1.698e6 | 1.563e6 |
| edge_arrival | forward_selection | 1.605e6 | 1.455e6 | 1.271e6 | 1.064e6 |
| edge_arrival | k_medoids | 1.685e6 | 1.579e6 | 1.432e6 | 1.224e6 |
| first_burn_l1 (cells) | first_k | 3.959 | 3.565 | 3.259 | 2.962 |
| first_burn_l1 | forward_selection | 2.716 | 2.610 | 2.467 | 2.302 |
| first_burn_l1 | k_medoids | 2.797 | 2.753 | 2.687 | 2.585 |
| road_symdiff (weighted cells) | first_k | 3.736 | 3.339 | 2.963 | 2.742 |
| road_symdiff | forward_selection | 2.501 | 2.400 | 2.267 | 2.118 |
| road_symdiff | k_medoids | 2.575 | 2.544 | 2.482 | 2.387 |

The reduction cost decreases slowly because almost every trajectory is distinct: each one draws a few independent ignitions out of hundreds of possible cells. At the one-hour horizon, first_burn_l1 and road_symdiff carry the same information up to their weights, and only edge_arrival sees timing. In 7 of the 15 windows all 1,024 trajectories are identical inside the window, because no window cell has a positive probability; these windows are excluded from the means. An average of 0.38 to 0.5 corridor extremes was appended per window.

## Figures

- `figures/fig01_member_examples` (PNG 300 dpi and SVG). Uiseong-Andong window, cutoff 2025-03-25 17:00 UTC: first-new ignition seconds of v1 member 0 (frozen independent draws) and of v2 trajectory 0 with uniform and ordered sub-hour timing, on the same colour scale (0 to 3,600 s). Grey: present fire at the cutoff; circles mark the ignited cells. Same cutoff, same window and same grid.
- `figures/fig02_reduction_cost_vs_k`. Mean reduction cost D_J against the retained count K for first_k, forward selection and k-medoids under the three distances. Means are over the 8 windows whose trajectories differ, before the corridor extremes are appended.
- `figures/fig03_outcomes_vs_k_and_rule`. Checked routes, model-scoped no-route decisions and unresolved outcomes (none) of the 20 missions for every member set and rule.

## Reproduce

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -c constraints-routing.txt './integration[packets]' -r experimental/scenario-members/requirements-test.txt
python tools/fetch_routing_inputs.py
# forecast environment (PyTorch CPU): pip install -e ./forecast; then
python research/scenario-members/make_exports_v3.py --out EXPORTS_V3
# routing environment:
python research/scenario-members/run_members.py --exports EXPORTS_V3
python research/scenario-members/analyze.py --exports EXPORTS_V3
```

Inputs: release research-final-20261015 (archive SHA-256 `d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202`), `INPUT_FILES.json` SHA-256 `5d820b97740d879d2bc78a76d1b5854420793c927c6315f656dc1c2927b35235`, read at `/home/user/wfg-shared/routing-inputs`. Export v3 NPZ SHA-256 per window: `data/exports_v3/INDEX.json`. Checkpoint c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843 (unchanged). Seeds: rollout 0; sub-hour timing 20261029; k-medoids 20261029; v1 draws 20261008 (frozen). Host: Linux container, 4 vCPU, 15 GiB, no GPU, Python 3.12.3, NumPy 1.26.4, PyTorch 2.5.1 CPU for the export only. The run took 2,577 s on a host shared with two other tracks.

Data tree: the forecast environmental rasters were not attached during this run, so model-mode export v3 ran only on the FIXTURE data root. There it was used to check that one-hour replay reproduces model mode exactly (`tests/test_export_v3.py`), and to exercise multi-hour export. FIXTURE records are labelled as such and describe no real fire. When the real data tree arrives, the rerun command is `python experimental/scenario-members/export_v3.py model --source-root forecast --data-root DATA --checkpoint CK --event KFS_xx --cutoff ISO --out OUT`, per cutoff.

## Scope and limits

- At the one-hour horizon of the frozen missions, trajectory members equal the independent law in distribution. These results therefore test sub-hour ordering, member count, reduction and acceptance, not multi-hour coherence. The extended-horizon exploratory panel (3 h and 6 h, not frozen missions) is reported separately in `research/synthetic-truth/README.md`.
- Replay mode rests on the fact that the first rollout transition from the cutoff state is the exported v2 probability under the same boundary and missingness policies. It holds exactly for one hour and was checked on a FIXTURE with the real checkpoint. It refuses any other state.
- Decisions use the frozen contact sweep and the frozen centre checker (cell-centre flux). The kit's continuous whole-road radiation checker is not run here. Peak cannot bind on this panel, and dose never bound.
- The `ordered` timing is a heuristic ordering, not a physical model. Track 1A's isochrone timing can replace it later.
- 20 missions on five regional panels from four parent fires; the two Gyeongbuk panels are one fire. Coverage percentages are over Monte Carlo trajectories of one model, not over real outcomes.
- Caldor/Rim (6 missions) were not run: their sealed-study packets are not on this host.
