# The paper — how it is written and built

Target: one English manuscript, publication-ready in tone and figures, written
alongside the code by the `wfg-autoloop-paper` routine (docs/auto/CHARTER.md §12)
and rebuilt every time the code moves. Author: **Siyeong Park (박시영)**.

**Length: the ceiling is 25 pages.** The author decided it on 2026-09-05
(NH-028, verbatim: 「Don't worry about the word count for now. Just make sure it
doesn't exceed. 25 pages for. now」). `check_paper.py` now checks that directly —
it renders the document and counts — and keeps the 9,000-word budget as the
proxy for machines that cannot render, or that can render but not in a font
whose metrics are Calibri's. As of 2026-09-06 (lap 13) the built document is
**23 pages under Carlito**, measured rather than estimated: 21 at lap 9, 22 at
lap 10, 23 at lap 11, 23 at lap 12 and 23 again now. **Two** pages of margin remain
against the author's 25.

⚠ **The two margins have come apart, and the proxy is now the tighter one by about a
thousand words.** At lap 13 the document is 23 pages against a 25-page rule and 8,983
body words against a 9,000-word proxy: two pages of margin, **17** words of margin,
down from 31 at lap 12. The
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
one.** The next lap that must add a sentence has 17 words. Escalated to the
author as **NH-037**, which is now urgent rather than theoretical. Until it is answered
the proxy stands: it is the author's own number and a lap does not raise its own ceiling.

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
