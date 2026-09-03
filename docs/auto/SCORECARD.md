# Scorecard — what the five judges would score today

The critic lap appends one dated row **only when the window's diff plausibly moved a
score**; a lap that moved nothing leaves the table alone and says so in its report.
Scores are 0–20 per row against `docs/auto/RUBRIC.md`, Track B five first
(연구 목적 · 설계와 방법론 · 데이터 수집·분석·해석 · 창의성 · 제출 자료), then Track A five
(개발 목적 · 설계와 방법론 · 구현 및 유용성 · 창의성 · 제출 자료). The track assignment is
not published, so both tables are kept.

These are **one critic's estimate of what a judge would give on the current tree**, not a
measurement. They exist to show direction between laps. A score that moves without a
commit to point at is a defect in the scoring, not evidence of progress.

## Track B — SW 연구

| date | window head | 연구 목적 | 설계와 방법론 | 데이터 수집·분석·해석 | 창의성 | 제출 자료 | /100 | what moved |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09-03 | `1113388` | 15 | 15 | 16 | 15 | 11 | **72** | baseline (first critic lap) |

## Track A — 애플리케이션 / 실생활 도구

| date | window head | 개발 목적 | 설계와 방법론 | 구현 및 유용성 | 창의성 | 제출 자료 | /100 | what moved |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09-03 | `1113388` | 15 | 15 | 11 | 15 | 11 | **67** | baseline (first critic lap) |

## 2026-09-03 · `25f1e14..1113388` — why these numbers

**연구 목적 / 개발 목적 · 15.** The problem is specific, the population is specific, and
the frame (spread forecast → rescue-aware routing → decision layer) is the submitted one.
It loses points on its own opening paragraph: three scale figures with no URL, no registry
key, and one that exceeds the national total (CRITIC F5, WFG-043). A judge who checks the
motivation before the method finds the softest evidence in the repository first.

**설계와 방법론 · 15 (both tracks).** Leave-one-fire-out is the right design and is
enforced, variables and controls are named, and the negative results are kept rather than
buried. Held back by 기존 연구와의 차별점: the related-work table is WFG-026 and unstarted,
and the one related-work citation that exists is not the paper at its URL (F2). 일정·역할
(WFG-027) is also unstarted.

**데이터 수집·분석·해석 · 16 — the strongest row.** Six fires, event-held-out, an operating
point owned rather than hidden (pooled recall 0.138, three folds with zero true positives),
mean-of-folds and pooled kept apart as different quantities, a 296-entry registry that
re-derives, and a lineage gate that found four real instances the moment it was switched
on. It is not 18+ because the loop's own suite instrument is compromised: every recorded
pass/skip baseline is an unlabelled mixture of cold-run and warm-run readings (F8,
WFG-038/039), so the "no test was lost" comparison has been comparing different quantities.

**창의성 · 15.** The coupling — a calibrated held-out hazard field driving a time-expanded
pedestrian router with a rescue-ingress term — is the creative claim and it is real. Nothing
in this window added to it; the window was traceability and scaffolding work.

**제출 자료 · 11 — the weakest row, and the cheapest to move.** 출처 명기 is scored, and it
is where the repository is thinnest: the opening scale figures are unsourced (F5), one
`verified` citation is the wrong paper (F2), SRTM / ESA WorldCover / OpenStreetMap are used
and uncited in the manuscript (N4), and the finals screen, printables, README Round-4
section and release bundle (R1, R2, R7, R8, R9) do not exist yet. Logical 구성 is good; the
graphics are good; the sourcing is not.

**구현 및 유용성 · 11 (Track A only).** `web/finals.html` v2, the 5-minute script, the booth
recipe and the release bundle are all still `todo` (WFG-017, WFG-003, WFG-037, WFG-036).
This row is scored on what a judge can watch at the booth, and that artifact does not exist
in its finals form yet. It should move most between 09-07 and 09-14.

**Not scored here:** the two Pass/Fail rows (서류 구비, 위험성 검토). 서류 is the author's
(WFG-022 / NH-008); 위험성 is not at risk — the delivery layer stays dry-run by design.
