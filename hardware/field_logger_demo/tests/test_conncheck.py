"""Connection check (spec test 17). The double plays the board: it restarts on the open methods, on close or on the
replug as each case says, and follows the firmware's resume rules. The link reaches it through an injected port
object (a pseudo-terminal cannot carry DTR and RTS). The check's waits run on a fake clock: each wait moves the
double's time forward by the full amount (8 s after a close, 65 s after a restart) without the test waiting for it.
"""
import time

import pytest

from app.device import conncheck as ccmod
from app.device import double as dbl
from app.device import profiles
from app.device.conncheck import ConnCheck, interpret
from app.device.manager import DEFAULT_TIMING, DOUBLE_PORT, DeviceManager
from conftest import FAST, Recorder, only_extra_ports, wait_for

TIMING = dict(FAST, cc_close_wait=8.0, cc_restart_wait=65.0, cc_replug_settle=1.0)


@pytest.fixture
def sleeps(monkeypatch):
    log = []

    def fake_sleep(self, seconds, why):
        log.append((why, seconds))
        self._set(wait={"why": why, "s": seconds, "until": 0})
        self.mgr.double.advance(seconds, step=0.5)
        time.sleep(0.02)
        self._set(wait=None)
    monkeypatch.setattr(ConnCheck, "_sleep", fake_sleep)
    return log


def _rig(restart_on):
    d = dbl.LoggerDouble(clock=dbl.ManualClock(), restart_on=restart_on)
    rec = Recorder()
    m = DeviceManager(rec, double_obj=d, list_ports_fn=only_extra_ports, timing=TIMING)
    m.start()
    m.connect(DOUBLE_PORT)
    assert wait_for(lambda: m.conn["state"] == "connected" and m.busy is None, 8), m.conn
    return m, d, rec


def _drive(m, d, battery=True, timeout=60):
    """Play the owner: answer the battery question, press the button, unplug and replug when asked."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        cc = m.cc
        st = (cc.state if cc else m.cc_state) or {}
        if st.get("phase") in ("done", "failed", "cancelled") and m.cc is None:
            return st
        pr = st.get("prompt")
        if pr == "battery":
            m.conncheck_answer(battery)
        elif pr == "start_rec" and d.state != "RECORDING":
            d.press("long")
        elif pr == "unplug" and d.present:
            d.unplug()
        elif pr == "replug" and not d.present:
            d.replug()
        elif pr == "stop_rec" and d.state == "RECORDING":
            d.press("long")
        time.sleep(0.05)
    raise AssertionError("the connection check did not finish: %r" % st)


SCENARIOS = {
    # name: (restart_on, battery, expected summary fields, safe method, reconnect_ok, rule, cases followed by the 65 s wait)
    "nothing restarts": ({}, True, {"open_default": False, "open_lines_low": False, "close": False, "unplug": False},
                         "default", True, False, []),
    "open A restarts": ({"open_default": True}, True,
                        {"open_default": True, "open_lines_low": False, "close": False, "unplug": False},
                        "lines_low", True, False, ["A"]),
    "open B restarts": ({"open_lines_low": True}, True,
                        {"open_default": False, "open_lines_low": True, "close": False, "unplug": False},
                        "default", True, False, ["B"]),
    "close restarts": ({"close": True}, True,
                       {"open_default": False, "open_lines_low": False, "close": True, "unplug": False},
                       "default", True, False, ["A", "B"]),
    "replug restarts": ({"unplug": True}, True,
                        {"open_default": False, "open_lines_low": False, "close": False, "unplug": True},
                        "default", False, False, ["C"]),
    "every open restarts": ({"open_default": True, "open_lines_low": True}, True,
                            {"open_default": True, "open_lines_low": True, "close": False},
                            None, False, True, ["A", "B", "C"]),
    "no cell fitted": ({}, False, {"open_default": False, "open_lines_low": False, "close": False, "unplug": None},
                       "default", False, False, []),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_each_restart_gives_the_right_profile(tmp_root, sleeps, name):
    restart_on, battery, expect, safe, reconnect_ok, rule, waited = SCENARIOS[name]
    m, d, rec = _rig(restart_on)
    try:
        if restart_on.get("open_default"):
            assert m.restart_on_open is True             # the first connect already saw it
        m.conncheck_start()
        st = _drive(m, d, battery=battery)
        assert st["phase"] == "done", (st, rec.codes()[-10:])
        res = st["result"]
        for k, v in expect.items():
            assert res["summary"][k] == v, (name, k, res["summary"])
        assert res["open_method"] == safe and res["reconnect_ok"] == reconnect_ok and res["rule"] == rule
        # the 65 s wait follows every restart and nothing else
        cases = list(st["cases"])
        restarted = [c for c in cases if st["cases"][c]["open"] or st["cases"][c]["other"]]
        assert restarted == waited, (st["cases"], restarted)
        assert [s for w, s in sleeps if w == "resume_counter"] == [65.0] * len(waited)
        assert [s for w, s in sleeps if w == "close"] == [8.0] * len([c for c in cases if c != "C"])
        assert not any("RESET LOOP" in (e.get("raw") or "") for e in rec.lines())   # the waits kept the counter low
        # the sessions made during the check confirm the reading
        made = st["sessions"]
        assert made and all(s["ok"] for s in made)
        assert [s["start_reason"] for s in made][0] == "OWNER_BUTTON"
        assert sum(1 for s in made if s["start_reason"] == "AUTO_RESUMED_AFTER_RESET") == len(waited)
        assert sum(1 for s in made if s["end_reason"] == "RECOVERED_ON_BOOT") == len(waited)
        assert made[-1]["end_reason"] == "USER_STOP"
        prof = profiles.load(m.device_id())
        assert prof["open_method"] == (safe or "default") and prof["reconnect_ok"] == reconnect_ok
        assert prof["rule_connect_first"] == rule and prof["conncheck"]["fw"] == "0.2.0"
        # afterwards: the app opens with the safe method, and reconnects by itself only when allowed
        m.disconnect()
        d.restart_on.update({"open_default": False, "open_lines_low": False, "close": False, "unplug": False})
        m.connect(DOUBLE_PORT)
        assert wait_for(lambda: m.conn["state"] == "connected" and m.busy is None, 8)
        assert d.port.method == (safe or "default") and m.conn["method"] == (safe or "default")
        d.unplug()
        assert wait_for(lambda: m.conn["state"] == "lost", 5)
        d.replug()
        if reconnect_ok:
            assert wait_for(lambda: m.conn["state"] == "connected", 5), m.conn
        else:
            time.sleep(0.6)
            assert m.conn["state"] == "lost" and d.port is None
    finally:
        m.shutdown()


def test_the_check_can_be_cancelled(tmp_root, sleeps):
    m, d, rec = _rig({})
    try:
        m.conncheck_start()
        assert wait_for(lambda: m.cc and m.cc.state["prompt"] == "battery", 5)
        m.conncheck_cancel()
        assert wait_for(lambda: m.cc is None and m.cc_state and m.cc_state["phase"] == "cancelled", 5)
        assert m.busy is None and m.conn["state"] == "connected"
        assert profiles.load(m.device_id()).get("conncheck") is None
    finally:
        m.shutdown()


def test_real_timings():
    assert DEFAULT_TIMING["cc_close_wait"] == 8.0 and DEFAULT_TIMING["cc_restart_wait"] == 65.0
    assert DEFAULT_TIMING["cc_watch"] == 4.0 and DEFAULT_TIMING["watch_s"] == 3.0 and DEFAULT_TIMING["boot_wait_s"] == 8.0
    assert ccmod.CASES == (("A", "default"), ("B", "lines_low"), ("C", None))


def test_interpret():
    # boot text right after the open: the open restarted it; the resume line says which session the restart cut
    assert interpret(3, True, 3, "RECORDING", "S000004.wfg", False) == {"open": True, "other": False, "n_now": 4}
    assert interpret(3, True, 4, "RECORDING", "S000005.wfg", False) == {"open": True, "other": True, "n_now": 5}
    assert interpret(3, True, None, "RECORDING", "S000005.wfg", False)["other"] is True
    # no boot text: a new session means the close (or the unplug) restarted it
    assert interpret(3, False, None, "RECORDING", "S000004.wfg", False) == {"open": False, "other": True, "n_now": 4}
    assert interpret(3, False, None, "RECORDING", "S000003.wfg", False) == {"open": False, "other": False, "n_now": 3}
    # the recording ended without '# STOPPED - saved': a restart whose resume was blocked
    assert interpret(3, False, None, "IDLE", None, False) == {"open": False, "other": True, "n_now": None}
    assert interpret(3, False, None, "IDLE", None, True) == {"open": False, "other": False, "n_now": None}


def test_the_double_follows_the_resume_rules():
    """Every auto-resume adds 1; an owner start or 60 s of resumed recording sets it back to 0; at 3: RESET LOOP."""
    d = dbl.LoggerDouble(clock=dbl.ManualClock(), autostart=False)
    port = d.open_port("default")
    d.press("long")
    assert d.state == "RECORDING" and d.nvs["rs_qf"] == 0
    for k in (1, 2, 3):
        d.reset()
        assert d.state == "RECORDING" and d.nvs["rs_qf"] == k and d.cur_no == k + 1
    port.buf.clear()
    d.reset()                                                   # the fourth quick restart finds the counter at 3
    text = bytes(port.buf).decode()
    assert "# RESUME decision GIVE_UP_LOOP (was S000004 mode WALK" in text and "# RESET LOOP: not resuming" in text
    assert d.state == "IDLE" and d.nvs["rs_qf"] == 0
    d.press("long")                                             # owner start
    d.reset()
    assert d.nvs["rs_qf"] == 1
    d.advance(61.0)                                             # 60 s of resumed recording
    assert d.nvs["rs_qf"] == 0
    names = sorted(d.sessions)
    assert names[0] == "S000001.wfg"
    d.close()
