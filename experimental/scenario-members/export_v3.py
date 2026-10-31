"""Latest-forecast export (wfg.latest-forecast-export/2): run the latest supplied forecast (checkpoint c651f672...) through
its documented public API for one event and one whole-hour cutoff and write FORECAST_<tag>.npz + FORECAST_RECORD_<tag>.json.

Supersedes the unadmitted 14 October exporter (export/1). Changes: clock binding (requested cutoff == loaded sample time ==
Prediction time, embedded in the NPZ), strict raw-field validation before writing (contract.validate_raw), complete policy
and source/data/checkpoint identities in the record. Explicit choices (see contract.POLICY):
  * model.predict(sample, boundary='unknown', missing_burned_area='unknown'): native missingness kept; the owner's zero
    assignment for missing new-burn probabilities is applied later by the bridge with its own mask.
  * Heat timing: latest documented composed-API default use_cell_burning_duration=True, point residence 11.52 s, front speed
    341 m/h, direction 0 deg -> one scalar cell duration T (about 3970.46 s on 375 m cells). Present activity and remaining
    time come from the latest heat package (arrival age, same T). The package defines previous burning only on known
    already-burned cells; cells whose cumulative burned state is unknown (no reconstructed arrival) are reported separately.
  * Energy: fuel load 10 kg/m2 and consumed fraction 0.1 (WildfireGuardian research values), nominal FBFM40 heat content
    18.608 MJ/kg, radiative fraction 0.30, emission 5 m, receiver 0 m, transmissivity 1, uniform ignition timing.
Requires the forecast environment (PyTorch). Usage:
  python -I -B export.py --source-root SRC --data-root DATA --checkpoint CK --event KFS_xx --cutoff ISO --out DIR"""
import argparse, datetime, hashlib, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "integration" / "src" / "wfg_latest"
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def collect_trajectories(model, sample, *, horizon_hours=1, n_samples=1024,
                         trajectory_count=64, seed=0, trajectory_batch_size=32,
                         boundary="unknown", missing_burned_area="unknown"):
    """Additive v3 collector, with unchanged engine draws and explicit identity.

    Seeds are block stream seeds encoded as signed int64 bit patterns. A seed
    alone cannot regenerate a trajectory: offset, full batch size and horizon
    are also required because the existing engine draws full blocks per hour.
    Conservative coverage is recorded; unknown is never converted to unburned.
    """
    import numpy as np
    import torch
    from wildfire.rollout import simulate, _generator, validate_controls
    from wildfire.models import BayesianBurnModel
    if isinstance(horizon_hours, bool) or not isinstance(horizon_hours, int) or not 1 <= horizon_hours <= 32767:
        raise ValueError("horizon_hours must fit positive int16")
    validate_controls([float(horizon_hours)], n_samples, seed, trajectory_batch_size)
    if isinstance(trajectory_count, bool) or not isinstance(trajectory_count, int) or not 1 <= trajectory_count <= n_samples:
        raise ValueError("trajectory_count must be in 1..n_samples")
    inputs, geometry = model._prepare_prediction_inputs(sample)
    inputs, initialization = model._initialize_burned_area(inputs, geometry, missing_burned_area)
    initial = inputs["burned_area"]
    if initial.numel() != initial.shape[-2] * initial.shape[-1]:
        raise ValueError("One cutoff is required per export")
    initial_np = initial.detach().cpu().numpy().reshape(initial.shape[-2:])
    known = inputs["burned_area_valid"].detach().cpu().numpy().reshape(initial.shape[-2:]) & np.isfinite(initial_np)
    first = np.full((n_samples, *initial_np.shape), -1, dtype=np.int16)
    first[:, known & (initial_np == 1)] = 0
    first[:, ~known] = -2

    def callback(block, states, hour):
        start = block * trajectory_batch_size
        active = states.detach().cpu().numpy()[:, 0]
        block_first = first[start:start + len(active)]
        block_first[(block_first == -1) & active] = hour

    outputs = simulate(model.predictor, **inputs, hours=list(range(1, horizon_hours + 1)),
                       n_samples=n_samples, seed=seed, trajectory_batch_size=trajectory_batch_size,
                       boundary=boundary, missing_burned_area=missing_burned_area,
                       assumed_unburned_cells=initialization["assumed_unburned_cells"],
                       trajectory_callback=callback)
    valid = np.stack([o["details"].valid.detach().cpu().numpy().reshape(initial_np.shape) for o in outputs])
    first[:, ~valid[-1]] = -2
    seeds, offsets, components = [], [], []
    predictor = model.predictor
    if isinstance(predictor, BayesianBurnModel):
        supported = torch.isfinite(predictor.log_posterior_weights)
        original_indices = torch.nonzero(supported, as_tuple=False).flatten().cpu().numpy()
        weights = torch.softmax(predictor.log_posterior_weights[supported].detach().cpu().double(), dim=0)
    else:
        original_indices = np.array([0])
        weights = torch.ones(1, dtype=torch.float64)
    if len(original_indices) and int(max(original_indices)) > 32767:
        raise ValueError("Bayesian component index does not fit int16")
    for block, start in enumerate(range(0, trajectory_count, trajectory_batch_size)):
        count = min(trajectory_batch_size, trajectory_count - start)
        block_seed = _generator(seed, 0, block, 0).initial_seed()
        assignment = torch.multinomial(weights, trajectory_batch_size, replacement=True,
                                       generator=_generator(seed, 0, block, 1)).numpy()
        seeds.extend([block_seed] * count)
        offsets.extend(range(count))
        components.extend(original_indices[assignment[:count]])
    arrays = {"trajectory_first_burn_hour": first[:trajectory_count],
              "trajectory_seed": np.asarray(seeds, dtype=np.uint64).view(np.int64),
              "trajectory_component": np.asarray(components, dtype=np.int16),
              "trajectory_offset_in_block": np.asarray(offsets, dtype=np.int32),
              "trajectory_cumulative_probability": np.stack([o["burned_probability"].detach().cpu().numpy().reshape(initial_np.shape) for o in outputs]),
              "trajectory_valid_by_hour": valid}
    metadata = {"export_version": "wfg.latest-forecast-export/3", "trajectory_count": trajectory_count,
                "trajectory_simulated_count": n_samples, "trajectory_horizon_hours": horizon_hours,
                "trajectory_boundary": boundary, "trajectory_missing_policy": missing_burned_area,
                "trajectory_base_seed": seed, "trajectory_batch_size": trajectory_batch_size,
                "trajectory_seed_encoding": "uint64 block ignition-stream seed, bit-preserved in int64",
                "trajectory_identity": "base seed + cutoff index 0 + block index + offset + batch size + source/checkpoint + inputs/policies",
                "trajectory_environment": "repeated cutoff, no future labels",
                "trajectory_coverage": "conservative all-supported-component envelope; final unknown encoded -2"}
    return arrays, metadata


def main():
    ap = argparse.ArgumentParser()
    for k in ("--source-root", "--data-root", "--checkpoint", "--event", "--cutoff", "--out"):
        ap.add_argument(k, required=True)
    ap.add_argument("--export-version", choices=("2", "3"), default="3")
    ap.add_argument("--trajectory-count", type=int, default=64)
    ap.add_argument("--trajectory-samples", type=int, default=1024)
    ap.add_argument("--trajectory-horizon-hours", type=int, default=1)
    ap.add_argument("--trajectory-seed", type=int, default=0)
    ap.add_argument("--trajectory-batch-size", type=int, default=32)
    a = ap.parse_args()
    iso, epoch = C.normalize_cutoff(a.cutoff)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    npz_path = out / ("FORECAST_%s.npz" % C.tag(iso)); rec_path = out / ("FORECAST_RECORD_%s.json" % C.tag(iso))
    if npz_path.exists() or rec_path.exists():
        raise SystemExit("EXPORT_EXISTS (exports are write-once): %s" % npz_path)
    if sha(a.checkpoint) != C.CHECKPOINT_SHA256:
        raise SystemExit("CHECKPOINT_SHA_MISMATCH")
    sys.path.insert(0, a.source_root)
    import numpy as np
    import torch
    torch.set_num_threads(1)
    import wildfire
    from wildfire import load_model, load_data
    from wildfire.heat import AffineGrid, CombustionParameters, FlameResidenceTime
    P = C.POLICY
    t0 = time.perf_counter(); model = load_model(a.checkpoint, device="cpu"); t_load = time.perf_counter() - t0
    t0 = time.perf_counter()
    ds = load_data(a.data_root, events=[a.event], sequence_length=1, time_range=(iso, iso))
    if len(ds) != 1:
        raise SystemExit("EXPECTED_ONE_SAMPLE:%d" % len(ds))
    sample = ds[0]; t_data = time.perf_counter() - t0
    npy = lambda x: np.asarray(x.detach().cpu().numpy() if hasattr(x, "detach") else x)
    transform = npy(sample["affine_transform"]).astype(np.float64).ravel()[:6]
    epsg = int(npy(sample["epsg"]).ravel()[0])
    t0 = time.perf_counter()
    pred = model.predict(sample, boundary=P["boundary"], missing_burned_area=P["missing_burned_area"])
    t_prob = time.perf_counter() - t0
    clock = C.bind_clock(iso, npy(sample["time_utc"]), npy(sample.get("time_valid")) if sample.get("time_valid") is not None else None,
                         None if pred.time_utc is None else npy(pred.time_utc), npy(pred.dt_hours))
    residence = FlameResidenceTime(P["point_residence_s"], provenance={"source": "latest documented reference point residence 11.52 s (SAV 2000 ft^-1), documents/heat_parameter_models.md", "scope": "reference scenario, not Korean fuel evidence"})
    comb = CombustionParameters.from_flame_residence(residence, fuel_load_kg_m2=P["fuel_load_kg_m2"], heat_of_combustion_j_kg=P["heat_of_combustion_j_kg"],
        consumed_fraction=P["consumed_fraction"], provenance={"fuel_load_and_consumed_fraction": "WildfireGuardian research values (labelled)", "heat_of_combustion": "nominal FBFM40 18.608 MJ/kg"})
    t0 = time.perf_counter()
    hm = model.heat_model(grid=AffineGrid(tuple(transform.tolist())), epsg=epsg, combustion=comb, residence_time=residence,
                          radiative_fraction=P["radiative_fraction"], emission_height_m=P["emission_height_m"], receiver_height_m=P["receiver_height_m"],
                          atmospheric_transmissivity=P["atmospheric_transmissivity"], ignition_time_model=P["ignition_time_model"], interval_s=P["interval_s"],
                          use_cell_burning_duration=P["use_cell_burning_duration"], spread_rate_m_s=P["spread_rate_m_s"], spread_direction_deg=P["spread_direction_deg"])
    feats, fvalid = model._sample_environment(sample)   # the same named-channel selection model.predict applies (copy)
    heat_sample = dict(sample); heat_sample["features"] = feats; heat_sample["feature_valid"] = fvalid; heat_sample["channel_names"] = list(model.channel_names)
    heat = hm.predict_sample_details(heat_sample); t_heat = time.perf_counter() - t0
    cell_T = np.asarray(hm.combustion.burning_duration_s, dtype=float)
    if cell_T.size != 1 and not np.all(cell_T == cell_T.ravel()[0]):
        raise SystemExit("NON_SCALAR_CELL_DURATION (the declared scalar law needs one T)")
    T = float(cell_T.ravel()[0])
    if int(heat.metadata.get("cutoff_unix_s", epoch)) != epoch:
        raise SystemExit("CLOCK_HEAT_CUTOFF_MISMATCH")

    def two_d(x, name):
        v = np.squeeze(npy(x))
        if v.ndim != 2:
            raise SystemExit("EXPECTED_2D:%s:%s" % (name, v.shape))
        return v
    arrays = {"new_burn_probability": two_d(pred.probability, "probability").astype(np.float64),
              "probability_valid": two_d(pred.valid, "valid"), "rate_per_h": two_d(pred.rate, "rate").astype(np.float64),
              "rate_valid": two_d(pred.rate_valid, "rate_valid"),
              "source_burned_area": two_d(sample["burned_area"], "burned_area").astype(np.float64),
              "source_burned_area_valid": two_d(sample["burned_area_valid"], "burned_area_valid"),
              "affine_transform": transform,
              "heat__initial_active_burning_probability": two_d(heat.initial_active_burning_probability, "activity").astype(np.float64),
              "heat__initial_remaining_burning_duration_s": two_d(heat.initial_remaining_burning_duration_s, "remaining").astype(np.float64),
              "heat__initial_burning_valid": two_d(heat.initial_burning_valid, "initial_valid")}
    summary = C.validate_raw(arrays, T)          # fail closed before anything is written
    arrays = C.embed_clock(arrays, clock, a.event, T, epsg)
    trajectory_metadata = {}
    if a.export_version == "3":
        trajectory_arrays, trajectory_metadata = collect_trajectories(
            model, sample, horizon_hours=a.trajectory_horizon_hours,
            n_samples=a.trajectory_samples, trajectory_count=a.trajectory_count,
            seed=a.trajectory_seed, trajectory_batch_size=a.trajectory_batch_size,
            boundary=P["boundary"], missing_burned_area=P["missing_burned_area"])
        arrays.update(trajectory_arrays)
    tmp = out / (npz_path.name + ".partial.npz")
    np.savez_compressed(tmp, **arrays); os.replace(tmp, npz_path)
    data = Path(a.data_root)
    ident = {f: sha(data / f) for f in ("events.json",) if (data / f).is_file()}
    for f in ("grid.json", "arrival_time_hours.tif", "kriging_std_hours.tif"):
        p = data / "regions" / a.event / f
        if p.is_file():
            ident["regions/%s/%s" % (a.event, f)] = sha(p)
    rec = {"schema": "wfg.latest-forecast-export.record/2", "contract": C.CONTRACT_VERSION, "event": a.event, "cutoff_utc": iso, "clock": clock,
           "epsg": epsg, "checkpoint_sha256": C.CHECKPOINT_SHA256, "checkpoint_path": a.checkpoint, "source_root": a.source_root,
           "wildfire_module": wildfire.__file__, "wildfire_heat_sha256": sha(Path(wildfire.__file__).parent / "heat.py"),
           "wildfire_api_sha256": sha(Path(wildfire.__file__).parent / "api.py"), "data_root": a.data_root, "data_identity_sha256": ident,
           "exporter_sha256": sha(__file__), "contract_sha256": sha(HERE / "contract.py"), "npz": npz_path.name, "npz_sha256": sha(npz_path),
           "policy": C.POLICY, "cell_burning_duration_s": {"value": T, "scalar": True, "provenance": hm.cell_burning_duration.provenance_dict() if hm.cell_burning_duration is not None else None},
           "heat_release_rate_density_w_m2": float(np.asarray(hm.combustion.heat_release_rate_density_w_m2).ravel()[0]),
           "channel_names": list(model.channel_names), "raw_summary": summary,
           "timing_s": {"model_load": t_load, "data_load": t_data, "probability": t_prob, "heat": t_heat},
           "versions": {"torch": torch.__version__, "numpy": np.__version__, "python": sys.version.split()[0]},
           "utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    rec.update(trajectory_metadata)
    with rec_path.open("x") as f:
        json.dump(rec, f, indent=1, default=str); f.write("\n")
    print(json.dumps({k: rec[k] for k in ("event", "cutoff_utc", "npz_sha256", "raw_summary", "timing_s")}, default=str))


if __name__ == "__main__":
    main()
