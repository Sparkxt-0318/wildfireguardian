# Bound certificates for the F-DYN no_reentry/2 packets (MANIFEST_v3_7): rule (written before any run)

Source: Leo's `no_reentry/2` (NOREENTRY2_RULE.md, approved c22a59d9; MANIFEST_v3_7 sha 7c178267). Nora passed it
WITH NOTES in LEDGER-FIRE row 66 (verification/nora-fire 69d7a3ee). The orchestrator made it the person-facing default
and asked for bound WFGC 2 certificates from the start, as a tracked task with per-row checkpoints.

## 1. What is certified

- The F-3.2 integer-second contact relaxation of each (packet, origin, departure) request. Requests come from Leo's
  `fdyn/requests.py` at the manifest's commit.
- Each claim is ROUTE with arrival T, or NO_ROUTE.
- The scope is the relaxation (CERTIFICATE_SPEC §5). It covers contact only. It says nothing about radiation, dose or
  peak. Nora's note (c) applies: under the F1 convention, cells closed from 0 radiate for the whole horizon. That
  matters for exposure, not for these certificates.
- Under no_reentry/2, every cell in C0 (burned at or before the start) and every cell born later is blocked until
  H. A NO_ROUTE therefore means no route avoiding the whole burned and burning set from t = 0. It is not a statement
  about a leave-by time band.

## 2. Gates per packet (all must hold before any row is certified)

- **G-A, identity.** The packet is built from MANIFEST_v3_7 at Leo's commit, and its writer identity records
  transform `no_reentry/2`. The packet dir, the HAZARD sha256, the npz sha256 and the writer identity are recorded.
- **G-B, routable and supported.** `routable_contact_model` (default guards) accepts the packet:
  - no HAZARD-only marker;
  - no NaN or −inf births;
  - a complete write;
  - full `support`.

  A refused packet is reported as REFUSED with its reason, and none of its rows is certified. Envelope packets are
  expected to be refused here.
- **G-C, P1 consistency.** Flame cells from HAZARD.json, from the raw arrays and from ContactModel must agree:
  - raw vs ContactModel: 0 differences;
  - HAZARD vs ContactModel: 0 differences, except later interval ends by less than 1 µs (X1 rule 2 tolerance).

  X1 rule 3 (integer instances for every origin) is not a gate, because O2 per row covers the instance.

## 3. Per row (one request)

1. `build_instance` on (graph, request, routable ContactModel).
2. Run `generate.certify`, then `bind_bundle.to_v2` with `bind_digests.digests(graph, packet, request file)`.
3. Run `verify_bound.verify` with the same files. A row counts only if it prints **FULLY_BOUND**. That requires:
   - both checkers report LABELS_MATCH with the same claim and T;
   - the T7(a) structure check passes;
   - T7(b) O2 gives 0 differences.
4. Record per row:
   - packet, origin, departure;
   - claim, T, I;
   - bundle sha256 and bytes;
   - the verify_bound verdict, step and detail;
   - wall times.

   Bundles are kept outside git; their sha256 is in the record.

**Checkpointing.** Each finished row is appended to a JSONL file and flushed. A restart skips the keys already
recorded and re-checks the recorded bundle sha. Any row that is not FULLY_BOUND is reported with its step. It is
never retried silently and never dropped.

## 4. Pass and report

- Per packet: PASS iff the gates hold and every row is FULLY_BOUND. Report ROUTE and NO_ROUTE counts.
- REFUSED packets (G-B) are listed separately. They are not failures of certification; they are packets on which
  F-3.2 issues no certificate.
- Label (exact):
  - "F-DYN no_reentry/2 (person-facing default): relaxation certificates, bound and verified by verify_bound (both
    checkers, structure, O2); contact only, no radiation".
  - Add the variant's own label where it has one. For example, burnset rows keep the burn-set wording fixed by the
    orchestrator.

## 5. Scope

Decided by the orchestrator before the run starts. The options are listed with the measured cost per row
(section 6).

## 6. Measured cost

Filled in from a timing run on one Nora sample packet (Uiseong 0324T09 h5 kriged_mean /2), before the scope decision.
