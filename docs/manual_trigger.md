# PHASE 12 — the manual ignition-point trigger

Round-3 PHASE 12. Written 2026-08-03.

`scripts/run_manual_trigger.py` · `tests/test_manual_trigger.py` (21 tests)

```bash
python scripts/run_manual_trigger.py --lat 36.4436 --lon 129.3696 --reported-by "119 신고"
python scripts/build_operator_screen.py --region yeongdeok_2025 --trigger-source manual \
    --out outputs/live/screens/yeongdeok_2025_manual.html
```

---

## 0. Why

The pipeline reacted only to FIRMS. But in real operation a wildfire's location
arrives from a **119 call, a watch-tower, or a CCTV operator** long before a
satellite sees it: VIIRS revisits roughly every 12 hours, and FIRMS NRT then
publishes within about three hours of the overpass. Waiting for a detection can
cost hours that a phone call did not.

**Both triggers coexist.** `run_live_detection.py` still polls FIRMS and still
replays. This adds a third door into the same room.

| source | what fires it | what the trigger time means |
|---|---|---|
| `firms_nrt` | a satellite overpass, polled | **when an instrument observed** a fire |
| `replay` | an archived overpass, replayed | as above, recorded |
| **`manual`** | **a person entering a coordinate** | **when a person reported** one |

---

## 1. Identical downstream, by construction

The manual script does **not** reimplement the pipeline. It builds a one-point
trigger and hands it to `run_live_detection.run_trigger` — the same function the
FIRMS and replay branches call. Routing, classification, clustering and the
three delivery formats are therefore the *same code*, not merely the same idea.

A test asserts this against the import and call AST: `run_trigger` must be
imported from `run_live_detection`, and `pipeline.route_region`, `deliver`,
`write_viz` and `build_run_record` must **not** appear here — calling them
directly would fork the path.

### Measured equivalence

Same coordinate (36.4436, 129.3696), same region, same pre-computed field:

| | verdict |
|---|---|
| bucket counts | **identical** — 458 / 414 / 42 / 2 |
| villages, points | **identical** — 29 / 44 |
| every village name | **identical** |
| every point (label, window, bucket, note) | **identical** |
| SMS drafts | **identical** |
| hazard field digest | **identical** |
| weather basis | **identical** |
| parameters, applicability verdict | **identical** |
| 마을방송 script | **differs by one line** — see below |

The broadcast script is the single intended difference: the replay branch
prepends 「재생 모드입니다.」 so a recorded demonstration cannot be mistaken for a
live warning. A manual trigger is a *real* report, so it must not say that. The
rest of the script is byte-identical.

---

## 2. ⚠ The trigger time means something different here

For FIRMS and replay it is a **satellite overpass**. For a manual trigger it is
**when the coordinate was entered**. Those are not the same kind of fact, and
the difference is stated in four places rather than left to be inferred:

* the console — `⚠ 위 시각은 좌표 입력 시각이며 위성 통과 시각이 아닙니다.`
* `RUN.json` — `scope.trigger_at_meaning`, and
  `manual_trigger.entered_utc_meaning`
* the operator screen's status bar — a separate warn cell,
  `트리거 시각 = 좌표 입력 시각 (위성 통과 시각 아님)`
* the detection line itself — 「발화점: 수동 입력 · {시각}」, which does **not**
  say `FIRMS NRT`, because no instrument was involved

That last one matters most. `scope.detection_line()` returns the FIRMS wording
for the FIRMS and replay sources and the manual wording for this one, so a
coordinate someone phoned in can never be presented as a satellite detection.
The PHASE-6 mandated line is unchanged for every pre-existing caller — a test
pins that too.

---

## 3. The region gate

A coordinate outside the registered walk bbox is **refused** (exit **3**) before
any routing happens:

```
STOP (exit 3): 좌표가 등록 지역 bbox 밖입니다.
  이 지역의 보행망·대피소·위험면은 이 범위에 대해서만 준비되어 있으므로,
  범위 밖 좌표로 산출하면 없는 근거를 만들어내는 것이 됩니다.
```

The walk network, the refuge POIs and the hazard surface exist only inside that
box. Producing a dispatch list for a coordinate outside it would be inventing
evidence, not extrapolating it. A test asserts the gate precedes the routing
call in `main`'s AST.

**Address and 지번 lookup are out of scope** — latitude and longitude only. Also
asserted, so a geocoder cannot be added later without the claim widening
deliberately.

---

## 4. What is recorded

`outputs/live/manual/{region}/{timestamp}/` — the same structure the FIRMS path
writes, plus a `manual_trigger` block in `RUN.json`:

```json
{
  "trigger_source": "manual",
  "manual_trigger": {
    "reported_by": "119 신고",
    "input_lat": 36.4436, "input_lon": 129.3696,
    "entered_utc": "2026-08-03T05:12:36Z",
    "entered_utc_meaning": "when the coordinate was entered by an operator; NOT a satellite overpass time",
    "inside_registered_region": true,
    "region_bbox_wsen": [129.25, 36.3, 129.55, 36.6],
    "hazard_field": "data/processed/routing_demo_canonical.npz",
    "hazard_field_sha256": "81b4e4d1…",
    "hazard_weather_basis": "2025-03-25 12:25 UTC",
    "input_to_dispatch_list_s": 28.715,
    "input_to_dispatch_list_excludes_pdf_s": 79.0
  }
}
```

The hazard field is **not re-simulated**. It is the same pre-computed surface
the FIRMS path uses, and its weather basis is recorded beside it — a manual
report decides *whether* and *where* to act, exactly as a detection does. ERA5
publishes on a ~5-day lag, so no surface exists for today whatever triggered the
run.

---

## 5. Measured: coordinate in hand → dispatch list

Five consecutive runs, `--no-pdf`, idle machine:

| run | cold (incl. load) | of which routing | warm |
|---|---:|---:|---:|
| 1 | 29.7 s | 26.7 s | 26.8 s |
| 2 | 29.3 s | 26.5 s | 26.7 s |
| 3 | 30.2 s | 27.4 s | 27.6 s |
| 4 | 29.6 s | 26.7 s | 26.8 s |
| 5 | 26.2 s | 23.4 s | 23.6 s |
| **median** | **29.6 s** | **26.7 s** | **26.8 s** |

Plus the committed run with A4 PDFs: **28.7 s** to the list, **+79 s** for 29
sheets afterwards.

* **cold** — process start to a dispatch list in every text format, including
  loading the field, the graph and the POIs.
* **warm** — what a running service exhibits, having loaded those once.
* **A4 PDF conversion is excluded from both**, as everywhere else in this
  project: it runs after the list already exists and scales with the number of
  villages rather than with the decision.

**Say "about 30 seconds from a 119 call to a dispatch list."** Routing is ~90 %
of it; the delivery layer is 60 milliseconds. This matches the FIRMS path
because it *is* the FIRMS path — the only thing the manual door skips is waiting
for an overpass, which is the hours, not the seconds.

---

## 6. The operator screen

`--trigger-source manual` builds a screen from a manual run:

* the badge reads **수동 입력**, not 재생 모드;
* the status bar's first cell reads 「**발화점: 수동 입력 · {시각}**」 on a
  distinct blue ground;
* a warn cell beside it reads 「트리거 시각 = 좌표 입력 시각 (위성 통과 시각
  아님)」;
* the trigger sits at **t = 0** — there is no overpass to wait for, which is the
  whole point — and there is exactly **one** point on the map, the reported
  coordinate;
* the pre-roll defaults to **0**: nothing preceded the report to lead in from.

> ⚠ **`--trigger-source` is now required when a region has runs from more than
> one source.** `--region` used to pick the newest run of *any* source, which
> silently built a FIRMS screen out of a manual run. Ambiguity is an error now,
> not a coin toss.

---

## 7. Limits

1. **Coordinates only.** No address or 지번 lookup.
2. **The surface is still pre-computed and still anchored to its own fire.** A
   manual coordinate far from that fire's core is stamped `OUT_OF_SCOPE` exactly
   as a FIRMS hotspot would be — the outputs are produced and labelled, never
   suppressed.
3. **One coordinate per run.** A report of several simultaneous ignitions would
   need several runs; nothing aggregates them.
4. **`--reported-by` is recorded verbatim.** It is a channel label
   (119 신고 / 감시원 / CCTV), not a place for a caller's name or number.
