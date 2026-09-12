"""Every repository path this lap's judge-facing prose points at must resolve.

WFG-026's independent reviewer blocked the first version of `docs/related_work.md`
for pointing at **four files that do not exist** — `docs/model_card.md`,
`docs/routing.md`, `docs/rescue_dispatch.md` and `docs/conformal.md`, seven
present-tense assertions in all. The page's whole argument is 「we do not compare
accuracy here because the measurements and their limits live over there」, so a dead
「over there」 is not a typo: it is the load-bearing half of the refusal, and CHARTER
§3.5 forbids a citation the reader cannot open.

⚠ **The reviewer also established that no gate would have caught it.** `make verify`,
`check_forbidden`, `check_withdrawn_claims` and the registry suite were all green over
the four dead paths, because nothing in `scripts/` checks that a backticked repository
path exists.

**Why this test is narrow rather than repository-wide.** Measured at this commit: 68
distinct dead paths across 50 tracked `.md` files, and most are legitimate — backlog
rows and research proposals whose 「done when:」 names a file that does not exist *yet*,
plus the vendored `.claude/skills/` documents. A repository-wide gate therefore needs a
designed allowlist, which is **WFG-157** and is infra work that CHARTER §14b holds. What
does not need an allowlist is the set of documents a judge actually reads, where a
promised file is a broken promise today. That set is `FILES` below; a lap that adds a
judge-facing document adds it here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Judge-facing prose written by the loop, where every named path must resolve NOW.
#: Not a general list of documents a judge reads: `JUDGE_QA.md` and `BOOTH_SETUP.md`
#: deliberately name artifacts that a later lap creates, and sweeping them in would
#: recreate the allowlist problem this test exists to avoid.
FILES = (
    "docs/related_work.md",
    "docs/auto/finals/RELATED_WORK_PANEL.md",
)

#: A backticked repository path: a known top-level directory, then a path, then a
#: real extension. Anchoring on the directory prefix is what keeps prose like
#: `pages_per_source` or `--check-only` out of the match.
PATH_RX = re.compile(
    r"`((?:docs|scripts|tests|data|paper|web|delivery|outputs|config|release)"
    r"/[A-Za-z0-9_./-]+\.(?:md|py|json|yaml|yml|html|bib|csv|pdf))`"
)

#: Paths these documents name in order to say they are DEAD. Each is quoted inside the
#: correction note that records the reviewer's block, so it must not resolve; asserting
#: that keeps the note honest if someone later creates the file.
DELIBERATELY_ABSENT = {
    "docs/model_card.md",
    "docs/routing.md",
    "docs/rescue_dispatch.md",
    "docs/conformal.md",
}

#: ⚠ The exemption above is licensed PER LINE, not per file. The first version of this
#: test exempted the four names anywhere in the document, and its own grading probe
#: caught that: re-introducing `docs/rescue_dispatch.md` as a LIVE claim mid-page left
#: the test green. That is the same vacuity WFG-156 removed one file over -- an
#: exemption written for a record that silently also licenses a live assertion. A line
#: quoting a dead path as a record must say so.
RECORD_PRAGMA = "<!-- dead-path-ok -->"


def _exists_exact(path: Path) -> bool:
    """Case-exact existence. macOS's default filesystem is case-insensitive, so
    ``(ROOT / "docs/model_card.md").exists()`` is True there because
    ``docs/MODEL_CARD.md`` is tracked — and the dead-path record went red on the
    author's laptop for a file that does not exist (2026-09-12). Linux CI never saw it.
    """
    try:
        return path.name in {q.name for q in path.parent.iterdir()}
    except FileNotFoundError:
        return False


def _unlicensed_occurrences(text: str) -> list[tuple[int, str]]:
    """Every (line number, path) whose line does NOT declare itself a record.

    ⚠ Occurrence-level, not name-level. Two earlier versions of this helper returned a
    set of licensed NAMES and the caller subtracted it from the whole file, which meant
    one licensed record line exempted that name everywhere -- so re-introducing
    `docs/rescue_dispatch.md` as a live claim mid-page stayed green. Both versions were
    caught by the same grading probe, which is the argument for running the probe rather
    than reading the code: the second bug is invisible unless you re-run the first test.
    """
    out: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        if RECORD_PRAGMA in line:
            continue
        out.extend((n, m) for m in PATH_RX.findall(line))
    return out


def _licensed_dead(text: str) -> set[str]:
    """Dead paths quoted on a line that declares itself a record (for the twin test)."""
    out: set[str] = set()
    for line in text.splitlines():
        if RECORD_PRAGMA in line:
            out |= set(PATH_RX.findall(line)) & DELIBERATELY_ABSENT
    return out


@pytest.mark.parametrize("rel", FILES)
def test_every_repository_path_this_page_names_resolves(rel: str) -> None:
    """Graded red by pointing the page at `docs/model_card.md`, which is the exact
    defect the reviewer found: it then fails naming that path and nothing else."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert PATH_RX.findall(text), (
        f"{rel}: no repository path matched, so this test is vacuous")
    missing = sorted(
        {f"{p} (line {n})" for n, p in _unlicensed_occurrences(text)
         if not _exists_exact(ROOT / p)})
    assert not missing, (
        f"{rel} names repository paths that do not exist: {missing}\n"
        "This page is read by a judge and its argument is that the measurements live "
        "in the files it names. A path that does not resolve is a fabricated citation "
        "(CHARTER §3.5). Point it at a file that exists AND carries the claim -- the "
        "reviewer's finding was that the nearest-named file was superseded, so a "
        f"mechanical rename is not enough. To quote a dead path AS A RECORD, put "
        f"{RECORD_PRAGMA} on its line."
    )


@pytest.mark.parametrize("rel", FILES)
def test_the_paths_named_as_dead_are_still_dead(rel: str) -> None:
    """The correction note says four paths do not exist. If one is ever created, the
    note becomes false and has to be reworded rather than left standing."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    quoted = _licensed_dead(text)
    now_real = sorted(p for p in quoted if _exists_exact(ROOT / p))
    assert not now_real, (
        f"{rel} records {now_real} as paths that do not exist, and they now do. "
        "Reword the correction note: it is a record of a withdrawn error, and a "
        "record that has quietly become false is worse than no record."
    )
