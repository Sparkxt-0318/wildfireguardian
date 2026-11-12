# Procedure rehearsal: not evidence about people

**What this is.** Two AI agents played readers, given only the participant materials in schedule order (slots A01 and B01), with the facilitator's questions. A third agent played coder 2, given only `SCORING_SHEET.html`; Clara was coder 1 and wrote her codes before seeing coder 2's (`rehearsal/coder1_A01.csv`).

**This is a procedure rehearsal, not evidence about people.** It says nothing about how older adults or county staff read these outputs. It must never be reported as comprehension, in any form. Agent answers are not reader answers.

It checks only three things:
- Are the materials complete?
- Is the timing workable?
- Is the coding rule unambiguous?

## Materials complete?

The A01 reader saw 12 items:
- 4 broadcast transcripts, standing in for the one recording;
- 8 phone screenshots of `print/handouts/item-*.html`.

The B01 reader saw 8 items: the headline PNGs and the one-page A4 PDFs. The B01 notes are below.

- Every item was readable, and nothing the questions relied on was missing (A01).
- The card's destination sits in a collapsed "▶ 어디로" disclosure. The broadcast names the destination, but the card shown on paper or as a still image does not.
  - No question depends on the destination, so this is noted, not changed.
  - On a live phone, the facilitator should not expand it.
- The SMS shows "10:30" with no 오전/오후.
  - **Kit fix (facilitator rule, no wording change):** a time given without 오전/오후 is recorded as stated ("10시 반" → 10:30), and the facilitator does not ask which.

## Timing workable?

**Not measurable with agent readers**, so the Q1 seconds column is empty. The scorer therefore reports Q1 as NOT MET ("correct time but no recorded seconds"), which is the designed behaviour for a missing time. The planned session lengths (A ≈ 30–35 min, B ≈ 20 min) rest on the kit's broadcast estimates (29–32 s per script at the normal rate, 35–39 s slow) plus question time. They are **not** checked by this rehearsal. The owner should time a dry run with a staff member before the first participant.

## Coding rule unambiguous? **No.** Coders 1 and 2 agreed on 7 of 12 open answers.

Scored with `tools/score.py`; output in `rehearsal/rehearsal_A01_scored.md`. The scorer exits 1. Two of its "misses" are coding artefacts, explained below. They are **not** reading failures.

Findings that need **Iris's decision before any session**. Each one changes how a fixed rule is applied, so the kit does not settle them itself:

1. **TIME-INVENTED vs. the data time (critical).**
   - The C4 and C5 broadcasts themselves say "오전 10시 자료로는…".
   - The reader repeated it ("오전 10시 자료로는 대피 길을 확인 못 했대요"). Coder 2 coded TIME-INVENTED by the literal rule ("a clock time is given for C3–C5"); coder 1 did not.
   - Under the either-coder rule, that is two **critical misses** caused by the rule, not by the reader.
   - Proposed clarification: TIME-INVENTED = a time given **as a time to leave, or as a deadline**, where none is shown. Repeating the data time that the item shows is not TIME-INVENTED.
2. **OFFICIAL: "follow" vs. "comes first".**
   - Answers like "공식 지시를 따르라고 해요" name an official source but no order of precedence. Coder 1 coded NEUTRAL; coder 2 coded OFFICIAL.
   - This matters only for Q4, which is scored on its own answer column, but it caused 3 of the 5 disagreements.
   - Proposed: OFFICIAL needs a stated precedence (먼저, 우선, "comes first"); "follow official X" alone is NEUTRAL.
3. **Which bodies are official.** Is 119 an official source? Is "공식 대피 안내" (guidance, not an order) official? Proposed:
   - 119 counts as an emergency service, not as an evacuation authority;
   - "공식 대피 안내 / 명령" counts.
4. **Where the C2 follow-up ("…10시 40분에 출발하는 것에 대해서는…") is coded.** It is part of the open question, so it is recorded in `open_verbatim` and coded with it. The facilitator script already says so; the scoring sheet should say it too.
5. **The C2 follow-up presupposes content.** On the broadcast and the SMS, C2 says nothing about 10:40. The reader answered "10시 40분 얘기는 없어요", which is correct but shows the question assumes something the item does not say.
   - Also, asking about 10:40 before Q1 signals that 10:40 matters.
   - Both are protocol wording, so they go to Iris and are not changed here.
6. **Q4 primes the end question.** The end Q4 repeats item 1's Q4 after every item has said "공식 … 우선". The protocol already reports it as secondary.
7. **STAY at its edge.** "No route out; call 119 if urgent", with no other action, could be read as implying staying. Neither coder coded STAY. The rule gives no guidance on it.
8. **A possible misreading noted by the A01 reader (no wording change; wording is paused).** The large "자료: 2025-03-23 10:00 기록 (재현)" line on the card could be taken for a time to leave. That is exactly what Q1 and TIME-INVENTED would catch with real readers.

## Group B (B01)

The B01 reader saw 8 items: the 4 headline PNGs and the 4 one-page A4 PDFs. The B answers were not double-coded. The findings below are about the procedure.

9. **Q4 cannot be answered from the staff surfaces (decision needed).**
   - The staff headline says nothing about whose instruction comes first. The reader answered "그건 이 안내에 안 나와 있어요", which is correct about the item.
   - The A4 sheet says only "실시간 대피 지휘용 아님".
   - Q4 is scored on each participant's first item, and in group B that item is a headline or an A4 sheet. So group B's Q4 would measure prior knowledge, or count a correct "it doesn't say" as a miss.
   - Options for Iris: score Q4 for group B only from the end question; or reword Q4 for B as "whose instruction would you follow first"; or drop the Q4 target for B and report it descriptively. **Not changed here.**
10. **C2's A4 explains the 10:30 deadline as set by the 1-hour scenario window, not by fire.** Its text reads "10:40에 출발하면 … 1시간 시나리오 범위를 벗어나므로 … 예측 화염이 아니라 시나리오 범위로 정해진 것입니다".
    - So for Q2, both "no" and "unsure" are defensible. Only "yes" is a miss, which the rule already says.
    - The reader thought the departure-time strip marks 10:40 as no-route. At print size its boxes are hard to tell apart (see 11).
11. **Small print on the A4.**
    - The departure-time strip (10:00–10:50) is too small to read reliably on the printed page.
    - The "*" note does exist at the end of the section, but the reader did not find it.
    - Printing at 100 % on A4 is required; the facilitator should not shrink the page to fit.
12. **Time per item.** The reader guessed 30–60 s per headline and 2–4 min per A4 sheet. That is a guess, not a measurement. Against the 30 s Q1 cut, an A4 first exposure may be slow by design of the page, not by misreading. The 30 s cut is the protocol's own stated cut, and Iris may want to look at it for the A4 channel.
13. **Item 6 (C4 A4) mentions "실내 대피" as one alternative.** A reader could take this as "staying is OK". It is a STAY edge case for coders; see 7.

## v2.3: the coder rehearsal repeated (same 12 A01 answers)

Coder 1 (Clara, codes written first: `rehearsal/coder1_A01_v2.3.csv`) and a fresh coder-2 agent applied the v2.3 SCORING_SHEET to the same open answers. The reader answers were not redone, so the v2.3 closed questions have no answers here.

- **Open answers: 9 of 12 identical code sets** (v2.2: 7 of 12).
  - All 3 disagreements (items 3, 6, 9) are about whether "위급하면 119" earns EMERGENCY-SERVICE, a descriptive code with no target.
- **Later-departure answers: 3 of 3 identical. Q4: 2 of 2 identical** (OFFICIAL).
- **No disagreement on any miss code** (USABLE-LATER, STAY, TIME-INVENTED, AMBIGUOUS-TIME), and no miss code was given by either coder.
  - The two v2.2 "critical misses" on "오전 10시 자료로는…" are gone under the rule "repeating the item's data time is never a miss".
- **Doubts coder 2 raised, now settled in the rule text:**
  - (a) the data-time exemption now covers AMBIGUOUS-TIME as well as TIME-INVENTED;
  - (b) EMERGENCY-SERVICE in open answers = any mention of 119 or the fire service (this resolves the 3 disagreements);
  - (c) Q4: the first-item answer is scored, the end answer is secondary.
- Coder 2 also noted that word order ("이장이나 읍·면사무소 공식 지시를 따르고, 위급하면 119") is not stated precedence. The rule already says so (OFFICIAL-FOLLOW).

Iris's readiness criterion is "no coder disagreement on any answer that would be a critical miss". It holds on these 12 answers.

**This is still a procedure check, not evidence about people.** The rehearsal answers come from an AI agent, and the closed v2.3 questions were never put to a reader.
