"""Scoring a run against window truth under a frozen protocol (verify eval).

Protocol. A JSON file frozen before scoring (verify freeze) and pinned by its SHA-256:
  {"schema_version": 1, "name": ..., "sealed": true or false,
   "truth": {"path": "truth.json" (relative to the protocol's folder, or absolute), "sha256": ...},
   "targets": {"precision": 0.95, "recall_min": null, "false_tracks_per_min_max": null,
               "false_crossings_per_min_max": null},
   optional "method" and "profile" (a run of another method or profile is refused; a legacy
   run has the method "legacy" and no profile), and optional settings overriding DEFAULTS
   (frame_match_px, frame_sensitivity_px, track, bootstrap, alpha)}
`load_protocol` refuses a SHA-256 that differs from the pinned one and, unless told
otherwise, a protocol file that git does not hold committed and unchanged; a sealed protocol
is always held to that (no development override). A sealed protocol is scored once: the
first scoring creates two locks with exclusive create before anything is computed (so a
crash also uses it up): sealed_test_scored.json next to the protocol and
results/validation/sealed_scored/<protocol SHA-256>.json in the project, so a copy of the
protocol in another folder is refused too. Any later scoring is refused.

Frozen protocols (verify freeze) are YAML (.yaml or .yml, read with yaml.safe_load; any
other suffix is JSON) with the draft's own keys; `normalise_protocol` maps their targets
(accepted_track_precision -> precision, accepted_track_recall -> recall_min,
false_accepted_tracks_per_min -> false_tracks_per_min_max, false_crossings_per_min ->
false_crossings_per_min_max) and takes name from run_id. Their truth is a list, one entry per
recording ({population, recording, sealed, video_sha256, segment_s, path, sha256, ...}):
evaluate_run scores a run against the entry of its video and segment start (or the one named
by recording), and the entry's sealed flag decides the lock; a sealed entry's locks carry its
recording (sealed_test_scored_<recording>.json, <protocol SHA-256>_<recording>.json), so each
sealed recording is scored once. The sealed recordings are one test, scored with one scorer:
the first sealed scoring under a protocol records the run's scorer identity (scorer_identity:
method, profile, overlay, verify section and model or thresholds SHA-256, threshold, and the
selection.json SHA-256 when one is given) in sealed_test_identity.json next to the protocol
and <protocol SHA-256>_identity.json in the project, and a later sealed recording whose run
has another identity is refused before its lock is taken. With selection (verify eval
--selection, the committed selection.json of verify calibrate), the run must be the selected
one: the selected family as its method, the overlay SHA-256 the selection pinned, and the
selected model SHA-256 and threshold (patch, temporal) or thresholds SHA-256 (rules).

Inputs (`load_predictions`). A high-precision run must hold, in high_precision/,
hp_summary.json, hp_decisions.parquet (state, track_id, revoked), hp_events.parquet
(track_id or key, t, x, y), hp_frames.parquet (frame and a boolean motion_unsupported) and
frame_level/detections.parquet; a missing piece is refused, never replaced by legacy data.
Predictions are the tracks ever accepted: state method_accepted, or revoked (accepted, then
flagged static: they were drawn and counted while accepted). The measured points of a
predicted track are used, also those before its acceptance; a revoked track's points end at
its revocation (hp_decisions t_decision, the time of its latest transition), as a legacy
static track's end at its flag frame, so accept_all predicts the legacy tracks point for
point. A variant without the revoked tracks is reported. A legacy run's predictions are what the
booth draws: every track in track_points, a static one only up to the frame its static flag
was set (the tracker's test replayed, audit.static_flag_frames, with the track settings of
the config given, by default configs/default.yaml; whether that config is the run's is
recorded); a static track the replay cannot place is left out and counted. Legacy runs hold
no crossing times, so their false crossing rate is unavailable. `evaluate_run` checks
before scoring that the run analysed the windows' video, from the same segment start, with
the same ROI, and that every frame of every labelled window is in the run's frames.parquet
with the window's time (within 1e-6 s).

Frame level (`frame_level`). Per window frame, the predictions' points (a pseudo-run's
detections.parquet) are matched one to one to the sure truth points (Hungarian within
frame_match_px, 3 px; 5 px as a sensitivity check) with unsure, edge and non-observable
points don't care, exactly as validate.labels.score_labels does within a tile.

Track level (`track_level`). A predicted track is judged in a window when it has at least
track.min_points (2) measured points inside the window's space-time box (its frames,
inside the tile). A predicted point matches a truth point of the same frame within
max(track.base_px, track.streak_frac x L) (4 px, 0.5, L the predicted streak length). A
predicted and a truth track are co-located when they share at least min(min_shared (2),
the truth track's frames) matched frames and at least min_shared_frac (50%) of their joint
frames (frames where both have a point). Co-located pairs with observable truth are
matched one to one (Hungarian, most matched frames). An unmatched judged prediction is a
duplicate when it is co-located with a matched truth track (false in the primary
precision, left out in the fragment-tolerant one), don't care when it is co-located with
a non-observable or ambiguous truth track or when at least half of its points in the box
lie on don't-care points, and false otherwise. Recall = matched observable truth tracks /
observable truth tracks: rejections and abstentions are misses. Fragmentation (truth
tracks co-located with more than one prediction) and ID switches (changes of the
prediction nearest to a truth track from frame to frame) are reported separately.

Rates over footage. Window w samples a space-time box: its frames' time span (duration d_w
= last minus first frame time plus one frame interval dt_w, the box running from half an
interval before the first frame to half an interval after the last) times its tile's share
a_w of the ROI area. Supported minutes M = sum over windows outside camera-motion time of
d_w x a_w / 60 (full-frame minutes). Every numerator counts only what lies inside the boxes,
so each rate estimates the whole footage's rate without a bias from track lifetimes:
- false-track occupancy, seconds per minute: sum over supported windows and the tracks
  judged false there of (frames with a point in the box) x dt_w, divided by M;
- false gate crossings per minute: crossing events (t, x, y) of a track judged false in a
  window that lie inside that window's box, divided by M (exact Poisson bounds);
- false accepted tracks per minute: a track of lifetime L (last minus first point time)
  overlaps a box of duration d with a chance proportional to d + L, so each judgment of a
  false track in a supported window is weighted d_w / (d_w + L) (time-inclusion
  correction), and the sum is divided by M. Its bounds are exact Poisson bounds of the
  number of judgments scaled by their mean weight (the weights taken as fixed). The spatial
  extent of a moving false track is not corrected; that leans high (conservative).
Each count rate also reports zero_event_upper, the upper bound that zero events give over
M (about 3.0 / M at alpha 0.05): a rate target below it cannot PASS with these windows,
and status_notes says so.

Uncertainty and status. Precision and recall get exact Clopper-Pearson one-sided bounds
(level 1 - alpha, alpha 0.05; validate.metrics.clopper_pearson at 1 - 2 alpha) and a
percentile bootstrap over windows (2000 replicates, seed 0). `status`: PASSED only when
the point estimate and the one-sided lower bound both meet the target; FAILED when the
one-sided upper bound is below it (or the estimate is undefined); otherwise
INSUFFICIENT_EVIDENCE (mirrored for rates, where lower is better). capability_passed needs
a precision target, a defined precision and every given target PASSED; with no accepted
prediction precision is None and capability_passed is False.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from wfglink import PROJECT_ROOT

LOCK_NAME = "sealed_test_scored.json"
IDENTITY_NAME = "sealed_test_identity.json"
SEALED_DIR = PROJECT_ROOT / "results" / "validation" / "sealed_scored"   # one lock per protocol SHA-256
SCORER_KEYS = ("overlay_sha256", "verify_sha256", "model_sha256", "sidecar_sha256", "thresholds_sha256", "threshold")
TIME_TOL_S = 1e-6
PASSED, FAILED, INSUFFICIENT = "PASSED", "FAILED", "INSUFFICIENT_EVIDENCE"
DEFAULTS: dict[str, Any] = {
    "frame_match_px": 3.0, "frame_sensitivity_px": 5.0,
    "track": {"min_points": 2, "base_px": 4.0, "streak_frac": 0.5, "min_shared": 2, "min_shared_frac": 0.5,
              "dont_care_frac": 0.5},
    "bootstrap": {"n": 2000, "seed": 0}, "alpha": 0.05,
}
NOT_SCORABLE = ("unavailable", "not_real_time")      # high-precision run statuses a sealed test refuses


class ProtocolError(ValueError):
    """The protocol cannot be used: wrong hash, not committed, already scored, or inconsistent inputs."""


# Protocol -------------------------------------------------------------------------------

def git_clean(path: str | Path) -> bool | None:
    """True when git holds the file committed and unchanged, False when it is untracked or
    changed, None when it is not in a git working tree. Read-only git commands only."""
    p = Path(path).resolve()
    try:
        tracked = subprocess.run(["git", "-C", str(p.parent), "ls-files", "--error-unmatch", "--", p.name],
                                 capture_output=True, text=True)
        if tracked.returncode != 0:
            inside = subprocess.run(["git", "-C", str(p.parent), "rev-parse", "--is-inside-work-tree"],
                                    capture_output=True, text=True)
            return False if inside.returncode == 0 else None
        st = subprocess.run(["git", "-C", str(p.parent), "status", "--porcelain", "--", p.name],
                            capture_output=True, text=True, check=True)
        return not st.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def load_protocol(path: str | Path, expect_sha256: str | None, require_clean: bool = True) -> dict[str, Any]:
    """The protocol, after its SHA-256 and its git state are checked (see the module notes)."""
    from wfglink.provenance import sha256_file

    p = Path(path)
    if not p.is_file():
        raise ProtocolError(f"no protocol at {p}")
    if not expect_sha256:
        raise ProtocolError("the protocol's SHA-256 must be given (it is pinned when the protocol is frozen)")
    sha = sha256_file(p)
    if sha != expect_sha256.strip().lower():
        raise ProtocolError(f"the protocol's SHA-256 is {sha[:16]}, not the pinned {expect_sha256[:16]}: refused")
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        import yaml

        proto = yaml.safe_load(text)
    else:
        proto = json.loads(text)
    if not isinstance(proto, dict):
        raise ProtocolError(f"{p} does not hold a protocol mapping")
    proto = normalise_protocol(proto)
    if proto.get("sealed") and not require_clean:
        raise ProtocolError("a sealed protocol is scored only as committed; the development override "
                            "(--allow-dirty) is refused for it")
    if require_clean:
        clean = git_clean(p)
        if clean is not True:
            raise ProtocolError(f"{p} is {'not in a git working tree' if clean is None else 'not committed or changed'}"
                                "; a protocol is scored only as committed")
    proto["_path"], proto["_sha256"] = str(p), sha
    return proto


TARGET_ALIASES = {"accepted_track_precision": "precision", "accepted_track_recall": "recall_min",
                  "false_accepted_tracks_per_min": "false_tracks_per_min_max",
                  "false_crossings_per_min": "false_crossings_per_min_max"}


def normalise_protocol(proto: dict[str, Any]) -> dict[str, Any]:
    """A frozen protocol's draft keys in the shape scoring reads (see the module notes); the
    keys scoring already reads are kept as they are."""
    t = dict(proto.get("targets") or {})
    for a, b in TARGET_ALIASES.items():
        if a in t and b not in t:
            t[b] = t[a]
    if t:
        proto["targets"] = t
    if "name" not in proto and proto.get("run_id"):
        proto["name"] = proto["run_id"]
    return proto


def pick_truth(proto: dict[str, Any], run_dir: str | Path, recording: str | None = None) -> dict[str, Any]:
    """The truth entry of a list-form protocol for this run (its video and segment start), or
    the one named by recording."""
    entries = [e for e in (proto.get("truth") or []) if isinstance(e, dict)]
    if recording is not None:
        entries = [e for e in entries if str(e.get("recording")) == str(recording)]
        if not entries:
            raise ProtocolError(f"the protocol has no truth for recording {recording!r}")
    summary_p = Path(run_dir) / "summary.json"
    inp = (json.loads(summary_p.read_text(encoding="utf-8")).get("input") or {}) if summary_p.is_file() else {}
    start = float((inp.get("segment_s") or [0.0])[0] or 0.0)
    match = [e for e in entries if e.get("video_sha256") == inp.get("sha256")
             and abs(float((e.get("segment_s") or [0.0])[0] or 0.0) - start) <= TIME_TOL_S]
    if not match:
        raise ProtocolError("the protocol pins no truth for this run's video and segment start")
    if len(match) > 1:
        raise ProtocolError(f"{len(match)} truth entries fit this run ({', '.join(str(e.get('recording')) for e in match)}"
                            "): name one with recording")
    return match[0]


def settings(proto: dict[str, Any] | None = None) -> dict[str, Any]:
    """DEFAULTS overridden by the protocol's settings."""
    from wfglink.config import deep_merge

    keys = ("frame_match_px", "frame_sensitivity_px", "track", "bootstrap", "alpha")
    return deep_merge(DEFAULTS, {k: v for k, v in (proto or {}).items() if k in keys})


def lock_paths(proto: dict[str, Any]) -> tuple[Path, Path]:
    """(the lock next to the protocol, the project's lock for the protocol's SHA-256); for an entry
    of a list-form protocol, both carry the entry's recording."""
    rec = proto.get("_recording")
    if rec:
        tag = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(rec))
        return (Path(proto["_path"]).parent / f"{Path(LOCK_NAME).stem}_{tag}.json",
                Path(SEALED_DIR) / f"{proto['_sha256']}_{tag}.json")
    return Path(proto["_path"]).parent / LOCK_NAME, Path(SEALED_DIR) / f"{proto['_sha256']}.json"


def sealed_used(proto: dict[str, Any]) -> Path | None:
    """The first lock that exists for this protocol, or None."""
    return next((p for p in lock_paths(proto) if p.exists()), None)


def scorer_identity(info: dict[str, Any], selection_sha256: str | None = None) -> dict[str, Any]:
    """What one sealed test binds every sealed recording to: a high-precision run's method,
    profile and scorer hashes (hp_summary scorer), or a legacy run's config_sha256; and the
    selection.json SHA-256 when one was given."""
    if info.get("source") == "legacy":
        ident: dict[str, Any] = {"method": "legacy", "config_sha256": info.get("config_sha256")}
    else:
        sc = info.get("scorer") or {}
        ident = {"method": info.get("method"), "profile": info.get("profile"), **{k: sc.get(k) for k in SCORER_KEYS}}
    ident["selection_sha256"] = selection_sha256
    return json.loads(json.dumps(ident, sort_keys=True, default=str))


def identity_paths(proto: dict[str, Any]) -> tuple[Path, Path]:
    """(the identity record next to the protocol, the project's for the protocol's SHA-256)."""
    return Path(proto["_path"]).parent / IDENTITY_NAME, Path(SEALED_DIR) / f"{proto['_sha256']}_identity.json"


def _identity_differs(have: dict[str, Any], want: dict[str, Any]) -> list[str]:
    return sorted(k for k in set(have) | set(want) if have.get(k) != want.get(k))


def bind_identity(proto: dict[str, Any], identity: dict[str, Any], run_dir: str | Path) -> list[Path]:
    """The first sealed scoring under a list-form protocol records its scorer identity; a later
    one with another identity is refused (ProtocolError). Returns the identity records made."""
    from wfglink.provenance import now_shanghai

    def check(p: Path) -> None:
        have = (json.loads(p.read_text(encoding="utf-8")) or {}).get("identity") or {}
        diff = _identity_differs(have, identity)
        if diff:
            raise ProtocolError(f"{p}: the sealed test was started with another scorer ({', '.join(diff)} differ, first "
                                f"{have.get('method')!r}, now {identity.get('method')!r}); every sealed recording is "
                                "scored with the scorer of the first: refused")

    paths = identity_paths(proto)
    for p in paths:
        if p.exists():
            check(p)
    rec = {"protocol": proto["_path"], "protocol_sha256": proto["_sha256"], "identity": identity,
           "first_recording": proto.get("_recording"), "first_run_dir": str(run_dir), "created": now_shanghai()}
    made = []
    for p in reversed(paths):                       # the project's record first: it also covers copies
        if p.exists():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(p, "x", encoding="utf-8") as f:
                json.dump(rec, f, indent=2)
        except FileExistsError:
            check(p)
            continue
        made.append(p)
    return made


def check_selection(path: str | Path, info: dict[str, Any], require_clean: bool = True) -> dict[str, Any]:
    """The run is the one selection.json selected (see the module notes); returns its record."""
    from wfglink.provenance import sha256_file

    p = Path(path)
    if not p.is_file():
        raise ProtocolError(f"no selection at {p}")
    if require_clean and git_clean(p) is not True:
        raise ProtocolError(f"{p} is not committed or changed: the selection is used only as committed")
    sel = json.loads(p.read_text(encoding="utf-8"))
    fam = sel.get("family")
    if sel.get("status") != "SELECTED" or not fam:
        raise ProtocolError(f"the selection chose no method (status {sel.get('status')!r}): nothing to score")
    if info.get("method") != fam:
        raise ProtocolError(f"the selection chose {fam!r}, the run's method is {info.get('method')!r}")
    if sel.get("profile") and info.get("profile") != sel["profile"]:
        raise ProtocolError(f"the selection is for profile {sel['profile']!r}, the run's is {info.get('profile')!r}")
    sc = info.get("scorer") or {}
    if sel.get("overlay_sha256") and sc.get("overlay_sha256") != sel["overlay_sha256"]:
        raise ProtocolError("the run's overlay SHA-256 is not the one the selection pinned")
    if fam in ("patch", "temporal"):
        if sc.get("model_sha256") != sel.get("model_sha256"):
            raise ProtocolError("the run's model SHA-256 is not the selected model's")
        if sel.get("threshold") is None or sc.get("threshold") is None or \
                abs(float(sc["threshold"]) - float(sel["threshold"])) > 1e-12:
            raise ProtocolError(f"the run's threshold {sc.get('threshold')} is not the selected {sel.get('threshold')}")
    want = ((sel.get("pinned_identity") or {}).get(fam) or {}).get("thresholds_sha256")
    if fam == "rules" and want and sc.get("thresholds_sha256") != want:
        raise ProtocolError("the run's rules thresholds are not the ones the selection pinned")
    return {"path": str(p), "sha256": sha256_file(p), "family": fam, "seed": sel.get("seed"), "q": sel.get("q"),
            "threshold": sel.get("threshold"), "model_sha256": sel.get("model_sha256")}


def claim_sealed(proto: dict[str, Any], run_dir: str | Path, identity: dict[str, Any] | None = None) -> list[Path]:
    """Create both sealed-test locks (exclusively) or refuse when either exists; for an entry of
    a list-form protocol, first bind (or check) the sealed test's scorer identity."""
    from wfglink.provenance import git_state, now_shanghai

    used = sealed_used(proto)
    if used is not None:
        raise ProtocolError(f"{used} exists: the sealed test was scored already (a second scoring is refused)")
    if proto.get("_recording"):
        if identity is None:
            raise ProtocolError("a sealed recording of a list-form protocol is scored only with the run's scorer identity")
        bind_identity(proto, identity, run_dir)
    rec = {"status": "started", "protocol": proto["_path"], "protocol_sha256": proto["_sha256"],
           "recording": proto.get("_recording"), "identity": identity,
           "run_dir": str(run_dir), "started": now_shanghai(), **git_state()}
    made = []
    for p in reversed(lock_paths(proto)):            # the project's lock first: it also covers copies
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(p, "x", encoding="utf-8") as f:
                json.dump(rec, f, indent=2)
        except FileExistsError:
            raise ProtocolError(f"{p} exists: the sealed test was scored already (a second scoring is refused)") from None
        made.append(p)
    return made


# Inputs ---------------------------------------------------------------------------------

def _need(cond: bool, what: str) -> None:
    if not cond:
        raise ProtocolError(f"a high-precision run needs {what}; it is missing or has another shape (no fallback "
                            "to legacy data)")


def load_predictions(run_dir: str | Path, cfg: dict | None = None) -> dict[str, Any]:
    """Predictions of a run folder (see the module notes): points (track_id, frame, t, x, y,
    length), frame-level detections, crossing events (track_id, t, x, y) or None,
    camera-motion frames, frame times, revoked track IDs and the run's identity."""
    import pandas as pd

    from wfglink.provenance import sha256_file
    from wfglink.validate.plausibility import read_table

    run = Path(run_dir)
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    pts = read_table(run, "track_points", summary)
    hp = run / "high_precision"
    inp = summary.get("input") or {}
    out: dict[str, Any] = {"video_sha256": inp.get("sha256"), "unsupported_frames": None,
                           "segment_start": float((inp.get("segment_s") or [0.0])[0] or 0.0),
                           "roi_px": inp.get("roi_px"), "duplicate_frames": set(), "revoked_ids": set(),
                           "frame_t": None, "notes": []}
    frames_tab = read_table(run, "frames", summary)
    if frames_tab is not None and len(frames_tab):
        out["frame_t"] = dict(zip(frames_tab["frame"].astype(int), frames_tab["t"].astype(float)))
        if "duplicate" in frames_tab:
            out["duplicate_frames"] = set(frames_tab.loc[frames_tab["duplicate"].astype(bool), "frame"].astype(int))
    if (hp / "hp_decisions.parquet").exists():
        _need((hp / "hp_summary.json").is_file(), "high_precision/hp_summary.json")
        hs = json.loads((hp / "hp_summary.json").read_text(encoding="utf-8"))
        dec = pd.read_parquet(hp / "hp_decisions.parquet")
        _need({"state", "track_id", "revoked"} <= set(dec.columns),
              "hp_decisions.parquet with the columns state, track_id and revoked")
        ever = (dec["state"].astype(str) == "method_accepted") | dec["revoked"].astype(bool)
        acc = dec[ever]
        if "epoch" in acc and acc["epoch"].nunique() > 1:
            raise ProtocolError("decisions from more than one epoch: file-mode scoring expects one")
        ids = set(acc["track_id"].astype(int))
        out["revoked_ids"] = set(acc.loc[acc["revoked"].astype(bool), "track_id"].astype(int))
        keep = None
        if out["revoked_ids"] and pts is not None and len(pts):
            # A revoked track was a prediction until its revocation (t_decision): the same cut as
            # a legacy static track's at its flag frame.
            _need("t_decision" in dec, "hp_decisions.parquet with t_decision (when a revoked track was revoked)")
            t_rev = acc.loc[acc["revoked"].astype(bool)].set_index("track_id")["t_decision"].astype(float)
            cut = pts["track_id"].astype(int).map(t_rev).to_numpy(float)
            keep = ~(pts["t"].to_numpy(float) >= cut - 1e-9)       # NaN (not revoked) keeps every point
        ev_p, fr_p, det_p = hp / "hp_events.parquet", hp / "hp_frames.parquet", hp / "frame_level" / "detections.parquet"
        _need(ev_p.is_file(), "high_precision/hp_events.parquet")
        e = pd.read_parquet(ev_p)
        _need(("track_id" in e or "key" in e) and {"t", "x", "y"} <= set(e.columns),
              "hp_events.parquet with track_id (or key) and the event's t, x, y")
        tid = e["track_id"] if "track_id" in e else e["key"] % 10 ** 9
        out["crossings"] = pd.DataFrame({"track_id": tid.astype(np.int64), "t": e["t"].astype(float),
                                         "x": e["x"].astype(float), "y": e["y"].astype(float)})
        _need(fr_p.is_file(), "high_precision/hp_frames.parquet")
        f = pd.read_parquet(fr_p)
        _need("frame" in f and "motion_unsupported" in f and (not len(f) or f["motion_unsupported"].dtype == bool),
              "hp_frames.parquet with frame and a boolean motion_unsupported")
        out["unsupported_frames"] = set(f.loc[f["motion_unsupported"].astype(bool), "frame"].astype(int))
        _need(det_p.is_file(), "high_precision/frame_level/detections.parquet")
        out["detections"] = pd.read_parquet(det_p)
        out["source"] = "high_precision"
        out["decisions"] = dec
        out["run_info"] = {"source": "high_precision", **{k: hs.get(k) for k in ("mode", "method", "profile", "status",
                                                                                 "status_reason")},
                           "scorer": hs.get("scorer"), "hp_summary_sha256": sha256_file(hp / "hp_summary.json"),
                           "predicted_tracks": len(ids), "revoked_tracks": len(out["revoked_ids"])}
    else:
        from wfglink.config import load_config
        from wfglink.outputs.process import _legacy_cfg
        from wfglink.provenance import sha256_json
        from wfglink.verify.audit import static_flag_frames

        cfg = cfg or load_config()
        out["source"] = "legacy"
        out["detections"] = read_table(run, "detections", summary)
        out["crossings"] = None
        out["notes"].append("legacy runs hold no crossing times: the false crossing rate is unavailable")
        ids, keep = set(), None
        n_static = n_placed = 0
        if pts is not None and len(pts):
            ids = set(pts["track_id"].astype(int))
            static = pts["static"].astype(bool) if "static" in pts else pd.Series(False, index=pts.index)
            stat_ids = set(pts.loc[static, "track_id"].astype(int))
            n_static = len(stat_ids)
            if stat_ids:
                an = frames_tab
                if an is not None and "duplicate" in an:
                    an = an[~an["duplicate"].astype(bool)]
                ftimes = (an["frame"].to_numpy(np.int64), an["t"].to_numpy(float)) if an is not None else None
                t0 = float(an["t"].iloc[0]) if an is not None and len(an) else 0.0
                flag = static_flag_frames(pts, cfg, inp.get("fps"), t0, ftimes)
                n_placed = len(flag)
                ids -= stat_ids - set(flag)
                sf = pts["track_id"].astype(int).map(flag)
                keep = ~static | (sf.notna() & (pts["frame"].astype(float) < sf))
        out["run_info"] = {"source": "legacy", "method": "legacy", "profile": None,
                           "config_sha256": summary.get("config_sha256"),
                           "config_matches_run": (sha256_json(_legacy_cfg(cfg)) == summary.get("config_sha256")
                                                  if summary.get("config_sha256") else None),
                           "static_tracks": n_static, "static_kept_until_flag": n_placed,
                           "static_left_out": n_static - n_placed}
        if out["run_info"]["config_matches_run"] is False:
            out["notes"].append("the config given is not the run's (config_sha256 differs): the static replay uses "
                                "its track settings")
    if pts is None or not len(pts):
        out["points"] = pd.DataFrame(columns=["track_id", "frame", "t", "x", "y", "length"])
    else:
        sel = pts["track_id"].isin(ids) & ~pts["coasted"].astype(bool)
        if keep is not None:
            sel &= keep
        p = pts[sel]
        out["points"] = pd.DataFrame({"track_id": p["track_id"].astype(int), "frame": p["frame"].astype(int),
                                      "t": p["t"].astype(float), "x": p["x_meas"].astype(float),
                                      "y": p["y_meas"].astype(float), "length": p["length"].astype(float)})
    return out


def check_frame_times(truth: dict[str, Any], frame_t: dict[int, float] | None, tol: float = TIME_TOL_S) -> None:
    """Every frame of every labelled window is in the run with the window's time, or ProtocolError."""
    if frame_t is None:
        raise ProtocolError("the run has no frames table: its frame naming cannot be checked against the windows")
    for w in _windows(truth):
        for f, t in zip(w["frames"], w["t"]):
            rt = frame_t.get(int(f))
            if rt is None:
                raise ProtocolError(f"window {w['window_id']}: frame {f} is not in the run")
            if abs(float(rt) - float(t)) > tol:
                raise ProtocolError(f"window {w['window_id']}: frame {f} has t = {rt!r} in the run but {t!r} in the "
                                    "windows; the run and the windows name frames differently")


# Frame level ----------------------------------------------------------------------------

def _windows(truth: dict[str, Any]) -> list[dict[str, Any]]:
    return [w for w in truth["windows"] if w.get("status") == "ok"]


def frame_level(truth: dict[str, Any], detections, radius: float = 3.0, n_boot: int = 2000, seed: int = 0,
                skip_frames: Iterable[int] = ()) -> dict[str, Any]:
    """Point precision, recall and F1 of predicted points in the windows' frames (see the module notes).

    skip_frames: frames the run skipped as repeats (no prediction can exist there); left out."""
    import pandas as pd

    from wfglink.validate.labels import _in_tile, _match_dont_care, bootstrap_prf

    by_frame = ({int(k): g[["x", "y"]].to_numpy(float) for k, g in detections.groupby("frame")}
                if detections is not None and len(detections) else {})
    skip = set(int(f) for f in skip_frames)
    rows = []
    for w in _windows(truth):
        x0, y0, ww, hh = w["x0"], w["y0"], w["w"], w["h"]
        tp = fp = fn = dc = 0
        for k, f in enumerate(w["frames"]):
            if int(f) in skip:
                continue
            tpts = [(p["x"], p["y"], not p["dont_care"]) for tr in w["tracks"] for p in tr["points"] if p["k"] == k]
            pts = np.array([q[:2] for q in tpts], float).reshape(-1, 2)
            sure = np.array([q[2] for q in tpts], bool)
            d = by_frame.get(int(f), np.zeros((0, 2)))
            d = d[_in_tile(d, x0, y0, ww, hh, radius)]
            inside = _in_tile(d, x0, y0, ww, hh)
            pairs, dc_det, _ = _match_dont_care(d, np.ones(len(d), bool), pts, sure, radius)
            matched = np.zeros(len(d), bool)
            matched[pairs[:, 0]] = True
            tp += len(pairs)
            fp += int((inside & ~matched & ~dc_det).sum())
            fn += int(sure.sum()) - len(pairs)
            dc += int((inside & dc_det).sum())
        rows.append({"window_id": w["window_id"], "tp": tp, "fp": fp, "fn": fn, "dont_care": dc})
    df = pd.DataFrame(rows, columns=["window_id", "tp", "fp", "fn", "dont_care"])
    res = bootstrap_prf(df["tp"], df["fp"], df["fn"], n_boot, seed, 0.95, 5)
    res.update(radius_px=radius, dont_care=int(df["dont_care"].sum()), bootstrap_over="windows",
               per_window=df.to_dict(orient="records"))
    return res


# Track level ----------------------------------------------------------------------------

def _colocation(pred: dict[int, tuple[float, float, float]], truth_pts: dict[int, tuple[float, float]],
                s: dict[str, Any]) -> tuple[int, int]:
    """(matched frames, joint frames) of a predicted and a truth track."""
    joint = matched = 0
    for f, (tx, ty) in truth_pts.items():
        p = pred.get(f)
        if p is None:
            continue
        joint += 1
        if np.hypot(p[0] - tx, p[1] - ty) <= max(s["base_px"], s["streak_frac"] * p[2]):
            matched += 1
    return matched, joint


def _is_coloc(matched: int, joint: int, n_truth: int, s: dict[str, Any]) -> bool:
    return matched >= max(1, min(int(s["min_shared"]), n_truth)) and matched >= s["min_shared_frac"] * joint


def judge_window(w: dict[str, Any], points, s: dict[str, Any]) -> dict[str, Any]:
    """Track-level judgments of the predicted tracks in one window (see the module notes)."""
    from scipy.optimize import linear_sum_assignment

    from wfglink.validate.labels import _in_tile

    x0, y0, ww, hh = w["x0"], w["y0"], w["w"], w["h"]
    fset = set(int(f) for f in w["frames"])
    p = points[points["frame"].isin(fset)]
    preds: dict[int, dict[int, tuple[float, float, float]]] = {}
    judged = []
    if len(p):
        xy = p[["x", "y"]].to_numpy(float)
        inside = _in_tile(xy, x0, y0, ww, hh)
        ln = np.nan_to_num(p["length"].to_numpy(float), nan=0.0) if "length" in p else np.zeros(len(p))
        for tid, f, (x, y), L, ins in zip(p["track_id"].astype(int), p["frame"].astype(int), xy, ln, inside):
            preds.setdefault(int(tid), {})[int(f)] = (float(x), float(y), float(L), bool(ins))
        judged = sorted(t for t, d in preds.items() if sum(v[3] for v in d.values()) >= int(s["min_points"]))
    tracks = w["tracks"]
    tpts = [{int(q["frame"]): (q["x"], q["y"]) for q in tr["points"]} for tr in tracks]
    obs = [i for i, tr in enumerate(tracks) if tr["observable"] and not tr.get("ambiguous")]
    mf = np.zeros((len(judged), len(tracks)), np.int64)
    co = np.zeros((len(judged), len(tracks)), bool)
    for a, tid in enumerate(judged):
        for b, tp_ in enumerate(tpts):
            m, j = _colocation(preds[tid], tp_, s)
            mf[a, b], co[a, b] = m, _is_coloc(m, j, len(tp_), s)
    match: dict[int, int] = {}
    if judged and obs:
        wgt = np.where(co[:, obs], mf[:, obs], 0).astype(float)
        r, c = linear_sum_assignment(-wgt)
        for a, b in zip(r.tolist(), c.tolist()):
            if wgt[a, b] > 0:
                match[a] = obs[b]
    matched_truth = set(match.values())
    dc_pts = np.array([[q["x"], q["y"], q["frame"]] for tr in tracks for q in tr["points"] if q["dont_care"]],
                      float).reshape(-1, 3)
    cls = {}
    for a, tid in enumerate(judged):
        if a in match:
            cls[tid] = "tp"
        elif any(co[a, b] for b in obs):
            # Every observable truth track co-located with a prediction is matched (the
            # assignment maximises matched frames), so this one overlaps a matched track.
            cls[tid] = "duplicate"
        elif any(co[a, b] for b in range(len(tracks)) if b not in obs):
            cls[tid] = "dont_care"
        else:
            box = [(f, v) for f, v in preds[tid].items() if v[3]]
            near = 0
            for f, v in box:
                sel = dc_pts[dc_pts[:, 2] == f]
                r = max(s["base_px"], s["streak_frac"] * v[2])
                if len(sel) and np.min(np.hypot(sel[:, 0] - v[0], sel[:, 1] - v[1])) <= r:
                    near += 1
            cls[tid] = "dont_care" if box and near >= s["dont_care_frac"] * len(box) else "false"
    # Fragmentation and ID switches on observable truth tracks.
    fragmented = sum(1 for b in obs if int(co[:, b].sum()) > 1) if judged else 0
    idsw = 0
    for b in obs:
        seq = []
        for f in sorted(tpts[b]):
            tx, ty = tpts[b][f]
            best, bid = np.inf, None
            for tid in judged:
                v = preds[tid].get(f)
                if v is None:
                    continue
                dd = np.hypot(v[0] - tx, v[1] - ty)
                if dd <= max(s["base_px"], s["streak_frac"] * v[2]) and dd < best:
                    best, bid = dd, tid
            if bid is not None:
                seq.append(bid)
        idsw += sum(1 for u, v in zip(seq, seq[1:]) if u != v)
    counts = {c: sum(1 for v in cls.values() if v == c) for c in ("tp", "false", "duplicate", "dont_care")}
    return {"window_id": w["window_id"], "judged": len(judged), **counts, "truth_observable": len(obs),
            "truth_matched": len(matched_truth), "fragmented_truth": fragmented, "id_switches": idsw,
            "classes": {str(k): v for k, v in cls.items()},
            "in_box_frames": {str(t): int(sum(v[3] for v in preds[t].values())) for t in judged},
            "matches": {str(judged[a]): tracks[b].get("truth_id") for a, b in match.items()}}


def _window_box(w: dict[str, Any], roi_area: float | None, dt_default: float) -> tuple[float, float, float]:
    """(duration s, frame interval s, share of the ROI area) of a window's space-time box."""
    t = np.asarray(w["t"], float)
    dt = float(np.median(np.diff(t))) if t.size > 1 else dt_default
    frac = (w["w"] * w["h"] / roi_area) if roi_area else 1.0
    return float(t[-1] - t[0] + dt), dt, float(frac)


def poisson_bounds(k: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact one-sided (1 - alpha) Poisson bounds (lower, upper) for a count k."""
    from scipy.stats import chi2

    lo = 0.0 if k <= 0 else float(chi2.ppf(alpha, 2 * k) / 2)
    return lo, float(chi2.ppf(1 - alpha, 2 * k + 2) / 2)


def status(point: float | None, lo: float | None, hi: float | None, target: float, higher_is_better: bool = True) -> str:
    """PASSED, FAILED or INSUFFICIENT_EVIDENCE (see the module notes); an undefined estimate fails."""
    if point is None or not np.isfinite(point):
        return FAILED
    if higher_is_better:
        if point >= target and lo is not None and lo >= target:
            return PASSED
        if hi is not None and hi < target:
            return FAILED
        return INSUFFICIENT
    if point <= target and hi is not None and hi <= target:
        return PASSED
    if lo is not None and lo > target:
        return FAILED
    return INSUFFICIENT


def _proportion(k: int, n: int, alpha: float) -> dict[str, Any]:
    from wfglink.validate.metrics import clopper_pearson

    if n <= 0:
        return {"value": None, "k": k, "n": n, "lower": None, "upper": None, "level": 1 - alpha}
    lo, hi = clopper_pearson(k, n, 1.0 - 2.0 * alpha)
    return {"value": k / n, "k": k, "n": n, "lower": lo, "upper": hi, "level": 1 - alpha, "bounds": "one-sided"}


def _count_rate(k: int | None, minutes: float, alpha: float, weight_sum: float | None = None,
                reason: str = "") -> dict[str, Any]:
    """A count rate per supported minute with exact one-sided Poisson bounds (scaled by the
    mean weight for a weighted count) and the bound that zero events give."""
    zero = poisson_bounds(0, alpha)[1] / minutes if minutes > 0 else None
    if minutes <= 0 or k is None:
        return {"value": None, "count": k, "minutes": minutes, "zero_event_upper": zero,
                "reason": reason or ("no supported minutes" if minutes <= 0 else "")}
    lo, hi = poisson_bounds(k, alpha)
    scale = (weight_sum / k) if (weight_sum is not None and k > 0) else 1.0
    out = {"value": (k if weight_sum is None else weight_sum) / minutes, "count": k, "minutes": minutes,
           "lower": lo * scale / minutes, "upper": hi * scale / minutes, "zero_event_upper": zero,
           "level": 1 - alpha, "bounds": "one-sided exact Poisson" + (" of the judgments, scaled by their mean weight"
                                                                     if weight_sum is not None else "")}
    if weight_sum is not None:
        out["weighted_count"] = weight_sum
    return out


def track_level(truth: dict[str, Any], points, crossings=None, unsupported_frames: Iterable[int] | None = None,
                cfg: dict[str, Any] | None = None, targets: dict[str, Any] | None = None,
                revoked_ids: Iterable[int] = (), crossings_reason: str = "") -> dict[str, Any]:
    """Track-level precision, recall, rates, uncertainty and statuses over the labelled windows.

    crossings: crossing events (track_id, t, x, y), or None when the run holds none (the
    false crossing rate is then unavailable, crossings_reason says why). revoked_ids:
    predicted tracks whose acceptance was revoked (reported in the counts)."""
    import pandas as pd

    from wfglink.validate.labels import _in_tile, bootstrap_prf

    s = settings(cfg)
    ts, alpha = s["track"], float(s["alpha"])
    targets = targets or {}
    unsup = set(int(f) for f in unsupported_frames) if unsupported_frames is not None else set()
    revoked = set(int(i) for i in revoked_ids)
    if crossings is not None and not {"track_id", "t", "x", "y"} <= set(crossings.columns):
        raise ValueError("crossings must be events with track_id, t, x and y")
    roi = truth.get("roi_px")
    roi_area = float((roi[2] - roi[0]) * (roi[3] - roi[1])) if roi else None
    wins = _windows(truth)
    all_dt = [d for w in wins for d in np.diff(np.asarray(w["t"], float))]
    dt_default = float(np.median(all_dt)) if all_dt else 0.0
    life = {}
    if len(points):
        g = points.groupby("track_id")["t"].agg(["min", "max"])
        life = dict(zip(g.index.astype(int), (g["max"] - g["min"]).astype(float)))
    ev = None
    if crossings is not None and len(crossings):
        ev = (crossings["track_id"].to_numpy(np.int64), crossings["t"].to_numpy(float),
              crossings[["x", "y"]].to_numpy(float))
    per = []
    false_ids: set[int] = set()
    sup_min = occ_s = w_sum = 0.0
    n_judg = 0
    n_cross = 0 if crossings is not None else None
    for w in wins:
        j = judge_window(w, points, ts)
        dur, dt, frac = _window_box(w, roi_area, dt_default)
        j["supported"] = not (unsup & set(int(f) for f in w["frames"]))
        j["duration_s"], j["area_frac"] = dur, frac
        fl = [int(k) for k, v in j["classes"].items() if v == "false"]
        j["false_occupancy_s"] = float(sum(j["in_box_frames"][str(i)] for i in fl) * dt)
        j["false_weight"] = float(sum(dur / (dur + life.get(i, 0.0)) for i in fl))
        j["false_crossings"] = 0
        if ev is not None and fl:
            ta, tb = float(w["t"][0]) - dt / 2, float(w["t"][-1]) + dt / 2
            sel = np.isin(ev[0], fl) & (ev[1] >= ta) & (ev[1] <= tb)
            j["false_crossings"] = int((sel & _in_tile(ev[2], w["x0"], w["y0"], w["w"], w["h"])).sum())
        if j["supported"]:
            sup_min += dur * frac / 60.0
            false_ids |= set(fl)
            occ_s += j["false_occupancy_s"]
            w_sum += j["false_weight"]
            n_judg += len(fl)
            if n_cross is not None:
                n_cross += j["false_crossings"]
        per.append(j)
    df = pd.DataFrame(per)
    tot = {k: int(df[k].sum()) if len(df) else 0 for k in ("judged", "tp", "false", "duplicate", "dont_care",
                                                            "truth_observable", "truth_matched", "fragmented_truth",
                                                            "id_switches")}
    n_primary = tot["tp"] + tot["false"] + tot["duplicate"]
    prec = _proportion(tot["tp"], n_primary, alpha)
    prec_ft = _proportion(tot["tp"], tot["tp"] + tot["false"], alpha)
    rec = _proportion(tot["truth_matched"], tot["truth_observable"], alpha)
    b = s["bootstrap"]
    if len(df):
        bs = bootstrap_prf(df["tp"], df["false"] + df["duplicate"], df["truth_observable"] - df["truth_matched"],
                           int(b["n"]), int(b["seed"]), 0.95, 5)
        prec["bootstrap_ci"], rec["bootstrap_ci"] = bs["precision"]["ci"], bs["recall"]["ci"]
        prec["bootstrap_note"] = bs.get("ci_note")
    occ = {"value": (occ_s / sup_min) if sup_min > 0 else None, "seconds": occ_s, "minutes": sup_min}
    rates = {"false_tracks_per_min": _count_rate(n_judg, sup_min, alpha, w_sum),
             "false_crossings_per_min": _count_rate(n_cross, sup_min, alpha, reason="" if n_cross is not None else
                                                    (crossings_reason or "no crossing events given")),
             "false_occupancy_s_per_min": occ, "supported_minutes": sup_min,
             "minutes_rule": "sum over supported windows of duration x share of the ROI area (full-frame minutes); "
                             "numerators inside the windows' space-time boxes only, false tracks weighted "
                             "d / (d + lifetime)"}
    st: dict[str, str] = {}
    notes: dict[str, str] = {}
    if targets.get("precision") is not None:
        st["precision"] = status(prec["value"], prec["lower"], prec["upper"], float(targets["precision"]))
    if targets.get("recall_min") is not None:
        st["recall"] = status(rec["value"], rec["lower"], rec["upper"], float(targets["recall_min"]))
    for key in ("false_tracks_per_min", "false_crossings_per_min"):
        if targets.get(f"{key}_max") is not None:
            r, tgt = rates[key], float(targets[f"{key}_max"])
            st[key] = status(r["value"], r.get("lower"), r.get("upper"), tgt, False)
            z = r.get("zero_event_upper")
            if z is not None and z > tgt:
                notes[key] = (f"cannot PASS: {sup_min:.4g} supported minutes give an upper bound of {z:.4g} per minute "
                              f"even with zero events, above the target {tgt:g}")
            elif r["value"] is None:
                notes[key] = f"unavailable: {r.get('reason') or 'no estimate'}"
    capability = bool("precision" in st and prec["value"] is not None and all(v == PASSED for v in st.values()))
    judged_ids = {int(k) for j in per for k in j["classes"]}
    return {"precision": prec, "precision_fragment_tolerant": prec_ft, "recall": rec, "counts": {
                **tot, "unique_false_tracks": len(false_ids), "false_judgments_supported": n_judg,
                "windows": len(per), "windows_supported": int(sum(j["supported"] for j in per)),
                "revoked_judged": len(revoked & judged_ids),
                "revoked_false": len(revoked & {int(k) for j in per for k, v in j["classes"].items() if v == "false"})},
            "rates": rates, "status": st, "status_notes": notes, "capability_passed": capability,
            "capability_note": "" if capability else ("no accepted prediction judged: precision undefined"
                                                      if prec["value"] is None else
                                                      "no precision target" if "precision" not in st else
                                                      "a target is not PASSED"),
            "settings": s, "targets": targets, "per_window": per}


def pr_curve(truth: dict[str, Any], points, replays: Iterable[tuple[float, Iterable[int]]], crossings=None,
             cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Precision and recall per threshold from replays: (threshold, accepted track ids)."""
    out = []
    for thr, ids in sorted(replays, key=lambda r: r[0]):
        ids = set(int(i) for i in ids)
        cr = crossings[crossings["track_id"].isin(ids)] if crossings is not None else None
        r = track_level(truth, points[points["track_id"].isin(ids)], cr, cfg=cfg)
        out.append({"threshold": float(thr), "accepted": len(ids), "precision": r["precision"]["value"],
                    "precision_lower": r["precision"]["lower"], "recall": r["recall"]["value"],
                    "false_tracks_per_min": r["rates"]["false_tracks_per_min"]["value"]})
    return out


def evaluate(truth: dict[str, Any], preds: dict[str, Any], proto: dict[str, Any] | None = None) -> dict[str, Any]:
    """Frame- and track-level scores of loaded predictions (no files, no protocol checks)."""
    s = settings(proto)
    b = s["bootstrap"]
    det = preds.get("detections")
    frame = None
    if det is not None:
        skip = preds.get("duplicate_frames") or ()
        frame = {f"r{s['frame_match_px']:g}px": frame_level(truth, det, float(s["frame_match_px"]), int(b["n"]),
                                                            int(b["seed"]), skip),
                 f"r{s['frame_sensitivity_px']:g}px": frame_level(truth, det, float(s["frame_sensitivity_px"]),
                                                                  int(b["n"]), int(b["seed"]), skip)}
        for v in frame.values():
            v.pop("per_window", None)
    pts, cr = preds["points"], preds.get("crossings")
    revoked = set(preds.get("revoked_ids") or ())
    why = "legacy runs hold no crossing times" if preds.get("source") == "legacy" else ""
    targets = (proto or {}).get("targets")
    tl = track_level(truth, pts, cr, preds.get("unsupported_frames"), proto, targets, revoked, why)
    if revoked:
        v = track_level(truth, pts[~pts["track_id"].isin(revoked)],
                        None if cr is None else cr[~cr["track_id"].isin(revoked)], preds.get("unsupported_frames"),
                        proto, targets, (), why)
        tl["without_revoked"] = {"precision": v["precision"], "recall": v["recall"], "counts": v["counts"],
                                 "rates": {k: v["rates"][k] for k in ("false_tracks_per_min", "supported_minutes")},
                                 "note": "variant: the tracks accepted and then revoked (static) left out"}
    return {"frame_level": frame, "track_level": tl, "capability_passed": tl["capability_passed"],
            "source": preds.get("source"), "notes": list(preds.get("notes") or [])}


def evaluate_run(protocol: str | Path, expect_sha256: str, run_dir: str | Path, out: str | Path | None = None,
                 require_clean: bool = True, cfg: dict | None = None, recording: str | None = None,
                 selection: str | Path | None = None) -> dict[str, Any]:
    """Score a run under a frozen protocol (see the module notes); write the result to out.

    cfg: the config whose track settings replay a legacy run's static flags (default
    configs/default.yaml); not used for high-precision runs. recording: the truth entry of a
    list-form protocol (default: the one of the run's video and segment start). selection: the
    committed selection.json the run must match (its SHA-256 joins the sealed identity)."""
    from wfglink.provenance import git_state, now_shanghai, sha256_file, sha256_json
    from wfglink.verify.truth import load_truth

    proto = load_protocol(protocol, expect_sha256, require_clean)
    if isinstance(proto.get("truth"), list):
        entry = pick_truth(proto, run_dir, recording)
        proto["truth"] = entry
        proto["sealed"] = bool(entry.get("sealed", proto.get("sealed")))
        proto["_recording"] = str(entry.get("recording") or "")
    if proto.get("sealed"):
        used = sealed_used(proto)
        if used is not None:
            raise ProtocolError(f"{used} exists: the sealed test was scored already (a second scoring is refused)")
    tinfo = proto.get("truth") or {}
    tpath = Path(tinfo.get("path") or "")
    if not tpath.is_absolute():
        tpath = Path(proto["_path"]).parent / tpath
    if not tpath.is_file():
        raise ProtocolError(f"the protocol's truth {tpath} is not there")
    tsha = sha256_file(tpath)
    if tsha != str(tinfo.get("sha256") or ""):
        raise ProtocolError(f"the truth's SHA-256 {tsha[:16]} is not the protocol's {str(tinfo.get('sha256'))[:16]}")
    truth = load_truth(tpath)
    preds = load_predictions(run_dir, cfg)
    if truth.get("video_sha256") and preds.get("video_sha256") != truth["video_sha256"]:
        raise ProtocolError("the run analysed another video than the truth windows show")
    seg = truth.get("segment_s")
    if seg and abs(float(seg[0] or 0.0) - preds["segment_start"]) > TIME_TOL_S:
        raise ProtocolError(f"the run starts at {preds['segment_start']:g} s, the windows' segment at {seg[0]:g} s: "
                            "their frame indices differ")
    if truth.get("roi_px") and preds.get("roi_px") and [int(v) for v in truth["roi_px"]] != [int(v) for v in
                                                                                         preds["roi_px"]]:
        raise ProtocolError(f"the run's ROI {preds['roi_px']} differs from the windows' ROI {truth['roi_px']}")
    check_frame_times(truth, preds.get("frame_t"))
    info = preds["run_info"]
    for key in ("method", "profile"):
        if proto.get(key) is not None and info.get(key) != proto[key]:
            raise ProtocolError(f"the protocol is for {key} {proto[key]!r}, the run's is {info.get(key)!r}")
    warnings = list(preds.get("notes") or [])
    if info.get("status") in NOT_SCORABLE:
        if proto.get("sealed"):
            raise ProtocolError(f"the run's high-precision status is {info['status']!r} "
                                f"({info.get('status_reason') or 'no reason given'}): a sealed test is not spent on it")
        warnings.append(f"the run's high-precision status is {info['status']!r}: it accepts nothing as intended")
    sel = check_selection(selection, info, require_clean or bool(proto.get("sealed"))) if selection is not None \
        else None
    identity = scorer_identity(info, sel["sha256"] if sel else None)
    locks = claim_sealed(proto, run_dir, identity) if proto.get("sealed") else []
    res = evaluate(truth, preds, proto)
    res.update(protocol={"path": proto["_path"], "sha256": proto["_sha256"], "name": proto.get("name"),
                         "sealed": bool(proto.get("sealed")), "recording": proto.get("_recording")},
               truth={"path": str(tpath), "sha256": tsha}, run_dir=str(run_dir), run=info, notes=warnings,
               scorer_identity=identity, selection=sel, created=now_shanghai(), **git_state())
    text = json.dumps(res, indent=2, default=str)
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    for lock in locks:
        rec = json.loads(lock.read_text(encoding="utf-8"))
        rec.update(status="scored", scored=now_shanghai(), result_sha256=sha256_json(res),
                   result=str(out) if out is not None else None)
        lock.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return res
