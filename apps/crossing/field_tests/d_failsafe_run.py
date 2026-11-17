"""Test D run script: walk the operator through each fault while recording the crossing app's live State.

Connects to the crossing app's browser socket (default ws://127.0.0.1:8781/ws, DESIGN.md section 9) and records
every State summary with this laptop's receipt time to <run>/states.jsonl.gz. Optionally (--pi) it also records the
unit's raw stream into <run>/pi/ with recordkit (useful to see what the Pi itself reported).

For each fault (see FAULTS in d_failsafe_analyse.py): prepare prompt (Enter) -> 3-2-1 countdown -> mark
`fault_inject` at NOW (operator acts at NOW) -> live display of time to CLOSED (up to --timeout-s) -> restore
prompt (Enter) -> mark `fault_restore` -> wait for the sensor to be fresh again (up to --recover-s). At the end the
analysis runs and prints the table. The live time printed uses the same attribution rule as the analysis: a CLOSED
counts only when a reason code / health flag of that fault APPEARED compared with the last State before NOW (exact
codes; bench reasons such as RADAR_UNKNOWN or GNSS_NO_FIX never count). thermal_freeze needs --pi: its fault time
is taken afterwards from the received thermal frames (the sim session's freeze time T is not visible to the
operator, so NOW can be off by seconds); the live number for it is provisional and the analysis is the result. No fire is involved; see protocols/D_failsafe.md for the safety notes
(12 V plug, USB hot-unplug).

Usage (from apps/crossing, with the app running: python -m crossing --pi ws://10.42.0.1:8770/stream):
  .venv/bin/python -m field_tests.d_failsafe_run --faults thermal_unplug,radar_unplug,wifi_drop
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common, recordkit  # noqa: E402
from field_tests.d_failsafe_analyse import (FAULTS, PRE_MAX_AGE_S, analyse, attributable, cause_before,  # noqa: E402
                                            sensor_up, summarize_state)


class StateLog:
    def __init__(self, run_dir: Path):
        self.fh = gzip.open(run_dir / "states.jsonl.gz", "wt", compresslevel=5)
        self.latest = None
        self.n = 0
        self.connected = False

    def add(self, state: dict, t_rx: float) -> dict:
        s = summarize_state(state)
        s["t_rx"] = t_rx
        self.fh.write(json.dumps(s) + "\n")
        self.latest = s
        self.n += 1
        return s

    def link(self, kind: str, detail: str, t_rx: float) -> None:
        self.fh.write(json.dumps({"t_rx": t_rx, "verdict": None, "app_link": kind, "detail": detail, "fresh": {},
                                  "reasons": [], "link": None}) + "\n")

    def close(self):
        self.fh.close()


async def app_client(url: str, log: StateLog, stop: asyncio.Event) -> None:
    import websockets
    while not stop.is_set():
        try:
            async with websockets.connect(url, open_timeout=3.0, max_size=2 ** 24) as ws:
                log.connected = True
                log.link("connect", url, time.monotonic())
                while not stop.is_set():
                    try:
                        text = await asyncio.wait_for(ws.recv(), timeout=0.25)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        state = json.loads(text)
                    except (TypeError, ValueError):
                        continue
                    if isinstance(state, dict):
                        log.add(state, time.monotonic())
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            if log.connected:
                log.link("disconnect", str(exc), time.monotonic())
            log.connected = False
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass


async def ainput(prompt: str) -> str:
    print(prompt, end="", flush=True)
    return (await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)).strip()


async def run(args, run_dir: Path, marks: recordkit.SessionWriter, log: StateLog) -> None:
    stop = asyncio.Event()
    tasks = [asyncio.create_task(app_client(args.app, log, stop))]
    pi_writer = None
    if args.pi:
        pi_writer = recordkit.SessionWriter(run_dir / "pi")
        tasks.append(asyncio.create_task(recordkit.run_ws(args.pi, pi_writer, stop)))
    try:
        t0 = time.monotonic()
        while log.latest is None and time.monotonic() - t0 < 15:
            await asyncio.sleep(0.2)
        if log.latest is None:
            print("No State from %s within 15 s: is the crossing app running?" % args.app, file=sys.stderr)
            marks.mark("abort", "no state from the app")
            return
        for fid in args.faults:
            f = FAULTS[fid]
            if fid == "thermal_freeze" and not args.pi:
                print("WARNING: thermal_freeze without --pi: no thermal frames are recorded, so the fault time is "
                      "unknown and the analysis reports this row as NOT_MEASURED.", file=sys.stderr)
            print("\n=== Fault %s ===\n%s" % (fid, f.expected))
            if f.prepare:
                print("Prepare: %s" % f.prepare)
            st = log.latest
            print("Current verdict: %s   link: %s" % (st.get("verdict"), st.get("link")))
            ans = await ainput("Press Enter to start the countdown (s = skip, q = quit): ")
            if ans.lower() == "q":
                break
            if ans.lower() == "s":
                marks.mark("fault_skipped", ans, fault=fid)
                continue
            for k in (3, 2, 1):
                print("  %d ..." % k, flush=True)
                await asyncio.sleep(1.0)
            pre = log.latest                                   # last State received before NOW
            m = marks.mark("fault_inject", f.inject, fault=fid, sensors=list(f.sensors),
                           pre_verdict=pre.get("verdict") if pre else None)
            print(">>> NOW: %s" % f.inject, flush=True)
            t_m = m["t_rx"]
            got = None
            if pre is None or time.monotonic() - pre["t_rx"] > PRE_MAX_AGE_S:
                print("    no State within %.1f s before NOW: this fault cannot be timed (NOT_ATTRIBUTABLE)"
                      % PRE_MAX_AGE_S)
            elif cause_before(pre, f.sensors):
                print("    the fault's cause was already visible before NOW: cannot be timed (NOT_ATTRIBUTABLE)")
            else:
                while time.monotonic() - t_m < args.timeout_s:
                    s = log.latest
                    if s is not None and s["t_rx"] >= t_m and attributable(s, f.sensors, pre):
                        got = s["t_rx"] - t_m
                        break
                    await asyncio.sleep(0.05)
                tag = " (provisional: timed from NOW, the analysis times it from the thermal frames)" \
                    if fid == "thermal_freeze" else ""
                print("    CLOSED after %.2f s (%s)%s" % (got, "PASS" if got <= 2.0 else "FAIL > 2 s", tag)
                      if got is not None else "    no fault-attributed CLOSED within %.0f s (FAIL)%s"
                      % (args.timeout_s, tag))
            await ainput("Restore: %s. Press Enter when done: " % f.restore)
            mr = marks.mark("fault_restore", f.restore, fault=fid)
            while time.monotonic() - mr["t_rx"] < args.recover_s:
                s = log.latest
                if s is not None and s["t_rx"] >= mr["t_rx"] and sensor_up(s, f.sensors):
                    print("    sensor fresh again after %.1f s" % (s["t_rx"] - mr["t_rx"]))
                    break
                await asyncio.sleep(0.2)
            else:
                print("    sensor not fresh again within %.0f s" % args.recover_s)
    finally:
        stop.set()
        for t in tasks:
            try:
                await asyncio.wait_for(t, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                t.cancel()
        if pi_writer is not None:
            pi_writer.close({"test": "D", "role": "pi copy"})


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test D: fail-safe fault injection with timing")
    p.add_argument("--app", default=common.DEFAULT_APP_URL, help="crossing app State socket")
    p.add_argument("--pi", help="also record the unit stream (e.g. ws://10.42.0.1:8770/stream)")
    p.add_argument("--faults", default=",".join(k for k in FAULTS if k != "thermal_freeze"),
                   help="comma list from: %s" % ", ".join(FAULTS))
    p.add_argument("--timeout-s", type=float, default=10.0)
    p.add_argument("--recover-s", type=float, default=120.0)
    p.add_argument("--operator", default="")
    p.add_argument("--out", default=str(common.RECORDS / "D"))
    args = p.parse_args(argv)
    args.faults = [f.strip() for f in args.faults.split(",") if f.strip()]
    unknown = [f for f in args.faults if f not in FAULTS]
    if unknown:
        print("unknown fault(s): %s" % ", ".join(unknown), file=sys.stderr)
        return 2
    run_id = "D_%s" % common.utc_stamp()
    run_dir = Path(args.out) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    marks = recordkit.SessionWriter(run_dir)       # used for marks.jsonl only (no Pi messages go into it)
    log = StateLog(run_dir)
    trial = common.base_meta("D", argv)
    trial.update({"run_id": run_id, "faults": args.faults, "app_url": args.app, "pi_url": args.pi,
                  "operator": args.operator, "simulated": False})
    try:
        asyncio.run(run(args, run_dir, marks, log))
    except KeyboardInterrupt:
        marks.mark("operator_stop", "Ctrl-C")
    finally:
        log.close()
        trial["n_states"] = log.n
        marks.close(trial)
    res = analyse(run_dir / "analysis", run_dir=run_dir)
    print(res["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
