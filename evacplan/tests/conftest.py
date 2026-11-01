"""Keep hypothesis' storage (example database, constants cache) inside evacplan/ (git-ignored),
whatever directory pytest runs from; and refuse to run the suite beside a timed benchmark (program rule 6)."""
import os
from pathlib import Path

import pytest

os.environ.setdefault("HYPOTHESIS_STORAGE_DIRECTORY", str(Path(__file__).resolve().parents[1] / ".hypothesis"))
try:
    from hypothesis.configuration import set_hypothesis_home_dir
except ImportError:  # pragma: no cover - older hypothesis reads the variable itself
    pass
else:
    set_hypothesis_home_dir(os.environ["HYPOTHESIS_STORAGE_DIRECTORY"])

UNLOCKED = "EVACPLAN_TESTS_UNLOCKED"
HOW = "python program/benchlock.py --label evacplan-tests -- python -m pytest evacplan/tests"


def bench_lock_verdict(env=os.environ) -> str | None:
    """Why this test session may not run now, or None. The suite runs the solvers (B2, B3, E1, E4) with short
    budgets, so it must not overlap a timed run (program rule 6). It runs under the shared bench lock
    (``benchlock.py -- pytest``: a parent process holds it). Otherwise it is refused while anyone else holds the lock
    (a timed run, or another suite, is in progress), and, unless ``EVACPLAN_TESTS_UNLOCKED=1`` (a light selection
    while nothing is queued), also when the lock is free. Added after the batch-1 review found agents' pytest runs
    beside B2's timed repeats (finding harness D1)."""
    from evacplan.harness import load_benchlock, lock_held_by_ancestor
    try:
        bl = load_benchlock()
    except FileNotFoundError:                          # not a checkout of this repo: no shared lock to respect
        return None
    if lock_held_by_ancestor(bl):
        return None
    held = bl.holder()
    if held:
        return f"the bench lock is held by: {held}. Wait for it, or queue behind it with: {HOW}"
    if env.get(UNLOCKED) == "1":
        return None
    return (f"this pytest does not run under the shared bench lock. Run the suite with: {HOW} "
            f"(or set {UNLOCKED}=1 for a light selection while no timed run is queued)")


def pytest_sessionstart(session):
    why = bench_lock_verdict()
    if why is not None:
        pytest.exit(f"evacplan tests refused (program rule 6): {why}", returncode=75)
