"""Paths and fixed settings. Nothing here depends on where the planning package lives."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SESSIONS = ROOT / "sessions"
SIM_DIR = SESSIONS / "sim"
REAL_DIR = SESSIONS / "real"
DEVICE_TESTS_DIR = REAL_DIR / "device_tests"
LIBRARY_FILE = SESSIONS / "sessions.json"
PRIVACY_FILE = SESSIONS / "privacy.json"
ZONE_SECRET_FILE = SESSIONS / "zone_secret"      # privacy.secret(): made on first use, git-ignored
MAPDATA = ROOT / "mapdata"
OUT = ROOT / "out"
DEVICES = ROOT / "devices"
LOGS = ROOT / "logs"

DEFAULT_TZ = "Asia/Shanghai"
HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# Device id reserved for simulated data (the record format stores a u32; SIM uses 00000000).
SIM_DEVICE_ID = 0x00000000
