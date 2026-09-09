# CRITIC_LATEST — critic #48, 2026-09-09T0526Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `5f4e32b`;
**every measurement below was then RE-TAKEN at `7e222c2`** after the WFG-194 lap landed under this lap and
its push rebase, so nothing here is quoted from the tree it was written on. That landing changed two of this
lap's findings and both are corrected in place rather than left standing; the WFG-206 id this lap first used
was taken by that lap and its two rows are renumbered **WFG-208** and **WFG-209**.
⚠ **This clone opened SHALLOW at 50 commits**, reading back only to 2026-09-08T10:20Z, which would have
hidden half of my window. I deepened it with `git fetch --shallow-since='2026-09-08T00:00:00Z'` to **73**
commits, oldest resolvable `088203c` at **00:29:26Z on 09-08** — a deepening whose predicate is **the window
itself**, not a guessed number. `--is-shallow-repository` still answers **true**, so **no ancestry or
reachability claim appears anywhere below.** Full report: `docs/auto/reports/2026-09-09T0526Z-critic.md`.*

## `fix-before-next-row` — ONE item, minutes: **WFG-208**

**Put the repository's address on the USB.** `release/kcf-finals-2026/README_KO.md` cites **15** repository
paths in backticks; **7** of them exist in the tree and are **not** in the 19-file bundle
(`docs/auto/DEMO_SCRIPT_5MIN.md`, `docs/auto/JUDGE_QA.md`, `docs/auto/NEEDS_HUMAN.md`,
`docs/auto/finals/BOOTH_SETUP.md`, `docs/auto/finals/RELATED_WORK_PANEL.md`, `docs/finals_bundle.md`,
`docs/related_work.md`), and a count of `github.com` in that file answers **0**. The printed kit riding in
the same folder is the same shape at scale: `docs/auto/JUDGE_QA.md` cites **105** repository paths, **102**
exist, and **3** are inside the bundle. On the student's own booth laptop every one resolves, because
BOOTH_SETUP §1 has the full clone there. The USB is the copy a judge can carry away, and on it they do not,
with no address at which to look.

**Done when:** `README_KO.md` says in one sentence that backticked paths are paths **in the repository, not
in this folder**, gives the repository URL once, and `make finals-bundle UPDATE=1` plus the manifest is
committed so `make finals-bundle` and `check_bundle_copy.py` both stay green. `README_KO.md` is in
`scripts/build_finals_bundle.py`'s `AUTHORED` tuple, so it is edited in place and not generated.
⚠ **Do NOT add the seven documents to the bundle.** That widens the payload and the freeze; the fix is a
sentence and a URL. This is minutes on a §14b judge-facing surface (the release bundle), which is the whole
of what makes it eligible to displace the top row.

**Then take WFG-207, then WFG-027, then WFG-125.** ⚠ **WFG-194 closed under this lap** (`b451376`) and is not
in that list. **WFG-207 is new and sits at table position 1**; **WFG-027 was promoted to P0 and moved above
WFG-125 by this lap**; `docs/auto/DIRECTION.md` says the same three in the same order, so no further
instruction is needed to reconcile the table and the page.

## Everything else that is eligible under §14b is green, re-run rather than read

`gates.py --mode full` exits **0** at `5f4e32b` (`1806 passed, 63 skipped, 2 xfailed`, pytest 273.2 s) and
again on this lap's own commit after the rebase onto `7e222c2`. `baseline-verify` WARNs on the two
`data/raw/**` contracts that are git-ignored and cannot exist in any sandbox, which is NH-029/§3d working as
designed. **GitHub `auto-gates` runs 263 to 274 are every one `success`**, including **273** at `5f4e32b` and
**274** at `7e222c2`, so **there is no finding #1**. All dev reports in the window carry `Reviewed by:`,
`gates.py --assert-reported --base 86f8929` exits 0, and `make finals-bundle` rebuilds byte-identically at
19 files. The malformed-row count in `docs/auto/BACKLOG.md` is **11**, all pre-existing: this lap added three
rows and edited two and broke none, which is the WFG-191 invariant that critics #44 and #47 both broke.

---

## F1. The root objection: **the loop is asking the author for decisions the author appears to have already made, and the rule this routine obeys is not in the charter it cites**

The stored prompt that starts this routine binds it, by name, to two rules:

- 「CHARTER §14b the product-first rule ... (product first, **as amended 2026-09-07 by NH-038 B**)」, then
  states option B's content: an item must be **minutes**, anything larger is a P0 row at position 1 and
  never a preemption.
- 「CHARTER **§14c** how a `Do NOT edit` note must be written ... (CHARTER §14c, **NH-036 A**)」, then states
  option A's content: the note names the exact lines and the measurement, and expires at the next critic lap.

Measured at `5f4e32b`:

| what the prompt says | what this repository says |
|---|---|
| §14b amended 2026-09-07 by NH-038 B | `docs/auto/CHARTER.md` §14b is the unamended 2026-09-04 text, capping the **number** of items and not their **cost** |
| CHARTER §14c exists | a search for `14c` in `docs/auto/CHARTER.md` answers **0**. There is no §14c |
| NH-036 A and NH-038 B are decided | `NEEDS_HUMAN.md:1779` has NH-036 `open`; `:1966` has NH-038 `open` |
| the decisions are registered | `docs/auto/decisions_seen.json` stops at **NH-031** |

**Cheapest test, ten seconds, already run:** grep the charter for its own section number.

**Why it matters more than bookkeeping.** The divergence is operational. Under the charter's text a critic
may set one judge-facing item of **any size** and the dev lap must clear it before claiming a row; under the
prompt's text that item must be **minutes**. Those are two different loops, and which one runs depends on
which document the lap happens to read. Six lap outputs already cite 「CHARTER §14c」 as authority
(`CRITIC_LATEST.md`, `DIRECTION.md`, and four places in `KCF_READINESS.md`), and a reader who opens the
charter to check finds nothing. Meanwhile every report email since 2026-09-07 has re-asked NH-036 and
NH-038 inside a list of fifteen, which is where NH-032 and NH-034 — two days overdue, and the reason the
student is still forbidden to say any margin out loud — are going to get lost.

**A third thing it exposes.** `docs/auto/ROUTINE_PROMPTS.md:56`, which CHARTER §9 says keeps the prompts
「recorded verbatim」, still carries the **pre-amendment** critic prompt and names a 「2026-10-10 freeze」
that CHARTER §1 puts at **2026-10-16**. No gate reads that file.

**What this lap did NOT do.** It did not close NH-036 or NH-038. CHARTER §6 names three channels for the
author's decisions — an email reply, a PR comment on #31, a Claude Code session on the laptop — and the
routine page is not one of them. Registering a decision the author did not make is worse than asking once
more. → **NH-050** (three options, one line to answer) and **WFG-209**, filed `blocked(NH-050)`.

## F2. 창의성 is at zero on a fourth surface, and it is the front door

⚠ **This finding was written against `5f4e32b`, where all three of WFG-194's surfaces were at zero, and
WFG-194 then landed and fixed all three while this lap was writing. It is re-taken at `7e222c2` rather than
withdrawn, because the half that survives is the half that matters.** Raw count of 창의 or 독창 at
`7e222c2`: `web/finals.html` **3**, `docs/auto/DEMO_SCRIPT_5MIN.md` **10**, `docs/auto/JUDGE_QA.md` **3**,
`docs/creativity_card.md` **24**, and ⚠ **`README.md` 0**.

So WFG-194 delivered every surface it named, plus the printed kit, and closed correctly. **The README was
never in its scope**, and the README is the page a judge browses before the booth and the one this loop spent
a whole window writing a Round-4 section into. 창의성 is **20 points on both tables** and the 심사기준 names
it **first**. That residue is **WFG-207**, filed at table position 1, and it is a row rather than a
preemption because a README section is not minutes and this lap's one item is already spent on WFG-208.

**What this lap got wrong and is recording rather than quietly dropping:** it read the tree at 04:58Z, found
WFG-194 `in-progress(20260909T0321Z)` and 97 minutes old, correctly left it alone under CHARTER §5b, and then
wrote 「add README.md to that row's surfaces before closing it」 into a row that closed twenty minutes later.
A note addressed to an in-flight lap is a note that may arrive after the lap has ended. The durable form is a
row of its own, which is what WFG-207 is.

## F3. 일정 is at literal zero on every surface a judge meets, and it is a named sub-item of a 20-point row on both tables

This is this lap's ONE §3b reorder: **WFG-027 promoted to P0 and moved above WFG-125.** 설계와 방법론 lists
「일정 및 팀원(개인의 경우 제외) 역할 배분의 타당성」; for a solo entrant the 심사기준's own text excludes
the 팀원 half and not the 일정 half. Re-measured at this head, unpiped, on the raw count of the string 일정:
**0** on `README.md`, **0** on `web/finals.html`, **0** on `docs/auto/JUDGE_QA.md`, **1** on
`docs/auto/DEMO_SCRIPT_5MIN.md`, and that hit is line **70**, 「2 km 화소는 일정 크기 아래의」, the adjective.
로드맵 and 개발과정 answer zero on all four; 타임라인 occurs **once**, at `web/finals.html:463`, and it is the
UI hint 「아래 타임라인으로 시각을 움직여 보십시오」 for the fire-time slider, not a schedule. 계획 occurs 2 / 3 / 6 times on the
README, the script and the bank, and **not one of the eleven is a development schedule** — I read all eleven:
they are 경로계획 and 「위험면 위에서 계획하므로」 (route planning), 「군청이 실제로 쓸 계획」 and 「지금
불난 자리만 아는 계획」 (the opponent's planner), 「기관의 계획 발표」 twice (an agency's announcement),
「그렇게 만들 계획도 없습니다」 (a plan not held), and 연구 계획서 (a research proposal document).

Critics #45 and #47 both measured this and neither could act, because a priority change is not a position
change and §3b permits one act. It is one act: promote and move together. The answer already exists in
CHARTER §1 and §11 plus `git log`, and it is a larger scoring hole for less work than the row it displaced.

## F4. NH-049's premise is confirmed at the code, so this lap filed rows and no cards

`tests/test_printables.py:329-354` re-hashes all six `SOURCES` of the newest printable against the tree and
`assert`s no drift; `docs/auto/JUDGE_QA.md` is one of the six. A critic lap may not rebuild the PDF (「you
change NO code and NO artifact」), so **any** edit to the bank turns the gate red. The routine prompt's
「JUDGE_QA additions」 clause is therefore unexecutable as written, exactly as critic #47 filed it. The
judge-drill question this lap could not answer from any file — 「어떤 일정으로 개발했습니까?」, which the
심사기준 asks for by name — is therefore **WFG-027**, not a card. No duplicate entry was filed.

## F5. The scoring: no row moves on either track, and that is the window and not a courtesy

`86f8929..5f4e32b` holds one paper lap (`4b0010a`) and three commits repairing a report header; the one dev
lap in it is a bare claim whose work had not landed. Nothing a KCF judge meets changed. Track B holds at
**92** (18 / 19 / 20 / 16 / 19), Track A at **91** (19 / 19 / 20 / 16 / 17). The two zeros in F2 and F3 are
**already priced into** 설계와 방법론 19 and 창의성 16 and are not new information, so they are neither a
deduction nor a raise. 제출 자료 is **held rather than docked** for WFG-208: seven dead pointers on the USB's
front page is real 출처 명기 debt, and it is worth less than a point against a window whose 29 manuscript
references every one carry a note recording what was actually opened and what it does not say. **If WFG-208
is still open at critic #49, it becomes a deduction.**

⚠ **What this lap looked for and did not find.** No fabricated number, no unsourced world claim, and no
citation without a `verified` note (29 of 29 in `paper/references.bib`). The README's opening paragraph about
the 2025 fire was not touched and is not disputed here.

---

## ⚠ The one `Do NOT edit` note, RE-STATED after re-checking its premise, with its line range CORRECTED (CHARTER §14c, NH-036 A)

Critic #47 wrote this note over `README.md:220-247`. Measured here, the Round-4 fair-opponent block runs
**`README.md:210-282`** (「### 1.」 at line 210, 「### 2.」 at line 283), so the inherited range covered about
a third of what the note is about. **That drift is what a line-numbered note does the moment the file is
edited, and it is worth knowing before §14c's line-naming requirement is read as a guarantee.**

The note forbids exactly one thing over **`README.md:210-282`**: putting a present-perimeter **margin value**
(9, 27, 5, 19, 86) into those lines while NH-032 and NH-034 are open. I re-read both entries rather than
inheriting the claim: `NEEDS_HUMAN.md:1391` and `:1574` both still say `open`, both are now two days overdue,
and a scan of 210-282 finds no margin value there today.

**It expires at critic #49 unless that lap re-states it after re-reading NH-032 and NH-034.** It freezes no
file and no question: those lines were rewritten twice this week, and that is the kind of edit it permits.

## ⚠ Candidate for critic #49, so it need not re-derive it

**WFG-197** is the remaining promotion candidate and it is the same shape WFG-027 was: a judge-facing answer
that exists in a research note and on no surface a judge meets. It needs a priority change **plus** a move,
which is one §3b act.
