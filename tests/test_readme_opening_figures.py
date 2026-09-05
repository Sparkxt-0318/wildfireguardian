"""The README's opening figures are bound to the registry, and interim tallies are refused.

WFG-049. The first paragraph a judge reads was rewritten wrongly twice with every gate
green (116,000 ha, then 45,157 ha presented as final: critic #4 F16/F17/F18), because
its figures had no artifact and no key. They now live in
``data/processed/external/fire_2025_scale.json`` with agency, as-of date, scope, status
and URL, are registered as ``fire2025_*`` in ``docs/NUMBERS.json``, and
``scripts/check_readme_figures.py`` (in ``make verify``) binds both paragraphs to them.

This file pins three things: each final figure in both paragraphs is the registry's
value (the detection-card pattern); the gate script itself is green on the tree; and
the gate turns red on the two rewrites that got through before, reproduced verbatim.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
GATE = REPO / "scripts" / "check_readme_figures.py"
ARTIFACT = REPO / "data" / "processed" / "external" / "fire_2025_scale.json"
NUMBERS = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))["numbers"]

# (Korean literal, English literal, key, value) — the paragraph in each language must
# state the literal, and the key must hold the value.
CLAIMS = [
    ("99,289 ha", "99,289 ha", "fire2025_chain_area_ha", 99289),
    ("149시간", "149 hours", "fire2025_chain_hours_to_containment", 149),
    ("26명", "killed **26", "fire2025_chain_deaths", 26),
    ("영덕 10명", "10 of them in 영덕", "fire2025_chain_deaths_yeongdeok", 10),
    ("3,819동", "3,819 homes", "fire2025_chain_homes_damaged", 3819),
    ("2,246세대", "2,246 households", "fire2025_chain_displaced_households", 2246),
    ("3,587명", "3,587", "fire2025_chain_displaced_people", 3587),
    ("104,788 ha", "104,788 ha", "fire2025_nationwide_area_ha", 104788),
    ("347건", "347 fires", "fire2025_nationwide_fires", 347),
]


@pytest.fixture(scope="module")
def paragraphs() -> tuple[str, str]:
    text = README.read_text(encoding="utf-8")
    ko = text.split("**보호 대상**", 1)[1].split("**대회**", 1)[0]
    en = text.split("**Motivating event**", 1)[1].split("**Target venue**", 1)[0]
    return ko.replace("\n", " "), en.replace("\n", " ")


@pytest.mark.parametrize("ko,en,key,value", CLAIMS, ids=[c[2] for c in CLAIMS])
def test_each_final_figure_is_the_registry_value_in_both_languages(paragraphs, ko, en, key, value):
    assert key in NUMBERS, f"{key} is not registered"
    e = NUMBERS[key]
    assert e["value"] == value, f"{key} moved to {e['value']}"
    assert e["figure_status"] == "final"
    for field in ("agency", "as_of", "scope", "source_url"):
        assert e.get(field), f"{key} lacks {field}"
    k, n = paragraphs
    assert ko in k, f"Korean paragraph does not state {ko} for {key}"
    assert en in n, f"English paragraph does not state {en} for {key}"


def test_the_registry_agrees_with_the_artifact_it_reads():
    figs = json.loads(ARTIFACT.read_text(encoding="utf-8"))["figures"]
    for key, e in NUMBERS.items():
        if key.startswith("fire2025_") and e["check"]["kind"] == "json_path":
            fig = e["json_path"].split(".")[1]
            assert e["value"] == figs[fig]["value"], key
            assert e["source_url"] == figs[fig]["url"], key


def test_interim_tallies_are_registered_as_interim_so_the_gate_can_name_them():
    assert NUMBERS["fire2025_interim_chain_area_ha_20250327"]["figure_status"] == "interim"
    assert NUMBERS["fire2025_interim_chain_area_ha_20250327"]["value"] == 45157
    assert NUMBERS["fire2025_interim_homes_destroyed_20250326"]["figure_status"] == "interim"
    assert NUMBERS["fire2025_yeongnam_homes_damaged_secondary"]["figure_status"] == "secondary"


def _gate(readme: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GATE), "--readme", str(readme)],
                          cwd=REPO, capture_output=True, text=True, timeout=60)


def test_the_gate_is_green_on_the_tree():
    r = _gate(README)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_gate_refuses_the_12b8ac7_rewrite_interim_area_as_final(tmp_path):
    """45,157 ha typed in place of 99,289 ha, exactly what 12b8ac7 did (F16)."""
    bad = README.read_text(encoding="utf-8").replace("99,289 ha", "45,157 ha")
    p = tmp_path / "README.md"
    p.write_text(bad, encoding="utf-8")
    r = _gate(p)
    assert r.returncode == 1
    assert "45,157" in r.stdout and "interim" in r.stdout
    assert "fire2025_chain_area_ha" in r.stdout


def test_the_gate_refuses_the_original_116000_ha_and_the_27_deaths(tmp_path):
    bad = README.read_text(encoding="utf-8").replace("99,289 ha", "약 116,000 ha").replace("**26명**", "**27명**")
    p = tmp_path / "README.md"
    p.write_text(bad, encoding="utf-8")
    r = _gate(p)
    assert r.returncode == 1
    assert "116,000" in r.stdout and "27명" in r.stdout


def test_the_gate_refuses_the_different_event_note(tmp_path):
    """12b8ac7 also told the reader the nationwide figure belongs to a different event (F17)."""
    bad = README.read_text(encoding="utf-8").replace("**347건**은 이 산불 하나가 아니라", "**347건**은 다른 사건이며")
    p = tmp_path / "README.md"
    p.write_text(bad, encoding="utf-8")
    r = _gate(p)
    assert r.returncode == 1 and "다른 사건" in r.stdout
