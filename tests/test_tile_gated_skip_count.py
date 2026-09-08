"""The judge-facing count of tile-gated skips is derived from the tree, not typed.

Why this file exists (WFG-178). The lap that closed WFG-139 wrote 「여섯 개」 onto
three judge-facing surfaces as the honest remainder of its own fix, and added the
seventh tile-gated test in the same diff. `grep -rn '여섯 개' tests/` returned
nothing, so no gate was ever going to catch it, and the card reached paper and the
student's mouth. Correcting the integer alone would reinstall the same failure at
the same cost, which is why the correction ships with this file.

What is derived here, by reading the test sources rather than by running them, so
the answer does not depend on whether the tile happens to be cached on this
machine:

* **tile-gated** — tests whose ``skipif`` predicate reaches
  ``data/raw/dem/srtm/N36E129.hgt``, the tile a clean clone does not have.
* **SRTM-named but not tile-gated** — tests whose ``skipif`` says SRTM while
  gating on some other artifact. These exist (WFG-180) and they matter here
  because ``docs/auto/JUDGE_QA.md`` Q40 sends a judge to ``pytest -rs``, where
  both kinds print side by side.

⚠ **Blind spot, stated rather than implied.** The detector reads each decorator's
source text plus the body of any module-level helper the decorator names. A
predicate that reaches the tile through a helper imported from another module, or
through a fixture, is invisible to it. That is the same class of gap
``tests/conftest.py`` names for the socket guard, and it is recorded rather than
hidden. ``test_the_detector_is_graded_on_planted_source`` grades the detector on
source it is handed, so a rewrite that silently stops detecting anything fails
here instead of passing vacuously (WFG-156).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"

#: The tile a clean clone does not carry. Spelled once.
TILE = "N36E129"


def _tile_gated_in_source(src: str, label: str = "<planted>") -> tuple[list[str], list[str]]:
    """Split the skip-gated tests in ``src`` into (tile-gated, SRTM-named-only).

    A decorator counts as tile-gated when its own source names the tile, or when
    it calls a module-level helper whose body names the tile. It counts as
    SRTM-named-only when it says SRTM but reaches neither.
    """
    tree = ast.parse(src)

    tile_helpers = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and TILE in (ast.get_source_segment(src, node) or "")
    }

    tile_gated: list[str] = []
    srtm_named_only: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for dec in node.decorator_list:
            seg = ast.get_source_segment(src, dec) or ""
            if "skipif" not in seg:
                continue
            reaches_tile = TILE in seg or any(h in seg for h in tile_helpers)
            if reaches_tile:
                tile_gated.append(f"{label}::{node.name}")
                break
            if "srtm" in seg.lower():
                srtm_named_only.append(f"{label}::{node.name}")
                break
    return tile_gated, srtm_named_only


def _scan_tree() -> tuple[list[str], list[str]]:
    tile_gated: list[str] = []
    srtm_named_only: list[str] = []
    for path in sorted(TESTS.glob("test_*.py")):
        gated, named = _tile_gated_in_source(path.read_text(encoding="utf-8"), path.name)
        tile_gated.extend(gated)
        srtm_named_only.extend(named)
    return tile_gated, srtm_named_only


#: (path, regex with one capturing group, which derived set the number must equal).
#: Every match of every regex is checked, and a regex that matches nothing fails:
#: a reworded sentence must not silently drop out of this gate.
SURFACES: tuple[tuple[str, str, str], ...] = (
    # Q28's 없는 것 block.
    ("docs/auto/JUDGE_QA.md", r"지형 타일[^\n]{0,40}있어야 도는 테스트 \*\*(\d+)개\*\*", "tile"),
    # Q40, the card that sends a judge to `pytest -rs`.
    ("docs/auto/JUDGE_QA.md", r"그 타일에 걸린 테스트 \*\*(\d+)개\*\*", "tile"),
    ("docs/auto/JUDGE_QA.md", r"타일에 걸린 것은 \*\*(\d+)개\*\*", "tile"),
    ("docs/auto/JUDGE_QA.md", r"나머지 \*\*(\d+)개\*\*는 이름만 SRTM", "srtm_named_only"),
    ("docs/auto/JUDGE_QA.md", r"「SRTM」이 들어간 스킵 줄이 \*\*(\d+)개\*\*", "both"),
    ("docs/clean_clone_gates.md", r"The \*\*(\d+)\*\* tests that `skipif` on the cached tile", "tile"),
    ("docs/clean_clone_gates.md", r"\*\*(\d+)\*\* more skips say SRTM", "srtm_named_only"),
)


def test_the_detector_is_graded_on_planted_source() -> None:
    """A detector that finds nothing passes every count trivially. Grade it first."""
    planted = (
        "import pytest\n"
        "\n"
        "def _cached() -> bool:\n"
        "    return (ROOT / 'data' / 'raw' / 'dem' / 'srtm' / 'N36E129.hgt').exists()\n"
        "\n"
        "@pytest.mark.skipif(not _cached(), reason='tile absent')\n"
        "def test_reaches_the_tile_through_a_helper() -> None: ...\n"
        "\n"
        "@pytest.mark.skipif(not X, reason='SRTM N36E129.hgt not cached')\n"
        "def test_names_the_tile_in_its_reason() -> None: ...\n"
        "\n"
        "@pytest.mark.skipif(not DEM.exists(), reason='SRTM DEM absent')\n"
        "def test_says_srtm_but_gates_on_something_else() -> None: ...\n"
        "\n"
        "@pytest.mark.skipif(not OTHER, reason='unrelated')\n"
        "def test_is_neither() -> None: ...\n"
        "\n"
        "def test_is_not_skipped_at_all() -> None: ...\n"
    )
    tile_gated, srtm_named_only = _tile_gated_in_source(planted)
    assert [t.split("::")[1] for t in tile_gated] == [
        "test_reaches_the_tile_through_a_helper",
        "test_names_the_tile_in_its_reason",
    ]
    assert [t.split("::")[1] for t in srtm_named_only] == [
        "test_says_srtm_but_gates_on_something_else"
    ]


def test_the_tile_gated_set_is_not_empty() -> None:
    """The clean-clone remainder is a real set; if it ever empties, the prose must change."""
    tile_gated, _ = _scan_tree()
    assert tile_gated, (
        "no test in tests/ gates on the SRTM tile any more. That is good news, and it "
        "makes every judge-facing sentence about the remainder wrong: rewrite them "
        "before deleting this assertion."
    )


@pytest.mark.parametrize(("rel", "pattern", "which"), SURFACES)
def test_every_judge_facing_count_matches_the_tree(rel: str, pattern: str, which: str) -> None:
    tile_gated, srtm_named_only = _scan_tree()
    expected = {
        "tile": len(tile_gated),
        "srtm_named_only": len(srtm_named_only),
        "both": len(tile_gated) + len(srtm_named_only),
    }[which]

    text = (REPO / rel).read_text(encoding="utf-8")
    found = re.findall(pattern, text)
    assert found, (
        f"{rel}: nothing matches {pattern!r} any more. The sentence this gate binds was "
        "reworded or removed; re-anchor it here rather than deleting the row."
    )
    for stated in found:
        assert int(stated) == expected, (
            f"{rel} says {stated} where the tree has {expected} "
            f"({which}). The tree is right; the prose is stale. "
            f"tile-gated: {tile_gated}; SRTM-named-only: {srtm_named_only}"
        )
