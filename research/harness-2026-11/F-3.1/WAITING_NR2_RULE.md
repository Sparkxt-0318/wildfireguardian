# Waiting-location sensitivity on the `/2` multi-hour HEADLINE field (rule; committed before code and any run)

- **Source.** Orchestrator, 13 Nov 12:41 UTC. Inputs for the AIR-EXTRACT early-action list's waiting column
  (`EARLY_ACTION_RULE.md`, F-DYN builder). It also turns the F-BASE note "all-wait on `/2` is argued, not measured"
  into a measurement.
- **Parent rule.** `WAITING_SENSITIVITY_RULE.md`, multi-hour arm. This file fixes that arm's details for the `/2`
  HEADLINE.
- **Labels.**
  - SCENARIO, not what happened. Graphs are road-limited.
  - Sensitivity arm label, verbatim from the parent rule: "SENSITIVITY: waiting allowed at every node (not the
    supplied graph rule)".
  - The documented default stays: waiting only at graph dead-end nodes. No verified result changes.

## Scope and code

- **Packets.** The 48 HEADLINE `/2` packets: 4 variants × 6 recorded starts × {5 h, 8 h}, rebuilt from MANIFEST_v3_7
  (Leo 819bcb91). The static envelope_burnset row is its own stratum.
- **Code.** `PacketModel` pinned at 446978f6, the verified file (rows 79/79a). Arms:
  - default arm: the supplied graph rule;
  - sensitivity arm: `waitable_all=True`, which is also applied to the graph the full checker reads.
- **Fields.** CERT and ROUTER, per (destination, dwell), as in `headline.py`.
- **Environment.** numpy 1.26.4, Python 3.13.18.

## Units and what counts as a change

- **Destination unit:** (region, start, horizon, variant, field, place, destination). Compared: the feasible
  departure set (exact intervals) and its 30-min grid verdicts.
- **Place unit:** (region, start, horizon, variant, field, place). The early-action list reads this one. It is
  compared by:
  - the place leave-by, i.e. the end of the union over destinations of the feasible sets, prefix as in `headline.py`;
  - the route / no-route status.
- **A place unit "depends on the waiting rule"** when its leave-by differs between the arms, or when it has a route in
  only one arm. The column value is one of:
  - "no";
  - "yes: leave-by later by S s with waiting allowed everywhere";
  - "yes: route only with waiting allowed everywhere".
- **Not-evaluated places** (`NOT_EVALUATED_LABEL_RULE.md`) are reported with their state and not compared. Under
  `/2` their start point is closed at 0 in both arms.

## Pass/fail

- **Control.** The default arm's place leave-by equals `results/HEADLINE_NR2_summary.json` for every place unit
  (CERT and ROUTER). A mismatch is listed, and that packet's comparison is reported as not interpretable.
- **Direction.** Waiting is optional, so every sensitivity-arm feasible set must contain the default-arm set
  (destination units). Any exception is a **fault**, and every fault is listed.
- **Witnesses.** For every place unit whose leave-by is later in the sensitivity arm, the witness at the new leave-by
  passes the unchanged full checker on the sensitivity graph, and its next second is infeasible.

## Reported (labelled, per region, start, horizon and variant; never pooled across regions in a headline line)

- **Place units** "depends on the waiting rule": count, split into "leave-by later" and "route only with waiting".
  Also the median (upper) and maximum shift in seconds.
- **The cross-tab with "depends on the no-re-entry rule"** (`NOT_EVALUATED_LABEL_RULE.md`): how many place units carry
  both flags.
- **Destination-unit 30-min grid verdict changes:** a from → to table.
- **The static row** on its own.

## Runs

- **Sizing check before the batch.** One Yeongdeok pair is run alone first: YD 25T19Z h8 kriged_mean, the largest
  graph and longest horizon. Its peak RSS is measured for both arms.
  - If it exceeds 13 GB (approaching the 15 GB limit), the batch does not start. It is reported, and nothing is
    truncated.
- **Batch.**
  - One worker.
  - Tracked in a log with one line per packet.
  - Checkpointed: a finished packet's output is kept and skipped on restart.
- **Packets.** Built in scratch and deleted after each run.
