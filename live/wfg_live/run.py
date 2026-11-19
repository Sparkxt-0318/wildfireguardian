"""One live run: fetch -> compute -> bulletin day -> alerts -> pages -> log record (PROTOCOL §2-§10).

    python3 -m wfg_live run --site SITE --log LOGROOT [--work WORK] [--cache CACHE]
    python3 -m wfg_live replay --inputs DIR --out OUT          # compute only, from stored inputs (as of the issue time)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import alerts, common as C, compute, fetch, pages


def commit_id():
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.run(["git", "-C", str(C.REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def bulletin_day(rec, state):
    """Cells on at any issue hour of the KST day so far (state kept in the log)."""
    T = C.parse_iso(rec["issue_utc"]).astimezone(C.KST)
    day = T.strftime("%Y-%m-%d")
    b = state.get("bulletin")
    if not b or b.get("date_kst") != day:
        b = {"date_kst": day, "hours": {}, "single_exit_by_cell": {}}
    on = [[c["lat0"], c["lon0"]] for c in rec["bulletin"]["cells"] if c["state"]]
    if not rec["bulletin"].get("error"):
        b["hours"][T.strftime("%H")] = on
        for c in rec["bulletin"]["cells"]:
            if c["state"]:
                b["single_exit_by_cell"]["%s,%s" % (c["lat0"], c["lon0"])] = c.get("single_exit_places", [])
    state["bulletin"] = b
    cells = sorted({tuple(x) for v in b["hours"].values() for x in v})
    return {"date_kst": day, "hours": sorted(h for h, v in b["hours"].items() if v), "cells_on_today": [list(c) for c in cells],
            "single_exit_by_cell": b["single_exit_by_cell"]}


def write_log(log: Path, rec, inputs: Path):
    """records/YYYY/MM/DD/<stamp>.json + inputs/<stamp>/ (GFS once per cycle in inputs/gfs/)."""
    T = C.parse_iso(rec["issue_utc"])
    st = C.stamp(T)
    rdir = log / "records" / T.strftime("%Y/%m/%d")
    idir = log / "inputs" / st
    idir.mkdir(parents=True, exist_ok=True)
    (log / "inputs/gfs").mkdir(parents=True, exist_ok=True)
    for p in sorted(inputs.iterdir()):
        if p.name.startswith("gfs_") and p.suffix == ".npz":
            dst = log / "inputs/gfs" / p.name
            if not dst.exists():
                shutil.copy(p, dst)
        elif p.is_file():
            shutil.copy(p, idir / p.name)
    path = rdir / (st + ".json")
    b = C.dump(path, rec)
    return path, C.sha256(b)


def cmd_run(a):
    T = C.utcnow().replace(second=0)
    if a.issue:
        T = C.parse_iso(a.issue)
    work = Path(a.work)
    if work.exists():
        shutil.rmtree(work)
    inputs = work / "inputs"
    cache = Path(a.cache) if a.cache else None
    man = fetch.fetch_all(inputs, T, cache=cache, skip=tuple(a.skip or ()))
    rec = compute.compute(inputs, work / "road", replay=False)
    log = Path(a.log)
    state_p = log / "state.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    rec["bulletin_day"] = bulletin_day(rec, state)
    msgs = alerts.decide(rec, state.setdefault("alerts", {}))
    rec["alerts"] = alerts.send(msgs) | {"messages": [m["kind"] for m in msgs]}
    rec["run"] = {"commit": commit_id(), "event": os.environ.get("GITHUB_EVENT_NAME", "local"),
                  "trigger": os.environ.get("LIVE_TRIGGER") or None,
                  "workflow_run": ("%s/%s/actions/runs/%s" % (os.environ.get("GITHUB_SERVER_URL"), os.environ.get("GITHUB_REPOSITORY"),
                                                             os.environ.get("GITHUB_RUN_ID"))) if os.environ.get("GITHUB_RUN_ID") else None,
                  "replay": False, "fetch_finished_utc": man.get("fetch_finished_utc"), "compute_finished_utc": C.iso(C.utcnow())}
    rec["pages"] = pages.build(rec, work / "road", Path(a.site))
    path, sha = write_log(log, rec, inputs)
    C.dump(state_p, state)
    summary = {"record": str(path.relative_to(log)), "sha256": sha, "issue_utc": rec["issue_utc"], "kfs_ok": rec["kfs_ok"],
               "firms_ok": rec["firms_ok"], "gfs_ok": rec["gfs_ok"], "ahi_ok": rec["ahi_ok"], "listed": len(rec["listed"]),
               "in_scope": len(rec["fires"]), "bulletin_on": rec["bulletin"].get("n_on"), "alerts": rec["alerts"]}
    print(json.dumps(summary, ensure_ascii=False))
    if a.summary:
        Path(a.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


REPLAY_DROP = ("run", "alerts", "pages", "bulletin_day")


def cmd_replay(a):
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    rec = compute.compute(Path(a.inputs), out / "road", replay=True, with_cards=not a.no_cards)
    C.dump(out / "record.json", {k: v for k, v in rec.items() if k not in REPLAY_DROP})
    if a.site:
        rec.setdefault("bulletin_day", {})
        pages.build(rec, out / "road", Path(a.site))
    print(out / "record.json")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="wfg_live")
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--site", required=True)
    r.add_argument("--log", required=True)
    r.add_argument("--work", default="live-work")
    r.add_argument("--cache")
    r.add_argument("--issue", help="override the issue time (drills only)")
    r.add_argument("--skip", action="append", choices=["kfs", "firms", "ahi", "gfs"])
    r.add_argument("--summary")
    p = sp.add_parser("replay")
    p.add_argument("--inputs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--site")
    p.add_argument("--no-cards", action="store_true")
    a = ap.parse_args(argv)
    return {"run": cmd_run, "replay": cmd_replay}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
