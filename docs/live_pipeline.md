# PHASE 6 — the live detection pipeline

Round-3 PHASE 6. Written 2026-08-03.

`scripts/run_live_detection.py` · `src/wildfireguardian/live/` ·
`tests/test_live_pipeline.py` (44 tests)

---

## 0. What this is, and what it is not — read before anything else

> **화점 탐지: 실시간 (FIRMS NRT)**
> **기상 자료: 2025-03-25 12:25 UTC 기준 (ERA5는 약 5일 지연 발행)**

This is **real-time detection over a pre-computed risk surface**. It is **not**
real-time forecasting, and the difference is not a nuance:

| layer | real-time? | why |
|---|---|---|
| hotspot detection | **yes** | FIRMS NRT publishes VIIRS/MODIS detections within ~3 h of overpass |
| hazard surface | **no** | ERA5 reanalysis publishes on a **~5-day lag**. There is no weather field for today, so no hazard field can be simulated for today. |
| road network, refuges | no | snapshot store, fixed |

The surface routed on was simulated **once**, from the weather of the fire it
was built for, and is held fixed. A new detection decides *whether* and *where*
to act. It does not move the surface, and it cannot.

Claiming otherwise would be claiming a capability the project does not have, so
the two lines above appear on **every** screen, A4 sheet, broadcast script, SMS
draft and JSON record. `tests/test_live_pipeline.py` fails if one is missing,
and `live/scope.py` is the single place the strings are defined so that a
retyped caveat cannot drift.

---

## 1. The two branches

```bash
python scripts/run_live_detection.py --replay          # OFFLINE. The demo path.
python scripts/run_live_detection.py --once            # one live FIRMS poll
python scripts/run_live_detection.py                   # poll every 3 h, forever
```

| | `--replay` | live |
|---|---|---|
| source | committed detections CSV | FIRMS NRT area API |
| network | **none** | required |
| credentials | **none** | `FIRMS_MAP_KEY` |
| clock | archive time × speed multiplier | wall clock |
| banner | 「■ 재생 모드 ■」 | 「■ 실시간 모드 ■」 |

**Replay is the demonstration path, not the fallback.** A live demonstration
depends on three things a venue does not control: a working network, a satellite
overpass inside the demo window, and an actual fire burning in the registered
region. On an October afternoon the third is very unlikely. So replay is built
to be *more* robust than live:

* it imports no HTTP client at all — asserted against the **import AST**, not
  against a substring, so a docstring that merely mentions `urllib` cannot make
  the test pass or fail spuriously;
* a full replay is exercised in the test suite with `socket.socket` and
  `socket.create_connection` monkeypatched to raise;
* it needs no key, no `.env`, and no writable cache.

---

## 2. 6-A — FIRMS NRT acquisition

`live/firms.py`

* **NRT only.** `fetch_hotspots` raises on any source not ending `_NRT`. The
  `*_SP` archives are better data that lag by ~2 months; polling one would turn
  a live pipeline into a historical one without changing a line of output.
  Configured sources: `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT`,
  `MODIS_NRT`.
* **Polling interval** `live.firms.poll_interval_min`, default **180 min**.
* **All-or-nothing.** If one source fails after its retries (30/60/120 s
  backoff) the whole poll is discarded. A partial hotspot list reads as "no new
  fire", which is the single wrong answer here — the same rule §5.6 sets for
  Overpass.
* **A new hotspot** is one whose coordinate was absent from every previous poll.
  Two filters: exact key (4 dp ≈ 11 m), then a **375 m radius** — one VIIRS
  pixel. Anything closer cannot be resolved as a separate fire and must not be
  reported as one. The batch is also de-duplicated against itself, so one
  overpass over a fire front yields a handful of new points rather than 400
  near-identical ones.
* **Snapshotted immediately.** Every acquisition is written to the run directory
  *and* registered in `data/snapshots/` before anything is derived from it
  (§5.8 — never write acquired data only to a git-ignored cache).
* **The MAP_KEY is never recorded.** It appears in the request URL and nowhere
  else: every URL that reaches a log, an artifact or an exception passes through
  `_redact`. Asserted.

Confidence is normalised across instruments (VIIRS `l/n/h`, MODIS 0–100) onto
one ladder. **An ungradable value ranks `low`** — a detection we cannot grade
should not be the one that fires a dispatch.

---

## 3. 6-B — trigger → routing → delivery

A new hotspot inside the registered bbox, at or above `min_confidence`, with the
re-trigger interval elapsed, runs the **459-series scan** against the canonical
field and renders the three PHASE-3 formats.

| input | value |
|---|---|
| hazard field | **`data/processed/routing_demo_canonical.npz`** (정본), sha256 `81b4e4d159daa7a8…` |
| walk graph | `osm-walk_yeongdeok-2025_20260724_2bff8d85.graphml.gz` (snapshot store) |
| refuges | `osm-shelters_yeongdeok-2025_…` — 50 POIs → 46 nodes |
| parameters | identical to every 459-series run: slope 60 m, distance objective, 600-min budget, 10-min step, stride 18, p_cut 0.5 |

`routing_demo.npz` is **refused by name** at start-up: it is the output of a
reverted run (§2-A).

### The result is the committed one

The live scan reproduces `real_roads_real_hazard_canonical.json` exactly:

| | origins | both_safe | FA-only | no_safe | over budget |
|---|---:|---:|---:|---:|---:|
| committed batch run | 458 | 414 | 42 | 2 | 0 |
| **live pipeline** | **458** | **414** | **42** | **2** | **0** |

That is the point of the design: the live path is the same computation with a
different trigger, not a second implementation that might mean something else.
The origin rule is pinned line-for-line against the batch scan in the tests.

### Resident-side, so the sheets do not say 차량

The 459 series has **three buckets, no responder, no depot, no vehicle ETA**.
The mapping onto the delivery layer:

| bucket | on a sheet as | wording |
|---|---|---|
| `naive_into_FA_safe` | 안내 지점 | 최단 경로는 화재 통과 — 우회 경로 필요 |
| `no_safe_route` | 도보 대피 불가 | 예산 내 안전한 보행 경로가 없음(우회 포함) |
| `fa_exceeds_budget` | 도보 대피 불가 | 보행 경로는 있으나 대피 시간 예산 초과 |
| `both_safe` | — not on a sheet | |

`printable`, `sms` and `broadcast` were written for the 439 series, whose
unreachable points are places a **vehicle** cannot reach. Saying 차량 on a 459
sheet would describe a computation that was not performed. So the delivery layer
gained **purely additive** resident-side variants — `compose_family_walk`,
`compose_welfare_walk`, `broadcast.compose(mode="walk")`, and heading overrides
on `render_html`. **Every default is the original string**, so the committed
`outputs/dispatch*` sheets render byte-identically; a test asserts that too.

`남은 시간` on a live sheet is the origin's **own** time-to-cutoff — the minutes
until that place reaches the impassable probability. For a 이장 that is the same
question the 439 column answered, asked of a person on foot.

### The scope statement costs page space, and the one-page rule wins

The first full run put the mandated strings into **five** bordered banner boxes.
That pushed the largest cluster (9 dispatch rows) onto a **second A4 page**, and
one page per village is a PHASE-3 design constraint — a second page gets
separated from the first.

Nothing was dropped to fix it. The block was **compacted to two boxes**: the
mode banner stays on its own (it must be the first thing seen), the scope
statement and both mandated lines merge into one, and the standing 32.6 %
coverage qualifier moves into the **footer**, where the fixed cautions already
live. The footer is dense small text rather than a bordered box, and a standing
qualifier about the whole sheet belongs there rather than among the warnings
about things on it.

Result: **29 of 29 sheets on one page**. A test asserts all five mandated
strings survive the compaction, so a future edit cannot quietly buy page space
by deleting one.

### Field applicability — the honest limit, stamped rather than hidden

The canonical field was simulated for one fire. A hotspot 40 km away is a real
detection, but the field is not a statement about it. So every run measures the
distance from the triggering hotspot to the field's **own t = 0 core** and
records a verdict:

* `IN_SCOPE` — within `field_applicability_radius_km` (default 15 km);
* `OUT_OF_SCOPE` — beyond it. **Outputs are still produced**, and every one is
  stamped with the distance on its face.

It is a **label, never a filter**. Nothing is dropped: suppressing a real
detection is worse than publishing a stamped one.

> ⚠ The anchor is the **field's core**, not `fire_manifest.json`'s declared
> ignition point. For `yeongdeok_2025` those differ by **17 km** — the manifest
> records 129.05, 36.43, which falls *outside the walk bbox entirely*, while the
> observed first-overpass core sits at 129.222, 36.466. Anchoring on the
> manifest would have put every genuine in-region detection out of scope; the
> first smoke run did exactly that, at 28.6 km, which is how it was found. Both
> distances are recorded in `RUN.json`.

---

## 4. 6-C — replay mode

```bash
python scripts/run_live_detection.py --replay                    # 60x, 12 h window
python scripts/run_live_detection.py --replay --speed 720        # fast check
python scripts/run_live_detection.py --replay --replay-hours 40  # the whole fire
python scripts/run_live_detection.py --replay --speed 0 --no-pdf # as fast as possible
```

* **Speed** is archive-seconds per wall-second. `60` (default) puts twelve hours
  into twelve minutes. `0` means "as fast as the machine allows" and is what the
  tests use, so correctness never depends on real sleeping.
* **Window.** `--replay-hours` (default 12) cuts the archive at `t0 + N h`. The
  region filter is applied **first**, so the window is a window on the
  registered region's own detections.
* **Overpasses** are clustered on a 90-minute gap — the same grouping
  `spread_v2.grid.overpass_snapshots` used to build the hazard field.
* **「재생 모드」 is on everything**: the console banner, every A4 sheet, every SMS
  draft header, and as the **first spoken line** of every 마을방송 script
  (`재생 모드입니다.`) so a recorded demonstration cannot be mistaken for a live
  warning even by someone who only hears it.

### What the Yeongdeok archive actually contains

Within the walk bbox, the first 12 archive hours hold **848 detections across 2
overpasses** spanning 5.5 h (12:25 → 17:58 UTC on 2025-03-25). At 60× that is a
**5.5-minute** replay, not 12. The whole fire (`--replay-hours 40`) is 6
overpasses over 40 h. Stated here because "12시간을 12분으로" describes the
multiplier, not this archive.

The committed run (`outputs/live/replay/`) is that default: 60×, 12 h window,
**2 triggers**, each producing 29 villages / 44 points (42 안내 + 2 도보 불가)
from the same 458/414/42/2 scan.

---

## 5. 6-D — the state record

Every triggered run writes `outputs/live/{replay|live}/{timestamp}/`:

```
RUN.json                     the audit record (below)
MANIFEST.json                villages, formats, page budgets, demo-mode state
{NN}-{마을 이름}/
    dispatch_a4.html         the A4 sheet — the canonical artifact
    dispatch_a4.pdf          headless-Chrome conversion, page-budget checked
    broadcast_script.txt     마을방송, ≤15 chars per line
    sms_drafts.json/.txt     drafts. NEVER sent.
```

`RUN.json` answers, without running anything: which hotspots came in and from
where; **which one pulled the trigger**; which hazard field was used, by path
*and* sha256; what the **weather basis** of that field was; how long each stage
took; what came out; and whether anything was transmitted (`nothing_was_sent:
true`).

The **seen-set** (`state_{region}.json`) is written *before* routing begins, so a
crash mid-route cannot cause the same hotspot to trigger again on restart. A
state file belonging to another region is discarded rather than reused —
otherwise it would silently suppress this region's first real detection.

---

## 6. Measured timings

Measured on the reference environment (`wfg311`, this machine), full 458-origin
scan, from `RUN.json`:

Two triggers, both on the full 458-origin scan:

Two triggers, both on the full 458-origin scan
(`outputs/live/replay/*/RUN.json`):

| stage | trigger 1 | trigger 2 |
|---|---:|---:|
| load hazard field (npz) | 0.001 | — (warm) |
| load + slope-build walk graph | 2.92 | — (warm) |
| load refuge POIs | 0.06 | — (warm) |
| **routing (458 origins, 2 solves each)** | **26.72** | **24.87** |
| cluster (DBSCAN, eps 500 m) | 0.09 | 0.001 |
| render 3 formats × 29 villages (HTML/txt/JSON) | 0.06 | 0.07 |
| **trigger → the dispatch list (warm)** | **26.87** | **24.93** |
| process start → the dispatch list (cold) | 29.86 | 27.92 |
| — A4 PDF conversion, 29 sheets (*separate*) | 79.15 | 77.99 |

The ~1.9 s spread between the two routing figures is first-run warm-up (page
cache, NumPy/`networkx` import paths); the second trigger is the steady state.
Across three full runs routing measured **24.9 – 28.2 s**, so quote **"about 25
seconds"** and treat 30 s as the safe upper bound.

**Say "about 25 seconds", not "a few seconds".** Routing is 99 % of it: 458
origins × (one Dijkstra + one time-expanded search). The delivery layer — the
part that looks like it should be slow — is **40 milliseconds**.

*Warm* is what a running service exhibits, because a service loads the field and
graph once at start-up. *Cold* is process start to the list.

### Why PDF conversion is reported separately

Headless Chrome costs ~2.7 s per sheet, so 29 villages come to ~78 s — three
times the routing. It is excluded from `warm_total_s` and reported as `pdf_s`
because it happens **after the dispatch list already exists**, in every text
format, and it scales with the *number of villages* rather than with the
decision. Folding it in would answer "how long to print 29 sheets?" when the
question is "how long until an operator has the list?".

`warm_total_with_pdf_s` (106.0 / 102.9 s) is carried in `RUN.json` for when the
printed sheets are what is actually being waited on. `--no-pdf` skips the step
entirely and is the right flag for a timing demonstration.

> This split was introduced *after* the first full replay run reported 103.7 s as
> its headline, which conflated the two. The earlier number was not wrong, but
> it answered the wrong question.

---

## 7. Safety properties, and how each is enforced

| property | enforcement |
|---|---|
| the pipeline itself transmits nothing | `sms.send` is not called anywhere in `live/` or the runner — asserted against the **call AST** of every module, not a substring. `DEMO_MODE` is on unless the env var is exactly `"0"`, and `send` still requires a positional `approval_token`. ⚠ Since PHASE 7 a *separate*, manually-invoked script (`send_dispatch_email.py`) **can** transmit by email after an operator types a confirmation; the automatic pipeline still cannot. [`delivery_channels.md`](delivery_channels.md). |
| no committed artifact moves | the four protected digests are recorded before and after every run; exit **4** if one moves. |
| `routing_demo.npz` is never consumed | refused by name at start-up. |
| the ERA5 lag is never hidden | `scope.py` owns the strings; every artifact carries both lines; tests assert `"5일 지연"` survives. |
| the 32.6 % coverage caveat travels | added to every A4 sheet's banner block, because these are **absolute Yeongdeok counts** reaching an operational sheet (§2-A, rule 19). |
| replay cannot reach the network | no HTTP import (AST-checked) + a full replay run under a disabled socket layer. |
| a partial FIRMS poll is never used | all-or-nothing across sources. |
| credentials never leak | values are never printed; only variable **names** are reported; URLs are redacted before recording. |

### Twilio

`.env` currently holds `FIRMS_MAP_KEY` and `OPENTOPOGRAPHY_API_KEY`. **No Twilio
credentials are present (0 of 3)**, so the SMS layer stays in `DEMO_MODE` and
composes drafts only. This is recorded in every `RUN.json` under `notes` and
printed on every run. It changes nothing operationally: this PHASE composes
drafts and stops there by design, so even a fully configured Twilio account
would not be used.

---

## 8. Configuration

All of it under `live:` in `config/default.yaml` — a **pure addition**, so no
existing value moved (the config hash changes; no number depends on the new
keys).

| key | default | why |
|---|---|---|
| `live.region` | `yeongdeok_2025` | the registered region |
| `live.hazard_npz` | `routing_demo_canonical.npz` | 정본 |
| `live.firms.poll_interval_min` | 180 | VIIRS revisit cadence |
| `live.firms.dedupe_radius_m` | 375 | one VIIRS pixel |
| `live.trigger.retrigger_min_interval_min` | 180 | without it one overpass queues 400 identical runs |
| `live.trigger.min_confidence` | `nominal` | |
| `live.trigger.field_applicability_radius_km` | 15 | labelling threshold, never a filter |
| `live.replay.default_speed` | 60 | twelve hours in twelve minutes |
| `live.replay.default_window_h` | 12 | |

---

## 9. Known limits

1. **The hazard surface is fixed.** The strongest limit, and the reason for the
   scope statement. Removing it needs a real-time weather source; ERA5 cannot be
   one. KMA's public API could, and that is a project, not a parameter.
2. **One region.** The registered region is Yeongdeok. The other two have hazard
   fields and snapshots, so extending is a config change plus a run — but their
   fields carry their own applicability anchors and have not been exercised here.
3. **32.6 % coverage.** Every absolute count on a live sheet is a count on the
   covered third of the canonical fire core (§2-A). The caveat is on the sheet.
4. **`OUT_OF_SCOPE` is a label, not a rerouting.** When a hotspot is far from the
   field's core the system says so and still produces the list. It does not
   simulate a new field, because it cannot.
5. **The live branch has been exercised against the real API for reachability
   and credentials, but no trigger has ever fired on a live detection** — that
   needs an actual fire in the registered bbox. The replay branch is what has
   been run end to end.
