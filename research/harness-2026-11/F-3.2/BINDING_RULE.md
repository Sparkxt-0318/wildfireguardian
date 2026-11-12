# F-3.2 certificate-to-request binding: rule (written before any code)

Status: rule only. Implementation follows after review; Mira verifies.

## The gap today

- A `.wfgc` bundle embeds its integer instance `I`. Both checkers test the certificate against that embedded `I`.
- So a bundle is internally consistent wherever it is moved. If bundle A is handed over as the answer to request B,
  both checkers ACCEPT it, because it is checked against A's own instance, not B's.
- The input shas (graph, request, `HAZARD.json`, packet arrays, build summary) exist only in the `.wfgc.json`
  sidecar and the run manifest. Neither checker reads them (FORMAT.md: "Checkers need not compute it").

## Rule

**R1. Format version 2 carries a BIND section.**
- Header `WFGC 2`.
- A `BIND` section sits between `END_INSTANCE` and `CLAIM`.
- Each digest is written as 8 integers in `[0, 2^32 - 1]`: the SHA-256 in big-endian 32-bit words. This keeps the
  stream integer-only for the C reader.
- The fields are fixed, in this order:
  1. `I`: SHA-256 of the exact bytes from the `I` of `INSTANCE` through the newline after `END_INSTANCE`.
  2. `G`: SHA-256 of the graph file bytes.
  3. `P`: SHA-256 of the `HAZARD.json` bytes.
  4. `W`: the packet's `packet_writer_sha256`. All-zero if the packet declares none; the sidecar then says so.
  5. `Q`: SHA-256 of the canonical request bytes (JSON, sorted keys, separators `,` and `:`, UTF-8). It covers
     origin, destination(s), departure, horizon, dwell, policy id and limits.
- In version 2, the sidecar's arrays and build-summary shas stay in the sidecar. P1/X1 already ties the arrays to
  `HAZARD.json`.

**R2. Self-binding (both checkers, no external input).**
- Each checker computes `I` from the bytes it read and rejects on mismatch (`REJECT BIND_INSTANCE_DIGEST`).
- The C checker gets its own SHA-256, written from FIPS 180-4, sharing no code with the Python side, and tested on
  the NIST short-message vectors.

**R3. External binding (both checkers).**
- The consumer, who holds its own graph, packet and request, supplies the expected `G P W Q` digests on the command
  line (`--expect G=<hex>,P=<hex>,W=<hex>,Q=<hex>`).
- The checker rejects if any one differs (`REJECT BIND_<field>`), or if the bundle has no BIND section.
- ACCEPT is printed only after both binding steps and C0–C4 pass. The output line becomes
  `ACCEPT <claim> <T> BOUND <first 16 hex of I>`.
- Without `--expect`, a version-2 bundle that passes prints `ACCEPT <claim> <T> UNBOUND`. Exit status is still 0,
  but no report may count it as a bound result.

**R4. Version 1 bundles.**
- They keep their current output, `ACCEPT <claim> <T>`, and are reported as UNBOUND.
- Existing committed results are unchanged and are relabelled "UNBOUND (v1)" where quoted, not re-certified silently.

**R5. What binding does and does not prove.**
- It proves: this certificate was issued for an instance whose bytes hash to `I`, under inputs that hash to the
  consumer's own `G P W Q`. A bundle moved to another request, or with any edited instance byte, is rejected.
- It does NOT prove that `I` is the correct translation of (G, P, Q). A generator could write correct `G P W Q`
  labels next to a wrong instance.
- That translation is obligation O2: `derive_instance.py` independently re-derives `I` from the raw inputs, and
  its SHA-256 must equal BIND `I`.
- A bundle counts as **fully bound** only when R2, R3 and the O2 comparison all pass. Each step is reported
  separately.

## Tests (written before the code; both checkers must pass every case)

- **T1 swap.** Bundle for request A, checked with request B's expected digests → REJECT (`BIND_Q`, or the first
  differing field). Run it on pairs that share graph and packet but differ only in the request (origin, or
  departure 0 vs 7200), so that `Q` alone has to catch it.
- **T2 single-digest mutation.** Flip one bit in each of the 5 fields in turn → REJECT with that field's reason.
- **T3 instance edit.** Change one instance token, for example one `D_j` or one EB bound, and leave BIND untouched
  → `REJECT BIND_INSTANCE_DIGEST`. This holds even where the edited certificate would still pass C0–C4.
- **T4 missing or misplaced BIND.** No BIND, BIND after CLAIM, a field out of order, or a word ≥ 2^32 → REJECT.
- **T5 unbound.** A valid v2 bundle without `--expect` → `ACCEPT … UNBOUND`, and the harness counts it as unbound.
- **T6 positive.** For every case in the existing mutation suite (30 file tests + 2 extra), the v2 form with
  correct `--expect` → the same ACCEPT/REJECT as today, plus `BOUND`.
- **T7 O2 tie.** On the frozen 20-request panel, `derive_instance.py`'s SHA-256 equals BIND `I` for every bundle.

## Order of work

1. Mira reviews this rule.
2. Implement: the C SHA-256 with vectors, both checkers' BIND parsing, then T1–T7.
3. Re-emit the panel and the F-DYN v3.4 bundles as v2 with `--expect`, in a separate result file. The v1 files stay
   as they are.
4. Use v2 bound bundles for Priya's four stage-Z refusals: Hongseong FN1 and FX1, Miryang FD1 and FX1.
