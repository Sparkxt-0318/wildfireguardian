"""Support audit and matched one-hour member illustration."""
from pathlib import Path
import argparse
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap


def main():
    p = argparse.ArgumentParser(); p.add_argument("--exports", required=True)
    a = p.parse_args(); here = Path(__file__).parent; out = here / "figures"; out.mkdir(exist_ok=True)
    audit = json.loads((here / "EXPORT_AUDIT.json").read_text())
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "figure.facecolor": "white", "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    labels = [r["event"] + " " + r["cutoff"][5:16] for r in audit["rows"]]
    ax.bar(labels, [100 * r["unknown_fraction"] for r in audit["rows"]], color="#0072B2")
    ax.set_ylabel("Unknown trajectory support (%)"); ax.tick_params(axis="x", rotation=65)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / ("fig02_unknown_support_by_window." + ext), dpi=300)
    plt.close(fig)
    path = next(Path(a.exports).glob("KFS_02/*/FORECAST_*.npz"))
    with np.load(path) as z:
        f = z["trajectory_first_burn_hour"][0]
        q = z["new_burn_probability"]; unknown = f == -2
        v1 = np.random.default_rng(20261008).random(q.shape) < np.nan_to_num(q, nan=0.0)
        v1[f == 0] = True
        fields = [np.where(unknown, -1, v1.astype(int)), np.where(unknown, -1, (f >= 0).astype(int))]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3))
    for ax, field, title in zip(axes, fields, ["Independent one-hour draw", "One simulated one-hour trajectory"]):
        ax.imshow(field, cmap=ListedColormap(["#BBBBBB", "#FFFFFF", "#D55E00"]), vmin=-1, vmax=1, origin="upper")
        ax.set_title(title); ax.set_xlabel("Grid column (cells)"); ax.set_ylabel("Grid row (cells)")
    fig.suptitle("Matched unknown mask, grey means unsupported", fontsize=9); fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / ("fig01_member_examples." + ext), dpi=300)
    plt.close(fig)
    (here / "RESULTS.json").write_text(json.dumps(audit, indent=2) + "\n")


if __name__ == "__main__":
    main()
