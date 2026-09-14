# Report — the hindcast correction (Parts A and B)

**Brief:** `docs/auto/briefs/HINDCAST_CORRECTION.md` (author, via HQ, 2026-09-14).
**Lap:** 2026-09-14, one session, worktree on `auto/dev`.
**Commits:** `5348e31` (Part A), `d1e709f` (Part B). **PR:** #39, draft.
**Gates:** `python scripts/auto/gates.py --mode full` exit **0** at both commits, exit code
read directly and never piped. GitHub's own `auto-gates` run on `5348e31` concluded
**success**, matching this machine.

---

## 0. The one sentence the finals can defend

> 「이 경로들을 계획한 확산면은 발화 이후 실제로 관측된 기상(ERA5 재분석)으로 다시 만든 것,
> 즉 사후 재구성(hindcast)입니다. 발화 시점에 발표된 예보로 만든 확산면은 공개 벤치마크
> K-SPREAD-2025에서 채점 중이며, 그 결과가 나오기 전까지 이 수치는 「좋은 확산면이 주어졌을
> 때 경로 방법이 얻는 것」이지 「예보의 정확도」가 아닙니다.」

It is now in the **same block** as every routing headline on every surface the brief named
(the WC-013 rule). The method keeps its name, **no number moved**, and nothing was re-run.

---

## 1. Part A — surfaces changed, with line pointers

| surface | lines | block |
|---|---|---|
| `README.md` | 149, 279, 328, 486 | the multi-region table's note; the Round-4 lead blockquote; the fair-opponent ladder bullet carrying 27; §5 창의성 item ① |
| `scripts/finals.template.html` → `web/finals.html` | 1823 (both) | the 지역별 비교 card's `note` — the same card that prints 42 and 91. Rebuilt with `make finals` |
| `docs/auto/JUDGE_QA.md` | 961, 1093, 1392, 1631 | Q19, Q19a, Q29a, Q36 |
| `docs/auto/DEMO_SCRIPT_5MIN.md` | 185 | a new ⚠ answer block in 3막, beside the numbers and **not** in the timed spoken lines |
| `docs/auto/finals/RELATED_WORK_PANEL.md` | 37 | the front-panel dispatch claim |
| `docs/creativity_card.md` | 36 | the method table's item 1 |
| `docs/fair_opponent_line.md` | 42 | §2, under the shipping sentence that carries 265 / 327 / 354, 27 and 79 |
| `docs/rescue_routing_real_hazard.md` | 54 | §3, under the NH-057 result table |
| `outputs/dispatch_real_hazard/README.md` | 30 | 「What is real, what is not」, naming the frozen-sheet exception |

**Q29a took the no-digit variant**, as the brief directed: it is tier T0, spoken from
memory, and `test_creativity_card::test_the_card_states_no_number_about_this_repository`
forbids any multi-digit run in its draft. There alone the benchmark is 「공개 벤치마크」.

### 1a. Two blocks that quote 42 and did NOT get the sentence, named so the debt is visible

- **`README.md`'s TL;DR 「Headline result」 bullet.** The brief's README list does not
  include it, and **NH-054 closed on 2026-09-12 with option D, 「Do nothing before
  2026-10-24; revisit it for the paper」** — that entry is precisely about the caveat
  proportion of this bullet. Adding a fifth qualification would be deciding NH-054.
- **`README.md`'s 「### Abstract (draft)」.** It states, in its own header, that it tracks
  `paper/manuscript.md`, and the brief puts `paper/` out of scope because the author
  rewrites it later.

Neither is an oversight and neither is hidden: both are written into WC-022's `artifact`
field as well as here.

### 1b. One block the brief did not enumerate and that got the sentence anyway

`README.md:328`, the fair-opponent ladder bullet. It carries **27**, which A2's own first
sentence names as a routing headline, and the WC-013 rule it invokes is 「same block, never
one screen away」. Applying the author's rule to a block the enumeration missed is applying
the decision, not re-deciding it — and it adds a caveat while moving no number. Flagged
here in case the author wants it out.

### 1c. 1,606's home is not on the brief's list

A2 names **1,606** as a routing headline. Measured: on the finals screen it appears only
inside the coordinate JSON payload (coincidental digits, not a rendered figure), and its
real homes are `docs/leakfree_fold.md`, `docs/building_origins_*.md`,
`docs/corridor_treatment_atlas.md` and `docs/figures/finals/README.md` — **none of which
the brief lists**. They are technical pages rather than judge surfaces, so this lap applied
the list exactly and did not extend it. **Author's call** whether the sentence should go
there too.

---

## 2. WC-022 — and the honest shape of it

`docs/auto/withdrawn_claims.json`, id **WC-022**, claim 「the committed spread field is a
forecast, so the routing headlines measure what a forecast buys」.

⚠ **It is mostly a forward ratchet and the entry says so in those words.** Two of its three
spellings had **zero live instances** at registration. This repository never wrote
<!-- forbidden-ok: wc022-planned-on-the-forecast, wc022-yebo-ro-gyehoek -->
「the routes were planned on a forecast」 or 「예보로 계획」. It wrote an honest
「전방 시뮬레이션」 beside a method correctly called forecast-aware and let the reader supply
the rest. **The real defect was an omission, and no registry of spellings can catch an
omission.** What closes it is the sentence now standing in the same block as each number;
the registry only stops the short spelling from being written later.

**The one spelling with live instances had six of them, where this lap predicted two.**
<!-- forbidden-ok: wc022-forecast-field -->
「forecast field」 was expected in `paper/manuscript.md` and
`docs/present_perimeter_yeongdeok.md`. Registration also found it in
`docs/vehicle_pickup_intervention.md:40` — 「any hazard other than the committed forecast
field」, the plainest instance in the tree — and in `FIGURE_STYLE_REFERENCE.md:27`,
`IEEE_PLAN.md:37` and `WEEKLY_2026-W37.md:78`. **This lap's own grep missed four of six.**
That is the measured case for CHARTER §3.5c, restated with this lap's evidence rather than
WFG-133's, and it is written into the entry's `limits`.

**Eight dated known-stale exceptions** (CHARTER §3.5c, NH-042 A): the dispatch sheets
printed 2026-09-12, the six 「forecast field」 lines, and the brief's own three lines.
`paper/manuscript.md`'s F6 caption is licensed by a pragma on the line **above** it, so the
caption is byte-unchanged.

**Three predicates extended, never weakened**, each mirroring an exclusion the file already
documents:

1. `test_creativity_card` strips the exact literal `K-SPREAD-2025` before its count scan,
   as it already strips `Q29a` card IDs. **Never a bare `\d{4}` year shape** — that would
   let a real stale count through the moment one looked like a year.
2. `test_readme_round4_lead` strips `ERA5` before its margin scan. 「5」 is a registered
   margin value and `ERA5` ends in a bare one, so the sentence the brief requires in that
   very block was literally unwritable. **27 and 86 stay red.**
3. `paper/build_docx.py` skips HTML-comment-only lines. **A real fix, not an
   accommodation**: that branch would have rendered the pragma into the `.docx` as visible
   text and counted it as four words of prose. `body_words` stays 9155 and
   `paper/STATE.json` is untouched.

Rebuilt: `web/finals.html`, printables kit at new stamp **20260914T1349Z** (62 pages), the
finals bundle (19 files), and `docs/artifact_manifest.json` (138 artifacts).

---

## 3. Part B — what was declared, what was built, what could not run

`docs/forecast_track.md` states the rule **before anything runs** (§2), fixes the reading of
either outcome (§3), and its **§4 Results is empty by construction**.

| | status |
|---|---|
| The rule, declared first | **done** — §2, both entrants, pre-registered |
| The reading rule | **done** — §3, fixed before any number exists |
| F1 script | **written**, not run |
| F2 script | **written**, and it correctly **refuses** — all four refusal paths exercised |
| E4a benchmark score, 458-origin routing, 주건물 routing, observed grading, 5-hour counts, NH-057 split, figures | **NOT RUN — no number exists** |

### 3a. Why nothing ran, stated as narrowly as the evidence allows

This session is a **cloud container**, not the author's laptop. Measured here rather than
assumed: `data/raw/firms_data/` does not exist, `$WFG_FIRMS_DIR` is unset, and a
filesystem-wide search for `*_era5.nc`, `*_dem.tif`, `firms_data.zip` and
`*_detections.csv` returned nothing. F1 needs all three
(`run_leakfree_yeongdeok_fold.py:103` and `:165` are the same dependencies).
`data/raw/kma_forecast/MANIFEST.json` is absent too, so F2 refuses for the reason §2 says
it should — **the behaviour the brief asked for, not a failure**.

⚠ **An empty `data/raw` in a fresh checkout is not evidence that the author has no data** —
commit `4994f99` exists because a previous session drew exactly that inference. The claim
here is the narrower one: **this machine cannot reach the bundle.** The mountain-weather
commit `ffb489f`, landed mid-lap, is direct evidence the laptop *does* hold data this
container never sees.

**No number was estimated, interpolated or carried over from the canonical or leak-free
rows.** The brief's reading rule is fixed and there was nothing to read.

### 3b. What the laptop runs

    python scripts/run_forecast_track_f1.py
    python scripts/benchmark/score_kspread.py --entrant data/processed/benchmark/entrants/e4a_wfg_frozen_t0
    python scripts/run_forecast_track_f2_kma.py     # once the KMA archive is under data/raw/kma_forecast/

F1 refuses in about a second with a per-file list if the bundle is absent, persists each
stage as it finishes, and runs the NH-057 split **last on purpose** so a failure there
costs nothing before it. The figures (§2's last clause) are **not** written: they are the
one deliverable whose code could not be exercised at all here, and an untested plotting
script committed under `paper/` would be a guess with a runnable shape.

---

## 4. The thing this lap found that nobody asked it to look for

**A unit test written to check this lap's own freeze failed, and the bug was in the idiom
it had copied from `weather.py`.**

`WeatherSeries.at` resolves a time with `self.time.view("int64") - when.value`.
`Timestamp.value` is **always nanoseconds**; `DatetimeIndex.view("int64")` is the index's
**own** resolution. Under the pinned `pandas==3.0.5`:

| source array | index dtype | `at(T0 + 30 min)` picks |
|---|---|---|
| `datetime64[ns]` | `datetime64[ns, UTC]` | index 0 — correct |
| `datetime64[us]` | `datetime64[us, UTC]` | the **last** index — wrong |
| `datetime64[s]` | `datetime64[s, UTC]` | the **last** index — wrong |

On a 24-hour series with T0 at 10:30 the first freeze took **index 23** — hours after T0 —
**silently**. `weather.py:123` (`secs = time.view("int64") / 1e9`) has the same shape.

This matters beyond F1: `at()` is how `forward_simulate` gets the weather for **every step
of every committed spread field**. If the real ERA5 index is not nanosecond-resolution,
those fields were driven by the **last** sample in the window — a correctness bug *and* a
second, independent post-T0 leak on top of the one this whole correction is about.

⚠ **This lap did not determine which case is real, and says so rather than guessing.** The
answer is the `valid_time` resolution inside the ERA5 `.nc`, which no clone can see.

**`weather.py` is unchanged.** Fixing it could move registered numbers (CHARTER §3 rules 2
and 3) — the author's call, escalated as **NH-062** with the measured table, three options,
and the one-line command that settles it in about a second on the laptop. F1 does not
inherit the bug (it compares `Timestamp`s directly) and
`tests/test_forecast_track_f1_freeze.py` gates that at all three resolutions, 14 cases.

---

## 5. Discipline

New filenames only; no committed artifact modified; `docs/figures/*.png` untouched; no new
pip imports; `docs/artifact_manifest.json` rebuilt after staging; the finals screen rebuilt.
`baseline-verify` WARNs at both commits on `MISSING data/raw/firms_data/*.json` — the
git-ignored bundle a sandbox never has (CHARTER §4 「Sandbox facts」), environmental and
pre-existing, not this lap's.

## 6. Open for the author

1. **NH-062** — the datetime-resolution bug in `weather.py`. One command settles it.
2. **Part B has no numbers.** It needs one laptop run.
3. **§1c** — whether 1,606's pages should carry the sentence too.
4. **§1b** — whether `README.md:328` should keep it.
5. **§1a** — the TL;DR and the Abstract draft still quote 42 without it, by NH-054 D and
   the `paper/` scope rule.
