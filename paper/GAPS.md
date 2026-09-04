# Gaps — what the manuscript still lacks

Every `[GAP: …]` in `manuscript.md` has a row here (the gate checks both ways).
Close a gap by replacing the marker with prose backed by an artifact and
deleting the row. Gaps marked *after sprint* need the laptop-only raw bundle or
the author.

| # | where | what is missing | closes when | after sprint? |
|---|---|---|---|---|
| G5 | §4.7 Results | the provenance of the detection reference clock. Every delay in Table 3 is measured from `fire_manifest.json`'s `start` field, which the manifest marks "provenance only", sources nowhere, and elsewhere describes as the ignition. `docs/detection_floor.md` §1 reads it as a 신고 (report) time and draws from that the conclusion that GK2A rang after the telephone; no committed artifact supports the re-labelling, so the manuscript states the delays against the recorded occurrence time and makes no ordering claim. Until this is settled the paper cannot say whether the satellite beat the call, and the repository's trigger-design rationale rests on an unsourced reading | the author supplies, for at least one fire, the KFS / 119 / 중대본 record giving the 신고접수시각, or the acquisition note saying where the minute came from; then it is registered with agency and date and §4.7, §1, §5 and the abstract can state the ordering. Raised by the lap-2 reviewer (NEEDS_HUMAN NH-019) | no |
| G2 | §5 Discussion | structured expert consultations (fire-service duty officer, village head, social worker) in the project's consultation format, as design feedback rather than collected data; any quotation needs the author's consent handling first | the consultations happen and the author clears the quotations (NH-009) | yes |
| G3 | §6 Limitations | the leak-free Yeongdeok fold: refit the Yeongdeok LOFO fold with the co-located Uiseong-Andong fire excluded, re-simulate the canonical field, and route the same 458 origins, reporting the three-bucket counts as new filenames | the raw acquisition bundle on the author's laptop is available and WFG-032 runs | yes |
| G4 | §6 Limitations | **the hindsight-field routing arm — the single most load-bearing gap in the paper.** A third pass over the same 458 origins on a field rasterised from the *observed* FIRMS detections for Yeongdeok 2025, reporting how many of the 42 fire-blind routes actually intersect observed burn inside the walker's arrival window, and how many forecast-aware routes cross observed burn the model never flagged. Until it runs, "saved" means "re-routed around a model-flagged cell", not "away from where the fire went", and with pooled recall 0.138 that distinction is not cosmetic | the observed detections are available. ⚠ Checked 2026-09-03: `data/snapshots/firms-manifest_yeongdeok-2025_20260723_1aa75824.json` is committed and records 2,290 detections spanning 2025-03-25T12:25 to 2025-03-27T04:28, but the detections themselves (`yeongdeok_2025_detections.csv`) live under the git-ignored `data/raw/firms_data/`, which is absent from a fresh clone. So this arm needs the author's laptop too — it is cheaper than G3 (no refit, no re-simulation, reuses the committed walk graph and origin list) but it is not runnable in the cloud sandbox | yes |

## ⚠ Length pressure, 2026-09-04

The body is **7,479 words against a 7,500 hard fail and a 7,000 aim** — twenty-one words
of headroom. This lap added the sourced motivation, the closed G1 and the whole of §4.7, and
paid for about two thirds of that by compressing existing prose and moving three lineage
notes into figure and table captions, which `build_docx.py` does not count. The next lap
that adds anything must first take words out. The condensation candidates, in order, are
§6 (still the longest section at roughly 1,000 words, with several items that repeat a
Results caveat verbatim), §4.5, and §4.6's second half. No number and no caveat may be
dropped to make room; captions are the free space.

⚠ **And the 20-page limit is not actually measured.** `check_paper.py` enforces words, and
this file's budget line converts them at roughly 16 pages per 7,000 words. A crude recount
over the built `.docx` on 2026-09-04 — 8,909 words including captions, tables and 25
references, plus seven full-width figures — lands nearer 21 pages instead. LibreOffice is
present in the cloud sandbox but refuses to load the built document, so no PDF and no real
page count could be produced. Until one is, the "under 20 pages" claim is an inference from
a constant nobody has checked. Closing this needs either a working converter or a
words-per-page constant re-derived from the built document.

## Notes on gaps that were closed

- **G1 closed 2026-09-04 (paper lap 2).** The age composition is now written from two
  openable sources verified this lap: Yeongdeok-gun's casualty notice of 2025-04-29
  (mean age 84 of ten dead, maximum 101), quoted at p. 9 of the Greenpeace/녹색전환연구소/
  우리함께 survey report, and that survey's own age table (63.9 % of 296 respondents aged
  60–79, 17.9 % aged 80 or over). Both carry their caveats in the text: the casualty
  figures are re-cited by the report rather than measured by it, and the survey is a
  non-probability sample of survivors from which the dead are absent by construction.
  The same lap replaced the manuscript's opening damage figures, which had restated the
  WWA rapid study's differently-scoped tallies, with the chain-scoped provincial values.
- The abstract, Related work, Methods §3.3–§3.5, Results §4.1–§4.6, Discussion,
  Limitations and Conclusion were all `[GAP]` markers before 2026-09-03 and are
  now prose backed by committed artifacts.
- The `References` section is generated by `build_docx.py` from
  `references.bib` at build time and therefore does not appear as a heading in
  `manuscript.md`; it is present in the built `.docx`.
