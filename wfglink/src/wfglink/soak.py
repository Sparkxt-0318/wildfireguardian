"""Overnight booth soak: run the booth for hours, sample its heartbeat, judge PASS or FAIL.

The command is scripts/mac_soak.py (python scripts/mac_soak.py --hours 8). run_soak starts
the booth supervisor (bash booth/booth.sh: the playlist in a loop, restarted after a crash
or a hang) in its own process group and, while it runs, copies logs/heartbeat.json (which
the app rewrites every 2 s) into soak.csv every soak.every_s seconds. After the hours, on
Ctrl-C, or when the supervisor ends by itself (Esc pressed twice in the booth), it stops the
supervisor with SIGTERM and analyses the samples and logs/booth.log:

- paint fps, from the change in the painted-frame counter between samples of the same app
  instance (intervals that touch a pause are left out), with median, 5th percentile and
  minimum: each value is the average over one sampling interval;
- memory slope in MB per hour: a linear fit of resident memory (the app plus any child
  process) against time over the last soak.mem_fit_last_h hours, leaving out each app
  instance's warm-up. Restarts reset memory, so the fit is pooled within app instances
  (each keeps its own offset, all share one slope); a sample whose child memory could not
  be read is left out rather than summed short;
- restarts and hangs: lines that booth.sh wrote during the soak (rotated logs too), with
  the app instances seen in the samples as a check;
- analysis stalls: stretches of at least soak.analysis_stall_s, not paused, in which no
  frame was analysed although the app was alive (from the heartbeat's frame counter and
  its pipeline counters, which also say whether frames kept arriving);
- processing errors counted in the heartbeat, the share of samples with a fresh heartbeat,
  the clips played, and the share of playlist samples on the synthetic fallback (no clip
  could play).

judge_soak turns the analysis into PASS or FAIL with one line per check; the floors are
the soak: keys in configs/default.yaml. A soak cut off before its report (the Mac
restarted) can be analysed again from its folder:

    python -m wfglink.soak logs/soak/20261019-2215
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

from wfglink import PROJECT_ROOT

# Pipeline counters from the heartbeat (key "pipeline"): CSV column -> counter.
PIPE_COLUMNS = {"pipe_in": "frames_in", "pipe_analysed": "frames_analysed", "pipe_duplicate": "frames_duplicate"}
COLUMNS = ["sample_epoch", "sample_time", "hb_epoch", "hb_age_s", "status", "pid", "uptime_s", "frames", "paints",
           "fps", "source", "state", "clip", "paused", "errors", "last_error", "rss_mb", "rss_detail", "hb_status",
           "pipe_key", *PIPE_COLUMNS]
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[booth\.sh\] (.*)$")


def soak_config(cfg: dict | None = None) -> dict[str, Any]:
    """The soak: section of the config (configs/default.yaml, then configs/booth_local.yaml)."""
    if cfg is None:
        from wfglink.config import load_config

        cfg = load_config(local=True)
    return dict(cfg.get("soak") or {})


def log_dir() -> Path:
    """Where booth.sh writes booth.log and heartbeat.json (WFG_LOGDIR, else wfglink/logs)."""
    return Path(os.environ.get("WFG_LOGDIR") or PROJECT_ROOT / "logs")


# Sampling ----------------------------------------------------------------------------------

def read_heartbeat(path: str | Path) -> dict[str, Any] | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def sample_row(hb: dict[str, Any] | None, now: float | None = None, stale_s: float = 30.0) -> dict[str, Any]:
    """One CSV row from a heartbeat (or a 'missing' row when there is none). Missing keys stay empty."""
    now = time.time() if now is None else now
    row: dict[str, Any] = {k: "" for k in COLUMNS}
    row["sample_epoch"] = round(now, 3)
    row["sample_time"] = dt.datetime.fromtimestamp(now).isoformat(timespec="seconds")
    if not hb:
        row["status"] = "missing"
        return row
    hb_epoch = float(hb.get("epoch") or 0.0)
    age = now - hb_epoch if hb_epoch else float("inf")
    rss = hb.get("rss_mb") or {}
    # The sum covers the app and its child processes; when one of them could not be read the
    # sum would drop by that process's memory and look like a release, so it is left empty.
    vals = [float(v) for v in rss.values()] if all(v is not None for v in rss.values()) else []
    row.update({
        "hb_epoch": round(hb_epoch, 3), "hb_age_s": round(age, 1) if math.isfinite(age) else "",
        "status": hb.get("status", "") if age <= stale_s else "stale",
        "pid": hb.get("pid", ""), "uptime_s": hb.get("uptime_s", ""), "frames": hb.get("frames", ""),
        "paints": hb.get("paints", ""), "fps": hb.get("fps", ""), "source": hb.get("source", ""),
        "state": hb.get("state", ""), "clip": hb.get("clip") or "",
        "paused": "" if hb.get("paused") is None else int(bool(hb.get("paused"))),
        "errors": hb.get("errors", ""), "last_error": (hb.get("last_error") or "")[:200],
        "rss_mb": round(sum(vals), 1) if vals else "", "rss_detail": json.dumps(rss, separators=(",", ":")),
        "hb_status": hb.get("status", ""),     # the app's own status, kept when the row is stale
    })
    pipe = hb.get("pipeline") or {}
    if pipe:
        row["pipe_key"] = pipe.get("key") or ""
        row.update({col: pipe.get(name, "") for col, name in PIPE_COLUMNS.items()})
    return row


def append_row(csv_path: str | Path, row: dict[str, Any]) -> None:
    p = Path(csv_path)
    new = not p.exists() or p.stat().st_size == 0
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = COLUMNS
    if not new:   # keep the columns of a file started by an older sampler
        with open(p, newline="", encoding="utf-8") as fh:
            fields = next(csv.reader(fh), None) or COLUMNS
    with open(p, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def sample_once(heartbeat: str | Path, csv_path: str | Path, stale_s: float = 30.0) -> dict[str, Any]:
    row = sample_row(read_heartbeat(heartbeat), stale_s=stale_s)
    append_row(csv_path, row)
    return row


# Analysis ----------------------------------------------------------------------------------

def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def load_samples(csv_path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for k in ("sample_epoch", "hb_epoch", "hb_age_s", "uptime_s", "frames", "paints", "fps", "errors", "rss_mb",
                      *PIPE_COLUMNS):
                r[k] = _num(r.get(k))     # missing columns (an older CSV) and empty cells are None
            r["pid"] = str(r.get("pid") or "")
            r["paused"] = str(r.get("paused") or "").strip().lower() in ("1", "true")
            try:   # the processes whose memory was summed: the app, plus any child process
                r["rss_key"] = ",".join(sorted(json.loads(r.get("rss_detail") or "{}")))
            except ValueError:
                r["rss_key"] = ""
            rows.append(r)
    rows.sort(key=lambda r: r["sample_epoch"] or 0.0)
    return rows


def _live(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows from a running app with a fresh heartbeat, each heartbeat once (a sampler faster
    than the heartbeat reads the same one twice)."""
    out, seen = [], set()
    for r in rows:
        if r.get("status") in ("missing", "stale") or not r["pid"] or not r["hb_epoch"]:
            continue
        key = (r["pid"], r["hb_epoch"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def paint_fps_series(rows: list[dict[str, Any]]) -> list[float]:
    """Paint rate between consecutive samples of the same app instance (painted frames per
    second), leaving out intervals that start or end paused."""
    out = []
    live = _live(rows)
    for a, b in zip(live, live[1:]):
        if a["pid"] != b["pid"] or a["paints"] is None or b["paints"] is None or a["paused"] or b["paused"]:
            continue
        dt_s = b["hb_epoch"] - a["hb_epoch"]
        if dt_s <= 0.5 or b["paints"] < a["paints"]:
            continue
        out.append((b["paints"] - a["paints"]) / dt_s)
    return out


def mem_slope(rows: list[dict[str, Any]], last_h: float = 6.0, warmup_s: float = 600.0) -> dict[str, Any]:
    """Memory slope (MB per hour), pooled within app instances, over the last `last_h` hours.

    An instance is one app pid with one set of measured processes: a child process that is
    replaced inside the same app starts with fresh memory, so it starts a new group too.
    """
    live = [r for r in _live(rows) if r["rss_mb"] is not None]
    if not live:
        return {"slope_mb_h": None, "points": 0, "span_h": 0.0, "instances": 0}
    t_end = live[-1]["hb_epoch"]
    use = [r for r in live if r["hb_epoch"] >= t_end - last_h * 3600.0 and (r["uptime_s"] or 0.0) >= warmup_s]
    groups: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for r in use:
        groups.setdefault((r["pid"], r.get("rss_key", "")), []).append((r["hb_epoch"] / 3600.0, r["rss_mb"]))
    sxy = sxx = 0.0
    n = 0
    for pts in groups.values():
        if len(pts) < 2:
            continue
        a = np.array(pts)
        tc, mc = a[:, 0] - a[:, 0].mean(), a[:, 1] - a[:, 1].mean()
        sxy += float(np.sum(tc * mc))
        sxx += float(np.sum(tc * tc))
        n += len(pts)
    span = (use[-1]["hb_epoch"] - use[0]["hb_epoch"]) / 3600.0 if len(use) > 1 else 0.0
    slope = sxy / sxx if sxx > 0 else None
    return {"slope_mb_h": round(slope, 2) if slope is not None else None, "points": n, "span_h": round(span, 3),
            "instances": sum(1 for p in groups.values() if len(p) >= 2),
            "rss_first_mb": use[0]["rss_mb"] if use else None, "rss_last_mb": use[-1]["rss_mb"] if use else None}


def log_files(log: str | Path) -> list[Path]:
    """booth.log and its rotated copies (booth.log.1 ... booth.log.5), oldest first."""
    log = Path(log)
    rotated = sorted(log.parent.glob(log.name + ".*"), key=lambda p: -int(p.suffix[1:]) if p.suffix[1:].isdigit() else 0)
    return [p for p in rotated if p.suffix[1:].isdigit()] + ([log] if log.exists() else [])


def count_log_events(log: str | Path, start_epoch: float, end_epoch: float | None = None) -> dict[str, Any]:
    """Supervisor events written by booth.sh between start and end (local time, 1 s resolution).
    A hang is followed by an "app ended" line, so restarts include the hangs."""
    t0 = dt.datetime.fromtimestamp(math.floor(start_epoch))
    t1 = dt.datetime.fromtimestamp(math.floor(end_epoch)) if end_epoch is not None else None
    out: dict[str, Any] = {"restarts": 0, "hangs": 0, "clean_exits": 0, "starts": 0, "ended_lines": []}
    for p in log_files(log):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            m = LOG_LINE.match(line)
            if not m:
                continue
            when = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            if when < t0 or (t1 is not None and when >= t1):
                continue
            text = m.group(2)
            if text.startswith("app ended"):
                out["restarts"] += 1
                if len(out["ended_lines"]) < 20:
                    out["ended_lines"].append(line)
            elif text.startswith("hang detected"):
                out["hangs"] += 1
            elif text.startswith("clean exit"):
                out["clean_exits"] += 1
            elif text.startswith("start:"):
                out["starts"] += 1
    return out


def playback_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What played (sources, clips, clip changes, synthetic fallback) and the processing errors."""
    live = _live(rows)
    clips: dict[str, int] = {}
    changes, prev = 0, None
    for r in live:
        c = r.get("clip") or ""
        if not c:
            continue
        clips[c] = clips.get(c, 0) + 1
        changes += prev is not None and c != prev
        prev = c
    # The playlist falls back to synthetic video when no clip can play (files missing or broken).
    playlist = [r for r in live if r.get("source") == "playlist"]
    fallback = sum(1 for r in playlist if r.get("clip") == "synthetic")
    errors: dict[str, float] = {}
    last_error = ""
    for r in live:
        if r["errors"] is not None:
            errors[r["pid"]] = max(errors.get(r["pid"], 0.0), r["errors"])
        if r.get("last_error"):
            last_error = r["last_error"]
    states: dict[str, int] = {}
    for r in rows:
        key = r["status"] if r.get("status") in ("missing", "stale") else (r.get("state") or r.get("status") or "?")
        states[key] = states.get(key, 0) + 1
    return {"sources": sorted({r["source"] for r in live if r.get("source")}), "clips": clips, "clip_changes": changes,
            "playlist_samples": len(playlist), "fallback_samples": fallback,
            "fallback_fraction": round(fallback / len(playlist), 4) if playlist else None,
            "paused_samples": sum(1 for r in live if r["paused"]),
            "errors": int(sum(errors.values())), "last_error": last_error or None, "samples_by_state": states}


def pipeline_progress(rows: list[dict[str, Any]], stall_s: float = 180.0, reset_frac: float = 0.8,
                      reset_slack: float = 60.0) -> dict[str, Any]:
    """Whether the app kept analysing.

    Consecutive samples of the same app instance are compared, leaving out intervals that
    start or end paused (Space holds playback and analysis on purpose). An interval shows
    progress when the heartbeat's frame counter (frames the app processed) grew and, when
    both samples come from the same pipeline, its analysed-frame counter grew too. A clip
    that starts again gets a new pipeline under the same key, whose counters restart: they
    fall, or grow by less than reset_frac of the frames the app processed (minus
    reset_slack, since the process worker reports its counters only once a second); then
    only the frame counter is compared. Stretches of at least stall_s without progress are
    stalls; the cause says whether frames kept arriving: "repeated frames only", "frames
    not analysed" or "no frames". booth.sh restarts an app whose frame counter stops for a
    while, so most stalls of that kind end as a restart; a stall with arriving frames is one
    it cannot see.
    """
    live = [r for r in _live(rows) if r["frames"] is not None]
    stalls: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    intervals = analysed = 0

    def close() -> None:
        nonlocal cur
        if cur is not None and cur["s"] >= stall_s:
            g = cur["grew"]
            cause = ("repeated frames only" if g["duplicate"] > 0 else
                     "frames not analysed" if g["in"] > 0 else "no frames")
            stalls.append({"at": cur["at"], "minutes": round(cur["s"] / 60.0, 1), "cause": cause})
        cur = None

    for a, b in zip(live, live[1:]):
        if a["pid"] != b["pid"] or a["paused"] or b["paused"] or b["frames"] < a["frames"]:
            close()
            continue
        intervals += 1
        same = (a.get("pipe_key") or None) is not None and a.get("pipe_key") == b.get("pipe_key")
        d = {col: (b[col] or 0.0) - (a[col] or 0.0) for col in PIPE_COLUMNS} if same else {}
        d_frames = b["frames"] - a["frames"]
        if d and (any(v < 0 for v in d.values()) or d["pipe_in"] < reset_frac * d_frames - reset_slack):
            d = {}                             # counters restarted: a new pipeline under the same key
        progress = d_frames > 0 and (not d or d["pipe_analysed"] > 0)
        if d:
            analysed += int(d["pipe_analysed"])
        if progress:
            close()
            continue
        if cur is None:
            cur = {"at": a["sample_time"], "s": 0.0, "grew": {"in": 0.0, "duplicate": 0.0}}
        cur["s"] += b["hb_epoch"] - a["hb_epoch"]
        cur["grew"]["in"] += d.get("pipe_in", 0.0)
        cur["grew"]["duplicate"] += d.get("pipe_duplicate", 0.0)
    close()
    if intervals == 0:
        return {"intervals": 0, "verdict": "not enough data"}
    return {"intervals": intervals, "stall_s": stall_s, "stalls": len(stalls),
            "stall_minutes": round(sum(s["minutes"] for s in stalls), 1),
            "longest_stall_min": max((s["minutes"] for s in stalls), default=0.0), "stall_list": stalls[:20],
            "frames_analysed_compared": analysed, "verdict": "fail" if stalls else "pass"}


def _pct(values: list[float], q: float) -> float | None:
    return round(float(np.percentile(values, q)), 2) if values else None


def sampling_gaps(rows: list[dict[str, Any]], factor: float = 3.0) -> tuple[int, float]:
    """Gaps between samples longer than `factor` times the median interval (the Mac slept or
    restarted, or the sampler stopped): their number and total hours."""
    t = [r["sample_epoch"] for r in rows if r["sample_epoch"] is not None]
    d = [b - a for a, b in zip(t, t[1:])]
    if len(d) < 2:
        return 0, 0.0
    med = float(np.median(d))
    big = [x for x in d if med > 0 and x > factor * med]
    return len(big), round(sum(big) / 3600.0, 3)


def analyse_soak(csv_path: str | Path, log: str | Path, start_epoch: float, end_epoch: float | None = None,
                 last_h: float = 6.0, warmup_s: float = 600.0, mem_max_mb_h: float = 20.0,
                 min_hours: float = 2.0, stall_s: float = 180.0, start_grace_s: float = 120.0,
                 reset_frac: float = 0.8, reset_slack: float = 60.0) -> dict[str, Any]:
    """Soak statistics from the CSV and booth.log. A clean exit (Esc pressed twice) ends the
    soak, because booth.sh stops with it: later samples come from whatever runs afterwards
    and are left out, as is the time after it. Samples taken before the app's first
    heartbeat, within start_grace_s of the start, are start-up rather than downtime."""
    rows = load_samples(csv_path) if Path(csv_path).exists() else []
    # Rows sampled before this soak started belong to an earlier one in the same file.
    rows = [r for r in rows if (r["sample_epoch"] or 0.0) >= start_epoch]
    if not rows:
        return {"ok": False, "error": "no soak samples", "samples": 0}
    ended_by = "finish"
    # Only a clean exit written during the soak counts: the first sample can still read the
    # heartbeat an earlier booth left behind (for example after Esc), before booth.sh removes it.
    exit_row = next((r for r in rows if "clean_exit" in (r.get("status"), r.get("hb_status"))
                     and r["hb_epoch"] and r["hb_epoch"] >= start_epoch), None)
    if exit_row is not None and (end_epoch is None or exit_row["hb_epoch"] < end_epoch):
        end_epoch = exit_row["hb_epoch"]
        rows = [r for r in rows if (r["sample_epoch"] or 0.0) <= exit_row["sample_epoch"]]
        ended_by = "clean exit (Esc pressed twice)"
    first_fresh = next((i for i, r in enumerate(rows)
                        if r.get("status") not in ("missing", "stale") and r["pid"] and r["hb_epoch"]), len(rows))
    startup = sum(1 for r in rows[:first_fresh] if r["sample_epoch"] < start_epoch + start_grace_s)
    counted = rows[startup:]
    first, last = rows[0]["sample_epoch"], rows[-1]["sample_epoch"]
    hours = ((end_epoch or last) - start_epoch) / 3600.0
    pfps = paint_fps_series(rows)
    live = _live(rows)
    proc = [r["fps"] for r in live if r["fps"] is not None]
    mem = mem_slope(rows, last_h=last_h, warmup_s=warmup_s)
    if mem["slope_mb_h"] is None or hours < min_hours:     # a short run says little about a leak
        mem_verdict = "too short to judge"
    else:
        mem_verdict = "pass" if mem["slope_mb_h"] <= mem_max_mb_h else "fail"
    logs = count_log_events(log, start_epoch, end_epoch)
    play = playback_summary(rows)
    pids = [r["pid"] for r in live]
    pid_changes = sum(1 for a, b in zip(pids, pids[1:]) if a != b)
    n_gaps, gap_h = sampling_gaps(rows)
    n_fresh = sum(1 for r in counted if r.get("status") not in ("missing", "stale") and r["pid"] and r["hb_epoch"])
    return {
        "ok": True, "hours": round(hours, 3), "ended_by": ended_by,
        "hours_running": round(min(hours, ((live[-1]["hb_epoch"] if live else start_epoch) - start_epoch) / 3600.0), 3),
        "samples": len(rows), "samples_startup": startup, "samples_live": len(live),
        "live_fraction": round(n_fresh / len(counted), 3) if counted else 0.0,
        "sampled_span_h": round((last - first) / 3600.0, 3), "sampling_gaps": n_gaps, "sampling_gap_h": gap_h,
        "paint_fps_median": _pct(pfps, 50), "paint_fps_p5": _pct(pfps, 5), "paint_fps_min": _pct(pfps, 0),
        "paint_fps_intervals": len(pfps),
        "processing_fps_median": _pct(proc, 50), "processing_fps_p5": _pct(proc, 5),
        "memory": {**mem, "max_mb_h": mem_max_mb_h, "fit_last_h": last_h, "warmup_s": warmup_s,
                   "min_hours": min_hours, "verdict": mem_verdict},
        # Restarts come from booth.sh's log; the app instances seen in the samples are a check
        # on them (rotated-away log lines, or a supervisor that died, show up as a difference).
        "restarts": logs["restarts"], "hangs": logs["hangs"], "app_ended_lines": logs["ended_lines"],
        "instances": len(set(pids)), "pid_changes": pid_changes,
        "playback": {k: v for k, v in play.items() if k not in ("errors", "last_error", "samples_by_state")},
        "errors": play["errors"], "last_error": play["last_error"], "samples_by_state": play["samples_by_state"],
        "pipeline": pipeline_progress(rows, stall_s=stall_s, reset_frac=reset_frac, reset_slack=reset_slack),
    }


def analyse_with_config(csv_path: str | Path, log: str | Path, start_epoch: float, end_epoch: float | None,
                        sc: dict[str, Any]) -> dict[str, Any]:
    return analyse_soak(csv_path, log, start_epoch, end_epoch, last_h=float(sc.get("mem_fit_last_h", 6.0)),
                        warmup_s=float(sc.get("mem_warmup_s", 600.0)),
                        mem_max_mb_h=float(sc.get("mem_slope_max_mb_h", 20.0)),
                        min_hours=float(sc.get("mem_min_hours", 2.0)), stall_s=float(sc.get("analysis_stall_s", 180.0)),
                        start_grace_s=float(sc.get("start_grace_s", 120.0)),
                        reset_frac=float(sc.get("counter_reset_frac", 0.8)),
                        reset_slack=float(sc.get("counter_reset_slack", 60)))


# Verdict -----------------------------------------------------------------------------------

def _fmt(v: Any, spec: str = ".1f") -> str:
    return "none" if v is None else format(v, spec)


def judge_soak(a: dict[str, Any], sc: dict[str, Any], hours_requested: float | None = None, ended_by: str = "",
               supervisor_code: int | None = None) -> dict[str, Any]:
    """PASS or FAIL from the analysis, with one check per line: name, status (OK, FAIL or
    "not judged") and a short detail. Every judged check must be OK for a PASS."""
    checks: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    if not a.get("ok"):
        add("samples", "FAIL", f"{a.get('error', 'no analysis')}: the booth never wrote a heartbeat that was sampled")
        return {"verdict": "FAIL", "checks": checks}
    # How the soak ended. The supervisor ends by itself only after Esc pressed twice (a clean
    # exit, status 0); any other end means booth.sh could not keep the booth running.
    of = f" of {hours_requested:.3g} h" if hours_requested else ""
    how = ended_by or a.get("ended_by", "")
    if a.get("ended_by", "").startswith("clean exit"):
        how = a["ended_by"]
    own_end = supervisor_code is not None and supervisor_code != 0 and how.startswith("booth.sh ended")
    add("duration", "FAIL" if own_end else "OK", f"{a['hours']:.3g} h{of}, ended by {how}; "
        f"booth running {a['hours_running']:.3g} h")
    med_min, p5_min = float(sc.get("fps_median_min", 20)), float(sc.get("fps_p5_min", 10))
    if not a["paint_fps_intervals"]:
        add("paint fps", "FAIL", "no paint rate measured (no two heartbeats of one running app)")
    else:
        ok = a["paint_fps_median"] >= med_min and a["paint_fps_p5"] >= p5_min
        add("paint fps", "OK" if ok else "FAIL", f"median {a['paint_fps_median']:.1f}, 5th percentile "
            f"{a['paint_fps_p5']:.1f} over {a['paint_fps_intervals']} intervals (floors {med_min:g} and {p5_min:g})")
    m = a["memory"]
    slope = "no slope yet" if m["slope_mb_h"] is None else f"{m['slope_mb_h']:+.1f} MB/h"
    if m["verdict"] == "too short to judge":
        add("memory", "not judged", f"{slope} over {m['span_h']:.2f} h after warm-up: too short to judge "
            f"(judged from a {m['min_hours']:g} h run; limit {m['max_mb_h']:g} MB/h)")
    else:
        add("memory", "OK" if m["verdict"] == "pass" else "FAIL",
            f"{slope} over {m['span_h']:.2f} h after warm-up (limit {m['max_mb_h']:g} MB/h)")
    rmax = int(sc.get("restarts_max", 0))
    add("restarts", "OK" if a["restarts"] <= rmax else "FAIL",
        f"{a['restarts']} in booth.log, {a['hangs']} of them after a hang (allowed {rmax})")
    p = a["pipeline"]
    if p.get("verdict") == "not enough data":
        add("analysis", "not judged", "no two heartbeats of one running app to compare")
    elif p["stalls"]:
        s = p["stall_list"][0]
        add("analysis", "FAIL", f"{p['stalls']} stalls of {p['stall_s']:g} s or more, {p['stall_minutes']:g} min in all; "
            f"first at {s['at']} ({s['cause']})")
    else:
        add("analysis", "OK", f"frames analysed throughout (no stall of {p['stall_s']:g} s or more)")
    emax = int(sc.get("errors_max", 0))
    add("errors", "OK" if a["errors"] <= emax else "FAIL", f"{a['errors']} in processing (allowed {emax})"
        + (f"; last: {a['last_error'][:80]}" if a["errors"] > emax and a.get("last_error") else ""))
    lmin = float(sc.get("live_fraction_min", 0.9))
    add("heartbeat", "OK" if a["live_fraction"] >= lmin else "FAIL",
        f"fresh in {100 * a['live_fraction']:.1f} % of {a['samples'] - a['samples_startup']} samples "
        f"(floor {100 * lmin:g} %); {a['instances']} app instance{'' if a['instances'] == 1 else 's'}")
    pb = a["playback"]
    if pb["playlist_samples"]:
        fmax = float(sc.get("fallback_max", 0.0))
        real = [c for c in pb["clips"] if c != "synthetic"]
        add("playlist", "OK" if pb["fallback_fraction"] <= fmax else "FAIL",
            f"clips seen {len(real)}, clip changes {pb['clip_changes']}; synthetic fallback in "
            f"{100 * pb['fallback_fraction']:.1f} % of samples (allowed {100 * fmax:g} %)")
    else:
        add("playlist", "not judged", f"source {', '.join(pb['sources']) or 'unknown'}, not the playlist")
    failed = [c["name"] for c in checks if c["status"] == "FAIL"]
    return {"verdict": "FAIL" if failed else "PASS", "failed": failed,
            "not_judged": [c["name"] for c in checks if c["status"] == "not judged"], "checks": checks}


def format_report(report: dict[str, Any]) -> str:
    """The printed report: the verdict, then one line per check (status, name, detail) and the files."""
    j = report["judgement"]
    head = f"wfglink soak: {j['verdict']}"
    if j["verdict"] == "FAIL":
        head += f" ({', '.join(j['failed'])})"
    elif j["not_judged"]:
        head += f" (not judged: {', '.join(j['not_judged'])})"
    lines = [head]
    for c in j["checks"]:
        lines.append(f"  {c['status']:<10}  {c['name']:<10} {c['detail']}")
    for name, path in (report.get("files") or {}).items():
        lines.append(f"  {'':<10}  {name:<10} {path}")
    return "\n".join(lines)


# Running a soak ----------------------------------------------------------------------------

def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def stop_supervisor(proc: subprocess.Popen, timeout_s: float = 30.0) -> int | None:
    """SIGTERM to booth.sh (it stops the app and exits 130), then, if it does not end in time,
    to its whole process group, then SIGKILL. Whatever is left of the group is ended too."""
    pgid = proc.pid    # started with start_new_session, so it leads its own group
    if proc.poll() is None:
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout_s)
        except subprocess.TimeoutExpired:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(pgid, sig)
                except ProcessLookupError:
                    break
                try:
                    proc.wait(5.0)
                    break
                except subprocess.TimeoutExpired:
                    continue
    t_end = time.monotonic() + 5.0
    while _group_alive(pgid) and time.monotonic() < t_end:
        time.sleep(0.2)
    if _group_alive(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return proc.poll()


def _progress_line(start: float, hours: float, csv_path: Path, log: Path) -> str:
    rows = load_samples(csv_path) if csv_path.exists() else []
    live = [r for r in _live(rows) if r["sample_epoch"] >= start]
    fps = paint_fps_series(live[-2:]) if len(live) >= 2 else []
    last = live[-1] if live else {}
    ev = count_log_events(log, start, None)
    clip = last.get("clip") or last.get("source") or "no heartbeat yet"
    return (f"[{dt.datetime.now().strftime('%H:%M')}] {(time.time() - start) / 3600:.2f} of {hours:g} h: "
            f"paint {_fmt(fps[-1] if fps else None)} fps, memory {_fmt(last.get('rss_mb'), '.0f')} MB, "
            f"restarts {ev['restarts']}, errors {_fmt(last.get('errors'), '.0f')}, playing {clip}")


def run_soak(hours: float, booth_cmd: list[str], out_dir: str | Path, every_s: float | None = None,
             sc: dict[str, Any] | None = None, logdir: str | Path | None = None, cwd: str | Path | None = None,
             echo: Callable[[str], None] = print) -> dict[str, Any]:
    """Run the booth supervisor for `hours`, sample its heartbeat, stop it, judge and write
    soak_report.json in out_dir (with soak.csv, soak_meta.json and supervisor.txt, the
    supervisor's own output). SIGINT, SIGTERM and SIGHUP end the soak early, with a report."""
    sc = soak_config() if sc is None else sc
    every_s = float(every_s or sc.get("every_s", 60))
    stale_s = float(sc.get("stale_s", 30))
    progress_s = float(sc.get("progress_every_s", 600))
    logdir = Path(logdir) if logdir else log_dir()
    hb, log = logdir / "heartbeat.json", logdir / "booth.log"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "soak.csv"
    start = time.time()
    meta = {"start_epoch": start, "start": dt.datetime.fromtimestamp(start).isoformat(timespec="seconds"),
            "hours": hours, "every_s": every_s, "booth_cmd": booth_cmd, "heartbeat": str(hb), "log": str(log),
            "host": platform.node(), "soak_config": sc}
    (out / "soak_meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    stop: dict[str, str] = {}

    def _stop(signum, frame):  # noqa: ARG001
        stop.setdefault("by", "Ctrl-C" if signum == signal.SIGINT else f"signal {signal.Signals(signum).name}")

    old = {s: signal.signal(s, _stop) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    awake = None
    if platform.system() == "Darwin" and shutil.which("caffeinate"):
        # booth.sh keeps the display awake while it runs; this keeps the soak itself from idle sleep.
        awake = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
    with open(out / "supervisor.txt", "ab") as sup_out:
        proc = subprocess.Popen(booth_cmd, cwd=str(cwd or PROJECT_ROOT), stdout=sup_out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    echo(f"Soak started for {hours:g} h: {' '.join(booth_cmd)}")
    echo(f"Heartbeat samples every {every_s:g} s into {csv_path}. Ctrl-C ends the soak early (the report still follows).")
    deadline = start + hours * 3600.0
    next_progress = start + progress_s
    code = None
    try:
        while True:
            sample_once(hb, csv_path, stale_s)
            t_next = time.time() + every_s
            while not stop and time.time() < min(t_next, deadline) and proc.poll() is None:
                time.sleep(min(0.5, max(0.0, min(t_next, deadline) - time.time())))
            if stop or proc.poll() is not None or time.time() >= deadline:
                break
            if time.time() >= next_progress:
                echo(_progress_line(start, hours, csv_path, log))
                next_progress += progress_s
        code = proc.poll()
        end = time.time()
        sample_once(hb, csv_path, stale_s)     # the last state before the booth is stopped
        if code is not None:
            ended_by = f"booth.sh ended by itself (exit code {code})"
        else:
            ended_by = stop.get("by") or "the time limit"
            echo(f"Stopping the booth ({ended_by})...")
            code = stop_supervisor(proc, float(sc.get("stop_timeout_s", 30)))
    finally:
        if proc.poll() is None:
            stop_supervisor(proc, float(sc.get("stop_timeout_s", 30)))
        for s, h in old.items():
            signal.signal(s, h)
        if awake is not None:
            awake.terminate()
    analysis = analyse_with_config(csv_path, log, start, end, sc)
    supervisor_code = code if ended_by.startswith("booth.sh ended") else None
    judgement = judge_soak(analysis, sc, hours, ended_by, supervisor_code)
    report = {"verdict": judgement["verdict"], "judgement": judgement, "analysis": analysis,
              "start": meta["start"], "end": dt.datetime.fromtimestamp(end).isoformat(timespec="seconds"),
              "hours_requested": hours, "ended_by": ended_by, "supervisor_exit_code": code,
              "booth_cmd": booth_cmd, "soak_config": sc,
              "files": {"report": str(out / "soak_report.json"), "samples": str(csv_path)}}
    (out / "soak_report.json").write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    meta["end_epoch"], meta["ended_by"], meta["supervisor_exit_code"] = end, ended_by, code
    (out / "soak_meta.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return report


def reanalyse(folder: str | Path, sc: dict[str, Any] | None = None) -> dict[str, Any]:
    """The report of a soak folder again (for a soak cut off before its report was written)."""
    folder = Path(folder)
    meta = json.loads((folder / "soak_meta.json").read_text(encoding="utf-8"))
    if sc is None:
        sc = meta.get("soak_config") or soak_config()
    analysis = analyse_with_config(folder / "soak.csv", meta["log"], meta["start_epoch"], meta.get("end_epoch"), sc)
    ended_by = meta.get("ended_by") or "unknown (no end recorded)"
    code = meta.get("supervisor_exit_code")
    judgement = judge_soak(analysis, sc, meta.get("hours"), ended_by, code if ended_by.startswith("booth.sh ended") else None)
    report = {"verdict": judgement["verdict"], "judgement": judgement, "analysis": analysis, "start": meta.get("start"),
              "hours_requested": meta.get("hours"), "ended_by": ended_by, "supervisor_exit_code": code,
              "booth_cmd": meta.get("booth_cmd"), "soak_config": sc,
              "files": {"report": str(folder / "soak_report.json"), "samples": str(folder / "soak.csv")}}
    (folder / "soak_report.json").write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m wfglink.soak",
                                 description="Analyse a soak folder again (scripts/mac_soak.py runs a soak).")
    ap.add_argument("folder", help="a soak folder with soak_meta.json and soak.csv (logs/soak/<date-time>)")
    args = ap.parse_args(argv)
    report = reanalyse(args.folder)
    print(format_report(report))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
