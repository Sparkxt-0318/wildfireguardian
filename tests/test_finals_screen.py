"""The finals presentation screen (web/finals.html).

The screen is a build artifact; every test that reads it is skipped when it
has not been built (same convention as the operator screens). What is pinned
here:

- the strict offline / dash gates pass on the built file;
- every displayed count is byte-consistent with the canonical artifacts
  (the screen is a presentation layer, never a source of numbers);
- the Yeongdeok coverage caveat rides along, region facts do not leak
  across regions, and retired-lineage figures do not appear;
- the four outcome buckets stay triple-encoded (colour + shape + glyph);
- media is optional by construction and motion preferences are honoured.
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

from check_screen_assets import (  # noqa: E402
    check_dashes, check_dashes_in_scripts, check_offline,
)

FINALS = REPO / "web" / "finals.html"
TEMPLATE = REPO / "scripts" / "finals.template.html"

pytestmark = pytest.mark.skipif(
    not FINALS.exists(), reason="web/finals.html not built (make finals)")


def _text() -> str:
    return FINALS.read_text(encoding="utf-8")


def _payload() -> dict:
    m = re.search(
        r'<script id="data" type="application/json">(.*?)</script>',
        _text(), re.S)
    assert m, "embedded data payload not found"
    return json.loads(m.group(1))


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------


def test_the_screen_is_fully_offline_in_strict_mode():
    text = _text()
    assert check_offline(text) == []


def test_no_em_or_en_dash_survives_anywhere():
    text = _text()
    assert check_dashes(text, html=True) == []
    assert check_dashes_in_scripts(text) == []
    # the payload blind spot (docs'd in check_screen_assets) is closed at the
    # source: the builder normalises the whole JSON blob
    m = re.search(r'<script id="data"[^>]*>(.*?)</script>', text, re.S)
    assert "—" not in m.group(1) and "–" not in m.group(1)


def test_no_placeholder_leaks_into_the_built_page():
    marker = "/*__" + "DATA" + "__*/"
    assert marker not in _text()
    assert marker in TEMPLATE.read_text(encoding="utf-8")


def test_fonts_are_the_vendored_relative_files():
    text = _text()
    assert "assets/fonts/IBMPlexSansKR-Regular.woff2" in text
    assert "assets/fonts/IBMPlexMono-Regular.woff2" in text
    assert "assets/fonts/Pretendard-arrow.subset.woff2" in text


def test_reduced_motion_is_honoured_and_lang_is_korean():
    text = _text()
    assert "prefers-reduced-motion" in text
    assert '<html lang="ko">' in text


# --------------------------------------------------------------------------
# data integrity: the screen repeats the artifacts, never invents
# --------------------------------------------------------------------------


def _canonical_counts(region: str) -> dict:
    name = ("real_roads_real_hazard_canonical.json" if region == "yeongdeok_2025"
            else f"real_roads_real_hazard_{region}.json")
    data = json.loads((REPO / "data" / "processed" / name)
                      .read_text(encoding="utf-8"))
    return data["arms"]["slope_digraph_canonical"]["counts"]


def test_every_region_count_matches_its_canonical_artifact():
    payload = _payload()
    for region, rp in payload["regions"].items():
        want = _canonical_counts(region)
        for key, value in want.items():
            assert rp["counts"].get(key, 0) == value, (region, key)
        assert rp["n_scanned"] == sum(want.values()), region


def test_comparison_facts_come_from_the_committed_table():
    payload = _payload()
    table = json.loads((REPO / "data" / "processed" /
                        "multi_region_comparison.json").read_text(encoding="utf-8"))
    rows = {r["region"]: r for r in table["regions"]}
    assert payload["region_order"] == table["region_order"]
    for region, rp in payload["regions"].items():
        row = rows[region]
        assert rp["fa_only_pct"] == row["future_aware_only_safe_pct"], region
        assert rp["coverage_pct"] == round(
            row["envelope_coverage_final_slice"] * 100.0, 1), region
        assert rp["label"] == row["label_kr"], region
        assert rp["shelter_pois"] == row["shelter_pois"], region


def test_the_yeongdeok_coverage_caveat_rides_along():
    rp = _payload()["regions"]["yeongdeok_2025"]
    assert "32.6" in rp["coverage_note"]
    assert "편향의 방향" in rp["coverage_note"]


def test_region_facts_do_not_leak_across_regions():
    payload = _payload()
    # each region's fa-only percentage is unique in this dataset; make sure
    # no region record carries another region's value
    values = {r: p["fa_only_pct"] for r, p in payload["regions"].items()}
    assert len(set(values.values())) == len(values)
    # weather basis lines are region-specific strings from each run's scope
    lines = {r: p["weather_line"] for r, p in payload["regions"].items()}
    assert len(set(lines.values())) == len(lines)


def test_derived_road_states_are_internally_coherent():
    payload = _payload()
    for region, rp in payload["regions"].items():
        tr, tc = rp["roads"]["tr"], rp["roads"]["tc"]
        assert len(tr) == len(tc) == len(rp["roads"]["lens"]), region
        for a, b in zip(tr, tc):
            if b >= 0:
                assert a >= 0 and a <= b, region  # risk precedes closure
        loss = rp["loss"]["n"]
        assert all(x <= y for x, y in zip(loss, loss[1:])), region
        assert loss[-1] <= rp["loss"]["total_n"], region
        # the derivation thresholds are the pipeline's own
        assert payload["p_closed"] == 0.5 and payload["p_risk"] == 0.3


def test_the_flagship_pair_is_an_honest_contrast():
    payload = _payload()
    for region, rp in payload["regions"].items():
        rt = rp["routes"][rp["flagship"]]
        assert rt["naive"]["enters"] is True, region
        assert rt["fa"]["enters"] is False, region


def test_buckets_stay_triple_encoded():
    buckets = _payload()["buckets"]
    assert len(buckets) == 4
    assert len({b["shape"] for b in buckets}) == 4
    assert len({b["mark"] for b in buckets}) == 4
    assert len({b["fill"] for b in buckets}) == 4


# --------------------------------------------------------------------------
# claims discipline
# --------------------------------------------------------------------------


def _has_token(text: str, token: str) -> bool:
    pattern = r"(?<![\d.,])" + re.escape(token) + r"(?![\d])"
    return re.search(pattern, text) is not None


def test_retired_lineage_figures_do_not_appear():
    text = _text()
    for token in ("0.867", "0.8667", "0.834", "0.8340", "0.874", "0.8745",
                  "138619", "2731"):
        assert not _has_token(text, token), token
    # This IS the scanning list of a test that asserts these words are ABSENT
    # from the finals screen — hence the pragma on the line itself.
    for word in ("XGBoost", "Chen", "Guestrin", "multi-scale"):  # forbidden-ok: XGBoost, Chen, Guestrin, multi-scale
        assert word not in text, word


def test_forbidden_framings_do_not_appear():
    # registry caveats quoted in the payload may NAME a forbidden framing in
    # order to negate it ("carries no 'lives saved' reading") — that is the
    # rule text, not a claim. Scan the page with caveat fields removed.
    text = re.sub(r'"caveat":".*?(?<!\\)"', '"caveat":""', _text())
    for phrase in ("정확도 89", "89% accurate", "실시간 예보",
                   "lives saved", "명을 구했", "구조했습니다",
                   "소방서가 없습니다", "deadline-first rescues",
                   "우선순위가 검증", "최초로", "처음으로"):
        assert phrase not in text, phrase
    # pooled must never be presented as the fold mean
    assert "pooled AUC 0.890" not in text


def test_the_negative_ordering_result_is_stated_not_hidden():
    text = _text()
    assert "모서리" in text          # corner-not-boundary quote
    assert "이기는" in text or "존재하지 않" in text


def test_media_is_optional_by_construction():
    text = _text()
    # the intro must carry its no-media fallback, and nothing may fetch()
    assert "introFallback" in text
    assert "fetch(" not in text


# --------------------------------------------------------------------------
# the v2 evidence cards (WFG-017)
# --------------------------------------------------------------------------


def _artifact(*parts: str) -> dict:
    return json.loads((REPO.joinpath(*parts)).read_text(encoding="utf-8"))


def test_the_v2_cards_have_every_registry_key_they_read():
    # a card whose key is missing renders nothing at all and fails silently,
    # which is the one failure mode a screenshot would not show either
    entries = _payload()["registry"]["entries"]
    for key in ("oof_pooled_recall_at_operating_threshold",
                "oof_mean_of_folds_recall_at_operating_threshold",
                "oof_average_precision", "oof_prevalence",
                "det_size_floor_ha_tf750",
                "det_gk2a_delay_uiseong_andong_min",
                "det_gk2a_delay_gangneung_2023_min",
                "det_gk2a_delay_hongseong_2023_min",
                "det_control_steps", "det_false_alarm_steps",
                "kfs_cum_le_240_pct", "kfs_n_usable_events",
                "kfs_containment_median_min", "kfs_area_ge100ha_median_min",
                "l0i_best_single_refuge_saved", "l0i_best_pair_saved",
                "l0i_third_refuge_gain", "l0i_candidates_enumerated"):
        assert key in entries, key


def test_the_operating_point_card_matches_the_committed_per_fire_file():
    got = _payload()["ev2"]["operating_point"]
    per = _artifact("data", "processed", "operating_point",
                    "per_fire_recall.json")["per_fire"]
    misses = [v for v in per.values() if v["false_negative_rate"] >= 1.0]
    assert got["n_fires"] == len(per)
    assert got["n_folds_without_a_true_positive"] == len(misses)
    assert got["n_positive_of_those"] == sorted(v["n_positive"] for v in misses)
    rest = [v for v in per.values() if v["false_negative_rate"] < 1.0]
    fnrs = sorted(round(v["false_negative_rate"], 3) for v in rest)
    assert got["n_folds_with_a_true_positive"] == len(rest)
    # the range must exclude the perfect-miss folds: the card's sentence says
    # "the remaining folds", and 1.000 is not one of them
    assert got["fnr_max_among_folds_with_a_true_positive"] < 1.0
    assert (got["fnr_min_among_folds_with_a_true_positive"],
            got["fnr_max_among_folds_with_a_true_positive"]) == (fnrs[0], fnrs[-1])
    assert (got["n_folds_with_a_true_positive"]
            + got["n_folds_without_a_true_positive"] == got["n_fires"])
    # the row's point: the perfect-miss folds must read as prevalence, so the
    # positive counts have to travel with them
    assert got["n_folds_without_a_true_positive"] > 0
    assert all(n > 0 for n in got["n_positive_of_those"])


def test_the_refuge_card_matches_the_committed_placement_file():
    got = _payload()["ev2"]["refuge"]
    rp = _artifact("data", "processed", "vulnerability", "refuge_placement.json")
    ver = rp["verification"]["full_layer_verification"]
    assert got["site"] == rp["site"]
    assert got["failing_before"] == ver["full_layer_failing_before"]
    assert got["failing_after"] == ver["full_layer_failing_after"]
    assert got["horizon_min"] == ver["horizon_min"]
    assert (got["survival_evaluations"]
            == rp["verification"]["survival_check"]["n_site_scenario_evaluations"])
    # the marginal curve the card prints is the registry's, and it must agree
    entries = _payload()["registry"]["entries"]
    curve = rp["optimum_h240"]["marginal_curve"]
    assert entries["l0i_best_single_refuge_saved"]["value"] == curve["k1_saved"]
    assert entries["l0i_best_pair_saved"]["value"] == curve["k2_saved"]
    assert entries["l0i_third_refuge_gain"]["value"] == curve["k3_gain_over_k2"]


def test_the_refuge_card_never_reads_as_lives_or_as_a_siting_decision():
    # the artifact's own _README calls itself a geometric recommendation under
    # stated assumptions; the screen may not promote it past that
    text = _text()
    # NOTE the shape of this list: "입지 결정" is NOT bannable, because the
    # card's own caveat says 「입지 결정이 아닙니다」 and a substring ban would
    # forbid the sentence that does the work. Ban the assertions, not the noun.
    for phrase in ("가구를 구", "구조된 가구", "대피소를 지어",
                   "안전이 보장", "설치하면 안전", "입지 결정입니다"):
        assert phrase not in text, phrase
    for required in ("도달 가능해지는 가구 수", "입지 결정이 아닙니다",
                     "목적함수는 도달 가능성뿐"):
        assert required in text, required


def test_the_detection_card_rules_the_satellite_out_and_nothing_in():
    # WFG-053 withdrew the ordering claim; critic #7 F35 then found that the
    # size floor rules the SATELLITE OUT and does not rule the HUMAN CHANNEL
    # IN. The screen is the fifth judge-facing document and must not repeat it.
    text = _text()
    assert "정지궤도 위성을 일차 트리거로 둘 수 없습니다" in text
    for banned in ("사람 신고가 일차", "사람 신고를 일차",
                   "신고를 일차 소스", "99 %가 목격", "99%가 목격",
                   "위성은 사람보다", "사람보다 느", "사람보다 늦",
                   "사람보다 빠", "신고보다 느", "신고보다 빠"):
        assert banned not in text, banned
    # and the delays must be stated against the RECORDED time, not a report time
    assert "기록된 발생일시 대비" in text
    assert "먼저였다는 주장은 하지 않습니다" in text


def test_the_size_floor_is_shown_as_the_span_its_assumption_allows():
    """A point estimate here is five times narrower than the repo's interval.

    ``det_size_floor_ha_tf750`` is 0.1939 ha, and its own registry caveat says
    ORDER OF MAGNITUDE ONLY and READ THE FLOOR AS ROUGHLY 0.1-1 ha, because
    the flaming temperature is assumed rather than measured and moves the
    answer more than eightfold. A judge reading the card for five seconds
    should get the span, not the midpoint.
    """
    got = _payload()["ev2"]["size_floor"]
    spa = _artifact("data", "processed", "detection",
                    "gk2a_detection_floor.json")["per_fire"][
                        "uiseong_andong_2025"]["sub_pixel_area"]
    areas = sorted(v["fire_area_ha"] for v in spa.values())
    assert (got["ha_min"], got["ha_max"]) == (areas[0], areas[-1])
    assert got["n_assumed_temperatures"] == len(spa) >= 3
    # the span must actually be wide, or showing it buys nothing
    assert got["ha_max"] / got["ha_min"] > 5
    # NOTE the card's headline is composed at render time out of these two
    # payload numbers, so the formatted span exists nowhere in the source.
    # Pin the payload, and pin that the template still COMPOSES it rather
    # than having acquired a hand-typed literal.
    tpl = TEMPLATE.read_text(encoding="utf-8")
    assert "SF.ha_min.toFixed(2) + '~' + SF.ha_max.toFixed(2)" in tpl
    assert "자릿수로만 읽으십시오" in _text()


TRIGGER_PRIORITY_WORDS = ("일차", "우선", "먼저", "앞서", "앞섭", "앞선",
                          "최초", "주된", "주 소스")
TRIGGER_SOURCE_NOUNS = ("신고", "위성", "GK2A", "FIRMS", "감시카메라", "무전")
NEGATIONS = ("없습니다", "하지 않습니다", "않았습니다", "아닙니다", "못합니다")


def test_every_trigger_priority_sentence_on_the_screen_is_a_negation():
    """A counting gate, because a spelling gate inherits its own corpus.

    ``test_the_detection_card_rules_the_satellite_out_and_nothing_in`` bans
    the spellings this repository has actually written, and the MEMO entry of
    2026-09-04 is about exactly that being worth little: the next author uses
    a synonym. So this one does not read spellings. It asserts that any line
    naming BOTH a priority word and a trigger source must also carry a
    negation, which holds whatever words the sentence is built from.

    The source-noun condition is load-bearing, not decoration: without it the
    rule fires on 「최초 임계 도달」 (a route-timeline label) and 「최초 승리
    창」 (the ordering-boundary result), neither of which is about triggers.

    Mutation-checked against three phrasings that appear nowhere in the tree:
    「전화 신고를 우선 소스로 둡니다」, 「최초 인지는 주민 신고입니다」 and
    「위성보다 신고가 앞섭니다」. All three are caught; all three escape the
    spelling list. WFG-062 is the row that generalises this beyond one file.
    """
    tpl = TEMPLATE.read_text(encoding="utf-8")
    offenders = []
    for lineno, line in enumerate(tpl.splitlines(), 1):
        if not any(w in line for w in TRIGGER_PRIORITY_WORDS):
            continue
        if not any(s in line for s in TRIGGER_SOURCE_NOUNS):
            continue
        if not any(n in line for n in NEGATIONS):
            offenders.append((lineno, line.strip()[:90]))
    assert offenders == [], offenders


def test_the_horizon_card_discloses_the_reference_time_disagreement():
    """The screen may not silently pick a side of an open disagreement.

    An earlier draft of this test banned the phrase 「신고 시각」 from the card
    and asserted only ``docs/horizon_grounding.md`` §2's position ("we could
    not confirm what 발생일시 means"). That was wrong on the merits, and the
    lap's independent reviewer refused the push for it: the committed
    artifact the card cites says the OPPOSITE in its own header, and so do
    all four registry entries the card reads. Banning the artifact's own
    wording from the screen would have made the presentation layer outvote
    its source, permanently, through a gate.

    So the requirement is disclosure, not a side: the card must name the
    artifact's reading AND the fact that its upstream source is unconfirmed,
    and must state the durations in the form that is true under both.
    Resolving it is WFG-061 / NH-019.
    """
    text = _text()
    assert "기록된 발생일시에서 진화까지" in text
    assert "신고된 시작 시각" in text        # the artifact's own reading, stated
    assert "상위 출처는 아직 확인되지 않았습니다" in text
    assert "WFG-061" in text
    # and the sentence that is true either way
    assert "「기록 → 진화」로만 읽습니다" in text


def test_the_artifact_still_says_what_it_says():
    """A guard on the guard: if the artifact's header ever stops asserting a
    reported start time, the disclosure above becomes a false description of
    it and this test is what notices."""
    art = _artifact("data", "processed", "detection",
                    "kfs_containment_duration.json")
    assert "REPORTED start time" in art["⚠_reference_time"]


def test_the_refuge_card_claims_only_the_verification_that_was_run():
    """The full-layer recomputation covers ONE site, and the card said three.

    ``verification.full_layer_verification`` recomputes a single node at
    k = 1. ``marginal_curve``'s k2 and k3 figures were never put through it,
    and the verified node is not even the k1 optimum. The first draft of this
    card closed the k1/k2/k3 sentence with 「빠른 탐색의 예측과 전 계층
    재계산이 같은 가구 집합에서 일치했습니다」, which is a scope the artifact
    does not carry. Values alone cannot catch that, so this pins the scope.
    """
    got = _payload()["ev2"]["refuge"]
    rp = _artifact("data", "processed", "vulnerability", "refuge_placement.json")
    ver = rp["verification"]["full_layer_verification"]
    assert got["n_sites_full_layer_verified"] == 1
    assert got["verified_node"] == ver["node"]
    assert got["verified_k1_node"] == rp["optimum_h240"]["marginal_curve"]["k1_nodes"][0]
    # the artifact verified a DIFFERENT node from the k1 optimum; if that ever
    # stops being true the card's careful wording can be relaxed, on purpose
    assert got["verified_node"] != got["verified_k1_node"]
    text = _text()
    assert "두 곳·세 곳의 값은 그렇게 확인되지 않았습니다" in text
    # and the survivors of that one verification are shown, not hidden
    assert str(got["failing_after"]) in text
    assert "빠른 탐색의 예측과 전 계층 재계산이 같은 가구 집합에서 일치했습니다" not in text


def test_the_v2_cards_put_a_caveat_on_every_number_they_show():
    # each new card carries its own warn line; a card that lost its caveat in
    # an edit is the failure this pins
    text = _text()
    for caveat in (
            "경로 산출의 놓침 비율로 읽어서는 안 됩니다",   # operating point
            "어떤 소스가 일차여야 하는지는 재지 않았습니다",  # detection floor
            "평균은 계산하지 않습니다",                     # horizon
            "OSM 건물 스냅숏 위의 잠정치"):                 # refuge
        assert caveat in text, caveat


def test_the_reconciliation_card_states_the_lineage_rule_without_retired_values():
    text = _text()
    assert "제출본과 정본의 차이" in text
    assert "docs/submission_reconciliation.md" in text
    # The constraint on this row: retired-lineage counts never reach the
    # screen. Scan the TEMPLATE, not the built page: a retired figure gets
    # onto this screen by being typed into the template, and a bare-digit
    # scan of the 2 MB artifact payload both false-positives (a canonical
    # coordinate contains "438") and, when it does, makes pytest render the
    # whole payload as an assertion diff.
    # Ban the COMPOSITE spellings, not bare digits: "460" is a CSS max-width
    # in this very file and "438" is a coordinate. A retired routing lineage
    # only reaches a screen as its triple or its share, so that is the shape
    # to hold.
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for retired in ("438/18/3", "18/459", "440/17/3", "17/3/460",
                    "3.70%", "3.70 %", "438개", "459개", "460개"):
        assert retired not in tpl, retired


def test_provenance_is_on_screen():
    payload = _payload()
    for region, rp in payload["regions"].items():
        assert rp["prov"]["run"], region
        assert rp["prov"]["npz_sha16"], region
        assert rp["prov"]["walk_snap"].startswith("osm-walk_"), region


# ---------------------------------------------------------------------------
# WFG-067 · the integrity panel's commit id must resolve, and be reachable
# ---------------------------------------------------------------------------
#
# The panel a judge is invited to verify the build with carried "a562045" for
# four critic windows; `git cat-file -t a562045` answers "Not a valid object
# name" in a fresh clone. It is a pre-rebase hash: the WFG-017 lap built the
# screen, then `git pull --rebase` rewrote its commits and the stamp inside the
# built HTML kept pointing at the object the rebase discarded.
#
# The row's own done-when proposes `git cat-file -e <stamp>`, one line. THIS LAP
# MEASURED THAT AND IT IS NOT ENOUGH, and that is the objection this gate is
# built on. `cat-file -e` asks the object database whether the object exists,
# and a rebased-away commit still exists there, unreachable, until gc runs. So
# on the very machine that creates this defect the proposed gate stays green;
# it only goes red in the fresh clone, which is where nobody is looking. The
# predicate has to be REACHABILITY from HEAD, not existence:
# `git merge-base --is-ancestor <stamp> HEAD`.
#
# It must not be equality with HEAD: the commit that carries a build is always
# one later than the commit it was built at, so an equality gate is
# unsatisfiable and the next lap would weaken it (the row says so explicitly).

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def _stamp_is_reachable(stamp: str) -> bool:
    """The gate's whole predicate, factored out so it can be graded below."""
    if not stamp or stamp == "unknown":
        return False
    if _git("cat-file", "-e", f"{stamp}^{{commit}}").returncode != 0:
        return False
    return _git("merge-base", "--is-ancestor", stamp, "HEAD").returncode == 0


def _needs_git_history():
    """Only a missing work tree skips this gate.

    The first draft of this helper also skipped on `--is-shallow-repository`,
    which would have switched the gate off in exactly the place the loop runs:
    the cloud sandbox clones shallow (294 commits deep, but flagged shallow).
    A gate that skips where the defect is created is the hole it was written to
    close. The limit it really has is narrow and safe: a stamp older than the
    shallow boundary would fail `cat-file -e` and read as "rebuild the screen",
    which is a red gate asking for a rebuild, not a wrong screen shipped.
    """
    if _git("rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
        pytest.skip("not a git work tree")


def test_the_integrity_panel_names_a_commit_this_repository_has():
    """WFG-067. Fails on the a562045 class: a stamp orphaned by a rebase."""
    _needs_git_history()
    stamp = _payload()["git"]
    assert stamp and stamp != "unknown", (
        "build_finals.py could not read HEAD; the panel would print 'unknown'")
    assert _git("cat-file", "-e", f"{stamp}^{{commit}}").returncode == 0, (
        f"web/finals.html names commit {stamp}, which is not an object in this "
        "repository. Rebuild the screen (make finals) on the commit you are pushing.")
    assert _git("merge-base", "--is-ancestor", stamp, "HEAD").returncode == 0, (
        f"web/finals.html names commit {stamp}, which exists but is NOT reachable "
        "from HEAD: a rebase moved the build commit and the stamp was not rebuilt. "
        "A lap that rebases after building rebuilds before it pushes.")


def test_the_stamp_gate_is_graded_against_the_ways_a_stamp_goes_wrong():
    """The catch rate, measured rather than asserted (MEMO 2026-09-04).

    Five cases, four of them failures the panel has actually shown or could show.

    **This lap wrote its prediction down first and it was wrong.** It predicted
    `git cat-file -e` -- the one-line gate WFG-067's done-when proposes -- would
    score 3 of 5, having forgotten that the literal string "unknown" is not an
    object either, so existence rejects it correctly. The measurement is 4 of 5.
    The objection survives the correction and is sharpened by it: the proposed
    gate is right about almost everything and wrong about the single case the row
    was filed for, which is the shape of a gate that reads green for four windows
    while the defect ships. Recorded rather than quietly edited, because a rate
    that matches the guess teaches nothing and this one did not match.
    """
    _needs_git_history()
    head = _git("rev-parse", "HEAD").stdout.strip()
    parent = _git("rev-parse", "HEAD~1").stdout.strip()
    # A real commit object that no branch reaches: exactly what a rebase leaves.
    orphan = _git("commit-tree", f"{head}^{{tree}}", "-p", head,
                  "-m", "unreachable probe for the WFG-067 gate").stdout.strip()
    assert orphan, "could not build the orphan probe"

    cases = [
        ("built at HEAD",            head[:7],   True),
        ("built at HEAD's parent",   parent[:7], True),
        ("orphaned by a rebase",     orphan[:7], False),
        ("a562045, the shipped bug", "a562045",  False),
        ("git was unavailable",      "unknown",  False),
    ]
    graded = [(label, _stamp_is_reachable(stamp) is expected) for label, stamp, expected in cases]
    assert all(ok for _, ok in graded), [label for label, ok in graded if not ok]

    # And the measurement that decided the design: existence alone scores 4/5,
    # missing only the one case this row exists for.
    existence_only = [
        (_git("cat-file", "-e", f"{stamp}^{{commit}}").returncode == 0) is expected
        for _, stamp, expected in cases
    ]
    assert sum(existence_only) == 4, (
        "`git cat-file -e` was expected to misgrade the orphan case and be right "
        f"on the other 4 of 5; it scored {sum(existence_only)}. If this changed, "
        "the objection in the comment above needs re-measuring, not deleting.")
    orphan_case = next(i for i, (label, _, _) in enumerate(cases)
                       if label == "orphaned by a rebase")
    assert existence_only[orphan_case] is False, (
        "the whole objection is that existence passes the orphan case")
