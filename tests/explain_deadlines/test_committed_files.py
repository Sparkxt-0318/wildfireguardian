"""The committed explanation files alone (planner/public/data/explanations), without the routing inputs: the replay
totals that README section 5 states. The tests that recompute anything from the inputs are in test_real_data.py.
"""
import json
from pathlib import Path

from tools.explain_deadlines.cli import compact

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "planner" / "public" / "data" / "explanations"
INDEX = json.loads((REPO / "planner" / "cache" / "INDEX.json").read_text())


def test_replay_totals_over_the_six_files():
    """README section 5: 7,771 recorded checked routes replayed flame-free; 507 travel-only routes whose 2,028 per-member
    contact flags equal the API's full-policy assessment (10 of them with contact in some member); nothing failed."""
    assert len(INDEX) == 6
    tot = {"checked": 0, "contact_free": 0, "travel": 0, "matches": 0, "member_flags": 0, "with_contact": 0, "failed": 0}
    for e in INDEX:
        path = OUT / ("%s__%s.json" % (e["region_id"], compact(e["input_time"])))
        v = json.loads(path.read_text())["summary"]["validation"]
        rc, to = v["replay_checked_routes"], v["replay_travel_only"]
        tot["checked"] += rc["routes"]
        tot["contact_free"] += rc["contact_free"]
        tot["travel"] += to["routes"]
        tot["matches"] += to["matches"]
        tot["member_flags"] += to["member_flags"]
        tot["with_contact"] += to["with_contact"]
        tot["failed"] += rc["failed"] + to["failed"]
    assert tot == {"checked": 7771, "contact_free": 7771, "travel": 507, "matches": 507, "member_flags": 2028,
                   "with_contact": 10, "failed": 0}
