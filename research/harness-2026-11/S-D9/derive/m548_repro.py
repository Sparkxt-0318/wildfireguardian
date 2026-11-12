"""Cell-level reproduction of the preprint M548/c651 Wapiti figures (S-D9 step 3). DEVELOPMENT-ONLY.

Wapiti is exposed (it is cohort R and c651's SELECTED_ON fire); nothing sealed is read.
Inputs are the 25 stored-validation cases from the owner archive (sha256 b9e000e8…dd65),
member tree runs/20261013_observed_stored_validation/cases/<id>/{reference,m548_prediction,
farsite_prediction}.npz. They are NOT committed (owner data); this script records each file's sha256.

Population (new burn): cells valid in the reference at both times, valid in the prediction, and
unburned at the cutoff (burned_area[0] == 0). Label y = burned_area[1] == 1. p = `probability`.
Reproduced against the committed record forecast/documents/observed_runtime_stored_validation_20261013.json
(n 275,961; positives 2,525; Brier 0.008402493…) and the quoted preprint figures: BSS vs
always-zero 8.17%, 617 positives with exactly zero probability, AP 0.1461, 93.9% of entries in
the preprint's first calibration bin [0, 0.01) with observed 0.364% vs mean prediction 0.0131%.

  python m548_repro.py --cases DIR --out M548_REPRO.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "forecast"))
from wildfire import baselines as B  # noqa: E402

COMMITTED = Path(__file__).resolve().parents[4] / "forecast/documents/observed_runtime_stored_validation_20261013.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    ys, ps, fs, per_case, files = [], [], [], [], {}
    for case in sorted(p for p in args.cases.iterdir() if p.is_dir()):
        ref = np.load(case / "reference.npz", allow_pickle=False)
        m = np.load(case / "m548_prediction.npz", allow_pickle=False)
        fa = np.load(case / "farsite_prediction.npz", allow_pickle=False)
        for f in ("reference.npz", "m548_prediction.npz", "farsite_prediction.npz", "protocol.json"):
            files[f"{case.name}/{f}"] = sha(case / f)
        b0, b1 = ref["burned_area"][0, 0], ref["burned_area"][1, 0]
        v = ref["burned_area_valid"][0, 0] & ref["burned_area_valid"][1, 0] & m["valid"][0, 0]
        use = v & (b0 == 0)
        y = (b1[use] == 1).astype(float)
        p = m["probability"][0, 0][use].astype(float)
        fv = fa["valid"][0, 0][use]
        f = np.where(fv, fa["probability"][0, 0][use], np.nan).astype(float)
        ys.append(y), ps.append(p), fs.append(f)
        proto = json.loads((case / "protocol.json").read_text())
        per_case.append(dict(case=case.name, cutoff=proto["cutoff"], hours=proto["hours"], entries=int(use.sum()),
                             positives=int(y.sum()), brier=float(np.mean((p - y) ** 2))))
    y, p, f = np.concatenate(ys), np.concatenate(ps), np.concatenate(fs)
    s = B.score(y, p)
    base = float(y.mean())
    lowest = s["lowest_bin"]
    committed = json.loads(COMMITTED.read_text())
    cm = next(r["independent_metrics"] for r in committed["metrics"]
              if r["model"] == "M548" and r["quantity"] == "new_burn" and r["cohort"] == "shared_models")
    out = dict(
        label="DEVELOPMENT-ONLY cell-level reproduction on exposed Wapiti (owner-archive cases, not committed)",
        cases=len(per_case), entries=int(len(y)), positives=int(y.sum()),
        m548=dict(brier=s["brier"], average_precision=s["average_precision"],
                  bss_vs_always_zero=1 - s["brier"] / base, zero_probability_positives=int(((p == 0) & (y == 1)).sum()),
                  lowest_bin=lowest, share_entries_lowest_bin=lowest["count"] / len(y),
                  # the preprint's reliability table (archive calibration.csv) uses a first bin of [0, 0.01)
                  bin_0_to_0_01=dict(count=int((p < 0.01).sum()), share=float((p < 0.01).mean()),
                                     mean_prediction=float(p[p < 0.01].mean()),
                                     observed_frequency=float(y[p < 0.01].mean()))),
        farsite=dict(valid_entries=int(np.isfinite(f).sum()),
                     brier_on_valid=float(np.nanmean((f - y) ** 2)) if np.isfinite(f).any() else None),
        committed_record=dict(path=str(COMMITTED.relative_to(COMMITTED.parents[2])), sha256=sha(COMMITTED),
                              sample_count=cm["sample_count"], positive_sample_count=cm["positive_sample_count"],
                              brier=cm["brier"]),
        checks=dict(n_match=int(len(y)) == cm["sample_count"], positives_match=int(y.sum()) == cm["positive_sample_count"],
                    brier_abs_diff=abs(s["brier"] - cm["brier"])),
        per_case=per_case, input_sha256=files,
    )
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("cases", "entries", "positives", "m548", "farsite", "checks")}, indent=1))


if __name__ == "__main__":
    main()
