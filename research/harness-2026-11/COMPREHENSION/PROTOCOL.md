# Comprehension test of the leave-by outputs — protocol (PLAN ONLY)

Status: v2.3 (2026-11-12): after the procedure rehearsal (kit/REHEARSAL.md), with Iris's coding rules, Sofia's Korean, the orchestrator's rulings, and Mira's note N1. **All of these were decided before any person was tested.** v2.2 followed; v2.1 followed Iris's readings of v1 (bbbb640) and v2 (ffd541c). v2.2 (2026-11-12, orchestrator decision (a)) replaces C2 and drops C3, because the replay has no case of either (see "Cases not in the replay"). Iris confirms the revised decision cells before the kit is final. Plan only: no recruitment, no publication, no data collected. The
owner arranges participants, consent and any ethics review. Written 2026-11-12 after the orchestrator paused new
wording until one comprehension test with real readers has run.

**What a pass can mean.** This pilot is a go / no-go for the existing wording, not a measured comprehension rate. A
miss is decisive. A clean result at this size is weak: 0 misses of 8 does not show that misses are rare. A pass allows
paused wording work to resume. It supports **no statement about comprehension in public material**.

## Cases not in the replay (v2.2, measured)
Field origins by state, over all six booth caches (531), counted by `tests/planner/comprehension.kit.test.ts`:

| State | Origins |
|---|---|
| leave_by, later departures not checked (horizon) | 354 |
| leave_by, every later computed time has no checked road (none_checked) | 147 |
| no route | 11 |
| unresolved | 19 |
| gap | 0 |
| partial | 0 |
| staff later window | 0 |

**The following remain UNTESTED by this pilot, and may not be described as tested:**
- the gap wording ("Leaving at the next computed time has no checked road");
- the partial message;
- the staff later-window line ("…this is not the deadline; do not plan on it").

No synthetic case is shown to participants.

## Questions
1. **Find the time.** Can a reader tell whether the message gives a time to leave by, and find it?
   - The same closed question is asked on all four cases (v2.3).
   - Report every time.
   - 30 s is the stated cut, except for the A4 sheet (v2.3: no cut; see targets).
2. **Later is not usable.** Is a time later than the one the item gives ever read as usable?
   - v2.3: asked on C1 and C2, without naming any later time.
   - The broadcast and SMS of C2 read like those of C1.
   - The gap wording and the staff later-window line are untested; see above.
3. **Never "stay".** Is an unresolved or no-route result ever read as "stay where you are" or as "no need to leave"?
4. **Official first.** Do readers name an official source as coming first?
   - Group A: scored.
   - Group B: descriptive (v2.3), because the staff headline and the A4 do not state precedence.

**Principle (Iris, v2.3).** A reader who accurately repeats what the item says is never a miss. If the accurate repetition is itself worrying, that is a **wording finding**. It is logged separately, not counted as a reader error.

## Participants (two groups, reported separately, never pooled)
- **A. Older adults:** 65+, living in rural 시·군 like the replayed areas, N = 8–12.
- **B. County and village staff:** 이장, 읍·면 담당자, 시·군 재난 담당, N = 6–8.
- Record only the age band, the group and whether the person reads Korean on a phone without help. No names. No real
  resident data anywhere.
- **English outputs are not tested; no claim is made about them.** (Too few English readers to give a usable number,
  and the English call is not produced at 373 of 531 places.)

## Materials (existing replay only, unchanged, every item carries its replay mark)
Four fixed cases (v2.2), chosen by a fixed rule and listed with their ids before any session. The rule: caches in
`planner/cache/INDEX.json` order; within a cache, origin ids ascending; the first origin in each state. All four
come from `uiseong_andong_2025/20250323T010000Z`:

| Case | State | Origin | Place | Leave-by time |
|---|---|---|---|---|
| C1 | leave-by, "later departures not checked" | osm:node/415158323 | 신석리 | 10:50 |
| C2 | leave-by, "every later departure time computed has no checked road" (v2.2; was: gap) | osm:node/415158416 | 하아리 | 10:30; next computed time 10:40 |
| C4 | no route | osm:node/415160353 | 구암리 | none |
| C5 | unresolved (not checkable: more than 2 km from the road graph) | osm:node/415160364 | 고곡리 | none |

C3 (partial) is dropped (v2.2). Only C1 and C2 carry a leave-by time. C3–C5 below means C4 and C5.

Channels:
- **A:** the village-head broadcast, as ONE fixed audio recording of the script played to everyone (not a live
  reading), with one repeat on request, and whether the repeat was used recorded; the family text (SMS shown on a
  phone); the public replay card (offline on a phone; the page stays unpublished).
- **B:** the staff headline in the planner and the A4 plan sheet.

The automated voice call is omitted (no TTS engine in scope). The broadcast result is reported as **"script heard at a
table"**, the best case: a miss counts, and a pass does not transfer to an outdoor loudspeaker.

## Design and procedure (one-to-one, fixed script, no feedback between items)
- **Facilitator:** follows a fixed script, gives no feedback, and is not someone who wrote the wording, if the owner can
  arrange it.
- **Exposures:**
  - A: 4 cases × 3 channels = 12 items, about 30–35 min with a break;
  - B: 4 × 2 = 8 items, about 20 min.
  - Order follows a Latin square over case × channel (kit `SCHEDULE.csv`):
    - participant slot p (0-based) sees 3 (A) or 2 (B) rounds;
    - round r shows every case once, in the case order rotated by p + r;
    - case i is shown in channel (i + p + r) mod (number of channels).
    - Each case is seen in every channel once per participant. Its first exposure (round 0) rotates over the
      channels from one participant to the next.
- **Primary analysis = the FIRST exposure of each case** (a reading). Later exposures of the same case in other
  channels are recall, and are reported as secondary.
- **For each item, in this order (v2.3).** The facilitator never says a time that the participant's own item does not contain, and never introduces "안전". Every question is read as written in kit/FACILITATOR.html (Korean, checked by Sofia).
  1. **Open question.** Record verbatim.
     - C1, C2: "What does this message tell you?" (이 안내는 무엇을 알려 주나요?)
     - C4, C5: "What does this message tell you to do?" (이 안내는 무엇을 하라고 하나요?)
  2. **Time question (all four cases, closed).** "Does this message give a time to leave by? If so, what time?" (이 안내에 출발해야 하는 시각이 나와 있습니까? 있으면 몇 시입니까?)
     - The timer runs from the item shown (or from the end of the recording) to the first clock time the reader states as the leave-by time, in the open or the closed answer.
  3. **Later-departure questions (C1, C2).**
     - Open: "What does it say about leaving later than the time it gives?" (이 안내에 나온 시각보다 늦게 출발하는 것에 대해서는 뭐라고 합니까?)
     - Closed: "Does it say you could still get out if you left later than that time?" (그 시각보다 늦게 출발해도 나갈 수 있다고 합니까?) Answer yes, no, or not stated / unsure.
     - No later time is named, on any channel.
  4. **Stay question (C4, C5, closed).** "Does this message mean you should stay where you are?" (이 안내는 지금 있는 곳에 그대로 있으라는 뜻인가요?) Answer yes, no, or unsure.
- **Q4,** "Whose instruction comes first if they differ?":
  - asked on each participant's **first item only**, and once more at the end (secondary);
  - scored for group A;
  - descriptive for group B (v2.3).
- **Coding:** the coding rule below is fixed before any session. A second person codes every open answer and every Q4 answer without seeing the first person's codes. Disagreements are reported, not resolved silently.

## Coding rule (v2.3, fixed now)
A code set may hold several codes. Verbatim text is always kept.

| Code | When |
|---|---|
| USABLE-LATER | A time later than the item's time is described as one at which one can still leave or get out. |
| STAY | The reader says the message tells them to remain where they are, or that leaving isn't needed. "No route; call 119 if urgent" alone is NEUTRAL. |
| SHELTER-MENTION | The reader repeats that the A4 lists "실내 대피" as an alternative. Descriptive, not a miss. "So I can stay home" is STAY. |
| TIME-INVENTED | A time given **as a time to leave or as a deadline** where none is shown (C4, C5). Repeating a time the item shows (e.g. "오전 10시 자료로는…") is not TIME-INVENTED. "10시까지 나가야 한대요" is, because it turns the data time into a deadline. |
| AMBIGUOUS-TIME | An open answer on C4/C5 with a clock time whose role is unclear. It is **resolved by the closed time question**: a time given there is TIME-INVENTED; "no time given" clears it. A time that is plainly the item's own data time ("오전 10시 자료로는…") is neither TIME-INVENTED nor AMBIGUOUS-TIME. |
| OFFICIAL | An official source is named **with stated precedence** (먼저, 우선, "comes first"). Official sources: 시·군 / 시장·군수, 공식 대피 명령 or 안내, 재난문자, 읍·면사무소, 이장. |
| OFFICIAL-FOLLOW | An official source is named as one to follow, with no stated precedence. Kept, no target. |
| EMERGENCY-SERVICE | In an open answer: any mention of 119 or the fire service, as a number to call or as the authority. Descriptive. Never OFFICIAL. |
| NEUTRAL | None of the above. |

- **Q4: which answer counts.** The first-item answer is scored (group A). The end answer is secondary and never scored.
- **Q4 answers.** The question already supplies "comes first", so naming an official source is enough for OFFICIAL. "119" alone is EMERGENCY-SERVICE: a miss for group A, listed for both groups.
- **Group B Q4 (descriptive).** Each answer is reported verbatim in one of three categories:
  - OFFICIAL: names an official source;
  - NOT-STATED: says the item doesn't say;
  - MODEL-AUTHORITY: names the model or the sheet as the authority. This category is flagged.
- **Either-coder rule.** An answer is a miss if either coder gives it a miss code. For group A's Q4, both coders must code OFFICIAL.

## Pre-stated targets (fixed before any session, as counts; v2.3)
- **Which count decides (fixed now, so no count can be picked afterwards):**
  - **Q1** is decided on the **first exposure per group × leave-by case (C1, C2), pooled over channels**. N is the group size. There are four decision cells:
    - group A × C1;
    - group A × C2;
    - group B × C1;
    - group B × C2.
  - The per-channel breakdown and the all-exposure counts are descriptive, with no target.
  - **Q2, Q3 and the Q1 critical miss** are decided on **every exposure, open or closed**. Zero misses are allowed.
  - **Q4 (group A)** is decided on each participant's first item, pooled over cases and channels.
- **Q1:**
  - Allowed misses: ≤ ⌊0.2·N⌋ per group × case, i.e. 1 at N = 6–9 and 2 at N = 10–12.
  - A miss is:
    - a wrong time;
    - "no time given" on C1 or C2;
    - the correct time after more than 30 s, on the broadcast, SMS, card or headline.
  - **A4 sheet (v2.3, decided on the page's design before any person is tested):** a miss is a wrong time or no time. Seconds are recorded and reported, with no cut. A full-page planning sheet is not a glance channel, and half of group B's first exposures are A4.
  - Report the median and the longest time per channel.
- **Q1 critical miss:** TIME-INVENTED on C4/C5, or a time given in answer to the closed time question on C4/C5. 0 allowed.
- **Q2 (C1 and C2, v2.3):** 0 USABLE-LATER on any open answer, and 0 "yes" to the closed later-departure question. "No" and "not stated" are both correct.
- **Q3 (C4, C5):** 0 STAY, and 0 "yes" to the closed stay question.
- **Q4, group A** (first item, pooled over cases and channels): misses ≤ ⌊0.1·N⌋, i.e. 0 at N ≤ 9 and 1 at N = 10–12.
- **Q4, group B:** descriptive, no target. The missing precedence line on the staff surfaces is a wording finding for after the pause.
- **Wording findings** (e.g. "119" answers prompted by the C4 broadcast's "위급하면 119", the A4 departure-time strip too small to read at print size, the A4 footnote not found) are logged verbatim, apart from the targets.

Every miss is reported verbatim with its case, channel, group and exposure order. No percentage without its n/N.

## Decision rule
- **All targets met:** the paused wording work may resume, scoped by the results. No public statement about
  comprehension is made.
- **Any target missed, or any critical miss:** the failing wording is revised first, with Iris and Sofia, and re-tested
  on new participants, before any new wording is added.

## Limits
- Small samples, not representative, a table setting with no time pressure, smoke or stress.
- A miss is decisive; a clean result is weak. The 30 s cut has no published basis; it is a stated cut.
- First-exposure cells are small: about N/3 per case and channel in group A, and N/2 in group B. That is why they are
  reported with counts only.
- v2.2: the gap wording, the partial message and the staff later-window line are not tested (they do not occur in the
  replay). C5 is a not-checkable origin, chosen by the fixed rule.
- v2.3, Mira N1: the public-card item is the top of the page without two controls that sit between the question and
  the card at phone width: the "English" language button and the "재현할 기록: <region> · <input time>" scenario
  selector. The reading task concerns the card. A participant on the real page would also see the region and the
  input time in that selector.
- v2.3: no timing has been measured. The owner times a dry run with one staff member before the first participant
  (required).
- No hearing-impaired subgroup unless the owner recruits one. English is not tested.
