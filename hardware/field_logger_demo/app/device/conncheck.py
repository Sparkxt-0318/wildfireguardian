"""Connection check (spec section 3C, "Connection check"; the serial-open measurement of section 5).

The FireBeetle has an auto-reset circuit on DTR/RTS, so opening, closing, unplugging or replugging the port may restart
the ESP32. This guided check finds out which, for this board, while a recording runs:
  A: close, wait 8 s, open with pyserial's default open, watch 4 s for boot text, STATUS
  B: close, wait 8 s, open with DTR and RTS set False before open(), watch 4 s, STATUS
  C: the owner unplugs the cable for 3 s and plugs it back in (only with the battery fitted); open with a method that
     did not restart the board, watch 4 s, STATUS
Boot text right after an open means the open restarted the board. A new session name without boot text means the
close (or the unplug) did. After any restart the check waits 65 s, because the device counts auto-resumes and stops
resuming at 3 until a resumed session has recorded for 60 s. At the end the owner stops the recording, the sessions made
during the check are pulled, and their start and end reasons confirm the reading. The result goes into the board's
profile (devices/<device_id>.json).
"""
import threading
import time

from . import profiles

CASES = (("A", "default"), ("B", "lines_low"), ("C", None))


class Cancelled(Exception):
    pass


def session_no(name):
    try:
        return int(name[1:7])
    except (TypeError, ValueError, IndexError):
        return None


def interpret(n_prev, boot_seen, resume_was, state, session, stopped_seen):
    """Reading of one case. Returns {"open": bool, "other": bool or None, "n_now": int or None}.
    "other" is the close (cases A and B) or the unplug (case C)."""
    n_now = session_no(session) if state == "RECORDING" else None
    if boot_seen:
        if resume_was is not None:
            other = resume_was > n_prev                 # the session the open's restart cut came after n_prev
        elif n_now is not None:
            other = (n_now - n_prev) >= 2               # two new sessions: both the close and the open
        else:
            other = None                                # the recording stopped; nothing more to read
        return {"open": True, "other": other, "n_now": n_now}
    if n_now is not None:
        return {"open": False, "other": n_now > n_prev, "n_now": n_now}
    return {"open": False, "other": not stopped_seen, "n_now": None}


class ConnCheck(threading.Thread):
    def __init__(self, mgr):
        super().__init__(daemon=True, name="conncheck")
        self.mgr = mgr
        self.cancelled = False
        self.answer_ev = threading.Event()
        self.answer_val = None
        self.t = mgr.timing
        self.state = {"phase": "running", "prompt": "battery", "cases": {}, "battery": None, "wait": None,
                      "result": None, "error": None, "sessions": [], "started": int(time.time() * 1000)}

    # ------------------------------------------------------------------ owner interaction
    def answer(self, value):
        self.answer_val = value
        self.answer_ev.set()

    def cancel(self):
        self.cancelled = True
        self.answer_ev.set()

    def _check(self):
        if self.cancelled or not self.mgr.alive:
            raise Cancelled()

    def _set(self, **kw):
        self.state.update(kw)
        self.mgr.cc_changed()

    def _prompt(self, kind):
        self._set(prompt=kind, wait=None)

    def _wait_answer(self):
        self.answer_ev.clear()
        while not self.answer_ev.wait(0.2):
            self._check()
        self._check()
        return self.answer_val

    def _sleep(self, seconds, why):
        end = time.monotonic() + seconds
        self._set(wait={"why": why, "s": seconds, "until": int(time.time() * 1000 + seconds * 1000)})
        while True:
            self._check()
            left = end - time.monotonic()
            if left <= 0:
                break
            time.sleep(min(0.2, left))
        self._set(wait=None)

    def _until(self, fn, timeout, poll=1.0):
        """Wait until fn() returns a truthy value; returns it (None on timeout)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self._check()
            v = fn()
            if v:
                return v
            time.sleep(poll)
        return None

    def _recording(self):
        st = self.mgr.cmd_status()
        return st if st and st.get("state") == "RECORDING" else None

    def _idle(self):
        st = self.mgr.cmd_status()
        return st if st and st.get("state") != "RECORDING" else None

    # ------------------------------------------------------------------ the check
    def run(self):
        try:
            self._run()
            self._set(phase="done", prompt=None)
        except Cancelled:
            self._set(phase="cancelled", prompt=None, wait=None)
            self.mgr.app_line("cc_cancel")
        except Exception as ex:   # noqa: BLE001  (report any failure to the page instead of dying silently)
            self._set(phase="failed", prompt=None, wait=None, error=str(ex))
            self.mgr.app_line("cc_failed", cls="err", err=str(ex))
        finally:
            self.mgr.cc_finished(self)

    def _run(self):
        m = self.mgr
        m.app_line("cc_start")
        self._prompt("battery")
        battery = bool(self._wait_answer())
        self._set(battery=battery)
        st = self._recording()
        if not st:
            self._prompt("start_rec")
            st = self._until(self._recording, self.t["cc_rec_timeout"])
            if not st:
                raise RuntimeError("no recording started")
        first_no = n_prev = session_no(st["session"])
        port = m.conn_port()
        results = {}
        cases = [c for c in CASES if c[0] != "C" or battery]
        for case, method in cases:
            self._check()
            self.state["cases"][case] = {"st": "running"}
            self._set(prompt="case", case=case)
            m.app_line("cc_case", case=case, what=case)
            if case == "C":
                method = self._safe_method(results)
                self._prompt("unplug")
                m.app_line("cc_unplug")
                if not self._until(lambda: not m.port_listed(port["id"]), self.t["cc_unplug_timeout"], poll=0.3):
                    raise RuntimeError("the port did not go away")
                m.app_line("cc_gone")
                self._prompt("replug")
                if not self._until(lambda: m.port_listed(port["id"]), self.t["cc_unplug_timeout"], poll=0.3):
                    raise RuntimeError("the port did not come back")
                m.app_line("cc_back")
                self._prompt("case")
                self._sleep(self.t["cc_replug_settle"], "settle")
            else:
                m.close_for_check()
                m.app_line("cc_close", s=int(self.t["cc_close_wait"]))
                self._sleep(self.t["cc_close_wait"], "close")
            obs = m.open_for_check(port, method, self.t["cc_watch"])
            st = m.cmd_status() or {}
            r = interpret(n_prev, obs["boot"], obs["resume_was"], st.get("state"), st.get("session"),
                          obs["stopped"])
            res = {"st": "done", "method": method, "open": r["open"], "other": r["other"], "before": n_prev,
                   "after": r["n_now"], "state": st.get("state")}
            results[case] = res
            self.state["cases"][case] = res
            self._set()
            if r["open"]:
                m.app_line("cc_restart_open", cls="err")
            if r["other"]:
                m.app_line("cc_restart_other", cls="err", what="unplug" if case == "C" else "close")
            if not r["open"] and not r["other"]:
                m.app_line("cc_none")
            if r["open"] or r["other"]:
                m.app_line("cc_wait", s=int(self.t["cc_restart_wait"]))
                self._sleep(self.t["cc_restart_wait"], "resume_counter")
            st = m.cmd_status() or {}
            if st.get("state") == "RECORDING":
                n_prev = session_no(st.get("session"))
            elif case != cases[-1][0]:
                self._prompt("start_rec")
                st = self._until(self._recording, self.t["cc_rec_timeout"])
                if not st:
                    raise RuntimeError("no recording started")
                n_prev = session_no(st["session"])
        # 5. stop, pull the sessions made during the check, confirm from the files
        self._prompt("stop_rec")
        if not self._until(self._idle, self.t["cc_rec_timeout"]):
            raise RuntimeError("the recording was not stopped")
        self._prompt("pull")
        made = [s for s in m.cmd_list() if (session_no(s["name"]) or 0) >= first_no]
        m.app_line("cc_pull", n=len(made))
        checked = []
        for s in made:
            self._check()
            info = m.pull_quiet(s["name"])
            checked.append(info)
            m.app_line("cc_reason", name=s["name"], start=info.get("start_reason") or "-",
                       end=info.get("end_reason") or "-")
        self._set(sessions=checked)
        self._save(results, checked)

    def _safe_method(self, results):
        for case, method in (("A", "default"), ("B", "lines_low")):
            r = results.get(case)
            if r and not r["open"]:
                return method
        return "default"

    def _save(self, results, checked):
        m = self.mgr
        a, b, c = results.get("A"), results.get("B"), results.get("C")
        safe = None
        if a and not a["open"]:
            safe = "default"
        elif b and not b["open"]:
            safe = "lines_low"
        closes = [r["other"] for r in (a, b) if r and r["other"] is not None]
        summary = {"date": time.strftime("%Y-%m-%d %H:%M"), "fw": m.fw_version(),
                   "open_default": a["open"] if a else None, "open_lines_low": b["open"] if b else None,
                   "close": any(closes) if closes else None,
                   "unplug": c["other"] if c else None, "open_after_replug": c["open"] if c else None,
                   "battery_fitted": self.state["battery"],
                   "sessions": [{"name": x.get("name"), "start": x.get("start_reason"), "end": x.get("end_reason")}
                                for x in checked]}
        reconnect_ok = bool(safe and c and not c["open"] and not c["other"])
        rule = safe is None
        dev = m.device_id()
        prof = None
        if dev:
            prof = profiles.update(dev, conncheck=summary, open_method=safe or "default", reconnect_ok=reconnect_ok,
                                   rule_connect_first=rule)
        result = {"summary": summary, "open_method": safe, "reconnect_ok": reconnect_ok, "rule": rule}
        self._set(result=result)
        m.profile_changed(prof)
        m.app_line("cc_done", method=safe or "-", auto="yes" if reconnect_ok else "no")
        if rule:
            m.app_line("cc_rule")
