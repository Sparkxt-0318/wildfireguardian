# One region's values, typed into text every region reads

**2026-08-07.** The same defect was found three times in three files. All three
were **correct on Yeongdeok**, which is why all three survived review.

---

## 1. The three

| # | where | what it said | who actually saw it |
|---|---|---|---|
| 1 | `build_operator_screen.py` legend | `보행망 범위 (커버리지 32.6%)` typed into static markup, while the footer read the per-region value | the **의성·안동 demonstration screen** displayed **32.6 % and 99.2 % at the same time** |
| 2 | `build_console.py` | `"coverage_pct": 32.6` in the payload builder | nobody yet: it would have gone wrong the moment the console could switch region |
| 3 | `live/scope.py` | `COVERAGE_CAVEAT_KO`, naming 영덕 and 32.6 % | **273** A4 dispatch sheets belonging to 의성·안동 and 울진·삼척 |

⚠ **The pathology:** the author checks the screen in front of them, and that
screen is the one the literal happens to match. A defect invisible from the
default region needs a check that does not start there.

---

## 2. Instance 3 in detail — it reached paper

`COVERAGE_CAVEAT_KO` was a module constant applied with no region condition to
every A4 dispatch sheet, every email body, and every `viz.json` / `RUN.json`.

Measured before the fix:

| region | sheets | its own coverage on its own sheet | 32.6 % | 「영덕」 |
|---|---:|---:|---:|---:|
| 의성·안동 2025 | 260 | 99.2 % → **0 sheets** | 260 | 260 |
| 울진·삼척 2022 | 13 | 81.5 % → **0 sheets** | 13 | 13 |
| 영덕 2025 | 29 | 32.6 % → 29 (correct) | 29 | 29 |

It was not a *false* statement about those regions — the sentence says
「영덕 수치는」. It was the **wrong region's caveat on a single-village dispatch
sheet**, and on a page with a one-page budget it displaced the one that belonged
there.

⚠ **Not a recorded decision.** The only related entry
(`HANDOFF_ROUND3.md` §"caveat drift") records that `email.py` held a second,
hand-retyped copy that had lost a sentence, and that the fix was to make it ONE
definition. Making it one was right. Nobody asked whether that one should be
region-conditional.

---

## 3. The fix: read, never retype

`live/scope.py` now builds both strings per region from committed artifacts.

| what | source | function |
|---|---|---|
| coverage %, Korean label | `multi_region_comparison.json` | `region_coverage_pct`, `region_label_kr`, `coverage_caveat_ko` |
| walk-bbox area, station counts | `osm_completeness.json` | `responder_status_ko` |

```
영덕 2025 수치는 정본 화재 핵심의 32.6 %만 덮는 보행망에서 산출되었습니다.
  나머지 67.4 %에 있는 …  지역 간 비교에서 영덕 2025 행을 인용할 때는 …
의성·안동 2025 수치는 … 99.2 %만 덮는 … 나머지 0.8 %에 있는 …
울진·삼척 2022 수치는 … 81.5 %만 덮는 … 나머지 18.5 %에 있는 …
```

⚠ **The remainder is now a figure, not 「3분의 2」.** Two thirds described 67.4 %
well and describes 0.8 % not at all.

### ⚠ Where a number does not exist, it is not invented

`osm_completeness.json` carries the **planar** walk-bbox areas — and only inside
the *key names* of `fire_station_counts_by_extent`
(`walk_bbox_919km2`, `walk_bbox_924km2`, `walk_bbox_931km2`). They are parsed
from there rather than retyped, because a fourth hand-written 919 is the exact
shape of this defect. The integers are regrouped on output so the mandated
「3,926」 keeps its separator.

The **wider manifest-bbox** count was measured for `uiseong_andong_2025` only.
So for any *other* region with zero depots the sentence ends

> 더 넓은 범위의 소방서 수는 이 지역에 대해 측정되지 않았습니다.

rather than borrowing Uiseong-Andong's 3,926 km² and its six. A test pins that.

⚠ The planar/geodesic split (919 vs 896.5) is **not** a defect: it is a recorded
decision in `multi_region.md`, and the operator-facing text uses planar
deliberately.

### The email path

`compose_family` / `compose_welfare` now take a **required** `region` with no
default. A default is how this defect is spelled politely: the caller knows
which region it is composing for, so it has to say so. `send_dispatch_email.py`
passes `"yeongdeok_2025"` explicitly, with a comment that it reads
`outputs/dispatch*`, which is the 439-series Yeongdeok lineage and nothing else.

---

## 4. Verified from the rendered PDFs, not from the source

All three regions re-run with PDF conversion on:

| region | sheets | max pages | over 1 page | own coverage in the PDF | another region named |
|---|---:|---:|---:|---:|---:|
| 영덕 2025 | 29 | **1** | 0 | **29 / 29** | 0 |
| 의성·안동 2025 | 65 | **1** | 0 | **65 / 65** | 0 |
| 울진·삼척 2022 | 13 | **1** | 0 | **13 / 13** | 0 |

**107 sheets, every one a single page**, which was the risk: the caveat's length
now varies by region (67.4 % / 0.8 % / 18.5 %) and one A4 page per village is a
PHASE-3 design constraint. Text extracted with `pdftotext`, page counts with
`printable.pdf_page_count`.

---

## 5. The check

`scripts/check_region_literals.py`, wired into **`make verify`**.

Scoped to the nine files that build or emit operator-facing text. Flags a Korean
region name (영덕 / 의성 / 안동 / 울진 / 삼척) or a per-region figure inside a
user-visible string. Exempts per-region tables (a line naming a region *key* —
that is the fix, not the defect), comments, and docstrings.

⚠ **It is not complete and does not try to be.** The bar is "would it have
caught the three".
`tests/test_screen_checks.py::test_the_region_literal_check_catches_all_three`
feeds it each of the three exactly as written and asserts it fires; a companion
test feeds it six *correct* patterns and asserts it stays quiet, because a
detector that always fires is as useless as one that never does.

It ratchets, like the dash and offline gates. `KNOWN_REGION_LITERALS` holds one
entry, with its reason.

### Two weaknesses found while building it, both fixed

* It flagged **its own docstring** explaining the defect: comment detection
  matched only an *opening* line, so docstring prose was scanned. It now tracks
  the fences.
* It was **blind to instance 2**. An early exemption skipped any line mentioning
  `coverage_pct`, on the grounds that such a line "reads the value" — but
  `"coverage_pct": 32.6` both names the field and states the value, so the
  exemption covered precisely the defect. A line that genuinely reads a value
  carries no literal, so the exemption was removed rather than narrowed.

---

## 6. Recorded, deliberately not fixed

Both are correct on every path that can currently reach them. They are written
down because "correct today" is what let the three real ones through.

| where | literal | why it holds |
|---|---|---|
| `console.template.html:195` | `<svg … aria-label="영덕 …">` | `renderFacts()` overwrites it with `${D.label_kr}` on every mount including the first; the literal exists only between parse and first paint. The one `KNOWN_REGION_LITERALS` entry. |
| `build_console.py` | `차고지 0곳` in the build printout | reached only when `available` is false, and `available` is `n_depot_pois > 0`. Build stdout, never shipped. |
