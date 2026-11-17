# RESULTS: WildfireGuardian vehicle unit and crossing app

Status: 2026-11-17 (Tuesday). Hard stop: Monday 23 November, 18:00 Shanghai time.

**No hardware test has been run.** Every result below comes from simulated sessions (`wfgvu.synth`), from replays
of them, or from the FDS C064 virtual unit (step 8). Each is labelled SIMULATED. None shows that the unit works on a
vehicle or on a flame.

The verdicts are advisory for trained crews. Every limit is a placeholder (`LIMITS.md`).

The allowed claim is "vehicle-mountable unit, tested on a car and on lab flames, ready for a fire-service trial".
It may **not** be made yet: tests A-F have not run. No claim of operational readiness is made.

## 1. Hardware tests A-F

| test | what | status | result |
|---|---|---|---|
| A | flux plate vs Bunsen burner | NOT RUN. Needs the adult supervisor's signed risk assessment first; Bunsen burner only. | none |
| B | radar, corner reflector (nothing / flame / smoke / mist) | NOT RUN. Radar EVM not yet tested; flame and smoke conditions need the signed risk assessment. | none |
| C | thermal near edge vs tape, 3-15 m | NOT RUN | none |
| D | fail-safe CLOSED within 2 s | NOT RUN on hardware. Simulated loopback timings in section 4. | none |
| E | car roof, 30 min | NOT RUN | none |
| F | housing spray and hot air | NOT RUN | none |

What exists for each test:
- the script and protocol in `field_tests/`;
- an analysis that writes a Markdown snippet for this file;
- example outputs in `field_tests/example_outputs/`, made from SIMULATED inputs only and not results.

Paste each snippet below this table when its test has run, failures included.

**Radar contingency.** If the IWR6843AOP EVM has not arrived by Friday 20 November, the delivery is:
- simulated mode, thermal, flux and step 8, as the brief requires;
- this section then states that the radar was never run, and that flame confirmation, the radar ceiling and test B
  are untested.

As of this writing the radar has not been run with this software. All three radar configs are untested on the EVM.

**Thermal camera gain (FS-1).** The 300 °C flame threshold needs the TC001 in low gain, and nothing has verified
that yet. `crossing.yaml` sets `thermal.low_gain_verified: false`, so **every live (non-simulated) verdict is
CLOSED** until a lab check on a target hotter than 150 °C confirms low gain and its scale. Run this check early
in test C (or A).

## 2. Test suites (2026-11-17, laptop, Python 3.12 venv; loopback allowed)

| suite | result |
|---|---|
| `hardware/vehicle-unit` (Pi code, drivers, synth, docs) | 220 passed, 0 failed |
| `apps/crossing` (app, decision, depth, simlink, step 8, field-test analyses, web) | 527 passed, 0 failed |
| `tests/api -m 'not golden and not panel'` (step 9 live input and existing API) | 125 passed, 2 deselected |

Notes on the runs:
- Pi code is parsed with the Python 3.11 grammar: 27 files, 0 errors. It has not been run on a real 3.11 interpreter
  or on a Pi.
- `tools/verify_release.py`: PASS.

## 3. End to end over loopback sockets (SIMULATED)

Setup:
- The Pi sim server (`python -m wfgvu --sim <sample>`) feeds the crossing app over a real WebSocket on one laptop.
- Vehicles: `fire_engine`, and a TEST-ONLY profile (dose limit 1e6 TDU, has water) that makes the CROSS FAST path
  reachable.
- 0 pipeline errors in every run.

| sample | fire_engine | TEST-ONLY 1e6 TDU |
|---|---|---|
| no_fire | CLOSED throughout | CLOSED throughout |
| smoke_only | CLOSED; **0 FLAME ticks** | CLOSED; 0 FLAME ticks |
| water_mist | CLOSED; **0 FLAME ticks** | CLOSED; 0 FLAME ticks |
| corner_reflector_3m | CLOSED | CLOSED |
| after_pass | CLOSED (radar baseline only at 23 s) | CLOSED |
| flame_front | CLOSED (DOSE_OVER_LIMIT from 13.8 s, dose about 6,000-20,000 TDU) | CROSS FAST 13.7-24.9 s, 29.7-39.1 s and 44.5 s, CLOSED in between (min speed 0.1-0.2 m/s) |
| crossing | CLOSED (dose 22,324 TDU; INTAKE_AIR_OVER_LIMIT 23.7-25.5 s) | CROSS FAST 13.8-20.0 s, then CLOSED |
| crossing_return | CLOSED, then **REOPENED** at the end | same |
| crossing_return_hot (hot area left on the road) | CLOSED, **never REOPENED** | CLOSED, never REOPENED |
| flame_front_fail_radar | CLOSED | CROSS FAST until 20.9 s, then CLOSED SENSOR_NOT_FRESH:radar to the end |
| flame_front_freeze_thermal | CLOSED | CROSS FAST until 20.6 s, then CLOSED SENSOR_NOT_FRESH:thermal to the end |

REOPENED on crossing_return:
- Before the stopped-hold fix: 65.1 s (fire_engine) and 64.6 s (custom) over sockets.
- With the fix, the hold counts only while stopped: first REOPENED at 66.2 s over sockets (fire_engine) and 66.4 s in
  the in-process replay (5 Hz).
  - Truth stop at 36.69 s; speed below 1.0 m/s from 36.4 s.
  - quiet_s 30.0; GNSS stamp within 3 m of the true stop.
- Without the DEM, REOPENED never appears.

The flame_front CROSS FAST runs are broken up: the verdict flips between CROSS FAST and CLOSED (RADAR_UNKNOWN /
FLAME_EVIDENCE_TOO_SHORT) as the radar effect drops in and out. This fails closed, but it is unsteady for a crew.

### Depth against the sample truth (3.0 m flame depth), SIMULATED

Values are min / median / max over ticks with a valid depth.

| sample | depth_m | hi_m (display) | decision upper end | ticks with decision upper end below 3.0 m |
|---|---|---|---|---|
| flame_front | 0.46 / 0.58 / 1.22 | 1.07 / 1.22 / 7.51 | 1.22 / 3.77 / 7.51 | 8-9 % |
| crossing | 0.46 / 1.10 / 1.91 | 2.80 / 6.74 / 11.72 | same as hi_m | 1.3 % |
| crossing_return | 0.14 / 1.14 / 1.50 | 0.89 / 6.96 / 9.18 | same | 4-7 % |
| flame_front_freeze_thermal | 0.23 / 0.55 / 1.34 | 0.50 / 1.18 / 8.23 | 2.73 / 4.49 / 8.23 | 1.8 % |

**Failure:**
- The central depth is biased low on every flame sample: median 0.55-1.14 m against 3.0 m true.
- The DEPTH-HI rule takes the decision upper end as the largest upper end among the valid estimators. It raised the
  share of flame_front States whose interval covers the truth from 14 % to 93 %.
- But **during CROSS FAST (TEST-ONLY vehicle) the decision upper end fell as low as 2.73 m against 3.0 m true**.
  That side is not conservative.
- With real limits this could understate time in flame and dose.

## 4. Fault to CLOSED latency (SIMULATED, loopback, one laptop)

| fault (injected at about 20 s) | verdict before | first CLOSED after the fault | reason |
|---|---|---|---|
| radar stops (fail_radar) | CROSS FAST | +0.97 s | SENSOR_NOT_FRESH:radar |
| thermal frames frozen | CROSS FAST | +0.79 s | SENSOR_NOT_FRESH:thermal |
| Pi process killed (SIGKILL) | CROSS FAST | +0.19 s | LINK_DOWN |
| Pi process frozen (SIGSTOP) | CROSS FAST | +0.79 s | INPUT_TIME_MISSING:pi (LINK_DOWN at +1.59 s) |

- All four are under the 2 s target on loopback.
- CROSS FAST stayed on screen for up to 0.97 s after the fault, inside the freshness windows.
- After SIGCONT, the frozen Pi's link came back and the verdict stayed CLOSED.
- Delivery to the client added 4-14 ms. Wi-Fi and real hardware have not been tested; test D does that.
- Unit tests show that no single sensor failure, link loss or stale verdict can give CROSS FAST or REOPENED: see
  `tests/test_failsafe.py` and `tests/test_decision.py`.

## 5. Step 8: FDS virtual unit (SIMULATED)

The full table is in `virtual_fds/REPORT.md`. Summary:
- Depth:
  - The combined depth covers the 11.1 m truth in 9 of 9 windows (10 / 20 / 30 m), at 8.7-11.5 m [4.0-5.4,
    19.0-24.6].
  - The thermal near edge is 4.5-6.8 m too far.
  - The flame height is 2 to 4.6 times too low.
  - Byram is 3 to 10 times too low.
- **Radar with the shipped default config: UNKNOWN in 9 of 9 windows.** The noise-rise gate reads the clutter's phase
  flicker from hot gas in front of the flame as noise. Every verdict on this simulation would be CLOSED, and CROSS
  FAST cannot be reached. FLAME_EFFECT appears only with unscaled clutter or the old 0.0488 m bins.
- Estimator d (radar flicker extent) **does not work** as a depth measurement. Keep it experimental and off.
- Flux:
  - The plate model recovers its input to about 0.6 kW/m² rms and is noise-limited below about 0.3 kW/m².
  - Outside the flame, the closed form is 20-60 times above the FDS radiometers (conservative).

## 6. Step 9: live closures to the routing simulator (loopback only)

- `test_end_to_end_against_the_routing_api` started the real API (uvicorn, `WFG_API_LIVE_CLOSURES=1`, token) and
  passed:
  - with no token the handshake is refused;
  - a CLOSED with the token is applied;
  - the REOPENED of the same claim lifts it;
  - a REOPENED without the claim token is refused and the road stays closed;
  - CROSS FAST and SPRAY are never sent.
- Smoke run with the crossing app on the crossing_return sample:
  - The link connected.
  - It sent nothing, by design: simulated data is never sent as road state.
  - In the replay test mode it also sent nothing: no flame-backed CLOSED was decided in that sample.
  - So no CLOSED/REOPENED from a sample travelled the live path; only the constructed test above did.
- The root `.venv` lacks `websockets`. `api/requirements.txt` now pins `websockets==13.1`, and `make api-setup` must
  be re-run before `WS /v1/live/closures` works.
- Nothing was tested over a real network.

## 7. Known issues and open decisions (as measured)

1. **In-flame flux.**
   - At the true depth and intensity, the closed form gives 38.5 kW/m² against the FDS C064 in-fuel radiometers'
     78.2 / 62.6 kW/m². That is about 0.5 times, and not conservative.
   - The decision uses the depth lower end and the intensity upper end, which raises the value, but that margin has
     not been checked against FDS.
   - The FDS value is shown beside it, not used.
   - Decision needed: use max(closed form, FDS reference) for the dose?
2. **Depth biased low.** See section 3. The decision upper end still undercovers in up to 9 % of ticks, including
   CROSS FAST ticks.
3. **Radar config vs clutter.** In step 8 the default config never confirmed a flame. With real clutter it may be
   the same: a CLOSED that never lifts. This needs test B.
4. **CROSS FAST flicker.** On flame_front the verdict switches between CROSS FAST and CLOSED.
5. **Thermal gain (FS-1).** Every live verdict is CLOSED until the low-gain lab check is done.
6. **Radar baseline.** The baseline needs 30 stationary frames (4 s still for auto-baseline).
   - In crossing_return(_hot) and after_pass no baseline exists before the flame, so FLAME is never confirmed there.
     This fails closed.
7. **Hot spot read as depth.** crossing_return_hot reports a "valid" depth of 0.01-0.03 m from the hot spot after
   burn-out. The verdict stayed CLOSED, but only because the radar was UNKNOWN.
8. **Sim calibration pairs.** With `--no-log`, simulated runs still append calibration pairs to
   `records/calibration/pairs_sim.jsonl`, kept apart from live pairs.
9. **REOPENED needs a DEM** (`--dem`) and a forward turn that faces the crossing.
   - The laptop does not yet load the DEM path from session.json.
   - A reversing three-point turn makes the heading unknown and blocks REOPENED. This is by design and untested.
10. **Timing constants.** freeze_s, use_max_age_s and silence_s were chosen to meet 2 s on loopback. They are
    unmeasured over Wi-Fi.
11. **Samples size.** The `samples/` folder is at 4.93 MB of the 5 MB test budget.

## 8. Hardware results

(Empty. Paste the analysis snippets from tests A-F here, failures included.)
