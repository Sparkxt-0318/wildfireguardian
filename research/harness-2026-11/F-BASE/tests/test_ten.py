"""F-BASE-TEN (third-party BFS on the explicit time-expanded network) against the exact solver and brute force."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fbase import instance_text, parse_instance, replay, solve_brute, solve_exact  # noqa: E402
from fbase_ten import parse, solve_ten  # noqa: E402
from test_fbase import random_instance  # noqa: E402


def test_ten_equals_exact_and_brute_and_witness_replays():
    rng = random.Random(7)
    routes = 0
    for _ in range(1500):
        inst = random_instance(rng)
        text = instance_text(inst)
        claim, T, legs, _ = solve_ten(parse(text))
        assert (claim, T) == solve_brute(inst) == solve_exact(inst)[:2], text
        if claim == "ROUTE":
            routes += 1
            wit = [(k, x, a, b) for k, x, a, b in legs]
            assert replay(parse_instance(text), wit, T), text
    assert routes > 200
