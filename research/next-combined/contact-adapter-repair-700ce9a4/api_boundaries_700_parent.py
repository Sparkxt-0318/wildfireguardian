"""Independent repair checks using the retained original tiny fixtures."""
import hashlib
import importlib.util
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parent / "audit-1c"
for part in ("sipp-routing", "scenario-members", "synthetic-truth"):
    sys.path.insert(0, str(REPO / "experimental" / part / "src"))
spec = importlib.util.spec_from_file_location(
    "retained_contact_fixture",
    REPO / "experimental/sipp-routing/tests/test_known_footprint.py",
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
kf = fixture.kf
checks = []


def record(name, passed, observed):
    checks.append(dict(name=name, passed=bool(passed), observed=observed))


def plans(name, raw, graph, request, kwargs=None, arrival=None):
    for method in ("sipp", "sweep"):
        result = kf.plan_contact_route(
            graph, request, fixture.source(raw, **(kwargs or {})), method=method
        )
        good = result["status"] == kf.CHECKED
        if arrival is not None:
            good = good and result["arrival"] == arrival
        record(name + ":" + method, good,
               {key: result.get(key) for key in ("status", "arrival", "destination")})


def refused(name, raw, kwargs, reason):
    try:
        fixture.source(raw, **kwargs)
    except ValueError as error:
        record(name, reason in str(error), str(error))
    else:
        record(name, False, "constructor accepted")


raw, graph, request = fixture.fixture()
plans("all_known_original_positive", raw, graph, request, arrival=2)

raw, graph, request = fixture.fixture()
raw["source_burned_area"][2, 1] = 1
raw["heat__initial_active_burning_probability"][2, 1] = 1
raw["heat__initial_remaining_burning_duration_s"][2, 1] = 100
raw["trajectory_first_burn_hour"][:, 2, 1] = 0
plans("consistent_active_fire_positive", raw, graph, request)

raw, graph, request = fixture.fixture()
raw["heat__initial_active_burning_probability"][2, 1] = 1
raw["heat__initial_remaining_burning_duration_s"][2, 1] = 100
refused("original_contradictory_active_refuses", raw, {},
        "RAW_ACTIVE_OUTSIDE_KNOWN_BURNED")

raw, graph, request = fixture.fixture()
graph["nodes"][1]["x"] = 1.5
graph["nodes"].append(dict(id="c", x=2.5, y=.5, waitable=True))
graph["edges"] = [dict(id="ab", u="a", v="b", travel_ticks=1),
                  dict(id="ac", u="a", v="c", travel_ticks=2)]
request["destinations"] = [dict(node="b", dwell=1.5, open_intervals=[[0, 3600]]),
                           dict(node="c", dwell=0, open_intervals=[[0, 3600]])]
plans("integer_support_fractional_dwell_positive", raw, graph, request,
      dict(member_valid_until_s=[3, 3]), arrival=1)
refused("original_fractional_support_explicitly_refuses", raw,
        dict(member_valid_until_s=[Fraction(5, 2)] * 2), "whole-second")

raw, graph, request = fixture.fixture()
refused("original_nanosecond_source_refuses", raw,
        dict(cutoff_utc="2025-01-01T00:00:00.000000001Z"), "RFC3339")
plans("equivalent_utc_offset_positive", raw, graph, request,
      dict(cutoff_utc="2025-01-01T01:00:00+01:00"), arrival=2)

raw, graph, request = fixture.fixture()
request["as_of"] = "9999-01-01T00:00:00.000001Z"
kwargs = dict(cutoff_utc="9999-01-01T01:00:00.000001+01:00")
plans("far_year_exact_offset_positive", raw, graph, request, kwargs, arrival=2)
request["as_of"] = "9999-01-01T00:00:00.000002Z"
for method in ("sipp", "sweep"):
    result = kf.plan_contact_route(graph, request, fixture.source(raw, **kwargs), method=method)
    record("far_year_microsecond_mismatch_refuses:" + method,
           result["status"] != kf.CHECKED,
           {key: result.get(key) for key in ("status", "reason")})

raw, graph, request = fixture.fixture()
request["as_of"] = "2025-01-01T00:00:00.000000001Z"
for method in ("sipp", "sweep"):
    result = kf.plan_contact_route(graph, request, fixture.source(raw), method=method)
    record("nanosecond_request_refuses:" + method,
           result["status"] != kf.CHECKED,
           {key: result.get(key) for key in ("status", "reason")})

report = dict(
    head=subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip(),
    scope="Parent independent tiny repair controls; original fixtures reused, no native graph, study data or timed campaign.",
    original_failure_script_sha256=hashlib.sha256((HERE / "api_boundaries_fd8bf2e7.py").read_bytes()).hexdigest(),
    producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    checks=checks, count=len(checks), passed=sum(row["passed"] for row in checks),
)
(HERE / "api_boundaries_700_parent.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(dict(head=report["head"], checks=report["count"], passed=report["passed"])))
raise SystemExit(0 if report["passed"] == report["count"] else 1)
