"""Stitch the rerun's cell-centred 3D HRRPUV slice (x 30..110 m) into one [t, z, y, x] array.

    python stitch_fds_slice.py FDS_RUN_DIR OUT.npz

Decoding follows the C064 study's export_slices.read_slcc (verified there against fdsreader): Fortran records, padded
index 0 on each axis, interior cells 1..N. Mesh extents come from the &MESH records of input.fds (mesh k = k-th
record); the SLCC entries of the .smv give mesh number, index bounds and file name. Zero-thickness entries (FDS writes
one on the face x = 30 m of mesh [10, 30]) are skipped. Every target cell must be written exactly once.
"""
import re
import struct
import sys
from pathlib import Path

import numpy as np


def record(f, optional=False):
    raw = f.read(4)
    if not raw and optional:
        return None
    n = struct.unpack("<i", raw)[0]
    data = f.read(n); trail = struct.unpack("<i", f.read(4))[0]
    if len(data) != n or trail != n:
        raise ValueError("inconsistent Fortran record")
    return data


def read_slcc(path):
    with open(path, "rb") as f:
        name = record(f).decode().strip(); record(f); unit = record(f).decode().strip()
        i0, i1, j0, j1, k0, k1 = struct.unpack("<6i", record(f))
        dims = (i1 - i0 + 1, j1 - j0 + 1, k1 - k0 + 1)
        times, frames = [], []
        while (t := record(f, True)) is not None:
            times.append(struct.unpack("<f", t)[0])
            a = np.frombuffer(record(f), dtype="<f4").reshape(dims, order="F")
            frames.append(a[1:, 1:, 1:].transpose(2, 1, 0).copy())
    return name, unit, (i0, i1, j0, j1, k0, k1), np.asarray(times), np.asarray(frames, dtype=np.float32)


def main(run_dir, out):
    run = Path(run_dir)
    meshes = [tuple(map(float, m.group(1).split(","))) for m in
              re.finditer(r"&MESH[^/]*XB=([-\d.,\s]+?),\s*MPI_PROCESS", (run / "input.fds").read_text())]
    smv = (run / [p.name for p in run.glob("*.smv")][0]).read_text().splitlines()
    entries = []
    for i, line in enumerate(smv):
        m = re.match(r"^SLCC\s+(\d+)\s+.*&\s*(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)", line)
        if m and smv[i + 2].strip() == "HRRPUV":
            entries.append((int(m.group(1)), tuple(map(int, m.groups()[1:])), smv[i + 1].strip()))
    X0, Y0, Z0, NX, NY, NZ = 30.0, -60.0, 0.0, 80, 120, 20
    h = None; count = np.zeros((NZ, NY, NX), dtype=int); times = None
    for mid, b, fname in entries:
        if b[0] == b[1] or b[2] == b[3] or b[4] == b[5]:
            continue
        xb = meshes[mid - 1]
        _, unit, bounds, t, a = read_slcc(run / fname)
        if unit != "kW/m3" or bounds != b or bounds[::2] != (0, 0, 0):
            raise SystemExit("unexpected slice header %s %s %s" % (fname, unit, bounds))
        if times is None:
            times = t; h = np.full((len(t), NZ, NY, NX), np.nan, dtype=np.float32)
        elif not np.array_equal(t, times):
            raise SystemExit("slice clocks differ: %s" % fname)
        i0, j0, k0 = int(round(xb[0] - X0)), int(round(xb[2] - Y0)), int(round(xb[4] - Z0))
        nz, ny, nx = a.shape[1:]
        h[:, k0:k0 + nz, j0:j0 + ny, i0:i0 + nx] = a
        count[k0:k0 + nz, j0:j0 + ny, i0:i0 + nx] += 1
    if not (count == 1).all() or np.isnan(h).any():
        raise SystemExit("cells not covered exactly once")
    np.savez_compressed(out, hrrpuv_kw_m3=h, time_s=times, x_m=X0 + 0.5 + np.arange(NX), y_m=Y0 + 0.5 + np.arange(NY),
                        z_m=Z0 + 0.5 + np.arange(NZ))
    print(out, h.shape, float(times[0]), float(times[-1]), "meshes used", int((count > 0).sum() // 8000))


if __name__ == "__main__":
    main(*sys.argv[1:3])
