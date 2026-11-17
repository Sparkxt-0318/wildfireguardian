# kcf-heat: making radiant heat bind in routing

The frozen heat law caps at 0.703 kW/m² because it spreads a point's 11.5 s burn over the 66 min a front takes to
cross a 375 m cell. This directory derives a closed-form front law, checks it against a 3D FDS grass fire
(model-to-model), and puts it into the F-3.1 deadline field.

Nothing outside `research/kcf-heat/` is changed. The closure rule subclasses F-3.1's `PacketModel`, and the v2 law is
called from `experimental/flame-front-radiation` unchanged.

| document | answers |
|---|---|
| [DERIVATION.md](DERIVATION.md) | why 0.703; the line-source law; T\* = χE_A/(2πq\*) − t_r/2; packet values; verdict and limits |
| [FDS_CHECK.md](FDS_CHECK.md) | B.1 reproduction with corrections; B.2 FDS radiometer rerun; one figure; the v2 factor-of-three gate decision |
| [ROUTING_EFFECT.md](ROUTING_EFFECT.md) | the closure rule; one table of leave-by shifts, lost routes and witness TDU; the multi-hour status |

## Results in brief

* **A.** The law is correct under its assumptions. On packet values T\* = 1.38 / 2.87 / 5.83 min at
  10 / 5 / 2.5 kW/m².
* **B.1.** Reproduced from the C064 field with a 20 kW/m³ leading edge. The closed form is **9–11% high** (not
  16–17%). v2 as implemented (two panels) is **2.2–2.9× high**; the brief's 1.5–1.9× matches the leading panel alone.
* **B.2.** FDS's own radiometers read **6× (1–3 m) to ~100× (40–60 m) below** both the voxel sum and the closed form.
  The run is bit-reproducible and the orientation convention was verified. A fit suggests FDS at 1 m cells behaves
  like a self-absorbing flame zone plus path absorption.
* **Gate.** Not passed; v2 stays on HOLD. The closed form is adopted only as a conservative screening law.
* **C.** On the 1-hour panel, heat moves **6 of 508** leave-by times (median 84 s, max 346 s) and costs **1** place
  its route. Witness doses:
  * 30 of 15,727 witnesses exceed the pain / first-degree thresholds (92 / 105 TDU), none the second-degree one
    (290 TDU; HSL/2004/04);
  * without heat, 16 exceed 1000 TDU;
  * the multi-hour runs are NOT RUN (inputs absent here).

## Layout

| path | what |
|---|---|
| `kcf_heat/law.py` | frozen cap, line law, finite-front factor, lead time and halo |
| `kcf_heat/voxel.py` | front metrics and voxel-sum radiometer on FDS HRRPUV fields |
| `kcf_heat/v2_adapter.py` | evaluates the repo's v2 panel law on a straight front |
| `kcf_heat/closure.py` | `HeatRule`, `HeatPacketModel` (variant `cert_heat`) |
| `kcf_heat/exposure.py` | flux along witness routes, TDU |
| `scripts/` | B.1, FDS input and guarded run, slice stitching, B.2 comparison and absorption fit, figure, C.2 1-hour and multi-hour runners, summary, TDU |
| `tests/` | 28 tests: numerical-integration checks of the derivation, voxel and TDU, and closure against a sampling oracle on a real packet |
| `data/` | small evidence files: FDS inputs, devices, HRR, guards, both runs, orientation check; B.1 and B.2 JSON; 1-hour summaries and TDU counts |
| `figures/fds_check.png` | the FDS_CHECK figure |

## Requirements

* Python 3.12, numpy (1.26.4 used), matplotlib, pytest.
* The frozen routing inputs (`python tools/fetch_routing_inputs.py`). The closure tests skip without them.
* For B.1 and B.2: the attached study zip `WildfireGuardian_C064_Temporal_Helicopter_Study.zip` (sha256 `5524404f…`)
  and FDS 6.11.1.

```sh
python -m pytest -q -p no:cacheprovider research/kcf-heat/tests
```
