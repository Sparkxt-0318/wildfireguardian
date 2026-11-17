"""Run FDS (6 MPI processes) on RUN_DIR/input.fds with memory, disk and wall-time guards.

Adapted from the C064 study's volume_run_guard.py. The free-disk floor is lower (default 1 GiB) because this run writes
only devices, HRR and one partial 3D HRRPUV slice (about 0.1 GB); the guard also caps the run directory size.
    FDS_ROOT=/path/to/fds/extracted python run_fds_guarded.py RUN_DIR WALL_LIMIT_S [MIN_FREE_GIB] [MAX_DIR_GIB]
writes RUN_DIR/guard.json.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


def dir_bytes(p):
    return sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file())


def main():
    folder = Path(sys.argv[1]).resolve(); limit = float(sys.argv[2])
    min_free = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    max_dir = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    root = Path(os.environ["FDS_ROOT"]).resolve()
    env = os.environ.copy()
    env.update(OPAL_PREFIX=str(root / "bin/openmpi"), DYLD_LIBRARY_PATH=str(root / "bin/openmpi/lib"), OMP_NUM_THREADS="1")
    start = time.monotonic(); peak = 0; stop = None; minfree = shutil.disk_usage(folder).free; maxdir = 0
    with (folder / "run.stdout").open("w") as out, (folder / "run.stderr").open("w") as err:
        p = subprocess.Popen([str(root / "bin/openmpi/bin/mpirun"), "-np", "6", str(root / "bin/fds"), "input.fds"],
                             cwd=folder, env=env, stdout=out, stderr=err, start_new_session=True)
        while p.poll() is None:
            minfree = min(minfree, shutil.disk_usage(folder).free)
            maxdir = max(maxdir, dir_bytes(folder))
            sample = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True)
            recs = []
            for line in sample.stdout.splitlines():
                try:
                    recs.append(tuple(map(int, line.split())))
                except ValueError:
                    pass
            ids = {p.pid}
            while True:
                more = {pid for pid, ppid, _ in recs if ppid in ids} - ids
                if not more:
                    break
                ids |= more
            peak = max(peak, sum(r * 1024 for pid, _, r in recs if pid in ids))
            if peak > 6 * 1024 ** 3:
                stop = "6 GiB sampled process-tree RSS"
            elif minfree < min_free * 1024 ** 3:
                stop = "%.2f GiB minimum free disk" % min_free
            elif maxdir > max_dir * 1024 ** 3:
                stop = "%.2f GiB run-directory cap" % max_dir
            elif time.monotonic() - start > limit:
                stop = "%.0f s wall-time guard" % limit
            if stop:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                break
            time.sleep(1.0)
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL); p.wait()
    outs = list(folder.glob("*.out"))
    success = bool(outs) and "STOP: FDS completed successfully" in outs[0].read_text(errors="replace")
    rec = {"exit_code": p.returncode, "stop": stop, "fds_success_marker": success, "elapsed_s": time.monotonic() - start,
           "sampled_process_tree_peak_rss_bytes": peak, "sampled_min_free_bytes": minfree, "sampled_max_dir_bytes": maxdir,
           "fds_binary": str(root / "bin/fds")}
    (folder / "guard.json").write_text(json.dumps(rec, indent=2) + "\n")
    print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    main()
