# Prospective registration: 2026 first-survey mapped-extent cohort

Status: PENDING_CURRENT_MODEL_FREEZE. After all seven
intended fits, complete membership audit and exact registry have passed, the
repository version will be READY_FOR_OWNER_REGISTRATION. Actual future
execution remains NOT_READY_FOR_2026_EXECUTION until the documentary gates below
are satisfied. This task performs no external registration, source-release
verification or 2026 evaluation. The selection rule predates current heldout
prediction and score inspection.

## Question, target and primary comparison

Does the development-selected perimeter-trained model reduce endpoint Brier
error relative to the best training-selected dilation baseline on unseen US incidents in the operational 2026 first-survey cohort? The target is cumulative mapped extent at actual published survey
endpoints, within a fixed event rectangle. It is not observed flame contact,
vehicle tenability, evacuation effectiveness or a joint fire probability law.
Korean 2026 reconstruction endpoints are a separate secondary assessment.

The primary statistic is the pooled cell-interval Brier difference, candidate
minus dilation, with a percentile interval from 10,000 whole-fire bootstrap
resamples (seed 20261030). Report every fire separately. A positive headline
requires its interval to lie below zero, the corresponding comparison with
persistence to lie below zero, and the candidate's lowest fixed calibration
bin to have no larger absolute calibration gap than either baseline. Report
all criteria separately. Failure of any criterion forbids a superiority claim.
No calibration or decision threshold is fitted on 2026 outcomes.

## Frozen model identities

Checkpoint identities will be written by the producing run into
`research/forecast-v2/MODEL_SELECTION.json` and an immutable blind registry
before any blind evaluation is permitted. Until those files identify exact
bytes, this draft is not ready for registration.

- The primary candidate is selected by lowest equal-fire development Brier
  across leave-one-year-out folds of 2020, 2021 and 2022 US fit fires. The
  catalog contains no 2023 US fit fire. Fixed tie order is base, D4,
  D4 plus local wind frame, ellipse, burnout, burnout plus spotting, mixed.
- All final variants use all eligible 2020 to 2023 fit intervals and the same
  fixed three-epoch policy. The mixed variant additionally uses eligible
  reconstruction windows of fit fires with kriging-SD weights. No 2024 or
  Korean 2025 fire contributes to fitting or model selection.
- c651 remains a frozen comparator, SHA-256
  `c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843`.
- Baselines are no-new-burn persistence, dilation at one cell per 1, 2, 4 or
  8 hours, the single best dilation rate selected using fit fires only, and
  training-fitted logistic hand features. The registry pins the chosen rate,
  logistic parameters, normalization and every candidate checkpoint.
- The supplied 2024 FARSITE deterministic scenarios belong to the separate
  current retrospective supplement. This registered future test has no FARSITE
  prediction column or discretionary native-scenario addition. Any future
  native scenario study requires its own prospectively specified analysis;
  it cannot change this test's cohort, baselines or primary comparison.

Inspecting 2024 results never permits a checkpoint, hyperparameter or primary
candidate change for this protocol. Any such change makes a new prospective
registration necessary and invalidates this version's blind claim.

## Dataset freeze and exclusions

Use the first public NIROPS release containing 2026 survey acquisitions, if
public by 2027-12-31 23:59:00 UTC. The operational incident predicate is first
published survey year 2026 and catalog nominal year 2026. This is a proxy,
not proof of physical ignition in 2026. Every raw incident satisfying the
first-survey predicate requires a catalog entry before admission. A claim
about physical ignition-year cohorts requires independent ignition metadata;
that claim cannot be inferred from this test or used to change membership.
Include incidents with at least two distinct published UTC survey times, an
aligned metric 375 m event grid and the six source channels in the frozen
model contract: temperature, eastward/northward wind, slope, tree cover and
biome. The registered six-channel availability policy cannot be changed after
source access. Prepared initial/endpoint arrays must cover the full grid.
If that release is already accessible or inspected before external registration,
this workflow remains blocked. A separately specified retrospective assessment
would be required; selecting a later release cannot restore blindness.

Before running models, freeze a cohort manifest from incident metadata,
timestamps, grids, source hashes and input availability. No model output or
endpoint growth amount can select a fire or interval. Include every consecutive
survey pair with duration in (0,48] hours whose cutoff weather is available.
Use cumulative unions up to each exact endpoint, rasterized at cell centres.
The raw adapter inventories every record in every complete SHP bundle in the
pinned whole ZIP. The only admitted members are the five SHP bundle components,
UTF-8 .txt/.md metadata and matching UTF-8 .shp.xml metadata. Reject nested or
unrecognized formats, malformed/deleted/trailing DBF records, invalid or empty
non-polygon geometry, and non-WGS84 source coordinates. Do not repair invalid
geometry. File symlinks, VRT canonical or quality rasters and unpinned raster
dependencies fail admission. Recompute every prepared cumulative array from
raw features and compare all cells before any model runs. Every missing-input
exclusion must be independently reconstructed under the registered policy;
spatial unknown values do not select incidents or intervals.
No interpolation of survey polygons or times is permitted. Published normalized
times can include estimated acquisition timestamps; retain that limitation.

Within each full rectangle, score initially unmapped cells on the independently
reconstructed intersection of registered model validity masks and baseline
feature support. Numerical NaN, infinite or out-of-range probabilities on
declared-valid support fail the case; they never shrink the population. Record excluded cells, intervals and
fires with their reasons. An empty supported population is unavailable, never
a zero Brier score. Absence outside a mapped union is a negative mapped-extent
reference under this policy, not evidence of physically unburned terrain. No
complete survey coverage footprint is available under the present data model.

All qualifying fires are retained until the fixed data deadline. If fewer than
ten US fires qualify, report all results and intervals as exploratory and mark
the primary test INCONCLUSIVE. There is no early stopping on a favourable score.
For each Korean catalog event with nominal year and source t0 year 2026, take
the finite minimum and maximum arrival hours. Enumerate proposed cutoffs using
`arange(floor(minimum), ceil(maximum), 12)`, add the source t0 and floor each
cutoff to a UTC whole hour. Retain cutoffs within the catalog start/end window
with at least one initially burned finite cell. Each endpoint is exactly 12 h
after cutoff, without clipping to the catalog end. Initial burn is arrival <=
elapsed cutoff hours; endpoint burn is arrival <= elapsed + 12. The reference
mask is finite arrival and initially unburned. These are equal-cell scores:
kriging-SD weighting belongs to mixed training, not this secondary evaluation.
Korean reconstruction results are never pooled with NIROPS mapped extents.

## Forecast and scoring rules

Use cutoff information only. Repeat the latest available whole-hour cutoff
weather over each interval; no subsequently observed weather enters a forecast.
Use hourly synchronous transitions and one final fractional step. Recursive
Monte Carlo uses 1,024 trajectories, blocks of 32 and the frozen case-seed
function. Record seeds, checkpoint and input hashes, boundary policy, support
masks, finite-window source assumptions and physical scenario parameters.

Report Brier, Brier skill relative to persistence and best dilation, average
precision, ROC AUC, ten equal-width calibration bins, expected calibration error,
clipped NLL with floor 1e-7, exact zero-probability positives, per-fire values,
whole-fire paired intervals, runtime and parameter counts. Single-class AUC or
AP is unavailable as appropriate. Do not treat cells, intervals or repetitions
as independent fires. Do not conceal infinite exact log loss behind clipping.

All seven final variants are secondary comparisons. Report their full table
regardless of sign. The primary decision uses only the previously selected
candidate, with no post-hoc replacement by the best 2026 model. Reliability
figures show all bins and the low-probability region with the same bin edges.

## Execution and custody

The pinned registry, raw inventory and cohort are mandatory inputs. The blind execution tool
must verify model/source/data identities before producing predictions, write one
case receipt and retain every failed or unavailable case. Scoring recomputes
all figures and metrics from stored common-cohort predictions. A clean relocated
replay must reproduce those scores before the assessment is called complete.

Current freeze commands, executed in the pinned fresh environment before any
current heldout evaluation, are `audit_caches.py`, `audit_fit_coverage.py`,
`run_campaign.py freeze`, then `freeze_registry.py`. MODEL_SELECTION records
exact candidate/baseline identities; BLIND_REGISTRY additionally binds current
source, dependency versions, completed fit receipts, full sample membership
and intended flaming-only spotting phases. Historical smouldering-inclusive
spotting checkpoints are excluded from all intended-variant completeness and
selection. Historical pure schedules are explicitly source-derived inference;
newly instrumented mixed membership is actual runtime evidence.

The current execution uses the fresh pinned environment at
`/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/venv-forecast/bin/python`
and repository working directory
`/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b`.
These are the exact freeze commands; the completed artifacts and their hashes
are retained with this protocol. `DATA` below is the task-local verified input
root, not the metadata-only repository folder.

```sh
PY=/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/venv-forecast/bin/python
DATA=/Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/data/forecast-v2
RUN=forecast/runs/20261030_perimeter_trained/execution_v3
"$PY" research/forecast-v2/scripts/audit_fit_coverage.py --model-root . --input-root "$DATA" --cache-root "$DATA/campaign-work" --run-root "$RUN" --cache-audit research/forecast-v2/CACHE_AUDIT_FINAL.json --out research/forecast-v2/FIT_COVERAGE.json
"$PY" research/forecast-v2/scripts/run_campaign.py freeze --attempt 3
"$PY" research/forecast-v2/scripts/freeze_registry.py --model-root . --run-root "$RUN" --selection research/forecast-v2/MODEL_SELECTION.json --out research/forecast-v2/BLIND_REGISTRY.json
```

The dependency order is complete fit coverage, MODEL_SELECTION, this document
with the exact checkpoint/baseline table, then BLIND_REGISTRY. This document
does not embed the hash of its own registry: the registry pins this document's
bytes. Later public registration, release and independent review sidecars pin
the already frozen bundle without editing this document or registry. Their
unknown future identities are prescribed execution inputs, not blank current
model identities or discretionary scientific choices.

Before future input access, the owner registers this exact document, registry
and source bundle publicly on OSF. A named independent verifier must establish
that registration preceded the true first public release and that the source
was not previously accessed for model selection. If the true first release
predates registration, this version cannot claim a blind test; do not choose
a later release to manufacture that chronology. A local URL or caller boolean
cannot satisfy this gate.

The required pre-run review is a pinned JSON receipt with schema
`wfg.forecast-blind-documentary-clearance/1`, decision
`HUMAN_ATTESTED_DOCUMENTARY_CLEARANCE` and scope
`pre_run_registration_first_release_and_access`. It includes the verifier's
name, affiliation and independence statement; exact registry, inventory,
source closure, input closure and case-membership hashes; immutable public
registration and publisher-release references and UTC times; pinned nonempty
reviewed evidence for public OSF registration, publisher-first-release
chronology and no pre-registration source access; a pinned signed attestation
with signature description; reviewed/signed UTC times; and explicit limits.
The registration artifact must pin the registry hash and the publisher receipt
must pin the exact source ZIP. Times require registration < release <= review
<= signature, with no future signature time. The machine checks local bytes
and chronology consistency only. It never authenticates human independence,
a signature's identity, publisher priority or OSF truth.

The executable receipt contract uses these exact JSON keys. Values below are
future evidence, not identities fabricated by this task. `bindings` must equal
`clearance_bindings(registry, cohort)` from the source-pinned blind tool:
`registry_sha256`, `inventory_manifest_sha256`, `source_closure_sha256`,
`input_closure_sha256` and `case_membership_sha256`. Object digests are SHA-256
of UTF-8 `json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)`;
case membership is sorted by event, normalized UTC cutoff and endpoint.
`registration` contains `immutable_url`, `registered_utc` and
`registry_artifact_sha256`; `publisher_release` contains `immutable_url`,
`public_release_utc` and `archive_sha256`. `verifier` contains nonempty `name`,
`affiliation` and `independence_statement`. `attestation` contains `path`,
`sha256` and `signature_description`. Every `evidence_reviewed` entry contains
`path`, `sha256`, `immutable_url` and `purpose`. Required purpose values are
`public_osf_registration`, `publisher_first_release_chronology` and
`no_pre_registration_source_access`; post-score review additionally requires
`independent_relocated_replay_execution` and `primary_claim_and_completeness`.
`limits` is a nonempty list of nonempty statements. Top-level `reviewed_utc`
and `signed_utc` require explicit zero UTC offsets. All evidence/attestation
paths are relative to the pinned future input root and refer to nonempty files.

The cohort attaches the pre-run receipt through exactly
`"documentary_clearance": {"path": "review/pre_run_clearance.json", "sha256": "<actual receipt SHA-256>"}`.
The cohort's `registration` uses `url`, `registered_utc` and `registry_sha256`.
Its `inventory` uses `path`, `sha256` and the entire derived `exclusions` array.
Its `cases` equal all authoritative inventory US cases plus every prescribed
Korean window, with event, cutoff, endpoint, year and reference_kind. Its
`input_sha256` pins every consumed scientific source, raw-release inventory
and publisher first-release attestation; `source_release_utc` equals the
inventory's publisher-release time. Independent review receipts are separately
pinned by `documentary_clearance` and the finalization command. They must not
be inserted into `input_sha256`, because their own bindings contain that input
closure digest. Signed attestations sign the explicit closure/case/score
digests, without embedding the hash of a receipt that itself embeds the
attestation hash. Documentary evidence files are pinned by each receipt's
`evidence_reviewed` and `attestation` entries. This ordering avoids circular
self-hashes. No field may replace missing evidence with an assertion of
machine authentication.

After the future cohort manifest and independent pre-run receipt are prepared,
these commands produce every numerical score. `INPUTS`, `REGISTRY`, `COHORT`,
`ENTRIES`, `SCORES`, `REPLAY`, `APPROVAL` and `FINAL` are fixed paths declared in
the signed execution record; approval is relative to INPUTS and its exact SHA
is independently pinned. The future cohort must include the complete raw
inventory exclusions and all authoritative US cases plus separately labelled
Korean windows. No caller-selected list can replace raw inventory membership.
`INVENTORY` is that pinned manifest file, `INVENTORY_SHA` its actual SHA-256,
`INVENTORY_REPORT` the adapter's retained output, and `APPROVAL_SHA` the actual
post-score receipt hash. These are paths/identities fixed before execution,
not selectable outcomes. Use the exact registry-pinned dependency versions in
both source trees. `python` below denotes that interpreter. `RELOCATED` is an
absolute distinct directory containing an exact copy of the registered source
and model bytes; its own blind script must execute the replay command.

```sh
python research/forecast-v2/scripts/blind_inventory.py --input-root INPUTS --manifest INVENTORY --manifest-sha256 INVENTORY_SHA --out INVENTORY_REPORT
python research/forecast-v2/scripts/blind_test.py validate --registry REGISTRY --cohort COHORT --model-root . --input-root INPUTS
python research/forecast-v2/scripts/blind_test.py run --registry REGISTRY --cohort COHORT --model-root . --input-root INPUTS --out ENTRIES
python research/forecast-v2/scripts/blind_test.py score --registry REGISTRY --cohort COHORT --model-root . --input-root INPUTS --entries ENTRIES --out SCORES
python RELOCATED/research/forecast-v2/scripts/blind_test.py score --registry REGISTRY --cohort COHORT --model-root RELOCATED --input-root INPUTS --entries ENTRIES --out REPLAY
```

Absent pre-run documentary clearance remains NOT_READY and blocks prediction.
Software-complete scoring remains SCORED_PENDING_INDEPENDENT_REVIEW with final
superiority false. Any failed or unavailable case prevents every complete-
cohort primary promotion field; descriptive subset criteria remain separate.

A second named independent review must attest a clean, separately executed
relocated replay of these exact scores. Its scope is
`post_score_independent_relocated_replay_and_claim`, with all pre-run bindings
and evidence plus the score, replay and original prediction-receipt hashes,
absolute relocated source root, executed command, verifier identity and replay
output hash. The two score files must be byte identical; matching copied files
alone are not proof of independent execution. Reviewed evidence additionally
covers independent replay execution and primary-claim/completeness review.
Post-score approval must follow the completed original run. Finalization
recomputes the decision from the bound numerical fields and completeness; a
caller-supplied criterion flag has no authority.

The post-score receipt adds exact `scored_artifacts` keys `score_sha256`,
`relocated_replay_sha256` and `run_receipt_sha256`. Its `independent_replay`
contains absolute `source_root`, the actually executed `command` argument
array, `verifier_name` equal to the named review verifier, and `output_sha256`
equal to the independently produced REPLAY file hash. This source_root must
differ from the original model root. These additions do not change any
pre-run input-closure digest or rewrite the frozen registry/protocol.

```sh
python research/forecast-v2/scripts/blind_test.py finalize --registry REGISTRY --cohort COHORT --model-root . --input-root INPUTS --scores SCORES --replay REPLAY --approval APPROVAL --approval-sha256 APPROVAL_SHA --out FINAL
```

No external OSF registration or future source access was performed by this
task. The human review procedure is a frozen future execution prerequisite,
not a discretionary choice to be made after outcomes.

## Scope and limits

This is a blind retrospective test of mapped-extent forecasts within predefined
archive rectangles. Those rectangles can use hindsight and do not establish
prospective landscape detection. A positive result would remain conditional on
one archive, repeated cutoff weather, masks, lattice, fuel scenarios and the
fixed model family. It would not establish physical flame accuracy, calibrated
joint trajectories, continuous thermal truth or operational evacuation safety.
