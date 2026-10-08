"""Compatibility and release-boundary checks for the reorganized package."""

import contextlib
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from routing.checks import PACKAGE_ROOT, verify_release_hashes
from routing.cli import build_parser, main, read_fixture, solve_fixture


def semantic(value):
    value = deepcopy(value)
    if isinstance(value, dict):
        for key in ["wall_s", "peak_rss_mb", "end_to_end_s"]:
            value.pop(key, None)
        return {key: semantic(child) for key, child in value.items()}
    if isinstance(value, list):
        return [semantic(child) for child in value]
    return value


class CommandLineCompatibilityTests(unittest.TestCase):
    def invoke(self, entry, command, *, prepare=False):
        args = [sys.executable, "-B", *entry, command]
        if prepare:
            args.append("--prepare-graph")
        if command == "replay":
            args += ["--input", str(PACKAGE_ROOT / "fixtures/continuity_replay.json")]
        env = dict(os.environ, PYTHONPATH=str(PACKAGE_ROOT))
        with tempfile.TemporaryDirectory() as outside:
            done = subprocess.run(
                args,
                cwd=outside,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
        return json.loads(done.stdout)

    def test_legacy_and_module_solve_outside_working_directory(self):
        legacy = self.invoke([str(PACKAGE_ROOT / "run.py")], "solve")
        module = self.invoke(["-m", "routing"], "solve")
        self.assertEqual(semantic(legacy), semantic(module))

    def test_prepared_solve_preserves_raw_semantics(self):
        raw = self.invoke(["-m", "routing"], "solve")
        prepared = self.invoke(["-m", "routing"], "solve", prepare=True)
        self.assertEqual(semantic(raw), semantic(prepared))

    def test_legacy_and_module_replay_with_preparation(self):
        legacy = self.invoke([str(PACKAGE_ROOT / "run.py")], "replay")
        module = self.invoke(["-m", "routing"], "replay", prepare=True)
        self.assertEqual(legacy, module)

    def test_main_outputs_existing_json_facade(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["solve"]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(semantic(result), semantic(solve_fixture(read_fixture(None))))

    def test_invalid_command_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(
            SystemExit
        ) as error:
            build_parser().parse_args(["unsupported"])
        self.assertEqual(error.exception.code, 2)

    def test_import_has_no_console_side_effects(self):
        done = subprocess.run(
            [sys.executable, "-B", "-c", "import routing.cli"],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(done.stdout, "")
        self.assertEqual(done.stderr, "")

    def test_release_verification_rejects_modified_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "verification").mkdir()
            (root / "input.json").write_text("changed")
            (root / "verification/REFRACTOR_FREEZE.json").write_text(
                json.dumps({"hashes": {"input.json": "0" * 64}})
            )
            with self.assertRaisesRegex(
                RuntimeError, "release hash mismatch input.json"
            ):
                verify_release_hashes(root)


if __name__ == "__main__":
    unittest.main()
