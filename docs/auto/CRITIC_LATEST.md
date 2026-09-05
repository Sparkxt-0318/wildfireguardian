# CRITIC_LATEST — critic #15, 2026-09-05

Window `a234a1c..43710f7` on `auto/dev` (5 commits; the 24 h window is 101).
Written by the `wfg-autoloop-critic` routine. The next dev lap clears every
`fix-before-next-row` item here before claiming a row.

## fix-before-next-row

**One item, WFG-095, and it is fifteen minutes on the document this window earned its score with.**

`docs/auto/DEMO_SCRIPT_5MIN.md` is the only file in this repository whose sentences are spoken
out loud to a judge, and it is good. It also marks one droppable sentence per segment with
**[버림]**, so that a student running long knows what to cut. In 1막 that marker sits on a
sentence carrying its claim and its caveat together (`:52-53`, 709단계 / 0건 with 「오경보율의
측정이 아니라 상한입니다」) — drop it and both go, which is right.

In 2막 (`:70-71`) and 3막 (`:85-86`) the marker sits on a **caveat-only** sentence while the
claim it guards stays in the non-droppable text:

- **2막.** The droppable line is 「이 표본과 1막의 표본은 서로 다른 자료입니다. 두 시각을 같은
  성격이라고 말하지 않습니다.」 The claims stay: 1막's 「기록된 발생일시 대비 22분, 34분, 64분」
  and 2막's 「2,008건 중 79.23 %가 기록된 발생일시에서 240분 안에」. Drop the caveat and the
  student has spoken two different 발생일시 clocks in consecutive segments with nothing left
  saying they are different samples. That is the conflation `WFG-053` withdrew and NH-018 /
  NH-019 were opened over, and the paper routine had a §4.6 paragraph blocked by its own
  reviewer for exactly it (`72cf230`).
- **3막.** The droppable line is 「지역 차이는 실제 지형 차이만이 아니라 OSM 지도 작성 밀도
  차이이기도 합니다. 그래서 지역끼리 순위를 매기지 않습니다.」 The claims stay: 24.73 %
  (의성·안동), 9.17 % (영덕), 15.14 % and 23.67 % (울진·삼척), four regional numbers in a row.
  And **§4 item 4 of the same document** lists 「지역 간 순위」 among the sentences this script
  never says. The script's own never-say list is enforced by a sentence it marks as disposable.

**Measured, not asserted.** I deleted each caveat in the working tree and ran
`scripts/check_forbidden.py`, `tests/test_withdrawn_claims_registry.py`,
`tests/test_detection_ordering_is_not_claimed.py` and `tests/test_demo_script_5min.py`:
**all four exit 0 on both deletions.** The tree was restored; nothing was committed.

**Done when** every **[버림]** marker sits on a sentence that carries its own claim, so cutting
it cuts the number too — either move the marker onto the claim-plus-caveat pair, or move the
caveat into that segment's ⚠ block where the script's non-droppable warnings already live — and
the six segment times still sum to 300 s.

This qualifies under CHARTER §14b: it is a judge-facing surface in the plainest sense the rule
has, the words the student says to the judge. It is the only item this lap sets.

## What I ticked, and why it is the news

**R4 is ticked at `43710f7`, the first `KCF_READINESS.md` line to move in six critic laps**
(the last was R2 by critic #8 at `12bf2d9`, 0750Z on 09-04). **4 of 11.** I ticked it on my own
reading rather than on the lap's claim: the six segment lengths sum to exactly 300 s and every
cumulative bracket is consistent with them; §2 carries one interruption sentence for each of the
five judge lenses; all **33 registry keys** in the §3 mapping table resolve in `docs/NUMBERS.json`
with values matching the spoken text; the two screen sentences the script tells the student to
quote verbatim are in the built `web/finals.html`; and `default_region` really is
`uiseong_andong_2025` in `scripts/build_finals.py:846`, which §0's twenty-second reset depends on.

The half a test cannot reach is unchanged and the tick does not claim it: whether five minutes of
spoken Korean fits in five minutes is R12 / NH-014, and §5 of the document says so itself.

## Verified independently this lap

`gates.py --mode full` exits **0** at `43710f7` in a fresh cloud sandbox: `1464 passed,
62 skipped` in 317.3 s, **COLD** (first full run here, so the six SRTM-gated tests skip;
WFG-039). Against critic #14's cold `1453 / 62` at `ed35f0d` that is **+11 passed, skips
unchanged**, like for like, ninth comparable window. `verify`, `snapshot-verify`, `env-check`
PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, fifteenth window and still not
a finding. Green at HEAD for a **twelfth** consecutive critic lap. `--assert-head` and
`--assert-reported` both exit 0.

**GitHub's own runs (CHARTER §4b), read through the MCP because the sandbox proxy answers
nothing to unauthenticated `api.github.com` calls.** Two red runs in the window, and they are a
new kind: **runs 103 (`a2a2994`) and 104 (`c8124a8`) are `failure` with the `gates` job PASSED
and only the new `promote` job failed.** CHARTER §4c's fast-forward of `Main` cannot run while
`Main` requires a pull-request review. Fixed at `b3244f8` twenty minutes after the first red,
inside §4b's hour; runs 105, 106 and 107 (this head) are `success`. **This is not finding #1 and
no lap reported green over a red gate** — but it changes what a red `auto-gates` run means from
09-05 onward, and every lap must now read the failing **job**, not the run. The author action it
needs is filed as **NH-025**.

**Report certification.** `--assert-reported --base a234a1c` exits 0. Every dev report of the
last 24 h carries a `Reviewed by:` line — seven of seven, clean for a second consecutive window.

## The one thing I would not have known without measuring

I graded `tests/test_demo_script_5min.py` from outside with 16 mutations written from the
document before reading the test body: **9 of 16 caught**, **10 of 16** counting the tree's other
claim gates. Every numeric mutation was caught. Six of the seven survivors are on the prose half
(the DRAFT label, a 화면→구두 downgrade, the ⚠ block distinguishing 26.6 % from 15.14 %, and the
caveats above) and are filed as **WFG-097**, P1, parked behind the readiness lines by §14b — by
the critic who found it, which is what §14b is for.

The survivor that did **not** survive is worth more than the six: putting the withdrawn
detection-ordering claim back into 1막 was **caught by `tests/test_withdrawn_claims_registry.py`**.
That is WFG-062 catching a withdrawn claim in a document written after it, on a file nobody added
to a guard list. Critic #14 measured that row at 1/20 on rewordings and was right to; this is the
dimension it did buy, and it is the first time the tree has demonstrated it on new prose.
