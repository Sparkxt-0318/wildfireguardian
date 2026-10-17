"""Blind accepted-track review for precision (protocol precision_review, amendment 2 of 2026-10-17).

Reviewers see verify sheets of sampled accepted tracks mixed with decoys, in a seeded random
order with randomised item ids; the key (which point sampled which track, which items are
decoys) is written before the review and read only to score. Decoys only keep the reviewers
blind: they are excluded from every scored quantity.

    python scripts/precision_review.py sample --population calibration --accepted ACCEPTED.parquet --out DIR
        ACCEPTED.parquet: one row per (point_id, recording, track_id) a point ever accepted (verify
        calibrate writes calibration_accepted.parquet). Every point's sample: up to --per-point (20)
        of its accepted tracks, a simple random sample (numpy default_rng(seed) over its tracks
        sorted by recording and track key). Each (recording, track) is presented once, whatever
        the number of points that sampled it. Decoys: --decoy-frac (0.3) of the item count,
        uniform from accept_all tracks that reached a checkpoint and are in no sample.
    python scripts/precision_review.py sample --population test --accepted ACCEPTED.parquet --out DIR
        The selected point: all its accepted tracks when at most --max (300), else a simple random
        sample of 300; the accept_all control (point_id accept_all): a sample of --control (100);
        decoys: --decoy-frac (0.5) from accept_all tracks the selected point did not accept.
    python scripts/precision_review.py sheets --out DIR
    python scripts/precision_review.py score --out DIR --review REVIEW.json --accepted ACCEPTED.parquet
        -> DIR/review_points.json {"points": {point_id: figures}}: true, false, ambiguous and
        unresolved reviewed tracks, the inclusion probability, reviewed precision (primary,
        optimistic, pessimistic), its exact one-sided 95 percent lower bound, accepted and false
        accepted tracks per supported minute, true-ember yield; per recording too. verify select
        reads it.

Item frames: an accepted track at its acceptance frame; a decoy at its first checkpoint.
Positions are the track's measured point there (its filtered position when coasted).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RUNS = ROOT / "results/runs/precision_20261017/runs"
SEED = 20261017


def _run_dir(rec: str) -> Path:
    return RUNS / f"{rec}_dump"


def _checkpoints(rec: str, min_hits: int = 4) -> pd.DataFrame:
    w = pd.read_parquet(_run_dir(rec) / "high_precision" / "hp_windows.parquet", columns=["key", "t", "frame", "n_hits"])
    w = w[w["n_hits"] >= min_hits].sort_values(["key", "t"]).groupby("key").head(1)
    return pd.DataFrame({"track_id": (w["key"] % 10**9).astype(int).to_numpy(), "frame": w["frame"].astype(int).to_numpy()})


def _position(points: pd.DataFrame, track_id: int, frame: int) -> tuple[float, float, int, float]:
    p = points[points["track_id"] == track_id]
    row = p[p["frame"] == frame]
    if not len(row):
        row = p.iloc[[int(np.argmin(np.abs(p["frame"].to_numpy() - frame)))]]
    r = row.iloc[0]
    x = r["x_meas"] if pd.notna(r["x_meas"]) else r["x"]
    y = r["y_meas"] if pd.notna(r["y_meas"]) else r["y"]
    return float(x), float(y), int(r["frame"]), float(r["t"])


def _srs(g: pd.DataFrame, n: int, rng) -> pd.DataFrame:
    g = g.sort_values(["recording", "track_id"]).reset_index(drop=True)
    return g if len(g) <= n else g.iloc[np.sort(rng.choice(len(g), n, replace=False))]


def cmd_sample(a) -> int:
    acc = pd.read_parquet(a.accepted)
    rng = np.random.default_rng(a.seed)
    chosen: dict[tuple[str, int], dict] = {}
    sizes = {}

    def add(pid: str, take: pd.DataFrame) -> None:
        for _, r in take.iterrows():
            c = chosen.setdefault((r["recording"], int(r["track_id"])),
                                  {"recording": r["recording"], "track_id": int(r["track_id"]), "role": "accepted",
                                   "frame": int(r["frame_accept"]), "sampled_for": []})
            c["sampled_for"].append(pid)

    if a.population == "calibration":
        for pid, g in sorted(acc.groupby("point_id"), key=lambda x: x[0]):
            take = _srs(g, a.per_point, rng)
            sizes[pid] = {"accepted": int(len(g)), "sampled": int(len(take))}
            add(pid, take)
        excluded = set(chosen)
    else:
        pids = sorted(p for p in acc["point_id"].unique() if p != "accept_all")
        if len(pids) != 1 or "accept_all" not in set(acc["point_id"]):
            raise SystemExit("the sealed review has one selected point and the accept_all control")
        sel = acc[acc["point_id"] == pids[0]]
        take = _srs(sel, a.max, rng)
        sizes[pids[0]] = {"accepted": int(len(sel)), "sampled": int(len(take))}
        add(pids[0], take)
        ctl = acc[acc["point_id"] == "accept_all"]
        take = _srs(ctl, a.control, rng)
        sizes["accept_all"] = {"accepted": int(len(ctl)), "sampled": int(len(take))}
        add("accept_all", take)
        excluded = set(chosen) | {(r, int(t)) for r, t in zip(sel["recording"], sel["track_id"])}
    recs = sorted(acc["recording"].unique())
    pool = []
    for rec in recs:
        cp = _checkpoints(rec)
        pool += [(rec, int(t), int(f)) for t, f in zip(cp["track_id"], cp["frame"]) if (rec, int(t)) not in excluded]
    n_dec = int(round(a.decoy_frac * len(chosen)))
    dec_idx = np.sort(rng.choice(len(pool), min(n_dec, len(pool)), replace=False)) if pool and n_dec else []
    items = list(chosen.values()) + [{"recording": pool[i][0], "track_id": pool[i][1], "role": "decoy",
                                      "frame": pool[i][2], "sampled_for": []} for i in dec_idx]
    order = rng.permutation(len(items))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    key, rows, cache = {}, {}, {}
    for n, i in enumerate(order):
        it = items[int(i)]
        iid = f"p{n:04d}"
        rec = it["recording"]
        if rec not in cache:
            cache[rec] = pd.read_parquet(_run_dir(rec) / "track_points.parquet",
                                         columns=["track_id", "frame", "t", "x", "y", "x_meas", "y_meas"])
        x, y, fr, t = _position(cache[rec], it["track_id"], it["frame"])
        key[iid] = {**it, "frame_shown": fr}
        rows.setdefault(rec, []).append({"item_id": iid, "key": it["track_id"], "track_id": it["track_id"], "frame": fr,
                                         "t": t, "x": x, "y": y, "category": "trk"})
    for rec, rs in rows.items():
        pd.DataFrame(rs).to_csv(out / f"items_{rec}.csv", index=False, lineterminator="\n")
    meta = {"population": a.population, "seed": a.seed, "per_point": a.per_point, "max": a.max, "control": a.control,
            "decoy_frac": a.decoy_frac, "accepted_table": str(a.accepted), "n_items": len(items),
            "n_scored_items": len(chosen), "n_decoys": len(items) - len(chosen), "recordings": recs,
            "inclusion": {p: {**v, "probability": v["sampled"] / v["accepted"] if v["accepted"] else None}
                          for p, v in sizes.items()}}
    (out / "sample.json").write_text(json.dumps(meta, indent=1) + "\n")
    (out / "key.json").write_text(json.dumps(key, indent=1) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "inclusion"}))
    return 0


def cmd_sheets(a) -> int:
    out = Path(a.out)
    rc = 0
    for f in sorted(out.glob("items_*.csv")):
        rec = f.stem[len("items_"):]
        cmd = [sys.executable, "-m", "wfglink", "verify", "sheets", "--run", str(_run_dir(rec)), "--items", str(f),
               "--clip", str(ROOT / "data/clips" / f"{rec}.yaml"), "--out", str(out / "sheets")]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:]
        print(rec, r.returncode, tail)
        rc |= r.returncode
    for c in (out / "sheets").glob("contact_*"):      # contact sheets of different recordings overwrite each other
        c.unlink()
    return rc


def _supported_min(rec: str) -> float:
    s = json.loads((_run_dir(rec) / "high_precision" / "hp_summary.json").read_text())
    return float(s["totals"]["supported_s"]) / 60.0


def cmd_score(a) -> int:
    from wfglink.verify.calibrate import review_counts, reviewed_metrics

    out = Path(a.out)
    key = json.loads((out / "key.json").read_text())
    review = json.loads(Path(a.review).read_text())
    review = review.get("result", review)
    final: dict[str, str | None] = {}
    for r in review["final"]:              # one presentation per item; a repeat keeps the first review
        if r["item_id"] not in final:
            final[r["item_id"]] = (r.get("final") or {}).get("category")
    acc = pd.read_parquet(a.accepted)
    recs = sorted(acc["recording"].unique())
    sup = {r: _supported_min(r) for r in recs}
    points = {}
    for pid, g in sorted(acc.groupby("point_id"), key=lambda x: x[0]):
        cats_by_rec: dict[str, list] = {}
        for iid, v in key.items():
            if v["role"] == "accepted" and pid in v["sampled_for"]:
                cats_by_rec.setdefault(v["recording"], []).append(final.get(iid))
        cats = [c for cs in cats_by_rec.values() for c in cs]
        m = reviewed_metrics(review_counts(cats), int(len(g)), sum(sup.values()))
        m["family"] = str(g["family"].iloc[0])
        m["per_recording"] = {r: reviewed_metrics(review_counts(cats_by_rec.get(r, [])),
                                                  int((g["recording"] == r).sum()), sup[r]) for r in recs}
        points[pid] = m
    dec = [final.get(i) for i, v in key.items() if v["role"] == "decoy"]
    rec = {"population": json.loads((out / "sample.json").read_text())["population"], "points": points,
           "decoys": {"n": len(dec), "note": "decoys keep the reviewers blind and are excluded from every score"},
           "supported_minutes": sup, "unreviewed_items": sorted(i for i in key if i not in final),
           "labels": "agent-only review: PROVISIONAL"}
    (out / "review_points.json").write_text(json.dumps(rec, indent=1, default=str) + "\n")
    print(json.dumps({p: {k: v.get(k) for k in ("accepted_tracks", "reviewed", "true", "false", "ambiguous",
                                                "unresolved", "precision", "precision_lower95")}
                      for p, v in points.items()}, indent=1, default=str)[:4000])
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("sample")
    q.add_argument("--population", required=True, choices=["calibration", "test"])
    q.add_argument("--accepted", required=True)
    q.add_argument("--out", required=True)
    q.add_argument("--seed", type=int, default=SEED)
    q.add_argument("--per-point", type=int, default=20)
    q.add_argument("--max", type=int, default=300)
    q.add_argument("--control", type=int, default=100)
    q.add_argument("--decoy-frac", type=float, default=None)
    q = sub.add_parser("sheets")
    q.add_argument("--out", required=True)
    q = sub.add_parser("score")
    q.add_argument("--out", required=True)
    q.add_argument("--review", required=True)
    q.add_argument("--accepted", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "sample" and a.decoy_frac is None:
        a.decoy_frac = 0.3 if a.population == "calibration" else 0.5
    return {"sample": cmd_sample, "sheets": cmd_sheets, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
