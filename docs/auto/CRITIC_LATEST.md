# CRITIC_LATEST — critic #49, 2026-09-09T0820Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `7f914fd`, and
every measurement below was taken on that head in this clone. ⚠ **This clone opened SHALLOW at 50 commits.**
I deepened it with `git fetch --shallow-since='2026-09-08T00:00:00Z'` to **83** commits, oldest resolvable
`088203c` at **00:22:53Z on 09-08** — a deepening whose predicate is **the window itself**, not a guessed
number. `--is-shallow-repository` still answers **true**, so **no ancestry or reachability claim appears
anywhere below.** Full report: `docs/auto/reports/2026-09-09T0820Z-critic.md`.*

## `fix-before-next-row` — ONE item, minutes: the README half of **WFG-210**

**The front door's 창의성 item ① sends a judge to the competitors and to no instance of the thing it claims.**

`README.md:326-355` shipped this window (WFG-207) and is good work. Its item ① says the contribution is the
**output object** — 「가구 단위의 「걸어서 나갈 수 있는가 / 구조를 보내야 하는가」 판정과 그 도보 경로」 — and
its only link is `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`, the landscape note about NIFoS and
G-DAPS. Two measurements at `7f914fd`:

- `tests/test_creativity_card.py:86` sets
  `OTHER_SYSTEMS = ("NIFoS", "G-DAPS", "산림청", "경기도", "국립산림과학원", "소방청", "소방방재청", …)` and four
  graded mutations prove the suite goes **red** if the spoken draft names one of them, in either direction.
  The file the same suite registers as item ①'s anchor at `:65` and `:331` carries **34** occurrences of those
  names and **12** of their announced percentages (30 %, 76 %, 88 %). The gate keeps the competitors out of
  the student's mouth; the anchor hands them to the judge.
- A judge who reads item ① and asks 「그 산출물을 하나 보여주십시오」 has no path from the block.
  `git ls-files 'outputs/dispatch/*dispatch_a4.html'` answers **33** and `outputs/dispatch_full/` **113**,
  and `docs/dispatch_ordering.md` is already linked from `README.md:302` — two lines above the section that
  needs it.

**Done when:** item ① in `README.md:326-355` carries **one added path to a committed instance of the output
object** — a `dispatch_a4.html` under `outputs/dispatch/`, or `docs/dispatch_ordering.md`, whichever the lap
judges a judge can open fastest — and the block still passes `tests/test_creativity_card.py`
(`test_every_link_in_the_readme_block_opens` resolves the new target; the item-level anchor pairing and
`test_the_label_a_judge_reads_is_the_path_the_link_opens` mean the visible label must equal the link target).
The existing `KOREAN_OPERATIONAL_SYSTEMS.md` link **may stay**: it is the honest anchor for the *choice* not
to compete on accuracy, and it is the item's claim about the *object* that has no anchor today.

⚠ **Do NOT put a comparison sentence into the block**, in either direction, and do not name another system
there. The register rule is what makes this card safe and it is the reason WC-007, WC-008 and WC-009 exist.
⚠ **Do NOT touch `README.md:210-282`** with a margin value while NH-032 and NH-034 are open — see the note at
the end of this file. The creativity block is four lines below that range and is not covered by it.

This is minutes on a §14b judge-facing surface (the README opening), which is the whole of what makes it
eligible to displace the top row.

## The rest of WFG-210 is a row, not a preemption, and it sits at table position 1

The same anchor stands on **two more surfaces** and neither is minutes:

- `web/finals.html` → `CREATIVE[0].doc` = `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md §3`. This one is
  sharper than the README's, because the screen's own wording already names the object —
  「가구 단위의 대피 판정과 걸어 나갈 경로, 그리고 **마을 단위 출동 목록**」 — and then anchors on the note.
  Changing it needs `make finals` and a stamp refresh.
- `docs/creativity_card.md` §2, table row 1, which is where the anchor was **written** (WFG-182) and from
  which the screen (WFG-194) and the README (WFG-207) each inherited it while doing their own rows correctly.
  The card is now the **7th** `SOURCES` entry of the printed kit, so changing it means rebuilding
  `WFG_printables_*.pdf` and re-pointing `release/kcf-finals-2026/MANIFEST.json` **in the same lap**.

**Done when** all three surfaces name a path to an instance of the output object for item ①, the kit is
rebuilt and re-pointed in the same lap, and `tests/test_creativity_card.py` gains an assertion that **an item
① anchor naming a document in `OTHER_SYSTEMS`' subject matter is red** — otherwise the next surface inherits
it a fourth time, which is exactly how this defect reached three surfaces.

**Then take WFG-027, then WFG-125.** `docs/auto/DIRECTION.md` says the same order. ⚠ **WFG-197 was NOT
promoted this lap** and the reason is written on that page and in the row: promoting it would have moved
WFG-125 to fourth place for a third consecutive critic lap.

## Everything else eligible under §14b is green, re-run rather than read

- `gates.py --mode full` exits **0** at `7f914fd`: `1826 passed, 63 skipped, 3 xfailed`, pytest **470.7 s**,
  `make verify` PASSED. `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is
  NH-029 and §3d working as decided.
- `--assert-head` exits 0; `--assert-reported --base 088203c` exits 0 over **90** substantive paths.
- **GitHub `auto-gates`: every run in this window carries zero `failure`** — the sixteen runs ending at
  **279**, read through the Actions API. Runs 275 and 278 are `cancelled`, each superseded by the next push,
  and run **279** is `success` at this exact head. **No CHARTER §4b finding.**
- Every dev report in the 24 h window carries `Reviewed by:`. The three window reports without it are
  `2026-09-08T1132Z-manual.md` (a prose-correction report carrying no build, declined by critics #42 and #43
  and declined again here), `2026-09-08T1836Z-research.md` (a research lap, which does not spawn a reviewer)
  and `2026-09-08T2231Z-manual.md` (already filed onto **WFG-147** by critic #46).
- `make finals-bundle` rebuilds `release/kcf-finals-2026/` byte-identically, **19** files, exit 0.
- **WFG-208 is closed and verified here**, not read: a count of `github.com` in
  `release/kcf-finals-2026/README_KO.md` answered 0 before and answers **1** now, and no document was added to
  the payload.
- The printed kit is `WFG_printables_20260909T0700Z.pdf` with `release/kcf-finals-2026/MANIFEST.json` naming
  that exact file, and its `SOURCES` list is now **seven**: `BOOTH_SETUP.md`, `DEMO_SCRIPT_5MIN.md`,
  `JUDGE_QA.md`, `submission_reconciliation.md`, `DETECTION_FLOOR_CARD.md`, **`docs/creativity_card.md`**,
  `RELATED_WORK_PANEL.md`.

## What this lap did NOT do, said plainly

- **No JUDGE_QA card was added**, although the drill found two questions with no card: 「개발 일정이 어떻게
  됩니까?」 (WFG-027, zero on all four surfaces) and 「왜 3–12시간 예보입니까?」 (WFG-197, zero on the bank, the
  screen and the script). `docs/auto/JUDGE_QA.md` is a hashed `SOURCES` entry of the printed kit, so a critic
  lap editing it turns `tests/test_printables.py` red and a critic lap may not rebuild the kit. **That is
  NH-049, open**, and both gaps are carried as backlog rows instead.
- **No §3b reorder was spent.** WFG-027 stays first among `todo`; WFG-125 stays second.
- **No new NEEDS_HUMAN entry.** Twenty-two are open and six are overdue; the one measurement this lap had for
  the author went into **NH-038**, which already asks the question in the author's own words.

## The one `Do NOT edit` note, RE-STATED after re-reading its premise

CHARTER §14c as the routine prompt states it, NH-036 A — ⚠ both NH-036 and NH-038 are still `open` in this
repository and a search for `14c` in `docs/auto/CHARTER.md` still answers **0**, which is **NH-050**.

**It covers `README.md:210-282` and nothing else.** The Round-4 fair-opponent block's bounds were re-measured
here — 「### 1.」 at `:210`, 「### 2.」 at `:283` — and are unchanged from critic #48's corrected range. It
forbids exactly one thing in those lines: putting a present-perimeter **margin value** (9, 27, 5, 19, 86)
there while NH-032 and NH-034 are open. Both re-read at `NEEDS_HUMAN.md:1391` and `:1574`: both still `open`,
both due 2026-09-08, so **one day overdue** — critic #48 wrote 「two days」 and the 0654Z dev report 「three
days」, and the correct figure is one. A scan of 210-282 finds no margin value there today.

**It expires at critic #50 unless that lap re-states it after re-reading those two entries.** It freezes no
file and no question: this lap's own `fix-before-next-row` item edits `README.md:326-355`, four lines below
the range, and that is exactly the kind of edit it permits.
