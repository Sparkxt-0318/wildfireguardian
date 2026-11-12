"""S-D9 multi-fire, multi-horizon probabilistic scoring harness.

    from sd9bench import load, score
    result = score(load(paths))
"""

from .entries import Entries, load
from .score import score

__all__ = ["Entries", "load", "score"]
