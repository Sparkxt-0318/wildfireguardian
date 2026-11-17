# Test B: radar, corner reflector, nothing / flame / smoke / mist

Status: protocol written 2026-11-17, not yet run. Print and fill in by hand.

The flame AND smoke conditions need `--risk-assessment PATH --supervisor NAME` (the record script refuses to run
without them): a smouldering smoke source still burns. The flame condition also needs `--flame-kind bunsen|other`.

Flame source for test B: as approved in the signed risk assessment. The analysis assumes a Bunsen-size flame (the
same burner as test A); any run recorded with `--flame-kind other` is flagged in `B_gate.csv` and under Problems.

## Purpose

Measure how a flame, smoke alone and water mist on the line of sight change the echo of a static corner reflector
at 2, 3, 4 and 5 m: loss (dB), amplitude flicker (dB) and phase flicker (rad) at the reflector's range bin, against
the noise of repeated "nothing" runs. Smoke must show no effect (the app's smoke assumption). If a flame effect is
smaller than 3 sigma of the nothing runs, the analysis prints **"flame effect below noise"** and that is the
result.

## Equipment

| Item | Notes | Tick |
|---|---|---|
| Roof unit with the IWR6843AOP EVM streaming (radar baseline uses the heatmap) | Radome fitted as on the vehicle | [ ] |
| Aluminium trihedral corner reflector, edge ____ mm | On a non-metallic stand at radar height | [ ] |
| Tape measure; floor marks at 2, 3, 4, 5 m from the radar face to the reflector apex | | [ ] |
| Flame source as approved in the risk assessment (e.g. Bunsen burner) on a non-flammable base | Mid-way on the line of sight | [ ] |
| Smoke source with no flame (e.g. smouldering incense bundle in a metal tray, or a cold-smoke generator) | Check with the thermal camera: no flame-temperature pixels | [ ] |
| Mist source (hand-pump garden sprayer / misting nozzle) | Water must not reach the unit | [ ] |
| CO2 extinguisher, fire blanket, safety glasses | | [ ] |

## Safety

- Flame condition: adult supervisor present and named; signed risk assessment; nothing flammable within 1 m;
  gas off between runs; never leave the flame unattended.
- Smoke: outdoors or with extraction; nobody stands in the smoke; a smouldering source still burns: same fire
  precautions as the flame, and the same gate (signed risk assessment and named supervisor, enforced by the record
  script; a cold-smoke generator passes the same gate).
- Mist: keep the spray plume away from the unit and the laptop; the EVM is not waterproof.
- The radar transmits at 60-64 GHz at evaluation-module power; nobody needs to stand in front of it, and nobody
  should, because people in the view change the echoes.

## Set-up

1. Clear line of sight; no other metal within about 1 m of the line from the radar to the reflector.
2. Reflector apex facing the radar, centred on boresight, same height as the radar.
3. Condition source at half the reflector distance (or note the distance: `--flame-distance-m`).
4. Nothing in the scene moves during a distance block (people stay behind the radar).

## Steps (per distance)

1. Baseline: `python -m field_tests.b_radar_record --distance-m 3 --condition nothing --role baseline` (30 s).
2. Then, in a randomised order written down here, 3 x nothing, 3 x flame, 2-3 x smoke, 2-3 x mist:
   `python -m field_tests.b_radar_record --distance-m 3 --condition smoke --repeat 1 --smoke-source "..."`
   Each run: 10 s pre (off) -> "condition_on NOW" (30 s) -> "condition_off NOW" (10 s).
3. Flame: `... --condition flame --flame-kind bunsen --flame-source "Bunsen burner, air hole closed" --risk-assessment PATH --supervisor NAME`.
   Smoke: `... --condition smoke --smoke-source "..." --risk-assessment PATH --supervisor NAME`.
4. Move the reflector to the next distance and start again from the baseline.

Analysis: `python -m field_tests.b_radar_analyse --runs records/field_tests/B --out records/field_tests/B/analysis`.
It also writes `B_gate.csv` (risk-assessment SHA-256 and supervisor per run; a flame or smoke run without them is
GATE MISSING, never dropped) and checks the runs against this plan (2, 3, 4, 5 m; >= 3 nothing, 3 flame, 2 smoke,
2 mist per distance). A metric whose noise sigma or effect cannot be computed (e.g. a single nothing window) is
reported as "not computable", never as an effect.

## What to record (by hand)

| Distance (m) | Order of runs | Flame/smoke/mist source and position | Wind | People/vehicles moving in view? | Notes |
|---|---|---|---|---|---|
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

## Known limits

- A Bunsen flame covers a small fraction of the radar beam (about 30 deg half-width); a small or no effect is the
  expected outcome and is reported as measured.
- Window statistics assume a static scene; any movement in view adds flicker to every condition.
- The radar alone never decides FLAME in the app: FLAME needs the radar effect and flame-temperature pixels.
