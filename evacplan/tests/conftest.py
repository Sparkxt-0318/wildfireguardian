"""Keep hypothesis' storage (example database, constants cache) inside evacplan/ (git-ignored),
whatever directory pytest runs from."""
import os
from pathlib import Path

os.environ.setdefault("HYPOTHESIS_STORAGE_DIRECTORY", str(Path(__file__).resolve().parents[1] / ".hypothesis"))
try:
    from hypothesis.configuration import set_hypothesis_home_dir
except ImportError:  # pragma: no cover - older hypothesis reads the variable itself
    pass
else:
    set_hypothesis_home_dir(os.environ["HYPOTHESIS_STORAGE_DIRECTORY"])
