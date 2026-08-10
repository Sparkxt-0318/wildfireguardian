# The dash gate: what it covers, why, and what it cannot see

**Written 2026-08-07**, after an investigation found that both reasons the rule
gave for itself were wrong as stated, and that the gate was reporting a clean
pass on a screen with a visible dash on it.

Companion to [`forbidden_check_scope.md`](forbidden_check_scope.md), which
records the same shape of question for `make check-forbidden`.

---

## 1. ⚠ The stated rationale did not survive measurement

`check_screen_assets.py` gave two reasons for banning U+2014 and U+2013 in
visible text. Both were checked directly. **Neither holds as written.**

### "The shipped subset has no glyph, so it renders as tofu"

Half true, wrong conclusion. From the vendored fonts' own `cmap` tables:

| font | U+2014 | U+2013 | U+2192 | U+00B7 |
|---|---|---|---|---|
| `IBMPlexSansKR-Regular.woff2` (2,487 glyphs) | **absent** | **absent** | absent | present |
| `IBMPlexMono-Regular.woff2` (280 glyphs) | **present** | **present** | absent | present |
| `Pretendard-arrow.subset.woff2` (5 glyphs) | absent | absent | **present** | absent |

So the sans face really has no dash. But the pages declare
`'IBM Plex Sans KR', system-ui, sans-serif`, and browsers fall back **per
character**. Measured on the live console at 40 px:

| | width |
|---|---|
| EM dash, vendored sans **only** | 40.00 px — the notdef box |
| EM dash, the stack the page actually declares | **33.62 px** |
| EM dash, `system-ui` alone | **33.62 px** |

Identical. **It renders. It is not tofu.** What actually happens is that one
character of a Korean sentence is drawn in a different typeface, chosen by
whatever the viewing machine has installed.

### "Wider than a digit, so it defeats tabular-nums"

False exactly where it would matter. Numeric columns are set in `IBM Plex Mono`,
which **does** carry the dash, and there:

| | width |
|---|---|
| EM dash in `IBM Plex Mono` | **24.00 px** |
| digit `0` in `IBM Plex Mono` | **24.00 px** |

Exactly one digit. Alignment is unaffected.

### What the rule actually rests on

> A glyph the body face cannot draw is silently served by whatever the OS
> happens to have, so the same sentence renders in two typefaces and does so
> differently on every machine — and the machine that matters is a stranger's
> laptop in a competition hall.

That is a real defect, it is invisible to the author (whose machine has the
font), and it costs a tilde to avoid. **The rule stands; only its reasoning was
wrong.** Both original claims are corrected in place in the checker's docstring
rather than quietly deleted.

---

## 2. ⚠ What the gate cannot see: strings that arrive as data

The checker reads files. Text that reaches the screen from an **inlined JSON
payload** is invisible to it, because:

* `visible_text()` strips `<script>` wholesale — correct for the markup layer,
  and it removes the payload with it;
* `check_dashes_in_scripts()` only flags a line that *literally contains* a
  banned dash **and** writes to the DOM.

A payload string assigned through a variable satisfies neither:

```js
const D = { … "status_ko": "…구조자 측 산출이 불가합니다 «BANNED DASH» 더 넓은 …" }  // not scanned
d.textContent = D.responder.status_ko;                                             // no literal
```

**Measured, on the screen `operator_screen.md` names as the demonstration:** the
checker reported **0 findings** while the rendered page carried

* **1** EM dash in the footer warning (`responder.status_ko`, from
  `live/pipeline.py`);
* **4** EN dashes in the hazard band legend (`band_labels`).

### Both instances are now closed. The hole is not.

Fixed at their sources — `live/pipeline.py` uses a full stop, `BAND_LABELS` uses
`~` — and re-measured across **every payload string in every shipped screen and
the console**:

⚠ **The first version of this table (9,089 strings across six files) was
measured over a list that silently excluded the two TOP-LEVEL screen files** —
`uiseong_andong_2025_demo.html` and `yeongdeok_2025_manual.html` — because both
the measurement and every test glob matched only `screens/*/*.html`. Both
excluded files were stale pre-PHASE-21 builds still carrying EN-dash band
labels, so "every shipped screen: 0 dashes" was true of the list and false of
the tree. Rebuilt 2026-08-10, globs widened (`tests/test_screen_checks.py`
`SHIPPED_SCREENS`, `tests/test_operator_screen.py`), and re-measured over all
eight files:

| file | payload strings | banned dashes |
|---|---|---|
| `outputs/live/screens/uiseong_andong_2025/operator_screen.html` | 848 | **0** |
| `…/operator_screen_nopreroll.html` | 848 | **0** |
| `outputs/live/screens/uiseong_andong_2025_demo.html` | 848 | **0** |
| `outputs/live/screens/uljin_samcheok_2022/operator_screen.html` | 909 | **0** |
| `outputs/live/screens/yeongdeok_2025/operator_screen.html` | 2,326 | **0** |
| `outputs/live/screens/yeongdeok_2025_manual.html` | 632 | **0** |
| `demo/operator_screen.html` | 2,326 | **0** |
| `web/console.html` | 1,732 | **0** |
| | **10,469** | **0** |

Rendered confirmation on the 의성·안동 demonstration screen: **0 visible dashes**,
with 919 km², 3,926 km², 6곳 and 「OSM에 매핑된」 all intact.

⚠ **A pass from this gate is still not proof that the rendered page is clean.**
The next displayed payload string will be exactly as invisible as these were.
Closing the hole needs either a checker that renders the page, or a declared
list of payload keys that are displayed. Neither is built, and neither is
proposed here without a decision.

---

## 3. Scope: `outputs/live/screens/**` is in; the rest of `outputs/` is out

### In, from 2026-08-07

`outputs/live/screens/*/*.html` joined `demo/*.html` and `web/console.html` in
`SHIPPED_SCREENS`.

**Why:** they are shown to judges. `operator_screen.md` line 11 gives the
demonstration command as
`open outputs/live/screens/uiseong_andong_2025/operator_screen.html`, and line 25
calls that region **시연용 — "this is the demo"**. A file's directory does not
decide whether it is a shipped screen; who looks at it does.

They pass at **0 findings** after regeneration (§4).

### Out, deliberately

Widening the gate to all generated HTML was measured before being rejected:

| path | files | dash findings |
|---|---|---|
| `demo/*.html` (already gated) | 2 | 0 |
| `web/*.html` (already gated) | 1 | 0 |
| **`outputs/live/screens/**`** (**newly gated**) | 4 | **0** |
| `outputs/dispatch*/**` | 148 | **297** |
| `outputs/live/replay/**` | 295 | **593** |
| `outputs/live/manual/**` | 29 | 58 |

**960 findings across 475 files**, and almost all of them are one thing: the
live heading constants in `delivery.printable`, e.g.

```python
DISPATCH_HEADING    = "■ 구조 필요 지점 — 남은 시간 순"
UNREACHABLE_HEADING = "■ 차량 도달 불가 지점 — 별도 조치 필요"
```

⚠ **The rule's rationale does not reach them.** Those files are **A4 sheets
printed on paper** for the 이장. There is no vendored subset — the PDF renderer
uses a full system font, so §1's typeface-substitution argument does not apply.
And they are **section headings**, not numeric cells, so even the (already
false) alignment argument would not apply.

Gating them would flag 297 sheets that are correct, and the honest response
would be to add 297 exemptions — a ratchet holding a floor nobody believes.
**Not done.**

---

## 4. What was regenerated, and what that fixed on its own

The screens under `outputs/live/screens/` were built **2026-08-03**, before
PHASE 21 fixed the dash constants. The generator has been correct since
(`·`, `:`, `~`); the artifacts were simply stale. Rebuilding them from the
current replay runs cleared every visible dash the gate could see, with no
source change:

| screen | before | after |
|---|---|---|
| `yeongdeok_2025/operator_screen.html` | 4 | **0** |
| `uiseong_andong_2025/operator_screen.html` | 4 | **0** |
| `uiseong_andong_2025/operator_screen_nopreroll.html` | 4 | **0** |
| `uljin_samcheok_2022/operator_screen.html` | did not exist | **0** |
| `demo/operator_screen.html` | 0 (all 4 in comments) | **0** |

⚠ **One rendered dash survives regeneration**: `responder.status_ko`, §2. It
lives in `live/pipeline.py`, not in the screen template.

Earlier documentation claimed that constant "could not be fixed at source
because `tests/test_operator_screen.py` pins the generated screens to it
verbatim". **That was wrong and is corrected in
[`console_regions.md`](console_regions.md) §6.** The test parses the payload out
of the *same file* it greps, so it is a self-consistency check, not a coupling —
fixing the constant and regenerating would keep it passing. The fix is available
whenever it is wanted; it has simply not been taken.
