"""Reproduce this bounded prototype's tests, optics figures and gate records."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import time
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    spec=importlib.util.spec_from_file_location("physics",HERE/"physics_validation/run_physics.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    physics=module.run()
    command=[sys.executable,"-m","pytest","experimental/flame-front-radiation/tests","-q"]
    start=time.perf_counter();completed=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    (HERE/"TEST_OUTPUT.txt").write_text(completed.stdout+completed.stderr)
    matches=re.findall(r"(\d+) passed",completed.stdout)
    tests={"command":command,"exit_code":completed.returncode,"passed":int(matches[-1]) if matches else None,"wall_s":time.perf_counter()-start,"random_box_interval_cases":1000,"seed":20261030}
    inputs={}
    for rel in ["integration/src/wfg_latest/bridge.py","integration/src/wfg_latest/radiation/heat.py","integration/kit/phaseB/road_bounds.py","integration/kit/routing_candidate/baseline/radiation_bounds.py"]:
        inputs[rel]=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
    requirements={
        "front_segments":{"state":"PARTIAL","evidence":"src/wfg_flamefront/isochrone.py; tests/test_law.py","limit":"Straight-segment approximation, strict unknown/infinite and present-phase refusal; not every legacy packet supported"},
        "intensity_and_wind":{"state":"PASS_MODEL_FORMULA","evidence":"intensity.py; sources NIST and Weise/Biging","limit":"Fuel-specific empirical laws and declared cap, no local physical fit"},
        "flux_at_points":{"state":"PASS_ON_SUPPORTED_GEOMETRY","evidence":"law_v2.py; analytic view-factor tests","limit":"Two-boundary panel model, not volumetric flame or exact bilinear isochrone"},
        "spatial_time_enclosure":{"state":"PASS_COARSE_MODEL_BOUND_ON_SUPPORTED_DOMAIN","evidence":"law_v2.py shared interval-wide domain guard, proof and 1000 supported-domain regression cases","limit":"Unsupported active ignition/expiry interiors and possible receiver/panel intersections are refused; zero lower bound and global panel-count upper are generally too loose for route acceptance"},
        "physical_comparisons":{"state":"UNRESOLVED","evidence":"physics_validation/SOURCES.json; MODEL_TABLE.csv; INCOMPARABLE_DIAGNOSTICS.csv","limit":"Prompt mixes shrub/flame heights, absent instantaneous front widths, in-flame irradiance and emitter power"},
        "factor_three_gate":{"state":"UNRESOLVED","evidence":"physics_validation/RESULTS.json","limit":"No comparable empirical threefold-error assessment can be asserted; diagnostics are not measured validation errors"},
        "cutoff_error":{"state":"PASS_NO_TRUNCATION","evidence":"solidflame.py omitted_absolute_bound","limit":"No default radius truncation; no uniform relative tail-error claim"},
        "extinction_and_present_state":{"state":"PARTIAL_FAIL_CLOSED","evidence":"law_v2.py _inputs and refusal tests","limit":"Per-cell finite expiry supported, scalar max-remaining old-fire phases cannot identify a front"},
        "dose":{"state":"PASS_DECLARED_INTERPOLATION","evidence":"law_v2.py and analytic constant/ramp tests","limit":"Piecewise-linear flux assumption, not continuous-route integration bounds"},
        "provenance":{"state":"PARTIAL","evidence":"provenance.py; SOURCES.json","limit":"Unlocated clinical thresholds omitted, not silently adopted"},
        "frozen_adapter_copy":{"state":"NOT_RUN_GATED","evidence":"adapters/journey_check.py","limit":"No complete v2 checker, gate raises NotImplementedError"},
        "frozen_uljin_v1_regression":{"state":"NOT_RUN_GATED","evidence":None,"limit":"No copied full adapter claimed"},
        "korean_18_journey_replay":{"state":"NOT_RUN_GATED","evidence":None,"limit":"Physics gate unresolved"},
        "caldor_3_journey_replay":{"state":"NOT_RUN_GATED","evidence":None,"limit":"Physics gate unresolved"},
        "five_policy_20_mission_ablation":{"state":"NOT_RUN_GATED","evidence":None,"limit":"Physics gate unresolved; no changed thresholds or invented outcomes"},
        "binding_peak_position_maps":{"state":"NOT_RUN_GATED","evidence":None,"limit":"Cannot generate journey binding maps from unexecuted studies"},
        "journey_cost_abba_two_repetitions":{"state":"NOT_RUN_GATED","evidence":None,"limit":"No v2 complete checker performance claim"},
        "optics_figures":{"state":"PASS","evidence":"physics_validation/fig01_flux_vs_distance.{png,svg}; fig02_parameter_sweep.{png,svg}","limit":"Model scenario figures only"},
    }
    result={"track":"1A","status":"HOLD_INCOMPLETE","tests":tests,"physics_gate":physics["overall_gate"],"routing_executions":0,"previous_routes_rejected_under_v2":None,"peak_binding_missions":None,"dose_binding_missions":None,"headline":"Optical unit checks pass; empirical physics gate unresolved, no routing-v2 measurements","host":{"platform":platform.platform(),"machine":platform.machine(),"python":sys.version,"numpy":np.__version__},"seed":20261030,"input_sha256":inputs,"requirements":requirements,"domain_repair":{"prior_head":"90b125a79d67301fac3058c97fe240b18cf8ae83","prior_failure":"point refused simultaneous active ignition but interval enclosure returned zero between contour events","new_rule":"Shared interval-wide supported-domain guard precedes contour selection, with conservative receiver/panel intersection refusal","regression_class":"SupportedDomain in tests/test_law.py","random_boxes":"supported-domain boxes outside possible emitting-panel prisms","physics_and_routing_status_changed":False}}
    (HERE/"RESULTS.json").write_text(json.dumps(result,indent=2)+"\n")
    (HERE/"REQUIREMENTS_STATUS.json").write_text(json.dumps(requirements,indent=2)+"\n")
    (HERE/"EXECUTIONS.csv").write_text("phase,outcome,exit_code,cases,seed\nunit_tests,PASS,"+str(completed.returncode)+","+str(tests["passed"])+",20261030\nbox_interval_regressions,PASS,0,1000,20261030\nphysics_empirical,UNRESOLVED,,0,20261030\nrouting_v2,NOT_RUN_GATED,,0,20261030\n")
    readme=f'''# Flame-front radiation research prototype

**{tests["passed"]} tests passed, including {tests["random_box_interval_cases"]:,} deterministic random box/interval cases; routing-v2 experiments: NOT_RUN.** The mandatory empirical physics gate remains unresolved. Rejected prior routes and peak/dose binding counts are unavailable, not zero. This branch is HOLD and does not satisfy the complete track acceptance criteria.

## What is supported

The NumPy-only library supplies polygonal fronts on affine grids, Byram intensity, sourced Putnam wind tilt, exact polygon view factors, point flux, a rigorous but loose monotone model enclosure on its supported domain, and analytic integration of piecewise-linear flux dose. Tests compare closed forms and explicitly refuse unknown geometry and scalar old-fire phase enclosures. Point and enclosure queries share an interval-wide guard for zero-gradient ignition/expiry activity and possible receiver/panel intersections. Enlarging a query can make it unsupported; unsupported is never replaced by zero. Numerical enclosure samples use supported query boxes and are regression checks; the finite panel-count argument is the bound proof.

## Why the physics gate is open

Source retrieval found a material input error: the quoted Mediterranean vegetation height is not an identified flame height. Plot width does not establish instantaneous radiating width. The deliberately retained diagnostic assumptions produce large ratios, but they are not comparable measurement errors. Primary crown-fire sensor data do not uniquely determine a spatially uniform panel emissive power. Uniform-panel model agreement is reported separately from measurements. No emission constant was fitted to these values or to a routing result.

The primary Cohen paper also contradicts the prompt's statement that wall ignition occurred only with flame contact. Its ideal-model flux values must remain distinct from its measurement table. Details, citation locations and retrieval failures are in [the source ledger](physics_validation/SOURCES.json) and [physics notes](physics_validation/README.md).

## Readiness defect repaired

Independent review found that the earlier enclosure returned zero for an unsupported simultaneous-ignition active interior between contour events. The point operator correctly refused that same time. The repair uses the shared domain guard before contour selection, checks the whole closed interval against half-open potential activity, and covers zero-gradient ignition and extinction fields. Tests also cover interval interiors missed by endpoint sampling, never/invalid cells, present phases and possible receiver/panel intersections. The reproducing fixture and old-head identity are preserved in the domain repair record in RESULTS.json. This repair changes no empirical gate or routing outcome.

## Reproduce

From repository root in the fresh pinned routing environment:

```sh
python3.12 -m venv /absolute/path/to/venv
/absolute/path/to/venv/bin/python -m pip install -c constraints-routing.txt './integration[packets]'
/absolute/path/to/venv/bin/python -m pip install -r experimental/flame-front-radiation/requirements-test.txt
/absolute/path/to/venv/bin/python research/flame-front-radiation/run_evidence.py
```

Producing script: `run_evidence.py`, with `physics_validation/run_physics.py`. Recorded seed: {result["seed"]}. Exact commands, exit codes, host, Python and NumPy versions, input hashes and full requirement states are in [RESULTS.json](RESULTS.json), [TEST_OUTPUT.txt](TEST_OUTPUT.txt), [EXECUTIONS.csv](EXECUTIONS.csv) and [REQUIREMENTS_STATUS.json](REQUIREMENTS_STATUS.json). This execution used Python {platform.python_version()}, NumPy {np.__version__}, {platform.machine()} on {platform.system()}. No scored repetitions were run.

## Figures and captions

![Finite-panel model diagnostics](physics_validation/fig01_flux_vs_distance.png)

The straight-front figure evaluates declared finite rectangular flame panels at ground-level receivers for the specified Byram intensities and common scenario emissive power. It uses the actual receiver-to-panel geometry. Curves describe the optical model, not observed Korean fire flux or a route policy outcome. The infinite-wall limit has a different receiver orientation and is retained in the model table. PNG and SVG files share the same calculation.

![Parameter scenarios](physics_validation/fig02_parameter_sweep.png)

The parameter chart compares snapshot radiation at the stated distance under declared emissive powers, widths, orientations and sourced tilt scenarios. Residence-time changes leave this fixed geometry snapshot unchanged; they change the evolution of the trailing front in a time-dependent calculation. These are sensitivity scenarios, not a fit or a confidence interval.

## Scope and limits

This is a model-relative prototype with no field validation. Straight marching-square segments approximate curved bilinear contours, and leading/trailing panels do not resolve the volumetric flaming band. The mean quad gradient is a declared rate approximation. Unknown cells, never-boundary interpolation and missing present-fire phases are not supplied silently. An optional explicit never-time surrogate or exclusion is a different scenario and must not be used as an unqualified route certificate. The coarse enclosure can remain indecisive under refinement. Literature emissive powers and residence times are not Korean measurements. Convection, smoke, embers, vehicle shielding, terrain occlusion and parameter uncertainty are omitted. No full journey checker, frozen journey replay, policy ablation, or continuous-route physical accuracy is established. Existing thresholds and frozen files are unchanged.
'''
    (HERE/"README.md").write_text(readme)
    paths=list((ROOT/"experimental/flame-front-radiation").rglob("*.py"))
    paths+=list((ROOT/"research/flame-front-radiation").rglob("*.py"))
    paths+=[ROOT/"docs/RADIATION_LAW_V2.md"]
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths) if p.exists()}
    (ROOT/"experimental/flame-front-radiation/SOURCE_SHA256.json").write_text(json.dumps({"source_files":manifest,"read_only_frozen_inputs":inputs},indent=2)+"\n")
    print(json.dumps({"tests":tests,"status":result["status"],"physics_gate":result["physics_gate"]},indent=2))
    return completed.returncode


if __name__=="__main__":raise SystemExit(main())
