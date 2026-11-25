"""Why per-path radiant flux stays low: the pipeline's flame-front geometry and power per source. No criterion is evaluated.
Run like perpath_export.py. Writes export_v2/diag_radiant.json."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import perpath_export as E


def main():
    from wildfire import monte_carlo_hazards as mch
    initial, spread, factory = E.setup(6)
    cap = []
    orig = mch._window_exposure
    mch._window_exposure = lambda *a, **k: cap.append((a, k))
    try:
        spread.calculate_hazards(hours_later=list(range(6)), initial_activity=initial, physical_factory=factory,
                                 ignition_timing="uniform_within_step", timing_seed=E.SEED, time_step_s=60.,
                                 batch_size=E.BATCH_PIPELINE, activity_mode="probability_map")
    finally:
        mch._window_exposure = orig
    ph = cap[0][0][6]
    p = ph.parameters_dict()
    src = ph.source_flat_indices
    K = ph.radiant_kernel.astype(float)
    ny, nx = ph.receiver_shape
    sr, sc = np.divmod(src, nx)
    own = K[np.arange(len(src)), src]
    nb = []
    for i, (r, c) in enumerate(zip(sr, sc)):
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            if 0 <= r + dr < ny and 0 <= c + dc < nx:
                nb.append(K[i, (r + dr) * nx + c + dc])
    Q = np.asarray(ph.heat_release_w, float)
    width = np.broadcast_to(np.asarray(ph.front_width_m, float), Q.shape)
    md = ph.metadata_dict()
    out = {"sources": int(len(src)),
           "heat_release_mw": {"median": float(np.median(Q) / 1e6), "max": float(Q.max() / 1e6)},
           "front_width_m": {"median": float(np.median(width)), "min": float(width.min()), "max": float(width.max())},
           "radiative_fraction": p.get("radiative_fraction"), "atmospheric_transmissivity": p.get("atmospheric_transmissivity"),
           "receiver_height_m": p.get("receiver_height_m"),
           "own_cell_flux_kw_m2_max": float(own.max() / 1000), "own_cell_flux_nonzero": int(np.sum(own > 0)),
           "neighbour_375m_flux_kw_m2": {"median": float(np.median(nb) / 1000), "max": float(np.max(nb) / 1000)},
           "kernel_max_kw_m2": float(K.max() / 1000)}
    # emissive power of each source's front: radiative_fraction * Q / (2 * width * flame height)
    h = np.asarray(md.get("flame_height_m", np.nan), float) if "flame_height_m" in md else None
    from demonstration.flame_danger.reference_inputs import load_reference_inputs
    fh = np.broadcast_to(np.asarray(load_reference_inputs().flame_height_m, float), (ny, nx)).ravel()[src]
    ep = p["radiative_fraction"] * Q / (2 * width * fh)
    out["flame_height_m"] = {"median": float(np.median(fh)), "max": float(fh.max())}
    out["emissive_power_kw_m2"] = {"median": float(np.median(ep) / 1000), "max": float(ep.max() / 1000)}
    Path(HERE, "export_v2", "diag_radiant.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
