"""Unmodified-rollout control on the six US2024 fires, ORIGINAL inputs (owner archive b9e000e8…).

Question: does the frozen scoring path, re-executed here with unmodified code on the original inputs, reproduce the
stored heldout forecasts (forecast/runs/20261030_perimeter_trained/execution_v3/heldout)? It is a control for every
later comparison that re-executes models on these fires (rebuilt inputs, ± half-step, conditional estimators).

Nothing in forecast/ or research/forecast-v2/scripts is edited. This script calls, unchanged:
  * pipeline.Environment (inputs hash-verified against pins computed from the extracted archive members, which
    are CRC-checked members of the sha-matched owner archive; the frozen EXTRACTION_MANIFEST.json is not in git),
  * pipeline.perimeter_samples(event, perimeters, env, crop=False) (perimeters rebuilt by the unmodified
    prepare_perimeters.py from the pinned NIROPS b19fb16c… and Choi 612edf5f… archives),
  * score_cohorts.source_identity, pipeline.c651_monte_carlo (1024 trajectories, seed 0, batch 32, as frozen),
    survival.sample_forecast with the frozen d4_wind_seed0 checkpoint (sha-checked).

Stages (each writes one JSON line per case to --out):
  identity : rebuild every case; compare all source_identity hashes with the stored case receipt, and the stored
             (row, col, y) with the rebuilt endpoint. No model runs.
  d4_wind  : identity + sample_forecast(d4_wind_seed0) on the stored cells vs stored p_d4_wind_seed0.
  c651     : identity + c651_monte_carlo vs stored p_c651_mc (use --shard i/n to split cases across processes).

    python unmodified_rollout_control.py --stage identity --data-root ARCH/wildfire/data/environment \
        --perimeters PERIM --heldout HELDOUT_DIR --work WORK --out OUT.jsonl [--shard 0/1] [--events ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SCRIPTS = REPO / "research/forecast-v2/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "forecast"))
import importlib.util  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

EVENTS = ["ID-BOF-000683_Wapiti_Wapiti", "ID-BOF-000904_Goat", "ID-BOF-001080_Lava", "ID-SCF-240202_RedRock",
          "WA-SES-000173_Pioneer", "WY-BTF-002416_FishCreek"]
D4_WIND = REPO / "forecast/runs/20261030_perimeter_trained/execution_v3/final/d4_wind_seed0/checkpoint.pt"
D4_WIND_SHA = "33c5b3cfc1332940a905da80b9414d0a5a91aad06d8797b46dc151e893de48a3"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def compare(new, old):
    new, old = np.asarray(new, np.float64), np.asarray(old, np.float64)
    d = np.abs(new - old)
    return dict(n=int(d.size), bit_identical=int((np.asarray(new, np.float32) == np.asarray(old, np.float32)).sum()),
                max_abs=float(d.max()) if d.size else 0.0, mean_abs=float(d.mean()) if d.size else 0.0,
                sum_new=float(new.sum()), sum_old=float(old.sum()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=("identity", "d4_wind", "c651"), required=True)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--perimeters", type=Path, required=True)
    ap.add_argument("--heldout", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--events", nargs="*", default=EVENTS)
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    shard_i, shard_n = (int(x) for x in args.shard.split("/"))
    P = load_module("full_cohort_pipeline", SCRIPTS / "pipeline.py")
    S = load_module("score_cohorts_ctl", SCRIPTS / "score_cohorts.py")
    from wildfire.api import load_model
    from wildfire.survival import sample_forecast

    root = args.data_root.resolve()
    pins = {str(p.relative_to(root.parent)): sha(p) for p in root.rglob("*") if p.is_file()}
    env = P.Environment(root, args.work / "env", input_sha256=pins)
    c651 = d4w = None
    if args.stage == "c651":
        if sha(P.C651) != P.C651_SHA256:
            raise SystemExit("c651 checkpoint changed")
        c651 = load_model(P.C651, device="cpu")
    if args.stage == "d4_wind":
        if sha(D4_WIND) != D4_WIND_SHA:
            raise SystemExit("d4_wind checkpoint changed")
        d4w = P.load_structured(D4_WIND)
    header = dict(header=True, stage=args.stage, shard=args.shard, script_sha256=sha(__file__),
                  pipeline_sha256=sha(SCRIPTS / "pipeline.py"), score_cohorts_sha256=sha(SCRIPTS / "score_cohorts.py"),
                  perimeter_manifest_sha256=sha(args.perimeters / "PERIMETER_MANIFEST.json"),
                  n_pinned_inputs=len(pins), inputs_digest=hashlib.sha256(json.dumps(sorted(pins.items())).encode()).hexdigest(),
                  host=dict(python=platform.python_version(), platform=platform.platform(), torch=torch.__version__,
                            numpy=np.__version__, threads=args.threads))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as out:
        out.write(json.dumps(header) + "\n")
        k = -1
        for event in args.events:
            samples = P.perimeter_samples(event, args.perimeters, env, crop=False)
            for sample in samples:
                k += 1
                if k % shard_n != shard_i:
                    continue
                case = dict(event=event, cutoff=sample.t1, endpoint=sample.meta["t2"], hours=sample.hours)
                cid = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()[:24]
                row = dict(case_id=cid, case=case)
                rpath = args.heldout / "cases" / f"{cid}.json"
                if not rpath.exists():
                    row.update(status="NO_STORED_RECEIPT")
                    out.write(json.dumps(row) + "\n"); out.flush()
                    continue
                rec = json.loads(rpath.read_text())
                ident = S.source_identity(sample)
                row["identity_mismatch"] = [f for f, v in ident.items() if rec.get(f) != v]
                with np.load(args.heldout / "cases" / f"{cid}.npz", allow_pickle=False) as z:
                    r, c, y = z["row"], z["col"], z["y"]
                    stored = {n: z["p_" + n] for n in ("c651_mc", "d4_wind_seed0")}
                row["entries_match"] = bool(np.array_equal(y, sample.endpoint[r, c].astype(np.int8))
                                            and bool(sample.score_mask[r, c].all()) and not bool(sample.initial[r, c].any()))
                row["cells"] = int(len(y))
                t0 = time.perf_counter()
                if args.stage == "d4_wind":
                    with torch.no_grad():
                        q, v = sample_forecast(d4w, sample, use_burnout=True, use_spotting=True)
                    q, v = q.numpy(), v.numpy()
                    row["d4_wind"] = dict(compare(q[r, c], stored["d4_wind_seed0"]), valid_all=bool(v[r, c].all()))
                elif args.stage == "c651":
                    p, v = P.c651_monte_carlo(c651.predictor, sample, env.names, 1024, 0)
                    row["c651_mc"] = dict(compare(p[r, c], stored["c651_mc"]), valid_all=bool(v[r, c].all()))
                row["seconds"] = time.perf_counter() - t0
                row["stored_c651_seconds"] = rec.get("model_seconds", {}).get("c651_mc")
                out.write(json.dumps(row) + "\n"); out.flush()
    print("done", args.stage, args.shard)


if __name__ == "__main__":
    main()
