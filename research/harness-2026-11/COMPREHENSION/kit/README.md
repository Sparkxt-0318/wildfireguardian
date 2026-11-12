# Comprehension pilot: session kit (PROTOCOL.md v2.3)

**Status.** This kit gets the pilot ready to run. It contains no data from any person. The owner arranges participants, consent and any ethics review. Comprehension is **untested**. Nothing here shows that any output is fit for live use, and P-PROTO stays unpublished: the public card is shown offline from a file.

No resident-facing wording was changed for this test. Every item is the production output for its case, written by the production modules. The test `tests/planner/comprehension.kit.test.ts` regenerates every item and fails on any byte difference.

## What is here

| File | For whom | What |
|---|---|---|
| `CASES.json` | facilitator, scorer | The selection rule, the origins picked, how many replay origins are in each state, and the time a reader must find (`leave_by_kst`). |
| `items/<case>/head.ko.txt` | the person who records | The village-head broadcast script, exactly as the kit produces it (`buildChannels(...).text.ko.head.script`). |
| `items/<case>/sms.ko.txt` | group A | The family SMS (`familyText`). |
| `items/<case>/card.ko.html`, `page.ko.html` | group A | The P-PROTO card (`Card`), and the top of the page in its fixed order (replay banner, official-orders slot, question, card). |
| `items/<case>/headline.ko.txt` / `.png` | group B | The planner's staff headline, captured from the real static build. |
| `items/<case>/a4.ko.txt` / `.pdf` | group B | The A4 plan sheet page for the origin, printed by the planner as `export_plan_pdfs.mjs` prints it. |
| `print/handouts/item-NNN.html` | group A / B | One item per page, labelled only with a neutral code (자료-NNN). Open offline on the phone, or print. |
| `print/RECORDING_SCRIPT.html` | one recorder | The broadcast scripts, to record **once**. Every participant hears the same file. |
| `FACILITATOR.html` | facilitator | Fixed Korean script: open question first, then the closed questions, the timing rules, no feedback, and the debrief. |
| `FACILITATOR_KEY.csv` | facilitator only | Maps each handout code to its case and channel. Never shown to participants. |
| `SCHEDULE.csv` | facilitator | Item order per participant slot (A01–A12, B01–B08), as a Latin square over case × channel. |
| `results_template.csv` | facilitator, two coders | One pre-filled row per exposure, plus one `end` row for Q4. |
| `SCORING_SHEET.html` | coders | The fixed coding rule, the miss definitions and the targets. |
| `CONSENT_TEMPLATE.html` | owner | Information sheet and consent form. **To be adapted by the owner; ethics is the owner's responsibility.** |
| `tools/score.py` | owner | Computes the pre-stated pass/fail counts from the filled sheet. |
| `REHEARSAL.md` | orchestrator | A rehearsal of the procedure only: **procedure rehearsal, not evidence about people**. |

## Reproduce and verify

```
cd planner && npx vitest run ../tests/planner/comprehension.kit.test.ts      # text items + card: byte-identical to production
cd planner && npm run build:static && node scripts/serve_static.mjs --dir dist --base / --port 4180 &
node research/harness-2026-11/COMPREHENSION/kit/tools/capture_staff.mjs --check   # headline + A4 text: byte-identical to a fresh capture
python3.12 research/harness-2026-11/COMPREHENSION/kit/tools/build_print.py --check  # handouts, schedule, template
python3.12 -m pytest -q research/harness-2026-11/COMPREHENSION/kit/tools/test_score.py
```

To regenerate, use `KIT_WRITE=1` for the vitest step and drop `--check` from the other two.

- The capture fixes the page clock at `now_iso`, because the A4 sheet prints its own preparation time.
- PNG and PDF bytes carry renderer metadata, so they are not compared. They are pictures of the same captured page.
- The card's GPX link is an object URL that changes on every render. A fixed placeholder (`blob:replay-gpx`) stands in for it.

## Before the first participant (required)

- **Time a dry run with one staff member.** No timing has been measured; the rehearsal used AI agents, which cannot be timed.
- Print the A4 sheets at 100 %. Never shrink them to fit.
- Adapt the consent template. Ethics review and consent are the owner's responsibility.

## What v2.3 settled (all decided before any person is tested)

1. **Cases (v2.2).** C2 is the first leave_by/none_checked origin, and C3 is dropped. The replay has no gap, partial or later-window origin.
   - The tally: 354 / 147 / 11 / 19 / 0 / 0 / 0.
   - The gap wording, the partial message and the staff later-window line are **untested**.
   - On the broadcast and SMS, C2 reads like C1.
2. **Questions (orchestrator, on Iris and Sofia's advice):**
   - one closed time question on all four cases;
   - later-departure questions on C1 and C2, asked without naming any later time;
   - the stay question in a less leading form, without "안전";
   - the facilitator never says a time the participant's own item does not contain.
3. **Coding (Iris):**
   - repeating the item's data time is never a miss;
   - OFFICIAL needs stated precedence, and OFFICIAL-FOLLOW is kept apart;
   - EMERGENCY-SERVICE and SHELTER-MENTION are descriptive codes;
   - AMBIGUOUS-TIME is resolved by the closed time question.
4. **Targets:**
   - Q4 is descriptive for group B, because the staff surfaces state no precedence;
   - the A4 has no 30 s cut (a wrong time or no time is still a miss);
   - Q2's zero-miss target covers C1 and C2.
5. **Kit rules:**
   - either-coder rule for misses; both coders must code OFFICIAL for group A's Q4;
   - a time said without 오전/오후 is recorded as said;
   - the timer stops at the first stated leave-by time, open or closed.
6. **Mira N1.** The public-card item omits the "English" button and the "재현할 기록: <region> · <input time>" selector. On the real page, both sit between the question and the card at phone width. This is stated in PROTOCOL v2.3.
7. **Coder rehearsal repeated under v2.3** (REHEARSAL.md):
   - the open answers agree on 9 of 12 code sets;
   - all three disagreements are on EMERGENCY-SERVICE (descriptive), and there are **none on any miss code**;
   - the rule text was then tightened on the two points coder 2 raised.

## Limits (from the protocol)

- The samples are small and not representative. The setting is a table, with no time pressure, smoke or stress.
- A miss is decisive; a clean result is weak.
- The broadcast is tested as "script heard at a table". A pass does not transfer to an outdoor loudspeaker.
- English and the automated voice call are not tested.
- A pass supports no statement about comprehension in public material.
