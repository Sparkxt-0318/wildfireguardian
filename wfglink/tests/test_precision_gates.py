"""scripts/precision_gates.py: every branch of the accuracy gates on hand-made inputs, the
separate gates, and the command end to end."""
from __future__ import annotations

import importlib.util
import json

import pytest

from wfglink import PROJECT_ROOT
from wfglink.verify.calibrate import reviewed_metrics

spec = importlib.util.spec_from_file_location("precision_gates_t", PROJECT_ROOT / "scripts" / "precision_gates.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

LOW, POS = "low_observability", "ember_positive"


def counts(t=0, f=0, a=0, u=0):
    return {"true": t, "false": f, "ambiguous": a, "unresolved": u}


def review(per: dict, control: dict | None = None, population: str = "test") -> dict:
    """review_points.json as precision_review.py score writes it: per recording (true, false,
    ambiguous, unresolved, accepted, supported minutes) of the selected point."""
    sup = {r: v[5] for r, v in per.items()}
    tot = [sum(v[i] for v in per.values()) for i in range(5)]
    point = reviewed_metrics(counts(*tot[:4]), tot[4], sum(sup.values()))
    point["family"] = "rules"
    point["per_recording"] = {r: reviewed_metrics(counts(*v[:4]), v[4], v[5]) for r, v in per.items()}
    pts = {"rules_q0.01": point}
    if control is not None:
        pts["accept_all"] = reviewed_metrics(counts(*control[:4]), control[4], sum(sup.values()))
    return {"population": population, "points": pts, "decoys": {"n": 0}, "supported_minutes": sup}


def ev(rec: str, tp=0, false=0, dup=0, matched=0, observable=0, fcount=0, fweight=0.0, minutes=1.0, sealed=True,
       **extra) -> dict:
    """A verify eval output (evaluate_run) reduced to what the gates read."""
    tl = {"counts": {"tp": tp, "false": false, "duplicate": dup, "dont_care": 0, "judged": tp + false + dup,
                     "truth_matched": matched, "truth_observable": observable},
          "rates": {"false_tracks_per_min": {"value": fweight / minutes, "count": fcount, "weighted_count": fweight,
                                             "minutes": minutes}}}
    return {"track_level": tl, "protocol": {"sealed": sealed, "recording": rec}, **extra}


def loaded(tmp_path, stratum: str, evals: list[dict], listed=None) -> list[dict]:
    paths = []
    for i, e in enumerate(evals):
        p = tmp_path / f"{stratum}_{i}.json"
        p.write_text(json.dumps(e))
        paths.append(str(p))
    return G.load_evals(paths, stratum, listed, False)


# Precision -------------------------------------------------------------------------------------

def test_precision_passes_with_299_true_and_none_false():
    r = G.precision_status(299, 299, 0, 0, 0)
    assert r["status"] == G.PASSED and r["precision_lower95_one_sided"] >= 0.99


def test_precision_298_true_is_insufficient_evidence():
    r = G.precision_status(298, 298, 0, 0, 0)
    assert r["status"] == G.INSUFFICIENT and r["precision"] == 1.0 and r["precision_lower95_one_sided"] < 0.99


def test_precision_zero_accepted_tracks_fails():
    r = G.precision_status(0, 0, 0, 0, 0)
    assert r["status"] == G.FAILED and r["precision"] is None
    assert any("zero accepted" in x for x in r["reasons"])


def test_precision_point_estimate_below_target_fails():
    assert G.precision_status(100, 90, 10, 0, 0)["status"] == G.FAILED


def test_precision_reviewed_but_nothing_true_or_false_is_insufficient():
    r = G.precision_status(5, 0, 0, 0, 0)
    assert r["status"] == G.INSUFFICIENT and r["precision"] is None


def test_precision_window_override_fails_a_passing_review():
    r = G.precision_status(300, 300, 0, window_tp=9, window_n=10)
    assert r["status"] == G.FAILED and r["window"]["override_applies"]
    assert any("window-judged" in x for x in r["reasons"])


def test_precision_window_override_needs_ten_judged_tracks():
    r = G.precision_status(300, 300, 0, window_tp=0, window_n=9)
    assert r["status"] == G.PASSED and not r["window"]["override_applies"]
    assert G.precision_status(300, 300, 0, window_tp=10, window_n=10)["status"] == G.PASSED


def test_precision_gate_pools_both_strata_and_reports_each(tmp_path):
    rv = review({"A": (150, 0, 2, 1, 160, 30.0), "B": (149, 0, 0, 0, 149, 20.0)}, control=(40, 60, 0, 0, 500))
    evals = {LOW: loaded(tmp_path, LOW, [ev("A", tp=1)]), POS: loaded(tmp_path, POS, [ev("B", tp=2)])}
    g = G.gate_precision(rv, None, evals, {LOW: ["A"], POS: ["B"]})
    assert g["status"] == G.PASSED and g["provisional"] and G.label(g) == "PASSED, PROVISIONAL"
    assert g["true"] == 299 and g["accepted_tracks"] == 309 and g["window"]["judged"] == 3
    assert g["per_stratum"][LOW]["status"] == G.INSUFFICIENT and g["per_stratum"][POS]["status"] == G.INSUFFICIENT
    assert g["per_stratum"][LOW]["true"] == 150 and g["per_stratum"][POS]["accepted_tracks"] == 149
    assert g["control_accept_all"]["false"] == 60


def test_precision_gate_window_override_from_the_evaluations(tmp_path):
    rv = review({"A": (299, 0, 0, 0, 299, 30.0)})
    evals = {LOW: loaded(tmp_path, LOW, [ev("A", tp=5, false=3)]), POS: loaded(tmp_path, POS, [ev("B", tp=4)])}
    g = G.gate_precision(rv, None, evals, {LOW: ["A"], POS: ["B"]})
    assert g["status"] == G.FAILED and g["window"]["precision"] == pytest.approx(9 / 12)


def test_precision_gate_not_run_without_review_or_windows():
    assert G.gate_precision(None, None, {LOW: [], POS: []}, {LOW: None, POS: None})["status"] == G.NOT_RUN
    rv = review({"A": (299, 0, 0, 0, 299, 30.0)})
    g = G.gate_precision(rv, None, {LOW: [], POS: None}, {LOW: None, POS: None})
    assert g["status"] == G.NOT_RUN and not g["provisional"] and G.label(g) == "NOT_RUN"


def test_precision_gate_needs_the_selected_point_named_when_ambiguous():
    rv = review({"A": (10, 0, 0, 0, 10, 1.0)})
    rv["points"]["patch_s0_t0.9"] = rv["points"]["rules_q0.01"]
    with pytest.raises(SystemExit):
        G.gate_precision(rv, None, {LOW: [], POS: []}, {LOW: None, POS: None})
    assert G.gate_precision(rv, "patch_s0_t0.9", {LOW: [], POS: []}, {LOW: None, POS: None})["point_id"] == \
        "patch_s0_t0.9"


# Recall ----------------------------------------------------------------------------------------

def test_recall_19_observable_tracks_is_insufficient_with_the_estimate_reported():
    r = G.recall_status(19, 19)
    assert r["status"] == G.INSUFFICIENT and r["recall"] == 1.0


def test_recall_20_observable_tracks_can_pass():
    r = G.recall_status(20, 20)
    assert r["status"] == G.PASSED and r["recall_lower95_two_sided"] >= 0.5


def test_recall_below_target_fails_only_when_measurable():
    assert G.recall_status(9, 20)["status"] == G.FAILED
    assert G.recall_status(5, 19)["status"] == G.INSUFFICIENT


def test_recall_meeting_target_with_a_low_bound_is_insufficient():
    r = G.recall_status(12, 20)
    assert r["status"] == G.INSUFFICIENT and r["recall"] == 0.6 and r["recall_lower95_two_sided"] < 0.5


def test_recall_lower_bound_is_two_sided():
    from scipy import stats

    assert G.recall_status(15, 25)["recall_lower95_two_sided"] == pytest.approx(stats.beta.ppf(0.025, 15, 11))


def test_recall_gate_sums_the_ember_positive_stratum(tmp_path):
    evals = loaded(tmp_path, POS, [ev("B1", matched=8, observable=10), ev("B2", matched=7, observable=10)])
    g = G.gate_recall(evals)
    assert g["matched"] == 15 and g["observable"] == 20 and g["recall"] == 0.75 and g["provisional"]
    assert g["status"] == G.PASSED and g["recall_lower95_two_sided"] == pytest.approx(0.50895, abs=1e-4)
    assert g["per_recording"] == {"B1": {"matched": 8, "observable": 10}, "B2": {"matched": 7, "observable": 10}}
    assert G.gate_recall(None)["status"] == G.NOT_RUN
    assert G.gate_recall([])["status"] == G.INSUFFICIENT


def test_recall_never_reads_proposal_retention(tmp_path):
    e = ev("B1", matched=0, observable=0, proposal_retention=0.97)
    e["track_level"]["proposal_retention"] = 0.97
    e["track_level"]["counts"]["proposal_retention"] = 0.97
    evals = loaded(tmp_path, POS, [e])
    g = G.gate_recall(evals)
    assert g["status"] == G.INSUFFICIENT and g["recall"] is None
    raw = G.load_json(tmp_path / f"{POS}_0.json")
    with pytest.raises(AssertionError):
        raw["proposal_retention"]
    with pytest.raises(AssertionError):
        raw["track_level"]["counts"].get("proposal_retention")


def test_recall_refuses_an_input_without_window_truth(tmp_path):
    p = tmp_path / "selection.json"
    p.write_text(json.dumps({"rows": [{"proposal_retention": 0.9}]}))
    with pytest.raises(SystemExit):
        G.load_evals([str(p)], POS, None, False)


# False alarm -----------------------------------------------------------------------------------

def test_rate_status_branches():
    assert G.rate_status(0.0, 0.05)[0] == G.PASSED
    assert G.rate_status(0.2, 0.5)[0] == G.FAILED
    assert G.rate_status(0.05, 0.3)[0] == G.INSUFFICIENT
    assert G.rate_status(None, None)[0] == G.INSUFFICIENT


def test_false_alarm_gate_uses_the_review_upper_bound(tmp_path):
    rv = review({"A": (300, 0, 0, 0, 300, 40.0), "B": (0, 0, 0, 0, 0, 20.0)})
    evals = {LOW: loaded(tmp_path, LOW, [ev("A", fcount=1, fweight=0.5, minutes=0.5)]), POS: []}
    g = G.gate_false_alarm(rv, None, evals, {LOW: ["A"], POS: ["B"]})
    assert g["status"] == G.PASSED and g["provisional"]
    assert g["review"]["upper95"] == pytest.approx(rv["points"]["rules_q0.01"]["false_per_supported_min_upper95"])
    assert g["review_recomputed"]["upper95"] == pytest.approx(g["review"]["upper95"])
    assert g["window"]["value"] == pytest.approx(1.0) and g["window"]["note"] == "reported, not gated"
    assert g["per_stratum"][POS]["review"]["value"] == 0.0


def test_false_alarm_gate_fails_and_is_insufficient():
    st = {LOW: None, POS: None}
    many = review({"A": (200, 20, 0, 0, 220, 60.0)})
    assert G.gate_false_alarm(many, None, {LOW: None, POS: None}, st)["status"] == G.FAILED
    few = review({"A": (50, 0, 0, 0, 50, 10.0)})
    assert G.gate_false_alarm(few, None, {LOW: None, POS: None}, st)["status"] == G.INSUFFICIENT


def test_false_alarm_with_zero_accepted_tracks():
    st = {LOW: None, POS: None}
    long = review({"A": (0, 0, 0, 0, 0, 60.0)}, control=(5, 5, 0, 0, 30))
    g = G.gate_false_alarm(long, None, {LOW: None, POS: None}, st)
    assert g["status"] == G.PASSED and g["review"]["value"] == 0.0 and g["review"]["upper95"] < 0.1
    short = review({"A": (0, 0, 0, 0, 0, 10.0)}, control=(5, 5, 0, 0, 30))
    assert G.gate_false_alarm(short, None, {LOW: None, POS: None}, st)["status"] == G.INSUFFICIENT
    assert G.gate_false_alarm(None, None, {LOW: None, POS: None}, st)["status"] == G.NOT_RUN


# Separate gates --------------------------------------------------------------------------------

def test_implementation_gate(tmp_path):
    good = tmp_path / "tests.json"
    good.write_text(json.dumps({"passed": 550, "failed": 0, "skipped": 3}))
    log = tmp_path / "pytest.txt"
    log.write_text("....F..\nFAILED tests/test_x.py::test_y\n1 failed, 552 passed, 1 skipped in 464.02s\n")
    cut = tmp_path / "cut.txt"
    cut.write_text("......\n")
    assert G.gate_implementation([str(good)])["status"] == G.PASSED
    assert G.gate_implementation([str(good), str(log)])["status"] == G.FAILED
    assert G.gate_implementation([str(cut)])["status"] == G.FAILED
    assert G.gate_implementation(None)["status"] == G.NOT_RUN
    assert "provisional" not in G.gate_implementation([str(good)])


def test_phone_gate(tmp_path):
    p = tmp_path / "phone_check.json"
    p.write_text(json.dumps({"pass": True, "checks": {"source_identity": {"pass": True}}}))
    assert G.gate_phone(str(p))["status"] == G.PASSED
    p.write_text(json.dumps({"pass": False, "checks": {"same_host_stride": {"pass": False}}}))
    g = G.gate_phone(str(p))
    assert g["status"] == G.FAILED and g["failed_checks"] == ["same_host_stride"]
    assert G.gate_phone(None)["status"] == G.NOT_RUN


def bench(median=29.0, p5=26.0, dec=None, **hp):
    dec = dec or {"status": "MEASURED", "median": 40.0, "p95": 120.0}
    mode = {"paint_fps": {"median": median, "p5": p5}, "publish_to_state_ms": {"p95": 60.0, "decision_frames": dec},
            "rss_mb": {"slope_mb_per_h": 1.0}, "seconds": 300.0, "source_problem": None, **hp}
    return {"note": "Linux container reference only", "modes": {"legacy": dict(mode), "high_precision": mode}}


def test_runtime_gate(tmp_path):
    p = tmp_path / "bench.json"

    def run(rep):
        p.write_text(json.dumps(rep))
        return G.gate_runtime(str(p))

    assert run(bench())["status"] == G.PASSED
    assert run(bench(median=19.0))["status"] == G.FAILED
    assert run(bench(p5=9.0))["status"] == G.FAILED
    assert run(bench(dec={"status": "MEASURED", "p95": 251.0}))["status"] == G.FAILED
    assert run(bench(dec={"status": "NOT_MEASURED", "reason": "no track was accepted"}))["status"] == G.INSUFFICIENT
    assert run(bench(source_problem="synthetic video played"))["status"] == G.INSUFFICIENT
    g = G.gate_runtime(None)
    assert g["status"] == G.NOT_RUN and g["booth_mac"]["status"] == G.NOT_RUN


def test_reliability_gate(tmp_path):
    g = G.gate_reliability(None)
    assert g["status"] == G.FAILED and g["soak"]["status"] == G.FAILED and g["long_soak"]["status"] == G.NOT_RUN
    assert "OVERALL FAIL" in g["soak"]["evidence_text"]
    p = tmp_path / "soak.json"
    p.write_text(json.dumps({"verdict": "PASS", "start": "2026-10-18T22:00:00+08:00"}))
    g = G.gate_reliability(str(p))
    assert g["soak"]["status"] == G.PASSED and g["long_soak"]["status"] == G.NOT_RUN and g["status"] == G.NOT_RUN
    p.write_text(json.dumps({"verdict": "FAIL"}))
    assert G.gate_reliability(str(p))["status"] == G.FAILED


def test_default_promotion_is_never_run():
    g = G.gate_promotion()
    assert g["status"] == G.NOT_RUN and g["promoted"] is False


# The command -----------------------------------------------------------------------------------

def write(tmp_path, name, obj) -> str:
    p = tmp_path / name
    p.write_text(json.dumps(obj) if not isinstance(obj, str) else obj)
    return str(p)


def protocol_yaml(tmp_path, low=("A",), pos=("B",), precision=0.99) -> str:
    import yaml

    proto = {"populations": {"sealed_test": {"recordings": list(low)},
                             "sealed_test_ember_positive": {"recordings": list(pos)}},
             "targets": {"accepted_track_precision": precision, "accepted_track_recall": 0.5,
                         "false_accepted_tracks_per_min": 0.1}}
    return write(tmp_path, "protocol.yaml", yaml.safe_dump(proto))


def test_command_end_to_end(tmp_path):
    rv = write(tmp_path, "review_points.json", review({"A": (150, 0, 0, 0, 150, 40.0), "B": (149, 0, 0, 0, 149, 20.0)},
                                                       control=(50, 50, 0, 0, 900)))
    lo = write(tmp_path, "eval_A.json", ev("A", tp=2, minutes=0.5))
    po = write(tmp_path, "eval_B.json", ev("B", tp=3, matched=12, observable=15, minutes=0.4))
    tests = write(tmp_path, "tests.json", {"passed": 600, "failed": 0})
    phone = write(tmp_path, "phone_check.json", {"pass": True, "checks": {}})
    out = tmp_path / "gates" / "gates.json"
    assert G.main(["--out", str(out), "--protocol", protocol_yaml(tmp_path), "--review", rv,
                   "--eval-low-observability", lo, "--eval-ember-positive", po, "--tests", tests,
                   "--phone-check", phone]) == 0
    rec = json.loads(out.read_text())
    gates = rec["gates"]
    assert gates["precision"]["status"] == G.PASSED and gates["precision"]["provisional"]
    assert gates["precision"]["review_lower95_agrees"] and rec["strata_source"] == {LOW: "protocol", POS: "protocol"}
    assert gates["recall"]["status"] == G.INSUFFICIENT and gates["recall"]["recall"] == 0.8
    assert gates["false_alarm"]["status"] == G.PASSED
    assert gates["implementation"]["status"] == G.PASSED and gates["phone_non_regression"]["status"] == G.PASSED
    assert gates["runtime"]["status"] == G.NOT_RUN and gates["reliability"]["status"] == G.FAILED
    assert gates["default_promotion"]["status"] == G.NOT_RUN
    assert rec["strata"] == {LOW: ["A"], POS: ["B"]} and not rec["dry_run"]
    assert set(rec["inputs"]) >= {"protocol", "review", "eval_low_observability_0", "eval_ember_positive_0"}
    md = out.with_suffix(".md").read_text()
    for word in ("PASSED, PROVISIONAL", "INSUFFICIENT_EVIDENCE, PROVISIONAL", "NOT_RUN", "FAILED"):
        assert word in md
    text = out.read_text() + md
    assert chr(0x2013) not in text and chr(0x2014) not in text     # no en or em dash


def test_command_missing_inputs_are_not_run(tmp_path):
    out = tmp_path / "gates.json"
    assert G.main(["--out", str(out)]) == 0
    gates = json.loads(out.read_text())["gates"]
    for k in ("precision", "recall", "false_alarm", "implementation", "phone_non_regression", "runtime"):
        assert gates[k]["status"] == G.NOT_RUN, k
    assert not gates["precision"]["provisional"]


def test_command_refuses_unsealed_inputs_and_misfiled_strata(tmp_path):
    out = str(tmp_path / "gates.json")
    cal = write(tmp_path, "cal.json", review({"A": (10, 0, 0, 0, 10, 5.0)}, population="calibration"))
    with pytest.raises(SystemExit):
        G.main(["--out", out, "--review", cal])
    assert G.main(["--out", out, "--review", cal, "--allow-unsealed"]) == 0
    assert json.loads((tmp_path / "gates.json").read_text())["dry_run"]
    unsealed = write(tmp_path, "unsealed.json", ev("B", sealed=False))
    with pytest.raises(SystemExit):
        G.main(["--out", out, "--eval-ember-positive", unsealed])
    misfiled = write(tmp_path, "misfiled.json", ev("A"))
    with pytest.raises(SystemExit):
        G.main(["--out", out, "--protocol", protocol_yaml(tmp_path), "--eval-ember-positive", misfiled])
    twice = write(tmp_path, "twice.json", ev("B"))
    with pytest.raises(SystemExit):
        G.main(["--out", out, "--eval-ember-positive", twice, twice])
    with pytest.raises(SystemExit):
        G.main(["--out", out, "--protocol", protocol_yaml(tmp_path, precision=0.95)])
    stray = write(tmp_path, "stray.json", review({"A": (10, 0, 0, 0, 10, 5.0), "Z": (1, 0, 0, 0, 1, 1.0)}))
    with pytest.raises(SystemExit):
        G.main(["--out", out, "--protocol", protocol_yaml(tmp_path), "--review", stray])


def test_command_strata_from_the_evaluations_when_the_protocol_lists_none(tmp_path):
    out = tmp_path / "gates.json"
    rv = write(tmp_path, "review_points.json", review({"A": (100, 0, 0, 0, 100, 30.0), "Z": (5, 0, 0, 0, 5, 1.0)}))
    lo, po = write(tmp_path, "a.json", ev("A")), write(tmp_path, "b.json", ev("B"))
    assert G.main(["--out", str(out), "--review", rv, "--eval-low-observability", lo, "--eval-ember-positive", po]) == 0
    rec = json.loads(out.read_text())
    assert rec["strata"] == {LOW: ["A"], POS: ["B"]}
    assert rec["strata_source"] == {LOW: "evaluations", POS: "evaluations"}
    assert rec["gates"]["precision"]["per_stratum"][LOW]["true"] == 100
    assert rec["gates"]["precision"]["per_stratum"][POS]["status"] == G.FAILED      # no accepted track there
    assert any("Z" in n for n in rec["notes"])
