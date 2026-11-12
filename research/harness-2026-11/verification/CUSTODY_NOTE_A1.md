# A1 part c: minimal custody procedure (design note)

Requested by the orchestrator on 2026-11-12 (16:02Z and 16:03Z), after an external review passed on by the owner. Iris reads it. Hannah wrote it.

**Scope.** The full custody design belongs to CR1 (`S-D9/clean_replication/`). For A1, this note covers only the minimal procedure that is a **condition of opening part c**. It is not a condition of the stage-2 freeze.

## 1. What exists today

**The sealed geometry is public.**
- Part b, c and d perimeters come from the public Mendeley NIROPS 2020–24 archive (`NIROPS_2020_2024_R1_R6.zip`, sha256 `b19fb16c…`).
- Anyone can download it again, so custody cannot make the geometry unavailable. It can only control who builds part-c labels and who runs the part-c scoring, and record both.

**Copies of the raw shapefile.** By the declarations (ledger rows 38 and 45), the raw shapefile is held in scratch by:
- Daniel;
- Elena;
- Owen;
- Marcus;
- Hannah: `/home/user/parta/nirops/x/`, for the part-a spot rebuild (row 39).

Victor holds only derived tables. Other sessions may hold repository checkouts, which contain the NIROPS **catalog** files but no geometry (Richard's Q7).

**Reads by fid.**
- Since 14:00Z, Daniel's reads go through `nirops_access.py`, which reads the `Incident_C` column, then everything else by fid, for allowlisted records only (row 35).
- Other sessions' code does not use it:
  - Elena's `nirops_brackets.py` uses a where-filter;
  - Marcus's `nirops_cap.py` reads the whole attribute table.

**Already exposed, which this procedure cannot undo:**
- per-incident survey timing, discovery dates, names and points of origin for all b, c and d incidents (F1–F4; row 38);
- pooled survey cadence including b, c and d (Marcus);
- whole-column reads of attributes such as DateUTC (Elena, Daniel);
- the existing scratch copies listed above.

What remains sealed: **labels, perimeters and growth of part-c fires, as built and scored.**

## 2. Minimal procedure (a condition of opening part c)

1. **Record the sealed inputs.** Before opening, the custodian records the sha256 of:
   - the raw shapefile components;
   - the part-c manifest;
   - every file the part-c build reads.

   They go into a committed `PART_C_INPUTS.json`, with the stage-2 freeze SHAs it scores against.
2. **One custodian builds and scores.** Part-c labels are built, and part-c scoring is run, only by the custodian, from the stage-2 frozen SHAs (predictors and `sd9bench`).
   - The command line, start and end times, environment and output hashes are logged in the verification ledger.
   - No worker session builds part-c labels or reads part-c label or perimeter files.
3. **Workers get scores and receipts only.** They never receive label files, per-cell outputs or perimeter geometry for part c.
   - Per-fire tables are released after the decision is recorded, in the same way as CR1 §8.
4. **Two independent runs, compared exactly.**
   - A second custodian (Nora, as in CR1) reruns the scoring from the same frozen SHAs and the same recorded inputs, in her own environment.
   - Their released-statistic hashes must match before any number is reported. A mismatch is reported as a mismatch, not resolved silently.
5. **A no-touch declaration.** At opening, every worker session declares that it will not build, read or derive part-c labels until the decision is recorded. A breach moves the affected fires to an "exposed" stratum, in the same way as CR1 §1.6.

## 3. What it cannot do

- It cannot remove the public archive or the scratch copies that already exist.
- Deleting them is optional hygiene; the orchestrator decides. It is not a guarantee.
- It cannot undo the metadata exposure in §1. That stays in the limitations wording (ACCESS_CONTROL, combined amendment).
- It cannot stop a session from re-downloading the public archive. It turns doing so into a declared, logged breach.

## 4. Cost

- **Custodian work:** one build of the part-c inputs (part a's pipeline built 490 incidents in about 30 minutes, plus terrain and landcover), one scoring run, and logging.
- **Second custodian:** one rerun.
- About half a day of session time in all. There is no new code beyond a small wrapper that records hashes and the command.

## 5. Recommendation

- Make §2 a condition of **opening part c**, not of the stage-2 freeze. The freeze fixes the predictors; custody governs the opening.
- Do not require deleting existing scratch copies as a condition. Record them (§1) and rely on the no-touch declaration plus the mechanical access audit (`access_audit.py`) to detect use.
- Carry the full custody design, with salted IDs and sealed stores, in CR1 only.
