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
  - Waiting rule, form (S) for single-departure results (F-3.1/WAITING_SENSITIVITY_RULE.md @ 1b792c77; orchestrator,
    2026-11-13 00:13 UTC, verbatim): "The trip starts at the stated time. Once moving, a stop is allowed only at a road
    dead end (a graph dead-end node), which may be a short detour off the route; waiting is not allowed at any other
    node, including the start unless it is itself a dead end. Other departure times are separate results."
  - Departures 0 s and 7200 s are separate results. They are never read as a leave-by window: the relaxation is not
    monotone in departure under dead-end-only waiting.
  - Where reported, "waiting allowed everywhere" is a labelled sensitivity row, never the default.

## 5. Scope (orchestrator, 2026-11-12 ~23:05 UTC: option (a))

- **Starts:** Nora's two checked starts, Uiseong 20250324T090000Z and Yeongdeok 20250325T110000Z.
- **Horizon and variants:** h5 × {kriged_mean, firms_early, envelope_burnset}. That is **6 packets**.
- **Envelope packets:** the h5 envelope packet of each start is also run through the gates, to record its expected
  REFUSED status. It produces no rows.
- **Departures:** 0 and 7200 s. Every origin in the region's INSTANCE.json is used.
- **Uncertified:** the other **360 certifiable packets** of MANIFEST_v3_7 no_reentry/2 (366 minus these 6). They carry
  no F-3.2 certificate, and the record states this.
- **Option (b):** the 6 recorded starts × h5/h8 × 3 variants = 36 packets. It runs only if a person-facing output
  later needs it.

## 6. Measured cost (before the scope decision)

- Uiseong 0324T09 h5 kriged_mean /2: first row FULLY_BOUND, certify 11.8 s plus verify 3.4 s.
- About 15 s per row. A packet has 168 rows at the two departures, so about 42 minutes.
- All 366 certifiable packets would take about 250 h. That is why the scope is limited.
