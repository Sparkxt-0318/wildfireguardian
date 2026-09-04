"""WFG-062 — the registry of withdrawn claims, and the gate that drives off it.

WHAT THIS ROW WAS FILED ON, in one sentence: *「a registry of withdrawn CLAIMS (id, banned
spellings, the artifact that withdrew it, the pragma token) that any document can be
checked against, so a fifth document asserting the ordering tomorrow is caught」*.

THE DEFECT IT CLOSES IS COVERAGE, NOT SENSITIVITY, AND SAYING SO IS THE POINT.
``tests/test_detection_ordering_is_not_claimed.py`` holds four claim families and five
hand-written guard lists.  Their union is **11 files**.  There are **988** tracked ``.md``
and ``.html`` files in this repository at the commit that added this test.  Every escape
this loop has actually paid for was a file nobody had listed:

* WFG-063 — ``docs/SESSION19_REPORT.md``, 「a session report nobody had listed」, still
  carrying the rank table and the primacy sentence unannotated;
* WFG-070 — ``docs/auto/research/RESEARCH_BRIEF_2026-09-03.md`` and
  ``sweeps_2026-09-03/R3_science_gaps.md``, plus ``R7_rubric_gap.md``, which the row that
  went looking did not know about.

So the registry inverts the default: **every** tracked document in scope, minus one
exception class whose every member carries a written reason.  Adding a claim to
``docs/auto/withdrawn_claims.json`` gates it across 915 files at once.

WHAT IT DOES NOT DO — read this before quoting any number about it at a booth:

* It reads **spellings**.  Its sensitivity to a *rewording* of a withdrawn claim is
  **identical to the families it draws from**, because they are the same patterns, and
  ``test_the_registry_has_not_drifted_from_the_hand_rolled_families`` below is what keeps
  them the same.  The externally measured sensitivity of those patterns stands unchanged, on three sets
  none of whose authors wrote the patterns: critic #9's twenty primacy sentences scored
  ``primacy_violations`` **0/20** and ``priority_violations`` **2/20** (BACKLOG WFG-062,
  critic #9 F47); the 20260904T0855Z lap's reviewer wrote twenty more and nineteen escaped
  ``primacy_violations`` (**1/20**), of which the screen's negation rule caught **8/20**;
  WFG-070's reviewer scored the English structural rule **9/18**.
  **Nothing in this file improves those numbers and no test here claims a new one.**
* It does not absorb the two **structural** rules (``priority_violations``,
  ``english_ordering_violations``).  Those reconstruct sentences from wrapped markdown
  blocks per language and cannot be expressed as a registry row; folding them in is a
  later row, not this one.
* Its coverage number counts files READ, not claims CAUGHT, and the two are not the same:
  915 gated files are **652** generated ``outputs/**`` dispatch sheets, **105** vendored
  ``.claude/skills/**`` documents and **158** hand-written project documents.  The honest
  pair to quote is **11 → 158** for prose a person writes, and 915 for what is scanned.
  (The reviewer of the lap that wrote this made that distinction; it is kept in its words.)
* Widening scope has a measured cost, paid once here: ``docs/finals_screen_v2.md:75``
  says 「사람 신고를 일차로 **끌어올리지 않습니다**」 — an honest negated sentence that the
  ``신고 일차`` spelling matches.  The structural rule reads the negation and passes it; the
  spelling rule cannot.  It is licensed by pragma, and that is the mechanism, not a
  workaround: one false positive in 915 files is the price of the coverage.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "docs" / "auto" / "withdrawn_claims.json"
CHECKER = REPO / "scripts" / "check_withdrawn_claims.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checker = _load("check_withdrawn_claims", CHECKER)
families = _load(
    "detection_ordering", REPO / "tests" / "test_detection_ordering_is_not_claimed.py"
)

REGISTRY = checker.load_registry()
CLAIMS = REGISTRY["claims"]
SPELLINGS = [(c["id"], s) for c in CLAIMS for s in c["spellings"]]

#: The union of every hand-written guard list in the older file. These 11 paths are what
#: coverage looked like before this row.
HAND_ROLLED = (
    set(families.GUARDED)
    | set(families.PRIMACY_GUARDED)
    | set(families.PRIORITY_GUARDED)
    | set(families.EN_GUARDED)
    | set(families.MUST_STATE_THE_PROVENANCE)
)

REQUIRED_CLAIM_FIELDS = ("id", "title", "claim", "withdrawn_by", "artifact",
                         "say_instead", "spellings")


# ---------------------------------------------------------------------------
# the registry is well formed
# ---------------------------------------------------------------------------

def test_the_registry_parses_and_declares_its_version():
    assert REGISTRY["version"] == 1
    assert CLAIMS, "an empty registry gates nothing"


@pytest.mark.parametrize("claim", CLAIMS, ids=[c["id"] for c in CLAIMS])
def test_every_claim_carries_the_five_fields_the_row_named(claim: dict):
    """id, banned spellings, the artifact that withdrew it, the pragma token — WFG-062.

    `withdrawn_by` and `artifact` are the two halves of 「the artifact that withdrew it」:
    the decision, and the file a reader can open. `say_instead` is not in the row's list
    and is required anyway, because a gate that only forbids teaches the next author
    nothing and gets routed around.
    """
    for field in REQUIRED_CLAIM_FIELDS:
        assert claim.get(field), f"{claim.get('id')} is missing `{field}`"
    assert re.fullmatch(r"WC-\d{3}", claim["id"]), claim["id"]


def test_claim_ids_are_unique():
    ids = [c["id"] for c in CLAIMS]
    assert len(ids) == len(set(ids)), f"duplicate claim id in the registry: {ids}"


@pytest.mark.parametrize("claim_id,spelling", SPELLINGS,
                         ids=[f"{cid}:{s['token']}" for cid, s in SPELLINGS])
def test_every_spelling_compiles_and_says_why(claim_id: str, spelling: dict):
    for field in ("pattern", "token", "why"):
        assert spelling.get(field), f"{claim_id}: spelling missing `{field}`"
    re.compile(spelling["pattern"])
    assert len(spelling["why"]) > 20, (
        f"{claim_id} · {spelling['token']}: `why` is the sentence the next author reads "
        f"when the gate stops them; one word is not one"
    )


def test_a_token_names_exactly_one_claim():
    """A pragma licenses a token, so a token shared by two claims is a silent hole.

    `scripts/check_forbidden.py`'s per-token discipline exists for this: a pragma added
    for one claim shape must not license another.
    """
    owner: dict[str, str] = {}
    for claim_id, s in SPELLINGS:
        prev = owner.setdefault(s["token"], claim_id)
        assert prev == claim_id, (
            f"token {s['token']!r} is used by both {prev} and {claim_id}; a pragma for "
            f"one would silently license the other"
        )


# ---------------------------------------------------------------------------
# the scope model
# ---------------------------------------------------------------------------

def test_every_record_path_carries_a_reason():
    """The exception class is the whole risk in this design, so it is written, not implied."""
    for entry in REGISTRY["scope"]["record_prefixes"]:
        assert entry.get("path"), entry
        assert len(entry.get("why", "")) > 20, (
            f"{entry['path']} is exempt from every claim in this repository and the file "
            f"does not say why. That is how the 11-file guard lists happened."
        )


def test_no_record_path_is_also_a_guarded_document():
    """A path cannot be both 「a judge reads this」 and 「this is only a record」."""
    for entry in REGISTRY["scope"]["record_prefixes"]:
        path = entry["path"]
        clash = {g for g in HAND_ROLLED if g == path or (path.endswith("/") and g.startswith(path))}
        assert not clash, (
            f"record path {path!r} exempts {sorted(clash)}, which "
            f"tests/test_detection_ordering_is_not_claimed.py guards as judge-facing"
        )


def test_every_hand_rolled_guarded_file_is_also_gated_by_the_registry():
    """The registry may not cover LESS than the lists it generalises. The regression test."""
    gated = set(checker.gated_files(REGISTRY))
    tracked = set(checker.tracked_files(REGISTRY))
    for rel in sorted(HAND_ROLLED):
        if rel not in tracked:
            continue  # a generated file such as web/finals.html may be untracked in a clone
        assert rel in gated, f"{rel} is guarded by hand but exempted by the registry"


@pytest.mark.parametrize(
    "rel",
    [
        "docs/SESSION19_REPORT.md",          # the file WFG-063 found the claim in
        "docs/auto/research/RESEARCH_BRIEF_2026-09-03.md",  # the file WFG-070 found it in
        "docs/finals_screen_v2.md",
        "docs/detection_floor.md",
        "paper/manuscript.md",
        "README.md",
    ],
)
def test_the_surfaces_that_have_actually_carried_a_withdrawn_claim_are_gated(rel: str):
    assert rel in set(checker.gated_files(REGISTRY)), f"{rel} is not gated"


def test_a_document_nobody_has_listed_is_gated_by_construction():
    """WFG-062's sentence, made mechanical: 「so a fifth document … tomorrow is caught」.

    No such file exists, which is exactly why this is a test of the classifier rather
    than of the tree: a path that is not in the record class is gated the moment it is
    created, with no list to edit.
    """
    for rel in (
        "docs/a_document_no_guard_list_names.md",
        "docs/auto/finals/A_NEW_BOOTH_CARD.md",
        "web/a_new_screen.html",
        "paper/appendix_written_tomorrow.md",
    ):
        assert not checker.is_record(rel, REGISTRY), f"{rel} would be exempt"


def test_the_record_class_matches_exactly_and_not_by_prefix():
    """`docs/auto/MEMO.md` must not exempt `docs/auto/MEMO_APPENDIX.md`."""
    assert checker.is_record("docs/auto/MEMO.md", REGISTRY)
    assert not checker.is_record("docs/auto/MEMO_APPENDIX.md", REGISTRY)
    assert checker.is_record("docs/auto/reports/2026-09-04T2119Z-dev.md", REGISTRY)
    assert not checker.is_record("docs/auto/JUDGE_QA.md", REGISTRY)


# ---------------------------------------------------------------------------
# SSOT — the registry cannot fall behind the families it absorbs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "family_name",
    ["BANNED", "BANNED_PRIMACY", "BANNED_EN_SPELLINGS"],
)
def test_the_registry_has_not_drifted_from_the_hand_rolled_families(family_name: str):
    """Every spelling in the older file is in the registry, byte for byte, and vice versa.

    This is what makes 「absorbs the per-row hand-rolled gates」 true without deleting them
    (CHARTER §3 rule 7). The older file keeps its four families and its long docstrings,
    which are the argument; the registry is where the strings live, and a pattern widened
    in one place and not the other fails here rather than in a judge's hands.
    """
    in_file = {(p, t) for p, t, _w in getattr(families, family_name)}
    in_registry = {(s["pattern"], s["token"]) for _cid, s in SPELLINGS}
    missing = in_file - in_registry
    assert not missing, (
        f"{family_name} holds patterns the registry does not:\n"
        + "\n".join(f"  {t}: {p}" for p, t in sorted(missing))
        + "\n\nAdd them to docs/auto/withdrawn_claims.json — that file is the source of "
          "truth for withdrawn spellings, and this file is where the two are reconciled."
    )


def test_the_registry_holds_nothing_the_families_do_not():
    """The other direction: a spelling added only to the registry is fine, but must be
    deliberate, so it is listed here by name rather than passing silently."""
    in_files = set()
    for family_name in ("BANNED", "BANNED_PRIMACY", "BANNED_EN_SPELLINGS"):
        in_files |= {(p, t) for p, t, _w in getattr(families, family_name)}
    #: Registered by the independent reviewer of dev lap 20260904T2119Z, which found the
    #: spelling live at docs/SESSION19_REPORT.md:229 and :293 — three lines from a line
    #: this row had just licensed. It is here rather than in the older file because it was
    #: found IN THE TREE by someone who had not written the patterns; a spelling the
    #: pattern's author invents and then grades with its own sentence is leakage.
    reviewer_found = {(r"기준이?\s*(?:「\s*)?신고\s*시각", "기준 시각은 신고")}
    extra = {(s["pattern"], s["token"]) for _cid, s in SPELLINGS} - in_files - reviewer_found
    assert extra == set(), (
        "the registry has grown past the families it absorbed. That is allowed, and when "
        "you do it, add the new spelling to this test's expected set and say in "
        "docs/withdrawn_claims.md which claim it belongs to:\n"
        + "\n".join(f"  {t}: {p}" for p, t in sorted(extra))
    )


# ---------------------------------------------------------------------------
# the load-bearing test
# ---------------------------------------------------------------------------

def test_no_gated_document_carries_an_unlicensed_withdrawn_claim():
    """The gate. 915 files, three claims, every hit licensed by its own token or absent."""
    hits = checker.scan_repo(REGISTRY)
    assert not hits, (
        "a withdrawn claim is asserted in a document with no `forbidden-ok:` licence:\n"
        + "\n".join(
            f"  {rel}:{h['line']}  [{h['claim']} · {h['token']}]  {h['text'][:110]}"
            for rel, found in sorted(hits.items())
            for h in found
        )
        + f"\n\nWhat each claim was withdrawn on, and what to say instead, is in "
          f"{REGISTRY_PATH.relative_to(REPO)}."
    )


def test_the_script_agrees_with_the_test_and_exits_zero():
    """The gate a lap runs by hand (`make check-withdrawn-claims`) is the gate pytest runs."""
    # `sys.executable`, never a bare `python`: MEMO 2026-09-04 — a test that shells out
    # must not read ambient configuration, and PATH is ambient. A blank runner has no
    # guarantee that `python` is the interpreter running this suite.
    proc = subprocess.run(
        [sys.executable, str(CHECKER)], cwd=REPO, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASSED" in proc.stdout


# ---------------------------------------------------------------------------
# both directions — the bar `scripts/check_forbidden.py` sets for a claim rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("claim_id,spelling", SPELLINGS,
                         ids=[f"{cid}:{s['token']}" for cid, s in SPELLINGS])
def test_each_registered_spelling_is_caught_in_a_file_no_list_names(claim_id, spelling):
    """The positive direction, on the dimension this row actually moves.

    The sentence is not one I wrote: each is a line lifted from the withdrawn text or
    from the registry's own `why`, and the *pattern* is the shipped pattern. What is
    being measured here is not whether the pattern is clever — it is not, and critic #9's
    2/20 stands — but that a document **outside every guard list** is read at all.
    """
    probe = _probe_sentence(spelling["pattern"])
    hits = checker.scan_text(probe, REGISTRY)
    assert any(h["token"] == spelling["token"] for h in hits), (
        f"{claim_id} · {spelling['token']}: the registry did not catch\n  {probe}"
    )


@pytest.mark.parametrize("claim_id,spelling", SPELLINGS,
                         ids=[f"{cid}:{s['token']}" for cid, s in SPELLINGS])
def test_a_pragma_naming_the_token_licenses_it_and_nothing_else(claim_id, spelling):
    """The negative direction, and the per-token discipline in one test."""
    probe = _probe_sentence(spelling["pattern"])
    licensed = f"{probe} <!-- forbidden-ok: {spelling['token']} -->"
    assert not [h for h in checker.scan_text(licensed, REGISTRY)
                if h["token"] == spelling["token"]], (
        f"{claim_id}: an explicit pragma did not license its own token"
    )
    wrong = f"{probe} <!-- forbidden-ok: a-token-for-some-other-claim -->"
    assert any(h["token"] == spelling["token"] for h in checker.scan_text(wrong, REGISTRY)), (
        f"{claim_id}: a pragma naming a different token licensed this one"
    )


def test_the_pragma_may_sit_on_the_line_above():
    """Matching `scripts/check_forbidden.py`: a caveat is written above what it caveats."""
    text = "<!-- forbidden-ok: 신고보다 -->\n위성은 신고보다 늦게 도착했습니다.\n"
    assert not [h for h in checker.scan_text(text, REGISTRY) if h["token"] == "신고보다"]


def test_a_pragma_two_lines_above_does_not_reach():
    text = "<!-- forbidden-ok: 신고보다 -->\n\n위성은 신고보다 늦게 도착했습니다.\n"
    assert [h for h in checker.scan_text(text, REGISTRY) if h["token"] == "신고보다"]


# ---------------------------------------------------------------------------
# the coverage number this row publishes
# ---------------------------------------------------------------------------

def test_the_coverage_this_row_bought_is_recorded_and_re_derived():
    """The one number this row is allowed to claim, re-derived rather than restated.

    Before: the union of five hand-written guard lists. After: every tracked document in
    scope minus the declared record class. Coverage is asserted as a FLOOR, so a document
    added tomorrow does not fail the suite, while a *shrinking* of coverage — the failure
    this row exists to prevent — does.

    ⚠ THE FIRST DRAFT OF THIS TEST PINNED THE RECORD CLASS AT ITS 73 FILES AND WOULD HAVE
    GONE RED ON THE VERY NEXT PUSH, INCLUDING THE PUSH THAT CARRIED IT. `docs/auto/reports/`
    gains a file every lap and `docs/auto/archive/` grows whenever something is retired
    under CHARTER §3 rule 7, so the *file count* of the exception class is not a constant
    and pinning it would have made this gate a tax on the report machinery. What a human
    actually edits — and what must not grow silently — is the list of DECLARED paths, and
    the two growing directories are the two whose growth is by design. So the pin is on the
    twelve declarations and on the ten single files among them; the reports and the archive
    are counted but not fixed.
    """
    tracked = checker.tracked_files(REGISTRY)
    gated = checker.gated_files(REGISTRY)
    record = [f for f in tracked if checker.is_record(f, REGISTRY)]
    growing = ("docs/auto/reports/", "docs/auto/archive/")
    pinned = [f for f in record if not f.startswith(growing)]

    assert len(HAND_ROLLED) == 11, (
        f"the hand-rolled guard lists now cover {len(HAND_ROLLED)} files, not 11; "
        f"update docs/withdrawn_claims.md, which quotes the before-number"
    )
    assert len(gated) >= 900, f"registry coverage fell to {len(gated)} gated files"
    assert len(REGISTRY["scope"]["record_prefixes"]) == 12, (
        "the exception class has gained or lost a declared path. Growth here is the one "
        "way this gate quietly gets smaller; if it is deliberate, say so in "
        "docs/withdrawn_claims.md and change this number in the same commit."
    )
    assert len(pinned) == 10, (
        f"the record class exempts {len(pinned)} named files outside the two directories "
        f"that grow by design, not 10: {sorted(pinned)}"
    )
    assert len(record) + len(gated) == len(tracked)


def _probe_sentence(pattern: str) -> str:
    """A one-line document that matches `pattern`, taken from the withdrawn text itself.

    Deliberately a lookup rather than a generator: a probe built by inverting the regex
    would grade the pattern against itself (`mandela`, leakage pattern #4). These are the
    sentences the repository actually shipped and then withdrew.
    """
    probes = {
        r"사람보다[^\n]{0,24}?(?:느[렸리린]|늦[었게은는]|뒤[에였])":
            "위성은 사람보다 22분 늦었습니다.",
        r"사람보다[^\n]{0,24}?(?:빠[르른릅]|이르|먼저|앞[서선])":
            "위성이 사람보다 먼저 감지했습니다.",
        r"신고\s*대비": "아래는 전부 신고 대비 탐지 지연입니다.",
        r"신고보다": "세 건 모두 신고보다 느렸습니다.",
        r"기준\s*시각은\s*(?:「\s*)?신고": "기준 시각은 신고 시각입니다.",
        # found live in the tree by the reviewer, not invented from the regex
        r"기준이?\s*(?:「\s*)?신고\s*시각": "기준이 신고 시각이므로 실제 지연은 더 큽니다.",
        r"신고\s*시각\s*(?:대비|기준)": "표의 값은 신고 시각 대비입니다.",
        r"신고[^\n]{0,20}?[*\s]{0,4}일차[*\s]{0,4}(?:로|이|입니|였|소스|트리거)":
            "트리거 인터페이스는 사람 신고를 일차로 가정합니다.",
        r"일차[^\n]{0,20}?(?:소스|트리거|자리)[^\n]{0,24}?신고":
            "트리거의 일차 소스는 사람 신고입니다.",
        r"신고\s*우선": "트리거 설계가 신고 우선, 위성 확인입니다.",
        r"신고[^\n]{0,20}?[*\s]{0,4}(?:1|１|일)\s*순위": "사람 신고가 1순위입니다.",
        r"^\|\s*\**\s*[1１]\s*\**\s*\|[^\n]*사람\s*신고":
            "| **1** | **사람 신고** | 세 사건 모두 가장 빠름 |",
        r"99\s*%[^\n]{0,12}?목격\s*신고": "산불 신고의 99 %가 목격 신고였습니다.",
        r"after\s+the\s+human\s+report":
            "A satellite trigger would have fired after the human report.",
        r"report[-\s]first": "So the design is report-first, satellite-confirm.",
        r"human\s+report\s+is\s+the\s+primary|primary\s+trigger\s+source\s+is\s+the\s+human":
            "The human report is the primary trigger source.",
    }
    assert pattern in probes, (
        f"no probe sentence for a newly registered pattern:\n  {pattern}\n"
        f"Add the sentence the repository actually withdrew, not one derived from the regex."
    )
    return probes[pattern]


def test_every_registered_pattern_has_a_probe():
    """A spelling added without a withdrawn sentence beside it is a pattern nobody graded."""
    for _cid, s in SPELLINGS:
        _probe_sentence(s["pattern"])


def test_the_registry_is_valid_json_with_a_trailing_newline():
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    json.loads(raw)
