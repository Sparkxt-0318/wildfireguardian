# WildfireGuardian

**Probabilistic wildfire mapping and time-dependent vehicle evacuation routing.**

WildfireGuardian studies how possible future fire development can inform a vehicle's entire journey: driving, permitted waiting and the required stay at a destination. Its intended use is to support responders and caregivers planning assistance for residents who may need more time to evacuate, including older adults. Field effectiveness and evacuation safety have not been established.

This repository contains the preserved October 2026 research release, subsequent verified engineering improvements, and opt-in experiments. **Merged code, passing software tests and scientific acceptance are separate states.**

[Run a recorded case](#2-replay-a-recorded-korean-routing-case) · [Results](#routing-results-and-their-scope) · [Current research status](#current-research-status) · [Verification](#6-verify-source-and-run-component-checks) · [Data and rights](docs/DATA_AND_RIGHTS.md)

## How the system works

**Environmental inputs and fire history → probabilistic forecast → scenario hazards → route search → complete-journey checking → decision**

1. **Forecast:** environment-conditioned, nonnegative convolution kernels combine neighboring burned-state information into new-burning probabilities. Recursive Monte Carlo simulation produces possible future fire histories and probability maps.
2. **Hazard construction:** versioned fire histories and declared thermal-source parameters become time-dependent flame-contact and heat-flux inputs. Unknown data and burning-duration assumptions remain part of the input contract.
3. **Routing:** generate flame-contact-avoiding candidate journeys and an earliest-arrival lower bound, then check the complete journey against the required contact, peak-flux, cumulative-exposure and destination-stay rules. A passing candidate that attains the bound can end the search within the declared model.
4. **Decision:** return a checked route, a no-route conclusion with an explicit model/horizon scope, or an unresolved result. Incomplete computation is not a no-route proof.

The forecast is the learned component; routing is a search-and-check algorithm. The GPS logger and illustrative 3D showcase are separate tools with their own evidence and launch instructions.

## Current research status

Status as of **31 October 2026**, following merged PRs [#85](https://github.com/Sparkxt-0318/wildfireguardian/pull/85), [#86](https://github.com/Sparkxt-0318/wildfireguardian/pull/86), [#87](https://github.com/Sparkxt-0318/wildfireguardian/pull/87), [#88](https://github.com/Sparkxt-0318/wildfireguardian/pull/88) and [#89](https://github.com/Sparkxt-0318/wildfireguardian/pull/89). **HOLD** means the stated scientific acceptance requirements remain unmet; it does not mean the code failed to run.

| Component | Available evidence and implementation | Acceptance boundary |
|---|---|---|
| Preserved forecast-to-routing release | c651 checkpoint, `wfg_latest` 1.0.0, kit v3; original Korean routing evidence | Default research reference; model-relative results, not field validation |
| Request-window/check-first routing | Opt-in kit; original-panel replay and separate Caldor/Rim engineering panel | Verified for the recorded inputs and limits; no default replacement or universal speedup |
| Graph preparation and authenticated reuse | Opt-in native preparation/cache package; separate matched research records | Preparation-stage benefit on the measured candidate; packaged/refactored source is not automatically benchmark-equivalent |
| New forecasting study | Frozen fits, saved-output audits, cohort accounting and descriptive intervals | Selected forecast **failed its primary superiority criterion**; no checkpoint promotion |
| Flame-front radiation v2 | Supported-geometry formulas, directed numerical controls and conservative bounds | **Physics HOLD**; empirical comparison and complete v2 journey integration remain open |
| Scenario members, SIPP and truth evaluation | Trajectory export controls and restricted contact-routing comparisons | **Full-policy risk HOLD**; unknown support and causal input alignment remain unresolved |
| Logger, API and showcase | Recording/interface tools and an illustrative local exhibition | No demonstrated field deployment or reduction in evacuation harm |

See the [combined scientific assessment](research/next-combined/README.md), [radiation requirements](research/flame-front-radiation/REQUIREMENTS_STATUS.json), and [post-merge verification report](research/postmerge-fixes-20261031/README.md). The combined assessment preserves its pre-merge history beneath a dated status note.

### Software verification after integration

PR #89 repaired the exact callback/source-provenance conflict, unresolved-outcome scoring, malformed extinction-field handling, SIPP deadline exits and stale merge-status documentation. Historical producer hashes and archived failures remain preserved.

- **3,531 forecast/cross-track tests passed**, including 24 new counterexample and source-mutation regressions.
- **177 radiation/export/scenario/SIPP/truth tests passed with no skips** in the complete environment.
- **3,640 protected artifacts remained byte-identical.**
- The same full suites passed in [GitHub CI](https://github.com/Sparkxt-0318/wildfireguardian/actions/runs/41154036377), alongside the macOS/Linux routing regressions. The required `gates` job now depends on the experimental suites as well as the earlier routing checks.

[Raw logs, retained setup failures, source identities and preservation receipts](research/postmerge-fixes-20261031/README.md) describe exactly what was verified. These are software checks, not new benchmark samples or physical validation.

## Routing results and their scope

The candidate is the proposed implementation; the reference is the project's repaired resource-constrained A* implementation. These comparisons do not establish superiority over every routing algorithm. Each study below retains its own source version, inputs, host and scoring rules.

### Frozen October 15 comparison

The native-Mac benchmark contains **20 missions across five Korean regional panels from four parent fires**, two implementations and two repetitions: **80 executions**. Mission endpoints are constructed benchmark requests on real road graphs, not observed evacuation journeys. Eligible destinations, opening intervals and required stays are mission inputs.

| Measure | Reference | Candidate |
|---|---:|---:|
| Missions resolved in both repetitions | 13/20 (65%) | **20/20 (100%)** |
| Missions providing checked routes | 13/20 (65%) | **15/20 (75%)** |
| Qualifying scoped-refusal missions | 0 | 5 |
| Unresolved executions | 14/40 | 0/40 |
| Median request time in 26 jointly resolved route pairs | 7.344 s | 8.006 s |
| Maximum recorded largest-process RSS | 2,055 MiB | 1,492 MiB |

**The result is 100% verified on-time mission resolution on this panel, not 100% routing accuracy or 20 evacuation routes.** Candidate and reference arrival times match in all 26 jointly resolved route pairs. More missions receive qualifying decisions, but these data establish neither a matched successful-route speed advantage nor a consistent paired memory saving.

All 80 outcome records were published within the 30 s request allowance. The reference's 14 unresolved executions comprise eight search-label-limit stops and six centre-only refusal publications without qualifying frozen authority; they are not 14 wall-clock deadline failures. Independent centre/contact checks found no recorded contradiction among the 56 returned-route executions. Continuous-road radiation-enclosure and global-bound proof obligations remain open.

[Independent report](research/routing/INDEPENDENT_REPORT.v1.md) · [Reviewed figures and source tables](research/routing/figures/)

![Reviewed mission outcomes](research/routing/figures/fig01_resolution.png)

### Verified October 29 request-window update

The [opt-in request-window/check-first repair](experimental/window-routing/README.md) limits expensive radiation geometry work to relevant source activity within the request window while retaining full checking and cache-identity requirements.

A fresh replay retained the original input hashes, cold preparation, **30 s** request limit and **3,072 MiB** memory guard. All **80 executions** completed: candidate **20/20** resolved (**15 checked routes + five scoped no-route decisions**), reference **13/20**. All **56 returned witnesses** matched the historical routes. This confirms no regression in already achieved mission coverage.

Independent programs checked **18 distinct returned journeys**, **72/72 scenario-specific thermal thresholds** and the five candidate no-route missions. These checks concern the frozen mathematical inputs and do not establish physical heat-model accuracy.

Across 26 jointly checked route pairs, request medians were **6.846 s candidate versus 6.765 s reference**; this replay establishes no speed gain. In the **separate six-mission Caldor/Rim engineering panel**, resolution increased from **3/6 to 6/6** under unchanged limits. It is not pooled with the Korean panel.

[Execution records, independent verification and reproduction](research/routing/request-window-20261029/README.md). The historical kit remains unchanged; see the opt-in build instructions below.

### Routing constraint ablation

The separate [200-execution final-input study](research/routing/final-input-ablation/README.md) evaluates five policies on the final 20 missions. Eight travel-only journeys encounter predicted flames. Flame avoidance produces three checked detours and five independently corroborated model-infeasible missions. Adding peak/dose limits changes no additional outcomes on this panel; this does not establish that thermal constraints are unnecessary in other conditions.

This is a hazard-constraint ablation, not a forecast evaluation or a causal test of individual speed optimizations. The older 300-execution Uljin study uses earlier inputs and remains separate.

### Graph preparation and cache reuse

The [experimental package](experimental/routing-preparation/README.md) explores native graph preparation and authenticated reuse. [Matched records](research/routing/prepared-graph-cache/README.md) distinguish preparation time, complete-request time and initial cache-build cost. They show a preparation-stage benefit on the measured candidate, without establishing a general request-time benefit. Historical update replays are not live operational replanning, and those timings are not measurements of the subsequently namespace-refactored package.

## Forecast evidence

The default **c651** checkpoint and the new experimental study are different evaluated versions. Results must remain attached to their exact checkpoint, support policies, inputs and selection procedure.

The [new frozen study](research/next-combined/README.md) evaluates the selected `d4_wind` model on **six US fires / 273 windows**, with raw Brier **0.0049268862** and AP **0.05425462**. Its paired Brier-difference interval against persistence includes zero, and its lowest-bin calibration gap is worse than the best dilation comparator. **The frozen primary superiority criterion is false**, regardless of positive secondary descriptors.

The Korean cohort retains **33 windows: 26 scored and seven unavailable**. A supported subset does not establish a complete-cohort result. Descriptive intervals, unavailable cases and the limits of mapped-extent reference data remain explicit in the linked assessment. This study does not replace c651 or establish physical flame/heat truth.

The [earlier forecast-ablation handoff](research/forecast/FORECAST_EVIDENCE_HANDOFF.md) also remains separately versioned; general four-scale superiority was not demonstrated.

## Scientific next steps

The next priority is **physical validation of the flame-front radiation model**. First establish whether primary measurements provide compatible radiative flux, flame geometry, sensor geometry and timing. Freeze a validation protocol before comparison, separate calibration from evaluation, and retain insufficient-evidence outcomes. Existing hypothetical parameter sweeps and agreement between two models do not close this gate.

After that prerequisite passes, complete and independently verify the v2 checker for driving, waiting and destination stays, then replay sealed journeys and run the gated routing-policy studies under unchanged limits. Passing the existing empirical factor-of-three criterion would support only the declared validation scope, not vehicle tenability or operational safety.

Separate work is required on scenario support, causal forecast alignment and full-policy truth/risk evaluation. Future forecast improvements need a newly declared evaluation; the current frozen negative result remains intact. See [radiation requirements](research/flame-front-radiation/REQUIREMENTS_STATUS.json), [cross-track gates](research/next-combined/GATES.json) and [broader extensions](docs/FUTURE_EXTENSIONS.md).

## Choose what to run

| Component | Directory | Start here |
|---|---|---|
| Forecast and selected checkpoint | [`forecast/`](forecast/GITHUB_SNAPSHOT.md) | Prediction and thermal API documentation |
| Final forecast-to-routing integration | [`integration/`](integration/README.md) | Installable `wfg_latest` 1.0.0 and reviewed kit v3 |
| Logger and live map | [`hardware/`](hardware/README.md) | Firmware 0.3.0, USB export and local map |
| Offline 3D exhibition | [`demos/showcase/`](demos/showcase/README.md) | One local launcher; no map token |
| Results and ablations | [`research/`](research/README.md) | Independent rows, figures and separate forecast study |
| Experimental research tracks | [`experimental/`](experimental/) | [Current gates and evidence](research/next-combined/README.md) |
| HTTP Route-Check API | [`api/`](api/) | [Service setup and contracts](api/README.md) |
| Monte Carlo extension | [`monte-carlo-extension/`](monte-carlo-extension/EXTENSION_GUIDE.md) | Separately versioned optional study |

## 1 Install the final routing API

Use **Python 3.12**. Native macOS is the evaluated runtime; Windows is not supported by the preserved POSIX worker/controller. Linux measurements require their own host-specific interpretation.

```sh
git clone --branch Main https://github.com/Sparkxt-0318/wildfireguardian.git
cd wildfireguardian
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints-routing.txt './integration[packets]'
python tools/verify_release.py
```

The routing API uses NumPy and the standard library; packet construction uses pyproj. Fresh forecast inference additionally needs the pinned forecasting dependencies. No GPU is required for the timed route search.

## 2 Replay a recorded Korean routing case

Download and verify the exact evaluated roads, hazard packets and requests, then run one unscored replay:

```sh
python tools/fetch_routing_inputs.py
python integration/examples/run_frozen_case.py --out artifacts/uljin-replay
```

This uses already constructed hazards from the latest forecast. It does not rerun forecasting and needs no external environmental rasters. The accepted recorded Uljin journey arrives at **3,119 s**, uses **512 road legs**, and remains at its destination for **120 s**. New execution costs depend on the host and load; preserve unresolved or rejected outcomes rather than treating a raw path as success.

The **30 s allowance covers the complete routing request**, including cold preparation, search, runtime checking and publication. The script's offline independent checker has a separate cap, so total script time can exceed 30 s. Outputs include raw status, authoritative publication, cleanup and independent-check scope.

To use an already downloaded input archive:

```sh
python tools/fetch_routing_inputs.py --archive /path/to/WFG-evaluated-routing-inputs-20261015.zip
```

## 3 Run a fresh forecast-to-route chain

```sh
python -m pip install -r requirements.txt
python integration/examples/run_full_pipeline.py \
  --data-root /absolute/path/to/environment \
  --out artifacts/uljin-full-chain
```

`--data-root` must contain `events.json` and the aligned event inputs. The repository includes the selected checkpoint but not the full external environmental/training/survey datasets. Follow [forecast setup](forecast/GITHUB_SNAPSHOT.md) and [data provenance](docs/DATA_AND_RIGHTS.md); a metadata catalog cannot replace the rasters. The complete environment was reused in accepted reproductions, so publication does not establish a clean-machine data installation.

## 4 Import it in Python

```python
from wfg_latest import api

result = api.route_and_check(
    kit_root="integration/kit",
    packet_dir="data/routing/latest_inputs_try02/packets/uljin_2022/20220304T030000Z",
    graph="data/routing/graphs/uljin_2022/graph.json",
    request="data/routing/latest_inputs_try02/requests/uljin_2022/20220304T030000Z_FX1.json",
    out_dir="artifacts/python-route",  # fresh path
    arm="RDA_CAND",
)
print(result["authoritative_status"], result["arrival_s"])
print(result["independent"])
```

For the opt-in request-window kit, follow [its build and replay instructions](experimental/window-routing/README.md). Select `RDA_CAND`; the shared-checker overlay baseline is not the unchanged historical reference used in the paired study.

The other entry points are `export_forecast`, `build_packet` and `rekey_request`. See the [full-chain example](integration/examples/run_full_pipeline.py). A checked journey includes legal roads/turns/waits, scenario exposure history, destination opening and required stay. A timeout is unresolved, and a scoped refusal is not proof that every real-world escape is impossible.

## 5 Open the 3D showcase or live-map interface

Offline 3D exhibition, from the repository root:

```sh
cd demos/showcase
./Launch.command
```

It uses Node.js 20+ or Python 3, bundles assets locally, and is explicitly illustrative. It is not a live forecast or a routing-performance visualization.

For device recording and the local LIVE/replay map, follow [`hardware/README.md`](hardware/README.md). Real movement files, browser profiles and device secrets stay out of Git. Indoors, GNSS may have no fix.

## 6 Verify source and run component checks

Lightweight source and preserved-result checks, from the repository root:

```sh
python tools/verify_release.py
python tools/verify_postmerge_preservation.py
python research/routing/final-input-ablation/tools/verify_published_results.py
python research/routing/request-window-20261029/verify_evidence.py
```

These check published identities/accounting and their stated evidence scope; they do not rerun a timed campaign or establish physical validation.

For the full forecast and experimental tests, use Python 3.12 in an environment with the complete dependencies. On Linux, first install the CPU wheel with `python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu` to match CI:

```sh
python -m pip install './forecast[test,baseline]' './integration[packets]' hypothesis==6.170.13
export PYTHONPATH="forecast:experimental/scenario-members:experimental/scenario-members/src:experimental/sipp-routing/src:experimental/synthetic-truth/src:experimental/flame-front-radiation/src"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider forecast/tests tests/postmerge
python -B -m pytest -q -p no:cacheprovider \
  experimental/flame-front-radiation/tests experimental/scenario-members/tests \
  experimental/sipp-routing/tests experimental/synthetic-truth/tests
```

[Required CI](.github/workflows/verified-window-routing.yml) installs the CPU PyTorch build on Linux and fetches complete Git history for historical-source tests. A shallow checkout may need `git fetch --unshallow` before those tests. Missing optional dependencies can skip tests in a lean environment; use the complete setup above when comparing with the recorded no-skip result. External-data/native-FARSITE workflows retain their own prerequisites.

Showcase controls use Node.js:

```sh
node --test demos/showcase/tests/*.test.mjs
```

Firmware builds and device-interface tests have separate instructions in [hardware/README.md](hardware/README.md). A publication check or unscored replay is not a new 80-execution benchmark.

## Exact versions and downloads

- Forecast checkpoint: **c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843**.
- Integrated API: **wfg_latest 1.0.0**; executed routing kit: **v3**.
- [Release identities](docs/RELEASE_IDENTITY.json), [source manifest](docs/PUBLICATION_SOURCE_MANIFEST.json), [project structure](docs/PROJECT_STRUCTURE.md).
- [Final research release and complete evidence archives](https://github.com/Sparkxt-0318/wildfireguardian/releases/tag/research-final-20261015), with SHA-256 checksums. Large evidence bundles are release assets rather than duplicated Git blobs.

The previous `routing-api/`, `routing-package/` and `routing-review/` paths remain for historical compatibility. **Use `integration/` for the finalized forecast-to-routing work.** Earlier results remain attached to their original inputs. No forecast-ablation checkpoint replaces the selected final checkpoint.

## Reproducibility, attribution and intended use

External environmental rasters, upstream prepared arrays and observed-survey inputs are not all bundled. Follow [data provenance and distribution scope](docs/DATA_AND_RIGHTS.md) and each workflow's input instructions. Preserve OpenStreetMap attribution and upstream asset licenses; repository publication does not grant blanket rights over external data.

A checked route satisfies the implemented model and declared input scope. It is not a guarantee of real-world safety. Smoke, embers, convection, shielding, data freshness, accessibility and destination suitability require additional evidence for operational use. No universal speedup, general forecast superiority or field effectiveness is established by this repository.

For citation metadata, see [CITATION.cff](CITATION.cff). Keep historical release identities and recorded failures when extending the research; new checkpoints, hazard policies and performance claims require their own evidence.
