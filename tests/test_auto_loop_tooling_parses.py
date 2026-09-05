"""The loop's own tooling must at least import on the interpreter that runs it.

Found by WFG-019's lap, 2026-09-03.

THE FAILURE THIS PREVENTS
-------------------------
``scripts/auto/report.py`` and ``scripts/auto/dashboard.py`` were both
**unparseable on Python 3.11** — the interpreter in the cloud sandbox and on the
``auto-gates`` runner. Python 3.11 rejects a backslash anywhere inside an
f-string *expression*; PEP 701 relaxed that in 3.12, so both files parsed fine on
the machine they were written on and raised ``SyntaxError`` at import time
everywhere else, before a single line of their logic ran.

It survived a push because **no gate reads these files as code.** ``make verify``
greps them as text, ``pytest`` never collected them, and
``check_declared_deps.py`` tolerates a file it cannot parse. They are the one code
path in this repository with nothing standing behind them — and they are the path
that writes the report, which is the loop's only output the author ever sees. A
lap that cannot write its report is a failed lap.

⚠ WHAT THIS DOES NOT CHECK. Not that the scripts are correct, and not that they
run — only that this interpreter can compile them. That is the floor, not the
ceiling: a run of ``report.py`` against a fixture summary would be the real test,
and it does not exist yet. Compiling is what catches the version-skew class,
which is the one that actually bit.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
AUTO = REPO / "scripts" / "auto"


def _scripts() -> list[Path]:
    return sorted(AUTO.glob("*.py"))


def test_the_auto_directory_still_holds_the_loop_tooling():
    """A guard on the guard: an empty glob would make every check below vacuous."""
    names = {p.name for p in _scripts()}
    assert {"report.py", "dashboard.py", "gates.py"} <= names, sorted(names)


@pytest.mark.parametrize("path", _scripts(), ids=lambda p: p.name)
def test_every_auto_script_compiles_on_this_interpreter(path: Path):
    source = path.read_text(encoding="utf-8")
    try:
        ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover - the failure being prevented
        pytest.fail(
            f"{path.relative_to(REPO)} does not parse on this interpreter: "
            f"{exc.msg} (line {exc.lineno}). The loop imports this file to write "
            "its report, so a syntax error here silently costs a whole lap. "
            "Backslashes inside f-string expressions are the known cause — they "
            "need Python 3.12+ (PEP 701); hoist the value into a variable."
        )
