"""Guards for the truck-crew replay (brief TRUCK_CREW_REPLAY, docs/truck_crew_replay.md).

Four properties the brief names, and they are the four that can be checked without
a crew, a fire or a browser:

1. **The artifact's counts re-derive from its own rows.** Every headline number the
   finals may quote is recomputed here from the per-trip records and must match. A
   summary that drifted from the rows it summarises is the failure this catches.
2. **Every trip's abort minute is `closing - margin`, and the rule is applied.** The
   abort rule is the only thing on the screen that tells a crew to turn round, so it
   is re-derived per trip rather than trusted, and a trip that arrives after it must
   be flagged aborted and must not be counted as reached.
3. **The page has no external asset.** It opens from `file://` in a hall with no
   network, or it is useless. Checked with the repository's own screen gate.
4. **The printed vehicle sheet is one A4 page.** Measured with headless Chrome when
   this machine has one, and SKIPPED with a reason when it does not: an unmeasurable
   page budget is reported as unmeasured, never as a pass.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

ARTIFACT = REPO / "data/processed/truck_crew_replay_yeongdeok.json"
PAGE = REPO / "web/truck_crew_replay.html"
TEMPLATE = REPO / "scripts/truck_crew_replay.template.html"
DOC = REPO / "docs/truck_crew_replay.md"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists() or not PAGE.exists(),
    reason="truck-crew replay not built (scripts/build_truck_crew_replay.py)")


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def _trips(run: dict) -> list[dict]:
    return [t for v in run["per_vehicle"] for t in v["trips"]]


# --- 1. the counts re-derive -------------------------------------------------

def test_every_headline_count_re_derives_from_the_trips_it_summarises(data):
    for key, run in data["runs"].items():
        trips = _trips(run)
        assert run["trips_ordered"] == len(trips), key
        assert run["aborted_by_rule"] == sum(1 for t in trips if t["aborted_by_rule"]), key
        assert run["reached_before_observed_closure"] == sum(
            1 for t in trips if t["reached_before_observed_closure"]), key
        assert run["not_reached"] == (
            run["trips_ordered"] - run["aborted_by_rule"]
            - run["reached_before_observed_closure"]), key
        assert run["buildings_behind_ordered_trips"] == sum(t["n_buildings"] for t in trips), key
        assert run["distinct_pickups_ordered"] == len({t["drive_node"] for t in trips}), key
        assert run["trips_with_an_inadmissible_ingress_leg_m0"] == sum(
            1 for t in trips if t["ingress"]["observed"]["class_m0"] == "inadmissible_all"), key
        for v in run["per_vehicle"]:
            assert v["n_trips"] == len(v["trips"]), (key, v["vehicle"])


def test_the_four_counts_partition_the_ordered_trips(data):
    """N = K + M + not-reached, for every fleet size, by construction and in fact."""
    for key, run in data["runs"].items():
        assert (run["aborted_by_rule"] + run["reached_before_observed_closure"]
                + run["not_reached"]) == run["trips_ordered"], key
        assert run["not_reached"] >= 0, key


def test_the_population_counts_re_derive_from_the_pickup_rows(data):
    p, pick = data["population"], data["pickups"]
    assert p["pickups"] == len(pick)
    assert p["buildings_behind_pickups"] == sum(r["n_buildings"] for r in pick)
    assert p["rescue_needing_walk_nodes"] == sum(r["n_walk_nodes"] for r in pick)
    assert p["walk_nodes_sharing_a_pickup"] == p["rescue_needing_walk_nodes"] - p["pickups"]
    # a pickup is a drive node, once (docs §1); a repeated one would make the
    # scheduler's per-home outcome ambiguous, which is why the rule exists
    assert len({r["drive_node"] for r in pick}) == len(pick)
    assert all(r["sources"] for r in pick)


def test_the_success_line_carries_the_measured_numbers_and_nothing_else(data):
    head = data["runs"]["k4"]
    line = data["success_line_ko"]
    for v in (head["trips_ordered"], head["reached_before_observed_closure"],
              head["aborted_by_rule"]):
        assert str(v) in line, (v, line)
    # every bare integer in the sentence is one of the three, the fleet size, or the date
    allowed = {str(head["trips_ordered"]), str(head["reached_before_observed_closure"]),
               str(head["aborted_by_rule"]), str(head["vehicles"]),
               "2025", "3", "25"}
    assert set(re.findall(r"\d+", line)) <= allowed, line


# --- 2. the abort rule -------------------------------------------------------

def test_every_trips_abort_minute_is_the_closing_minute_less_the_margin(data):
    margin = data["parameters"]["safety_margin_min"]
    for key, run in data["runs"].items():
        for t in _trips(run):
            closing = t["ingress"]["closing_min"]
            if closing is None:
                assert t["abort_min"] is None, (key, t["seq"])
                assert t["aborted_by_rule"] is False, (key, t["seq"])
                continue
            assert t["abort_min"] == pytest.approx(closing - margin, abs=0.011), (key, t["seq"])
            assert t["abort_min"] <= closing - margin + 0.011


def test_a_trip_that_arrives_after_its_abort_minute_is_aborted_and_never_counted_reached(data):
    for key, run in data["runs"].items():
        for t in _trips(run):
            late = t["abort_min"] is not None and t["eta_min"] > t["abort_min"]
            assert t["aborted_by_rule"] == late, (key, t["seq"], t["eta_min"], t["abort_min"])
            if t["aborted_by_rule"]:
                assert t["reached_before_observed_closure"] is False, (key, t["seq"])


def test_reached_means_the_observation_had_not_reached_the_pickup_cell(data):
    for key, run in data["runs"].items():
        for t in _trips(run):
            if t["aborted_by_rule"]:
                continue
            seen = t["pickup_observed_first_seen_min"]
            expected = seen is None or seen > t["eta_min"]
            assert t["reached_before_observed_closure"] == expected, (key, t["seq"])


def test_the_scheduler_deadline_was_respected_and_the_clock_bounds_arrivals(data):
    margin = data["parameters"]["safety_margin_min"]
    horizon = data["parameters"]["horizon_min"]
    for key, run in data["runs"].items():
        for t in _trips(run):
            assert t["eta_min"] + margin <= t["deadline_applied_min"] + 1e-6, (key, t["seq"])
            assert t["eta_min"] <= horizon, (key, t["seq"])


def test_a_fallback_corridor_is_from_a_different_depot_road_node(data):
    for key, run in data["runs"].items():
        for t in _trips(run):
            fb = t["depot_fallback"]
            if fb is None:
                continue
            assert fb["depot_drive_node"] != t["depot_primary"]["depot_drive_node"], (key, t["seq"])
            assert fb["reachable"] is True


# --- 3. the page is offline --------------------------------------------------

def test_the_page_has_no_external_asset():
    from check_screen_assets import check_dashes, check_dashes_in_scripts, check_offline

    text = PAGE.read_text(encoding="utf-8")
    findings = check_offline(text) + check_dashes(text) + check_dashes_in_scripts(text)
    assert not findings, "\n".join(f"[{f.gate}] line {f.line}: {f.detail}" for f in findings)


def test_the_payload_strings_the_page_displays_carry_no_banned_dash():
    """The gate's own recorded blind spot: payload strings written through a variable."""
    payload = json.loads(re.search(
        r'<script id="data" type="application/json">(.*?)</script>',
        PAGE.read_text(encoding="utf-8"), re.S).group(1))
    bad: list[str] = []

    def walk(v, path):
        if isinstance(v, str):
            if "—" in v or "–" in v:
                bad.append(f"{path}: {v[:80]}")
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v[:400]):
                walk(x, f"{path}[{i}]")

    walk(payload, "payload")
    assert not bad, bad


def test_the_page_is_the_template_with_the_payload_substituted():
    tpl = TEMPLATE.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    marker = "/*__" + "DATA" + "__*/"
    assert marker in tpl and marker not in page
    head, tail = tpl.split(marker, 1)
    assert page.startswith(head) and page.endswith(tail)


def test_the_rule_was_written_before_the_results():
    """§4 is appended by the run; the rule sections must precede it and be filled."""
    doc = DOC.read_text(encoding="utf-8")
    for heading in ("## 1.", "## 2.", "## 3.", "## 3b.", "## 4. Results"):
        assert heading in doc, heading
    assert doc.index("## 3b.") < doc.index("## 4. Results")
    assert "abort_min = closing" in doc.replace("`", "")
    assert "buildings are not households" in doc.lower() or "건물" in doc


# --- 4. the printed sheet is one page ----------------------------------------

def _chromium() -> str | None:
    from wildfireguardian.delivery.printable import find_chrome

    found = find_chrome()
    if found:
        return found
    # a Playwright-provisioned Chromium, which find_chrome does not look for
    for pat in ("/opt/pw-browsers/*/chrome-linux/chrome",
                "/opt/pw-browsers/*/chrome-linux/headless_shell"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def test_the_printed_vehicle_sheet_is_one_a4_page(data):
    from wildfireguardian.delivery.printable import MAX_PAGES, html_to_pdf, pdf_page_count

    chrome = _chromium()
    if chrome is None:
        pytest.skip("no headless Chrome/Chromium on this machine; the one-page print "
                    "budget is UNMEASURED here rather than passing by default")
    tmp = Path(tempfile.mkdtemp(prefix="wfg-tcr-print-"))
    env_path = os.environ.get("PATH", "")
    try:
        # html_to_pdf finds its engine through PATH, so the located binary is put
        # there under a name it looks for. Nothing in src/ is changed.
        (tmp / "chromium").symlink_to(chrome)
        os.environ["PATH"] = f"{tmp}{os.pathsep}{env_path}"
        # The sheet as it loads, and the sheet of the BUSIEST vehicle in any run,
        # which is the one with the most table rows and therefore the real budget.
        # The second is the shipped page plus one call to the page's own
        # WFG_SELECT hook, which is exactly what the two dropdowns do.
        busiest = max(((v["n_trips"], key, i)
                       for key, run in data["runs"].items()
                       for i, v in enumerate(run["per_vehicle"])))
        worst = tmp / "worst.html"
        worst.write_text(
            PAGE.read_text(encoding="utf-8").replace(
                "</body>",
                f'<script>WFG_SELECT("{busiest[1]}", {busiest[2]});</script></body>'),
            encoding="utf-8")
        for label, path in (("as it loads", PAGE), (f"busiest vehicle ({busiest[0]} trips)", worst)):
            pdf = tmp / (path.stem + ".pdf")
            res = html_to_pdf(path, pdf)
            if not res.get("ok"):
                pytest.skip(f"headless Chrome did not produce a PDF here: {res.get('reason')}")
            n = res.get("n_pages") or pdf_page_count(pdf)
            assert n is not None, f"{label}: PDF produced but its page count could not be read"
            assert n <= MAX_PAGES, (
                f"the printed vehicle sheet ({label}) is {n} pages; it is designed for "
                f"{MAX_PAGES}. A second page gets separated from the first and a crew "
                "acts on half a list.")
    finally:
        os.environ["PATH"] = env_path
        shutil.rmtree(tmp, ignore_errors=True)


def test_the_build_script_imports_rather_than_reimplements_the_pipeline():
    """The brief's one hard constraint on this build: no second copy of the router."""
    import ast

    path = REPO / "scripts/build_truck_crew_replay.py"
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {a.asname or a.name
                for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names}
    for name in ("schedule", "classify_route", "rescuer_route", "ingress_corridor",
                 "round_trip_margin", "node_survival_time", "corridor_survival_time",
                 "sample_corridor_points", "_immobile_homes", "build_scenario"):
        assert name in imported, f"{name} is not imported; the brief forbids a second copy"
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not (defined & imported), sorted(defined & imported)
