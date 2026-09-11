# Critic #63 — 2026-09-11T0300Z, reviewed `0796336`

**The next dev lap reads this file first.** Window `f93af93..0796336`: one dev lap that closed
four rows in one bundle, plus two report-header commits. No code outside tests, no data, no
figure, no `docs/NUMBERS.json` entry.

---

## `fix-before-next-row`: ZERO, measured

No gate is red on the pushed head. **GitHub `auto-gates` run 356 is `success` at exactly
`0796336`**, at `fetch-depth: 0`. Both findings below sit on hashed printables sources, so each
costs `make printables` at a new stamp plus a re-pointed `release/kcf-finals-2026/MANIFEST.json`;
CHARTER §14b says that is not minutes, so both are P0 rows at position 1 and neither is a
preemption. **Take the top row directly.**

⚠ **`gates.py --mode full` came back RED on this lap's first run and the pushed head is NOT the
cause. Read this before you treat a red critic gate as a finding.** The single failure was
`tests/test_timeline_roles.py::test_the_artifact_still_agrees_with_the_history_when_the_clone_has_one`,
with `STALE timeline artifact: phase starts or anchor commits`. CHARTER §4 requires
`git fetch --unshallow`, which obeys the remote refspec and pulls in **eleven** side branches,
while `actions/checkout@v4` at `fetch-depth: 0` fetches one. More objects, longer abbreviation:
committed anchors are **seven** characters (`a88700c`, `4e9dfe3`, `66abf92`, `25f1e14`,
`522f7a7`), this clone derived **eight**. Cure, on the identical tree and touching nothing
tracked:

    for r in $(git branch -r | grep -v -E 'origin/(Main|auto/dev)$'); do git update-ref -d "refs/remotes/$r"; done
    git reflog expire --expire=now --all && git gc --prune=now

Packed objects 16,420 → 13,011, abbreviation back to seven, `--check` prints
`OK — timeline artifact agrees with git log (745 commits, 44 active days)`, full suite green.
**Critic #60 met and repaired this identical failure one day ago; nothing records the repair as a
step, so critic #63 paid for it again.** Recorded on **WFG-217**, which is the row that fixes it.

---

## Finding 1 — WFG-247 (P0, KCF, filed at position 1)

**The last thing each of the five judges hears is this project's own result counted in the unit
this project withdrew the day before, with a third population standing beside it in the same
sentence.**

`docs/auto/DEMO_SCRIPT_5MIN.md:266-268`, spoken in the 마무리 at 4:04, verbatim:

> 「보행망 노드 **2,218곳을 전수 탐색**해서, 대피 지점 한 곳을 추가하면 **20가구**, 두 곳이면
> **24가구** 가 도달 가능해지고, **세 번째는 0가구** 를 더합니다.」

Three populations in one breath, and the repository knows all three are different:

| said | key | what it actually counts |
|---|---|---|
| 2,218곳 | `l0i_candidates_enumerated` | candidate SITES on the walk graph |
| 20가구 / 24가구 / 0가구 | `l0i_best_single_refuge_saved`, `l0i_best_pair_saved`, `l0i_third_refuge_gain` | `unit: households` on `sample: 영덕 2025, **OSM 건물 124동(잠정)**` |
| 지점 (the demo's own opening claim) | — | one node of the OSM walking graph (`JUDGE_QA.md` Q20a) |

And 「가구」 is the register **`WC-013`** withdrew for this project's output object on 2026-09-10,
which the 2026-09-11 lap then cleared off all eight lines of the two printed sources — and left
standing here, four lines at a time, on a third printed source.

**The reconciliation already exists and nothing points at it.** `docs/auto/JUDGE_QA.md:947`:
「두 질문은 모집단도 다릅니다. 한쪽은 보행 도로망 노드이고 다른 쪽은 **OSM 건물 124개**입니다」
— 190 lines away, in a different card, in a different segment of the demo. `WC-013`'s own
`say_instead` states the rule this breaks in one line: **the bound goes in the SAME block as the
claim, never one screen away.**

**Four surfaces:** `DEMO_SCRIPT_5MIN.md:266-268` (spoken), `:358-361` (the 화면/구두 number
table), `:380` (금지 item 6, which forbids 「20가구를 구했다」 and licenses
「20가구가 도달 가능해진다」 without touching the population), and `web/finals.html:1978-1995`.
The screen is the weaker half: `:1995` does carry 「모든 가구 수는 OSM 건물 스냅숏 위의 잠정치」
in the same card. The script does not.

⚠ **This is NOT a `WC-013` violation and must not be filed as one.** `WC-013` withdrew the
household register for the walk-or-be-rescued verdict; the refuge-siting result genuinely is
measured on buildings and `docs/NUMBERS.json` says so.
⚠ **Do not fix it by swapping 가구 for 지점** — that would be false. Name the population where
the number is said, so the student has an answer in hand for
「아까 단위가 지점이라고 하셨는데 왜 여기는 가구입니까」.

---

## Finding 2 — WFG-248 (P0, KCF, filed at position 1)

**The card that tells the student to open a DOI in front of the judge describes that record in a
way the record's own abstract does not support.**

`docs/auto/JUDGE_QA.md:829-832` (Q16d, added yesterday) rests this project's *method*
differentiator on: 「저쪽은 **D\* Lite 로 다시 계획합니다**」. The Zenodo abstract for
`10.5281/zenodo.22668358`, read at the source in this lap:

> "The system orchestrates **OpenRouteService vector routing** using spatial polygon clustering to
> bypass API area limitations. **During API constraints or in wilderness scenarios**, the system
> delegates to an internal **D\* Lite heuristic grid fallback** that incrementally routes traffic
> away from actively predicted fires."

D\* Lite is their **fallback**. The card compares this project's PRIMARY mechanism against the
other team's FALLBACK — and three paragraphs later, at `:848-849`, tells the student
「심사위원이 「그 논문 진짜 있습니까」라고 물으면 이 DOI 를 그 자리에서 열어 보이십시오」. A judge
who takes that invitation reads the abstract standing next to the student.

**One clause, not a rewrite**, and the card already holds the correct fact fifteen lines below at
`:834` (「도로와 **차량** 경로 스택(OpenRouteService)이며」).

⭕ **Everything else on Q16d survived independent verification, at the API and not at the report
that wrote the card:** `conceptdoi` `10.5281/zenodo.22668357` resolving to record `22668358`
(a version relation, exactly as the card says, not a duplicate deposit); title verbatim;
`publication_date` **2026-09-09**; `resource_type` **Preprint**; the five authors in the card's
order; one attached file named `IEEE_Conference_Template.pdf`. The card's hardest claim —
「기록에는 성능 수치가 하나도 없습니다」 — is **exact**: a digit regex over the abstract returns
the empty list. **Do not weaken any of those while fixing the one clause.**

---

## Finding 3 — WFG-191, re-measured, and it explains the board's rival counts

Rule, stated so the next lap can check it: split each row on pipes **not preceded by a
backslash** (`\|` is a Markdown escape and renders as a literal pipe), and count rows whose cell
count differs from the header's ten. At `0796336`: **11 malformed of 242 rows.**

The list has **moved**, not merely persisted — WFG-133 and WFG-149 have left it and **WFG-243 has
joined**, a row filed 2026-09-10 and closed 2026-09-11. **The defect is still being introduced.**
Three of the eleven are `**P0**`, and for six the cell in the status position is not a status:
WFG-181 → `프라이버시`, WFG-188 → `예산`, WFG-175 → `title-derivable`, WFG-168 → `않습니다`,
WFG-115 → `grep -c 41498ef…`, WFG-112 → a regex fragment. **WFG-182's status cell is an awk
program** for counting this board.

**This is where the two published board counts come from.** Critic #62's 「238 rows, 98 P0,
18 P0 todo」 reconciles **exactly** under this rule once its own two rows are added back
(236+2, 96+2, 16+2), so its arithmetic and its 「after this lap」 labelling were right. Its
「106 P1 todo」 does not: this rule answers **111**, and four of the difference are rows whose
shifted cells put `P1` in the priority position when it is not their priority. **Two careful laps
cannot agree on a number whose file does not have the shape either rule assumes.** The gate this
row already asks for is the whole answer; no further lap should spend measurement here first.

**Stays P1** under §14b until R3 ticks. ⚠ Said plainly because the rule and the cost point
different ways with four days left: the board is the first file every dev lap reads to choose its
work, and three P0 rows display their status in the wrong column.

---

## Finding 4 — WFG-217's silent half grew to 83 commits

`build_timeline_roles.py --check` prints **OK** at this head while
`data/processed/timeline_roles/timeline_roles.json` holds `total_commits` **662** and
`last_commit_date` **2026-09-09** against a tree at **745** and **2026-09-11**. Phase 5's `end`
reads `2026-09-09` against `2026-09-11` live, its commit count **417** against **500**. That is
**83 commits and two active days**, up from critic #60's **64** one day ago, growing at roughly
twenty commits a day. The check cannot see it: `:173-177` exempts totals as growth and the spine
comparison covers phase **starts** and anchor commits only, never an open phase's end.

⭕ **Not a false statement, and worth recording as the project behaving well.**
`docs/auto/finals/TIMELINE_ROLES.md:28` says outright 「이 문서의 수는 산출물이 만들어진 트리의
값입니다 — 2026-09-09, 커밋 `89da7d3` 기준」 and `:48` tells the student to say the as-of date
aloud. A **widening disclosed gap**, not a lie. Deadline stays the 2026-10-16 freeze; the
refreshing lap works from a **single-branch full clone**.

---

## What the window got right, measured rather than read

- **The withdrawn household register is off the printed kit.** All six `WC-013` spellings
  re-swept over every tracked `.md`/`.html` on text **flattened of newlines**, so the sweep sees
  what the shipped line-based checker cannot: 「이 집 사람」 7, 「가구 하나하나」 6,
  「공간 단위 … 가구/집」 7, 「어느 집을 먼저」 6, 「가구 단위의 도보 대피」 5, 「가구별 대피」 2 —
  **33 hits, zero outside the record class.**
- **The kit and the bundle are on paper as claimed.** `manifest_20260911T0102Z.json` re-hashed
  **7 of 7** sources against the tree; `release/kcf-finals-2026/MANIFEST.json` **19 of 19**. Both
  recomputed in this lap's own process.
- **The panel names what it deliberately keeps.** `RELATED_WORK_PANEL.md:39-41` states which two
  「집」 lines stay and why (G-DAPS's own spatial unit, and `WC-008`'s other-systems sentence).
  That is the scope note whose absence caused the defect one lap earlier.
- **Q36 puts the disc null on a T0 card** with both IoU pairs and all four centroid displacements
  in cells, in one block — discharging half of critic #60's and #61's reason for holding 창의성
  at 19. The other half (one fire, one canvas, one threshold) is why it is still 19.
- **All three dev reports in the window record `Reviewed by:`**, and `--assert-reported` exits 0.

---

## Root objection (`hate`) on the current headline narrative

**The project traded a novelty claim it lost for one whose only exhibit is synthetic.** On
2026-09-09 Bokade et al. took the architecture; the thesis correctly retreated to 「the output
object and its measured limits」. But the committed instances of that object were produced in a
run where **hazard and terrain are synthetic and the origins are sampled coordinates**, and the
panel says so in bold: 「실제 확산면으로 만든 출동 지시서는 아직 없습니다」. So the
differentiator and the confession are now the same sentence. That is elegant on paper and thin
at a booth, where 「그 판정을 실제 불로 한 번이라도 내보셨습니까」 is the obvious next question
and the answer is no.

**Cheapest test:** NH-057 option B — the agent-doable half, **WFG-242**. It already exists,
already `blocked(NH-057)`, and needs one letter from the author. The objection therefore does not
land on the loop's work; it lands on the decision queue, which is the same place everything else
landed this lap.

---

## Scorecard

**Track B 94 → 96, Track A 95 → 97, both on 제출 자료 17 → 19.** The first rise on that row in
four laps, paid on exactly the defect that took it down. **19 and not 20:** WFG-247 and WFG-248
are both on this same criterion and both on the paper in the box.
**Pre-registered for critic #64:** 제출 자료 reaches **20 on both tracks** when WFG-247 and
WFG-248 both close with the kit rebuilt and the manifest re-pointed, and falls back to 18 on
either track if a kit source drifts against its manifest hash.

## Readiness

**8 of 11**, unchanged. ⚠⚠ **ZERO lines ticked for the TWENTIETH consecutive critic lap**, and
this window was not idle. R3 is `blocked(NH-046)`, R11's WFG-024 is held by §14b until R3 ticks,
and **112 P1 rows wait on one reply**. Appended to NH-046 and NH-049 rather than filed again.
