"""Live received-signal-strength chart for the two-ESP32 booth demo.

Usage: python live_chart.py /dev/tty.usbserial-XXXX   (macOS) or COM5 (Windows)
Reads "millis,seq,rssi" lines from the receiver board, plots RSSI (1 dB steps) with a rolling
baseline, and shows the same two detectors used in the study: drop below the baseline and a
jump in rolling variance. Requires: pip install pyserial matplotlib numpy
"""
import collections
import sys

import matplotlib.pyplot as plt
import numpy as np
import serial
from matplotlib.animation import FuncAnimation

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
WINDOW_S, BASE_S, VAR_S = 60.0, 20.0, 2.0
DROP_DB, VAR_RATIO = 4.0, 3.0

ser = serial.Serial(PORT, 115200, timeout=0.05)
t = collections.deque(maxlen=6000)
r = collections.deque(maxlen=6000)
lost = {"last": None, "n": 0}

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
(l_rssi,) = ax1.plot([], [], color="#0072B2", lw=1, label="RSSI")
(l_base,) = ax1.plot([], [], color="#000000", lw=1.5, ls="--", label="Baseline (rolling median)")
(l_sd,) = ax2.plot([], [], color="#D55E00", lw=1.5, label="Rolling std (2 s)")
status = ax1.text(0.01, 0.95, "", transform=ax1.transAxes, va="top", fontsize=14, weight="bold")
ax1.set_ylabel("RSSI (dBm)")
ax2.set_ylabel("Std (dB)")
ax2.set_xlabel("Time (s)")
ax1.legend(loc="lower left")
ax2.legend(loc="upper left")


def update(_):
    while ser.in_waiting:
        line = ser.readline().decode(errors="ignore").strip()
        parts = line.split(",")
        if len(parts) != 3:
            continue
        try:
            ms, seq, rssi = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if lost["last"] is not None and seq > lost["last"] + 1:
            lost["n"] += seq - lost["last"] - 1
        lost["last"] = seq
        t.append(ms / 1000.0)
        r.append(rssi)
    if len(t) < 10:
        return l_rssi, l_base, l_sd, status
    ta, ra = np.array(t), np.array(r, float)
    keep = ta > ta[-1] - WINDOW_S
    ta, ra = ta[keep], ra[keep]
    base = np.array([np.median(ra[(ta > x - BASE_S) & (ta <= x - 1.0)]) if np.any((ta > x - BASE_S) & (ta <= x - 1.0)) else np.nan for x in ta])
    sd = np.array([np.std(ra[(ta > x - VAR_S) & (ta <= x)]) for x in ta])
    sd_base = np.nanmedian(sd[: max(len(sd) // 2, 1)])
    l_rssi.set_data(ta, ra)
    l_base.set_data(ta, base)
    l_sd.set_data(ta, sd)
    drop = np.nanmedian(base[-10:]) - np.median(ra[-10:])
    alarm = drop >= DROP_DB or sd[-1] >= VAR_RATIO * max(sd_base, 0.5)
    status.set_text(f"{'ALARM' if alarm else 'normal'}  drop {drop:.1f} dB  lost packets {lost['n']}")
    status.set_color("#D55E00" if alarm else "#009E73")
    ax1.set_xlim(ta[0], ta[-1])
    ax1.set_ylim(ra.min() - 5, ra.max() + 5)
    ax2.set_ylim(0, max(sd.max() * 1.2, 2))
    return l_rssi, l_base, l_sd, status


ani = FuncAnimation(fig, update, interval=200, cache_frame_data=False)
plt.show()
