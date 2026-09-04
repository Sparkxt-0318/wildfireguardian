# Gaps — what the manuscript still lacks

Every `[GAP: …]` in `manuscript.md` has a row here (the gate checks both ways).
Close a gap by replacing the marker with prose backed by an artifact and
deleting the row. Gaps marked *after sprint* need the laptop-only raw bundle or
the author.

| # | where | what is missing | closes when | after sprint? |
|---|---|---|---|---|
| G5 | §4.7 Results | the provenance of the detection reference clock. Every delay in Table 3 is measured from `fire_manifest.json`'s `start` field, which the manifest marks "provenance only" and sources nowhere. **Narrowed 2026-09-04 (paper lap 3), and the repository has now come to the same reading.** Checked this lap against `docs/data_provenance/fire_manifest.json` — the only copy tracked here; the copy the pipeline actually reads, `data/raw/firms_data/fire_manifest.json`, is git-ignored and absent from a fresh clone, so this is the documentation copy and is assumed, not verified, to match. In it: all six entries mark `start/end/reported_ha` as `provenance only`, and **no entry contains 신고 or any word for a report**. That much is solid and is what the manuscript rests on. ⚠ **What this lap first wrote here, and the lap reviewer knocked down**: that exactly one entry says what the field is, namely `yeongdeok_2025`, whose note reads `first hit (2025-03-25) lags the 2025-03-22 ignition by days` against that entry's own `start` of `2025-03-22T12:15+09:00`. That is an inference from a date coincidence, not a statement — the note never mentions `start` — and it is probably the wrong inference: `2025-03-22` is the **parent Uiseong chain's** ignition date (its own `start` is `2025-03-22T11:25`, fifty minutes earlier), while Yeongdeok's first detection is three days later, so the "ignition" that note names is most plausibly the parent fire's, not Yeongdeok's. `docs/detection_floor.md` §1 reads the same five other notes as saying nothing about `start` either. So the honest statement is the weaker one: **no entry says what the field is, in either direction.** The manuscript was corrected to that before this lap pushed. `docs/detection_floor.md` §1 and §9 read the field as a 신고 (report) time and concluded that GK2A rang after the telephone; **that reading was withdrawn on 2026-09-04 (WFG-053) with no number moving**, the manuscript having reached the narrow form first. Until a call time exists the paper cannot say whether the satellite beat the call, in either direction | the author supplies, for at least one of Uiseong-Andong, Gangneung or Hongseong, the KFS / 119 / 중대본 record giving the 신고접수시각, or the acquisition note saying where the minute came from; then it is registered with agency and date and §4.7, §1, §5 and the abstract can state the ordering. Raised by the lap-2 reviewer (NEEDS_HUMAN NH-019) | no |
| G2 | §5 Discussion | structured expert consultations (fire-service duty officer, village head, social worker) in the project's consultation format, as design feedback rather than collected data; any quotation needs the author's consent handling first | the consultations happen and the author clears the quotations (NH-009) | yes |
| G3 | §6 Limitations | the leak-free Yeongdeok fold: refit the Yeongdeok LOFO fold with the co-located Uiseong-Andong fire excluded, re-simulate the canonical field, and route the same 458 origins, reporting the three-bucket counts as new filenames | the raw acquisition bundle on the author's laptop is available and WFG-032 runs | yes |
| G4 | §6 Limitations | **the hindsight-field routing arm — the single most load-bearing gap in the paper.** A third pass over the same 458 origins on a field rasterised from the *observed* FIRMS detections for Yeongdeok 2025, reporting how many of the 42 fire-blind routes actually intersect observed burn inside the walker's arrival window, and how many forecast-aware routes cross observed burn the model never flagged. Until it runs, "saved" means "re-routed around a model-flagged cell", not "away from where the fire went", and with pooled recall 0.138 that distinction is not cosmetic | the observed detections are available. ⚠ Checked 2026-09-03: `data/snapshots/firms-manifest_yeongdeok-2025_20260723_1aa75824.json` is committed and records 2,290 detections spanning 2025-03-25T12:25 to 2025-03-27T04:28, but the detections themselves (`yeongdeok_2025_detections.csv`) live under the git-ignored `data/raw/firms_data/`, which is absent from a fresh clone. So this arm needs the author's laptop too — it is cheaper than G3 (no refit, no re-simulation, reuses the committed walk graph and origin list) but it is not runnable in the cloud sandbox | yes |

## ⚠ Length pressure, updated 2026-09-04 (paper lap 3)

The body is **7,408 words against a 7,500 hard fail and a 7,000 aim** — 92 words of
headroom, up from lap 2's twenty-one. Lap 3 added about 80 words (the settled
fire-affected-area reasoning in §1, the re-sourced death-toll attribution, the withdrawn
detection reading in §4.7, and the narrowed G5 marker) and cut about 152, taking them
from the places lap 2 nominated: §6's first item and its Coverage and router-approximation
restatements, §4.5's terrain and network summaries, §4.6's closing repetition of its own
headline, §3.1's duplicate of the availability statement, §3.2's restatement of what §4.1
then shows concretely, and §2's one filler sentence. **No number and no caveat was dropped
to make room**, and the deletions were all sentences that restated a claim already made in
the same or an adjacent section.

The candidates left, in order, are §6 (still the longest section), §4.5 and §4.6's second
half. Captions remain the free space: `build_docx.py` does not count them.

⚠ **The 20-page limit is still not measured, and lap 2's diagnosis of why was wrong.**
`check_paper.py` enforces words, and this file's budget line converts them at roughly 16
pages per 7,000 words; a crude recount over the built `.docx` — 8,909 words including
captions, tables and references, plus seven full-width figures — lands nearer 21 pages.
Lap 2 recorded that LibreOffice "refuses to load the built document", which reads as a
fact about our file. **It is not.** Checked on lap 3: `soffice --convert-to pdf` fails with
`Error: source file could not be loaded` on a two-paragraph `.docx` written by the same
`python-docx` in the same environment, so the converter cannot open *any* `.docx` here and
says nothing about `WildfireGuardian_Park_2026.docx`. No metric-compatible Calibri
(Carlito) is installed either, so a text-flow simulation would have to substitute Arial
metrics for Calibri's and assume a line height this repository has not measured — which is
the kind of unchecked constant the gap exists to remove. So no page number is asserted
here. **The cheapest close is the author**: open the committed `.docx` in Word or Google
Docs and report the page count; one number settles it. Failing that, a working converter.

## ⚠ Two repository inconsistencies the manuscript is on the safe side of (for a dev lap)

Both found by the paper lap-3 reviewer. Neither moves a number and neither is the paper's
to fix — `docs/NUMBERS.json` and `README.md` are outside what CHARTER §12 lets this
routine touch — so they are recorded here and in the lap report.

1. **The registry still asserts the ~95 % ratio that `docs/data_sources.md` withdrew.**
   `fire2025_chain_area_ha`'s caveat reads "It is about 95 % of the nationwide 104,788 ha"
   and `fire2025_nationwide_area_ha`'s reads "The 의성발 chain is 99,289 ha of this, about
   95 %". `data_sources.md` 함정 6 retired that ratio on 2026-09-04 and the manuscript
   states no share at all. CHARTER §12 says a number's caveats travel with it, so the
   manuscript is currently declining to repeat a caveat its own registry still carries.
   The manuscript's position is the safe one; the registry entries need an annotated
   supersede (add, never edit) from a dev lap. **Escalated 2026-09-04 as a new option D on
   NEEDS_HUMAN NH-018**, which already owns this question — no source settles whether two
   differently-scoped totals may be divided, and the `forbidden_phrasings` on
   `fire2025_nationwide_area_ha` make it gate-enforced behaviour rather than a note.
2. **The agency on `fire2025_chain_deaths` is wrong against its own sources.** The entry
   gives 중앙재난안전대책본부 and cites a 뉴시스 stub that names no agency and a 서울신문
   page that gives 중대본's undivided two-province total of 30. The page that carries the
   26 and the five-district split is 대구MBC 2025-03-30, which attributes both to
   경상북도 재난안전대책본부 and never says 중대본. The manuscript now cites that page
   (`dgmbc2025toll`). `README.md` attributes the Yeongdeok 9 correctly but still puts the
   26 under an 아시아경제 link that carries no death figure at all, and still closes that
   paragraph with 「경상북도 최종 집계·중앙재난안전대책본부 확인」. This is backlog
   **WFG-051** (P0, open): the paper half is done, the registry entry and the README
   reconciliation are not, and only a dev lap can do them.

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
