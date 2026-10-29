"""Forecast export v3 overlay (Contract A, `wfg.latest-forecast-export/3`).

The frozen v2 exporter `integration/src/wfg_latest/export.py` is not edited (orchestrator decision D1: it is hash-pinned
by docs/PUBLICATION_SOURCE_MANIFEST.json). This overlay adds, without changing any v2 field, value or dtype:

  trajectory_first_burn_hour  int16 [K,H,W]  first whole hour 1..horizon at which the cell is burned in trajectory k of
                                             the recursive Monte Carlo rollout from the cutoff state; 0 burned at the
                                             cutoff; -1 never within the horizon; -2 state unknown (outside the
                                             rollout's conservative coverage at the horizon)
  trajectory_seed             int64 [K]      the ignition-stream seed of the trajectory's block, derived exactly as
                                             forecast/wildfire/rollout.py::_generator derives it (uint64 stored as its
                                             int64 two's-complement view); trajectory k is row k % B of block k // B
  trajectory_component        int16 [K]      Bayesian component index used by the trajectory (0 for a single predictor)

and the record fields export_version, trajectory_count, trajectory_horizon_hours, trajectory_boundary,
trajectory_missing_policy (plus provenance fields listed in `write_v3`). The checkpoint SHA-256 is unchanged (c651).

Two modes:
  model   run the frozen v2 exporter (imported and called, unchanged) into a staging folder, then run
          forecast/wildfire/rollout.py::simulate on the same sample with the optional `trajectory_callback`
          (needs the forecast environment and the environmental rasters, `--data-root`).
  replay  for a ONE-HOUR horizon only: re-run `simulate` with its real random streams on a replay transition that
          returns the frozen v2 probability for the cutoff state and refuses any other state. With hourly synchronous
          updates a one-hour trajectory is exactly one transition from the cutoff state, and that transition is the
          v2 export's `model.predict(..., boundary="unknown", missing_burned_area="unknown")`. Needs PyTorch only.

Usage (forecast environment):
  python export_v3.py replay --v2-dir DIR --event KFS_xx --cutoff ISO --out OUT [--n 1024 --export-count 64]
  python export_v3.py model  --source-root SRC --data-root DATA --checkpoint CK --event KFS_xx --cutoff ISO --out OUT
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WFG_LATEST = REPO / "integration" / "src" / "wfg_latest"
EXPORT_VERSION = "wfg.latest-forecast-export/3"
RECORD_SCHEMA = "wfg.latest-forecast-export.record/3"
V2_EXPORTER_SHA256 = "fe9e6b65cb959cc341b13c55bfd15a1ca8e610e06cd7b57e24ec2883e2ac5686"
CHECKPOINT_SHA256 = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"
TRAJECTORY_ARRAYS = ("trajectory_first_burn_hour", "trajectory_seed", "trajectory_component")
REPLAY_CHANNEL = "replay.v2_new_burn_probability"
DEFAULTS = {"n": 1024, "export_count": 64, "seed": 0, "batch": 32, "hours": 1}


def sha(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def derived_seed(seed: int, cutoff: int, block: int, stream: int) -> int:
    """The uint64 that rollout._generator feeds to torch.Generator.manual_seed (same SeedSequence call)."""
    return int(np.random.SeedSequence([seed, cutoff, block, stream]).generate_state(1, dtype=np.uint64)[0])


def as_int64(value: int) -> int:
    return int(np.array([value], dtype=np.uint64).view(np.int64)[0])


class TrajectoryRecorder:
    """Callback for rollout.simulate: records, per trajectory, the first step at which each cell is burned."""

    def __init__(self, observed, batch):
        self.observed = np.asarray(observed, dtype=bool)          # [H,W] known burned at the cutoff
        self.batch = int(batch)
        self.blocks = {}
        self.calls = 0

    def __call__(self, block, states, step):
        s = states.detach().cpu().numpy()[:, 0]                    # [Kb,H,W] bool
        first = self.blocks.get(block)
        if first is None:
            first = self.blocks[block] = np.full(s.shape, -1, dtype=np.int16)
        new = s & (first == -1) & ~self.observed[None]
        first[new] = step
        self.calls += 1

    def first_burn_hour(self, coverage):
        coverage = np.asarray(coverage, dtype=bool)
        rows = np.concatenate([self.blocks[b] for b in sorted(self.blocks)], axis=0)
        rows[:, self.observed] = 0
        rows[:, ~coverage & ~self.observed] = -2
        if np.any(rows[:, ~coverage & ~self.observed] > 0):
            raise RuntimeError("burn recorded outside the coverage envelope")
        return rows


def simulate_trajectories(predictor, burned, burned_valid, environment, feature_valid, channel_names, *, hours, n, seed,
                          batch, boundary="unknown", missing_burned_area="unknown"):
    """Run rollout.simulate with the trajectory callback on one cutoff; return Contract A arrays and the outputs."""
    import torch
    from wildfire import rollout
    from wildfire.models import BayesianBurnModel
    hours = int(hours)
    burned_t = torch.as_tensor(np.asarray(burned, dtype=np.float64)).reshape(1, *np.shape(burned)[-2:])
    valid_t = torch.as_tensor(np.asarray(burned_valid, dtype=bool)).reshape(1, *np.shape(burned)[-2:])
    known = (valid_t & torch.isfinite(burned_t)).numpy()[0]
    observed = known & (np.nan_to_num(burned_t.numpy()[0]) == 1)
    recorder = TrajectoryRecorder(observed, batch)
    outputs = rollout.simulate(
        predictor, burned_t, torch.as_tensor(environment), channel_names=tuple(channel_names),
        burned_area_valid=valid_t, feature_valid=torch.as_tensor(feature_valid), hours=list(range(1, hours + 1)),
        n_samples=int(n), seed=int(seed), trajectory_batch_size=int(batch), boundary=boundary,
        missing_burned_area=missing_burned_area, trajectory_callback=recorder)
    coverage = outputs[-1]["details"].valid.detach().cpu().numpy().reshape(observed.shape)
    first = recorder.first_burn_hour(coverage)[:n]
    blocks = np.arange(n) // int(batch)
    seeds = np.array([as_int64(derived_seed(int(seed), 0, int(b), 0)) for b in blocks], dtype=np.int64)
    if isinstance(predictor, BayesianBurnModel):
        supported = torch.isfinite(predictor.log_posterior_weights)
        weights = torch.softmax(predictor.log_posterior_weights[supported].detach().cpu().double(), dim=0)
        comp = []
        for b in range(int(blocks.max()) + 1):
            g = torch.Generator(device="cpu").manual_seed(derived_seed(int(seed), 0, b, 1))
            comp.append(torch.multinomial(weights, int(batch), replacement=True, generator=g).numpy())
        component = np.concatenate(comp)[:n].astype(np.int16)
    else:
        component = np.zeros(n, dtype=np.int16)
    probability = [o["details"].probability.detach().cpu().numpy().reshape(observed.shape) for o in outputs]
    return {"trajectory_first_burn_hour": first.astype(np.int16), "trajectory_seed": seeds, "trajectory_component": component,
            "probability_by_hour": probability, "coverage": coverage, "observed": observed, "callback_calls": recorder.calls}


def _replay_predictor(v2):
    """A transition that returns the frozen v2 one-hour probability for the cutoff state and refuses anything else."""
    import torch
    from wildfire.models import BurnProbability

    class ReplayScopeError(RuntimeError):
        pass

    class ReplayTransition(torch.nn.Module):
        channel_names = (REPLAY_CHANNEL,)
        prediction_metadata = {"replay": "frozen v2 export, one-hour transition from the cutoff state only"}

        def __init__(self):
            super().__init__()
            burned = np.asarray(v2["source_burned_area"], dtype=np.float64)
            known = np.asarray(v2["source_burned_area_valid"], dtype=bool) & np.isfinite(burned)
            self.register_buffer("base", torch.as_tensor(np.where(known, burned, 0.0))[None])
            self.register_buffer("known", torch.as_tensor(known)[None])
            self.register_buffer("q", torch.as_tensor(np.asarray(v2["new_burn_probability"], dtype=np.float64))[None])
            self.register_buffer("valid", torch.as_tensor(np.asarray(v2["probability_valid"], dtype=bool))[None])
            self.register_buffer("rate", torch.as_tensor(np.asarray(v2["rate_per_h"], dtype=np.float64))[None])
            self.register_buffer("rate_valid", torch.as_tensor(np.asarray(v2["rate_valid"], dtype=bool))[None])

        def forward(self, burned_area, environmental_data, *, channel_names, burned_area_valid, feature_valid,
                    dt_hours, boundary):
            if float(dt_hours) != 1.0 or tuple(channel_names) != self.channel_names:
                raise ReplayScopeError("replay supports one-hour transitions of its own channel only")
            states = burned_area.reshape(-1, 1, *burned_area.shape[-2:])
            masks = burned_area_valid.reshape(-1, 1, *burned_area.shape[-2:])
            if not (torch.equal(states, self.base.expand_as(states)) and torch.equal(masks, self.known.expand_as(masks))):
                raise ReplayScopeError("replay transition called on a state other than the cutoff state (horizon > 1 h)")
            shape = states.shape
            return BurnProbability(self.q.expand(shape), self.valid.expand(shape), self.rate.expand(shape),
                                   self.rate_valid.expand(shape))

    return ReplayTransition().double().eval(), ReplayScopeError


def load_v2(npz_path):
    with np.load(npz_path, allow_pickle=False) as a:
        return {k: a[k].copy() for k in a.files}


def replay_trajectories(v2, *, n, seed, batch, hours=1):
    if int(hours) != 1:
        raise SystemExit("REPLAY_SCOPE: replay is exact only for a one-hour horizon; use model mode")
    import torch
    torch.set_num_threads(1)
    predictor, _ = _replay_predictor(v2)
    H, W = v2["new_burn_probability"].shape
    env = np.zeros((1, 1, H, W), dtype=np.float64)
    fvalid = np.ones((1, 1, H, W), dtype=bool)
    return simulate_trajectories(predictor, v2["source_burned_area"][None], v2["source_burned_area_valid"][None], env, fvalid,
                                 predictor.channel_names, hours=1, n=n, seed=seed, batch=batch)


def write_v3(out_dir, tag, v2_arrays, v2_record, v2_npz_sha256, v2_record_sha256, traj, *, export_count, n, seed, batch, hours,
             mode, extra=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    npz_path, rec_path = out / ("FORECAST_%s.npz" % tag), out / ("FORECAST_RECORD_%s.json" % tag)
    if npz_path.exists() or rec_path.exists():
        raise SystemExit("EXPORT_EXISTS (exports are write-once): %s" % npz_path)
    K = int(export_count)
    if not 1 <= K <= n:
        raise SystemExit("export_count must lie in 1..n")
    arrays = dict(v2_arrays)
    if set(arrays) & set(TRAJECTORY_ARRAYS):
        raise SystemExit("v2 export already carries trajectory arrays")
    arrays["trajectory_first_burn_hour"] = np.ascontiguousarray(traj["trajectory_first_burn_hour"][:K], dtype=np.int16)
    arrays["trajectory_seed"] = np.ascontiguousarray(traj["trajectory_seed"][:K], dtype=np.int64)
    arrays["trajectory_component"] = np.ascontiguousarray(traj["trajectory_component"][:K], dtype=np.int16)
    tmp = out / (npz_path.name + ".partial.npz")
    np.savez_compressed(tmp, **arrays)
    os.replace(tmp, npz_path)
    import torch
    from wildfire import rollout
    rec = dict(v2_record)
    rec.update({
        "schema": RECORD_SCHEMA, "export_version": EXPORT_VERSION, "trajectory_count": K, "trajectory_simulated_count": int(n),
        "trajectory_horizon_hours": int(hours), "trajectory_boundary": "unknown", "trajectory_missing_policy": "unknown",
        "trajectory_seed_base": int(seed), "trajectory_batch_size": int(batch),
        "trajectory_seed_semantics": "trajectory_seed[k] = int64 view of SeedSequence([seed, cutoff=0, block=k//batch, stream=0]) "
                                     "(rollout._generator ignition stream of the block); trajectory k is row k % batch",
        "trajectory_first_burn_hour_coding": {"0": "burned at cutoff", "1..H": "first burned at that whole hour", "-1": "not burned within horizon",
                                               "-2": "state unknown (outside the rollout coverage envelope)"},
        "trajectory_mode": mode, "checkpoint_sha256": CHECKPOINT_SHA256,
        "v2_npz_sha256": v2_npz_sha256, "v2_record_sha256": v2_record_sha256, "v2_exporter_sha256": V2_EXPORTER_SHA256,
        "exporter_v3_sha256": sha(__file__), "rollout_sha256": sha(rollout.__file__),
        "npz": npz_path.name, "npz_sha256": sha(npz_path),
        "trajectory_statistics": {"callback_calls": int(traj["callback_calls"]),
                                  "ignitions_per_trajectory_mean": float((traj["trajectory_first_burn_hour"] >= 1).sum(axis=(1, 2)).mean()),
                                  "coverage_cells": int(np.asarray(traj["coverage"]).sum())},
        "versions_v3": {"torch": torch.__version__, "numpy": np.__version__, "python": sys.version.split()[0]},
        "utc_v3": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    if extra:
        rec.update(extra)
    with rec_path.open("x") as f:
        json.dump(rec, f, indent=1, default=str)
        f.write("\n")
    return npz_path, rec_path, rec


def _tag(iso):
    sys.path.insert(0, str(WFG_LATEST))
    import contract as C
    iso, _ = C.normalize_cutoff(iso)
    return iso, C.tag(iso)


def main_replay(a):
    iso, tag = _tag(a.cutoff)
    v2_dir = Path(a.v2_dir)
    npz, recp = v2_dir / ("FORECAST_%s.npz" % tag), v2_dir / ("FORECAST_RECORD_%s.json" % tag)
    record = json.loads(recp.read_text())
    npz_sha = sha(npz)
    if npz_sha != record["npz_sha256"] or record["checkpoint_sha256"] != CHECKPOINT_SHA256 or record["event"] != a.event:
        raise SystemExit("V2_EXPORT_IDENTITY_MISMATCH")
    v2 = load_v2(npz)
    t0 = time.perf_counter()
    traj = replay_trajectories(v2, n=a.n, seed=a.seed, batch=a.batch)
    wall = time.perf_counter() - t0
    _, rec_path, rec = write_v3(a.out, tag, v2, record, npz_sha, sha(recp), traj, export_count=a.export_count, n=a.n, seed=a.seed,
                                batch=a.batch, hours=1, mode="replay",
                                extra={"replay_scope": "one-hour horizon only: the single synchronous transition from the cutoff state is the "
                                                       "frozen v2 probability; the replay transition refuses every other state",
                                       "trajectory_wall_s_host_specific": wall})
    print(json.dumps({"event": a.event, "cutoff": iso, "npz_sha256": rec["npz_sha256"], "K": rec["trajectory_count"], "N": a.n,
                      "ignitions_mean": rec["trajectory_statistics"]["ignitions_per_trajectory_mean"], "wall_s": round(wall, 3)}))


def main_model(a):
    """Frozen v2 export (imported and called unchanged) into staging, then the trajectory rollout on the same sample."""
    iso, tag = _tag(a.cutoff)
    out = Path(a.out)
    staging = out / "v2_staging"
    if sha(WFG_LATEST / "export.py") != V2_EXPORTER_SHA256:
        raise SystemExit("V2_EXPORTER_CHANGED")
    spec = importlib.util.spec_from_file_location("wfg_latest_export_v2", WFG_LATEST / "export.py")
    v2mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v2mod)
    argv = sys.argv
    sys.argv = ["export.py", "--source-root", a.source_root, "--data-root", a.data_root, "--checkpoint", a.checkpoint,
                "--event", a.event, "--cutoff", iso, "--out", str(staging)]
    try:
        v2mod.main()
    finally:
        sys.argv = argv
    npz, recp = staging / ("FORECAST_%s.npz" % tag), staging / ("FORECAST_RECORD_%s.json" % tag)
    record = json.loads(recp.read_text())
    v2 = load_v2(npz)
    import torch
    torch.set_num_threads(1)
    from wildfire import load_model, load_data
    model = load_model(a.checkpoint, device="cpu")
    sample = load_data(a.data_root, events=[a.event], sequence_length=1, time_range=(iso, iso))[0]
    inputs, geometry = model._prepare_prediction_inputs(sample)
    inputs, _ = model._initialize_burned_area(inputs, geometry, "unknown")
    t0 = time.perf_counter()
    traj = simulate_trajectories(model.predictor, inputs["burned_area"].cpu().numpy(), inputs["burned_area_valid"].cpu().numpy(),
                                 inputs["environmental_data"].cpu().numpy(), inputs["feature_valid"].cpu().numpy(),
                                 model.channel_names, hours=a.hours, n=a.n, seed=a.seed, batch=a.batch)
    wall = time.perf_counter() - t0
    write_v3(out, tag, v2, record, sha(npz), sha(recp), traj, export_count=a.export_count, n=a.n, seed=a.seed, batch=a.batch,
             hours=a.hours, mode="model", extra={"trajectory_wall_s_host_specific": wall, "v2_staging": str(staging)})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    for name in ("replay", "model"):
        p = sub.add_parser(name)
        p.add_argument("--event", required=True)
        p.add_argument("--cutoff", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--n", type=int, default=DEFAULTS["n"])
        p.add_argument("--export-count", type=int, default=DEFAULTS["export_count"])
        p.add_argument("--seed", type=int, default=DEFAULTS["seed"])
        p.add_argument("--batch", type=int, default=DEFAULTS["batch"])
        if name == "replay":
            p.add_argument("--v2-dir", required=True)
        else:
            for k in ("--source-root", "--data-root", "--checkpoint"):
                p.add_argument(k, required=True)
            p.add_argument("--hours", type=int, default=DEFAULTS["hours"])
    a = ap.parse_args(argv)
    (main_replay if a.mode == "replay" else main_model)(a)


if __name__ == "__main__":
    main()
