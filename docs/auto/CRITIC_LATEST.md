# CRITIC_LATEST — critic #42, 2026-09-08T1115Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head:
`ceb43ba`. Window: the 24 h to 2026-09-08T11:09Z. ⚠ **This clone is shallow:**
`git rev-parse --is-shallow-repository` = **true** and `git rev-list --count HEAD` = **50**, and
the oldest resolvable commit is `2720840` at 10:09Z on 09-07, so this clone reads about 25 hours
and I make no claim about anything older and no ancestry or reachability claim at all
(DIRECTION's standing rule). Full report: `docs/auto/reports/2026-09-08T1115Z-critic.md`.*

## `fix-before-next-row` — ONE item: **WFG-187**. Run it, then take the table (WFG-010).

**The judged screen's build stamp is five commits from the limit that closed `auto/dev` to every
routine on 2026-09-07, and this lap is filing it BEFORE the limit instead of at it.**

Measured here at `ceb43ba`, every command read unpiped:

- `web/finals.html:434` carries `"git":"1bca8ed"`, built 2026-09-08 00:29 UTC.
- `git rev-list --count 1bca8ed..HEAD` answers **25**.
- `tests/test_finals_screen.py:540` sets `STAMP_MAX_COMMITS_BEHIND = 30`; `:732` asserts
  `behind <= STAMP_MAX_COMMITS_BEHIND`. **The branch closes at 31.**
- Gates are ALL GREEN at this head. Nothing is red yet, and that is the point.

**The arithmetic, said rather than felt.** The screen was rebuilt at `1bca8ed` at 22:21Z on 09-07
and the branch has taken 25 commits in the 11 h 59 m since, about two an hour. The six dev work
commits in this window each travelled with 3 to 5 commits (claim, work, reviewer fix, report). So
the **next** dev lap lands at roughly 28 to 30, and the one after it trips the assert **on its
claim commit alone**, before it has done a single piece of work. That is NH-045 replaying with the
same cast, and CHARTER §3.9 then parks whichever routine met it.

**Why this qualifies under §14b as amended by NH-038 B.** One command, `make finals`, on the
surface §14b's own list names ("finals screen"). It is the same shape and cost as critic #38's
WFG-173, which the loop cleared inside one lap — except that WFG-173 was filed **at** the limit,
after the branch had already shut and critic #38's own work had to be parked on
`auto/red/2026-09-07T2319Z`. Five commits of headroom is the whole difference.

⚠ **It is NOT the structural fix and must not be written up as one.** WFG-159, WFG-160 and
WFG-161 already carry the recurrence; **NH-043** (due 2026-09-09, unanswered) is the author's
decision on what a lap may do when the gate fires. This row buys the time for that answer.

⚠⚠ **Re-measured AFTER this lap's own two commits landed: `behind` is now 27, not 25, and the
headroom is three.** This lap pushed `2fa29af` (the findings) and `6baf478` (the report's head
annotation), and its own commits are part of the drift it is reporting — said here rather than left
for the next reader to discover. At 27, a dev lap that claims first and rebuilds later can cross 31
**in the middle of its own lap**: claim 28, work 29, reviewer fix 30, report 31. That is why the
order below is not a preference.

**Done when:** the lap runs `make finals` and pushes the rebuilt `web/finals.html` **before it
claims a row**; its report records `git rev-list --count <new stamp>..HEAD`; and
`gates.py --mode full` exits 0 on the commit it actually pushes.

**Then take the table: WFG-010 is position 1** and this lap moved its row there (below).

---

## The one row move, and why the table needed it

**Critic #41 raised WFG-010 from P1 to P0 and left the row at table line 151, so the priority
changed and the position did not.** Measured here at `ceb43ba` before the move: the first `todo`
row in table order was **WFG-186**, P1 infra, whose own cell ends 「CHARTER §14b holds this behind
R3 and R8」 — a row the loop's own rule forbids a lap to take — and **eight P0 `todo` rows sat
below it**: WFG-007, WFG-117, WFG-127, WFG-128, WFG-129 (lines 71-75), WFG-036 (103), WFG-010
(151), WFG-054 (172).

This is critic #40's finding recurring within three laps, and not because anything moved: the four
P0 rows that were sitting above the P1 block all **closed**, and the block surfaced again. One row
moved (WFG-010, to the head of the `todo` block). The other seven violations are recorded in
DIRECTION and are **not** this lap's reorder; the standing rule that would end the class is that a
row raised to P0 is repositioned in the same edit that raises it.

---

## The baseline, re-derived rather than read

✅ **ALL GREEN on the routine's DEFAULT clone, measured before any deepening, read unpiped.**
`gates.py --mode full` exits **0** at `ceb43ba`: `1741 passed, 63 skipped, 2 xfailed`, pytest
**258.3 s**. `verify`, `snapshot-verify`, `env-check` PASS; the `baseline-verify` WARN is the
documented CHARTER §3d sandbox state. **The run downloaded nothing:** `du -sb data/raw` answers
**201,187** bytes before and after, and `data/raw/dem/srtm/` is empty afterwards. **Cold on the
tile, which was never present; WARM on `data/cache`**, said rather than implied. `--assert-head`
exits 0, and `--assert-reported --base 2720840` exits 0 over 69 substantive paths.

✅ **GitHub's own runs (CHARTER §4b): no finding.** Through the GitHub MCP; `curl` against
`api.github.com` is still refused in this sandbox (WFG-119). `auto-gates` runs **216 to 241** on
`auto/dev`: **21 `success`, 5 `cancelled` (218, 226, 229, 232, 235), ZERO `failure`.** Run **241**
at this exact head is `success`. No red run sits behind a green report.

✅ **Report certification.** Every dev and critic report in the window carries `Reviewed by:`. The
one report without the line is `2026-09-07T1432Z-manual.md`, a report written to satisfy
`--assert-reported` for a prose correction that carried no build; that is not a finding.

---

## The root objection

**Six consecutive dev work commits have edited the same file, and the product's own
definition of done has not moved in three critic laps.**

Measured here, not felt: `git show --name-only` over the six dev work commits since
2026-09-07T18:00Z — `6d1d730`, `fa18fcc`, `82ec346`, `ab4e71e`, `c2a7980`, `5845953` — returns
`docs/auto/JUDGE_QA.md` in **every one of the six**. Over the same six laps `KCF_READINESS.md`
holds at **7 of 11** and **zero lines ticked for the third consecutive critic lap**. `web/finals.html`
was touched once, by a rebuild, and it is the thing now five commits from closing the branch.

Each of those six laps was individually right, and this is not an accusation that any of them
picked wrong. It is that the two mechanisms meant to protect the product — the
`fix-before-next-row` item and DIRECTION position 1 — have pointed at the same file for six laps
running, because a Q&A card is the cheapest judge-facing surface to fix and the queue has no other
entrance. The bank is now the best-tested artifact in the repository and the screen has a stale
stamp, the README has no Round-4 section, and R3 and R8 are where they were on 09-05.

**The cheapest test, and the author already owns it: NH-038, due 2026-09-09, unanswered.** It asks
this exact question in the author's own words ("Your product first rule has spent the last three
dev laps on documents"). It is now six. This lap opened **no new entry** and instead wrote the new
measurement into NH-038, per DIRECTION's own rule about not opening a fourteenth question while
thirteen are unanswered.

---

## What this lap did NOT find, said plainly

- **No red gate, on this machine or on GitHub.** Both channels checked.
- **No false claim about the world in the window's new prose.** `docs/creativity_card.md`,
  Q29a, the WFG-146 date correction and the WFG-171/WC-009 narrowing were each re-read against
  their sources; the corrections hold and the registers are the ones DIRECTION requires.
- **No `Do NOT edit` note is written by this lap** (CHARTER §14c, NH-036 A). WFG-187 must rebuild
  `web/finals.html`, and WFG-010 must edit `README.md`; freezing either would block the work.

## The one thing worth copying forward

**WFG-186's rule was honoured one lap before WFG-186 was taken.** Critic #41 wrote that a lap
reporting a mutation score must name one mutation it could **not** make the gate catch. The 1013Z
lap did it twice without being asked: the superset phrasing 「`<run>` 를 포함해 커밋된 33장 전부에」
for Q16b, and the register drift 「이 접근은 매우 독창적입니다」 for Q29a, both written into the test
files as `_the_mutation_this_cannot_catch` rather than into a report only. That is the first time
this loop has published the denominator of its own coverage claim.
