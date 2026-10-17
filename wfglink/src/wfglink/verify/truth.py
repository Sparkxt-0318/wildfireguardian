"""Truth tracks per annotation window from two blind labellers and an adjudicator.

Inputs: a window folder (verify windows) and label CSVs with the columns window_id, k, x,
y, confidence, ember_id, size_class, note (x, y in tile pixels, pixel centres at integers).
A label is sure when its confidence is at least min_confidence (default 0.75: 1.0 sure,
0.5 unsure) or empty. Only windows that both labellers labelled (any row) get truth.

Rules, per window frame k:
1. The two labellers' points are matched one to one (Hungarian, `validate.match`, within
   match_px = 3 px). A pair of sure points agrees: a sure truth point at their mean. A pair
   of unsure points is an unsure point (don't care). An unmatched unsure point is don't care.
2. Disagreements (a pair with one sure and one unsure point, or an unmatched sure point) go
   to the adjudicator. In a window the adjudicator labelled (any row), a disagreement
   matched to an adjudicator point within match_px takes that point's position and
   confidence; one without is rejected (no ember: a prediction there is false); an
   adjudicator point near no labeller point is added with its own confidence. In a window
   the adjudicator did not label, disagreements stay unresolved and are don't care.
3. Identity: points are linked through the ember_id each contributor gave (a labeller's
   ember_id is the same ember in every frame of the window); linked points form one truth
   track. A point without ember_id is a track of its own (unless the other labeller's
   matched point links it), so its ember is rarely observable: sure points without
   ember_id are counted per contributor and window (sure_without_ember_id) and each window
   that has any gets a warning. A track with two points in one frame is ambiguous (the
   labellers linked different embers).
4. A track is observable when it is not ambiguous, has at least min_points (3) sure points
   and at least one point edge_px (4 px) or more inside the tile. Points of other tracks,
   unsure points and points within edge_px of the tile edge are don't care.

Agreement of the labellers: the point F1 of `validate.labels.inter_labeler_f1` (unsure
labels don't care), with a bootstrap over windows, and a track-level F1: each labeller's
tracks (ember IDs with at least min_points sure points) matched one to one by the number
of their matched sure points (at least 2).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from wfglink.verify.windows import LABEL_COLUMNS, WINDOWS_JSON, read_manifest

_EMPTY = {"", "nan", "na", "none", "<na>"}


def read_window_labels(labels) -> Any:
    """Window label rows as a DataFrame (LABEL_COLUMNS); x, y NaN for 'no ember' rows.

    Raises ValueError, naming CSV lines, for rows without window_id, with x, y or
    confidence that is not a number, with only one of x and y, or with a point but no
    integer k, so that no label disappears silently.
    """
    import pandas as pd

    if isinstance(labels, pd.DataFrame):
        df, name, line0 = labels.copy(), "labels", 0
    else:
        p = Path(labels)
        if not p.read_text(encoding="utf-8", errors="replace").strip():
            raise ValueError(f"{p} is empty; a labels file starts with the header {','.join(LABEL_COLUMNS)}")
        df, name, line0 = pd.read_csv(p, dtype=str, keep_default_na=False), str(p), 2
    if "window_id" not in df:
        raise ValueError(f"{name} has no window_id column; the header is {','.join(LABEL_COLUMNS)}")
    for col in LABEL_COLUMNS:
        if col not in df:
            df[col] = ""
    df = df.reset_index(drop=True)

    def txt(col):
        return df[col].map(lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip())

    problems, num = [], {}
    for col in ("x", "y", "confidence", "k"):
        tx = txt(col)
        blank = tx.str.lower().isin(_EMPTY)
        val = pd.to_numeric(tx.where(~blank), errors="coerce")
        bad = ~blank & ~np.isfinite(val.to_numpy(dtype=float))
        problems += [f"line {i + line0}: {col} {tx[i]!r} is not a number" for i in np.flatnonzero(bad)]
        num[col] = val.where(~bad)
    has_pt = num["x"].notna() & num["y"].notna()
    problems += [f"line {i + line0}: only one of x and y given"
                 for i in np.flatnonzero((num["x"].isna() != num["y"].isna()).to_numpy())]
    kk = num["k"].to_numpy(dtype=float)
    bad_k = has_pt.to_numpy() & ~(np.isfinite(kk) & (np.round(kk) == kk))
    problems += [f"line {i + line0}: a point needs an integer k" for i in np.flatnonzero(bad_k)]
    wid = txt("window_id")
    problems += [f"line {i + line0}: no window_id" for i in np.flatnonzero((wid == "").to_numpy())]
    if problems:
        raise ValueError(f"{name}: {len(problems)} rows cannot be read: " + "; ".join(sorted(set(problems))[:10]))
    eid = txt("ember_id")
    out = pd.DataFrame({"window_id": wid, "k": num["k"].astype(float), "x": num["x"].astype(float),
                        "y": num["y"].astype(float), "confidence": num["confidence"].astype(float),
                        "ember_id": pd.Series([None if v.lower() in _EMPTY else v for v in eid], index=eid.index,
                                              dtype=object),
                        "size_class": txt("size_class"), "note": txt("note")})
    return out[LABEL_COLUMNS]


def _ember_id(e) -> str | None:
    """The ember_id as text, or None when it is missing (None, NaN or an empty marker)."""
    if e is None or (isinstance(e, float) and np.isnan(e)):
        return None
    e = str(e).strip()
    return None if e.lower() in _EMPTY else e


class _Union:
    def __init__(self):
        self.parent: dict[Any, Any] = {}

    def find(self, a):
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb, key=str)] = min(ra, rb, key=str)


def _frame_points(df, kk: int, src: str, min_conf: float, w: float, h: float):
    """(positions (n, 2), sure flags, identity nodes, outside count) of one labeller in one frame."""
    from wfglink.validate.labels import _in_tile

    g = df[(df["k"] == kk) & df["x"].notna() & df["y"].notna()]
    p = g[["x", "y"]].to_numpy(float).reshape(-1, 2)
    conf = g["confidence"].to_numpy(float)
    sure = ~(np.isfinite(conf) & (conf < min_conf))
    nodes = [(src, "e", e) if e is not None else (src, "row", int(i))
             for i, e in zip(g.index, map(_ember_id, g["ember_id"]))]
    ok = _in_tile(p, 0.0, 0.0, w, h)
    return p[ok], sure[ok], [n for n, o in zip(nodes, ok) if o], int((~ok).sum())


def _edge_distance(p: np.ndarray, w: float, h: float) -> np.ndarray:
    """Distance (px) of tile points to the tile edge (the outer edge of the border pixels)."""
    return np.minimum.reduce([p[:, 0] + 0.5, w - 0.5 - p[:, 0], p[:, 1] + 0.5, h - 0.5 - p[:, 1]])


def merge_window(a, b, c, K: int, w: float, h: float, adjudicated: bool, match_px: float = 3.0,
                 min_conf: float = 0.75) -> dict[str, Any]:
    """Merged points of one window (rules 1 and 2): points with tile position, k, sure flag,
    source and identity nodes; rejected points; labels outside the tile."""
    from wfglink.validate.match import match_points

    pts: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    outside = 0
    for kk in range(K):
        pa, sa, na, oa = _frame_points(a, kk, "a", min_conf, w, h)
        pb, sb, nb, ob = _frame_points(b, kk, "b", min_conf, w, h)
        outside += oa + ob
        gi, di, _ = match_points(pa, pb, match_px)
        dis: list[dict[str, Any]] = []
        for i, j in zip(gi.tolist(), di.tolist()):
            rec = {"k": kk, "tx": float((pa[i, 0] + pb[j, 0]) / 2), "ty": float((pa[i, 1] + pb[j, 1]) / 2),
                   "nodes": [na[i], nb[j]]}
            if sa[i] and sb[j]:
                pts.append({**rec, "sure": True, "source": "both"})
            elif not sa[i] and not sb[j]:
                pts.append({**rec, "sure": False, "source": "both_unsure"})
            else:
                dis.append({**rec, "reason": "confidence differs"})
        for side, p, s, nn, used in (("a", pa, sa, na, set(gi.tolist())), ("b", pb, sb, nb, set(di.tolist()))):
            for i in range(len(p)):
                if i in used:
                    continue
                rec = {"k": kk, "tx": float(p[i, 0]), "ty": float(p[i, 1]), "nodes": [nn[i]]}
                if s[i]:
                    dis.append({**rec, "reason": f"only {side}"})
                else:
                    pts.append({**rec, "sure": False, "source": f"{side}_unsure"})
        if not adjudicated:
            pts += [{**d, "sure": False, "source": "unadjudicated"} for d in dis]
            continue
        pc, sc, nc, oc = _frame_points(c, kk, "c", min_conf, w, h)
        outside += oc
        dp = np.array([[d["tx"], d["ty"]] for d in dis]).reshape(-1, 2)
        gi, ci, _ = match_points(dp, pc, match_px)
        for i, j in zip(gi.tolist(), ci.tolist()):
            pts.append({"k": kk, "tx": float(pc[j, 0]), "ty": float(pc[j, 1]), "nodes": dis[i]["nodes"] + [nc[j]],
                        "sure": bool(sc[j]), "source": "adjudicated"})
        rejected += [{"k": kk, "tx": d["tx"], "ty": d["ty"], "reason": d["reason"]}
                     for i, d in enumerate(dis) if i not in set(gi.tolist())]
        frame_pts = [q for q in pts if q["k"] == kk]
        for j in range(len(pc)):
            if j in set(ci.tolist()):
                continue
            near = [q for q in frame_pts if np.hypot(q["tx"] - pc[j, 0], q["ty"] - pc[j, 1]) <= match_px]
            if near:
                near[0]["nodes"].append(nc[j])          # the same ember: its identity links too
            else:
                pts.append({"k": kk, "tx": float(pc[j, 0]), "ty": float(pc[j, 1]), "nodes": [nc[j]],
                            "sure": bool(sc[j]), "source": "adjudicator"})
    return {"points": pts, "rejected": rejected, "outside": outside}


def build_tracks(points: list[dict[str, Any]], w: float, h: float, edge_px: float = 4.0, min_points: int = 3
                 ) -> list[dict[str, Any]]:
    """Rules 3 and 4: truth tracks from merged points."""
    uf = _Union()
    for q in points:
        for n in q["nodes"]:
            uf.union(q["nodes"][0], n)
    groups: dict[Any, list[dict[str, Any]]] = {}
    for q in points:
        groups.setdefault(uf.find(q["nodes"][0]), []).append(q)
    tracks = []
    for members in sorted(groups.values(), key=lambda g: (min(q["k"] for q in g), min(q["tx"] for q in g))):
        members = sorted(members, key=lambda q: (q["k"], q["tx"], q["ty"]))
        ks = [q["k"] for q in members]
        ambiguous = len(ks) != len(set(ks))
        p = np.array([[q["tx"], q["ty"]] for q in members]).reshape(-1, 2)
        edge = _edge_distance(p, w, h)
        sure = np.array([q["sure"] for q in members], bool)
        interior = edge >= edge_px
        n_sure = int(sure.sum())
        observable = (not ambiguous) and n_sure >= min_points and bool((sure & interior).any())
        reason = ("" if observable else "ambiguous" if ambiguous else
                  f"fewer than {min_points} sure points" if n_sure < min_points else f"no sure point {edge_px:g} px inside")
        tracks.append({"observable": observable, "ambiguous": ambiguous, "n_points": len(members), "n_sure": n_sure,
                       "reason": reason, "nodes": sorted({"/".join(str(v) for v in n) for q in members for n in q["nodes"]}),
                       "points": [{"k": q["k"], "tx": q["tx"], "ty": q["ty"], "sure": bool(s), "edge": bool(not i),
                                   "dont_care": bool(not (observable and s and i)), "source": q["source"]}
                                  for q, s, i in zip(members, sure, interior)]})
    return tracks


def _labeller_tracks(df, K: int, w: float, h: float, src: str, min_conf: float, min_points: int) -> dict[str, int]:
    """Sure points per ember_id of one labeller in one window (tracks with at least min_points)."""
    n: dict[str, int] = {}
    for kk in range(K):
        _, s, nodes, _ = _frame_points(df, kk, src, min_conf, w, h)
        for node, ok in zip(nodes, s):
            if ok and node[1] == "e":
                n[node[2]] = n.get(node[2], 0) + 1
    return {e: v for e, v in n.items() if v >= min_points}


def _track_agreement(a, b, K: int, w: float, h: float, match_px: float, min_conf: float, min_points: int
                     ) -> tuple[int, int, int]:
    """(matched tracks, tracks of a, tracks of b) in one window."""
    from scipy.optimize import linear_sum_assignment

    from wfglink.validate.match import match_points

    ta = _labeller_tracks(a, K, w, h, "a", min_conf, min_points)
    tb = _labeller_tracks(b, K, w, h, "b", min_conf, min_points)
    if not ta or not tb:
        return 0, len(ta), len(tb)
    ia, ib = {e: i for i, e in enumerate(ta)}, {e: i for i, e in enumerate(tb)}
    shared = np.zeros((len(ta), len(tb)))
    for kk in range(K):
        pa, sa, na, _ = _frame_points(a, kk, "a", min_conf, w, h)
        pb, sb, nb, _ = _frame_points(b, kk, "b", min_conf, w, h)
        ra, rb = np.flatnonzero(sa), np.flatnonzero(sb)
        gi, di, _ = match_points(pa[ra], pb[rb], match_px)
        for i, j in zip(ra[gi].tolist(), rb[di].tolist()):
            ea, eb = na[i], nb[j]
            if ea[1] == "e" and eb[1] == "e" and ea[2] in ia and eb[2] in ib:
                shared[ia[ea[2]], ib[eb[2]]] += 1
    r, c = linear_sum_assignment(-shared)
    return int((shared[r, c] >= 2).sum()), len(ta), len(tb)


def merge_truth(windows_dir: str | Path, labels_a, labels_b, adjudicator=None, match_px: float = 3.0,
                edge_px: float = 4.0, min_points: int = 3, min_confidence: float = 0.75) -> dict[str, Any]:
    """Truth tracks per window (see the module notes). Returns the truth.json record."""
    import pandas as pd

    from wfglink.provenance import now_shanghai, sha256_file
    from wfglink.validate.labels import _match_dont_care, bootstrap_prf

    wdir = Path(windows_dir)
    man = read_manifest(wdir)
    wj = json.loads((wdir / WINDOWS_JSON).read_text(encoding="utf-8")) if (wdir / WINDOWS_JSON).exists() else {}
    a, b = read_window_labels(labels_a), read_window_labels(labels_b)
    c = read_window_labels(adjudicator) if adjudicator is not None else read_window_labels(
        pd.DataFrame(columns=LABEL_COLUMNS))
    known = set(man["window_id"])
    for name, df in (("labeller a", a), ("labeller b", b), ("adjudicator", c)):
        unknown = sorted(set(df["window_id"]) - known)
        if unknown:
            raise ValueError(f"{name} names windows that are not in the manifest: {unknown[:10]}")
        kmax = man.set_index("window_id")["k"]
        bad = df[df["k"].notna() & ((df["k"] < 0) | (df["k"] >= df["window_id"].map(kmax)))]
        if len(bad):
            raise ValueError(f"{name}: k outside the window for {sorted(set(bad['window_id']))[:5]}")
    windows, agree_rows, warnings = [], [], []
    no_id_tot = {"a": 0, "b": 0, "adjudicator": 0}
    for _, wr in man.iterrows():
        wid, K, w, h = wr["window_id"], int(wr["k"]), float(wr["w"]), float(wr["h"])
        frames, times = list(wr["frames"]), list(wr["t"])
        base = {"window_id": wid, "frames": frames, "t": times, "x0": int(wr["x0"]), "y0": int(wr["y0"]),
                "w": int(w), "h": int(h)}
        la, lb = a[a["window_id"] == wid], b[b["window_id"] == wid]
        lc = c[c["window_id"] == wid]
        if not len(la) or not len(lb):
            windows.append({**base, "status": "not_labelled", "labelled_by": [s for s, d in (("a", la), ("b", lb))
                                                                               if len(d)], "tracks": [], "dont_care": []})
            continue
        no_id = {}
        for name, d in (("a", la), ("b", lb), ("adjudicator", lc)):
            n = 0
            for kk in range(K):
                _, s_, nodes, _ = _frame_points(d, kk, name, min_confidence, w, h)
                n += sum(1 for node, ok in zip(nodes, s_) if ok and node[1] == "row")
            no_id[name] = n
            no_id_tot[name] += n
        if any(no_id.values()):
            who = ", ".join(f"{k} {v}" for k, v in no_id.items() if v)
            warnings.append(f"window {wid}: sure points without ember_id ({who}); each is a track of its own "
                            "unless the other labeller links it")
        merged = merge_window(la, lb, lc, K, w, h, bool(len(lc)), match_px, min_confidence)
        tracks = build_tracks(merged["points"], w, h, edge_px, min_points)
        for n, tr in enumerate(tracks):
            tr["truth_id"] = f"{wid}_{n:02d}"
            for p in tr["points"]:
                p.update(frame=frames[p["k"]], t=times[p["k"]], x=p["tx"] + base["x0"], y=p["ty"] + base["y0"])
        dc = [{"k": p["k"], "frame": p["frame"], "t": p["t"], "x": p["x"], "y": p["y"], "truth_id": tr["truth_id"],
               "reason": ("track " + tr["reason"]) if not tr["observable"] else
                         ("unsure" if not p["sure"] else f"within {edge_px:g} px of the tile edge")}
              for tr in tracks for p in tr["points"] if p["dont_care"]]
        rej = [{**r, "frame": frames[r["k"]], "x": r["tx"] + base["x0"], "y": r["ty"] + base["y0"]}
               for r in merged["rejected"]]
        windows.append({**base, "status": "ok", "adjudicated": bool(len(lc)), "tracks": tracks, "dont_care": dc,
                        "rejected": rej, "labels_outside_tile": merged["outside"], "sure_without_ember_id": no_id,
                        "observable_tracks": int(sum(tr["observable"] for tr in tracks))})
        # Agreement of a and b in this window.
        tp = na = nb = 0
        for kk in range(K):
            pa, sa, _, _ = _frame_points(la, kk, "a", min_confidence, w, h)
            pb, sb, _, _ = _frame_points(lb, kk, "b", min_confidence, w, h)
            pairs, dc_a, dc_b = _match_dont_care(pa, sa, pb, sb, match_px)
            tp, na, nb = tp + len(pairs), na + int((sa & ~dc_a).sum()), nb + int((sb & ~dc_b).sum())
        mt, ta, tb = _track_agreement(la, lb, K, w, h, match_px, min_confidence, min_points)
        agree_rows.append({"window_id": wid, "tp": tp, "n_a": na, "n_b": nb, "tracks_matched": mt,
                           "tracks_a": ta, "tracks_b": tb})
    ag = pd.DataFrame(agree_rows, columns=["window_id", "tp", "n_a", "n_b", "tracks_matched", "tracks_a", "tracks_b"])
    pf = bootstrap_prf(ag["tp"], ag["n_b"] - ag["tp"], ag["n_a"] - ag["tp"], 2000, 0, 0.95, 5)
    tm, ta, tb = int(ag["tracks_matched"].sum()), int(ag["tracks_a"].sum()), int(ag["tracks_b"].sum())
    ok = [wd for wd in windows if wd["status"] == "ok"]

    def sha(x):
        return sha256_file(x) if isinstance(x, (str, Path)) else None

    return {
        "schema_version": 1, "created": now_shanghai(), "windows_dir": str(wdir),
        "window_set_id": wj.get("window_set_id"), "clip_id": wj.get("clip_id"), "video_sha256": wj.get("video_sha256"),
        "roi_px": wj.get("roi_px"), "segment_s": wj.get("segment_s"), "manifest_sha256": sha(wdir / "manifest.csv"),
        "labels": {"a": {"path": str(labels_a) if sha(labels_a) else None, "sha256": sha(labels_a)},
                   "b": {"path": str(labels_b) if sha(labels_b) else None, "sha256": sha(labels_b)},
                   "adjudicator": {"path": str(adjudicator) if sha(adjudicator) else None, "sha256": sha(adjudicator)}},
        "rules": {"match_px": match_px, "edge_px": edge_px, "min_points": min_points, "min_confidence": min_confidence,
                  "coordinates": "x, y: ROI crop pixels as in detections.parquet; tx, ty: tile pixels"},
        "windows": windows,
        "totals": {"windows": len(windows), "windows_labelled": len(ok),
                   "tracks": int(sum(len(wd["tracks"]) for wd in ok)),
                   "observable_tracks": int(sum(wd["observable_tracks"] for wd in ok)),
                   "dont_care_points": int(sum(len(wd["dont_care"]) for wd in ok)),
                   "rejected_points": int(sum(len(wd["rejected"]) for wd in ok)),
                   "windows_adjudicated": int(sum(wd["adjudicated"] for wd in ok)),
                   "sure_without_ember_id": no_id_tot},
        "warnings": warnings,
        "agreement": {"point_f1": pf["f1"], "matches": pf["tp"], "points_a": int(ag["n_a"].sum()),
                      "points_b": int(ag["n_b"].sum()), "bootstrap_over": "windows", "ci_note": pf.get("ci_note"),
                      "track_f1": (2 * tm / (ta + tb)) if ta + tb else None, "tracks_matched": tm, "tracks_a": ta,
                      "tracks_b": tb, "per_window": ag.to_dict(orient="records")},
    }


def write_truth(rec: dict[str, Any], out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return out


def load_truth(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
