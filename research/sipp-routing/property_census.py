"""Census of the random-instance equivalence check: run SIPP and the brute-force lattice search on 10,000 instances drawn
from the same Hypothesis strategy as the test suite (derandomised, no database) and record how many instances have a
journey, how many are refusals, and how many blocked intervals actually changed the travel-only answer.

  python research/sipp-routing/property_census.py --out research/sipp-routing/data/property_census.json
"""
import argparse
import json
import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "sipp-routing" / "tests"))
sys.path.insert(0, str(REPO / "experimental" / "sipp-routing" / "src"))
from strategies import instances, rebuild, seeded_instance  # noqa: E402
from wfg_sipp import bruteforce, sipp as S  # noqa: E402

COUNTS = {"cases": 0, "agree": 0, "disagree": 0, "found": 0, "no_journey": 0, "fire_changed_answer": 0,
          "witness_legal": 0, "pieces_total": 0, "lattice_states_bound_total": 0}


def one(inst):
    bf = bruteforce.earliest_arrival(inst)
    r = S.solve(inst)
    got = r["arrival"] if r["status"] == "FOUND" else None
    COUNTS["cases"] += 1
    COUNTS["agree" if got == bf else "disagree"] += 1
    COUNTS["found" if got is not None else "no_journey"] += 1
    if got is not None and bruteforce.check_legs(inst, r["legs"], got):
        COUNTS["witness_legal"] += 1
    free = S.solve(rebuild(inst, edge_block={}, wait_block={}))
    if (free["arrival"] if free["status"] == "FOUND" else None) != got:
        COUNTS["fire_changed_answer"] += 1
    COUNTS["pieces_total"] += r["metrics"]["pieces"]
    COUNTS["lattice_states_bound_total"] += (inst.E + 1) * (inst.horizon - inst.departure + 1)


def run(n):
    for seed in range(n - n // 2):
        one(seeded_instance(seed))
    @settings(max_examples=n // 2, deadline=None, derandomize=True, database=None, suppress_health_check=list(HealthCheck))
    @given(instances())
    def census(inst):
        one(inst)
    census()
    return COUNTS


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--out", default=str(HERE / "data" / "property_census.json"))
    a = ap.parse_args()
    c = run(a.n)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(c, indent=1) + "\n")
    print(json.dumps(c))
