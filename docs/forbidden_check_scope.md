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
`"n_origins": 452`. That is not someone asserting 452 today; it is the
superseded run's own faithful record. Rewriting or flagging it would corrupt the
evidence. The same digits in `docs/` prose, unqualified, would mislead.

## Two rule families, two scopes

| family | tokens | scope |
|---|---|---|
| **word** | `Chen`, `Guestrin`, `multi-scale`, `Multi-scale`, `XGBoost` | **every** tracked text file |  <!-- forbidden-ok: Chen, Guestrin, Multi-scale, multi-scale -->
| **retired figure** | `452`, `264`, `154`, `0.867`, `0.8667`, `0.834`, `0.8309`, `0.8337`, `0.8340`, `0.8745`, `0.874`, `138619`, `2731`, `약 40%` | **authored prose only** — every `.md`, wherever it lives |  <!-- forbidden-ok: 0.8309, 0.8337, 0.834, 0.8340, 0.8667, 0.867, 0.874, 0.8745, 138619, 2731 -->

**Word rules are repo-wide** because a misattributed model name is wrong
everywhere. `Chen` / `Guestrin` is the XGBoost citation; the canonical model is  <!-- forbidden-ok: Chen, Guestrin -->
sklearn `HistGradientBoostingClassifier`. A code comment is exactly where a
wrong attribution gets copied from into a document.

**Retired-figure rules are prose-only.** They do not apply to:

| | why not |
|---|---|
| `.py` | `Sardoy et al. (2008) Combust. Flame **154**` is a citation. `산**154**` is a Korean land-lot number. The `XGBoost` in `spread_v2_xgb/model.py` is the superseded build's own source code. None are claims. |
| `.json`, `.npz` | pipeline outputs. `"n_origins": 452` is that run's recorded value. |
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
