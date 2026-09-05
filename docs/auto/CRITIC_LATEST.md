# CRITIC_LATEST — critic #21, 2026-09-05

Window `3efd0db..492364c` on `auto/dev`. **One commit, one changed line** — the status cell of one
backlog row. Written by the `wfg-autoloop-critic` routine. Gates re-run here: ALL GREEN at `492364c`
(`1515 passed, 62 skipped`, cold), `--assert-head` and all 44 push pairs of the last 24 h pass
`--assert-reported`, `auto-gates` runs 131 to 139 carry no `failure`.

## Before you claim a row: WFG-114 may be a lock with no key

`docs/auto/BACKLOG.md` shows **WFG-114 `in-progress(20260905T1820Z)`** — the author's own NH-027 row.
The lap that claimed it pushed `492364c` at 18:20Z and nothing since; at 20:10Z there was no artifact
under `data/processed/` and `git log --all --grep=WFG-114` found only the claim. I did **not** release
it: at that moment the lap was still inside CHARTER §4's two-hour box, and releasing a live claim is
the NH-007 failure.

**So the first thing you do is decide whether it is stale, using CHARTER §5 rather than judgement:**

1. `git fetch origin && git log origin/auto/dev --oneline -5`.
2. If a WFG-114 work commit has landed, nothing here applies — read the item below and carry on.
3. If WFG-114 is still `in-progress(20260905T1820Z)` with no work commit behind it, the claiming lap
   has ended. CHARTER §5: 「A lap that ends without finishing its row sets the row back to `todo`」 and
   「`in-progress` written by a lap that has ended is a lock with no key」. **Set it back to `todo` with
   a residue note naming the dead stamp, push that alone, and then claim it yourself.** It is the
   author's own row, it is first on `docs/auto/DIRECTION.md`, and it answers the objection four
   consecutive critics have written down. Do not step over it to reach the item below.

**NH-030** is open on this for the author. Do not close it; it asks them something the loop cannot
answer (whether the routine run failed).

## fix-before-next-row

**One item, and it is a judge-facing surface under CHARTER §14b: WFG-117.**

`docs/auto/JUDGE_QA.md` Q30 is **T0** — 「그러면 오늘의 숫자는 왜 믿습니까?」, the question this
project's whole credibility case answers — and the drafted answer has the student say:

> 등록된 값 **295**개 중 **261**개가 커밋된 아티팩트에서 `make verify`로 다시 계산되고, 나머지
> **34**개는 「확인됨, 재현 불가」로 라벨이 붙어 있습니다. **16**개는 ... OSM ... **18**개는 ...

Counted from the file this lap, not read from a report:

```
docs/NUMBERS.json  numbers                      -> 326 entries
                   reproducible: true           -> 268
                   reproducible: false          ->  58
web/finals.html    registry.n_entries           -> 326
                   registry.n_reproducible      -> 268
```

All three spoken figures are stale, and the 16 + 18 decomposition accounts for 34 of 58. The 검증
레지스트리 card **on the screen behind the student** prints 326 · 268, so a judge who looks up hears
one number and sees another, on the highest drill tier. Nothing gates it: `tests/test_judge_qa_bank.py`
contains no check that reads a registry count, which is how they drifted 31 apart. This is the WFG-057
failure shape in a worse place.

I have already put a ⚠ 근거 없음 note on Q30 so nobody rehearses the numbers before you close this.

**Done when:** Q30 states counts a test derives from `docs/NUMBERS.json` at run time (or states no count
and points at the card); the non-reproducible decomposition is recounted against the 58 or withdrawn in
writing; and a test in `tests/test_judge_qa_bank.py` goes red **both** ways — edit a digit in the bank,
and flip one entry's `reproducible` flag in a scratch copy of the registry. Grade it, do not assert it.

## Findings, ranked

**F1 · NH-030 · the loop · the dev slot produced no work, on the author's own row.** Detailed above.
This is the first slot in the sprint with no work in it, and it reframes six laps of stalled readiness:
critic #18 blamed the queue, #19 blamed the queue, #20 blamed the direction page, and this window rules
all three out — the page named the right row, the lap took it, nothing came out. **Critic #20's
falsifiable test is half-resolved and it resolved for the page.**

**F2 · WFG-117 · judge-facing · P0 ·** the `fix-before-next-row` item above.

**F3 · WFG-119 · the loop's own instruments · P1 (parked by §14b) · every ancestry claim four critic
laps have made was measured in a depth-50 shallow clone, and none of them said so.**
`git rev-parse --is-shallow-repository` → `true`; `git rev-list --count HEAD` → **50**.
`git merge-base --is-ancestor` cannot answer across a shallow boundary, and it is the instrument behind
WFG-067's gate (`tests/test_finals_screen.py:523`, `:550`, `:649`) and behind every 「not reachable from
HEAD」 finding, WFG-115 included. **So I removed the confounder before trusting the finding:**
`git fetch --deepen=120` (170 commits), then re-ran it. `41498ef` is **still** not an ancestor and is
still on `origin/auto/lap-b1989d5-superseded` and `origin/ordering-boundary` only. **WFG-115 stands.**
The predicted failure, not yet observed, is the mirror image of CHARTER §4b: the screen's stamp
`5f9a3b8` is 7 commits behind `HEAD`, the branch moves on the order of 40 commits a day, and once a
stamp ages past 50 commits the ancestry test goes **RED in every sandbox while staying GREEN in CI**,
which checks out at `fetch-depth: 0`. A red only the sandbox sees would be read as a real defect.
⚠ Same row: this routine's own step-2 command, `curl .../actions/runs`, now returns **403**
「GitHub access is not enabled for this session」. The runs must be read through the GitHub MCP.

**F4 · WFG-118 · the loop · P1 (parked by §14b) · the tail of the backlog table is in filing order, so
the charter's own fallback would take a P1 infra row before three P0 judge-facing ones.** Measured by
parsing the table at `492364c`: `todo` P1 WFG-107 (pos 22) and WFG-108 (23) sat above `todo` P0
WFG-110 (25), WFG-113 (28) and WFG-115 (29), with P1 WFG-111 and WFG-112 interleaved. CHARTER §5 says
the dev lap takes the first `todo` row in table order; CHARTER §14 forbids a P0 below a non-P0. Latent
only because `DIRECTION.md` names the next rows — and #20's own finding is that the page can go stale
for a full lap. **I moved WFG-115 above the P1 block. That was this lap's entire reorder budget**, and
WFG-110 and WFG-113 are still below P1 rows, which is why WFG-118 exists.

**F5 · verified rather than repeated.** Things earlier laps claimed, re-run here: `make baseline-verify`
reports **2** differences against `944243054a59`, both the git-ignored `data/raw/firms_data/` manifests
(the author's NH-029 re-freeze holds, critic #20's reading confirmed); `make finals-bundle` exits 0 with
`OK — release/kcf-finals-2026/ rebuilt byte-identically, 17 files`; `docs/auto/finals/` holds no PDF on
the **sixth** day (R7 / WFG-007); `JUDGE_QA.md`'s self-count is correct (41 questions, 15 / 19 / 7,
re-counted); every dev, paper and critic report of the last 24 h carries `Reviewed by:` and the five
without it are `manual`, the author's own laptop.

## Not findings

- **No `factchk` finding, and no prose to check.** The window added one backlog status cell. No claim
  about the world entered the tree, so there is nothing this lap could verify or withdraw.
- **No scorecard movement from anything built**, because nothing was built. B 83 → 82 and A 78 → 77
  are one defect (WFG-117) scored once per track, on a tree that did not change.

## Root objection (`hate`, on the current headline narrative)

**The headline still has no fair opponent, and for the fourth consecutive critic lap the only scheduled
answer to that is a row with nothing behind it.** The demo's strongest sentence compares survival-aware
routing against an arm that cannot see the fire. The author saw this and personally promoted the fix
into the sprint (NH-027 option A, 「report the number whatever it says」). It is WFG-114. It has been
claimed for two hours and has produced nothing.

**Cheapest test, for the next lap and it is one command:** `git log --all --grep=WFG-114 --stat`. If
that shows a work commit, the objection is being answered and the loop is fine. If it shows only the
claim and critic reports, then the single most important experiment in this project is being held by a
status cell, and releasing that cell is worth more than anything else either of us could build today.
