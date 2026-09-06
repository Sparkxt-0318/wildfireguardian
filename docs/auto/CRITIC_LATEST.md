# CRITIC_LATEST — critic #27, 2026-09-06T1400Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `dd500e6`. Window: `b2bdaf0..dd500e6`, plus the
24 h to 2026-09-05T14:00Z for the gate, CI and report checks.*

## fix-before-next-row (exactly one, CHARTER §14b)

**WFG-133 — `docs/auto/JUDGE_QA.md` Q35's ⚠ block scripts the student to say a false sentence to a judge,
and critic #26 forbade editing it.**

Q35 is **T1** and is the reproducibility question: 「화면 아래 적힌 커밋을 받아서 이 화면을 그대로 다시
만들 수 있습니까?」. Its draft answer says the stamp is 「현재 브랜치에서 닿는 커밋입니다」, which is
**true**. Its ⚠ block then tells the student not to say that, and to say this instead:

> 「레지스트리 카드의 각인은 레지스트리를 마지막으로 생성한 시점의 것이고 **지금 브랜치에서 닿지
> 않습니다**.」

Measured at `dd500e6` on a clone **fully unshallowed** — `git rev-parse --is-shallow-repository` answers
`false`, 488 commits, so the instrument that produced five earlier false readings is not in play:

| the block says | the truth at `dd500e6`, measured here |
|---|---|
| `git merge-base --is-ancestor 41498ef HEAD` exits non-zero | it exits **0** |
| `git branch -a --contains` finds it only on two superseded branches | it names **`auto/dev`, `origin/auto/dev`, `origin/Main`** |
| (unstated) | `git rev-list --count 41498ef..HEAD` = **283** |
| the card beside it prints **326** | it prints **383** (WFG-113, `1ec1d06`) |

Critic #26 withdrew this measurement at 1100Z into `CRITIC_LATEST.md`, `KCF_READINESS.md` R1 and
`DIRECTION.md`, and in the same lap wrote **「`JUDGE_QA.md` Q35 is correct as written and must not be
edited」**. That sentence is true of Q35's **draft answer** and false of the **⚠ block** that overrides it.
Its effect was to shield the false half from repair for a full window, on the one file a human reads aloud.

⚠ **Critic #26's 「must not be edited」 is lifted for the ⚠ block only. The draft answer above it is correct
and stays.** A dated ⚠⚠ correction note with the table above is already on Q35 at this head, so nobody
rehearses the false block tonight; the row's job is to make the card itself true and to gate it. The
done-when is on the row.

## What this lap verified rather than read

- `gates.py --mode full` **ALL GREEN** at `dd500e6`: `1569 passed, 62 skipped`, cold, 304.3 s
  (critic #26: `1565 / 62` — **+4 passed**, skips unchanged). `verify`, `snapshot-verify`, `env-check`
  PASS; `baseline-verify` WARN is CHARTER §3d information.
- **No red CI run behind a green report, so no CHARTER §4b finding.** Read through the GitHub MCP (the
  routine's `curl` returns 403, WFG-119): `auto-gates` runs **145 to 173** on `auto/dev` are **22
  `success` and 3 `cancelled`** (`828bbae`, `ef61e9b`, `9ebf5a5`, each superseded by a green push). Run
  173 at `dd500e6`, this head, is `success`. **Zero `failure`.**
- `--assert-head` and `--assert-reported` both exit 0. Every **dev** report in the window carries
  `Reviewed by:` (the 1313Z lap's says `subagent (block)`, and the row went back to `todo` because of it,
  which is CHARTER §5 working). ⚠ Critic #26 wrote that every *critic* report of the last 24 h carries the
  line too; `docs/auto/reports/2026-09-05T2330Z-critic.md` does not. Critic laps have no subagent reviewer
  by design, so that is a wrong sentence rather than a missing practice, and it is not a finding.
- **No author decision is waiting.** The Gmail search
  (`from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop" newer_than:14d`) returns 25 threads,
  every one of them sent by this loop and holding exactly one message with no reply.
  `docs/auto/decisions_seen.json` is unchanged.

## Critic #26's falsifiable test, both branches, answered

1. **The ancestry commands re-run on an unshallowed clone: the withdrawal stands.** `is-ancestor` exits 0,
   the object is **283** back (critic #26's 277 measured at `b2bdaf0`, plus this window's six commits, so
   the two agree), `rev-list HEAD | grep -c` answers 1, `branch --contains` names `auto/dev` and
   `origin/Main`. WFG-115 stays at P1, re-scoped.
2. **Q30's ⚠⚠ block no longer says 326 · 268, so the item mechanism DOES carry prose. Do not escalate it.**
   And it carried it better than the item asked: the card now names **three** reason-buckets instead of
   two (the third, `external`, was the largest and the draft had omitted it), holds **no** live count at
   all, and ships `test_the_cards_account_of_the_irreproducible_covers_every_bucket`, which goes red when
   the registry grows a reason the card does not describe. That is the right shape of gate.

## The root objection

**This loop measures whether a correction was made. It never measures whether the correction arrived.**

Twice in one window, on the same file:

- critic #26 withdrew the `41498ef` finding into three pages the *loop* reads and left it standing in the
  card the *student* reads, then wrote a sentence protecting it (WFG-133);
- WFG-117 repaired Q30 in `docs/auto/JUDGE_QA.md` and the booth PDF built from that file was not rebuilt,
  so the paper the student carries still holds the withdrawn 「326 · 268」 warning (WFG-134). The manifest
  records the source at `2c8451211e5f97eb…`; the tree hashes `af955a30fa500391…`. The other three sources
  match, so the drift is one file and it is the 17-page one. `tests/test_printables.py` checks that the
  manifest *has* a hash per source and that the PDF matches its own hash. **Nothing compares a recorded
  source hash against the tree**, which is the one comparison that detects a stale printable, so the suite
  is green on an out-of-date booth kit.

The cheapest test is a grep. It is now a standing rule on `DIRECTION.md`: **grep the judge-facing surfaces
for the withdrawn string before writing 「withdrawn」 anywhere.**

## Also filed this lap

- **WFG-134 (P0)** — the stale printables kit and the missing freshness gate, above. Do it in the same lap
  as **WFG-130** (the reconciliation sheet R7 names and the manifest calls nonexistent): one rebuild pays
  both, and CHARTER §3.2 means a **new stamp beside** `WFG_printables_20260906T0620Z.pdf`, never over it.
- **WFG-135 (P1)** — Q30's repaired card invites a judge to count the irreproducible values by
  `reproducibility.status`, and **18 of the 58** carry no such field (24 `external`, 16
  `not_reproducible`, 18 absent). The card's third bucket is therefore an interpretation of an absent
  field. The gate is right; the promise is what over-reaches. Do not close it by dropping the invitation.

## Do NOT do this

- Do not edit Q35's **draft answer**, `Q30`'s repaired card, or `web/finals.html`'s provenance line to
  "fix" reachability. Nothing on the judged screen is wrong about it.
- Do not re-add a live registry count literal to `JUDGE_QA.md`. That is the defect WFG-117 removed.
- Do not overwrite `WFG_printables_20260906T0620Z.pdf` or its manifest (CHARTER §3.2).
- Do not write a reachability or ancestry claim until `git rev-parse --is-shallow-repository` answers
  `false`. Not 「deepened to N」. `false`.

## The falsifiable test for critic #28

1. If Q35's ⚠ block still tells the student 「지금 브랜치에서 닿지 않습니다」 at the next critic head, then
   a `fix-before-next-row` item cannot survive a **previous critic's** prohibition, and the finding is
   about how critic laps bind each other rather than about the row. Say so and escalate the binding.
2. Re-hash the newest printables manifest's sources against the tree. If any is still stale, R7's kit is a
   snapshot with no freshness gate and WFG-134 is understated: file the gate as its own P0 rather than as
   part of a rebuild.
