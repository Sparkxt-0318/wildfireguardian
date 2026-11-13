"""Rebuilt-input run (REBUILT_INPUT_PLAN.md, committed before any run): frozen d4_wind_seed0 on Daniel's rebuilt US2024
covariates, on exactly the 273 stored heldout cases (6a3265a0). DESCRIPTIVE ROW ONLY; no pass/fail.

Same unmodified calls as the control's d4_wind stage (unmodified_rollout_control.py):
  pipeline.Environment(data_root, work, input_sha256=PINS)  (PINS = Daniel's us2024_input_manifest_night1.json, 286f4c47)
  pipeline.perimeter_samples(event, perimeters, env, crop=False)  (the control's rebuilt perimeters)
  survival.sample_forecast(d4_wind_seed0, sample, use_burnout=True, use_spotting=True)
Cells are exactly the stored (row, col, y) per case_id; nothing is re-derived. Per case, written to --cells-dir as
<case_id>.npz: row, col, y, p_rebuilt, p_original (stored p_d4_wind_seed0), dist_m, valid. Identity fields are compared
with the stored receipt (environmental_snapshot_sha256 is expected to differ; residence_sha256 reported either way).

    python rebuilt_input_run.py --data-root WS/data/environment --pins PINS.json --perimeters PERIM \
        --heldout HELDOUT --work W --cells-dir CELLS --out RESULTS_rebuilt_input.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import unmodified_rollout_control as U  # noqa: E402  (EVENTS, D4_WIND, D4_WIND_SHA, sha, load_module)

import numpy as np  # noqa: E402
import torch  # noqa: E402

CELL_M = 375.0
IDENTITY_EQUAL = ("initial_sha256", "endpoint_sha256", "reference_mask_sha256", "initial_age_sha256", "rectangle")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("--data-root", "--pins", "--perimeters", "--heldout", "--work", "--cells-dir", "--out"):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    from scipy.ndimage import distance_transform_edt
    P = U.load_module("full_cohort_pipeline", U.SCRIPTS / "pipeline.py")
    S = U.load_module("score_cohorts_ctl", U.SCRIPTS / "score_cohorts.py")
    from wildfire.survival import sample_forecast
    if U.sha(U.D4_WIND) != U.D4_WIND_SHA:
        raise SystemExit("d4_wind checkpoint changed")
    model = P.load_structured(U.D4_WIND)
    pins = json.loads(a.pins.read_text())
    env = P.Environment(a.data_root.resolve(), a.work / "env", input_sha256=pins)
    a.cells_dir.mkdir(parents=True, exist_ok=True)
    stored_ids = {p.stem for p in (a.heldout / "cases").glob("*.json")}
    seen = set()
    with a.out.open("w") as out:
        out.write(json.dumps(dict(
            header=True, plan="REBUILT_INPUT_PLAN.md", label="descriptive row only; archive-trained model on rebuilt inputs",
            script_sha256=U.sha(__file__), control_sha256=U.sha(HERE / "unmodified_rollout_control.py"),
            pipeline_sha256=U.sha(U.SCRIPTS / "pipeline.py"), score_cohorts_sha256=U.sha(U.SCRIPTS / "score_cohorts.py"),
            checkpoint_sha256=U.D4_WIND_SHA, pins_sha256=U.sha(a.pins), n_pins=len(pins),
            perimeter_manifest_sha256=U.sha(a.perimeters / "PERIMETER_MANIFEST.json"),
            host=dict(python=platform.python_version(), torch=torch.__version__, numpy=np.__version__, threads=a.threads))) + "\n")
        for event in U.EVENTS:
            for sample in P.perimeter_samples(event, a.perimeters, env, crop=False):
                case = dict(event=event, cutoff=sample.t1, endpoint=sample.meta["t2"], hours=sample.hours)
                cid = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()[:24]
                if cid not in stored_ids:
                    continue  # not one of the 273 stored cases (e.g. hours > 48 is excluded by perimeter_samples)
                seen.add(cid)
                rec = json.loads((a.heldout / "cases" / f"{cid}.json").read_text())
                ident = S.source_identity(sample)
                row = dict(case_id=cid, case=case,
                           identity_mismatch=[f for f in IDENTITY_EQUAL if rec.get(f) != ident.get(f)],
                           environmental_snapshot_differs=rec.get("environmental_snapshot_sha256") != ident.get("environmental_snapshot_sha256"),
                           residence_equal=rec.get("residence_sha256") == ident.get("residence_sha256"))
                with np.load(a.heldout / "cases" / f"{cid}.npz", allow_pickle=False) as z:
                    r, c, y, p0 = z["row"], z["col"], z["y"], z["p_d4_wind_seed0"]
                t0 = time.perf_counter()
                with torch.no_grad():
                    q, v = sample_forecast(model, sample, use_burnout=True, use_spotting=True)
                q, v = q.numpy(), v.numpy()
                dist = (distance_transform_edt(~sample.initial) * CELL_M if sample.initial.any()
                        else np.full(sample.initial.shape, np.inf))
                valid = v[r, c].astype(bool)
                np.savez_compressed(a.cells_dir / f"{cid}.npz", row=r, col=c, y=y, p_rebuilt=q[r, c].astype(np.float32),
                                    p_original=p0.astype(np.float32), dist_m=dist[r, c].astype(np.float32), valid=valid)
                row.update(cells=int(len(y)), positives=int(y.sum()), unsupported_cells=int((~valid).sum()),
                           entries_match=bool(np.array_equal(y, sample.endpoint[r, c].astype(np.int8))),
                           flagged=bool(row["identity_mismatch"]) or bool((~valid).any()),
                           seconds=time.perf_counter() - t0)
                out.write(json.dumps(row) + "\n"); out.flush()
        missing = sorted(stored_ids - seen)
        out.write(json.dumps(dict(footer=True, stored_cases=len(stored_ids), run_cases=len(seen),
                                  stored_cases_not_rebuilt=missing)) + "\n")
    print(json.dumps(dict(stored=len(stored_ids), run=len(seen), missing=len(missing))))


if __name__ == "__main__":
    main()
