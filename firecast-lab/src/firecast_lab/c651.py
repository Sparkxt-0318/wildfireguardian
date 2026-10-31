"""c651 SMOKE baseline: K member trajectories from the frozen checkpoint. Needs PyTorch and the real data root.

FIRST REAL USE: time one fire at K = 256 before any full run (``firecast-lab time-c651 --fire ID``, through the
bench lock). c651 trained on 25 dev fires (SPLITS.json ``c651_role`` "train+validation"): label its dev scores
in-sample.

Engine: ``wildfire.rollout.simulate`` with a ``trajectory_callback`` (map 03 section 4.5; the collector of
``experimental/scenario-members/export_v3.collect_trajectories`` does the same), with these policies:

- cutoff state of DATA_NOTES section 5: ``missing_burned_area="unburned"`` (cells outside the final scar are not
  burned at the cutoff; the engine records the count), ``boundary="zero"``; the reconstruction mask is never used
  as support;
- repeated cutoff weather, cached environment kernels (bitwise equal to the uncached path), per-window seed
  ``wildfire.cumulative_report.case_seed(seed, fire, cutoff)``, fixed ``trajectory_batch_size`` (it changes which
  trajectories are drawn: record it);
- support = the engine's coverage envelope at the horizon; outside it members are unknown (NaN).

Integer first-burn hours h (state after step h) become continuous hours ``h - 1 + offset`` with one uniform offset in
(0, 1] per member: uniform timing within the hour, as ``members.coherent_members`` assumes.
"""
from __future__ import annotations

import numpy as np

from firecast_lab.data import Window, data_root

UNKNOWN, NOT_BURNED, AT_CUTOFF = -2, -1, 0
WEATHER = ("ECMWF IFS archive via Open-Meteo: 2 m temperature and 10 m wind at the cutoff hour, repeated over the "
           "horizon (persistence weather)")
POLICY = dict(boundary="zero", missing_burned_area="unburned", cache_environment_kernels=True,
              environment="repeated cutoff weather")


def _torch():
    try:
        import torch
    except ImportError as error:
        raise ModuleNotFoundError("c651 needs PyTorch 2.5.1 (forecast/pyproject.toml), which is not installed on "
                                  "this host; run it where torch is available (Siyeong's Mac)") from error
    return torch


class TrajectoryRecorder:
    """``trajectory_callback`` for ``wildfire.rollout.simulate``: first-burn hour codes per member (int16).

    Codes: ``UNKNOWN`` (-2), ``NOT_BURNED`` (-1, not by the last step seen), ``AT_CUTOFF`` (0), else the step h.
    Member m is row ``m % batch_size`` of block ``m // batch_size``, as the engine draws them.
    """

    def __init__(self, burned, known, K: int, batch_size: int):
        burned, known = np.asarray(burned, dtype=bool), np.asarray(known, dtype=bool)
        self.batch_size = int(batch_size)
        self.first = np.full((K, *burned.shape), NOT_BURNED, dtype=np.int16)
        self.first[:, known & burned] = AT_CUTOFF
        self.first[:, ~known] = UNKNOWN

    def __call__(self, block: int, states, hour: int) -> None:
        s = states.detach().cpu().numpy() if hasattr(states, "detach") else np.asarray(states)
        s = s.reshape(s.shape[0], *self.first.shape[1:]).astype(bool)
        rows = self.first[block * self.batch_size: block * self.batch_size + s.shape[0]]
        rows[(rows == NOT_BURNED) & s] = hour


def lattice_to_hours(first, initial_h, offsets) -> np.ndarray:
    """Member arrival hours (``members`` conventions) from first-burn codes ``[K, H, W]``: UNKNOWN -> NaN,
    NOT_BURNED -> +inf, AT_CUTOFF -> ``initial_h`` (<= 0), step h -> ``h - 1 + offsets[k]`` with offsets in (0, 1]."""
    first = np.asarray(first)
    offsets = np.asarray(offsets, dtype=np.float64)
    if offsets.shape != (first.shape[0],) or ((offsets <= 0) | (offsets > 1)).any():
        raise ValueError("one offset in (0, 1] per member is required")
    hours = first - 1.0 + offsets[:, None, None]
    hours = np.where(first == AT_CUTOFF, np.asarray(initial_h, dtype=np.float64)[None], hours)
    hours = np.where(first == NOT_BURNED, np.inf, hours)
    return np.where(first == UNKNOWN, np.nan, hours)


def c651_members(root, window: Window, *, K: int, seed: int, batch_size: int = 32, model=None,
                 device: str = "cpu") -> tuple[np.ndarray, dict]:
    """K member arrival fields of c651 for one window, and the run facts to record. The data root is checked
    first, then torch. ``model``: a loaded ``wildfire.WildfireModel`` to reuse across windows."""
    root = data_root(root)
    _torch()
    from wildfire import load_data, load_model, select_time
    from wildfire.cumulative_report import case_seed
    from wildfire.paths import DEFAULT_CHECKPOINT
    from wildfire.rollout import simulate, validate_controls

    model = model or load_model(DEFAULT_CHECKPOINT, device=device)
    schema = dict(channels=list(model.channel_names), categorical_encoding="one_hot",
                  categorical_classes=model.contract["categorical_classes"])
    with load_data(root, events=[window.fire], sequence_length=1, patch_size=None,
                   time_range=(window.cutoff_utc, window.cutoff_utc), **schema) as dataset:
        sample = select_time(dataset[0], index=0)
    inputs, geometry = model._prepare_prediction_inputs(sample)
    inputs, init = model._initialize_burned_area(inputs, geometry, POLICY["missing_burned_area"])
    shape = tuple(inputs["burned_area"].shape[-2:])
    burned = inputs["burned_area"].reshape(shape).cpu().numpy() == 1
    known = inputs["burned_area_valid"].reshape(shape).cpu().numpy().astype(bool)
    if not np.array_equal(burned & known, window.inputs.burned):
        raise ValueError(f"c651's cutoff state differs from the window's ({window.fire} {window.cutoff_utc})")
    hours = [float(h) for h in range(1, window.lead_h + 1)]
    trajectory_seed = case_seed(seed, window.fire, window.cutoff_utc)
    validate_controls(hours, K, trajectory_seed, batch_size)
    recorder = TrajectoryRecorder(burned, known, K, batch_size)
    outputs = simulate(model.predictor, **inputs, hours=hours, n_samples=K, seed=trajectory_seed,
                       trajectory_batch_size=batch_size, boundary=POLICY["boundary"],
                       missing_burned_area=POLICY["missing_burned_area"],
                       assumed_unburned_cells=init["assumed_unburned_cells"],
                       cache_environment_kernels=POLICY["cache_environment_kernels"], trajectory_callback=recorder)
    recorder.first[:, ~outputs[-1]["details"].valid.reshape(shape).cpu().numpy().astype(bool)] = UNKNOWN
    offsets = 1.0 - np.random.default_rng([trajectory_seed, 1]).random(K)
    facts = dict(checkpoint_sha256=model.checkpoint_sha256, trajectory_seed=trajectory_seed, batch_size=batch_size,
                 assumed_unburned_cells=int(init["assumed_unburned_cells"]), **POLICY)
    return lattice_to_hours(recorder.first, window.inputs.initial_h, offsets), facts


class C651:
    """Baseline wrapper: nothing to fit (frozen checkpoint); the model is loaded once, on first use."""

    name, weather_source = "c651", WEATHER

    def __init__(self, root=None, *, batch_size: int = 32, device: str = "cpu"):
        self.root, self.batch_size, self.device = data_root(root), batch_size, device
        self.model, self.facts = None, {}

    def fit(self, windows) -> "C651":
        return self

    def load(self):
        """The checkpoint, loaded once (needs torch)."""
        if self.model is None:
            _torch()
            from wildfire import load_model
            from wildfire.paths import DEFAULT_CHECKPOINT
            self.model = load_model(DEFAULT_CHECKPOINT, device=self.device)
        return self.model

    def members(self, window: Window, *, K: int, seed: int) -> np.ndarray:
        hours, self.facts = c651_members(self.root, window, K=K, seed=seed, batch_size=self.batch_size,
                                         model=self.load(), device=self.device)
        return hours

    def describe(self) -> dict:
        return dict(self.facts)
