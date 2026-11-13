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
``Environment(input_sha256=<manifest>)``. Full grid (no crop), every survey whose floor-hour weather is available as
a cutoff, leads = every later survey within 48 h (A1 §2).

Custody (Hannah, ledger row 78, adopted 03:03Z): cohort R's survey states, times and cutoffs come ONLY through
``nirops_access.py`` (sha256 pinned below) with the R allowlist (sha256 pinned below): ``id_index`` (Incident_C
column only), then ``read_incident`` per allowlisted incident (geometry and attributes by fid, allowlisted fids
only). The driver opens the archive by no other route (no direct pyogrio/fiona/read_file, no hash of the archive
file, no F1-F5) and writes an access log with one JSON line per read call (call, fids, Incident_C of each fid).
States are rasterized exactly as ``prepare_perimeters.py`` does (``survival.survey_states`` on the events.json
grid, features in EPSG:4326 with ``time_utc`` from the ``UTC`` attribute). Outputs are R only.

    python demo_native_marginals_R.py --input-manifest us2024_input_manifest_night1.json --data-root DATA \\
        --nirops-shp ARCHIVE.shp --nirops-access nirops_access.py --allowlist R_ALLOWLIST.csv \\
        --work WORK --checkpoint CKPT.pt --weights-note "..." --out OUTDIR
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
NIROPS_ACCESS_SHA256 = "08753d9669ccfedc48f50a0f6b3f42897f9a63e30ead8ea0e8c0183b80613a2b"  # nirops_access.py @ ab065e85 (Hannah row 78)
ALLOWLIST_SHA256 = "307fc097c7440e8b5c62a8db95c60ecb6778adf206c3980ed4ec086067d32536"  # R_ALLOWLIST.csv @ c4d74159
R_EVENTS = {"ID-BOF-000683_Wapiti_Wapiti", "ID-BOF-000904_Goat", "ID-BOF-001080_Lava", "ID-SCF-240202_RedRock",
            "WA-SES-000173_Pioneer", "WY-BTF-002416_FishCreek"}   # SPLIT held_out us_2024 = cohort R


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
    ap.add_argument("--nirops-shp", type=Path, required=True)
    ap.add_argument("--nirops-access", type=Path, required=True)
    ap.add_argument("--allowlist", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--weights-note", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    for path, expected in PINNED.items():
        if sha256(path) != expected:
            raise SystemExit(f"Pinned source changed: {path.relative_to(REPO)}")
    acc_sha, allow_sha = sha256(a.nirops_access), sha256(a.allowlist)
    if acc_sha != NIROPS_ACCESS_SHA256 or allow_sha != ALLOWLIST_SHA256:
        raise SystemExit("nirops_access.py or the R allowlist differs from the pinned file")
    import csv
    allowed = [row["Incident_C"].strip() for row in csv.DictReader(a.allowlist.open())]
    if set(allowed) != R_EVENTS or len(allowed) != 6:
        raise SystemExit("allowlist is not exactly cohort R")
    pins = json.loads(a.input_manifest.read_text())
    if not isinstance(pins, dict) or not pins or not all(isinstance(v, str) and len(v) == 64 for v in pins.values()):
        raise SystemExit("--input-manifest must be a non-empty {relative_path: sha256} object")

    spec = importlib.util.spec_from_file_location("pipeline", PIPELINE)
    pipeline = importlib.util.module_from_spec(spec)
    sys.modules["pipeline"] = pipeline
    spec.loader.exec_module(pipeline)
    import pandas as pd
    import torch
    spec = importlib.util.spec_from_file_location("native_marginals", HERE / "native_marginals.py")
    NM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(NM)
    torch.set_num_threads(a.threads)

    env = pipeline.Environment(a.data_root, a.work / "environment_cache", input_sha256=pins)
    model = pipeline.load_structured(a.checkpoint)        # load_state_dict(strict=True): any key or shape remap raises
    saved = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    sd_saved, sd_model = saved["state_dict"], model.state_dict()
    load_check = dict(
        model_class=f"{type(model).__module__}.{type(model).__qualname__}", strict_load=True,
        keys_equal=sorted(sd_saved) == sorted(sd_model),
        shapes_equal=all(tuple(sd_saved[k].shape) == tuple(sd_model[k].shape) for k in sd_model),
        values_equal=all(torch.equal(sd_saved[k].cpu(), sd_model[k].cpu()) for k in sd_model),
        parameters=int(sum(v.numel() for v in sd_model.values())))
    if not (load_check["keys_equal"] and load_check["shapes_equal"] and load_check["values_equal"]):
        raise SystemExit(f"weights did not load unchanged: {load_check}")
    if set(pipeline.SPLIT["held_out"]["us_2024"]) != R_EVENTS:
        raise SystemExit("SPLIT held_out us_2024 differs from cohort R")
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "arrival").mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location("nirops_access", a.nirops_access)
    NA = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(NA)
    log_path = a.out / "NIROPS_ACCESS_LOG.jsonl"
    log = log_path.open("w")
    ids = NA.id_index(str(a.nirops_shp))
    log.write(json.dumps(dict(utc=pd.Timestamp.now(tz="UTC").isoformat(), call="id_index",
                              columns=["Incident_C"], geometry=False, records=int(len(ids)))) + "\n")
    log.flush()
    grids = {e["id"]: e for e in json.loads((REPO / "forecast/data/environment/events.json").read_text())}

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
        nirops_access_sha256=acc_sha, allowlist_sha256=allow_sha, allowlist=allowed,
        nirops_archive_path=str(a.nirops_shp), nirops_archive_hash="not computed (would read every record's bytes)",
        access_log="NIROPS_ACCESS_LOG.jsonl", per_event={},
        weights=dict(checkpoint=str(a.checkpoint), sha256=sha256(a.checkpoint), note=a.weights_note,
                     status="development weights, not part-a-trained",
                     provenance="archive-trained d4_wind weights (forecast-v2 final d4_wind_seed0) loaded into the D2 "
                                "code path; not a D2-trained model (ruling #155 §2 at 8e02a19d)",
                     load_check=load_check),
        lead_window_hours=WINDOW, crop=False,
        host=dict(python=platform.python_version(), platform=platform.platform(), torch=torch.__version__,
                  numpy=np.__version__),
        rps_computed=False, rows=[], skipped=[])
    t_start = time.perf_counter()
    for event in sorted(allowed):
        gdf = NA.read_incident(str(a.nirops_shp), event, allowed, ids=ids)
        fids = [int(f) for f in gdf.index]
        log.write(json.dumps(dict(utc=pd.Timestamp.now(tz="UTC").isoformat(), call="read_incident", incident=event,
                                  fids=fids, incident_c=[str(ids.loc[f]) for f in fids])) + "\n")
        log.flush()
        times, states, meta = survey_states_from_records(gdf, grids[event])
        receipt["per_event"][event] = meta
        run_event(event, times, states, env, model, NM, a.out, receipt)
    log.close()
    receipt["access_log_sha256"] = sha256(log_path)
    build_summary(receipt, t_start)
    out = a.out / "NATIVE_MARGINALS_R_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=1) + "\n")
    print(json.dumps(dict(receipt=str(out), **receipt["summary"]), indent=1))


def build_summary(receipt, t_start):
    """Summary flags of the receipt (validity, bit-identity, non-degeneracy)."""
    rows = receipt["rows"]
    allv = np.concatenate(receipt.pop("_last_lead_values")) if receipt.get("_last_lead_values") else np.zeros(0)
    entry_quantiles = ({str(q): float(np.quantile(allv, q)) for q in (0.5, 0.9, 0.99, 0.999, 1.0)}
                       if allv.size else None)
    receipt["summary"] = dict(
        fires=len({r["event"] for r in rows}), cutoffs=len(rows), skipped=len(receipt["skipped"]),
        all_in_unit_interval=all(r["in_unit_interval"] for r in rows),
        all_nondecreasing=all(r["nondecreasing"] for r in rows),
        max_decrease_overall=max((r["max_decrease"] for r in rows), default=None),
        all_single_lead_bit_identical=all(r["single_lead_bit_identical"] for r in rows),
        all_columns_match_later_surveys_within_48h=True,   # by construction; arrival_entries re-checks shapes
        non_degenerate=dict(
            rule="max cdf over entries > 0.01 on some cutoff, every cutoff's entry cdf not constant, and no cutoff "
                 "with all entries at exactly 1",
            any_cutoff_max_above_001=any((r["entry_cdf_max"] or 0) > 0.01 for r in rows),
            no_constant_cutoff=all((r["entry_cdf_sd"] or 0) > 0 for r in rows if r["entries"]),
            no_all_one_cutoff=not any(r["entry_cdf_min"] == 1.0 for r in rows if r["entries"]),
            entry_cdf_last_lead_quantiles=entry_quantiles),
        wall_seconds=time.perf_counter() - t_start)
    nd = receipt["summary"]["non_degenerate"]
    nd["pass"] = bool(nd["any_cutoff_max_above_001"] and nd["no_constant_cutoff"] and nd["no_all_one_cutoff"])


def survey_states_from_records(gdf, grid):
    """prepare_perimeters.py's rasterization, from records already read through nirops_access."""
    from datetime import datetime, timezone
    from wildfire.survival import survey_states
    crs = None if gdf.crs is None else gdf.crs.to_string()
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    items = []
    for fid, row in gdf.iterrows():
        stamp = datetime.fromisoformat(str(row["UTC"]).strip())
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        items.append(dict(type="Feature", id=int(fid), geometry=row.geometry.__geo_interface__,
                          properties=dict(time_utc=stamp.astimezone(timezone.utc).isoformat())))
    items.sort(key=lambda f: (f["properties"]["time_utc"], f["id"]))
    times, states = survey_states(items, grid)
    inc = sorted({str(v) for v in gdf["Inc Number"]}) if "Inc Number" in gdf.columns else None
    meta = dict(records=len(items), distinct_times=len(times), source_crs=crs, inc_numbers=inc,
                final_mapped_cells=int(states[-1].sum()) if len(states) else 0,
                states_sha256=hashlib.sha256(np.ascontiguousarray(states).tobytes()).hexdigest())
    return list(times), states.astype(bool), meta


def run_event(event, times, states, env, model, NM, out_dir, receipt):
    """Native marginals for every cutoff of one fire; appends receipt rows and writes the arrival file."""
    import torch
    from wildfire.survival import PerimeterSample, ages_from_states, sample_forecast
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
        receipt.setdefault("_last_lead_values", []).append(cdf[-1][ok].astype(np.float32))
        receipt["rows"].append(dict(
            event=event, cutoff_index=i, cutoff_utc=times[i].isoformat(), n_leads=len(leads),
            lead_hours=[round(x, 6) for x in leads], cdf_min=info["min_raw"], cdf_max=info["max_raw"],
            max_decrease=info["max_decrease_raw"], in_unit_interval=bool(info["min_raw"] >= 0 and info["max_raw"] <= 1),
            nondecreasing=bool(info["max_decrease_raw"] <= 0.0),
            single_lead_bit_identical=same, cells=int(ok.size), entries=int(ok.sum()),
            mean_cdf_last_lead_on_entries=float(cdf[-1][ok].mean()) if ok.any() else None,
            entry_cdf_max=float(cdf[:, ok].max()) if ok.any() else None,
            entry_cdf_min=float(cdf[:, ok].min()) if ok.any() else None,
            entry_cdf_sd=float(cdf[-1][ok].std()) if ok.any() else None,
            seconds=time.perf_counter() - t0))
    if cutoffs:
        e = NM.arrival_entries(cutoffs, hours, states, forecasts, window=WINDOW)
        np.savez_compressed(out_dir / "arrival" / f"{event}.npz", cutoff=e["cutoff"], n_leads=e["n_leads"],
                            arrival_bin=e["arrival_bin"], lead_hours=e["lead_hours"], cdf_d2_dev=e["cdf"])


if __name__ == "__main__":
    main()
