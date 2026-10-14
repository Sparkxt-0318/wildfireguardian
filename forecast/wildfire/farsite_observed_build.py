"""Build an isolated pinned FARSITE copy with exact minute-bearing clocks.

The public legacy port parses military HHMM input but assigns it to its hour
field without assigning the separate minute field. Its elapsed-time arithmetic
therefore interprets, for example, 0802 as 8.02 hours instead of 8 h 2 min.
This builder splits HHMM into the port's hour and minute fields. It preserves
the previously evaluated engine and records all changes in a separate copy.
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

from .farsite_build import (
    REPOSITORY, REVISION, ROOT, _macos_copy_patch, _pointer_syntax_patch, _run,
)


def _build_clock_probe(source: Path, compiler: str, system: str) -> tuple[Path, str]:
    """Link an independent reader to the actual native objects, then exercise it.

    With landscape/input paths it inspects the clock loaded by LoadInputsFile.
    With no arguments it checks the native elapsed-time implementation against
    the 08:02-to-next-day-02:14 example. It does not run fire spread.
    """
    cpp = source / "observed_clock_probe.cpp"
    cpp.write_text(r'''#include "Farsite5.h"
#include <cstdio>
bool cancelRequest = false;
int nFarsites = 0;
int main(int argc, char** argv) {
    Farsite5 engine;
    if (argc == 3) {
        if (engine.LoadLandscapeFile(argv[1]) != 1) return 2;
        if (engine.LoadInputsFile(argv[2]) != 1) return 3;
    } else if (argc == 1) {
        engine.SetStartMonth(8); engine.SetStartDay(22);
        engine.SetStartHour(800); engine.SetStartMin(2);
        engine.SetEndMonth(8); engine.SetEndDay(23);
        engine.SetEndHour(200); engine.SetEndMin(14);
        engine.SetStartDate(engine.GetJulianDays(8) + 22);
        engine.SetSimulationDuration(engine.ConvertActualTimeToSimtime(
            engine.GetEndMonth(), engine.GetEndDay(), engine.GetEndHour(),
            engine.GetEndMin(), false));
    } else return 4;
    std::printf("{\"start_hhmm\":%ld,\"end_hhmm\":%ld,\"duration_minutes\":%.12g}\n",
        engine.GetStartHour() + engine.GetStartMin(),
        engine.GetEndHour() + engine.GetEndMin(), engine.GetSimulationDuration());
    return argc == 1 && engine.GetSimulationDuration() != 1092.0 ? 5 : 0;
}
''')
    executable = source / "observed_clock_probe"
    objects = sorted(path for path in (source / "src").glob("*.o") if path.name != "TestFARSITE.o")
    args = [compiler, "-std=c++11", "-O2", "-DUNIX", "-I", str(source / "src")]
    if system == "Darwin":
        args.append("-Wno-c++11-narrowing")
    args.extend([str(cpp), *map(str, objects), "-o", str(executable)])
    _run(args, source)
    return executable, _run([str(executable)], source).strip()


def _clock_assignments_patch(source: Path) -> None:
    """Split the two parsed HHMM values, preserving newline organization."""
    path = source / "src" / "Farsite5.cpp"
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for endpoint in ("Start", "End"):
        field = f"icf.i_Farsite{endpoint}Hour"
        space = "  " if endpoint == "Start" else "    "
        original = f"Set{endpoint}Hour{space}({field});"
        replacement = (
            f"Set{endpoint}Hour{space}(({field} / 100) * 100);\n"
            f"   Set{endpoint}Min   ({field} % 100);"
        )
        if text.count(replacement) == 1 and original not in text:
            continue
        if text.count(original) != 1:
            raise RuntimeError(f"Pinned FARSITE {endpoint.lower()} clock assignment was not found exactly once")
        text = text.replace(original, replacement)
    newline = "\r\n" if b"\r\n" in raw else "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def _apply_validated_observed_patches(source: Path, system: str) -> None:
    """Accept only pristine, portability-patched, or fully documented bytes."""
    modified = set(_run(["git", "diff", "--name-only", "HEAD"], source).splitlines())
    if modified - {"src/Farsite5.cpp"}:
        raise RuntimeError(f"Observed FARSITE copy has unrelated tracked edits: {sorted(modified)}")
    pristine = subprocess.run(
        ["git", "show", "HEAD:src/Farsite5.cpp"], cwd=source,
        check=True, stdout=subprocess.PIPE,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="wildfire-farsite-observed-patch-") as temp:
        expected_root = Path(temp)
        (expected_root / "src").mkdir()
        expected_file = expected_root / "src" / "Farsite5.cpp"
        expected_file.write_bytes(pristine)
        if system == "Darwin":
            _macos_copy_patch(expected_root)
        _pointer_syntax_patch(expected_root)
        portable = expected_file.read_bytes()
        _clock_assignments_patch(expected_root)
        expected = expected_file.read_bytes()
    actual = source / "src" / "Farsite5.cpp"
    if actual.read_bytes() not in {pristine, portable, expected}:
        raise RuntimeError("Observed FARSITE copy differs from the pinned revision and documented patches")
    actual.write_bytes(expected)


def build_observed_engine(
    source_dir: Path | str | None = None,
    *, original_source_dir: Path | str | None = None, jobs: int = 4,
) -> Path:
    """Build an independently recorded copy without changing the old engine."""
    if isinstance(jobs, bool) or not isinstance(jobs, int) or jobs < 1:
        raise ValueError("jobs must be a positive integer")
    original = Path(original_source_dir or ROOT / "tmp" / "farsite_source").resolve()
    source = Path(source_dir or ROOT / "tmp" / "farsite_observed_source").resolve()
    if source == original or original in source.parents or source in original.parents:
        raise ValueError("Observed source must be a separate directory from the original source")
    if not (original / ".git").is_dir():
        raise RuntimeError("An existing pinned FARSITE source checkout is required; build the original engine first")
    if _run(["git", "rev-parse", "HEAD"], original).strip() != REVISION:
        raise RuntimeError("Original FARSITE source is not the pinned revision")
    original_cpp = original / "src" / "Farsite5.cpp"
    old_binary = original / "src" / "TestFARSITE"
    original_source_hash = hashlib.sha256(original_cpp.read_bytes()).hexdigest()
    old_binary_hash = hashlib.sha256(old_binary.read_bytes()).hexdigest() if old_binary.is_file() else None
    if not source.exists():
        shutil.copytree(original, source, ignore=shutil.ignore_patterns("*.o", "TestFARSITE"))
    if not (source / ".git").is_dir():
        raise RuntimeError("Refusing to overwrite a non-Git observed source directory")
    if _run(["git", "rev-parse", "HEAD"], source).strip() != REVISION:
        raise RuntimeError("Observed FARSITE copy is not the pinned revision")
    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        raise RuntimeError("This build supports Linux or macOS only")
    _apply_validated_observed_patches(source, system)
    compiler = shutil.which("clang++" if system == "Darwin" else "g++")
    if compiler is None or shutil.which("make") is None:
        raise RuntimeError("A C++ compiler and make are required")
    flags = "-c -std=c++11 -O2 -Wall -DUNIX -Wno-deprecated"
    if system == "Darwin":
        flags += " -Wno-c++11-narrowing"
    _run(["make", "clean"], source / "src")
    log_path = source / "observed_build.log"
    with log_path.open("w") as log:
        subprocess.run(
            ["make", f"-j{jobs}", f"CC={compiler}", f"CFLAGS={flags}"],
            cwd=source / "src", check=True, stdout=log, stderr=subprocess.STDOUT,
        )
    executable = source / "src" / "TestFARSITE"
    probe, clock_check = _build_clock_probe(source, compiler, system)
    patch = _run(["git", "diff", "--", "src/Farsite5.cpp"], source)
    patch_path = source / "observed_clock_and_portability.patch"
    patch_path.write_text(patch)
    if hashlib.sha256(original_cpp.read_bytes()).hexdigest() != original_source_hash:
        raise RuntimeError("Original FARSITE source changed while building its isolated copy")
    if old_binary_hash is not None and hashlib.sha256(old_binary.read_bytes()).hexdigest() != old_binary_hash:
        raise RuntimeError("Original FARSITE executable changed while building its isolated copy")
    manifest = dict(
        repository=REPOSITORY, revision=REVISION,
        model_version="legacy public FARSITE Unix port (Farsite5 source)",
        platform=platform.platform(), compiler=compiler,
        compiler_version=_run([compiler, "--version"]).strip(), cflags=flags,
        original_source_dir=str(original), original_source_sha256=original_source_hash,
        original_executable_sha256=old_binary_hash, original_engine_preserved=True,
        source_dir=str(source), source_sha256=hashlib.sha256((source / "src" / "Farsite5.cpp").read_bytes()).hexdigest(),
        macos_backup_copy_shim=system == "Darwin", pointer_syntax_fixes=True,
        clock_assignment_correction="split start/end parsed HHMM into hour*100 and separate minute fields",
        clock_input_resolution="one minute; no rounding of survey times",
        expected_clock_example=dict(start="08:02", end_next_day="02:14", duration_minutes=1092),
        native_clock_probe=str(probe), native_clock_probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
        native_clock_example_result=clock_check,
        spread_physics_changes=False, clock_loading_changes=True,
        patch=str(patch_path), patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),
        executable=str(executable), executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        build_log=str(log_path), license=str(source / "LICENSE"),
    )
    (source / "observed_build_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return executable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "tmp" / "farsite_observed_source")
    parser.add_argument("--original-source-dir", type=Path, default=ROOT / "tmp" / "farsite_source")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    executable = build_observed_engine(args.source_dir, original_source_dir=args.original_source_dir, jobs=args.jobs)
    print((executable.parent.parent / "observed_build_manifest.json").read_text())


if __name__ == "__main__":
    main()
