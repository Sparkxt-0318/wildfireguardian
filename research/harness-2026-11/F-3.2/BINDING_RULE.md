# F-3.2 certificate-to-request binding: rule (written before any code)

Status: revision 2.2 (Mira ledgers 99-101). Implemented; see xcheck/results/binding_*.json. Implementation follows; Mira verifies.

## The gap today

- A `.wfgc` bundle embeds its integer instance `I`. Both checkers test the certificate against that embedded `I`.
- So a bundle is internally consistent wherever it is moved. If bundle A is handed over as the answer to request B,
  both checkers ACCEPT it, because it is checked against A's own instance, not B's.
- The input shas (graph, request, `HAZARD.json`, packet arrays, build summary) exist only in the `.wfgc.json`
  sidecar and the run manifest. Neither checker reads them (FORMAT.md: "Checkers need not compute it").

## Rule (revision 2, after Mira's review, ledger 99)

**R1. Format version 2 carries a BIND section.**
- Header `WFGC 2`.
- A `BIND` section sits between `END_INSTANCE` and `CLAIM`.
- Each digest is written as 8 integers in `[0, 2^32 - 1]`: the SHA-256 in big-endian 32-bit words.
- The fields are fixed, in this order:
  1. `I`: SHA-256 of the exact bytes from the `I` of `INSTANCE` through the newline after `END_INSTANCE`.
  2. `G`: SHA-256 of the graph file bytes.
  3. `A`: the **routed-hazard digest**: SHA-256 of the canonical bytes (R6) of exactly what the routing path and its
     guards read (rev 2.1, Mira ledger 100):
     - from `constructed_arrays.npz`, these four keys, each as `name`, `present`, `dtype.str`, `shape` and C-order
       data bytes:
       - `ignition_time_s` and `current_active`: read by `ContactModel.from_packet`, `contact.py:88-96`;
       - `support`: read by the Tier A/R unknown-support certificates. F-9.3 masked and optimistic packets differ
         only here;
       - `per_cell_law_HAZARD_only`: the routability marker read by `p1_check.require_routable_arrays`.

       A key missing from the `.npz` enters as `{name, present: false}`. Absence is bound explicitly, never skipped.
     - from `REPORT.json`: `native_metadata.construction.assumptions.burning_duration_s`, `...initial_remaining_s`,
       and the member ids (`rows[0].request.incurred` keys, in order).

     Raw file bytes are NOT used:
     - the `.npz` zip entries carry write timestamps;
     - `REPORT.json` and `HAZARD.json` embed an absolute module path (Mira ledger 74).

     So a consumer that rebuilt the same packet elsewhere would get a false REJECT. `HAZARD.json` is not bound: the
     router does not read it, and X1/P1 ties it to the arrays.
  4. `W`: `packet_writer_sha256` from `HAZARD.json` `provenance.identity`.
     - All-zero means "the packet declares none".
     - It is compared as an exact value. All-zero matches only a consumer whose own packet also declares none.
       It is never a wildcard.
  5. `Q`: SHA-256 of the canonical bytes (R6) of the **request projection `wfg.request-projection/1`**. These are
     exactly the request fields that `build_instance` and the at-issue checks read (`frontend.py`):
     - `position.node`, `incoming_edge`, `departure`, `horizon`;
     - `destinations[]` as `{node, dwell, open_intervals}`, in request order;
     - `budgets.dose`, `incurred`.

     Fields outside the projection do not enter Q. Test T8 proves that none of them changes the instance.
- The sidecar keeps the raw file shas (graph, request, `HAZARD.json`, arrays, build summary) for provenance. They
  are not part of the binding.

**R2. Self-binding (both checkers, no external input).**
- Each checker computes `I` from the bytes it read and rejects on mismatch (`REJECT BIND_INSTANCE_DIGEST`).
- The C checker gets its own SHA-256, written from FIPS 180-4, sharing no code with the Python side.

**R3. External binding (both checkers).**
- The consumer computes `G A W Q` from its own inputs, with the shared reference tool `bind_digests.py`. The
  C checker never parses JSON or npz.
- The consumer supplies them as `--expect G=<hex>,A=<hex>,W=<hex>,Q=<hex>`.
- The checker rejects on any difference (`REJECT BIND_<field>`), on a missing BIND section, or on a version-1
  bundle (`REJECT BIND_MISSING`).
- ACCEPT is printed only after R2, R3 and C0–C4 pass: `ACCEPT <claim> <T> LABELS_MATCH <first 16 hex of I>`.
  (Rev 2.2: renamed from `BOUND`, Mira ledger 101 N1. The checker can only compare the labels the generator
  wrote with the consumer's digests. It cannot tell whether those labels are true. See R5.)
- Without `--expect`, a version-2 bundle that passes prints `ACCEPT <claim> <T> UNBOUND`. No report counts it as
  bound.

**R4. Version 1 bundles.**
- Without `--expect` they keep their current output and are reported as UNBOUND (v1).
- With `--expect` they REJECT (R3).
- Committed v1 results are not re-certified silently.

**R5. What binding does and does not prove (rev 2.2).**
- R2 proves that the BIND section names the instance actually in the file: `I` matches its bytes.
- R3 proves only that the generator's LABELS `G A W Q` equal the consumer's digests. It catches honest mix-ups:
  a bundle moved to another request, a stale packet, the wrong graph.
- R3 does NOT catch a wrong or dishonest generator. Mira (ledger 101) relabelled the FN1 bundle with FX1's
  `G A W Q`, and both checkers printed `LABELS_MATCH`.
- What ties the instance to the consumer's inputs is T7: the consumer re-derives from its OWN graph, packet and
  request, and compares against the instance in the bundle. In Mira's relabel case only T7 caught it (O2: 2
  differences).
- So `LABELS_MATCH` is never quoted as "bound" on its own.
- O2 today is a semantic comparison, not a sha: `derive_instance.compare_semantic`, 0 differences required. T7
  uses exactly that, against the instance **parsed from the bound bundle's own bytes** (the bytes hashed into
  `I`), not against the solver's in-memory object.
- **Fully bound** = R2 + R3 + T7(a) + T7(b). Each step is reported separately.
  - T7(a) is the structure check against the consumer's graph and request: V, E, tail/head/D per edge, WAITABLE,
    FORBID, ORIGIN, START, DEP, HOR. O2 never re-derives any of these.
  - T7(b) is O2: `compare_semantic`, 0 differences.
  - Consumers run `verify_bound.py`: bundle plus their own graph, packet and request → both checkers with
    `--expect`, then T7(a) and T7(b). It prints `FULLY_BOUND` only when every step passes.

**R6. Canonical bytes.**
- RFC 8785 (JCS) over a JSON value built only from integers, strings, arrays and objects. There are no floats.
- Rationals and float times are first converted to the exact reduced string `"p/q"`, or `"p"` when q = 1, using
  `fractions.Fraction(x)` on the stored value.
- Strings are NFC-normalised. `allow_nan` is false; a non-finite value is a REJECT at digest time.
- Array data bytes enter as lowercase hex strings of the C-order buffer.
- The reference tool asserts that its output equals a JCS implementation on every digest it computes in the tests.

## Tests (written before the code; both checkers must pass every case)

- **T1 swap.** Bundle for request A, checked with request B's expected digests → REJECT. Run it on pairs that share
  graph and packet but differ only in the request (origin, or departure 0 vs 7200), so that `Q` alone has to catch
  it.
- **T2 single-digest mutation.** Flip one bit in each of the 5 fields in turn → REJECT with that field's reason.
- **T3 instance edit.** Change one instance token and leave BIND untouched → `REJECT BIND_INSTANCE_DIGEST`. This
  holds even where the edited certificate would still pass C0–C4.
- **T4 malformed BIND.** No BIND, BIND after CLAIM, a field out of order, or a word ≥ 2^32 → REJECT. A version-1
  bundle with `--expect` → `REJECT BIND_MISSING`.
- **T5 unbound.** A valid v2 bundle without `--expect` → `ACCEPT … UNBOUND`, and the harness counts it as unbound.
- **T6 positive.** For every case in the existing mutation suite (30 file tests + 2 extra), the v2 form with correct
  `--expect` → the same ACCEPT/REJECT as today, plus `LABELS_MATCH`.
- **T7 O2 tie.** On the frozen 20-request panel, `compare_semantic` on the instance parsed from each bound bundle →
  0 differences.
- **T8 request-projection completeness.** For every field of every panel request, each top-level field and each
  destination subfield, mutate it in turn (change a value, or delete it where optional). Required:
  - `Q` changes, OR
  - the rebuilt instance bytes are identical, OR
  - `build_instance` refuses the mutated request.

  Any field that changes the instance without changing `Q` fails the test.
- **T9 routed-hazard completeness.** Same as T8, for the packet. It also requires that adding or removing `support` or the marker key changes `A`, and that the F-9.3 masked/optimistic pair has different `A`.
  - perturbing one element of each array in `constructed_arrays.npz`, and each scalar of `REPORT.json`, must change
    `A`, or leave the instance bytes identical, or be refused;
  - rewriting the `.npz` with a different zip timestamp, or editing an absolute path in `REPORT.json`, must leave
    `A` unchanged.
- **T10 C SHA-256.** The NIST short vectors; multi-block messages; lengths 55, 56, 63, 64 and 65 bytes; the
  one-million-`a` vector. Every committed v2 bundle's `I` is also cross-checked against Python `hashlib`.

- **T11 relabel (rev 2.2).** For every panel pair sharing graph and packet: rewrite bundle X's G A W Q with Y's
  digests (I unchanged), then run `verify_bound.py` with Y's inputs. Both checkers print `LABELS_MATCH`, by
  design. `verify_bound` must NOT print `FULLY_BOUND`.

## Order of work

1. Mira reviews this rule.
2. Implement: the C SHA-256 with vectors, both checkers' BIND parsing, then T1–T7.
3. Re-emit the panel and the F-DYN v3.4 bundles as v2 with `--expect`, in a separate result file. The v1 files stay
   as they are.
4. Use v2 bound bundles for Priya's four stage-Z refusals: Hongseong FN1 and FX1, Miryang FD1 and FX1.
