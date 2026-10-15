# Independent checking of the native outputs

This folder, with `runner/` and `decision/`, holds everything needed to check the native campaign's outputs. Every
command below runs offline, outside every request deadline. RUN is the kit directory created by the native launch
(`outputs/routing_native_confirmation_20261014_v1/WFG-integrated-preparation-candidate-20261014`), and PY is its
worker interpreter (`RUN/env/bin/python`, or the one recorded in `RUN/ENVIRONMENT.json`).

## 1. Exact checker sources (unchanged copies, hashes in CANDIDATE_MANIFEST.json)

| File | SHA-256 | Role |
|---|---|---|
| runner/ffi_independent_checker.py | 8ce23dba... | Independent trajectory checker (wfg.ffi.independent-checker/1). Imports no routing, bridge or checker module; numpy and the standard library only. |
| runner/witness_wholeroad.py | 035d86ff... | Offline whole-road check of an independent centre-model counterexample, with the hash-pinned runtime checker (used only to settle a dispute). |
| decision/journey_decision_v2_1.py | 80adfc0b... | Authoritative decision (journey / refusal / unresolved) from RESULT, the outer receipt and the job. |
| runner/native_tally.py | see manifest | The frozen KLB regional tally (a50c7f36...) with asserted substitutions only: interpreter path, scope text, preparation fields and the N1 reporting class. Class rules unchanged. |
| checking/compare_tallies.py | see manifest | Field-by-field comparison of two tally outputs. |

The scoring definitions are in SCORING_DEFINITIONS.md. Open verification items are in OPEN_VERIFICATION.md.

## 2. Three different kinds of evidence (do not merge them)

1. **Centre-model verification (independent).** `ffi_independent_checker.py` re-checks every published journey or
   refusal from the raw RESULT and the frozen inputs. It covers path and mission grammar, exact flame contact on the
   closed road segments, and the cell-centre exposure model (each road piece charged the flux at the centre of its grid
   cell). Its optimality and refusal verdicts come from an exact time-expanded relaxation in which contact and peak are
   enforced for every member and dose is relaxed. These verdicts are therefore statements about the cell-centre model.
2. **Runtime road certificates (not independent).** The mandatory whole-road check inside each worker
   (`adaptive_checker.HybridChecker`, hash-pinned per job) returns CERTIFIED_ADMISSIBLE with an outward enclosure of the
   continuous-road dose and peak. The candidate's FULL_OPTIMUM certificate is its runtime road lower-bound argument. Both
   are produced by the software under test.
3. **Independently validated road enclosures: none.** No independently authored implementation validates the
   continuous-road radiation enclosure. The independent checker's road radiation output is a dense numerical sample
   (every 5 m and 1 s) and is labelled non-certifying. Samples lying inside the runtime enclosure are a consistency
   check, not a proof that the enclosure covers every unsampled position and time.

## 3. Commands

The launcher already runs these after the timed queue (`wfg_native.py all`). To run them by hand, for each queue
Q in NATIVE_PRIMARY_yeongdeok_2025 and NATIVE_PRIMARY_uiseong_andong_2025 (or the NATIVE_WARM_OPTION_* queues):

    PY -I -B RUN/runner/native_tally.py indep RUN Q 100000     # independent checker, 120 s cap per attempt, no retries
    PY -I -B RUN/runner/native_tally.py wroad RUN Q 100000     # only disputed witnesses (centre counterexamples), 150 s each
    PY -I -B RUN/runner/native_tally.py tally RUN Q RUN/analysis/Q
    PY -I -B RUN/runner/native_report.py RUN primary           # NATIVE_SUMMARY_primary.json and .md

Outputs: `RUN/raw/Q_INDEPENDENT/<label>.json` (or `.TIMEOUT` / `.FAILED.log`), `RUN/raw/Q_WITNESS_WROAD/`,
`RUN/analysis/Q/EXECUTIONS.csv|json` and `SUMMARY.json`.

Single attempt, by hand:

    PY -I -B RUN/runner/ffi_independent_checker.py --graph RUN/<graph_path> --packet-dir RUN/<source_directory> \
        --request RUN/<request_path> --result RUN/raw/Q/<label>/RESULT.json --out /tmp/check_<label>.json

(the relative paths are in that attempt's JOB.json).

## 4. Independent re-check by a separate checker (recommended)

A separate checker should not reuse the campaign's own checker outputs. Copy the run, without its checking outputs, into
a new directory and re-run the commands there:

    R2=/path/to/recheck_root; mkdir -p "$R2/raw"
    cp -R RUN/routing_candidate RUN/phaseB RUN/decision RUN/runner RUN/queues RUN/inputs RUN/checking RUN/CANDIDATE_MANIFEST.json "$R2/"
    cp -R RUN/raw/Q "$R2/raw/"
    PY -I -B "$R2/runner/native_tally.py" indep "$R2" Q 100000
    PY -I -B "$R2/runner/native_tally.py" wroad "$R2" Q 100000
    PY -I -B "$R2/runner/native_tally.py" tally "$R2" Q "$R2/analysis/Q"
    PY -I -B "$R2/checking/compare_tallies.py" RUN/analysis/Q/EXECUTIONS.json "$R2/analysis/Q/EXECUTIONS.json"

Before trusting either result, verify the copied code against CANDIDATE_MANIFEST.json (every listed file's SHA-256) and
each attempt's raw folder against its JOB.json input hashes. The checker is deterministic; identical class columns are
expected. The independent checker's own wall time is not part of any request deadline.

## 5. What a checker should confirm

- Every one of the 348 primary slots appears exactly once (NOT_RUN and INTERRUPTED slots are listed, never dropped).
- Every completed primary attempt recorded `preparation.mode == COLD_FAST` and the pinned preparation source identity
  (`RESULT.json` field `preparation.preparation_source_sha256`, equal to `preparation_source_sha256` in
  CANDIDATE_MANIFEST.json). `NATIVE_SUMMARY_primary.json` reports both checks in its integrity section
  (`rows_with_other_mode`, `rows_with_other_source_identity`). No warm attempt appears in the primary queues.
- On-time follows the frozen rule (exit 0, no termination, launch-to-completion wall at most 30 s, authority_final and
  publication before the deadline). Memory-guard stops are never on time.
- Resolved classes only: VERIFIED_ROUTE, VERIFIED_FULL_OPTIMUM, CERTIFIED_REFUSAL. ROAD_ONLY_ROUTE and
  UNSUPPORTED_REFUSAL_CLAIM stay unresolved. Contradictions are reported, never resolved.
- Counts are per region and per arm. Nothing is pooled across regions, hosts, workloads or repetitions, and no
  percentage is formed.
