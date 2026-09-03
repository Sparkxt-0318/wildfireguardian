"""The commit you push must be the commit the gates read.

Twice in the loop's first three laps a lap ran `gates.py --mode full`, committed
another two hundred lines, and pushed under an **ALL GREEN** headline that named a
superseded commit (critic #3, findings F13 and F14; MEMO 2026-09-03). The gate run
was honest and the branch was red anyway, because nothing compared the record with
the tree.

`gates.py --assert-head` is that comparison and this file is its test. It also
covers `report.py`'s half: when the record is stale, the report says so in the
prose a judge and the critic actually read, instead of printing two short hashes in
different sections and leaving the reader to notice they differ.

The gates themselves are not run here — `--assert-head` runs nothing by design, so
these tests are pure and fast. `AUTO` and `git` are patched so the assertions are
about the logic, not about whatever state this sandbox's own `.auto/` happens to be
in when the suite runs.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_wfg_{name}", REPO / "scripts" / "auto" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


gates = _load("gates")
report = _load("report")

GREEN_FULL = {
    "written_at_utc": "2026-09-03T20:52:29Z",
    "mode": "full",
    "git_head": "abc1234",
    "git_branch": "auto/dev",
    "passed": True,
    "pytest_summary": "1159 passed, 56 skipped",
    "steps": [{"name": "verify", "passed": True, "hard": True, "seconds": 14.3, "tail": ["=== make verify: PASSED ==="]}],
}


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Point gates.AUTO at a temp dir and drive `git` from the test."""
    monkeypatch.setattr(gates, "AUTO", tmp_path)
    state = {"head": "abc1234", "dirty": ""}

    def fake_git(*args: str) -> str:
        if args[:2] == ("rev-parse", "--short"):
            return state["head"]
        if args[:1] == ("status",):
            return state["dirty"]
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(gates, "git", fake_git)

    def write(record: dict | None) -> None:
        if record is not None:
            (tmp_path / "gates.json").write_text(json.dumps(record))

    return state, write


def test_a_full_green_run_at_this_exact_head_is_the_only_thing_that_passes(sandbox):
    _, write = sandbox
    write(GREEN_FULL)
    assert gates.assert_head("full") == 0


def test_no_record_at_all_fails_rather_than_defaulting_to_permissive(sandbox, capsys):
    # the fixture writes nothing unless the test asks it to, so there is no gates.json
    assert gates.assert_head("full") == 1
    assert "no .auto/gates.json" in capsys.readouterr().out


def test_an_unreadable_record_fails_instead_of_raising(sandbox, tmp_path):
    (tmp_path / "gates.json").write_text("{not json")
    assert gates.assert_head("full") == 1


def test_the_f14_failure_the_gates_read_an_older_commit_than_head(sandbox, capsys):
    state, write = sandbox
    write(GREEN_FULL)
    state["head"] = "8d1decf"  # two commits and 200-plus lines later, as on 2026-09-03
    assert gates.assert_head("full") == 1
    out = capsys.readouterr().out
    assert "the gates read 'abc1234'; HEAD is '8d1decf'" in out
    assert "do not push" in out


def test_a_dirty_tree_fails_because_head_is_not_what_was_tested(sandbox, capsys):
    state, write = sandbox
    write(GREEN_FULL)
    state["dirty"] = " M docs/auto/BACKLOG.md\n?? scripts/new_thing.py"
    assert gates.assert_head("full") == 1
    assert "2 uncommitted change(s)" in capsys.readouterr().out


def test_a_quick_run_does_not_satisfy_the_full_gate_a_push_requires(sandbox, capsys):
    _, write = sandbox
    write({**GREEN_FULL, "mode": "quick"})
    assert gates.assert_head("full") == 1
    assert "was mode 'quick', not 'full'" in capsys.readouterr().out
    # ...but a lap that only claims a row may assert the quick run it actually did
    assert gates.assert_head("quick") == 0


def test_a_red_run_fails_even_when_it_names_the_right_head(sandbox):
    _, write = sandbox
    write({**GREEN_FULL, "passed": False})
    assert gates.assert_head("full") == 1


def test_every_reason_is_reported_at_once_so_one_rerun_shows_them_all(sandbox, capsys):
    state, write = sandbox
    write({**GREEN_FULL, "mode": "quick", "passed": False})
    state["head"] = "deadbee"
    state["dirty"] = " M x"
    assert gates.assert_head("full") == 1
    out = capsys.readouterr().out
    assert out.count("\n  - ") == 4


def test_assert_head_runs_no_gate(sandbox, monkeypatch):
    """The check must be cheap enough to sit immediately before every push."""
    _, write = sandbox
    write(GREEN_FULL)
    monkeypatch.setattr(gates, "run", lambda *a, **k: pytest.fail("--assert-head ran a gate"))
    monkeypatch.setattr(sys, "argv", ["gates.py", "--assert-head"])
    assert gates.main() == 0


# --- report.py's half: a stale record has to say so in the report's own prose ---

def test_the_report_names_the_head_its_gate_table_certifies():
    block = report.gate_block_for(GREEN_FULL, "abc1234")
    assert "**ALL GREEN**" in block and "current at `abc1234`" in block
    assert "stale" not in block


def test_a_report_written_after_later_commits_says_all_green_is_stale():
    block = report.gate_block_for(GREEN_FULL, "8d1decf")
    assert "stale: the gates read `abc1234`, HEAD is `8d1decf`" in block
    assert "does not certify the pushed tree" in block
    assert "--assert-head" in block


def test_no_gate_record_is_still_reported_honestly():
    assert report.gate_block_for(None, "abc1234") == "(gates not run this lap)"


def test_report_py_checks_its_own_prose_and_says_no_by_exit_code(tmp_path, monkeypatch):
    """WFG-046 (a): a report that trips the prose gates must not be committed.

    The file is written before it is checked on purpose — the lap needs it to
    repair — so the only thing that says "not yet" is the exit code.
    """
    calls = []

    class Result:
        def __init__(self, rc):
            self.returncode, self.stdout, self.stderr = rc, "FAILED tests/test_rescue_lineage_ssot.py", ""

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return Result(0 if "check-forbidden" in " ".join(cmd) else 1)

    monkeypatch.setattr(report.subprocess, "run", fake_run)
    out = report.REPO / "docs" / "auto" / "reports" / "x.md"
    assert report.prose_gates(out) == 1
    assert len(calls) == 2, "both prose gates run even after the first one fails"

    monkeypatch.setattr(report.subprocess, "run", lambda cmd, **kw: Result(0))
    assert report.prose_gates(out) == 0


def test_the_report_prose_gate_is_not_the_full_suite():
    """Three minutes in the report step would be worked around (WFG-046 constraint)."""
    joined = [" ".join(cmd) for cmd, _ in report.prose_gate_commands()]
    assert any("check-forbidden" in c for c in joined)
    assert any("tests/test_rescue_lineage_ssot.py" in c for c in joined)
    assert not any(c.rstrip().endswith("pytest") or " pytest -q$" in c for c in joined)


def test_the_charter_step_that_precedes_a_push_names_the_command():
    """CHARTER §4 step 8 is what a fresh lap follows; the check has to be in it."""
    charter = (REPO / "docs" / "auto" / "CHARTER.md").read_text(encoding="utf-8")
    assert "gates.py --assert-head" in charter
