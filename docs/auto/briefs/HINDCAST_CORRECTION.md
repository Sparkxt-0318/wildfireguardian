# Brief — the hindcast correction: wording on judge surfaces, then the forecast-track field

Written 2026-09-14 by the author's HQ session after `docs/benchmark/results_v0.1.md` §2
established that `forward_simulate` advances each step with ERA5 reanalysis at times after
T0. Every committed spread field, and every 「forecast-aware」 number built on one, is a
**hindcast**: the router was given the weather that occurred, not a forecast anyone could
have issued at ignition. This brief fixes what the surfaces say (Part A, do first, small)
and builds the field that would make the word 「forecast」 true (Part B).

Decisions below are the author's via HQ; the build agent applies them, it does not re-decide
them. Laptop session on `auto/dev`, own worktree; harness paused; CHARTER §3 in force.

## Part A — wording (decided; apply exactly)

**A1. The method keeps its name.** 「forecast-aware routing」 / 「시간 인지 경로」 names a
router that consumes a time-varying hazard field; that is true regardless of how the field
was made. Do not rename the method, the classes (`naive_into_FA_safe`), the keys or the
tests. A rename would touch dozens of gates and change no fact.

**A2. What changes is the description of the field, on every judge-facing surface that
quotes a routing headline (42, 91, 34, 1,606, 27, the dispatch sheets).** Add this sentence
in the same block as the number, never one screen away (the WC-013 rule):

- KO: 「이 경로들을 계획한 확산면은 발화 이후 실제로 관측된 기상(ERA5 재분석)으로 다시 만든
  것, 즉 사후 재구성(hindcast)입니다. 발화 시점에 발표된 예보로 만든 확산면은 공개 벤치마크
  K-SPREAD-2025에서 채점 중이며, 그 결과가 나오기 전까지 이 수치는 「좋은 확산면이 주어졌을
  때 경로 방법이 얻는 것」이지 「예보의 정확도」가 아닙니다.」
- EN: 「The spread field these routes were planned on was reconstructed with the weather
  that actually occurred after ignition (ERA5 reanalysis): a hindcast. A field built from
  the forecast issued at ignition is being scored on the open K-SPREAD-2025 benchmark; until
  it is, these numbers measure what the routing method gains from a good spread field, not
  the accuracy of a forecast.」

Surfaces: `README.md` (Round-4 lead block, §5 ①, the multi-region table's note),
`scripts/finals.template.html` → rebuild `web/finals.html` (`make finals`), `docs/auto/JUDGE_QA.md`
(every card that speaks 42 / 91 / 27 / 1,606: at least Q19, Q19a, Q29a, Q36; digits are
forbidden in Q29a's spoken draft, so use the sentence without the benchmark name's digits
there — write 「공개 벤치마크」), `docs/auto/DEMO_SCRIPT_5MIN.md` (the ⚠ answer block, not
the timed spoken lines), `docs/auto/finals/RELATED_WORK_PANEL.md`, `docs/creativity_card.md`,
`docs/fair_opponent_line.md` §2, `docs/rescue_routing_real_hazard.md`, the README of
`outputs/dispatch_real_hazard/`. `paper/` is out of scope (the author rewrites it later).

**A3. Register it.** One new entry in `docs/auto/withdrawn_claims.json`, id the next WC
number, claim 「the routes were planned on a forecast」 with the pre-fix wording quoted from  <!-- forbidden-ok: wc022-planned-on-the-forecast -->
each surface, `say_instead` = the sentence above, spellings that catch 「예보로 계획」 /  <!-- forbidden-ok: wc022-yebo-ro-gyehoek -->
「planned on the forecast」 / 「forecast field」 used as a description of the committed field  <!-- forbidden-ok: wc022-forecast-field, wc022-planned-on-the-forecast -->
(not the method name). Frozen artifacts that carry the old wording (dispatch sheets, the
printed kit already stamped) get the dated known-stale exception CHARTER §3.5c allows.
Re-run `check_withdrawn_claims.py`; rebuild the printables kit at a new stamp; rebuild the
finals bundle.

**A4. Gates and hygiene.** Full gates green before push; `test_output_object_claim_bounds`,
`test_creativity_card`, `test_judge_qa_bank`, `test_readme_round4*` will need their
predicates extended to accept the new sentence where they pin a block; extend, never
weaken. No number moves; nothing is re-run in Part A.

## Part B — the forecast-track field (decided design; pre-register before running)

Two entrants, both leave-one-complex-out (영덕 and 의성·안동 both out of training), on the
canonical 영덕 canvas, same seed, same steps, new npz filenames, canonical npz untouched:

- **F1 frozen-weather (no forecast at all):** every step uses the ERA5 values at the last
  time at or before T0 and holds them. This is what an operator with no forecast would
  assume; it needs no new data and runs today on the laptop's raw bundle.
- **F2 KMA-forecast:** every step uses the KMA 동네예보 (초단기 where it covers, else 단기)
  **issued before T0**, mapped onto the model's weather features (10 m wind → u/v, T, RH →
  VPD; precipitation). Requires the archived forecast files from 기상자료개방포털 under
  `data/raw/kma_forecast/` with a MANIFEST.json; if absent, F2 is written as a script that
  refuses to run and says why, and the report says so.

For each field that runs: (1) score it on the benchmark as entrant E4a / E4b in the
**forecast track** (`scripts/benchmark/score_kspread.py`); (2) route the 458 canonical
origins and the 19,250 주건물 nodes exactly as `scripts/run_leakfree_yeongdeok_fold.py` does
and report the partition and the observed three-way grading beside the canonical and
leak-free rows; (3) last-safe-departure counts under the 5 h rule; (4) the four-way rescue
split on the NH-057 scene. New artifacts under `data/processed/forecast_track/`, a page
`docs/forecast_track.md` with the rule declared before the run, figures in the house style
into `docs/figures/finals/` (new filenames), nothing registered, nothing on a judge surface.

**Reading rule, fixed now.** Whatever F1/F2 say is the result. If the forecast-track field
recovers most of the hindcast's routing advantage, the method's value is shown to survive
forecast error; if it recovers little, the finding is that the router's value depends on
forecast quality, quantified for the first time, and the benchmark is where that is fixed.
Neither outcome is edited into a better one.

## Order and report
Part A first (one PR), then Part B. Report to
`docs/auto/briefs/HINDCAST_CORRECTION_REPORT.md`: the surfaces changed with line pointers,
the WC id, the F1 (and F2) tables beside canonical and leak-free, what could not run, and the
one sentence the finals can defend.
