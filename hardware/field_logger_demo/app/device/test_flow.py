"""The one-minute test recording (spec section 3C, "Test recording").

Five steps. A step turns green only when the device itself confirms it with a '#' line or a STATUS reply; the app
never completes a step on its own. The device's real behaviour wins over the script: a long press during step 2 or 3
ends the recording and the flow goes to step 5 with what was recorded.
"""
import time

WAIT_S = 30.0
STOP_CODES = ("stopped", "low_batt_stop", "full_stop")


def _ms():
    return int(time.time() * 1000)


class TestFlow:
    def __init__(self, status, now=None):
        """status: the last parsed STATUS reply (or None)."""
        now = time.monotonic() if now is None else now
        self.steps = [{"st": "now"}, {"st": "todo"}, {"st": "todo"}, {"st": "todo"}, {"st": "todo"}]
        self.phase = "running"            # running | pulling | done | failed | cancelled | interrupted
        self.session = None
        self.t1 = None                    # monotonic seconds when step 1 was confirmed
        self.records = 0
        self.note = None                  # "export_on" | "full" | None
        self.started_before = False       # recording already when T was pressed: step 1 says "이미 기록 중"
        self.before_connect = False       # ... and already when the laptop connected: the result says so (manager)
        self.restarted = False
        self.error = None
        self.session_at_start = status.get("session") if status else None
        self.created = _ms()
        if status and status.get("state") == "RECORDING":
            self.started_before = True
            self._step1(status.get("session"), now, "already")

    # ------------------------------------------------------------------ transitions
    def _step1(self, session, now, variant):
        self.session = session
        self.t1 = now
        self.steps[0] = {"st": "done", "at": _ms(), "session": session, "variant": variant}
        self.steps[1] = {"st": "now"}
        self.note = None if self.note == "full" else self.note

    def on_note(self, code, groups, now=None):
        """A '#' line the firmware printed (notes.classify code). Returns True when something changed."""
        now = time.monotonic() if now is None else now
        if self.phase != "running":
            return False
        s1, s2, s3, s4 = (self.steps[i]["st"] for i in range(4))
        if code == "rec" and s1 != "done":
            self._step1(groups[0], now, "started")
            return True
        if code == "full" and s1 != "done":
            self.note = "full"
            return True
        if code == "export_on":
            self.note = "export_on"
            return True
        if code in ("export_off", "export_timeout") and self.note == "export_on":
            self.note = None
            return True
        if code in ("boot", "rom_boot", "resumed"):
            self.restarted = True
            return True
        if code == "event" and s1 == "done" and s2 != "done" and s4 != "done":
            self.steps[1] = {"st": "done", "at": _ms(), "n": int(groups[0]), "located": groups[1] == "marked"}
            if s3 != "done":
                self.steps[2] = {"st": "now"}
            return True
        if code in STOP_CODES and s1 == "done" and s4 != "done":
            self._step4(code)
            return True
        return False

    def on_status(self, st, now=None):
        now = time.monotonic() if now is None else now
        if self.phase != "running" or not st:
            return False
        changed = False
        s1, s2, s3, s4 = (self.steps[i]["st"] for i in range(4))
        if s1 != "done":
            if st.get("state") == "RECORDING" and st.get("session") and st.get("session") != self.session_at_start:
                self._step1(st["session"], now, "started")
                return True
            return False
        if st.get("state") == "RECORDING":
            if st.get("seq") is not None and st["seq"] != self.records:
                self.records = st["seq"]
                changed = True
            if s2 == "done" and s3 != "done" and now - self.t1 >= WAIT_S:
                self.steps[2] = {"st": "done", "at": _ms(), "el": WAIT_S, "n": self.records}
                self.steps[3] = {"st": "now"}
                changed = True
        elif s4 != "done" and st.get("session") is None:
            self._step4("idle")
            changed = True
        return changed

    def _step4(self, reason):
        for i in (1, 2):
            if self.steps[i]["st"] != "done":
                self.steps[i] = {"st": "skipped"}
        self.steps[3] = {"st": "done", "at": _ms(), "reason": reason}
        self.steps[4] = {"st": "now"}
        self.phase = "pulling"

    def pulled(self, ok, error=None):
        self.steps[4] = {"st": "done" if ok else "failed", "at": _ms(), "error": error}
        self.phase = "done" if ok else "failed"
        self.error = error

    def cancel(self):
        if self.phase in ("running", "pulling"):
            self.phase = "cancelled"

    def interrupt(self):
        if self.phase in ("running", "pulling"):
            self.phase = "interrupted"

    @property
    def ready_to_pull(self):
        return self.phase == "pulling" and self.steps[4]["st"] == "now"

    def to_dict(self, now=None):
        now = time.monotonic() if now is None else now
        el = None
        if self.t1 is not None and self.steps[3]["st"] != "done":
            el = round(now - self.t1, 1)
        return {"phase": self.phase, "steps": self.steps, "session": self.session, "elapsed": el,
                "wait_s": WAIT_S, "records": self.records, "note": self.note, "started_before": self.started_before,
                "restarted": self.restarted, "error": self.error, "created": self.created}
