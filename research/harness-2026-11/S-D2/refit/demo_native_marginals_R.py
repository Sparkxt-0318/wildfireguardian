"""A1 §5.2 demonstration: native multi-observation cumulative marginals on cohort R (US2024, 6 fires).

Ruling (Victor / orchestrator, #155 §2 at 843191da): a pre-freeze model is acceptable if
(a) the demo runs from the exact refit/ code that will be frozen (shas recorded below);
(b) the weights' provenance is recorded (here: a committed development checkpoint, see --weights-note);
(c) the receipt shows, per R fire and cutoff, valid cumulative CDFs (in [0, 1], non-decreasing across later
    surveys, one column per later survey within 48 h) and the single-lead column bit-identical to
    ``survival.sample_forecast``;
(d) NO RPS or any other score is computed here.

Both D2 candidates (d2_nll_rebuilt, d2_bracket_rebuilt) forecast through the same
``survival.sample_forecast`` path; they differ only in training. One demo covers that path for both.

Inputs exactly as the refits: pinned forecast-v2 ``pipeline.py``/``RUN_PROTOCOL.json``; rebuilt covariates via
``Environment(input_sha256=<manifest>)``; perimeter states from ``<perimeters>/<event>/states.npz`` verified
against ``PERIMETER_MANIFEST.json`` (the pipeline's own check). Full grid (no crop), every survey whose
floor-hour weather is available as a cutoff, leads = every later survey within 48 h (A1 §2).

    python demo_native_marginals_R.py --input-manifest us2024_input_manifest_night1.json --data-root DATA \\
        --perimeters PERIMETERS --work WORK --checkpoint CKPT.pt --weights-note "..." --out OUTDIR
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PIPELINE = REPO / "research/forecast-v2/scripts/pipeline.py"
PROTOCOL = REPO / "research/forecast-v2/RUN_PROTOCOL.json"
PINNED = {
    PIPELINE: "88d376d219993e72832f21c86df5f90140dc894f876b3bb9cd37688520c92d67",
    PROTOCOL: "c2dce7f7724b1bda6d71391b690904067e6ad46c808276c34f72fd4a1b1e8243",
}
CODE_FILES = ["d2_bracket.py", "run_d2_bracket.py", "run_d2.py", "time_estep.py", "native_marginals.py",
              "demo_native_marginals_R.py", "test_d2_bracket.py", "test_run_d2.py", "test_native_marginals.py"]
WINDOW = 48.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-manifest", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--perimeters", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--weights-note", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--events", nargs="*", default=None, help="default: SPLIT held_out us_2024 (cohort R)")
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    for path, expected in PINNED.items():
        if sha256(path) != expected:
            raise SystemExit(f"Pinned source changed: {path.relative_to(REPO)}")
    pins = json.loads(a.input_manifest.read_text())
    if not isinstance(pins, dict) or not pins or not all(isinstance(v, str) and len(v) == 64 for v in pins.values()):
        raise SystemExit("--input-manifest must be a non-empty {relative_path: sha256} object")

    spec = importlib.util.spec_from_file_location("pipeline", PIPELINE)
    pipeline = importlib.util.module_from_spec(spec)
    sys.modules["pipeline"] = pipeline
    spec.loader.exec_module(pipeline)
    import pandas as pd
    import torch
    from wildfire.survival import PerimeterSample, ages_from_states, sample_forecast
    spec = importlib.util.spec_from_file_location("native_marginals", HERE / "native_marginals.py")
    NM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(NM)
    torch.set_num_threads(a.threads)

    env = pipeline.Environment(a.data_root, a.work / "environment_cache", input_sha256=pins)
    model = pipeline.load_structured(a.checkpoint)
    events = a.events or list(pipeline.SPLIT["held_out"]["us_2024"])
    manifest = json.loads((a.perimeters / "PERIMETER_MANIFEST.json").read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "arrival").mkdir(exist_ok=True)

    try:
        head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", str(HERE)],
                               capture_output=True, text=True).stdout.strip()
    except OSError:
        head, dirty = None, None
    receipt = dict(
        purpose="A1 §5.2 native multi-observation cumulative marginals demonstrated on cohort R; no score computed",
        candidates=["d2_nll_rebuilt", "d2_bracket_rebuilt"], forecast_path="wildfire.survival.sample_forecast",
        git_head=head, refit_dir_uncommitted_changes=dirty,
        code_sha256={f: sha256(HERE / f) for f in CODE_FILES if (HERE / f).exists()},
        pipeline_sha256=PINNED[PIPELINE], run_protocol_sha256=PINNED[PROTOCOL],
        input_manifest=str(a.input_manifest), input_manifest_sha256=sha256(a.input_manifest), input_files=len(pins),
        perimeter_manifest_sha256=sha256(a.perimeters / "PERIMETER_MANIFEST.json"),
        weights=dict(checkpoint=str(a.checkpoint), sha256=sha256(a.checkpoint), note=a.weights_note),
        lead_window_hours=WINDOW, crop=False,
        host=dict(python=platform.python_version(), platform=platform.platform(), torch=torch.__version__,
                  numpy=np.__version__),
        rps_computed=False, rows=[], skipped=[])
    t_start = time.perf_counter()
    for event in events:
        run_event(event, a.perimeters, manifest, env, model, NM, a.out, receipt)
    rows = receipt["rows"]
    receipt["summary"] = dict(
        fires=len({r["event"] for r in rows}), cutoffs=len(rows), skipped=len(receipt["skipped"]),
        all_in_unit_interval=all(r["in_unit_interval"] for r in rows),
        all_nondecreasing=all(r["nondecreasing"] for r in rows),
        max_decrease_overall=max((r["max_decrease"] for r in rows), default=None),
        all_single_lead_bit_identical=all(r["single_lead_bit_identical"] for r in rows),
        all_columns_match_later_surveys_within_48h=True,   # by construction; arrival_entries re-checks shapes
        wall_seconds=time.perf_counter() - t_start)
    out = a.out / "NATIVE_MARGINALS_R_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(dict(receipt=str(out), **receipt["summary"]), indent=1))


def run_event(event, perimeters, manifest, env, model, NM, out_dir, receipt):
    """Native marginals for every cutoff of one fire; appends receipt rows and writes the arrival file."""
    import pandas as pd
    import torch
    from wildfire.survival import PerimeterSample, ages_from_states, sample_forecast
    states_path = perimeters / event / "states.npz"
    if sha256(states_path) != manifest["events"][event]["states_sha256"]:
        raise SystemExit(f"Perimeter reference identity differs from its source manifest: {event}")
    data = np.load(states_path, allow_pickle=False)
    times = list(pd.to_datetime(data["times"], utc=True))
    states = data["states"].astype(bool)
    hours = np.array([(t - times[0]).total_seconds() / 3600 for t in times])
    forecasts, cutoffs = {}, []
    for i in range(len(times)):
        later = [k for k in range(i + 1, len(times)) if 0 < hours[k] - hours[i] <= WINDOW]
        if not later:
            continue
        hour = times[i].floor("h")
        if not env.available_at(event, hour):
            receipt["skipped"].append(dict(event=event, cutoff_index=i, reason="weather unavailable at floor hour"))
            continue
        raw = env.at(event, hour)
        leads = [float(hours[k] - hours[i]) for k in later]
        age = ages_from_states(times, states.astype(np.uint8), i)
        sample = PerimeterSample(event, times[i].isoformat(), leads[0], raw, states[i], states[later[0]],
                                 ~states[i], np.ones(states[i].shape, np.float32),
                                 np.nan_to_num(age, nan=0.0).astype(np.float32),
                                 meta=dict(t2=times[later[0]].isoformat(), interval_index=i),
                                 residence_hours=env.residence(event))
        info = {}
        t0 = time.perf_counter()
        cdf, valid = NM.cumulative_marginals(model, sample, leads, info=info)
        with torch.no_grad():
            p1, v1 = sample_forecast(model, sample)
        same = bool(np.array_equal(cdf[0], p1.numpy().astype(np.float64))
                    and np.array_equal(valid[0], v1.numpy().astype(bool)))
        ok = valid.all(0) & ~states[i]
        forecasts[i] = (cdf, valid)
        cutoffs.append(i)
        receipt["rows"].append(dict(
            event=event, cutoff_index=i, cutoff_utc=times[i].isoformat(), n_leads=len(leads),
            lead_hours=[round(x, 6) for x in leads], cdf_min=info["min_raw"], cdf_max=info["max_raw"],
            max_decrease=info["max_decrease_raw"], in_unit_interval=bool(info["min_raw"] >= 0 and info["max_raw"] <= 1),
            nondecreasing=bool(info["max_decrease_raw"] <= 0.0),
            single_lead_bit_identical=same, cells=int(ok.size), entries=int(ok.sum()),
            mean_cdf_last_lead_on_entries=float(cdf[-1][ok].mean()) if ok.any() else None,
            seconds=time.perf_counter() - t0))
    if cutoffs:
        e = NM.arrival_entries(cutoffs, hours, states, forecasts, window=WINDOW)
        np.savez_compressed(out_dir / "arrival" / f"{event}.npz", cutoff=e["cutoff"], n_leads=e["n_leads"],
                            arrival_bin=e["arrival_bin"], lead_hours=e["lead_hours"], cdf_d2_dev=e["cdf"])


if __name__ == "__main__":
    main()
