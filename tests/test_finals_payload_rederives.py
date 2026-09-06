"""The judged screen's payload must be what the builder derives from the tree.

WFG-113. Every number a judge reads off `web/finals.html` lives on one line: the
embedded JSON payload that `scripts/build_finals.py` writes. Until this file,
nothing asserted that line had been produced by the builder at all.

WFG-109's independent reviewer proved the hole by running it rather than
reasoning about it: it changed `"n_entries": 326` to `999` on the payload line and
every named guard stayed green. `verify_numbers.py` never opens the screen;
`check_forbidden.py` reads it but limits its numeric rules to `.md`
(`docs/forbidden_check_scope.md` documents that exemption, and WFG-109 made the
payload line the single exempt line of the identity gate, so the exemption is
load-bearing); `test_finals_template_sync.py` exempts the same line by design.

So the check here is not another string comparison. It re-runs the builder into a
temporary path and compares the two payloads structurally. A value that no
longer follows from the committed artifacts fails, whether it drifted (the
registry grew and nobody re-ran `make finals`) or was typed in by hand.

**What is tolerated, and why.** Exactly the build-provenance keys:
`built_utc` (wall clock), `git` (the head at build time) and, in the integrity
block, `seconds` (gate wall time). The rest of the integrity block is not
compared here because it exists only under `--verify`, which re-runs three gates
and costs about 16 s of them; `test_the_integrity_panel_reports_the_builders_own_gate_list`
covers it against the builder's own `GATES` constant instead.

**When this goes red the screen is stale, not wrong.** The repair is two commands
and no decision:

    make finals              PYTHON=.auto/venv/bin/python
    make finals-bundle UPDATE=1 PYTHON=.auto/venv/bin/python

The second one carries the rebuilt screen into the 17-file release bundle, which
ships it. A lap that registers a number and does not re-run them will land here.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

FINALS = REPO / "web" / "finals.html"
BUILDER = REPO / "scripts" / "build_finals.py"

# The keys the builder cannot reproduce on a second run, by construction.
# `integrity` is compared by the second test rather than tolerated outright.
PROVENANCE_TOP = ("built_utc", "git")
PROVENANCE_GATE = ("seconds",)

REPAIR = ("re-run the builder:  make finals PYTHON=.auto/venv/bin/python  "
          "&&  make finals-bundle UPDATE=1 PYTHON=.auto/venv/bin/python")


def _stack_available() -> bool:
    """The builder needs the geospatial stack (docs/ENVIRONMENT.md)."""
    try:
        import networkx, numpy, pyproj, rasterio  # noqa: F401,E401
        from PIL import Image  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


pytestmark = [
    pytest.mark.skipif(not FINALS.exists(),
                       reason="web/finals.html not built (make finals)"),
    pytest.mark.skipif(not _stack_available(),
                       reason="geospatial stack unavailable (docs/ENVIRONMENT.md)"),
]


def _payload_of(html: str) -> dict:
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>',
                  html, re.S)
    assert m, "embedded data payload not found"
    return json.loads(m.group(1))


@pytest.fixture(scope="module")
def rebuilt(tmp_path_factory) -> dict:
    """The payload the builder derives from this tree, right now.

    Built without ``--verify``: the three gates it would run add about 16 s and
    `scripts/auto/gates.py` runs them anyway.
    """
    out = tmp_path_factory.mktemp("finals") / "rebuilt.html"
    proc = subprocess.run(
        [sys.executable, str(BUILDER), "--out", str(out)],
        cwd=REPO, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        pytest.fail("scripts/build_finals.py failed to re-derive the payload:\n"
                    + (proc.stderr or proc.stdout)[-3000:])
    return _payload_of(out.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def shipped() -> dict:
    return _payload_of(FINALS.read_text(encoding="utf-8"))


def _differences(shipped, rebuilt, path="") -> list[str]:
    """Every JSON path at which the two payloads disagree, provenance aside."""
    out: list[str] = []
    if isinstance(shipped, dict) and isinstance(rebuilt, dict):
        for key in sorted(set(shipped) | set(rebuilt)):
            here = f"{path}.{key}" if path else key
            if not path and key in PROVENANCE_TOP:
                continue
            if not path and key == "integrity":
                continue  # covered by the integrity test below
            if key in PROVENANCE_GATE and path.startswith("integrity.gates"):
                continue
            if key not in shipped:
                out.append(f"{here}: missing from the screen")
            elif key not in rebuilt:
                out.append(f"{here}: on the screen, not derived any more")
            else:
                out += _differences(shipped[key], rebuilt[key], here)
    elif isinstance(shipped, list) and isinstance(rebuilt, list):
        if len(shipped) != len(rebuilt):
            out.append(f"{path}: {len(shipped)} items on the screen, "
                       f"{len(rebuilt)} derived")
        else:
            for i, (a, b) in enumerate(zip(shipped, rebuilt)):
                out += _differences(a, b, f"{path}[{i}]")
    elif shipped != rebuilt:
        out.append(f"{path}: screen={shipped!r} derived={rebuilt!r}")
    return out


def test_every_value_the_screen_displays_is_what_the_builder_derives_today(
        shipped, rebuilt):
    diffs = _differences(shipped, rebuilt)
    assert not diffs, (
        f"{len(diffs)} value(s) on the judged screen no longer follow from the "
        f"committed artifacts. The screen is stale, not wrong: " + REPAIR
        + "\n  " + "\n  ".join(diffs[:25])
        + ("\n  ... and more" if len(diffs) > 25 else ""))


def test_the_registry_card_counts_the_registry_it_ships_beside(shipped):
    """The live instance WFG-113 was filed for, without a rebuild.

    The general test above subsumes this one, but only by re-running the whole
    builder. This reads `docs/NUMBERS.json` through the builder's own
    `registry_slice()` and costs milliseconds, so the two counts a judge reads
    off the 검증 레지스트리 card are checked even when the rebuild is skipped.

    It calls `registry_slice()` rather than re-implementing its predicate: a
    copied rule goes on asserting the old definition after the builder's moves
    (MEMO 2026-09-06, and this file's own third test).
    """
    import build_finals  # noqa: PLC0415

    derived = build_finals.registry_slice()
    card = shipped["registry"]
    for field in ("n_entries", "n_reproducible"):
        assert card[field] == derived[field], (
            f"the 검증 레지스트리 card says {field} = {card[field]} and "
            f"docs/NUMBERS.json derives {derived[field]}. " + REPAIR)


def test_the_integrity_panel_reports_the_builders_own_gate_list(shipped):
    """The one part of the payload a plain rebuild cannot reproduce.

    Its expectation is read off `build_finals.GATES` rather than typed here: a
    check written against strings its own author picked confirms the author, not
    the artifact (MEMO 2026-09-06).
    """
    import build_finals  # noqa: PLC0415

    integrity = shipped["integrity"]
    assert integrity["verified"] is True, (
        "the SYSTEM INTEGRITY panel says the screen was built without --verify; "
        "`make finals` passes it. " + REPAIR)

    expected = [name for name, _argv in build_finals.GATES]
    assert [g["name"] for g in integrity["gates"]] == expected, (
        "the panel names gates the builder no longer runs, or omits ones it "
        "does. " + REPAIR)

    for gate in integrity["gates"]:
        assert gate["ok"] is True, (
            f"the screen ships a recorded FAIL for {gate['name']}. " + REPAIR)
        assert gate["line"].strip(), (
            f"{gate['name']} recorded no output line. " + REPAIR)
        assert isinstance(gate["seconds"], (int, float)), (
            f"{gate['name']} recorded no wall time. " + REPAIR)
