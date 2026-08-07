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

All three were re-run once more on 2026-08-07 **with PDFs**, to check the A4 page
budget after the coverage caveat became per region ([`region_literals.md`](region_literals.md)).
The shipped console is built from those:

| region | run | warm | routing | counts (safe / FA-only / none / budget) | matches the committed table |
|---|---|---|---|---|---|
| 영덕 2025 | `20260807T100249Z` | **9.961 s** | 9.801 s | 414 / 42 / 2 / 0 | yes |
| 의성·안동 2025 | `20260807T100427Z` | **18.252 s** | 18.057 s | 263 / 91 / 12 / 2 | yes |
| 울진·삼척 2022 | `20260807T100745Z` | **8.174 s** | 8.042 s | 377 / 3 / 10 / 3 | yes |

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

### ⚠ One dash, normalised — and a correction to what this section first said

That constant contains an **EM dash**, which the PHASE-21 gate bans in visible
text. `build_console._dash_safe` normalises the punctuation on the way to **this**
screen only. Content is untouched, and a test checks that 919 km², 3,926 km² and
6곳 all survive and that no banned dash reaches the console.

⚠ **CORRECTION, 2026-08-07.** This section originally justified normalising here
rather than at source with two claims. Both were investigated and **both were
wrong**; they are restated rather than deleted, because a wrong reason that
quietly disappears is indistinguishable from one that was never made.

| the claim | what the measurement shows |
|---|---|
| "it could not be fixed at source: `tests/test_operator_screen.py` pins the generated screens to `status_ko` **verbatim**, so changing the constant would desync them" | **Wrong.** `payload(p)` parses the inlined `const D = {…}` out of the *same file* `html(p)` reads, so the assertion compares a file with itself. It is a self-consistency check, not a coupling to `live/pipeline.py`. Fixing the constant and regenerating keeps it passing. |
| "the vendored subset font has no glyph for it" (implying it renders as tofu) | **Half true, wrong conclusion.** `IBMPlexSansKR` lacks U+2014, but the page declares `system-ui, sans-serif` after it and the browser falls back per character: 33.62 px, identical to `system-ui` alone, against a 40 px notdef box. It renders — in a *different typeface*. Full measurements in [`screen_gate_scope.md`](screen_gate_scope.md) §1. |

**Normalising at build time is still what this console does**, and it is still
defensible — one screen, one place, no effect on any other consumer. But it is a
choice, not a necessity, and fixing `live/pipeline.py` is available whenever it
is wanted.

⚠ **Recorded, NOT fixed:** the responder sentence's EM dash still **renders** on
the 의성·안동 demonstration screen, and the dash gate reports **0 findings** on
that file — because the string arrives as JSON payload data, which the checker
cannot see. That blind spot, and the (now measured) reasons the gate scope stops
where it does, are in [`screen_gate_scope.md`](screen_gate_scope.md) §2~3.

⚠ **Superseded here:** an earlier version of this note said the generated screens
"each carry 4 EM dashes in visible text" and "ship a glyph their own font cannot
draw". The count was right for what the gate could see and wrong for what
rendered (6 rendered, only 2 of them flagged); the font claim was wrong outright
— those screens vendor **no** font at all and use the system stack.

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

---

## 10. Recorded, deliberately NOT fixed

Two literals name one region in code the other regions also run. **Both are
correct on every path that can currently reach them**, which is exactly why they
are recorded rather than left unmentioned — that property is what made the three
real instances survive review.

| where | literal | why it is correct today |
|---|---|---|
| `scripts/console.template.html:195` | `<svg … aria-label="영덕 위험 확률장과 …">` | `renderFacts()` overwrites it with `${D.label_kr}` on **every** mount including the first, so what a screen reader announces is always the mounted region. The literal is only the value between parse and first paint. |
| `scripts/build_console.py` | `차고지 0곳 → 구조자 측 산출 불가 표시` in the build printout | reached only inside `if not p["responder"]["available"]`, and `available` is `n_depot_pois > 0`, so the count is 0 by construction. Build stdout only; never shipped. |

The first is the single entry in
`check_region_literals.KNOWN_REGION_LITERALS`, so the ratchet holds at one and
any **new** literal fails. The second is not matched by that checker (no Korean
region name, no per-region figure) and is recorded here instead.

---

## 11. The three instances of one defect, and the check that now catches them

| # | where | what it said | who saw it |
|---|---|---|---|
| 1 | `build_operator_screen.py` legend | `보행망 범위 (커버리지 32.6%)` in static markup while the footer read the per-region value | the **의성·안동 demonstration screen** showed 32.6 % and 99.2 % at once |
| 2 | `build_console.py` | `"coverage_pct": 32.6` in the payload builder | nobody yet — it would have gone wrong the moment the console could switch |
| 3 | `live/scope.py` | `COVERAGE_CAVEAT_KO` naming 영덕 and 32.6 % | **273** A4 sheets for the other two regions, none of which carried its own figure |

⚠ **All three were correct on Yeongdeok.** That is the whole pathology: the
author checks the screen in front of them, and that screen is the one the
literal happens to match. A defect invisible from the default region needs a
check that does not start there.

`scripts/check_region_literals.py` is that check. It is scoped to the nine
operator-facing builders and delivery modules, it looks for a Korean region name
or a per-region figure inside a user-visible string, and it exempts per-region
tables (a line naming a region *key*), comments and docstrings.

**It is not complete and does not try to be.** The bar it was built to clear is
"would it have caught the three", and
`tests/test_screen_checks.py::test_the_region_literal_check_catches_all_three`
feeds it each of the three exactly as they were written and asserts it fires.
A companion test feeds it six *correct* patterns — the per-region dict, the
templated string, the value read from the payload, the comments — and asserts it
stays quiet, because a detector that always fires is as useless as one that
never does.

Wired into `make verify`.

### Two weaknesses found while building it, both fixed

* It flagged **its own docstring** explaining the defect. Comment detection only
  matched an *opening* line, so docstring continuation prose was scanned. It now
  tracks the fences.
* It was **blind to instance 2**. An early exemption skipped any line mentioning
  `coverage_pct` on the grounds that such a line "reads the value" — but
  `"coverage_pct": 32.6` both names the field and states the value, so the
  exemption covered precisely the defect. A line that genuinely reads a value has
  no literal in it, so the exemption was removed rather than narrowed.
