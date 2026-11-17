"""Derive the radiometer rerun input from the packaged C064 input (B.2).

Reads the concatenated FDS input that produced fire-data/csiro-volume-dt5-120.npz and applies only these edits:

  * CHID renamed (so outputs cannot be confused with the earlier run);
  * T_END 120 s -> 140 s, so the head can reach the end of the fuel bed (x = 100 m) and the
    radiometers see distances down to ~2 m (the earlier run stopped with the head near x = 93 m);
  * DUMP: DT_DEVC 0.5 s (as requested), DT_HRR 0.5 s, DT_SLCF 1 s and DT_SL3D 1 s (3D slices follow DT_SL3D; a
    first run without it wrote only 6 volume frames and is kept as run A, see FDS_CHECK.md);
  * all output-only SLCF/BNDF records removed and replaced by one 3D HRRPUV slice over
    x 30..110 m (for the same-run voxel-sum comparison); output records do not change the solution;
  * gas-phase radiometers added: QUANTITY='RADIATIVE HEAT FLUX GAS', ORIENTATION=-1,0,0 (facing the
    fire, which arrives from -x), on the centreline y = 0, z = 1.5 m, at x = 102, 105, 108 m
    (requested) and x = 80, 90 m (supplementary, inside the fuel bed, used only while the front is behind them).

Physics records (meshes, fuel, wind, reaction, radiation defaults) are untouched. Usage:
    python make_fds_input.py SOURCE.fds OUT_DIR
writes OUT_DIR/input.fds and OUT_DIR/input_manifest.json.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

RADIOMETERS = [  # (id, x, role)
    ("RAD_X102", 102.0, "requested"),
    ("RAD_X105", 105.0, "requested"),
    ("RAD_X108", 108.0, "requested"),
    ("RAD_X080", 80.0, "supplementary"),
    ("RAD_X090", 90.0, "supplementary"),
]
Y, Z = 0.0, 1.5
NEW_CHID = "C064_kcf_radiometers"
T_END = 140.0


def derive(text: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("&HEAD"):
            line = re.sub(r"CHID='[^']*'", "CHID='%s'" % NEW_CHID, line)
        elif s.startswith("&TIME"):
            line = "&TIME T_END=%.1f /" % T_END
        elif s.startswith("&DUMP"):
            line = "&DUMP DT_HRR=0.5, DT_DEVC=0.5, DT_SLCF=1.0, DT_SL3D=1.0, SIG_FIGS=5, SIG_FIGS_EXP=2 /"
        elif s.startswith("&SLCF") or s.startswith("&BNDF"):
            continue
        elif s.startswith("&TAIL"):
            out.append("&SLCF XB=30,110,-60,60,0,20, QUANTITY='HRRPUV', CELL_CENTERED=T /")
            for ident, x, role in RADIOMETERS:
                out.append("&DEVC ID='%s', QUANTITY='RADIATIVE HEAT FLUX GAS', XYZ=%.1f,%.1f,%.1f, "
                           "ORIENTATION=-1,0,0 / %s" % (ident, x, Y, Z, role))
            out.append("")
        out.append(line)
    return "\n".join(out) + "\n"


def main(src, out_dir):
    src = Path(src); out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = src.read_bytes()
    new = derive(raw.decode())
    (out_dir / "input.fds").write_text(new)
    # the &CATF record of the source is already expanded in the concatenated file; refuse if one remains
    if "&CATF" in new:
        raise SystemExit("unexpanded &CATF in source; use the concatenated input")
    manifest = {
        "source_input": str(src), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "derived_input_sha256": hashlib.sha256(new.encode()).hexdigest(),
        "chid": NEW_CHID, "t_end_s": T_END, "dt_devc_s": 0.5,
        "radiometers": [{"id": i, "xyz_m": [x, Y, Z], "orientation": [-1, 0, 0], "role": r} for i, x, r in RADIOMETERS],
        "edits": __doc__.split("Physics records")[0].strip(),
    }
    (out_dir / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: manifest[k] for k in ("source_sha256", "derived_input_sha256", "chid")}))


if __name__ == "__main__":
    main(*sys.argv[1:3])
