"""Device manager (spec section 3C): port listing, the one link to the logger, basic-mode polling, LIVE (section 5),
the test recording, pulls (P), the connection check, the Wi-Fi pull and battery calibration.

Rules it keeps:
- Listing ports never opens one. A port is opened only when the owner asks (connect), or by itself after an unplug
  when the board's profile shows that neither the open nor a replug restarts it.
- One link owns the open port; commands go one at a time; polling pauses while LIST, CHECK and DUMP run.
- The app never sends DELETE, CONFIRM or FORMAT. CALVBAT is sent only from calibrate() (the calibration form).
- Everything the page shows arrives through emit(): "line" events for the device stream, "state" events, "ports"
  and "live" events. Coordinates never reach the page from a DUMP: the position bytes of FIX and EVENT records are
  masked in the stream (the log file keeps the exact lines).
"""
import collections
import contextlib
import json
import re
import threading
import time
from pathlib import Path

from .. import config, library, session
from ..vendor import usb_export as ux
from . import checks, link as linkmod, notes, ports as portsmod, profiles, save, wifi
from .conncheck import ConnCheck
from .double import LoggerDouble
from .live import LiveState
from .test_flow import TestFlow

DOUBLE_PORT = "SIMULATED-LOGGER"
DUMP_LINE = re.compile(r"^[RT](?:[\s\d]|$)")     # a DUMP line, or what is left of one: _rec_line masks it
STREAM_MAX = 400
DEFAULT_TIMING = {
    "scan_s": 2.0, "watch_s": 3.0, "boot_wait_s": 8.0, "hello_timeout": 2.0, "cmd_timeout": 3.0,
    "dump_inactivity": 5.0, "dump_begin": 30.0, "status_fast": 1.0, "status_slow": 5.0, "vbat_s": 10.0,
    "cc_close_wait": 8.0, "cc_watch": 4.0, "cc_restart_wait": 65.0, "cc_unplug_timeout": 180.0,
    "cc_rec_timeout": 180.0, "cc_replug_settle": 1.0,
}
REC_TYPE = {ux.T_START: "START", ux.T_FIX: "FIX", ux.T_NOFIX: "NOFIX", ux.T_EVENT: "EVENT", ux.T_CLOCK: "CLOCK",
            ux.T_END: "END", ux.T_STATUS: "STATUS"}


def _now_ms():
    return int(time.time() * 1000)


def _short(sha):
    return (sha[:6] + "…" + sha[-4:]) if sha and len(sha) > 12 else (sha or "-")


def _mmss(sec):
    """As mmss() in web/js/util.js: 0:52, 12:05, 1:02:05."""
    s = max(0, int(sec + 1e-6))
    h, m, x = s // 3600, s % 3600 // 60, s % 60
    return "%d:%02d:%02d" % (h, m, x) if h else "%d:%02d" % (m, x)


def _circled(n):
    """As circled() in web/js/replay.js."""
    return chr(0x2460 + n - 1) if 1 <= n <= 20 else str(n)


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def parse_status(line):
    kv = linkmod.parse_kv(line)
    sess = kv.get("session")
    return {"state": kv.get("state"), "mode": kv.get("mode"), "session": None if sess in (None, "-") else sess,
            "seq": _int(kv.get("seq"), 0), "free": _int(kv.get("free")), "total": _int(kv.get("total"))}


def parse_vbat(line):
    kv = linkmod.parse_kv(line)
    mv = _int(kv.get("vbat_mv"), -1)
    return {"pin_mv": _int(kv.get("pin_mv")), "factor": kv.get("factor"), "cal": kv.get("cal"), "vbat_mv": mv,
            "low_stop_mv": _int(kv.get("low_stop_mv")), "valid": 2500 <= mv <= 4500}


def parse_sess(line):
    p = line.split()
    return {"name": p[1], "size": int(p[2]), "records": int(p[3]), "mode": p[4], "closed": p[5] == "1",
            "end_reason": p[6], "exported": p[7] == "1", "sha256": p[8]}


def _load_en():
    try:
        return json.loads((config.WEB / "i18n" / "en.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class DeviceManager:
    def __init__(self, emit, double=False, double_fw="0.2.0", factory=None, list_ports_fn=None, timing=None,
                 double_obj=None):
        self.hub = emit
        self.timing = dict(DEFAULT_TIMING, **(timing or {}))
        self.double = double_obj or (LoggerDouble(fw=double_fw) if double else None)
        self.factory_override = factory
        self.list_ports_fn = list_ports_fn or portsmod.list_ports
        self.lock = threading.RLock()
        self.alive = True
        self.n = 0
        self.stream = collections.deque(maxlen=STREAM_MAX)
        self.en = _load_en()
        self.link = None
        self.ports_list = []
        self.conn = {"state": "disconnected", "port": None, "port_id": None, "method": None, "simulated": False,
                     "error": None, "detail": None, "since": None}
        self.view_visible = False
        self.busy = None
        self.test = None
        self.result = None
        self.result_ctx = None
        self.result_session = None
        self.cc = None
        self.cc_state = None
        self.lost_port = None
        self.watch = None
        self.pending_handshake = False
        self.last_poll = {}
        self.poll_misses = 0
        self.live_lines = {}
        self.candidates = self._load_candidates()
        self.threads = []
        self._reset_device_state()

    def _reset_device_state(self):
        self.hello = None
        self.mode = None
        self.status = None
        self.vbat = None
        self.vbat_unknown = False
        self.restart_on_open = None
        self.restarts = 0
        self.rec_started_ms = None
        self.rec_before_connect = False
        self.last_session = None
        self.events_seen = 0
        self.last_event = None
        self.export_mode = False
        self.fs_error = False
        self.format_error = False
        self.profile = None
        self.live = None

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        self.app_line("start")
        if self.double:
            self.app_line("double", cls="warn")
        self.app_line("scan")
        self._scan()
        for fn in (self._scanner, self._poller):
            th = threading.Thread(target=fn, daemon=True, name="dev-" + fn.__name__.strip("_"))
            th.start()
            self.threads.append(th)

    def shutdown(self):
        self.alive = False
        if self.cc:
            self.cc.cancel()
        lk = self.link
        self.link = None
        if lk:
            lk.close()
        if self.double:
            self.double.close()

    # ------------------------------------------------------------------ emitting
    def _line(self, d, raw, cls, **kw):
        with self.lock:
            self.n += 1
            ev = {"type": "line", "n": self.n, "ts": _now_ms(), "time": time.strftime("%H:%M:%S"), "dir": d,
                  "raw": raw, "cls": cls}
            ev.update({k: v for k, v in kw.items() if v is not None})
            if ev.get("note"):
                ev["note_text"] = self._en_note(ev["note"], ev.get("args") or [])
            self.stream.append(ev)
        self.hub(ev)
        return ev

    def app_line(self, code, cls="app", **args):
        text = self._en_text("stream." + code, args)
        return self._line("·", "", cls, code=code, args=args, text=text)

    def _en_text(self, key, args):
        t = self.en.get(key)
        if not t:
            return key
        try:
            return t.format(**{k: ("" if v is None else v) for k, v in args.items()})
        except (KeyError, IndexError, ValueError):
            return t

    def _en_note(self, code, args):
        """English note for the terminal (the page renders its own notes from web/i18n)."""
        return notes.english(code, tuple(args))

    def _changed(self):
        self.hub({"type": "state", "state": self.snapshot(stream=False)})

    def snapshot(self, stream=True):
        with self.lock:
            s = {"double": self.double.snapshot() if self.double else None, "ports": list(self.ports_list),
                 "conn": dict(self.conn), "hello": self.hello, "mode": self.mode, "status": self.status,
                 "vbat": self.vbat, "vbat_unknown": self.vbat_unknown, "restart_on_open": self.restart_on_open,
                 "restarts": self.restarts, "rec_started_ms": self.rec_started_ms,
                 "rec_before_connect": self.rec_before_connect, "last_session": self.last_session,
                 "events_seen": self.events_seen, "last_event": self.last_event, "export_mode": self.export_mode,
                 "fs_error": self.fs_error, "format_error": self.format_error, "busy": self.busy,
                 "profile": self.profile, "test": self.test.to_dict() if self.test else None, "result": self.result,
                 "conncheck": self.cc.state if self.cc else self.cc_state, "view_visible": self.view_visible,
                 "timing": {k: self.timing[k] for k in ("status_fast", "status_slow", "vbat_s", "scan_s")},
                 "now_ms": _now_ms()}
            if self.live:
                lv = self.live.summary()
                if not stream:
                    lv = dict(lv, rows=None)
                s["live"] = lv
            else:
                s["live"] = None
            if stream:
                s["stream"] = list(self.stream)
            return s

    # ------------------------------------------------------------------ ports
    def _load_candidates(self):
        try:
            return json.loads((config.DEVICES / "candidates.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _remember_candidate(self, vidpid):
        if vidpid and vidpid not in self.candidates:
            self.candidates.append(vidpid)
            config.DEVICES.mkdir(parents=True, exist_ok=True)
            (config.DEVICES / "candidates.json").write_text(json.dumps(self.candidates), encoding="utf-8")

    def _double_port(self):
        return {"device": DOUBLE_PORT, "description": "simulated logger (development only)", "vid": None,
                "pid": None, "vidpid": None, "serial": None, "chip": None, "usb": True, "likely": True,
                "simulated": True}

    def _list(self):
        extra = [self._double_port()] if (self.double and self.double.present) else []
        try:
            return self.list_ports_fn(extra_candidates=tuple(self.candidates), extra_ports=extra)
        except Exception:   # noqa: BLE001  (a failing system listing must never stop the app)
            for p in extra:
                p["id"] = portsmod.identity(p)
            return extra

    def ports(self):
        return list(self.ports_list)

    def port_listed(self, port_id):
        return any(p["id"] == port_id for p in self._list())

    def _scanner(self):
        while self.alive:
            time.sleep(self.timing["scan_s"])
            try:
                self._scan()
            except Exception as ex:   # noqa: BLE001
                self.app_line("scan_failed", cls="err", err=str(ex))

    def _scan(self):
        new = self._list()
        with self.lock:
            old = {p["id"] for p in self.ports_list}
            cur = {p["id"]: p for p in new}
            added = [p for p in new if p["id"] not in old]
            removed = [p for p in self.ports_list if p["id"] not in cur]
            self.ports_list = new
            connected = self.conn["state"] in ("connected", "connecting")
        likely_added = False
        for p in added:
            if p.get("likely"):
                self.app_line("port_new", port=p["device"])
                if p.get("simulated"):
                    self.app_line("port_sim")
                else:
                    self.app_line("port_likely", vidpid=p.get("vidpid") or "-", chip=p.get("chip") or "")
                likely_added = True
            elif p.get("usb"):
                self.app_line("port_usb", cls="dim", port=p["device"], vidpid=p.get("vidpid") or "-")
            else:
                self.app_line("port_nousb", cls="dim", port=p["device"])
        if likely_added and not connected:
            self.app_line("port_enter")
        for p in removed:
            self.app_line("port_gone", cls="dim", port=p["device"])
        if added or removed:
            self.hub({"type": "ports", "ports": new})
            self._changed()
        self._maybe_reconnect(cur)

    def _maybe_reconnect(self, cur):
        with self.lock:
            lp = self.lost_port
            ok = lp is not None and self.conn["state"] == "lost" and self.busy is None and lp["id"] in cur
        if not ok:
            return
        prof = profiles.for_port(lp["id"])
        if profiles.reconnect_allowed(prof):
            self.app_line("reconnect")
            with self.lock:
                self.lost_port = None
                self.busy = "connect"
                self.conn.update(state="connecting", error=None)
            threading.Thread(target=self._connect_run, args=(cur[lp["id"]],), daemon=True).start()

    # ------------------------------------------------------------------ opening and the handshake
    def _factory(self, port, method):
        if self.double and port == DOUBLE_PORT:
            return self.double.open_port(method)
        if self.factory_override:
            return self.factory_override(port, method)
        return linkmod.default_factory(port, method)

    def connect(self, port_dev):
        with self.lock:
            if self.link is not None:
                raise RuntimeError("already connected")
            if self.busy:
                raise RuntimeError("busy: %s" % self.busy)
            p = next((x for x in self.ports_list if x["device"] == port_dev), None)
            if p is None:
                p = next((x for x in self._list() if x["device"] == port_dev), None)
            if p is None:
                raise ValueError("no such port: %s" % port_dev)
            self.busy = "connect"
            self.lost_port = None
            self.conn.update(state="connecting", port=p["device"], port_id=p["id"], simulated=bool(p.get("simulated")),
                             error=None, detail=None)
        self._changed()
        threading.Thread(target=self._connect_run, args=(p,), daemon=True, name="dev-connect").start()
        return {"ok": True}

    def _connect_run(self, p):
        try:
            self._connect_seq(p)
        except Exception as ex:   # noqa: BLE001
            self._conn_fail("open_failed", str(ex))
        finally:
            with self.lock:
                if self.busy == "connect":
                    self.busy = None
            self._changed()

    def _conn_fail(self, code, detail=None):
        with self.lock:
            lk, self.link = self.link, None
            self.conn.update(state="disconnected", error=code, detail=detail)
        if lk:
            lk.close()

    def _connect_seq(self, p):
        self._reset_device_state()
        prof = profiles.for_port(p["id"])
        self.profile = prof
        method = profiles.open_method(prof)
        obs = self._open(p, method, self.timing["watch_s"])
        if obs is None:
            return False
        if obs["download"] and not obs["fw"]:
            # flashing mode: _open() has set pending_handshake; the boot line after RST finishes the handshake
            with self.lock:
                self.conn.update(state="connecting", error="download")
            return False
        self.restart_on_open = obs["boot"]
        self.app_line("restarted" if obs["boot"] else "norestart", cls="warn" if obs["boot"] else "app")
        return self._handshake(p)

    def _open(self, p, method, watch_s):
        """Open the port and watch it for watch_s seconds for boot text. Returns the observations, or None."""
        self.watch = {"boot": False, "fw": False, "download": False, "resume_was": None, "stopped": False}
        self.app_line("open" if method == "default" else "open_low", port=p["device"])
        lk = linkmod.Link(p["device"], method, listener=self._on_link, factory=self._factory, log_dir=config.LOGS)
        lk.on_lost = lambda ex, lk=lk: self._on_lost(lk, ex)
        try:
            lk.open()
        except Exception as ex:   # noqa: BLE001  (busy port, permission, vanished device)
            self.watch = None
            self.app_line("open_failed", cls="err", port=p["device"], err=str(ex))
            self._conn_fail("open_failed", str(ex))
            return None
        with self.lock:
            self.link = lk
            self.conn.update(state="connecting", port=p["device"], port_id=p["id"], method=method,
                             simulated=bool(p.get("simulated")))
        end = time.monotonic() + watch_s
        while time.monotonic() < end and lk.alive and not self.watch["download"]:
            time.sleep(0.05)
        if self.watch["boot"] and not self.watch["fw"] and not self.watch["download"]:
            end = time.monotonic() + self.timing["boot_wait_s"]
            while time.monotonic() < end and lk.alive and not self.watch["fw"]:
                time.sleep(0.05)
        with self.lock:
            # Ending the watch and arming the flashing-mode handshake happen together, so a boot line that arrives
            # in between (the owner pressed RST at once) is never lost: _apply_note() reads both under this lock.
            obs = dict(self.watch)
            self.watch = None
            if obs["download"] and not obs["fw"]:
                self.pending_handshake = True
        return obs

    def _cmd(self, cmd, **kw):
        lk = self.link
        if lk is None:
            raise linkmod.LinkLost("not connected")
        kw.setdefault("timeout", self.timing["cmd_timeout"])
        return lk.command(cmd, **kw)

    def _handshake(self, p):
        reply, ms = None, None
        for _ in range(2):
            t0 = time.monotonic()
            try:
                lines = self._cmd("HELLO", timeout=self.timing["hello_timeout"])
                reply = lines[-1] if lines else None
                ms = int((time.monotonic() - t0) * 1000)
                break
            except TimeoutError:
                continue
            except linkmod.LinkLost:
                return False
        if reply is None:
            self.app_line("noreply", cls="err")
            self._conn_fail("noreply")
            return False
        if reply.startswith("ERR FS"):
            self.fs_error = True
        elif reply.startswith("OK HELLO"):
            kv = linkmod.parse_kv(reply)
            self.hello = {"fw": kv.get("fw"), "board": kv.get("board"), "device": kv.get("device"),
                          "fmt": kv.get("fmt"), "recsize": kv.get("recsize"), "state": kv.get("state"), "ms": ms}
            if not (kv.get("recsize") == "48" and kv.get("fmt") in ("1", "2")):
                self.format_error = True
                self.app_line("format", cls="err")
        else:
            self.app_line("noreply", cls="err")
            self._conn_fail("noreply", reply)
            return False
        try:
            if self.fs_error:
                self.mode = "basic"
                self.app_line("fs", cls="err")
            else:
                r = self._cmd("LIVE ON")
                if r and r[-1].startswith("OK LIVE"):
                    self.mode = "live"
                    self.live = LiveState(auto_zones=not self.conn["simulated"])
                    self._cmd("LIVE NMEA ON")
                    self.app_line("live")
                else:
                    self.mode = "basic"
            self._poll("STATUS")
            self._poll("VBAT")
            if not self.fs_error and not self.format_error and self.status and self.status["state"] != "RECORDING":
                self._cmd("LIST")
        except TimeoutError:
            self.app_line("noreply", cls="err")
        except linkmod.LinkLost:
            return False
        if self.hello and self.hello.get("device"):
            dev = self.hello["device"]
            profiles.remember_port(p["id"], dev)
            self.profile = profiles.update(dev, fw=self.hello.get("fw"), board=self.hello.get("board"),
                                           last_port=p["device"], restart_on_last_open=self.restart_on_open)
            if not p.get("likely"):
                self._remember_candidate(p.get("vidpid"))
        with self.lock:
            self.rec_before_connect = bool(self.status and self.status["state"] == "RECORDING")
            self.conn.update(state="connected", since=_now_ms(), error=None, detail=None)
            self.lost_port = None
        self._changed()
        return True

    def _after_download_boot(self):
        """The owner pressed RST after the board started in its flashing mode: finish the handshake."""
        end = time.monotonic() + 3.0
        while time.monotonic() < end and self.busy == "connect":
            time.sleep(0.02)                    # the connect thread that saw the flashing mode is still finishing
        with self.lock:
            p = {"device": self.conn["port"], "id": self.conn["port_id"], "likely": True}
            self.busy = self.busy or "connect"
        try:
            self.restart_on_open = None
            self._handshake(p)
        finally:
            with self.lock:
                if self.busy == "connect":
                    self.busy = None
            self._changed()

    # ------------------------------------------------------------------ incoming lines
    def _on_link(self, kind, text, p):
        try:
            if kind == "sent":
                if not getattr(p, "quiet", False):
                    self._line("→", text, "sent")
            elif kind == "reply":
                self._on_reply(text, p)
            else:
                self._on_unsolicited(text)
        except Exception as ex:   # noqa: BLE001  (a bad line must never kill the reader thread)
            self._line("·", "", "err", code="internal", args={"err": str(ex)}, text="internal error: %s" % ex)

    def _on_reply(self, text, p):
        kw = p.kw
        quiet = getattr(p, "quiet", False)
        if text.startswith("ERR FS"):
            first = not self.fs_error
            self.fs_error = True
            if first or not quiet:
                self._line("←", text, "err", note="fs")
            self._changed()
            return
        if text.startswith("OK STATUS"):
            st = parse_status(text)
            self._apply_status(st)
            if quiet:
                self._poll_line("STATUS", text, st)
            else:
                self._line("←", text, "reply")
            return
        if text.startswith("OK VBAT"):
            vb = parse_vbat(text)
            self.vbat = dict(vb, ts=_now_ms())
            self.vbat_unknown = False
            if quiet:
                self._poll_line("VBAT", text, vb)
            else:
                self._line("←", text, "reply")
            self._changed()
            return
        if kw == "VBAT" and text.startswith("ERR"):
            first = not self.vbat_unknown
            self.vbat_unknown = True
            self.vbat = None
            if first or not quiet:
                self._line("←", text, "reply", note="vbat_unknown")
            self._changed()
            return
        if kw == "LIVE" and text.startswith("ERR LIVE unknown-command"):
            self._line("←", text, "reply", note="basic")
            return
        if kw == "DUMP" and DUMP_LINE.match(text):
            self._rec_line(text)
            return
        self._line("←", text, "err" if text.startswith("ERR") else "reply")

    def _poll(self, kind):
        return self._cmd(kind, quiet=True)

    def _poll_line(self, kind, raw, fields):
        if kind == "STATUS":
            key = (fields["state"], fields["mode"], fields["session"], fields["seq"], fields["free"])
        else:
            key = (fields["pin_mv"], fields["vbat_mv"], fields["cal"])
        same = self.last_poll.get(kind) == key
        self.last_poll[kind] = key
        self._line("←", raw, "poll", poll=kind, fields=fields, same=same)

    def _rec_line(self, text):
        """A DUMP line ('R <i> <hex>' or 'T <hex>'): shown with the type decoded and the position bytes masked."""
        parts = text.split()
        if parts and parts[0] == "T":
            hx = parts[1] if len(parts) > 1 else ""
            # the torn tail of an unfinished record: whatever it holds from byte 20 on is masked (all of it if it
            # is not hex at all)
            shown = hx[:40] + "x" * max(0, len(hx) - 40) if re.fullmatch(r"[0-9a-fA-F]*", hx) else "x" * 8
            self._line("←", "T %s" % shown, "rec", rec={"i": None, "type": "TORN", "n_bytes": len(hx) // 2})
            return
        try:
            idx, hx = int(parts[1]), parts[2]
            b = bytes.fromhex(hx)
        except (IndexError, ValueError):
            self._line("←", "R " + "x" * 8, "err")      # unreadable: never shown raw (it may hold a position)
            return
        d = ux.decode(b) if len(b) == 48 else None
        info = {"i": idx, "type": "CORRUPT" if d is None else REC_TYPE.get(d["type"], "UNKNOWN")}
        if d is not None:
            t = d["type"]
            if t in (ux.T_FIX, ux.T_NOFIX):
                info["nr"] = None if t == ux.T_FIX else ux.NOFIX_NAME.get(d["nofix_reason"], "UNKNOWN")
                info["ft"] = {1: "NONE", 2: "2D", 3: "3D"}.get(d["fix_type"]) if d["valid"] & ux.V_FIXTYPE else None
            elif t == ux.T_EVENT:
                info.update(n=d["event_no"], loc=d["located"])
            elif t == ux.T_STATUS:
                info.update(vb=d["vbat_mv"] if (d["st_flags"] & ux.ST_BATT_VALID and d["vbat_mv"] != 0xFFFF) else None,
                            nmea=d["nmea_ok"])
            elif t == ux.T_START:
                info.update(mode=ux.MODE_NAME.get(d["mode"], "UNKNOWN"),
                            sr=ux.START_REASON.get(d["start_reason"], "OWNER_BUTTON"))
            elif t == ux.T_END:
                info.update(er=ux.END_NAME.get(d["reason"], "UNKNOWN"))
            elif t == ux.T_CLOCK:
                info.update(kind="FIRST_UTC" if d["kind"] == 1 else "JUMP")
        shown = hx
        if d is None or d["type"] in (ux.T_FIX, ux.T_EVENT):
            # positions never reach the page from a DUMP: bytes 20 to 27 and the CRC are masked; a line of the wrong
            # length is masked from byte 20 on
            shown = hx[:40] + "x" * 16 + hx[56:88] + "x" * 8 if len(hx) == 96 else hx[:40] + "x" * max(0, len(hx) - 40)
        self._line("←", "R %d %s" % (idx, shown), "rec", rec=info)

    def _on_unsolicited(self, text):
        if text.startswith("#J "):
            self._on_live_json(text)
            return
        if text.startswith("#N "):
            self._on_live_nmea(text)
            return
        if DUMP_LINE.match(text):
            # a DUMP line that arrives after its command gave up (or from another program's DUMP): masked all the same
            self._rec_line(text)
            return
        code, groups = notes.classify(text)
        if text.startswith("#"):
            cls = "hash"
        else:
            cls = "boot" if code else "other"
        if code in notes.ERROR_CODES or code == "download_mode":
            cls = "err"
        self._line("←", text, cls, note=code, args=list(groups) if code else None)
        self._apply_note(code, groups)

    def _apply_note(self, code, groups):
        if code is None:
            return
        now = time.monotonic()
        with self.lock:
            w = self.watch
            if w is not None and code in ("rom_boot", "boot", "download_mode"):
                if code == "download_mode":
                    w["download"] = True
                    w["fw"] = False             # a normal start must follow the flashing mode to count
                else:
                    w["boot"] = True
                    w["fw"] = w["fw"] or code == "boot"
            pending = False
            if w is None and code == "boot" and self.pending_handshake:
                self.pending_handshake = False
                pending = True
        if code in ("rom_boot", "boot"):
            if w is None and code == "boot":
                self.restarts += 1
                self.app_line("restart", cls="warn")
                if pending:
                    threading.Thread(target=self._after_download_boot, daemon=True).start()
                elif self.conn["state"] == "connected" and self.busy != "conncheck":
                    threading.Thread(target=self._after_restart, daemon=True).start()
        elif code == "download_mode":
            self.app_line("download", cls="err")
            with self.lock:
                self.conn["error"] = "download"
        elif code == "resume_decision":
            if w is not None:
                w["resume_was"] = _int(groups[1][1:]) if groups[1] else None
        elif code == "rec":
            st = dict(self.status or {}, state="RECORDING", session=groups[0], mode=groups[1], seq=0)
            self.status = st
            self.rec_started_ms = _now_ms()
            self.rec_before_connect = False
            self.events_seen = 0
            self.last_event = None
        elif code == "event":
            self.events_seen += 1
            self.last_event = {"n": int(groups[0]), "located": groups[1] == "marked", "ts": _now_ms()}
        elif code in ("stopped", "low_batt_stop", "full_stop"):
            if w is not None and code == "stopped":
                w["stopped"] = True
            if self.status:
                self.last_session = self.status.get("session") or self.last_session
                self.status = dict(self.status, state="FULL" if code == "full_stop" else "IDLE", session=None)
            self.rec_started_ms = None
        elif code == "mode":
            if self.status:
                self.status = dict(self.status, mode=groups[0])
        elif code == "export_on":
            self.export_mode = True
        elif code in ("export_off", "export_timeout"):
            self.export_mode = False
        elif code == "fs_error":
            self.fs_error = True
        if self.test:
            self.test.on_note(code, groups, now)
            self._maybe_test_pull()
        self._changed()

    def _after_restart(self):
        """Boot text while connected: the firmware starts with LIVE off and may have resumed a session."""
        time.sleep(0.3)
        try:
            if self.mode == "live":
                self._cmd("LIVE ON")
                self._cmd("LIVE NMEA ON")
            self._poll("STATUS")
        except (TimeoutError, linkmod.LinkLost):
            pass

    def _apply_status(self, st):
        prev = self.status
        self.status = dict(st, ts=_now_ms())
        if prev:
            if prev.get("state") != "RECORDING" and st["state"] == "RECORDING" and self.rec_started_ms is None:
                self.rec_started_ms = _now_ms()
            if prev.get("state") == "RECORDING" and st["state"] != "RECORDING":
                self.last_session = prev.get("session") or self.last_session
                self.rec_started_ms = None
        if self.test:
            self.test.on_status(st)
            self._maybe_test_pull()
        self._changed()

    # ------------------------------------------------------------------ LIVE lines (firmware 0.3.0)
    def _on_live_json(self, text):
        try:
            obj = json.loads(text[3:])
        except ValueError:
            self._line("←", text, "other")
            return
        if self.live is None:
            self.live = LiveState(auto_zones=not self.conn["simulated"])
        evs = self.live.on_json(obj)                   # first: a zone this line opens applies to the line itself
        shown = self.live.mask_json_line(text, obj)
        t = obj.get("t")
        ev = self._line("←", shown, "live", live=t)
        self._keep_live_line(ev, text, obj, None)
        if t == "st" and obj.get("vb") is not None:
            self.vbat = dict(self.vbat or {}, vbat_mv=obj["vb"], valid=2500 <= obj["vb"] <= 4500, ts=_now_ms())
        if t == "drop":
            self.app_line("live_drop", cls="err", n=obj.get("n"))
        for e in evs:
            if e.get("ev") == "rezone":
                self._remask()
            self.hub(dict({"type": "live"}, **e))
            if e.get("ev") in ("stop_detected", "stop_ended", "stop_removed"):
                self._live_stop_line(e)

    def _live_stop_line(self, e):
        """Spec 6.9 in the device stream: the stop announcements of the REPLAY console, with the stop's circled
        number and its start on the local clock (session time when the receiver gave no time)."""
        n = _circled(e["n"])
        if e["ev"] == "stop_detected":
            when = self.live.clock_label(e["t0"]) if self.live else None
            self.app_line("live_stop", cls="det", n=n, time=when or "+" + _mmss(e["t0"]), v=e.get("v"),
                          t=int(e.get("tmin") or 10))
        elif e["ev"] == "stop_ended":
            self.app_line("live_stop_end", cls="det", n=n, dur=_mmss(e["dur"]))
        else:
            self.app_line("live_stop_removed", n=n)

    def _on_live_nmea(self, text):
        if self.live is None:
            self.live = LiveState(auto_zones=not self.conn["simulated"])
        rec = self.live.recording
        ev = self._line("←", self.live.mask_nmea(text, recording=rec), "nmea")
        self._keep_live_line(ev, text, None, rec)
        e = self.live.on_nmea(text)
        if e:
            self.hub(dict({"type": "live"}, **e))

    def _keep_live_line(self, ev, text, obj, recording):
        """Remember the original of a LIVE line still on the page, so the end zone can mask it afterwards."""
        with self.lock:
            self.live_lines[ev["n"]] = (text, obj, recording, self.live.session_no)
            if len(self.live_lines) > 2 * STREAM_MAX:
                first = self.stream[0]["n"] if self.stream else ev["n"]
                self.live_lines = {k: v for k, v in self.live_lines.items() if k >= first}

    def _remask(self):
        """The session ended and its end zone exists: mask the lines of this session that fall inside it. Lines are
        only ever masked further, never unmasked."""
        changes = []
        with self.lock:
            ss = self.live.session_no
            for ev in self.stream:
                src = self.live_lines.get(ev["n"])
                if not src or src[3] != ss or ev["raw"] != src[0]:
                    continue
                text, obj, rec, _ = src
                new = self.live.mask_json_line(text, obj) if obj is not None else self.live.mask_nmea(text, rec)
                if new != text:
                    ev["raw"] = new
                    changes.append({"n": ev["n"], "raw": new})
        if changes:
            self.hub({"type": "remask", "lines": changes})

    # ------------------------------------------------------------------ lost, disconnect, view
    def _on_lost(self, lk, ex):
        with self.lock:
            if self.link is not lk:
                return
            self.link = None
            self.lost_port = {"device": self.conn["port"], "id": self.conn["port_id"]}
            self.conn.update(state="lost", error=None, detail=str(ex))
        threading.Thread(target=lk.close, daemon=True).start()
        self.app_line("lost", cls="err")
        if self.test:
            self.test.interrupt()
            with self.lock:
                if self.busy == "test":
                    self.busy = None
        self._changed()

    def disconnect(self):
        with self.lock:
            if self.busy in ("pull", "conncheck", "connect", "list"):
                raise RuntimeError("busy: %s" % self.busy)
            lk, self.link = self.link, None
            if self.test:
                self.test.cancel()
                self.busy = None
        if lk:
            lk.close()
        with self.lock:
            self.conn.update(state="disconnected", error=None, detail=None)
            self.lost_port = None
            self.pending_handshake = False
            self._reset_device_state()
        self.app_line("closed")
        self._changed()
        return {"ok": True}

    def set_view(self, visible):
        self.view_visible = bool(visible)

    def _require(self):
        if self.conn["state"] != "connected" or self.link is None:
            raise RuntimeError("not connected")

    def _require_format(self):
        """HELLO gave a record format the app cannot read: no pulls (spec section 3C, step 3), so no P, no test
        recording (it ends with a pull) and no connection check (it pulls the sessions it made)."""
        if self.format_error:
            raise RuntimeError("format.error")

    # ------------------------------------------------------------------ polling (basic mode)
    def _poller(self):
        next_status = next_vbat = 0.0
        while self.alive:
            time.sleep(0.1)
            with self.lock:
                lk = self.link
                ok = (lk is not None and lk.alive and self.conn["state"] == "connected"
                      and self.busy in (None, "test"))
            if not ok:
                continue
            now = time.monotonic()
            if not self.fs_error and now >= next_status:
                fast = self.view_visible or self.test is not None and self.test.phase == "running"
                next_status = now + (self.timing["status_fast"] if fast else self.timing["status_slow"])
                self._poll_safe(lk, "STATUS")
            if not self.vbat_unknown and now >= next_vbat:
                next_vbat = now + self.timing["vbat_s"]
                self._poll_safe(lk, "VBAT")

    def _poll_safe(self, lk, kind):
        try:
            r = lk.command(kind, timeout=self.timing["cmd_timeout"], blocking=False, quiet=True)
        except TimeoutError:
            self.poll_misses += 1
            if self.poll_misses == 3:
                self.app_line("poll_noreply", cls="err", cmd=kind)
            return
        except linkmod.LinkLost:
            return
        if r is not None:
            self.poll_misses = 0

    # ------------------------------------------------------------------ commands used by pulls and the check
    def cmd_status(self, visible=False):
        try:
            lines = self._cmd("STATUS", quiet=not visible)
        except (TimeoutError, linkmod.LinkLost):
            return None
        for ln in lines or []:
            if ln.startswith("OK STATUS"):
                return parse_status(ln)
        if lines and lines[-1].startswith("ERR FS"):
            raise RuntimeError("fs.error")
        return None

    def cmd_list(self):
        lines = self._cmd("LIST", timeout=10.0)
        if lines and lines[-1].startswith("ERR"):
            raise RuntimeError(lines[-1])
        return [parse_sess(ln) for ln in lines if ln.startswith("SESS ")]

    def _dump(self, name):
        lines = self._cmd("DUMP " + name, timeout=None, inactivity=self.timing["dump_inactivity"],
                          first_timeout=self.timing["dump_begin"])     # usb_export.py waits 30 s for BEGIN too
        return linkmod.parse_dump(lines, name)

    def conn_port(self):
        return {"device": self.conn["port"], "id": self.conn["port_id"], "simulated": self.conn["simulated"]}

    def fw_version(self):
        return self.hello.get("fw") if self.hello else None

    def device_id(self):
        return self.hello.get("device") if self.hello else None

    def profile_changed(self, prof):
        if prof is not None:
            self.profile = prof
        self._changed()

    # ------------------------------------------------------------------ test recording
    def test_start(self):
        with self.lock:
            self._require()
            if self.fs_error:
                raise RuntimeError("fs.error")
            self._require_format()
            if self.busy:
                raise RuntimeError("busy: %s" % self.busy)
            self.test = TestFlow(self.status)
            # the result's note "began before the laptop was connected" (spec 3C): recording already when the port
            # was opened, not only when T was pressed
            self.test.before_connect = bool(self.test.started_before and self.rec_before_connect)
            self.busy = "test"
            self.result = None
        self.app_line("test_start")
        self._changed()
        return {"ok": True}

    def test_cancel(self):
        with self.lock:
            if self.test:
                self.test.cancel()
            if self.busy == "test":
                self.busy = None
        self.app_line("test_cancel")
        self._changed()
        return {"ok": True}

    def _maybe_test_pull(self):
        t = self.test
        with self.lock:
            go = t is not None and t.ready_to_pull and self.busy == "test"
            if go:
                self.busy = "pull"
                t.steps[4] = {"st": "running"}
        if go:
            threading.Thread(target=self._test_pull, args=(t,), daemon=True, name="dev-test-pull").start()

    def _test_pull(self, t):
        try:
            time.sleep(0.3)     # let the device finish its '#' line before the first command
            with self._live_paused():
                res = self._pull(t.session, force=True, device_test=True, started_before=t.before_connect)
            t.pulled(bool(res.get("ok")), res.get("error"))
        except Exception as ex:   # noqa: BLE001
            t.pulled(False, str(ex))
            self.app_line("pull_failed", cls="err", err=str(ex))
        finally:
            with self.lock:
                if self.busy == "pull":
                    self.busy = None
            self._changed()

    def screen_answer(self, seen):
        with self.lock:
            if self.result is None or self.result_session is None:
                raise RuntimeError("no result to answer for")
            ctx = dict(self.result_ctx, screen=bool(seen))
            self.result_ctx = ctx
            keep = {k: self.result.get(k) for k in ("file", "pulled", "saved_status", "device_test", "bad",
                                                    "started_before")}
            self.result = dict(checks.compute(self.result_session, ctx), **keep)
            dev = self.device_id()
        if dev:
            self.profile = profiles.update(dev, screen={"seen": bool(seen), "date": time.strftime("%Y-%m-%d")})
        self._changed()
        return {"ok": True, "result": self.result}

    # ------------------------------------------------------------------ pulls (P)
    @contextlib.contextmanager
    def _live_paused(self):
        """P in LIVE mode (spec section 8): LIVE OFF before LIST, CHECK and DUMP, LIVE ON again afterwards."""
        live = self.mode == "live"
        if live:
            try:
                self._cmd("LIVE OFF")
            except (TimeoutError, linkmod.LinkLost):
                pass
        try:
            yield
        finally:
            if live and self.link is not None:
                try:
                    self._cmd("LIVE ON")
                    self._cmd("LIVE NMEA ON")
                except (TimeoutError, linkmod.LinkLost):
                    pass

    def device_sessions(self):
        with self.lock:
            self._require()
            self._require_format()
            if self.busy:
                raise RuntimeError("busy: %s" % self.busy)
            self.busy = "list"
        try:
            with self._live_paused():
                st = self.cmd_status(visible=True)
                if st and st["state"] == "RECORDING":
                    raise RuntimeError("pull.recording")
                items = self.cmd_list()
            idx = save.library_sha_index()
            for it in items:
                it["known"] = idx.get(it["sha256"])
            return {"sessions": items}
        finally:
            with self.lock:
                if self.busy == "list":
                    self.busy = None
            self._changed()

    def pull(self, name, force=False):
        with self.lock:
            self._require()
            self._require_format()
            if self.busy:
                raise RuntimeError("busy: %s" % self.busy)
            self.busy = "pull"
        self._changed()
        try:
            with self._live_paused():
                return self._pull(name, force, device_test=False)
        finally:
            with self.lock:
                if self.busy == "pull":
                    self.busy = None
            self._changed()

    def _ctx(self, size_match, sha_match, sha, device_test):
        prof = self.profile or {}
        screen = None
        if not device_test and isinstance(prof.get("screen"), dict):
            screen = prof["screen"].get("seen")
        return {"size_match": size_match, "sha_match": sha_match, "sha": sha, "vbat": self.vbat, "device_name": None,
                "free": self.status.get("free") if self.status else None, "restart_on_open": self.restart_on_open,
                "screen": screen, "usb_power": True}

    def _rel(self, p):
        try:
            return str(Path(p).relative_to(config.SESSIONS))
        except ValueError:
            return str(p)

    def _pull(self, name, force=False, device_test=False, started_before=False):
        """started_before: the test recording found the session already running (spec 3C: the result says so)."""
        if not name:
            raise RuntimeError("no session to pull")
        st = self.cmd_status(visible=True)
        if st and st["state"] == "RECORDING":
            raise RuntimeError("pull.recording")
        items = self.cmd_list()
        it = next((x for x in items if x["name"] == name), None)
        if it is None:
            raise RuntimeError("%s is not on the device" % name)
        known = save.library_sha_index().get(it["sha256"]) if len(it["sha256"]) == 64 else None
        if known and not force:
            self.app_line("pull_same", cls="ok", sha=_short(it["sha256"]))
            s = library.load(library.safe_path(known))
            ctx = dict(self._ctx(True, True, it["sha256"], device_test), device_name=name)
            result = dict(checks.compute(s, ctx), file=known, pulled=_now_ms(), saved_status="same",
                          device_test=device_test, started_before=started_before)
            with self.lock:
                self.result, self.result_ctx, self.result_session = result, ctx, s
            return {"ok": True, "status": "same", "file": known, "result": result}
        self.app_line("pull_start", name=name, size="{:,}".format(it["size"]))
        self._cmd("CHECK " + name, timeout=10.0)
        data, size, dev_sha = self._dump(name)
        digest = save.sha256(data)
        simulated = bool(self.conn["simulated"]) or save.reserved_sim_id(data)
        out_dir = save.target_dir(simulated, device_test)
        if len(data) != size or digest != dev_sha:
            bad = save.save_bad(data, name, out_dir)
            self.app_line("sha_bad", cls="err", got=_short(digest), dev=_short(dev_sha), path=self._rel(bad))
            s = session.load_wfg_bytes(data, name)
            ctx = dict(self._ctx(len(data) == size, False, digest, device_test), device_name=name)
            result = dict(checks.compute(s, ctx), file=None, bad=self._rel(bad), pulled=_now_ms(),
                          saved_status="bad", device_test=device_test, started_before=started_before)
            with self.lock:
                self.result, self.result_ctx, self.result_session = result, ctx, s
            self._summary_line(result)
            return {"ok": False, "status": "bad", "error": "sha", "result": result}
        saved = save.save_pulled(data, name, out_dir, simulated=simulated)
        rel = self._rel(saved["path"])
        rep = ux.integrity(data)
        self.app_line("sha_ok", cls="ok", sha=_short(digest), size="{:,}".format(len(data)))
        crc_ok = rep["records"] - rep["crc_errors"]
        if rep["ok"]:
            self.app_line("crc_ok", cls="ok", ok=crc_ok, total=rep["records"], end=rep["end_reason"])
        else:
            self.app_line("crc_info", cls="err", ok=crc_ok, total=rep["records"], status=rep["status"])
        self.app_line("saved", path=rel)
        if not device_test and not simulated:
            try:
                library.add(rel)
            except (OSError, ValueError):
                pass
        s = library.load(saved["path"])
        ctx = dict(self._ctx(True, True, digest, device_test), device_name=name)
        result = dict(checks.compute(s, ctx), file=rel, pulled=_now_ms(), saved_status=saved["status"],
                      device_test=device_test, started_before=started_before)
        with self.lock:
            self.result, self.result_ctx, self.result_session = result, ctx, s
        self._summary_line(result)
        return {"ok": True, "status": saved["status"], "file": rel, "result": result}

    def _summary_line(self, result):
        c = result["counts"]
        cls = "err" if c["bad"] else ("app" if c["wait"] else "ok")      # the ✓ only when every check passed
        self.app_line("summary_wait" if c["wait"] else "summary", cls=cls, n=result["total"], p=c["ok"], i=c["info"],
                      f=c["bad"], w=c["wait"])

    def pull_quiet(self, name):
        """Connection check: pull one session made during the check and report its start and end reasons."""
        data, size, dev_sha = self._dump(name)
        ok = len(data) == size and save.sha256(data) == dev_sha
        info = {"name": name, "ok": ok}
        if ok:
            sim = bool(self.conn["simulated"]) or save.reserved_sim_id(data)
            saved = save.save_pulled(data, name, save.target_dir(sim, True), simulated=sim)
            info["file"] = self._rel(saved["path"])
        meta = ux.Meta(data, name)
        rep = ux.integrity(data)
        info.update(start_reason=meta.start_reason, end_reason=rep.get("end_reason"), status=rep.get("status"))
        return info

    # ------------------------------------------------------------------ connection check
    def conncheck_start(self):
        with self.lock:
            self._require()
            if self.fs_error:
                raise RuntimeError("fs.error")
            self._require_format()
            if self.busy:
                raise RuntimeError("busy: %s" % self.busy)
            self.busy = "conncheck"
            self.cc = ConnCheck(self)
            self.cc_state = None
        self.cc.start()
        self._changed()
        return {"ok": True}

    def conncheck_answer(self, value=None):
        if not self.cc:
            raise RuntimeError("no connection check running")
        self.cc.answer(value)
        return {"ok": True}

    def conncheck_cancel(self):
        if self.cc:
            self.cc.cancel()
        return {"ok": True}

    def cc_changed(self):
        self._changed()

    def cc_finished(self, cc):
        with self.lock:
            self.cc_state = dict(cc.state)
            self.cc = None
            if self.busy == "conncheck":
                self.busy = None
            if self.link is not None and self.conn["state"] != "connected":
                self.conn.update(state="connected", error=None)
        if self.link is not None:
            threading.Thread(target=self._after_restart, daemon=True).start()
        self._changed()

    def close_for_check(self):
        with self.lock:
            lk, self.link = self.link, None
            self.conn.update(state="checking")
        if lk:
            lk.close()
        self._changed()

    def open_for_check(self, port, method, watch_s):
        with self.lock:
            old, self.link = self.link, None
        if old:
            old.close()
        obs = self._open(port, method, watch_s)
        if obs is None:
            raise RuntimeError("could not open %s" % port["device"])
        if obs["boot"]:
            self.restarts += 1
            self.app_line("restart", cls="warn")
        with self.lock:
            self.conn.update(state="connected", method=method, error=None)
        self._changed()
        return obs

    # ------------------------------------------------------------------ battery calibration (only from the form)
    def calibrate(self, mv=None, reset=False):
        with self.lock:
            self._require()
            if self.busy not in (None,):
                raise RuntimeError("busy: %s" % self.busy)
        if reset:
            cmd = "CALVBAT RESET"
        else:
            v = _int(str(mv).strip() if mv is not None else None)
            if v is None or not 0 < v < 100000:
                raise ValueError("cal.bad_input")
            cmd = "CALVBAT %d" % v
        lines = self._cmd(cmd)
        reply = lines[-1] if lines else None
        try:
            self._poll("VBAT")
        except (TimeoutError, linkmod.LinkLost):
            pass
        return {"reply": reply, "ok": bool(reply and reply.startswith("OK CALVBAT"))}

    # ------------------------------------------------------------------ Wi-Fi pull (backend only, 192.168.4.1)
    def wifi_status(self):
        try:
            return {"ok": True, "status": wifi.status()}
        except wifi.WifiError as ex:
            return {"ok": False, "error": str(ex)}

    def wifi_list(self):
        items = wifi.sessions()
        idx = save.library_sha_index()
        for it in items:
            it["known"] = idx.get(str(it.get("ok_sha") or ""))
        return {"sessions": items}

    def wifi_pull(self, name):
        if not (isinstance(name, str) and len(name) == 11 and name.startswith("S") and name.endswith(".wfg")):
            raise ValueError("bad session name")
        with self.lock:
            self._require_format()
            if self.busy:
                raise RuntimeError("busy: %s" % self.busy)
            self.busy = "wifi"
        try:
            self.app_line("wifi_pull", name=name)
            data, _, _ = wifi.download(name)
            sim = save.reserved_sim_id(data)
            saved = save.save_pulled(data, name, save.target_dir(sim, False), simulated=sim)
            rel = self._rel(saved["path"])
            self.app_line("sha_ok", cls="ok", sha=_short(save.sha256(data)), size="{:,}".format(len(data)))
            self.app_line("saved", path=rel)
            if not sim:
                try:
                    library.add(rel)
                except (OSError, ValueError):
                    pass
            s = library.load(saved["path"])
            ctx = {"size_match": True, "sha_match": True, "sha": save.sha256(data), "vbat": None, "free": None,
                   "restart_on_open": None, "screen": None, "usb_power": False, "device_name": name}
            result = dict(checks.compute(s, ctx), file=rel, pulled=_now_ms(), saved_status=saved["status"],
                          device_test=False, via="wifi")
            return {"ok": True, "file": rel, "result": result}
        finally:
            with self.lock:
                if self.busy == "wifi":
                    self.busy = None
            self._changed()

    # ------------------------------------------------------------------ the simulated logger (development only)
    def double_action(self, action, body=None):
        d = self.double
        if d is None:
            raise RuntimeError("no simulated logger: start the app with --dev-device-double")
        body = body or {}
        if action == "press":
            kind = body.get("kind", "short")
            if kind not in ("short", "long", "very_long"):
                raise ValueError("kind must be short, long or very_long")
            d.press(kind)
        elif action == "unplug":
            d.unplug()
        elif action == "replug":
            d.replug()
        elif action == "reset":
            d.reset()
        elif action == "gnss":
            if body.get("mode") not in ("indoor", "nodata", "cksum", "time", "fix"):
                raise ValueError("mode must be indoor, nodata, cksum, time or fix")
            d.gnss = body["mode"]
        elif action == "restart":
            for k, v in body.items():
                if k in d.restart_on:
                    d.restart_on[k] = bool(v)
        elif action == "battery":
            d.battery = bool(body.get("on"))
        elif action == "fill":
            d.used_extra = (d.free() + d.used_extra - 36_000) if body.get("on") else 0
        elif action == "fs_error":
            d.fs_fail_next_boot = True
            d.reset()
        elif action == "fs_ok":
            d.fs_ok = True
            d.reset()
        elif action == "corrupt":
            d.corrupt_next_dump = True
        elif action == "download":
            d.download_next_boot = True
            d.reset()
        elif action == "samples":
            k = d.next_session_no()
            for p in sorted(config.SIM_DIR.glob("*.wfg")):
                d.sessions["S%06d.wfg" % k] = p.read_bytes()
                k += 1
        else:
            raise ValueError("unknown action %s" % action)
        self._scan()
        self._changed()
        return {"ok": True, "double": d.snapshot()}
