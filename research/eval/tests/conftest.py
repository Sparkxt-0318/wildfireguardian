"""Put ``research/eval`` on the path so the tests import the module under test.

There is no package ``__init__.py`` under ``research/eval`` on purpose: the
module is imported by modeling agents from a script directory, and a test that
needs a different import path from the one agents use is testing the wrong
thing.
"""

import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1]
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))
