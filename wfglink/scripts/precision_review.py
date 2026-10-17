"""Blind accepted-track review for precision (protocol precision_review, amendment 2 of 2026-10-17).

Reviewers see verify sheets of sampled accepted tracks mixed with decoys, in a seeded random
order with randomised item ids; the key (which point sampled which track, which items are
decoys) is written before the review and read only to score. Decoys only keep the reviewers
blind: they are excluded from every scored quantity.

    python scripts/precision_review.py sample --population calibration --accepted ACCEPTED.parquet --out DIR
        ACCEPTED.parquet: one row per (point_id, recording, track_id) a point ever accepted (verify
        calibrate writes calibration_accepted.parquet, with supported: the acceptance frame is
        not motion_unsupported in the dump's hp_frames; a table without that column gets it from
        each recording's hp_frames). Only supported rows of scored recordings are sampled and
        counted as a point's accepted tracks; the rows left out are reported per point. Every
        point's sample: up to --per-point (20) of those tracks, a simple random sample (numpy
        default_rng(seed) over its tracks sorted by recording and track key). Each (recording,
        track) is presented once, whatever the number of points that sampled it. Decoys:
        --decoy-frac (0.3) of the item count, uniform from accept_all tracks that reached a
        checkpoint and are in no sample.
    python scripts/precision_review.py sample --population test --accepted ACCEPTED.parquet --out DIR
        The selected point: all its supported accepted tracks when at most --max (300), else a
        simple random sample of 300; the accept_all control (point_id accept_all): a sample of
        --control (100) of its supported tracks that reached a checkpoint (its accepted total is
        that restricted count); decoys: --decoy-frac (0.5) from accept_all tracks the selected
        point did not accept.
        Recordings (both populations): --recordings names the population's runs; by default
        the recordings of calibration_points.json next to the accepted table (calibration), else
        the accepted table's. A recording whose summary says tracking only (metrics_scope
        tracking_only or status not_real_time) is not scored: no decoys, rows or supported time.
        sample.json records the recordings and the SHA-256 of the accepted table and of key.json.
    python scripts/precision_review.py sheets --out DIR
    python scripts/precision_review.py score --out DIR --review REVIEW.json --accepted ACCEPTED.parquet
        Refused unless the accepted table and key.json have the SHA-256 that sample.json recorded.
        -> DIR/review_points.json {"population", "accepted_sha256", "key_sha256", "points":
        {point_id: figures}}: true, false, ambiguous and unresolved reviewed tracks, the inclusion
        probability, reviewed precision (primary, optimistic, pessimistic), its exact one-sided
        95 percent lower bound and a recording-cluster bootstrap (2000 replicates, default_rng(0):
        percentile 95 percent interval, one-sided 5th percentile, undefined replicates counted),
        accepted and false accepted tracks per supported minute, true-ember yield, the rows left
        out; per recording too. Supported minutes: per scored recording of sample.json, the frames
        of high_precision/hp_frames.parquet whose motion_unsupported is false, each weighted by
        its interval to the next frame (the median interval for the last). verify select reads it.

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
SUPPORTED_SOURCE = ("high_precision/hp_frames.parquet: frames whose motion_unsupported is false, each weighted by its "
                    "interval to the next frame (the median interval for the last), over the analysed span; recordings "
                    "tracking only (metrics_scope tracking_only or status not_real_time) excluded")


def _run_dir(rec: str) -> Path:
    return RUNS / f"{rec}_dump"


def _sha256(path: str | Path) -> str:
    from wfglink.provenance import sha256_file

    return sha256_file(path)


def _checkpoints(rec: str, min_hits: int = 4) -> pd.DataFrame:
    w = pd.read_parquet(_run_dir(rec) / "high_precision" / "hp_windows.parquet", columns=["key", "t", "frame", "n_hits"])
    w = w[w["n_hits"] >= min_hits].sort_values(["key", "t"]).groupby("key").head(1)
    return pd.DataFrame({"track_id": (w["key"] % 10**9).astype(int).to_numpy(), "frame": w["frame"].astype(int).to_numpy()})


def _tracking_only(rec: str) -> bool:
    """The run's summary (or hp_summary) says tracking only: metrics_scope tracking_only or status not_real_time."""
    d = _run_dir(rec)
    s = json.loads((d / "summary.json").read_text()) if (d / "summary.json").is_file() else {}
    h = json.loads((d / "high_precision" / "hp_summary.json").read_text())
    return "tracking_only" in (s.get("metrics_scope"), h.get("metrics_scope")) or h.get("status") == "not_real_time"


def _frames(rec: str) -> pd.DataFrame:
    return pd.read_parquet(_run_dir(rec) / "high_precision" / "hp_frames.parquet",
                           columns=["frame", "t", "motion_unsupported"]).sort_values("frame")


def _supported_min(rec: str) -> float:
    """Supported minutes of one recording (SUPPORTED_SOURCE)."""
    f = _frames(rec)
    t = f["t"].to_numpy(np.float64)
    if not len(t):
        return 0.0
    dt = np.diff(t)
    w = np.append(dt, float(np.median(dt)) if len(dt) else 0.0)
    return float(w[~f["motion_unsupported"].astype(bool).to_numpy()].sum()) / 60.0


def _supported_rows(acc: pd.DataFrame) -> tuple[pd.Series, str]:
    """Per accepted row: its acceptance frame is outside camera-motion time; and where that came from."""
    if "supported" in acc:
        return acc["supported"].astype(bool), "accepted table column supported (verify calibrate)"
    unsup = {}
    for r in acc["recording"].unique():
        f = _frames(r)
        unsup[r] = set(f.loc[f["motion_unsupported"].astype(bool), "frame"].astype(int))
    s = pd.Series([int(fr) not in unsup[r] for r, fr in zip(acc["recording"], acc["frame_accept"])], index=acc.index,
                  dtype=bool)
    return s, "high_precision/hp_frames.parquet motion_unsupported at the acceptance frame"


def _population(acc: pd.DataFrame, population: str, scored: list[str], reached: set | None = None):
    """Per point (sorted): its accepted rows the review samples and counts (supported, on a scored
    recording; for the sealed test's accept_all control, tracks that reached a checkpoint), the
    rows left out per reason, and where supported came from."""
    acc = acc.reset_index(drop=True)
    sup, source = _supported_rows(acc)
    on = acc["recording"].isin(scored)
    if population == "test" and reached is None:
        reached = {(r, int(t)) for r in scored for t in _checkpoints(r)["track_id"]}
    rows, left = {}, {}
    for pid, g in sorted(acc.groupby("point_id"), key=lambda x: x[0]):
        keep = (sup.loc[g.index] & on.loc[g.index]).to_numpy()
        out = {"not_scored_recording": int((~on.loc[g.index]).sum()),
               "unsupported": int((on.loc[g.index] & ~sup.loc[g.index]).sum())}
        if population == "test" and pid == "accept_all":
            cp = np.array([(r, int(t)) in reached for r, t in zip(g["recording"], g["track_id"])], dtype=bool)
            out["no_checkpoint"] = int((keep & ~cp).sum())
            keep = keep & cp
        rows[pid] = g[keep]
        left[pid] = out
    return rows, left, source


def _recordings(a, acc: pd.DataFrame) -> tuple[list[str], str]:
    """The population's recordings (see the module notes) and where the list came from."""
    if a.recordings:
        return sorted(set(a.recordings)), "--recordings"
    cp = Path(a.accepted).parent / "calibration_points.json"
    if a.population == "calibration" and cp.is_file():
        names = []
        for r in json.loads(cp.read_text())["recordings"]:
            tp = Path(r["truth"])
            if not tp.is_file() and not tp.is_absolute():
                tp = ROOT / tp
            if not tp.is_file():
                raise SystemExit(f"{cp}: the truth {r['truth']} is not there, so its recording cannot be named: give "
                                 "--recordings")
            names.append(str(json.loads(tp.read_text()).get("clip_id") or Path(r["run"]).name))
        return sorted(set(names)), str(cp)
    return sorted(acc["recording"].unique()), "the accepted table (give --recordings to name the population's runs)"


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
    recs, recs_source = _recordings(a, acc)
    outside = sorted(set(acc["recording"]) - set(recs))
    if outside:
        raise SystemExit(f"the accepted table holds recordings outside the population: {outside}")
    tonly = [r for r in recs if _tracking_only(r)]
    scored = [r for r in recs if r not in tonly]
    cps = {r: _checkpoints(r) for r in scored}
    reached = {(r, int(t)) for r, cp in cps.items() for t in cp["track_id"]}
    elig, left, sup_source = _population(acc, a.population, scored, reached)
    rng = np.random.default_rng(a.seed)
    chosen: dict[tuple[str, int], dict] = {}
    sizes = {}

    def add(pid: str, take: pd.DataFrame) -> None:
        for _, r in take.iterrows():
            c = chosen.setdefault((r["recording"], int(r["track_id"])),
                                  {"recording": r["recording"], "track_id": int(r["track_id"]), "role": "accepted",
                                   "frame": int(r["frame_accept"]), "sampled_for": []})
            c["sampled_for"].append(pid)

    def size(pid: str, g: pd.DataFrame, take: pd.DataFrame) -> dict:
        return {"accepted": int(len(g)), "sampled": int(len(take)), "excluded_rows": left[pid],
                "per_recording": {r: int((g["recording"] == r).sum()) for r in scored}}

    if a.population == "calibration":
        for pid, g in elig.items():
            take = _srs(g, a.per_point, rng)
            sizes[pid] = size(pid, g, take)
            add(pid, take)
        excluded = set(chosen)
    else:
        pids = sorted(p for p in elig if p != "accept_all")
        if len(pids) != 1 or "accept_all" not in elig:
            raise SystemExit("the sealed review has one selected point and the accept_all control")
        sel = elig[pids[0]]
        take = _srs(sel, a.max, rng)
        sizes[pids[0]] = size(pids[0], sel, take)
        add(pids[0], take)
        ctl = elig["accept_all"]
        take = _srs(ctl, a.control, rng)
        sizes["accept_all"] = size("accept_all", ctl, take)
        add("accept_all", take)
        every = acc[acc["point_id"] == pids[0]]
        excluded = set(chosen) | {(r, int(t)) for r, t in zip(every["recording"], every["track_id"])}
    pool = []
    for rec in scored:
        cp = cps[rec]
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
    (out / "key.json").write_text(json.dumps(key, indent=1) + "\n")
    meta = {"population": a.population, "seed": a.seed, "per_point": a.per_point, "max": a.max, "control": a.control,
            "decoy_frac": a.decoy_frac, "accepted_table": str(a.accepted), "accepted_sha256": _sha256(a.accepted),
            "key_sha256": _sha256(out / "key.json"), "n_items": len(items), "n_scored_items": len(chosen),
            "n_decoys": len(items) - len(chosen), "recordings": recs, "recordings_source": recs_source,
            "tracking_only": tonly, "supported_rows": sup_source,
            "inclusion": {p: {**v, "probability": v["sampled"] / v["accepted"] if v["accepted"] else None}
                          for p, v in sizes.items()}}
    (out / "sample.json").write_text(json.dumps(meta, indent=1) + "\n")
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


def cmd_score(a) -> int:
    from wfglink.verify.calibrate import cluster_bootstrap_precision, review_counts, reviewed_metrics

    out = Path(a.out)
    meta = json.loads((out / "sample.json").read_text())
    for what, path, want in (("accepted table", Path(a.accepted), meta.get("accepted_sha256")),
                             ("key", out / "key.json", meta.get("key_sha256"))):
        have = _sha256(path)
        if not want or have != want:
            raise SystemExit(f"{path}: its SHA-256 {have[:16]} is not the {what} SHA-256 sample.json recorded "
                             f"({str(want)[:16]}): refused")
    key = json.loads((out / "key.json").read_text())
    review = json.loads(Path(a.review).read_text())
    review = review.get("result", review)
    final: dict[str, str | None] = {}
    for r in review["final"]:              # one presentation per item; a repeat keeps the first review
        if r["item_id"] not in final:
            final[r["item_id"]] = (r.get("final") or {}).get("category")
    acc = pd.read_parquet(a.accepted)
    recs = list(meta["recordings"])
    tonly = [r for r in recs if _tracking_only(r)]
    scored = [r for r in recs if r not in tonly]
    sup = {r: _supported_min(r) for r in scored}
    elig, left, sup_source = _population(acc, meta["population"], scored)
    points = {}
    for pid, g in elig.items():
        want = (meta["inclusion"].get(pid) or {}).get("accepted")
        if want != int(len(g)):
            raise SystemExit(f"{pid}: {len(g)} accepted tracks in the scored population, sample.json has {want}: "
                             "refused")
        cats_by_rec: dict[str, list] = {}
        for iid, v in key.items():
            if v["role"] == "accepted" and pid in v["sampled_for"]:
                cats_by_rec.setdefault(v["recording"], []).append(final.get(iid))
        cats = [c for cs in cats_by_rec.values() for c in cs]
        try:
            m = reviewed_metrics(review_counts(cats), int(len(g)), sum(sup.values()))
            m["per_recording"] = {r: reviewed_metrics(review_counts(cats_by_rec.get(r, [])),
                                                      int((g["recording"] == r).sum()), sup[r]) for r in scored}
        except ValueError as exc:
            raise SystemExit(f"{pid}: {exc}") from None
        m["family"] = str(acc.loc[acc["point_id"] == pid, "family"].iloc[0])
        m["excluded_rows"] = left[pid]
        m["precision_bootstrap"] = cluster_bootstrap_precision([(m["per_recording"][r]["true"],
                                                                 m["per_recording"][r]["false"]) for r in scored])
        points[pid] = m
    dec = [final.get(i) for i, v in key.items() if v["role"] == "decoy"]
    rec = {"population": meta["population"], "accepted_table": str(a.accepted),
           "accepted_sha256": meta["accepted_sha256"], "key_sha256": meta["key_sha256"],
           "sample_sha256": _sha256(out / "sample.json"), "points": points,
           "decoys": {"n": len(dec), "note": "decoys keep the reviewers blind and are excluded from every score"},
           "recordings": scored, "tracking_only_recordings": tonly, "supported_rows": sup_source,
           "supported_minutes": sup, "supported_minutes_source": SUPPORTED_SOURCE,
           "bootstrap": "recording-cluster bootstrap of reviewed precision per point: the scored recordings resampled "
                        "with replacement, 2000 replicates, numpy default_rng(0) per point; percentile 95 percent "
                        "interval and one-sided 5th percentile over the defined replicates",
           "unreviewed_items": sorted(i for i in key if i not in final), "labels": "agent-only review: PROVISIONAL"}
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
    q.add_argument("--recordings", nargs="+", default=None, help="the population's recordings (default: see the notes)")
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
