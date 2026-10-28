#!/usr/bin/env python3
"""Build the optional native extension in this source checkout.

Run with the same CPython environment that will import the package. The
standard-library fallback does not require this script. Compiling requires
CPython development headers and a C compiler with __int128 support. Rebuilds
change the authenticated cache identity; never rebuild during a running use.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import sys
import sysconfig
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "wfg_routing_experimental"
SOURCE = PACKAGE / "native_cell.c"


def main():
    if sys.implementation.name != "cpython":
        raise SystemExit("The optional native backend requires CPython.")
    if sys.platform not in ("darwin", "linux"):
        raise SystemExit("Native building is supported experimentally on macOS and Linux only; other platforms are unvalidated.")
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    linker = sysconfig.get_config_var("LDSHARED")
    if not suffix or not linker:
        raise SystemExit("This interpreter does not expose an extension suffix or compiler command.")
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = [sysconfig.get_path("include"), sysconfig.get_config_var("INCLUDEPY"),
                  str(Path(sys.base_prefix) / "include" / version),
                  str(Path(sys.prefix) / "include" / version)]
    header = next((Path(p) for p in candidates if p and (Path(p) / "Python.h").is_file()), None)
    if header is None:
        raise SystemExit("CPython development headers (Python.h) are not available for this interpreter.")
    if not SOURCE.is_file() or SOURCE.is_symlink():
        raise SystemExit("Missing or unexpected native source file.")
    target = PACKAGE / ("wfg_native_cell" + suffix)
    if target.is_symlink():
        raise SystemExit("Refusing to replace a symlinked extension.")
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    # Build alongside the final target, then atomically install on success.
    fd, temporary_name = tempfile.mkstemp(prefix=".native-build-", suffix=suffix, dir=PACKAGE)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        command = (shlex.split(linker) + shlex.split(sysconfig.get_config_var("CCSHARED") or "")
                   + ["-O3", "-std=c11", "-fPIC", "-I" + str(header), str(SOURCE), "-o", str(temporary)])
        print("Building optional native extension with", shlex.join(command), flush=True)
        subprocess.run(command, check=True)
        if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
            raise RuntimeError("Native source changed during compilation; refusing to install.")
        binary_hash = hashlib.sha256(temporary.read_bytes()).hexdigest()
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Built {target}\nsource SHA-256: {source_hash}\nbinary SHA-256: {binary_hash}")
    print("The binary is machine-specific and ignored by git. Run the test suite before use.")


if __name__ == "__main__":
    main()
