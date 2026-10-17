"""Gates and status table of the precision verifier's sealed test (protocol precision_20261017).

Frozen before scoring. It computes the protocol's gates from saved results only (it runs and
rescores nothing), applying the protocol's status_rules and gates as written:

    python scripts/precision_gates.py --out results/validation/precision_20261017/gates.json \
        --protocol results/validation/precision_20261017/protocol.yaml \
        --review REVIEW_DIR/review_points.json \
        --eval-low-observability EVAL.json ... --eval-ember-positive EVAL.json ... \
        --tests final_tests.json --phone-check phone_check.json --bench bench.json [--soak soak.json]

Every input is optional; a gate whose input is missing is NOT_RUN. Writes the JSON record to
--out and the status table to --md (default: --out with the suffix .md).

Accuracy gates (agent-only annotation, so every status computed here is also PROVISIONAL):
- precision: the selected point's accepted-track precision on the sealed test, both strata
  pooled, from the blind review (review_points.json of precision_review.py score, primary:
  true / (true + false)). FAILED with zero accepted tracks (precision undefined), or a point
  estimate below 0.99, or a window-judged accepted-track precision (verify eval track_level,
  tp / (tp + false + duplicate) summed over the sealed windows of both strata) below 0.99 over
  at least 10 judged tracks; PASSED when the point estimate and its exact one-sided 95 percent
  Clopper-Pearson lower bound are at least 0.99; otherwise INSUFFICIENT_EVIDENCE (also when
  tracks were accepted but no reviewed one is true or false: the review cannot measure it).
  Reported per stratum too (the review's per-recording counts summed over the stratum).
- recall: matched observable truth tracks over observable truth tracks, summed over the
  ember-positive stratum's verify eval outputs (track_level counts) and nothing else; fewer
  than 20 observable tracks is INSUFFICIENT_EVIDENCE (the estimate is still reported); an
  estimate below 0.5 FAILED; an estimate and two-sided 95 percent Clopper-Pearson lower bound
  of at least 0.5 PASSED; otherwise INSUFFICIENT_EVIDENCE. Proposal retention never counts:
  every JSON input is read through a mapping that refuses a field named with "retention".
- false alarm: the review's false accepted tracks per supported minute (scaled by the inclusion
  probability) and its exact one-sided 95 percent Poisson upper bound, as in review_points.json;
  PASSED when the upper bound is at most 0.1, FAILED when the estimate is above 0.1, otherwise
  INSUFFICIENT_EVIDENCE. The window estimate (verify eval false_tracks_per_min, pooled) is
  reported beside it, not gated.
Separate gates (none stands in for another): implementation (test results, JSON with passed
and failed counts or a pytest log), phone non-regression (phone_check.json pass), runtime
(verify bench JSON, high_precision mode: median paint >= 20 fps, p5 paint >= 10 fps, p95
publish-to-state at decision frames <= 250 ms; a Linux container reference, the booth Mac is
NOT_RUN), reliability (the soak FAILED as the owner's evidence of 2026-10-16 reports, unless a
passing soak report is given; the long soak NOT_RUN) and default promotion (never here:
NOT_RUN, not promoted).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RUN_ID = "precision_20261017"
PASSED, FAILED, NOT_RUN, INSUFFICIENT = "PASSED", "FAILED", "NOT_RUN", "INSUFFICIENT_EVIDENCE"
PROVISIONAL = "PROVISIONAL"
TARGETS = {"accepted_track_precision": 0.99, "accepted_track_recall": 0.50, "false_accepted_tracks_per_min": 0.1}
MIN_WINDOW_JUDGED = 10           # window-judged tracks for the window precision to fail the precision gate
MIN_OBSERVABLE = 20              # observable ember-positive truth tracks for recall to be measurable
RUNTIME = {"paint_fps_median_min": 20.0, "paint_fps_p5_min": 10.0, "decision_publish_to_state_p95_ms_max": 250.0}
SOAK_EVIDENCE = ("results/validation/precision_20261017/environment.json", "external_evidence",
                 "overnight_soak_20261016")
STRATA = {"low_observability": "sealed_test", "ember_positive": "sealed_test_ember_positive"}


class NoRetention(dict):
    """A JSON object that refuses to give a field named with "retention" (proposal retention is a
    development selection aid and never enters a gate)."""

    @staticmethod
    def _check(key) -> None:
        assert "retention" not in str(key).lower(), f"a gate read the field {key!r}: proposal retention never counts"

    def __getitem__(self, key):
        self._check(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._check(key)
        return super().get(key, default)


def load_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_hook=NoRetention)


# Bounds ----------------------------------------------------------------------------------------

def cp_lower_one_sided(k: int, n: int, alpha: float = 0.05) -> float | None:
    """Exact one-sided (1 - alpha) Clopper-Pearson lower bound of k successes in n."""
    from scipy import stats

    if n <= 0:
        return None
    return 0.0 if k <= 0 else float(stats.beta.ppf(alpha, k, n - k + 1))


def cp_lower_two_sided(k: int, n: int, level: float = 0.95) -> float | None:
    """Lower end of the exact two-sided Clopper-Pearson interval at `level`."""
    return cp_lower_one_sided(k, n, (1.0 - level) / 2.0)


def poisson_upper(k: int, alpha: float = 0.05) -> float:
    """Exact one-sided (1 - alpha) Poisson upper bound of a count k."""
    from scipy import stats

    return float(stats.chi2.ppf(1 - alpha, 2 * k + 2) / 2)


# Status rules ----------------------------------------------------------------------------------

def precision_status(accepted: int, true: int, false: int, window_tp: int | None = None,
                     window_n: int | None = None, target: float = TARGETS["accepted_track_precision"]) -> dict:
    """The precision gate's status from reviewed counts and the window-judged counts."""
    n = true + false
    point = true / n if n else None
    low = cp_lower_one_sided(true, n)
    wp = window_tp / window_n if window_n else None
    failed = []
    if accepted <= 0:
        failed.append("zero accepted tracks: precision undefined")
    if point is not None and point < target:
        failed.append(f"reviewed precision {point:.4g} below {target:g}")
    if wp is not None and window_n >= MIN_WINDOW_JUDGED and wp < target:
        failed.append(f"window-judged precision {wp:.4g} below {target:g} over {window_n} judged tracks")
    if failed:
        st, why = FAILED, failed
    elif point is None:
        st, why = INSUFFICIENT, ["accepted tracks were reviewed, but none is true or false: the review cannot measure "
                                 "precision"]
    elif low >= target:
        st, why = PASSED, [f"reviewed precision and its one-sided 95 percent lower bound at least {target:g}"]
    else:
        st, why = INSUFFICIENT, [f"reviewed precision meets {target:g}, its one-sided 95 percent lower bound "
                                 f"{low:.4g} does not"]
    return {"status": st, "reasons": why, "accepted_tracks": int(accepted), "true": int(true), "false": int(false),
            "precision": point, "precision_lower95_one_sided": low,
            "window": {"tp": window_tp, "judged": window_n, "precision": wp,
                       "override_applies": window_n is not None and window_n >= MIN_WINDOW_JUDGED}}


def recall_status(matched: int, observable: int, target: float = TARGETS["accepted_track_recall"]) -> dict:
    """The recall gate's status from the ember-positive stratum's pooled window truth."""
    point = matched / observable if observable else None
    low = cp_lower_two_sided(matched, observable)
    if observable < MIN_OBSERVABLE:
        st, why = INSUFFICIENT, [f"{observable} observable truth tracks, fewer than {MIN_OBSERVABLE}: recall cannot be "
                                 "measured (the estimate is reported)"]
    elif point < target:
        st, why = FAILED, [f"recall {point:.4g} below {target:g}"]
    elif low >= target:
        st, why = PASSED, [f"recall and its two-sided 95 percent lower bound at least {target:g}"]
    else:
        st, why = INSUFFICIENT, [f"recall meets {target:g}, its two-sided 95 percent lower bound {low:.4g} does not"]
    return {"status": st, "reasons": why, "matched": int(matched), "observable": int(observable), "recall": point,
            "recall_lower95_two_sided": low}


def rate_status(value: float | None, upper: float | None,
                target: float = TARGETS["false_accepted_tracks_per_min"]) -> tuple[str, list[str]]:
    """A rate where lower is better: PASSED when the upper bound meets the target, FAILED when the
    estimate misses it, otherwise INSUFFICIENT_EVIDENCE."""
    if value is None:
        return INSUFFICIENT, ["no estimate: the review sampled no accepted track or there are no supported minutes"]
    if value > target:
        return FAILED, [f"estimate {value:.4g} per supported minute above {target:g}"]
    if upper is not None and upper <= target:
        return PASSED, [f"one-sided 95 percent upper bound {upper:.4g} at most {target:g}"]
    return INSUFFICIENT, [f"estimate meets {target:g}, its one-sided 95 percent upper bound "
                          f"{'none' if upper is None else f'{upper:.4g}'} does not"]


# Inputs ----------------------------------------------------------------------------------------

def protocol_strata(proto: dict | None) -> dict[str, list[str] | None]:
    """Each sealed stratum's recordings as the frozen protocol lists them (None when not listed)."""
    pops = (proto or {}).get("populations") or {}
    out = {}
    for name, pop in STRATA.items():
        recs = (pops.get(pop) or {}).get("recordings")
        out[name] = [str(r) for r in recs] if isinstance(recs, list) else None
    return out


def load_evals(paths: list[str] | None, stratum: str, listed: list[str] | None, allow_unsealed: bool) -> list[dict]:
    """verify eval outputs of one stratum: their track_level counts and false-track rates."""
    out, seen = [], set()
    for p in paths or []:
        res = load_json(p)
        tl = res.get("track_level")
        if not tl or "counts" not in tl:
            raise SystemExit(f"{p}: no track_level counts (a verify eval output is needed)")
        proto = res.get("protocol") or {}
        rec = proto.get("recording") or None
        if not proto.get("sealed") and not allow_unsealed:
            raise SystemExit(f"{p}: not a sealed scoring (protocol.sealed is not true); --allow-unsealed for a dry run")
        if listed is not None and rec is not None and rec not in listed:
            raise SystemExit(f"{p}: recording {rec} is not in the protocol's {stratum} stratum")
        if (rec or str(Path(p).resolve())) in seen:
            raise SystemExit(f"{p}: recording {rec} given twice")
        seen.add(rec or str(Path(p).resolve()))
        c, fr = tl["counts"], (tl.get("rates") or {}).get("false_tracks_per_min") or {}
        out.append({"path": str(p), "recording": rec, "stratum": stratum,
                    "tp": int(c["tp"]), "false": int(c["false"]), "duplicate": int(c["duplicate"]),
                    "truth_matched": int(c["truth_matched"]), "truth_observable": int(c["truth_observable"]),
                    "false_count": fr.get("count"), "false_weighted": fr.get("weighted_count", fr.get("count")),
                    "minutes": float(fr.get("minutes") or 0.0)})
    return out


def window_precision(evals: list[dict]) -> tuple[int, int]:
    """tp and judged tracks (tp + false + duplicate, the primary precision's denominator)."""
    return sum(e["tp"] for e in evals), sum(e["tp"] + e["false"] + e["duplicate"] for e in evals)


def window_false_rate(evals: list[dict]) -> dict:
    """Window false accepted tracks per supported minute, pooled: weighted judgments over the
    supported minutes, exact Poisson bounds of the judgment count scaled by the mean weight."""
    k = sum(int(e["false_count"] or 0) for e in evals)
    w = sum(float(e["false_weighted"] or 0.0) for e in evals)
    m = sum(e["minutes"] for e in evals)
    if m <= 0:
        return {"value": None, "count": k, "minutes": m, "upper95": None, "zero_event_upper95": None}
    return {"value": w / m, "count": k, "weighted_count": w, "minutes": m,
            "upper95": poisson_upper(k) * (w / k if k else 1.0) / m, "zero_event_upper95": poisson_upper(0) / m}


def review_point(review: dict, point_id: str | None) -> tuple[str, dict]:
    """The selected point of a sealed review: --point, else its one point other than accept_all."""
    pts = review["points"]
    if point_id is None:
        others = sorted(p for p in pts if p != "accept_all")
        if len(others) != 1:
            raise SystemExit(f"the review has points {sorted(pts)}: name the selected one with --point")
        point_id = others[0]
    if point_id not in pts:
        raise SystemExit(f"the review has no point {point_id!r} (points: {sorted(pts)})")
    return point_id, pts[point_id]


def review_counts(point: dict, recordings: list[str] | None, supported: dict) -> dict:
    """A point's reviewed counts, accepted tracks and supported minutes: pooled (recordings None)
    or summed over the review's per-recording figures of the given recordings."""
    keys = ("true", "false", "ambiguous", "unresolved", "reviewed", "accepted_tracks")
    if recordings is None:
        return {**{k: int(point[k]) for k in keys}, "supported_minutes": float(sum(supported.values()))}
    per = point.get("per_recording") or {}
    out = {k: sum(int(per[r][k]) for r in recordings if r in per) for k in keys}
    out["supported_minutes"] = float(sum(supported.get(r, 0.0) for r in recordings))
    return out


def review_false_rate(c: dict) -> dict:
    """False accepted tracks per supported minute from reviewed counts, as precision_review.py
    scores it: false / inclusion probability / minutes, the Poisson upper bound scaled the same
    way. With no accepted track the rate is 0 with nothing sampled (inclusion probability 1)."""
    m = c["supported_minutes"]
    incl = 1.0 if c["accepted_tracks"] == 0 else c["reviewed"] / c["accepted_tracks"]
    if not incl or m <= 0:
        return {"value": None, "upper95": None, "inclusion_probability": incl, "minutes": m, "false": c["false"]}
    return {"value": c["false"] / incl / m, "upper95": poisson_upper(c["false"]) / incl / m,
            "inclusion_probability": incl, "minutes": m, "false": c["false"]}


# Gates -----------------------------------------------------------------------------------------

def _accuracy(rec: dict) -> dict:
    rec["provisional"] = rec["status"] != NOT_RUN
    return rec


def _not_run(reason: str, accuracy: bool = False) -> dict:
    return {"status": NOT_RUN, "reasons": [reason], **({"provisional": False} if accuracy else {})}


def gate_precision(review: dict | None, point_id: str | None, evals: dict[str, list[dict] | None],
                   strata: dict[str, list[str] | None]) -> dict:
    if review is None:
        return _not_run("no review_points.json given", True)
    if any(evals[s] is None for s in STRATA):
        return _not_run("the window evaluations of both strata are needed (the window override); give "
                        "--eval-low-observability and --eval-ember-positive (an empty list for an empty stratum)", True)
    pid, point = review_point(review, point_id)
    sup = review.get("supported_minutes") or {}
    tp, n = window_precision(evals["low_observability"] + evals["ember_positive"])
    c = review_counts(point, None, sup)
    rec = precision_status(c["accepted_tracks"], c["true"], c["false"], tp, n)
    stored = point.get("precision_lower95")
    low = rec["precision_lower95_one_sided"]
    rec.update(point_id=pid, ambiguous=c["ambiguous"], unresolved=c["unresolved"], reviewed=c["reviewed"],
               inclusion_probability=point.get("inclusion_probability"), review_lower95=stored,
               review_lower95_agrees=(stored is None and low is None) or (stored is not None and low is not None
                                                                          and abs(stored - low) < 1e-9))
    rec["per_stratum"] = {}
    for s in STRATA:
        recs = strata[s]
        if recs is None:
            rec["per_stratum"][s] = {"status": NOT_RUN, "reasons": ["the stratum's recordings are not listed"]}
            continue
        cs = review_counts(point, recs, sup)
        stp, sn = window_precision(evals[s])
        rec["per_stratum"][s] = _accuracy({**precision_status(cs["accepted_tracks"], cs["true"], cs["false"], stp, sn),
                                           "recordings": recs})
    ctl = review["points"].get("accept_all")
    if ctl is not None:
        rec["control_accept_all"] = {k: ctl.get(k) for k in ("accepted_tracks", "reviewed", "true", "false",
                                                             "ambiguous", "unresolved", "precision",
                                                             "precision_lower95")}
    return _accuracy(rec)


def gate_recall(evals: list[dict] | None) -> dict:
    if evals is None:
        return _not_run("no ember-positive verify eval output given (--eval-ember-positive)", True)
    rec = recall_status(sum(e["truth_matched"] for e in evals), sum(e["truth_observable"] for e in evals))
    rec["source"] = "ember-positive stratum window truth only (verify eval track_level counts)"
    rec["per_recording"] = {e["recording"] or e["path"]: {"matched": e["truth_matched"],
                                                          "observable": e["truth_observable"]} for e in evals}
    return _accuracy(rec)


def gate_false_alarm(review: dict | None, point_id: str | None, evals: dict[str, list[dict] | None],
                     strata: dict[str, list[str] | None]) -> dict:
    if review is None:
        return _not_run("no review_points.json given", True)
    pid, point = review_point(review, point_id)
    sup = review.get("supported_minutes") or {}
    c = review_counts(point, None, sup)
    if c["accepted_tracks"] == 0:
        fr = review_false_rate(c)
    else:
        fr = {"value": point.get("false_per_supported_min"), "upper95": point.get("false_per_supported_min_upper95"),
              "inclusion_probability": point.get("inclusion_probability"), "minutes": c["supported_minutes"],
              "false": c["false"]}
    st, why = rate_status(fr["value"], fr["upper95"])
    rec = {"status": st, "reasons": why, "point_id": pid, "review": fr, "review_recomputed": review_false_rate(c),
           "per_stratum": {}}
    given = [e for s in STRATA for e in (evals[s] or [])]
    rec["window"] = {**window_false_rate(given), "note": "reported, not gated"} if given else None
    for s in STRATA:
        recs = strata[s]
        if recs is None:
            rec["per_stratum"][s] = {"status": NOT_RUN, "reasons": ["the stratum's recordings are not listed"]}
            continue
        frs = review_false_rate(review_counts(point, recs, sup))
        sst, swhy = rate_status(frs["value"], frs["upper95"])
        rec["per_stratum"][s] = _accuracy({"status": sst, "reasons": swhy, "review": frs, "recordings": recs,
                                           "window": window_false_rate(evals[s]) if evals[s] else None})
    return _accuracy(rec)


def parse_tests(path: str) -> dict:
    """passed, failed and error counts from a tests JSON or a pytest log's summary line."""
    p = Path(path)
    try:
        d = load_json(p)
    except (json.JSONDecodeError, UnicodeDecodeError):
        d = None
    if isinstance(d, dict):
        if "passed" not in d or "failed" not in d:
            return {"path": path, "summary": None}
        return {"path": path, "summary": "json", "passed": int(d["passed"]), "failed": int(d["failed"]),
                "errors": int(d.get("errors", d.get("error", 0)) or 0), "skipped": int(d.get("skipped", 0) or 0)}
    lines = [ln for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
             if re.search(r"\d+ (passed|failed|errors?)\b", ln)]
    if not lines:
        return {"path": path, "summary": None}
    counts = {w: int(n) for n, w in re.findall(r"(\d+) (passed|failed|errors?|skipped)\b", lines[-1])}
    return {"path": path, "summary": lines[-1].strip(" ="), "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0), "errors": counts.get("error", 0) + counts.get("errors", 0),
            "skipped": counts.get("skipped", 0)}


def gate_implementation(paths: list[str] | None) -> dict:
    if not paths:
        return _not_run("no test results given (--tests)")
    runs = [parse_tests(p) for p in paths]
    bad = [r for r in runs if r["summary"] is None or r["failed"] or r["errors"] or not r["passed"]]
    why = [f"{r['path']}: " + ("no test summary found" if r["summary"] is None else
                               "failures or errors, or nothing passed") for r in bad]
    why = why or ["every given test run passed with no failure or error"]
    return {"status": FAILED if bad else PASSED, "reasons": why, "runs": runs}


def gate_phone(path: str | None) -> dict:
    if path is None:
        return _not_run("no phone_check.json given (--phone-check)")
    d = load_json(path)
    ok = d.get("pass") is True
    failed = sorted(k for k, v in (d.get("checks") or {}).items() if not (v or {}).get("pass"))
    return {"status": PASSED if ok else FAILED, "reasons": ["phone_check.json pass"] if ok else
            [f"phone_check.json fails: {', '.join(failed) or 'pass is not true'}"],
            "path": path, "git_commit": d.get("git_commit"), "created": d.get("created"), "failed_checks": failed}


def gate_runtime(path: str | None) -> dict:
    booth = {"status": NOT_RUN, "reasons": ["the booth Mac is not measured in this task"]}
    if path is None:
        return {**_not_run("no verify bench report given (--bench)"), "booth_mac": booth}
    d = load_json(path)
    hp = (d.get("modes") or {}).get("high_precision")
    rec = {"path": path, "note": d.get("note"), "criteria": RUNTIME, "booth_mac": booth,
           "legacy": _runtime_figures((d.get("modes") or {}).get("legacy"))}
    if hp is None:
        return {**rec, "status": INSUFFICIENT, "reasons": ["the bench report has no high_precision mode"]}
    if hp.get("error"):
        return {**rec, "status": FAILED, "reasons": [f"the high_precision run failed: {hp['error']}"]}
    fig = _runtime_figures(hp)
    rec["high_precision"] = fig
    if hp.get("source_problem"):
        return {**rec, "status": INSUFFICIENT, "reasons": [f"not the source's numbers: {hp['source_problem']}"]}
    checks = {"paint_fps_median": (fig["paint_fps_median"], RUNTIME["paint_fps_median_min"], True),
              "paint_fps_p5": (fig["paint_fps_p5"], RUNTIME["paint_fps_p5_min"], True),
              "decision_publish_to_state_p95_ms": (fig["decision_publish_to_state_p95_ms"],
                                                   RUNTIME["decision_publish_to_state_p95_ms_max"], False)}
    res = {k: NOT_RUN if v is None else (PASSED if (v >= lim if hi else v <= lim) else FAILED)
           for k, (v, lim, hi) in checks.items()}
    rec["checks"] = res
    if FAILED in res.values():
        st = FAILED
    elif NOT_RUN in res.values():
        st = INSUFFICIENT
    else:
        st = PASSED
    why = [f"{k}: {v} ({'not measured' if checks[k][0] is None else checks[k][0]})" for k, v in res.items()]
    if fig.get("decision_status") not in (None, "MEASURED"):
        why.append(f"decision frames: {fig.get('decision_reason')}")
    return {**rec, "status": st, "reasons": why}


def _runtime_figures(m: dict | None) -> dict | None:
    if not m or m.get("error"):
        return None
    pf = m.get("paint_fps") or {}
    dec = (m.get("publish_to_state_ms") or {}).get("decision_frames") or {}
    return {"paint_fps_median": pf.get("median"), "paint_fps_p5": pf.get("p5"),
            "decision_publish_to_state_p95_ms": dec.get("p95") if dec.get("status") == "MEASURED" else None,
            "decision_status": dec.get("status"), "decision_reason": dec.get("reason"),
            "publish_to_state_p95_ms": (m.get("publish_to_state_ms") or {}).get("p95"),
            "rss_slope_mb_per_h": (m.get("rss_mb") or {}).get("slope_mb_per_h"), "seconds": m.get("seconds")}


def gate_reliability(path: str | None) -> dict:
    long_soak = {"status": NOT_RUN, "reasons": ["no long soak was run"]}
    if path is not None:
        d = load_json(path)
        ok = str(d.get("verdict", "")).upper() == "PASS"
        soak = {"status": PASSED if ok else FAILED, "reasons": [f"soak report verdict {d.get('verdict')!r}"],
                "path": path, "start": d.get("start")}
    else:
        ev = ROOT / SOAK_EVIDENCE[0]
        quoted = ((json.loads(ev.read_text(encoding="utf-8")).get(SOAK_EVIDENCE[1]) or {}).get(SOAK_EVIDENCE[2])
                  if ev.is_file() else None)
        soak = {"status": FAILED, "reasons": ["carried forward: the owner's overnight soak of 2026-10-16 is OVERALL "
                                              "FAIL and no new passing soak report is given"],
                "evidence": f"{SOAK_EVIDENCE[0]} ({'/'.join(SOAK_EVIDENCE[1:])})", "evidence_text": quoted}
    st = FAILED if soak["status"] == FAILED else NOT_RUN
    return {"status": st, "reasons": soak["reasons"] + long_soak["reasons"], "soak": soak, "long_soak": long_soak}


def gate_promotion() -> dict:
    return {"status": NOT_RUN, "promoted": False,
            "reasons": ["the high-precision verifier stays opt-in; the default is never promoted by this run"]}


# Record and table ------------------------------------------------------------------------------

def compute(review: dict | None, point_id: str | None, evals: dict[str, list[dict] | None],
            strata: dict[str, list[str] | None], tests: list[str] | None = None, phone: str | None = None,
            bench: str | None = None, soak: str | None = None) -> dict:
    """Every gate from loaded inputs (see the module notes)."""
    return {"precision": gate_precision(review, point_id, evals, strata),
            "recall": gate_recall(evals["ember_positive"]),
            "false_alarm": gate_false_alarm(review, point_id, evals, strata),
            "implementation": gate_implementation(tests), "phone_non_regression": gate_phone(phone),
            "runtime": gate_runtime(bench), "reliability": gate_reliability(soak),
            "default_promotion": gate_promotion()}


def label(g: dict) -> str:
    return g["status"] + (f", {PROVISIONAL}" if g.get("provisional") else "")


def _f(x, nd: int = 4) -> str:
    return "n/a" if x is None else (f"{x:.{nd}g}" if isinstance(x, float) else str(x))


def table_rows(gates: dict) -> list[list[str]]:
    """Rows of the status table: gate, status, estimate, bound, basis."""
    p, r, fa = gates["precision"], gates["recall"], gates["false_alarm"]
    rows = []

    def prec_row(name: str, g: dict) -> list[str]:
        if g["status"] == NOT_RUN:
            return [name, label(g), "", "", "; ".join(g["reasons"])]
        w = g["window"]
        basis = (f"{g['true']} true, {g['false']} false of {g['accepted_tracks']} accepted; window-judged "
                 f"{_f(w['precision'])} over {w['judged']} tracks")
        bound = f"one-sided 95% lower {_f(g['precision_lower95_one_sided'])}"
        return [name, label(g), _f(g["precision"]), bound, basis]

    rows.append(prec_row("precision (sealed test, both strata pooled)", p))
    for s, g in (p.get("per_stratum") or {}).items():
        rows.append(prec_row(f"precision, {s.replace('_', '-')} stratum (reported)", g))
    if r["status"] == NOT_RUN:
        rows.append(["recall (ember-positive stratum)", label(r), "", "", "; ".join(r["reasons"])])
    else:
        rows.append(["recall (ember-positive stratum)", label(r), _f(r["recall"]),
                     f"two-sided 95% lower {_f(r['recall_lower95_two_sided'])}",
                     f"{r['matched']} of {r['observable']} observable truth tracks matched"])

    def fa_row(name: str, g: dict) -> list[str]:
        if g["status"] == NOT_RUN:
            return [name, label(g), "", "", "; ".join(g["reasons"])]
        v, w = g["review"], g.get("window")
        basis = f"{v['false']} false reviewed, inclusion {_f(v['inclusion_probability'])}, {_f(v['minutes'])} min"
        if w:
            basis += f"; window {_f(w['value'])} per min (upper {_f(w['upper95'])}, not gated)"
        return [name, label(g), f"{_f(v['value'])} per supported min", f"one-sided 95% upper {_f(v['upper95'])}",
                basis]

    rows.append(fa_row("false alarm (sealed test, review)", fa))
    for s, g in (fa.get("per_stratum") or {}).items():
        rows.append(fa_row(f"false alarm, {s.replace('_', '-')} stratum (reported)", g))
    im = gates["implementation"]
    rows.append(["implementation", label(im), "; ".join(f"{x.get('passed')} passed, {x.get('failed')} failed"
                                                       for x in im.get("runs", [])), "", "; ".join(im["reasons"])])
    ph = gates["phone_non_regression"]
    rows.append(["phone non-regression", label(ph), "", "", "; ".join(ph["reasons"])])
    rt = gates["runtime"]
    hp = rt.get("high_precision") or {}
    rows.append(["runtime (Linux container reference)", label(rt),
                 f"paint median {_f(hp.get('paint_fps_median'))} fps, p5 {_f(hp.get('paint_fps_p5'))} fps, "
                 f"decision p95 {_f(hp.get('decision_publish_to_state_p95_ms'))} ms" if hp else "",
                 ">= 20 fps, >= 10 fps, <= 250 ms", "; ".join(rt["reasons"])])
    rows.append(["runtime (booth Mac)", label(rt["booth_mac"]), "", "", "; ".join(rt["booth_mac"]["reasons"])])
    rl = gates["reliability"]
    rows.append(["reliability (soak)", label(rl["soak"]), "", "", "; ".join(rl["soak"]["reasons"])])
    rows.append(["reliability (long soak)", label(rl["long_soak"]), "", "", "; ".join(rl["long_soak"]["reasons"])])
    dp = gates["default_promotion"]
    rows.append(["default promotion", label(dp), "not promoted", "", "; ".join(dp["reasons"])])
    return rows


def markdown(rec: dict) -> str:
    head = [f"# Gates of {RUN_ID}", "",
            f"Computed {rec['created']} from saved results by scripts/precision_gates.py "
            f"(sha256 {rec['script_sha256'][:16]}).", ""]
    if rec["dry_run"]:
        head += ["DRY RUN: inputs that are not the sealed test were allowed (--allow-unsealed); not a gate result.", ""]
    head += ["Statuses: PASSED, FAILED, NOT_RUN, INSUFFICIENT_EVIDENCE; PROVISIONAL marks every accuracy status "
             "that rests on agent-only annotation (all of them here). The gates are separate: none stands in "
             "for another.", "", "| Gate | Status | Estimate | Bound | Basis |", "|---|---|---|---|---|"]
    body = ["| " + " | ".join(c.replace("|", "/") for c in row) + " |" for row in rec["table"]]
    return "\n".join(head + body) + "\n"


def main(argv: list[str] | None = None) -> int:
    import yaml

    from wfglink.provenance import git_state, now_shanghai, sha256_file

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="gates JSON")
    ap.add_argument("--md", default=None, help="status table (default: --out with the suffix .md)")
    ap.add_argument("--protocol", default=None, help="the frozen protocol (strata recordings, targets checked)")
    ap.add_argument("--review", default=None, help="the sealed test's review_points.json")
    ap.add_argument("--point", default=None, help="the selected point's id (default: the one point but accept_all)")
    ap.add_argument("--eval-low-observability", nargs="*", default=None, help="verify eval outputs of that stratum")
    ap.add_argument("--eval-ember-positive", nargs="*", default=None, help="verify eval outputs of that stratum")
    ap.add_argument("--tests", nargs="+", default=None, help="test results: JSON (passed, failed) or a pytest log")
    ap.add_argument("--phone-check", default=None, help="phone_check.json")
    ap.add_argument("--bench", default=None, help="verify bench report JSON")
    ap.add_argument("--soak", default=None, help="a new soak report JSON (verdict PASS or FAIL)")
    ap.add_argument("--allow-unsealed", action="store_true", help="dry run on inputs that are not the sealed test")
    a = ap.parse_args(argv)
    proto = yaml.safe_load(Path(a.protocol).read_text(encoding="utf-8")) if a.protocol else None
    if proto is not None:
        have = {k: (proto.get("targets") or {}).get(k) for k in TARGETS}
        if have != TARGETS:
            raise SystemExit(f"the protocol's targets {have} are not the frozen targets {TARGETS}")
    strata = protocol_strata(proto)
    source = {s: "protocol" if strata[s] is not None else None for s in STRATA}
    evals = {"low_observability": a.eval_low_observability, "ember_positive": a.eval_ember_positive}
    loaded = {s: None if evals[s] is None else load_evals(evals[s], s, strata[s], a.allow_unsealed) for s in STRATA}
    for s in STRATA:                    # strata not listed by the protocol: the recordings of their evaluations
        if strata[s] is None and loaded[s] and all(e["recording"] for e in loaded[s]):
            strata[s], source[s] = sorted(e["recording"] for e in loaded[s]), "evaluations"
    review = load_json(a.review) if a.review else None
    if review is not None and review.get("population") != "test" and not a.allow_unsealed:
        raise SystemExit(f"{a.review}: population {review.get('population')!r}, not the sealed test; "
                         "--allow-unsealed for a dry run")
    outside = sorted(set((review or {}).get("supported_minutes") or {})
                     - {r for s in STRATA for r in (strata[s] or [])})
    if outside and all(source[s] == "protocol" for s in STRATA):
        raise SystemExit(f"{a.review}: recordings outside both sealed strata: {outside}")
    gates = compute(review, a.point, loaded, strata, a.tests, a.phone_check, a.bench, a.soak)
    files = {"protocol": a.protocol, "review": a.review, "phone_check": a.phone_check, "bench": a.bench,
             "soak": a.soak, **{f"tests_{i}": p for i, p in enumerate(a.tests or [])},
             **{f"eval_{s}_{i}": p for s in STRATA for i, p in enumerate(evals[s] or [])}}
    rec = {"schema_version": 1, "run_id": RUN_ID, "created": now_shanghai(), **git_state(),
           "script_sha256": sha256_file(Path(__file__)), "dry_run": bool(a.allow_unsealed),
           "inputs": {k: {"path": str(p), "sha256": sha256_file(p)} for k, p in files.items() if p},
           "targets": TARGETS, "strata": strata, "strata_source": source, "gates": gates}
    rec["table"] = table_rows(gates)
    rec["notes"] = ["agent-only annotation and review: every accuracy status computed here is PROVISIONAL",
                    "the contingency rule (fewer than 3 sealed-test recordings decode) is not evaluated here",
                    "the review's supported minutes cover every scored recording of its sample.json (tracking-only "
                    "recordings left out), from hp_frames motion_unsupported"]
    if outside:
        rec["notes"].append(f"reviewed recordings in no listed stratum (left out of the per-stratum figures): "
                            f"{outside}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8")
    md = Path(a.md) if a.md else out.with_suffix(".md")
    md.write_text(markdown(rec), encoding="utf-8")
    print(markdown(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
