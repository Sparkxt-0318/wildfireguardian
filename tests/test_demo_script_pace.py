"""The booth script's six segment times are one rate, and stay one rate (WFG-100).

`tests/test_demo_script_5min.py` already asserts the six numbers sum to 300. That is
true of 25/45/55/75/55/45 and of 50/50/50/50/50/50 alike, so it never saw what critic
#16 measured: under this module's convention the six implied 4.51 to 7.29 syllables per
second, a 1.62x spread inside one document, with the *fastest* segment being the
limitations close, which is last and therefore the first thing a running clock eats -
once per judge. (Critic #16's own figures were 4.24 to 7.07 and 1.67x under a convention
it did not write down. The two sets are not interchangeable and are never mixed; this
docstring shipped mixing them in the lap's first commit and its reviewer caught it.)

These tests own the question that one could not ask: does each segment get seconds in
proportion to the syllables it asks the student to pronounce? They recompute the count
from the committed document on every run rather than comparing it to a stored census,
which is the MEMO 2026-09-05 lesson - a test that pins someone else's word count goes
red when that prose legitimately improves. The property here is the pace, not the count.

What no test in this file can reach: whether 5.61 syllables per second is a rate a human
can speak. That is a stopwatch and a person (R12 / NH-014), and both
`docs/demo_script_pace.md` and §5 of the script say so.

No clock, no timezone, no network, no file outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "docs" / "auto" / "DEMO_SCRIPT_5MIN.md"
PACE_DIR = REPO / "data" / "processed" / "demo_script_pace"
REGISTRY = REPO / "docs" / "NUMBERS.json"

# How far one segment's implied rate may sit from the document's single rate. Whole-second
# allocation alone moves it about 1 %; 5 % is the band where an added or deleted sentence
# is what has moved, not the rounding. Widening this band is not a fix for a red run - the
# re-measure procedure in docs/demo_script_pace.md is.
BAND = 0.05

# The measurement whose keys the registry carries for the CURRENT text of the script. A
# re-measure registers a NEW tag rather than editing these (CHARTER §3.2), and moves this
# constant; the old entries stay as the record of what the script used to ask for.
TAG = "20260905t0947z"


def _module():
    path = REPO / "scripts" / "measure_demo_script_pace.py"
    spec = importlib.util.spec_from_file_location("measure_demo_script_pace", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pace():
    return _module()


@pytest.fixture(scope="module")
def measured(pace):
    return pace.measure(SCRIPT.read_text(encoding="utf-8"))


def test_the_sino_korean_reading_is_the_one_a_speaker_uses(pace):
    """The count is only as good as how it reads a numeral out loud.

    Pinned by example because these are the readings the whole budget rests on: a bug
    that read 2,008 as eight syllables instead of three would inflate 2막 alone.
    """
    assert pace.sino_korean("2,008") == "이천팔"
    assert pace.sino_korean("2025") == "이천이십오"
    assert pace.sino_korean("240") == "이백사십"
    assert pace.sino_korean("2218") == "이천이백십팔"  # 일십 is said 십
    assert pace.sino_korean("100") == "백"
    assert pace.sino_korean("0.1939") == "영점일구삼구"
    assert pace.sino_korean("0") == "영"


def test_an_unreadable_token_is_an_error_and_never_a_silent_zero(pace):
    """The failure mode this whole measurement had to avoid.

    A tokenizer that scores an unrecognised token as zero under-counts exactly the
    segments densest in symbols, and hands the student a budget that is wrong in a new
    way with a green test on top. It fired for real on the first run of the script
    (`pooled`, in the limitations close).
    """
    with pytest.raises(pace.UnknownToken):
        pace.count_syllables(["운영점 재현율은 unmapped_token 입니다."])


def test_the_six_segments_share_one_rate(measured):
    """WFG-100's whole point: one rate, not six.

    Honest about its own strength: this is *implied* by the allocation test below, which
    is strictly stronger, so the two are not two independent confirmations of anything.
    It is kept as the legible statement of the invariant and for its error message, and
    because it survives a later lap deciding the allocation may be hand-adjusted.
    """
    rate = measured["syllables_per_second"]
    off = [(r["name"], r["implied_syllables_per_second"]) for r in measured["segments"]
           if abs(r["implied_syllables_per_second"] - rate) / rate > BAND]
    assert not off, (
        f"a segment's pace is more than {BAND:.0%} from the script's own rate of {rate} "
        f"syllables/s, so the six segment times are no longer one budget: {off}. A spoken "
        "sentence was probably added or removed. Do not widen the band - re-measure and "
        "re-allocate: docs/demo_script_pace.md."
    )


def test_the_spread_between_the_fastest_and_slowest_segment_stays_closed(measured):
    """The finding was the spread, so the spread is what is pinned.

    1.62x was the defect. Whole-second allocation cannot do better than about 1.03x, and
    anything approaching the old figure means the re-budget has been undone.
    """
    assert measured["implied_rate_spread"] <= 1.10, (
        "the fastest segment is now more than 10 % faster than the slowest; critic #16's "
        f"1.62x spread is coming back: {measured['implied_rate_spread']}x"
    )


def test_the_seconds_are_the_proportional_allocation_of_the_measured_syllables(measured, pace):
    """Each header's seconds are derivable, not chosen.

    This is the check that makes the budget an artifact rather than an opinion: given the
    syllable counts, largest-remainder allocation of 300 s reproduces the six numbers the
    document prints. It is stricter than the band above and is what a judge asking "why
    60 seconds?" is owed.
    """
    want = pace.allocate([r["spoken_syllables"] for r in measured["segments"]])
    have = [r["declared_seconds"] for r in measured["segments"]]
    assert have == want, (
        "the six segment times are no longer the proportional allocation of the syllables "
        f"actually spoken: document says {have}, the measurement says {want}"
    )
    assert sum(have) == pace.TOTAL_SECONDS


def test_the_document_does_not_claim_the_rate_is_comfortable(measured):
    """CHARTER §3.5 and §5b: this repository has measured no speech rate.

    5.61 syllables/s is arithmetic over this text and this budget. Saying it is a
    comfortable or verified speaking rate would be a claim about the world with no
    source, in the one document that is read aloud to five judges.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    for phrase in ("편안한 발화 속도", "말할 수 있는 속도로 확인", "리허설을 마쳤"):
        assert phrase not in text, f"the booth script now claims a rehearsal it never ran: {phrase}"
    assert "R12" in text or "NH-014" in text, (
        "§1/§5 no longer point at the rehearsal that is the missing half of this measurement"
    )


def test_the_registered_numbers_re_derive_from_the_committed_document(measured):
    """The two registry keys are bound to the script's live text, not to a stored number.

    If a later lap edits a spoken line, this goes red on purpose; the fix is the
    re-measure procedure in docs/demo_script_pace.md, never a new value typed in here.
    """
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["numbers"]
    assert registry[f"demo_pace_{TAG}_total_spoken_syllables"]["value"] == measured["total_spoken_syllables"]
    assert registry[f"demo_pace_{TAG}_rate_spread"]["value"] == measured["implied_rate_spread"]


def test_the_doc_that_explains_the_budget_prints_the_budget_that_shipped(measured):
    """docs/demo_script_pace.md restates the six seconds, so it can go stale silently.

    The seconds live in the script's own headers - that is the canonical copy, because
    it is the one a student reads at the booth and the one the measurement parses. The
    doc's table is a second copy for a reader who wants the before/after in one place,
    and a second copy with nothing checking it is how a document starts lying about the
    thing it exists to explain. Found by the lap's own `sip` pass, not by a reviewer.
    """
    doc = (REPO / "docs" / "demo_script_pace.md").read_text(encoding="utf-8")
    for row in measured["segments"]:
        line = next((l for l in doc.splitlines()
                     if l.startswith("| " + row["name"])), None)
        assert line, f"docs/demo_script_pace.md has no table row for {row['name']}"
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert cells[1] == f"{row['spoken_syllables']:,}".replace(",", "") or \
               cells[1] == f"{row['spoken_syllables']}", (
            f"{row['name']}: the doc says {cells[1]} syllables, the document measures "
            f"{row['spoken_syllables']}")
        assert cells[3] == f"**{row['declared_seconds']}**", (
            f"{row['name']}: the doc's table says {cells[3]} seconds, the booth script "
            f"says {row['declared_seconds']}. Re-measure per the doc's own procedure.")
    assert f"**{measured['total_spoken_syllables']:,}**" in doc, (
        "the doc's total row no longer matches the measurement")


def test_the_artifact_the_registry_points_at_is_committed_and_current(measured):
    """The artifact behind TAG, not the last filename in sort order.

    This test picked `sorted(glob)[-1]` until WFG-103's re-measure, and that is not the
    newest measurement: `pace_before_039a0de.json` sorts after every `pace_2026...` name,
    so the *before* artifact was the one being checked. It passed only because the before
    and after totals happened to be equal at 1,684 - the edit that changed the count is
    exactly the edit this test exists to catch, and it would have gone red naming the
    wrong file. Bind it to TAG, which is what the registry keys are built from.
    """
    live_path = next((p for p in sorted(PACE_DIR.glob("pace_*.json"))
                      if p.stem.lower() == f"pace_{TAG}"), None)
    assert live_path is not None, (
        f"no data/processed/demo_script_pace/pace_{TAG}.json for the tag the registry "
        "keys and this module are pinned to; a re-measure writes the artifact, registers "
        "the keys and moves TAG together"
    )
    live = json.loads(live_path.read_text(encoding="utf-8"))
    assert live["total_spoken_syllables"] == measured["total_spoken_syllables"], (
        f"{live_path.name} was measured from a different version of the script; "
        "re-measure under a new stamp (CHARTER §3.2 forbids overwriting it)"
    )
    assert live["variant"] == "full"
