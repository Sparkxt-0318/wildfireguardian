"""Training rows for the verifier's model families from a verify dump and track labels
(python -m wfglink verify dataset).

Labels. CSV files of two kinds, read together:
- a track review: track_key (the observer's key, epoch * 10**9 + track_id) or track_id,
  category, and optionally reviewer and adjudicated (bool);
- audit categories: rows of a verify audit table (det_row, track_id, status, ...) with a
  category or adjudicated_category column (adjudicated_category rows count as adjudicated).
Per track, the adjudicated rows decide when there are any, otherwise all rows; rows that
disagree make the track a conflict (excluded). CATEGORIES maps a category to its class:
ember is 1; fixture_light, reflection, flame_glare_edge, moving_non_ember, codec_artifact and
overlay_text are 0; faint_possible_ember, unclear and duplicate_fragment are excluded
(an ambiguous track never becomes background). The error audit's own categories are read
too: true_ember is ember; detected_but_displaced, localization_offset, label_doubtful,
missed_merged_or_crowded and missed_large_or_saturated (position or label errors, not a
class of the track) are excluded. Another category is an error.

Labels are tied to the dump run: a label row that gives frame, x and y (the audit
inventory's detection rows) must have a measured point of its track at that frame within
LABEL_POS_PX (2 px); a track with a row that fails is left out (label_position_mismatch),
and more than LABEL_MISMATCH_MAX (5 percent) of the checked rows failing refuses the build
(the labels are of another run or config). The review confidence (sure, unsure) is carried:
a track is sure when every deciding row with a confidence says sure, unsure when one says
unsure; tracks.parquet has it as confidence, and dataset.json counts the track samples by
class and confidence, so whether unsure judgments may train can be decided from it.

Track samples (tracks.parquet). One per labelled track: its window features at the first
checkpoint where the online methods would score it (at least verify.min_hits feature hits
and no camera motion, the decision moment of rules, patch and temporal), found by replaying
the dump with a probe scorer that records that window and never accepts (verify/replay.py),
plus the window's hits (their rows in hits.parquet: win_hit_start, win_hit_count), which
are the patch PCA inputs of the temporal family and the hits a patch model scores.
group = int(t_first // block_s); cell = (x // cell_px, y // cell_px) of the track's first
point. Negatives are capped per cell at train time (cap_negatives, a seeded subset of at
most max_neg_per_cell per cell), so a fixture light that makes many tracks in one place
does not dominate; dataset.json reports the counts after the cap.

Hit samples (hits.parquet, role sample). Up to max_hits_per_track hits per labelled track,
from the hits whose patches were dumped, in time order: a hit whose target patch is nearly
the previous kept hit's (cosine > DEDUPE_COS) is dropped first, then at most
max_hits_per_track are taken evenly spaced. They carry the track's label and group. The
patches (float16, (n, 2, P, P)) are patches.npy, row patch_row; a hit that is both a sample
and in its track's window is one row.

A window hit whose patch was not dumped (the replay's missing_hits; an all-zero patch would
enter the dataset) leaves its track out (missing_patch); dataset.json records the probe
replay's missing_patches count.

Optional exclusion zone (exclude_tiles): tracks with a measured point within exclude_px of a
scored label tile (a label-tiles folder's manifest.csv, its reserve tiles not counted: they
were never scored) and within exclude_s of its frame time are left out (the development
audit tiles stay out of training).

Data floor (dataset.json floor): adequate with at least FLOOR_POS positive and FLOOR_NEG
negative tracks after the cap and at least FLOOR_CELLS distinct negative cells; otherwise
adequate false with the reason, and `verify train` trains nothing.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from wfglink.verify.features import FEATURE_NAMES, WINDOW_NAMES

POSITIVE = ("ember",)
NEGATIVE = ("fixture_light", "reflection", "flame_glare_edge", "moving_non_ember", "codec_artifact", "overlay_text")
AMBIGUOUS = ("faint_possible_ember", "unclear", "duplicate_fragment")
AUDIT_ALIASES = {"true_ember": "ember"}
AUDIT_EXCLUDED = ("detected_but_displaced", "localization_offset", "label_doubtful", "missed_merged_or_crowded",
                  "missed_large_or_saturated")
CATEGORIES = {**{c: 1 for c in POSITIVE}, **{c: 0 for c in NEGATIVE}, **{c: None for c in AMBIGUOUS},
              **{c: None for c in AUDIT_EXCLUDED}}
DEDUPE_COS = 0.995
FLOOR_POS, FLOOR_NEG, FLOOR_CELLS = 100, 200, 30
KEY_BASE = 10 ** 9
LABEL_POS_PX = 2.0
LABEL_MISMATCH_MAX = 0.05
CONFIDENCES = ("sure", "unsure")


class ProbeScorer:
    """Records each track's first scored window (the online methods' decision moment) and
    never accepts. Gated like rules, patch and temporal; replay's ledger sets key, t, frame."""

    method = "probe"
    threshold = math.inf
    gated = True
    available = True

    def __init__(self, min_hits: int):
        self.min_hits = int(min_hits)
        self.key: int | None = None
        self.t, self.frame = math.nan, -1
        self.observer = None
        self.first: dict[int, dict[str, Any]] = {}

    def score(self, window_vec, patch_stats):
        return 0.0, True, ""

    def score_window(self, window):
        if self.key is not None and self.key not in self.first:
            hits = list(self.observer.last_hits.get(self.key, [])) if self.observer is not None else []
            self.first[self.key] = {"t": self.t, "frame": self.frame, "vec": np.array(window.vec, np.float64),
                                    "n_feature_hits": int(window.n_feature_hits),
                                    "hits": [h for h in hits if h.values is not None and h.patch is not None]}
        return 0.0, True, ""

    def identity(self) -> dict[str, Any]:
        return {"method": self.method, "min_hits": self.min_hits}


# Labels --------------------------------------------------------------------------------

def _truthy(v) -> bool:
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "t")


def _num(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return math.nan
    return f


def _conf(v) -> str | None:
    s = "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v).strip().lower()
    return s if s in CONFIDENCES else None


def label_rows(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """Every usable label row: key, category, adjudicated, confidence (sure, unsure or None),
    frame, x, y (NaN when the file has none) and source."""
    import pandas as pd

    rows = []
    for p in paths:
        df = pd.read_csv(p)
        if "adjudicated_category" in df:
            cat, adj = df["adjudicated_category"], pd.Series(True, index=df.index)
            if "category" in df:          # rows without an adjudicated category keep their own
                miss = cat.isna() | (cat.astype(str).str.strip() == "")
                cat = cat.where(~miss, df["category"])
                adj = ~miss
        elif "category" in df:
            cat = df["category"]
            adj = df["adjudicated"].map(_truthy) if "adjudicated" in df else pd.Series(False, index=df.index)
        else:
            raise ValueError(f"{p}: no category or adjudicated_category column")
        if "track_key" in df:
            key = pd.to_numeric(df["track_key"], errors="coerce")
        elif "track_id" in df:
            key = pd.to_numeric(df["track_id"], errors="coerce")
        else:
            raise ValueError(f"{p}: no track_key or track_id column")
        nan = pd.Series(np.nan, index=df.index)
        conf = df["confidence"] if "confidence" in df else nan
        pos = [df[c] if c in df else nan for c in ("frame", "x", "y")]
        for k, c, a, cf, f, x, y in zip(key, cat, adj, conf, *pos):
            if not np.isfinite(k) or c is None or (isinstance(c, float) and math.isnan(c)) or not str(c).strip():
                continue
            c = AUDIT_ALIASES.get(str(c).strip(), str(c).strip())
            if c not in CATEGORIES:
                raise ValueError(f"{p}: unknown category {c!r} (use one of {', '.join(CATEGORIES)})")
            rows.append({"key": int(k), "category": c, "adjudicated": bool(a), "confidence": _conf(cf),
                         "frame": _num(f), "x": _num(x), "y": _num(y), "source": str(p)})
    return rows


def read_labels(paths: Iterable[str | Path], rows: list[dict[str, Any]] | None = None
                ) -> tuple[Any, list[dict[str, Any]]]:
    """Track labels from review and audit CSVs (or their label_rows): a DataFrame (key,
    track_id, epoch, category, label, adjudicated, confidence, sources) of the decided tracks
    and the list of conflicts."""
    import pandas as pd

    if rows is None:
        rows = label_rows(paths)
    by: dict[int, list[dict]] = {}
    for r in rows:
        by.setdefault(r["key"], []).append(r)
    out, conflicts = [], []
    for k in sorted(by):
        rs = by[k]
        use = [r for r in rs if r["adjudicated"]] or rs
        cats = sorted({r["category"] for r in use})
        if len(cats) > 1:
            conflicts.append({"key": k, "categories": cats})
            continue
        confs = {r.get("confidence") for r in use} - {None}
        out.append({"key": k, "track_id": k % KEY_BASE, "epoch": k // KEY_BASE, "category": cats[0],
                    "label": CATEGORIES[cats[0]], "adjudicated": any(r["adjudicated"] for r in use),
                    "confidence": "unsure" if "unsure" in confs else ("sure" if confs else None),
                    "sources": ";".join(sorted({r["source"] for r in use}))})
    return pd.DataFrame(out, columns=["key", "track_id", "epoch", "category", "label", "adjudicated", "confidence",
                                      "sources"]), conflicts


def position_mismatches(rows: list[dict[str, Any]], points, px: float = LABEL_POS_PX) -> tuple[int, int, set[int]]:
    """(label rows with frame, x and y checked, rows that fail, keys of the tracks with a
    failing row: no measured point of the track at the row's frame within px)."""
    import pandas as pd

    check = [r for r in rows if math.isfinite(r["frame"]) and math.isfinite(r["x"]) and math.isfinite(r["y"])]
    if not check:
        return 0, 0, set()
    p = points[~points["coasted"].astype(bool)]
    tid, fr = p["track_id"].to_numpy(np.int64), p["frame"].to_numpy(np.int64)
    want = pd.MultiIndex.from_arrays([np.array([r["key"] % KEY_BASE for r in check], np.int64),
                                      np.array([int(r["frame"]) for r in check], np.int64)])
    sel = pd.MultiIndex.from_arrays([tid, fr]).isin(want)
    by: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for t, f, x, y in zip(tid[sel], fr[sel], p["x_meas"].to_numpy(float)[sel], p["y_meas"].to_numpy(float)[sel]):
        by.setdefault((int(t), int(f)), []).append((x, y))
    bad, n_bad = set(), 0
    for r in check:
        xy = np.array(by.get((r["key"] % KEY_BASE, int(r["frame"])), []), float).reshape(-1, 2)
        if not xy.size or not (np.hypot(xy[:, 0] - r["x"], xy[:, 1] - r["y"]) <= px).any():
            bad.add(int(r["key"]))
            n_bad += 1
    return len(check), n_bad, bad


# Sampling ------------------------------------------------------------------------------

def cap_negatives(tracks, max_per_cell: int, seed: int) -> np.ndarray:
    """Mask of the track samples kept: every positive, and per cell a seeded random subset of
    at most max_per_cell negatives (numpy default_rng(seed), cells in sorted order)."""
    keep = tracks["label"].to_numpy(np.int64) == 1
    neg = np.flatnonzero(~keep)
    if not neg.size:
        return keep
    rng = np.random.default_rng(int(seed))
    cells = tracks["cell"].to_numpy()[neg]
    for c in sorted(set(cells.tolist())):
        idx = neg[cells == c]
        idx = idx[np.argsort(tracks["key"].to_numpy()[idx], kind="stable")]
        if idx.size > max_per_cell:
            idx = np.sort(rng.choice(idx, size=int(max_per_cell), replace=False))
        keep[idx] = True
    return keep


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.astype(np.float64).ravel(), b.astype(np.float64).ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 1.0 if na == nb else 0.0
    return float(a @ b / (na * nb))


def sample_hits(patches: np.ndarray, max_hits: int) -> np.ndarray:
    """Indices (time order) of the hits kept for one track: near-duplicates of the previous
    kept hit's target patch dropped, then at most max_hits evenly spaced."""
    kept: list[int] = []
    for i in range(len(patches)):
        if kept and _cos(patches[i, 0], patches[kept[-1], 0]) > DEDUPE_COS:
            continue
        kept.append(i)
    kept_a = np.array(kept, np.int64)
    if kept_a.size > max_hits:
        kept_a = kept_a[np.unique(np.round(np.linspace(0, kept_a.size - 1, int(max_hits))).astype(np.int64))]
    return kept_a


def _near_tiles(points, tiles_dir: str | Path, px: float, s: float) -> set[int]:
    """Track ids with a measured point within px of a label tile and within s of its time."""
    import pandas as pd

    man = pd.read_csv(Path(tiles_dir) / "manifest.csv", dtype={"tile_id": str})
    if "reserve" in man:              # reserve tiles were never scored; their labels may train
        man = man[~man["reserve"].astype(str).str.lower().isin(("true", "1"))]
    p = points[~points["coasted"].astype(bool)]
    x, y, t = p["x_meas"].to_numpy(float), p["y_meas"].to_numpy(float), p["t"].to_numpy(float)
    tid = p["track_id"].to_numpy(np.int64)
    out: set[int] = set()
    for _, r in man.iterrows():
        x0, y0, w, h, tt = float(r["x0"]), float(r["y0"]), float(r["w"]), float(r["h"]), float(r["t"])
        sel = ((x >= x0 - px) & (x <= x0 + w - 1 + px) & (y >= y0 - px) & (y <= y0 + h - 1 + px)
               & (np.abs(t - tt) <= s))
        out |= set(tid[sel].tolist())
    return out


def floor_verdict(n_pos: int, n_neg: int, n_cells: int) -> dict[str, Any]:
    why = []
    if n_pos < FLOOR_POS:
        why.append(f"{n_pos} positive tracks (at least {FLOOR_POS} needed)")
    if n_neg < FLOOR_NEG:
        why.append(f"{n_neg} negative tracks after the per-cell cap (at least {FLOOR_NEG} needed)")
    if n_cells < FLOOR_CELLS:
        why.append(f"{n_cells} distinct negative cells (at least {FLOOR_CELLS} needed)")
    return {"adequate": not why, "reason": "; ".join(why), "positive_tracks": n_pos, "negative_tracks": n_neg,
            "negative_cells": n_cells, "rule": f">= {FLOOR_POS} positive and >= {FLOOR_NEG} negative tracks "
                                                f"(after the per-cell cap) and >= {FLOOR_CELLS} distinct negative cells"}


# Build ---------------------------------------------------------------------------------

def build_dataset(dump_run, label_csvs, out_dir, cfg: dict, block_s: float = 4.0, cell_px: int = 16,
                  max_neg_per_cell: int = 20, max_hits_per_track: int = 8, profile: str = "file_native",
                  exclude_tiles: str | Path | None = None, exclude_px: float = 16.0, exclude_s: float = 1.0,
                  strict_config: bool = True, command_line: str | None = None) -> dict[str, Any]:
    """Write tracks.parquet, hits.parquet, patches.npy and dataset.json (see the module notes);
    returns the dataset.json record."""
    import pandas as pd

    from wfglink.provenance import git_state, now_shanghai, sha256_file, sha256_json
    from wfglink.verify.config import VerifyConfig
    from wfglink.verify.replay import load_dump, replay_many

    if isinstance(label_csvs, (str, Path)):
        label_csvs = [label_csvs]
    label_csvs = [Path(p) for p in label_csvs]
    vcfg = VerifyConfig.from_cfg(cfg)
    if vcfg is None:
        raise ValueError("the config has no verify section (use verify.config.hp_config)")
    dump = load_dump(dump_run)
    lrows = label_rows(label_csvs)
    labels, conflicts = read_labels(label_csvs, lrows)
    n_checked, n_bad_rows, pos_bad = position_mismatches(lrows, dump.points)
    if n_checked and n_bad_rows > LABEL_MISMATCH_MAX * n_checked:
        raise ValueError(f"{n_bad_rows} of {n_checked} label rows with a frame and position have no measured point of "
                         f"their track there (within {LABEL_POS_PX:g} px): the labels are not of this run "
                         f"({dump.run_dir})")
    excluded: dict[str, int] = {}
    exclusion_rows: list[dict[str, Any]] = []

    def drop(key: int, why: str, cat: str = "") -> None:
        excluded[why] = excluded.get(why, 0) + 1
        exclusion_rows.append({"key": int(key), "reason": why, "category": cat})

    for c in conflicts:
        drop(c["key"], "conflicting_labels")
    by_cat = labels["category"].value_counts().to_dict() if len(labels) else {}
    amb = labels[labels["label"].isna()] if len(labels) else labels
    for k, c in zip(amb["key"], amb["category"]):
        drop(k, f"ambiguous:{c}", c)
    lab = labels[labels["label"].notna()].copy() if len(labels) else labels
    lab["label"] = lab["label"].astype(int) if len(lab) else lab["label"]
    if len(lab) and (lab["epoch"] != 0).any():
        raise ValueError("labels name tracks of another epoch than 0: a file-mode dump has one epoch")
    dec = dump.decisions.set_index("key")
    pts = dump.points
    first = pts.sort_values(["track_id", "frame"], kind="stable").groupby("track_id").first() if len(pts) else None
    near = _near_tiles(pts, exclude_tiles, exclude_px, exclude_s) if exclude_tiles else set()

    probe = ProbeScorer(vcfg.min_hits)
    probe_res = replay_many(dump, {"probe": probe}, cfg, profile, strict_config=strict_config)["probe"]
    missing = probe_res.missing_hits
    win = probe.first

    with np.load(Path(dump.run_dir) / "high_precision" / "hp_patches.npz", allow_pickle=False) as z:
        pk, pf, pj = z["key"].astype(np.int64), z["frame"].astype(np.int64), z["det_index"].astype(np.int64)
    order = np.lexsort((pj, pf, pk))
    pk, pf, pj = pk[order], pf[order], pj[order]
    pidx = order                               # row in dump.patches
    fpos = {int(f): i for i, f in enumerate(dump.frames)}

    track_rows, hit_rows, patch_list = [], [], []
    hit_index: dict[tuple[int, int, int], int] = {}

    def add_hit(key: int, label: int, group: int, frame: int, det_index: int, values: np.ndarray, patch: np.ndarray,
                role: str) -> int:
        k3 = (key, frame, det_index)
        i = hit_index.get(k3)
        if i is None:
            i = len(hit_rows)
            hit_index[k3] = i
            fi = fpos[frame]
            hit_rows.append({"row": i, "key": key, "track_id": key % KEY_BASE, "frame": frame,
                             "det_index": det_index, "t": float(dump.times[fi]), "label": label, "group": group,
                             "sample": False, "window": False, "patch_row": i,
                             **{n: float(v) for n, v in zip(FEATURE_NAMES, values)}})
            patch_list.append(np.asarray(patch, np.float16))
        hit_rows[i][role] = True
        return i

    for r in lab.itertuples(index=False):
        key, label, cat = int(r.key), int(r.label), str(r.category)
        conf = r.confidence if isinstance(r.confidence, str) else None
        if key in pos_bad:
            drop(key, "label_position_mismatch", cat)
            continue
        if key not in dec.index:
            drop(key, "not_confirmed", cat)
            continue
        if key % KEY_BASE in near:
            drop(key, "near_scored_tiles", cat)
            continue
        w = win.get(key)
        if w is None or not w["hits"]:
            drop(key, "no_decision_window", cat)
            continue
        if any((int(h.frame), int(h.det_index)) in missing for h in w["hits"]):
            drop(key, "missing_patch", cat)
            continue
        d = dec.loc[key]
        group = int(float(d["t_first"]) // block_s)
        f0 = first.loc[key % KEY_BASE]
        x0, y0 = float(f0["x_meas"]), float(f0["y_meas"])
        cx, cy = int(x0 // cell_px), int(y0 // cell_px)
        # Hit samples: the dumped patches of this track, in time order.
        a, b = np.searchsorted(pk, key, "left"), np.searchsorted(pk, key, "right")
        rows_k = pidx[a:b]
        fr_k, dj_k = pf[a:b], pj[a:b]
        tord = np.argsort(fr_k, kind="stable")
        rows_k, fr_k, dj_k = rows_k[tord], fr_k[tord], dj_k[tord]
        keep = sample_hits(dump.patches[rows_k], max_hits_per_track) if len(rows_k) else np.zeros(0, np.int64)
        for q in keep.tolist():
            fi = fpos[int(fr_k[q])]
            vrow = int(dump.det_start[fi]) + int(dj_k[q])
            add_hit(key, label, group, int(fr_k[q]), int(dj_k[q]), dump.hit_values[vrow], dump.patches[rows_k[q]],
                    "sample")
        wrows = [add_hit(key, label, group, h.frame, h.det_index, h.values, h.patch, "window") for h in w["hits"]]
        track_rows.append({"key": key, "track_id": key % KEY_BASE, "category": cat, "label": label,
                           "confidence": conf, "group": group,
                           "cell_x": cx, "cell_y": cy, "cell": f"{cx}_{cy}", "x0": x0, "y0": y0,
                           "t_first": float(d["t_first"]), "t_confirm": float(d["t_confirm"]),
                           "t_window": float(w["t"]), "frame_window": int(w["frame"]),
                           "n_feature_hits": int(w["n_feature_hits"]), "win_hits": wrows,
                           **{n: float(v) for n, v in zip(WINDOW_NAMES, w["vec"])}})

    # Window hits of one track are contiguous: rows are re-ordered by (key, frame) and the
    # windows referenced as start and count.
    hits = pd.DataFrame(hit_rows)
    P = vcfg.patch.target_px
    if len(hits):
        hits = hits.sort_values(["key", "frame", "det_index"], kind="stable").reset_index(drop=True)
        old_to_new = {int(o): i for i, o in enumerate(hits["row"])}
        patches = np.stack([patch_list[int(o)] for o in hits["row"]]).astype(np.float16)
        hits["patch_row"] = np.arange(len(hits))
        hits = hits.drop(columns=["row"])
    else:
        old_to_new = {}
        patches = np.zeros((0, 2, P, P), np.float16)
        hits = pd.DataFrame(columns=["key", "track_id", "frame", "det_index", "t", "label", "group", "sample", "window",
                                     "patch_row", *FEATURE_NAMES])
    for tr in track_rows:
        new = sorted(old_to_new[i] for i in tr.pop("win_hits"))
        if new != list(range(new[0], new[0] + len(new))):
            raise AssertionError("window hits are not contiguous")
        tr["win_hit_start"], tr["win_hit_count"] = int(new[0]), len(new)
    tcols = ["key", "track_id", "category", "label", "confidence", "group", "cell_x", "cell_y", "cell", "x0", "y0",
             "t_first",
             "t_confirm", "t_window", "frame_window", "n_feature_hits", "win_hit_start", "win_hit_count",
             *WINDOW_NAMES]
    tracks = pd.DataFrame(track_rows, columns=tcols)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tracks.to_parquet(out / "tracks.parquet", index=False)
    hits.to_parquet(out / "hits.parquet", index=False)
    np.save(out / "patches.npy", patches)
    pd.DataFrame(exclusion_rows, columns=["key", "reason", "category"]).to_csv(out / "exclusions.csv", index=False)

    kept0 = cap_negatives(tracks, max_neg_per_cell, 0) if len(tracks) else np.zeros(0, bool)
    capped = tracks[kept0] if len(tracks) else tracks
    n_pos = int((capped["label"] == 1).sum()) if len(capped) else 0
    n_neg = int((capped["label"] == 0).sum()) if len(capped) else 0
    n_cells = int(capped.loc[capped["label"] == 0, "cell"].nunique()) if len(capped) else 0
    from wfglink.verify.replay import feature_settings, feature_settings_sha256

    def by_conf(df) -> dict[str, dict[str, int]]:
        if not len(df):
            return {}
        c = df["confidence"].where(df["confidence"].notna(), "none").astype(str)
        return {str(y): {k: int(v) for k, v in c[df["label"] == y].value_counts().sort_index().items()}
                for y in sorted(set(df["label"].astype(int)))}

    hp = Path(dump.run_dir) / "high_precision"
    src_files = [Path(dump.run_dir) / n for n in ("summary.json", "detections.parquet", "track_points.parquet",
                                                  "frames.parquet")]
    src_files += [hp / n for n in ("hp_summary.json", "hp_hits.parquet", "hp_patches.npz", "hp_decisions.parquet",
                                   "hp_frames.parquet")]
    rec = {
        "schema_version": 1, "created": now_shanghai(), "profile": profile,
        "labels_note": "agent labels unless the review says otherwise: PROVISIONAL, development only",
        "dump_run": str(dump.run_dir), "online_method": dump.method,
        "sources": {"dump": {p.name: {"path": str(p), "sha256": sha256_file(p)} for p in src_files},
                    "labels": [{"path": str(p), "sha256": sha256_file(p)} for p in label_csvs]},
        "config_sha256": sha256_json(cfg), "video_sha256": (dump.summary.get("input") or {}).get("sha256"),
        "feature_settings": feature_settings(cfg), "feature_settings_sha256": feature_settings_sha256(cfg),
        "settings": {"block_s": block_s, "cell_px": cell_px, "max_neg_per_cell": max_neg_per_cell,
                     "max_hits_per_track": max_hits_per_track, "min_hits": vcfg.min_hits,
                     "window_hits": vcfg.window_hits, "dedupe_cos": DEDUPE_COS, "patch_px": P,
                     "ood": {"z_max": vcfg.ood.z_max, "max_out": vcfg.ood.max_out},
                     "exclude_tiles": str(exclude_tiles) if exclude_tiles else None, "exclude_px": exclude_px,
                     "exclude_s": exclude_s, "label_pos_px": LABEL_POS_PX, "label_mismatch_max": LABEL_MISMATCH_MAX},
        "categories": CATEGORIES,
        "label_positions": {"rows_checked": n_checked, "rows_mismatched": n_bad_rows,
                            "tracks_left_out": len(pos_bad)},
        "missing_patches": {"buffer_hits_without_dumped_patch": int(probe_res.missing_patches),
                            "tracks_left_out": int(excluded.get("missing_patch", 0))},
        "counts": {
            "labelled_tracks": int(len(labels)) + len(conflicts), "labels_by_category": {k: int(v) for k, v in
                                                                                         sorted(by_cat.items())},
            "labels_by_class_and_confidence": by_conf(labels[labels["label"].notna()].assign(
                label=lambda d: d["label"].astype(int))) if len(labels) else {},
            "track_samples": int(len(tracks)),
            "track_samples_by_class_and_confidence": by_conf(tracks),
            "after_cap_by_class_and_confidence": by_conf(capped),
            "track_samples_by_class": {str(k): int(v) for k, v in tracks["label"].value_counts().sort_index().items()}
            if len(tracks) else {},
            "track_samples_by_category": {k: int(v) for k, v in tracks["category"].value_counts().sort_index().items()}
            if len(tracks) else {},
            "after_cap_by_class": {"1": n_pos, "0": n_neg},
            "groups": {str(k): int(v) for k, v in tracks["group"].value_counts().sort_index().items()}
            if len(tracks) else {},
            "negative_cells": int(tracks.loc[tracks["label"] == 0, "cell"].nunique()) if len(tracks) else 0,
            "negative_cells_after_cap": n_cells,
            "max_negatives_in_a_cell": int(tracks[tracks["label"] == 0].groupby("cell").size().max())
            if len(tracks) and (tracks["label"] == 0).any() else 0,
            "hit_rows": int(len(hits)), "hit_samples": int(hits["sample"].sum()) if len(hits) else 0,
            "window_hits": int(hits["window"].sum()) if len(hits) else 0,
            "hit_samples_by_class": {str(k): int(v) for k, v in hits[hits["sample"]]["label"].value_counts()
                                     .sort_index().items()} if len(hits) else {}},
        "exclusions": dict(sorted(excluded.items())), "conflicts": conflicts[:50],
        "floor": floor_verdict(n_pos, n_neg, n_cells),
        "outputs": {"tracks": "tracks.parquet", "hits": "hits.parquet", "patches": "patches.npy",
                    "exclusions": "exclusions.csv"},
        "files_sha256": {n: sha256_file(out / n) for n in ("tracks.parquet", "hits.parquet", "patches.npy")},
        "command_line": command_line, "notes": list(dump.notes), **git_state(),
    }
    (out / "dataset.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return rec


def load_dataset(ds_dir: str | Path) -> dict[str, Any]:
    """dataset.json, tracks, hits and patches of a dataset folder (sha256 of each file checked)."""
    import pandas as pd

    from wfglink.provenance import sha256_file

    d = Path(ds_dir)
    rec = json.loads((d / "dataset.json").read_text(encoding="utf-8"))
    for n, sha in (rec.get("files_sha256") or {}).items():
        if sha256_file(d / n) != sha:
            raise ValueError(f"{d / n} changed after the dataset was written (sha256 differs from dataset.json)")
    return {"record": rec, "tracks": pd.read_parquet(d / "tracks.parquet"), "hits": pd.read_parquet(d / "hits.parquet"),
            "patches": np.load(d / "patches.npy", allow_pickle=False), "dir": d}
