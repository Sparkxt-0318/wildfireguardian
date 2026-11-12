# Packet consistency: arrays and HAZARD.json must express one law (rule; fixed before any code or rebuild)

Orchestrator decisions A and B, 2026-11-12. Defect found by Thomas (P1), confirmed by Mira and by Nora (ledger row 34).

## Why it happened

- A routing packet carries the hazard twice:
  - `HAZARD.json` members: breakpoints and per-bin flame and flux;
  - the array path: `constructed_arrays.npz` (`ignition_time_s`, `current_active`) together with the REPORT
    construction assumptions `burning_duration_s` (T) and `initial_remaining_s` (R).
- Array readers (`ContactModel.from_packet`, so `frontend.build_instance`, the certificates and F-BASE) apply the
  writer's scalar law: [birth, birth + T) per member event, and [0, R) for present fire.
- F-DYN's per-cell override (`fdyn/_packet_child.py`: the `envelope` per-cell end; the burn-set static law) rebuilt
  the HAZARD members but **left the arrays and REPORT on the scalar law**. The two representations therefore
  disagreed:
  - arrays-derived cells cleared after T + Q;
  - export-burned cells were missing.

  Routing on the arrays was **under-blocked** relative to the stated law.
- No check compared the two. The **builder self-check** (§C) exists to make that impossible from now on.

## A. `envelope_burnset`: one scalar law, expressed in both representations

- **Plan.** Birth 0 for every burn-set cell that is not present fire in the export. That includes export-burned
  cells, which the writer's draws do not forbid; its PRESENT_FIRE check covers only current cells.
- **Settings.** In the F-DYN path, `burning_duration_s` = H, and `consumed_fraction` = cf0 · H / T0, so the
  heat-release density fuel · ΔH · cf / T is unchanged.
- **Present fire.** R = H. The per-cell R values stay in `mask__initial_remaining_s_native`, enclosed by R as the
  source law already does.
- **Members.** The writer's own scalar loop (`rebuild_members` with the scalar end; self-checked against the writer)
  is used, **not** a separate override. HAZARD and the arrays then both give burn set ∪ present fire on [0, H).
- **Conditions (orchestrator):**
  1. The rebuilt packet's HAZARD flame bins **and flux values** must equal those of the version Nora passed (row 32;
     Yeongdeok 25T11Z h5, HAZARD sha 16eb283b…). The comparison is exact: breakpoints, every flame bin, and every
     flux value bitwise. **If any flux value differs, it is a new variant with a new name, not a fix.** That is
     reported, and no flux is forced to match.
  2. If the writer refuses births on export-burned cells, or recomputes R after the F-DYN override, **stop and
     report**. No workaround.

## B. `envelope` (bracket-start, per-cell end hi + T + Q): HAZARD-only; the array path refuses

- A per-cell end cannot be expressed with the scalar T of the array path. HAZARD.json is the **only** source for
  this variant.
- **After the writer's checks pass**, the F-DYN builder rewrites `constructed_arrays.npz`:
  - `ignition_time_s` becomes NaN everywhere (`ContactModel.from_arrays` already rejects NaN);
  - a marker array `per_cell_law_HAZARD_only` = True is added.

  BUILD_SUMMARY's `files_sha256` records the new file hash, and `fdyn.arrays_sha256_as_written` keeps the writer's
  original.
- **Label:** "HAZARD-only; not for array-based routing or certification".
- **Router code is untouched.**
- **Entry-point test.** Every array-based entry point available here must **fail loudly** on such a packet:
  - `ContactModel.from_packet`;
  - `frontend.build_instance`, via its model;
  - the replay's packet consistency check (`tools/explain_deadlines/packet.py`);
  - Thomas's F-3.2 tools that load packet arrays (`p1_check`, `cases`, `run_panel`), where runnable here.

  Any entry point that does **not** fail is reported, not patched.

## C. Builder self-check (every variant, every build)

- After a packet is written, `fdyn/consistency.py` derives the array-law intervals exactly as ContactModel does.
  For every HAZARD bin it requires two things:
  - the array active set equals the flame mask;
  - no array knot lies strictly inside the bin. A 1 µs tolerance absorbs the writer's `round_up_sum`.
- **Outcomes:**
  - The build fails on any difference.
  - For HAZARD-only variants (B), the check instead requires the array load to refuse.
- **Coverage.** Run on a sample of every variant in the new manifest, plus all packets on disk. Per-variant counts go
  in the manifest notes and the README.

## D. Manifest

- `MANIFEST_v3_4.json` (wfg.fdyn.manifest/5):
  - `envelope` is labelled HAZARD-only;
  - `envelope_burnset` uses the law in A;
  - the self-check counts are included.
- In v3–v3.3, the `envelope` and `envelope_burnset` / footprint entries are listed as **"arrays inconsistent with
  HAZARD; valid only for readers that take phases from HAZARD"**. The pinned manifests are not edited.

## E. Verification

Nora re-verifies:
- the self-check over every variant;
- her own cell-by-cell comparison;
- the replay's packet consistency check.

Thomas runs X1. For `envelope`, X1 is expected to fail by design: its arrays are refused.

## STATUS

- **Fix implemented** at 588f74e and faa89c4 (`MANIFEST_v3_4.json`).
- **Nora: PASS WITH NOTES, ledger row 37**
  (2026-11-12). Details are under STATUS in `ENVELOPE_BURNSET_RULE.md`.
- **Thomas X1:** running on the 16 v3.4 samples.
