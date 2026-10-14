"""Run the booth display.

    python -m lastgasp_demo --sim                 # simulator, live window
    python -m lastgasp_demo --sim --headless --duration 150 --snapshots 40,80,150 --out out/
    python -m lastgasp_demo --serial /dev/tty.usbserial-0001
    python -m lastgasp_demo --ble

Run from the demo/ folder (or put demo/ on PYTHONPATH).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Last Gasp booth display")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--sim", action="store_true", help="simulated heartbeats (default)")
    src.add_argument("--serial", metavar="PORT", help="JSON-lines receiver on a serial port")
    src.add_argument("--ble", action="store_true", help="scan BLE advertisements directly")
    ap.add_argument("--village", default=str(HERE / "village.json"))
    ap.add_argument("--interval", type=float, default=1.0, help="heartbeat interval (s)")
    ap.add_argument("--timeout-beats", type=int, default=3)
    ap.add_argument("--speed", type=float, default=1.0, help="simulator time multiplier")
    ap.add_argument("--no-spot", action="store_true", help="simulator without a spot fire")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--headless", action="store_true", help="no window; write PNG snapshots")
    ap.add_argument("--duration", type=float, default=160.0, help="headless run length (s)")
    ap.add_argument("--snapshots", default="40,80,160", help="headless snapshot times (s)")
    ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)

    import matplotlib
    if a.headless:
        matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    from .render import Display
    from .sources import BleSource, SerialSource, SimulatorSource
    from .state import DemoState

    village = json.loads(Path(a.village).read_text())
    if a.serial:
        source, label = SerialSource(a.serial), "LIVE  serial"
    elif a.ble:
        source, label = BleSource(), "LIVE  BLE"
    else:
        source, label = SimulatorSource(village, a.interval, spot=not a.no_spot, seed=a.seed), "SIMULATOR"
    st = DemoState(village, a.interval, a.timeout_beats)
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    disp = Display(fig, village, label)

    if a.headless:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        snaps = sorted(float(s) for s in a.snapshots.split(",") if s)
        t, dt = 0.0, 0.25
        while t <= a.duration + 1e-9:
            st.ingest(source.poll(t))
            st.update(t)
            for s in [s for s in snaps if s <= t]:
                disp.draw(st, t)
                fig.savefig(out / f"demo_t{int(s):04d}.png", facecolor=fig.get_facecolor())
                snaps.remove(s)
            t += dt
        print(f"burned {int(st.dead.sum())} of {len(st.ids)}, spot fires {len(st.spots)}: "
              + ", ".join(f"node {s['id']} ({s['jump_m']:.0f} m)" for s in st.spots))
        for t_e, msg in st.events:
            print(f"{t_e:7.2f}s  {msg}")
        return st

    t0 = time.monotonic()
    plt.ion()
    plt.show(block=False)
    try:
        while plt.fignum_exists(fig.number):
            now = (time.monotonic() - t0) * (a.speed if not (a.serial or a.ble) else 1.0)
            st.ingest(source.poll(now))
            st.update(now)
            disp.draw(st, now)
            fig.canvas.draw_idle()
            plt.pause(0.2)
    except KeyboardInterrupt:
        pass
    return st


if __name__ == "__main__":
    main()
