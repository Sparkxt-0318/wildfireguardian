# F-C1b account-based results (ACCOUNT-BASED; separate from the satellite analysis)

**Rules.** `DEFINITION_C1b_accounts.md`: @0674f70, amendment 1 @02c312d, sources @2ba8a85. All were fixed before
computing.

**Code.** `seebefore/c1b_accounts.py` @0b2244d. It reads only the documented rows of `C1B_documented.json`.

**Output.** `C1B_accounts.json`. Times are KST, 25 Mar 2025.

> Retrospective research. Accounts are what a named person told a newspaper or broadcaster; they are a third source,
> not truth. These are case studies chosen because accounts exist, not a sample, and no rate is given.

## Answer

**In none of the three eligible cases can the question be answered from the accounts.**

- C1 (지품면사무소) and C3 (신덕리) document a sighting but no arrival at the place.
- C2 (매정리) documents an arrival but no sighting.

Under the fixed rule, a sign needs both, so no account-based sign is called. This comes from what the sources say
(Sofia read all three in full), not from a computing limit.

## Cases

**C1: 지품면사무소 (V1). Source: dgmbc 628364, read in full.**
- **Sighting.** The 면장 saw black smoke from the north at about 16:30, so S = [16:00, 17:00].
- **No arrival.** The 17:55 "flames" are not in this interview. They come from a different article, a resident
  driving with fire "right behind", village not named. The interview's other fire lines are untimed.
- **Satellite.** Arrival within 500 m is (14:58, 21:25]. Trip is 67 s.
- **Visibility at S.** "Possible" for flame and smoke, both settings, both timing rows. The model's fire positions
  are consistent with the sighting but cannot confirm it.

**C2: 매정1/2/3리 halls (V2). Source: hankookilbo A2025032714350000238, read in full.**
- **Arrival.** "Ten minutes after I left, the fire swallowed the village." The 20:30 departure is in the photo
  caption, so A = [20:10, 21:10].
- **No sighting.** The 20:00 door-knock by the 이장 is a warning, not a sighting.
- **Leave-by** L = A − trip (112, 131 and 112 s by hall) is about [20:08, 21:08]. It is an upper bound: a drive-only
  time with no time to get ready.
- **Satellite brackets.** 매정1/3 are (14:58, 21:25]. 매정2 is (21:25, 26 Mar 01:09], so the account falls before
  its bracket (already reported in RESULTS_C1b).

**C3: 신덕리 centroid, flagged (V6). Source: Nocut 6318424, read in full.**
- **Sighting.** "Red fire coming over", about 17:30–18:00, hedged ("I think it was"), so S = [17:00, 18:30].
- **No arrival in words.** The source says "fire spread within about 10 min"; she fled by car and was burned by
  embers. Arrival at the place is implied, not stated. Her house survived; buildings about 50 m away burned.
- **Satellite.** Arrival within 500 m is (14:58, 21:25]. Trip is 412 s (6.9 min), from the nearest planner place's
  entry node, not her house.
- **Visibility at S** (bracket row):
  - flame, optimistic: possible.
  - flame, pessimistic: **not possible**. The first visible flame in the model is (21:25, 26 Mar 01:09]. Under the
    pessimistic setting, the model's detected-cell fire positions do not explain flames seen by 18:30. This is a
    statement about the model, not evidence against the account. In the wide (kriged ±2 sd) row it becomes
    possible.
  - smoke, optimistic: **certain by S**. The model has smoke in line of sight from 24 Mar 12:44–13:07.
  - smoke, pessimistic: possible.
- **The ±15 min sensitivity row gives the same classes.**

## Tally

No case has both a documented sighting and a documented arrival: not C1, not C2, not C3. So no "saw with less time
left than the route needed" call and no "saw with enough time" call is made.

## F-DYN leave-by

Not available: Richard's F-3.1 deadline field was not present at computation. No substitute was computed.

## Ideas and gaps

1. **C3 is the closest to answerable.**
   - Reading "약 10분 만에 불이 번져" as arrival would give time left of about [0, 25] min against a 6.9 min drive,
     with no time to get ready. That would be indeterminate even then.
   - That reading was **not** made: the rule needs the arrival stated in words, and changing it after seeing the
     sources would be tuning.
2. **Sharper anchors.** The 20:25 지품 power cut and the 17:00 지품 evacuation with a text message 2 h later (same
   Hankook Ilbo article) are timed and documented. They are not sightings or arrivals at an observer point, so they
   do not fit this test. A test built around "departure time versus fire at the road" would use them; that needs a
   new definition fixed before computing.
3. **The model cannot place C3's flames at 17:30–18:00** under the pessimistic setting from detected cells. This is
   one more sign that polar-satellite timing is too coarse at village scale.
