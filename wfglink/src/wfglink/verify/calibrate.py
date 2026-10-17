"""Calibration and selection of the verifier's operating point (python -m wfglink verify calibrate).

Rules (family A) candidates. From the DEVELOPMENT positives (the dataset's ember tracks,
their window features at the decision moment), for each q of the protocol grid: lower
bounds at the q quantile of snr_med, speed_med, net_disp and straightness, upper bounds at
the 1 - q quantile of hotspot_max, pre_presence_med, bg_grad_med, large_near_max, codec_med
and ctx_change_med, and iqr = the positives' interquartile range (at least IQR_EPS); q = 0
gives the observed minimum and maximum (numpy quantiles over the finite values). A feature
with no finite value among the positives gets no rule (recorded). The sets are in the
overlay format of verify.rules.thresholds.<profile> (scorers.RuleScorer).

Calibration replay. For every calibration recording (an accept_all dump run and its window
truth, verify truth), every candidate is replayed (verify/replay.py, one tracker pass for
all): accept_all (the control, never selected), rules at each q, and patch and temporal at
each seed and each probability threshold of the grid (models from verify train, pinned by
their SHA-256 as the overlay would pin them). Each replay is scored against that recording's
truth with evaluate.track_level (track level, primary rule; the run is first checked against
the truth: same video, segment start, ROI and frame times), and the counts are pooled over
recordings (sums of tp, false, duplicate, judged, observable and matched truth tracks,
weighted false judgments and supported minutes). calibration_points.json holds per point:
family, seed, threshold or q, tp, fp (false plus duplicate), fn, judged, precision, recall,
accepted tracks, false tracks per supported minute, the median confirmation delay
(t_accept - t_confirm over the accepted tracks of all recordings) and the per-recording
counts.

Selection (`select`, the protocol's rule verbatim): among points with precision >= 0.99
choose the highest recall; ties: rules, then temporal, then patch, then lower confirmation
delay. If none reaches 0.99, the highest precision point with recall >= 0.5; if none, the
highest precision point with at least 5 accepted tracks, recording that the target was
missed. If nothing has >= 5 accepted tracks, the selection is INSUFFICIENT_EVIDENCE with the
best available point recorded (the highest precision point with any accepted track). Ties
the rule leaves open are broken by higher precision, then the lower seed, then the
stricter setting (higher q or threshold), so the choice is deterministic.

write_config (--write-config) pins the selected family's setting (and model SHA-256) into
configs/high_precision.yaml for the profile and also the best point of every other family
(the same rule within that family), so each method can run; the file is edited line by
line, so its comments stay. Under a protocol with a precision_review section (amendment 2)
the selection is made by verify select on the blind review (write_reviewed_selection), so
calibrate refuses write_overlay there and writes selection_preview.json only. selection.json
records the selected family, seed, threshold or q, the overlay's SHA-256 after writing, the
model SHA-256, what each pin is at run time (pinned_identity: the rules thresholds_sha256,
the models' SHA-256 and threshold; verify eval --selection checks a sealed run against it),
the SHA-256 of calibration_points.json and the time.

Truth and the protocol. Calibration runs under the frozen protocol (evaluate.load_protocol:
its SHA-256 pinned, the file committed). Every truth file given must be a truth entry of the
protocol (matched by its SHA-256) of the population calibration_selection and not sealed; a
sealed entry, an entry of another population, or a truth of a recording the protocol holds
with another (frozen) truth file is refused (ProtocolError), even in development. A truth of
a recording the protocol does not hold at all is refused unless allow_unfrozen_truth
(development). There is no calibration without a protocol: no method output on a
calibration or test recording is scored before the protocol is frozen. Development
calibrations (allow_unfrozen_truth, an uncommitted protocol) never write the overlay:
write_overlay is refused for them. calibration_points.json and selection.json record the
protocol (path, SHA-256), the matched truth entries and whether the run was development.

Models. A candidate model must come from the dataset given: its sidecar's
training_data_sha256.dataset_json must be the SHA-256 of <dataset>/dataset.json, and with a
train report (train_report.json of verify train) the report must say OK, be of the same
dataset and list the model with this SHA-256; otherwise the candidate is
Unavailable(model_not_from_dataset, train_report_not_ok, train_report_not_of_dataset or
model_not_in_train_report). Seeds whose models are byte-identical (the per-cell cap does not
bind, so the temporal seeds are one model) are calibrated once: the later seed is left out
and listed in duplicate_models. A point records its model's sidecar SHA-256, and
model_nondeterministic when a fit stopped on the wall-time cap.

Every recording's replays must have every buffer hit's patch dumped (missing_patches 0);
otherwise the recording is refused (ReplayError), since the patch and temporal scores would
use all-zero patches.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from wfglink.verify.scorers import RULE_LOWER, RULE_UPPER

RULES_Q = (0.0, 0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3)
MODEL_THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99)
SEEDS = {"patch": (0, 1), "temporal": (0, 1)}
SELECTABLE = ("rules", "temporal", "patch")
FAMILY_RANK = {f: i for i, f in enumerate(SELECTABLE)}
PRECISION_TARGET = 0.99
RECALL_FLOOR = 0.5
MIN_ACCEPTED = 5
IQR_EPS = 1e-6
SELECTED = "SELECTED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
CALIBRATION_POPULATION = "calibration_selection"


# Rules candidates --------------------------------------------------------------------------

def rule_thresholds(positives, q: float) -> tuple[dict[str, Any], list[str]]:
    """The rules threshold set at q from the positives' window features (a DataFrame with the
    WINDOW_NAMES columns), and the features left without a rule."""
    lower, upper, iqr, skipped = {}, {}, {}, []
    for names, side in ((RULE_LOWER, "lower"), (RULE_UPPER, "upper")):
        for n in names:
            v = positives[n].to_numpy(np.float64) if n in positives else np.zeros(0)
            v = v[np.isfinite(v)]
            if not v.size:
                skipped.append(n)
                continue
            thr = float(np.quantile(v, q if side == "lower" else 1.0 - q))
            (lower if side == "lower" else upper)[n] = thr
            q1, q3 = np.quantile(v, [0.25, 0.75])
            iqr[n] = max(float(q3 - q1), IQR_EPS)
    return {"lower": lower, "upper": upper, "iqr": iqr}, skipped


def rule_candidates(positives, grid: Iterable[float] = RULES_Q) -> dict[str, Any]:
    """{q: {"thresholds": ..., "skipped": [...]}} for every q of the grid (keys as strings)."""
    out = {}
    for q in grid:
        th, sk = rule_thresholds(positives, float(q))
        out[_qkey(q)] = {"q": float(q), "thresholds": th, "skipped": sk}
    return out


def _qkey(q: float) -> str:
    return f"{float(q):g}"


# Candidates and scoring ----------------------------------------------------------------------

def _grids(protocol: dict | None) -> tuple[tuple[float, ...], tuple[float, ...], dict[str, tuple[int, ...]]]:
    sel = (protocol or {}).get("selection") or {}
    g = sel.get("grids") or {}
    seeds = sel.get("seeds") or {}
    return (tuple(float(v) for v in g.get("rules_q", RULES_Q)),
            tuple(float(v) for v in g.get("model_threshold", MODEL_THRESHOLDS)),
            {f: tuple(int(s) for s in seeds.get(f, SEEDS[f])) for f in SEEDS})


def protocol_truth(proto: dict[str, Any] | None, recordings: list[tuple[str | Path, str | Path]],
                   allow_unfrozen_truth: bool = False) -> list[dict[str, Any]]:
    """Each recording's truth matched to a calibration_selection entry of the protocol (see the
    module notes); ProtocolError for sealed or other-population truth, or (without
    allow_unfrozen_truth) truth the protocol does not list."""
    from wfglink.provenance import sha256_file
    from wfglink.verify.evaluate import ProtocolError

    t = (proto or {}).get("truth")
    entries = [e for e in (t if isinstance(t, list) else [t]) if isinstance(e, dict)]

    def foreign(e: dict) -> bool:
        return bool(e.get("sealed")) or e.get("population") != CALIBRATION_POPULATION

    out = []
    for run, tp in recordings:
        sha = sha256_file(tp)
        vid = (json.loads(Path(tp).read_text(encoding="utf-8")) or {}).get("video_sha256")
        hit = [e for e in entries if str(e.get("sha256") or "") == sha]
        bad = [e for e in hit if foreign(e)]
        if bad:
            e = bad[0]
            raise ProtocolError(f"{tp} is the protocol's truth of {e.get('recording')!r} in {e.get('population')!r} "
                                f"(sealed {bool(e.get('sealed'))}): calibration uses {CALIBRATION_POPULATION} truth only")
        other = [e for e in entries if vid and e.get("video_sha256") == vid and (foreign(e) or not hit)]
        if other:
            e = other[0]
            raise ProtocolError(f"{tp}: its video is the protocol's recording {e.get('recording')!r} of "
                                f"{e.get('population')!r} (sealed {bool(e.get('sealed'))}), whose frozen truth is "
                                f"another file: only frozen {CALIBRATION_POPULATION} truth is used for calibration")
        if not hit:
            if not allow_unfrozen_truth:
                raise ProtocolError(f"{tp} (SHA-256 {sha[:16]}) is not a {CALIBRATION_POPULATION} truth entry of the "
                                    "frozen protocol: calibration uses frozen calibration truth only "
                                    "(development, for a recording the protocol does not hold: allow_unfrozen_truth, "
                                    "which never writes the overlay)")
            out.append({"run": str(run), "truth": str(tp), "truth_sha256": sha, "frozen": False, "entry": None})
            continue
        e = hit[0]
        out.append({"run": str(run), "truth": str(tp), "truth_sha256": sha, "frozen": True,
                    "entry": {k: e.get(k) for k in ("population", "recording", "sealed", "window_set_id", "path",
                                                    "sha256", "video_sha256", "segment_s")}})
    return out


def model_provenance(path: Path, family: str, seed: int, dataset_sha256: str | None,
                     train_report: dict[str, Any] | None) -> tuple[str | None, dict[str, Any]]:
    """(why the model may not be calibrated, or None; its sidecar SHA-256 and fit notes). A
    missing model file is left to build_scorer (missing_file)."""
    from wfglink.provenance import sha256_file

    if not path.is_file():
        return None, {}
    sp = path.with_suffix(".json")
    if not sp.is_file():
        return "missing_sidecar", {}
    try:
        side = json.loads(sp.read_text(encoding="utf-8"))
    except ValueError:
        return "bad_sidecar", {}
    stopped = (side.get("fit") or {}).get("stopped")
    info = {"sidecar_sha256": sha256_file(sp), "fit_stopped": stopped, "nondeterministic": stopped == "time_cap",
            "trained_on": (side.get("training_data_sha256") or {}).get("dataset_json")}
    if dataset_sha256 is not None and info["trained_on"] != dataset_sha256:
        return "model_not_from_dataset", info
    if train_report is not None:
        if train_report.get("status") != "OK":
            return "train_report_not_ok", info
        if dataset_sha256 is not None and (train_report.get("training_data_sha256") or {}).get("dataset_json") \
                != dataset_sha256:
            return "train_report_not_of_dataset", info
        e = (train_report.get("models") or {}).get(f"{family}_seed{int(seed)}") or {}
        if (e.get("final") or {}).get("sha256") != sha256_file(path):
            return "model_not_in_train_report", info
        info["nondeterministic"] = info["nondeterministic"] or train_report.get("deterministic") is False
    return None, info


def build_candidates(rules: dict[str, Any], models_dir: str | Path, cfg: dict, profile: str,
                     thresholds: Iterable[float] = MODEL_THRESHOLDS, seeds: dict | None = None,
                     families: Iterable[str] = ("accept_all", "rules", "patch", "temporal"),
                     dataset_sha256: str | None = None, train_report: dict[str, Any] | None = None,
                     duplicates: list | None = None) -> dict[str, dict]:
    """name -> {"family", "seed", "param", "scorer", "model_path", "model_sha256", "thresholds",
    "sidecar_sha256", "model_check", "model_nondeterministic"}. dataset_sha256 and
    train_report tie the models to their training data (see the module notes); duplicates
    receives the seeds left out as byte-identical to an earlier seed."""
    from wfglink.provenance import sha256_file
    from wfglink.verify.config import VerifyConfig
    from wfglink.verify.scorers import AcceptAll, RuleScorer, Unavailable, build_scorer
    from wfglink.verify.train import model_path

    vcfg = VerifyConfig.from_cfg(cfg)
    fams = set(families)
    out: dict[str, dict] = {}
    if "accept_all" in fams:
        out["accept_all"] = {"family": "accept_all", "seed": None, "param": None, "scorer": AcceptAll()}
    if "rules" in fams:
        for qk, c in rules.items():
            try:
                sc = RuleScorer(c["thresholds"], vcfg.min_hits)
            except ValueError as exc:
                sc = Unavailable(f"bad_thresholds:{exc}", "rules")
            out[f"rules_q{qk}"] = {"family": "rules", "seed": None, "param": float(c["q"]), "scorer": sc,
                                   "thresholds": c["thresholds"]}
    for fam in ("patch", "temporal"):
        if fam not in fams:
            continue
        seen: dict[str, int] = {}
        for seed in (seeds or SEEDS)[fam]:
            path = model_path(models_dir, profile, fam, seed)
            sha = sha256_file(path) if path.is_file() else None
            why, info = model_provenance(path, fam, int(seed), dataset_sha256, train_report)
            if why is None and sha is not None:
                if sha in seen:
                    if duplicates is not None:
                        duplicates.append({"family": fam, "seed": int(seed), "same_as_seed": seen[sha], "sha256": sha,
                                           "note": "byte-identical to an earlier seed's model: calibrated once"})
                    continue
                seen[sha] = int(seed)
            for thr in thresholds:
                if why is not None:
                    sc = Unavailable(why, fam)
                else:
                    spec = {"path": str(path), "sha256": sha, "threshold": float(thr)}
                    v = VerifyConfig.from_cfg({**cfg, "verify": {**cfg["verify"], "method": fam,
                                                                 "models": {fam: {profile: spec}}}})
                    sc = build_scorer(v, profile)
                out[f"{fam}_seed{seed}_t{float(thr):g}"] = {
                    "family": fam, "seed": int(seed), "param": float(thr), "scorer": sc, "model_path": str(path),
                    "model_sha256": sha, "sidecar_sha256": info.get("sidecar_sha256"), "model_check": why,
                    "model_nondeterministic": bool(info.get("nondeterministic"))}
    return out


def check_run_against_truth(dump, truth: dict[str, Any]) -> None:
    """The dump run analysed the truth windows' video, segment and ROI, with their frame times."""
    import pandas as pd

    from wfglink.verify.evaluate import TIME_TOL_S, ProtocolError, check_frame_times

    inp = dump.summary.get("input") or {}
    if truth.get("video_sha256") and inp.get("sha256") != truth["video_sha256"]:
        raise ProtocolError(f"{dump.run_dir}: the run analysed another video than the truth windows show")
    seg = truth.get("segment_s")
    start = float((inp.get("segment_s") or [0.0])[0] or 0.0)
    if seg and abs(float(seg[0] or 0.0) - start) > TIME_TOL_S:
        raise ProtocolError(f"{dump.run_dir}: the run starts at {start:g} s, the windows' segment at {seg[0]:g} s")
    if truth.get("roi_px") and inp.get("roi_px") and [int(v) for v in truth["roi_px"]] != [int(v) for v in
                                                                                         inp["roi_px"]]:
        raise ProtocolError(f"{dump.run_dir}: the run's ROI {inp['roi_px']} differs from the windows' {truth['roi_px']}")
    fr = pd.read_parquet(Path(dump.run_dir) / "frames.parquet")
    check_frame_times(truth, dict(zip(fr["frame"].astype(int), fr["t"].astype(float))))


def _counts(tl: dict[str, Any]) -> dict[str, Any]:
    c = tl["counts"]
    r = tl["rates"]["false_tracks_per_min"]
    return {"tp": c["tp"], "false": c["false"], "duplicate": c["duplicate"], "dont_care": c["dont_care"],
            "judged": c["judged"], "truth_observable": c["truth_observable"], "truth_matched": c["truth_matched"],
            "false_weighted": float(r.get("weighted_count") or 0.0), "minutes": float(tl["rates"]["supported_minutes"])}


ACCEPTED_COLUMNS = ["point_id", "family", "seed", "param", "recording", "run_dir", "track_id", "frame_accept",
                    "t_accept", "t_confirm", "revoked", "supported"]


def accepted_rows_of(decisions, unsupported_frames: set[int], base: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per track ever accepted in a replay's decisions (state method_accepted, or
    revoked): base (point_id, family, seed, param, recording, run_dir) plus the track, its
    acceptance and supported (its acceptance frame is not motion_unsupported in the dump's
    hp_frames)."""
    if not len(decisions):
        return []
    d = decisions
    ever = d[(d["state"].astype(str) == "method_accepted") | d["revoked"].astype(bool)]
    return [{**base, "track_id": int(row["track_id"]), "frame_accept": int(row["frame_accept"]),
             "t_accept": float(row["t_accept"]), "t_confirm": float(row["t_confirm"]),
             "revoked": bool(row["revoked"]), "supported": int(row["frame_accept"]) not in unsupported_frames}
            for _, row in ever.iterrows()]


def score_recordings(recordings: list[tuple[str | Path, str | Path]], candidates: dict[str, dict], cfg: dict,
                     profile: str, protocol: dict | None = None, progress=None,
                     recording_info: list | None = None, accepted_rows: list | None = None) -> list[dict[str, Any]]:
    """Replay every candidate on every recording, score each against its truth, pool (see the
    module notes). Returns the calibration points; recording_info receives per recording its
    replay notes and missing_patches; accepted_rows receives one row per track a candidate ever
    accepted (the population the blind precision review samples; accepted_rows_of)."""
    from wfglink.verify.evaluate import track_level
    from wfglink.verify.replay import ReplayError, confirmation_delays, load_dump, predictions, replay_many
    from wfglink.verify.truth import load_truth

    per: dict[str, list[dict]] = {n: [] for n in candidates}
    delays: dict[str, list[np.ndarray]] = {n: [] for n in candidates}
    for run_dir, truth_path in recordings:
        truth = load_truth(truth_path)
        dump = load_dump(run_dir)
        check_run_against_truth(dump, truth)
        res = replay_many(dump, {n: c["scorer"] for n, c in candidates.items()}, cfg, profile,
                          progress=(lambda i, n, r=run_dir: progress(str(r), i, n)) if progress else None)
        missing = max((r.missing_patches for r in res.values()), default=0)
        if recording_info is not None:
            recording_info.append({"run": str(run_dir), "truth": str(truth_path), "missing_patches": int(missing),
                                   "notes": list(dump.notes)})
        if missing:
            raise ReplayError(f"{run_dir}: {missing} buffer hits have no dumped patch, so the replayed patch and "
                              "temporal scores would use all-zero patches (a damaged or foreign dump): refused")
        hf = dump.hp_frames
        unsup = set(hf.loc[hf["motion_unsupported"].astype(bool), "frame"].astype(int))
        for name, r in res.items():
            if accepted_rows is not None:
                c = candidates[name]
                accepted_rows += accepted_rows_of(r.decisions, unsup, {
                    "point_id": name, "family": c["family"], "seed": c.get("seed"), "param": c.get("param"),
                    "recording": str(truth.get("clip_id") or Path(run_dir).name), "run_dir": str(run_dir)})
            pred = predictions(dump, r)
            tl = track_level(truth, pred["points"], pred["crossings"], pred["unsupported_frames"], protocol, None,
                             pred["revoked_ids"])
            per[name].append({"recording": str(run_dir), "truth": str(truth_path), "accepted_tracks":
                              pred["accepted_tracks"], "missing_patches": int(r.missing_patches), **_counts(tl)})
            delays[name].append(confirmation_delays(r))
    points = []
    for name, c in candidates.items():
        rows = per[name]
        tot = {k: sum(r[k] for r in rows) for k in ("tp", "false", "duplicate", "dont_care", "judged",
                                                     "truth_observable", "truth_matched", "accepted_tracks")}
        fw, mins = sum(r["false_weighted"] for r in rows), sum(r["minutes"] for r in rows)
        n_primary = tot["tp"] + tot["false"] + tot["duplicate"]
        d = np.concatenate(delays[name]) if delays[name] else np.zeros(0)
        sc = c["scorer"]
        points.append({
            "name": name, "family": c["family"], "seed": c.get("seed"),
            "q" if c["family"] == "rules" else "threshold": c.get("param"),
            "available": bool(getattr(sc, "available", True)), "unavailable": getattr(sc, "reason", None),
            "tp": tot["tp"], "fp": tot["false"] + tot["duplicate"], "false": tot["false"],
            "duplicate": tot["duplicate"], "fn": tot["truth_observable"] - tot["truth_matched"],
            "judged": tot["judged"], "truth_observable": tot["truth_observable"],
            "precision": tot["tp"] / n_primary if n_primary else None,
            "recall": tot["truth_matched"] / tot["truth_observable"] if tot["truth_observable"] else None,
            "accepted_tracks": tot["accepted_tracks"],
            "false_tracks_per_min": fw / mins if mins > 0 else None, "supported_minutes": mins,
            "median_confirmation_delay_s": float(np.median(d)) if d.size else None,
            "model_path": c.get("model_path"), "model_sha256": c.get("model_sha256"),
            "sidecar_sha256": c.get("sidecar_sha256"), "model_check": c.get("model_check"),
            "model_nondeterministic": bool(c.get("model_nondeterministic")),
            "per_recording": rows})
    return points


# Selection --------------------------------------------------------------------------------

def _param(p: dict[str, Any]) -> float:
    v = p.get("q") if p.get("family") == "rules" else p.get("threshold")
    return float(v) if v is not None else 0.0


def _delay(p: dict[str, Any]) -> float:
    d = p.get("median_confirmation_delay_s")
    return float(d) if d is not None else math.inf


def _tie(p: dict[str, Any]) -> tuple:
    """Family order (rules, temporal, patch), lower delay, higher precision, lower seed, stricter setting."""
    return (FAMILY_RANK.get(p["family"], 99), _delay(p), -(p.get("precision") or 0.0),
            p.get("seed") if p.get("seed") is not None else -1, -_param(p))


def select(points: list[dict[str, Any]], families: Iterable[str] = SELECTABLE) -> dict[str, Any]:
    """The protocol's selection rule (see the module notes) over the points of `families`."""
    fams = set(families)
    pts = [p for p in points if p.get("family") in fams]
    defined = [p for p in pts if p.get("precision") is not None]
    top = [p for p in defined if p["precision"] >= PRECISION_TARGET and p.get("recall") is not None]
    if top:
        best = min(top, key=lambda p: (-p["recall"], *_tie(p)))
        return {"status": SELECTED, "branch": "precision_target_met", "target_missed": False, "point": best,
                "rule": f"precision >= {PRECISION_TARGET}: highest recall"}
    rec = [p for p in defined if p.get("recall") is not None and p["recall"] >= RECALL_FLOOR]
    if rec:
        best = min(rec, key=lambda p: (-p["precision"], *_tie(p)))
        return {"status": SELECTED, "branch": "recall_floor", "target_missed": True, "point": best,
                "rule": f"no point reaches precision {PRECISION_TARGET}: highest precision with recall >= {RECALL_FLOOR}"}
    many = [p for p in defined if (p.get("accepted_tracks") or 0) >= MIN_ACCEPTED]
    if many:
        best = min(many, key=lambda p: (-p["precision"], *_tie(p)))
        return {"status": SELECTED, "branch": "min_accepted", "target_missed": True, "point": best,
                "rule": f"no point reaches precision {PRECISION_TARGET} nor recall {RECALL_FLOOR}: highest precision "
                        f"with at least {MIN_ACCEPTED} accepted tracks; the target was missed"}
    any_acc = [p for p in defined if (p.get("accepted_tracks") or 0) > 0]
    best = min(any_acc, key=lambda p: (-p["precision"], -(p.get("accepted_tracks") or 0), *_tie(p))) if any_acc \
        else None
    return {"status": INSUFFICIENT, "branch": "insufficient_evidence", "target_missed": True, "point": None,
            "best_available": best, "rule": f"no point has at least {MIN_ACCEPTED} accepted tracks"}


def family_bests(points: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    """Per selectable family: the selection rule within that family (its best available point
    when the rule finds none)."""
    out = {}
    for f in SELECTABLE:
        s = select(points, (f,))
        out[f] = s["point"] if s["point"] is not None else s.get("best_available")
    return out


# Writing the overlay -----------------------------------------------------------------------

def _scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        r = repr(float(v))
        if not math.isfinite(float(v)):
            raise ValueError("thresholds must be finite")
        if "e" in r and "." not in r.split("e")[0]:
            m, e = r.split("e")
            r = f"{m}.0e{e}"
        return r
    return json.dumps(str(v))


def flow(v) -> str:
    """A YAML flow mapping or scalar (keys bare, strings quoted, floats always with a dot)."""
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {flow(x)}" for k, x in v.items()) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(flow(x) for x in v) + "]"
    return _scalar(v)


def _replace_line(lines: list[str], section: str, key: str, value: str) -> None:
    """Replace the value of `key:` inside the `section:` block of the verify overlay (one line),
    keeping its indentation and trailing comment."""
    sec = None
    for i, ln in enumerate(lines):
        if re.match(rf"^\s+{re.escape(section)}:\s*(#.*)?$", ln):
            sec = i
            break
    if sec is None:
        raise ValueError(f"the overlay has no `{section}:` block")
    ind = len(lines[sec]) - len(lines[sec].lstrip())
    for j in range(sec + 1, len(lines)):
        ln = lines[j]
        if ln.strip() and not ln.lstrip().startswith("#") and len(ln) - len(ln.lstrip()) <= ind:
            break
        m = re.match(rf"^(\s+{re.escape(key)}:)(\s*)(.*?)(\s+#.*)?$", ln)
        if m:
            lines[j] = f"{m.group(1)} {value}{m.group(4) or ''}"
            return
    raise ValueError(f"the overlay has no `{section}.{key}` line")


def _rel(path: str | Path) -> str:
    from wfglink import PROJECT_ROOT

    p = Path(path).resolve()
    try:
        return str(p.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(p)


def write_config(overlay: str | Path, profile: str, pins: dict[str, dict[str, Any]],
                 rules_candidates: dict[str, Any]) -> dict[str, Any]:
    """Pin rules thresholds and model settings for `profile` into the overlay file (other
    profiles kept, comments kept). pins: family -> point (rules: its q; models: path, sha256,
    threshold). Returns what was written."""
    import yaml

    p = Path(overlay)
    text = p.read_text(encoding="utf-8")
    cur = (yaml.safe_load(text) or {}).get("verify") or {}
    lines = text.splitlines()
    written: dict[str, Any] = {}
    if pins.get("rules") is not None:
        q = float(pins["rules"]["q"])
        th = rules_candidates[_qkey(q)]["thresholds"]
        every = dict((cur.get("rules") or {}).get("thresholds") or {})
        every[profile] = th
        _replace_line(lines, "rules", "thresholds", flow(every))
        _replace_line(lines, "rules", "q", _scalar(q))
        written["rules"] = {"q": q, "thresholds": th}
    for fam in ("patch", "temporal"):
        pt = pins.get(fam)
        if pt is None:
            continue
        if not pt.get("model_sha256"):
            raise ValueError(f"{fam}: the selected point has no model SHA-256 to pin")
        per = dict(((cur.get("models") or {}).get(fam)) or {})
        per[profile] = {"path": _rel(pt["model_path"]), "sha256": pt["model_sha256"], "threshold": float(pt["threshold"])}
        _replace_line(lines, "models", fam, flow(per))
        written[fam] = per[profile]
    new = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    back = (yaml.safe_load(new) or {}).get("verify") or {}
    if "rules" in written and back["rules"]["thresholds"][profile] != written["rules"]["thresholds"]:
        raise AssertionError("the written rules thresholds do not read back")
    for fam in ("patch", "temporal"):
        if fam in written and back["models"][fam][profile] != written[fam]:
            raise AssertionError(f"the written {fam} model settings do not read back")
    p.write_text(new, encoding="utf-8")
    return written


# Driver -----------------------------------------------------------------------------------

def calibrate(dataset_dir: str | Path, models_dir: str | Path, recordings: list[tuple[str, str]], out_dir: str | Path,
              cfg: dict, profile: str = "file_native", protocol: str | Path | None = None,
              protocol_sha256: str | None = None, write_overlay: bool = False, overlay: str | Path | None = None,
              families=("accept_all", "rules", "patch", "temporal"), train_report: str | Path | None = None,
              allow_unfrozen_truth: bool = False, require_clean: bool = True, command_line: str | None = None,
              progress=None) -> dict[str, Any]:
    """Candidates, calibration replays, calibration_points.json, the selection and (with
    write_overlay) the pinned overlay and selection.json (see the module notes). protocol and
    protocol_sha256: the frozen protocol and its pinned SHA-256 (evaluate.load_protocol; with
    require_clean, as committed)."""
    from wfglink.provenance import git_state, now_shanghai, sha256_file
    from wfglink.verify.config import OVERLAY
    from wfglink.verify.dataset import load_dataset
    from wfglink.verify.evaluate import ProtocolError, load_protocol
    from wfglink.verify.replay import feature_settings_sha256

    development = bool(allow_unfrozen_truth or not require_clean)
    if protocol is None:
        raise ProtocolError("calibration runs under the frozen protocol: give it and its SHA-256 (verify calibrate "
                            "--protocol --sha256); no method output on a calibration or test recording is scored "
                            "before the protocol is frozen")
    if write_overlay and development:
        raise ProtocolError("the overlay is pinned only by a calibration under the committed frozen protocol whose "
                            f"{CALIBRATION_POPULATION} entries hold every truth given (no development options)")
    proto = load_protocol(protocol, protocol_sha256, require_clean)
    if write_overlay and proto.get("precision_review"):
        raise ProtocolError("this protocol has a precision_review section (amendment 2): the selection is made on the "
                            "blind accepted-track review by verify select, which writes selection.json and pins the "
                            "overlay; verify calibrate writes selection_preview.json only (run it without "
                            "--write-config)")
    matched = protocol_truth(proto, recordings, allow_unfrozen_truth)
    proto_rec = {"path": proto["_path"], "sha256": proto["_sha256"], "name": proto.get("name"),
                 "committed": bool(require_clean)}
    dev_note = ("development calibration (truth of a recording the protocol does not hold, or an uncommitted "
                "protocol): not a selection; the overlay is not written") if development else ""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    qs, thresholds, seeds = _grids(proto)
    ds = load_dataset(dataset_dir)
    ds_sha = sha256_file(Path(dataset_dir) / "dataset.json")
    rep = rep_rec = None
    if train_report is not None:
        rep = json.loads(Path(train_report).read_text(encoding="utf-8"))
        rep_rec = {"path": str(train_report), "sha256": sha256_file(train_report), "status": rep.get("status"),
                   "deterministic": rep.get("deterministic")}
    pos = ds["tracks"][ds["tracks"]["label"] == 1]
    rules = rule_candidates(pos, qs)
    (out / "rules_candidates.json").write_text(json.dumps(
        {"profile": profile, "positives": int(len(pos)), "dataset": str(dataset_dir), "dataset_json_sha256": ds_sha,
         "note": "from development positives (agent labels, PROVISIONAL)", "candidates": rules}, indent=2),
        encoding="utf-8")
    dups: list[dict[str, Any]] = []
    cands = build_candidates(rules, models_dir, cfg, profile, thresholds, seeds, families, ds_sha, rep, dups)
    rinfo: list[dict[str, Any]] = []
    acc_rows: list[dict[str, Any]] = []
    points = score_recordings(recordings, cands, cfg, profile, proto, progress, rinfo, acc_rows)
    import pandas as pd

    acc_path = out / "calibration_accepted.parquet"
    pd.DataFrame(acc_rows, columns=ACCEPTED_COLUMNS).to_parquet(acc_path, index=False)
    common = {"protocol": proto_rec, "truth_entries": matched, "development": development,
              "development_note": dev_note, "dataset": {"path": str(dataset_dir), "dataset_json_sha256": ds_sha},
              "train_report": rep_rec, "duplicate_models": dups, "feature_settings_sha256": feature_settings_sha256(cfg)}
    cp = {"schema_version": 1, "created": now_shanghai(), "profile": profile, "recordings": [
          {"run": str(r), "truth": str(t), "truth_sha256": sha256_file(t)} for r, t in recordings],
          "replays": rinfo, **common,
          "grids": {"rules_q": list(qs), "model_threshold": list(thresholds), "seeds": {k: list(v) for k, v in
                                                                                    seeds.items()}},
          "scoring": "evaluate.track_level, primary rule, pooled over recordings", "points": points,
          "accepted_tracks_table": {"path": str(acc_path), "sha256": sha256_file(acc_path)},
          "command_line": command_line, **git_state()}
    cp_path = out / "calibration_points.json"
    cp_path.write_text(json.dumps(cp, indent=2, default=str), encoding="utf-8")
    sel = select(points)
    bests = family_bests(points)
    rec = {"schema_version": 1, "created": now_shanghai(), "profile": profile, **_sel_summary(sel),
           "family_bests": {f: _brief(p) for f, p in bests.items()}, **common,
           "calibration_points": str(cp_path), "calibration_points_sha256": sha256_file(cp_path),
           "labels": "calibration recordings, agent-annotated windows: PROVISIONAL",
           "rule_note": ("the window-truth selection rule of the first draft; protocol amendment 2 selects on the blind "
                         "accepted-track review instead (verify select), so this record is kept for comparison only"),
           **git_state()}
    warn = [f"{p['name']}: a fit of this model stopped on the wall-time cap (not reproducible byte for byte)"
            for p in [sel["point"], *bests.values()] if p is not None and p.get("model_nondeterministic")]
    if warn:
        rec["warnings"] = sorted(set(warn))
    if write_overlay:
        ov = Path(overlay) if overlay else OVERLAY
        pins = dict(bests)
        if sel["point"] is not None:
            pins[sel["point"]["family"]] = sel["point"]
        pins = {f: p for f, p in pins.items() if p is not None and (f == "rules" or p.get("model_sha256"))}
        rec["pinned"] = write_config(ov, profile, pins, rules)
        rec["pinned_identity"] = pinned_identity(rec["pinned"], pins, cfg)
        rec["overlay"] = str(ov)
        rec["overlay_sha256"] = sha256_file(ov)
        (out / "selection.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    else:
        (out / "selection_preview.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return rec


def pinned_identity(written: dict[str, Any], pins: dict[str, dict[str, Any]], cfg: dict) -> dict[str, Any]:
    """What each pin is at run time, as hp_summary's scorer reports it: the rules
    thresholds_sha256 (scorers.RuleScorer.identity), a model's SHA-256, sidecar SHA-256 and
    threshold."""
    from wfglink.verify.config import VerifyConfig
    from wfglink.verify.scorers import RuleScorer

    out: dict[str, Any] = {}
    for fam, w in written.items():
        if fam == "rules":
            out[fam] = RuleScorer(w["thresholds"], VerifyConfig.from_cfg(cfg).min_hits).identity()
        else:
            out[fam] = {"method": fam, "model_sha256": w["sha256"], "threshold": float(w["threshold"]),
                        "sidecar_sha256": (pins.get(fam) or {}).get("sidecar_sha256")}
    return out


def _brief(p: dict[str, Any] | None) -> dict[str, Any] | None:
    if p is None:
        return None
    keys = ("name", "family", "seed", "q", "threshold", "precision", "recall", "tp", "fp", "fn", "accepted_tracks",
            "false_tracks_per_min", "median_confirmation_delay_s", "model_path", "model_sha256", "sidecar_sha256",
            "model_nondeterministic")
    return {k: p.get(k) for k in keys if k in p}


def _sel_summary(sel: dict[str, Any]) -> dict[str, Any]:
    p = sel["point"]
    out = {"status": sel["status"], "branch": sel["branch"], "target_missed": sel["target_missed"],
           "rule": sel["rule"], "selected": _brief(p)}
    if p is not None:
        out.update(family=p["family"], seed=p.get("seed"), q=p.get("q"), threshold=p.get("threshold"),
                   model_sha256=p.get("model_sha256"))
    else:
        out["best_available"] = _brief(sel.get("best_available"))
    return out


# Selection under protocol amendment 2 (reviewed precision, proposal retention) ---------------

REVIEW_TRUE = ("ember",)
REVIEW_FALSE = ("fixture_light", "reflection", "flame_glare_edge", "moving_non_ember", "codec_artifact", "overlay_text",
                "duplicate_fragment")
REVIEW_AMBIGUOUS = ("faint_possible_ember", "unclear")
REVIEW_ALIASES = {"true_ember": "ember"}
MIN_REVIEWED_DEFINED = 10        # reviewed true + false accepted tracks for a point's precision to be defined
MIN_OBSERVABLE_FOR_RECALL = 20   # observable calibration truth tracks for window recall to rank the points
FAMILY_TIE = {"rules": 0, "temporal": 1, "patch": 2}
REVIEWED_RULE = "amendment_2_reviewed_precision"   # selection.json rule of verify select (evaluate.check_selection)
BOOTSTRAP_N, BOOTSTRAP_SEED = 2000, 0


def review_counts(categories: list[str | None]) -> dict[str, int]:
    """true, false, ambiguous and unresolved counts of a point's reviewed accepted tracks. None
    and the empty string are unresolved, true_ember is read as ember; any other category outside
    the true, false and ambiguous sets is a ValueError."""
    out = {"true": 0, "false": 0, "ambiguous": 0, "unresolved": 0}
    for c in categories:
        if c is None or (isinstance(c, str) and not c.strip()):
            out["unresolved"] += 1
            continue
        c = REVIEW_ALIASES.get(c, c)
        if c in REVIEW_TRUE:
            out["true"] += 1
        elif c in REVIEW_FALSE:
            out["false"] += 1
        elif c in REVIEW_AMBIGUOUS:
            out["ambiguous"] += 1
        else:
            raise ValueError(f"review category {c!r} is not one of the protocol's categories (true {REVIEW_TRUE}, "
                             f"false {REVIEW_FALSE}, ambiguous {REVIEW_AMBIGUOUS}, or none for unresolved)")
    return out


def cluster_bootstrap_precision(counts: list[tuple[int, int]], n: int = BOOTSTRAP_N,
                                seed: int = BOOTSTRAP_SEED) -> dict[str, Any]:
    """Recording-cluster bootstrap of reviewed precision: the recordings' (true, false) reviewed
    counts resampled with replacement, n replicates (numpy default_rng(seed)); the percentile
    95 percent interval and the one-sided 5th percentile over the replicates whose precision is
    defined (true + false > 0); the undefined replicates are counted."""
    c = np.asarray(counts, dtype=np.int64).reshape(-1, 2)
    out: dict[str, Any] = {"cluster": "recording", "recordings": int(len(c)), "replicates": int(n), "seed": int(seed)}
    if not len(c):
        return {**out, "defined": 0, "undefined": int(n), "interval95": None, "lower05": None}
    idx = np.random.default_rng(seed).integers(0, len(c), size=(int(n), len(c)))
    t, f = c[idx, 0].sum(axis=1), c[idx, 1].sum(axis=1)
    ok = t + f > 0
    p = t[ok] / (t[ok] + f[ok])
    return {**out, "defined": int(ok.sum()), "undefined": int((~ok).sum()),
            "interval95": [float(np.percentile(p, 2.5)), float(np.percentile(p, 97.5))] if p.size else None,
            "lower05": float(np.percentile(p, 5)) if p.size else None}


def reviewed_metrics(counts: dict[str, int], accepted: int, supported_min: float) -> dict[str, Any]:
    """Reviewed precision (primary, optimistic, pessimistic with unresolved as false), its exact
    one-sided 95 percent lower bound, the inclusion probability and the false and true-ember
    rates per supported minute (scaled by the inclusion probability)."""
    from scipy import stats

    t, f, a, u = counts["true"], counts["false"], counts["ambiguous"], counts["unresolved"]
    shown = t + f + a + u
    incl = shown / accepted if accepted else None
    prec = t / (t + f) if t + f else None
    low = None if t + f == 0 else (0.0 if t == 0 else float(stats.beta.ppf(0.05, t, f + 1)))
    rate = accepted / supported_min if supported_min else None
    out = {**counts, "reviewed": shown, "accepted_tracks": int(accepted), "inclusion_probability": incl,
           "precision": prec, "precision_defined": t + f >= MIN_REVIEWED_DEFINED, "precision_lower95": low,
           "precision_optimistic": (t + a) / (t + f + a) if t + f + a else None,
           "precision_pessimistic": t / shown if shown else None,
           "accepted_per_supported_min": rate,
           "false_per_supported_min": (f / incl) / supported_min if incl and supported_min else None,
           "false_per_supported_min_upper95": ((float(stats.chi2.ppf(0.95, 2 * (f + 1)) / 2) / incl) / supported_min
                                               if incl and supported_min else None),
           "true_yield_per_supported_min": prec * rate if prec is not None and rate is not None else None}
    return out


def select_reviewed(points: list[dict[str, Any]], reviewed: dict[str, dict[str, Any]],
                    observable: int) -> dict[str, Any]:
    """The protocol's selection rule (amendment 2): precision is the reviewed precision when
    defined; the ranking basis is window recall when the calibration truth has at least
    MIN_OBSERVABLE_FOR_RECALL observable tracks, otherwise proposal retention (true-ember yield
    over accept_all's), a development aid that never stands for ember recall. Proposal
    retention is measurable only when accept_all's reviewed precision is defined (and its
    yield is above zero); otherwise it is None for every point. With no defined precision the
    status is INSUFFICIENT_EVIDENCE: no point, and best_available the point with the most
    reviewed true tracks."""
    use_window = observable >= MIN_OBSERVABLE_FOR_RECALL
    base = next((reviewed.get(p["name"]) for p in points if p["family"] == "accept_all"), None)
    y0 = base.get("true_yield_per_supported_min") if base and base.get("precision_defined") else None
    measurable = bool(y0)
    rows = []
    for p in points:
        r = reviewed.get(p["name"])
        if r is None:
            continue
        retention = (r["true_yield_per_supported_min"] / y0 if measurable and r["true_yield_per_supported_min"]
                     is not None else None)
        rows.append({**p, "reviewed": r, "proposal_retention": retention,
                     "rank_recall": p.get("recall") if use_window else retention})
    cand = [x for x in rows if x["family"] in FAMILY_TIE and x.get("available", True)]
    defined = [x for x in cand if x["reviewed"]["precision_defined"]]

    def delay(x):
        d = x.get("median_confirmation_delay_s")
        return d if d is not None else 1e9

    def by_recall(x):
        rr = x["rank_recall"] if x["rank_recall"] is not None else -1.0
        return (-rr, FAMILY_TIE[x["family"]], delay(x), -x["reviewed"]["precision"], x["name"])

    def by_precision(x):
        return (-x["reviewed"]["precision"], FAMILY_TIE[x["family"]], delay(x), x["name"])

    basis = "window recall" if use_window else "proposal retention"
    ranked = use_window or measurable
    best_available = None
    top = [x for x in defined if x["reviewed"]["precision"] >= 0.99]
    if top:
        best = sorted(top, key=by_recall)[0]
        branch = (f"reviewed precision >= 0.99: highest {basis}" if ranked else
                  "reviewed precision >= 0.99: proposal retention is not measurable, so the tie order decides (rules, "
                  "temporal, patch, then lower confirmation delay)")
    else:
        half = [x for x in defined if x["rank_recall"] is not None and x["rank_recall"] >= 0.5]
        if half:
            best = sorted(half, key=by_precision)[0]
            branch = f"no point reaches reviewed precision 0.99: highest reviewed precision with {basis} >= 0.5"
        elif defined:
            best = sorted(defined, key=by_precision)[0]
            branch = (f"no point reaches reviewed precision 0.99 nor {basis} >= 0.5: highest defined reviewed "
                      "precision; target missed" if ranked else
                      "no point reaches reviewed precision 0.99 and proposal retention is not measurable: highest "
                      "defined reviewed precision; target missed")
        else:
            best = None
            best_available = min(cand, key=lambda x: (-x["reviewed"]["true"], FAMILY_TIE[x["family"]], x["name"])) \
                if cand else None
            branch = ("no point has defined reviewed precision: INSUFFICIENT_EVIDENCE, nothing is selected; "
                      f"best_available is the point with the most reviewed true tracks (ranking basis {basis})")
    if use_window:
        recall_basis = (f"window recall (window truth over {int(observable)} observable calibration truth tracks, at "
                        f"least {MIN_OBSERVABLE_FOR_RECALL})")
    elif measurable:
        recall_basis = "proposal retention (development selection aid; not ember recall)"
    else:
        recall_basis = ("proposal retention not measurable: accept_all has no defined reviewed precision (or no "
                        "true-ember yield), so it is None for every point; a development selection aid, not ember "
                        "recall, and ember recall was not measurable on calibration either")
    out = {"status": "SELECTED" if best is not None else "INSUFFICIENT_EVIDENCE", "branch": branch, "point": best,
           "rows": rows, "recall_basis": recall_basis, "ranking_basis": basis, "proposal_retention_measurable":
           measurable, "observable_calibration_truth_tracks": int(observable),
           "target_missed": not (best is not None and best["reviewed"]["precision"] >= 0.99)}
    if best is None:
        out["best_available"] = best_available
    return out


def write_reviewed_selection(cal_dir: str | Path, reviewed_path: str | Path, cfg: dict, protocol: str | Path,
                             protocol_sha256: str | None, write_overlay: bool = False,
                             overlay: str | Path | None = None, require_clean: bool = True,
                             command_line: str | None = None) -> dict[str, Any]:
    """selection.json under protocol amendment 2: select_reviewed on a calibration's points and
    the blind review's per-point figures (reviewed_path: review_points.json of
    scripts/precision_review.py score, {"population", "accepted_sha256", "points": {point name:
    reviewed_metrics}}), the same rule within each family for the other pins, and
    (write_overlay) the overlay pins as calibrate writes them. The review must be of the
    calibration population and sampled from this calibration's accepted-track table (its
    accepted_sha256 is calibration_points.json accepted_tracks_table.sha256); otherwise
    ProtocolError. rule is REVIEWED_RULE; with no selected point, best_available is recorded and
    nothing is pinned for it."""
    from wfglink.provenance import git_state, now_shanghai, sha256_file
    from wfglink.verify.config import OVERLAY
    from wfglink.verify.evaluate import ProtocolError, load_protocol

    proto = load_protocol(protocol, protocol_sha256, require_clean)
    cal = Path(cal_dir)
    cp_path = cal / "calibration_points.json"
    cp = json.loads(cp_path.read_text(encoding="utf-8"))
    if cp.get("protocol", {}).get("sha256") != proto["_sha256"]:
        raise ProtocolError("the calibration was not made under this protocol")
    if write_overlay and cp.get("development"):
        raise ProtocolError("a development calibration never pins the overlay")
    review = json.loads(Path(reviewed_path).read_text(encoding="utf-8"))
    if review.get("population") != "calibration":
        raise ProtocolError(f"{reviewed_path} is a review of the {review.get('population')!r} population: the "
                            "selection uses the calibration review only")
    want = (cp.get("accepted_tracks_table") or {}).get("sha256")
    if not want or review.get("accepted_sha256") != want:
        raise ProtocolError(f"{reviewed_path} was not sampled from this calibration's accepted-track table (its "
                            f"accepted_sha256 {str(review.get('accepted_sha256'))[:16]} is not calibration_points.json "
                            f"accepted_tracks_table.sha256 {str(want)[:16]}): refused")
    reviewed = review["points"]
    points = cp["points"]
    observable = max((int(p.get("truth_observable") or 0) for p in points), default=0)
    sel = select_reviewed(points, reviewed, observable)
    bests = {}
    for fam in SELECTABLE:
        s = select_reviewed([p for p in points if p["family"] in (fam, "accept_all")], reviewed, observable)
        bests[fam] = s["point"]

    def brief(x):
        if x is None:
            return None
        return {**_brief(x), "reviewed": x.get("reviewed"), "proposal_retention": x.get("proposal_retention")}

    rec = {"schema_version": 1, "created": now_shanghai(), "profile": cp.get("profile"), "status": sel["status"],
           "branch": sel["branch"], "target_missed": sel["target_missed"], "recall_basis": sel["recall_basis"],
           "observable_calibration_truth_tracks": sel["observable_calibration_truth_tracks"],
           "ranking_basis": sel["ranking_basis"], "proposal_retention_measurable": sel["proposal_retention_measurable"],
           "rule": REVIEWED_RULE,
           "rule_text": "protocol amendment 2 (selection.rule): reviewed precision; proposal retention only ranks",
           "selected": brief(sel["point"]), "family_bests": {f: brief(p) for f, p in bests.items()},
           "points": [{"name": x["name"], "family": x["family"], "reviewed": x["reviewed"],
                       "proposal_retention": x["proposal_retention"], "window_precision": x.get("precision"),
                       "window_recall": x.get("recall"), "accepted_tracks": x.get("accepted_tracks")}
                      for x in sel["rows"]],
           "protocol": {"path": proto["_path"], "sha256": proto["_sha256"]},
           "calibration_points": str(cp_path), "calibration_points_sha256": sha256_file(cp_path),
           "review_points": str(reviewed_path), "review_points_sha256": sha256_file(reviewed_path),
           "review_population": review.get("population"), "accepted_sha256": review.get("accepted_sha256"),
           "labels": "agent-only review and window annotation: PROVISIONAL", "command_line": command_line,
           **git_state()}
    p = sel["point"]
    if p is not None:
        rec.update(family=p["family"], seed=p.get("seed"), q=p.get("q"), threshold=p.get("threshold"),
                   model_sha256=p.get("model_sha256"))
    else:
        rec["best_available"] = brief(sel.get("best_available"))
    if write_overlay:
        rules = json.loads((cal / "rules_candidates.json").read_text(encoding="utf-8"))["candidates"]
        pins = dict(bests)
        if p is not None:
            pins[p["family"]] = p
        pins = {f: x for f, x in pins.items() if x is not None and (f == "rules" or x.get("model_sha256"))}
        ov = Path(overlay) if overlay else OVERLAY
        rec["pinned"] = write_config(ov, cp.get("profile") or "file_native", pins, rules)
        rec["pinned_identity"] = pinned_identity(rec["pinned"], pins, cfg)
        rec["overlay"] = str(ov)
        rec["overlay_sha256"] = sha256_file(ov)
    name = "selection.json" if write_overlay else "selection_reviewed_preview.json"
    (cal / name).write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return rec
