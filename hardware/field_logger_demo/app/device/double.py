"""A simulated logger for development and tests (the app reaches it only with --dev-device-double).

It follows firmware 0.2.0 closely: the replies of wfg_proto.cpp and main.cpp handleSerial() (including the
'recording-active' refusals, VBAT and CALVBAT), the '#' lines of main.cpp banner() and setup(), the button rules of
handleGesture(), the gap filler of wfg_logger.cpp (a NOFIX row every 1.5 s while the receiver has no time), STATUS
records every 60 s, boot recovery (an unclosed session is closed RECOVERED_ON_BOOT) and the auto-resume rules of
wfg_resume.h (max_quick_fails 3, reset by an owner start or 60 s of resumed recording). With fw="0.3.0" it also prints
the LIVE lines of firmware 0.3.0 ('#J' and '#N').

The link talks to it through DoublePort, an in-process stand-in for an open pyserial port. A pseudo-terminal cannot
carry DTR and RTS, so this is how the double can restart on open (per open method), on close and on unplug, as the
connection check needs. Its device id is the reserved 00000000; the app watermarks everything from it and saves its
sessions under sessions/sim/device_double/. Records are written by the SIM writer (app/simgen.py), whose files pass
usb_export.py verify.
"""
import hashlib
import json
import math
import threading
import time

from .. import mapgen, simgen
from ..geo import Local
from ..vendor import usb_export as ux

TOTAL = 2_555_904            # LittleFS partition of the 4 MB board
META_B = 8_192               # meta.txt and directory blocks
BLOCK = 4_096
RESERVE = 32_768
START_MIN_FREE = RESERVE + 8_192
FILL_S = 1.506               # gap filler: 1500 ms plus loop latency
END_CODE = {"USER_STOP": 1, "STORAGE_FULL": 2, "LOW_BATTERY": 3, "RECOVERED_ON_BOOT": 4, "FS_ERROR": 5}
ROM_BOOT = ["ets Jul 29 2019 12:21:46", "", "rst:0x1 (POWERON_RESET),boot:0x13 (SPI_FAST_FLASH_BOOT)",
            "configsip: 0, SPIWP:0xee", "clk_drv:0x00,q_drv:0x00,d_drv:0x00,cs0_drv:0x00,hd_drv:0x00,wp_drv:0x00",
            "mode:DIO, clock div:1", "load:0x3fff0030,len:1344", "load:0x40078000,len:13964",
            "load:0x40080400,len:3600", "entry 0x400805f0"]
DOWNLOAD_BOOT = ["ets Jul 29 2019 12:21:46", "",
                 "rst:0x1 (POWERON_RESET),boot:0x3 (DOWNLOAD_BOOT(UART0/UART1/SDIO_REI_REO_V2))",
                 "waiting for download"]
UTC_BASE_MS = 1791900000000  # the receiver's time in the "time" and "fix" modes (2026-10-13 UTC)
FILLER_MODES = ("indoor", "nodata", "cksum")


class PortGone(OSError):
    pass


def nmea(body):
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    return "$%s*%02X" % (body, cs)


class RealClock:
    def __init__(self):
        self.t0 = time.monotonic()

    def __call__(self):
        return time.monotonic() - self.t0


class ManualClock:
    """Tests: time moves only when the test moves it."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class DoublePort:
    """The open port as the link sees it (read, write, flush, close, dtr, rts), like a pyserial port."""

    def __init__(self, dev, method):
        self.dev = dev
        self.method = method
        self.buf = bytearray()
        self.cond = threading.Condition()
        self.closed = False
        self.gone = False
        self.timeout = 0.05
        self.dtr = method != "lines_low"
        self.rts = method != "lines_low"

    def feed(self, data):
        with self.cond:
            self.buf += data
            self.cond.notify_all()

    def read(self, n=1):
        with self.cond:
            if not self.buf and not self.closed and not self.gone:
                self.cond.wait(self.timeout)
            if self.gone and not self.buf:
                raise PortGone("device disconnected")
            if self.closed:
                raise PortGone("port closed")
            out = bytes(self.buf[:n])
            del self.buf[:n]
            return out

    def write(self, data):
        if self.gone or self.closed:
            raise PortGone("device disconnected")
        self.dev.receive(bytes(data))
        return len(data)

    def flush(self):
        pass

    def close(self):
        with self.cond:
            if self.closed:
                return
            self.closed = True
            self.cond.notify_all()
        self.dev.port_closed(self)

    def unplugged(self):
        with self.cond:
            self.gone = True
            self.cond.notify_all()


class LoggerDouble:
    def __init__(self, fw="0.2.0", board="SIMULATED LOGGER (not real hardware)", device_id=0, clock=None,
                 gnss="indoor", battery=True, restart_on=None, stable_s=60.0, sessions=None, autostart=True,
                 boot_delay=0.05):
        self.fw = fw
        self.live_supported = tuple(int(x) for x in fw.split(".")[:3]) >= (0, 3, 0)
        self.board = board
        self.device_id = device_id
        self.clock = clock or RealClock()
        self.gnss = gnss                      # indoor | nodata | cksum | time | fix
        self.battery = battery
        self.restart_on = {"open_default": False, "open_lines_low": False, "close": False, "unplug": False}
        self.restart_on.update(restart_on or {})
        self.stable_s = stable_s
        self.boot_delay = boot_delay
        self.lock = threading.RLock()
        self.port = None
        self.present = True                   # USB cable plugged in (the port is listed)
        self.powered = True
        self.received = []                    # every line the host sent (tests check what the app never sends)
        self.sessions = dict(sessions or {})  # name -> bytes of closed (or recovered) sessions
        self.used_extra = 0                   # "fill storage" for tests
        self.fs_ok = True
        self.fs_fail_next_boot = False
        self.corrupt_next_dump = False
        self.dump_delay_s = 0.0               # tests: BEGIN this late (the firmware hashes the whole file first)
        self.download_next_boot = False
        self.cal = 1000
        self.vbat_pin = 2061
        self.nvs = {"rec_on": False, "rec_mode": "WALK", "rec_sess": 0, "rs_qf": 0, "mode": "WALK"}
        self.boots = 0
        self.alive = True
        self.loc = Local(*mapgen.CENTER)
        self._rxbuf = b""
        self._boot_state()
        self.thread = None
        if autostart:
            self.start()

    # ------------------------------------------------------------------ state reset at every boot
    def _boot_state(self):
        self.boot_t = self.clock()
        self.state = "IDLE"
        self.mode = self.nvs.get("mode", "WALK")
        self.screen_on = True
        self.last_input = self.clock()
        self.export_mode = False
        self.export_since = 0.0
        self.w = None
        self.cur = None
        self.cur_no = 0
        self.rec_t0 = 0.0
        self.next_row_t = 0.0
        self.next_status_t = 0.0
        self.next_idle_st = 0.0
        self.next_epoch_t = 0.0
        self.event_no = 0
        self.idle_seq = 0                     # Logger::seq() keeps the last session's count until the next start
        self.resumed = False
        self.nmea_ok = 0
        self.nmea_bad = 0
        self._nmea_t = None
        self.have_offset = False
        self.live = False
        self.live_nmea = False
        self.banner_text = ""
        self.boots += 1

    def start(self):
        self.thread = threading.Thread(target=self._ticker, daemon=True, name="logger-double")
        self.thread.start()

    def close(self):
        self.alive = False
        if self.port:
            self.port.unplugged()

    def mono(self, t=None):
        return 900 + int(round(((self.clock() if t is None else t) - self.boot_t) * 1000))

    # ------------------------------------------------------------------ output
    def out(self, line):
        """Serial.printf("...\\n") and banner(): lines end with LF."""
        p = self.port
        if p is not None and self.powered:
            p.feed((line + "\n").encode("utf-8"))

    def println(self, line):
        """Serial.println(): lines end with CR LF."""
        p = self.port
        if p is not None and self.powered:
            p.feed((line + "\r\n").encode("utf-8"))

    def banner(self, msg):
        self.banner_text = msg
        self.out("# " + msg)

    def live_json(self, obj):
        if self.live:
            self.out("#J " + json.dumps(dict({"v": 1}, **obj), separators=(",", ":")))

    # ------------------------------------------------------------------ port lifecycle
    def open_port(self, method):
        with self.lock:
            if not self.present:
                raise PortGone("no such device")
            if self.port is not None and not self.port.closed:
                raise PortGone("Resource busy")
            self.port = DoublePort(self, method)
            port = self.port
            restart = self.restart_on.get("open_" + method, False)
        if restart:
            threading.Timer(self.boot_delay, self.reset).start()
        return port

    def port_closed(self, port):
        with self.lock:
            if self.port is port:
                self.port = None
            restart = self.restart_on.get("close", False) and self.present
        if restart:
            self.reset()

    def unplug(self):
        with self.lock:
            self.present = False
            if self.port is not None:
                self.port.unplugged()
                self.port = None
            if not self.battery:
                self.powered = False          # no cell: the board loses power with the cable
            elif self.restart_on.get("unplug", False):
                self.reset()

    def replug(self):
        with self.lock:
            self.present = True
            if not self.powered:
                self.powered = True
                self.reset()                  # power returns: a fresh boot

    # ------------------------------------------------------------------ boot (main.cpp setup())
    def reset(self, reason=1):
        """EN reset, brownout or power-on: the ESP32 starts again and prints what the ROM and setup() print."""
        with self.lock:
            if not self.powered:
                return
            recovered = None
            if self.w is not None:            # cut mid-session: boot recovery closes it RECOVERED_ON_BOOT
                self.w.end(0, END_CODE["RECOVERED_ON_BOOT"])
                self.sessions[self.cur] = self.w.data()
                recovered = (self.cur, len(self.w.recs) - 1)
                self.w = None
            self._boot_state()
            if self.download_next_boot:
                self.download_next_boot = False
                for ln in DOWNLOAD_BOOT:
                    self.println(ln)
                self.state = "DOWNLOAD"
                return
            for ln in ROM_BOOT:
                self.println(ln)
            if self.fs_fail_next_boot:
                self.fs_ok = False
                self.fs_fail_next_boot = False
            if self.fs_ok and recovered:
                self.out("# RECOVERED %s records=%d torn_bytes=0 closed=1 unrecoverable=0" % recovered)
                self.banner("RECOVERED 1 session")
            self._resume(reason)
            if not self.fs_ok:
                self.banner("FS ERROR: see README")
                self.println("# LittleFS mount failed and partition is not blank. Not formatting automatically.")
                self.println("# To erase ALL data: send 'FORMAT ERASE-ALL-SESSIONS' over USB.")
            self.out("# WFG logger fw %s board %s device %08X" % (self.fw, self.board, self.device_id))

    def _resume(self, reason):
        nv = self.nvs
        if not nv["rec_on"]:
            return
        if not self.fs_ok:
            action = "BLOCKED_FS"
        elif nv["rs_qf"] >= 3:
            action = "GIVE_UP_LOOP"
        elif self.free() < START_MIN_FREE:
            action = "BLOCKED_FULL"
        else:
            action = "RESUME"
        self.out("# RESUME decision %s (was S%06d mode %s, reset_reason %d, quick_fails %d)"
                 % (action, nv["rec_sess"], nv["rec_mode"], reason, nv["rs_qf"]))
        if action == "RESUME":
            nv["rs_qf"] += 1
            self.mode = nv["rec_mode"]
            if self._start(start_reason=1, resumed_from=nv["rec_sess"]):
                self.banner("AUTO-RESUMED after reset")
            else:
                nv["rec_on"] = False
                self.banner("RESUME FAILED")
        elif action == "GIVE_UP_LOOP":
            nv["rec_on"] = False
            nv["rs_qf"] = 0
            self.banner("RESET LOOP: not resuming")
        elif action == "BLOCKED_FULL":
            nv["rec_on"] = False
            self.banner("FULL: not resuming")

    # ------------------------------------------------------------------ storage
    def used(self):
        files = sum(-(-len(d) // BLOCK) * BLOCK for d in self.sessions.values())
        if self.w is not None:
            files += -(-len(self.w.recs) * 48 // BLOCK) * BLOCK
        return META_B + files + self.used_extra

    def free(self):
        return max(0, TOTAL - self.used())

    def next_session_no(self):
        nums = [int(n[1:7]) for n in self.sessions]
        return max(nums + [self.cur_no, 0]) + 1

    # ------------------------------------------------------------------ recording (wfg_logger.cpp)
    def _start(self, start_reason=0, resumed_from=0):
        if self.free() < START_MIN_FREE:
            self.state = "FULL"
            return False
        no = self.next_session_no()
        self.cur_no = no
        self.cur = "S%06d.wfg" % no
        self.w = simgen.RecordWriter()
        now = self.clock()
        self.rec_t0 = now
        mono = self.mono(now)
        self.w.start(mono, self.device_id, no, self.mode, boot=self.boots, reset_reason=1,
                     start_reason=start_reason, resumed_from=resumed_from)
        self._wrote()
        if self.have_offset:                  # UTC known before the session: restated so the file stands alone
            self.w.clock(mono, UTC_BASE_MS + mono)
            self._wrote()
        self._status_record(now)
        self.state = "RECORDING"
        self.resumed = start_reason == 1
        self.event_no = 0
        self.next_status_t = now + 60.0
        self.next_row_t = now + (FILL_S if self.gnss in FILLER_MODES else 1.0)
        self.nvs.update({"rec_on": True, "rec_mode": self.mode, "rec_sess": no})
        if start_reason == 0:
            self.nvs["rs_qf"] = 0             # an owner start resets the reboot-loop guard
        self.live_json({"t": "ss", "ss": no, "md": self.mode,
                        "sr": "AUTO_RESUMED_AFTER_RESET" if start_reason else "OWNER_BUTTON"})
        return True

    def _stop(self, reason="USER_STOP"):
        self.w.end(self.mono(), END_CODE[reason])
        self._wrote()
        self.sessions[self.cur] = self.w.data()
        self.idle_seq = len(self.w.recs)
        self.live_json({"t": "se", "ss": self.cur_no, "er": reason, "n": len(self.w.recs)})
        self.w = None
        self.state = "FULL" if reason == "STORAGE_FULL" else "IDLE"
        self.nvs["rec_on"] = False
        self.resumed = False

    def _wrote(self):
        rec = self.w.recs[-1]
        self.live_json({"t": "rec", "seq": len(self.w.recs) - 1, "ty": rec[2], "b": len(self.w.recs) * 48,
                        "crc": "%08x" % int.from_bytes(rec[44:48], "little"), "hx": rec.hex()})

    def vbat_mv(self):
        return self.vbat_pin * 2 * self.cal // 1000

    def _status_record(self, t):
        self.w.status(self.mono(t), self.vbat_mv(), self.free(), TOTAL, self.nmea_ok, self.nmea_bad)
        self._wrote()
        self.live_json({"t": "st", "vb": self.vbat_mv(), "ff": self.free()})

    def _pos(self, t):
        """'fix' mode: walk round the park block on the pavement at 1.25 m/s (600 m a lap)."""
        corners = [mapgen.g2m(u, v) for u, v in ((-3.05, -2.05), (-1.95, -2.05), (-1.95, -0.95), (-3.05, -0.95))]
        legs = [(a, b, math.dist(a, b)) for a, b in zip(corners, corners[1:] + corners[:1])]
        d = ((t - self.rec_t0) * 1.25) % sum(L for _, _, L in legs)
        for (x0, y0), (x1, y1), L in legs:
            if d <= L:
                f = d / L
                return self.loc.ll(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
            d -= L
        return self.loc.ll(*corners[0])

    def _epoch(self, t):
        """One receiver epoch in the "time" and "fix" modes: 1 Hz, with time; a position only in "fix"."""
        mono = self.mono(t)
        utc = UTC_BASE_MS + mono
        fix = self.gnss == "fix"
        first = not self.have_offset
        self.have_offset = True
        lat = lon = None
        if fix:
            lat, lon = self._pos(t)
        if self.live_nmea and self.live:
            self._nmea_lines(utc, lat, lon)
        self.live_json({"t": "ep", "ms": mono, "utc": ux.fmt_iso_epoch(utc), "fix": 1 if fix else 0,
                        "q": 1 if fix else 0, "ft": "3D" if fix else "NONE", "su": 9 if fix else 0,
                        "hd": 0.9 if fix else None, "la": round(lat, 7) if fix else None,
                        "lo": round(lon, 7) if fix else None, "al": 31.0 if fix else None,
                        "sp": 1.25 if fix else None, "co": 90.0 if fix else None,
                        "nr": None if fix else "RECEIVER_NO_FIX", "rs": self.state,
                        "ss": self.cur_no if self.w is not None else None, "md": self.mode})
        if self.w is None:
            return
        if first:
            self.w.clock(mono, utc)
            self._wrote()
        if fix:
            self.w.fix(mono, utc, lat, lon, 31.0, 1.25, 90.0, 0.9, 9)
        else:
            self.w.nofix(mono, utc, 0, 1)
        self._wrote()

    def _filler(self, t):
        reason = {"indoor": 1, "nodata": 2, "cksum": 3}[self.gnss]
        if self.live_nmea and self.live and self.gnss == "indoor":
            self._nmea_lines(None, None, None)
        self.w.nofix(self.mono(t), None, 0, reason)
        self._wrote()

    def _nmea_lines(self, utc, lat, lon):
        if utc is None:
            for body in ("GNGGA,,,,,,0,00,25.5,,,,,,", "GNRMC,,V,,,,,,,,,,N", "GPGSV,1,1,03,05,,,,12,,,,21,,,"):
                self.out("#N " + nmea(body))
            return
        hh, mm, ss = utc // 3600000 % 24, utc // 60000 % 60, utc / 1000.0 % 60
        tm = "%02d%02d%06.3f" % (hh, mm, ss)
        if lat is None:
            self.out("#N " + nmea("GNGGA,%s,,,,,0,00,25.5,,,,,," % tm))
            self.out("#N " + nmea("GPGSV,1,1,03,05,41,140,,12,22,301,,21,63,040,"))
            return
        la, lo = abs(lat), abs(lon)
        lat_s = "%02d%07.4f,%s" % (int(la), (la - int(la)) * 60, "N" if lat >= 0 else "S")
        lon_s = "%03d%07.4f,%s" % (int(lo), (lo - int(lo)) * 60, "E" if lon >= 0 else "W")
        self.out("#N " + nmea("GNGGA,%s,%s,%s,1,09,0.9,31.0,M,8.9,M,," % (tm, lat_s, lon_s)))
        self.out("#N " + nmea("GPGSV,2,1,07,05,41,140,38,12,22,301,31,21,63,040,42,25,15,210,27"))
        self.out("#N " + nmea("GPGSV,2,2,07,29,55,095,40,31,08,330,,32,33,260,35"))

    # ------------------------------------------------------------------ the loop (main.cpp loop())
    def _ticker(self):
        while self.alive:
            time.sleep(0.02)
            self.tick()

    def tick(self):
        with self.lock:
            if not self.powered or self.state == "DOWNLOAD":
                return
            now = self.clock()
            self._count_nmea(now)
            if self.screen_on and now - self.last_input > 30.0:
                self.screen_on = False
            if self.export_mode and now - self.export_since > 600.0:
                self.export_mode = False
                self.banner("Export mode timed out")
            if self.gnss in ("time", "fix"):
                if self.next_epoch_t == 0.0:
                    self.next_epoch_t = now + 1.0
                while self.next_epoch_t <= now:
                    self._epoch(self.next_epoch_t)
                    self.next_epoch_t += 1.0
            else:
                self.next_epoch_t = 0.0
            if self.w is None:
                if self.live and now >= self.next_idle_st:
                    self.next_idle_st = now + 10.0
                    self.live_json({"t": "st", "vb": self.vbat_mv(), "ff": self.free()})
                return
            while self.w is not None and self.next_status_t <= now:
                self._status_record(self.next_status_t)
                self.next_status_t += 60.0
            if self.gnss in FILLER_MODES:
                while self.next_row_t <= now:
                    self._filler(self.next_row_t)
                    self.next_row_t += FILL_S
            else:
                self.next_row_t = now + 1.0
            if self.resumed and now - self.rec_t0 > self.stable_s:
                self.nvs["rs_qf"] = 0         # the resumed session ran long enough: not a reboot loop
                self.resumed = False
            if self.free() < RESERVE:
                self._stop("STORAGE_FULL")
                self.banner("STORAGE FULL - stopped")

    NMEA_RATE = {"indoor": 6.0, "time": 13.0, "fix": 13.0, "nodata": 0.0, "cksum": 0.0}

    def _count_nmea(self, now):
        """Valid sentences since boot keep growing while the receiver talks, recording or not (nmea_ok in STATUS)."""
        last = getattr(self, "_nmea_t", None)
        self._nmea_t = now
        if last is None or now <= last:
            return
        dt = now - last
        self._nmea_acc = getattr(self, "_nmea_acc", 0.0) + dt * self.NMEA_RATE.get(self.gnss, 0.0)
        whole = int(self._nmea_acc)
        self.nmea_ok += whole
        self._nmea_acc -= whole
        if self.gnss == "cksum":
            self._bad_acc = getattr(self, "_bad_acc", 0.0) + dt * 6.0
            wb = int(self._bad_acc)
            self.nmea_bad += wb
            self._bad_acc -= wb

    def advance(self, seconds, step=0.25):
        """Tests with a ManualClock: move time forward and let the double catch up."""
        end = self.clock.t + seconds
        while self.clock.t < end - 1e-9:
            self.clock.t = min(end, self.clock.t + step)
            self.tick()

    # ------------------------------------------------------------------ button (main.cpp handleGesture())
    def press(self, kind):
        """kind: short (< 2.5 s), long (2.5 to 6 s) or very_long (> 6 s), reported on release like the firmware."""
        with self.lock:
            if not self.powered or self.state == "DOWNLOAD":
                return
            now = self.clock()
            was_on = self.screen_on
            self.screen_on = True
            self.last_input = now
            if not self.fs_ok:
                return
            if self.w is not None:
                if kind == "short":
                    self.event_no += 1
                    mono = self.mono(now)
                    self.w.event(mono, self.event_no, mono - 180, 180)
                    self._wrote()
                    located = self.w.recs[-1][38] == 1       # EVENT byte 38: located
                    self.live_json({"t": "ev", "n": self.event_no, "loc": 1 if located else 0})
                    self.banner("EVENT %d %s" % (self.event_no, "marked" if located else "(NO POSITION)"))
                else:
                    self._stop("USER_STOP")
                    self.banner("STOPPED - saved")
                return
            if self.export_mode:
                if kind == "very_long":
                    self.export_mode = False
                    self.banner("Export mode OFF")
                return
            if kind == "short":
                if not was_on:
                    return                    # the first press only wakes the screen
                self.mode = {"WALK": "VEHICLE", "VEHICLE": "UNKNOWN"}.get(self.mode, "WALK")
                self.nvs["mode"] = self.mode
                self.banner("MODE: %s" % self.mode)
            elif kind == "long":
                if self.state == "FULL":
                    self.banner("FULL: export+delete first")
                    return
                if self._start():
                    self.banner("REC %s %s" % (self.cur, self.mode))
                else:
                    self.banner("FULL: cannot start" if self.state == "FULL" else "START FAILED")
            elif kind == "very_long":
                self.export_mode = True
                self.export_since = now
                self.banner("Export mode ON")

    # ------------------------------------------------------------------ USB lines (main.cpp handleSerial())
    def receive(self, data):
        self._rxbuf += data
        while b"\n" in self._rxbuf:
            raw, self._rxbuf = self._rxbuf.split(b"\n", 1)
            line = raw.decode("utf-8", "replace").replace("\r", "")
            self.received.append(line)
            self.handle(line)

    def handle(self, line):
        with self.lock:
            if not self.powered or self.state == "DOWNLOAD":
                return
            if line.startswith("FORMAT ERASE-ALL-SESSIONS"):
                self.println("ERR FORMAT refused-by-the-double")
                return
            if line.startswith("VBAT"):
                self.out("OK VBAT pin_mv=%d factor=%d.%03d cal=%d.%03d vbat_mv=%d low_stop_mv=3400"
                         % (self.vbat_pin, 2 * self.cal // 1000, 2 * self.cal % 1000, self.cal // 1000,
                            self.cal % 1000, self.vbat_mv()))
                return
            if line.startswith("CALVBAT "):
                arg = line[8:]
                if arg == "RESET":
                    self.cal = 1000
                else:
                    meas = _atoi(arg)
                    nominal = self.vbat_pin * 2
                    cal = meas * 1000 // nominal if nominal else 0
                    if meas < 3000 or meas > 4300 or cal < 800 or cal > 1200:
                        self.println("ERR CALVBAT out-of-range (expect 3000-4300 mV and a correction within 20 %)")
                        return
                    self.cal = cal
                self.out("OK CALVBAT cal=%d.%03d vbat_mv=%d" % (self.cal // 1000, self.cal % 1000, self.vbat_mv()))
                return
            if not self.fs_ok:
                self.println("ERR FS not-mounted")
                return
            heavy = line.startswith("DUMP") or line.startswith("LIST") or line.startswith("CHECK")
            if heavy and self.w is not None:
                self.out("ERR %.5s recording-active (stop recording first)" % line)
                return
            if self.live_supported and line.startswith("LIVE"):
                rest = line[4:].strip()
                if rest in ("ON", "OFF", "NMEA ON", "NMEA OFF"):
                    if rest == "ON":
                        self.live = True
                        self.next_idle_st = 0.0
                    elif rest == "OFF":
                        self.live = False
                    else:
                        self.live_nmea = rest == "NMEA ON"
                    self.out("OK LIVE " + rest)
                else:
                    self.out("ERR LIVE bad-argument")
                return
            self._proto(line)

    def _proto(self, line):
        """wfg_proto.cpp Proto::handleLine()."""
        parts = line.split()
        if not parts:
            return
        cmd = parts[0][:15]
        a1 = parts[1][:39] if len(parts) > 1 else ""
        if cmd == "HELLO":
            self.out('OK HELLO fw=%s board="%s" device=%08X fmt=2 recsize=48 state=%s'
                     % (self.fw, self.board, self.device_id, self.state))
        elif cmd == "STATUS":
            self.out("OK STATUS state=%s mode=%s session=%s seq=%d free=%d total=%d"
                     % (self.state, self.mode, self.cur if self.w is not None else "-",
                        len(self.w.recs) if self.w is not None else self.idle_seq, self.free(), TOTAL))
        elif cmd == "LIST":
            names = sorted(self.sessions)
            for name in names:
                d = self.sessions[name]
                rep = ux.integrity(d)
                self.out("SESS %s %d %d %s %d %s 0 %s" % (
                    name, len(d), len(d) // 48, ux.Meta(d, name).mode, 1 if rep["has_end"] else 0,
                    rep["end_reason"] if rep["has_end"] else "-", hashlib.sha256(d).hexdigest()))
            self.out("OK LIST %d" % len(names))
        elif cmd == "CHECK":
            if not _valid_name(a1):
                self.out("ERR CHECK bad-name")
                return
            d = self.sessions.get(a1)
            if d is None:
                self.out("OK CHECK %s MISSING rec=0 crc_err=0 seq_err=0 trailing=0 fix=0 nofix=0 events=0 status=0" % a1)
                return
            r = ux.integrity(d)
            self.out("OK CHECK %s %s rec=%d crc_err=%d seq_err=%d trailing=%d fix=%d nofix=%d events=%d status=%d"
                     % (a1, r["status"], r["records"], r["crc_errors"], r["seq_errors"], r["trailing_bytes"], r["fix"],
                        r["nofix"], r["events"], r["status_records"]))
        elif cmd == "DUMP":
            if not _valid_name(a1):
                self.out("ERR DUMP bad-name")
                return
            d = self.sessions.get(a1)
            if d is None:
                self.out("ERR DUMP not-found")
                return
            if self.dump_delay_s > 0:
                delay, self.dump_delay_s = self.dump_delay_s, 0.0
                threading.Timer(delay, self._dump_out, args=(a1, d)).start()
                return
            self._dump_out(a1, d)
        elif cmd in ("CONFIRM", "DELETE"):
            self.out("ERR %s refused-by-the-double" % cmd)
        else:
            self.out("ERR %s unknown-command" % cmd)

    def _dump_out(self, name, d):
        self.out("BEGIN %s %d %s" % (name, len(d), hashlib.sha256(d).hexdigest()))
        sent = bytearray(d)
        if self.corrupt_next_dump and len(sent) > 200:
            self.corrupt_next_dump = False
            sent[150] ^= 0x01             # one bit flips on the way: the SHA-256 the host computes differs
        n = len(sent) // 48
        for k in range(n):
            self.out("R %d %s" % (k, bytes(sent[k * 48:(k + 1) * 48]).hex()))
        if len(sent) % 48:
            self.out("T %s" % bytes(sent[n * 48:]).hex())
        self.out("OK DUMP %s %d" % (name, n))

    # ------------------------------------------------------------------ development panel
    def snapshot(self):
        with self.lock:
            return {"state": self.state, "mode": self.mode, "session": self.cur if self.w is not None else None,
                    "records": len(self.w.recs) if self.w is not None else 0, "screen_on": self.screen_on,
                    "export_mode": self.export_mode, "gnss": self.gnss, "present": self.present,
                    "powered": self.powered, "battery": self.battery, "fs_ok": self.fs_ok, "fw": self.fw,
                    "restart_on": dict(self.restart_on), "sessions": len(self.sessions), "free": self.free(),
                    "banner": self.banner_text, "quick_fails": self.nvs["rs_qf"], "port_open": self.port is not None}


def _atoi(s):
    """C atoi(): leading digits (and a sign), 0 when there are none."""
    s = s.strip()
    n = ""
    for ch in s:
        if ch.isdigit() or (ch in "+-" and not n):
            n += ch
        else:
            break
    try:
        return int(n)
    except ValueError:
        return 0


def _valid_name(n):
    return len(n) == 11 and n[0] == "S" and n[1:7].isdigit() and n[7:] == ".wfg"
