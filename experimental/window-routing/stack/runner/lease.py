"""Shared heavy-timing lease client (protocol: outputs/SHARED_HEAVY_TIMING_LOCK.md). Never overwrites a valid foreign lease.
Usage: python lease.py LOCK_JSON acquire|renew|release|status HOLDER [PURPOSE] [MINUTES]"""
import datetime, json, os, sys, time
from pathlib import Path
def now(): return datetime.datetime.now(datetime.timezone.utc)
def read(p):
    try: return json.loads(Path(p).read_text())
    except Exception as e: return {"status": "UNREADABLE", "error": str(e)}
def valid_foreign(d, holder):
    if d.get("status") != "HELD" or d.get("holder") == holder: return False
    try: return datetime.datetime.fromisoformat(d["lease_until_utc"]) > now()
    except Exception: return True
def log(p, line):
    with open(Path(p).with_suffix(".log"), "a") as f: f.write(now().isoformat() + " " + line + "\n")
def write(p, d):
    Path(p).write_text(json.dumps(d))
def main():
    p, op, holder = sys.argv[1], sys.argv[2], sys.argv[3]
    purpose = sys.argv[4] if len(sys.argv) > 4 else "FFI1"
    minutes = float(sys.argv[5]) if len(sys.argv) > 5 else 30.0
    d = read(p)
    if op == "status":
        print(json.dumps({"lock": d, "foreign_valid": valid_foreign(d, holder)})); return 0
    if op in ("acquire", "renew"):
        if valid_foreign(d, holder):
            print(json.dumps({"result": "BUSY", "lock": d})); return 3
        if op == "renew" and d.get("holder") != holder:
            print(json.dumps({"result": "NOT_HOLDER", "lock": d})); return 4
        t = now()
        mine = {"status": "HELD", "holder": holder, "acquired_utc": d.get("acquired_utc") if op == "renew" else t.isoformat(),
                "lease_until_utc": (t + datetime.timedelta(minutes=min(minutes, 45))).isoformat(), "purpose": purpose}
        write(p, mine)
        if op == "acquire":
            time.sleep(5)
            if read(p).get("holder") != holder:
                print(json.dumps({"result": "LOST_RACE", "lock": read(p)})); return 5
            log(p, "ACQUIRE " + holder + " " + purpose)
        print(json.dumps({"result": "HELD", "lock": read(p)})); return 0
    if op == "release":
        if d.get("holder") != holder:
            print(json.dumps({"result": "NOT_HOLDER", "lock": d})); return 4
        write(p, {"status": "FREE", "released_by": holder, "released_utc": now().isoformat()}); log(p, "RELEASE " + holder)
        print(json.dumps({"result": "RELEASED"})); return 0
if __name__ == "__main__": sys.exit(main())
