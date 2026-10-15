"""Heartbeat message format shared by the ESP32 firmware, the receiver and this software.

Two encodings carry the same fields.

1. BLE advertisement (sent by each tag): manufacturer-specific data, 13 bytes
   after the AD type, little-endian:

   offset size field       notes
   0      2    company_id  0xFFFF while prototyping (reserved for testing); register an ID before production
   2      2    magic       ASCII "LG" (0x4C 0x47)
   4      1    version     1
   5      2    node_id     1..65535, printed on the board
   7      2    seq         increments every heartbeat, wraps at 65535
   9      2    battery_mv  supply voltage in millivolts
   11     1    temp_c      signed, board temperature in degrees C (ESP32 internal sensor is fine)
   12     1    flags       bit0 test mode, bit1 low battery, bit2 over-temperature, bit3 tamper/manual burn

   Full AD structure: [0x0E, 0xFF, <13 bytes>] after the usual Flags AD [0x02, 0x01, 0x06].

2. Serial JSON lines (sent by a receiver ESP32 that scans BLE, or by the
   simulator), one object per line, UTF-8, newline terminated:

   {"v":1,"id":7,"seq":1234,"bat_mv":3010,"temp_c":31,"flags":0,"rssi":-67,"rx":"gw1"}

   The host stamps arrival time itself, so tag clocks never matter.

Heartbeat interval: 1 s for the booth (30 s or more in the field). A node is
declared dead after `timeout_beats` missed heartbeats (default 3), and its
death time is the arrival time of its last heartbeat.
"""
from __future__ import annotations

import json
import struct

COMPANY_ID_TESTING = 0xFFFF
MAGIC = b"LG"
VERSION = 1
_FMT = "<H2sBHHHbB"  # company, magic, version, node_id, seq, battery_mv, temp_c, flags
PAYLOAD_LEN = struct.calcsize(_FMT)  # 13

FLAG_TEST = 0x01
FLAG_LOW_BATTERY = 0x02
FLAG_OVER_TEMP = 0x04
FLAG_TAMPER = 0x08


def encode_adv(node_id, seq, battery_mv=3000, temp_c=25, flags=0, company_id=COMPANY_ID_TESTING) -> bytes:
    """Manufacturer data bytes (what follows the 0xFF AD type)."""
    return struct.pack(_FMT, company_id, MAGIC, VERSION, node_id, seq & 0xFFFF, battery_mv, temp_c, flags)


def decode_adv(data: bytes) -> dict | None:
    """Parse manufacturer data; returns None if it is not a Last Gasp heartbeat."""
    if len(data) < PAYLOAD_LEN:
        return None
    company, magic, version, node_id, seq, bat, temp, flags = struct.unpack(_FMT, data[:PAYLOAD_LEN])
    if magic != MAGIC or version != VERSION:
        return None
    return {"v": version, "id": node_id, "seq": seq, "bat_mv": bat, "temp_c": temp, "flags": flags}


def encode_json(msg: dict) -> str:
    return json.dumps(msg, separators=(",", ":")) + "\n"


def decode_json(line: str) -> dict | None:
    try:
        m = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(m, dict) or m.get("v") != VERSION or "id" not in m:
        return None
    return m
