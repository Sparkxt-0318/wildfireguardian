#!/usr/bin/env python3
"""Build the pinned, public legacy FARSITE Unix port on Linux or macOS.

This is a platform build helper, not an implementation of the fire model.
The source patches replace Linux's backup-file copying on macOS and correct
two invalid pointer expressions accepted by older, permissive builds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path


REPOSITORY = "https://github.com/mbedward/farsite.git"
REVISION = "4537d60ab013fa91d0b49d8efb385ffb1b3ddd13"
ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout


def _macos_copy_patch(source: Path) -> bool:
    """Change the backup-copy API only; preserve all model computations."""
    path = source / "src" / "Farsite5.cpp"
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    marker = "// wildfire macOS backup-copy portability shim"
    if marker in text:
        return True
    header = "#include <sys/sendfile.h>"
    replacement = ("#ifdef __APPLE__\n#include <copyfile.h>\n#else\n"
                   "#include <sys/sendfile.h>\n#endif")
    if text.count(header) != 1:
        raise RuntimeError("Pinned FARSITE backup-copy include was not found exactly once")
    text = text.replace(header, replacement)
    start = text.index("void CopyFile(char *in, char *out, bool unused)\n{")
    end = text.index("\n}\n#endif", start) + 2
    original = text[start:end]
    patched = ("void CopyFile(char *in, char *out, bool unused)\n{\n"
               "#ifdef __APPLE__\n"
               f"    {marker}\n"
               "    copyfile(in, out, NULL, COPYFILE_DATA | COPYFILE_STAT);\n"
               "#else\n" + original.split("{", 1)[1].rsplit("}", 1)[0]
               + "#endif\n}")
    text = text[:start] + patched + text[end:]
    newline = "\r\n" if b"\r\n" in raw else "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return True


def _pointer_syntax_patch(source: Path) -> None:
    """Correct two rejected pointer expressions, without model changes."""
    path = source / "src" / "Farsite5.cpp"
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    text = text.replace("if (perimeter1[NumFire] && perimeter1[NumFire] > 0)",
                        "if (perimeter1[NumFire] != NULL)")
    text = text.replace("long* Farsite5::GetElevAddress(long Num)\n{\n\tif (!GroundElev)\n\t\treturn (long) NULL;",
                        "long* Farsite5::GetElevAddress(long Num)\n{\n\tif (!GroundElev)\n\t\treturn NULL;")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def _apply_validated_patches(source: Path, system: str) -> bool:
    """Reject extra tracked edits before making documented platform changes."""
    modified = set(_run(["git", "diff", "--name-only", "HEAD"], source).splitlines())
    if modified - {"src/Farsite5.cpp"}:
        raise RuntimeError(f"FARSITE source has unrelated tracked edits: {sorted(modified)}")
    pristine = subprocess.run(["git", "show", "HEAD:src/Farsite5.cpp"], cwd=source,
                              check=True, stdout=subprocess.PIPE).stdout
    with tempfile.TemporaryDirectory(prefix="wildfire-farsite-patch-") as temp:
        expected_root = Path(temp)
        (expected_root / "src").mkdir()
        expected_file = expected_root / "src" / "Farsite5.cpp"
        expected_file.write_bytes(pristine)
        if system == "Darwin":
            _macos_copy_patch(expected_root)
        _pointer_syntax_patch(expected_root)
        expected = expected_file.read_bytes()
    actual_file = source / "src" / "Farsite5.cpp"
    if actual_file.read_bytes() not in {pristine, expected}:
        raise RuntimeError("FARSITE source differs from the pinned revision and documented portability patches")
    actual_file.write_bytes(expected)
    return system == "Darwin"


def build_engine(source_dir: Path | str | None = None, *, jobs: int = 4,
                 examples: bool = False) -> Path:
    """Acquire and build authentic pinned FARSITE; return its executable.

    A ``build_manifest.json`` beside the source records source revision,
    compiler, portability changes, and the executable digest.  Acquisition
    requires GitHub network access; rebuilding an existing checkout does not.
    """
    if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs < 1:
        raise ValueError("jobs must be a positive integer")
    source = Path(source_dir or ROOT / "tmp" / "farsite_source").resolve()
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        _run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
              REPOSITORY, str(source)])
    if not (source / ".git").exists():
        raise RuntimeError(f"Refusing to overwrite a non-Git source directory: {source}")
    actual = _run(["git", "rev-parse", "HEAD"], source).strip()
    if actual != REVISION:
        _run(["git", "fetch", "--depth", "1", "origin", REVISION], source)
        _run(["git", "checkout", "--detach", REVISION], source)
    sparse = ["src"]
    if examples:
        sparse += ["examples/flatland/Inputs", "examples/flatland/caseRunFiles"]
    _run(["git", "sparse-checkout", "set", *sparse], source)
    system = platform.system()
    if system not in {"Linux", "Darwin"}:
        raise RuntimeError("This Unix-port build helper supports Linux or macOS only")
    patched = _apply_validated_patches(source, system)
    compiler = shutil.which("clang++" if system == "Darwin" else "g++")
    if compiler is None or shutil.which("make") is None:
        raise RuntimeError("A C++ compiler and make are required")
    flags = "-c -std=c++11 -O2 -Wall -DUNIX -Wno-deprecated"
    if system == "Darwin":
        # Upstream C++ uses long values in double initializer lists.  GCC's
        # existing build accepts them; Clang needs this diagnostic adjustment.
        flags += " -Wno-c++11-narrowing"
    _run(["make", "clean"], source / "src")
    build_log = source / "build.log"
    with build_log.open("w") as log:
        subprocess.run(["make", f"-j{jobs}", f"CC={compiler}", f"CFLAGS={flags}"],
                       cwd=source / "src", check=True, stdout=log, stderr=subprocess.STDOUT)
    executable = source / "src" / "TestFARSITE"
    patch = _run(["git", "diff", "--", "src/Farsite5.cpp"], source)
    (source / "portability.patch").write_text(patch)
    manifest = {
        "repository": REPOSITORY,
        "revision": REVISION,
        "model_version": "legacy public FARSITE Unix port (Farsite5 source)",
        "official_current_distribution": "FARSITE in FlamMap6, Windows 64 bit",
        "platform": platform.platform(),
        "compiler": compiler,
        "compiler_version": _run([compiler, "--version"]).strip(),
        "cflags": flags,
        "macos_backup_copy_shim": patched,
        "pointer_syntax_fixes": ["nonnull perimeter allocation check", "pointer null return"],
        "physical_model_changes": False,
        "portability_patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
        "executable": str(executable),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "build_log": str(build_log),
        "license": str(source / "LICENSE"),
    }
    (source / "build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return executable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "tmp" / "farsite_source")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--examples", action="store_true",
                        help="Also fetch the upstream flatland example input files")
    args = parser.parse_args()
    executable = build_engine(args.source_dir, jobs=args.jobs, examples=args.examples)
    print((executable.parent.parent / "build_manifest.json").read_text())


if __name__ == "__main__":
    main()
