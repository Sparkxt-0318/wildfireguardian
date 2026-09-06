# Gaps — what the manuscript still lacks

Every `[GAP: …]` in `manuscript.md` has a row here (the gate checks both ways).
Close a gap by replacing the marker with prose backed by an artifact and
deleting the row. Gaps marked *after sprint* need the laptop-only raw bundle or
the author.

| # | where | what is missing | closes when | after sprint? |
|---|---|---|---|---|
| G5 | §6 Limitations (the measurement it is about is §4.8) | the provenance of the detection reference clock. Every delay in Table 4 is measured from `fire_manifest.json`'s `start` field, which the manifest marks "provenance only" and sources nowhere. **Narrowed 2026-09-04 (paper lap 3), and the repository has now come to the same reading.** Checked this lap against `docs/data_provenance/fire_manifest.json` — the only copy tracked here; the copy the pipeline actually reads, `data/raw/firms_data/fire_manifest.json`, is git-ignored and absent from a fresh clone, so this is the documentation copy and is assumed, not verified, to match. In it: all six entries mark `start/end/reported_ha` as `provenance only`, and **no entry contains 신고 or any word for a report**. That much is solid and is what the manuscript rests on. ⚠ **What this lap first wrote here, and the lap reviewer knocked down**: that exactly one entry says what the field is, namely `yeongdeok_2025`, whose note reads `first hit (2025-03-25) lags the 2025-03-22 ignition by days` against that entry's own `start` of `2025-03-22T12:15+09:00`. That is an inference from a date coincidence, not a statement — the note never mentions `start` — and it is probably the wrong inference: `2025-03-22` is the **parent Uiseong chain's** ignition date (its own `start` is `2025-03-22T11:25`, fifty minutes earlier), while Yeongdeok's first detection is three days later, so the "ignition" that note names is most plausibly the parent fire's, not Yeongdeok's. `docs/detection_floor.md` §1 reads the same five other notes as saying nothing about `start` either. So the honest statement is the weaker one: **no entry says what the field is, in either direction.** The manuscript was corrected to that before this lap pushed. `docs/detection_floor.md` §1 and §9 read the field as a 신고 (report) time and concluded that GK2A rang after the telephone; **that reading was withdrawn on 2026-09-04 (WFG-053) with no number moving**, the manuscript having reached the narrow form first. Until a call time exists the paper cannot say whether the satellite beat the call, in either direction | the author supplies, for at least one of Uiseong-Andong, Gangneung or Hongseong, the KFS / 119 / 중대본 record giving the 신고접수시각, or the acquisition note saying where the minute came from; then it is registered with agency and date and §4.8, §1, §5 and the abstract can state the ordering. Raised by the lap-2 reviewer (NEEDS_HUMAN NH-019) | no |
| G2 | §5 Discussion | the **practitioner** consultations (fire-service duty officer, village head, social worker) in the project's consultation format, as design feedback rather than collected data; any quotation needs the author's consent handling first. **Narrowed 2026-09-05 (paper lap 6):** the *researcher* half is no longer missing — `docs/auto/research/EXPERT_REPLIES_2026-09-04.md` records three written replies to the author on 2026-09-04, and §5 now carries the two questions one of them raises that nothing here answers (age-only rescue prioritisation; the division of roles between forest-fire suppression and residential emergency response), while a second reply's off-network walking point became a §6 limitation and the third's WUI-transfer point a clause in §2. ⚠ **The paper names nobody.** That doc names the three by the author's decision *for the repository*; consent to be named there is not consent to be cited in a publication, so the manuscript says "an external researcher" and "three domain researchers". Before submission the author either obtains explicit permission to cite each as a personal communication, or leaves the attribution as it stands | the practitioner consultations happen and the author clears the quotations (NH-009); separately, the author decides whether to seek naming permission from the three researchers | yes |
| G3 | §6 Limitations | the leak-free Yeongdeok fold: refit the Yeongdeok LOFO fold with the co-located Uiseong-Andong fire excluded, re-simulate the canonical field, and route the same 458 origins, reporting the three-bucket counts as new filenames | the raw acquisition bundle on the author's laptop is available and WFG-032 runs | yes |
| G4 | §6 Limitations | **the hindsight-field routing arm — the single most load-bearing gap in the paper.** A third pass over the same 458 origins on a field rasterised from the *observed* FIRMS detections for Yeongdeok 2025, reporting how many of the 42 fire-blind routes actually intersect observed burn inside the walker's arrival window, and how many forecast-aware routes cross observed burn the model never flagged. Until it runs, "saved" means "re-routed around a model-flagged cell", not "away from where the fire went", and with pooled recall 0.138 that distinction is not cosmetic | the observed detections are available. ⚠ Checked 2026-09-03: `data/snapshots/firms-manifest_yeongdeok-2025_20260723_1aa75824.json` is committed and records 2,290 detections spanning 2025-03-25T12:25 to 2025-03-27T04:28, but the detections themselves (`yeongdeok_2025_detections.csv`) live under the git-ignored `data/raw/firms_data/`, which is absent from a fresh clone. So this arm needs the author's laptop too — it is cheaper than G3 (no refit, no re-simulation, reuses the committed walk graph and origin list) but it is not runnable in the cloud sandbox | yes |
| G6 | §6 Limitations | the refuge-provenance comparison. Every refuge in the paper is an OpenStreetMap point; the 주소정보누리집 designated-site subset for 영덕군 is now committed and correctly scoped, and nothing has been re-routed against it. The question the paper cannot answer is how much of the 458-origin partition is a statement about where refuges actually are rather than about where OpenStreetMap says they are — which bears on every absolute Yeongdeok rate, though not on the paired contrast, both arms of which use the same refuge set | **runnable in the cloud sandbox, unlike G3 and G4**: the designated-site layers are committed under `data/processed/external/juso_yeongdeok/` and counted in that folder's `manifest.json` (64 earthquake outdoor sites, 92 tsunami sites), as are the walk graph and the origin list. ⚠ Only `manifest.json` and `minwon_agencies.geojson` of that folder are listed in `docs/artifact_manifest.json`; the seven 사물주소 `*.geojson` layers are not, though `scripts/register_juso_yeongdeok.py` registers a count for each (seven layer stems in `SAMUL_LAYERS`, seven `samul_*.geojson` files on disk). That is a dev-lap item, not the paper's — this row names the folder rather than a layer file because citing an unlisted one fails `make check-artifact-manifest`. A dev lap re-snaps the refuge nodes to the designated sites, re-runs the same 458 origins on the same canonical field under both policies, and commits the three-bucket partition under a new filename beside the committed one; the paper then reports both. This is backlog WFG-073, which the paper routine cannot run itself (it would be a new artifact outside `paper/`) | no |
| G8 | §4.5 Results | **which build of the present-perimeter opponent defines the comparison, and therefore what the forecast's residual advantage over it is.** The arm ran (WFG-114, author decision NH-027 option A) and §4.5 reports, qualitatively, that it recovers most of the Uiseong-Andong origins the fire-blind contrast credits to the forecast. ⚠ **Until 2026-09-06 (paper lap 11) this sentence instead said that §4.5 reports the recovery count, and printed it — the recovered figure over the 91. It was false in two directions at once** (the wording is described rather than restated here, for the second of those reasons): §4.5 states no count, as the rest of this row says twice in bold, and the sentence was itself putting fact (1)'s recovery half into the paper bundle without the other three facts the shared caveat binds to it. Lap 10 rewrote §4.5 and left its own ledger describing the draft it had withdrawn; lap 11's reviewer found it. What §4.5 declines to state is the difference that is left, because the row was built **twice, concurrently, by two dev laps that could not see each other**, and the two builds disagree by about a factor of three on exactly that quantity. Both reproduce the committed classification node for node before measuring; they differ only in how the opponent is constructed — one prunes the refused nodes and runs the distance-minimising `naive_route` on what is left, with no time budget; the other runs the time-expanded router against a frozen binary hazard, budget-capped at 600 minutes and able to refuse departure from inside the buffer. Both are defensible readings of 「a county office with a perimeter map」. The project's own ledger holds this open as **NH-032** and its consequences as **NH-034**, and NH-032's standing instruction is that no judge-facing surface carries either margin until the author answers; CHARTER §14b lists the manuscript as a judge-facing surface, so this manuscript names neither. ⚠ **THIS ROW IS THE REASON §4.5 QUOTES NO COUNT AT ALL, AND THE FIRST DRAFT OF THE SECTION GOT THAT WRONG — the lap reviewer blocked the push and was right.** That draft quoted the recovery count (described, not restated, for the same reason as above) and shipped a new figure whose bars carried each width's failure total against a 「of 368 scanned」 axis. Neither states a margin. Together with Table 2 they *determine* one: the bar totals and the denominator give the present-aware safe series, Table 2's own row gives the forecast-aware total, and the subtraction lands on the committed arm's margin — reaching the reader stripped of the five caveats the `pp_uiseong_*` entries make mandatory, and with the losing build's answer alongside it from the draft's own 「about a factor of three」. Withholding a number while printing its determinants is the appearance of restraint with none of the protection. Worse, the draft's two derivable residuals disagreed with each other, because the reconciling term — the already-safe origins the buffer breaks — was the one registered value it did not print. **The deadlock is real and is worth stating plainly**: the shared `pp_uiseong_*` caveat opens 「Four facts travel together or none of them may be quoted」 and fact (1) is the margin, while NH-032 bars the margin from every judge-facing surface. So quoting *any* count from the arm was unavailable, and the section now quotes none. ⚠ Two further things bind the answer whichever way it goes, and §4.5 states both: the forecast-aware arm plans on the field it is graded against, so any such margin is what a **noiseless** forecast buys and this project's model buys less (backlog **WFG-125**); and the five widths differ by factors of two, so the grid holds one point in the region a 「which width could an operator pick」 claim would be about (backlog **WFG-127**). ⚠ **The manuscript reached this strength first and one of the two surfaces behind it has now caught up.** `docs/fair_opponent_line.md` §3 was narrowed on 2026-09-06 (WFG-127 (i), critic #23's finding carried by critic #24): it now states the change of kind, states the sweep's spacing as the resolution limit, and asserts neither shape, and `tests/test_fair_opponent_line.py::test_the_doc_does_not_claim_a_fixed_buffer_cannot_work` bans the retired spellings in that file — the gate that used to *require* one of them. `docs/present_perimeter_arm.md` §4 (「The 1 km row is a **spike, not a plateau**」) still draws the stronger conclusion from those same five points; that is the rest of WFG-127(i), a dev-lap item outside CHARTER §12's paths, and §4.5's last sentence now says one document rather than two. **This row asserts no shape either** — not spike, not plateau; only that five points a factor of two apart cannot tell them apart. 🖼 **The figure exists and is committed but is not in the manuscript.** `paper/make_figures.py` → `F9_present_perimeter` draws the failure-mode composition across the five widths and `paper/figures/F9_present_perimeter.png` is committed, so the moment NH-032 is answered the figure drops into §4.5 with the margin and its caveats. It is deliberately left unreferenced rather than deleted (CHARTER §3.7), and `check_paper.py` does not object because it checks that every referenced figure exists, not that every drawn figure is referenced | the author answers **NH-032** (which opponent) and **NH-034** (what the surfaces then say); the manuscript then states the margin from the chosen build with its five registered caveats, adds the already-safe-broken term so the residuals reconcile, and references F9. Nothing else is needed — both artifacts exist and both are green | no |
| G7 | §4.3 Results | **what the headline contrast is allowed to attribute.** The baseline the 42 (and §4.4's 91 of 368, 24.73 %) are measured against is `naive`, which is **fire-blind**: it consults no hazard at all, present or forecast (`src/wildfireguardian/routing/evacuation.py:270` 「Fire-blind shortest path to the nearest shelter, then scored against the hazard」; `docs/real_roads_real_hazard.md:50` 「the fire-blind shortest walk to the nearest refuge (the status quo)」). So the contrast measures what hazard awareness of ANY kind buys, and an unmeasured share of it is bought by knowing where the fire is **now** rather than where it will be — a router refusing only the cells alight at departure would recover some of the 42. Raised by critic #17 (2026-09-05) against the booth script, which had handed the fire-blind arm the stronger description 「지금 이 순간만 보는 지도」; WFG-103 fixed that sentence. The manuscript had the same overclaim in its **abstract** (「reach a refuge only when the router accounts for where the fire will be」) and it was corrected this lap, with the caveat added to §4.3 as its third. ✅ **NARROWED 2026-09-06 (paper lap 10): the arm has run, on the other region.** WFG-114 (author decision NH-027 option A) built the present-perimeter opponent on **의성·안동 2025** — the §4.4 region, whose fire-blind contrast is the 91 of 368 — and §4.5 of the manuscript now reports it. So G7's premise is no longer 「an unmeasured share」 in general: on that region the share is large and measured, and saying otherwise would be a fabricated limitation (CHARTER §3.5; `docs/fair_opponent_line.md` §2 makes the same point about the booth surfaces). What is still missing is **the same arm over the canonical Yeongdeok 458**, which is the origin set the paper's headline 42 comes from, and that is what the §4.3 marker now asks for. ⚠ The margin half of the Uiseong-Andong result is a separate gap, **G8** above, and is an open author decision rather than a missing run | the arm runs **on Yeongdeok's 458 origins**, i.e. the still-outstanding part of **WFG-033(b)**, 「static current perimeter (slice 0, p ≥ p_cut) + fixed buffer 0.5/1/2 km」, agent-doable, two laps, on committed hazard fields with no re-acquisition. It is **P2**, i.e. after the finals, and whether to pull it into the sprint is open with the author as **NH-027** (four options, by 2026-09-08). The paper routine cannot run it: it would be a new artifact outside `paper/`. ⚠ **A much cheaper version answers the framing question and this lap's reviewer specified it exactly** — mask slice 0 of the committed canonical field (p ≥ 0.5, 249 cells, `data/processed/routing_demo_canonical.npz`, shape [5,181,156]) as a node filter and re-run the existing `naive_route` over **only the 44 origins whose fire-blind route enters the hazard**, counting how many a present-perimeter-only router already saves. Zero buffer, one region, 44 origins, all inputs committed, no refit and no re-simulation; `F8(a)` in `make_figures.py` already loads and renders that same slice-0 mask. That is minutes of work against WFG-033(b)'s two laps, and it converts §4.3's 「an unmeasured share」 from a hedge into a number. **A dev lap should run this before the finals whatever the author decides on NH-027** | yes for full WFG-033(b); the 44-origin version above is runnable in the sandbox now by a dev lap |

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

⚠ **That sentence was too strong, and lap 7 falsified it by having to.** Lap 7 arrived with
a correction it could not decline to ship (G7: the abstract attributed the headline contrast
to forecast knowledge when the baseline is fire-blind) and 33 words of margin. It found 106
words of prose that carried **no** registered number and **no** caveat, and cut them: §5's
county-subset arc compressed to one clause; §5's 「A second raised Section 6's off-network
walking limitation」 deleted as a duplicate of §6, which already carries that point with its
attribution; §5's 「and one field answers the responder's mirror-image question too」 deleted
as a duplicate of §1 and §3.4; §1's restatement of the 22–64 min and 0.1–1 ha figures cut to
「tens of minutes」 and 「a size floor」, both stated in full with their caveats in §4.7 (the
abstract keeps 0.1–1 ha but says only 「tens of minutes」 — the lap reviewer corrected this
sentence, which had claimed the abstract carried both in full); §1's 「and this paper is as much about the evaluation design under which it was
built」 deleted as a duplicate of §1's own claims paragraph and the abstract; §6's 「Reading
those shares as estimates for households would need an interval nothing here supports」
deleted as a restatement of the sentence before it; and the abstract's opening compressed.
No number and no caveat left the manuscript, and the body went 7,467 → 7,457 while
absorbing the ~100-word correction.

The lesson is the mirror of the one above it. Lap 6 learned that a compression keeping every
number can still drop a caveat. Lap 7 adds: a section can be *dense* in numbers and still
hold prose that repeats another section, and 「every paragraph carries a number」 is not the
same claim as 「every sentence earns its words」. What is **now** true is the weaker and more
useful statement: the duplication has been harvested, the next lap starts from 43 words of
margin, and the structural choice below is still the author's.

- **(a)** Move §6's designated-site inventory block (~200 words: the 주소정보누리집 counts,
  their two data dates and the extent caveat) to an appendix or to the data-availability
  section. It is a description of an input no result uses, not a limitation of a result.
- **(b)** Cut §4.7 (detection timing, ~530 words) to a short paragraph plus Table 4, and
  publish the measurement separately. It is the section least connected to the routing
  claim the paper is built on.
- **(c)** Accept the current length and let the venue's own rule govern. ⚠ **Half of what
  this option said was unverified, and lap 7 checked it.** IEEE Access's Article Processing
  Charges page states 「There is no page limit for articles and therefore no over-length
  article charge」 and 「strongly recommend[s] keeping the page count under 20 pages for ease
  of readability」 (IEEE Access, <https://ieeeaccess.ieee.org/about/article-processing-charges/>,
  read 2026-09-05) — so the venue rule is a *recommendation*, and the 7,500-word gate is this
  repository's own invention rather than anyone's requirement. ✅ **The other half is no
  longer unmeasured: the built document is 21 pages** (lap 8, below).

✅ **ANSWERED 2026-09-05 — the author took none of (a), (b) or (c) as written and set a
ceiling instead: 25 pages, word count secondary.** So the trimming regime this whole block
describes is over. Nothing above is deleted, because it is the record of four laps spent
trading word for word and of the two caveat-losing near-misses that discipline caught; read
it as history, not as instruction. The operative rule and the measurement behind it are in
「The page count exists now」 below.

## ⚠ And now it rots loudly rather than quietly — the anchor (lap 9, 2026-09-05)

**This heading read "✅ And it cannot rot now either" until the lap reviewer blocked the
push over it, and the objection is kept because it is the same discipline as the
manuscript paragraph shipped in the same diff.** Nothing below re-derives the page count.
A renderer is the only thing that produces it, `STATE.json` is bookkeeping a lap writes by
hand, and every field in it — the new one included — is forgeable by the lap the gate
audits. Critic #21 F4's sentence, 「`built_pages` is the one field in that file nothing
re-derives」, is still literally true after this change.

Not a `[GAP]`. Critic #21's F4 (backlog **WFG-116**, P1) is the objection the block below
invites: the 21 pages was measured inside a sandbox that no longer exists, the branch that
can fail needs LibreOffice **Writer**, and no machine the loop owns has it — so `built_pages`
was the one field in `STATE.json` nothing re-derived, on the one quantity a new **figure**
changes and the word budget cannot see.

What is true is narrower and still worth having. `check_paper.py` now carries
`built_pages_inputs`, a digest of the document the count was measured on — the ordered
figure list with each PNG's pixel size, the table count, the reference count, the
body-word count — and **the check needs no renderer**. A run that can measure refreshes
both fields; a run that cannot fails if `built_pages` is carried while that digest has
moved, and its message says to re-measure or set both to `null`. So a figure arriving
unnoticed turns the gate red instead of quietly invalidating a number nobody rechecks, and
keeping the old count anyway becomes an edit visible in the diff rather than an accident.
Graded as the row asks, with `_has_writer` stubbed false: matching state passes, a figure
swapped for one of a different size goes red on the digest, `built_pages: null` passes.

⚠ **The reviewer's operational point changed the code, not only the prose.** The first
version printed the digest on every run, so on a cloud lap the bypass — paste the string
the gate just printed, keep the old page count — and the honest act — null both — were the
same keystrokes, and the bypass was the routine one, because `body_words` is in the digest
and every lap therefore invalidates it. The digest is now printed **only by a run that
measured**, and neither failure message contains it.

Two choices worth keeping: the digest is over **pixel sizes, not PNG bytes**, because the
font-fallback problem below makes a byte digest call a re-render a change; and **`body_words`
is in it**, because the word budget bounds the ceiling rather than the accuracy of a recorded
count, and the curve moves a page inside the budget's own range.

This lap also re-measured instead of inheriting: **21 pages under Carlito at 7,639 words**,
after one `apt-get install libreoffice-writer fonts-crosextra-carlito fonts-nanum`. The
The 178 words this lap added to §3.5 cost no page. ⚠ **WFG-116 is not closed, and the half that
is still open is the one that actually re-derives**: `auto-gates.yml` installing those
packages so a clean clone measures. It is outside `paper/` and only a dev lap can do it,
together with a fixture-driven test in `tests/test_paper.py` — the new failing branches
have no committed test, are unreachable in the local suite once Writer is installed
(`measured_here` is then true and the run takes the refresh path), and were exercised only
by the stub above. The row also cannot be marked from here, since `docs/auto/BACKLOG.md`
is outside CHARTER §12's paths.

## ✅ The page count exists now — 21 pages (lap 8, 2026-09-05)

**This is the number NH-028 said only the author could produce, and it is the one clause
every earlier lap had to strike.** `paper/measure_pages.py` renders the committed
`WildfireGuardian_Park_2026.docx` and counts: **21 pages under Carlito**, cross-checked two
ways in the script (21 page objects against a page-tree `/Count` of 21, and it refuses to
print a number when those disagree). `pypdf` 6.17.0 was pip-installed once as a third check,
also said 21, and was removed; it is in neither `requirements.txt` nor the bootstrap venv, so
that third check is a note rather than something a fresh clone re-derives. Body words at that
render: **7,461**, with 8 figures, 4 tables and 27 references.

⚠ **「21 pages」 is conditional and the condition is the font.** Measured on the identical
file and renderer, varying only which faces fontconfig may see: **Carlito 21, DejaVu Sans 23**.
`build_docx.py` asks for Calibri, which is not redistributable; Carlito is metric compatible
with it and DejaVu is not. The first version of this lap's gate computed the substituted face,
printed it, and then failed hard on the number anyway — caught by the lap reviewer. It now
gates only on a metric-compatible face and otherwise reports and falls back to the word
budget, because failing on a DejaVu render would reject a document that is inside the author's
rule in Word.

So the conversion this file and `paper/README.md` had been assuming — 「roughly 16 pages per
7,000 words」, and lap 3's crude recount of 「nearer 21」 — resolves to: **the old 7,500-word
gate sat at about 21 pages**, four under the author's 25-page ceiling. Lap 3's estimate was
right and its method was not, which is why it was recorded as an estimate and is now replaced
by a measurement.

**Why nobody could do this before, and it was not the file.** Lap 2 recorded that LibreOffice
"refuses to load the built document"; lap 3 correctly narrowed that to "it refuses a
two-paragraph `.docx` written by the same `python-docx` in the same environment, so it says
nothing about our file". Both true, and one step short of the cause: the sandbox image ships
`libreoffice-core` **without `libreoffice-writer`**, so no text-document import filter exists
and every word-processor format fails identically with `source file could not be loaded`.
Confirmed this lap by listing `/usr/lib/libreoffice/program/` (no `swriter`, no `libswlo.so`)
and then by installing the package, after which the same command converted the same file in
under four seconds. The install is machine setup, not a repository dependency:

    apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer fonts-crosextra-carlito fonts-nanum

**Carlito is not cosmetic.** `build_docx.py` sets Calibri, which is not redistributable;
Carlito is metric compatible with it, so with Carlito installed the line breaks and the page
count track Word. Without it the substitute is not metric compatible and the count is that
machine's rather than the document's — `measure_pages.py` prints which case it is in
(`"calibri_substitute": "Carlito"` on this render) instead of a bare integer. `fonts-nanum`
renders the Korean runs; there are few enough of them to move no page boundary here, which is
an observation and not a guarantee.

**The author answered NH-028 while this lap was running, and the answer makes the measurement
load-bearing rather than merely interesting.** Verbatim, through the laptop decision channel on
2026-09-05: 「Don't worry about the word count for now. Just make sure it doesn't exceed. 25
pages for. now」. That session raised the proxy to 8,500 / 9,000 words in
`docs/auto/LOOP_CONFIG.json`, CHARTER §12 and `paper/check_paper.py`, estimating 「about 21
pages」 at the current length. **The estimate was exactly right, and this lap replaced it with
the measurement and with a check.**

So the length rule is now enforced as the author stated it. `check_paper.py` renders the
document it just built and fails above 25 pages, and the 9,000-word budget stays as the proxy
everywhere else. Five branches, each exercised by hand this lap: no `measure_pages` module
(the import is lazy, so an unstaged file cannot make every push ImportError-red), no renderer,
renderer broken, face not metric-compatible, count over the ceiling. **Only the last one
fails.** A broken renderer is reported and passes — that is deliberate, so a flaky converter
cannot turn a push red, and it is said plainly because the first version of this block claimed
the opposite of code that failed on nothing. ⚠ **None of those branches has a committed
test**: `tests/` is outside what CHARTER §12 lets this routine touch, so a fixture-driven test
is a dev-lap item, and until it lands the branch that can fail a push is untested.

**The curve** (`python paper/calibrate_pages.py` regenerates it). Filler is the manuscript's
own paragraphs recycled, the 8 figures, 4 tables and 27 references held fixed, and the only
variable is where the words land:

| body words | 7,461 | 7,961 | 8,561 | 8,961 | 9,461 | 9,961 | 10,461 |
|---|---|---|---|---|---|---|---|
| appended after the last figure | 21 | 21 | 22 | 23 | 24 | 24 | **25** |
| spliced into §4, among the figures | 21 | **22** | **23** | 23 | 24 | **25** | **25** |

⚠ **The first row is a lower bound, not a conversion rate, and this lap got that wrong first.**
It measured only the tail row, ran a control with two fillers of different vocabulary (4.87 and
5.13 mean word length), found the counts identical at every point, and wrote that the
conversion was 「a property of the template, not of the words poured into it」. The lap reviewer
answered that this varied the thing that cannot matter and held fixed the thing that does. The
second row is the re-run: same words, up to one page more. Real prose is added in the middle of
a paper, not after it. The sentence is withdrawn and the control is recorded as what it was —
a control on the wrong variable, which is the failure mode §3.5 of the manuscript exists to
warn about, committed by the file that describes it.

What the sampling supports: at the proxy's own 9,000-word limit the document is **23 pages by
either route**, two pages of margin, so the proxy is sound; the ceiling arrives between 9,961
words (among the figures) and 10,461 (at the end), so the proxy stops a lap about a thousand
words early. The step is 500 words and **no count above 25 was ever measured**, so the ceiling
is bracketed rather than located.

⚠ **The proxy is not the rule.** Where the pages go, same render: title page 1, §1 p. 2, §2
p. 3, §3 pp. 4–6, §4 pp. 7–14, §5 p. 15, §6 pp. 16–17, §7 p. 18, availability and References
pp. 19–21 (heading positions read with the one-off `pypdf`; the script reports only the total,
which is the load-bearing number). §4 is eight of the 21 pages because it carries six of the
eight figures — so a **new figure costs a page and no words at all**, which the word budget
cannot see and is exactly why the page check exists. Options (a) and (b) in the block above
both cut prose, and prose is not where the pages are.

**What this means for the next lap.** The length pressure that dominated laps 4 through 7 is
gone: the body is at 7,461 against a 9,000-word proxy and 21 pages against a 25-page ceiling.
A lap that needs 200 words for a caveat now takes them. The trap that replaces it is the
figures, and the page check is the thing that catches it.

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

⚠ **One cut was reverted by the test suite, correctly.** Trimming the detection section's closing
"Whether that is ahead of or behind the emergency call, this measurement cannot say" as a
duplicate of §5 broke `tests/test_detection_ordering_is_not_claimed.py::
test_the_manuscript_keeps_its_withdrawal`, which pins that sentence: that section is the only
place stating the reference clock's provenance in full and must refuse the ordering claim
in its own voice, not delegate it to §5 (WFG-053, NH-019). The sentence is back and the
test was not touched. **Read this before treating a sentence in the detection section (§4.8
since lap 10 inserted §4.5; it was §4.7 when this block was written) as redundant** — two
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

⚠ **CLOSED on lap 8 — see "The page count exists now" above. The block below is the record
of how it stood, and lap 3's estimate was right for the wrong reason.**
`check_paper.py` enforces words, and this file's budget line converts them at roughly 16
pages per 7,000 words; a crude recount over the built `.docx` — 8,909 words including
captions, tables and references, plus seven full-width figures — lands nearer 21 pages.
*(Lap 8: the measurement is 21. The recount landed on the right integer from a word count
that double-counts captions and a figure count that was one short.)*
Lap 2 recorded that LibreOffice "refuses to load the built document", which reads as a
fact about our file. **It is not.** Checked on lap 3: `soffice --convert-to pdf` fails with
`Error: source file could not be loaded` on a two-paragraph `.docx` written by the same
`python-docx` in the same environment, so the converter cannot open *any* `.docx` here and
says nothing about `WildfireGuardian_Park_2026.docx`. *(Lap 8: correct, and the cause is that
`libreoffice-writer` is not installed — no import filter for any word-processor format. One
apt install and the same command converts the same file.)* No metric-compatible Calibri
(Carlito) is installed either, so a text-flow simulation would have to substitute Arial
metrics for Calibri's and assume a line height this repository has not measured — which is
the kind of unchecked constant the gap exists to remove. *(Lap 8: `fonts-crosextra-carlito`
installs it, so no simulation and no assumed line height were needed — the renderer does the
flowing and the script reports which face Calibri resolved to.)* So no page number is asserted
here. **The cheapest close is the author**: open the committed `.docx` in Word or Google
Docs and report the page count; one number settles it. Failing that, a working converter.
*(Lap 8: it was the working converter, and it cost one install. The author's open-and-look is
still worth one minute as an independent check against real Word rather than Carlito-in-Writer.)*

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

## ⚠ Three repository inconsistencies the manuscript is on the safe side of (for a dev lap)

The first two were found by the paper lap-3 reviewer, the third by paper lap 11. None moves
a number and none is the paper's to fix — `docs/NUMBERS.json` and `README.md` are outside
what CHARTER §12 lets this routine touch — so they are recorded here and in the lap report.

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
3. **The `pp_uiseong_*` caveats still assert the width claim WFG-127 (i) retired.** Their
   shared caveat lists four facts that must travel together, and fact (3) reads 「an operator
   on the day cannot know which width they are on」. That is the sentence critic #23 found
   too strong for a five-point grid spaced by factors of two, and the sentence
   `docs/fair_opponent_line.md` §3 and `docs/auto/DEMO_SCRIPT_5MIN.md` 3막 were both narrowed
   away from on 2026-09-06. Counted in one process this lap: **all 57 `pp_uiseong_*` entries
   carry it, and no entry outside that family does.** So a lap reading only the registry will
   restore the retired claim, exactly as item 1 above describes for the ~95 % ratio and as the
   `kfs_*` block further down describes for the two clocks. The manuscript declines to inherit
   it and §4.5 states the resolution limit instead. The repair is an annotated supersede (add,
   never edit) on those entries from a dev lap; it belongs with the rest of WFG-127 (i), whose
   open half is `docs/present_perimeter_arm.md` §4. ⚠ Not a gate failure and not urgent for the
   finals: no judge-facing surface quotes fact (3) any more. It is a trap for the next lap that
   quotes a `pp_uiseong_*` value and copies its caveat verbatim, which is what the caveat field
   is for and what CHARTER §12 tells a lap to do.

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
