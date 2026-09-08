# CRITIC_LATEST — critic #44, 2026-09-08T1700Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head:
`0cca093`. Window: the 24 h to 2026-09-08T17:00Z. ⚠ **This clone is shallow:**
`git rev-parse --is-shallow-repository` = **true** and `git rev-list --count HEAD` = **54**, and
the oldest resolvable commit is `6d1d730` at 18:50Z on 09-07, so this clone reads about 22 hours
and I make no claim about anything older and **no ancestry or reachability claim at all**
(DIRECTION's standing rule). Full report: `docs/auto/reports/2026-09-08T1718Z-critic.md` — the readings below were taken from 17:00Z and the report stamp is when `report.py` ran.*

## The one thing to read first: **GitHub says the current head is RED, and your own gates say green. Both are right.**

`auto-gates` run **253** (id 34250797625) at `0cca093` has conclusion **`failure`**. Inside it,
the gates **passed**: the job log prints `[gates] ALL GREEN  mode=full head=0cca093 (auto/dev)`
and `1763 passed, 63 skipped, 2 xfailed` in 341.5 s, and the step
「Gates (make verify, baseline, snapshot, env, full pytest)」 concluded `success`.

What failed is the step after it, 「Keep the gate record」 (`actions/upload-artifact@v4`):

    ##[error]Failed to FinalizeArtifact: Received non-retryable error:
    Failed request: (403) Forbidden: Error from intermediary with HTTP status code 403 "Forbidden"

**And that is not cosmetic, because `promote` needs the job and not the step.**
`.github/workflows/auto-gates.yml:89` gives `promote` `needs: gates`, so `promote` was **skipped**.
`git ls-remote origin Main` answers **`6ecc386`** while `auto/dev` is **`0cca093`**.
**`Main` stopped following the last gate-certified commit because an archival upload 403'd**
(CHARTER §4c).

---

## `fix-before-next-row` — ONE item: **WFG-193**. One line, and it is a red gate rather than a page.

§14b as amended by NH-038 B names 「a red gate (a red GitHub run counts)」 beside the judge-facing
surfaces, and the routine prompt makes a red run behind a green report finding #1 and the one item.
**The commit is `0cca093`.**

**Done when:** the 「Keep the gate record」 step can no longer decide the colour of the `gates` job
(`continue-on-error: true` on that step is the whole of it), the change is pushed, and the lap reads
the resulting run **through the GitHub MCP** and says in its report whether the artifact upload
succeeded. `curl` against `api.github.com` is still refused in this sandbox (WFG-119).

**Why that is the right shape and not a workaround.** The workflow already applies exactly this rule
twice and this one step is the place it was not applied:

| where | what it does when the side-effect fails |
|---|---|
| `finals-acts` upload | `if-no-files-found: warn`, with the comment 「an empty upload is a warning rather than a red job」 |
| `promote` | exits 0 on a refused fast-forward, 「Never turn a green gate into a red run」 |
| **`gates` → 「Keep the gate record」** | **fails the job, and takes `Main` with it** |

The artifact is a **record**, not a check. No gate is weakened by this: `gates.py` still runs in
full, and `--assert-head` and `--assert-reported` still run before every push.

⚠ **Whether the 403 is transient is NOT established, and the fix does not depend on it.** Run 252
(15:47Z) uploaded fine; `finals-acts` inside run **253 itself** uploaded 2,238,204 B successfully at
16:24:41Z, and the 9,774 B gate record failed six minutes later; runs 223 to 253 hold exactly this
one `failure`. If it recurs **after** the fix, the cause is the artifact service or the account
rather than this repository, and that is when it becomes a NEEDS_HUMAN entry. Not before: fourteen
DECISION entries are unanswered and nothing is blocked by this one.

**Then take the table: WFG-127 is position 1**, and this lap's one reorder is what put it there.

---

## The root objection

**This loop has a mechanism for a claim getting weaker on its way to the front door and none for a
claim getting stronger, and this window it got stronger — onto the front door, past a gate written
for exactly that claim, in the language the gate does not read.**

Critic #43 measured the soft direction and filed **WFG-192** for it. The 1518Z lap acted on it,
fixed both sentences it was given, and in the same paragraph wrote a third. Measured here at
`0cca093`, every command unpiped:

- **`README.md:232`** now reads 「이 실행이 쓴 폭은 그 sweep 안에서 **고원이 아니라 뾰족한
  봉우리**입니다」.
- **`docs/auto/JUDGE_QA.md:1394`** (Q37 · T1) says in bold: 「1 km 의 양옆 이웃이 각각 두 배 거리에
  있어서, 「1 km 에서 뾰족하다」와 「그 부근이 평평하다」를 이 sweep 으로는 **구분할 수 없습니다**」
  and closes 「**재보지 않은 것을 재봤다고 말하지 마십시오**」. `:920` says the same.
- **`docs/auto/DEMO_SCRIPT_5MIN.md:151`** has the student say aloud 「좋았던 폭 주변이 뾰족한
  봉우리인지 넓은 고원인지 이 실험은 **가리지 못합니다**」.
- **`docs/present_perimeter_arm.md:129`** is where the sentence was copied from — and it is the
  **third surface WFG-127 already records as defective**, filed by critic #23 on 2026-09-06 and
  still `todo`.

So the front door now contradicts the booth script, the Q&A bank and an open P0 row, and it asserts
the one thing the bank explicitly forbids the student from saying.

**And the gate written for this exact claim passed.** `tests/test_fair_opponent_line.py:177-191`
bans the string 「spike, not a plateau」; its docstring gives WFG-127's own reasoning; `:185` records
that it was already hardened once against markdown-asterisk evasion. **It reads English.**
`README.md:232` is Korean, and it uses the exact vocabulary — 뾰족한 봉우리 / 고원 — that
`DEMO_SCRIPT_5MIN.md:151` already uses for the **negation**. DIRECTION has said since critic #37
that a registered spelling reaches one language; this is the first time that has been measured on a
**newly written** claim rather than a withdrawn one. The lint is **WFG-168** and it does not exist.

**The cheapest test is one grep and it is already written into the row:** WFG-127 (v) now requires
(iii)'s test to cover four surfaces and to ban the Korean spelling in the same commit as the English
one.

---

## The other findings

**F3 · The head of the `todo` block was a P1 infra row again, for the third time in five laps, and
this lap's ONE reorder was spent on it.** At `0cca093` the first `todo` row in table order was P1
infra **WFG-189**, followed by a run of P1 infra rows that §14b holds behind R3, with **six P0
`todo` rows below them** (WFG-127, WFG-128, WFG-129, WFG-106, WFG-101, WFG-054). CHARTER §5 sends a
fresh lap to the first `todo` row in table order, so the table was again pointing at work §14b
forbids. **WFG-127 moved to the head; nothing else moved.** ⚠ Critics #40 and #42 each spent their
one reorder on this identical shape and it recurred both times as soon as the P0 rows above it
closed. The move is correct and it is not the cure; the cure is a gate on the table's own shape,
which is **WFG-183** and **WFG-191**. No fourth row filed: the two that exist say it.

**F4 · WFG-150 is blocked by arithmetic now, not by attention, and paper lap 20 proved it.** That
lap (`6ecc386`) wrote the manuscript's missing caveat, its independent reviewer blocked it, and it
was **reverted rather than argued or shipped** — `paper/manuscript.md` is byte-identical to lap
18's. The correct version is **+50 words against a margin of 6**, and every cheaper shape inverted
the bound, stranded the premise or broke a citation. What unblocks it is **NH-037** (open, due
09-10) or **WFG-116**'s open half. Recorded as a step-5 update to WFG-150; no new row, and no
fifteenth NEEDS_HUMAN entry.

**F5 · 창의성 reached the bank and stopped there.** `grep -cE` over the alternation of 창의 and
독창 answers **2** on `docs/auto/JUDGE_QA.md`, **0** on `web/finals.html`, **0** on
`docs/auto/DEMO_SCRIPT_5MIN.md`. WFG-182 closed correctly on its own scope — a card — but the row is
**20 points on both rubric tables**, the 심사기준 names it first, and the two surfaces a judge is
actually shown still say nothing about it. **WFG-194**, P0, position 3.

---

## The baseline, re-derived rather than read

✅ **ALL GREEN on the routine's DEFAULT clone, measured before any deepening, read unpiped.**
`gates.py --mode full` exits **0** at `0cca093`: `1763 passed, 63 skipped, 2 xfailed`, pytest
**247.9 s**. `verify`, `snapshot-verify`, `env-check` PASS; the `baseline-verify` WARN is the
documented CHARTER §3d sandbox state. **The run downloaded nothing:** `du -sb data/raw` answers
**201,187** bytes before and after and `data/raw/dem/srtm/` holds **0** files. **Cold on the tile,
warm on `data/cache`.** `--assert-head` exits 0; `--assert-reported --base 6d1d730` exits 0 over
**56** substantive paths.

⚠ **The bootstrap needed three attempts again, exactly as critic #43 recorded.**
`scripts/auto/bootstrap.sh` died twice on
`pip._vendor.urllib3.exceptions.ReadTimeoutError` against `files.pythonhosted.org` and succeeded on
the third with no change. `.auto/bootstrap.json` records `pins_ok: true`, `stack_ok: true`. Nothing
in the repository is implicated; it is a slow-network sandbox fact, and it is now on two consecutive
laps rather than one.

⚠ **GitHub's own runs (CHARTER §4b): ONE FINDING, above.** Through the GitHub MCP. `auto-gates` runs
**230 to 253** on `auto/dev`: **19 `success`, 4 `cancelled` (232, 235, 242, 245), 1 `failure`
(253)**. Run 253 is at this exact head.

✅ **Report certification.** Every dev, critic and paper report in the window carries `Reviewed by:`.
The one report without it is `2026-09-08T1132Z-manual.md`, written to satisfy `--assert-reported`
for a `CRITIC_LATEST` correction that carried no build. Critics #42 and #43 both declined to file
it and **this lap declines it too**, for the same reason and not a new one.

✅ **The author's decisions: nothing new, both channels checked.** Gmail,
`from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop" newer_than:14d`: every matching
thread holds exactly **one** message and every one of them is labelled `SENT` — the loop's own
reports arriving back at the same address. `pull_request_read` on PR **#31** returns `[]`.
**No reply to apply**, so `decisions.py apply` was not called and `docs/auto/decisions_seen.json` is
unchanged. Fourteen entries remain open; **NH-032 and NH-034 are now overdue by a day**, NH-035,
NH-038 and NH-043 come due tomorrow, and **NH-046 (due 09-10) is the single reply holding eight P1
infra rows shut.**

---

## What this lap did NOT find, said plainly

- **No red gate on this machine at the reviewed head, and no test failure on either machine.** The
  one red run is an artifact upload, and both machines agree the code is green at `0cca093`.
  ⚠ **My own first commit `dc8fa9f` WAS red** — two `check-number-collisions` hits on prose this lap
  wrote (341.5 s of pytest wall-clock and 1.5 km of buffer width, both read against a registered
  detection time in minutes). Both are genuinely different quantities and both were marked with the
  documented `collision-ok` pragma rather than by changing a number. Caught by CHARTER §4 step 8
  before the push, and written into the report rather than quietly fixed.
- **No fabricated number.** Every figure in this window's new prose is registered or absent by
  design; `make verify` PASS at this head.
- **The screen is nowhere near its staleness limit.** `web/finals.html` carries `"git":"25f6b60"`
  and `git rev-list --count 25f6b60..HEAD` answers **16** against
  `tests/test_finals_screen.py:540`'s limit of **30**. DIRECTION's 「say so at 20 or more」 rule does
  not trigger; I took the number anyway so the next lap need not.
- **The backlog's malformed-row count did not grow: 10 before this lap and 10 after.** ⚠ But I wrote
  **WFG-194 malformed first** — the `grep -cE` alternation put an unescaped pipe in the title cell —
  and had to rewrite the row whole. That is the eleventh instance of **WFG-191**'s defect, committed
  by the lap that was reading WFG-191 at the time, and it is written into WFG-194 rather than hidden.
- **No JUDGE_QA card is added by this lap**, and none may be: the critic routine must not edit a
  printables `SOURCES` file (DIRECTION, WFG-152). The judge drill's finding is F5 and it is a row.
- **No new NEEDS_HUMAN entry.** Nothing this lap found is blocked on the author, and DIRECTION's
  standing rule forbids opening a fifteenth DECISION while fourteen are unanswered.

## The one `Do NOT edit` note, RE-STATED after re-checking (CHARTER §14c, NH-036 A)

**Do not put a margin value — 9, 27, 5, 19, 42, 91 or 86 — into `README.md:220-239`.** That is the
whole of it: two dozen lines, one prohibition. The premise was re-checked rather than inherited:
`docs/auto/NEEDS_HUMAN.md:1391` (NH-032) and `:1524` (NH-034) are both still `open` and both were
due **2026-09-08**, which is today. **It expires at critic #45** unless that lap re-reads those two
entries and re-states it. **It freezes no file and no question:** WFG-127 (iv) must edit
`README.md:232`, and that edit is prose about a **grid**, not about a result.

## The one thing worth copying forward

**The paper lap wrote a correction, was blocked by its own reviewer, and reverted it instead of
arguing or shipping a cheaper version that would have been wrong.** `paper/manuscript.md` is
byte-identical to lap 18's, and the commit message says why in numbers rather than in apology.
CHARTER §7 says a lap that verifies and finds nothing it can honestly ship reports exactly that.
That is the second time this window a reviewer's block held — the 1518Z lap's did too, at
`e428468` — and it is the reason this repository's claims are worth reading.
