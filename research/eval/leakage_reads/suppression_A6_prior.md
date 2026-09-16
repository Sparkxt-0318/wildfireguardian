# A6 prior leakage read, suppression (H-SUPP)

**Owner: A6. Written 2026-09-16, round 5.**

## Provenance of this document, and why the header matters

**This read was begun before any suppression pre-registration existed, and was
written without ever reading one.** Two claims, of different strengths, and the
difference between them matters enough to spell out.

*What I can attest without qualification.* Nothing under `research/suppression/`
and nothing under `research/reports/A5/` was read at any point, before, during or
after writing. Not a file, not a line, not a filename used as a hint about
content.

*What I can attest with a timestamp.* When this task began and I listed
`research/`, `research/suppression/` was an empty directory. A5 was drafting in
parallel and had filed nothing.

*What changed while I worked, which I am recording rather than glossing.* A5
created `research/suppression/design/` at 16:55:52 UTC, part-way through this
session, and it is no longer empty. I noticed only because a `git status` at the
end of the round showed the path as untracked, and I established the time from
directory metadata alone. My file's final modification stamp is later than that,
because I was still correcting verdict markers and a pragma after A5's directory
appeared.

So the honest version of the header is **not** "written before the reviewed
document existed", which is what I would have written if I had not checked. It is
that the read was begun before it existed, its substance was fixed from the
program brief and the committed CSVs alone, and the barrier that actually holds
is the one in the first paragraph: I never opened it.

I am labouring this because the entire value of this document is that its
provenance claim is exactly true. A provenance claim that is nearly true is worth
less than none, since it invites the reader to extend the same latitude to
everything else in the file.

This is the structural version of the fix that condition C10 made by promise.
On roads the review order ran backwards and the two leakage lists were not
independent. On landslides the order was corrected, but the briefing I received
had already named six of the ten convergent items, so the barrier was a ritual:
I could not have disagreed with A4 about items I had been handed. I raised that
as PF-1 and asked that the reviewer's prior-read briefing be drawn from the
program brief and the committed data alone.

Starting before the reviewed document exists is stronger than any rule about
reading order, because for most of the writing there was nothing to leak. That is
the reason this round was sequenced the way it was. The residual gap, that A5's
tree became non-empty before I finished editing, is closed by the first
attestation above rather than by the timing.

**What was consulted before writing.** All of it is material A5 also has, and
none of it is A5's analysis:

| source | what was taken from it |
|---|---|
| the program brief's suppression design, as stated in this round's task | the design under review |
| `research/README.md`, `research/data/REGISTRY.yaml` | scope rules, dataset ids, statuses, known issues |
| `research/eval/LEAKAGE.md` v1.0 | A6's own checklist, items A1 to A12 and D1 to D11 |
| `research/eval/SIGNOFF.md` v1.0 | items P1 to P16, and the section 4 rule on what counts as looking at data |
| `research/eval/KILLSHOT_TEMPLATE.md` | A6's own seeded suppression prior of 2026-09-16 |
| `research/eval/splits.py` | A6's own splitter and `PRIMARY_SPLITS["suppression"]` |
| `research/eval/NUMBERS_PROTOCOL.md` | the re-run levels, for section 7 |
| `research/FORBIDDEN_CLAIMS.md` | RC-006, RC-007, RC-008, and the rest |
| `research/TASKBOARD.md` | the Waiting-on-John items, WJ-001 and WJ-006 |
| the two committed CSVs themselves | every count in section 2, computed here |

## Handling instruction, which is part of the barrier

**This file must not reach A5 before A5 has filed its pre-registration.** Section
2 below contains outcome views, including a marginal night-versus-day comparison
on burned area, which is the direction's own headline contrast. If A5 reads this
first, the pre-registration becomes a post-registration and `SIGNOFF.md` section
4 applies to it from birth. The orchestrator owns that sequencing; I am naming it
because I am the one creating the hazard.

## Declaration under `SIGNOFF.md` section 4, of what I looked at

I have looked at the outcome variable. Listing it is mandatory and the list is
not short:

1. The burned-area column in full: count, minimum, maximum, quantiles, the count
   above each of eight size thresholds, and the same by year and by season.
2. The report-to-containment duration in full, and its cross-tabulation against
   burned area in seven duration bands.
3. The share of total burned area held by the largest one, two, three, five, ten
   and twenty five fires.
4. A marginal comparison of burned area and duration between fires reported at
   night and fires reported by day, unadjusted.
5. The report hour of day, for all fires and for fires at or above ten hectares.
6. The identity of the twelve largest fires by province and county.

Items 4 and 5 are the ones that matter, because they are views of the direction's
own contrast rather than of the record's structure. I did not compute any
held-out-year score, any discrimination measure, or any fitted quantity, and I
declined to compute the discrimination of the survival baseline of item S3 for
exactly that reason: the single usable fold is too scarce to spend on my own
curiosity before a design exists. That decision is recorded so that it can be
checked, and so that nobody later assumes the number was computed and suppressed.

Item A6 of the checklist, the analyst's memory, is therefore worse after this
document than before it. That is the price of the barrier and it is the right
trade, but it is a price and it is stated rather than hidden.

---

## 1. The design as briefed, restated

So that the comparison later is against a fixed target:

1. Data from the KFS fire statistics Open API, pulled for the longest range it
   returns, with a probe for 1991 to 2001 to establish the record's depth.
2. A discrete-time hazard on fire-hours, with time-varying local daylight, wind,
   humidity, cause and access distance. Fires still burning at the end of the
   record count as censored.
3. A generalized Pareto tail with covariate-dependent parameters. A partially
   interpretable neural extreme-value model only if the sample of large fires is
   confirmed sufficient.
4. Growth at night versus day under matched weather, with calm nights as a
   negative control, and an E-value for unmeasured confounding. Two named
   biases: dispatch responding to danger, and recorded start times that are
   report times.
5. A FasterRisk integer point score as the deliverable.
6. Evaluation on held-out years: tail-weighted Brier score and PR-AUC at the ten
   and one hundred hectare thresholds, plus a season-by-season ledger.

---

## 2. What the committed record actually is, computed here

Every number in this section was computed in this session from the two registered
raw CSVs directly, with the loaders bypassed. The statistics file is
`data/raw/kfs_fire_statistics/산림청_산불통계데이터_20250911.csv`, registry id
`kfs_fire_stats_csv`. The state history file is
`research/data/raw/kfs_fire_state_history_csv/산불상태별이력_2025.11.10.csv`,
registry id `kfs_fire_state_history_csv`. Both are at status `verified`. Both are
CP949, not UTF-8.

**The record is four calendar years and it is shrinking in the middle.** The
statistics file holds 2,020 rows: 756 in 2022, 589 in 2023, 278 in 2024 and 397
in 2025, the last ending 2025-09-11. The state history file holds 2,030 rows and
runs to 2025-11-10. The two files therefore do not end on the same day.

**The size distribution is short and its top is two fires.** Burned area runs
from 0.01 to 52,707.3 ha. 343 fires reach 1 ha, 114 reach 5 ha, 78 reach 10 ha,
48 reach 30 ha, 25 reach 100 ha, 12 reach 500 ha and 7 reach 1,000 ha. The
largest fire alone is 39.1 per cent of all area burned in four years, the largest
two are 73.6 per cent, the largest five are 91.3 per cent.

**Fires at or above 10 ha by year: 26, 32, 1, 19.** This reproduces the
orchestrator's figures exactly. 2024 has one fire at or above 10 ha, none at or
above 30 ha, and its largest fire is 19.8 ha.

**The two largest rows are the same day, the same county, and almost certainly
the same fire.** 2025-03-22 in 경북 의성 appears twice, at 52,707.30 ha and at
46,575.20 ha. The registry records this duplicate against the state history file.
It is also in the statistics file, and it sits at ranks one and two of the size
distribution. No exact duplicate row exists on date, place and area jointly, so a
naive deduplication does not find it. 53 rows share a date and a county with
another row.

**The median fire lasts two hours.** Report-to-containment duration, on the 2,008
rows where it is non-negative: median 2.00 h, upper quartile 3.53 h, ninetieth
percentile 6.71 h. 1,678 fires last at least an hour, 1,006 at least two, 639 at
least three, 227 at least six, 117 at least twelve, 66 at least a day.

**Duration and final size are very nearly the same variable.** Of fires lasting
under an hour, the largest is 0.7 ha. Under two hours, 2.8 ha. Under three hours,
5.0 ha. **No fire that reached 10 ha lasted under 3.67 h, and all 78 of them were
still burning at hour three.** Their median duration is 27.3 h. So the risk set
at hour three holds 639 fires and contains every large fire in the record: the
base rate at ten hectares rises from 3.9 per cent unconditionally to 12.2 per
cent among fires still burning at hour three, and to 32.6 per cent at hour six,
using no covariate at all.

**There is no administrative censoring in either file.** Missing containment time
is zero rows in both, independently recorded in
`research/data/interim/` by A2 and reproduced here. Every fire in the extract has
a containment time entered. The brief's censoring mechanism, fires still burning
at the end of the record, has no instances.

**The containment clock is rounded and the report clock is not.** Report-time
minutes are effectively uniform: 4.1 per cent land on the hour or half hour
against a uniform expectation of 3.3 per cent, and 14.5 per cent on a multiple of
ten minutes against 16.7 per cent expected, which is if anything below uniform.
Containment minutes heap violently: 25.6 per cent land exactly on the hour, 38.4
per cent on the hour or the half hour, and 61.2 per cent on a multiple of ten
minutes. The duration's measurement error is therefore concentrated entirely at
the closing end, at a granularity of up to half an hour, against a median
duration of two hours.

**The two files carry different clocks.** The statistics file's 발생일시 is a
report time and its 진화종료시간 a containment time, so its durations are
report-to-containment, median 2.00 h. The state history file's 진화시작시간 is a
suppression start and its 진화완료시간 a containment, so its durations are
suppression-start-to-containment, median 0.87 h, with 13.7 per cent lasting three
hours or more against 31.8 per cent on the other clock. The state history file's
report field, 산불신고일, is a date with no time: 1,999 of 2,030 suppression
starts fall on the reported date, so a dispatch delay cannot be computed from it
at better than day resolution.

**The state history file has no area column and the files do not join.** Its nine
columns are an id, a report date, an address, a suppression start, a containment,
an agency, a text-message flag, a sunrise and a sunset. The registry warns that
its id is not confirmed to share an identifier space with anything in the
statistics file. The addresses are in different formats: the statistics file
splits four short-form administrative fields (경북, 의성), the history file holds
one concatenated long-form string (충청남도천안시서북구성거읍). A date plus
county-substring match produces 2,132 candidate pairs for 2,030 history rows,
which is many-to-many and not a join.

**The text-message column has zero variance.** 문자전송여부 is `Y` for all 2,030
rows.

**The sunrise and sunset columns are one national value per date, and the error
lands where the night contrast is defined.** 607 dates, zero dates carrying more
than one sunrise or sunset value, confirming the registry. Computed from solar
geometry, sunrise and sunset across mainland Korea differ by 13 to 21 minutes
depending on the date, and by 19 to 26 minutes including Baengnyeong. Against the
national value, 4.4 per cent of suppression starts fall within thirty minutes of
the national terminator and 8.9 per cent within an hour. The national value
classifies 17.1 per cent of rows as night.

**The night stratum is small and it is not the same by either definition.** By
report hour in the statistics file, 210 of 2,020 fires (10.4 per cent) are
reported between 20:00 and 05:59, and 9 of those reach 10 ha. By the national
daylight columns in the history file, 347 of 2,030 rows (17.1 per cent) are
night.

**The unadjusted night contrast is close to null on size and clear on duration.**
Reported at night: 210 fires, median 0.16 ha, 4.29 per cent at or above 10 ha,
median duration 2.88 h. Reported by day: 1,810 fires, median 0.15 ha, 3.81 per
cent at or above 10 ha, median duration 1.93 h. The direction of the duration gap
and the flatness of the size gap are both what a reverse-causality story predicts,
and are equally what a slower-spread-at-night story predicts.

**Night is entangled with season.** The night share of reports runs 15.5 per cent
in January, 9.3 in March, 6.2 in April, 17.6 in May, zero in July and August, 2.6
in October, 14.4 in December.

**Reports cluster in the early afternoon.** 1,245 of 2,020 fires (62 per cent)
are reported between 11:00 and 15:59. The hour with most large fires is 14:00.

**The cause covariate is mostly free text.** 발생원인_세부원인 has eleven values,
of which 기타(직접입력), meaning other by direct entry, holds 1,479 of 2,020 rows
(73.2 per cent). 발생원인_구분 has four values and 294 nulls. Lightning accounts
for 8 rows.

**The administrative covariates are high-cardinality and thin.** 24 stations, 18
provinces, 215 counties, 783 towns, 1,445 villages. Median fires per county: 7,
maximum 44. Only 56 of 215 counties have ever recorded a fire at or above 10 ha.
307 rows have no town and 13 no county.

**Season is nearly the whole story.** Across the sixteen year-by-season cells,
only 11 hold any fire at or above 10 ha and only 5 hold any at or above 100 ha.
All five of those are spring except winter 2022. Summer contributes one fire at
or above 10 ha in four years, autumn one, and neither contributes any at or above
100 ha.

**The registered split refuses this extract, as it should.**
`PRIMARY_SPLITS["suppression"]` calls `forward_chaining_by_year` with
`min_train_years=10`. Run here on the four observed years, it raises
`LeakageRefusal`. Relaxed, four years give three folds at a one-year training
requirement, two at two years and exactly one at three years. The single
three-year fold trains on 2022 to 2024 (1,623 fires, 59 at or above 10 ha, 19 at
or above 100 ha) and tests on 2025 (397 fires, 19 at or above 10 ha, 6 at or above
100 ha).

**Every covariate the containment model needs, except cause, is at status
`pending`.** Local daylight needs coordinates, so it needs `vworld_geocoder`
(pending). Wind and humidity need `kma_asos_aws` (pending, blocked on WJ-001).
Access distance needs coordinates and a road layer, so `vworld_geocoder` plus
`kfs_forest_roads` (pending, blocked on WJ-017). Of the eighteen registered
datasets, three are `verified` and fifteen are `pending`. The covariates actually
on disk and knowable at the report hour are: year, month, day, hour, weekday,
station, four administrative address fields, and cause.

**The API that would lengthen the record is unreachable.** `kfs_fire_stats_api`
is at status `pending`, `DATA_GO_KR_KEY` is unset, and the 1991 to 2001 probe has
never run. The true depth of the Korean record is unknown to this program.

---

## 3. Part D of `research/eval/LEAKAGE.md`, run against this design

Severities are as registered in v1.0. Where I would now raise one, I say so
rather than editing the severity, because the registered severity is what the
refusal rule of `LEAKAGE.md` section "How to run it" operates on.

### D1. Any covariate computed over the whole fire duration leaks the outcome. CRITICAL. Verdict: `present`.

The item as written asks whether each covariate could have been written down at
the prediction horizon. On this record the answer is harsher than the item
anticipates, because duration and final size are not merely correlated, they are
close to a step function of one another: no fire under three hours reached 10 ha,
and all 78 fires at or above 10 ha were still burning at hour three. Final
duration is therefore not one leaking covariate among several. It is a
near-restatement of the label.

That makes three things collapse into one. The containment hazard's response
(time to containment), the tail model's response (final size) and the score's
label (size above a threshold) are the same measurement seen three ways. A
program that fits a hazard, then fits a tail, then distils a score is not
building three models on one dataset; it is building one model three times and
will read the agreement between them as corroboration.

*What would settle it:* a covariate table with a knowable-at time in hours for
every row, and a demonstration that removing every quantity whose value requires
the fire to be over leaves a covariate set that is not empty. On the committed
extract I expect that demonstration to leave: hour, weekday, month, station,
address and cause.

### D2. Reported size at hour h does not exist. CRITICAL. Verdict: `present`, confirmed against both files.

The statistics file carries exactly one area column, 피해면적_합계, entered at
containment. The state history file carries no area column at all. There is no
size time series anywhere in the committed data, so any feature resembling early
size is a reconstruction, and the reconstruction's assumptions would be doing the
work.

*What would settle it:* either a data source with a timestamped perimeter or
timestamped area (FIRMS active fire detections are the only candidate in the
registry, and are `pending`), or an explicit statement in P4 that no size-like
covariate is used at any horizon.

### D3. Report time is not ignition time. MAJOR as registered. Verdict: `present`, and I would raise it to CRITICAL.

The item says fires reported late are already large when the clock starts. That is
right and it is the smaller half of the problem. The larger half is that the
clock's zero is a different physical stage of the fire for every fire, and the
offset is unobserved and is correlated with precisely the things the direction
wants to measure. A fire in a remote valley at night is reported later, is bigger
at report, and is bigger at containment. So report delay is upstream of size,
correlated with night and with remoteness, and absent from the record.

Two findings sharpen it beyond the v1.0 text.

First, **the two committed files do not even agree on the clock.** One measures
report to containment, the other suppression start to containment, and the medians
are 2.00 h and 0.87 h. A "fire-hours" hazard is a different model depending on
which file supplies the clock, and the choice moves the share of fires surviving
to hour three from 31.8 per cent to 13.7 per cent. The pre-registration must name
the clock, and naming it is not a formality: it is choosing the estimand.

Second, **the offset cannot be estimated from the record**, because the history
file's report field is a date with no time.

*What would settle it:* a Korean source that timestamps detection separately from
report, or a stated sensitivity analysis over an assumed report-delay
distribution with its range declared in advance, reported as a band. Absent
either, P15 has to say that the hazard is a hazard on time since report and not
on time since ignition, and the deliverable score has to be described as taking
effect from the report, which is what a dispatcher actually has.

### D4. The tail model is fitted to what suppression left behind. CRITICAL. Verdict: `present`. This remains the direction's central threat.

The quantity the direction most wants, the size a fire would have reached without
suppression, is not observed for any Korean fire and cannot be, because
suppression is applied to every one. There is no subgroup of unsuppressed fires,
no natural experiment named in the brief, and nothing in the committed record that
marks a fire as having been left alone. Identification therefore comes entirely
from an assumption about how the containment hazard would behave in its absence,
and that assumption is not checkable against anything in the data.

The committed extract makes this worse in a specific way. A generalized Pareto
shape parameter is determined by the largest exceedances. Here the largest two
observations are 73.6 per cent of all area burned and are, on the evidence of
section 2, plausibly one fire entered twice. A shape parameter fitted on 25
exceedances above 100 ha, whose top two may be a duplicate, is not an estimate of
a tail; it is a summary of a data-entry decision.

*What would settle it:* real variation in suppression intensity that is not itself
a response to fire behaviour. Candidates worth looking for, none of which are in
the registry: fires where resources were committed elsewhere on the same day, an
aircraft fleet grounded by weather independent of the fire's own conditions, or a
documented change in dispatch doctrine that lands mid-record. The discriminating
test remains the one in `KILLSHOT_TEMPLATE.md`: sensitivity of the tail across a
declared range of the identifying assumption, reported as a band. If the band
spans the operationally meaningful range, the correction does not support a
number and the deliverable becomes the score, which does not need the
counterfactual.

### D5. Forward chaining only, and the committed data does not support it. CRITICAL. Verdict: `present`.

Confirmed by running the registered call: four distinct years cannot satisfy
`min_train_years=10`, and the splitter refuses. Relaxing to a three-year training
window yields exactly one fold.

The deeper point, which the item's v1.0 text does not make, is that **a year is
not an independent unit here**. The task asks whether a held-out year is really
held out given that weather and policy are shared within a year. It is not, for
three reasons that are separable.

*Weather.* Korean large fires are a spring phenomenon driven by synoptic
conditions that last days. A single Föhn episode over the Yeongnam coast produces
several of the record's largest fires within the same week. Holding out a year
holds out those episodes, which is correct, but it also means the held-out year's
score is a sample of a handful of episodes and not of 397 independent fires. The
resampling unit is the episode, and the effective sample size at the tail is
single digit.

*Policy.* Four years is one doctrine period, one leased helicopter fleet
generation and one reporting regime. So forward chaining over 2022 to 2025 does
not test the thing forward chaining exists to test. It gives the appearance of a
temporal guard while guarding nothing, which is worse than no guard, because a
reader sees "forward-chained held-out year" and grants it the credit that phrase
normally earns.

*Boundary.* The registered kwargs set `gap_years=0`. A fire reported on 31
December and contained in January straddles the fold boundary, and any weather
covariate with a look-back window crosses it too. On this record that is a small
number of fires, but the embargo is free and its absence is a stated defect.

*What would settle it:* the longer record, which is WJ-001 then WJ-006. Until
then, the honest options are to fit nothing, or to pre-register a descriptive
analysis that makes no held-out claim and says so in P1 and P15. My splitter
already refuses the alternative, and that refusal should not be worked around by
lowering `min_train_years` in the registry.

### D6. The point score is a second model and needs its own held-out year. CRITICAL. Verdict: `unresolved`, and on four years it is unavailable.

The distillation into a FasterRisk integer score is model selection and needs
years that neither the hazard model nor the distillation has seen. Four years
cannot supply three roles. Any allocation that gives the hazard model a training
set, the distillation an inner set and the evaluation a clean set leaves at most
one year each, and the evaluation year would be 2024, which has one fire at or
above 10 ha and none at or above 100 ha.

*What would settle it:* more years. Failing that, a pre-registration that states
the score is fitted and evaluated on the same years, reports that as a known
optimism, and makes no held-out claim, which RC-008 then constrains to a
statement with its evaluation frame attached.

### D7. Administrative target encoding. MAJOR. Verdict: `present`.

215 counties with a median of 7 fires each. A county-level escape rate computed
over the record is, for the median county, the outcome of 7 fires including the
one being predicted. Only 56 counties have ever had a fire at or above 10 ha, so
a county encoding at that threshold is a binary memorisation of which 56 counties
they were. 24 stations is a safer cardinality but the same mechanism.

*What would settle it:* either drop administrative encodings, or compute them
inside the training fold with the encoding function declared in P4, and report
the encoded value's shrinkage. With one fold, in-fold recomputation is nearly
vacuous, which argues for dropping.

### D8. Duplicate fire records counted twice. MAJOR. Verdict: `present`, and worse than the registry currently records.

The registry attaches the Uiseong 2025 duplicate to the state history file. It is
in the statistics file too, and it occupies ranks one and two of the size
distribution, which is the worst possible place for it. The two rows differ in
area, so an exact-duplicate check on date, place and area finds nothing: there are
zero exact duplicates on that key.

Whether they are one fire entered twice or two genuinely separate ignitions in
의성 on 2025-03-22 is not decidable from the file, and the K-SPREAD complex rule
in `splits.py` groups Uiseong-Andong with Yeongdeok as one complex for a related
reason. What is decidable is that the answer changes the fitted tail shape
materially, because it changes the top of the distribution.

*What would settle it:* the K-SPREAD benchmark's own account of the Uiseong and
Andong perimeters, or the KFS record with its incident identifiers, which the
Open API may carry and the CSV does not. Until then, a pre-registered rule for
these two rows, declared before the tail is fitted, plus the tail refitted both
ways and both reported.

### D9. Outcome-dependent cleaning. MAJOR. Verdict: `unresolved`.

The 12 negative durations and the 2 impossible end years (2055 and 2223) are
outcome-side defects and are independently counted three times over in this
repository. No rule for them is stated in the brief. Their areas are 0.55 and 0.20
ha, so the two impossible end years are small fires and dropping them has little
effect on the tail, but the rule has to exist before anyone knows that.

*What would settle it:* a rule in P3 or P4, declared in advance, that names what
happens to each of the 14 rows, with the count reported either way. My standing
position is flag, count and report, never silently drop.

### D10. Night as a covariate carries reverse causality. MAJOR. Verdict: `present`, and the binding constraint is not the one the brief names.

The brief requires an E-value for unmeasured confounding, which is the right
instrument for the confounding it is aimed at. But an E-value quantifies how
strong an unmeasured confounder would have to be to explain away an observed
association, and on this record the association barely exists to explain away:
unadjusted, 4.29 per cent of night-reported fires reach 10 ha against 3.81 per
cent of day-reported ones, on 210 night fires of which 9 are large. The
comparison the E-value would be applied to rests on 9 events.

Three distinct threats sit under this item and the brief names only two.

*Reverse causality from dispatch*, which the brief names. Dispatch responds to
danger. Aerial assets are grounded at night in Korean practice, so night fires
receive a different and generally slower suppression, which is visible here as a
longer median duration (2.88 h against 1.93 h) with no corresponding size gap.
That pattern is equally consistent with night suppressing more slowly and with
night spreading more slowly, and the record cannot separate them without the
weather that is `pending`.

*Report-time bias*, which the brief names, and which interacts with night
specifically. Fires at night are seen later. So the night stratum is enriched in
fires that were already larger at their clock zero, which biases the early hazard
downward for night and does so in the same direction as the hypothesis.

*Selection into the night stratum*, which the brief does not name. Night share
varies by month from zero in July and August to 17.6 per cent in May, and the
large fires are overwhelmingly spring. So a night indicator is partly a season
indicator, and matching on weather does not fix that, because the strata that
would make the match work are the ones with no large fires in them.

Under RC-007 nothing here may be stated causally, and I do not expect the E-value
to be the thing that decides this item.

*What would settle it:* `kma_asos_aws` at status `verified` and geocoded fire
locations, so that "matched weather" means matched on measured wind and humidity
at the fire rather than on a national daylight flag; plus a pre-registered
negative control that is genuinely a control, which calm nights can be only once
wind is observed.

### D11. The threshold of the tail model is a researcher degree of freedom. MAJOR. Verdict: `present`.

The exceedance count over the plausible threshold grid runs 306 at 1 ha, 195 at 2,
110 at 5, 78 at 10, 57 at 20, 38 at 50 and 25 at 100. That is a twelve-fold swing
in sample size across a grid any analyst would consider reasonable, and the shape
parameter is unstable across it by construction. Choosing the threshold after
seeing which one gives a clean fit is the single easiest unreported decision in
this direction.

*What would settle it:* the threshold and the full grid declared in P5 before the
fit, every value in the grid reported, and the diagnostic (mean residual life or
equivalent) named in advance rather than read off afterwards.

**On the neural extreme-value model.** The brief says to consider it only if I
confirm the sample of large fires is sufficient. I do not confirm it. A
covariate-dependent generalized Pareto with the brief's five covariates already
carries roughly a dozen free parameters against 78 exceedances at 10 ha or 25 at
100 ha, and shape parameters are the worst-identified quantities in extreme value
statistics. A neural parameterisation multiplies the parameter count against a
sample whose top two observations may be one fire. The answer is no, and it is not
close.

---

## 4. Part A of `research/eval/LEAKAGE.md`, run against this design

| id | severity | verdict | one line, and what would settle it |
|---|---|---|---|
| A1 preprocessing inside the fold | CRITICAL | `unresolved` | Nothing in the brief says where the tail threshold, any standardisation or any cause recode is constructed. With one fold, a transform fitted once over everything is indistinguishable from a correct one by inspection. *Settled by:* every parameterised transform constructed inside the fold loop, or declared as a constant in the pre-registration. |
| A2 hyper-parameters and priors | CRITICAL | `unresolved` | The threshold, the FasterRisk sparsity and integer range, and any prior scale are all unstated. With a single usable fold, one look at the held-out score is the entire evaluation. *Settled by:* values fixed in P5, and a fit count recorded under P10. |
| A3 feature selection before the split | CRITICAL | `unresolved` | FasterRisk selects features. Doing that over the pooled record and then quoting a held-out year gives an optimistic score on covariates that may carry nothing. *Settled by:* the selection run inside the training fold, with the covariate pool fixed in P4. |
| A4 feature support crossing the boundary | CRITICAL | `present` | Weather is synoptic, so every fire on a given day shares its field, and the registered kwargs set `gap_years=0`, so a fire reported 31 December and contained in January straddles the fold edge. *Settled by:* a non-zero embargo, and a support statement per covariate in P4. |
| A5 duplicates and near-duplicates | MAJOR | `present` | See D8. The known duplicate is the top two rows of the size distribution and is invisible to an exact-key check. *Settled by:* a declared near-duplicate rule and both counts reported. |
| A6 the analyst's memory | MAJOR | `present` | Everyone in this program knows what Uiseong 2025 and Uljin 2022 were, and those two fires are 73.6 per cent of the burned area. This document adds to the problem, per the declaration above. *Settled by:* nothing. It is stated in P15 and in the paper, not cured. |
| A7 undocumented fits | MAJOR | `unresolved` | No fit count is stated. *Settled by:* P10, and the count reported beside the result. |
| A8 outcome-driven cleaning | MAJOR | `unresolved` | See D9, and add the containment-time rounding of S1: any rule that drops sub-hour durations as implausible would remove 330 fires, all of them small. *Settled by:* rules declared in advance and functions of covariates, not residuals. |
| A9 geocoder drift | MINOR | `present`, and it reaches further than this item's usual scope | `vworld_geocoder` is `pending`, 307 rows have no town and 13 no county. More sharply, an administrative boundary moved inside the observation window and the record follows it: 군위 appears under 경북 in 2022 and 2023 (8 rows) and under 대구 in 2024 and 2025 (6 rows), the transfer having taken effect mid-2023. So the same place is two counties on opposite sides of a fold boundary, which is a year boundary. That touches D7 as well, because a county encoding splits 군위 into two thin strata, and D5, because the split is exactly where the encoding changes. *Settled by:* a county-code crosswalk frozen to one vintage and applied to the whole record before any encoding, with the geocoder version and date recorded and precision carried as a covariate. |
| A10 outcome-dependent missingness | MAJOR | `present` | 294 nulls in the cause class and 1,479 of 2,020 causes recorded as free-text other. A cause is written down properly when somebody investigated, and somebody investigates when the fire mattered. So cause completeness is a function of the outcome. *Settled by:* a missingness indicator carried as its own level rather than rows dropped, and the large-fire cause completeness rate reported against the overall rate. |
| A11 resampling unit | MAJOR | `present` | The cluster is the synoptic episode, not the fire: 53 rows share a date and county with another row, and the record's largest fires arrive in clusters within single spring weeks. An interval resampled over fires is too narrow. *Settled by:* an effective-sample-size estimate at the tail under P2, and resampling at the episode level with the episode rule declared. |
| A12 foreign quantity entering through a prior | MINOR | `unresolved` | FasterRisk, the generalized Pareto and the neural extreme-value family are foreign methods, which scope rule 1 permits. A shape or scale prior taken from a foreign fire record would not be. *Settled by:* P14 listing each foreign source with the sentence that it supplies a method and not data, and any prior stated with its source and checked by a flat-prior sensitivity run. |

---

## 5. Items not in `research/eval/LEAKAGE.md` v1.0, found in this pass

Numbered S1 onward and candidates for a v1.1 of Part D.

### S1. The containment clock is administratively rounded and the report clock is not, so a fire-hours hazard has its error at one end and on its own bin boundaries. CRITICAL. Verdict: `present`.

25.6 per cent of containment times land exactly on the hour, 38.4 per cent on the
hour or half hour, 61.2 per cent on a multiple of ten minutes. Report times show
no such heaping at all. Two consequences, and the second is specific to the
briefed model form.

First, the duration's measurement error is one-sided in location, sitting entirely
at the closing end, with a granularity of up to half an hour against a median
duration of two hours. That is up to a quarter of a typical fire's recorded life,
and it is larger in relative terms for short fires, which are the majority.

Second, a **discrete-time hazard on fire-hours bins time into hours, and the event
times are already snapped to the hour.** A quarter of all containments fall
exactly on a bin boundary. The fitted hazard will show spikes at integer hours
that are artefacts of the data-entry convention, and those spikes will be
interpretable as something real, because shift changes and daylight transitions
also fall near round hours. This is a defect that a discrete-time model is
uniquely bad at tolerating, and choosing a coarser bin does not fix it, it only
moves it.

*What would settle it:* a bin width declared in advance that is not a divisor of
the heaping period, a reported heaping diagnostic (the share of events on the bin
edge) beside the fitted hazard, and a sensitivity run under a declared jitter or
interval-censoring treatment where each containment is treated as falling within
its rounding interval rather than at its recorded instant. Interval censoring is
the statistically correct handling here and it is the honest one.

### S2. The censoring the brief models does not exist in this extract, and the censoring that does exist is not of that kind. CRITICAL. Verdict: `present`.

The brief says fires still burning at the end of the record count as censored.
Missing containment time is zero rows in both committed files. There are no such
fires. The administrative right-censoring that a survival model would handle
routinely has no instances here, so the censoring machinery the design proposes
is machinery with nothing to operate on.

The censoring that actually threatens this direction is a completely different
object: it is suppression itself, which is not a censoring event in the survival
sense at all, because it is the treatment rather than the end of observation, it
is applied to every unit, and its intensity is a response to the outcome. Calling
both of these censoring in one design invites the reader, and the author, to
believe the second is handled because the first is.

Under RC-006 this must not be described as censoring having been handled. The
distinction belongs in P1 and P5 in plain words: administrative censoring is
absent, and suppression is confounding by indication, not censoring.

*What would settle it:* the longer record, which may well contain fires open at
the extract boundary and would give the censoring term instances. Failing that,
an explicit statement that the censoring indicator is constant.

### S3. Survival to hour h is itself the dominant predictor, and it is an observation rather than a forecast. CRITICAL, and it is also the P8 baseline. Verdict: `present`.

All 78 fires at or above 10 ha were still burning at hour three. Conditioning on
survival to hour three takes the base rate from 3.9 per cent to 12.2 per cent, and
to 32.6 per cent at hour six, using no covariate at all.

This has two edges and both matter.

The favourable edge: it is a real operational fact, it is available to a
dispatcher, and it is the honest baseline that any score must beat. `SIGNOFF.md`
P8 requires a baseline that is genuinely simple and named in advance with a margin
in the units of the primary metric. **The baseline for this direction is
"still burning at hour h", and it should be fixed now, before anybody sees what
the covariate model scores.** I deliberately did not compute its held-out
discrimination, so that number is still clean for whoever fits it.

The unfavourable edge: if the covariate model cannot beat it by the declared
margin, the direction's deliverable is the observation that a fire still burning
at hour six is more likely to get large, which is not a finding and would not
survive a reviewer. And because the label threshold sits at 10 ha while no fire
under 3.67 h ever reached 10 ha, a score that merely encodes "this fire is not
over yet" will look good at both thresholds for a reason that has nothing to do
with fire behaviour.

*What would settle it:* the baseline implemented, its score computed once on the
declared held-out frame, and a margin agreed in advance. This is the single most
informative experiment available on the committed extract, and it can be run
without the pending datasets.

### S4. The clock and the outcome live in different files, and the files do not join. CRITICAL. Verdict: `present`.

The state history file has the suppression-start clock and no area. The statistics
file has the area and a report-to-containment clock. The registry warns that their
identifiers are not confirmed to share a space, and the addresses are in
incompatible formats, so a date-plus-county match returns a many-to-many
correspondence rather than a join.

So a hazard on the suppression clock cannot be linked to a final size, and a tail
on final size cannot be linked to a suppression clock. The design as briefed
needs both in one model.

*What would settle it:* a join key, which the Open API may supply and the CSVs do
not, or a pre-registered fuzzy matching rule with its match rate and its false
match rate estimated on a hand-checked sample, declared before the fit and
reported. Absent both, the direction has to choose one file and accept its clock,
and P2 has to say which.

### S5. Every time-varying covariate in the briefed model is at status `pending`. CRITICAL. Verdict: `present`.

Local daylight, wind, humidity and access distance are all unavailable: two are
blocked on WJ-001, the road layer on WJ-017, and all of them need coordinates the
program cannot yet produce. Of the brief's five named covariates, only cause is on
disk, and item S8 explains what condition it is in. A discrete-time hazard with
time-varying covariates, fitted on a record with no time-varying covariates, is
not a reduced version of the briefed model; it is a different model.

Under `SIGNOFF.md` P12 a `pending` dataset may appear in a pre-registration, but
the sign-off is then `signed with conditions` at best and the fit does not start
until the status reaches `verified`. On the present registry that condition
attaches to four of the five covariates, which effectively means the containment
model does not start.

*What would settle it:* WJ-001, then WJ-017, then the geocoder. Nothing else.

### S6. The daylight column is national, and its error is concentrated exactly where the night contrast is decided. MAJOR. Verdict: `present`.

Sunrise and sunset in the state history file are a single national value per date,
confirmed over 607 dates. Solar geometry puts the true spread across mainland
Korea at 13 to 21 minutes depending on the date. 4.4 per cent of rows sit within
thirty minutes of the national terminator and 8.9 per cent within an hour.

The misclassification is therefore not random with respect to the outcome, for a
reason that is particular to fire. The dawn and dusk transitions are when relative
humidity and wind change fastest, so they are when the day-night growth
difference, if it exists, is largest. The rows most likely to be misclassified are
the rows carrying most of the contrast's information. That biases the estimated
day-night difference toward zero, in the same way item B12 describes for road
width, and the asymmetry has to be written into the reading rule before the fit: a
null night contrast on this column is weak evidence, while a large one measured
under this error is stronger than it looks.

*What would settle it:* local solar times computed from the fire's own coordinates,
which the registry's own known-issues note already instructs. That needs
`vworld_geocoder`. Until then, a declared exclusion of the rows within a stated
window of the national terminator, with the count reported, is the partial fix,
and it must be declared before anyone sees which way it moves the answer.

### S7. The season-by-season ledger has empty cells by construction, and the direction is a spring-fire direction. MAJOR. Verdict: `present`.

Across the sixteen year-by-season cells, only 11 hold any fire at or above 10 ha
and only 5 hold any at or above 100 ha. Summer contributes one large fire in four
years and autumn one, and neither contributes any at or above 100 ha. The 2024
row is empty at 30 ha and above in every season.

So a PR-AUC in a summer or autumn cell is undefined or is computed on one positive,
and the ledger the brief asks for will be mostly blank. A tail-weighted Brier score
in those cells is computable but is a score against an all-negative reference,
which measures calibration of near-zero predictions and nothing else.

More importantly, the ledger's blankness is the finding rather than a formatting
problem: the direction's claim, whatever it turns out to be, holds for Korean
spring fires, and P14 and P15 have to say so.

*What would settle it:* the ledger pre-registered with the cells that will be
reported as empty named in advance, and the primary metric defined on a frame that
has positives in it. The longer record would populate the off-season cells
somewhat, but the seasonality is real and would not disappear.

### S8. The cause covariate is three-quarters free text, and its completeness depends on the outcome. MAJOR. Verdict: `present`.

1,479 of 2,020 rows have cause recorded as 기타(직접입력), other by direct entry,
with the substance in a free-text field of 455 distinct values. The four-value
class column has 294 nulls. Lightning is 8 rows, so effectively every Korean fire
in this record is human-caused, which means cause is a proxy for who was where and
doing what, which is also a proxy for how quickly somebody noticed, which is the
report delay of D3.

Turning 455 free-text strings into model categories is a coding exercise, and a
coding exercise performed by somebody who has seen the outcomes is feature
engineering on the label.

*What would settle it:* a coding scheme written and frozen before the outcomes are
joined, ideally coded by a rule over the text rather than by hand, with the rule in
P4 and the resulting category counts reported. And a missingness level carried
explicitly rather than 294 rows dropped.

### S9. The duration and the area are entered by the same office at the same moment, so their association may be a recording artefact rather than a fact about fire. MAJOR. Verdict: `unresolved`, and undecidable from the file.

Section 2 shows a near-deterministic relation between duration and final size. The
natural reading is physical: fires that burn longer burn more. But 피해면적_합계 is
an assessed damage area entered at containment, not a measured perimeter, and the
assessor knows how long the fire ran and how many resources were committed. If the
area assessment is informed by the duration, then the relation is partly the
assessment procedure and not the fire, and every model in this direction is fitting
the procedure.

This is not decidable from the committed record, and I do not assert it is
happening. I assert that it cannot be ruled out and that the direction's entire
structure rests on the relation being physical.

*What would settle it:* independently measured burned area for a subset, which
Sentinel-2 dNBR could supply for the large fires (`sentinel2_l2a_dnbr`, `pending`),
compared against the recorded area. For the handful of fires in the K-SPREAD
benchmark the repository may already have perimeters, and that comparison is worth
doing before anything is fitted, because it is cheap and it bears on everything.

### S10. The record is four spring seasons in one doctrine period, so the scope sentence is narrower than "Korean fires". MINOR, and it bounds the claim. Verdict: `present`.

Not a leakage path. A P14 and P15 sentence: any result from this extract is about
fires reported to the Korea Forest Service between 2022 and 2025, overwhelmingly in
spring, under one suppression doctrine and one fleet generation, with sizes as
assessed by the responding agency. Whether it generalises to the 1990s Korean
record is exactly the question the 1991 probe was meant to answer and cannot,
because `DATA_GO_KR_KEY` is unset.

---

## 6. Grade summary

| | CRITICAL | MAJOR | MINOR | total |
|---|---|---|---|---|
| `present` | 10 | 12 | 2 | 24 |
| `unresolved` | 4 | 4 | 1 | 9 |
| `clean` | 0 | 0 | 0 | 0 |
| `mitigated` | 0 | 0 | 0 | 0 |
| `not applicable` | 0 | 0 | 0 | 0 |
| **total** | **14** | **16** | **3** | **33** |

Not one item on this sheet came back `clean` or `mitigated`. That is unusual and I
want to be careful about it, because a checklist that refuses everything is as
useless as one that refuses nothing. The reason it happened here is not that the
design is careless. It is that the design was written for a record that would come
back from the Open API, and the record that exists on disk is four years of a
different shape. Most of these verdicts would move if WJ-001 cleared and the probe
returned a long series. Several, specifically D4, S1, S2, S3 and S9, would not
move at all, because they are properties of how the Korean record is made rather
than of how much of it there is.

Under the refusal rule in `LEAKAGE.md`, 14 CRITICAL items at `present` or
`unresolved` without an accepted scope cut refuse the sign-off. I expect to write
that refusal. It is a refusal of the design as briefed against the committed
extract, not a judgement that the direction is worthless, and section 8 says what
I think survives.

---

## 7. What I will and will not accept as evidence later

Recorded now so that it cannot be adjusted after the fact.

- A number from this direction reaches L2 in `NUMBERS_PROTOCOL.md` only if I can
  re-derive it from the registered raw CSVs by my own path, with my own split, and
  the split fingerprint matches P6. On one usable fold there is no fingerprint
  diversity to hide in, which makes this easier than usual.
- A held-out claim quoted without its year is refused under RC-008 regardless of
  its value.
- A statement that censoring has been handled is refused under RC-006. The <!-- research-claim-ok: RC-006 -->
  permitted shape is that administrative censoring is absent from the extract and
  that suppression is treated as confounding by indication.
  (That line carries a pragma because the rule fires on it. It is a legitimate
  neighbour of the shape RC-006 exists to stop: a statement *about* the forbidden
  wording rather than an instance of it. `FORBIDDEN_CLAIMS.md` pragmas its own
  RC-006 row for the same reason, so this is the established handling rather than
  a workaround. If a v1.1 of the rule set is ever cut, this shape belongs in
  RC-006's spares corpus.)
- A causal night statement is refused under RC-007. An E-value does not license
  causal wording by itself here, for the reason in D10: the association it would
  be applied to rests on 9 large fires.
- A tail shape parameter quoted as an estimate, from 25 exceedances whose top two
  may be one fire, is refused whatever its interval.

---

## 8. Where I expect this to land, written before reading A5

Recorded now so it can be checked later.

I expect to **refuse** the design as briefed, on D4 first, then S2 and S1
together, then D5 with S7, then S5. I expect the generalized Pareto arm to be
unavailable on this extract and the neural extreme-value model to be unavailable
outright, and I have said so in D11 rather than leaving it to be argued. I expect
the night comparison to be unavailable until `kma_asos_aws` is `verified`, and to
be weak even then because of S6 and the size of the stratum. I expect the
containment hazard to be unavailable because four of its five covariates are
`pending`, per S5.

What I expect to survive, and what I would advise the direction be rebuilt around,
is narrower and I think it is real. The committed extract can support a
pre-registered descriptive artifact with no held-out claim, containing: the
survival-to-hour-h baseline of S3 stated as an operational fact with its
evaluation frame attached; the measurement-quality findings of S1, S2, S4, S6 and
S8, which are properties of the Korean record that a user of that record needs to
know and which nobody has written down in this program before; and the tail
concentration and duplicate arithmetic of D8, which bears directly on how anyone
should fit a Korean fire size distribution. That is a methods contribution rather
than the modelling contribution the brief wants, and I think it is the only
defensible thing on four years.

**My prior on whether this direction can produce anything defensible on a
four-year record**, written before reading A5: the escape-risk score cannot, the
tail cannot, and the night comparison cannot. The record's own defects can, and
they are worth documenting properly, but a direction whose deliverable is a
critique of its input data should be described that way from the start rather than
arrived at after a fit fails. If the program wants the score, the binding item is
WJ-001 and then WJ-006, and the direction should wait rather than fit small.

I will revise any of this in response to a fact from A5 and not in response to
persistence, per `SIGNOFF.md` section 5.
