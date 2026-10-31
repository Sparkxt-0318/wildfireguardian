"""Targeted simulator-reader boundary fixtures, not a native simulator run."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-c", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.track_c.resolve()
    sys.path.insert(0, str(root / "experimental/synthetic-truth/src"))
    import numpy as np
    from wfg_synthetic_truth.adapters import external_simulator, utc_seconds

    observations = []
    with tempfile.TemporaryDirectory(prefix="reader-audit-") as temporary:
        folder = Path(temporary)
        affine = np.array([10., 0., 0., 0., -10., 20.])
        for name, shift in (("reference", 0), ("shifted_reference", 1000)):
            t = affine.copy(); t[2] += shift
            np.savez_compressed(folder / (name+".npz"), burned_area=np.zeros((1, 1, 2, 2)),
                                affine_transform=t, epsg=np.array(5070), time_utc=np.array([100]), event_id=np.array("fixture"))
        metadata = {"model_family": "FARSITE", "method": "farsite_deterministic", "arrival_units": "minutes",
                    "grid_alignment": "caller_verified_no_resampling_in_importer", "arrival_origin_time_utc": 100,
                    "no_burn_value": -9999., "exact_duration_minutes": 10}
        cases = [
            ("arrival_beyond_run_end", np.array([[0., 1.], [2., 1000.]]), metadata, True),
            ("finite_run_nonarrival", np.array([[0., 1.], [2., -9999.]]), metadata, True),
            ("explicit_non_simulator_family", np.array([[.1, .2], [.3, .4]]), dict(metadata, model_family="LearnedProbability", method="probability_predictor", output_interpretation="cell_burn_probability"), True),
            ("borrowed_reference_grid", np.array([[0., 1.], [2., 3.]]), metadata, False),
        ]
        for name, arrivals, meta, has_grid in cases:
            path = folder / (name+".npz")
            payload = {"arrival_minutes": arrivals, "valid": np.ones((2, 2), bool), "metadata_json": np.array(json.dumps(meta))}
            if has_grid:
                payload.update(affine_transform=affine, epsg=np.array(5070))
            np.savez_compressed(path, **payload)
            try:
                truth = external_simulator(path, reference_path=folder/"reference.npz", cutoff_utc=100,
                                           source_id="fixture:"+name, expected_event="fixture")
                point = truth.exact_ignition()
                observed = {"state": "RETURNED", "point_status": point["status"], "known": truth.known.tolist(),
                            "never": truth.never.tolist(), "lower_s": [["inf" if np.isposinf(x) else float(x) for x in row] for row in truth.lower_s],
                            "point_keys": list(point), "declared_duration_minutes": meta["exact_duration_minutes"],
                            "interpretation": truth.interpretation}
                qualified = point["status"] == "UNSCORABLE"
                if name == "finite_run_nonarrival":
                    qualified |= any(k in point for k in ("valid_until_s", "horizon_s", "maximum_query_time_s"))
                    passed = qualified
                elif name == "borrowed_reference_grid":
                    shifted = external_simulator(path, reference_path=folder/"shifted_reference.npz", cutoff_utc=100,
                                                 source_id="fixture:"+name+":shifted", expected_event="fixture")
                    observed["same_output_accepted_with_shifted_reference"] = True
                    observed["original_affine"] = list(truth.grid.affine)
                    observed["shifted_affine"] = list(shifted.grid.affine)
                    passed = qualified or point.get("alignment_state") == "CALLER_ASSERTED_UNVERIFIED"
                else:
                    passed = qualified
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                observed = {"state": "RAISED", "type": type(exc).__name__, "message": str(exc)}
                passed = True
            observations.append({"id": name, "fixture": {"arrival_minutes": arrivals.tolist(), "metadata": meta,
                                  "output_has_grid": has_grid, "reference_shape": [2, 2], "affine": affine.tolist(), "epsg": 5070,
                                  "cutoff_utc": 100}, "input_npz_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                 "pass_defensive_admission": bool(passed), "observed": observed})
        try:
            value = utc_seconds("1970-01-01T00:03:20+00:00:01.5")
            clock = {"state": "RETURNED", "value": value}
            passed = False
        except ValueError as exc:
            clock = {"state": "RAISED", "message": str(exc)}
            passed = True
        observations.append({"id": "fractional_utc_offset", "fixture": "1970-01-01T00:03:20+00:00:01.5",
                             "pass_defensive_admission": passed, "observed": clock})
    path = root / "experimental/synthetic-truth/src/wfg_synthetic_truth/adapters.py"
    result = {"scope": "synthetic reader-admission fixtures only; no assertion that the actual stored Wapiti output has these malformed fields",
              "track_head": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
              "host": platform.platform(), "python": sys.version, "numpy": np.__version__,
              "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()},
              "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "observations": observations, "checks": len(observations),
              "passed": sum(row["pass_defensive_admission"] for row in observations)}
    result["status"] = "PASS_TARGETED_READERS" if result["passed"] == result["checks"] else "FAIL_OR_UNQUALIFIED_TARGETED_READERS"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": result["status"], "checks": result["checks"], "passed": result["passed"],
                      "findings": [{"id": r["id"], "observed": r["observed"]} for r in observations if not r["pass_defensive_admission"]]}, indent=2))
    return 0 if result["passed"] == result["checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
