# The paper — how it is written and built

Target: one English manuscript, publication-ready in tone and figures, written
alongside the code by the `wfg-autoloop-paper` routine (docs/auto/CHARTER.md §12)
and rebuilt every time the code moves. Author: **Siyeong Park (박시영)**.

**Length: the ceiling is 25 pages.** The author decided it on 2026-09-05
(NH-028, verbatim: 「Don't worry about the word count for now. Just make sure it
doesn't exceed. 25 pages for. now」). `check_paper.py` now checks that directly —
it renders the document and counts — and keeps the 9,000-word budget as the
proxy for machines that cannot render, or that can render but not in a font
whose metrics are Calibri's. As of 2026-09-07 (lap 17) the built document is
**23 pages under Carlito**, measured rather than estimated: 21 at lap 9, 22 at
lap 10, and 23 at every lap from 11 to 16. **Two**
pages of margin remain against the author's 25. Lap 17 **re-measured** rather
than inheriting — 8,995 words still render 23 under Carlito, page objects and
page-tree `/Count` agreeing — after its own edits moved `body_words` and
therefore `built_pages_inputs`, which turned the anchor red exactly as designed
until a run had actually produced a new count.

⚠ **The two margins have come apart, and the proxy is now the tighter one by about a
thousand words.** At lap 16 the document is 23 pages against a 25-page rule and 8,992
body words against a 9,000-word proxy: two pages of margin, **8** words of margin —
the first lap since lap 11 to end with more headroom than it started with (6 at lap 15,
15 at lap 14, 17 at lap 13, 31 at lap 12), and it bought that by compressing, not by
writing less. The
curve below is why — at 9,000 words the document is 23 pages by either route — so the
proxy stops a lap roughly a thousand words before the rule the author actually set.
Lap 12 was squeezed by it twice: once tightening its own new prose by 27 words, which
cost only adjectives, and once paying for a caveat its reviewer required by **deleting a
rule from §3.5** (kept in `GAPS.md`). Lap 13 was squeezed harder still, and this is the
paragraph to read before deciding NH-037. The related-work paragraph its own research
routine's finding required — Korea already runs two wildfire *spread* systems and the
manuscript named neither — cost about 100 words against 31 of headroom, so it was paid for
by six compressions across §3.5, §4.5, §5, §6, §7 and the availability section. **Twice the
budget, not the evidence, chose the wording, and the lap's independent reviewer blocked the
push for it:** the draft wrote that Gyeonggi's model 「entered trial operation」 where its own
cited source says only that trial operation was *announced* for the following month, and the
§3.5 compression deleted the payload test's scope exemption while keeping 「field by field」,
claiming more coverage than the test has. Both were repaired before the push and the repairs
were paid for by a further round of compression. No caveat and no registered number was
traded in either lap — CHARTER §12 forbids that, and the reviewer checked it token by token
— but the compressible prose is close to exhausted and the failure mode is no longer
hypothetical: **a lap under this budget will write a wrong sentence before it writes a long
one.** 〔as written at lap 13; the margin at lap 15 is **6** words〕 Escalated to the
author as **NH-037**, which is now urgent rather than theoretical. Until it is answered
the proxy stands: it is the author's own number and a lap does not raise its own ceiling.

⚠ **Lap 14 is what this constraint now looks like when nothing is broken, and it is the
cleanest evidence NH-037 has.** The code moved and no sentence in the manuscript had gone
false, so the lap had no mandatory correction to fund. It made one net-**+2**-word change to
§3.5 (a registration failure that had happened once has now happened twice; `GAPS.md`) and
then **declined a second, better sentence it wanted** — that §3.5's 「scanned by both gates」
is now three gates, the third being the one that reads this manuscript's own headline block
and whose false-negative rate is re-derived on every run. The shortest honest form of it
costs 12 words against 15 of headroom, and spending them would leave the next mandatory
correction with three. So the budget is no longer only shaping *how* a lap writes a required
sentence; it is now deciding **whether** an optional true one is written at all. That is a
milder failure than lap 13's — nothing wrong was shipped — but it is the same mechanism one
step earlier, and it will not stay mild.

⚠ **Lap 15 is the next step, and it is the one where the budget met a correction that had to
be made whatever it cost — 9 of its 15 words, found by its reviewer and not by the lap.**
§3.5 had been asserting, since the paragraph was written, that 「every gated document is read
against it, so a withdrawn claim cannot survive in a file nobody thought to list」. **That is
false, and it is false right now**: the registry's scope is `.md` and `.html` only, and
`WC-006`'s registered spellings are alive today in four **tracked** `.json` manifests under
`docs/auto/finals/printables/`, frozen under CHARTER §3.2 and therefore permanent, while
`check_withdrawn_claims.py` prints 「PASSED === 6 claims over 931 gated files」. No listing
would have caught them. It now reads 「cannot survive in a **prose** file nobody thought to
list; **a data file or a generator escapes it**」, which also absorbs critic #32's WFG-155
finding against this manuscript. **The sentence a hostile reviewer attacks first is the one
about the instrument, and this one had been wrong since the paragraph was written.**

The same block corrected the lap's own arithmetic in the other direction: the draft had taken
the count of unregistered withdrawals from two to three, and `WC-005` turned out to be a
compliance success (registered inside its own lap, CHARTER §3.5c) rather than a failure. So
the manuscript keeps 「twice」 — **the word did not move but both of its referents did**, from
`WC-004` + `WC-005` to `WC-004` + `WC-006` — and 「edited or printed」 became 「edited or
shipped」 at no cost, `printed` having belonged to the instance that left the tally. `GAPS.md`
carries the full record, including four numbers this file's and that ledger's drafts got
wrong.

What the lap still could **not** buy: that registering `WC-006` found a live instance in a
file no hand sweep had named — 10 words against the **6** left after the corrections — nor
the §2 entry `docs/related_work.md` supplies. **Two laps in a row have now declined a true
sentence.** ⚠ The draft called this lap's declined sentence 「new evidence」 for NH-037 and it
is not: §5d records the same observation for `WC-005` three hours earlier, so the escalation
is smaller than drafted and is stated smaller. What stands without inflation is the shape of
this lap: **the mandatory work alone took nine of fifteen words, and the next lap that must
fix something on this scale has six.** NH-037 is the answer and it is still open.

⚠ **Lap 16 is the one where the budget stood between the manuscript and a correction the
manuscript's own bibliography demanded — and it was payable only by luck.** §2 had been
asserting that of the two Korean operational systems 「**neither answers** which household can
still walk out and by which path」. That is a negative claim about two documents nobody here
has opened: what was read of the NIFoS guide is a catalogue entry listing chapter names (the
guide is an ~18 MB PDF, **NH-039**), and of G-DAPS a single newspaper article.
`references.bib`'s own note for `nifos2026guide` says so verbatim — 「Only the catalogue page
was opened」 — so **the paper's apparatus had been contradicting the paper's prose since the
paragraph was written at lap 13**, one citation click away from any reviewer. The fix costs
**+11** words and was paid by three meaning-preserving compressions worth **−13** (`GAPS.md`
lists all three; none is a caveat or a number). The document went 8,994 → 8,992 and the margin
**6 → 8**. ⚠ **Do not read that as headroom.** The correction was payable because three
sentences happened to be compressible, and that stock is finite and is now visibly smaller.
Four laps in a row have now had their writing shaped by the proxy rather than by the evidence.
**NH-037 is the answer and it is still open.**

⚠⚠ **And the lap's account of the repository around that sentence was wrong in three ways,
all found by its independent reviewer, all corrected before the push. Read `GAPS.md`'s lap-16
section before this paragraph.** The first draft here said the identical claim had been
narrowed in `dispatch_ordering.md`, `JUDGE_QA.md` Q16a **and `related_work.md`**, and that the
manuscript was 「the file that escaped」. **`docs/related_work.md` was never corrected for this
claim** — its 2026-09-07 diff is the WFG-146 date and WFG-144's 「in their favour」, neither of
which touches it — and its table **rows 13 and 14 assert the retracted negative today**, under
the column header 「what it does **not** compute」, on the manuscript's own §2 source page.
`docs/auto/finals/RELATED_WORK_PANEL.md:40` carries the same shape in the file that gets
**printed** (WFG-162, `todo`). So the narrowing reached two files and missed at least three,
and this lap fixed the one inside CHARTER §12's paths and filed the rest as **NH-044**.

**The mechanism of that error is the one this whole section is about, one level up.** The
draft discharged DIRECTION.md's ⚠⚠ rule — 「grep for the SUBJECT of the claim, never for the
sentence you just wrote; `git grep -n "<subject>" -- docs/ paper/ release/ web/`; name every
file it returned and what you did about each」 — by running `git grep -n "neither answers which
household" -- paper/ docs/`. **That is a grep of the sentence it had just written, over half
the mandated paths, printed in the ledger as evidence the rule had been followed.** The rule
was one lap old and was written by the critic whose finding this lap was extending. `GAPS.md`
now carries the real grep and a four-row table of what was done about each hit.

⚠⚠ **Lap 17 is the one where the lap's own repair was a category error, and its independent
reviewer killed it before the push. Read `GAPS.md`'s lap-17 section before this paragraph.**
The defect was real: §3.5's 「cannot survive in a **prose** file nobody thought to list」 — lap
15's own narrowing, quoted three paragraphs above — is falsified by the incorporated diff.
`docs/withdrawn_claims.md` §5g-2 records **WC-008** registered with an **English** spelling and
the same claim living on in **Korean** inside `docs/auto/JUDGE_QA.md` Q16a, a gated prose file
and the card the student reads aloud to five judges. §5g records the mirror image ninety minutes
earlier — **WC-007** in Korean, its English twin alive in `KOREAN_OPERATIONAL_SYSTEMS.md` §3.3.

**The draft repaired it by appending the language case to the escape list, and that is the wrong
list.** The other two members escape by **scope** — never opened at all. The Korean copy escaped
by **spelling**, inside a file the scanner *did* open and pass. So the sentence would have read
*prose files are covered, except this prose file*; and it would have sold a **contingent**
registration gap, closed the same day by a Korean pattern, to an IEEE reviewer as a structural
property. The escape list is back to its lap-15 wording, and the language case now sits in the
sentence the repository's own §5g files it under: 「It matches spellings, not meaning, **and one
language at a time**」, closing 「and **both limits** are recorded rather than designed away」 —
the trailing clause the draft had deleted, and which the reviewer showed is payload, restored.

⚠⚠ **The second half of the block was a wrong number, and the instance it omitted was this
routine's own.** §3.5's 「September 2026 retractions skipped it **twice**」 is **three**. Paper
lap 16 (`8ff1b40`, 15:30Z) retracted the claim from §2 and, *in that same commit*, wrote the
retracted sentence verbatim and **unlicensed** into `paper/GAPS.md:77` and `:79`; a **different
routine** registered it 42 minutes later (`7cc4eb7`, 16:12Z) and had to license those two lines.
Both halves of the manuscript's own sentence fit it. The draft of the ledger asserted 「twice」 on
the false ground that WC-008 was registered in the lap that withdrew it — taken from the ledger's
summary instead of from the commits, which is the error this whole section is about.

8,992 → **8,995**; margin **8 → 5**, the tightest yet, paid down by four meaning-preserving
syntax compressions. **Laps 13, 14, 15, 16 and 17 have now all had their writing shaped by the
proxy rather than by the evidence. NH-037 is the answer and it is still open.**

✅ **Lap 18 is the first lap since 12 that could write the optional true sentence it wanted, and
the reason is worth reading before the next NH-037 decision: the work it most needed to do cost
nothing.** The incorporated diff made no manuscript sentence false. What it did do was register
**WC-009** — 「never a flat present-tense sentence about what a system does, in **either**
direction, when the only thing opened is a catalogue record or a newspaper」 — which is precisely
the charge lap 17's reviewer had **filed without fixing** against this paper's own bibliography:
fifteen of 29 references verified 「via the Crossref record」 while §2 characterised six of them
substantively. The paper was applying one provenance standard to the Korean operational systems
and a laxer one to the Western evacuation-routing literature.

This lap opened twelve abstracts in full (OpenAlex, Semantic Scholar and arXiv records) and quoted
them verbatim into their notes; **four could not be opened past a catalogue record** — `dozier1981`,
`cova2003`, `li2017`, `li2019` — and are marked `⚠ CATALOGUE RECORD ONLY`, with `nifos2026guide`
the fifth. **Three sentences were narrowed to what their titles support**, the sharpest being
`li2019`'s 「so it accounts for the time evacuation takes」, which was in nothing that was opened
*and* was partly foreclosed by `cova2005`'s own abstract taking 「estimated evacuation time」 as an
input. Two more were moved onto opened text, and two compressions were themselves corrections.

**The crucial mechanical fact: `build_docx.py`'s `fmt_ref` does not render the `note` field.** So
provenance for sixteen references cost **zero** words and zero pages. 8,995 → **8,994**; margin
**5 → 6**.

⚠⚠ **And the one sentence the lap ADDED broke the rule the lap spent its whole diff enforcing.
Read `GAPS.md`'s lap-18 section before this paragraph.** The draft wrote 「Each reference's note
says what was opened; five rest on catalogue records」 — **a flat universal over 29 notes, written
by a lap that had rewritten 17 of them, and false for four**: `firms` and `era5` carried the
entire note 「verified 2026-09-03」, nineteen characters naming nothing, and `worldcover` and `osm`
stated a fact about the source rather than what was read. Two greps falsify it. That is the
WC-005 / WC-009 shape precisely — *the sentence advertising the correction was the thing that was
now wrong.* Independently fatal: 「five」 was the diff's only new number and is **unregistered**,
one line below the manuscript's own 「Every measured number is registered in `docs/NUMBERS.json`」
(CHARTER §3.3; §12 forbids this routine from registering it). Both halves went. It now reads
「`references.bib` marks each work known only from a catalogue record」, and **the four thin notes
were fixed rather than only the sentence**.

⚠⚠ **The reviewer's sharpest finding was a hole the narrowing itself opened.** Dropping 「the
Korean local area」 from §2 left §4.8's 「a **two-minute cadence**」 with no stated source anywhere
in the paper — and the `kim2021gk2a` note asserted §3.1 supplied it when §3.1 named neither sector
nor cadence. **A bib note certifying a repair the manuscript does not contain: the WFG-171 circle
in reverse, inside the lap whose subject is precisely that.** §3.1 now carries the LA sector and
its cadence, sourced to this repository's own ingestion code rather than to the cited paper.

⚠ **Do not generalise the relief.** This lap had an unusually cheap fix available because most of
the defect lived in a file the length gate cannot see. The §3.5 illustration is still declined,
for the **sixth** lap running, and it now has its best instance yet (WC-009's registration found a
live copy in a file the reviewer had passed as clean). **Laps 13 through 18 have all had their
writing shaped by the proxy rather than by the evidence. NH-037 is the answer and it is still
open.**

⚠ **The subject grep caught a file this routine owns, and it is `GAPS.md`.** Lap 15's ledger
entry ended 「the completeness claim is now scoped to what the instrument actually reads」 — an
own-voice completeness assertion, in `paper/`, that is still incomplete. It is **annotated in
place as superseded, not deleted** (CHARTER §3.7), and `GAPS.md`'s lap-17 section carries the
full seven-row grep table. This paragraph is the pointer for the block above it, which quotes
lap 15's wording as a record and does not assert it.

⚠⚠ **Lap 19 changed no sentence in the manuscript, and measured the thing every block above it
has been arguing about: the proxy does not count 2,403 of the words the document renders.** Read
`GAPS.md`'s lap-19 section for the working; this is the summary. **`python paper/measure_render_gap.py`**
(new in that lap) re-derives it from the shipped `.docx`: **11,397** words render against the
**8,994** `build_docx.py` calls `body_words` — the counter is incremented in the paragraph branch
(`:187`) and the list-item branch (`:177`) and nowhere else, so figure captions (**789**), table
captions (**439**), table cells (**213**), headings (**119**), the generated References section
(**802** over 29 entries), the title page (**39**) and the rendered citation markers the counter
strips from the source (**2**) are all outside it. **The proxy sees 79 % of the words that
render** — words, not page area; this section's whole point is that the two are not the same.

⚠⚠ **The first version of that table was itself a word miscount, and the lap's independent
reviewer found it before the push.** It decomposed the Markdown *source* rather than the rendered
document, published 773 / 431 / 153 / 40, and those parts sum to **2,412** against the 2,403 they
decompose: heading lines had been counted with their `#` markers attached, and the builder's
rendered `Figure N. ` / `Table N. ` labels do not exist in the source. **The lap whose entire
product was 「a word counter mis-counts words」 shipped a word miscount in the same table, into
three files, and nothing here could have caught it** — no script re-derived any of the six
integers. `measure_render_gap.py` is that script and exits **1** when its parts do not reconcile
with its total. ⚠ It gates nothing: no push runs it, so a number copied out of it can still go
stale, the same standing weakness `measure_pages.py` has and a dev-lap item for the same reason.

⚠ **That makes it bypassable in one keystroke, over 1,441 words of caption and table prose —
16.0 % of `body_words` — and no lap may use it.** Move a sentence from a
paragraph into the figure caption above it and `check_paper.py` reports a shorter document. It is
the `built_pages_inputs` bypass again — the one lap 9's reviewer killed because the dishonest act
and the honest one were the same keystrokes — except that here nothing stands against it at all.
A caption carrying body argument to dodge a counter is a false measurement of the document, not a
short document. Lap 19 did not use it and did not compress anything either: with 6 words of
margin and **no mandatory correction to fund**, it was the cheapest lap in which to realise
compressible stock, and it refused because every compression is an edit to litigated prose for no
gain in truth and two of the three sentences laps 13 and 15 got wrong were compressions. The
margin is **6** and is reported as 6 — ⚠ **and never bare, because it is a margin against a proxy
that does not measure the rule it stands in for.** What is operative is the author's 25 pages, and
the document measured 23 at lap 18 with no input to that measurement moved since. The 6 is what
the gate enforces until NH-037 is answered, and that is all it is.

⚠ **One caption in this paper already carries argument that is nowhere else**, which is why the
paragraph above is a rule and not a worry. F5's caption ends 「Not re-acquiring the region is
deliberate: the walk box does not fit the simulation grid, so redrawing it would force
re-extending the canvas and re-simulating the field, replacing a stated limit with an unstated
one」 — a methodological justification §4.3's first caveat does not restate. **No claim is made
about how it got there:** `git log -S` names `e649f2d`, but this clone answers `true` to
`--is-shallow-repository` at a depth of **50** commits (measured 2026-09-08), so that commit shows
`manuscript.md` as a *new file* and the answer is the clone boundary, not the history. CHARTER §4
forbids the ancestry claim and none is made. Moving it into §4.3 costs about 30 words against 6.

⚠ **What this does to NH-037, in both directions.** It sharpens the question — the entry should
ask about a proxy that is tight on prose and blind on captions and tables, not about a proxy
「a thousand words early」, and the words-to-pages table below was calibrated at *this* caption
density and holds only there, `calibrate_pages.py` holding figures, tables and references fixed by
construction. The remedy that removes the class is not a bigger number but **WFG-116's one `apt`
line in `.github/workflows/auto-gates.yml`**, after which a clean clone measures the 25 pages the
author actually set. ⚠ And it **shrinks** the entry's case by one line, which is owed: the §3.5
illustration recorded as declined at laps 13–18 — that registration keeps finding live copies a
hand sweep missed, the want the blocks above quote at 10 and 20 words — **is retired as a want,
not deferred a seventh time.** This diff carries the other direction: `WC-010`'s `say_instead`
field was wrong from `ab4e71e` to `82ec346` (2 h 16 min on the commits' **author** dates; `82ec346`
was rebased and its committer date gives 3 h 03 min, and author date is the one that answers how
long the wrong wording sat in the tree the lap wrote it into), and the scan
that enforces `WC-010` over 933 files reads `.md` and `.html`, so it does not read the file
`WC-010` lives in — a hand grep of the subject found it and registration structurally could not.
Both directions hold; what dies is the **one-directional** form all six drafts had, which is the
register `WC-009` itself forbids. The blocks above are records and are not rewritten; this
paragraph is their annotation (CHARTER §3.7). **The rest of NH-037 stands: laps 13, 15 and 16 each
funded a mandatory correction by compression, and lap 13 shipped two wrong sentences doing it.**

⚠⚠ **Lap 20 is the one where this routine wrote a correction, its own reviewer proved it was
worse than the defect, and the lap reverted. Read `GAPS.md`'s lap-20 section before this
paragraph.** The defect is real and stands: `docs/auto/DIRECTION.md:59` requires every
judge-facing surface stating **42** or **91** to carry *both* binding caveats — fire-blind
opponent, and upper bound for a noiseless forecast — CHARTER §14b names the manuscript as such a
surface, and the manuscript carries the second only in §4.5, scoped there to the
present-perimeter comparison rather than to the 42. ⚠ **The repository had a sharper statement of
that than this file did, and the lap did not run it:**
`tests/test_future_aware_attribution.py` enumerates exactly two claim blocks in the manuscript —
the Abstract and §7 — and is `xfail(strict=True)` because neither names the oracle bound.

**Four things were wrong with the fix, all found by the reviewer, all verified in the tree before
the revert, none reachable by any gate here.** The lap asserted that `README.md:626` cites
`paper/manuscript.md` §4.5 for the caveat and wrote that line number into three files; **`:626`
carries no citation at all and the citing line is `README.md:38`**, the TL;DR bullet. The fix
then **deleted the very text `:38` cites** — `grep -niE 'noiseless|upper bound'` matched §4.5 at
`:512` before the diff and matched nothing in §4.5 after — which would have left the README
citing a section silent on the claim it quotes, **strictly worse than the mismatch being fixed**,
and CHARTER §12 bars this routine from repairing `README.md`. The Abstract clause **inverted the
bound**, reading 「bounds a noiseless forecast rather than this model」 where every other surface
has 42 as an upper bound *on this model* equal to what a noiseless forecast buys — the inverse of
the safety-relevant meaning, on the headline number, in the diff whose purpose was to make two
surfaces agree. And the §4.5 back-reference imported a fire-blind clause into a section whose
opponent is expressly not fire-blind, while the merged lead's second clause was left with **no
premise anywhere in §4.3**, that premise being the sentence deleted from §4.5.

⚠⚠ **The reason it was reverted rather than repaired is the whole of NH-037.** The correct
version needs the mechanism stated once with its premise, §4.5's original 43 words **kept** so
the README's citation survives, a corrected Abstract clause, and §7 — roughly **+50 words against
a margin of 6**. Every cheaper shape inverts the bound, strands the premise, or breaks the
citation. **Nothing was compressed and no caveat was trimmed to close it**, because CHARTER §12
forbids that and the only compressible prose left is the stock that produced wrong sentences at
laps 13 and 15. ⚠ And whoever does land it needs more than words: the strict xfail above means
`paper/manuscript.md` must be promoted into that test's `ORACLE_SURFACES` and its reason string
rewritten in the same change, or the suite turns red the moment the prose becomes correct —
`tests/` being outside CHARTER §12, that half is a dev-lap job.

✅ **What the lap did land: the page count, re-derived rather than inherited.** It ran the one
`apt` line this file has printed since lap 9, so `check_paper.py` took its measuring branch —
`pages 23, calibri_face Carlito, metrics_ok true` — and **re-derived the anchor
`f2ee9be6c9c7c4e0` and found it matching** rather than accepting it. ⚠ It does **not** close
WFG-116; that is the same line in `.github/workflows/auto-gates.yml`, outside `paper/`, still
open. **Both margins now stand measured on one document by one run: two pages against the
author's 25, six words against the proxy's 9,000.** When NH-037 was written they were two pages
and **55** words. The word margin has fallen to 6 and the page count has not moved once, and
**the case that entry was written for has now arrived** — a correction the repository's own
DIRECTION rule and its own strict tripwire both require does not fit, and the rule it does not
fit is the proxy rather than the author's.

⚠⚠ **Lap 21 is the one where the count went false in the direction nothing here watches: a new
surface was born carrying the retired shape. Read `GAPS.md`'s lap-21 section before this
paragraph.** §4.5 had ended 「**One** repository document still draws the stronger conclusion from
those same five points … a **second** was narrowed to this reading during revision」. The
incorporated diff (`d6d801d`) added a Round-4 bullet at **`README.md:232`** — 「그 sweep 안에서
**고원이 아니라 뾰족한 봉우리**입니다」, the 1 km buffer is a sharp peak and not a plateau — which <!-- forbidden-ok: wc011-buffer-width-is-a-spike-ko --> <!-- These lines RECORD the withdrawn shape claim in order to say it was withdrawn; WC-011 registered it on 2026-09-08 and this file is not record class, so the quotation is licensed per line rather than by exemption (CHARTER §3.5c). -->
is precisely the shape §4.5 says five widths a factor of two apart cannot resolve. So it is
**two** now, and §4.5 says two. Net **−1** word; 8,994 → **8,993**, margin **6 → 7**.

**The three surfaces that state the resolution limit all still state it — none regressed.**
`fair_opponent_line.md` (whose own note is dated 「Narrowed 2026-09-06」), `DEMO_SCRIPT_5MIN.md:151`
and `JUDGE_QA.md` Q37 each carry their own record of that narrowing. What happened is not a survival
a sweep missed: **the sentence was written afterwards, into a file that had never carried it, and
that file is the project's front door.** ⚠ No ancestry claim is made and none can be: this clone
answers `true` to `--is-shallow-repository` at a depth of **50**, oldest resolvable commit
`ab4e71e` (2026-09-08), and `git log -S` on both Korean narrowings returns that boundary commit,
which is the clone edge and not an answer. The ordering above rests on the documents' own dated
records and on `d6d801d` being inside the incorporated range.

⚠ The shape claim is in **no** entry of `docs/auto/withdrawn_claims.json` — checked key by key this
lap, none of `spike`, `plateau`, 고원, 봉우리, 뾰족 or 평평 occurs anywhere in that file — so the
scan never reads for it, and the only guard that exists, `tests/test_fair_opponent_line.py`, bans
the retired spellings **in one file, by name, and in English**. `README.md:232` is Korean.

⚠⚠ **And the first draft of this block was wrong in three ways, all found by the independent
reviewer, all verified in the tree before the push. Read `GAPS.md`'s lap-21 section before this
paragraph.** It called that mechanism 「new」 and 「a third failure mode beside §3.5's two」: it is
neither. Critic #44 filed it at 2026-09-08T1700Z (`dc8fa9f`, **inside the diff this lap
incorporated**) as 「A FOURTH SURFACE」 in WFG-127's own row — the row this block cites by name —
with a sharper root than the draft had, namely that the guard reads English while the claim was
written in Korean. **That is §3.5's own 「It matches spellings, not meaning, and one language at a
time」**, firing on a guard rather than the registry and on a newly written claim rather than a
surviving one (DIRECTION's rule; WFG-168, not yet filed). So the manuscript is owed nothing here and
nothing was written into it. The draft also said WFG-127 is 「position 1 of the backlog table」:
measured at `eff2183` it is table row **12** and the **second** `todo` row, WFG-199 having been put
at the head of that block by critic #45 in that same commit — true at `9c24a8b`, falsified by the
last commit of the range being incorporated. And it said 「933 gated files」 three times; the script
prints **935** (`scripts/check_withdrawn_claims.py`, run this lap). ⚠⚠ **Two of those three are the
wrong-count class this whole lap exists to fix, committed by the lap in the act of reporting it, in
a block whose own headline is that a hand-typed count went stale.** The **933** in the lap-19 block
above and in the two `GAPS.md` passages of laps 18 and 19 is left standing as those laps' record
(CHARTER §3.7), and no line number is given for any of them, because this lap's own insertions moved
them all.

⛔ **And the budget declined a LIMITATION this lap, not an illustration. That is new, and it is
what NH-037 was waiting to become.** The paper nowhere says that its hazard field cannot be
current. `docs/live_pipeline.md` §0 makes it the project's own lead line — detection is
near-real-time (FIRMS NRT), the weather is not, ERA5 publishing on a ~5-day lag — `live/scope.py`
owns the strings, `tests/test_live_pipeline.py` fails if either is missing from **any** screen,
sheet, broadcast script, SMS draft or JSON record, and this lap's own incorporated diff added
`tests/test_adoption_card.py`, binding a judge card that opens on the same asymmetry.
`references.bib`'s `era5` note already carries 「about five days' latency」, verified at the
Copernicus page. The manuscript's only neighbouring line is §6's 「No trigger has ever fired on a
**live** detection」, which says the system has not been run live and **not** that its weather
source makes a current field impossible — a structural limit no deployment effort removes.

The sentence — 「The hazard field cannot be current: ERA5 publishes on a ~5-day lag.」 — was
**inserted and measured, not estimated**: `body_words` **8,993 → 9,005**, i.e. **12 words against a
margin of 7**, five over the proxy's hard fail. It was reverted and the document rebuilt at 8,993.
**Nothing was compressed to fund it** — CHARTER §12 forbids buying space with a caveat, and the
only compressible prose left is the stock that produced wrong sentences at laps 13 and 15. ⚠ The
honest other half, owed by the same rule that makes this worth escalating: **the manuscript is not
false without the sentence.** It claims no real-time operation anywhere. What is missing is the
*reason*, and a reviewer who asks for it is asking a fair question the paper cannot answer today.
⚠ And this lap **re-measured** rather than inheriting: `body_words` moved, which moves
`built_pages_inputs`, so lap 20's anchor turned the gate red exactly as designed until a run had
produced a new count. After the one `apt` line this file has printed since lap 9,
`check_paper.py` took its measuring branch — `pages 23, calibri_face Carlito, metrics_ok true` —
and the new anchor `84b91dde83d63607` is the one that run printed. **Both margins stand measured
on one document by one run: two pages against the author's 25, seven words against the proxy's
9,000.** Twelve words move no page. **The rule that stopped a limitation is
the proxy, not the author's. Laps 13 through 21 have now all had their writing shaped by it, and
this is the first one where what it shaped away was a limitation. NH-037 is the answer and it is
still open.**

✅ **Lap 22 is the second lap in ten where the budget shaped nothing, and the reason is the
same as lap 18's: the work it had to do paid for itself.** Two sentences of §4.5 had gone
false — 「the grid holds a single point in the region such a claim would be about」 and
「**Two** repository documents still draw the stronger conclusion」 — because the incorporated
diff **measured the three widths that grid was missing** and corrected both surfaces in the
same commit. Removing 80 false words bought 84 true ones plus one (「Two **further** caveats」),
so the whole of WFG-202's post-hoc-maximum qualifier landed for a **measured net +5**:
8,993 → **8,998**, margin **7 → 2**. Nothing was compressed and no caveat or number was traded.

⚠ **Read the direction of that, not the relief.** The margin is the smallest it has ever
been, and it was funded by an unrepeatable source: a sentence that went false. The compressible
stock is untouched and still exhausted, and **laps 13 through 21 all had their writing shaped
by the proxy** — lap 21's casualty being a *limitation*. This lap's own declined clause is
costed at **8 words against 2** in `GAPS.md`. **NH-037 is the answer and it is still open.**

⚠⚠ **And the lap's independent reviewer BLOCKED it, on a count this file's first draft had
not re-measured. Read `GAPS.md`'s lap-22 section before the paragraph below.** The lap ran
`unqualified_post_hoc_claims`, fixed the one real hit it found, then **wrote the entire lap-22
ledger without re-running it** — and the ledger's own new prose stated the shape of the top
bare, a fresh unqualified argmax claim, with the qualifier one
heading away in the next unit. That is `WC-004`'s shape, in the section explaining why the
gate cannot be satisfied, in the lap whose subject is a count going stale. The reviewer also
struck §4.5's mechanism claim: the runner sets a **default** buffer and sweeps around it, so
「the opponent is therefore handed the best width the sweep found」 asserted code that does not
exist; the sentence now says the score is **reported at** the best width measured. Both were
repaired before the push and every integer below was re-derived after the repair.

⚠⚠ **The gate is nonetheless unsatisfiable in `paper/` by honest means, and that is the
finding.** WFG-202's done-when is 「`unqualified_post_hoc_claims` returns empty for every
`paper/` path」. After the repair it returns **six** units, **zero** of them real: every one
is the trigger `margin\s+(?:of|is|was)\s+\d` matching *this file's own* and `GAPS.md`'s
**word-budget** margin. In `paper/` the dominant sense of 「margin」 is NH-037's, not NH-032's,
and **one of the six units is the paragraph describing the false positives** — the gate
cannot tell a margin from a sentence about one. Silencing them would mean writing a
post-hoc-maximum qualifier into a paragraph about a word counter — a sentence using the right
words wrongly, which is the leakage that module's own docstring says it cannot detect. It was
not done. The fix is a narrowed trigger in `tests/`, outside CHARTER §12.

⚠ **The page that took the count from 22 to 23 cost eleven words, and it is worth
knowing that before reading the words-to-pages table below as a rate.** Lap 11
took the body 8,735 → 8,825 (a mandatory §4.5 correction, one clause, and the
repairs its reviewer's block required in §4.4 and §4.5), but the page had gone by
the first of those: measured in the same lap, the mandatory correction **alone**
(8,746 words) already renders 23. §4.5 was sitting on a page boundary and any
edit to it would have tipped the same page. The table below samples at 500-word
steps and cannot see a boundary an eleven-word sentence crosses. **A lap that
must correct a sentence corrects it and re-measures; it does not trade a caveat
for a page.**

⚠ **This paragraph itself read 「23 pages … two pages of margin」 for a lap while
the file was 22, which is the opposite error and was luck rather than accuracy.**
Lap 10 drafted §4.5 with a ninth figure (F9) in it, measured **23**, then withdrew
the figure on its reviewer's block (`GAPS.md` G8) — which took the document back
to 22 without this paragraph following it. `STATE.json` carried 22 correctly
throughout, so the two disagreed and nothing compared them: `check_paper.py`
gates `STATE.json` against the manuscript, and **no gate reads this file at
all.** The withdrawn measurement is kept rather than deleted because it is the
cleanest datum the loop has for what a figure costs: the same prose, one figure
added, is one page. The Carlito
qualifier is load-bearing and the next section says why. Earlier versions of this file and of CHARTER §12
said 20 pages, which was IEEE Access's *recommendation* read as a rule; the
author's ceiling is the operative one.

| file | role |
|---|---|
| `manuscript.md` | the single source of truth; Markdown subset (see below) |
| `references.bib` | every citation, verified by opening the URL; unverified ones are not allowed in the manuscript |
| `figures/F*.png` | built by `make_figures.py` from committed artifacts only; never hand-edited |
| `style.py` | the one figure style (fonts, palette, sizes); every figure imports it |
| `make_figures.py` | regenerates every figure deterministically |
| `build_docx.py` | Markdown → `WildfireGuardian_Park_2026.docx` (python-docx; title page, numbered figures/tables, references) |
| `check_paper.py` | the paper's own gate: the 25-page ceiling where it can be measured, the word budget as its proxy where it cannot, figure/reference integrity, gap ledger, registry-anchored numbers |
| `measure_pages.py` | renders the built `.docx` and counts its pages, two ways, refusing to answer when they disagree; `check_paper.py` calls it, and `--why` prints the install a machine needs to run it |
| `measure_render_gap.py` | what the word proxy does **not** count: decomposes the built document into `body_words` and the captions, tables, headings, references and front matter outside it, and exits 1 if the parts do not reconcile with the total. Gates nothing |
| `GAPS.md` | every `[GAP: …]` marker in the manuscript, with what closes it and when (after the sprint if needed) |
| `STATE.json` | the commit the manuscript last incorporated, the counts `check_paper.py` drift-checks, and `built_pages` with the `built_pages_inputs` digest that anchors it |

## Markdown subset `build_docx.py` understands

`# Title` (once) · `## Section` · `### Subsection` · paragraphs · `- bullets` ·
`1. numbered` · `**bold**` / `*italic*` / `` `code` `` · figures as
`![Caption text](figures/F1_system.png)` on their own line · tables in pipe
syntax with a preceding line `Table N. Caption` · citations as `[@key]` or
`[@key1; @key2]` (numbered in order of first appearance; the References section
is generated from `references.bib`) · `[GAP: what is missing]` markers, rendered
in red and mirrored in `GAPS.md`.

## Rules (from docs/auto/CHARTER.md §3, §9, §12)

- Every number comes from `docs/NUMBERS.json` or a committed artifact, and the
  registry-anchored collision gate runs over `manuscript.md` like any other
  prose. Withdrawn claims stay withdrawn.
- Figures are drawn from artifacts by `make_figures.py`; if the artifact is
  missing the figure is not drawn and the manuscript says `[GAP]`.
- The manuscript is a draft the student owns: `AUTHORSHIP.md` records that the
  loop drafted it; the abstract and any ISEF text are rewritten by the student
  before submission; nothing is submitted anywhere before the December ceremony.
- Length: **25 built pages** is the rule and `check_paper.py` measures it where a
  renderer exists. The word budget — target 8,500, hard fail above 9,000
  (`docs/auto/LOOP_CONFIG.json`, CHARTER §12) — is its stand-in everywhere else.
  The old gloss "≈ 16 pages at this style" was an assumed conversion and it was
  wrong; the measured curve is in the next section. ⚠ **The proxy is not the
  rule**: figures, not prose, are why §4 is most of the document, so a new
  figure adds a page without adding a word. Re-measure after adding one — lap 10
  did, and its ninth figure cost exactly the page the curve predicts. That figure
  was then withdrawn for an unrelated reason (`GAPS.md` G8) and the page came back.

## How many pages this actually is

`python paper/measure_pages.py` renders `WildfireGuardian_Park_2026.docx` with
LibreOffice and counts the pages, cross-checking the page objects against the
page tree and refusing to print a number when the two disagree. On 2026-09-05
it reported **21 pages** (page objects 21, page-tree `/Count` 21). `pypdf` 6.17.0
was `pip install`ed once as a third check and also said 21, then removed again;
it is not in `requirements.txt` and not in the bootstrap venv, so treat that
cross-check as a note, not as something a fresh clone re-derives.

⚠ **The count is font-conditional, and the qualifier is not pedantry.** Measured
on the identical built file with the identical renderer, varying only which
faces fontconfig was allowed to see: **Carlito 21 pages, DejaVu Sans 23**.
`build_docx.py` asks for Calibri, which is not redistributable; only a
metric-compatible stand-in makes the number a statement about the document
rather than about the machine. So `check_paper.py` gates only when the face is
Carlito or real Calibri, and otherwise reports the count and falls back to the
word budget — because failing on a DejaVu render would reject a document that is
inside the author's rule in Word.

**The words-to-pages curve.** `python paper/calibrate_pages.py` regenerates it.
Filler is the manuscript's own paragraphs recycled; the 8 figures, 4 tables and
27 references are held fixed; the only variable is **where the words go**:

| body words | 7,461 | 7,961 | 8,561 | 8,961 | 9,461 | 9,961 | 10,461 |
|---|---|---|---|---|---|---|---|
| appended after the last figure | 21 | 21 | 22 | 23 | 24 | 24 | **25** |
| spliced into §4, among the figures | 21 | **22** | **23** | 23 | 24 | **25** | **25** |

⚠ **The first row is a lower bound, not a conversion rate.** This lap first
measured only that row, ran a two-filler control that varied vocabulary, found
the counts identical and concluded the conversion was "a property of the
template, not of the words poured into it". The lap reviewer pointed out that
this controlled the variable that cannot matter and held fixed the one that
does. The second row is the re-run, and it costs up to a page at equal word
count. Real prose is added in the middle of a paper, not after it.

What the sampling actually supports: at the proxy's own 9,000-word limit the
document is **23 pages by either route**, so the proxy keeps two pages of margin
and is sound; the 25-page ceiling arrives between 9,961 words (among the
figures) and 10,461 (at the end), so the proxy stops a lap about a thousand
words early, which is the right direction to err in. The step is 500 words and
**no count above 25 was ever measured**, so the ceiling is bracketed, not
located. The laptop session that set the proxy estimated "about 21 pages" at the
current length; that estimate was exactly right.

Two things make that number meaningful, and both are printed by the script
rather than assumed. `build_docx.py` sets **Calibri**, which is not
redistributable; the render substitutes **Carlito**, which is metric compatible
with it, so the line breaks — and therefore the page count — track Word. Where
Carlito is absent the substitute is not metric compatible and the script says
so in its output instead of printing a bare integer. The Korean runs fall to
whatever CJK face is installed (`fonts-nanum` here); there are few enough of
them that no page boundary moves, which is an observation and not a guarantee.

⚠ **This sandbox cannot do it out of the box, and three laps mis-recorded
why.** `paper/GAPS.md` had it that LibreOffice "refuses to load the built
document", then correctly narrowed that to "it refuses a two-paragraph `.docx`
too, so it says nothing about our file". Both were true and the diagnosis
stopped one step short: this image ships `libreoffice-core` **without**
`libreoffice-writer`, so there is no text-document import filter at all and
every word-processor format fails identically with `source file could not be
loaded`. (What CI's runner ships has not been inspected and is not asserted
here; the gate skips wherever the renderer is absent, whatever the reason.)
The fix is one install, which `measure_pages.py --why` prints:

    apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer fonts-crosextra-carlito fonts-nanum

That is machine setup, not a repository dependency, so no gate runs it and
`measure_pages.py` exits **2** (not 1) where the renderer is missing — a fact
about the machine, not about the document. `check_paper.py` imports the module
lazily and survives its absence for the same reason: a module-scope import of a
sibling a lap forgot to stage would turn every push red through
`tests/test_paper.py`.

⚠ **The page check has no committed test.** Its five branches — no module, no
renderer, renderer broken, face not metric-compatible, count over the ceiling —
were each exercised by hand on 2026-09-05 and behave, but `tests/` is outside
what CHARTER §12 lets the paper routine touch, so a fixture-driven test in
`tests/test_paper.py` is a dev-lap item. Until it exists, the branch that can
fail a push is untested.

## `built_pages` now rots loudly instead of quietly (lap 9, WFG-116)

⚠ **This heading read "cannot rot any more" for the first hour of lap 9 and the lap
reviewer blocked the push over it.** Its objection is kept here rather than paraphrased,
because it is the same discipline the manuscript paragraph shipped in the same diff is
about: nothing below re-derives the page count. A renderer is the only thing that
produces that number, `STATE.json` is bookkeeping a lap writes by hand, and so every
field in it — the new one included — is forgeable by the very lap the gate audits.
Critic #21 F4's sentence, "`built_pages` is the one field in that file nothing
re-derives", is still literally true. What changed is narrower and worth having:

Critic #21 (F4) found the hole the block above leaves: **the only branch that can
fail needs LibreOffice Writer, and no machine the loop owns has it** — not a
cloud lap, not `auto-gates`. So `built_pages` was the one field in `STATE.json`
that nothing ever re-derived, on exactly the quantity a new figure changes and
the word budget cannot see. The lap that measured 21 pages did it inside a
sandbox that no longer exists.

`check_paper.py` now **anchors** the number, and the check needs **no renderer**.
`built_pages_inputs` is a digest of the document the count was measured on: the
ordered figure list with each PNG's pixel size, the table count, the reference
count and the body-word count. Where a run can measure, it refreshes both and
prints the digest. Where it cannot, carrying a `built_pages` whose digest has
moved is a **failure**, and the message says to re-measure or to set both fields
to `null` — an unknown page count is honest and a stale one is not.

What that buys, stated at the size it is: a figure, table or block of prose
arriving unnoticed now turns the gate red instead of quietly invalidating a
number nobody rechecks; and keeping the old count anyway stops being an accident
and becomes an edit that shows in the diff. What it does not buy: any
re-derivation. **WFG-116's first alternative — one `apt` line in
`.github/workflows/auto-gates.yml` so a clean clone actually measures — is the
fix that re-derives, is outside `paper/`, and is still open.**

⚠ The reviewer's sharpest point was operational and it changed the code, not
only this file. The first version printed `built_pages_inputs` on **every** run,
including runs that could not measure — so on a cloud lap the bypass (paste the
string the gate just printed, keep the old page count) and the honest act (null
both) were the same keystrokes, and the bypass was the routine one because
`body_words` is in the digest and therefore every lap invalidates it. The digest
is now printed **only by a run that measured**, and the failure messages no
longer contain it. The value a lap may record is the value a run derived.

Two decisions inside it, both deliberate:

- **Not a digest of the PNG bytes.** The next section explains why: the same
  script on the same artifacts re-renders to different bytes under a different
  font set, and a byte digest would call that a change. Pixel size is what
  drives the page cost and it survives a substituted face.
- **`body_words` is in the digest.** Leaving it out would let a recorded 21 ride
  through any amount of new prose on the argument that the word budget covers
  prose. It covers the *ceiling*, not the accuracy of a recorded count, and the
  curve below moves a page well inside the budget's own range.

Graded the way the backlog row asks, on 2026-09-05 with `_has_writer` stubbed
false to reproduce the cloud case: matching state passes; a figure swapped for
one of a different size fails with the digest mismatch; `built_pages: null`
passes. This lap also **re-measured** rather than inheriting: 21 pages under
Carlito at 7,639 words, after one `apt-get install libreoffice-writer
fonts-crosextra-carlito fonts-nanum` in the sandbox.

⚠ **These branches have no committed test either, and that is now the same
criticism one layer up from the one above.** The diff that added them touches no
file under `tests/`, because CHARTER §12 does not let this routine write there.
Worse for local coverage: this sandbox *has* Writer once the install above has
run, so `measured_here` is true and the suite takes the refresh path — the
failing branches are unreachable in `pytest` here and were exercised only by the
stub above, by hand. A fixture-driven test belongs in `tests/test_paper.py` and
is a dev-lap item, alongside the workflow line.

⚠ **One piece of critic #21 F4's own evidence does not stand, and the finding
survives without it.** F4 cited `paper/measure_pages.py --why` printing "No
LibreOffice Writer on this machine" as proof that none was installed.
`--why` prints `SETUP_HINT` unconditionally and returns 0 (`measure_pages.py`
`main()`); re-checked here with Writer present and it prints the same text and
still exits 0, so that output says nothing about the machine. What does
establish the hole is F4's other check — `libreoffice-writer` and
`fonts-crosextra-carlito` appear nowhere in `.github/workflows/`,
`scripts/auto/bootstrap.sh`, `requirements.txt` or the `Makefile` — and that is
unaffected. Raised by this lap's reviewer.

⚠ **The page map below is the lap-8 render (21 pages) and no lap since has
re-derived it.** The total was re-measured — 23 — but the per-section boundaries
were read with a one-off `pypdf` install that no longer exists here, so the
positions are kept as the record of where the pages went at 21 rather than
restated as current. The shape of the answer is unchanged and is the only part
that matters for a lap deciding where to buy space: Results carries most of the
figures and therefore most of the pages.

Where the pages went at the lap-8 render: title page 1; Abstract and
§1 on p. 2; §2 p. 3; §3 pp. 4–6; §4 pp. 7–14; §5 p. 15; §6 pp. 16–17; §7 p. 18;
Data and code availability and References pp. 19–21. Results was eight pages
because it carried six of the eight figures; the page lap 10 added to it was
prose, its ninth figure having been withdrawn before the push. If a lap
ever has to buy pages rather than words, that is where they are.

## ⚠ Figures are deterministic within an environment, not across environments

`style.py` asks for `Source Sans 3` and falls back through `Source Sans Pro`,
`DejaVu Sans`, `Helvetica`, `Arial`. The cloud sandbox has **only DejaVu Sans**,
so every figure re-renders with a different face there than on a machine that
has the Source Sans family — the PNG bytes change even when neither the script
nor the artifact did. That is what happened to F1–F3 on 2026-09-03: they were
committed by one environment and regenerated by another, with no code change
between. The figures are still reproducible in the sense that matters (same
script, same committed artifacts, same numbers), but the byte-level diff is not
evidence that anything moved. Vendoring the font into the repository, the way
`web/assets/fonts/` already does for the screens, would close this; it is not
done, and it is recorded here rather than hidden.

**This is not only cosmetic, and on 2026-09-04 it had broken F1.** Matplotlib
neither wraps nor shrinks text to fit a patch, so a diagram label sized against
Source Sans renders straight through its box border in the wider DejaVu. Four of
F1's seven boxes were doing exactly that — into the neighbouring box, and in one
case off the canvas — in the committed PNG and therefore in the built `.docx`.
Any figure that puts text inside a drawn shape must measure it: `_fit_text()` in
`make_figures.py` places the label, reads its rendered extent, and steps the font
size down until it fits its own box, which is deterministic for a given font and
correct under either family. Use it for every new diagram label; never hand-tune
a font size against whichever font this machine happens to have.

## ⚠ Two figure rules added 2026-09-04 (lap 3), after critic #7 found both broken

Both defects shipped in figures a lap had recorded as "looked at", so looking is not
enough on its own — check these two things by name.

- **A colour means one thing in one figure.** F7 panel b coloured "deadline first wins"
  with panel a's *nearest-first* teal, so the same teal carried opposite meanings in two
  panels an inch apart. Both panels now read: vermilion = deadline-first, teal =
  nearest-first, and panel b's legend says "ahead" rather than "wins/loses" so the colour
  and the word agree. Ties take `style.LINE`, which is not a series colour anywhere.
- **A legend or a value label must not be placed where the data is.** F2's value labels
  were struck through by the mean-of-folds rule and its "pooled" label sat on the x-axis
  tick labels; F7 panel a's boxed legend covered the nearest-first line between three and
  five teams. Value labels now go *inside* the bars (white on the fill, the Moreno
  reference's own convention), and a legend goes either in a corner that is provably
  empty — F2's lower right, empty because the bars there are the shortest — or below the
  axes, as both of F7's now are. Growing series leave no free corner: check.

## ⚠ Figure numbers in prose are appearance numbers, not F-numbers

`build_docx.py` numbers figures in order of appearance, so `figures/F4_*.png` is
"Figure 3" in the built document whenever an earlier-numbered file appears later
in the text. The `F` numbers are stable internal identifiers for
`make_figures.py`; the `Fig. N` references in `manuscript.md` must match the
**appearance** order. Current mapping: F1→1, F2→2, F4→3, F5→4, **F8→5**, F3→6,
F6→7, F7→8. Re-check it after moving or adding any figure. The check that catches
a mistake here is reading the captions back out of the built `.docx` with
`python-docx` and comparing them to the `Fig. N` mentions in the prose; nothing
mechanical does it.

⚠ **`F9_present_perimeter` is drawn and committed but is NOT in the manuscript,
so it has no appearance number.** Lap 10 wrote it for the new §4.5, then withdrew
it after its own reviewer showed that the bar totals plus the axis denominator
plus Table 2 determine the margin NH-032 bars from judge-facing surfaces
(`paper/GAPS.md`, gap **G8**). It stays in `FIGURES` so it keeps being rebuilt
and stays reproducible; when NH-032 is answered it is referenced from §4.5 and
becomes Fig. 7, pushing F6 and F7 to 8 and 9 — at which point §4.6's two `Fig. 7`
references and §4.7's three `Fig. 8` references all move up one. `check_paper.py`
does not object to a drawn-but-unreferenced figure: it checks that every
referenced figure exists, not the converse.

⚠ **This table was stale for two laps and the manuscript went with it.** F8 was
added to §4.3 after the mapping was written, which pushed F3, F6 and F7 down one
each; nobody re-checked, so §4.4 pointed at "Fig. 5" (the routing map) for the
three-region partition and §4.6 pointed at "Fig. 7" (the sensitivity panel) for
the dispatch lineage caveat that binds every number in that section. Both fixed
on 2026-09-04 (lap 5). Nothing mechanical catches this — `check_paper.py` checks
that each figure *file* exists, not that a `Fig. N` in prose names the right one.
Count the `![` lines in order and compare, by hand, after any figure move.

## ⚠ A table caption must touch its table — no blank line

`build_docx.py` treats a `Table N.` line as a caption **only** when the very next
line starts with `|`. With a blank line between them the caption falls through to
the paragraph branch: it is counted in `body_words`, rendered as ordinary prose,
and the table is built with the label `Table N. ` and an empty caption. All three
captions were written that way and cost 318 words of the length budget until lap 5.
`check_paper.py` counts tables and cannot see a missing caption, so after adding a
table read it back out of the built `.docx` with `python-docx` and look at the
caption. Figure captions are unaffected — that branch has no such condition.

## ⚠ Two gate behaviours the manuscript has to be written around

- `scripts/check_number_collisions.py` matches anchor words and numbers **per
  source line**, so one very long Markdown line produces false collisions
  between unrelated quantities. `manuscript.md` is therefore hard-wrapped at
  88 columns; `build_docx.py` rejoins wrapped paragraph lines, so the wrapping
  is invisible in the `.docx`. Do not unwrap it. List items and figure caption
  lines cannot be wrapped (the builder matches them per line), so those must be
  phrased to avoid packing many numbers onto one line.
- That gate's number pattern does not capture a leading sign, so a **negative**
  registered value written with a typographic minus (U+2212) can never match
  its own registry entry. Write negatives with an ASCII hyphen-minus.
