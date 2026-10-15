"""Overnight soak (check C): a heartbeat sampler and the morning analysis.

The booth supervisor (booth/booth.sh) keeps the app running and the app rewrites
logs/heartbeat.json every 2 s (fps, paints, source, errors, memory). During the soak a
small sampler process copies that heartbeat into a CSV once a minute:

    python -m wfglink.sitting.soak sample --heartbeat logs/heartbeat.json --out SOAK.csv --every 60

It writes its pid to a pid file (default: next to the CSV) and stops cleanly on SIGTERM
or SIGINT. In the morning `analyse_soak` turns the CSV and logs/booth.log into:

- hours of soak (to the finish, or to a clean exit: Esc pressed twice ends the soak, since
  booth.sh stops with it), hours with the booth running, the share of samples with a live
  heartbeat, and gaps in the sampling (the Mac slept or restarted);
- paint fps (from the change in the painted-frame counter between samples of the same
  app instance) with median, 5th percentile and minimum: each value is the average over
  one sampling interval;
- memory slope in MB per hour: a linear fit of resident memory (app plus process
  worker) against time over the last `last_h` hours (all data when shorter), leaving out
  each app instance's warm-up. Restarts reset memory, so the fit is pooled within app
  instances (each instance keeps its own offset, all share one slope); a sample whose
  worker memory could not be read is left out rather than summed short;
- restarts: "app ended" lines that booth.sh wrote during the soak (rotated logs too),
  with the app instances seen in the samples as a check;
- source switches and processing errors seen in the heartbeat;
- whether the app kept analysing (`pipeline_progress`): the share of frames read clean,
  the source coverage in booth mode, and stalls in which frames arrived but none was
  analysed (a failure the screen check missed).

    python -m wfglink.sitting.soak analyse --csv SOAK.csv --start EPOCH [--end EPOCH]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np

# Pipeline counters from the heartbeat (wfglink.pipeline.HEARTBEAT_COUNTERS): CSV column -> counter.
PIPE_COLUMNS = {"pipe_in": "frames_in", "pipe_analysed": "frames_analysed", "pipe_duplicate": "frames_duplicate",
                "pipe_unclean": "frames_unclean", "pipe_no_code": "frames_no_code", "pipe_loops": "loops",
                "pipe_advance": "source_advance"}
COLUMNS = ["sample_epoch", "sample_time", "hb_epoch", "hb_age_s", "status", "pid", "uptime_s", "frames", "paints",
           "fps", "source", "state", "errors", "last_error", "rss_mb", "rss_detail", "hb_status",
           "pipe_key", *PIPE_COLUMNS]
LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[booth\.sh\] (.*)$")


# Sampling ----------------------------------------------------------------------------------

def read_heartbeat(path: str | Path) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def sample_row(hb: dict[str, Any] | None, now: float | None = None, stale_s: float = 30.0) -> dict[str, Any]:
    """One CSV row from a heartbeat (or a 'missing' row when there is none)."""
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
    # The sum covers the app and its process worker; when one of them could not be read the
    # sum would drop by that process's memory and look like a release, so it is left empty.
    vals = [float(v) for v in rss.values()] if all(v is not None for v in rss.values()) else []
    row.update({
        "hb_epoch": round(hb_epoch, 3), "hb_age_s": round(age, 1) if math.isfinite(age) else "",
        "status": hb.get("status", "") if age <= stale_s else "stale",
        "pid": hb.get("pid", ""), "uptime_s": hb.get("uptime_s", ""), "frames": hb.get("frames", ""),
        "paints": hb.get("paints", ""), "fps": hb.get("fps", ""), "source": hb.get("source", ""),
        "state": hb.get("state", ""), "errors": hb.get("errors", ""),
        "last_error": (hb.get("last_error") or "")[:200],
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


def run_sampler(heartbeat: str | Path, csv_path: str | Path, every_s: float = 60.0,
                pid_file: str | Path | None = None, stale_s: float = 30.0, max_samples: int | None = None) -> int:
    """Sample until SIGTERM or SIGINT (or max_samples). Writes and removes the pid file."""
    pid_path = Path(pid_file) if pid_file else Path(csv_path).with_name("soak_sampler.pid")
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))
    stop = {"now": False}

    def _stop(signum, frame):  # noqa: ARG001
        stop["now"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    n = 0
    try:
        while not stop["now"]:
            sample_once(heartbeat, csv_path, stale_s)
            n += 1
            if max_samples is not None and n >= max_samples:
                break
            t_next = time.monotonic() + every_s
            while not stop["now"] and time.monotonic() < t_next:
                time.sleep(min(0.5, max(0.0, t_next - time.monotonic())))
    finally:
        try:
            if pid_path.read_text().strip() == str(os.getpid()):
                pid_path.unlink()
        except OSError:
            pass
    return 0


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
                r[k] = _num(r.get(k))     # pipeline columns are None in a CSV from an older sampler
            r["pid"] = str(r.get("pid") or "")
            try:   # the processes whose memory was summed: the app, plus its worker in process mode
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
    """Paint rate between consecutive samples of the same app instance (painted frames per second)."""
    out = []
    live = _live(rows)
    for a, b in zip(live, live[1:]):
        if a["pid"] != b["pid"] or a["paints"] is None or b["paints"] is None:
            continue
        dt_s = b["hb_epoch"] - a["hb_epoch"]
        if dt_s <= 0.5 or b["paints"] < a["paints"]:
            continue
        out.append((b["paints"] - a["paints"]) / dt_s)
    return out


def mem_slope(rows: list[dict[str, Any]], last_h: float = 6.0, warmup_s: float = 600.0) -> dict[str, Any]:
    """Memory slope (MB per hour), pooled within app instances, over the last `last_h` hours.

    An instance is one app pid with one set of measured processes: a process worker that is
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
    """Supervisor events written by booth.sh between start and end (local time, 1 s resolution)."""
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


def source_changes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Source switches and processing errors seen in the samples."""
    live = _live(rows)
    named = [r for r in live if r.get("source")]     # an app before its first frame has no source yet
    switches, transitions = 0, []
    for a, b in zip(named, named[1:]):
        ka, kb = (a["source"], a["state"]), (b["source"], b["state"])
        if ka != kb:
            switches += 1
            if len(transitions) < 20:
                transitions.append({"at": b["sample_time"], "from": "/".join(ka), "to": "/".join(kb)})
    errors: dict[str, float] = {}
    last_error = ""
    for r in live:
        if r["errors"] is not None:
            errors[r["pid"]] = max(errors.get(r["pid"], 0.0), r["errors"])
        if r.get("last_error"):
            last_error = r["last_error"]
    states: dict[str, int] = {}
    for r in rows:
        key = r.get("state") or r.get("status") or "?"
        if r.get("status") in ("missing", "stale"):
            key = r["status"]
        states[key] = states.get(key, 0) + 1
    return {"switches": switches, "transitions": transitions, "errors": int(sum(errors.values())),
            "last_error": last_error or None, "samples_by_state": states}


def pipeline_progress(rows: list[dict[str, Any]], stall_s: float = 180.0) -> dict[str, Any]:
    """Whether the app kept analysing, from the heartbeat's pipeline counters.

    Counters are compared between consecutive samples of the same app instance and the
    same source (they restart on a restart or a source switch). Reported:
    - clean_fraction: frames analysed or recognised as a repeat of the last one, over the
      frames received (in booth mode, camera frames whose screen codes read clean);
    - coverage (booth mode): new source frames analysed over source frames shown, the
      quantity check B's hold rule is built on;
    - stalls: stretches of at least stall_s in which frames kept arriving but none was
      analysed, or no frame arrived, while the app was alive on one source. A paused or
      lost screen should make the source chain fall back within seconds, so a long stall is
      a failure the screen check missed. The cause is the counter that grew most.
    """
    live = [r for r in _live(rows) if r.get("pipe_in") is not None]
    tot = {"in": 0.0, "analysed": 0.0, "duplicate": 0.0, "advance": 0.0}
    stalls: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    intervals = 0

    def close() -> None:
        nonlocal cur
        if cur is not None and cur["s"] >= stall_s:
            cause = max(cur["grew"], key=cur["grew"].get) if any(cur["grew"].values()) else "no_input"
            stalls.append({"at": cur["at"], "minutes": round(cur["s"] / 60.0, 1), "cause": cause})
        cur = None

    for a, b in zip(live, live[1:]):
        if a["pid"] != b["pid"] or a.get("pipe_key") != b.get("pipe_key"):
            close()
            continue
        d = {col: (b[col] or 0.0) - (a[col] or 0.0) for col in PIPE_COLUMNS}
        if any(v < 0 for v in d.values()):     # counters restarted (a new pipeline under the same key)
            close()
            continue
        intervals += 1
        tot["in"] += d["pipe_in"]
        tot["analysed"] += d["pipe_analysed"]
        tot["duplicate"] += d["pipe_duplicate"]
        tot["advance"] += d["pipe_advance"]
        if d["pipe_analysed"] > 0:
            close()
            continue
        if cur is None:
            cur = {"at": a["sample_time"], "s": 0.0, "grew": {"repeated": 0.0, "unclean": 0.0, "no_code": 0.0}}
        cur["s"] += b["hb_epoch"] - a["hb_epoch"]
        cur["grew"]["repeated"] += d["pipe_duplicate"]
        cur["grew"]["unclean"] += d["pipe_unclean"]
        cur["grew"]["no_code"] += d["pipe_no_code"]
    close()
    if intervals == 0:
        return {"intervals": 0, "verdict": "not enough data"}
    return {
        "intervals": intervals, "frames_in": int(tot["in"]), "frames_analysed": int(tot["analysed"]),
        "clean_fraction": round((tot["analysed"] + tot["duplicate"]) / tot["in"], 4) if tot["in"] else None,
        "coverage": round(tot["analysed"] / tot["advance"], 4) if tot["advance"] else None,
        "stall_s": stall_s, "stalls": len(stalls), "stall_minutes": round(sum(s["minutes"] for s in stalls), 1),
        "longest_stall_min": max((s["minutes"] for s in stalls), default=0.0), "stall_list": stalls[:20],
        "verdict": "fail" if stalls else "pass",
    }


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
                 min_hours: float = 1.0, stall_s: float = 180.0) -> dict[str, Any]:
    """The morning analysis. A clean exit (Esc pressed twice) ends the soak, because booth.sh
    stops with it: later samples come from whatever runs afterwards (for example the booth
    started for the rehearsal) and are left out, as is the time after it."""
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
    first, last = rows[0]["sample_epoch"], rows[-1]["sample_epoch"]
    hours = ((end_epoch or last) - start_epoch) / 3600.0
    pfps = paint_fps_series(rows)
    live = _live(rows)
    proc = [r["fps"] for r in live if r["fps"] is not None]
    mem = mem_slope(rows, last_h=last_h, warmup_s=warmup_s)
    if mem["slope_mb_h"] is None or mem["span_h"] < min_hours:
        mem_verdict = "not enough data"
    else:
        mem_verdict = "pass" if mem["slope_mb_h"] <= mem_max_mb_h else "fail"
    logs = count_log_events(log, start_epoch, end_epoch)
    src = source_changes(rows)
    pids = [r["pid"] for r in live]
    pid_changes = sum(1 for a, b in zip(pids, pids[1:]) if a != b)
    n_gaps, gap_h = sampling_gaps(rows)
    n_fresh = sum(1 for r in rows if r.get("status") not in ("missing", "stale") and r["pid"] and r["hb_epoch"])
    return {
        "ok": True, "hours": round(hours, 3), "ended_by": ended_by,
        "hours_running": round(min(hours, ((live[-1]["hb_epoch"] if live else start_epoch) - start_epoch) / 3600.0), 3),
        "samples": len(rows), "samples_live": len(live), "live_fraction": round(n_fresh / len(rows), 3),
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
        "source_switches": src["switches"], "source_transitions": src["transitions"],
        "errors": src["errors"], "last_error": src["last_error"], "samples_by_state": src["samples_by_state"],
        "pipeline": pipeline_progress(rows, stall_s=stall_s),
    }


# Command line ------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m wfglink.sitting.soak", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="copy the booth heartbeat into a CSV every few seconds until stopped")
    s.add_argument("--heartbeat", default="logs/heartbeat.json")
    s.add_argument("--out", required=True, help="CSV file (appended)")
    s.add_argument("--every", type=float, default=60.0, help="seconds between samples")
    s.add_argument("--pid-file", default=None, help="default: soak_sampler.pid next to the CSV")
    s.add_argument("--stale-s", type=float, default=30.0)
    s.add_argument("--max-samples", type=int, default=None)
    a = sub.add_parser("analyse", help="soak statistics from the CSV and logs/booth.log")
    a.add_argument("--csv", required=True)
    a.add_argument("--log", default="logs/booth.log")
    a.add_argument("--start", type=float, required=True, help="soak start, Unix epoch seconds")
    a.add_argument("--end", type=float, default=None)
    args = ap.parse_args(argv)
    if args.cmd == "sample":
        return run_sampler(args.heartbeat, args.out, args.every, args.pid_file, args.stale_s, args.max_samples)
    print(json.dumps(analyse_soak(args.csv, args.log, args.start, args.end), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
