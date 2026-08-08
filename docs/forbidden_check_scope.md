# What `check_forbidden.py` checks, what it deliberately does not, and why

A scan whose exclusions are undocumented looks like a hole. This file is the
record of where each rule applies and on what principle.

Implementation: `scripts/check_forbidden.py`. Run it with `make check-forbidden`
or `make verify`.

## The principle

> A retired number is misleading exactly when it reads as a **current claim**.
> Claims live in authored prose. Records — code, run outputs — are **evidence**,
> and evidence must stay legible.

`data/processed/rescue_baseline_synthetic/rescue_capacity.json` contains
`"n_origins": 452`. That is not someone asserting 452 today; it is the  <!-- forbidden-ok: 452 -->
superseded run's own faithful record. Rewriting or flagging it would corrupt the
evidence. The same digits in `docs/` prose, unqualified, would mislead.

## Two rule families, two scopes

| family | tokens | scope |
|---|---|---|
| **word** | `Chen`, `Guestrin`, `multi-scale`, `Multi-scale`, `XGBoost` | **every** tracked text file |  <!-- forbidden-ok: Chen, Guestrin, Multi-scale, XGBoost, multi-scale -->
| **retired figure** | `452`, `264`, `154`, `0.867`, `0.8667`, `0.834`, `0.8309`, `0.8337`, `0.8340`, `0.8745`, `0.874`, `138619`, `2731`, `약 40%` | **authored prose only** — every `.md`, wherever it lives |  <!-- forbidden-ok: 0.8309, 0.8337, 0.834, 0.8340, 0.8667, 0.867, 0.874, 0.8745, 138619, 2731 -->

**Word rules are repo-wide** because a misattributed model name is wrong
everywhere. `Chen` / `Guestrin` is the XGBoost citation; the canonical model is  <!-- forbidden-ok: Chen, Guestrin, XGBoost -->
sklearn `HistGradientBoostingClassifier`. A code comment is exactly where a
wrong attribution gets copied from into a document.

**Retired-figure rules are prose-only.** They do not apply to:

| | why not |
|---|---|
| `.py` | `Sardoy et al. (2008) Combust. Flame **154**` is a citation. `산**154**` is a Korean land-lot number. The `XGBoost` in `spread_v2_xgb/model.py` is the superseded build's own source code. None are claims. |
| `.json`, `.npz` | pipeline outputs. `"n_origins": 452` is that run's recorded value. |  <!-- forbidden-ok: 452 -->
| `.html`, `.txt`, `.toml`, `.yaml` | generated payloads and machine config. `demo_data.json` holds polygon vertices, one of which is literally `[0.8745, 0.5558]` — a coordinate, not an IoU. |  <!-- forbidden-ok: 0.8745 -->

### `.md` is in scope wherever it lives

Every `.md` file is treated as authored prose, including
`data/processed/spread_v2/LEGACY_DO_NOT_CITE.md` and
`data/processed/rescue_baseline_synthetic/README.md`. A document is a document
regardless of which directory it sits in; living beside artifacts does not make
it an artifact.

## Nothing is hidden

Every skipped numeric match is counted and printed **on every run**, per file:

```
scope: 174 retired-number match(es) skipped in 17 non-prose file(s) — records,
       not claims (docs/forbidden_check_scope.md). Word rules still applied:
          32  data/processed/rescue_baseline_synthetic/rescue_verify.json
          31  data/processed/demo_data.json
          ...
```

If a skip count moves, that is visible without reading this file.

## Two severities

* **HARD** — zero occurrences permitted; exit 1. Retired values presented as
  current, or a misattributed model.
* **LABEL** — permitted only with a qualifier (`superseded`, `legacy`,
  `Build A`, `폐기`, `이전`, …) on the same line. Warns; `--label-is-error`
  promotes it to a failure.

## Line pragmas

A rule's own statement necessarily contains the thing it forbids. Suppression is
**per line, and only per line**:

```markdown
<!-- forbidden-ok: 0.874 -->
```
```python
# forbidden-ok: 0.834, 0.8309
```

The pragma must sit on the offending line or the line directly above, and
suppresses only the tokens it names. There is **no whole-file pragma and no
`forbidden-ok: *`** — a file-level escape hatch becomes a permanent one. The
token list allows hyphens, so `multi-scale` can be suppressed.  <!-- forbidden-ok: multi-scale -->

Legitimate pragma uses today: `scripts/check_forbidden.py`'s own rule table, and
documents whose job is to name a retired value (`MODEL_CARD.md` blocking 0.874,  <!-- forbidden-ok: 0.874 -->
`LEGACY_DO_NOT_CITE.md` naming 0.8309 / 0.8337).  <!-- forbidden-ok: 0.8309, 0.8337 -->

## Known limitation

The qualifier must appear on the **same line**. A document that declares itself
superseded in a banner at the top — `docs/rescue_routing.md` does exactly this —
still reports every later mention. That is a deliberate conservatism, not an
oversight: document-level trust is what let a superseded number drift into a
submission in the first place. Those mentions are reported and reviewed rather
than auto-excused.

## The gap this scope leaves

Recorded 2026-08-06. **Not fixed** — widening the rules would flag a large body
of existing generated assets at once, and deciding what to do with each of them
is a separate judgement.

Retired-number rules apply to `.md` only. That was reasoned deliberately (above:
"a retired number is misleading exactly when it reads as a CURRENT CLAIM, and
claims live in prose"). But the reasoning has a seam, and the seam is now load
bearing:

> **A generated `.html` demonstration screen is not a record. It is a claim,
> made to a judge, in a room.**

`demo/wildfire_demo.html` is the case that exposed it. It inlines
`data/processed/demo_data.json`, whose routing block is exported from
`routing_demo.json` / `routing_demo.npz` — the **pre-canonical** lineage
(`HANDOFF_ROUND3.md` §2-A). The scan passes it without a word, because it is
`.html`, while a `.md` file containing the same figures would be stopped.

It carries no HARD-forbidden value today, so nothing is currently mis-stated.
What it does carry is a superseded lineage: the canonical figures a presenter
would say out loud — 458 / 414 / 42 / 2, 9.17 % — appear nowhere on it.

⚠ **Until that page is re-exported, do not cite it and do not demonstrate from
it.** The provenance is recorded at the top of `scripts/export_demo_data.py`.
Re-export is sequenced after the operator dashboard, deliberately: doing it
first would mean doing it twice.

Two ways to close the gap when someone decides to:

1. Extend `is_authored_prose` to generated screens under `demo/`. Cheap, and it
   will report a batch of existing assets that then need individual decisions.
2. Check the DATA a screen inlines rather than the screen — `demo_data.json`
   already carries a `source` string per figure, so a rule could assert those
   sources name canonical artifacts. Narrower, and it catches the real failure
   (wrong lineage) rather than the symptom (a digit in a blob of HTML).

The second is the better shape. Neither is done.

---

## LABEL_NEAR — retired claims stated without a caveat (2026-08-08)

A third severity, added after the same defect was found in five documents in one
day: a value the repository has **retired** stated as a **current claim**, with no
marker anywhere near it. `MODEL_CARD.md` — the file the README calls "canonical
source of truth for every number below" — carried a section headed
**"Headline finding (severity ≫ wind direction)"** with no caveat in the file at
all, months after that conclusion was withdrawn.

`HARD` could not express this (the values are legitimate history and must NOT be
deleted) and `LABEL` could not either, for a measured reason.

### ⚠ Why the window is ±10 lines and not the same line

`LABEL` requires the qualifier **on the same line**. That suits its five tokens,
which are single prose mentions. It does not suit these, because **the natural way
to caveat a table is a block quote above it, not a suffix on every row.**

Measured against the tree before and after the caveat pass:

| window | false positives (corrected tree) | detections (pre-fix tree) |
|---|---:|---:|
| same line | **37** | 42 |
| ±3 | 14 | 31 |
| **±10** | **6** | **23** |
| ±25 | 5 | 17 |

Same-line put **88 %** of its findings on content that was already correctly
marked. Past ±10, each further widening buys one fewer false positive and loses
six detections.

### Two mistakes made while building it, both fixed

* **The `44×` pattern matched nothing.** It ended in `\b`, and `×` is not a word
  character, so the boundary could never hold before the `**` in `**44×**`. Only
  the ASCII `44x` spelling ever matched — the rule silently passed the very
  `MODEL_CARD` line it was written for. The lookbehind `(?<![\d.])` alone does the
  real work; it is what keeps `1.44×` and `18.3×` (a different quantity, in
  `OVERNIGHT_REPORT_SESSION4.md`) out.
* **Bare `canonical` in the label vocabulary masked a real finding.** This
  repository calls its current model the "canonical reference", and a baseline
  table row saying so eight lines above a retired ratio silenced
  `docs/baselines.md`. Only the contrastive usage — the canonical *field* or
  *re-run* — now counts.

Both were caught by re-running the checker against the reverted documents rather
than by reading it.

### ⚠ What LABEL_NEAR CANNOT do

> **It catches "a retired TOKEN appears with no caveat nearby". It does not, and
> cannot, judge that a CLAIM has been retired.** The next withdrawn claim will be
> exactly as invisible as this one was, in exactly the way an unregistered value
> is invisible to `check_region_literals`. **The registry IS the scope.**

So: **the existence of this check is not a reason to feel safe.** It converts one
specific failure — *we already knew this was retired and said it anyway* — from a
thing found by chance months later into a thing found at `make verify`. It does
nothing about the failure that actually hurt here, which is *nobody asked whether
the claim still held*. That one has no textual signature, and no rule proposed so
far would have caught it.

Two further limits, stated so a pass is not over-read:

* **Prose scope only.** Like the retired-number rules, it runs on `.md`. A claim
  restated in a slide, a screen or a commit message is out of reach.
* **Proximity is not endorsement.** A caveat within ten lines satisfies the rule
  even if it is about something else entirely. The check tests for the *presence*
  of a marker, never for its relevance.
