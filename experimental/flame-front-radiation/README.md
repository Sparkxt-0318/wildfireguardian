# Flame-front radiation law v2 (opt-in research library)

`wfg_flamefront` implements `wfg.radiation.law/2-flamefront` (Contract C of `docs/NEXT_INTERFACES.md`): flame segments on the isochrone of a scenario member's arrival field, Byram intensity and flame length, solid-flame view factors, incident flux at points, a rigorous flux enclosure over boxes and time intervals, and linear and TDU dose. It needs NumPy only and does not import the frozen kit. Equations, constants, sources and the enclosure argument: [`docs/RADIATION_LAW_V2.md`](../../docs/RADIATION_LAW_V2.md). Evidence: [`research/flame-front-radiation/README.md`](../../research/flame-front-radiation/README.md).

This is a model-relative research construction. Nothing in it is field validated, and it makes no physical-safety claim.

## Use

```python
import sys; sys.path.insert(0, "experimental/flame-front-radiation/src")
import wfg_flamefront as W

members, grid, info = W.load_packet_members("data/routing/latest_inputs_try02/packets/uljin_2022/20220304T060000Z")
q = W.flux_at_points([[1160000.0, 1900000.0]], [600.0, 1200.0], members[0], grid, None)      # kW/m2, [P, T]
lo, up = W.flux_enclosure((1159990, 1160010, 1899990, 1900010), (600.0, 610.0), members[0], grid, None)
d = W.dose(q[0], [600.0, 1200.0], form="tdu")
segs = W.front_segments(members[0], 600.0, grid, 11.52)
p = W.provenance()
```

`member` is a mapping of the v1 member arrays (`ignition_time_s`, present-fire `current_active` and `remaining_s`, `burning_duration_s`, optional masks, or the bridge's `breakpoints` and `flame` frames) or a prepared `FrontField`. `fuel` is `None` (defaults), a mapping or `FuelParameters`; `emissive_power_kw_m2` is the flame-surface E of the panels and `inflame_emissive_power_kw_m2` the in-flame value (default: the same). The measurement-consistent variant used in the evidence is `{"emissive_power_kw_m2": 22.6, "inflame_emissive_power_kw_m2": 100.0}`.

## Layout

- `src/wfg_flamefront/`: `field.py` (grid, arrival field, v1 activity), `isochrone.py`, `intensity.py`, `solidflame.py`, `law_v2.py`, `provenance.py`.
- `adapters/` (test-only, evaluation): `frozen_copy/` holds byte-identical copies of the frozen routing `core.py`, `independent.py` and `phaseB/zsweep.py` (hashes in `SOURCE_SHA256.json`; the package marker `__init__.py` is new). `journey_check.py` switches `radiation_law="v1" | "v2"`; v1 is the frozen centre check, v2 keeps its contact test and evaluates radiation with this library. `policy_sweep.py` and `flux_tables.py` run the five-policy study; `journeys.py` extracts the 18 returned journeys.
- `tests/`: unit and regression tests. `tools/write_manifest.py` rewrites `SOURCE_SHA256.json`.

## Tests

From the repository root, in a fresh environment:

```sh
python3.12 -m venv /tmp/wfg-1a && . /tmp/wfg-1a/bin/activate
pip install -c constraints-routing.txt './integration[packets]'
pip install -c constraints-routing.txt -r experimental/flame-front-radiation/requirements-test.txt
python -m pytest experimental/flame-front-radiation/tests
```

Tests that need the frozen routing inputs read `WFG_ROUTING_INPUTS` (default `data/routing`, where `python tools/fetch_routing_inputs.py` writes them, else the shared verified copy `/home/user/wfg-shared/routing-inputs` used in this run) and skip when neither exists.
