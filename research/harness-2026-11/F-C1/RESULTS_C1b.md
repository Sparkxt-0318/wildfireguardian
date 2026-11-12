# F-C1b: see-before-leave for documented villages (results; unselected set pending)

**Definitions.** `DEFINITION_C1b.md` @dae181e plus amendment 1 @a285c67, both fixed before computing.

**Code.** `seebefore/c1b.py`. Documented points: full computation, `_data/C1B_documented_full.json`, copied to
`C1B_documented.json`. Lazy evaluation is identical to full: checked on V1, all fields equal.

**Timing source.** FIRMS per-cell brackets, all times in **KST** (UTC+9). The AHI timing row is discussed below.

> Retrospective research. Line of sight to modelled burning cells is necessary, not sufficient, for a resident to
> notice the fire. The six villages are **case studies chosen because accounts exist, not a sample**, and no rate is
> quoted from them.

## Result: every documented case is **indeterminate**

| Village / observer | Village arrival bracket (KST), 500 m + entry cell | Flame | Smoke | Account (label) | Account inside bracket? |
|---|---|---|---|---|---|
| V1 지품면사무소 | 25 Mar 14:58 – 21:25 | indeterminate | indeterminate | smoke ~16:30 (read in full); *the "flames 17:55" first listed here is not in the source (see note)* | **yes** |
| V2 매정1리 hall | 14:58 – 21:25 | indeterminate | indeterminate | arrival ~20:40 (read in full) | **yes** |
| V2 매정2리 hall | 21:25 – 26 Mar 01:09 | indeterminate | indeterminate | ~20:40 | **no** (earlier than the bracket start) |
| V2 매정3리 hall | 14:58 – 21:25 | indeterminate | indeterminate | ~20:40 | **yes** |
| V3 경정1/2/3리 halls | 21:25 – 01:09 | indeterminate | indeterminate | ~20:00 (snippet) | **no** (earlier than the bracket start) |
| V4 노물리 hall | 21:25 – 01:09 | indeterminate | indeterminate | ~midnight (snippet) | **yes** |
| V5 강구2/4리 halls | no detection within 500 m: **not bracketed** | not bracketed | not bracketed | ~00:37 (snippet) | n/a |
| V6 신덕리 (centroid, flagged) | 14:58 – 21:25 | indeterminate | indeterminate | flames ~17:30–18:00, arrival +10 min (read in full) | **yes** |

**Correction (2026-11-12):** V1's "flames 17:55" is not in the dgmbc interview, which Sofia read in full. That
time comes from a different article, about an unnamed village. V1's account check rests on smoke at about 16:30
alone and is unchanged.

**Account check.**

- **Count (reconciled, Iris).** Of 6 villages, 1 (V5) is not bracketed. Of the 5 bracketed villages:
  - **3 fully consistent:** V1, V4, V6.
  - **1 mixed:** V2 is consistent at 2 of its 3 halls; 매정2리 is not.
  - **1 not consistent:** V3.

  That is 2 misses at observer level (매정2리 hall, 경정리).
- **The two failures are both earlier than the bracket start.** The bracket start is "the previous overpass with ≥1
  detection anywhere in the grid", not a valid non-detection of that cell. It is **not a sound lower bound on
  arrival**, as Elena noted for AHI. 1 km MODIS pixels and polar timing miss burning cells. Only the
  upper side (burning by first detection) is a fact.

**V1 test of the visibility model** (smoke visible from 지품면사무소 by 16:30 KST): **"possibly"** under both settings.
Smoke becomes visible inside [14:58, —]. That is consistent with the account, but not a confirmation.

## Why everything is indeterminate (structural, not a computing limit)

- **The arrival brackets are 4–6.5 h wide.** The bracket at these villages is (05:58, 12:25] UTC or
  (12:25, 16:09] UTC. The preliminary leave-by is "bracket minus the fastest fire-free trip (2–7 min)", so it is just
  as wide. The gap interval [L_lo − V_hi, L_hi − V_lo] therefore spans hours of both signs.
- **The wide-bracket row** (undetected cells at kriged ± 2 sd, sd ≈ 17 h) is wider still.
- **AHI cannot narrow village arrival** under the agreed soundness rule. AHI bounds a quantity only if the quantity
  is a minimum over a set containing **all** burned cells of a 2 km pixel (buffered set). A 500 m village footprint
  never contains a whole pixel, so the leave-by interval stays at the FIRMS width. AHI can narrow the first-visible
  time V, but not the leave-by side.
- **Implication.** With the satellite record available for this event, **the sign of the see-before-leave gap for a
  specific village cannot be determined.** Timed accounts are sharper, but by design they are not substituted for
  measurements.

## What would decide it (ideas and gaps)

1. **A per-village arrival source at about 10-minute resolution.** Candidates: geostationary data at finer than
   2 km (not available); a documented arrival treated as a separate, labelled "account-based" analysis run in
   parallel, never mixed into the satellite column; or CCTV and power-cut logs (Yeongdeok's 20:25 지품 power cut is
   a sharp anchor).
2. **The F-DYN deadline field on bracket variants** replaces the preliminary leave-by, but inherits the same width.
3. **Resident-cue framing.** Sofia's sources (NIST TN 2103) and the 일직면 원리 quote ("산 너머에서 연기가 넘어오는 게
   잘 보이지 않아", ridge blocked sight) say the visibility question is real. This event's timing data cannot
   resolve it village by village.

## Pending

- **Unselected set:** all 174 planner places (observer = OSM place point), running.
- **AHI row:** for V only.
- Verification with Hannah or Nora.
