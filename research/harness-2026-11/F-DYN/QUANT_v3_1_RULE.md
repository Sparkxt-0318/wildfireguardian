# F-DYN v3.1 quantization convention (amendment; fixed before any code change or rebuild)

Orchestrator decision, 2026-11-12. Finding by Thomas (F-3.2 O2 independent derivation).

## Why

- FIRMS and VIIRS detection times are minute-resolution, so (a − h)·3600 is meant to be an **exact multiple of
  300 s** for many cells.
- v3 computed it in binary64 hours. A representation error of ±1e-12 then flips `floor_300` by a whole quantum.
- Over all 61 built starts (cells igniting within 8 h):
  - firms_early: **612 of 61,759** cell-starts land one quantum earlier than the stated rule.
  - firms_constrained, the envelope hi: **102 of 62,491**.
  - kriged_mean and envelope_sound: 0.
  - None land later.
- v3 is therefore conservative, but it can only be reproduced by copying float operations. An independent checker
  cannot implement that.
- Thomas's note 4: some envelope ends are up to 4.5e-13 s earlier than exact. That is anti-conservative and
  negligible, but not zero.

## Rule (v3.1, `wfg.fdyn.quant/3.1`)

1. **Integer milliseconds since t0** (2025-03-22 02:24:00 UTC) for every time that is floored:
   - **Start h.** A whole-hour UTC start, so start_ms is an exact integer.
   - **Timestamp-derived arrival values.** These are FIRMS/VIIRS detection or overpass times (minute resolution),
     the ignition time 0, and the "beyond horizon" constant 10^6 h. They are **exact integers**. Each variant file
     records which cells are timestamp-derived (`timestamp_exact` mask). The integer is recovered as
     round(arrival_h · 3,600,000); the binary64 error is below 1e-6 ms, so the recovery is exact.
   - **Real-valued arrival values.** These are the kriged TOA raster and every cell of a variant that keeps the kriged
     value. They are **rounded to the nearest millisecond** (round-half-to-even). Soundness is stated relative to
     arrival times rounded to 1 ms. The worst-case anti-conservative shift is **a start less than 0.5 ms later than
     the real-valued arrival**.
2. **rel_ms = arrival_ms − start_ms** (int64).
3. **Ignition (scalar law).** t = floor_div(p·rel_ms − q·shift_ms, q·Q_ms) · Q, clamped at 0, using integer
   arithmetic only. The member speed factor is the rational p/q: central 1/1, faster_1.33x 3/4, faster_2x 1/2.
4. **Envelope (per-cell law).** births = floor_div(max(rlo_ms, 0), Q_ms)·Q and hi_rel = floor_div(max(rhi_ms, 0),
   Q_ms)·Q, both integers. The end hi_rel + T + Q ≥ hi + T then holds **exactly**, which removes note 4.
5. **Comparisons** (burned out, still burning at the start, inside the horizon) use the same integers, with T_ms =
   T·1000 (T = 3,970 s, an integer).
6. **Recording.**
   - Plan and packet metadata carry `quantization: wfg.fdyn.quant/3.1` and the count of cells whose value was rounded
     to 1 ms.
   - The manifest becomes `wfg.fdyn.manifest/2` (`MANIFEST_v3_1.json`, `packets_v31/`).
   - `MANIFEST_v3.json` stays in place, listed as **superseded**, with this reason.

## Expected effect (stated in advance)

- The 612 firms_early and 102 firms_constrained cell-starts above move **300 s later**, to the stated rule's value.
- kriged_mean and envelope_sound are unchanged.
- Nothing else differs.

## Acceptance

- **Diff.** v3 against v3.1 for all 488 manifest entries at the schedule level (ignition times and hi_rel arrays),
  plus a full packet diff of every v3 packet already on disk. Every difference is reported.
- **Thomas's independent derivation** must match v3.1 **with integer equality**, on a sample that includes boundary
  cells.
- Results already computed on v3 kriged_mean packets stay valid if the diff confirms they are unchanged.
  firms_early and envelope results are recomputed on v3.1.
