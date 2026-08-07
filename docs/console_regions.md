# PHASE 22 STEP 3 — three regions in one console, switched at runtime

**Status: done 2026-08-07.** `web/console.html` now carries all three registered
regions and swaps between them without touching the network.

---

## 1. ⚠ Measure first: is each region's default ignition point servable?

STEP 1 found that Yeongdeok's unclicked start was refused **422** every time,
because the hazard field's t=0 core lies outside the registered walk bbox
([`api_layer.md`](api_layer.md) §1.11). Before building a switcher, the same
question had to be asked of the other two — a switcher that inherited that fault
for two more regions would have tripled it.

Computed from the committed `.npz` files with the same definition
`live/pipeline.py` uses (centroid of the t=0 cells at p ≥ 0.5), gated with the
same `check_in_region` the API refuses on:

| region | t=0 core | inside its walk bbox | distance to the nearest edge |
|---|---|---|---|
| `yeongdeok_2025` | 129.2224, 36.4663 | **no** | **2,472 m outside** (west) |
| `uiseong_andong_2025` | 128.6323, 36.3556 | yes | 7,384 m inside |
| `uljin_samcheok_2022` | 129.3267, 37.0652 | yes | 4,975 m inside |

**Only Yeongdeok.** The other two have room to spare, so the console opens with
the run button **live** for them and **disabled with the explanation** for
Yeongdeok. Nothing is special-cased by name: `build_console._default_start` asks
the gate per region and the page reads the answer. A test asserts the verdict
matches `check_in_region` for **every** inlined region.

---

## 2. ⚠ The payload decision, measured before it was taken

The brief offered two shapes and asked for a measurement.

| | size | switch latency |
|---|---|---|
| **(a) three regions inline** | **153.9 KiB** built (was 78.0 with one) | no network at all |
| (b) per-region API fetch | ~34 KiB page + 32~43 KiB per region | **+0.42~0.73 ms** |

Localhost round trip, 30 samples, median: `/api/regions` **0.42 ms**,
`/` (78 KiB) **0.73 ms**. Component costs measured off the shipped payload:
51.8 B per origin, 51.9 B per refuge, hazard bands 6.7 / 1.5 / 2.0 KiB.

⚠ **A projection of 141.8 KiB was reported before the build; the actual is
153.9 KiB.** The projection multiplied measured unit costs by the committed
origin and refuge counts and did not account for the per-region `rows`,
`routes`, `responder` and `honesty` blocks growing with the region. Recorded
because the number was quoted in advance and the difference is 8 %.

**Neither size nor latency decides it.** 64 KiB and 0.7 ms are both nothing. The
decision is about **staleness**:

* Three built files were rejected outright — "which of these is current?" is a
  problem this project has already paid for.
* A fetching console would have to read a **replay run directory at runtime**,
  and that is exactly the thing that went missing in §1.12. It would make the
  failure mode worse, not better.
* Inline keeps the property `build_console.py` documents: the file opens and
  works with nothing else present.

---

## 3. The §1.12 guard, extended to three regions and exercised

`build_console.check_not_a_downgrade` compares the outgoing build against the
one already on disk, **per region**, and refuses to overwrite with an older run.

```
$ python scripts/build_console.py --run-dir outputs/live/replay/uiseong_andong_2025/20260803T051938Z
REFUSED: this build would ship an older result than the one already on disk.

  ⚠ uiseong_andong_2025: about to build from 20260803T051938Z (warm 30.661 s)
    but the shipped console was built from the NEWER 20260807T050300Z (warm 18.361 s)

  Rebuild the run, or pass --allow-older to accept the downgrade deliberately.
```

Exit **5**, and `web/console.html` is byte-identical afterwards (verified by
sha256). `--allow-older` prints the same line and proceeds, so a deliberate
downgrade is recorded rather than silent. It also reports when the shipped
console names a run that is no longer on disk — the §1.12 case itself.

---

## 4. ⚠ Three badges, one code version

The existing Uiseong-Andong replay runs were from 2026-08-03, **before PHASE 20**.
Shipping them beside Yeongdeok's 10.4 s would have put 30.7 s next to it and
invited "Uiseong-Andong is three times slower", when the difference was the
optimisation, not the region. Both missing regions were re-run on current code.

| region | run | warm | routing | counts (safe / FA-only / none / budget) | matches the committed table |
|---|---|---|---|---|---|
| 영덕 2025 | `20260807T022854Z` | **10.385 s** | 10.249 s | 414 / 42 / 2 / 0 | yes |
| 의성·안동 2025 | `20260807T050300Z` | **18.361 s** | 18.105 s | 263 / 91 / 12 / 2 | yes |
| 울진·삼척 2022 | `20260807T050338Z` | **8.543 s** | 8.406 s | 377 / 3 / 10 / 3 | yes |

Every count checked against `data/processed/multi_region_comparison.json`, and a
test now pins that agreement so a rebuild cannot quietly move one.

⚠ **The three warm figures are NOT comparable as a regional ranking.** They
differ by origin count (458 / 368 / 393), network size, shelter count and how
many origins need a full search. They are on the screen to say what THIS result
cost, nothing more. The old runs were kept, not deleted.

---

## 5. What changes per region

| | 영덕 2025 | 의성·안동 2025 | 울진·삼척 2022 |
|---|---|---|---|
| 보행망 커버리지 | **32.6 %** | **99.2 %** | **81.5 %** |
| 기상 자료 기준 | 2025-03-25 12:25 UTC | 2025-03-22 05:39 UTC | 2022-03-04 05:26 UTC |
| 위험면 digest | `81b4e4d159daa7a8…` | `4016c2e6ef8e27eb…` | `5482c9b5ded9a576…` |
| 출동 목록 | 44 지점 · 29 마을 | 105 지점 · 65 마을 | 16 지점 · 13 마을 |
| 차고지 | 4 | **0** | 4 |
| 기본 발화점 | 게이트 거절 | 통과 | 통과 |

⚠ **Coverage was the literal `32.6` in the builder.** Correct for Yeongdeok and
silently wrong for the other two the moment the console could switch. It is now
read per region from `envelope_coverage_final_slice` in the committed comparison
table, and a test asserts the three figures differ and match that artifact.

---

## 6. ⚠ Uiseong-Andong's empty responder side is stated, not shown as a blank

It has **zero** `amenity=fire_station` mapped in OSM inside its walk bbox, so
there is no responder-side output. An empty table reads as a broken screen, and
an operator's next move would be to reload it.

The console shows an amber panel where the rows would be:

> **구조자 측 산출 없음**
> 이 지역은 walk bbox(919 km²) 내에 OSM에 매핑된 소방서가 없어 구조자 측 산출이
> 불가합니다. 더 넓은 3,926 km² 범위에는 6곳

The sentence is `viz.json`'s `responder_side.status_ko`, produced by
`live/pipeline.py` — not composed here. It is worded the way **rule 11**
requires: the claim is about OSM mapping inside one bbox, never "this region has
no fire stations", and a test bans the shortened phrasings on the built file.

### ⚠ One dash, normalised, and why not at the source

That constant contains an **EM dash**, which the PHASE-21 gate bans in visible
text because the vendored subset font has no glyph for it. It could not be fixed
at the source: `tests/test_operator_screen.py` asserts the generated
`outputs/live/screens/**` screens contain `status_ko` **verbatim**, so changing
the constant would desync committed screens from the code that made them.

So `build_console._dash_safe` normalises the punctuation on the way to **this**
screen only. Content is untouched and a test checks that 919 km², 3,926 km² and
6곳 all survive, and that no banned dash reaches the console.

⚠ **Recorded, NOT fixed:** `outputs/live/screens/*/operator_screen.html` each
carry **4** EM dashes in visible text, measured. The dash gate only scans
`demo/*.html` and `web/console.html`, so generated screens are outside it — the
same blind spot the handoff records for `make check-forbidden`. Those screens
ship a glyph their own font cannot draw. It needs its own decision.

---

## 7. A switch is a full reset

The clicked or photographed ignition point belongs to the region it was chosen
in — Yeongdeok's walk bbox and Uiseong-Andong's do not overlap, so carrying a
point across would leave the header showing one the new region cannot route
from. `mountRegion()` therefore:

* cancels a running job and clears the progress line;
* drops the chosen point and re-labels the run button;
* returns the badge to 「사전 계산 결과」 and the calculation label to **that
  region's own** measured cost;
* re-raises the unservable-default note if that region needs one;
* resets the photo panel's status line;
* redraws hazard, walk bbox, origins, refuges, ignition, routes and legend
  against that region's grid, which differs in extent and aspect.

Verified: after a live run on 의성·안동 (368 origins, 18.77 s), switching to 영덕
returned mode to 사전 계산 결과, the label to 10.385초, coverage to 32.6 %, the
point to empty, and the button to disabled-with-explanation.

---

## 8. The 1366×768 table clip, fixed

Pre-existing and measured identical on `HEAD` before this phase: the dispatch
table was **548 px inside a 519 px pane**, and `#tablewrap`'s `overflow:hidden`
cut **29 px** off the 구분 column — no scrollbar, no ellipsis, the column simply
stopped. 구분 is the four-way answer, so it is the one column that must never be
shortened.

`table-layout: fixed` makes the table exactly as wide as the pane. Column widths
are **measured, not chosen** — each set to the widest content it must hold, read
off the rendered table:

| column | width | widest content |
|---|---|---|
| # | 38 px | `40` |
| 위치 | remainder | ellipsises; the 「A4 전달물에는 전부 실립니다」 line says where the full text is |
| 남은 시간 | 76 px | `해당 없음` |
| 도보 | 58 px | `568분` |
| 구분 | 86 px | `■ 도달 불가` (needs 84) |

⚠ 구분 was set to 76 px first and rendered 「■ 도달 ...」. Caught by measuring
`scrollWidth` against the rendered width rather than by looking at it.

---

## 9. Verified in the browser

Every cell measured from the live page, not eyeballed.

| viewport | region | doc scroll | table clipped | columns ellipsised | banner over panel |
|---|---|---|---|---|---|
| 1920×1080 | all three | 0 × 0 | 0 px | none | no |
| 1600×900 | all three | 0 × 0 | 0 px | none | no |
| 1366×768 | 영덕 | 0 × 0 | 0 px | 위치 only (by design) | no |
| 1366×768 | 의성·안동 · 울진·삼척 | 0 × 0 | 0 px | none | no |

Driven end to end:

* **switch** — all three, by mouse and by keyboard-activated button;
* **click** — 울진·삼척 at 36.9598, 129.3191 accepted; live run **393 origins,
  9.684 s**;
* **live run** — 의성·안동 **368 origins, 18.77 s**;
* **photo** — the SAME JPEG (36.3556, 128.6323) is **refused on 영덕** with the
  map-click refusal sentence and **accepted on 의성·안동**, which is the region
  gate working through the EXIF path;
* **reset** — switching after a live run clears mode, label, point and progress.

Gates: offline **0** · dash **0** · contrast **0**. Suite **949 passed, 4
skipped**. `make verify` PASSED, `check-forbidden` HARD **0**.
