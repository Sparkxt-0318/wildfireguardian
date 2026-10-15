# Utility trip logs in Korea (phase 2, item 2, desk research)

Compiled on 2026-10-15 by a research agent in this session; web and paper search only. Markers:

- [R]: the page was read.
- [S]: only a search snippet was seen.
- [verified]: re-fetched by the main session and the quoted text confirmed.

Full URLs are in `data/SOURCES.md` under "Phase 2: utility logs". All times are KST.

## Short answer

- **Logs exist in principle, but no public timestamped trip log was found.**
  - Distribution: KEPCO's distribution automation (DAS, now Grid-K ADMS) receives fault and switch events from FRTUs (remote terminal units at automated switches) and stores alarms and events in a history database [R].
  - Transmission: relays and fault recorders on 154 kV and above are remotely collected (the PDAS system) [R].
  - Not found publicly: event-level logs, timestamp resolution, time synchronisation, or the share of reclosers that are remotely monitored.
- **In 2025, fire contact and deliberate de-energisation overlapped**, which is the main confound for using trips as a fire sensor:
  - Reactive cut on 2025-03-22: about 13:40, power was cut to 20 of the 55 towers between the Angye and Uiseong substations, and "17 of the 20 were already affected by the fire". [verified] (천지일보, 2025-03-23)
  - Yeongdeok was declared an emergency de-energisation zone from 21:00 on 2025-03-25 [R]. Flames also "caused transmission line trips", and about 95% of Yeongdeok lost power. [verified] (Electimes, 2025-04-09)
  - During that event "the automation equipment all stopped", and crews switched sections by hand. [verified] (Electimes, 2025-04-09) The DAS record for the critical hours is therefore likely incomplete.
- **No formal Korean pre-emptive shutoff policy (like the US PSPS) was found.** Shutoffs appear to be operational decisions made during the event:
  - 2021 "strengthened" breaker operation on dry, windy days [R];
  - a 2023 agreement with the Gyeongbuk fire service on de-energising lines during firefighting [S];
  - a 2025 after-action plan with no published criteria [R].

## Distribution event recording (KEPCO)

- DAS architecture:
  - master station servers and a history-management database;
  - a front-end processor talking DNP3.0 to FRTUs;
  - alarms and events distributed to all programs and stored [R] (Kim and Oh, JKIIECT 2022).
- In Seoul, remote units report faults to the distribution control centre immediately, and isolation takes about 3 min (about 54 min before DAS) [R] (T&D World, 2012).
- Automation coverage: a national audit reported 118,752 of 177,522 switches automated at end-2018 (66.8%), with a 90% target by 2030. 357 automated switches were not connected to the communication network [R] (정보통신신문, 2020-09-23).
- KEPCO publishes only annual regional outage counts on data.go.kr (dataset 3068741), with no causes, times or feeder IDs [R].

## Transmission

- 154 kV and above: relays store fault records. A KEPCO pilot (PDAS) collected records remotely from 269 digital relays at 39 substations [R] (KIEE, 2007).
- KPX publishes outage statistics as counts and rates, not per-event times [R].
- Wildfire-caused transmission faults reported for KEPCO: 7 in 2020, 54 in 2022, 2 in 2023 [R] (경북매일, 2025-03-26).

## Reported 2025 power events (best reconstruction)

| Time (KST) | Event | Type | Source |
|---|---|---|---|
| 03-22 about 13:40 | Angye to Uiseong line, 20 of 55 towers cut, 17 already fire-affected | Reactive shutoff | 천지일보 [verified] |
| 03-25 21:00 | Yeongdeok emergency de-energisation zone, lifted about 02:00 to 03:00 on 03-26 | Precautionary | Hankyung [R] |
| 03-25 21:06 | Outage across all of Yeongdeok | Mixed | Newsis [R] |
| 03-25 evening | Jinbo and Yeongdeok substations stop, about 93,000 households out; flames cause transmission trips; automation stops | Fire caused and precautionary | Asia Economy [R]; Electimes [verified] |
| By 03-26 | 16 transmission lines in Yeongnam had stopped, 4 restarted | Unknown split | Asia Economy [R] |
| Later total | 18 transmission lines faulted, 2 substations fully lost power, about 9 h outage | Unknown split | Newsis 2025-04-28 [verified in phase 1] |

The public record gives no trip times or line names for the 16 to 18 lines.

## Access

- Event logs are not public.
- Possible routes, all untested:
  - KEPCO's Data Safe Zone (on-site analysis of non-public data, designated 2023) [R];
  - data obtained through a National Assembly member, as in the Newsis story;
  - an official-information disclosure request.

## International precedent

Trip and fault times have been matched to ignitions after the fact:
- PG&E Camp Fire 2018: Caribou to Palermo line relayed at about 06:15, fire seen at about 06:30 [S].
- Kincade 2019 [S].
- SCE Eaton 2025: faults logged by Whisker Labs sensors and by SCE [R].
- Lahaina 2023: Whisker Labs logged 34 faults [R].

These were used for ignition forensics. No peer-reviewed paper was found that reconstructs fire progression from trip timestamps.

## What this means for the simulation

The synthetic trip log (`lastgasp/trips.py`) includes the confounds found here:
- only SCADA-monitored devices are logged;
- devices below an open device cannot trip;
- event types may be missing;
- blanket and ahead-of-fire precautionary shutoffs;
- reactive shutoffs of lines the fire already reached;
- a logging blackout part-way through the event.

Results are in `RESULTS_PHASE2.md`.
