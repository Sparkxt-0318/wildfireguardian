# CRITIC_LATEST — critic #43, 2026-09-08T1429Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head:
`dee1bc1`. Window: the 24 h to 2026-09-08T14:29Z. ⚠ **This clone is shallow:**
`git rev-parse --is-shallow-repository` = **true** and `git rev-list --count HEAD` = **50**, and
the oldest resolvable commit is `7cc4eb7` at 16:12Z on 09-07, so this clone reads about 22 hours
and I make no claim about anything older and **no ancestry or reachability claim at all**
(DIRECTION's standing rule). Full report: `docs/auto/reports/2026-09-08T1429Z-critic.md`.*

## The one thing to read first: **a readiness line ticked.** R8 is green.

**`KCF_READINESS.md` moves 7 of 11 to 8 of 11, and the zero-tick streak ends at three critic
laps.** Measured here at `dee1bc1`, not read:

- `grep -nE '^## Round' README.md` answers `:59`, `:75` and **`:200`**, where for a week it
  answered only `:59` and `:75`.
- `grep -n '^### Abstract' README.md` answers **`:596`**.
- `make check-forbidden` exits **0**; `make verify` PASS inside the full gate run.

That is all three halves of R8's condition. The row is ticked in `KCF_READINESS.md` with those
three commands as its evidence. **WFG-187 also closed:** `web/finals.html` carries
`"git":"25f6b60"` and `git rev-list --count 25f6b60..HEAD` answers **9** against
`tests/test_finals_screen.py:540`'s limit of **30**, where critic #42 measured 29.

Two judge-facing rows landed in one window and the product's own definition of done moved. Said
plainly because the last three critic laps could not say it.

---

## `fix-before-next-row` — ONE item: **WFG-190**. It is two sentences in the section that just
## ticked R8, and no test binds either of them.

**The Round-4 section this window put on the front door is the weakest of the four surfaces that
carry the same fact, and one of its sentences is a flat universal the repository contradicts.**

Measured here at `dee1bc1`, every command read unpiped. Both defects sit in one paragraph block,
`README.md:220-239`.

**(a) `README.md:235-239` states a universal that `docs/auto/JUDGE_QA.md` falsifies.** The line
reads 「이 실험이 내놓은 **구체적인 margin 값들은 아직 어느 심사용 자료에도 싣지 않습니다.**」
`docs/auto/JUDGE_QA.md:849-852` carries **9**, **27** and **5** in one paragraph, and
`docs/auto/finals/printables/manifest_20260908T0939Z.json` lists that file with the title
「심사위원 질의응답 카드」 among the six documents bound into the **41-page** printed booth kit.
So a document whose own title contains 심사위원 carries all three values, on paper, today.
⚠ **The card is not wrong and must not be changed:** its block ends with an explicit
❌ forbidding the student from speaking 9, 27 or 5 at the booth, which is exactly the discipline
NH-032 and NH-034 are waiting on. **The README sentence is what is wrong**, because
「심사용 자료」 is defined nowhere in this repository and the sentence is the WC-009 class the
loop registered on 2026-09-07: never a flat sentence about what a document contains.

**(b) `README.md:220-225` states a buffer-conditional result unconditionally, and the project's
own manuscript does not.** The line reads 「지금 타고 있는 영역에 **고정 완충거리**를 더해
거부하는 경로계획」 and then 「fire-blind 대비가 예보의 공으로 돌리던 것의 **상당 부분을** …
이미 회수합니다」. Three other surfaces carry the condition this one drops:

| surface | what it says about the buffer |
|---|---|
| `paper/manuscript.md:493` | 「The buffer width is a second free parameter and nothing in the data chooses it.」 |
| `docs/present_perimeter_arm.md:116` | section title: 「Why 1 km is not a constant, and why that matters more than the 9」 |
| `docs/auto/JUDGE_QA.md:1346` (Q37 · T1) | five widths swept; 「1 km 의 양옆 이웃이 각각 두 배 거리에 있어서 … 이 sweep 으로는 구분할 수 없습니다」 |
| **`README.md:220-225`** | **the width is not named, and the sweep is not mentioned** |

And the strength is understated in both languages. `docs/present_perimeter_arm.md:103-104`
measures that the opponent recovers **86 of the 91**, and the same document's table at `:121`
gives **12 of 91** at 250 m and **23 of 91** at 500 m, with **91** origins walking into the fire
at 250 m. 「상당 부분」 and the English abstract's 「recovers most」 (`README.md:629`,
`paper/manuscript.md:23`) are both true and both weaker than 86 of 91, on a result the section's
own header promises reads **against** this project.

**Why this qualifies under §14b as amended by NH-038 B.** `README.md` opening is the first
surface §14b's own list names. `grep -nE '상당 부분|회수|recovers most|완충' tests/test_readme_round4.py`
returns **nothing**, so neither sentence is bound by a test and the fix is prose alone.

**Done when:** (a) the 「어느 심사용 자료에도」 sentence names the set it means (screen, panels,
submitted documents) and says that the Q&A bank carries the values only in the
「말하지 말 것」 form; (b) the paragraph names the buffer width as a free parameter that the data
did not choose and points at `docs/present_perimeter_arm.md` §4; and `gates.py --mode full`
exits 0 on the commit actually pushed.
⚠ **Do NOT add a margin value or a new figure to `README.md` while NH-032 and NH-034 are open.**
The fix is qualitative. 「1 km」 is a method parameter already in `docs/present_perimeter_arm.md`
and `paper/manuscript.md`; a *result* number is not to be written here.

**Then take the table: WFG-188 is position 1** and it got there by fall-through, not by a move.

---

## The other findings

**F2 · The backlog table does not parse as the table CHARTER §5 defines, in 11 rows of 187, and the
worst of them is at the head of the `todo` block.** Splitting each backlog row on the pipe
character, **11 of the 187** `WFG-` rows yield something other than the 9 columns §5 names:
WFG-112, WFG-115, WFG-133, WFG-149, WFG-167, WFG-168, WFG-175, WFG-181, WFG-182, WFG-188 and (as
first written by this lap) WFG-191, from 11 fields to 19. The cause every time is an unescaped
pipe inside a quoted `grep` alternation or a regex in the title cell. WFG-188 is the one that
matters now: its column 5, which §5 defines as `status`, reads **「예산」**, its real `todo` sits
in column 9, and `goal`, `agent_doable`, `effort` and `rubric rows` are each shifted by four.
**The next dev lap is about to take that row; read its status from the prose, not the column.**

⚠ **I filed this row and then committed the same defect three times inside five minutes.** Both
of my new rows first went in malformed (13 and 17 fields), and my first repair appended text into
the middle of a sentence because the row was already split. WFG-191 had to be rewritten whole.
That is not an aside: it is the evidence that a convention cannot hold this invariant and a gate
must, and it is written into the row. Filed as **WFG-191**, P1 under §14b because the backlog is
loop machinery. **The ten pre-existing rows are left as they are** and are the row's own work;
this lap repaired only what it broke.

**F3 · `WFG-179` is `todo` with `agent_doable: true`, and its own escalation says a lap may not
do it.** The row's *Done when* cell ends 「whichever the author picks in NH-046」, and
`docs/auto/NEEDS_HUMAN.md`'s NH-046 says in the author's-reasons section: 「A lap that edits a
readiness line to match what the loop already does is a lap grading its own homework」. A `todo`
row a lap is forbidden to finish is the `in-progress`-with-no-key shape from CHARTER §5b, one
column over. **Status changed to `blocked(NH-046)` by this lap** as a step-5 update to an
existing row. Nothing was reordered to do it.

**F4 · With R8 ticked, `R3` is the last of §14b's six lines, and it is the author's, not a
lap's.** §14b holds the P1 infra block until R1, R3, R4, R7, R8 and R9 are ticked. R1, R4, R7
and R9 were ticked before this window, R8 ticks today, and **R3 is the only one left**. R3's row
is WFG-179, which F3 has just established is blocked on **NH-046, due 2026-09-10**. So eight P1
infra rows now wait on one email reply. This is written into NH-046 rather than into a new
entry.

---

## The baseline, re-derived rather than read

✅ **ALL GREEN on the routine's DEFAULT clone, measured before any deepening, read unpiped.**
`gates.py --mode full` exits **0** at `dee1bc1`: `1749 passed, 63 skipped, 2 xfailed`, pytest
**312.3 s**. `verify`, `snapshot-verify`, `env-check` PASS; the `baseline-verify` WARN is the
documented CHARTER §3d sandbox state. **The run downloaded nothing:** `du -sb data/raw` answers
**201,187** bytes and `data/raw/dem/srtm/` holds **0** files afterwards. **Cold on the tile,
warm on `data/cache`.** `--assert-head` exits 0; `--assert-reported --base 7cc4eb7` exits 0 over
61 substantive paths.

⚠ **The bootstrap needed three attempts and that is worth recording.** `scripts/auto/bootstrap.sh`
died twice on `pip._vendor.urllib3.exceptions.ReadTimeoutError` against `files.pythonhosted.org`
before `PIP_DEFAULT_TIMEOUT=300 PIP_RETRIES=15` carried it through. `.auto/bootstrap.json` records
`pins_ok: true`, `stack_ok: true`. Nothing in the repository is implicated; it is a slow-network
sandbox fact a later lap may meet, and the two variables above are the whole remedy.

✅ **GitHub's own runs (CHARTER §4b): no finding.** Through the GitHub MCP; `curl` against
`api.github.com` is still refused in this sandbox (WFG-119). `auto-gates` runs **230 to 249** on
`auto/dev`: **16 `success`, 4 `cancelled` (232, 235, 242, 245), ZERO `failure`.** Run **249** at
this exact head is `success`. No red run sits behind a green report.

✅ **Report certification.** Every dev and critic report in the window carries `Reviewed by:`.
The one report without it is `2026-09-08T1132Z-manual.md`, written to satisfy
`--assert-reported` for a `CRITIC_LATEST` correction that carried no build; that is the same
case critic #42 declined to file and this lap declines it too.

✅ **The author's decisions: nothing new.** Gmail returned `The service is currently unavailable`
once and then answered. Every thread matching `from:siyeong0318@gmail.com subject:"WildfireGuardian
autoloop" newer_than:14d` holds exactly **one** message and every one of them is `SENT` by the
loop itself. `pull_request_read` on PR **#31** returns `[]`. **No reply to apply**, so
`decisions_seen.json` is unchanged. Fourteen entries remain open; NH-032 and NH-034 are two days
overdue and NH-035, NH-038 and NH-043 come due tomorrow.

---

## The root objection

**The loop keeps writing the weakest version of its own honesty on the surface a judge meets
first, and the strongest version in the file nobody opens at a booth.**

Measured, not felt. On the buffer's freedom: `paper/manuscript.md:493` states it outright,
`docs/present_perimeter_arm.md:116` gives it a section heading and says it 「matters more than the
9」, `docs/auto/JUDGE_QA.md:1346` sweeps five widths and names what the sweep cannot resolve, and
`README.md:220-225`, written this window and last of the four, says none of it. On what the
opponent recovers: the artifact says **86 of 91**, the manuscript and the README both say
「most」/「상당 부분」. On where the margins live: the README says 「어느 심사용 자료에도」 and the
printed 41-page kit carries all three.

This is not the same complaint as critic #42's. Critic #42 said the loop kept fixing the same
file; this window it fixed two different judge-facing surfaces and ticked a readiness line, so
that objection is answered. The new one is about **direction of travel inside a document**: every
time this repository restates a hard fact for a wider audience, the restatement comes out softer,
and nothing in the loop measures that. `docs/withdrawn_claims.json` catches a **withdrawn** claim
being copied forward; it does not catch a **standing** claim being weakened on its way to the
front door.

**The cheapest test, and it fits in one lap:** for each of the three unfavourable results the
README's Round-4 section promises (present-perimeter recovery, dispatch ordering, detection
floor), diff the README's sentence against the source document's own strongest sentence and say
which is weaker. Two of the three were checked here and both were weaker on the README. That is
the shape of a gate, and **WFG-192** files it as a P1 row rather than a claim.

## What this lap did NOT find, said plainly

- **No red gate, on this machine or on GitHub.** Both channels checked, unpiped.
- **No fabricated number.** Every figure in this window's new README prose is either registered
  (the abstract's `0.890`, `0.905`, `0.138`, `42 of 458`, `2`, `32.6 %` all survive `make verify`
  at this head) or absent by design.
- **No JUDGE_QA card is added by this lap.** The judge drill's one gap, 「what would a county
  need to run this」, is already **WFG-188** at position 1 and I confirmed it rather than
  duplicating it: `grep -nE '군청|도입 비용|운영 비용|유지보수' docs/auto/JUDGE_QA.md` returns
  **2** lines and neither answers the question (`:703` is about legal status, `:851` is a passing
  clause). Adding a card here would make the 41-page kit stale on a lap that cannot rebuild it.
- **R11 re-checked and it is still correctly unticked, for the reason already on file.**
  `docs/HANDOFF_ROUND3.md:898` still reads 「All work stays on `round3-dev`」 inside §5, which
  contradicts CHARTER §3.1. That is **WFG-024**, blocked on WFG-023, and named in R11's own
  evidence cell. No new row.
- **No `Do NOT edit` note is written by this lap** (CHARTER §14c, NH-036 A). WFG-190 must edit
  `README.md:220-239` and WFG-188 must edit `docs/auto/JUDGE_QA.md`; freezing either would block
  the work. The single prohibition above is scoped to two lines and one clause: do not put a
  margin value into `README.md` while NH-032 and NH-034 are open, and it expires at critic #44
  unless that lap re-states it after re-reading NH-032 and NH-034.

## The one thing worth copying forward

**The 1303Z lap wrote the section that ticked R8 and made three of its four items arguments
against this project, in Korean, on the front door.** `README.md:207-208` says so out loud:
「이 절에서 이 프로젝트에 **유리한** 항목은 4번뿐입니다.」 A README that tells the reader which
of its own paragraphs cut against it is the rarest thing in this repository and it is worth
keeping when the next lap edits the two sentences above. **Fix the scope, keep the register.**
