"""Notes for the lines the firmware prints (firmware 0.2.0, main.cpp banner() and setup()). Anchored patterns; a line
that matches none is shown unchanged. The page turns the code into Korean or English text (i18n keys note.*)."""
import re

PATTERNS = [
    ("rec", re.compile(r"^# REC (S\d{6}\.wfg) (WALK|VEHICLE|UNKNOWN)$")),
    ("event", re.compile(r"^# EVENT (\d+) (marked|\(NO POSITION\))$")),
    ("stopped", re.compile(r"^# STOPPED - saved$")),
    ("mode", re.compile(r"^# MODE: (WALK|VEHICLE|UNKNOWN)$")),
    ("export_on", re.compile(r"^# Export mode ON$")),
    ("export_off", re.compile(r"^# Export mode OFF$")),
    ("export_timeout", re.compile(r"^# Export mode timed out$")),
    ("boot", re.compile(r"^# WFG logger fw (\S+) board (.+) device ([0-9A-F]{8})$")),
    ("resumed", re.compile(r"^# AUTO-RESUMED after reset$")),
    ("resume_decision", re.compile(r"^# RESUME decision (\w+) \(was (S\d{6}) mode (\w+), reset_reason (\d+), "
                                   r"quick_fails (\d+)\)$")),
    ("reset_loop", re.compile(r"^# RESET LOOP: not resuming$")),
    ("recovered_detail", re.compile(r"^# RECOVERED (S\d{6}\.wfg) records=(\d+) torn_bytes=(\d+) closed=(\d+) "
                                    r"unrecoverable=(\d+)$")),
    ("recovered", re.compile(r"^# RECOVERED (\d+) sessions?$")),
    ("low_batt_stop", re.compile(r"^# LOW BATTERY - stopped$")),
    ("low_batt_noresume", re.compile(r"^# LOW BATT: not resuming$")),
    ("full_stop", re.compile(r"^# STORAGE FULL - stopped$")),
    ("full", re.compile(r"^# FULL: (.+)$")),
    ("fs_error", re.compile(r"^# (FS ERROR: see README|LittleFS mount failed.*|FLASH SIZE MISMATCH.*)$")),
    ("start_failed", re.compile(r"^# START FAILED$")),
    ("resume_failed", re.compile(r"^# RESUME FAILED$")),
    ("fs_blank", re.compile(r"^# LittleFS partition is blank: formatting.*$")),
]
ERROR_CODES = {"fs_error", "start_failed", "resume_failed"}
ROM_BOOT = re.compile(r"(rst:0x|boot:0x|ets )")
DOWNLOAD = re.compile(r"(DOWNLOAD_BOOT|waiting for download)")

EN = {"rec": "recording started · {0}", "event": "button mark {0}", "stopped": "recording stopped · saved",
      "mode": "movement mode · {0}", "export_on": "Wi-Fi export on", "export_off": "Wi-Fi export off",
      "export_timeout": "Wi-Fi export timed out", "boot": "device started", "resumed": "restarted; recording resumed",
      "resume_decision": "resume decision · {0}", "reset_loop": "repeated restarts: not resuming",
      "recovered_detail": "earlier session recovered · {0}", "recovered": "earlier session recovered",
      "low_batt_stop": "stopped: battery low", "low_batt_noresume": "battery low", "full_stop": "storage full",
      "full": "storage full", "fs_error": "error", "start_failed": "error", "resume_failed": "error",
      "fs_blank": "first start: storage prepared", "rom_boot": "device restarting", "download_mode": "flashing mode",
      "basic": "basic link · STATUS every 1 s", "vbat_unknown": "no VBAT command in this firmware · battery unknown",
      "fs": "storage cannot be opened"}


def classify(line):
    """Return (code, groups) for a firmware line, or (None, ()) when unknown. Also recognises ROM boot text."""
    if line.startswith("#"):
        for code, rx in PATTERNS:
            m = rx.match(line)
            if m:
                return code, m.groups()
        return None, ()
    if DOWNLOAD.search(line):
        return "download_mode", ()
    if ROM_BOOT.search(line):
        return "rom_boot", ()
    return None, ()


def english(code, groups):
    if code == "event" and len(groups) == 2:
        return "button mark %s · %s" % (groups[0], "with position" if groups[1] == "marked" else "no position")
    t = EN.get(code)
    if not t:
        return ""
    try:
        return t.format(*groups)
    except (IndexError, KeyError):
        return t
