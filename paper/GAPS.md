# Gaps — what the manuscript still lacks

Every `[GAP: …]` in `manuscript.md` has a row here (the gate checks both ways).
Close a gap by replacing the marker with prose backed by an artifact and
deleting the row. Gaps marked *after sprint* need the laptop-only raw bundle or
the author.

| # | where | what is missing | closes when | after sprint? |
|---|---|---|---|---|
| G5 | §4.7 Results | the provenance of the detection reference clock. Every delay in Table 4 is measured from `fire_manifest.json`'s `start` field, which the manifest marks "provenance only" and sources nowhere. **Narrowed 2026-09-04 (paper lap 3), and the repository has now come to the same reading.** Checked this lap against `docs/data_provenance/fire_manifest.json` — the only copy tracked here; the copy the pipeline actually reads, `data/raw/firms_data/fire_manifest.json`, is git-ignored and absent from a fresh clone, so this is the documentation copy and is assumed, not verified, to match. In it: all six entries mark `start/end/reported_ha` as `provenance only`, and **no entry contains 신고 or any word for a report**. That much is solid and is what the manuscript rests on. ⚠ **What this lap first wrote here, and the lap reviewer knocked down**: that exactly one entry says what the field is, namely `yeongdeok_2025`, whose note reads `first hit (2025-03-25) lags the 2025-03-22 ignition by days` against that entry's own `start` of `2025-03-22T12:15+09:00`. That is an inference from a date coincidence, not a statement — the note never mentions `start` — and it is probably the wrong inference: `2025-03-22` is the **parent Uiseong chain's** ignition date (its own `start` is `2025-03-22T11:25`, fifty minutes earlier), while Yeongdeok's first detection is three days later, so the "ignition" that note names is most plausibly the parent fire's, not Yeongdeok's. `docs/detection_floor.md` §1 reads the same five other notes as saying nothing about `start` either. So the honest statement is the weaker one: **no entry says what the field is, in either direction.** The manuscript was corrected to that before this lap pushed. `docs/detection_floor.md` §1 and §9 read the field as a 신고 (report) time and concluded that GK2A rang after the telephone; **that reading was withdrawn on 2026-09-04 (WFG-053) with no number moving**, the manuscript having reached the narrow form first. Until a call time exists the paper cannot say whether the satellite beat the call, in either direction | the author supplies, for at least one of Uiseong-Andong, Gangneung or Hongseong, the KFS / 119 / 중대본 record giving the 신고접수시각, or the acquisition note saying where the minute came from; then it is registered with agency and date and §4.7, §1, §5 and the abstract can state the ordering. Raised by the lap-2 reviewer (NEEDS_HUMAN NH-019) | no |
| G2 | §5 Discussion | the **practitioner** consultations (fire-service duty officer, village head, social worker) in the project's consultation format, as design feedback rather than collected data; any quotation needs the author's consent handling first. **Narrowed 2026-09-05 (paper lap 6):** the *researcher* half is no longer missing — `docs/auto/research/EXPERT_REPLIES_2026-09-04.md` records three written replies to the author on 2026-09-04, and §5 now carries the two questions one of them raises that nothing here answers (age-only rescue prioritisation; the division of roles between forest-fire suppression and residential emergency response), while a second reply's off-network walking point became a §6 limitation and the third's WUI-transfer point a clause in §2. ⚠ **The paper names nobody.** That doc names the three by the author's decision *for the repository*; consent to be named there is not consent to be cited in a publication, so the manuscript says "an external researcher" and "three domain researchers". Before submission the author either obtains explicit permission to cite each as a personal communication, or leaves the attribution as it stands | the practitioner consultations happen and the author clears the quotations (NH-009); separately, the author decides whether to seek naming permission from the three researchers | yes |
| G3 | §6 Limitations | the leak-free Yeongdeok fold: refit the Yeongdeok LOFO fold with the co-located Uiseong-Andong fire excluded, re-simulate the canonical field, and route the same 458 origins, reporting the three-bucket counts as new filenames | the raw acquisition bundle on the author's laptop is available and WFG-032 runs | yes |
| G4 | §6 Limitations | **the hindsight-field routing arm — the single most load-bearing gap in the paper.** A third pass over the same 458 origins on a field rasterised from the *observed* FIRMS detections for Yeongdeok 2025, reporting how many of the 42 fire-blind routes actually intersect observed burn inside the walker's arrival window, and how many forecast-aware routes cross observed burn the model never flagged. Until it runs, "saved" means "re-routed around a model-flagged cell", not "away from where the fire went", and with pooled recall 0.138 that distinction is not cosmetic | the observed detections are available. ⚠ Checked 2026-09-03: `data/snapshots/firms-manifest_yeongdeok-2025_20260723_1aa75824.json` is committed and records 2,290 detections spanning 2025-03-25T12:25 to 2025-03-27T04:28, but the detections themselves (`yeongdeok_2025_detections.csv`) live under the git-ignored `data/raw/firms_data/`, which is absent from a fresh clone. So this arm needs the author's laptop too — it is cheaper than G3 (no refit, no re-simulation, reuses the committed walk graph and origin list) but it is not runnable in the cloud sandbox | yes |
| G6 | §6 Limitations | the refuge-provenance comparison. Every refuge in the paper is an OpenStreetMap point; the 주소정보누리집 designated-site subset for 영덕군 is now committed and correctly scoped, and nothing has been re-routed against it. The question the paper cannot answer is how much of the 458-origin partition is a statement about where refuges actually are rather than about where OpenStreetMap says they are — which bears on every absolute Yeongdeok rate, though not on the paired contrast, both arms of which use the same refuge set | **runnable in the cloud sandbox, unlike G3 and G4**: the designated-site layers are committed under `data/processed/external/juso_yeongdeok/` and counted in that folder's `manifest.json` (64 earthquake outdoor sites, 92 tsunami sites), as are the walk graph and the origin list. ⚠ Only `manifest.json` and `minwon_agencies.geojson` of that folder are listed in `docs/artifact_manifest.json`; the seven 사물주소 `*.geojson` layers are not, though `scripts/register_juso_yeongdeok.py` registers a count for each (seven layer stems in `SAMUL_LAYERS`, seven `samul_*.geojson` files on disk). That is a dev-lap item, not the paper's — this row names the folder rather than a layer file because citing an unlisted one fails `make check-artifact-manifest`. A dev lap re-snaps the refuge nodes to the designated sites, re-runs the same 458 origins on the same canonical field under both policies, and commits the three-bucket partition under a new filename beside the committed one; the paper then reports both. This is backlog WFG-073, which the paper routine cannot run itself (it would be a new artifact outside `paper/`) | no |

## ⚠ The length budget is now the binding constraint, and it is an author decision (lap 6)

Not a `[GAP]` — nothing is missing from the manuscript; the problem is that nothing more
fits. This lap added four things the evidence supports (the withdrawn-claim registry in
§3.5, the not-a-probability-sample statement and the off-network walking limitation in §6, the
outside-readers paragraph in §5) and had to pay for them by trimming elsewhere. **After the
trims the body stands at 7,467 words against a 7,000 target and a 7,500 hard fail: 33
words of margin.** The next lap that adds a clause fails `check_paper.py`.

What was trimmed this lap, so the record exists: the abstract and §1's three-claims
paragraph were tightened; four `[GAP]` markers were cut to what is missing, their detail
already living in this file; §1 dropped "2,246 households" and "1.05 trillion won" (neither
is used by any result; 99,289 ha and 3,819 homes stay); §4.6's mechanism paragraph, §4.7's
opening and closing, §5's conformal paragraph and the availability section were compressed
without dropping a number or a caveat.

⚠ **The first version of this block said that of every trim, and it was false in two
places — the lap reviewer caught both and they were restored before the push.** The §1
compression had deleted "its casualty figures are re-cited rather than measured", which is
the registered caveat on `fire2025_chain_deaths_yeongdeok`; the §4.3 compression had deleted
"and no per-origin ledger exists", which is the caveat that stops a reader inferring a
per-origin reclassification count between the reverted and canonical lineages. Both are back
in the manuscript. The lesson is the one §3.5 now states about the other registry: a
compression that keeps every *number* can still drop the *caveat* bound to it, and no gate
here reads for that — `make verify`, the collision scan, the forbidden-string scan,
`check_withdrawn_claims` and `check_paper` were all green across both deletions.

**No further trim of this kind is available.** Every remaining paragraph carries a
registered number and the caveat that CHARTER §3 rule 3 binds to it, and the loop will not
drop a caveat to buy space. Closing the 467-word gap to the target is therefore structural,
and the choice belongs to the author, not to a lap:

- **(a)** Move §6's designated-site inventory block (~200 words: the 주소정보누리집 counts,
  their two data dates and the extent caveat) to an appendix or to the data-availability
  section. It is a description of an input no result uses, not a limitation of a result.
- **(b)** Cut §4.7 (detection timing, ~530 words) to a short paragraph plus Table 4, and
  publish the measurement separately. It is the section least connected to the routing
  claim the paper is built on.
- **(c)** Accept 7,460 and target a venue whose limit is the page count rather than the
  word count — IEEE Access measures pages, and the built `.docx` is inside 20.

Until the author chooses, laps must keep the body under 7,500 by trading word for word.

## ✅ That input was re-cut and is now in the manuscript (lap 5) — the block below is the record

**Closed 2026-09-04 (paper lap 5).** The author re-cut the subset on the laptop under
NH-022 and the repository landed it at `79887696`: `sigungu_cd` is now **47770**, and the
extractor and its test check the label against the data itself rather than against a code
table — every 민원행정기관 road address contains 영덕군, the 지진해일긴급대피장소 layer is
populated (92 rows where the wrong cut returned 0), and `manifest.json` → `bbox_check`
records centroid-inside plus ≥ 50 % of points inside the canonical 영덕 box, result `pass`.
The eight registry keys carry `scope_status: corrected`.

So §6 now carries the designated-site inventory with its agency, both data dates and its
scope, and G6 above is the experiment it opens. **The category statement this block
predicted was written in a weaker form than predicted, on purpose**: the extractor cuts
seven named 사물주소 point layers out of the zip (`SAMUL_LAYERS` in
`scripts/extract_juso_yeongdeok.py`), so "no wildfire category exists in the national
taxonomy" is not checkable from anything committed here — only "none of the designated
categories in this subset is a wildfire one", which is what the manuscript says. Do not
strengthen it without an enumeration of the zip's own layer list, which is laptop-only.
Also written: §5's sentence on the label-versus-geometry check, which is the transferable
half of the whole episode and belongs to the paper's "the instrument is the contribution"
argument rather than to its process notes.

### The original block (lap 4), kept as the record

## ⚠ An input that exists, is registered, and must not enter the manuscript (lap 4)

`data/processed/external/juso_yeongdeok/` and its eight `juso_yeongdeok_*_count` registry
keys arrived in this lap's window: the author's 주소정보누리집 download, cut to what
`scripts/extract_juso_yeongdeok.py` labels 영덕군. It is the first agency-designated list
of evacuation sites and public offices in the repository, and it bears directly on two
things the manuscript states — the refuge semantics in §6 ("OpenStreetMap tags, which in
rural Korea return parks and pavilions") and the depot columns of Table 2.

**None of it is written, and none of it may be, until WFG-075 re-cuts the subset.** Critic
#11 (F54) measured every committed point at 36.78–37.05 N, 128.65–129.15 E, against this
project's own canonical 영덕 box of (129.25, 36.30, 129.55, 36.60) — about 45 km apart,
overlapping on neither axis, centroid beside 봉화읍. The artifact corroborates the finding
against itself: a road address in `minwon_agencies.geojson` reads 경상북도 **봉화군**
봉화읍, 영덕 is an East Sea coastal county and the set holds zero points east of 129.15 E,
and the 지진해일긴급대피장소 layer is empty, which a coastal county's would not be. The
county code `47920` is not 영덕's. The re-cut needs the laptop-only zips (NH-022); the
annotation half is WFG-075.

So the manuscript stays clean of it, deliberately, and this row exists so that a later lap
reads the block rather than the invitation. When the subset is re-cut, the sentence it
earns is not a count but a category statement: the 사물주소 designated-site taxonomy is
earthquake, tsunami and heat, and holds no wildfire evacuation category at all — which is
a fact about the national taxonomy, not about the county, and survives the re-cut.

## ⚠ Length pressure — and the counting bug lap 5 found underneath it

**Read this before shaving another sentence: 318 of the words every previous lap was
fighting were table captions, which the builder never meant to count.**
`build_docx.py` recognises a table caption only when the `Table N.` line is *immediately*
followed by the `|` row (`m and i + 1 < len(lines) and lines[i + 1].startswith("|")`).
All three captions had a blank line between them and their table, so each one fell through
to the paragraph branch: counted as body text, rendered as an ordinary paragraph, and the
table itself built with the label `Table N. ` and **an empty caption**. Lap 5 deleted the
three blank lines. The captions now render bold-labelled and attached, and the body count
dropped 7,423 → 7,105 with not one word of prose removed. Figure captions were never
affected — that branch has no such condition. **Keep every future `Table N.` line glued to
its table**; a blank line there silently costs both the caption and the budget. Lap 5
proved the trap by falling into it: the new Table 3 was written with the habitual blank
line, built with an empty caption, and was caught only by reading the tables back out of
the `.docx` with `python-docx`. Do that read-back after adding a table — `check_paper.py`
counts tables but cannot see that a caption went missing.

Where lap 5 finished: **7,362 words**, 138 of headroom against the hard fail, after adding
§6's designated-refuge limitation with its G6 marker and §5's label-versus-geometry
sentence, and after two structural compressions — §4.6's two comparison grids folded into
Table 3, and §4.5's budget and terrain paragraphs trimmed of the values Fig. 7 already
plots. So the aim is still not met, but the headroom is now real rather than an artifact
of miscounting, and the remaining distance is smaller than lap 4's ledger below implies.

Earlier record, lap 4: **Lap 4 did not move this, and should not be read as having
tried to.** It spent its budget on corrections rather than on new prose: the §5 withdrawal
record was added, and then the lap reviewer's block forced two caveats back in that cost
more than the lap had gained — the synthetic-hazard label on the whole 439-origin
responder series (§3.4, §3.3, §4.6) and the restored scope on the attribution study in §1.
The §4.6 window grounding this lap first wrote was **removed entirely**, not trimmed, for
the reasons in the reviewer's block below; that removal is what paid for the caveats.

⚠ **One cut was reverted by the test suite, correctly.** Trimming §4.7's closing
"Whether that is ahead of or behind the emergency call, this measurement cannot say" as a
duplicate of §5 broke `tests/test_detection_ordering_is_not_claimed.py::
test_the_manuscript_keeps_its_withdrawal`, which pins that sentence: §4.7 is the only
place stating the reference clock's provenance in full and must refuse the ordering claim
in its own voice, not delegate it to §5 (WFG-053, NH-019). The sentence is back and the
test was not touched. **Read this before treating a §4.7 sentence as redundant** — two
statements of the same refusal in that section are load-bearing, not restatement.

Cuts were taken only from sentences restating a claim made in the same or an adjacent
section, or from numbers removed together with their own caveat so that none was left
orphaned: §1's nationwide-total reconciliation (the 104,788 ha / 347 fires figures are
gone entirely and the paper's "states no share of any nationwide total anywhere" position
is now stated without quoting the totals it declines to divide), §4.7's fourth
restatement of the detection withdrawal, §4.2's duplicate
non-comparability clause, §3.1's explanatory gloss on the detector floor, three editorial
restatements in §4.5, §5's "coupling rather than a model" line and its repeat of §4.6's
mechanism, and three short §6 restatements including Coverage, now a cross-reference.

**The 400 words between here and the aim will not come from more of this.** Restatement
has now been squeezed roughly dry; §6 (the longest section at about 1,000 words) is a list
of distinct limitations each carrying its own numbers, and cutting there means dropping a
caveat, which CHARTER §12 forbids. The realistic routes are structural, and a lap should
pick one deliberately rather than shaving: fold §4.5's five sensitivity paragraphs into one
paragraph plus a table (tables and captions are not counted by `build_docx.py`), or move
§4.6's second half — the 2,160-cell window sweep and the reproducibility re-derivation —
into a table with two sentences of text.

Earlier record, lap 3: the body was 7,408 words. Lap 3 added about 80 words (the settled
fire-affected-area reasoning in §1, the re-sourced death-toll attribution, the withdrawn
detection reading in §4.7, and the narrowed G5 marker) and cut about 152, taking them
from the places lap 2 nominated: §6's first item and its Coverage and router-approximation
restatements, §4.5's terrain and network summaries, §4.6's closing repetition of its own
headline, §3.1's duplicate of the availability statement, §3.2's restatement of what §4.1
then shows concretely, and §2's one filler sentence. **No number and no caveat was dropped
to make room**, and the deletions were all sentences that restated a claim already made in
the same or an adjacent section.

The candidates left, in order, are §6 (still the longest section), §4.5 and §4.6's second
half. Captions remain the free space: `build_docx.py` does not count them.

⚠ **The 20-page limit is still not measured, and lap 2's diagnosis of why was wrong.**
`check_paper.py` enforces words, and this file's budget line converts them at roughly 16
pages per 7,000 words; a crude recount over the built `.docx` — 8,909 words including
captions, tables and references, plus seven full-width figures — lands nearer 21 pages.
Lap 2 recorded that LibreOffice "refuses to load the built document", which reads as a
fact about our file. **It is not.** Checked on lap 3: `soffice --convert-to pdf` fails with
`Error: source file could not be loaded` on a two-paragraph `.docx` written by the same
`python-docx` in the same environment, so the converter cannot open *any* `.docx` here and
says nothing about `WildfireGuardian_Park_2026.docx`. No metric-compatible Calibri
(Carlito) is installed either, so a text-flow simulation would have to substitute Arial
metrics for Calibri's and assume a line height this repository has not measured — which is
the kind of unchecked constant the gap exists to remove. So no page number is asserted
here. **The cheapest close is the author**: open the committed `.docx` in Word or Google
Docs and report the page count; one number settles it. Failing that, a working converter.

## ⚠ Two clocks, and the trap a lap fell into (lap 4, caught by the lap reviewer)

**Do not write that the KFS containment durations and the GK2A detection delays rest on
the same clock.** They do not, and saying so restores a claim this repository withdrew.

Lap 4 wrote a paragraph grounding §4.6's dispatch windows in the Korea Forest Service
containment statistics (79.23 % of fires contained within 240 minutes of their recorded
occurrence time over 2,008 usable records, median 120, and 4,025 minutes for the 25 events
of 100 ha or more — all four values correct against
`data/processed/detection/kfs_containment_duration.json`). It closed by saying those
durations "run from the same recorded-start field whose provenance §4.7 flags". **That is
the exact claim WFG-053 withdrew on 2026-09-04**, and `docs/horizon_grounding.md` §2 now
carries the dated correction verbatim: 「두 측정은 자료가 다릅니다 — 이 표는 산림청
산불통계데이터 CSV 의 `발생일시` 열이고, Session 19 는 `fire_manifest.json` 의 `start`
필드입니다」. Two different datasets, two separately unverified time semantics. The
manuscript may say each is a recorded-start-to-containment or recorded-start-to-detection
figure; it may **not** say they are the same field or share one weakness.

⚠ **The registry still carries the withdrawn wording, so a lap reading only the registry
will fall into this again.** All four `kfs_*` entries' caveats end 「Same limitation as
Session 19's GK2A delays — both rest on the same reported clock」, which is what
`horizon_grounding.md` §2 retracted. The entries need an annotated supersede (add, never
edit) from a dev lap — that is backlog **WFG-061**, same root as NH-019. Until then the
manuscript declines to inherit its own registry's caveat, as it already does for the
~95 % ratio in item 1 below.

**And the grounding did not apply anyway.** The 240 minutes that
`docs/horizon_grounding.md` justifies is `scripts/vulnerability_layer.py`'s
`TIME_BUDGET_MIN = HORIZON_MIN = 240.0` — the vulnerability layer's horizon, a different
parameter from §4.6's exploratory dispatch window. The committed 75-minute dispatch window
is `config/default.yaml:365 time_budget_min: 75.0`, marked **ASSUMED**, and nothing in the
repository grounds it. The paragraph was removed and §6's assumptions list now says so
outright. If a later lap wants to ground the dispatch axis, the artifact it needs does not
exist yet.

## ⚠ Two repository inconsistencies the manuscript is on the safe side of (for a dev lap)

Both found by the paper lap-3 reviewer. Neither moves a number and neither is the paper's
to fix — `docs/NUMBERS.json` and `README.md` are outside what CHARTER §12 lets this
routine touch — so they are recorded here and in the lap report.

1. **The registry still asserts the ~95 % ratio that `docs/data_sources.md` withdrew.**
   `fire2025_chain_area_ha`'s caveat reads "It is about 95 % of the nationwide 104,788 ha"
   and `fire2025_nationwide_area_ha`'s reads "The 의성발 chain is 99,289 ha of this, about
   95 %". `data_sources.md` 함정 6 retired that ratio on 2026-09-04 and the manuscript
   states no share at all. CHARTER §12 says a number's caveats travel with it, so the
   manuscript is currently declining to repeat a caveat its own registry still carries.
   The manuscript's position is the safe one; the registry entries need an annotated
   supersede (add, never edit) from a dev lap. **Escalated 2026-09-04 as a new option D on
   NEEDS_HUMAN NH-018**, which already owns this question — no source settles whether two
   differently-scoped totals may be divided, and the `forbidden_phrasings` on
   `fire2025_nationwide_area_ha` make it gate-enforced behaviour rather than a note.
2. **The agency on `fire2025_chain_deaths` is wrong against its own sources.** The entry
   gives 중앙재난안전대책본부 and cites a 뉴시스 stub that names no agency and a 서울신문
   page that gives 중대본's undivided two-province total of 30. The page that carries the
   26 and the five-district split is 대구MBC 2025-03-30, which attributes both to
   경상북도 재난안전대책본부 and never says 중대본. The manuscript now cites that page
   (`dgmbc2025toll`). `README.md` attributes the Yeongdeok 9 correctly but still puts the
   26 under an 아시아경제 link that carries no death figure at all, and still closes that
   paragraph with 「경상북도 최종 집계·중앙재난안전대책본부 확인」. This is backlog
   **WFG-051** (P0, open): the paper half is done, the registry entry and the README
   reconciliation are not, and only a dev lap can do them.

## Notes on gaps that were closed

- **G1 closed 2026-09-04 (paper lap 2).** The age composition is now written from two
  openable sources verified this lap: Yeongdeok-gun's casualty notice of 2025-04-29
  (mean age 84 of ten dead, maximum 101), quoted at p. 9 of the Greenpeace/녹색전환연구소/
  우리함께 survey report, and that survey's own age table (63.9 % of 296 respondents aged
  60–79, 17.9 % aged 80 or over). Both carry their caveats in the text: the casualty
  figures are re-cited by the report rather than measured by it, and the survey is a
  non-probability sample of survivors from which the dead are absent by construction.
  The same lap replaced the manuscript's opening damage figures, which had restated the
  WWA rapid study's differently-scoped tallies, with the chain-scoped provincial values.
- The abstract, Related work, Methods §3.3–§3.5, Results §4.1–§4.6, Discussion,
  Limitations and Conclusion were all `[GAP]` markers before 2026-09-03 and are
  now prose backed by committed artifacts.
- The `References` section is generated by `build_docx.py` from
  `references.bib` at build time and therefore does not appear as a heading in
  `manuscript.md`; it is present in the built `.docx`.
