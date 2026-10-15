#!/usr/bin/env python3
"""Write the SIM library: the synthetic city map data (mapdata/sim_city/) and four SIMULATED sessions in sessions/sim/
(a walk through 4 crossings, a vehicle ride with 6 traffic lights, a 30 m loop and a 10 km drive), each with a
.sim.json sidecar holding the ground truth. Then it updates sessions/sessions.json: SIM entries are added or replaced,
real entries are kept.

  python3 tools/make_sim_session.py            (from the field_logger_demo folder)

SIM files use the reserved device id 00000000 and are watermarked everywhere in the app. Never copy them to
sessions/real/.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from app import config, mapgen, simgen  # noqa: E402
from app.vendor import usb_export as ux  # noqa: E402


def main():
    meta = mapgen.write(config.MAPDATA / mapgen.AREA)
    print("map data:", config.MAPDATA / mapgen.AREA, "(synthetic, %s)" % meta["attribution"]["en"])
    entries = simgen.write_library(config.SIM_DIR)
    for e in entries:
        data = (config.SESSIONS / e["file"]).read_bytes()
        rep = ux.integrity(data)
        print("%-34s %6d B  %5d records  status=%s" % (e["file"], len(data), rep["records"], rep["status"]))
    lib = []
    if config.LIBRARY_FILE.exists():
        lib = [x for x in json.loads(config.LIBRARY_FILE.read_text(encoding="utf-8"))
               if not str(x.get("file", "")).startswith("sim/")]
    used = {x["key"] for x in lib}
    free_keys = [k for k in range(1, 10) if k not in used]
    for e in entries:
        if free_keys:
            e["key"] = free_keys.pop(0)
        else:
            e["key"] = None
        lib.append(e)
    lib.sort(key=lambda x: (x["key"] is None, x["key"] or 0))
    config.LIBRARY_FILE.write_text(json.dumps(lib, ensure_ascii=False, indent=1), encoding="utf-8")
    print("library:", config.LIBRARY_FILE, "(%d entries)" % len(lib))


if __name__ == "__main__":
    main()
