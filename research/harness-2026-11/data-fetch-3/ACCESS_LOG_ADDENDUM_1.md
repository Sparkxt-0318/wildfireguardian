# ACCESS_LOG addendum 1 (12 Nov 2026)

This corrects and extends `ACCESS_LOG.md` (sha256 `5608c582…3e87`, commit 982eb71c), which is left unchanged.
Source: the session transcript. The orchestrator asked for the declaration questions; Hannah's Q6 prompted this addendum.

## Correction to the 09:01:51 / 09:02:06 row

That row says the command printed only "file counts and folder names per zip". This is incomplete. At 09:02:06, `unzip -l Area_Progression_TimeSeries.zip` also printed member names together with byte sizes and zip timestamps. The part of the output that was displayed showed 25 incident IDs, and 5 of them are S-D9 part b/c/d:

- CA-ENF-024030_Caldor
- CA-ENF-027219_Fork
- CA-KNF-007022_HappyCampEast
- CA-KNF-007022_HappyCampWest
- CA-KNF-007084_Devil

No H-test fire was among them. Only names were shown. No PNG was ever opened, extracted or viewed. The 09:02:36 command only counted members per folder.

## Reads of sources other than the NIROPS shapefile that touch b/c/d or H-test fires

| Time (UTC) | What | Scope | Printed |
|---|---|---|---|
| 08:50:39–08:50:58 | GOFER v0.2 (Zenodo): fire table, the GOFERC_fireProg attribute table | all 28 GOFER fires, which include the 7 H-test fires (before the split existed) | Kincade and Walker ignition hour (GOESIg_UTC) and official acres; the first 3 Kincade hourly rows (tUTC, farea, fareaPer, fperim); perimeter count and first and last tUTC for each of the 28 fires. Used for nothing. |
| 09:04:23 | NIROPS dbf (already logged) | all records | the dataset-wide UTC min and max, 2020-05-12 to 2024-12-17, which was also sent to Victor at 09:07 |
| 09:29:42 | WFIGS Incident Locations, one query by IRWIN ID | NM-LNF-000227_Blue2 (part a) | the field schema and the service-wide count only |
| 09:30–09:32 | WFIGS and ICS-209-PLUS join by IRWIN ID → `data-fetch/incident_metadata.csv` | all 733 incidents (disclosed) | one row (AZ-A1S-001211_Monument, part a); one aggregate: "discovery_utc after first survey: 13" over all 733 |
| 14:53:21–14:53:30 | repo files during the leak search: S-D9 RUN_FILTERS, PREREGISTRATION_ADDENDUM, ACCESS_CONTROL, GOFER_MATCH.csv | b/c/d rows | ID lists, and the GOFER_MATCH rows with discovery_utc and GOFER hours for Caldor (d), Dolan (d), LNU Hennessey (c), LNU Walbridge (c) and McFarland (d), among the 10 b/c/d rows the file holds |

None of these values went into any price, sizing, build or committed file. No web search, InciWeb, news, agency page or NIFC FTP access was made for any b/c/d or H-test fire.
