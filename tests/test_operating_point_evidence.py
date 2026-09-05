"""The operating-point evidence must be recomputable, and must not drift.

WFG-019.

THE FOUR FAILURES THESE PREVENT
-------------------------------
1. **A calibration convention that quietly changes.** ``lambda_for_budget`` is
   the whole of the negative result: pick the wrong tie-break or the wrong
   inequality and lambda moves, the held-out FNRs move, and the conclusion
   ("naive calibration does not hold out; the corrected one holds but flags a
   third of the map") can flip without anyone editing a document. The two
   Round-3 verdicts already disagreed on lambda for exactly this reason. A
   synthetic frame with a hand-computable answer pins the convention.

2. **The finite-sample correction losing its point.** The finding is not that
   conformal risk control is unavailable in general; it is that at n = 5
   calibration fires the ``1/(n+1)`` term consumes 83 % of a 0.20 budget. That
   is arithmetic, and if the fire count or the budget ever changes the doc's
   sentence must change with it.

3. **Recall silently disagreeing with Session 18.** The artifact recomputes
   pooled and mean-of-folds recall from the cell-level file and cross-checks
   them against ``oof_classification_metrics.json``. The script refuses to
   write on a mismatch; this holds the committed artifact to the same rule so a
   hand-edit cannot smuggle a different number in.

4. **A per-fire row losing the count that makes it readable.** "FNR 1.000" on
   gangneung means eight positives, not a broken model, and a table that drops
   ``n_positive`` invites the wrong reading — which is the reading the whole
   document exists to prevent.

⚠ WHAT THESE DO NOT CHECK. Not whether 0.3 is a good threshold (it is a
default, and the document says so). Not whether the conformal correction is
*valid* here — it is not, and the artifact's own ``leakage_caveat`` is the
statement of that; these tests hold the arithmetic, not the inference.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = REPO / "data" / "processed" / "operating_point" / "per_fire_recall.json"
METRICS = REPO / "data" / "processed" / "oof_classification_metrics.json"
SCRIPT = REPO / "scripts" / "operating_point_evidence.py"
DOC = REPO / "docs" / "operating_point.md"


def _module():
    spec = importlib.util.spec_from_file_location("operating_point_evidence", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _module()


@pytest.fixture(scope="module")
def artifact():
    """The artifact is GIT-TRACKED, so its absence is a defect, not a condition.

    ⚠ This fixture deliberately does NOT skip. The repository's standing rule is
    that an absent input skips with its reason rather than failing — but that
    rule is about *git-ignored* inputs (the FIRMS bundle, the DEM, the OSM
    graphs), which genuinely do not reach a clean clone. This file is committed
    and `.gitignore` carries an explicit negation for it, so "absent" can only
    mean it was deleted or never written, and a skip would turn six failing
    tests into six quiet skips inside a summary line that still reads green.
    That happened once during this row's own build: one full-suite run reported
    1,071 passed / 60 skipped where every neighbouring run reported 1,077 / 54,
    and the delta was exactly the six tests behind this fixture. Fail loudly
    instead.
    """
    assert ARTIFACT.exists(), (
        f"{ARTIFACT.relative_to(REPO)} is git-tracked and missing. Regenerate "
        "with: python scripts/operating_point_evidence.py --figure"
    )
    return json.loads(ARTIFACT.read_text())


def _synthetic() -> pd.DataFrame:
    """Three fires, hand-computable, with one deliberate tie.

    Fire ``a``: positives at 0.10, 0.20, 0.90, 0.90 — note the tie at 0.90.
    Fire ``b``: positives at 0.40, 0.50.
    Fire ``c``: positives at 0.05, 0.95.
    Every fire also carries two negatives so ``flagged_fraction`` is defined.
    """
    rows = []
    spec = {
        "a": ([0.10, 0.20, 0.90, 0.90], [0.01, 0.99]),
        "b": ([0.40, 0.50], [0.02, 0.98]),
        "c": ([0.05, 0.95], [0.03, 0.97]),
    }
    for fire, (pos, neg) in spec.items():
        for p in pos:
            rows.append({"fire_id": fire, "label": 1, "prob": p})
        for p in neg:
            rows.append({"fire_id": fire, "label": 0, "prob": p})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 1. the convention, pinned on a frame whose answer can be read off by hand
# --------------------------------------------------------------------------


def test_lambda_is_the_largest_threshold_meeting_the_budget(mod):
    """Positives 0.1/0.2/0.9/0.9, budget 0.5 -> lambda 0.9, FNR exactly 0.5.

    The comparison is strict, so the two positives AT 0.9 count as caught and
    the achieved FNR is 2/4. A non-strict comparison would put it at 4/4 and a
    "smallest feasible lambda" convention would return 0.2; both are defensible
    and both give a different negative result, which is why this is pinned.
    """
    pos = np.array([0.10, 0.20, 0.90, 0.90])
    lam = mod.lambda_for_budget(pos, 0.5)
    assert lam == pytest.approx(0.90)
    assert float((pos < lam).mean()) == pytest.approx(0.5)


def test_a_zero_budget_admits_no_misses_at_all(mod):
    """Budget 0 must return 0.0, not the smallest positive probability."""
    assert mod.lambda_for_budget(np.array([0.1, 0.2, 0.9]), 0.0) == 0.0


def test_the_budget_is_never_exceeded_on_the_calibration_set(mod):
    """Whatever the tie structure, the achieved calibration FNR is within budget."""
    df = _synthetic()
    calib = mod.nested_lofo_calibration(df, 0.5)
    for block in calib["conventions"].values():
        target = block["target_fnr_on_calibration_fires"]
        for row in block["per_held_out_fire"].values():
            assert row["calibration_fnr"] <= target + 1e-9


# --------------------------------------------------------------------------
# 2. the correction is the finding, so its arithmetic is held
# --------------------------------------------------------------------------


def test_the_finite_sample_correction_is_one_over_n_plus_one(mod):
    """Three fires -> two calibration fires -> 1/3, and it eats 2/3 of a 0.5 budget."""
    calib = mod.nested_lofo_calibration(_synthetic(), 0.5)
    assert calib["n_calibration_fires"] == 2
    assert calib["finite_sample_correction"] == pytest.approx(1 / 3, abs=5e-4)
    assert calib["correction_share_of_budget"] == pytest.approx(2 / 3, abs=5e-3)


def test_at_six_fires_the_correction_consumes_most_of_the_budget(artifact):
    """The committed run: 1/6 of a 0.20 budget is 83 %, which is the whole point."""
    calib = artifact["threshold_calibration"]
    assert calib["n_fires"] == 6
    assert calib["n_calibration_fires"] == 5
    assert calib["finite_sample_correction"] == pytest.approx(1 / 6, abs=5e-4)
    assert calib["correction_share_of_budget"] >= 0.8


def test_the_two_conventions_fail_in_opposite_directions(artifact):
    """Neither column alone is the result; the pair is.

    Naive meets the budget on the calibration fires and then breaks it on the
    fire it never saw; corrected holds on every held-out fire and pays for it by
    flagging a large share of the map against a 1.97 % prevalence.
    """
    conv = artifact["threshold_calibration"]["conventions"]
    naive, conformal = conv["naive"], conv["conformal"]

    assert naive["n_held_out_bound_holds"] < 6
    assert naive["held_out_fnr_max"] > artifact["threshold_calibration"]["budget_fnr"]

    assert conformal["n_held_out_bound_holds"] == 6
    assert conformal["flagged_fraction_all_cells_min"] > 10 * artifact["prevalence"]


# --------------------------------------------------------------------------
# 3. the committed artifact agrees with Session 18 and keeps its counts
# --------------------------------------------------------------------------


def test_recall_agrees_with_the_session_18_metrics(artifact):
    metrics = json.loads(METRICS.read_text())
    assert artifact["cross_check"]["pooled_agrees"] is True
    assert artifact["cross_check"]["mean_of_folds_agrees"] is True
    assert artifact["pooled_recall"] == metrics["pooled"]["recall"]
    assert artifact["mean_of_folds_recall"] == metrics["mean_of_folds"]["recall"]


def test_every_fire_carries_the_positive_count_beside_its_rate(artifact):
    per_fire = artifact["per_fire"]
    assert len(per_fire) == 6
    for fire, row in per_fire.items():
        assert row["n_positive"] > 0, fire
        assert row["recall"] is not None, fire
        assert row["false_negative_rate"] == pytest.approx(1.0 - row["recall"], abs=5e-4)
    assert sum(r["n_positive"] for r in per_fire.values()) == artifact["n_positive"]


def test_the_two_fires_the_threshold_can_never_fire_on_are_marked(artifact):
    """0.3 is above every probability in gangneung and hongseong.

    That is a stronger statement than zero recall, and the JUDGE_QA answer
    leans on it, so the flag is held rather than left to be re-derived.
    """
    per_fire = artifact["per_fire"]
    unreachable = {f for f, r in per_fire.items() if not r["threshold_is_reachable"]}
    assert unreachable == {"gangneung_2023", "hongseong_2023"}
    for fire in unreachable:
        assert per_fire[fire]["max_prob_any_cell"] < artifact["operating_threshold"]


# --------------------------------------------------------------------------
# 4. the document must keep the distinction that stops the misreading
# --------------------------------------------------------------------------


def test_the_document_separates_the_two_thresholds(artifact):
    """recall at advance_threshold is not the router's miss rate at p_cut."""
    assert DOC.exists(), (  # git-tracked; see the note on the artifact fixture
        f"{DOC.relative_to(REPO)} is git-tracked and missing"
    )
    text = DOC.read_text(encoding="utf-8")
    assert "forward_sim_advance_threshold" in text
    assert "walk_cutoff_p" in text
    assert str(artifact["router_p_cut"]) in text
