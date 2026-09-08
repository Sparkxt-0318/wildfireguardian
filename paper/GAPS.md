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
| G8 | §4.5 Results | **which build of the present-perimeter opponent defines the comparison, and therefore what the forecast's residual advantage over it is.** The arm ran (WFG-114, author decision NH-027 option A) and §4.5 reports, qualitatively, that it recovers most of the Uiseong-Andong origins the fire-blind contrast credits to the forecast. ⚠ **Until 2026-09-06 (paper lap 11) this sentence instead said that §4.5 reports the recovery count, and printed it — the recovered figure over the 91. It was false in two directions at once** (the wording is described rather than restated here, for the second of those reasons): §4.5 states no count, as the rest of this row says twice in bold, and the sentence was itself putting fact (1)'s recovery half into the paper bundle without the other three facts the shared caveat binds to it. Lap 10 rewrote §4.5 and left its own ledger describing the draft it had withdrawn; lap 11's reviewer found it. What §4.5 declines to state is the difference that is left, because the row was built **twice, concurrently, by two dev laps that could not see each other**, and the two builds disagree by about a factor of three on exactly that quantity. Both reproduce the committed classification node for node before measuring; they differ only in how the opponent is constructed — one prunes the refused nodes and runs the distance-minimising `naive_route` on what is left, with no time budget; the other runs the time-expanded router against a frozen binary hazard, budget-capped at 600 minutes and able to refuse departure from inside the buffer. Both are defensible readings of 「a county office with a perimeter map」. The project's own ledger holds this open as **NH-032** and its consequences as **NH-034**, and NH-032's standing instruction is that no judge-facing surface carries either margin until the author answers; CHARTER §14b lists the manuscript as a judge-facing surface, so this manuscript names neither. ⚠ **THIS ROW IS THE REASON §4.5 QUOTES NO COUNT AT ALL, AND THE FIRST DRAFT OF THE SECTION GOT THAT WRONG — the lap reviewer blocked the push and was right.** That draft quoted the recovery count (described, not restated, for the same reason as above) and shipped a new figure whose bars carried each width's failure total against a 「of 368 scanned」 axis. Neither states a margin. Together with Table 2 they *determine* one: the bar totals and the denominator give the present-aware safe series, Table 2's own row gives the forecast-aware total, and the subtraction lands on the committed arm's margin — reaching the reader stripped of the five caveats the `pp_uiseong_*` entries make mandatory, and with the losing build's answer alongside it from the draft's own 「about a factor of three」. Withholding a number while printing its determinants is the appearance of restraint with none of the protection. Worse, the draft's two derivable residuals disagreed with each other, because the reconciling term — the already-safe origins the buffer breaks — was the one registered value it did not print. **The deadlock is real and is worth stating plainly**: the shared `pp_uiseong_*` caveat opens 「Four facts travel together or none of them may be quoted」 and fact (1) is the margin, while NH-032 bars the margin from every judge-facing surface. So quoting *any* count from the arm was unavailable, and the section now quotes none. ⚠ Two further things bind the answer whichever way it goes, and §4.5 states both: the forecast-aware arm plans on the field it is graded against, so any such margin is what a **noiseless** forecast buys and this project's model buys less (backlog **WFG-125**); and the five widths differ by factors of two, so the grid holds one point in the region a 「which width could an operator pick」 claim would be about (backlog **WFG-127**). ⚠ **The manuscript reached this strength first and one of the two surfaces behind it has now caught up.** `docs/fair_opponent_line.md` §3 was narrowed on 2026-09-06 (WFG-127 (i), critic #23's finding carried by critic #24): it now states the change of kind, states the sweep's spacing as the resolution limit, and asserts neither shape, and `tests/test_fair_opponent_line.py::test_the_doc_does_not_claim_a_fixed_buffer_cannot_work` bans the retired spellings in that file — the gate that used to *require* one of them. `docs/present_perimeter_arm.md` §4 used to draw the stronger conclusion from those same five points (「The 1 km row is a **spike, not a plateau**」 <!-- forbidden-ok: wc011-buffer-width-is-a-spike-en -->) — ⚠ **CLOSED 2026-09-08 by dev lap 20260908T2117Z on WFG-127**, which did not soften the sentence but MEASURED the shape: 750 m, 1250 m and 1500 m were added on the same code and the same committed inputs, all five original widths reproduced cell for cell, and the top is a **shoulder** (750 m scores 349, 1 km 345, of 368). The claim is withdrawn as **WC-011** and the evidence is `docs/present_perimeter_buffer_shape.md`. ⚠ The result runs AGAINST this project: the fair opponent is stronger at 750 m than at the committed 1 km, so the forecast's margin on this fire is smaller than §4.5 would suggest — a live consideration for this row, not a closed one. §4.5's last sentence now says one document rather than two. ⚠ **SUPERSEDED 2026-09-08 (paper lap 21), and in the direction nobody was watching: it says two again, and the new one is `README.md:232`** — a Round-4 bullet added by the diff this lap incorporated (`d6d801d`), reading 「그 sweep 안에서 **고원이 아니라 뾰족한 봉우리**입니다」. It was not a survival; it was **written after the narrowing**, into the project's front door, which is CHARTER §14b's first-named judge-facing surface. **Nothing in this repository could have caught it:** the shape claim appears in **no** entry of `docs/auto/withdrawn_claims.json` (checked key by key this lap — none of `spike`, `plateau`, 고원, 봉우리, 뾰족, 평평 occurs anywhere in that file), so the **935**-file scan (re-derived this lap by running `scripts/check_withdrawn_claims.py`: 「PASSED === 10 claims over 935 gated files」) never reads for it, and the only guard that exists, `tests/test_fair_opponent_line.py`, bans the retired spellings **in one file by name and in English only**. ⚠ **TRUE WHEN WRITTEN AND CLOSED THE SAME EVENING, by the dev lap three hours later:** the shape claim is now **WC-011** in `docs/auto/withdrawn_claims.json`, registered in **both** languages plus the recited booth sentence, so the tree-wide scan (936 gated files, 11 claims) does read for it and `README.md:232` is corrected. The paper lap's diagnosis was right and is what the registration was modelled on; recorded here as closed rather than deleted (CHARTER §3.7). ⚠ Registering it then caught a surface neither routine had named — **this row**, which quoted the withdrawn sentence and asserted §4 still drew the stronger conclusion. ⚠ **This lap did not find that: critic #44 did, three and a half hours earlier, inside the diff this lap incorporated.** WFG-127's own row records `README.md:232` as 「A FOURTH SURFACE」 and gives the sharper root — the guard reads English, the README wrote 뾰족한 봉우리 / 고원, which is DIRECTION's standing 「a registered spelling reaches ONE language」 rule firing on a **newly written** claim (WFG-168, not yet filed). That is §3.5's own 「one language at a time」 limit, which the manuscript already states, so no manuscript sentence is owed. The lap-21 section below carries the full subject grep and the correction of this lap's own first draft, which called the mechanism new. **This row asserts no shape either** — not spike, not plateau; only that five points a factor of two apart cannot tell them apart. 🖼 **The figure exists and is committed but is not in the manuscript.** `paper/make_figures.py` → `F9_present_perimeter` draws the failure-mode composition across the five widths and `paper/figures/F9_present_perimeter.png` is committed, so the moment NH-032 is answered the figure drops into §4.5 with the margin and its caveats. It is deliberately left unreferenced rather than deleted (CHARTER §3.7), and `check_paper.py` does not object because it checks that every referenced figure exists, not that every drawn figure is referenced | the author answers **NH-032** (which opponent) and **NH-034** (what the surfaces then say); the manuscript then states the margin from the chosen build with its five registered caveats, adds the already-safe-broken term so the residuals reconcile, and references F9. Nothing else is needed — both artifacts exist and both are green | no | <!-- forbidden-ok: wc011-buffer-width-is-a-spike-ko --> <!-- These lines RECORD the withdrawn shape claim in order to say it was withdrawn; WC-011 registered it on 2026-09-08 and this file is not record class, so the quotation is licensed per line rather than by exemption (CHARTER §3.5c). -->
| G7 | §4.3 Results | **what the headline contrast is allowed to attribute.** The baseline the 42 (and §4.4's 91 of 368, 24.73 %) are measured against is `naive`, which is **fire-blind**: it consults no hazard at all, present or forecast (`src/wildfireguardian/routing/evacuation.py:270` 「Fire-blind shortest path to the nearest shelter, then scored against the hazard」; `docs/real_roads_real_hazard.md:50` 「the fire-blind shortest walk to the nearest refuge (the status quo)」). So the contrast measures what hazard awareness of ANY kind buys, and an unmeasured share of it is bought by knowing where the fire is **now** rather than where it will be — a router refusing only the cells alight at departure would recover some of the 42. Raised by critic #17 (2026-09-05) against the booth script, which had handed the fire-blind arm the stronger description 「지금 이 순간만 보는 지도」; WFG-103 fixed that sentence. The manuscript had the same overclaim in its **abstract** (「reach a refuge only when the router accounts for where the fire will be」) and it was corrected this lap, with the caveat added to §4.3 as its third. ✅ **NARROWED 2026-09-06 (paper lap 10): the arm has run, on the other region.** WFG-114 (author decision NH-027 option A) built the present-perimeter opponent on **의성·안동 2025** — the §4.4 region, whose fire-blind contrast is the 91 of 368 — and §4.5 of the manuscript now reports it. So G7's premise is no longer 「an unmeasured share」 in general: on that region the share is large and measured, and saying otherwise would be a fabricated limitation (CHARTER §3.5; `docs/fair_opponent_line.md` §2 makes the same point about the booth surfaces). What is still missing is **the same arm over the canonical Yeongdeok 458**, which is the origin set the paper's headline 42 comes from, and that is what the §4.3 marker now asks for. ⚠ The margin half of the Uiseong-Andong result is a separate gap, **G8** above, and is an open author decision rather than a missing run | the arm runs **on Yeongdeok's 458 origins**, i.e. the still-outstanding part of **WFG-033(b)**, 「static current perimeter (slice 0, p ≥ p_cut) + fixed buffer 0.5/1/2 km」, agent-doable, two laps, on committed hazard fields with no re-acquisition. It is **P2**, i.e. after the finals, and whether to pull it into the sprint is open with the author as **NH-027** (four options, by 2026-09-08). The paper routine cannot run it: it would be a new artifact outside `paper/`. ⚠ **A much cheaper version answers the framing question and this lap's reviewer specified it exactly** — mask slice 0 of the committed canonical field (p ≥ 0.5, 249 cells, `data/processed/routing_demo_canonical.npz`, shape [5,181,156]) as a node filter and re-run the existing `naive_route` over **only the 44 origins whose fire-blind route enters the hazard**, counting how many a present-perimeter-only router already saves. Zero buffer, one region, 44 origins, all inputs committed, no refit and no re-simulation; `F8(a)` in `make_figures.py` already loads and renders that same slice-0 mask. That is minutes of work against WFG-033(b)'s two laps, and it converts §4.3's 「an unmeasured share」 from a hedge into a number. **A dev lap should run this before the finals whatever the author decides on NH-027** | yes for full WFG-033(b); the 44-origin version above is runnable in the sandbox now by a dev lap |

## What lap 21 incorporated (2026-09-08): a count in the manuscript went false because a *new* surface was born carrying a retired shape, and the limitation this lap wanted costs 12 words against 7

Incorporated diff **`dee1bc1..eff2183`**, **five** files outside `paper/` and `docs/auto/`:
`README.md` (one Round-4 bullet added, one rewritten, and the paragraph above them rewritten), `.github/workflows/auto-gates.yml`
(`continue-on-error` on two artifact-upload steps, NH-047), `release/kcf-finals-2026/MANIFEST.json`
(printables hashes), `tests/test_adoption_card.py` (new, WFG-188) and `tests/test_finals_acts.py`
(a Chromium launch failure becomes a skip, WFG-196). **`docs/NUMBERS.json` is not in the diff and
no artifact under `data/processed/` is either**, so no result section could gain a number, a table
or a figure. `paper/make_figures.py` was run and printed `drawn [F1 … F9]; skipped []`, after which
`git status paper/figures/` is empty — all nine redrawn, all nine byte-identical. `F9_present_perimeter`
is still drawn, committed and **not** referenced (gap **G8**, NH-032 open). Gap count unchanged at 7.

### The mandatory correction: §4.5's count of who still disagrees with the paper

§4.5 ended 「**One** repository document still draws the stronger conclusion from those same five
points … a **second** was narrowed to this reading during revision」. The incorporated diff made
that false. `d6d801d` added a Round-4 bullet at **`README.md:232`** reading 「그 sweep 안에서
**고원이 아니라 뾰족한 봉우리**입니다」 — the 1 km buffer width is a sharp peak and not a plateau — <!-- forbidden-ok: wc011-buffer-width-is-a-spike-ko --> <!-- These lines RECORD the withdrawn shape claim in order to say it was withdrawn; WC-011 registered it on 2026-09-08 and this file is not record class, so the quotation is licensed per line rather than by exemption (CHARTER §3.5c). -->
which is exactly the shape §4.5 says five points a factor of two apart cannot resolve. §4.5 now
reads **「Two repository documents still draw … others were narrowed to this reading during
revision」**. Net **−1** word; no caveat and no registered number moved.

**The subject grep, run as DIRECTION requires — on the subject, not on the sentence.**
`git grep -n -E "뾰족|평평|고원|봉우리|plateau|spike|sharp peak" -- README.md docs/ paper/ release/ web/ src/ scripts/ tests/`,
record-class pages (`reports/`, `archive/`, BACKLOG, CRITIC_LATEST, DIRECTION, KCF_READINESS,
NEEDS_HUMAN, SCORECARD, MEMO, dashboard) excluded, unrelated hits dropped:

| file | what it says | side |
|---|---|---|
| `README.md:232` | 「고원이 아니라 뾰족한 봉우리」 | **asserts the shape** (new in this diff) | <!-- forbidden-ok: wc011-buffer-width-is-a-spike-ko --> <!-- These lines RECORD the withdrawn shape claim in order to say it was withdrawn; WC-011 registered it on 2026-09-08 and this file is not record class, so the quotation is licensed per line rather than by exemption (CHARTER §3.5c). -->
| `docs/present_perimeter_arm.md:129` | 「The 1 km row is a **spike, not a plateau**」 | **asserts the shape** | <!-- forbidden-ok: wc011-buffer-width-is-a-spike-en --> <!-- These lines RECORD the withdrawn shape claim in order to say it was withdrawn; WC-011 registered it on 2026-09-08 and this file is not record class, so the quotation is licensed per line rather than by exemption (CHARTER §3.5c). -->
| `docs/fair_opponent_line.md:60, 75, 106` | separates neither; 「§3 asserts neither」 | states the resolution limit |
| `docs/auto/DEMO_SCRIPT_5MIN.md:151` | 「이 실험은 가리지 못합니다」 | states the resolution limit |
| `docs/auto/JUDGE_QA.md:920-921, 1394` | 「이 sweep 으로는 구분할 수 없습니다」 | states the resolution limit |
| `docs/NUMBERS.json` `pp_uiseong_*` caveats | fact (3) 「an operator on the day cannot know which width they are on」 | **asserts the shape** — re-read this lap, unchanged, and the clause 「as do the caveats the registry carries on this arm's own entries」 is kept because of it. ⚠ The first draft of this row also cited fact (2) 「it sits on the crossing of two failure regimes」; the reviewer showed that is the change-of-kind statement §4.5 itself endorses, so the clause stands on fact (3) alone |
| `paper/manuscript.md` §4.5 | the resolution limit | corrected here |

⚠⚠ **The mechanism, and the correction this lap's reviewer forced on this very paragraph: it is
NOT new, and this lap re-derived a finding the repository had held for three and a half hours.**
Critic #44 filed it at 2026-09-08T1700Z (`dc8fa9f`, inside the diff this lap incorporated) as
「A FOURTH SURFACE」 in WFG-127's own row — the row this section cites by name — with the same
diagnosis and a sharper root than the first draft here had. The three narrowed surfaces held: none of
them regressed. `README.md:232` is not a survival that a sweep missed — **the sentence was written
after the correction, into a file that had never carried it**, and the file is the project's front
door. Nothing here could have caught that. The shape claim is in **no** entry of
`docs/auto/withdrawn_claims.json`: checked key by key this lap, none of `spike`, `plateau`, 고원,
봉우리, 뾰족 or 평평 occurs anywhere in that file, so `check_withdrawn_claims.py`'s scan never
reads for it. ⚠ **That scan covers 935 gated files, re-derived this lap by running the script**
(「PASSED === 10 claims over 935 gated files」); the first draft of this section, of `paper/README.md`'s
lap-21 block and of the G8 row above all said **933**, which is lap 18's figure carried forward and
was caught by this lap's independent reviewer. The **933** in lap 19's `WC-010` paragraph, in lap
18's own verification table in this file, and in `paper/README.md`'s lap-19 block is left standing as
those laps' record (CHARTER §3.7); it is not today's count. ⚠ No line numbers are given for them
deliberately — this lap's insertions moved every one of them, which is the same hand-typed-locator
defect lap 20's reviewer blocked a push over. The only guard that exists is
`tests/test_fair_opponent_line.py`, which bans the retired spellings **in one file, by name, and in
English**. WFG-127's root is the second half of that: `:177-191` reads 「spike, not a plateau」; <!-- forbidden-ok: wc011-buffer-width-is-a-spike-en --> <!-- These lines RECORD the withdrawn shape claim in order to say it was withdrawn; WC-011 registered it on 2026-09-08 and this file is not record class, so the quotation is licensed per line rather than by exemption (CHARTER §3.5c). -->
`README.md:232` is Korean and uses the exact vocabulary (뾰족한 봉우리 / 고원) that
`DEMO_SCRIPT_5MIN.md:151` already uses for the *negation*. **That is §3.5's own 「It matches
spellings, not meaning, and one language at a time」, firing on a guard rather than on the registry
and on a newly written claim rather than a surviving one** — DIRECTION's standing rule, filed as
WFG-168, which does not exist yet. ⚠ **So no manuscript sentence is owed and none was written:**
§3.5 already states the limit this instance instantiates, and the first draft of this section called
it 「a third failure mode」 and 「new」, which its independent reviewer showed was false in both
words. WFG-127 is the row; measured at `eff2183`, it is table row **12** and the **second** `todo`
row, WFG-199 having been put at the head of the `todo` block by critic #45 in that same commit —
this section's first draft said 「position 1」, which was true at `9c24a8b` and was falsified by the
last commit of the range this lap incorporated. ⚠ **That is the same wrong-count class as the §4.5
defect this lap exists to fix, committed by the lap in the act of reporting it.** The remaining
correction — WFG-127 (iv) and (v) — is a dev-lap job outside CHARTER §12's paths.

### ⛔ The limitation this lap wanted, its exact cost, and why it is not in the paper

**The paper does not say that its hazard field cannot be current, and it should.**
`docs/live_pipeline.md` §0 states it as the project's own lead-with-what-it-cannot-do line —
「화점 탐지: 실시간 (FIRMS NRT) / 기상 자료: … ERA5는 약 5일 지연 발행」 — `live/scope.py` owns
those two strings so a retyped caveat cannot drift, `tests/test_live_pipeline.py` fails if either
is missing from any screen, A4 sheet, broadcast script, SMS draft or JSON record, and the diff this
lap incorporated added `tests/test_adoption_card.py`, which binds a judge card that opens on the
same asymmetry. `paper/references.bib`'s `era5` note already carries the fact, verified at the
Copernicus page on 2026-09-08: 「about five days' latency」. **The manuscript carries none of it.**
`grep -niE "latency|lag|five-day|5-day|precomputed|real-time|live" paper/manuscript.md` returns one
relevant line — §6's 「No trigger has ever fired on a **live** detection」 — which says the system
has not been run live and does not say that its weather source makes a current field impossible.
That is a structural limit, not an incidental one: no amount of deployment effort removes it, only
a different weather source does, and the paper's own framing (「which way a rural household should
walk **now**」, Abstract) is what makes a reviewer ask.

The sentence, drafted, placed at the head of §6's **Operational status** paragraph:

> The hazard field cannot be current: ERA5 publishes on a ~5-day lag.

**Measured, not estimated.** It was inserted, `build_docx.py` was run, and `body_words` went
**8,993 → 9,005**: **12 words against a margin of 7**, and 5 over the proxy's hard fail. It was
then reverted and the manuscript rebuilt at 8,993. Nothing was compressed to try to fit it:
CHARTER §12 forbids buying space with a caveat, the only prose left to compress is the litigated
stock that produced wrong sentences at laps 13 and 15, and the two clauses in §4.5 that could have
been squeezed for the balance — 「from those same five points」 and 「an open item there」 — are
payload, the first tying the strong claim to the very grid the sentence says cannot support it.

⚠⚠ **This is the datum NH-037 did not have, and it is a different kind from all the earlier ones.**
Laps 13–18 recorded illustrations and better wordings the budget declined, and lap 19 retired the
one-directional form of that complaint. What the budget declined **this** lap is a **limitation** —
a fact about what the system cannot do, on the paper's own core operational claim, sourced,
verified, and enforced everywhere else in this repository. CHARTER §3.5's rule is 「no rounding a
limitation away」. ⚠ And the honest other half, owed by the same rule: **the manuscript is not
false without it.** It claims no real-time operation anywhere, and §6 says no trigger has ever
fired live. What is missing is the reason, and a reviewer who asks for it is asking a fair
question the paper cannot currently answer. Also owed: this lap **re-measured** the document rather than
inheriting the count — the moved `body_words` invalidated lap 20's anchor, and after the `apt` line
`check_paper.py` printed `pages 23, calibri_face Carlito, metrics_ok true` and the new anchor
`84b91dde83d63607`. **Two pages of margin against the author's 25, seven words against the proxy.**
Twelve more words move no page: the rule that stopped this sentence is the proxy, not the author's.

**What the next lap or the author does with it.** The sentence above is verbatim and costed; land
it the moment NH-037 raises the proxy, or as part of any lap that frees 12 words honestly. It is
**not** a `[GAP]` marker and no marker was opened: the evidence exists and is committed, so the
paper is short a sentence, not short a run.

## What lap 20 incorporated (2026-09-08): a defect found, a fix written, the reviewer's block, and the revert — plus the page count re-derived

**`manuscript.md` is byte-identical to the one lap 18 pushed.** `body_words` stays **8,994**,
the margin against the 9,000-word proxy stays **6**, `figures` 8, `tables` 4, `references` 29,
gaps **7**. This lap wrote a change, its independent reviewer **blocked** it, and the change was
**reverted rather than argued or shipped** (CHARTER §4 step 5). What survives is the finding, the
re-measurement, and the datum NH-037 was waiting for.

Incorporated diff **`d36ad21..dee1bc1`**, **seven** files outside `paper/` and `docs/auto/`:
`README.md` (a new Round-4 section), `docs/creativity_card.md` (new), `web/finals.html` (its one
embedded stamp line), `release/kcf-finals-2026/MANIFEST.json` (hashes), and
`tests/test_creativity_card.py`, `tests/test_readme_round4.py`,
`tests/test_responsibility_and_privacy_cards.py`. **`docs/NUMBERS.json` is not in the diff and no
artifact under `data/processed/` is either**, so no result section could gain a number, a table
or a figure. `paper/make_figures.py` was **run** and printed `drawn [F1 … F9]; skipped (artifact
absent) []`, after which `git status paper/figures/` is empty — all nine redrawn, all nine
byte-identical. `F9_present_perimeter` is still drawn, committed and **not** referenced (gap
**G8**, NH-032 open).

### The page count was re-derived this lap, and it is the lap's one unqualified product

This lap ran the `apt` line `paper/README.md` and `measure_pages.py --why` have printed since lap
9, so `check_paper.py` took its **measuring** branch for the first time since lap 18:

```
[check_paper] pages {"pages": 23, "calibri_face": "Carlito", "metrics_ok": true}
[check_paper] built_pages_inputs f2ee9be6c9c7c4e0  (measured this run)
```

The anchor was **re-derived and found to match**, not accepted. ⚠ That is machine setup, not a
repository change, and it does **not** close **WFG-116**: the fix that makes a *clean clone*
measure is the same line in `.github/workflows/auto-gates.yml`, outside `paper/`, still open.

### The finding, which stands

`docs/auto/DIRECTION.md:59`: **「Every judge-facing surface that states 42 or 91 carries both
binding caveats (fire-blind opponent; upper bound for a noiseless forecast). A new sentence about
either number carries both caveats or it is not written.」** CHARTER §14b names the manuscript as
a judge-facing surface. The manuscript carries the **fire-blind** caveat in the Abstract, §4.3,
§4.4, §6 and §7, and carries the **upper-bound** caveat only in §4.5, scoped there to the
present-perimeter comparison and not to the 42.

⚠ **The repository already had a more precise specification of this defect than the lap wrote,
and the lap did not run it.** `tests/test_future_aware_attribution.py` enumerates exactly **two**
claim blocks in `manuscript.md` — the **Abstract** and **§7** — and
`test_the_manuscript_claim_blocks_do_not_yet_name_it` is `xfail(strict=True)` because neither
names the oracle bound. Three lines settle it:

```
.auto/venv/bin/python -c "import sys;sys.path.insert(0,'tests');import test_future_aware_attribution as T;from pathlib import Path;print([T._names_the_oracle_bound(b) for b in T._claim_blocks(Path('paper/manuscript.md'))])"
[False, False]
```

**That test, not this ledger, is the specification for the fix.**

### The fix that was written, and the four reasons it was blocked

The lap put the caveat in the Abstract and in §4.3's third caveat and paid for it by replacing
§4.5's 43-word statement with a 9-word back-reference. Every defect below was found by the
independent reviewer and **verified in this tree before the revert**; none is reachable by any
gate in this repository.

1. ⚠⚠ **The load-bearing line number was wrong and was written into three files unverified.**
   The lap asserted that `README.md:626` cites `paper/manuscript.md` §4.5 for the upper-bound
   caveat. It does not — `:626` is the English abstract draft and carries **no citation at all**.
   The citing line is **`README.md:38`**, the TL;DR bullet, CHARTER §14b's first-named
   judge-facing surface, which the lap never identified. `sed -n '38p;626p' README.md` settles it
   in under a second, and DIRECTION's subject-grep rule exists for exactly this. It was not run.
2. ⚠⚠ **The fix deleted the text `README.md:38` cites.** `grep -niE 'noiseless|upper bound'
   paper/manuscript.md` matched `:512`, in §4.5, before the diff and matched nothing in §4.5
   after it. README:38 would have been left citing a section silent on the claim it quotes —
   **strictly worse than the scope mismatch the lap set out to fix** — and CHARTER §12 bars this
   routine from repairing `README.md`.
3. ⚠⚠ **The Abstract clause inverted the bound.** It read 「bounds a noiseless forecast rather
   than this model」. Everywhere else the repository states this — `README.md:36-38`, `:626`,
   `docs/present_perimeter_arm.md` §5 — the 42 is an upper bound **on this model** and **equals**
   what a noiseless forecast would buy. The lap's wording says the number bounds the noiseless
   forecast and explicitly *not* this model, which reads as 「this model may do better」: the
   inverse of the safety-relevant meaning, on the headline number, in the most-read block, inside
   the diff whose whole purpose was to make two surfaces agree. It also dropped the direction
   word 「upper」 that DIRECTION:59 names.
4. ⚠ **The back-reference was false of §4.5, and the merged lead had no premise.** §4.5's
   opponent is expressly *not* fire-blind — that is the section — so importing 「§4.3's third
   caveat」 imported a half that is false there. And the merged lead's second clause was
   established nowhere in §4.3: the sentence that established it was the one deleted from §4.5,
   so the paragraph jumped to a conclusion whose mechanism had left the section.

⚠ **And one the reviewer found inside this routine's own file.** Row **G8** above asserts 「and
§4.5 states both: the forecast-aware arm plans on the field it is graded against …」. The diff
would have made that false — a live gap row, in the file the lap was editing in the same diff,
left standing. It is true again on the reverted text and is not edited.

### Why it was reverted rather than repaired, which is NH-037's answer

The correct version needs: the mechanism stated once **with its premise** (about 48 words as a
fourth §4.3 caveat); §4.5's original 43-word scoped statement **kept**, so `README.md:38`'s
citation survives; a corrected Abstract clause (about +23); and **§7**, which the tripwire also
enumerates. That is roughly **+50 words net against a margin of 6**. Every cheaper shape was
costed and each one either inverts the bound, strands the premise, or breaks the citation.

**Nothing was compressed and nothing was trimmed to close the gap.** CHARTER §12 forbids buying
space with a caveat, and the only prose left to compress is the litigated stock that produced
wrong sentences at laps 13 and 15. So the lap reverted.

**Both margins, measured on this document on one run: 23 pages against the author's 25 (NH-028)
is two pages; 8,994 words against the proxy is six words.** When NH-037 was written they were
two pages and **55** words. The word margin has fallen to **6**; the page count has not moved
once. ⚠⚠ **The case NH-037 was written for has now arrived**: a correction that the repository's
own DIRECTION rule *and* its own strict tripwire both require does not fit — and the rule it does
not fit is the proxy, not the author's.

### What whoever lands this needs to know

The fix is **not four words**, and an earlier draft of this section said it was. Because
`test_the_manuscript_claim_blocks_do_not_yet_name_it` is `xfail(strict=True)`, whoever lands the
clause must **also** promote `paper/manuscript.md` into that test's `ORACLE_SURFACES` and rewrite
its reason string, or the suite turns red the moment the prose becomes correct. `tests/` is
outside CHARTER §12's paths, so that half is a **dev-lap** job.

## What lap 19 incorporated (2026-09-08): the manuscript did not move, and the proxy that has been squeezing it does not count 2,403 of the words it renders

No `[GAP]` opened or closed; the count stays at **7**. **`manuscript.md` is byte-identical to
the one lap 18 pushed.** `body_words` stays **8,994**, the margin against the 9,000-word proxy
stays **6**, `figures` 8, `tables` 4, `references` 29 — so `built_pages_inputs` is unchanged at
`f2ee9be6c9c7c4e0` and the recorded **23 pages** still anchors to the document it was measured
on. No re-measurement was owed and none is claimed; this sandbox again cannot render, and
`check_paper.py` prints `pages null`. ⚠ Read that precisely: `/usr/bin/soffice` **does** exist
here (LibreOffice 24.2.7.2), and it is the `libreoffice-writer` component that is absent, so a
reader who checks `which soffice` will find a binary. `README.md`'s own diagnosis is the
operative one — no text-document import filter, so every word-processor format fails identically.

Incorporated diff: **`c456da7..d36ad21`**, thirteen commits, **four** files outside `paper/` and
`docs/auto/` — `docs/clean_clone_gates.md`, `release/kcf-finals-2026/MANIFEST.json`,
`tests/test_tile_gated_skip_count.py` and `tests/test_responsibility_and_privacy_cards.py`.
**`docs/NUMBERS.json` is not in the diff and no artifact under `data/processed/` is either**, so
no result section could gain a number, a table or a figure. `paper/make_figures.py` was **run**
and reported `drawn [F1 … F9]; skipped (artifact absent) []`, after which `git status
paper/figures/` is empty — so all nine were redrawn and all nine are byte-identical. ⚠ The
`git status` line alone would not distinguish that from never having run the script, which is why
the run's own output is quoted beside it. `F9_present_perimeter` is still drawn,
committed and **not** referenced (gap **G8**, NH-032 open).

### Nothing in the diff made a manuscript sentence false, and this is what was checked

The manuscript makes exactly four assertions about this repository's own instrument, and the
diff touches the machinery behind all four, so each was re-run rather than reasoned about:

| §3.5 / availability sentence | check | result |
|---|---|---|
| 「a gate re-derives every entry on every change, scans the prose for retired figures and quantity-name collisions」 | `scripts/check_number_collisions.py` | `OK — no registered quantity appears elsewhere with a different, unmarked value (22 quantities carry marked historical values)` |
| 「every gated document is read against it」 | `scripts/check_withdrawn_claims.py` | `PASSED === 10 claims over 933 gated files` — the same 10 and 933 lap 18 recorded; the diff registered no new `WC-###` |
| 「a data file or a generator escapes it」 | `scripts/check_withdrawn_claims.py` docstring and `_git_files()` in the collision gate | both read tracked `.md` (plus `.html` / `.py` respectively). Still true, and the diff supplies a new instance — see below |
| 「This manuscript is scanned by both gates like any other document」 | `git ls-files '*.md'` includes `paper/manuscript.md`; both gates glob it | true |

And the one number-bearing sentence the diff could have moved:

- **§3.5's 「September 2026 retractions skipped it three times」 is unchanged, re-derived from the
  commits and not from the ledger's own summary** (which is the error lap 17 made). The diff
  registers **no new `WC-###`** at all: `docs/auto/withdrawn_claims.json` changes only two fields
  of the existing `WC-010`. The 0407Z lap that made that change says in its own report why it
  registered nothing — 「Nothing was withdrawn: a count was corrected」 — and the available
  spelling 「여섯 개」 is a common Korean phrase live in nine unrelated files, so registering it
  would have manufactured false positives. A corrected count is not a retraction, so it is not a
  fourth skip.

Two further sentences were re-read against the diff and are unaffected. §6's 「the SMS path is
simulated … the approval-gated email channel has never completed a verification send」 was
independently re-verified by the 0655Z dev lap against the tree (`sms.send(` called nowhere in
`src/` or `scripts/`, 28 run records carrying `nothing_was_sent: true`, no `email_sent.json`
anywhere), and `tests/test_responsibility_and_privacy_cards.py` now checks that absence *as* an
absence. ⚠ Do not read NH-041 as touching it: that entry is about this loop's **report email** to
the author, not about the delivery layer §6 describes. §3.4's `immobile_fraction` of 0.3 is read
from the committed artifact by the same new test and matches.

### The finding: the word proxy does not count 2,403 of the words the document renders

Every lap from 13 to 18 has had its writing shaped by the 9,000-word proxy, and five reports have
described that pressure without anyone measuring what the proxy actually counts. Measured by
**`paper/measure_render_gap.py`**, new in this lap, on the shipped `.docx`:

```
rendered in the built document :  11397
counted by build_docx.py       :   8994  (body_words)
rendered and NOT counted       :   2403  (21.1% of the document)
the proxy sees                 : 79% of the words that render
  figure captions                                 789
  table captions                                  439
  table cells                                     213
  headings                                        119
  references (29 entries)                         802
  title-page front matter                          39
  citation markers rendered but not counted         2
of that, prose a lap could move a sentence INTO: 1441  (16.0% of body_words)
```

The mechanism is one line of `build_docx.py`: `body_words` is incremented only in the paragraph
branch (`:187`) and the list-item branch (`:177`). The figure branch, the `Table N.` caption
branch and the pipe-table branch each `continue` without touching it, and the References section
is generated after the loop has finished. The two-word residual is the other half of the same
line: the counter strips `[@key]` from the source while `add_runs` renders `[n]` in its place.

⚠⚠ **The first draft of this table was itself a word miscount, its independent reviewer found it,
and the script above is the repair rather than a corrected integer.** The draft decomposed the
Markdown *source* instead of the rendered *document* and published figure captions 773, table
captions 431, headings 153 and front matter 40 — which sum to **2,412** against the **2,403** they
claim to decompose. Two distinct errors: heading lines were counted with their `#` markers
attached (`153` against the `119` words that render in Heading style; the 12-word title renders as
front matter, not as a heading), and the builder prepends a rendered `Figure N. ` / `Table N. `
label the source does not contain (8 × 2 and 4 × 2 words, both likewise uncounted by
`body_words`). **The one lap whose entire product was the finding that a word counter mis-counts
words shipped a word miscount of its own, in the same table, replicated into three files** — and
nothing in the repository could have caught it, because the lap had committed no script that
re-derives any of the six integers. That is the reviewer's root objection and it stands as
written. `measure_render_gap.py` exits **1** when its parts do not reconcile with its total, so a
decomposition that does not add up can no longer be printed as though it did. ⚠ It gates nothing:
no push runs it, so an integer copied out of it into prose can still go stale in the ordinary way
— the standing weakness `measure_pages.py` has, and a dev-lap item for the same reason (CHARTER
§12 keeps this routine out of `tests/`).

**Three consequences, in the order they matter.**

1. **The proxy is bypassable and the bypass is one keystroke**, over **1,441** words of caption
   and table prose — 16.0 % of `body_words`. A lap under length pressure can
   move a sentence out of a paragraph and into the figure caption directly above it, and the gate
   will report the document as having shrunk. That is the shape of the bypass lap 9's reviewer
   killed in `built_pages_inputs` — where 「paste the digest the gate just printed」 and the honest
   act were the same keystrokes — and here nothing at all stands against it. ⚠ **This lap did not
   use it and no lap may.** A sentence belongs where its argument belongs; a caption that carries
   body argument to dodge a counter is a false measurement of the document, not a short document.
2. **This paper's captions are already unusually heavy, and one of them carries argument that is
   nowhere else.** F5's caption ends 「Not re-acquiring the region is deliberate: the walk box does
   not fit the simulation grid, so redrawing it would force re-extending the canvas and
   re-simulating the field, replacing a stated limit with an unstated one」 — a methodological
   justification, not a description of the figure, and §4.3's first caveat does not restate it.
   ⚠ **No claim is made about how it got there.** `git log -S` names `e649f2d` as the commit that
   introduced the string, but this clone answers `true` to `--is-shallow-repository` and holds
   **50** commits (measured 2026-09-08), so `e649f2d` shows `manuscript.md` as a *new file* and
   that is the clone boundary, not the file's history. CHARTER §4 forbids the ancestry claim and
   none is made. Moving the sentence into §4.3 would cost about 30 words against 6 and is
   therefore not done; it is recorded so the next lap that has room can do it.
3. **It changes what NH-037 is asking the author.** The question five laps have put is 「the proxy
   stops us about a thousand words before your 25-page rule」. The truer question is that the proxy
   measures **79 %** of what renders, is therefore tight on prose and blind on captions and
   tables, and that the words-to-pages curve in `README.md` was calibrated at *this* caption
   density and holds only there — `calibrate_pages.py` holds the figures, tables and references
   fixed by construction. The remedy that removes the whole class is not a bigger number: it is
   **WFG-116's one `apt` line in `.github/workflows/auto-gates.yml`**, after which a clean clone
   measures the 25 pages the author actually set and the proxy stops being load-bearing.

### The sentence six laps have declined is retired as a want, and this diff is why

Laps 13 to 18 each recorded declining the same optional §3.5 illustration — *that registration
keeps finding live copies a hand sweep missed* — and cited the decline as the cost of the budget.
**It should not be written in that form, budget or no budget, and this lap withdraws the want
rather than deferring it a seventh time.**

The diff contains the other direction. `WC-010`'s **`say_instead`** field — the field that tells
the student what to say *instead of* the withdrawn claim — carried 「여섯 개」 / 「six tests」 from
the moment it was written, and the scan that enforces `WC-010` across 933 files reads `.md` and
`.html`, so **it does not read the file `WC-010` lives in**. Registration could not have found it.
A hand grep of the *subject* across every extension did, returning 34 hits, which is DIRECTION's
own rule doing the work the machine structurally cannot.

⚠ **Stated at its true size.** This is not a contradiction of the declined sentence — both
directions can hold, and `WC-009` finding a live copy in a file two readers had passed is real.
What it kills is the **one-directional present-tense form** all six drafts had, which is the exact
register `WC-009` itself forbids. The two-sided sentence that would be honest is longer than the
one-sided one, says less, and is about this loop's bookkeeping rather than about wildfire
evacuation — so the right answer is that an IEEE manuscript does not carry it. ⚠ **It also shrinks
NH-037's own case by one line**, and that correction is owed: the entry has been carrying 「a true
sentence declined for the sixth lap running」 as evidence, and that particular sentence was not one
the paper should have had. The rest of NH-037 stands untouched — laps 13, 15 and 16 each funded a
**mandatory** correction by compression, and lap 13 shipped two wrong sentences doing it.

The window: `WC-010` was registered in `ab4e71e` (2026-09-08T01:21:58Z) and the field corrected in
`82ec346` (2026-09-08T03:37:48Z) — **2 h 16 min on the two commits' author dates**. The entry's
own prose says 00:18Z and 03:21Z; those are lap stamps, not commit times, and the difference is
why the commits were read. ⚠ **Which of the two commit timestamps is not a detail here**, and the
reviewer was right to say the silence was not defensible: `82ec346` was rebased, so its
*committer* date is 04:25:05Z and the same window read that way is 3 h 03 min. Author date is the
one that answers 「how long was the wrong wording in the tree the lap wrote it into」, so it is the
one used and now the one named. That `ab4e71e^` holds no `WC-010` at all — so 「from the moment it
was written」 is answerable rather than assumed — was checked in this clone, `ab4e71e` being 15
commits from `HEAD` and therefore inside the depth-50 boundary.

### What this lap deliberately did not do

- **No prose was compressed to bank margin.** It was considered: the margin is 6 words, critic #40
  wrote that 「the next sentence any lap adds parks it」, and this lap had no mandatory correction
  to fund, which makes it the cheapest lap in which to realise compressible stock. It was refused
  because every compression is an edit to litigated prose for no gain in truth, and two of the
  three sentences laps 13 and 15 got wrong were compressions. The margin is 6 and is reported as 6.
  ⚠ **And it must not be reported bare, which the reviewer filed and this sentence answers: the 6
  is a margin against a proxy that does not measure the rule it stands in for.** A lap cannot
  establish in one paragraph that the counter is blind to 21 % of the document and in the next
  quote its residue as the operative constraint. What is operative is the author's 25 pages; the
  document measured 23 at lap 18 and no input to that measurement has moved. The 6 is what the
  gate will enforce until NH-037 is answered, and that is all it is.
- **No sentence was moved into a caption**, for the reason in consequence 1 above.
- **No `[GAP]` was opened for the missing archival identifier.** 「Data and code availability」
  points at a moving GitHub branch with no tag and no DOI, which an IEEE venue will ask about. It
  is not an evidence gap — nothing in the paper is unsupported by it — and it is already tracked as
  **WFG-031** (`CITATION.cff` without a `doi:`) and **WFG-015** (P3, IEEE), both author-only after
  the finals, needing a Zenodo login this sandbox does not have. Recorded here rather than as a
  marker so the gap table keeps meaning 「evidence the artifacts cannot supply」.
- **No new figure.** No new artifact means nothing to draw; F9 stays drawn and unreferenced.

## What lap 18 incorporated (2026-09-08): the paper was running two provenance standards, and the repository had just registered the rule against it

No `[GAP]` opened or closed; the count stays at **7**. The document went **8,995 → 8,992** and
the margin against the 9,000-word proxy went **5 → 8**. **Re-measured, not inherited:** this lap
ran the `apt` line `README.md` records and `measure_pages.py` returned **23 pages** under Carlito,
page objects and page-tree `/Count` both 23; the anchor `1c92e40a8efbd84d` was printed by the run
that measured it.

Incorporated diff: **`64f015b..c456da7`**, ten files outside `paper/` and `docs/auto/`. No new
artifact under `data/processed/`, so no result section gained a number, a table or a figure, and
all nine figures re-rendered **byte-identically** (`git status paper/figures/` empty).
`F9_present_perimeter` is still drawn, committed and **not** referenced (gap **G8**, NH-032 open).

### Nothing in the diff made a manuscript sentence false, and that was checked rather than assumed

- §2's NIFoS clause was already at 「whose catalogue chapter list implies an operator-set origin
  point」, which is the wording `docs/auto/withdrawn_claims.json`'s **WC-009** prescribes.
- `docs/related_work.md` row 13 was narrowed in the same family and now agrees with §2.
- **WC-009** and **WC-010** were each registered **inside the lap that withdrew them**, so neither
  is a fourth registration skip and §3.5's 「three times」 is unchanged.
- `docs/clean_clone_gates.md`'s new network-guard section and `tests/conftest.py` describe a gate
  this manuscript does not cite; no sentence here depended on the defect they closed.

### The real item was the one lap 17's reviewer filed and did not fix

Fifteen of the 29 references were verified 「via the Crossref record」 — **a catalogue entry** —
while §2 characterised six of them substantively. The incorporated diff registers **WC-009**
against exactly that move: 「NEVER a flat present-tense sentence about what a system does, in
EITHER direction, when the only thing opened is a catalogue record or a newspaper.」 The paper was
applying that standard to the two Korean operational systems and **a laxer one to the Western
evacuation-routing literature**, and `check_paper.py:203` cannot see the difference because it
tests only for the substring `verified`.

**This lap opened what could be opened.** Twelve abstracts were retrieved in full and quoted
verbatim into their notes: `cova2005`, `wahlqvist2021`, `finney2002`, `radeloff2005`,
`studenski2011` and `farr2007` through the OpenAlex records; `wildfirespreadts2024`, `rescue2026`
and `boeing2017` through the Semantic Scholar records; `ndws2022`, `borgwardt2024`, `wstsplus2026`
and `angelopoulos2024crc` re-opened at their arXiv pages.

**Four could not be opened, and are now marked `⚠ CATALOGUE RECORD ONLY`.** `dozier1981`,
`cova2003`, `li2017` and `li2019`: `doi.org` redirects to Elsevier or Springer, `linkinghub` and
the ScienceDirect abstract pages return HTTP 403, `link.springer.com` redirects to an
authorisation endpoint, Unpaywall reports `is_oa: false` for all four, and Crossref, OpenAlex and
Semantic Scholar all carry the record with the abstract empty or elided by the publisher.
`nifos2026guide` is the fifth and was already so; it is now marked with the same phrase so the
count is greppable.

### Three sentences were narrowed because of it, each to what the title actually supports

| citation | was | is | why |
|---|---|---|---|
| `li2019` | 「later coupled to traffic simulation **so it accounts for the time evacuation takes**」 | 「later coupled to **fire and traffic simulation models**」 | the second clause is in nothing that was opened **and** is contradicted in implicature by `cova2005`'s own abstract, which already takes 「estimated evacuation time」 as an input. It claimed a novelty the record does not support and the earlier paper partly forecloses (**−5**) |
| `li2017` | 「to name the **road segments** that matter」 | 「to identify **the prominent ones**」 | 「road segments」 appears nowhere in what was opened; 「prominent … trigger points」 is the title (**−2**) |
| `dozier1981` | 「the sub-pixel area inversion **standard since** Dozier」 | 「**a** sub-pixel area inversion **after** Dozier」 | 「standard since」 is a claim about the literature's status, made from a title (**−1**) |

§4.8's 「two-component sub-pixel split」 is **left standing**, and that is a decision rather than an
oversight: it describes *this repository's* computation on its own committed artifact, not the
content of a paper nobody here opened. The note says so in as many words.

### Two more were narrowed onto text that was opened, and two compressions are also corrections

- `cova2005`: 「a **spatial line** whose crossing by the fire front should **start an evacuation**」
  → 「a **buffer edge** whose crossing by the fire front should **trigger evacuation**」 — the
  abstract's own noun and verb, 「a trigger buffer … whereby an evacuation is recommended if a fire
  crosses the edge of the buffer」 (**−1**).
- `kim2021gk2a`: 「returns the **Korean local area** every two minutes」 → 「returns **its sectored
  regions** every two minutes」. The abstract gives 「2 km for near-infrared and infrared channels」
  and 「around 10 min for full disk and 2 min for sectored regions」 and **does not name the Korean
  peninsula as the two-minute sector**. The identification of the sector this repository ingests is
  made in §3.1 from the archive it reads, which is where it belongs (**−1**).
- `wstsplus2026`: 「**reports that** time-series inputs beat」 → 「**finds** time-series inputs beat」,
  matching the abstract's 「we found that」 (**−1**).
- `studenski2011`: 「the range for which gait speed is **an established predictor** of survival」 →
  「the range over which gait speed **predicts** survival」. The abstract supports 「predicted
  survival」; 「established predictor」 is a claim about the literature's status that one pooled
  analysis does not settle (**−4**).

### ⚠⚠ The one sentence the lap ADDED broke the rule the lap spent its whole diff enforcing, and its reviewer killed it

The draft wrote, in Data and code availability: 「Each reference's note says what was opened; five
rest on catalogue records.」 **Root objection: that is a flat universal over 29 notes, written by a
lap that had rewritten 17 of them, and it is false for four.**

| entry | its entire note before this lap | says what was opened? |
|---|---|---|
| `firms` | 「verified 2026-09-03」 | **no** — 19 characters, no URL clause, no product named |
| `era5` | 「verified 2026-09-03」 | **no** — the same 19 characters |
| `worldcover` | 「… 10 m products for 2020 and 2021」 | **no** — a fact about the product, not about what was read |
| `osm` | 「… published under the Open Database License (ODbL)」 | **no** — the same shape |

**This is the WC-005 and WC-009 shape exactly**: a lap chooses which documents to correct, misses
one, and the sentence it writes to advertise the correction is the thing that is now wrong. The
first nail costs two greps and no source: `grep -c 'note = ' paper/references.bib` returns **29**,
and `grep -n 'note = {verified 2026-09-03}'` returns `firms` and `era5`.

**Second objection, independently fatal.** 「five」 was the only new number in the diff and it is
**unregistered**: no `docs/NUMBERS.json` key covers it, `scripts/build_numbers.py` never reads
`references.bib`, and `check_number_collisions.py` cannot see it — while it sat one line below the
manuscript's own 「Every measured number is registered in `docs/NUMBERS.json` and re-derived from
its artifact by `make verify`」. CHARTER §3.3: **a number you cannot register, you do not write**,
and CHARTER §12 forbids this routine from registering it. The count was *correct*; it was
ungated, and it goes stale silently the moment a sixth note is downgraded.

**The repair drops both halves.** The sentence now reads 「`references.bib` marks each work known
only from a catalogue record」 — no universal over the notes, no numeral, and still checkable by
grepping `CATALOGUE RECORD ONLY`. **And the four thin notes were fixed rather than only the
sentence**: `firms`, `era5`, `worldcover` and `osm` were re-opened at their URLs this lap and now
record what each page states.

### ⚠⚠ The reviewer's sharpest finding was a hole the narrowing itself opened

Dropping 「the Korean local area」 from §2 left §4.8's 「still a few alarms a day at a **two-minute
cadence**」 — a claim about the Korean sites — with **no stated source anywhere in the paper**. And
the `kim2021gk2a` note asserted that §3.1 supplied it, when §3.1's whole GK2A sentence was 「GK2A
level-1B radiances, read without credentials from the NOAA open-data mirror」: no sector, no
cadence. **That is the WFG-171 circle in reverse — a bib note certifying a repair the manuscript
does not contain — committed inside the lap whose subject is precisely that.**

§3.1 now reads 「GK2A level-1B radiances **from its two-minute Korean local-area sector**」, and its
source is **this repository's own ingestion, not the cited paper**:
`src/wildfireguardian/detection/gk2a.py` names the LA sector 「every 2 minutes at 2 km in the
infrared」 and builds `AMI/L1B/LA/<yyyymm>/<dd>/<hh>/` keys with area `la020ge`, and
`docs/gk2a_direction_experiment.md` records the archive as 「FD 10-min, LA 2-min」. §2 stays at the
abstract's own 「its sectored regions」.

### Two further note defects, both the desynchronisation this lap is about

- **`dozier1981`.** The note justified §2's wording as 「the title's own subject」. It is not: the
  title is 「A method for satellite identification of surface temperature **fields** of subpixel
  resolution」, and neither 「area」 nor 「two-component」 appears in it. The *sentence* is not false —
  the reviewer checked the claim against the world in both directions and it holds — but the note's
  **reasoning** was wrong. It now says what is actually true: both §2's and §4.8's phrases describe
  *this repository's* computation with the paper cited for the method's origin, and the attribution
  is conventional rather than evidenced from anything opened here.
- **`studenski2011`.** The note quoted §2's **old** wording (「is an established predictor of」) that
  the same lap had already changed to 「predicts survival」 — a note certifying a sentence the
  manuscript no longer contained. Refreshed.

### What the freed words bought, after the repairs

**+10**, in Data and code availability, and **+6 − 2** in §3.1 for the sector clause the reviewer
required. **Net +2 on the lap**, 8,995 → **8,994**, margin **5 → 6** — still the first lap since 16
to end with more headroom than it started, and the first since 12 to write an optional true
sentence at all. The sixteen rewritten notes cost **nothing**: `build_docx.py`'s `fmt_ref` does not
render the `note` field, which is the whole reason this lap could buy provenance for sixteen
references without spending a word on any of them. Every caveat, lineage warning, registered number
and gap marker is byte-identical to lap 17.

### What was declined, and it is the sixth lap running

The §3.5 illustration wanted since lap 15 — that registration keeps finding live copies a hand
sweep missed — has a **new and better instance** in this diff, and it was still not written.
`docs/withdrawn_claims.md` §5h records that WC-009's registration found a third copy in
`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §1, **a file the lap's own independent reviewer
had explicitly read and passed as clean**: two people read it, one machine read it, and only the
machine found that copy. The shortest honest form costs about 20 words against the 8 this lap ends
with. **Laps 13 through 18 have now all had their writing shaped by the proxy rather than by the
evidence. NH-037 is the answer and it is still open** — though this lap is the mildest instance
yet, because the work it most needed to do turned out to cost nothing.

## What lap 17 incorporated (2026-09-07): its reviewer blocked, and the block was right twice

No `[GAP]` opened or closed; the count stays at **7**. The document went **8,992 → 8,995** and
the margin against the 9,000-word proxy went **8 → 5**, the tightest it has been.
**Re-measured, not inherited:** this lap ran the `apt` line `README.md` records and
`measure_pages.py` returned **23 pages** under Carlito, page objects and page-tree `/Count`
both 23; the new anchor `295bbc7453f1ad14` was printed by the run that measured it.

Incorporated diff: **`6ee996b..64f015b`**, thirteen files outside `paper/` and `docs/auto/`.
No new artifact under `data/processed/`, so no result section gained a number, a table or a
figure, and all nine figures re-rendered **byte-identically** (`git status paper/figures/`
empty). `F9_present_perimeter` is still drawn, committed and **not** referenced (gap **G8**,
NH-032 open).

### ⚠⚠ The draft's repair was a category error, and its own reviewer killed it

The lap started from a real defect. §3.5 read:

> and every gated document is read against it, so a withdrawn claim **cannot survive in a
> prose file nobody thought to list**; a data file or a generator escapes it.

The counter-example is in the incorporated diff. `docs/withdrawn_claims.md` §5g-2 records that
**WC-008** was registered with an **English** spelling while the same claim went on living in
**Korean** inside `docs/auto/JUDGE_QA.md` Q16a — a **gated prose file**, and the T0 card the
student reads aloud to five judges. §5g and §5f record the mirror image ninety minutes earlier:
**WC-007** went in in Korean and its **English** twin was found alive in
`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3.3.

**The draft repaired it by appending 「or the same claim in the repository's other working
language」 to the escape list. That is the wrong list, and it leaves the broken half standing.**
The other two members escape by **scope** — a `.json` manifest and a `gated: False` generator
are never opened at all (`scope.extensions` = `['.md','.html']`) — whereas the Korean copy
escaped by **spelling**, inside a file the scanner *did* open and pass, green, all day. The
sentence would have read: *prose files are covered, except this prose file.* It was also an
overclaim in kind: a data file escapes **no matter what is registered**, while the other
language escapes **only until a lap registers it**, which the 1820Z lap did the same day
(`wc008-household-walk-out-negative-ko`). And the project's own registry says so —
`docs/withdrawn_claims.md` §5g files the cross-language case as 「§4 가 모든 패턴에 대해 적어 둔
한계가 그대로 실현된 것」, i.e. as an instance of the 「matches spellings, not meaning」 limit the
manuscript states two sentences later.

**The repair puts it where the evidence puts it.** The escape list is back to its lap-15
wording verbatim. The spelling sentence now opens 「It matches spellings, not meaning, **and one
language at a time**」 — which is *analytic*, a registered spelling being a spelling in a
language, so it needs no probe — and the probe stays attached to the rewording limit it
actually measured. The sentence closes 「and **both limits** are recorded rather than designed
away」. **+6 words.**

### ⚠⚠ The count was wrong, and the instance it omitted was this routine's own

§3.5 read 「September 2026 retractions skipped it **twice**」. **It is three**, and the first
draft of this ledger asserted 「twice」 on a justification that was **false**: that WC-008 was
registered inside the lap that withdrew it. Checked here against the commits rather than
against the ledger's summary, which is how the draft got it wrong:

- **Withdrawal:** paper lap 16, `8ff1b40`, **15:30Z** — which retracted the claim from
  manuscript §2 and, **in that same commit**, wrote the retracted sentence verbatim and
  **unlicensed** into `paper/GAPS.md:77` and `:79`.
- **Registration:** a **different routine**, dev lap `20260907T1528Z`, `7cc4eb7`, **16:12Z** —
  42 minutes and two reports later — whose own message reads 「Three record lines licensed with
  the token rather than reworded … `paper/GAPS.md` 77 and 79」.

**Both halves of the manuscript's own sentence fit that instance exactly**: the correction was
hand-applied, and it left the same claim standing in a file that lap had itself edited.
CHARTER §12 forbade paper lap 16 from touching `withdrawn_claims.json`, so it escalated NH-044
instead — but whether a lap was *permitted* to register is a different question from whether
registration happened, and the failure mode the sentence describes materialised. Declining to
count the one instance this routine authored would have read as self-serving. It now reads
**「three times」** (**+1**).

### The deleted clause is restored

The draft had funded its escape-list edit by deleting

> **, and that limit is recorded rather than designed away**

and calling it self-congratulation. The reviewer showed it is payload —
`docs/auto/reports/2026-09-05T0317Z-manual.md:31` records it as the reason the paragraph exists
for an IEEE reviewer — and that lap 16 paid for its own **+11** with meaning-preserving
**syntax** compressions while this draft paid by deleting a sentence's **content**. A different
transaction, and the ledger should not have called both 「not a caveat」. **Restored.**

### What paid for the +7

Four meaning-preserving syntax compressions, none a caveat, none a number, none a gap marker:
「a document **that states**」 → 「a document **stating**」 (−1); 「which **the scan** does read」 →
「which **it** does read」 (−1); 「a correction **applied** to a generated file」 → 「a correction to
a generated file」 (−1); 「like any other document **here**」 → 「like any other document」 (−1).
**Net +3.** Every caveat, lineage warning, registered number and gap marker is byte-identical
to lap 16.

### What the reviewer cleared, and the one thing it filed instead of fixing

Cleared: all 29 `[@key]` citations resolve in `references.bib` and all 29 carry a `verified`
note; §2 is consistent with `docs/related_work.md` rows 13–14 as narrowed at `7cc4eb7` and with
both bib notes; §2's 「walk out, and by which path」 does **not** collide with WC-008's registered
pattern, which requires 「along which path」; no other manuscript sentence goes false from the
incorporated diff; §4.5's 「one repository document still draws the stronger conclusion」 still
holds.

⚠ **Filed as a dev-lap row rather than a manuscript edit — and a hostile reviewer will raise
it.** Fifteen of the 29 references are verified 「via the Crossref record」, and §2 then
characterises their *content* substantively (`li2017`, `li2019`, `wahlqvist2021`, `cova2003`,
`cova2005`, `finney2002`). **A Crossref record is a catalogue entry** — the same standard lap 16
applied one commit earlier when it retracted the NIFoS sentence for resting on 「a catalogue
entry listing chapter names」. The paraphrases are all title-derivable, so none is called false;
what is real is that the paper now applies **one provenance standard to the Korean operational
systems and a laxer one to the Western evacuation-routing literature**, and
`check_paper.py:203` cannot see the difference because it only tests for the substring
`verified`.

### The subject grep, and the file it caught was this one

DIRECTION.md's rule is to grep for the **subject** of the claim, never for the sentence just
written. Run as `git grep -n -i "cannot survive\|nobody thought to list\|every gated document"`
and `git grep -n -i "escapes it\|빠져나갑니다"` over `docs/ paper/ release/ web/ scripts/`:

| file | what it holds | what this lap did |
|---|---|---|
| `paper/manuscript.md:271` | the claim itself | left at its lap-15 wording; the language case moved into the spelling sentence instead, per the reviewer's block above |
| `paper/GAPS.md:189` | lap 15's ledger, ending 「the completeness claim is now scoped to what the instrument actually reads」 — **an own-voice completeness assertion**, and the escape list it describes is still incomplete for the *spelling* reason, not the scope one | annotated in place as superseded (CHARTER §3.7), not deleted |
| `paper/README.md:66` | quotes lap 15's wording as a record; does not assert completeness in its own voice | pointer added in this lap's README block |
| `docs/auto/reports/2026-09-06T2119Z-manual.md`, `2026-09-07T0928Z-manual.md` | the same wording in past lap reports | **record class**, exempt by design (CHARTER §3.5c); left alone |
| `docs/withdrawn_claims.md` §4, §5f, §5g, §5g-2 | the registry's own account of its limits, including this one | already correct; it is the source for this lap's edit |
| `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §2, §3.3 | the two copies WC-007/WC-008 found | already corrected by the 1528Z and 1820Z dev laps |
| `web/finals.html`, `web/field_view.html` | `Escape` **keycodes** and Gleason's LCES **escape routes** | false hits of the second pattern; nothing to do |

### One more thing checked rather than assumed

- **WC-007 is *not* a fourth skip, and that was checked the same way.** Its lap tried to close
  by hand grep and its own reviewer blocked on exactly that; it then registered **in-lap**
  (`docs/withdrawn_claims.md` §5f). A near-miss, not a skip. The three that are skips are
  **WC-004**, **WC-006** and now **WC-008**.
- **NH-044 is closed by somebody else and the manuscript needed no edit for it.** Lap 16's
  reviewer filed it because `docs/related_work.md` rows 13 and 14 still asserted the negative
  this manuscript had just retracted, and CHARTER §12 forbids the paper routine editing that
  file. The 1528Z dev lap narrowed both rows to 「not stated in what was opened」 — the register
  §2 already uses — and registered the family as WC-008. **§2 is unchanged and now agrees with
  its own source page.**

### What was declined, and it is the fifth lap in a row

A sentence naming the two instances concretely — WC-007 and WC-008 found alive in the other
language on one day, one of them on the card the student reads aloud — was wanted and **not
written**. The mechanism is now stated (「one language at a time」) and the instances live in
`docs/withdrawn_claims.md` §5f–§5g-2; the illustration costs about 25 words and there were
**5** left after two mandatory corrections. **Laps 13, 14, 15, 16 and 17 have now all had their
writing shaped by the proxy rather than by the evidence, and this lap ends with the smallest
margin any of them has had. NH-037 is the answer and it is still open.**

## What lap 16 incorporated (2026-09-07): the manuscript was the file that escaped

No `[GAP]` opened or closed; the count stays at **7**. One mandatory correction, **+11
words**, paid for by three meaning-preserving compressions worth **−13**, so the document
went **8,994 → 8,992** and the margin against the 9,000-word proxy went **6 → 8**. Measured
again with the renderer this lap installed: **23 pages** under Carlito, page objects and
page-tree `/Count` agreeing, two pages under the author's 25-page rule (NH-028).

### The correction: §2 asserted the contents of a document nobody here has opened

§2's operational-systems paragraph read:

> Both answer where the fire goes, for a suppression commander or a siren operator;
> **neither answers** which household can still walk out and by which path — the object this
> paper produces.

The second clause is a **negative claim about two documents this repository has never
read**. What was actually opened of the NIFoS 산불확산예측시스템 is a catalogue entry
listing the guide's chapter names; the guide itself is an ~18 MB PDF that no lap has
retrieved, escalated as **NH-039**. What was opened of G-DAPS is one 경향신문 article of
2026-03-30. Neither can support "neither answers".

**The manuscript's own bibliography said so, and the prose disagreed with it.**
`references.bib` → `nifos2026guide`'s `note` reads, verbatim: 「⚠ Only the catalogue page was
opened; the guide itself is an ~18 MB PDF this sandbox did not retrieve … escalated to the
author as NH-039」. A reader who followed the citation would have found the paper's apparatus
contradicting the paper's sentence. That is the cheapest possible kill for a hostile reviewer
and it had been sitting there since the paragraph was written on lap 13.

**The repository had narrowed this exact claim in two places on the same day, and the
manuscript was not one of them.** Under **WFG-144** on 2026-09-07: `docs/dispatch_ordering.md`
§8 carries a dated correction block replacing 「**다른 어떤 체계도** 이 값을 계산하지 않습니다」
with 「`docs/related_work.md`가 조사한 어느 **연구**도 이 값을 내지 않습니다」, saying in its own
words that the old form had become 「아무도 열어 본 적 없는 매뉴얼에 무엇이 없다」는 주장; and
`docs/auto/JUDGE_QA.md` Q16a teaches the student the forbidden and the permitted form by
name — ❌ 「저쪽은 가구 단위로는 못 합니다」 against ⭕ 「**공개된 자료에서는** 가구 단위
산출물이 확인되지 않습니다」 — adding 「심사위원이 그 시스템을 직접 써 본 분일 수 있고, 그때
무너지는 것은 이 답변 하나가 아니라 신뢰 전부입니다」.

### ⚠ The subject grep, run properly this time, and it says the correction is INCOMPLETE

⚠⚠ **The first draft of this section claimed 「`docs/related_work.md` was corrected in the
same window」 and called the manuscript 「the file that escaped」. Both are wrong, this lap's
independent reviewer found them, and the corrected version is below.** What that draft ran
was `git grep -n "neither answers which household" -- paper/ docs/` — **a grep of the
sentence this lap had just written, over two of the four mandated paths.** That is the exact
thing `docs/auto/DIRECTION.md`'s ⚠⚠ rule, written by critic #35 one lap earlier, forbids:
「a lap that narrows a claim greps for the SUBJECT of the claim, never for the sentence it
just wrote … `git grep -n "<subject>" -- docs/ paper/ release/ web/` … and it names in
writing every file the grep returned and what it did about each.」 **This lap wrote that it
had followed the rule while doing the thing the rule bans**, which is worse than not knowing
the rule.

The subject grep — `git grep -n "which household can still walk out\|walking route for one
person\|가구 단위 산출물" -- docs/ paper/ release/ web/` — returns four live sites outside the
record class, and here is what was done about each:

| file | what it says | status |
|---|---|---|
| `docs/related_work.md:63` (row 13, NIFoS) | column header 「what it does **not** compute」, cell 「which household can still walk out, and along which path」 | ⚠ **STILL LIVE, UNNARROWED.** This is the manuscript's own §2 source page, and it asserts of an unopened user guide the flat negative §2 has just retracted. **Outside CHARTER §12's paths — a dev-lap item, escalated as NH-044.** The page's §1 preamble does carry a global 「*not found in the surveyed work*, never 최초」 qualifier, so the row is softer than the manuscript's sentence was; it is not soft enough, because rows 13–14 are not surveyed work — what was surveyed of them is a catalogue entry and a news article | <!-- forbidden-ok: wc008-household-walk-out-negative -->
| `docs/related_work.md:64` (row 14, G-DAPS) | same column, 「anything below the township; a walking route for one person」 | ⚠ **STILL LIVE, UNNARROWED.** Same row, same fix, same NH-044 |
| `docs/auto/finals/RELATED_WORK_PANEL.md:40` | 「앞의 두 시스템은 **재현 방법을 공개하지 않습니다**」 | ⚠ **STILL LIVE.** A different spelling of the same shape — a negative about unopened documents — already filed as **WFG-162, status `todo`**, on the file that gets **printed** for judges. Not this routine's to fix; named here because the rule requires naming | <!-- forbidden-ok: wc007-two-systems-do-not-publish-reproduction -->
| `docs/auto/JUDGE_QA.md:672` | ⭕ 「**공개된 자료에서는** 가구 단위 산출물이 확인되지 않습니다」 | ✅ **Already correct.** This is the form the manuscript now matches |

**So the honest statement is not 「the manuscript was the file that escaped」 but: the
narrowing reached two files, missed at least three, and this lap fixed the one inside its own
paths and could only file the rest.** Critic #35 found **two** escapees, not one — WFG-162
(`RELATED_WORK_PANEL.md`) and WFG-163 (`PYROGEOGRAPHY.md`), and its own root objection says
so: 「Two independent narrowings, two escapees」. It did cite `paper/manuscript.md:114` by line
number, for the *G-DAPS trial-operation* narrowing which the manuscript had already absorbed
correctly; what it did not check was this file for **this** claim.

The section now reads:

> Both answer where the fire goes, for a suppression commander or a siren operator. **What
> was opened of either — a catalogue entry, press reports — describes no output of this
> paper's kind**: which household can still walk out, and by which path.

The negative is now about the record rather than about the systems, which is what the
evidence supports. Nothing is conceded about what those systems do, and no accuracy
comparison is made in either direction — the sentence after it already forbids that.

### What paid for it, and why none of it is a caveat trade

CHARTER §12 forbids trading a caveat or a registered number for length. None was traded:
every `[GAP]` marker, every lineage warning, every registered value and every 32.6 % coverage
qualifier is byte-identical to lap 15. The three compressions are pure syntax:

| where | before | after | words |
|---|---|---|---|
| §5 | 「recovered by refusing where the fire is now**, with no model at all**」 | 「… where the fire is now」 | **−5** |
| §4.5 | 「**What the run does not support is any** statement about whether …」 | 「**The run supports no** statement about whether …」 | **−4** |
| §4.5 | 「Which **of them** is the fair opponent … and **it is** not one an analysis settles」 | 「Which is the fair opponent … and not one …」 | **−4** |

The §5 cut is the only one that removes a phrase rather than rearranging one, and it removes
the **third** copy of it. The two that survive are the **Abstract** (「needs no model at all」,
`manuscript.md:23`) and **§4.5** (「what a county office can run with no model at all」, `:467`),
and the §5 sentence cites §4.5 in its own clause. ⚠ The draft of this paragraph named §4.5 and
**§7** as the two carriers; §7 carries a *different* phrase (「a policy which refuses only where
the fire is now」, `:827`) and the unnamed second carrier is the Abstract. The count 「third」 was
right and one of its two witnesses was wrong — found by this lap's reviewer. No claim of this
project's is weakened either way; the phrase is a point in the project's own favour, not a
limitation.

### The escalation, stated at the size it is

**This is the fourth consecutive lap whose writing was shaped by the proxy rather than by the
evidence, and the first where the budget stood between the manuscript and a correction its own
bibliography demanded.** Lap 13 wrote two wrong sentences under compression pressure and its
reviewer caught both; lap 14 declined a true sentence it wanted; lap 15 spent 9 of its 15 words
on mandatory corrections it did not find itself. This lap's correction was **payable only
because three sentences happened to be compressible** — that is luck, not headroom. The stock
of meaning-preserving compressions is finite and is now visibly smaller. **NH-037** is the
answer, it is unchanged, and it is still open.

⚠ **And one line of that escalation does not survive the reviewer either.** The apparatus half
of this correction cost **zero** body words and was therefore never blocked by the budget at
all: `references.bib` → `nifos2026guide` was titled as the user guide, so the generated
reference list printed, as a consulted source, a document §2 now tells the reader nobody
opened. `check_paper.py:203` cannot catch that — it tests only that the `note` contains the
substring 「verified」, and that note opens 「verified 2026-09-06 … at this URL」 before saying
「Only the catalogue page was opened」. Fixed this lap, at no cost to the budget: the entry's
`howpublished` now reads 「Cited from the publisher's catalogue record; the guide itself was
not retrieved」, which is what the reference list prints. **The budget was the binding
constraint on the prose half and on nothing else, and the first draft of this ledger implied
otherwise.**

Still declined and unbought, unchanged from lap 15: 「registering the third found one no hand
sweep had named」 (10 words); `docs/related_work.md`'s Uiryeong shelter MIP
(10.3390/systems13121125) as a §2 entry (~30 words **and** not yet opened at its URL, so
CHARTER §12 forbids citing it either way until a lap opens it); §3.5's 「scanned by both
gates」, still an undercount.

### What was in the diff and produced nothing here

`e649f2d..6ee996b`, six files outside `paper/` and `docs/auto/`. `docs/related_work.md`
(WFG-144's 「in their favour」 → 「where they say they will be ahead」, and WFG-146's
사이언스타임즈 date 2026-02-12 → **2026-02-13**, the 연합뉴스 wire original being the 02-12);
`docs/dispatch_ordering.md` (the narrowing above); `docs/finals_screen_v2.md`,
`tests/test_finals_screen.py`, `web/finals.html` and `release/kcf-finals-2026/MANIFEST.json`
(WFG-119, a staleness gate that measures commits-behind rather than asking a shallow clone to
resolve a stamp). **No new artifact under `data/processed/`**, so no result section gained a
number or a figure, and the WFG-146 date is not a figure this manuscript ever cited — the 5 m
resolution it dates appears nowhere here, because it is an agency plan statement and §2 says
only that such statements exist. All nine figures re-rendered **byte-identically** from the
committed artifacts, so none was added, changed or needed looking at.

## What lap 15 incorporated (2026-09-07): its reviewer blocked it, and the block was right

No `[GAP]` opened or closed; the count stays at **7**. The code moved — WFG-026 shipped
`docs/related_work.md` and the booth differentiation panel, WFG-153 registered `WC-006`, and
the printables kit and the finals bundle were rebuilt. Three §3.5 edits, net **+9 words**,
8,985 → 8,994, leaving **6**. ⚠ **Two of the three are not what this lap first wrote. Its
independent reviewer returned `block` with six findings, four of them against numbers in this
very ledger, and the record below is the corrected version rather than the drafted one.**

### The one the reviewer's root objection forced, and it is the biggest of the three

§3.5 read 「every gated document is read against it, so a withdrawn claim cannot survive in a
file nobody thought to list.」 **That is false as written, and it is false right now.** The
registry's scope is `docs/auto/withdrawn_claims.json` → `scope.extensions` = `['.md','.html']`.
Re-derived here rather than taken on the reviewer's word: at `e649f2d`,
`scripts/check_withdrawn_claims.py` prints 「PASSED === 6 claims over 931 gated files」 while
`git grep` finds `WC-006`'s exact registered spellings alive in four **tracked** files —
`docs/auto/finals/printables/manifest_20260906T0620Z.json`, `_20260907T0032Z.json`,
`_20260907T0059Z.json` and `_20260907T0630Z.json`. They are frozen artifacts under CHARTER
§3.2, so they are permanent, and no amount of listing would have caught them: the extension is
out of scope. A claim **can** survive in a file nobody thought to list, if the file is not
prose.

The sentence now reads 「so a withdrawn claim cannot survive in a **prose** file nobody thought
to list; **a data file or a generator escapes it**.」 +9 words, and the completeness claim is
now scoped to what the instrument actually reads. ⚠ **Superseded 2026-09-07 (lap 17), kept
per CHARTER §3.7: that second sentence was wrong in its own voice.** The scoping was still
incomplete — a *prose* file in scope keeps a withdrawn claim whenever it keeps it in the
repository's other working language — and lap 17's section at the top of this file records
the evidence and the further narrowing. This paragraph is the record of what lap 15 did, not
a statement of what §3.5 says today. This also absorbs critic #32's WFG-155
finding against the manuscript — that §3.5's later 「the template, which the scan does read」 is
true of `scripts/finals.template.html` (an `.html` file, `gated: True`) and hides that
`scripts/build_printables.py`, where `WC-006` also lived, is `gated: False` — so the later
clause was left alone and the point is made once, earlier, and for both escape classes rather
than one. **This was the lap's most important edit and the lap did not find it; its reviewer
did.**

### The count went to three and came back to two, and the reviewer was right about that too

The draft read 「skipped it **three** times」 on the reasoning that `WC-006` was a third
unregistered withdrawal after `WC-004` and `WC-005`. The reviewer's objection: **`WC-005` was
registered inside its own lap and is therefore a compliance success, not a failure.** Checked:
the correcting commit is `590c29a` (00:43Z) and the registration `d0a739e` (01:08Z), both
inside lap `20260907T0018Z`; CHARTER §3.5c's unit is the lap, and that lap met it. What
`docs/withdrawn_claims.md` §5d records — 「등록되지 않은 철회가 두 번째로 일어났고, 이번엔 같은
랩 안에서 잡혔습니다」 — is a **near miss caught by its own reviewer**, not a §3.5c violation.
Two retractions reached the branch unregistered: `WC-004` and `WC-006`.

So the manuscript keeps 「twice」, and this is the entry to read if the number is ever
questioned: **the word did not change but both of its referents did, and the reason it was
right was wrong.** Lap 14 wrote 「twice」 meaning `WC-004` + `WC-005`, which over-counted by
one at the time; today 「twice」 means `WC-004` + `WC-006` and is correct. A number that is
right for the wrong reason survives exactly until someone checks it, which is what happened
here.

Consequently the verb triad went too. The draft widened 「edited or printed」 to 「edited,
printed or shipped」; with `WC-005` out of the tally, 「printed」 was carrying an instance the
sentence no longer counts. It is now 「edited or **shipped**」 — same length as the original —
and both remaining instances are covered: `WC-004`'s claim stayed live in `docs/auto/JUDGE_QA.md`
Q35, a file that lap had **edited**; `WC-006`'s stayed live in
`release/kcf-finals-2026/printables/manifest_20260907T0059Z.json`, **inside the folder a judge
is handed**, which the 0355Z lap **shipped** there by changing the bundle plan
(`newest_printables()`, `86d1b2c`, which moved `release/kcf-finals-2026/MANIFEST.json` from 17
files to 19). ⚠ The triad still does not cover every surviving instance — `WC-006` also
survived in `docs/printables.md`, which that lap never touched — and the sentence does not
claim it does; it says such a file existed each time, which is true.

### Four numbers this ledger's own draft got wrong, corrected in place

The reviewer found these in the paragraphs about not letting unchecked claims stand. Kept
rather than quietly fixed, in lap 14's style.

1. 「**thirteen hours** after the second」. Wrong by about ten hours: `WC-005`'s lap is
   `20260907T0018Z` (`0c862cb`, 00:30Z) and `WC-006`'s is `20260907T0320Z` (`ff566bc`,
   03:19Z) — **about three hours**. Thirteen hours is the `WC-004`→`WC-005` interval
   (`828bbae` 2026-09-06T11:13Z → 00:30Z = 13 h 18 m), which lap 14 measured correctly and
   this lap copied forward one step. ⚠ `docs/withdrawn_claims.md` §5e carries the same
   「열세 시간 뒤에」 and is a dev-lap file; the error originates there and was inherited
   unchecked. **A dev-lap item.**
2. 「the first **observed** instance」 of the design claim. It is the **second**.
   `docs/withdrawn_claims.md` §5d records the identical observation three hours earlier for
   `WC-005`: the reviewer registered it provisionally, ran the scanner, and
   「PASSED, 4 claims」 became 「FAILED, 1 unlicensed mention」 naming
   `docs/auto/finals/BOOTH_SETUP.md:240` — 「손으로 훑은 랩이 놓친 파일을, 등록 한 줄이 한
   번에 찾아냈습니다」. This matters beyond bookkeeping and the draft's escalation rested on
   it; see the next section.
3. 「the 2026-09-07T0355Z lap (`86d1b2c`) declared it false」. **Inverted.** `86d1b2c` is the
   commit that *asserted* it (`+ … the 29 dispatch sheets are already committed PDFs that <!-- forbidden-ok: wc006-dispatch-committed-pdfs, wc006-29-dispatch-sheets -->
   print`). The declaration of falsity and every correction are in `15f3df2`, 37 seconds
   later in the same lap, **after that lap's own independent reviewer blocked it**. The lap
   attribution stands; the commit attribution did not.
4. 「corrected it in **three** places」. `15f3df2`'s own message says
   「Corrected in README_KO.md, docs/finals_bundle.md, KCF_READINESS.md R7 and R9, and
   R7_ITEMS」 — four files, five sites. The 「three」 comes from `WC-006`'s own registry entry
   in `docs/auto/withdrawn_claims.json`, which undercounts. **A dev-lap item.**

### What is still declined, and the escalation the reviewer made smaller

`WC-006`'s registration found a live instance in `docs/printables.md` that neither the
correcting lap's hand sweep nor critic #32's hand-written probe had named. That remains a
good instance of what §3.5 asserts, and 「registering the third found one no hand sweep had
named」 remains unaffordable — 10 words against the 6 left after three mandatory corrections.
It is recorded here and unbought, as at lap 14.

⚠ **But the draft called it 「new evidence」 and built an NH-037 escalation on that, and it
is not new — finding 2 above.** The honest, smaller statement: **two laps in a row have now
declined a true sentence**, which is real and is the argument; the sentence declined this time
is a *second* instance of a thing the tree already recorded, not a first. Deleting the
overstatement costs the escalation some of its force and that is the correct outcome.

What is new, and does not need the overstatement: **this lap arrived with a mandatory
correction it did not find, and its reviewer did.** The root objection above is a false
completeness claim that had been sitting in §3.5 across every lap since the paragraph was
written, in the sentence a hostile reviewer would attack first because the registry is this
paper's headline methodological contribution. That is the case for NH-037 restated without
inflation: at 6 words of margin, the next lap that must fix something on this scale has
nowhere to put it.

**Also unbought, unchanged from lap 14.** `docs/related_work.md` (WFG-026) shipped this lap
with a 16-entry survey, and its Kwon, Kim & Han entry — an Uiryeong shelter-siting
mixed-integer program for a Korean rural county, `10.3390/systems13121125` — is a §2 entry
this manuscript should carry. That page states plainly that the entry is **not** in
`paper/references.bib` with a `verified` note, so CHARTER §12 forbids citing it until a lap
opens it; and at roughly 30 words with its 「what it does not compute」 clause it does not fit
in 6 either way. Both halves have to move together and the word half is NH-037's.
§3.5's 「scanned by both gates」 is also still the undercount lap 14 recorded (a third gate,
`tests/test_future_aware_attribution.py`, reads this manuscript) and is still unbought.

**The measurement, taken rather than inherited:** 23 pages under Carlito at 8,994 words,
after the one `apt-get install libreoffice-writer fonts-crosextra-carlito fonts-nanum` that
`paper/README.md` records. All nine `FIGURES` re-rendered **byte-identically** from the
committed artifacts, so no figure was added, changed or looked at this lap; nothing in the
incorporated diff produced a new artifact under `data/processed/`, which is why no result
section gained one.

## ⛔ WFG-150(a) is not a paper-lap row, and this lap measured why (lap 14, 2026-09-07)

**Read this before any future paper lap tries to close WFG-150(a).** The row asks that the
Abstract's opening block and the Conclusion's — the two blocks
`tests/test_future_aware_attribution.py` sees carrying `42 of 458` with an *only*
attribution — gain the manuscript's **second** binding caveat: that the forecast-aware arm
plans on the hazard field it is scored against, so the 42 is an upper bound, what a
*noiseless* forecast would buy rather than what this project's model buys. §4.5 already
states it in the words every other surface quotes, so what the manuscript lacks is
**locality**, not the claim. The backlog row gives one reason it was not done — the word
budget, NH-037 — and that reason is real but it is **not the binding one**.

The binding one is a gate. `test_the_manuscript_claim_blocks_do_not_yet_name_it` is
`xfail(strict=True)` **by design**, so that the day the manuscript gains the clause the test
goes red and asks `paper/manuscript.md` to be promoted into `ORACLE_SURFACES` rather than
sitting there as a permanent excuse. That design is right. Its consequence for this routine
is that closing the row from inside `paper/` **ships a red suite**: measured this lap rather
than reasoned about — the clause was written into both blocks, `pytest
tests/test_future_aware_attribution.py` went from `17 passed, 2 xfailed` to
`1 failed, 17 passed, 1 xfailed` (`XPASS(strict)`), and the edit was reverted. The repair —
promoting the surface and deleting that test — is in `tests/`, which CHARTER §12 does not
let this routine touch.

So: **WFG-150(a) is a dev-lap row, or a paper lap coordinated with one in the same commit.**
A paper lap that closes it alone fails `gates.py --mode full` and parks under CHARTER §3
rule 9. Both halves have to move together, and the words have to exist first
(NH-037). At **8,985** words the two clauses do not fit in any case.

## What lap 14 incorporated (2026-09-07), and the one sentence it declined to buy

No `[GAP]` opened or closed; the count stays at **7**. The code moved — `README.md`'s TL;DR
gained both binding caveats (WFG-138, WFG-148), `WC-005` was registered, the booth kit was
rebuilt, and two gates were added, one of which reads this manuscript — but **nothing in the
manuscript had gone false.** Critic #31 checked lap 13's related-work paragraph on the two
Korean operational systems against CHARTER §3 rule 5b, on both `references.bib` entries, and
cleared it: agency, date and scope present, no accuracy comparison made in either direction.
So this lap made **one** change, and its net cost was **two words**.

**§3.5, the registration sentence, is now about two failures rather than one.** It read
「a September 2026 retraction skipped it, and the hand-applied correction left the same claim
standing further down a file it had already edited」 — WC-004, where a lap corrected the
claim on Q30's card and left it standing in Q35's block of the same file. On 2026-09-07 it
<!-- forbidden-ok: en evidence sheet does not exist -->
happened again: the dev lap that withdrew 「the A4 evidence sheet does not exist yet」 declared
it false in three places and registered it in none, and its independent reviewer found the
same claim alive in four places in `docs/auto/finals/BOOTH_SETUP.md` — the **first** of the
kit's five `SOURCES`, in the PDF that lap had just built — while
`docs/submission_reconciliation.md`, the sheet the claim said did not exist, was bound into
that same kit a few sources later (`WC-005`, `docs/withdrawn_claims.md` §5d). The sentence
now reads 「September 2026 retractions skipped
it twice, and each hand-applied correction left the same claim standing in a file that lap
had itself edited or printed」 — **edited** is WC-004, **printed** is WC-005. A recurrence
**about thirteen hours apart** (`828bbae`, 2026-09-06T11:13Z, against the 2026-09-07T0018Z
lap), the second inside the very lap that had copied the first one's lesson into
its own notes, is stronger evidence for §3.5's own thesis than a single anecdote: the
mechanical scan, not the hand sweep, is the load-bearing part.

**What it declined to buy, and this is the entry that matters if NH-037 is ever answered.**
§3.5 ends 「This manuscript is scanned by both gates like any other document here.」 That is
now an undercount: since `786318c` it is scanned by a **third**,
`tests/test_future_aware_attribution.py`, which names `paper/manuscript.md` in its `SURFACES`
and refuses any block of it that states the headline contrast without naming the fire-blind
control in the *same* block. The gate is also the first in this repository whose own
**false-negative rate is re-derived on every run** rather than quoted from a report: it is
scored against fourteen sentences a reviewer wrote without having seen its patterns, in both
directions, and the class it cannot reach — a reworded overclaim carrying no keyed spelling —
is kept as a `strict` xfail instead of being regexed away. That is a better instance of §3.5's
own point than anything in the paragraph, and it belongs there. The shortest honest form
costs **+12 words** and this lap has **15**; spending them would leave the next mandatory
correction with three, which is the state NH-037 says forces a park. **Not bought. Buy it
when the budget moves.**

**The measurement, taken rather than inherited:** 23 pages under Carlito at 8,985 words,
after the one `apt-get install libreoffice-writer fonts-crosextra-carlito fonts-nanum` that
`paper/README.md` records. All nine `FIGURES` re-rendered **byte-identically** from the
committed artifacts with those fonts newly present in the sandbox — neither Carlito nor
Nanum is in `style.py`'s fallback chain, which is why installing them moved no figure.

⚠ **The lap reviewer blocked this lap, and four of the numbers it knocked down were in the
two paragraphs above — the paragraphs about not letting unchecked claims stand.** They are
corrected in place rather than quietly; this is the record.

1. 「pages 1–5 … pages 21–23」 of the printed kit. **Not derivable, and I had restated it
   from the registry instead of checking it.** `manifest_20260907T0032Z.json` — the pre-fix
   build that actually carried the false claim — records `pages: 33` while its own
   `pages_per_source` sums to **38** (6+7+18+4+3), so that build's manifest does not
   determine any page range. The corrected `20260907T0059Z` build is internally consistent
   (5+6+17+3+2 = 33 = `pages`) but is the build that *fixed* the defect, so describing the
   defect with its pagination is the wrong document. The two registry files disagree with
   each other besides: `docs/auto/withdrawn_claims.json` WC-005 says 「on page 2」 and
   `docs/withdrawn_claims.md` §5d says 1~5. **No page number is load-bearing for the point,
   so the text above now states source order and no pagination.** The stale
   `pages`/`pages_per_source` split in the `0032Z` manifest is a dev-lap item.
2. 「went from `18 passed`」. The baseline is **`17 passed, 2 xfailed`** over 19 tests; the
   second xfail (`test_a_reworded_overclaim_still_escapes`) was dropped from both halves of
   the claim. Re-run and corrected above. The finding it supports survives unchanged, but a
   measurement quoted as 「measured rather than reasoned about」 has to reproduce.
3. 「three days apart」. `828bbae` is 2026-09-06T11:13Z and the WC-005 lap is
   2026-09-07T0018Z: **about thirteen hours**, inside one sprint day. Corrected above.

⚠ **Two more the reviewer found that this routine may not fix, both for a dev lap.**
(i) `docs/auto/withdrawn_claims.json` WC-004 still says the withdrawal 「had reached three
loop pages and not the card the student reads aloud」; `docs/withdrawn_claims.md` §5a
explicitly refutes that with `git show --stat 828bbae` (+19 lines to `docs/auto/JUDGE_QA.md`).
The **machine-read** surface is the stale one, which is the same class of defect §5a exists
to record. The manuscript's new sentence follows §5a and is therefore right.
(ii) `tests/test_future_aware_attribution.py`'s xfail reason still reads 「17 words of
headroom」; this lap moved that to **15**. It is the message a future lap reads when deciding
whether it can afford WFG-150(a), and it should be corrected in the same commit that closes
that row.

## What lap 12 incorporated (2026-09-06), and the one thing it could not

No `[GAP]` opened or closed this lap; the count stays at 7. What moved is a sentence in
§3.5 that had gone **false**, and it is recorded here because the manuscript's own rule —
a limitation that no longer holds is a fabricated limitation (CHARTER §3.5) — cuts in this
direction as well as the usual one.

§3.5 ended: 「The injected line itself stays outside that test, and a wrong value inside it
still passes every gate named here; that hole is open and recorded rather than repaired.」
**WFG-113 repaired it at `1ec1d06`, inside this lap's window.**
`tests/test_finals_payload_rederives.py` re-runs `scripts/build_finals.py` into a temporary
path and compares the payload it emits, structurally, against the payload embedded in the
shipped `web/finals.html` — exempting three build-history fields only (`built_utc`, the
`git` stamp, the integrity block's `seconds`), and checking the integrity block against the
**builder's own `GATES` constant** rather than against a list the test's author typed.
`docs/finals_screen_v2.md` §4.3 is the method and its four graded mutations. §3.5 now says
so, and adds the sentence that is the transferable half: checking a generated artifact
against a string its checker chose verifies the checker, not the artifact.

⚠ **The first draft of that repair overclaimed in three places and the lap reviewer blocked
it. Read this before writing the next such paragraph, because the paragraph is *about* this
failure mode and committed it anyway** — every gate in the repository was green while the
sentence was false, which is §3.5's own thesis pointed at its author.

1. 「exempting only stamps of the build itself」 was **false against the code**.
   `_differences()` skips the whole top-level `integrity` object
   (`tests/test_finals_payload_rederives.py:117`), not just its `seconds`; the
   `PROVENANCE_GATE` branch one line below cannot execute for it, because the comparator
   never recurses in. The integrity panel is covered by a *separate* test against the
   builder's `GATES` constant, which checks the gate names, `ok is True` and a non-empty
   `line` — so a fabricated non-empty gate line still passes. §3.5 now says 「exempting the
   build's own stamps and the integrity panel, which a companion test checks against the
   builder's list of gates」.
2. 「It caught a live defect at once」 **did not happen**. Critic #25 found the stale screen
   by hand; the WFG-113 lap ran the two-command repair first, as its `fix-before-next-row`
   item, and wrote the gate after — the same commit `1ec1d06` carries both the rebuilt
   `web/finals.html` and the new test, and that lap's own reviewer wrote that it was
   「green at HEAD by construction … its entire value is prospective」. The gate was shown to
   catch the defect only by replaying the pre-repair payload. §3.5 now says exactly that,
   and says the value is prospective.
3. **The caveat was dropped.** `docs/finals_screen_v2.md` §4.3 discloses four limits and the
   draft carried none; the load-bearing one is 「빌더가 틀리면 같이 틀립니다」 — the oracle is
   the builder. Worse, the sentence the draft deleted is **still true** of one field in the
   very same payload: `registry.built_at_commit` comes from `docs/NUMBERS.json`'s own
   `built_at_git_commit`, `make finals` does not touch it, so a rebuild reproduces it
   unchanged and the new gate passes it by construction (§4.3 says so outright; it is
   **WFG-115**, open). §3.5 now carries both halves.

**What paid for those words, and it is the trade CHARTER §12 dictates.** The draft's closing
sentence — the WFG-117 rule below, stated in the manuscript — **was cut**, because a caveat
outranks a new rule when only one fits. The rule is kept here instead:

- **Recorded, not shipped.** WFG-117 (`docs/judge_qa_gates.md`): a registry count in a T0
  rehearsal card was corrected by three consecutive critic laps in two days, so the fourth
  repair removed the count rather than correcting it again, and gated the qualitative claim
  (「대부분」) that survives a moving registry, re-derived in-process from
  `docs/NUMBERS.json`. The rule: where a quantity moves faster than the documents quoting
  it, the gate holds the claim that survives the movement and the count is read off the
  artifact when it is wanted. A later lap with words to spare should put it in §3.5. ⚠ The
  manuscript quotes **no** registry count anywhere, and after this lap that is a stated
  position rather than an accident — the entry count changed 44 times across 45 distinct
  values between 2026-08-01 and 2026-09-05 (a measurement of this repository's git history,
  made by that dev lap, not a registry value; it is not written into the manuscript for
  exactly the reason it documents). **This lap then broke that rule one file away and its
  reviewer caught it** — see the digest note below.
- **Out, and it is a live defect a dev lap owns.** `docs/printables.md` claimed the booth
  print kit's staleness 「can be checked mechanically」 because `manifest_20260906T0620Z.json`
  records the sha256 of its four sources. Nothing compares those digests to the tree:
  `tests/test_printables.py` checks the manifest against itself. The dev lap of
  2026-09-06T1230Z found the live case — it edited `docs/auto/JUDGE_QA.md` (WFG-117), so the
  file no longer hashes to the `2c845121…` the manifest records, **and every printables test
  stayed green**, so the committed booth PDF is older than the card it was built from. ⚠ The
  first version of this row printed the file's then-current digest beside the manifest's, and
  this lap's reviewer found that it had **already gone stale inside this same lap** — critic
  #27's WFG-133 edit moved the file again before this lap committed. The mismatch is what is
  load-bearing and it survives; the moving digest is exactly the kind of value the WFG-117
  rule above says not to copy into prose, so it is not restated here and `sha256sum` is.
  Filed as **WFG-130** (rebuild at a new stamp, plus the gate that re-hashes
  every `SOURCES` path). It is the same shape as the hole §3.5 just recorded as closed —
  「can be checked」 is not 「is checked」 — but it is outside CHARTER §12's paths and it is
  not a claim this manuscript makes, so the manuscript says nothing about it and this row
  carries it instead.

**No figure was added or redrawn.** All nine `FIGURES` entries re-rendered byte-identically
from the committed artifacts in this sandbox, and no result section gained a result needing
a new one — the new material is methodological and sits in §3, which carries no figure of
its own. F9 stays drawn and unreferenced for the reason G8 gives.

**The measurement, taken rather than inherited:** 23 pages under Carlito at 8,969 words,
after the one `apt-get install libreoffice-writer fonts-crosextra-carlito fonts-nanum` that
`paper/README.md` records. The 144 words this lap added cost no page.

## ⚠ The word proxy now binds about a thousand words before the author's page rule (lap 12, NH-037)

Not a `[GAP]`, and not the lap-6 length crisis returning — the shape is the opposite. The
author's rule is **25 pages** and the document measures **23**. The proxy standing in for
that rule is **9,000 body words** and the document is at **8,969**: two pages of margin
against 31 words of margin. `paper/README.md`'s own sampled curve is why they disagree — at
9,000 words the document is 23 pages by either route, so the proxy stops a lap roughly a
thousand words early.

That was the right direction to err in while nothing could render. It is now the constraint
that would make the next mandatory correction unshippable, and CHARTER §12 forbids the way
out: a lap does not trim a caveat to buy space. **This lap was squeezed by the proxy twice,
and the second time it cost content.** First it tightened its own new prose by 27 words
(8,972 → 8,945), which cost only adjectives. Then its reviewer required three repairs, one
of them a caveat that had been dropped — and the words for that caveat came from **deleting
the WFG-117 rule out of the manuscript** (recorded above instead). No caveat was traded, and
that ordering is not negotiable; but the paper is now losing real content to a limit that is
not the author's rule, at **31** words of margin against **two pages**.

Escalated as **NH-037** with three options (raise the proxy to a measured number, land
WFG-116's open half so a clean clone measures and the proxy stops being load-bearing, or
leave it and let laps trim). Until the author answers, the loop keeps the proxy: it is
the author's own number and a lap does not raise its own ceiling.

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
