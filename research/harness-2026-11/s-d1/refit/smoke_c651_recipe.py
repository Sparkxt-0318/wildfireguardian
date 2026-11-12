"""Smoke test of run_c651_recipe.py on forecast-v2's SYNTHETIC fixture (no scientific content).

1. Three-partition fixture (McCash = season train, Moose = validation, Pioneer = test): both arms
   (--fullvalid off/on) run `prepare` then `candidate` (2 epochs, CPU) end to end; asserts the cache files,
   the receipts, a one-candidate selection with the expected id, and that the arm changes the cache.
2. Train-only fixture (McCash + Antelope): prepare must fail in BOTH arms with KeyError('target') at the
   summary of the empty validation/test partitions. This is a known fixture artefact, asserted explicitly
   so that it cannot hide a different failure (Victor).

    python research/harness-2026-11/s-d1/refit/smoke_c651_recipe.py --choi <unzipped Choi archive> --work DIR
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WRAPPER = Path(__file__).with_name("run_c651_recipe.py")
FIXTURE = REPO / "research/forecast-v2/scripts/make_fixture.py"
PREP = ["--kernel-size", "9", "--contact-negatives-per-event", "5000", "--no-contact-negatives-per-event", "2000",
        "--seed", "7"]


def run(cmd, **kw):
    return subprocess.run([sys.executable, *map(str, cmd)], capture_output=True, text=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--choi", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    args = ap.parse_args()
    w = args.work
    w.mkdir(parents=True, exist_ok=False)
    # 1. three partitions, both arms, both stages
    r = run([FIXTURE, "--root", w / "fx3/root", "--zenodo", args.choi, "--events", "CA-SRF-000651_McCash",
             "ID-SCF-022105_Moose", "WA-SES-000173_Pioneer"])
    assert r.returncode == 0, r.stderr[-2000:]
    sizes = {}
    for arm in ("off", "on"):
        prep = w / f"fx3/prep_{arm}"
        r = run([WRAPPER, "--fullvalid", arm, "--", "prepare", "--output-dir", prep, "--data-root", w / "fx3/root", *PREP])
        assert r.returncode == 0, r.stderr[-2000:]
        for name in ("train.npz", "validation.npz", "test.npz", "metadata.json", f"C651_RECIPE_RECEIPT_prepare_{arm}.json"):
            assert (prep / name).exists(), name
        receipt = json.loads((prep / f"C651_RECIPE_RECEIPT_prepare_{arm}.json").read_text())
        assert receipt["fullvalid"] == arm and "forecast/wildfire/search.py" in receipt["wildfire_package_sha256"]
        sizes[arm] = (prep / "train.npz").stat().st_size
        out = w / f"fx3/cand_{arm}"
        r = run([WRAPPER, "--fullvalid", arm, "--", "candidate", "--cache", prep, "--output", out, "--epochs", "2",
                 "--finalist-epochs", "4096", "--learning-rates", "0.01", "0.05", "0.1", "--schedules", "constant",
                 "warmup_cosine", "--seed", "7", "--device", "cpu", "--threads", "2"])
        assert r.returncode == 0, r.stderr[-2000:]
        sel = json.loads((out / "candidate_selection.json").read_text())
        assert len(sel) == 1 and sel[0]["candidate"]["id"] == "mixed_3_5_7_9_02_lr0.1_warmup_cosine"
        assert sel[0]["epochs_completed"] == 2 and (out / f"C651_RECIPE_RECEIPT_candidate_{arm}.json").exists()
        print(arm, {k: sel[0][k] for k in ("best_epoch", "train_sample_count", "validation_native_sample_count")})
    assert sizes["on"] != sizes["off"], "the arm must change the prepared cache"
    # 2. single-partition fixture: the known KeyError, asserted explicitly
    r = run([FIXTURE, "--root", w / "fx1/root", "--zenodo", args.choi, "--events", "CA-KNF-006454_Antelope",
             "CA-SRF-000651_McCash"])
    assert r.returncode == 0, r.stderr[-2000:]
    for arm in ("off", "on"):
        r = run([WRAPPER, "--fullvalid", arm, "--", "prepare", "--output-dir", w / f"fx1/prep_{arm}",
                 "--data-root", w / "fx1/root", *PREP])
        assert r.returncode != 0 and r.stderr.strip().splitlines()[-1] == "KeyError: 'target'", r.stderr[-1500:]
    print("SMOKE_C651_RECIPE_OK")


if __name__ == "__main__":
    main()
