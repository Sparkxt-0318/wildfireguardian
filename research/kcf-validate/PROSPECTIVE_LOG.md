# PROSPECTIVE_LOG: predictions fixed before the outcome is known

Model output on detections only. Advisory. Not an order. Not what happened to people. No claim about what any official should do.

A retrospective replay (kcf-replay, kcf-roadcut) can be fitted, consciously or not, to what is already known. A prospective entry
cannot: the prediction is made public with a hash before the event it predicts. This file is append-only. An entry is never edited;
a mistake is a new entry that says which one it corrects.

## Status, 2026-11-18

**No entry has been made.** No active Korean wildfire was identified. What was checked: two web searches (Korean and English,
2026-11-18, ~15:40 UTC) returned preparation material for the 2026 autumn fire-watch season (산불조심기간 1 Nov-15 Dec) and earlier
2026 fires (Miryang 23 Feb), and no fire in progress; the NASA FIRMS and Korea Forest Service sites are **not reachable from the
build container** (network policy), so the absence of an active fire is **not verified** by a satellite feed. If a fire is burning,
this log does not know about it. The first entry should be made by whoever sees a fire first, with the steps below.

## Procedure (a new fire anywhere in Korea)

1. **Trigger.** A cluster of VIIRS/MODIS detections (confidence n/h for VIIRS, ≥ 30 for MODIS, type 0) that is not a known industrial
   source, or an official fire report. Note the first-detection time (UTC): this is `--since-utc`.
2. **Fetch inputs, record the clock.** Download the FIRMS NRT CSVs for the area (VIIRS SNPP, NOAA-20, NOAA-21 if available, MODIS) and
   immediately run `date -u`; that is `--retrieved-utc`. Inputs may only contain detections acquired before the issue time.
3. **Choose the issue time T** ≥ retrieved time (T is when the prediction is "spoken"). Nothing acquired at or after T is used.
4. **Make the entry:**

   ```bash
   python3 research/kcf-validate/prospective/make_entry.py --fire-id KR-YYYYMMDD-PLACE --since-utc <first detection> \
     --issue-utc <T> --retrieved-utc <clock> --firms-csv <file> [--firms-csv ...] --bbox LON0 LAT0 LON1 LAT1 \
     --out research/kcf-validate/prospective/entries/KR-YYYYMMDD-PLACE/<T as YYYYMMDDTHHMMSSZ>
   ```
   It refuses when the inputs were retrieved after T or when nothing was detected before T. Output: `prediction.json` (claims, code
   commit, rule, per-file SHA-256), `arrival_minutes.tif` (the 8 h closure-time field, `product/wfg-roadlayer` input format), and
   copies of the inputs. The prediction is the kcf-replay **MEASURED** arm unchanged (R(5 h), R(8 h) by prior-3 h spread class).
5. **Commit and push before the outcome time.** One commit containing only the new entry directory; push to the remote. The remote's
   push time (e.g. the commit's push event on GitHub) is the receipt; the local commit time is not. Record in the table below, **in a
   second commit**, the entry's `prediction.json` SHA-256, the commit SHA, and the observed push time. Do not push the table row first.
6. **Optional, regions with a road graph only** (영덕, 의성·안동): `python3 product/wfg-roadlayer/roadlayer.py run --region ... --issue-time T
   --raster arrival_minutes.tif` and commit its CSV in the same entry directory before step 5. For other regions there is no road graph
   in this repository, so an entry makes **zone claims only** (C1-C3 in `prediction.json`), not road cut-off claims.
7. **Scoring, no earlier than T + 8 h + 24 h.** Same rules as `research/kcf-validate/PROTOCOL.md` §2 (coverage of newly burned cells by
   the 5 h and 8 h zones, misses reported; FIRMS detections acquired in (T, T + 8 h] and a Sentinel-2 scene if one exists), and, where the
   source can be read, official records (재난문자 send times, road closure announcements) with the kcf-roadcut comparison rule. The
   score is written as a new entry, with its misses, whatever it is. Entries that are never scored are listed as unscored.
8. **What breaks it.** Editing an old entry; using a detection acquired after T; pushing after the outcome; an entry made from past data
   that is not labelled DRY RUN; scoring with a rule chosen after seeing the outcome.

## Known limits of this procedure

* The known fire area uses FIRMS only. The retrospective rule also used Himawari AHI hotspots (a persistence rule on raw B07/B14); the
  entry maker does not fetch AHI, so a prospective entry sees less than the retrospective replay did. AHI hotspots can be passed as a
  further input only by extending the script (not done).
* Delivery latency is not modelled: FIRMS NRT can arrive hours after the overpass (NASA states up to about 3 h globally; not measured here); `--retrieved-utc` records what was really available.
* The push time is a third party's clock (the Git host), not a cryptographic timestamp. No RFC 3161 or blockchain timestamp is used
  (`freetsa.org` and similar hosts were not reachable from the build container).
* R(5 h) and R(8 h) are calibrated on 28 historical fires (kcf-margin); a single entry says little. The log is meant to accumulate.

## Dry run (not an entry)

`prospective/dry-run-2025-03-25/` is the maker run on the committed 2025 FIRMS files, T = 2025-03-25 09:00 UTC, FIRMS only, to show that
the pipeline runs and what its outputs look like. Label inside the file: "DRY RUN (retrospective, NOT a prospective entry)". It uses 1,761
FIRMS discs, class quiet (the committed example for the same T uses FIRMS **and** AHI and gets class running: the two differ because AHI
is absent here). The 5 h / 8 h zone sizes are in `prediction.json`. The retrieval time in it is made up (T − 10 min) and is not a receipt.

## Entries

| # | fire id | issue time (UTC) | prediction.json SHA-256 | commit | push time observed | scored |
|---|---|---|---|---|---|---|
| (none) | | | | | | |
