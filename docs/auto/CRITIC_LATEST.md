# CRITIC_LATEST — critic #20, 2026-09-05

Window `8a8a940..ce262fe` on `auto/dev` (7 commits, two of them the author's own laptop
sessions; 1,670 authored insertions with images, the board and the `.docx` excluded).
Written by the `wfg-autoloop-critic` routine.

## fix-before-next-row

**None this lap, and the reason is a rule, not an absence of candidates.**

`docs/auto/DIRECTION.md` now names two rows above anything I found: **WFG-114**, the author's own
NH-027 row, which this page had never named; and **WFG-007**, the printables, raised to P0 on
critic #19's falsifiable test. Setting an item would displace one of them. Readiness has been
4 of 11 for **five** consecutive critic laps, and critic #18's rule — set no item when readiness
stalls two laps — fires and is obeyed. WFG-115 below would qualify under CHARTER §14b and is
filed as a P0 row, third on the direction page, not as an item.

## Findings, ranked

**F1 · WFG-115 · judge-facing · P0 · the judged screen prints a second commit id and it is not on
this branch.** The 검증 레지스트리 evidence card renders `'built at commit ' + DATA.registry.built_at_commit`
(`web/finals.html:1924`, `scripts/finals.template.html:1924`), fed by `scripts/build_finals.py:628`
from `docs/NUMBERS.json` `built_at_git_commit`. The value is `41498ef`. Run here, not reasoned about:

```
git cat-file -t 41498ef                       -> commit
git merge-base --is-ancestor 41498ef HEAD     -> exits non-zero
git branch -a --contains 41498ef              -> origin/auto/lap-b1989d5-superseded
                                                 origin/ordering-boundary
```

That is the **exact** WFG-067 failure shape (a stamp that exists but is not reachable), in the same
panel WFG-067 was about, and `tests/test_finals_screen.py` never looks at this field: both of its
ancestry assertions (`:544`, `:550`, `:649`) read `_payload()["git"]`, which is `5f9a3b8` and is fine.
Two commit stamps on one screen, one gated, one not.

⚠ It is also **stale by construction**. `built_at_git_commit` was written when the registry held
153 entries (`41498ef` is 「session 8 closes: 1085 green, 153 registered」); the card beside it prints
**326**. `build_numbers.py` is deliberately not re-run (WFG-040), so the field will keep drifting.

⚠ And it falsifies half of a judge-facing answer. `docs/auto/JUDGE_QA.md` Q35 (T1, drill round 3) is
「화면 아래 적힌 커밋을 받아서 이 화면을 그대로 다시 만들 수 있습니까?」 and the drafted answer says the
panel's hash 「이 저장소에 실제로 있고 **현재 브랜치에서 닿는** 커밋입니다」. True of one stamp, false of
this one. Its 「없는 것」 line disclaims only byte-identity of the HTML. The whole 「이 질문의 내력」
paragraph holds WFG-067 up as this project's best example of how it handles reproducibility, which is
what makes the second stamp worse than an ordinary stale string. A ⚠ note is added to Q35 in this lap
so the student does not rehearse it; the answer itself is WFG-115's to rewrite once the gate proves
what it may say.

**F2 · a duplicate backlog id, and one of the two rows is the author's.** Two live rows carried
`WFG-108`: the `make finals-bundle` row filed by the 1302Z dev lap at 13:02Z, and the fair-opponent
arm added by the author's laptop at 14:24Z (`9442430`). The dev lap picks 「the highest-priority `todo`
row」 by id, and a report saying 「WFG-108 done」 would be ambiguous between a P1 infra row and a P0
science row. Repaired the way CHARTER precedent sets (WFG-040, WFG-094: an id others quote wins): the
bundle row keeps `WFG-108`, quoted in `docs/auto/finals/BOOTH_SETUP.md:86` (judge-facing),
`docs/auto/MEMO.md:1012`, critic #19's `CRITIC_LATEST.md` and `docs/auto/reports/2026-09-05T1302Z-dev.md`;
the fair-opponent row becomes **WFG-114**. The author's decision text names no id, so nothing the author
wrote moves. Reports are records and are not edited, so the two 1424Z/1449Z manual reports still say
`WFG-108`.

**F3 · the direction page did not know the author had moved a row, and it outranks the table.**
`9442430` (14:24Z) closed NH-027 with 「A) Run it in the sprint now, P0 ... (new row at the top of the
table after WFG-062)」 and put the row there. `DIRECTION.md` was rewritten at 14:12Z, twelve minutes
earlier, and named WFG-109, WFG-106, WFG-104, WFG-007 and a tail of eleven more rows — not this one.
CHARTER §14b says the dev lap takes **the page's** order over the table when they differ, so for one
full lap the page steered the loop away from the row the author personally promoted, and the row that
answers this routine's own standing root objection. Fixed on the page; the transferable rule is that
the page is re-read after an **author push**, not only after a dev lap. This finding is about the loop,
so under §14b it stays a note rather than a row.

**F4 · WFG-116 · P1 · the paper's page ceiling is enforced by a gate that cannot run anywhere the loop
runs.** `paper/check_paper.py` `page_check()` gates the author's 25-page rule (NH-028) only when
LibreOffice **Writer** is present, and the previous lap installed it inside a sandbox that no longer
exists. Verified at `ce262fe`: `/usr/bin/soffice` is there,
`.auto/venv/bin/python paper/measure_pages.py --why` prints 「No LibreOffice Writer on this machine」,
and `libreoffice-writer` / `fonts-crosextra-carlito` grep to **zero** hits across `.github/workflows/`,
`scripts/auto/bootstrap.sh`, `requirements.txt` and `Makefile`. So the only branch that can fail is dead
in every cloud lap and every `auto-gates` run, and `paper/STATE.json` `built_pages: 21` is the one field
in that file nothing re-derives — the drift check skips it unless `metrics_ok`. The file's own docstring
says the risk the word proxy cannot see is a **figure**, which costs a page and no words. Not urgent
(21 of 25 pages, 7,461 of 9,000 words); it is filed so the number does not quietly rot.

**F5 · NH-029 executed, and it is the best thing in this window.** The author ran option A at `38620f2`.
Re-run here rather than read from the report: `make baseline-verify` now reports **2** differences, not
six, and both are the git-ignored `data/raw/firms_data/` manifests that exist only on the laptop. The
re-freeze **preserved every protection** — I diffed `38620f2^` against `38620f2`: both
`untracked_contracts` hashes and all four `protected` artifact hashes are byte-identical, and
`tracked_processed` went 127 → 130 (the three `pace_*.json` files). This is the outcome CHARTER §3.2
exists to protect and it survived. R3's box does not tick, because its own command still needs one run
on the author's machine, which is NH-029's remaining half.

**F6 · checked and NOT findings, recorded so no later lap re-derives them.**
(a) **WFG-109's gate is real and I graded it myself.** I edited the corrected caption in
`scripts/finals.template.html` back to the withdrawn wording and re-ran the suite: 2 failed, 7 passed.
The identity assertion (whole file outside the one payload line) is the right invariant and is stronger
than the caption comparison the row asked for.
(b) **WFG-113 reproduces exactly as filed.** I changed `"n_entries": 326` to `999` on `web/finals.html:434`
and ran the named guards: `test_finals_template_sync.py` + `test_finals_screen.py` 41 passed,
`check_forbidden.py` `OK`, `verify_numbers.py` `OK`. A false number stays on the judged screen and
everything is green. Independently confirmed, not read from the report.
(c) **factchk on the window's one new claim about the world.** `paper/measure_pages.py` and
`paper/check_paper.py` say Carlito is 「the metric-compatible stand-in for Calibri」. Debian's own package
page for `fonts-crosextra-carlito` reads 「Sans-serif font metric-compatible with Calibri font」
(packages.debian.org/sid/fonts-crosextra-carlito, opened 2026-09-05). Holds. No other new prose in the
window asserts anything about the world; the fire-science and Korean-source surfaces were untouched.
(d) The `git` stamp in the payload is `5f9a3b8`, an ancestor of `HEAD`, and its gate passes. F1 is about
the **other** stamp only.

**F7 · loop hygiene, clean, one line.** `auto-gates` runs 117 to 136 on `auto/dev`: **no `failure`**
anywhere in the window; 136 at this head is `success`; 131 and 125 were `cancelled` by a superseding push
(WFG-102). Every consecutive pair of commits in the window passes `--assert-reported`. Every dev, paper
and critic report in the last 24 h carries `Reviewed by:`; the four that do not are `manual`, which is the
author's own laptop and is not a lap. `gates.py --mode full` exits 0 here at `ce262fe`
(`1515 passed, 62 skipped`, 202.0 s, cold; +9 like for like over critic #19's cold run).

## Root objection (hate), unchanged, and now it has a row with the author's name on it

**The headline credits the forecast with what merely seeing the present fire would have bought.** Every
comparison the project ships is against `naive`, which is fire-blind
(`src/wildfireguardian/routing/evacuation.py:270`, `docs/real_roads_real_hazard.md:50`). Three consecutive
critics have written this and the cheapest test has been costed twice. **What changed this window is that
it stopped being a critic's objection and became the author's instruction:** NH-027 option A, 「Run it in
the sprint now, P0 ... report the number whatever it says」. The objection is now answered by doing WFG-114,
not by arguing about it, and the only thing that had gone wrong is that the page which orders the work did
not carry it.

## Scorecard

B 84 → **83**, A 79 → **78**, both on F1 and both scored once: a Track B judge takes an unreachable commit
id in the reproducibility panel out of 제출 자료 (출처 명기), a Track A judge takes it out of
구현 및 유용성 (작품 완성도). The window's real gains — the identity gate, the measured page count, the
re-freeze — are holes closed rather than capability added, and the identity gate's own disclosure paragraph
had to be corrected inside the same commit. Evidence per row in `docs/auto/SCORECARD.md`.
