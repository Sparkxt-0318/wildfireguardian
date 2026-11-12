# Comprehension pilot: session kit (PROTOCOL.md v2.2)

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

## Open points for the orchestrator, Iris and Sofia

1. **Cases (PROTOCOL v2.2, orchestrator decision (a)).** Across the six booth caches (531 field origins), the replay has no gap, no partial and no staff later-window origin: horizon 354, none_checked 147, no_route 11, unresolved 19, gap 0, partial 0, later-window 0.
   - C2 is therefore the first leave_by/none_checked origin, and C3 is dropped.
   - The gap wording, the partial message and the staff later-window line are **untested** by this pilot, and may not be described as tested.
   - C2's broadcast and SMS read like C1's; only its card states that later computed times have no checked road.
   - Iris confirms the revised decision cells before the kit is final.
2. **Q1 timing.** The protocol runs the timer "from the item shown to the answer", and it asks the open question first. The kit stops the timer at the first clock time the reader states as the leave-by time, even if it comes in the open answer. Otherwise the 30 s cut would include the open answer. This is the kit's reading of the protocol, and Iris should confirm it.
3. **C5 is a "not checkable" origin.** By the fixed rule, the first unresolved origin is one more than 2 km from the road graph.
   - Its staff headline carries that reason.
   - Its resident outputs read like those of any other unresolved origin.
4. **Coders.** An answer counts as a miss when either coder gives it a miss code. For Q4, both coders must code OFFICIAL. This is a kit rule, stated here before any session.

## Limits (from the protocol)

- The samples are small and not representative. The setting is a table, with no time pressure, smoke or stress.
- A miss is decisive; a clean result is weak.
- The broadcast is tested as "script heard at a table". A pass does not transfer to an outdoor loudspeaker.
- English and the automated voice call are not tested.
- A pass supports no statement about comprehension in public material.
